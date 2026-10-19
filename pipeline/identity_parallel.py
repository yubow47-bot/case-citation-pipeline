"""Guarded co-printed identity unions, separate from name/year heuristics."""
from collections import defaultdict
from identity_evidence import CourtEvidence, row_year
from identity_constraints import _proposal, _block, document_union_constraint


def merge_parallel_clusters(clusters, parallels, did_idx, start, registry,
                            own_cites, history, stats, trace, min_sources=1):
    if not parallels:
        return clusters
    if min_sources < 1 or trace is None:
        raise ValueError('Co-printed evidence requires a positive threshold and trace')
    parallels.verify()
    from identity_solve import (decisions_of, history_conflict_instances,
        history_instance_binding, pair_separation_conflicts, pair_separation_detail,
        SAME_KEY_HELD_REASONS)
    courts = CourtEvidence()
    aliases = getattr(own_cites, 'aliases', {})
    parent = list(range(len(clusters)))
    components = {i:list(c[0]) for i,c in enumerate(clusters)}
    reasons = {i:set(filter(None,c[1].split(';'))) for i,c in enumerate(clusters)}
    by_key = defaultdict(set)
    for i,c in enumerate(clusters):
        for m in c[0]: by_key[m['merge_key']].add(i)
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]; i=parent[i]
        return i
    history = history or {}
    history_by_key = defaultdict(set)
    for iid,record in history.items():
        for key in record['before']|record['after']: history_by_key[key].add(iid)
    proposals = defaultdict(list)
    for iid,record in parallels.items():
        proposals[tuple(record['keys'])].append(iid)
    order = sorted(proposals,key=lambda ks:(-len({parallels[i]['source'] for i in proposals[ks]}),ks))
    for keys in order:
        iids = sorted(proposals[keys])
        sources = sorted({parallels[i]['source'] for i in iids})
        if len(sources)<min_sources:
            stats['parallel_below_support_threshold'] += 1
            continue
        if any(k not in by_key for k in keys):
            stats['parallel_missing_member_key'] += 1
            continue
        indices = sorted({find(i) for k in keys for i in by_key[k]})
        combined = [m for i in indices for m in components[i]]
        left = components[indices[0]]
        right = [m for i in indices[1:] for m in components[i]]
        # A within-component proof can upgrade only its actual participating keys.
        if not right:
            left = [m for m in combined if m['merge_key']==keys[0]]
            right = [m for m in combined if m['merge_key']!=keys[0]]
        if not left or not right:
            continue
        refs = sorted({e for iid in iids for e in trace.snapshot.parallel_facts_by_instance[iid]})
        detail = {'instances':iids,'member_keys':list(keys),'distinct_sources':sources,
                  'support':len(sources),'min_sources':min_sources}
        proposal = _proposal(trace,'co_printed_run',left,right,'co_printed_run',
                             'explicit',detail,refs)
        blocker = None
        if any(any(held in reason for held in SAME_KEY_HELD_REASONS)
               for i in indices for reason in reasons[i]):
            blocker = _block(trace,'co_printed_run',left,right,proposal,'persistent_identity_holdout')
        if blocker is None:
            if any(m.get('court_designation_conflict') == 'true' for m in combined):
                blocker = _block(trace,'co_printed_run',left,right,proposal,'printed_court_conflict')
        if blocker is None:
            blocker = document_union_constraint(combined,aliases,registry,courts,
                {'trace':trace,'phase':'co_printed_run','left':left,'right':right,'proposal':proposal})
        years = {row_year(m) for m in combined if row_year(m) is not None}
        if blocker is None and years and max(years)-min(years)>1:
            blocker = _block(trace,'co_printed_run',left,right,proposal,'printed_year_span',
                             {'years':sorted(years)})
        if blocker is None:
            roots = decisions_of(combined,did_idx,start,registry)[0]
            if len(set(roots.values()))>1:
                blocker = _block(trace,'co_printed_run',left,right,proposal,'distinct_decision_roots')
        all_keys = {m['merge_key'] for m in combined}
        if blocker is None:
            conflicts = pair_separation_conflicts(all_keys,trace.snapshot.pair_cannot_links)
            if conflicts:
                item=conflicts[0]
                blocker = _block(trace,'co_printed_run',left,right,proposal,
                    'verified_pair_separation',pair_separation_detail(item),
                    additional_evidence_ids=[item['evidence_id']])
        if blocker is None:
            conflicts = history_conflict_instances(combined,history_by_key,history)
            if conflicts:
                bindings = [history_instance_binding(i,history[i],trace,
                    {m['merge_key'] for m in left},{m['merge_key'] for m in right}) for i in conflicts]
                blocker = _block(trace,'co_printed_run',left,right,proposal,
                    'appeal_history_connector',{'history_instances':bindings},
                    additional_evidence_ids=sorted({e for b in bindings for e in b['evidence_ids']}))
        if blocker:
            stats['parallel_blocked_'+blocker.rule] += 1
            trace.event('co_printed_run',combined,'rejected',blocker.rule,
                        [proposal.constraint_id,blocker.constraint_id])
            continue
        for m in combined:
            if m['merge_key'] in keys:
                existing=set(filter(None,m.get('co_printed_run_ids','').split(';')))
                m['co_printed_run_ids']=';'.join(sorted(existing|set(iids)))
        trace.event('co_printed_run',combined,'accepted','co_printed_run',
                    [proposal.constraint_id])
        stats['parallel_accepted_evidence_sets'] += 1
        if len(sources)==1:stats['parallel_single_source_evidence_sets'] += 1
        if len(indices)>1:
            stats['parallel_cluster_unions'] += len(indices)-1
            if len(sources)==1:stats['parallel_single_source_cluster_unions'] += len(indices)-1
            target=indices[0]
            for i in indices[1:]:
                parent[i]=target; reasons[target].update(reasons.pop(i)); del components[i]
            components[target]=combined
    return [(components[i],';'.join(sorted(reasons[i])),'') for i in sorted(components)]
