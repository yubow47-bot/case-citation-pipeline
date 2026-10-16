"""Build and publish complete offline keyword retrieval for one immutable pipeline run.

Default: no network calls, no vector table promises, no calibration borrowed from another run.
Use --vectors cached to reuse embeddings already present in the local cache.
Project writes enforce a 12 GiB logical-file budget, a 2 GiB free reserve and
SQLite page caps with rollback-journal space. --estimated-peak-gb defaults to 3;
explicit budget overrides and stage/cap receipts make capacity failures reviewable.
"""
import argparse
import json
import math
import sqlite3
import subprocess
import sys
from pathlib import Path
from common import (ROOT, DEFAULT_DB, connect, rows, source_record, verify_snapshot, digest,
                    start_component, finish_component, fail_component, component_status, dump,
                    storage_limits, current_storage_policy, database_preflight, capture_storage_reports)
import build
import score
import index_cases
import index_edges
import index_methods
import relations
import embed
import acceptance


def component(db_path, run_id, name, operation, sources=None):
    db = connect(db_path)
    generation = start_component(db, run_id, name, sources)
    db.close()
    try:
        report = operation()
        if sources:
            verify_snapshot(sources)
        db = connect(db_path)
        with db:
            finish_component(db, run_id, name, generation, details=dict(report, sources=sources or {}))
        db.close()
        return report
    except Exception as exc:
        db = connect(db_path)
        fail_component(db, run_id, name, generation, exc)
        db.close()
        raise


def method_sources():
    paths = set((ROOT/'pipeline').glob('*.py')) | set((ROOT/'decisions').glob('*.csv'))
    paths |= set((ROOT/'docs').glob('*.md')) | set((ROOT/'implementation').glob('*.md'))
    paths |= set((ROOT/'audit').rglob('*.md')) | set((ROOT/'docs'/'method_cards').glob('*.md'))
    paths.add(ROOT/'decisions'/'README.md')
    return {p.relative_to(ROOT).as_posix(): {'path': str(p), 'sha256': digest(p)}
            for p in sorted(paths) if p.is_file() and p.name != 'PROBLEMS.md'}


def _run_all(run_dir, db_path, corpus_dir, vectors, skip_acceptance, checkpoint):
    if vectors not in ('skip', 'cached'):
        raise ValueError('Only offline vector modes are supported by after_run')
    run_dir = Path(run_dir).resolve()
    run_id = run_dir.name
    report = {'run': run_id, 'db': str(Path(db_path).resolve()), 'network_allowed': False}
    checkpoint('before_import', fresh=True)
    report['import'] = build.build(run_dir, db_path, corpus_dir)
    checkpoint('after_import')
    db = connect(db_path)
    try:
        own = 'registry/decision_own_citations.csv'
        original = db.execute('SELECT sha256 FROM run_sources WHERE run_id=? AND logical_path=?', (run_id, own)).fetchone()
        if not original:
            raise ValueError('Missing imported own-citations registry snapshot')
        sources = {own: source_record(db, run_id, own, run_dir/own, original[0])}
        db.commit()
    finally:
        db.close()
    report['relations'] = component(db_path, run_id, 'relations', lambda: relations.label(run_dir, db_path), sources)
    checkpoint('after_relations')
    rates = ROOT/'audit'/'findings'/'canlii_crosscheck'/run_id/'t6_bucket_rates.csv'
    report['weights'] = score.score(run_id, db_path, rates) if rates.exists() else {
        'status': 'missing', 'reason': 'no calibration for this run; raw DD remains available'}
    checkpoint('before_case_profiles')
    report['case_profiles'] = index_cases.build_profiles(run_dir, db_path)
    checkpoint('after_case_profiles')
    report['edge_passages'] = index_edges.build_passages(run_dir, db_path)
    checkpoint('after_edge_passages')
    report['methods'] = component(db_path, run_id, 'methods', lambda: index_methods.build(db_path), method_sources())
    checkpoint('after_methods')
    if vectors == 'cached':
        report['vectors'] = embed.index(['cases', 'methods'], db_path, run_id, allow_network=False)
        report['vectors']['edges'] = index_edges.embed_passages(run_id, db_path, allow_network=False)
    else:
        report['vectors'] = {}
        db = connect(db_path)
        try:
            for collection in ('cases', 'methods', 'edges'):
                name = 'vectors_' + collection
                generation = start_component(db, run_id, name)
                value = {'status': 'missing', 'reason': 'offline keyword build; vector generation skipped'}
                with db:
                    finish_component(db, run_id, name, generation, 'missing', value)
                report['vectors'][collection] = value
        finally:
            db.close()
    checkpoint('after_vectors')
    if skip_acceptance:
        report['acceptance'] = {'status': 'skipped', 'published': False}
    else:
        report['acceptance'] = acceptance.accept_run(db_path, run_id, publish=True)
    checkpoint('after_acceptance')
    db = connect(db_path, readonly=True)
    try:
        report['status'] = db.execute('SELECT status FROM runs WHERE run_id=?', (run_id,)).fetchone()[0]
        report['components'] = {r['component']: dict(r) for r in db.execute(
            'SELECT component,generation,status,source_fingerprint,updated_at FROM run_components WHERE run_id=?', (run_id,))}
    finally:
        db.close()
    return report


def run_all(run_dir, db_path=DEFAULT_DB, corpus_dir=None, vectors='skip', skip_acceptance=False,
            max_project_bytes=None, min_free_bytes=None, estimated_peak_bytes=3 * 1024 ** 3):
    if not isinstance(estimated_peak_bytes, int) or isinstance(estimated_peak_bytes, bool) or estimated_peak_bytes < 0:
        raise ValueError('estimated_peak_bytes must be a nonnegative integer')
    checkpoints = []
    with storage_limits(max_project_bytes, min_free_bytes), capture_storage_reports() as caps:
        policy = dict(current_storage_policy())
        def checkpoint(phase, fresh=False):
            value = database_preflight(db_path, estimated_peak_bytes if fresh else 0)
            checkpoints.append(dict(value, phase=phase))
        try:
            report = _run_all(run_dir, db_path, corpus_dir, vectors, skip_acceptance, checkpoint)
            report['storage_budget'] = {'policy': policy, 'estimated_initial_peak_bytes': estimated_peak_bytes,
                'checkpoints': checkpoints, 'sqlite_caps': caps,
                'note': 'Every project writable connection has a main-file page cap plus journal reserve. This report does not govern unrelated concurrent writers; phase checks detect project growth between stages.'}
            # Include the small atomic receipt's peak in the last capacity check.
            receipt_bytes = len(json.dumps(report, ensure_ascii=False, indent=2).encode('utf-8')) + 4096
            checkpoint('before_receipt', fresh=False)
            database_preflight(db_path, receipt_bytes)
            dump(Path(db_path).parent/(Path(run_dir).resolve().name+'_foundation.json'), report)
            return report
        except Exception as exc:
            exc.foundation_storage_report = {'policy': policy, 'estimated_initial_peak_bytes': estimated_peak_bytes,
                'checkpoints': checkpoints, 'sqlite_caps': caps,
                'failure_preflight': getattr(exc, 'report', getattr(exc, 'storage_report', None))}
            # No failure receipt is written when capacity is exhausted; stderr retains the context.
            raise


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--run', help='an existing complete run directory')
    g.add_argument('--pipeline-out', help='run pipeline/run_all.py into this new directory first')
    p.add_argument('--db', default=str(DEFAULT_DB))
    p.add_argument('--corpus', help='corpus directory; imported paths and hashes bind all later evidence')
    p.add_argument('--court', action='append', default=None,
                   help='court to extract with --pipeline-out (repeatable); default uses pipeline environment/default courts')
    p.add_argument('--vectors', choices=['skip', 'cached'], default='skip')
    p.add_argument('--skip-acceptance', action='store_true', help='leave this run unpublished (building)')
    p.add_argument('--storage-budget-gb', type=float, default=12, help='Project logical-file budget, GiB; explicit override')
    p.add_argument('--min-free-gb', type=float, default=2, help='Disk free-space reserve, GiB')
    p.add_argument('--estimated-peak-gb', type=float, default=3, help='Additional initial build peak estimate, GiB')
    a = p.parse_args(argv)
    try:
        for name in ('storage_budget_gb', 'min_free_gb', 'estimated_peak_gb'):
            value = getattr(a, name)
            if value < 0 or not math.isfinite(value):
                raise ValueError(name + ' must be finite and nonnegative')
        run_dir = Path(a.run or a.pipeline_out).resolve()
        corpus_dir = str(Path(a.corpus).resolve()) if a.corpus else None
        if a.pipeline_out:
            with storage_limits(int(a.storage_budget_gb * 1024 ** 3), int(a.min_free_gb * 1024 ** 3)):
                database_preflight(a.db, int(a.estimated_peak_gb * 1024 ** 3))
            pipeline_cmd = [sys.executable, str(ROOT/'pipeline'/'run_all.py'), '--out', str(run_dir),
                            '--storage-budget-gb', str(a.storage_budget_gb),
                            '--min-free-gb', str(a.min_free_gb)]
            if corpus_dir:
                pipeline_cmd += ['--corpus-dir', corpus_dir]
            for court in a.court or ():
                pipeline_cmd += ['--court', court]
            subprocess.run(pipeline_cmd, check=True, cwd=ROOT)
        report = run_all(run_dir, a.db, corpus_dir, a.vectors, a.skip_acceptance,
                         int(a.storage_budget_gb * 1024 ** 3), int(a.min_free_gb * 1024 ** 3),
                         int(a.estimated_peak_gb * 1024 ** 3))
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc),
                          'storage_context': getattr(exc, 'foundation_storage_report', getattr(exc, 'storage_report', None))},
                         ensure_ascii=False, indent=2, default=str), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
