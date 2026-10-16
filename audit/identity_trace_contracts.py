"""Read-only structural contracts for every declared identity trace scope.

Kept independent of pipeline imports so a release audit cannot silently change
its checker by importing the solver it is checking. Semantic correctness and
native source spans are separate checks.
"""
from collections import Counter, defaultdict
import hashlib
import json


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def fact_id(record):
    return 'fact:' + hashlib.sha256(canonical_json(record).encode()).hexdigest()


def check_scope(run, relative):
    manifest = json.loads((run.path / relative / 'manifest.json').read_text(encoding='utf-8-sig'))
    trace = manifest['identity_trace']
    if trace['protocol'] != 'scoped-identity-constraints-v1':
        raise ValueError('Unsupported trace protocol')
    facts, rows, policies, court_refs = {}, {}, set(), []
    row_fact_ids = {}
    native_fact_ids = defaultdict(set)
    kinds = Counter()
    logical = relative + '/identity_evidence.csv'
    for _, record in run.rows(logical, ('evidence_id', 'scope', 'row_key', 'fact_kind', 'value_json', 'sources_json')):
        eid = record.pop('evidence_id')
        if eid in facts or eid != fact_id(record):
            raise ValueError('Duplicate or corrupt scoped evidence ID')
        value, sources = json.loads(record['value_json']), json.loads(record['sources_json'])
        if record['scope'] != ('XC' if manifest['mode'] == 'cross_court' else manifest['label']):
            raise ValueError('Evidence escaped its decide scope')
        facts[eid] = (record['row_key'], record['merge_key'], record['fact_kind'])
        kinds[record['fact_kind']] += 1
        if record['fact_kind'] == 'row_observation':
            if record['row_key'] in rows or record['row_key'] != record['court'] + '|' + record['merge_key']:
                raise ValueError('Duplicate or unscoped original row observation')
            if sources['input_row_key'] != record['row_key'] or sources['source_decision_ids'] != sorted(set(sources['source_decision_ids'])):
                raise ValueError('Noncanonical source evidence')
            rows[record['row_key']] = (record['merge_key'], tuple(sources['source_decision_ids']),
                                      tuple(filter(None, value.get('self_citation_of', '').split('|'))))
            row_fact_ids[record['row_key']] = eid
        elif record['fact_kind'] == 'own_citation_proof' and value.get('identity_qualified') == 'true':
            native_fact_ids[(value['decision_id'], value['evidence_id'])].add(eid)
        elif record['fact_kind'] == 'policy_record':
            policies.add(eid)
        elif record['fact_kind'] == 'court_observation':
            court_refs.extend(sources['policy_evidence_ids'])
    if not set(court_refs) <= policies:
        raise ValueError('Court observation cites missing policy facts')
    edges, relations, strength = {}, Counter(), Counter()
    for _, record in run.rows(relative + '/identity_constraints.csv', ('constraint_id', 'relation', 'evidence_ids_json')):
        cid = record.pop('constraint_id')
        if cid in edges or cid != 'constraint:' + hashlib.sha256(canonical_json(record).encode()).hexdigest():
            raise ValueError('Duplicate or corrupt constraint ID')
        refs = json.loads(record['evidence_ids_json'])
        if not refs or not set(refs) <= facts.keys() or record['relation'] not in ('must_link', 'cannot_link'):
            raise ValueError('Unbound identity relation')
        members = set(json.loads(record['left_members_json'])) | set(json.loads(record['right_members_json']))
        if not members or not members <= rows.keys():
            raise ValueError('Constraint endpoint lacks scoped original row')
        if not {row_fact_ids[key] for key in members} <= set(refs):
            raise ValueError('Constraint omits an endpoint original observation fact')
        if record['relation'] == 'must_link' and record['phase'] == 'single_anchor':
            right = json.loads(record['right_members_json'])
            if not right or len({rows[key][0] for key in right}) != 1:
                raise ValueError('Single-anchor proposal lacks an exact target anchor endpoint')
            target_sources = set()
            for key in right:
                target_sources.update(rows[key][1])
                target_sources.update(rows[key][2])
            if target_sources != set(json.loads(record['source_detail_json'])['right_sources']):
                raise ValueError('Single-anchor endpoint does not bind anc[target]|own[target]')
        if record['phase'] == 'document_holdout':
            detail = json.loads(record['source_detail_json'])
            for native in detail['qualified_evidence_ids']:
                required = native_fact_ids.get((detail['decision_id'], native), set())
                if not required or not required <= set(refs):
                    raise ValueError('Holdout edge omits complete exact-document native proof facts')
        edges[cid] = record['relation']
        relations[record['relation']] += 1
        strength[record['strength']] += 1
    conflicts, standalone, conflicted_blockers = 0, 0, set()
    for _, record in run.rows(relative + '/identity_conflicts.csv', ('attempted_constraint_id', 'blocking_constraint_ids_json')):
        attempt = record['attempted_constraint_id']
        blockers = json.loads(record['blocking_constraint_ids_json'])
        if attempt and edges.get(attempt) != 'must_link':
            raise ValueError('Conflict does not refer to an attempted must-link')
        if not blockers or any(edges.get(cid) != 'cannot_link' for cid in blockers):
            raise ValueError('Conflict lacks evidence-backed blocker')
        standalone += not bool(attempt)
        conflicts += 1
        conflicted_blockers.update(blockers)
    if {cid for cid, relation in edges.items() if relation == 'cannot_link'} - conflicted_blockers:
        raise ValueError('Negative constraint hidden from conflicts artifact')
    assigned, final_parts, sequence = {}, [], 0
    outcomes = Counter()
    for _, record in run.rows(relative + '/identity_solution.csv', ('sequence', 'phase', 'members_json', 'constraint_ids_json')):
        sequence += 1
        if record['sequence'] != str(sequence):
            raise ValueError('Nonconsecutive solver event sequence')
        members = tuple(json.loads(record['members_json']))
        if not set(members) <= rows.keys() or not set(json.loads(record['constraint_ids_json'])) <= edges.keys():
            raise ValueError('Solver event references missing source or relation')
        outcomes[record['phase'] + ':' + record['outcome']] += 1
        if record['phase'] == 'assigned_group_id':
            if record['group_id'] in assigned:
                raise ValueError('Duplicate final group assignment')
            assigned[record['group_id']] = members
        if record['phase'] == 'final_identity_partition':
            final_parts.append(members)
    actual, source_ids = defaultdict(set), defaultdict(set)
    for _, record in run.rows(relative + '/decided.csv', ('court', 'merge_key', 'merged_group_id')):
        key = record['court'] + '|' + record['merge_key']
        actual[record['merged_group_id']].add(key)
    for _, record in run.rows(relative + '/decision_ids.csv', ('row_key', 'source_decision_citation')):
        source_ids[record['row_key']].add(record['source_decision_citation'])
    if {gid: tuple(sorted(members)) for gid, members in actual.items()} != assigned:
        raise ValueError('Solution group IDs or members differ from product outputs')
    if sorted(final_parts) != sorted(assigned.values()):
        raise ValueError('Sorted final partitions differ from assigned membership')
    if set().union(*actual.values()) != rows.keys():
        raise ValueError('Original rows were lost or invented')
    for key, (_, sources, _) in rows.items():
        if set(sources) != source_ids.get(key, set()):
            raise ValueError('Scoped evidence source set differs from unchanged provenance output')
    counts = {'evidence': len(facts), 'constraints': len(edges), 'conflicts': conflicts, 'solution': sequence}
    if counts != trace['counts']:
        raise ValueError('Trace manifest counts disagree with sealed artifacts')
    return {'scope': manifest['label'], 'status': 'passed', 'rows': len(rows), 'groups': len(actual),
            'counts': counts, 'fact_kinds': dict(kinds), 'relations': dict(relations),
            'strengths': dict(strength), 'standalone_conflicts': standalone,
            'events': dict(outcomes)}
