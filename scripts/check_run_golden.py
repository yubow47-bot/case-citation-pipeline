"""Compare an explicit run with a separately frozen regression expectation.

No baseline-writing mode: changes to the expected JSON require review.
This characterizes output counts and selected identities, not semantic accuracy.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path

csv.field_size_limit(10**9)


def records(path, fields=None):
    path = Path(path)
    if not path.is_file():
        path = Path(str(path) + '.gz')
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream):
            yield {k: row[k] for k in fields} if fields else row


def snapshot(run, probe_keys):
    run = Path(run)
    manifest = json.loads((run/'run_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('status') != 'complete' or manifest.get('input_identity_verified_unchanged') is not True:
        raise ValueError('Golden comparison requires a complete, input-verified run')
    courts = sorted(manifest['params']['courts'])
    out = {'courts': courts, 'by_court': {}}
    for court in courts:
        rows = groups = 0
        for record in records(run/f'decide_out/{court}/decided.csv', ['is_primary']):
            rows += 1
            groups += record['is_primary'] == 'true'
        out['by_court'][court] = {'rows': rows, 'groups': groups}
    rows = list(records(run/'decide_out/cross_court/decided.csv',
                ['merged_group_id', 'is_primary', 'distinct_decisions_count', 'merge_key', 'case_name_modal']))
    primary = {r['merged_group_id']: r for r in rows if r['is_primary'] == 'true'}
    out['cross_court'] = {'rows': len(rows), 'groups': len(primary),
        'groups_dd_positive': sum(int(r['distinct_decisions_count']) > 0 for r in primary.values()),
        'groups_dd_ge5': sum(int(r['distinct_decisions_count']) >= 5 for r in primary.values()),
        'edges': sum(1 for _ in records(run/'edges/citation_edges.csv'))}
    out['probes'] = {}
    for key in probe_keys:
        groups = {r['merged_group_id'] for r in rows if r['merge_key'] == key}
        out['probes'][key] = sorted([[primary[g]['case_name_modal'], int(primary[g]['distinct_decisions_count'])]
                                    for g in groups])
    return out


def compare(run, expected_file):
    expected = json.loads(Path(expected_file).read_text(encoding='utf-8'))
    if expected.get('schema') != 'run-golden-v1' or not expected.get('snapshot', {}).get('probes'):
        raise ValueError('Expected a frozen run-golden-v1 snapshot with identity probes')
    actual = snapshot(run, expected['snapshot']['probes'])
    return {'status': 'passed' if actual == expected['snapshot'] else 'failed',
            'scope': 'characterization_regression_not_semantic_accuracy',
            'run': str(Path(run).resolve()), 'expected_file': str(Path(expected_file).resolve()),
            'expected': expected['snapshot'], 'actual': actual}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--run', required=True)
    parser.add_argument('--expect', required=True)
    parser.add_argument('--output')
    args = parser.parse_args(argv)
    report = compare(args.run, args.expect)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
