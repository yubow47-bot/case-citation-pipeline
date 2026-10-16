"""Reviewed, native-source proofs that two printed citations name distinct rulings.

These are negative identity facts, not name corrections, court guesses or links.
Every fact binds both citation spans to one unchanged corpus document. Runtime
validation checks the native text as well as the content-addressed table row.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PAIR_FIELDS = (
    'left_merge_key', 'right_merge_key', 'relation_type', 'verification_status',
    'source_court', 'source_decision', 'source_corpus', 'corpus_sha256',
    'corpus_row', 'text_field', 'text_sha256',
    'left_start', 'left_end', 'left_raw', 'right_start', 'right_end', 'right_raw',
    'span_start', 'span_end', 'span_sha256', 'distinction_quote',
    'source_locator', 'reviewer', 'reviewed_at', 'right_proof_json', 'evidence_id',
)
PROOF_FIELDS = ('source_court', 'source_decision', 'source_corpus', 'corpus_sha256',
                'corpus_row', 'text_field', 'text_sha256', 'span_start', 'span_end',
                'span_sha256', 'distinction_quote')
_CACHE = {}


def evidence_id(row):
    payload = {k: v for k, v in row.items() if k != 'evidence_id'}
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return 'pair:' + hashlib.sha256(data.encode('utf-8')).hexdigest()


def _digest(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _native_row(path, index, columns):
    import pyarrow.parquet as pq
    parquet = pq.ParquetFile(path)
    offset = 0
    for group in range(parquet.num_row_groups):
        count = parquet.metadata.row_group(group).num_rows
        if offset <= index < offset + count:
            return parquet.read_row_group(group, columns=columns).slice(index - offset, 1).to_pylist()[0]
        offset += count
    raise ValueError('Pair separation corpus row is outside the source')


def load_pair_separations(path=None, root=None, keys=None):
    """Return verified negative facts, failing closed on missing/stale provenance.

    A repository predating the optional table has no reviewed pair facts. An
    explicitly named missing table is an error. A keys scope only consumes facts
    with both endpoints present; unrelated offline fixtures need no corpus.
    Source byte hashes are checked on every call. Only native Parquet parsing
    and citation binding are cached for identical table and source bytes.
    """
    root = Path(root or ROOT).resolve()
    explicit = path is not None
    path = Path(path) if explicit else root / 'decisions/identity_pair_separations.csv'
    if not path.is_file():
        if explicit:
            raise FileNotFoundError(path)
        return []
    raw = path.read_bytes()
    if len(raw) > 1024 * 1024:
        raise ValueError('Pair separation table exceeds the byte budget')
    with path.open(encoding='utf-8-sig', newline='') as source:
        reader = csv.DictReader(source, strict=True)
        if tuple(reader.fieldnames or ()) != PAIR_FIELDS:
            raise ValueError('Pair separation columns are missing, duplicate or unexpected')
        rows = list(reader)
    if keys is not None:
        live_keys = set(keys)
        rows = [row for row in rows if row.get('left_merge_key') in live_keys
                and row.get('right_merge_key') in live_keys]
    pairs, ids, source_paths = set(), set(), set()
    for row in rows:
        if None in row or any(not isinstance(v, str) or not v.strip() for v in row.values()):
            raise ValueError('Pair separation lacks complete provenance')
        keys = (row['left_merge_key'], row['right_merge_key'])
        if any(len(k.split('|')) != 5 or not k.split('|')[2] or not k.split('|')[4] for k in keys):
            raise ValueError('Pair separation has an incomplete citation key')
        pair = tuple(sorted(keys))
        if (keys[0] == keys[1] or pair in pairs or row['evidence_id'] in ids
                or row['relation_type'] != 'verified_distinct_decisions'
                or row['verification_status'] != 'verified_corpus_distinct_decisions'
                or row['evidence_id'] != evidence_id(row)
                or row['text_field'] not in ('unofficial_text_en', 'unofficial_text_fr')
                or not re.fullmatch(r'[A-Z][A-Z0-9]*_.+', row['source_decision'])
                or row['source_court'] != row['source_decision'].split('_', 1)[0]
                or row['source_corpus'] != 'corpus/' + row['source_court'] + '.parquet'
                or not row['source_locator'].startswith('audit/findings/')
                or '..' in row['source_locator'].replace('\\', '/').split('/')):
            raise ValueError('Pair separation has malformed or duplicate provenance')
        for field in ('corpus_sha256', 'text_sha256', 'span_sha256'):
            if not re.fullmatch(r'[0-9a-f]{64}', row[field]):
                raise ValueError('Pair separation has an invalid source hash')
        for field in ('corpus_row', 'left_start', 'left_end', 'right_start', 'right_end', 'span_start', 'span_end'):
            if not row[field].isdigit():
                raise ValueError('Pair separation has an invalid source offset')
        try:
            right_proof = json.loads(row['right_proof_json'])
        except (TypeError, ValueError) as exc:
            raise ValueError('Pair separation has an invalid right source proof') from exc
        if (not isinstance(right_proof, dict) or set(right_proof) != set(PROOF_FIELDS)
                or any(not isinstance(v, str) or not v for v in right_proof.values())):
            raise ValueError('Pair separation right source proof is incomplete')
        for side in ('left', 'right'):
            start, end = int(row[side + '_start']), int(row[side + '_end'])
            proof = row if side == 'left' else right_proof
            if (any(not proof[k].isdigit() for k in ('corpus_row', 'span_start', 'span_end'))
                    or not (int(proof['span_start']) <= start < end <= int(proof['span_end']))):
                raise ValueError('Pair separation citation is outside its proof span')
            if (proof['text_field'] not in ('unofficial_text_en', 'unofficial_text_fr')
                    or proof['source_court'] != proof['source_decision'].split('_', 1)[0]
                    or proof['source_corpus'] != 'corpus/' + proof['source_court'] + '.parquet'
                    or any(not re.fullmatch(r'[0-9a-f]{64}', proof[k]) for k in
                           ('corpus_sha256', 'text_sha256', 'span_sha256'))):
                raise ValueError('Pair separation right source proof is malformed')
            source_path = root / proof['source_corpus']
            if not source_path.is_file() or source_path.is_symlink():
                raise ValueError('Pair separation source corpus is missing or linked')
            source_paths.add(source_path)
        pairs.add(pair)
        ids.add(row['evidence_id'])
    digests = {p: _digest(p) for p in sorted(source_paths)}
    policy_files = set((ROOT/'decisions').glob('*.csv')) | set((root/'decisions').glob('*.csv'))
    signature = (str(root), str(path.resolve()), hashlib.sha256(raw).hexdigest(),
                 tuple(row['evidence_id'] for row in rows),
                 tuple((str(p), digest) for p, digest in digests.items()),
                 tuple((str(p), _digest(p)) for p in sorted(policy_files)))
    if signature in _CACHE:
        return copy.deepcopy(_CACHE[signature])
    native = {}
    output = []
    for row in rows:
        right_proof = json.loads(row['right_proof_json'])
        from extract import source_decision_citation
        # The citation-to-key binding is checked through production extraction,
        # classification and key construction, rather than trusting the table.
        from extract import extract_candidates
        from classify import Classifier, load_runtime_tables
        from merge import build_merge_key_v2, apply_reporter_identity_fixes
        from collections import Counter
        tables = load_runtime_tables()
        classifier = Classifier(tables, Counter())
        for side in ('left', 'right'):
            proof = row if side == 'left' else right_proof
            source_path = root / proof['source_corpus']
            if digests[source_path] != proof['corpus_sha256']:
                raise ValueError('Pair separation source corpus hash changed')
            locale = proof['text_field'].rsplit('_', 1)[1]
            record_key = (source_path, int(proof['corpus_row']), proof['text_field'])
            if record_key not in native:
                native[record_key] = _native_row(source_path, record_key[1],
                                                [proof['text_field'], 'citation_' + locale])
            record = native[record_key]
            citation = record.get('citation_' + locale) or ''
            if source_decision_citation(proof['source_court'], citation) != proof['source_decision']:
                raise ValueError('Pair separation source document is misbound')
            text = record.get(proof['text_field']) or ''
            if hashlib.sha256(text.encode('utf-8')).hexdigest() != proof['text_sha256']:
                raise ValueError('Pair separation source text changed')
            span = text[int(proof['span_start']):int(proof['span_end'])]
            if (hashlib.sha256(span.encode('utf-8')).hexdigest() != proof['span_sha256']
                    or proof['distinction_quote'] not in span):
                raise ValueError('Pair separation distinction span changed')
            if text[int(row[side + '_start']):int(row[side + '_end'])] != row[side + '_raw']:
                raise ValueError('Pair separation citation span is misbound')
            candidates, _ = extract_candidates(text, proof['source_decision'], '',
                                                int(proof['corpus_row']), proof['source_court'])
            classified = [classifier.run_row(dict(c)) for c in candidates]
            # The production key includes verified continuous-volume year
            # normalization. Preserve that exact policy rather than comparing
            # a pre-merge printed year against a post-merge identity key.
            apply_reporter_identity_fixes({proof['source_decision']: classified}, Counter())
            found = {build_merge_key_v2(c) for c in classified
                     if int(c['match_start_offset']) == int(row[side + '_start'])
                     and int(c['match_end_offset']) == int(row[side + '_end'])}
            if row[side + '_merge_key'] not in found:
                raise ValueError('Pair separation citation does not print its claimed key: '
                                 + side + ' ' + row[side + '_merge_key']
                                 + ' in ' + proof['source_decision'])
        output.append({**row, 'table_evidence_id': row['evidence_id'],
                       'source_detail': {'artifact': path.relative_to(root).as_posix(),
                                         'table_evidence_id': row['evidence_id'],
                                         'source_corpus': row['source_corpus'],
                                         'corpus_row': row['corpus_row'],
                                         'source_decision': row['source_decision'],
                                         'text_field': row['text_field'],
                                         'span_start': row['span_start'],
                                         'span_end': row['span_end'],
                                         'span_sha256': row['span_sha256'],
                                         'right_source': right_proof,
                                         'source_locator': row['source_locator']}})
    _CACHE.clear()
    _CACHE[signature] = copy.deepcopy(output)
    return output
