"""Bounded, read-only quality review inputs and evidence provenance."""
from __future__ import annotations

from collections import defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.research.core import (ResearchSource, DOC_CTE, rows, csv_path, indexed_locator,
                                enrich_corpus, file_hash)
from tools.foundation.common import artifact_digest
from pipeline.corpus_fields import policy_from_manifest, POLICY_EN

MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_CSV_BYTES = 2 * 1024 * 1024
MAX_QUEUE_RECORDS = 500


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def read_bounded_json(path, max_bytes=MAX_JSON_BYTES):
    path = Path(path)
    if path.stat().st_size > max_bytes:
        raise ValueError('JSON input exceeds the byte budget: ' + str(path))
    with path.open(encoding='utf-8-sig') as stream:
        return json.load(stream)


def protected_output(path, inputs=(), source=None):
    path = Path(path).resolve()
    if path in {Path(p).resolve() for p in inputs}:
        raise ValueError('Output would overwrite a source input: ' + str(path))
    if source:
        folders = [source.run_dir, Path(source.manifest['params']['corpus_dir']).resolve()
                   if source.manifest['params'].get('corpus_dir') else None]
        for folder in folders:
            if folder and (path == folder or folder in path.parents):
                raise ValueError('Review outputs must be outside source run/corpus directories')
        db_path = source.provenance.get('db_path')
        if db_path and path == Path(db_path).resolve():
            raise ValueError('Output would overwrite the formal database')
    return path


def write_bounded_json(path, value, max_bytes=MAX_JSON_BYTES, inputs=(), source=None):
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if len(payload) > max_bytes:
        raise ValueError('JSON output exceeds the 2 MiB budget; narrow the declared review scope')
    path = protected_output(path, inputs, source)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return value


def open_source(run=None, db=None, run_id=None, corpus_dir=None, documents=None):
    if bool(run) == bool(db):
        raise ValueError('Choose exactly one complete run or read-only formal database')
    if run:
        return ResearchSource.stream(run, corpus_dir=corpus_dir, documents=documents)
    if corpus_dir or documents:
        raise ValueError('DB inputs use their imported document/source snapshots')
    return ResearchSource.sqlite(db, run_id=run_id)


def frame_identity(source):
    """Logical artifact hashes bind labels across lossless CSV compression."""
    hashes, stat_snapshot = {}, {}
    imported = {r['relative_path']: r['sha256'] for r in source.provenance.get('imported_artifacts', [])}
    for relative in ('select_out/selected.csv', 'edges/citation_edges.csv'):
        try:
            path = csv_path(source.run_dir / relative)
        except ValueError:
            if relative not in imported:
                raise ValueError('Missing source artifact identity: ' + relative)
            hashes[relative] = imported[relative]
            continue
        before = path.stat()
        actual = artifact_digest(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('Source artifact changed while hashing: ' + relative)
        if relative in imported and imported[relative] != actual:
            raise ValueError('Artifact no longer matches its formal imported snapshot: ' + relative)
        hashes[relative] = actual
        stat_snapshot[str(path)] = [after.st_size, after.st_mtime_ns]
    identity = {'run_id': source.run_id,
                'input_fingerprint': source.manifest['input_identity']['fingerprint'],
                'artifact_logical_sha256': hashes,
                'document_inputs': source.provenance.get('document_metadata_verification', 'formal_imported_documents'),
                'manifest_sha256': canonical_hash(source.manifest)}
    # Caller-supplied fixture metadata changes the sampling frame and its identity.
    metadata = [r for r in source.provenance.get('artifacts', [])
                if 'caller_supplied_metadata' in r.get('verification', '')]
    identity['metadata_sha256'] = [r['sha256'] for r in metadata]
    return canonical_hash(identity), identity, stat_snapshot


def verify_unchanged(snapshot):
    for name, expected in snapshot.items():
        st = Path(name).stat()
        if [st.st_size, st.st_mtime_ns] != expected:
            raise ValueError('Source changed during review generation: ' + name)


def member_rows(source):
    """Stream complete rows from original CSV/gz or the read-only imported table."""
    if source.mode == 'sqlite_readonly':
        for row in source.db.execute('SELECT * FROM members WHERE run_id=? ORDER BY row_number', (source.run_id,)):
            value = dict(row)
            number = int(value.pop('row_number'))
            value.pop('run_id', None)
            yield number, value
    else:
        yield from rows(source.run_dir / 'select_out/selected.csv',
                        ('court', 'merge_key', 'merged_group_id', 'citation_kind'))


def edge_rows(source):
    for row in source.db.execute('SELECT * FROM citation_edges WHERE run_id=?', (source.run_id,)):
        value = dict(row)
        value.pop('run_id', None)
        yield value


def document_metadata(source):
    # Shared research denominator: citing judgment date, verified/calendar-valid;
    # conflicting duplicate source IDs remain explicitly UNKNOWN.
    return {r['source_id']: dict(r) for r in source.db.execute(
        DOC_CTE + ' SELECT * FROM d', (source.run_id,))}


def brief_edge(edge):
    fields = ('source_decision', 'resolved_cited_case', 'edge_support', 'identity_status',
              'foreign_status', 'origin_country', 'origin_evidence_ids',
              'distinct_decisions_count', 'mention_count', 'case_name_modal', 'mention_detail_key')
    return {k: str(edge.get(k) or '')[:160] for k in fields}


def _field_proof(selection, policy, verified=False):
    """Never turn a policy/index claim into verified original field evidence."""
    proof = dict(selection)
    if proof.get('policy') is not None and proof['policy'] != policy:
        raise ValueError('Original field proof belongs to another corpus text policy')
    proof['text_policy'] = policy
    allowed = {'citation_field': ('citation_en', 'citation_fr'),
               'name_field': ('name_en', 'name_fr'),
               'date_field': ('document_date_en', 'document_date_fr'),
               'text_field': ('unofficial_text_en', 'unofficial_text_fr')}
    for name, values in allowed.items():
        value = proof.get(name)
        if value is not None and value not in values:
            raise ValueError('Unknown original corpus field: ' + str(value))
        if policy == POLICY_EN and value and value.endswith('_fr'):
            raise ValueError('French field contradicts this historical English-only run')
        if verified and value not in values:
            raise ValueError('Verified original evidence lacks field proof: ' + name)
        proof.setdefault(name, None)
    language = proof.get('language')
    if language is not None and language not in ('en', 'fr'):
        raise ValueError('Unknown original-text language: ' + str(language))
    if proof.get('text_field') and language and not proof['text_field'].endswith('_' + language):
        raise ValueError('Original text field and language disagree')
    if verified and language is None:
        raise ValueError('Verified original evidence lacks text language')
    proof.setdefault('language', None)
    proof['verification'] = 'original_corpus_fields_verified' if verified else 'policy_or_index_claim_not_original_text_verified'
    return proof


def locate_evidence(source, edges, with_text=False):
    """One counted span per chosen edge; no top-k index and no new persistent DB."""
    policy = policy_from_manifest(source.manifest)
    groups = {e['resolved_cited_case'] for e in edges}
    by_key = defaultdict(set)
    for group in sorted(groups):
        for row in source.db.execute('SELECT court,merge_key FROM members WHERE run_id=? AND merged_group_id=?',
                                     (source.run_id, group)):
            by_key[(row['court'], row['merge_key'])].add(group)
    results, pending, edge_lookup = {}, {}, {}
    for edge in edges:
        key = (edge['source_decision'], edge['resolved_cited_case'])
        docs = [dict(r) for r in source.db.execute(
            'SELECT court,corpus_row,source_id,citation,name,decision_date,corpus_path '
            'FROM documents WHERE run_id=? AND source_id=? ORDER BY court,corpus_row',
            (source.run_id, edge['source_decision']))]
        courts = {r['court'] for r in docs}
        item = {'source_decision': key[0], 'cited_group_id': key[1], 'source_documents': docs[:2],
                'candidate': None, 'span': None, 'quote': None, 'quote_sha256': None,
                'status': 'candidate_not_found', 'limitations': [],
                'field_selection': _field_proof({}, policy)}
        results[key] = item
        if len(courts) != 1:
            item['status'] = 'document_metadata_missing_or_conflicting'
            continue
        court = next(iter(courts))
        indexed_locator(source, item, docs)
        claims = item.get('indexed_evidence_locator', {}).get('corpus', {})
        claim = {key: claims[key] for key in ('citation_field', 'name_field', 'date_field', 'text_field', 'language') if key in claims}
        item['_indexed_field_claim'] = dict(claim)
        if not claim and policy == POLICY_EN:
            claim = {'citation_field': 'citation_en', 'name_field': 'name_en',
                     'date_field': 'document_date_en', 'text_field': 'unofficial_text_en', 'language': 'en'}
        item['field_selection'] = _field_proof(claim, policy)
        pending[key] = court
        edge_lookup[key] = edge
    hashes = {}
    for court in sorted(set(pending.values())):
        try:
            path = csv_path(source.run_dir / 'merge_out' / court / 'mentions_candidates.csv')
        except (ValueError, TypeError):
            for key, c in pending.items():
                if c == court:
                    results[key]['status'] = 'candidate_ledger_missing'
            continue
        before = path.stat()
        logical_sha = artifact_digest(path)
        logical = 'merge_out/' + court + '/mentions_candidates.csv'
        imported = next((r for r in source.provenance.get('run_sources', [])
                         if r['logical_path'] == logical), None)
        if imported and imported['sha256'] != logical_sha:
            raise ValueError('Mention ledger differs from its imported source snapshot: ' + logical)
        source.record_artifact(path, file_hash(path),
                               'matches_imported_mentions' if imported else 'current_ledger_bound_by_review_hash')
        for number, candidate in rows(path, ('source_decision_citation', 'merge_key', 'arbitration_status',
                                            'candidate_id', 'corpus_row_index', 'match_start_offset',
                                            'match_end_offset', 'raw_string')):
            if candidate['arbitration_status'] != 'counted':
                continue
            for gid in by_key.get((court, candidate['merge_key']), ()):
                key = (candidate['source_decision_citation'], gid)
                if key not in pending or pending[key] != court:
                    continue
                item = results[key]
                indexed = item.get('indexed_evidence_locator')
                if indexed and indexed.get('mention_record') != number:
                    continue
                row, start, end = [int(candidate[k]) for k in ('corpus_row_index', 'match_start_offset', 'match_end_offset')]
                if row < 0 or not 0 <= start < end:
                    raise ValueError('Invalid counted mention coordinates')
                if not source.db.execute('SELECT 1 FROM documents WHERE run_id=? AND source_id=? '
                                         'AND court=? AND corpus_row=?',
                                         (source.run_id, key[0], court, row)).fetchone():
                    raise ValueError('Counted mention is not in its imported source judgment row')
                if indexed and (row, start, end) != (indexed.get('corpus_row'), indexed.get('match_start'), indexed.get('match_end')):
                    raise ValueError('Indexed and streamed source coordinates disagree')
                item['candidate'] = {'candidate_id': candidate['candidate_id'], 'merge_key': candidate['merge_key'],
                                     'raw_string': candidate['raw_string'], 'csv_record_number': number,
                                     'row_sha256': canonical_hash(candidate), 'ledger_path': str(path),
                                     'ledger_logical_sha256': logical_sha, 'arbitration_status': 'counted'}
                item['span'] = {'court': court, 'corpus_row': row, 'start': start, 'end': end,
                                'text_policy': policy, 'text_field': item['field_selection'].get('text_field'),
                                'language': item['field_selection'].get('language'),
                                'coordinate_system': 'zero-based Unicode code points, half-open; run policy selected text; original text field not yet verified'}
                item['quote'] = candidate['raw_string']
                item['quote_sha256'] = hashlib.sha256(candidate['raw_string'].encode()).hexdigest()
                item['status'] = 'candidate_span_located_corpus_not_read'
                pending.pop(key)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('Mention ledger changed during review generation: ' + str(path))
        hashes['merge_out/' + court + '/mentions_candidates.csv'] = logical_sha
    if with_text:
        enrich_corpus(source, list(results.values()))
    for item in results.values():
        if item['status'] == 'original_text_verified':
            proof = dict(item.get('field_selection', {}))
            proof['text_field'] = item['span'].get('text_field', proof.get('text_field'))
            proof['language'] = item['span'].get('language', proof.get('language'))
            item['field_selection'] = _field_proof(proof, policy, verified=True)
            for name, claimed in item.get('_indexed_field_claim', {}).items():
                if claimed is not None and claimed != item['field_selection'].get(name):
                    raise ValueError('Indexed field proof contradicts selected original corpus field: ' + name)
            item['span']['text_policy'] = policy
            item['span']['coordinate_system'] = 'zero-based Unicode code points, half-open in ' + item['field_selection']['text_field']
        else:
            item['field_selection'] = _field_proof(item.get('field_selection', {}), policy)
        item.pop('_indexed_field_claim', None)
        # Original record/span hashes refer to full strings; previews are bounded.
        if item['quote'] is not None:
            item['quote_preview'] = item.pop('quote')[:640]
        if item['candidate']:
            raw = item['candidate'].pop('raw_string')
            item['candidate']['raw_preview'] = raw[:160]
        item.pop('indexed_passage', None)
        item.pop('evidence_generation', None)
        for document in item['source_documents']:
            document['name'] = (document.get('name') or '')[:120]
        item['limitations'] = item['limitations'][:3]
    return results, hashes
