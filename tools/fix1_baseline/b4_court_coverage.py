# Locally adapted from the existing engineering-fix baseline; G source remains unchanged.
"""B4. Court assignment coverage for Canadian-origin links.

Population view: share of eligible common-calendar links with foreign_status
DOMESTIC_CA whose edge court token is non-empty, by source court.
Sample view (validation v0.3, 720 random links): coverage and assigned agreement
against the v0.3 resolved court labels, mapping each sampled span to its edge in the
measured run. Run B values: weighted coverage 75.42%, assigned agreement 97.82%
(from analysis/validation_v1); 173 of 194 unassigned Canadian case links had a
reader-determinable court: 40 unrecognized designations, 29 ambiguous designations,
14 designations printed but not captured, the rest without a printed designation.
"""
import json, os
import pandas as pd
from common import args, common_sources, counted_mentions, key_to_group, load_members, dump, ROOT


def main():
    a = args()
    e = common_sources(a.norm_dir)
    ec = pd.read_csv(a.courts_dir + '/11_edge_courts.csv.gz', usecols=['source_id', 'final_group_id', 'court_token', 'court_status'], low_memory=False)
    ca = e[e.foreign_status == 'DOMESTIC_CA'].merge(ec, left_on=['source_decision', 'resolved_cited_case'], right_on=['source_id', 'final_group_id'], how='left')
    ca['assigned'] = ca.court_token.fillna('') != ''
    pop = {c: float(g.assigned.mean()) for c, g in ca.groupby('source_court')}
    pop['ALL_unweighted'] = float(ca.assigned.mean())
    # sample view
    V = os.path.join(a.reference_root, 'analysis', 'validation_v1')
    current_sigs = pd.read_csv(a.norm_dir + '/group_signatures.csv').set_index('group_id').stable_signature.to_dict()
    old_sigs = pd.read_csv(a.baseline_signatures).set_index('group_id').stable_signature.to_dict() if a.baseline_signatures else {}
    man = {json.loads(l)['unit_id']: json.loads(l) for l in open(V + '/samples/B_manifest.jsonl', encoding='utf-8')}
    lab = {json.loads(l)['unit_id']: json.loads(l) for l in open(V + '/cross_family_v0_3/B_random_resolved_labels_v0_3.jsonl', encoding='utf-8')}
    members = load_members(a.norm_dir)
    ecm = {(r.source_id, r.final_group_id): r.court_token for r in ec.itertuples() if isinstance(r.court_token, str)}
    cross = pd.read_csv(a.courts_dir + '/court_crosswalk.csv', encoding='utf-8-sig')
    tok = {r['court_token']: r['source_court_code'] for _, r in cross.iterrows() if isinstance(r.get('source_court_code'), str)}
    res = []
    by_court = {}
    for u, m in man.items():
        if u not in lab: continue
        by_court.setdefault(m['court'], []).append(u)
    for court, units in by_court.items():
        cm = counted_mentions(a.run_dir, court, cols=('corpus_row_index', 'source_decision_citation', 'match_start_offset', 'match_end_offset', 'merge_key'))
        idx = {(int(r.corpus_row_index), int(r.match_start_offset), int(r.match_end_offset)): r for r in cm.itertuples()}
        grp = key_to_group(a.run_dir, a.norm_dir, court, members)
        for u in units:
            m, g = man[u], lab[u]
            if g.get('is_case') != 'yes' or g.get('country') != 'CA' or g.get('court') in (None, 'uncertain'): continue
            hit = idx.get((int(m['corpus_row_index']), int(m['span_start']), int(m['span_end'])))
            if hit is None:
                res.append({'unit_id': u, 'mapped': False}); continue
            gid = grp(hit.merge_key, m['source_id']); t = ecm.get((m['source_id'], gid), '')
            code = tok.get(t, 'OTHER_CA' if t else '')
            res.append({'unit_id': u, 'mapped': True, 'group_changed': (current_sigs.get(gid) != old_sigs[m['final_group_id']]) if m['final_group_id'] in old_sigs else None, 'assigned': bool(t), 'agree': (code == g['court']) if t else None})
    df = pd.DataFrame(res, columns=['unit_id','mapped','group_changed','assigned','agree'])
    mapped = df[df.mapped]
    dump(a.out, 'b4_court_coverage.json', {
        'population_coverage_by_source_court': pop,
        'sample_units_with_reader_court': int(len(df)), 'sample_unmapped_spans': int((~df.mapped).sum()),
        'sample_groups_changed_vs_runB': int(mapped.group_changed.sum()) if old_sigs else None,
        'group_change_basis': 'stable_member_and_source_signature' if old_sigs else 'UNAVAILABLE_BASELINE_SIGNATURES_NOT_SUPPLIED',
        'sample_coverage_unweighted': float(mapped.assigned.mean()),
        'sample_assigned_agreement_unweighted': float(mapped[mapped.assigned].agree.mean()),
    })
    df.to_csv(a.out + '/b4_sample_units.csv', index=False, encoding='utf-8-sig')


if __name__ == '__main__':
    main()
