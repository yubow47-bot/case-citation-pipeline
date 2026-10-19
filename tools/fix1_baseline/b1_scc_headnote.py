# Locally adapted from the existing engineering-fix baseline; G source remains unchanged.
"""B1. SCC editorial headnote and APPEAL-from block.

Heuristic zone boundary (measurement only, not a pipeline rule): the reasons start at
the first 'delivered by' after the first appeal header (APPEAL from / REFERENCE /
MOTION / APPLICATION for / APPEAL by); fallback is the first line starting '[1]'.
Mentions before that boundary are 'headnote'; mentions between the appeal header and
the boundary are in the 'appeal block'.

Run B baseline (2026-10-19, SCC 2001-2025 excl. 2011): 53.1% of counted mentions in
the headnote; 8,710 appeal-block-only links (5.92 per judgment), 99.5% singleton
groups, 92.3% unnamed.
"""
import re
import numpy as np
from common import args, common_sources, counted_mentions, key_to_group, load_members, texts, dump

HEADERS = ['APPEAL from', 'APPEALS from', 'APPEAL and CROSS-APPEAL from', 'REFERENCE', 'MOTION', 'APPLICATION for', 'APPEAL by']


def zones(txt):
    a = -1
    for pat in HEADERS:
        j = txt.find(pat)
        if j >= 0 and (a < 0 or j < a):
            a = j
    d = txt.find('delivered by', max(a, 0))
    if d < 0:
        m = re.search(r'\n\s*\[1\]\s', txt[max(a, 0):])
        d = max(a, 0) + m.start() if m else -1
    return a, d


def main():
    a = args()
    e = common_sources(a.norm_dir, 'SCC')
    m = counted_mentions(a.run_dir, 'SCC')
    m = m[m.source_decision_citation.isin(set(e.source_decision))].copy()
    members = load_members(a.norm_dir)
    grp = key_to_group(a.run_dir, a.norm_dir, 'SCC', members)
    m['grp'] = [grp(r.merge_key, r.source_decision_citation) for r in m.itertuples()]
    size = members.groupby('merged_group_id').merge_key.nunique()
    named = set(members.dropna(subset=['case_name_modal']).merged_group_id)
    t = texts(a.corpus_dir, 'SCC')
    zz = {i: zones(t[int(i)]) for i in m.corpus_row_index.unique()}
    m['ap'] = m.corpus_row_index.map(lambda i: zz[i][0]); m['rs'] = m.corpus_row_index.map(lambda i: zz[i][1])
    k = m[m.rs > 0].copy()
    k['headnote'] = k.match_start_offset < k.rs
    k['block'] = (k.ap >= 0) & (k.match_start_offset >= k.ap) & k.headnote
    L = k.dropna(subset=['grp']).groupby(['source_decision_citation', 'grp']).agg(all_head=('headnote', 'all'), block=('block', 'any')).reset_index()
    A = L[L.all_head & L.block]
    n_j = L.source_decision_citation.nunique()
    dump(a.out, 'b1_scc_headnote.json', {
        'scc_judgments': int(n_j), 'reasons_boundary_found_share': float(np.mean([v[1] > 0 for v in zz.values()])),
        'counted_mentions': int(len(k)), 'headnote_mention_share': float(k.headnote.mean()),
        'links': int(len(L)), 'links_per_judgment': len(L) / n_j if n_j else None,
        'headnote_only_links': int(L.all_head.sum()), 'headnote_only_link_share': float(L.all_head.mean()),
        'appeal_block_only_links': int(len(A)), 'appeal_block_only_per_judgment': len(A) / n_j if n_j else None,
        'appeal_block_only_singleton_share': float((A.grp.map(size) == 1).mean()),
        'appeal_block_only_unnamed_share': float((~A.grp.isin(named)).mean()),
    })


if __name__ == '__main__':
    main()
