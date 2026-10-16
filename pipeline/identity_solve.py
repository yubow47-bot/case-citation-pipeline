"""Ordered identity proposals, guards, and partitions (legacy semantics)."""
from collections import Counter, defaultdict

from normalize import nk
from identity_constraints import (
    ConstraintEdge, _legacy_bucket_admission, _one_edit, mixed_identity,
    verified_bilingual_keys, same_decision_kind, same_decision, _identifier_keys,
    _combined_identifier_keys, variant_constraints, identifier_union_constraint,
    document_union_constraint, court_partition_constraints, document_holdout_constraints,
    atomic_link, name_year_link, cocitation_link, document_alias_link,
    anchor_root_link, alias_root_link, jurisdiction_constraint)
import identity_evidence as evidence
from identity_evidence import (row_year, row_key, _neutral_parts, _self_of,
    neutral_start, _before_start, load_bilingual, load_identifier_systems,
    identifier_system_of, parse_name_classes, load_identity_separations)

BAR = 0.8

def windows(items):
    """Partition sorted year/row pairs into windows whose span is at most one year."""
    parts, cur, start = [], [items[0]], items[0][0]
    for it in items[1:]:
        if it[0] - start <= 1:
            cur.append(it)
        else:
            parts.append(cur)
            cur, start = [it], it[0]
    parts.append(cur)
    return parts






def decisions_of(members, did_idx, start=None, registry=None,
                 typo_over=None, gate="literal", holdout=None, trace=None):
    """Resolve roots in descending source-count/key order. Preserve gate priority, mixed-name holdouts, verified bilingual equivalence, rarity checks and qualified document alias annotations. Registry claims do not enter local own/self sets. Optional tracing records local proposals, never global equivalence closure."""
    own, neu = defaultdict(set), defaultdict(bool)
    same_name = defaultdict(bool)      
    classes = defaultdict(dict)        
    kname = defaultdict(str)           
    for m in members:
        k = m["merge_key"]
        own[k] |= _self_of(m)
        neu[k] = neu[k] or m.get("citation_kind") == "neutral"
        sn = nk(m.get("self_case_name") or "")
        same_name[k] = same_name[k] or bool(sn and sn == nk(m.get("case_name_modal") or ""))
        for n_, c_ in parse_name_classes(m.get("name_classes")).items():
            classes[k][n_] = classes[k].get(n_, 0) + c_
        kname[k] = kname[k] or nk(m.get("case_name_modal") or "")
    for k in neu:
        if neu[k] and not own[k] and _before_start(k, start):
            neu[k] = False        
    anc, ajur = defaultdict(set), {}
    for m in members:
        k = m["merge_key"]
        if neu[k] or own[k]:
            anc[k] |= did_idx.get(row_key(m), set())
            ajur[k] = m.get("jurisdiction") or ""
    order = sorted(anc, key=lambda k: (-len(anc[k]), k))
    root, root_kind = {}, {}
    for i, k in enumerate(order):
        root[k] = k
        for big in order[:i]:
            if root[big] != big or not (neu[k] and neu[big]):
                continue          

            relation = variant_constraints(k, big, anc, ajur, own, same_name, classes,
                kname, registry, gate, holdout is not None, members, trace)
            proposal, blocker, kind = relation.proposal, relation.blocker, relation.kind
            registered, in_registry = relation.registered, relation.in_registry
            left_rows = [m for m in members if m['merge_key'] == k]
            right_rows = [m for m in members if m['merge_key'] == big]
            if blocker and blocker.rule == 'registered_identity_guard':
                continue
            if blocker:
                holdout.append((k, big, kname.get(big) or "",
                                "|".join("%s:%d" % kv for kv in
                                         sorted((classes.get(k) or {}).items(),
                                                key=lambda kv: (-kv[1], kv[0]))),
                                sum((classes.get(k) or {}).values()),
                                len(anc[k]), len(anc[big])))
                break
            if proposal:
                if trace:
                    trace.event('variant', left_rows + right_rows, 'accepted', kind,
                                [proposal.constraint_id])
                if registered and not same_name[k]:

                    if typo_over is not None:
                        typo_over.append((k, big, in_registry, kind,
                                          len(anc[k]), len(anc[big])))
                root[k] = big
                root_kind[k] = kind
                break
    # Only annotations made by merge_document_alias_clusters from qualified
    # metadata/header proofs may collapse separate self-citation roots here.
    # Legacy own-citation rows never supply these annotations.
    alias_roots = defaultdict(set)
    alias_witnesses = defaultdict(lambda: defaultdict(list))
    witness_roots = dict(root)
    for m in members:
        if m.get('document_alias_decision_id') and m['merge_key'] in root:
            alias_roots[m['document_alias_decision_id']].add(root[m['merge_key']])
            alias_witnesses[m['document_alias_decision_id']][root[m['merge_key']]].append(m)
    for did, roots in alias_roots.items():
        target = min(roots, key=lambda k: (-len(anc[k]), k))
        for k in root:
            if root[k] in roots and root[k] != target:
                proposal = alias_root_link(
                    [m for m in members if m['merge_key'] == k],
                    [m for m in members if m['merge_key'] == target], did,
                    alias_witnesses[did][root[k]], alias_witnesses[did][target],
                    witness_roots, root[k], target, trace)
                if proposal:
                    root[k], root_kind[k] = target, 'document_alias'
    return root, anc, ajur, own, root_kind

def _unknown(j):
    return j in ("", "UNSUPPORTED")

def _compatible(a, b):
    """Reject only two positive incompatible jurisdiction values; missing values remain unasserted."""
    if a is None or b is None:
        return False
    return not a or not b or a == b

def _with_held(parts, held):
    """Retain mixed-title keys as separate exact-key groups instead of silently dropping rows."""
    if not held:
        return parts
    bykey = defaultdict(list)
    for m in held:
        bykey[m["merge_key"]].append(m)
    return list(parts) + [(bykey[k], "mixed_identity") for k in sorted(bykey)]



def split_by_decision(members, did_idx, stats, start=None, registry=None,
                      typo_over=None, gate="literal", holdout=None, trace=None,
                      bucket_admission=None):
    root, anc, ajur, own, root_kind = decisions_of(members, did_idx, start,
                                                   registry, typo_over, gate,
                                                   holdout, trace)

    held = []
    if holdout:
        mixed_here = {h[0] for h in holdout}
        if mixed_here and any(m["merge_key"] in mixed_here for m in members):
            keep = []
            for m in members:
                (held if m["merge_key"] in mixed_here else keep).append(m)
            if keep:

                members = keep
                if trace:
                    trace.event('root_recompute_after_holdout', keep, 'reset',
                                'mixed_identity_holdout')
                root, anc, ajur, own, root_kind = decisions_of(
                    members, did_idx, start, registry, None, gate, None, trace)
            else:
                held = []
    stats["anchors_collapsed_as_variant"] += sum(1 for k, r in root.items() if k != r)
    decisions = sorted({root[k] for k in root}, key=lambda k: (-len(anc[k]), k))
    if len(decisions) < 2:

        dec0 = decisions[0] if decisions else None
        dec_ids0 = (anc.get(dec0, set()) | own.get(dec0, set())) if dec0 else set()
        ride, pend = [], []
        bucket_keys = set()
        # Exact identifiers from different courts move as one unit. Comparing
        # court rows separately would either split the same ID or attach only
        # the first row to the anchor, losing the cross-court source union.
        same_key = defaultdict(list)
        for m in members:
            same_key[m["merge_key"]].append(m)
        for us in sorted(same_key.values(), key=lambda rs: min(map(row_key, rs))):
            mk = us[0]["merge_key"]
            system = identifier_system_of(mk)
            # A single anchor is not evidence that every same-name reporter is
            # that judgment. It must have the same co-citation support required
            # by the multiple-anchor route, unless it is an explicit anchor alias.
            needs_support = bool(system) or (dec0 is not None and root.get(mk) != dec0)
            if needs_support:
                ids_m = set()
                for m in us:
                    ids_m |= did_idx.get(row_key(m), set())
                if not ids_m or not dec_ids0:
                    cov = 0.0
                else:
                    cov = (len(ids_m & dec_ids0) /
                           min(len(ids_m), len(dec_ids0)))
                proposal = cocitation_link(us, [m for m in members if m['merge_key'] == dec0], ids_m, dec_ids0, BAR,
                                            'single_anchor_cocitation', trace, 'single_anchor', 'ratio')
                identifier_blocker = None
                if proposal:
                    _, identifier_blocker = identifier_union_constraint(
                        _identifier_keys(us), {identifier_system_of(k): {k} for k in bucket_keys
                                              if identifier_system_of(k)}, us, ride, proposal,
                        trace, 'single_anchor')
                if proposal and not identifier_blocker:
                    if trace:
                        trace.event('single_anchor', us + ride, 'accepted', 'cocitation_support',
                                    [proposal.constraint_id])
                    ride.extend(us)
                    bucket_keys.add(mk)
                    continue
                if trace and not identifier_blocker:
                    trace.event('single_anchor', us, 'unresolved', 'insufficient_cocitation_support',
                                [proposal.constraint_id] if proposal else [])
                pend.append(us)
                continue
            if dec0 is not None:
                proposal = anchor_root_link(us, [m for m in members if m['merge_key'] == dec0],
                                            dec0, root, root_kind, trace)
            else:
                proposal = bucket_admission
                if proposal is not None and not {row_key(m) for m in members} <= set(proposal.members):
                    raise AssertionError('Bucket admission does not cover current rows')
                if proposal is None and trace is None:
                    proposal = name_year_link(members)
                if proposal is None and trace is None:
                    proposal = _legacy_bucket_admission()
            if proposal is None:
                raise AssertionError('Legacy bucket admission lacks scoped evidence')
            if trace:
                trace.event('anchor_root' if dec0 is not None else 'name_year_window', us,
                            'admitted', constraint_ids=[proposal.constraint_id])
            ride.extend(us)
            bucket_keys.add(mk)
        parts0 = []
        if ride:
            parts0.append((ride, ""))
        for pm in pend:
            reason = "identifier_uncoited" if identifier_system_of(pm[0]["merge_key"]) else "unanchored"
            parts0.append((pm, reason))
            if reason == "unanchored":
                stats["single_anchor_unsupported_reporter_units"] += 1
        if len(parts0) > 1:
            stats["clusters_identifier_split_uncoited"] += 1

            n_p = len(parts0)
            parent = list(range(n_p))
            component_keys = [_identifier_keys(p[0]) for p in parts0]

            def find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            for i in range(n_p):
                for j in range(i + 1, n_p):
                    ids_i = set()
                    for m in parts0[i][0]:
                        ids_i |= did_idx.get(row_key(m), set())
                    ids_j = set()
                    for m in parts0[j][0]:
                        ids_j |= did_idx.get(row_key(m), set())
                    proposal = cocitation_link(parts0[i][0], parts0[j][0], ids_i, ids_j,
                                                BAR, 'cocitation_component', trace,
                                                'single_anchor_components')
                    if proposal is None:
                        continue
                    ri, rj = find(i), find(j)
                    if ri == rj:
                        continue
                    keys, blocker = identifier_union_constraint(
                        component_keys[ri], component_keys[rj],
                        [m for q in range(n_p) if find(q) == ri for m in parts0[q][0]],
                        [m for q in range(n_p) if find(q) == rj for m in parts0[q][0]],
                        proposal, trace, 'single_anchor_components')
                    if blocker:
                        stats["identifier_component_conflicts_blocked"] += 1
                        continue      
                    if proposal:
                        parent[ri] = rj
                        component_keys[rj] = keys
                        if trace:
                            trace.event('single_anchor_components',
                                [m for q in range(n_p) if find(q) == rj for m in parts0[q][0]],
                                'joined', constraint_ids=[proposal.constraint_id])
            comps = defaultdict(list)
            for i in range(n_p):
                comps[find(i)].append(i)
            merged = []
            for comp in sorted(comps.values(),
                               key=lambda c: min(row_key(parts0[i][0][0])
                                                 for i in c)):
                g_rows = [m for i in comp for m in parts0[i][0]]
                reasons = sorted({parts0[i][1] for i in comp if parts0[i][1]})
                merged.append((g_rows, ";".join(reasons)))
            # A single component is a successful co-citation merge too. Return
            # the computed result and retain any mixed-key holdouts in all cases.
            return _with_held(merged, held)
        return _with_held(parts0 if parts0 else [(members, "")], held)
    stats["clusters_split_by_decision"] += 1

    dec_ids = defaultdict(set)
    for k, r in root.items():
        dec_ids[r] |= anc[k]
    for r in decisions:
        dec_ids[r] |= own[r]           
    buckets = {d: [] for d in decisions}
    units = defaultdict(list)          
    for m in members:
        if m["merge_key"] in root:
            buckets[root[m["merge_key"]]].append(m)
        else:
            units[m["merge_key"]].append(m)

    pending = []                       # (rows, ids, jurisdiction)
    for mk in sorted(units):
        us = units[mk]
        ids = set()
        for m in us:
            ids |= did_idx.get(row_key(m), set())
        known = {m.get("jurisdiction") for m in us if not _unknown(m.get("jurisdiction") or "")}
        if len(known) > 1:
            if trace:
                trace.event('multi_anchor', us, 'unresolved', 'member_jurisdiction_disagreement')
            stats["units_unanchored_jurisdiction_disagree"] += 1
            pending.append((us, ids, None))
            continue
        uj = next(iter(known)) if known else ""
        ov = {d: len(ids & dec_ids[d]) for d in decisions}
        cov = {d: (ov[d] / min(len(ids), len(dec_ids[d]))
                   if ids and dec_ids[d] else 0.0) for d in decisions}
        compatible = [d for d in decisions if jurisdiction_constraint(
            uj, ajur[d], us, buckets[d], trace, 'multi_anchor_jurisdiction') is None]
        good = sorted((d for d in compatible if cov[d] >= BAR),
                      key=lambda d: (-ov[d], d))
        target = None
        if len(good) == 1 or (len(good) > 1 and ov[good[0]] > ov[good[1]]):
            target = good[0]
        elif len(good) > 1:
            top = [d for d in good if ov[d] == ov[good[0]]]

            uy = row_year(us[0])
            same_year = [d for d in top
                         if uy is not None and d.split("|", 1)[0] == str(uy)]
            if len(same_year) == 1:
                target = same_year[0]
                stats["units_tie_broken_by_year"] += 1
        if target is not None:
            proposal = cocitation_link(us, buckets[target], ids, dec_ids[target], BAR,
                                        'cocitation_assignment', trace, 'multi_anchor', 'ratio')
            usys = identifier_system_of(mk)
            _, blocker = identifier_union_constraint(_identifier_keys(us),
                _identifier_keys(buckets[target]), us, buckets[target], proposal,
                trace, 'multi_anchor')
            if blocker:
                pending.append((us, ids, uj))
                stats["units_identifier_same_system_blocked"] += 1
            elif proposal:
                if trace:
                    trace.event('multi_anchor', us + buckets[target], 'accepted',
                                'cocitation_assignment', [proposal.constraint_id])
                buckets[target].extend(us)
                stats["units_assigned_by_cocitation"] += 1
            stats["dd_added_by_assignment"] += len(ids - dec_ids[target])
            if len(ids) > len(dec_ids[target]):
                stats["units_assigned_larger_than_target"] += 1
                if not uj:
                    stats["units_assigned_larger_than_target_unknown_jur"] += 1
        else:
            if trace:
                trace.event('multi_anchor', us, 'unresolved',
                    'tie' if len(good) > 1 else 'incompatible_or_insufficient_support')
            if len(good) > 1:
                stats["units_unanchored_tie"] += 1
            elif any(cov[d] >= BAR for d in decisions):
                stats["units_unanchored_incompatible_only"] += 1
            else:
                stats["units_unanchored_weak_cocitation"] += 1
            pending.append((us, ids, uj))

    n = len(pending)
    parent = list(range(n))
    component_keys = [_identifier_keys(p[0]) for p in pending]

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            blocker = jurisdiction_constraint(pending[i][2], pending[j][2],
                pending[i][0], pending[j][0], trace, 'pending_jurisdiction')
            if blocker:
                continue
            a, b = pending[i][1], pending[j][1]
            proposal = cocitation_link(pending[i][0], pending[j][0], a, b, BAR,
                                        'cocitation_component', trace, 'pending_components')
            if proposal:
                ri, rj = find(i), find(j)
                if ri == rj:
                    continue
                keys, blocker = identifier_union_constraint(
                    component_keys[ri], component_keys[rj],
                    [m for q in range(n) if find(q) == ri for m in pending[q][0]],
                    [m for q in range(n) if find(q) == rj for m in pending[q][0]],
                    proposal, trace, 'pending_components')
                if blocker:
                    stats["pending_identifier_same_system_skipped"] += 1
                    stats["identifier_component_conflicts_blocked"] += 1
                    continue
                if proposal:
                    parent[ri] = rj
                    component_keys[rj] = keys
                    if trace:
                        trace.event('pending_components',
                            [m for q in range(n) if find(q) == rj for m in pending[q][0]],
                            'joined', constraint_ids=[proposal.constraint_id])
    comps = defaultdict(list)
    for i in range(n):
        comps[find(i)].append(i)
    pend_groups = [[m for i in c for m in pending[i][0]]
                   for c in sorted(comps.values(),
                                   key=lambda c: min(pending[i][0][0]["merge_key"] for i in c))]
    stats["rows_unanchored"] += sum(len(p[0]) for p in pending)
    stats["unanchored_groups"] += len(pend_groups)
    return _with_held([(buckets[d], "decision") for d in decisions] +
                      [(g, "decision;unanchored") for g in pend_groups], held)

def cluster_same_case(rows, did_idx, stats, start=None, registry=None,
                      typo_over=None, gate="literal", holdout=None, trace=None):
    """Build exact identifier/bilingual units first, then title/year windows and ordered court/decision partitions. Missing title/year does not create a cross-key identity link. Conflicting metadata on an exact unit remains visible."""
    from identity_courts import CourtEvidence
    courts = CourtEvidence()
    def court_evidence(row):
        early = not _self_of(row) and _before_start(row["merge_key"], start)
        found = courts.evidence(row, before_start=early)
        row["identity_court_evidence"] = "|".join(
            c + "=" + ";".join(sorted(e)) for c, e in sorted(found.items()))
        row.setdefault("identity_court_conflict", "false")
        return found
    for row in rows:
        court_evidence(row)
    buckets, out = defaultdict(list), []
    projections = {}
    exact_identifiers = defaultdict(list)
    bilingual_parent = {}
    def bilingual_root(code):
        bilingual_parent.setdefault(code, code)
        if bilingual_parent[code] != code:
            bilingual_parent[code] = bilingual_root(bilingual_parent[code])
        return bilingual_parent[code]
    for pair in load_bilingual():
        a, b = sorted(pair)
        a, b = bilingual_root(a), bilingual_root(b)
        bilingual_parent[max(a, b)] = min(a, b)
    units = []
    for r in rows:
        kind = r.get("citation_kind")
        if kind == "identifier" and identifier_system_of(r["merge_key"]):
            exact_identifiers["identifier:" + r["merge_key"]].append(r)
        elif kind == "neutral" and any(e.startswith("neutral_code:") for ev in court_evidence(r).values() for e in ev):
            parts = r["merge_key"].split("|")
            parts[2] = bilingual_root(parts[2])
            exact_identifiers["neutral:" + "|".join(parts)].append(r)
        else:
            units.append([r])
    units.extend(exact_identifiers[k] for k in sorted(exact_identifiers))
    for members in units:
        if len(members) > 1:
            proposal = atomic_link(members, trace)
            if proposal is None:
                raise AssertionError('Atomic identity lacks exact identifier evidence')
            if trace:
                trace.event('atomic_unit', members, 'joined', constraint_ids=[proposal.constraint_id])
        court_tokens = {c for r in members for c in court_evidence(r)}
        if len(court_tokens) > 1:
            for r in members:
                r["identity_court_conflict"] = "true"
            stats["identity_exact_unit_court_conflicts"] += 1
        names = {nk(r.get("case_name_modal") or "") for r in members} - {""}
        
        years = {row_year(r) for r in members if row_year(r) is not None}
        if len(names) == 1 and len(years) == 1 and len(court_tokens) <= 1:
            name, y = next(iter(names)), next(iter(years))
            unit_keys = tuple(sorted(row_key(r) for r in members))
            for r in members:
                projections[row_key(r)] = (name, y, unit_keys)
            buckets[name].extend((y, r) for r in members)
        else:
            # Exact ID is enough to join its own court rows, but conflicting or
            # absent metadata supplies no name/year link to a different key.
            reason = "identity_court_conflict" if len(court_tokens) > 1 else "identity_metadata_variants" if len(names) > 1 else ""
            out.append((members, reason, ""))
            if len(members) > 1:
                stats["identifier_exact_key_groups_without_name_link"] += 1

    for name in sorted(buckets):
        items = sorted(buckets[name], key=lambda t: (t[0], row_key(t[1])))
        chains, cur = [], [items[0]]
        for it in items[1:]:                 
            if it[0] - cur[-1][0] <= 1:
                cur.append(it)
            else:
                chains.append(cur)
                cur = [it]
        chains.append(cur)

        for ch in chains:
            if ch[-1][0] - ch[0][0] <= 1:
                parts = [([r for _, r in ch], "")]
            else:
                stats["chains_split_by_span"] += 1
                parts = [([r for _, r in p], "span") for p in windows(ch)]
            seq = 0
            for rows_, r0 in parts:
                proposal = name_year_link(rows_, trace, projections)
                if proposal is None:
                    raise AssertionError('Name/year bucket lacks scoped evidence')
                for court_rows, court_reason in partition(
                        rows_, did_idx, court_evidence, row_key, stats, BAR, trace):
                    for sub, r1 in split_by_decision(court_rows, did_idx, stats, start,
                                                     registry, typo_over, gate,
                                                     holdout, trace, proposal):
                        reason = ";".join(x for x in (r0, court_reason, r1) if x)
                        if reason:
                            out.append((sub, reason, seq))
                            seq += 1
                        else:
                            out.append((sub, "", ""))
                            if len(sub) > 1:
                                stats["groups_merged_parallel"] += 1
    return out

def merge_document_alias_clusters(clusters, own_cites, registry, stats, trace=None):
    """Join qualified same-document aliases without weakening cannot-link rules.

    The entire candidate component is checked, so a reporter bridge cannot hide
    a different real neutral/vendor identifier or incompatible positive court.
    A failed claim remains visible as separate existing clusters.
    """
    aliases = getattr(own_cites, 'aliases', {})
    if not aliases:
        return clusters
    from identity_courts import CourtEvidence
    courts = CourtEvidence()
    document_proofs = defaultdict(set)
    for key,did in aliases.items():
        for proof in own_cites.evidence[key]:
            if proof.get('identity_qualified') == 'true' and proof['decision_id'] == did:
                document_proofs[did].add(proof['evidence_id'])
    # Positive source-document claims also invalidate a heuristic merge that
    # already happened. Keeping that contaminated cluster would block the real
    # alias and preserve the known wrong identity. Unclaimed members are held
    # separately by their exact key; they do not inherit a document assignment.
    cleaned = []
    for members, reason, sequence in clusters:
        docs = {aliases[m['merge_key']] for m in members if m['merge_key'] in aliases}
        if len(docs) <= 1:
            cleaned.append((members, reason, sequence))
            continue
        blocker = document_union_constraint(members, aliases, registry, courts,
            {'trace': trace, 'phase': 'document_cleanup'})
        if blocker is None or blocker.rule != 'different_document_claims':
            raise AssertionError('Document cleanup requires distinct document claims')
        by_doc, unknown = defaultdict(list), defaultdict(list)
        for m in members:
            did = aliases.get(m['merge_key'])
            (by_doc[did] if did else unknown[m['merge_key']]).append(m)
        stats['document_claim_contaminated_clusters_split'] += 1
        stats['document_claim_unassigned_key_units'] += len(unknown)
        for did in sorted(by_doc):
            if trace:
                trace.event('document_cleanup', by_doc[did], 'partitioned',
                            'document_claim_conflict', [blocker.constraint_id])
            cleaned.append((by_doc[did], ';'.join(x for x in (reason,'document_claim_conflict') if x), ''))
        for key in sorted(unknown):
            if trace:
                trace.event('document_cleanup', unknown[key], 'partitioned',
                            'document_unassigned', [blocker.constraint_id])
            cleaned.append((unknown[key], ';'.join(x for x in (reason,'document_claim_conflict','document_unassigned') if x), ''))
    clusters = cleaned
    parent = list(range(len(clusters)))
    components = {i: list(members) for i,(members,_,_) in enumerate(clusters)}
    detached = []
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    by_document = defaultdict(set)
    for index,(members,_,_) in enumerate(clusters):
        for m in members:
            if m['merge_key'] in aliases:
                by_document[aliases[m['merge_key']]].add(index)
    for did in sorted(by_document):
        indices = sorted(by_document[did], key=lambda i: min(row_key(m) for m in components[find(i)]))
        if not indices:
            continue
        left = find(indices[0])
        for index in indices[1:]:
            right = find(index)
            left = find(left)
            if left == right:
                continue
            combined = components[left]+components[right]
            proposal = document_alias_link(components[left], components[right], aliases,
                                           did, own_cites, trace)
            if proposal is None:
                raise AssertionError('Alias component lacks qualified document evidence')
            blocker = document_union_constraint(combined, aliases, registry, courts,
                {'trace': trace, 'phase': 'document_alias', 'left': components[left],
                 'right': components[right], 'proposal': proposal})
            why = blocker.rule if blocker else ''
            if blocker:
                # A direct alias cannot drag pre-existing heuristic passengers
                # through the year/court/number guard. Isolate those unclaimed
                # exact keys, then connect only the compatible positive proof.
                proven = [m for m in combined if m['merge_key'] in aliases]
                if len(proven) < len(combined) and document_union_constraint(proven, aliases, registry, courts) is None:
                    for component in (left,right):
                        unclaimed = defaultdict(list)
                        keep = []
                        for m in components[component]:
                            (keep if m['merge_key'] in aliases else unclaimed[m['merge_key']]).append(m)
                        components[component] = keep
                        for key in sorted(unclaimed):
                            evidence = document_proofs[did]
                            for m in unclaimed[key]:
                                m['document_alias_holdout_doc_ids'] = '|'.join(sorted(
                                    set(filter(None,m.get('document_alias_holdout_doc_ids','').split('|'))) | {did}))
                                m['document_alias_holdout_evidence_ids'] = '|'.join(sorted(
                                    set(filter(None,m.get('document_alias_holdout_evidence_ids','').split('|'))) | evidence))
                            if trace:
                                trace.event('document_alias_detach', unclaimed[key], 'held_out', why,
                                            [proposal.constraint_id, blocker.constraint_id])
                            detached.append((unclaimed[key], 'unanchored;document_alias_'+why+'_holdout', ''))
                            stats['document_alias_unknown_key_units_held_'+why] += 1
                    combined = components[left]+components[right]
                    proposal = document_alias_link(components[left], components[right],
                        aliases, did, own_cites, trace, 'document_alias_proven')
                    blocker = document_union_constraint(combined, aliases, registry, courts,
                        {'trace': trace, 'phase': 'document_alias_proven', 'left': components[left],
                         'right': components[right], 'proposal': proposal})
                    why = blocker.rule if blocker else ''
            if blocker:
                stats['document_alias_blocked_'+why] += 1
                continue
            if proposal is None:
                raise AssertionError('Invalid document-alias proposal')
            if trace:
                trace.event('document_alias', combined, 'accepted', 'qualified_alias',
                            [proposal.constraint_id])
            parent[right] = left
            components[left] = combined
            del components[right]
            stats['document_alias_cluster_unions'] += 1
    result = []
    old_parts = defaultdict(list)
    for index, cluster in enumerate(clusters):
        old_parts[find(index)].append(cluster)
    for index in sorted(components):
        members = components[index]
        doc_keys = defaultdict(set)
        for m in members:
            if m['merge_key'] in aliases:
                doc_keys[aliases[m['merge_key']]].add(m['merge_key'])
        if document_union_constraint(members, aliases, registry, courts) is None:
            for m in members:
                did = aliases.get(m['merge_key'])
                if did and len(doc_keys[did]) > 1:
                    proofs = [r for r in own_cites.evidence[m['merge_key']]
                              if r.get('identity_qualified') == 'true' and r['decision_id'] == did]
                    m['document_alias_decision_id'] = did
                    m['document_alias_evidence_ids'] = '|'.join(sorted({r['evidence_id'] for r in proofs}))
                    m['document_alias_source_rows'] = '|'.join(sorted({r['source_court']+':'+r['corpus_row']+':'+r['field'] for r in proofs}))
                    stats['document_alias_qualified_member_rows'] += 1
        # Preserve earlier splitting evidence. Alias joins carry their own
        # positive columns and never turn unrelated heuristic members into core.
        reasons = sorted({reason for _,reason,_ in old_parts[index] if reason})
        result.append((members, ';'.join(reasons), ''))
    return result+detached

def assign_identity_basis(members, did_idx, start, reason):
    """Recompute final root/basis using the historical no-registry accounting call. Multiple rows sharing a key count as same-citation only when that key alone defines the group."""
    root, anc, ajur, own, root_kind = decisions_of(members, did_idx, start)
    anchors = {k for k in anc if root.get(k) == k}
    keycount = Counter(m["merge_key"] for m in members)

    single_key_group = len(keycount) == 1
    out = {}
    for m in members:
        k = m["merge_key"]
        if m.get('document_alias_decision_id') and m.get('document_alias_evidence_ids'):
            b = 'document_alias'
        elif len(members) == 1:
            b = "singleton"
        elif k in anchors:
            b = "anchor"
        elif k in root and root[k] != k:
            b = "anchor_variant_" + root_kind.get(k, "typo")
        elif single_key_group:
            b = "same_citation"
        elif "unanchored" in (reason or ""):
            b = "unanchored"
        elif "identifier_uncoited" in (reason or ""):

            b = "cocitation"
        elif "decision" in (reason or ""):
            b = "cocitation"
        else:
            b = "name_year"
        out[row_key(m)] = b
    return out

def partition(members, did_idx, evidence, row_key, stats, bar=0.8, trace=None):
    """Split only incompatible positive courts; unassigned members stay visible.

    A full merge key is atomic. Its own conflicting court evidence is flagged,
    not resolved by choosing one court or splitting the same identifier.
    """
    units = defaultdict(list)
    for row in members:
        units[row["merge_key"]].append(row)
    known, pending = defaultdict(list), []
    for key in sorted(units):
        rows = units[key]
        tokens = {c for row in rows for c in evidence(row)}
        if len(tokens) == 1:
            known[next(iter(tokens))].extend(rows)
        else:
            if len(tokens) > 1:
                stats["identity_member_court_conflicts"] += 1
                for row in rows:
                    row["identity_court_conflict"] = "true"
            pending.append(rows)
    blockers = court_partition_constraints(known, trace)
    if not blockers:
        return [(members, "")]
    stats["identity_clusters_split_by_court"] += 1
    ids = {court: set().union(*(did_idx.get(row_key(r), set()) for r in rows))
           for court, rows in known.items()}
    unassigned = []
    for rows in pending:
        sources = set().union(*(did_idx.get(row_key(r), set()) for r in rows))
        supported = []
        if not any(r.get("identity_court_conflict") == "true" for r in rows):
            for court, target in ids.items():
                denominator = min(len(sources), len(target))
                if denominator and len(sources & target) >= bar * denominator:
                    supported.append(court)
        # Two eligible courts is genuinely ambiguous, even if one has more hits.
        if len(supported) == 1:
            proposal = cocitation_link(rows, known[supported[0]], sources, ids[supported[0]],
                                        bar, 'unique_cocitation_court_assignment', trace,
                                        'court_assignment')
            if proposal is None:
                raise AssertionError('Court assignment lacks co-citation evidence')
            known[supported[0]].extend(rows)
            if trace:
                trace.event('court_assignment', rows, 'assigned', supported[0],
                            [proposal.constraint_id])
            stats["identity_unknown_court_assigned_by_cocitation"] += 1
        else:
            if trace:
                trace.event('court_assignment', rows, 'unresolved',
                            'ambiguous_or_insufficient_court_support')
            unassigned.extend(rows)
            stats["identity_unknown_court_unassigned_units"] += 1
    result = [(known[c], "court_evidence") for c in sorted(known)]
    if unassigned:
        result.append((unassigned, "court_evidence;court_unassigned"))
    if trace:
        for part, reason in result:
            trace.event('court_partition', part, 'partitioned', reason,
                        [blocker.constraint_id for blocker in blockers])
    return result

def solve_identity(rows, did_idx, prefix, stats, registry=None, typo_over=None,
                   holdout=None, gate="literal", own_cites=None,
                   identity_separations=None, trace=None):
    for row in rows:
        for field in ('document_alias_decision_id','document_alias_evidence_ids','document_alias_source_rows'):
            row[field] = ''
        row.setdefault('document_alias_holdout_doc_ids','')
        row.setdefault('document_alias_holdout_evidence_ids','')
        row.setdefault('identity_separation_evidence_ids','')
    start = neutral_start(rows)
    stats["neutral_rows_before_court_start"] = sum(
        1 for r in rows if r.get("citation_kind") == "neutral" and _before_start(r["merge_key"], start))
    # A guarded holdout discovered in one court must not be guessed back into
    # the same document at the cross-court stage. Propagate by the stable full
    # key, and accept the exclusion only when its current qualified proof IDs
    # still match the own-citation source snapshot.
    valid_proofs = defaultdict(set)
    for key in getattr(own_cites,'aliases',{}):
        for evidence in own_cites.evidence[key]:
            if evidence.get('identity_qualified') == 'true':
                valid_proofs[evidence['decision_id']].add(evidence['evidence_id'])
    held_by_key = defaultdict(lambda: [set(),set(),set()])
    for row in rows:
        proof_ids=set(filter(None,row['document_alias_holdout_evidence_ids'].split('|')))
        targets=set(filter(None,row['document_alias_holdout_doc_ids'].split('|')))
        if not targets and not proof_ids:
            continue
        target_proofs=set().union(*(valid_proofs.get(did,set()) for did in targets))
        if (not targets or not proof_ids or not proof_ids <= target_proofs or
            any(not valid_proofs.get(did) or not valid_proofs[did] <= proof_ids for did in targets)):
            raise ValueError('Document-alias holdout has stale, missing, incomplete or misbound target proofs')
        for did in targets:
            if proof_ids and proof_ids <= target_proofs and valid_proofs.get(did,set()) and valid_proofs[did] <= proof_ids:
                held_by_key[row['merge_key']][0].add(did)
                # Bind each retained target to its complete current proof set.
                # Partial/stale proofs from another target are never propagated.
                held_by_key[row['merge_key']][1].update(valid_proofs[did])
    separations = load_identity_separations() if identity_separations is None else identity_separations
    fact_by_id = {fact['evidence_id']:fact for fact in separations}
    row_keys = {row['merge_key'] for row in rows}
    for row in rows:
        for evidence_id in filter(None,row['identity_separation_evidence_ids'].split('|')):
            fact=fact_by_id.get(evidence_id)
            if (not fact or fact['merge_key']!=row['merge_key'] or
                fact['target_decision_id'] not in held_by_key[row['merge_key']][0]):
                raise ValueError('Identity separation has stale or misbound inherited evidence')
            held_by_key[row['merge_key']][2].add(evidence_id)
    # Apply reviewed non-identity facts through the existing persistent holdout
    # path. That path preserves source rows, propagates exact keys across courts,
    # blocks only the prohibited document, and permits another proven document.
    for fact in separations:
        if fact['merge_key'] not in row_keys:
            continue
        did=fact['target_decision_id']
        expected=set(fact['target_qualified_evidence_ids'].split('|'))
        qualified=[proof for key in getattr(own_cites,'aliases',{})
                   for proof in own_cites.evidence[key]
                   if proof.get('identity_qualified')=='true' and proof['decision_id']==did]
        sources={(p['source_court'],p['corpus_row'],p['corpus_sha256']) for p in qualified}
        source_hashes={p.get('corpus_sha256')
                       for values in getattr(own_cites,'evidence',{}).values() for p in values
                       if p.get('source_court')==fact['source_court'] and p.get('corpus_sha256')}
        if getattr(own_cites,'aliases',{}).get(fact['merge_key'])==did:
            raise ValueError('Identity separation conflicts with a current positive document alias')
        if (not expected or expected!=valid_proofs.get(did,set()) or len(sources)!=1 or
            source_hashes!={fact['corpus_sha256']}):
            raise ValueError('Identity separation has stale, missing or ambiguous current qualified proofs')
        held_by_key[fact['merge_key']][0].add(did)
        held_by_key[fact['merge_key']][1].update(expected)
        held_by_key[fact['merge_key']][2].add(fact['evidence_id'])
        stats['identity_separation_facts_applied'] += 1
    active,held= [],defaultdict(list)
    for row in rows:
        if row['merge_key'] in held_by_key:
            dids,proofs,separation_ids=held_by_key[row['merge_key']]
            row['document_alias_holdout_doc_ids']='|'.join(sorted(dids))
            row['document_alias_holdout_evidence_ids']='|'.join(sorted(proofs))
            row['identity_separation_evidence_ids']='|'.join(sorted(separation_ids))
            held[row['merge_key']].append(row)
        else:
            active.append(row)
    for key, members in held.items():
        for did in sorted(held_by_key[key][0]):
            targets = [r for r in rows if getattr(own_cites, 'aliases', {}).get(r['merge_key']) == did]
            blocker = document_holdout_constraints(members, targets, did,
                                                     valid_proofs[did], trace)
            if not blocker:
                raise AssertionError('Document holdout requires a blocker')
            if trace:
                trace.event('document_holdout', members, 'held_out', blocker.rule,
                            [blocker.constraint_id])
    stats['document_alias_inherited_holdout_key_units'] += len(held)
    clusters = cluster_same_case(active, did_idx, stats, start, registry, typo_over,
                                 gate, holdout, trace)
    clusters += [(held[key],'unanchored;document_alias_inherited_holdout','') for key in sorted(held)]
    clusters = merge_document_alias_clusters(clusters, own_cites, registry, stats, trace)

    if holdout:
        mixed = {h[0] for h in holdout}
        for r in rows:
            if r["merge_key"] in mixed and (r.get("case_name_modal") or ""):
                r["case_name_modal"] = ""
                prev = r.get("name_rejected_reason") or ""
                r["name_rejected_reason"] = (prev + "|mixed_identity"
                                             if prev else "mixed_identity")
                stats["mixed_identity_names_suppressed"] += 1
    clusters.sort(key=lambda c: min(row_key(m) for m in c[0]))

    if trace:
        for members, reason, sequence in clusters:
            trace.event('final_identity_partition', members, 'partitioned', reason)
    return clusters, start
