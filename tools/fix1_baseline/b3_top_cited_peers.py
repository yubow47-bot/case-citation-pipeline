# Locally adapted from the existing engineering-fix baseline; G source remains unchanged.
"""B3. Candidate split groups among the most-cited cases.

For the top-N groups by distinct citing judgments (all eligible sources), list other
groups with the same normalized case name and the same earliest printed year.
Generic names (fewer than three tokens, or starting 'R v') are skipped. A peer is a
candidate split only: same name and year can be a genuinely different decision
(e.g. a chambers ruling and a trial ruling in one year).

Run B baseline (2026-10-19): 120 of the top-200 non-generic groups had peers; e.g.
Baker v. Canada 1999 split 3,592 / 386; Dunsmuir 9,665 plus 480 across 13 groups.
"""
import re
import pandas as pd
from common import args, load_members, dump


def norm(s):
    s = s.lower(); s = re.sub(r'\(re\)|\bre\b', '', s); s = re.sub(r'[^a-z0-9 ]', ' ', s)
    s = re.sub(r'\b(v|vs|c)\b', ' v ', s); return re.sub(r'\s+', ' ', s).strip()


def main():
    a = args([('--top', dict(type=int, default=200))])
    e = pd.read_csv(a.norm_dir + '/05_edges.csv.gz', usecols=['source_decision', 'resolved_cited_case', 'eligible_source'], low_memory=False)
    cit = e[e.eligible_source == True].groupby('resolved_cited_case').source_decision.nunique()
    mem = load_members(a.norm_dir)
    first = mem.dropna(subset=['case_name_modal']).drop_duplicates('merged_group_id').set_index('merged_group_id')
    G = pd.DataFrame({'name': first.case_name_modal, 'year': mem.groupby('merged_group_id').year_printed.min()}).dropna()
    G['cit'] = cit.reindex(G.index).fillna(0).astype(int)
    G['nn'] = G.name.map(norm)
    G = G[(G.nn.str.split().str.len() >= 3) & ~G.nn.str.startswith('r v ')]
    G['key'] = G.nn + '|' + G.year.astype(int).astype(str)
    top = G.sort_values('cit', ascending=False).head(a.top)
    by = G.groupby('key')
    rows = []
    for gid, r in top.iterrows():
        peers = by.get_group(r.key); peers = peers[peers.index != gid]
        for pid, p in peers.iterrows():
            rows.append({'top_group': gid, 'name': r['name'], 'year': int(r.year), 'top_citing': int(r.cit), 'peer_group': pid, 'peer_name': p['name'], 'peer_citing': int(p.cit)})
    df = pd.DataFrame(rows)
    df.to_csv(a.out + '/b3_top_cited_peer_candidates.csv', index=False, encoding='utf-8-sig')
    dump(a.out, 'b3_top_cited_peers.json', {'top_n': a.top, 'top_groups_with_peers': int(df.top_group.nunique()) if len(df) else 0,
                                            'peer_rows': int(len(df)), 'top_citing_total': int(top.cit.sum()),
                                            'peer_citing_total_with_double_counting': int(df.drop_duplicates('peer_group').peer_citing.sum()) if len(df) else 0})


if __name__ == '__main__':
    main()
