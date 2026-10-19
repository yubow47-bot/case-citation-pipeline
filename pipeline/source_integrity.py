"""Source-row integrity contract. Never rewrite a source ID or remove a raw row.

Native dates come only from labelled judicial headers, never citation years.
The CSV is the downstream contract; the input parquet remains unchanged.
"""
from collections import Counter, defaultdict
import argparse
import csv
import datetime as dt
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
          'source_measurable', 'quarantine_reason']

CONTENT = re.compile(r'(?im)^[ \t]*(?:Decision Content|Contenu de la décision)[ \t]*$')
BODY = re.compile(r'(?im)^[ \t]*(?:\[\d{1,5}\][ \t]*|'
                  r'(?:JUDGMENT AND REASONS|REASONS FOR DECISION|ENDORSEMENT|'
                  r'ORDER|JUDGMENT|MOTIFS DU JUGEMENT)[ \t]*$|UPON\b|THE COURT:)')
FORMAL = re.compile(r'(?im)^[ \t]*(?:CITATION|RÉFÉRENCE|DOCKETS?)[ \t]*:')
DATE = re.compile(r'(?im)^[ \t]*DATE[ \t]*:[ \t]*(?:\r?\n[ \t]*)?'
                  r'\(?(?P<date>\d{4}(?:[-/]\d{2}[-/]\d{2}|\d{4}))\)?[ \t]*\r?$')


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
    return {'source_id': sid, 'source_decision_citation': sid, 'court': court,
            'corpus_row_index': row_index, 'selected_citation': citation,
            'text_field': selected.get('text_field', ''),
            'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'text_characters': len(text), **resolve_date(selected),
            'source_measurable': not reasons, 'quarantine_reason': ';'.join(reasons)}


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
    _write(output / 'source_records.csv', records)
    anomalies = [r for r in records if not r['source_measurable'] or
                 r['date_conflict_status'] in {'YEAR_CONFLICT', 'DATE_CONFLICT'} or
                 r['native_date_status'] in {'AMBIGUOUS_NATIVE_DATES', 'INVALID_NATIVE_DATE'}]
    _write(output / 'source_anomalies.csv', anomalies)
    by_court = defaultdict(Counter)
    for r in records:
        count = by_court[r['court']]
        count['rows'] += 1
        count['measurable'] += r['source_measurable']
        count['quarantined'] += not r['source_measurable']
        count['year_changed'] += r['source_decision_year'] != r['provider_decision_year']
        count['native_date_' + r['native_date_status']] += 1
        count['date_' + r['date_conflict_status']] += 1
    summary = {'schema_version': VERSION, 'courts': list(courts),
               'text_policy': text_policy, 'corpus_dir': str(Path(corpus_dir).resolve()),
               'batch_size': batch_size, 'limit_batches': limit_batches,
               'rows': len(records), 'anomaly_rows': len(anomalies),
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
