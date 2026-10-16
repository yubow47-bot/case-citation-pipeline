"""Compare country coverage on two runs without changing their artifacts."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import json
from pathlib import Path

csv.field_size_limit(10 ** 9)


def rows(path):
    if not path.exists():
        path = Path(str(path) + '.gz')
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        yield from csv.DictReader(stream)


def summary(run):
    groups, members, bases = {}, {}, Counter()
    unknown_families = defaultdict(set)
    for row in rows(run / 'decide_out/cross_court/decided.csv'):
        gid = row['merged_group_id']
        groups[gid] = (row['group_origin_status'], row['group_origin_country'],
                       int(row['distinct_decisions_count']))
        members[(row['court'], row['merge_key'])] = gid
        bases[row.get('member_origin_basis') or 'unknown'] += 1
        if row['group_origin_status'] != 'DETERMINED':
            unknown_families[row['merge_key'].split('|')[2]].add(gid)
    status, identity = Counter(), Counter()
    pairs, counted, foreign_groups = set(), set(), set()
    mentions = 0
    for row in rows(run / 'edges/citation_edges.csv'):
        gid = row['resolved_cited_case']
        counted.add(gid)
        pairs.add((row['source_decision'], gid))
        status[row['foreign_status']] += 1
        identity[row['edge_support']] += 1
        mentions += int(row['mention_count'])
        if row['foreign_status'] == 'FOREIGN':
            foreign_groups.add(gid)
    known = {g for g in counted if groups[g][0] == 'DETERMINED'}
    unknown = len(counted - known)
    edge_count = sum(status.values())
    edge_unknown = status['UNDETERMINED'] + status['CONFLICT']
    selected = json.loads((run / 'select_out/manifest.json').read_text(encoding='utf-8-sig'))
    result = dict(run=run.name, groups_total=len(groups), counted_groups=len(counted),
                  country_known_groups=len(known), country_unknown_groups=unknown,
                  group_unknown_pct=100 * unknown / len(counted),
                  counted_edges=edge_count, country_unknown_edges=edge_unknown,
                  edge_unknown_pct=100 * edge_unknown / edge_count,
                  foreign_groups=len(foreign_groups), foreign_edges=status['FOREIGN'],
                  mentions=mentions, edge_country_status=dict(status), identity_support=dict(identity),
                  member_country_bases=dict(bases),
                  selection_threshold=selected['threshold_dd'],
                  selected_groups=selected['stats']['groups_kept'],
                  dd_profile=selected['dd_profile'],
                  remaining_unknown_families=[dict(family=k, groups=len(v)) for k, v in
                      sorted(unknown_families.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:30]])
    return result, (groups, members, pairs)


def compare(before, after):
    old, old_data = summary(before)
    new, new_data = summary(after)
    old_groups, old_members, old_pairs = old_data
    new_groups, new_members, new_pairs = new_data
    checks = dict(same_member_assignments=old_members == new_members,
                  same_counted_edge_pairs=old_pairs == new_pairs,
                  same_group_dd={k: v[2] for k, v in old_groups.items()} ==
                                {k: v[2] for k, v in new_groups.items()},
                  same_counted_mentions=old['mentions'] == new['mentions'])
    changes = {}
    for kind in ('groups', 'edges'):
        a, b = old['country_unknown_' + kind], new['country_unknown_' + kind]
        changes[kind] = dict(unknown_before=a, unknown_after=b,
                             unknown_reduced=a-b, relative_reduction_pct=100*(a-b)/a if a else None,
                             percentage_point_reduction=old[kind[:-1] + '_unknown_pct'] -
                                                        new[kind[:-1] + '_unknown_pct'])
    return dict(schema='country-assessment-impact-v1', before=old, after=new,
                conservation_checks=checks, changes=changes,
                interpretation='Country coverage, not accuracy. Inferred country remains marked by classification_jurisdiction or classification_reporter_consensus. Identity confidence is unchanged.',
                decision_review=[
                    dict(layer='extraction', action='retained', reason='Structural candidate matching; no country or DD prerequisite. Missing shapes require separate extraction changes.'),
                    dict(layer='classification', action='retained', reason='Non-case/date/statute exclusions and same-grade conflicting readings prevent double counting; case-name rejection is separate from citation admission.'),
                    dict(layer='member_country', action='changed', reason='Accepted jurisdiction classifications now supply country without a second exclusive-source requirement. Reporter candidates that differ only within one country also determine country. Explicit case/scope conclusions and country conflicts take precedence.'),
                    dict(layer='group_country', action='changed', reason='All member country observations participate; identity basis does not erase country. Different countries remain conflicts.'),
                    dict(layer='edge_country', action='changed', reason='A source citation uses its own member country independently of identity confidence. Group-only propagation still needs an identity-supported path.'),
                    dict(layer='identity', action='retained', reason='Distinct neutral judgments, positive incompatible courts, self-citation exclusion, date windows and exact identity conflicts guard case identity, not country assessment.'),
                    dict(layer='selection', action='changed', reason='Default DD >= 1 retains all counted groups; DD >= 5 is an optional frequent profile, not case validity.'),
                    dict(layer='research', action='changed', reason='Country coverage no longer requires identity-supported edges. Unknown/conflict and identity support have separate denominators.'),
                ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True, type=Path)
    parser.add_argument('--after', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report = compare(args.before, args.after)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(changes=report['changes'], conservation_checks=report['conservation_checks']), indent=2))


if __name__ == '__main__':
    main()
