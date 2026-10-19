"""Table-driven document structure; independent of citation or court inference.

Markers refer only to printed headings and paragraph structure. Missing or
contradictory boundaries remain unknown. Offsets always address selected native
corpus text, without whitespace normalization.
"""
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re

from corpus_fields import select_record, projection
from normalize import nk

TABLE = Path(__file__).resolve().parents[1] / 'decisions/document_zone_markers.csv'
ROLES = {'reasons_delivery', 'reasons_paragraph', 'numbered_paragraph',
         'reasons_title', 'appeal_start', 'appeal_end'}
FIELDS = ['source_decision_citation', 'corpus_row_index', 'text_field',
          'text_sha256', 'text_length', 'status', 'reasons_start',
          'appeal_spans_json', 'marker_evidence_json', 'table_sha256']


def load_markers(path=TABLE):
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    result = defaultdict(list)
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ['court', 'marker', 'zone_role', 'source', 'source_locator']:
            raise ValueError('Invalid document-zone marker schema')
        for line, row in enumerate(reader, 2):
            if any(not row.get(k) for k in reader.fieldnames) or row['zone_role'] not in ROLES:
                raise ValueError('Unverified document-zone marker row')
            result[row['court']].append((re.compile(row['marker']), row['zone_role'],
                {'table': 'decisions/document_zone_markers.csv', 'row': line,
                 'sha256': digest, 'source': row['source'],
                 'source_locator': row['source_locator']}))
    return result, digest


def locate(text, markers):
    hits = defaultdict(list)
    for regex, role, evidence in markers:
        for match in regex.finditer(text):
            hits[role].append({'start': match.start(), 'end': match.end(),
                               'printed': match.group(), **evidence})
    for values in hits.values():
        values.sort(key=lambda x: (x['start'], x['end'], x['row']))
    used = []
    if hits['reasons_delivery']:
        first = hits['reasons_delivery'][0]
    elif hits['reasons_paragraph']:
        first = hits['reasons_paragraph'][0]
        # An earlier numbered paragraph makes a later [1] a possible footnote.
        if any(h['start'] < first['start'] for h in hits['numbered_paragraph']):
            return {'status': 'ambiguous_paragraph_order', 'reasons_start': -1,
                    'appeal_spans': [], 'evidence': []}
        titles = [h for h in hits['reasons_title'] if h['start'] <= first['start']]
        if titles:
            used.append(first)
            first = titles[-1]
    else:
        return {'status': 'no_verified_boundary', 'reasons_start': -1,
                'appeal_spans': [], 'evidence': []}
    used.append(first)
    reasons = first['start']
    starts = [h for h in hits['appeal_start'] if h['start'] < reasons]
    spans = []
    for i, start in enumerate(starts):
        limit = starts[i+1]['start'] if i+1 < len(starts) else reasons
        ends = [h for h in hits['appeal_end'] if start['end'] <= h['start'] <= limit]
        end = ends[0]['start'] if ends else limit
        if end > start['start']:
            spans.append([start['start'], end]); used.append(start)
            if ends:
                used.append(ends[0])
    return {'status': 'located', 'reasons_start': reasons,
            'appeal_spans': spans, 'evidence': used}


def position_zone(boundary, start, end):
    if not boundary or boundary['reasons_start'] < 0 or start < 0 or end <= start:
        return 'unknown'
    rs = boundary['reasons_start']
    if start >= rs:
        return 'reasons'
    if end > rs:
        return 'unknown'
    for left, right in boundary['appeal_spans']:
        if left <= start and end <= right:
            return 'appeal_block'
        if start < right and end > left:
            return 'unknown'
    return 'headnote'


def build_index(corpus, court, policy, output):
    """Read each source once; never interpret another citation candidate."""
    import pyarrow.parquet as pq
    markers, digest = load_markers()
    parquet = pq.ParquetFile(corpus)
    index = {}; offset = 0
    target = Path(output) / 'document_zones.csv'
    temporary = target.with_suffix('.csv.tmp')
    with temporary.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS); writer.writeheader()
        for batch in parquet.iter_batches(batch_size=128, columns=projection(parquet.schema_arrow.names)):
            for i, native in enumerate(batch.to_pylist(), offset):
                record = select_record(native, policy)
                text = record['text']
                sid = court + '_' + nk(record['citation'])
                boundary = locate(text, markers.get(court, []))
                index[i] = (sid, boundary)
                writer.writerow({'source_decision_citation': sid, 'corpus_row_index': i,
                    'text_field': record['text_field'],
                    'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                    'text_length': len(text), 'status': boundary['status'],
                    'reasons_start': boundary['reasons_start'],
                    'appeal_spans_json': json.dumps(boundary['appeal_spans']),
                    'marker_evidence_json': json.dumps(boundary['evidence'], ensure_ascii=False),
                    'table_sha256': digest})
            offset += batch.num_rows
    temporary.replace(target)
    return index


def edge_zones(zones):
    """All counted occurrences must support a history-only classification."""
    zones = list(zones)
    own = bool(zones) and all(z == 'appeal_block' for z in zones)
    if not zones or any(z not in {'headnote', 'appeal_block', 'reasons'} for z in zones):
        return str(own).lower(), 'unknown'
    head = any(z in {'headnote', 'appeal_block'} for z in zones)
    body = 'reasons' in zones
    return str(own).lower(), 'both' if head and body else 'headnote_only' if head else 'reasons_only'
