"""Replay registry/decide/select/edges from sealed, compatible compressed upstream.

python pipeline/replay_decide.py --source-run data/run_SOURCE --out data/run_NEW

The source remains intact. All reused files remain in the new run if the source
is later removed. Reused extraction/classification/merge steps are recorded as
reuse, never as newly executed production steps. No CSV is unpacked on disk.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys

try:
    from . import run_all
except ImportError:
    import run_all

ROOT = Path(run_all.ROOT)
STAGES = ('extract_out', 'classify_out', 'merge_out')
ALLOW_CHANGED = frozenset({
    'pipeline/identity_evidence.py', 'pipeline/identity_constraints.py',
    'pipeline/identity_solve.py', 'pipeline/identity_courts.py',
    'pipeline/decide.py', 'pipeline/registry.py', 'pipeline/registry_report.py',
    'pipeline/edges.py', 'pipeline/run_all.py', 'pipeline/replay_decide.py',
    'tools/check_run.py',
    'tools/storage.py',  # Runtime capacity/deletion accounting, not upstream parsing.
    # Read only by CourtEvidence in registry/decide; never by extract/classify/merge.
    # All other decision tables still require a fresh upstream run.
    'decisions/identity_court_facts.csv',
    'decisions/identity_separations.csv',  # Exact proof-bound exclusions in decide only.
})
UPSTREAM_SCHEMAS = ('extract_legacy_kept_superseded', 'extract_candidates', 'classify', 'merge')
MAX_MANIFEST_BYTES = 2 * 1024**2
MAX_COPY_BYTES = 2 * 1024**2


def _link(path):
    st = path.lstat()
    return path.is_symlink() or bool(getattr(st, 'st_file_attributes', 0) & 0x400)


def run_path(path, root=None):
    """Require a literal direct data/run_* path, without any reparse ancestor."""
    root = Path(root or ROOT).absolute()
    path = Path(path).absolute()
    data = root / 'data'
    if path.parent != data or not re.fullmatch(r'run_[A-Za-z0-9_.-]+', path.name):
        raise ValueError('Replay source/output must be a direct data/run_* directory')
    current = path
    while True:
        if os.path.lexists(current) and _link(current):
            raise ValueError('Run paths must not contain links or junctions: ' + str(current))
        if current == root:
            break
        current = current.parent
    if path.resolve() != path:
        raise ValueError('Run path resolves outside its literal project location')
    return path


def _relative(relative):
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        raise ValueError('Unsafe sealed path: ' + str(relative))
    value = PurePosixPath(relative)
    if value.is_absolute() or any(p in ('', '.', '..') for p in value.parts) or value.as_posix() != relative:
        raise ValueError('Unsafe sealed path: ' + relative)
    return relative


def _tree_files(directory):
    files = set()
    for current, dirs, names in os.walk(directory, followlinks=False):
        for name in dirs + names:
            path = Path(current) / name
            if _link(path):
                raise ValueError('Source or replay tree contains a link/junction: ' + str(path))
        for name in names:
            path = Path(current) / name
            if not path.is_file():
                raise ValueError('Run tree contains a nonregular file: ' + str(path))
            files.add(path.relative_to(directory).as_posix())
    return files


def _json_bytes(path):
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError('Replay manifest exceeds 2 MiB: ' + str(path))
    raw = path.read_bytes()
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError('Replay manifest exceeds 2 MiB: ' + str(path))
    value = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError('Replay manifest must be an object: ' + str(path))
    return value, raw


def _identity_fingerprint(files, params):
    return hashlib.sha256((''.join('%s:%s\n' % (k, files[k]) for k in sorted(files))
        + 'params:' + json.dumps(params, sort_keys=True, default=str) + '\n').encode('utf-8')).hexdigest()


def verify_source(source_run, root=None):
    """Verify exact original output bytes and every non-downstream input SHA."""
    root = Path(root or ROOT).absolute()
    source = run_path(source_run, root)
    if not source.is_dir():
        raise ValueError('Replay source is missing: ' + str(source))
    manifest, raw = _json_bytes(source / 'run_manifest.json')
    if manifest.get('status') != 'complete' or manifest.get('input_identity_verified_unchanged') is not True:
        raise ValueError('Replay source must be complete with verified unchanged inputs')
    params, identity = manifest.get('params'), manifest.get('input_identity', {})
    if not isinstance(params, dict) or not isinstance(identity.get('files'), dict) or not identity['files']:
        raise ValueError('Source input identity is missing')
    if identity.get('params') != params or identity.get('fingerprint') != _identity_fingerprint(identity['files'], params):
        raise ValueError('Source input identity fingerprint/params are inconsistent')
    for relative, sha in identity['files'].items():
        _relative(relative)
        if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{64}', sha):
            raise ValueError('Source input SHA is malformed: ' + relative)
    courts = params.get('courts')
    if (not isinstance(courts, list) or not courts or len(set(courts)) != len(courts)
            or any(not isinstance(c, str) or not re.fullmatch(r'[A-Za-z0-9_]+', c) for c in courts)):
        raise ValueError('Source court scope is missing or malformed')
    if not params.get('corpus_dir') or not Path(params['corpus_dir']).is_absolute():
        raise ValueError('Source corpus directory must be explicitly recorded and absolute')
    for field in ('batch_size', 'year_from', 'limit_batches', 'anchor_corpus'):
        if field not in params:
            raise ValueError('Source scope parameter is missing: ' + field)
    if (not isinstance(params['batch_size'], int) or isinstance(params['batch_size'], bool) or params['batch_size'] <= 0
            or params['limit_batches'] is not None and (not isinstance(params['limit_batches'], int)
                or isinstance(params['limit_batches'], bool) or params['limit_batches'] <= 0)
            or params['year_from'] is not None and (not isinstance(params['year_from'], int) or isinstance(params['year_from'], bool))):
        raise ValueError('Source batch/year scope is malformed')
    anchors = params['anchor_corpus']
    if params.get('text_policy', run_all.POLICY_EN) not in run_all.POLICIES:
        raise ValueError('Source language policy is unknown')
    if (not isinstance(anchors, list) or len(set(anchors)) != len(anchors)
            or any(not isinstance(c, str) or not re.fullmatch(r'[A-Za-z0-9_]+', c) for c in anchors)):
        raise ValueError('Source anchor scope is malformed')
    for name in UPSTREAM_SCHEMAS:
        if manifest.get('schema_versions', {}).get(name) != run_all.SCHEMA_VERSIONS[name]:
            raise ValueError('Upstream schema changed: ' + name)
    current = run_all.input_identity(root=str(root), courts=tuple(courts), params=params,
                                     corpus_dir=params['corpus_dir'])
    differences = sorted(k for k in set(identity['files']) | set(current['files'])
        if k not in ALLOW_CHANGED and identity['files'].get(k) != current['files'].get(k))
    if differences:
        raise ValueError('Upstream/corpus/table inputs changed; refusing reuse: ' + ', '.join(differences[:20]))
    seal = manifest.get('output_identity', {})
    files = seal.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('Replay source must have a nonempty output seal')
    if seal.get('fingerprint') != hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest():
        raise ValueError('Source output seal fingerprint is inconsistent')
    normalized = set()
    for relative, sha in files.items():
        _relative(relative)
        norm = os.path.normcase(relative)
        if norm in normalized or not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{64}', sha):
            raise ValueError('Malformed/duplicate source seal entry: ' + relative)
        normalized.add(norm)
    actual = _tree_files(source) - {'run_manifest.json'}
    if actual != set(files):
        raise ValueError('Source seal must cover the exact file set (missing or unsealed files)')
    for relative, sha in files.items():
        if run_all.sha256_file(source / relative) != sha:
            raise ValueError('Source output seal changed: ' + relative)
    upstream = {k: v for k, v in files.items() if PurePosixPath(k).parts[0] in STAGES}
    required = {'extract_out/manifest.json', 'extract_out/candidates.csv.gz'}
    for court in courts:
        required.update({'classify_out/' + court + '/manifest.json',
                         'classify_out/' + court + '/classified.csv.gz',
                         'merge_out/' + court + '/manifest.json'})
        required.update('merge_out/' + court + '/' + name + '.csv.gz'
                        for name in ('merged', 'mentions_candidates', 'decision_ids', 'folded_log'))
    if not required <= set(upstream):
        raise ValueError('Sealed source is missing required compressed upstream files: ' + ', '.join(sorted(required - set(upstream))))
    if any(not k.endswith(('.csv.gz', '.json')) for k in upstream):
        raise ValueError('Only compressed CSV and small JSON may be reused; no plaintext CSV copies')
    for relative in upstream:
        if relative.endswith('.json') and (source / relative).stat().st_size > MAX_COPY_BYTES:
            raise ValueError('Reused JSON exceeds the small-copy budget: ' + relative)
    return {'source': source, 'manifest': manifest, 'manifest_bytes': raw,
            'manifest_sha256': hashlib.sha256(raw).hexdigest(), 'upstream': upstream,
            'upstream_bytes': sum((source / k).stat().st_size for k in upstream),
            'source_input_fingerprint': identity['fingerprint'],
            'source_output_fingerprint': seal['fingerprint']}


def verify_source_unchanged(proof, target=None):
    source = proof['source']
    if hashlib.sha256((source / 'run_manifest.json').read_bytes()).hexdigest() != proof['manifest_sha256']:
        raise ValueError('Source manifest changed during replay')
    files = proof['manifest']['output_identity']['files']
    if _tree_files(source) - {'run_manifest.json'} != set(files):
        raise ValueError('Source file set changed during replay')
    for relative, sha in files.items():
        if run_all.sha256_file(source / relative) != sha:
            raise ValueError('Source artifact changed during replay: ' + relative)
    if target is not None:
        target = Path(target)
        retained = {r for r in _tree_files(target) if PurePosixPath(r).parts[0] in STAGES}
        if retained != set(proof['upstream']):
            raise ValueError('Reused upstream file set changed in the new run')
        for relative, sha in proof['upstream'].items():
            if run_all.sha256_file(target / relative) != sha:
                raise ValueError('Reused upstream bytes changed in the new run: ' + relative)
        if (target / 'reused_upstream_manifest.json').read_bytes() != proof['manifest_bytes']:
            raise ValueError('Copied upstream source manifest changed in the new run')
    return dict(proof['upstream']) if target is None else {
        **proof['upstream'], 'reused_upstream_manifest.json': proof['manifest_sha256']}


def estimated_peak_bytes(proof):
    """Include logical duplicated hardlinks, generated CSVs and gzip scratch."""
    receipt_path = proof['source'] / 'compact_receipt.json'
    downstream, largest = 0, 0
    if 'compact_receipt.json' in proof['manifest']['output_identity']['files']:
        receipt, _ = _json_bytes(receipt_path)
        for row in receipt.get('files', []):
            relative = row.get('path', '').replace('\\', '/')
            size = row.get('logical_bytes')
            if relative and relative.split('/')[0] not in STAGES and isinstance(size, int) and not isinstance(size, bool) and size >= 0:
                downstream += size
                largest = max(largest, size)
    # Without a sealed compaction size receipt do not guess from gzip ISIZE,
    # which wraps at 4 GiB. Fail conservatively into a larger preflight.
    generated = math.ceil(downstream * 1.25) if downstream else 2 * run_all.GiB
    return max(run_all.GiB, proof['upstream_bytes'] + generated + largest + 64 * 1024**2)


def reuse_upstream(proof, target, storage_budget_gb=12):
    target = Path(target)
    records = []
    for relative, sha in sorted(proof['upstream'].items()):
        source, destination = proof['source'] / relative, target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise ValueError('Replay would overwrite an upstream artifact: ' + relative)
        if relative.endswith('.csv.gz'):
            try:
                os.link(source, destination)
                method = 'hardlink_compressed_csv'
            except OSError as exc:
                if source.stat().st_size > MAX_COPY_BYTES:
                    raise ValueError('Compressed upstream hardlink failed; refusing a large fallback copy: ' + relative) from exc
                shutil.copyfile(source, destination)
                method = 'copy_small_compressed_csv'
        else:
            shutil.copyfile(source, destination)
            method = 'copy_small_json'
        records.append({'path': relative, 'sha256': sha, 'bytes': destination.stat().st_size, 'method': method})
    (target / 'reused_upstream_manifest.json').write_bytes(proof['manifest_bytes'])
    receipt = {'schema': 'reused_upstream_v1', 'source_run': str(proof['source']),
               'source_input_fingerprint': proof['source_input_fingerprint'],
               'source_output_fingerprint': proof['source_output_fingerprint'],
               'source_manifest_sha256': proof['manifest_sha256'], 'files': records,
               'note': 'Upstream steps were reused as sealed bytes; no extraction/classification/merge was executed. Hardlinks remain valid if the source paths are deleted.'}
    payload = (json.dumps(receipt, ensure_ascii=False, indent=1) + '\n').encode('utf-8')
    if len(payload) > MAX_MANIFEST_BYTES:
        raise ValueError('Reuse receipt exceeds 2 MiB')
    (target / 'reused_upstream.json').write_bytes(payload)
    verify_source_unchanged(proof, target)
    run_all.preflight(ROOT, 0, max_project_bytes=int(storage_budget_gb * run_all.GiB))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--source-run', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--registry-gate', default='registered', choices=('literal', 'own_or_registry', 'registered_only', 'registered'))
    parser.add_argument('--mixed-key-holdout', action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument('--compact', action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument('--storage-budget-gb', type=float, default=12)
    args = parser.parse_args(argv)
    if not math.isfinite(args.storage_budget_gb) or args.storage_budget_gb <= 0:
        parser.error('Storage budget must be finite and positive')
    target = run_path(args.out)
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ValueError('New replay target must be missing or empty')
    proof = verify_source(args.source_run)
    params = proof['manifest']['params']
    args.out, args.corpus_dir = str(target), params['corpus_dir']
    args.batch_size, args.year_from, args.limit_batches = (params[k] for k in ('batch_size', 'year_from', 'limit_batches'))
    args.text_policy = params.get('text_policy', run_all.POLICY_EN)
    courts, anchors = tuple(params['courts']), tuple(params['anchor_corpus'])
    budget = run_all.preflight(ROOT, estimated_peak_bytes(proof), max_project_bytes=int(args.storage_budget_gb * run_all.GiB))
    reused = {'source_run': str(proof['source']), 'source_input_fingerprint': proof['source_input_fingerprint'],
              'source_output_fingerprint': proof['source_output_fingerprint'],
              'source_manifest_sha256': proof['manifest_sha256'], 'upstream_files': len(proof['upstream'])}
    runner = run_all.Runner(str(target), args, courts, anchors, reused_upstream=reused)
    run_all.ACTIVE_RUNNER = runner
    runner.check_dir()
    runner.write_manifest('running')
    runner.manifest['storage_preflight'] = budget
    runner.manifest['steps_reused'] = ['extract'] + ['classify_' + c for c in courts] + ['merge_' + c for c in courts]
    runner.manifest['replay'] = {'protocol': 'verified-upstream-replay-v1', 'source_input_fingerprint': proof['source_input_fingerprint'],
                                'source_output_fingerprint': proof['source_output_fingerprint'],
                                'allowed_downstream_changes': sorted(ALLOW_CHANGED), 'fresh_upstream_execution': False}
    runner.write_manifest('running')
    try:
        reuse_upstream(proof, target, args.storage_budget_gb)
        run_all.run_downstream(runner)
        run_all.finalize(runner, before_seal=lambda: verify_source_unchanged(proof, target))
    except BaseException as exc:
        run_all.mark_active_failed(exc)
        raise
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except BaseException as exc:
        run_all.mark_active_failed(exc)
        raise
