"""Apply user-authorized 6.1 evidence metadata and verify operational invariants.

No confidence, jurisdiction, range, identity, corpus or old-run changes.
Run --apply once; subsequent invocations verify/report without mutation.
"""
from __future__ import annotations

import argparse
import collections
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TABLE = ROOT / 'decisions' / 'reporter_jurisdiction.csv'
META = {'verification_level', 'source', 'source_locator', 'notes'}


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def dump(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load():
    review = json.loads((HERE / 'final_review.json').read_text(encoding='utf-8'))
    _, targets = read_csv(HERE / 'no_evidence_targets.csv')
    decisions = review['abbreviation_decisions']
    assert review['reviewer_model'] == 'gpt-6.1-sol'
    assert review['reasoning_effort'] == 'medium'
    assert len(decisions) == len(targets) == 50
    assert len({d['normalized_key'] for d in decisions}) == 50
    assert {d['normalized_key'] for d in decisions} == {t['normalized_key'] for t in targets}
    assert {int(d['direction']) for d in review['direction_decisions']} == {1, 2, 3, 4}
    for name in ('collection_head.json', 'collection_tail.json'):
        col = json.loads((HERE / name).read_text(encoding='utf-8'))
        assert col['collector_model'] == 'gpt-6-luna' and col['reasoning_effort'] == 'medium'
        assert len(col['rows']) == 25
    updates = []
    for d in decisions:
        assert d['status'] in {'approved', 'partial', 'withheld'}
        if d['status'] == 'withheld':
            assert not d['eligible_table_updates']
        for u in d['eligible_table_updates']:
            updates.append(dict(u, normalized_key=d['normalized_key'], abbreviation=d['abbreviation']))
    updates.extend(review['special_table_updates'])
    return review, targets, decisions, updates


def apply(updates):
    baseline = (HERE / 'reporter_jurisdiction_before.csv').read_bytes()
    original = TABLE.read_bytes()
    assert original == baseline, 'Table changed since snapshot; inspect concurrent edits before applying.'
    raw = original.decode('utf-8-sig')
    bom = '\ufeff' if original.startswith(b'\xef\xbb\xbf') else ''
    physical = raw.splitlines(keepends=True)
    stream = io.StringIO(raw, newline='')
    reader = csv.DictReader(stream)
    fields = list(reader.fieldnames or [])
    start = reader.line_num
    records = []
    for row in reader:
        end = reader.line_num
        records.append((start, end, row))
        start = end
    replacements = {}
    receipts = []
    for u in updates:
        matches = []
        for i, (_, _, row) in enumerate(records):
            if row['normalized_key'] != u['normalized_key'] or row['jurisdiction'] != u['jurisdiction']:
                continue
            if u.get('abbreviation') and row['abbreviation'] != u['abbreviation']:
                continue
            selectors = ('vol_range_start', 'vol_range_end', 'year_range_start', 'year_range_end')
            if any(k in u and row[k] != str(u[k]) for k in selectors):
                continue
            matches.append(i)
        assert matches, f'No exact table row for {u}'
        for i in matches:
            assert i not in replacements, f'Duplicate update for table row {i}'
            lo, hi, old = records[i]
            new = old.copy()
            for k in ('verification_level', 'source'):
                if k in u:
                    new[k] = u[k]
            # Retain corpus-count provenance used by the original summary script.
            loc = u.get('source_locator', '')
            if loc and loc not in old['source_locator']:
                new['source_locator'] = old['source_locator'] + '；2026-10-02 代理审批依据：' + loc
            note = u.get('notes_append', '')
            if note and note not in old['notes']:
                new['notes'] = old['notes'] + '；' + note
            assert all(new[k] == old[k] for k in fields if k not in META)
            newline = '\r\n' if physical[hi - 1].endswith('\r\n') else '\n'
            output = io.StringIO(newline='')
            writer = csv.DictWriter(output, fieldnames=fields, lineterminator=newline)
            writer.writerow(new)
            replacements[i] = output.getvalue()
            receipts.append({'row_number': i + 2, 'normalized_key': old['normalized_key'],
                             'abbreviation': old['abbreviation'], 'jurisdiction': old['jurisdiction'],
                             'changes': {k: {'before': old[k], 'after': new[k]} for k in META if old[k] != new[k]}})
    result = ''.join(physical[:records[0][0]])
    for i, (lo, hi, _) in enumerate(records):
        result += replacements.get(i, ''.join(physical[lo:hi]))
    result += ''.join(physical[records[-1][1]:])
    candidate = HERE / 'reporter_jurisdiction_after.csv'
    candidate.write_bytes((bom + result).encode('utf-8'))
    _, proposed = read_csv(candidate)
    assert len(proposed) == len(records)
    assert all(all(a[k] == b[k] for k in fields if k not in META)
               for (_, _, a), b in zip(records, proposed))
    TABLE.write_bytes(candidate.read_bytes())
    dump('applied_changes.json', {'metadata_only': True, 'changed_rows': len(receipts),
                                 'changed_fields': sorted(META), 'rows': receipts})


def verify(review, targets, decisions):
    fields, before = read_csv(HERE / 'reporter_jurisdiction_before.csv')
    actual_fields, after = read_csv(TABLE)
    assert fields == actual_fields and len(before) == len(after)
    semantic = [k for k in fields if k not in META]
    before_values = [[r[k] for k in semantic] for r in before]
    after_values = [[r[k] for k in semantic] for r in after]
    assert before_values == after_values
    changed = [i + 2 for i, (a, b) in enumerate(zip(before, after)) if a != b]
    sys.path.insert(0, str(ROOT / 'pipeline'))
    import classify
    tables = {k: classify.load_table(k + '.csv') for k in
              ('neutral_court_codes', 'reporter_jurisdiction', 'series_prefix')}
    old_tables = dict(tables, reporter_jurisdiction=before)
    new_tables = dict(tables, reporter_jurisdiction=after)
    old_c = classify.Classifier(old_tables, collections.Counter())
    new_c = classify.Classifier(new_tables, collections.Counter())
    probes = 0
    for ab in dict.fromkeys(r['abbreviation'] for r in before):
        for year in ('1890', '1950', '2006', '2025'):
            for vol in ('', '1', '38', '999', '1000', '2006'):
                row = {'shape_name': 'shape_bracket', 'raw_string': f'[{year}] {vol} {ab} 82',
                       'token': ab, 'abbr': '', 'leading_abbr': '', 'vol': vol,
                       'year_start': year, 'series': '', 'page': '82', 'preceding_text': ''}
                assert old_c.run_row(copy.deepcopy(row)) == new_c.run_row(copy.deepcopy(row)), row
                probes += 1
    sj = []
    for raw, vol, year, want in (
        ('[2006] S.J. No. 802', '', '2006', 'SK'),
        ('(1894) 38 S.J. 234', '38', '1894', 'GB'),
        ('2006 S.J. No. 456 (year misparsed as volume)', '2006', '', 'UNSUPPORTED'),
    ):
        row = {'abbreviation': 'S.J.', 'vol': vol, 'year_start': year}
        new_c.step3(row)
        assert row['jurisdiction'] == want, row
        sj.append({'input': raw, 'expected': want, 'actual': row['jurisdiction'],
                   'confidence': row['jurisdiction_confidence']})
    sys.path.insert(0, str(ROOT / 'pipeline' / 'tests'))
    import test_layers
    for name in ('test_admit_candidate', 'test_classifier', 'test_disambiguation',
                 'test_case_name_markers', 'test_decide_units', 'test_registry_gate', 'test_registry_audit'):
        getattr(test_layers, name)()
    weights = {r['normalized_key']: int(r['corpus_rows']) for r in targets}
    by_status = collections.Counter(d['status'] for d in decisions)
    weighted = collections.Counter()
    for d in decisions:
        weighted[d['status']] += weights[d['normalized_key']]
    semantic_hash = hashlib.sha256(json.dumps(before_values, ensure_ascii=False).encode('utf-8')).hexdigest()
    checks = {'status': 'passed', 'table_rows': len(after), 'changed_metadata_rows': len(changed),
              'changed_row_numbers': changed, 'semantic_fields_unchanged': semantic,
              'semantic_sha256_before': semantic_hash, 'semantic_sha256_after': semantic_hash,
              'classifier_probes_identical': probes, 'sj_existing_split_checks': sj,
              'unit_assertions_passed': len(test_layers.PASSED),
              'full_mini_chain': 'not verified: baseline select.py lacks PyYAML; see environment_check.json',
              'no_full_production_run_performed': True,
              'approval_counts': dict(by_status), 'original_registered_weight_by_status': dict(weighted),
              'original_no_evidence_weight_total': sum(weights.values()),
              'table_sha256_before': hashlib.sha256((HERE / 'reporter_jurisdiction_before.csv').read_bytes()).hexdigest(),
              'table_sha256_after': hashlib.sha256(TABLE.read_bytes()).hexdigest()}
    dump('verification.json', checks)
    print(json.dumps({k: checks[k] for k in ('status', 'table_rows', 'changed_metadata_rows',
                                          'classifier_probes_identical', 'unit_assertions_passed',
                                          'approval_counts', 'original_registered_weight_by_status')}, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    review, targets, decisions, updates = load()
    if args.apply:
        apply(updates)
    verify(review, targets, decisions)


if __name__ == '__main__':
    main()
