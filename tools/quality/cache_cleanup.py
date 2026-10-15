"""Preview or explicitly retire unreferenced embedding cache, without a DB copy.

Dry-run is the default. Apply requires the unchanged reviewed plan and a separate
small receipt. User-query and retired-run cache reuse is intentionally lost for
rows not referenced by any supported ready run or shared method record.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

try:
    from .common import ROOT, canonical_hash, open_source, read_bounded_json, write_bounded_json, protected_output
    from .cache_audit import embedding_contract
except ImportError:
    from common import ROOT, canonical_hash, open_source, read_bounded_json, write_bounded_json, protected_output
    from cache_audit import embedding_contract

from tools.storage import preflight, GiB, StorageError
from tools.foundation.common import REQUIRED_COMPONENTS

PAYLOAD_BLOCK_BYTES = 64 * 1024


class CleanupCommittedError(ValueError):
    """Deletion committed, but physical shrinking or final verification failed."""
    def __init__(self, report):
        self.report = report
        super().__init__(report['error'])


def _file_state(path):
    path = Path(path)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            digest.update(block)
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != \
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError('File changed while hashing: ' + str(path))
    return {'bytes': after.st_size, 'sha256': digest.hexdigest(),
            'mtime_ns': after.st_mtime_ns, 'inode': after.st_ino, 'device': after.st_dev}


def _cache_state(path):
    # SHM is coordination metadata; WAL carries committed vectors. Apply uses
    # rollback journalling only, avoiding implicit checkpoint/migration changes.
    result = {'main': _file_state(path)}
    wal = Path(str(path) + '-wal')
    if wal.is_file():
        result['wal'] = _file_state(wal)
    return result


def _connect(path, readonly=True):
    db = sqlite3.connect(Path(path).resolve().as_uri() + ('?mode=ro' if readonly else '?mode=rw'), uri=True, timeout=10)
    if readonly:
        db.execute('PRAGMA query_only=ON')
    db.execute('PRAGMA temp_store=MEMORY')
    return db


def _retention(db_path, current_run):
    """Exact actual inputs from every ready run, plus all shared methods."""
    source = open_source(db=db_path, run_id=current_run)
    try:
        db = source.db
        version = db.execute('PRAGMA data_version').fetchone()[0]
        runs = [dict(row) for row in db.execute('SELECT run_id,status,input_fingerprint,manifest_json FROM runs ORDER BY run_id')]
        if not runs or any(row['status'] != 'ready' for row in runs):
            raise ValueError('All supported database runs must be ready; building/stale runs refuse cleanup')
        run_ids = {row['run_id'] for row in runs}
        if current_run not in run_ids:
            raise ValueError('Designated current run is not ready')
        components = [dict(row) for row in db.execute('SELECT * FROM run_components ORDER BY run_id,component')]
        states = {(row['run_id'], row['component']): row['status'] for row in components}
        folders = {str(source.run_dir)}
        if any(row['status'] == 'building' for row in components):
            raise ValueError('A component is building; refuse concurrent cache cleanup')
        for rid in sorted(run_ids):
            if any(states.get((rid, name)) != 'ready' for name in REQUIRED_COMPONENTS):
                raise ValueError('Keyword generation is missing/stale for ready run: ' + rid)
            if rid != current_run:
                other = open_source(db=db_path, run_id=rid)
                folders.add(str(other.run_dir))
                other.close()
        contract = embedding_contract()
        current, all_ready = set(), set()
        counts = Counter()
        for row in runs:
            manifest = json.loads(row['manifest_json'])
            corpus = manifest.get('params', {}).get('corpus_dir')
            if corpus:
                folders.add(str(Path(corpus).resolve()))
        input_digest = hashlib.sha256()
        def remember(text, dim, collection, rid, shared=False):
            if not isinstance(text, str):
                raise ValueError('Embedding input is not text')
            h = hashlib.sha256(contract['prepare'](text).encode('utf-8')).hexdigest()
            key = (h, contract['model'], dim)
            all_ready.add(key)
            if shared or rid == current_run:
                current.add(key)
            counts[collection + ('/shared' if shared else '/current' if rid == current_run else '/historical')] += 1
            input_digest.update((canonical_hash([rid, collection, key]) + '\n').encode())
        for row in db.execute('SELECT id,run_id,collection,title,text FROM text_records ORDER BY collection,id'):
            shared = row['collection'] == 'methods'
            if not shared and row['run_id'] not in run_ids:
                raise ValueError('Non-method text record is unbound to a supported ready run')
            if not isinstance(row['title'], str) or not isinstance(row['text'], str):
                raise ValueError('Embedding title/text is malformed')
            remember(row['title'] + '\n' + row['text'], contract['text_dim'], row['collection'], row['run_id'], shared)
        for row in db.execute('SELECT id,run_id,passage FROM edge_passages ORDER BY id'):
            if row['run_id'] not in run_ids:
                raise ValueError('Edge passage is unbound to a supported ready run')
            remember(row['passage'], contract['edge_dim'], 'edge_passages', row['run_id'])
        if db.execute('PRAGMA data_version').fetchone()[0] != version:
            raise ValueError('Database changed while computing retention inputs')
        state = {'run_ids': sorted(run_ids),
                 'run_input_fingerprints': {r['run_id']: r['input_fingerprint'] for r in runs},
                 'run_metadata_sha256': canonical_hash(runs), 'component_metadata_sha256': canonical_hash(components),
                 'actual_inputs_sha256': input_digest.hexdigest(),
                 'prepare_code_sha256': contract['code_sha256'], 'edge_code_sha256': contract['edge_code_sha256'],
                 'model': contract['model'], 'text_dim': contract['text_dim'], 'edge_dim': contract['edge_dim']}
        return {'current': current, 'all_ready': all_ready, 'state': state,
                'retained_keys_sha256': canonical_hash(sorted(all_ready)), 'counts': dict(counts),
                'source_folders': sorted(folders)}
    finally:
        source.close()


def _blob_hash(cache, rowid, size, storage_type):
    """Read through SQLite's lock-aware VFS, at most 64 KiB at a time."""
    digest = hashlib.sha256()
    if storage_type == 'null':
        return digest.hexdigest()
    if storage_type != 'blob':
        raise ValueError('Cache vector must use BLOB storage (or NULL), not ' + str(storage_type))
    if not hasattr(cache, 'blobopen'):
        raise ValueError('Cache cleanup requires sqlite3 incremental BLOB reading')
    with cache.blobopen('emb', 'v', rowid, readonly=True) as blob:
        if len(blob) != size:
            raise ValueError('SQLite vector length changed during content verification')
        for block in iter(lambda: blob.read(PAYLOAD_BLOCK_BYTES), b''):
            digest.update(block)
    return digest.hexdigest()


def _scan_cache(cache, retention):
    """Fingerprint rowids, metadata and bounded BLOB streams; choose delete ids.

    Raw file reads cannot cross SQLite's Windows lock-byte page while an
    exclusive transaction is held. SQLite's own BLOB reader handles that page.
    VACUUM can renumber rowids, so the retained payload fingerprint separately
    hashes a sorted multiset of logical row hashes, without rowids.
    """
    columns = {r[1] for r in cache.execute('PRAGMA table_info(emb)')}
    if not {'h', 'model', 'dim', 'v'} <= columns:
        raise ValueError('Cache must have an emb(h,model,dim,v) table')
    totals = Counter()
    all_digest, keep_digest = hashlib.sha256(), hashlib.sha256()
    content_digest, keep_content_digest = hashlib.sha256(), hashlib.sha256()
    keep_payload_rows = []
    delete_ids = []
    for rowid, h, model, dim, size, storage_type in cache.execute(
            'SELECT rowid,h,model,dim,LENGTH(v),typeof(v) FROM emb ORDER BY h,model,dim,rowid'):
        item = [h, model, dim, size]
        encoded = (canonical_hash(item) + '\n').encode()
        all_digest.update(encoded)
        payload_hash = _blob_hash(cache, rowid, size, storage_type)
        logical_row_hash = canonical_hash([h, model, dim, size, storage_type, payload_hash])
        content_encoded = (canonical_hash([rowid, logical_row_hash]) + '\n').encode()
        content_digest.update(content_encoded)
        totals['cache_rows'] += 1
        totals['cache_payload_bytes'] += size or 0
        key = (h, model, dim)
        if key in retention['all_ready']:
            keep_digest.update(encoded)
            keep_content_digest.update(content_encoded)
            keep_payload_rows.append(logical_row_hash)
            totals['retained_rows'] += 1
            totals['retained_payload_bytes'] += size or 0
            kind = 'current' if key in retention['current'] else 'historical_ready_only'
            totals[kind + '_rows'] += 1
            totals[kind + '_payload_bytes'] += size or 0
            if not isinstance(dim, int) or dim <= 0 or size != dim * 4:
                totals['referenced_invalid_shape_rows'] += 1
        else:
            delete_ids.append(rowid)
            totals['unreferenced_rows'] += 1
            totals['unreferenced_payload_bytes'] += size or 0
    for name in ('cache_rows', 'cache_payload_bytes', 'retained_rows', 'retained_payload_bytes',
                 'current_rows', 'current_payload_bytes', 'historical_ready_only_rows',
                 'historical_ready_only_payload_bytes', 'referenced_invalid_shape_rows',
                 'unreferenced_rows', 'unreferenced_payload_bytes'):
        totals[name] += 0
    keep_payload_digest = hashlib.sha256()
    for row_hash in sorted(keep_payload_rows):
        keep_payload_digest.update((row_hash + '\n').encode())
    return {'totals': dict(totals), 'metadata_sha256': all_digest.hexdigest(),
            'retained_metadata_sha256': keep_digest.hexdigest(),
            'content_sha256': content_digest.hexdigest(),
            'retained_content_sha256': keep_content_digest.hexdigest(),
            'retained_payload_sha256': keep_payload_digest.hexdigest(), 'delete_ids': delete_ids}


def preview(db_path, cache_path, current_run):
    db_path, cache_path = Path(db_path).resolve(), Path(cache_path).resolve()
    if db_path == cache_path:
        raise ValueError('Cache cannot be the formal source database')
    before = _cache_state(cache_path)
    retention = _retention(db_path, current_run)
    cache = _connect(cache_path)
    try:
        cache.execute('BEGIN')
        scan = _scan_cache(cache, retention)
        mode = cache.execute('PRAGMA journal_mode').fetchone()[0]
    finally:
        cache.close()
    if _cache_state(cache_path) != before:
        raise ValueError('Cache changed while preparing preview')
    # A second exact input pass catches changed formal DB generations.
    if _retention(db_path, current_run)['state'] != retention['state']:
        raise ValueError('Inputs changed while preparing preview')
    plan = {'schema': 'embedding_cache_cleanup_plan_v2', 'mode': 'dry_run', 'run_id': current_run,
            'db_path': str(db_path), 'cache_path': str(cache_path), 'source_folders': retention['source_folders'],
            'input_state': retention['state'], 'embedding_input_counts': retention['counts'],
            'retained_keys_sha256': retention['retained_keys_sha256'],
            'retained_key_count': len(retention['all_ready']), 'cache_state': before,
            'cache_metadata_sha256': scan['metadata_sha256'],
            'retained_cache_metadata_sha256': scan['retained_metadata_sha256'],
            'cache_content_sha256': scan['content_sha256'],
            'retained_cache_content_sha256': scan['retained_content_sha256'],
            'retained_payload_sha256': scan['retained_payload_sha256'],
            'content_fingerprint_protocol': 'sql-incremental-blob-v1; rowid+key+type+length+blob-sha; retained logical multiset ignores VACUUM rowid changes',
            'cache_journal_mode': mode, **scan['totals'],
            'estimated_temporary_peak_bytes': 2 * before['main']['bytes'] + 64 * 1024**2,
            'policy': 'Keep actual current/shared-method and all supported ready-run inputs; retire all other derived/query cache rows.',
            'query_history_tradeoff': 'Unreferenced rows may include paid query/variant cache or retired-run/model cache. Apply intentionally removes that reuse value; there is no independent query-purpose annotation.',
            'space_note': 'Payload lengths are not exact allocated disk bytes. DELETE is transactional; VACUUM shrinks the only cache DB using bounded temporary scratch, without a persistent cache copy.'}
    plan['plan_hash'] = canonical_hash(plan)
    return plan


def _verify_plan(plan):
    if plan.get('schema') != 'embedding_cache_cleanup_plan_v2' or plan.get('mode') != 'dry_run':
        raise ValueError('Apply needs a fresh v2 dry-run plan with SQL payload fingerprints')
    if plan.get('plan_hash') != canonical_hash({k: v for k, v in plan.items() if k != 'plan_hash'}):
        raise ValueError('Dry-run plan hash is invalid')
    for name in ('cache_content_sha256', 'retained_cache_content_sha256', 'retained_payload_sha256'):
        value = plan.get(name)
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Dry-run plan lacks a valid SQL content fingerprint: ' + name)


def _verify_retention(db_path, current_run, expected):
    fresh = _retention(db_path, current_run)
    if fresh['state'] != expected['input_state'] or fresh['retained_keys_sha256'] != expected['retained_keys_sha256']:
        raise ValueError('Inputs changed after the reviewed retention plan')
    return fresh


def _output(path, plan, inputs=()):
    target = protected_output(path, [plan['db_path'], plan['cache_path'], *inputs,
                                   plan['db_path'] + '-wal', plan['db_path'] + '-shm',
                                   plan['cache_path'] + '-wal', plan['cache_path'] + '-shm'])
    if target.suffix != '.json':
        raise ValueError('Cache plan/receipt output must be a .json report')
    for folder in plan['source_folders']:
        folder = Path(folder).resolve()
        if target == folder or folder in target.parents:
            raise ValueError('Cache receipts must be outside source run/corpus directories')
    return target


def apply_plan(db_path, cache_path, current_run, plan, receipt_path, max_project_bytes=12 * GiB):
    _verify_plan(plan)
    cache_path, db_path = Path(cache_path).resolve(), Path(db_path).resolve()
    if str(cache_path) != plan['cache_path'] or str(db_path) != plan['db_path'] or current_run != plan['run_id']:
        raise ValueError('Reviewed plan belongs to another database/cache/run')
    literal = Path(plan['cache_path']).absolute()
    if ROOT not in literal.parents or literal.stat().st_nlink != 1:
        raise ValueError('Writable cache must be an exclusively held file inside this project')
    for ancestor in [literal, *list(literal.parents)[:list(literal.parents).index(ROOT) + 1]]:
        st = ancestor.lstat()
        if ancestor.is_symlink() or getattr(st, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Writable cache must not follow links or junctions')
    target = _output(receipt_path, plan)
    if _cache_state(cache_path) != plan['cache_state']:
        raise ValueError('Cache changed after the reviewed plan')
    retention = _verify_retention(db_path, current_run, plan)
    budget = preflight(ROOT, plan['estimated_temporary_peak_bytes'], max_project_bytes=max_project_bytes)
    report = {'schema': 'embedding_cache_cleanup_receipt_v2', 'status': 'prepared',
              'plan_hash': plan['plan_hash'], 'db_path': str(db_path), 'cache_path': str(cache_path),
              'run_id': current_run, 'before_cache_state': plan['cache_state'],
              'before_counts': {k: plan[k] for k in ('cache_rows', 'cache_payload_bytes', 'retained_rows',
                    'retained_payload_bytes', 'unreferenced_rows', 'unreferenced_payload_bytes')},
              'retained_keys_sha256': plan['retained_keys_sha256'], 'input_state': plan['input_state'],
              'before_cache_content_sha256': plan['cache_content_sha256'],
              'retained_payload_sha256': plan['retained_payload_sha256'],
              'storage_preflight': budget, 'query_history_tradeoff': plan['query_history_tradeoff']}
    write_bounded_json(target, report, inputs=[db_path, cache_path])
    cache = _connect(cache_path, readonly=False)
    committed = False
    failure = None
    try:
        if cache.execute('PRAGMA journal_mode').fetchone()[0] != 'delete':
            raise ValueError('Apply requires rollback DELETE journalling; no implicit WAL migration')
        # Retain the exclusive lock across commit, SQL verification and VACUUM.
        # Physical-file SHA is checked before this connection and after close;
        # reading it here fails at Windows' 1 GiB lock-byte page on large DBs.
        cache.execute('PRAGMA locking_mode=EXCLUSIVE')
        cache.execute('BEGIN EXCLUSIVE')
        scan = _scan_cache(cache, retention)
        if scan['metadata_sha256'] != plan['cache_metadata_sha256'] or scan['totals']['unreferenced_rows'] != plan['unreferenced_rows']:
            raise ValueError('Cache metadata no longer matches reviewed plan')
        if scan['content_sha256'] != plan['cache_content_sha256']:
            raise ValueError('Cache contents changed before exclusive delete transaction')
        removed = 0
        ids = scan['delete_ids']
        for start in range(0, len(ids), 500):
            batch = ids[start:start + 500]
            removed += cache.execute('DELETE FROM emb WHERE rowid IN (' + ','.join('?' * len(batch)) + ')', batch).rowcount
        if removed != plan['unreferenced_rows']:
            raise ValueError('Deleted cache row count disagrees with the reviewed plan')
        after_delete = _scan_cache(cache, retention)
        if after_delete['metadata_sha256'] != plan['retained_cache_metadata_sha256'] or \
                after_delete['content_sha256'] != plan['retained_cache_content_sha256'] or \
                after_delete['retained_payload_sha256'] != plan['retained_payload_sha256'] or after_delete['totals']['unreferenced_rows']:
            raise ValueError('Retained cache rows differ; rollback deletion')
        _verify_retention(db_path, current_run, plan)
        cache.commit()
        committed = True
        report['status'] = 'delete_committed'
        report['deleted_rows'] = removed
        report['deleted_payload_bytes'] = plan['unreferenced_payload_bytes']
        write_bounded_json(target, report, inputs=[db_path, cache_path])
        # VACUUM cannot run within DELETE's transaction. Verify again before its
        # independent exclusive rebuild; a failure here does not undo DELETE.
        _verify_retention(db_path, current_run, plan)
        before_vacuum = _scan_cache(cache, retention)
        if before_vacuum['metadata_sha256'] != plan['retained_cache_metadata_sha256'] or \
                before_vacuum['content_sha256'] != plan['retained_cache_content_sha256']:
            raise ValueError('Cache changed between committed delete and VACUUM')
        cache.execute('VACUUM')
        if cache.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Compacted cache failed quick_check')
        final = _scan_cache(cache, retention)
        if final['metadata_sha256'] != plan['retained_cache_metadata_sha256'] or \
                final['retained_payload_sha256'] != plan['retained_payload_sha256']:
            raise ValueError('Cache changed during VACUUM/final verification')
        _verify_retention(db_path, current_run, plan)
        report.update(status='complete', after_counts=final['totals'],
                      after_cache_content_sha256=final['content_sha256'],
                      after_retained_payload_sha256=final['retained_payload_sha256'])
    except BaseException as exc:
        failure = exc
        if not committed:
            cache.rollback()
            report.update(status='aborted_delete_rolled_back', error=str(exc))
        else:
            report.update(status='delete_committed_vacuum_or_verification_failed', error=str(exc))
    finally:
        cache.close()
    # Closing releases Windows' exclusive byte-range lock. Both success and
    # failure receipts must compute physical SHA only after that release.
    try:
        report['after_cache_state'] = _cache_state(cache_path)
        report['main_file_length_reduction_bytes'] = plan['cache_state']['main']['bytes'] - report['after_cache_state']['main']['bytes']
    except BaseException as exc:
        if failure is None:
            failure = exc
            report.update(status='delete_committed_vacuum_or_verification_failed' if committed else 'aborted_delete_rolled_back',
                          error=str(exc))
        else:
            report['physical_fingerprint_error_after_close'] = str(exc)
    report['space_note'] = 'Main file-length reduction measured separately from payload deletion; not exact disk allocated blocks/free-space change. No persistent DB copy was created.'
    write_bounded_json(target, report, inputs=[db_path, cache_path])
    if failure:
        if committed:
            raise CleanupCommittedError(report) from failure
        raise failure
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--db', required=True)
    parser.add_argument('--cache', default=str(ROOT / 'data/foundation/emb_cache.db'))
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--plan')
    args = parser.parse_args(argv)
    try:
        if args.apply:
            if not args.plan:
                raise ValueError('Explicit --apply also requires --plan from the dry-run')
            plan = read_bounded_json(args.plan)
            _output(args.output, plan, inputs=[args.plan])
            report = apply_plan(args.db, args.cache, args.run_id, plan, args.output)
        else:
            if args.plan:
                raise ValueError('--plan is used only together with --apply')
            report = preview(args.db, args.cache, args.run_id)
            write_bounded_json(_output(args.output, report), report, inputs=[args.db, args.cache])
        print(json.dumps({k: report[k] for k in ('schema', 'run_id')}, ensure_ascii=False))
        return 0
    except CleanupCommittedError as exc:
        print(json.dumps({'error': str(exc), 'status': exc.report['status'], 'deleted_rows': exc.report.get('deleted_rows')}, ensure_ascii=False), file=sys.stderr)
        return 3
    except (ValueError, OSError, sqlite3.Error, StorageError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
