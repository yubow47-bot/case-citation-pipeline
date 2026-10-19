# Locally adapted from the existing engineering-fix baseline; G source remains unchanged.
"""B2. Parallel citations printed in one run but resolved to different groups.

A 'run pair' is two consecutive counted mentions in one judgment whose gap text is
only a separator: optional short parenthetical tag such as (QL), (CanLII), (WL Can.),
(Lexis), then a comma. Measurement only: this is not the pipeline's run definition.
For each pair we test whether both keys landed in the same final group.

Pair types: neutral_other (one neutral, one reporter/database/identifier),
neutral_neutral (can be a bilingual pair or a list of different decisions; reported
but not used for the duplicate estimate), other_other.

Duplicate-link estimate: a link (source judgment, group g) is 'split-only' when every
counted mention of g in that judgment is the secondary side of a split pair (the
non-neutral side of a neutral_other pair, or the right side of an other_other pair).
Such links would disappear if the run were joined. This is an estimate: a comma run
can occasionally join two different decisions.

Run B (2026-10-19), common calendar: see outputs/<run>/b2_parallel_run_splits.json.
"""
import re
from collections import defaultdict
import pandas as pd
from common import args, common_sources, counted_mentions, key_to_group, load_members, texts, dump

SEP = re.compile(r'^\s*(\([A-Za-z.\s]{1,15}\)\s*)?,\s*$')
TYPES = ['neutral_other', 'neutral_neutral', 'other_other']


def main():
    a = args()
    members = load_members(a.norm_dir)
    rows, out = [], {}
    for court in a.courts:
        e = common_sources(a.norm_dir, court)
        n_links = int(len(e))
        m = counted_mentions(a.run_dir, court)
        m = m[m.source_decision_citation.isin(set(e.source_decision))].copy()
        grp = key_to_group(a.run_dir, a.norm_dir, court, members)
        m['grp'] = [grp(r.merge_key, r.source_decision_citation) for r in m.itertuples()]
        t = texts(a.corpus_dir, court)
        m = m.sort_values(['corpus_row_index', 'match_start_offset'])
        stats = {k: [0, 0] for k in TYPES}
        split_only = 0
        kept_examples = 0
        for idx, d in m.groupby('corpus_row_index', sort=False):
            txt = t[int(idx)]
            r = d.to_dict('records')
            secondary = [False] * len(r)
            for i, (x, y) in enumerate(zip(r, r[1:])):
                gap = txt[int(x['match_end_offset']):int(y['match_start_offset'])]
                if not SEP.match(gap) or x['merge_key'] == y['merge_key']:
                    continue
                kinds = (x['citation_kind'], y['citation_kind'])
                typ = 'neutral_neutral' if kinds == ('neutral', 'neutral') else 'neutral_other' if 'neutral' in kinds else 'other_other'
                same = x['grp'] == y['grp'] and isinstance(x['grp'], str)
                stats[typ][0] += 1; stats[typ][1] += int(not same)
                if not same and typ != 'neutral_neutral':
                    secondary[i if (typ == 'neutral_other' and y['citation_kind'] == 'neutral') else i + 1] = True
                if not same and kept_examples < 400 and hash((int(idx), i)) % 7 == 0:  # deterministic thinning, up to 400 per court
                    kept_examples += 1
                    rows.append({'court': court, 'source': x['source_decision_citation'], 'left': x['raw_string'], 'right': y['raw_string'],
                                 'left_group': x['grp'], 'right_group': y['grp'], 'type': typ})
            by_g = defaultdict(list)
            for row, sec in zip(r, secondary):
                if isinstance(row['grp'], str):
                    by_g[row['grp']].append(sec)
            split_only += sum(1 for v in by_g.values() if all(v))
        out[court] = {k: {'pairs': v[0], 'split': v[1], 'split_share': (v[1] / v[0] if v[0] else None)} for k, v in stats.items()}
        out[court]['split_only_links_estimate'] = split_only
        out[court]['common_calendar_links'] = n_links
        out[court]['split_only_share_of_links'] = split_only / n_links if n_links else None
    tot = {k: [sum(out[c][k]['pairs'] for c in a.courts), sum(out[c][k]['split'] for c in a.courts)] for k in TYPES}
    out['ALL'] = {k: {'pairs': v[0], 'split': v[1], 'split_share': (v[1] / v[0] if v[0] else None)} for k, v in tot.items()}
    so = sum(out[c]['split_only_links_estimate'] for c in a.courts); nl = sum(out[c]['common_calendar_links'] for c in a.courts)
    out['ALL'].update({'split_only_links_estimate': so, 'common_calendar_links': nl, 'split_only_share_of_links': so / nl if nl else None})
    pd.DataFrame(rows).to_csv(a.out + '/b2_split_pair_examples.csv', index=False, encoding='utf-8-sig')
    dump(a.out, 'b2_parallel_run_splits.json', out)


if __name__ == '__main__':
    main()
