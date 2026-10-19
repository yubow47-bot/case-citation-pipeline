"""Source-row integrity contract. Never rewrite a source ID or remove a raw row.

Native dates come only from labelled judicial headers, never citation years.
The CSV is the downstream contract; the input parquet remains unchanged.
"""
from collections import Counter, defaultdict
import argparse
import csv
import datetime as dt
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

from corpus_fields import POLICY_EN, POLICIES, projection, select_record
from normalize import nk

VERSION = 'source-integrity-1'
FIELDS = ['source_id', 'source_decision_citation', 'court', 'corpus_row_index',
          'selected_citation', 'text_field', 'text_sha256', 'text_characters',
          'provider_date', 'provider_decision_year', 'native_decision_date',
          'native_date_status', 'date_conflict_status', 'source_decision_year',
          'decision_year_basis', 'native_date_evidence_json',
          'own_citation_checked', 'native_own_citation', 'own_citation_status',
          'native_citation_evidence_json', 'citation_provider_year_conflict',
          'duplicate_text_source_count', 'duplicate_text_sources',
          'text_integrity_status', 'text_integrity_evidence_json',
          'source_measurable', 'quarantine_reason']

CONTENT = re.compile(r'(?im)^[ \t]*(?:Decision Content|Contenu de la décision)[ \t]*$')
BODY = re.compile(r'(?im)^[ \t]*(?:\[\d{1,5}\][ \t]*|'
                  r'(?:JUDGMENT AND REASONS|REASONS FOR DECISION|ENDORSEMENT|'
                  r'ORDER|JUDGMENT|MOTIFS DU JUGEMENT)[ \t]*$|UPON\b|THE COURT:)')
FORMAL = re.compile(r'(?im)^[ \t]*(?:CITATION|RÉFÉRENCE|DOCKETS?)[ \t]*:')
DATE = re.compile(r'(?im)^[ \t]*DATE[ \t]*:[ \t]*(?:\r?\n[ \t]*)?'
                  r'\(?(?P<date>\d{4}(?:[-/]\d{2}[-/]\d{2}|\d{4}))\)?[ \t]*\r?$')
CITATION = re.compile(r'(?im)^[ \t]*(?:CITATION|RÉFÉRENCE)[ \t]*:')
HEADER_FIELD = re.compile(r'(?m)^[ \t]*[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ /()-]{1,60}[ \t]*:')
NEUTRAL = re.compile(r'(?<!\w)(?P<year>(?:18|19|20)\d{2})[ \t]*'
                     r'(?P<code>[A-Z][A-Z.]{1,11})[ \t]*(?P<number>\d{1,7})(?!\w)')
SIGNATURE = re.compile(
    r'^(?:["“”\']\s*[A-Z][\w .,\'’()-]{0,80},\s*(?:[A-Z]\.){1,4}["“”\']|'
    r'The Honourable (?:Mr\.? |Madam |Chief )?(?:Justice|Judge) [A-Z][\w .,\'’()-]{0,80})$')


def inspect_content(selected):
    """Recognize positively identified header-and-signature remnants.

    No word-count threshold is used. Any unaccounted-for text keeps a short
    order observable; absent reasons markers alone never establish truncation.
    """
    text = selected.get('text') or ''
    if not text.strip():
        return {'text_integrity_status': 'MISSING_TEXT', 'text_integrity_evidence_json': '[]'}
    name = nk(selected.get('name') or '')
    citation = nk(selected.get('citation') or '')
    content = CONTENT.search(text)
    offset = content.end() if content else 0
    evidence = []
    roles = set()
    for raw in text[offset:].splitlines(keepends=True):
        line = raw.strip()
        start = offset
        offset += len(raw)
        if not line:
            continue
        role = ''
        if SIGNATURE.fullmatch(line):
            role = 'judicial_signature'
        elif (name and nk(line) == name) or (citation and nk(line) == citation):
            role = 'metadata_title'
        else:
            matches = _neutral_matches(line)
            if len(matches) == 1 and matches[0][1].start() == 0:
                match = matches[0][1]
                title = nk(line[match.end():])
                if nk(match.group()) == citation and name and title == name:
                    role = 'metadata_title'
        if not role:
            return {'text_integrity_status': 'PRESENT_UNVERIFIED',
                    'text_integrity_evidence_json': '[]'}
        roles.add(role)
        evidence.append({'role': role, 'start': start, 'end': offset})
    incomplete = roles == {'metadata_title', 'judicial_signature'}
    return {'text_integrity_status': 'INCOMPLETE_HEADER_SIGNATURE' if incomplete else 'PRESENT_UNVERIFIED',
            'text_integrity_evidence_json': json.dumps(evidence if incomplete else [])}


@lru_cache(maxsize=1)
def _neutral_policy():
    """Use only registered codes and already accepted bilingual equivalences."""
    from identity_evidence import load_bilingual
    path = Path(__file__).resolve().parents[1] / 'decisions/neutral_court_codes.csv'
    with path.open(encoding='utf-8-sig', newline='') as stream:
        codes = {nk(row['court_code']) for row in csv.DictReader(stream)}
    parent = {code: code for code in codes}

    def root(code):
        parent.setdefault(code, code)
        while parent[code] != code:
            parent[code] = parent[parent[code]]
            code = parent[code]
        return code

    for pair in load_bilingual():
        left, right = sorted(pair)
        a, b = root(left), root(right)
        parent[max(a, b)] = min(a, b)
    return codes, {code: root(code) for code in parent}


def _neutral_matches(text):
    codes, aliases = _neutral_policy()
    result = []
    for match in NEUTRAL.finditer(text):
        code = nk(match['code'])
        if code in codes:
            key = '%s:%s:%d' % (match['year'], aliases.get(code, code), int(match['number']))
            result.append((key, match))
    return result


def inspect_own_citation(selected):
    """Compare explicit own-header neutral citations with selected metadata.

    A body reference or an unlabelled web metadata field cannot establish an
    own citation. Unknown and ambiguous headers are retained as review states.
    """
    text = selected.get('text') or ''
    start, end = header_region(text)
    header = text[start:end]
    native = {}
    evidence = []
    # A Citation label by itself could be a quoted reference. Require another
    # printed judicial-header field before accepting it as source evidence.
    formal = re.search(r'(?im)^[ \t]*(?:DATE|DOCKETS?)[ \t]*:', header)
    if formal:
        for label in CITATION.finditer(header):
            following = HEADER_FIELD.search(header, label.end())
            stop = following.start() if following else len(header)
            block = header[label.end():stop]
            for key, match in _neutral_matches(block):
                native[key] = match.group()
                evidence.append({'citation': match.group(),
                                 'start': start + label.end() + match.start(),
                                 'end': start + label.end() + match.end()})
    metadata = {key for key, _ in _neutral_matches(selected.get('citation') or '')}
    if not native:
        status = 'NO_VERIFIED_NATIVE_CITATION'
    elif len(native) > 1:
        status = 'AMBIGUOUS_NATIVE_CITATION'
    elif len(metadata) != 1:
        status = 'METADATA_NOT_COMPARABLE'
    elif set(native) == metadata:
        status = 'MATCH'
    else:
        status = 'MISMATCH'
    provider = selected.get('date')
    year = str(provider.year) if isinstance(provider, dt.date) else ''
    return {'own_citation_checked': True,
            'native_own_citation': ' | '.join(native[k] for k in sorted(native)),
            'own_citation_status': status,
            'native_citation_evidence_json': json.dumps(evidence, ensure_ascii=False),
            'citation_provider_year_conflict': bool(year and len(metadata) == 1 and
                                                   next(iter(metadata)).split(':')[0] != year)}


def header_region(text):
    """Skip the provider web wrapper and stop at the first printed body marker."""
    content = CONTENT.search(text)
    start = content.end() if content else 0
    body = BODY.search(text, start)
    end = body.start() if body else len(text)
    return start, end


def resolve_date(selected):
    text = selected.get('text') or ''
    provider = selected.get('date')
    provider_day = provider.date() if isinstance(provider, dt.datetime) else provider
    if not isinstance(provider_day, dt.date):
        provider_day = None
    start, end = header_region(text)
    header = text[start:end]
    evidence = []
    invalid = False
    if FORMAL.search(header):
        for match in DATE.finditer(header):
            raw = re.sub(r'[-/]', '', match['date'])
            try:
                day = dt.date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
            except ValueError:
                invalid = True
                continue
            evidence.append({'date': day.isoformat(), 'start': start + match.start(),
                             'end': start + match.end()})
    dates = sorted({r['date'] for r in evidence})
    native = dates[0] if len(dates) == 1 and not invalid else ''
    native_status = ('VALID_FORMAL_HEADER' if native else
                     'AMBIGUOUS_NATIVE_DATES' if len(dates) > 1 else
                     'INVALID_NATIVE_DATE' if invalid else 'NO_VERIFIED_NATIVE_DATE')
    provider_year = str(provider_day.year) if provider_day else ''
    year = native[:4] if native else provider_year
    conflict = 'NOT_COMPARABLE'
    if native and provider_day:
        conflict = ('MATCH' if native == provider_day.isoformat() else
                    'YEAR_CONFLICT' if native[:4] != provider_year else 'DATE_CONFLICT')
    return {'provider_date': provider.isoformat() if isinstance(provider, dt.date) else '',
            'provider_decision_year': provider_year, 'native_decision_date': native,
            'native_date_status': native_status, 'date_conflict_status': conflict,
            'source_decision_year': year,
            'decision_year_basis': 'NATIVE_FORMAL_HEADER' if native else
                                   'PROVIDER_DATE' if provider_day else 'UNAVAILABLE',
            'native_date_evidence_json': json.dumps(evidence, ensure_ascii=False)}


def inspect_source(selected, court, row_index):
    text = selected.get('text') or ''
    citation = selected.get('citation') or ''
    sid = court + '_' + nk(citation)
    reasons = []
    if not text.strip():
        reasons.append('MISSING_TEXT')
    if not citation.strip():
        reasons.append('MISSING_SOURCE_CITATION')
    own = inspect_own_citation(selected)
    if own['own_citation_status'] == 'MISMATCH':
        reasons.append('SOURCE_CITATION_MISMATCH')
    content = inspect_content(selected)
    if content['text_integrity_status'] == 'INCOMPLETE_HEADER_SIGNATURE':
        reasons.append('INCOMPLETE_TEXT')
    return {'source_id': sid, 'source_decision_citation': sid, 'court': court,
            'corpus_row_index': row_index, 'selected_citation': citation,
            'text_field': selected.get('text_field', ''),
            'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'text_characters': len(text), **resolve_date(selected), **own, **content,
            'duplicate_text_source_count': 1, 'duplicate_text_sources': '[]',
            'source_measurable': not reasons, 'quarantine_reason': ';'.join(reasons)}


def annotate_duplicate_texts(records):
    """Cross-source equality is evidence for review, never authority to merge IDs."""
    by_hash = defaultdict(set)
    for row in records:
        if row['text_characters']:
            by_hash[row['text_sha256']].add(row['source_id'])
    groups = {key: sorted(ids) for key, ids in by_hash.items() if len(ids) > 1}
    for row in records:
        ids = groups.get(row['text_sha256'])
        if ids:
            row['duplicate_text_source_count'] = len(ids)
            row['duplicate_text_sources'] = json.dumps(ids)
    return groups


def _write(path, records):
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)
    temporary.replace(path)


def build_source_records(courts, corpus_dir, text_policy, output,
                         batch_size=500, limit_batches=None):
    """Inspect every physical row, including zero-citation and missing-text rows."""
    import pyarrow.parquet as pq
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for court in courts:
        parquet = pq.ParquetFile(Path(corpus_dir) / (court + '.parquet'))
        offset = 0
        for batch_index, batch in enumerate(parquet.iter_batches(
                batch_size=batch_size, columns=projection(parquet.schema_arrow.names))):
            if limit_batches is not None and batch_index >= limit_batches:
                break
            for i, raw in enumerate(batch.to_pylist(), offset):
                records.append(inspect_source(select_record(raw, text_policy), court, i))
            offset += batch.num_rows
    duplicate_groups = annotate_duplicate_texts(records)
    _write(output / 'source_records.csv', records)
    anomalies = [r for r in records if not r['source_measurable'] or
                 r['date_conflict_status'] in {'YEAR_CONFLICT', 'DATE_CONFLICT'} or
                 r['native_date_status'] in {'AMBIGUOUS_NATIVE_DATES', 'INVALID_NATIVE_DATE'} or
                 r['own_citation_status'] in {'MISMATCH', 'AMBIGUOUS_NATIVE_CITATION'} or
                 r['citation_provider_year_conflict'] or r['duplicate_text_source_count'] > 1]
    _write(output / 'source_anomalies.csv', anomalies)
    _write(output / 'own_citation_mismatches.csv',
           [r for r in records if r['own_citation_status'] == 'MISMATCH'])
    (output / 'duplicate_text_groups.json').write_text(
        json.dumps(duplicate_groups, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    by_court = defaultdict(Counter)
    for r in records:
        count = by_court[r['court']]
        count['rows'] += 1
        count['measurable'] += r['source_measurable']
        count['quarantined'] += not r['source_measurable']
        count['year_changed'] += r['source_decision_year'] != r['provider_decision_year']
        count['native_date_' + r['native_date_status']] += 1
        count['date_' + r['date_conflict_status']] += 1
        count['own_citation_checked'] += r['own_citation_checked']
        count['own_citation_' + r['own_citation_status']] += 1
        count['duplicate_text_rows'] += r['duplicate_text_source_count'] > 1
        count['text_' + r['text_integrity_status']] += 1
    summary = {'schema_version': VERSION, 'courts': list(courts),
               'text_policy': text_policy, 'corpus_dir': str(Path(corpus_dir).resolve()),
               'batch_size': batch_size, 'limit_batches': limit_batches,
               'rows': len(records), 'anomaly_rows': len(anomalies),
               'own_citation_checked': sum(r['own_citation_checked'] for r in records),
               'duplicate_text_groups': len(duplicate_groups),
               'by_court': dict(by_court)}
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n',
                                       encoding='utf-8')
    return summary


def load_source_records(path):
    """Return source-ID records; reject conflicting dispositions for repeated IDs."""
    path = Path(path)
    if path.is_dir():
        path /= 'source_records.csv'
    result = {}
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        required = {'source_id', 'source_measurable', 'source_decision_year', 'quarantine_reason'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('Invalid source integrity schema')
        for row in reader:
            if row['source_measurable'].lower() not in {'true', 'false'}:
                raise ValueError('Invalid source measurability flag')
            row['source_measurable'] = row['source_measurable'].lower() == 'true'
            old = result.get(row['source_id'])
            if old and any(old[k] != row[k] for k in required - {'source_id'}):
                raise ValueError('Conflicting source integrity rows: ' + row['source_id'])
            result[row['source_id']] = row
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--court', '--corpus', action='append', required=True, dest='courts')
    parser.add_argument('--corpus-dir', required=True)
    parser.add_argument('--text-policy', choices=POLICIES, default=POLICY_EN)
    parser.add_argument('--out', required=True)
    parser.add_argument('--batch-size', type=int, default=500)
    parser.add_argument('--limit-batches', type=int)
    args = parser.parse_args(argv)
    summary = build_source_records(args.courts, args.corpus_dir, args.text_policy,
                                   args.out, args.batch_size, args.limit_batches)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
