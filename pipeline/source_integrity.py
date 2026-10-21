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
from artifacts import open_csv
from normalize import nk

VERSION = 'source-integrity-2'
FIELDS = ['source_id', 'source_decision_citation', 'court', 'corpus_row_index',
          'selected_citation', 'text_field', 'text_sha256', 'text_characters',
          'provider_date', 'provider_decision_year', 'native_decision_date',
          'native_date_status', 'date_conflict_status', 'source_decision_year',
          'decision_year_basis', 'native_date_evidence_json',
          'own_citation_checked', 'native_own_citation', 'own_citation_status',
          'native_citation_evidence_json', 'citation_provider_year_conflict',
          'duplicate_text_source_count', 'duplicate_text_sources',
          'text_integrity_status', 'text_integrity_evidence_json',
          # method card 09, N8: a model-selected header date only corroborates the
          # provider year; it never changes source_decision_year.
          'model_native_date', 'model_date_p', 'model_date_status',
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
POLICY_PATH = Path(__file__).resolve().parents[1] / 'decisions/source_integrity_policy.csv'


@lru_cache(maxsize=1)
def source_policy():
    with POLICY_PATH.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    expected = {'native_year_min', 'native_year_ahead_allowance', 'year_conflict_requires_citation_support'}
    if {r['policy'] for r in rows} != expected or len(rows) != len(expected):
        raise ValueError('Invalid source integrity policy keys')
    if any(not r.get('source') or not r.get('source_locator') or not r.get('notes') for r in rows):
        raise ValueError('Source integrity policy needs evidence and rationale')
    values = {r['policy']: int(r['value']) for r in rows}
    if any(value < 1 for value in values.values()):
        raise ValueError('Invalid source integrity policy value')
    return values


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
        if code in codes and not _malformed_neutral(match, text):
            key = '%s:%s:%d' % (match['year'], aliases.get(code, code), int(match['number']))
            result.append((key, match))
    return result


def _malformed_neutral(match, text):
    # A zero followed by another integer is a malformed code/number boundary,
    # not decision zero (e.g. printed "2002 BCCA0 402").
    return int(match['number']) == 0 or bool(re.match(r'[ \t]+\d', text[match.end():]))


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
    malformed = False
    # A Citation label by itself could be a quoted reference. Require another
    # printed judicial-header field before accepting it as source evidence.
    formal = re.search(r'(?im)^[ \t]*(?:DATE|DOCKETS?)[ \t]*:', header)
    if formal:
        for label in CITATION.finditer(header):
            following = HEADER_FIELD.search(header, label.end())
            stop = following.start() if following else len(header)
            block = header[label.end():stop]
            codes, _ = _neutral_policy()
            for raw in NEUTRAL.finditer(block):
                if nk(raw['code']) in codes and _malformed_neutral(raw, block):
                    malformed = True
                    evidence.append({'citation': raw.group(), 'malformed': True,
                                     'start': start + label.end() + raw.start(),
                                     'end': start + label.end() + raw.end()})
            for key, match in _neutral_matches(block):
                native[key] = match.group()
                evidence.append({'citation': match.group(),
                                 'start': start + label.end() + match.start(),
                                 'end': start + label.end() + match.end()})
    metadata = {key for key, _ in _neutral_matches(selected.get('citation') or '')}
    if malformed:
        status = 'MALFORMED_NATIVE_CITATION'
    elif not native:
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
    adopted = bool(native)
    if native:
        policy = source_policy()
        native_year = int(native[:4])
        metadata_years = {int(key.split(':')[0])
                          for key, _ in _neutral_matches(selected.get('citation') or '')}
        supported_years = metadata_years | ({provider_day.year} if provider_day else set())
        if native_year < policy['native_year_min'] or (supported_years and
                native_year > max(supported_years) + policy['native_year_ahead_allowance']):
            adopted = False
            native_status = 'OUT_OF_RANGE_NATIVE_DATE'
        elif (provider_day and native_year != provider_day.year and
              policy['year_conflict_requires_citation_support'] and metadata_years != {native_year}):
            adopted = False
            native_status = 'UNRESOLVED_NATIVE_YEAR_CONFLICT'
    year = native[:4] if adopted else provider_year
    conflict = 'NOT_COMPARABLE'
    if native and provider_day:
        conflict = ('MATCH' if native == provider_day.isoformat() else
                    'YEAR_CONFLICT' if native[:4] != provider_year else 'DATE_CONFLICT')
        if not adopted and conflict != 'MATCH':
            conflict += '_UNRESOLVED'
    return {'provider_date': provider.isoformat() if isinstance(provider, dt.date) else '',
            'provider_decision_year': provider_year, 'native_decision_date': native,
            'native_date_status': native_status, 'date_conflict_status': conflict,
            'source_decision_year': year,
            'decision_year_basis': 'NATIVE_FORMAL_HEADER' if adopted else
                                   'PROVIDER_UNRESOLVED_NATIVE_DATE' if native and provider_day else
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
        if row['text_characters'] and row.get('text_integrity_status') != 'MISSING_TEXT':
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


N8_STATUSES = {'NO_VERIFIED_NATIVE_DATE', 'AMBIGUOUS_NATIVE_DATES', 'INVALID_NATIVE_DATE'}


def _queue_date(jev, record, selected, asks):
    """N8 scope: no single verified header date, or a provider/native disagreement."""
    import jev_nodes as jn
    if not (record['native_date_status'] in N8_STATUSES or
            'CONFLICT' in record['date_conflict_status']):
        return
    if not record['provider_decision_year']:
        return  # nothing to corroborate
    if jev.cfg.get('english_only', True) and not jn.is_english(record.get('text_field')):
        record['model_date_status'] = 'MODEL_SKIPPED_FRENCH'
        return
    text = selected.get('text') or ''
    start, end = header_region(text)
    header = text[start:min(end, start + 3000)]
    dates = jn.header_dates(header)
    if not dates:
        record['model_date_status'] = 'MODEL_NO_CANDIDATE_DATES'
        return
    asks.append((record, dates, jn.n8_state(header, dates), jn.n8_question(dates)))


def _ask_dates(jev, asks, output):
    import jev_client as jc
    import jev_nodes as jn
    asks, dropped = jc.cap(asks, jev.node_cfg('N8_source_date').get('max_questions_per_run'), 'N8')
    answers = jev.ask_many('N8_source_date', [(st, qs) for _, _, st, qs in asks])
    ledger = []
    for (record, dates, state, qs), (ckey, resp) in zip(asks, answers):
        ans = ((resp or {}).get('answers') or {}).get('judgment_date')
        decision, why = jc.gate(jev.cfg, 'T1', ans, abstain={'none'})
        if decision == 'adopt' and not jc.level_allowed(jev.cfg, 'L1'):
            decision, why = 'reject', 'level_disabled'
        status = 'MODEL_NOT_ADOPTED'
        pick = jn.option_index((ans or {}).get('choice', ''), 'D', len(dates))
        if decision == 'adopt' and pick is None:
            decision, why = 'reject', 'unknown_option'
        if decision == 'adopt':
            iso = dates[pick][0]
            record['model_native_date'] = iso
            record['model_date_p'] = round(jc.choice_metrics(ans)[1], 4)
            # Corroboration only: a different year is a conflict flag, never an override.
            if iso[:4] == record['provider_decision_year']:
                status = 'MODEL_SELECTED_HEADER_DATE'
            else:
                status, decision, why = 'MODEL_DATE_CONFLICT', 'reject', 'year_differs_from_provider'
        record['model_date_status'] = status
        ledger.append(jc.ledger_row('N8_source_date', record['source_id'], 'L1', 'judgment_date',
                                    qs, resp, decision, why, ckey, state=state))
    jc.write_ledger(Path(output) / 'jev' / 'N8_source_date.csv', ledger)


def build_source_records(courts, corpus_dir, text_policy, output,
                         batch_size=500, limit_batches=None, jev=None):
    """Inspect every physical row, including zero-citation and missing-text rows."""
    import pyarrow.parquet as pq
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    records = []
    date_asks = []
    for court in courts:
        parquet = pq.ParquetFile(Path(corpus_dir) / (court + '.parquet'))
        offset = 0
        for batch_index, batch in enumerate(parquet.iter_batches(
                batch_size=batch_size, columns=projection(parquet.schema_arrow.names))):
            if limit_batches is not None and batch_index >= limit_batches:
                break
            for i, raw in enumerate(batch.to_pylist(), offset):
                selected = select_record(raw, text_policy)
                record = inspect_source(selected, court, i)
                record.update(model_native_date='', model_date_p='', model_date_status='')
                if jev is not None and jev.enabled('N8_source_date'):
                    _queue_date(jev, record, selected, date_asks)
                records.append(record)
            offset += batch.num_rows
    if date_asks:
        _ask_dates(jev, date_asks, output)
    duplicate_groups = annotate_duplicate_texts(records)
    _write(output / 'source_records.csv', records)
    anomalies = [r for r in records if not r['source_measurable'] or
                 'CONFLICT' in r['date_conflict_status'] or
                 r['native_date_status'] in {'AMBIGUOUS_NATIVE_DATES', 'INVALID_NATIVE_DATE',
                                            'OUT_OF_RANGE_NATIVE_DATE', 'UNRESOLVED_NATIVE_YEAR_CONFLICT'} or
                 r['own_citation_status'] in {'MISMATCH', 'AMBIGUOUS_NATIVE_CITATION',
                                             'MALFORMED_NATIVE_CITATION'} or
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
        if r.get('model_date_status'):
            count['model_date_' + r['model_date_status']] += 1
    summary = {'schema_version': VERSION, 'courts': list(courts),
               'policy_sha256': hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest(),
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
    with open_csv(path) as stream:
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
    import jev_client
    jev_client.add_cli(parser)
    args = parser.parse_args(argv)
    jev = jev_client.from_args(args)
    summary = build_source_records(args.courts, args.corpus_dir, args.text_policy,
                                   args.out, args.batch_size, args.limit_batches, jev=jev)
    if jev.mode != 'off':
        jev.close()
        (Path(args.out) / 'jev_summary.json').write_text(
            json.dumps(jev.summary(), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
