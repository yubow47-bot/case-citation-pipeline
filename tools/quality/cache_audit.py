"""Read-only cache usefulness audit against the actual current embedding inputs.

Run only after the new keyword database is ready. No credentials, requests,
embedding vectors or database copies are read/written by this audit.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

try:
    from .common import ROOT, open_source, write_bounded_json, protected_output
except ImportError:
    from common import ROOT, open_source, write_bounded_json, protected_output


def embedding_contract():
    """Compile the repository's real prepare function, without importing key/API code."""
    path = ROOT / 'tools/foundation/embed.py'
    raw = path.read_bytes()
    tree = ast.parse(raw.decode('utf-8-sig'))
    values, prepare = {}, None
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ('MODEL', 'DIM', 'MAX_CHARS'):
                values[name] = ast.literal_eval(node.value)
            elif name == 'SECRET':
                call = node.value
                if (not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute)
                        or not isinstance(call.func.value, ast.Name) or call.func.value.id != 're'
                        or call.func.attr != 'compile' or len(call.args) != 1 or call.keywords):
                    raise ValueError('Unsupported prepare SECRET contract; refuse to approximate it')
                values[name] = re.compile(ast.literal_eval(call.args[0]))
        elif isinstance(node, ast.FunctionDef) and node.name == 'prepare':
            prepare = node
    if prepare is None or set(values) != {'MODEL', 'DIM', 'MAX_CHARS', 'SECRET'}:
        raise ValueError('Missing embedding prepare/model/dimension contract')
    # Restrict this audit to the pure function currently used by embed.py.
    for node in ast.walk(prepare):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
            raise ValueError('prepare is no longer a pure preprocessing function')
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id not in {'SECRET', 'MAX_CHARS', 'text'}:
            raise ValueError('prepare has a new dependency; update the audit before trusting its counts')
    namespace = dict(values)
    exec(compile(ast.Module(body=[prepare], type_ignores=[]), str(path), 'exec'), namespace)
    edge_path = ROOT / 'tools/foundation/index_edges.py'
    edge_raw = edge_path.read_bytes()
    edge_dim = None
    for node in ast.parse(edge_raw.decode('utf-8-sig')).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'EDGE_DIM' for t in node.targets):
            edge_dim = ast.literal_eval(node.value)
    if not isinstance(edge_dim, int) or not isinstance(values['DIM'], int):
        raise ValueError('Embedding dimensions are not explicit integer constants')
    return {'model': values['MODEL'], 'text_dim': values['DIM'], 'edge_dim': edge_dim,
            'prepare': namespace['prepare'], 'code_sha256': hashlib.sha256(raw).hexdigest(),
            'edge_code_sha256': hashlib.sha256(edge_raw).hexdigest()}


def audit_cache(db_path, cache_path, run_id=None):
    source = open_source(db=db_path, run_id=run_id)
    cache_path = Path(cache_path).resolve()
    cache = None
    try:
        if not cache_path.is_file():
            raise ValueError('Embedding cache does not exist: ' + str(cache_path))
        contract = embedding_contract()
        cache = sqlite3.connect(cache_path.as_uri() + '?mode=ro', uri=True)
        cache.execute('PRAGMA query_only=ON')
        cache.execute('PRAGMA temp_store=MEMORY')
        cache.execute('BEGIN')
        if not cache.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='emb'").fetchone():
            raise ValueError('Cache has no emb(h,model,dim,v) table')
        needed = defaultdict(set)
        counts = defaultdict(int)
        input_fingerprint = hashlib.sha256()
        model = contract['model']
        def remember(text, dim, kind):
            prepared = contract['prepare'](text)
            h = hashlib.sha256(prepared.encode('utf-8')).hexdigest()
            needed[(model, dim)].add(h)
            counts[kind] += 1
            input_fingerprint.update((kind + ':' + str(dim) + ':' + h + '\n').encode())
        # Methods are shared; every other collection is scoped to the current
        # run, matching embed.index() rather than retaining old-run case hashes.
        for row in source.db.execute("SELECT collection,title,text FROM text_records "
                                     "WHERE collection='methods' OR run_id=? ORDER BY collection,id",
                                     (source.run_id,)):
            remember(row['title'] + '\n' + row['text'], contract['text_dim'], 'text_records/' + row['collection'])
        exists = source.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='edge_passages'").fetchone()
        if not exists:
            raise ValueError('Current ready database has no edge_passages; cannot prove edge-cache usefulness')
        # embed_passages() sends passage alone (no title) with EDGE_DIM.
        for row in source.db.execute('SELECT passage FROM edge_passages WHERE run_id=? ORDER BY id', (source.run_id,)):
            remember(row['passage'], contract['edge_dim'], 'edge_passages')
        summary = defaultdict(lambda: {'cache_rows': 0, 'cache_payload_bytes': 0,
                                        'matched_current_rows': 0, 'matched_current_payload_bytes': 0,
                                        'unreferenced_rows': 0, 'unreferenced_payload_bytes': 0,
                                        'invalid_shape_rows': 0, 'referenced_current_invalid_shape_rows': 0,
                                        'referenced_current_invalid_shape_bytes': 0})
        hit_hashes = defaultdict(set)
        for h, cached_model, dim, size in cache.execute('SELECT h,model,dim,LENGTH(v) FROM emb'):
            key = (cached_model, dim)
            row = summary[key]
            row['cache_rows'] += 1
            row['cache_payload_bytes'] += size or 0
            valid_shape = isinstance(dim, int) and dim > 0 and size == dim * 4
            if not valid_shape:
                row['invalid_shape_rows'] += 1
            referenced = h in needed.get(key, set())
            if referenced and valid_shape:
                row['matched_current_rows'] += 1
                row['matched_current_payload_bytes'] += size
                hit_hashes[key].add(h)
            elif referenced:
                row['referenced_current_invalid_shape_rows'] += 1
                row['referenced_current_invalid_shape_bytes'] += size or 0
            else:
                row['unreferenced_rows'] += 1
                row['unreferenced_payload_bytes'] += size or 0
        entries = []
        for key in sorted(set(summary) | set(needed)):
            item = dict(summary[key], model=key[0], dim=key[1],
                        current_unique_input_hashes=len(needed[key]),
                        current_cache_hits=len(hit_hashes[key]),
                        current_cache_misses=len(needed[key] - hit_hashes[key]))
            entries.append(item)
        return {'schema': 'embedding_cache_usefulness_v1', 'run_id': source.run_id,
                'run_input_fingerprint': source.manifest['input_identity']['fingerprint'],
                'db_path': str(Path(db_path).resolve()), 'cache_path': str(cache_path),
                'source_provenance': {'run_directory': str(source.run_dir),
                                      'corpus_directory': source.manifest['params'].get('corpus_dir')},
                'cache_physical_file_bytes': cache_path.stat().st_size,
                'cache_page_size': cache.execute('PRAGMA page_size').fetchone()[0],
                'cache_freelist_pages': cache.execute('PRAGMA freelist_count').fetchone()[0],
                'embedding_input_counts': dict(counts),
                'embedding_input_fingerprint': input_fingerprint.hexdigest(),
                'prepare_code_sha256': contract['code_sha256'],
                'edge_code_sha256': contract['edge_code_sha256'], 'model_dimensions': entries,
                'matched_current_payload_bytes': sum(e['matched_current_payload_bytes'] for e in entries),
                'unreferenced_payload_bytes': sum(e['unreferenced_payload_bytes'] for e in entries),
                'mode': 'read_only_sql_snapshots_no_vector_blob_loading_no_network_no_key_reads',
                'limitations': ['Payload byte counts are exact LENGTH(v), not exact physical reclaim after DELETE/VACUUM.',
                                'Unreferenced means absent from current document/edge embedding inputs; future queries or historical rebuilds may request those hashes.',
                                'All current text records and edge passages are compared; a matched hash proves cache reuse, not semantic vector accuracy.',
                                'This report does not delete rows, copy databases or call any embedding service.']}
    finally:
        if cache:
            cache.close()
        source.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--cache', default=str(ROOT / 'data/foundation/emb_cache.db'))
    parser.add_argument('--run-id')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        if Path(args.output).suffix != '.json':
            raise ValueError('Cache audit output must be a .json report')
        protected_output(args.output, [args.db, args.cache])
        report = audit_cache(args.db, args.cache, args.run_id)
        target = Path(args.output).resolve()
        for directory in report['source_provenance'].values():
            if directory and (target == Path(directory).resolve() or Path(directory).resolve() in target.parents):
                raise ValueError('Audit output must stay outside source run/corpus directories')
        write_bounded_json(args.output, report, inputs=[args.db, args.cache])
        print(json.dumps({k: report[k] for k in ('schema', 'run_id', 'cache_physical_file_bytes',
                                                'matched_current_payload_bytes', 'unreferenced_payload_bytes')}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
