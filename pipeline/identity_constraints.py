"""Compile evidence-backed local relations without mutating identity components.

Must-link edges are phase-local proposals, not unconditional equivalence. Conflict
rows with no attempted ID describe standalone evidence-backed exclusions.
"""
import csv
import gzip
import hashlib
from pathlib import Path
from dataclasses import dataclass
from collections import defaultdict

from identity_evidence import (FACT_FIELDS, canonical_json, row_key, row_year,
    _neutral_parts, load_bilingual, load_identifier_systems, identifier_system_of)
from normalize import nk

CONSTRAINT_FIELDS = ('constraint_id', 'phase', 'context_id', 'left_members_json',
                     'right_members_json', 'relation', 'rule', 'evidence_ids_json',
                     'strength', 'source_detail_json')
SOLUTION_FIELDS = ('sequence', 'phase', 'context_id', 'members_json', 'outcome', 'group_id',
                   'split_reason', 'constraint_ids_json')
CONFLICT_FIELDS = ('phase', 'context_id', 'attempted_constraint_id',
                   'blocking_constraint_ids_json', 'reason', 'members_json')


class ConstraintLedger:
    """Record ordered local proposals and outcomes, without applying closure.

    A heuristic must-link is an attempted local proposal. It is not a global
    equivalence assertion. Missing support is an unresolved outcome, never a
    cannot-link fact.
    """
    def __init__(self, snapshot, output=None):
        self.snapshot, self.output = snapshot, Path(output) if output else None
        self.records = {'evidence': [], 'constraints': [], 'solution': [], 'conflicts': []}
        self.counts = dict.fromkeys(self.records, 0)
        self.writers, self.streams, self.seen = {}, [], set()
        self.context_constraints = {}
        if self.output:
            self.output.mkdir(parents=True, exist_ok=True)
            for name, fields in (('evidence', FACT_FIELDS), ('constraints', CONSTRAINT_FIELDS),
                                 ('solution', SOLUTION_FIELDS), ('conflicts', CONFLICT_FIELDS)):
                stream = gzip.open(self.output / ('identity_' + name + '.csv.gz'),
                                   'wt', encoding='utf-8', newline='')
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                self.writers[name] = writer
                self.streams.append(stream)
        for record in sorted(snapshot.records, key=lambda r: r['evidence_id']):
            self.emit('evidence', record)
        if self.output:
            snapshot.records.clear()

    def emit(self, name, record):
        self.counts[name] += 1
        if self.output:
            self.writers[name].writerow(record)
        else:
            self.records[name].append(record)

    @staticmethod
    def members(rows):
        return sorted({row_key(row) for row in rows})

    def context(self, phase, rows):
        return phase + ':' + hashlib.sha256(canonical_json(self.members(rows)).encode()).hexdigest()

    def _edge(self, phase, left, right, relation, rule, strength='heuristic', detail=None,
             context=None, additional_evidence_ids=()):
        if relation not in ('must_link', 'cannot_link'):
            raise ValueError('Unknown identity constraint relation')
        rows = list(left) + list(right)
        additional = set(additional_evidence_ids)
        if not additional <= self.snapshot.evidence_ids:
            raise ValueError('Additional constraint evidence is absent from the snapshot')
        refs = sorted(set(self.snapshot.refs(rows, rule)) | additional)
        if not refs:
            raise ValueError('Identity constraint requires source evidence')
        context = context or self.context(phase, rows)
        payload = {'phase': phase, 'context_id': context,
                   'left_members_json': canonical_json(self.members(left)),
                   'right_members_json': canonical_json(self.members(right)),
                   'relation': relation, 'rule': rule,
                   'evidence_ids_json': canonical_json(refs), 'strength': strength,
                   'source_detail_json': canonical_json(detail or {})}
        cid = 'constraint:' + hashlib.sha256(canonical_json(payload).encode()).hexdigest()
        if cid not in self.seen:
            self.seen.add(cid)
            self.emit('constraints', {'constraint_id': cid, **payload})
            self.context_constraints.setdefault(context, set()).add(cid)
        return cid

    def event(self, phase, rows, outcome, reason='', constraint_ids=(), group_id='', context=None):
        context = context or self.context(phase, rows)
        self.emit('solution', {'sequence': self.counts['solution'] + 1, 'phase': phase, 'context_id': context,
                             'members_json': canonical_json(self.members(rows)),
                             'outcome': outcome, 'group_id': group_id, 'split_reason': reason,
                             'constraint_ids_json': canonical_json(sorted(set(constraint_ids)))})

    def _proposal(self, phase, left, right, rule, strength='heuristic', detail=None,
                  additional_evidence_ids=()):
        return self._edge(phase, left, right, 'must_link', rule, strength, detail,
                          additional_evidence_ids=additional_evidence_ids)

    def _reject(self, phase, left, right, attempt, reason, detail=None, strength='explicit',
                additional_evidence_ids=()):
        block = self._edge(phase, left, right, 'cannot_link', reason, strength, detail,
                           additional_evidence_ids=additional_evidence_ids)
        self.emit('conflicts', {'phase': phase, 'context_id': self.context(phase, list(left)+list(right)),
                              'attempted_constraint_id': attempt,
                              'blocking_constraint_ids_json': canonical_json([block]),
                              'reason': reason,
                              'members_json': canonical_json(self.members(list(left)+list(right)))})
        return block

    def close(self):
        for stream in self.streams:
            stream.close()
        self.streams = []
        return {'protocol': 'scoped-identity-constraints-v1', 'counts': dict(self.counts),
                'artifacts': {name: 'identity_' + name + '.csv.gz' for name in self.counts}}

@dataclass(frozen=True)
class ConstraintEdge:
    """Immutable local relation; compatibility tokens are never persisted."""
    relation: str
    rule: str
    constraint_id: str = ''
    members: tuple = ()

    @property
    def recorded(self):
        return bool(self.constraint_id)


@dataclass(frozen=True)
class VariantConstraints:
    proposal: object = None
    blocker: object = None
    kind: str = ''
    registered: bool = False
    in_registry: bool = False


def _proposal(trace, phase, left, right, rule, strength='heuristic', detail=None,
              additional_evidence_ids=()):
    cid = (trace._proposal(phase, left, right, rule, strength, detail,
                           additional_evidence_ids) if trace else '')
    return ConstraintEdge('must_link', rule, cid, tuple(sorted({row_key(m) for m in list(left) + list(right)})))


def _block(trace, phase, left, right, proposal, rule, detail=None, strength='explicit',
           additional_evidence_ids=()):
    if trace:
        if proposal:
            cid = trace._reject(phase, left, right, proposal.constraint_id, rule, detail, strength,
                                additional_evidence_ids)
        else:
            cid = trace._edge(phase, left, right, 'cannot_link', rule, strength, detail,
                              additional_evidence_ids=additional_evidence_ids)
            trace.emit('conflicts', {'phase': phase,
                'context_id': trace.context(phase, list(left) + list(right)),
                'attempted_constraint_id': '',
                'blocking_constraint_ids_json': canonical_json([cid]), 'reason': rule,
                'members_json': canonical_json(trace.members(list(left) + list(right)))})
    else:
        cid = ''
    return ConstraintEdge('cannot_link', rule, cid)

def _one_edit(a, b):
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    s, l = (a, b) if len(a) < len(b) else (b, a)
    return any(l[:i] + l[i + 1:] == s for i in range(len(l)))


def mixed_identity(k_classes, big_name):
    """Hold out a key only when its printed names include both the target name and another name. Empty names supply no contrary evidence; no count threshold is introduced."""
    if not big_name or not k_classes:
        return "fold"
    hit_big = big_name in k_classes
    hit_other = any(n != big_name for n in k_classes)
    return "holdout" if (hit_big and hit_other) else "fold"


def verified_bilingual_keys(ka, kb):
    """Exact year/series/number agreement and an explicitly verified code pair."""
    a, b = ka.split('|'), kb.split('|')
    if (len(a) != 5 or len(b) != 5 or a[1] or b[1] or
        not (len(a[0]) == len(b[0]) == 4 and a[0].isdigit() and b[0].isdigit()) or
        not (a[4].isdigit() and b[4].isdigit())):
        return False
    ya, ca, sa, na = _neutral_parts(ka)
    yb, cb, sb, nb = _neutral_parts(kb)
    return (ya == yb and na == nb and sa == sb and
            frozenset((ca, cb)) in load_bilingual())


def same_decision_kind(ka, ja, dda, kb, jb, ddb):
    """Return the legacy bilingual/typo-number/typo-year variant rule. Only verified bilingual equivalence can support origin propagation."""
    ya, ca, sa, na = _neutral_parts(ka)
    yb, cb, sb, nb = _neutral_parts(kb)
    if ya == yb and na == nb and sa == sb and ja and ja == jb:

        if frozenset((ca, cb)) in load_bilingual():
            return "bilingual"
        return None
    if (ca, sa) != (cb, sb) or 2 * dda > ddb:
        return None

    if ca in load_identifier_systems() or cb in load_identifier_systems():
        return None
    if ya == yb and _one_edit(na, nb):
        return "typo_number"
    if na == nb and ya.isdigit() and yb.isdigit() and abs(int(ya) - int(yb)) == 1:
        return "typo_year"
    return None


def same_decision(ka, ja, dda, kb, jb, ddb):
    return same_decision_kind(ka, ja, dda, kb, jb, ddb) is not None


def _identifier_keys(members):
    """An identifier system may contribute one distinct key to an identity.

    Several court rows carrying that exact key are the same identifier, not a
    conflict. Keep keys, rather than only system names, for component-level checks.
    """
    out = defaultdict(set)
    for m in members:
        system = identifier_system_of(m["merge_key"])
        if system:
            out[system].add(m["merge_key"])
    return dict(out)


def _combined_identifier_keys(left, right):
    """Return the union, or None when it would join different IDs in one system.

    This checks whole union-find components: a cross-system bridge must not make
    a cannot-link disappear after the first union.
    """
    combined = {system: set(keys) for system, keys in left.items()}
    for system, keys in right.items():
        combined.setdefault(system, set()).update(keys)
    return None if any(len(keys) > 1 for keys in combined.values()) else combined



def variant_constraints(k, big, anc, ajur, own, same_name, classes, kname,
                        registry, gate, holdout_enabled, rows, trace=None):
    """Compile one ordered neutral candidate without assigning either root."""
    registered = bool(registry and k in registry)
    in_registry = bool(own[k]) or registered
    kind = same_decision_kind(k, ajur[k], len(anc[k]), big, ajur[big], len(anc[big]))
    if gate == 'literal':
        blocked = in_registry and same_name[k]
    elif gate == 'own_or_registry':
        blocked = (bool(own[k]) or registered) and same_name[k]
    elif gate == 'registered_only':
        blocked = (bool(own[k]) and same_name[k]) or (registered and not own[k])
    elif gate == 'registered':
        blocked = in_registry and kind != 'bilingual'
    else:
        raise SystemExit('Unknown --registry-gate: %r' % gate)
    if not kind:
        return VariantConstraints(registered=registered, in_registry=in_registry)
    left = [m for m in rows if m['merge_key'] == k]
    right = [m for m in rows if m['merge_key'] == big]
    proposal = _proposal(trace, 'variant', left, right, kind,
                         'explicit' if kind == 'bilingual' else 'heuristic', {'gate': gate})
    blocker = None
    if blocked:
        blocker = _block(trace, 'variant', left, right, proposal,
                         'registered_identity_guard', {'gate': gate})
    elif holdout_enabled and mixed_identity(classes.get(k) or {}, kname.get(big) or '') == 'holdout':
        blocker = _block(trace, 'variant', left, right, proposal, 'mixed_title_holdout')
    return VariantConstraints(proposal, blocker, kind, registered, in_registry)


def identifier_union_constraint(left_keys, right_keys, left, right, proposal=None,
                                trace=None, phase='identifier_union'):
    """Compile a whole-component same-system number exclusion."""
    combined = _combined_identifier_keys(left_keys, right_keys)
    blocker = (_block(trace, phase, left, right, proposal, 'different_identifier_numbers')
               if combined is None else None)
    return combined, blocker


def document_union_constraint(members, aliases, registry, courts, context=None):
    """Compile the first legacy component blocker, without mutating components."""
    context = context or {}
    docs = {aliases[m['merge_key']] for m in members if m['merge_key'] in aliases}
    reason = ''
    detail = context.get('detail')
    additional_evidence_ids = ()
    if len(docs) > 1:
        reason = 'different_document_claims'
    elif docs and any(next(iter(docs)) in set(filter(None, m.get('document_alias_holdout_doc_ids', '').split('|')))
                      for m in members):
        reason = 'explicit_document_holdout'
    elif any(len(keys) > 1 for keys in _identifier_keys(members).values()):
        reason = 'different_identifier_numbers'
    else:
        tokens = {token for m in members for token in courts.evidence(m)}
        if len(tokens) > 1 or any(m.get('identity_court_conflict') == 'true' for m in members):
            reason = 'positive_court_conflict'
        else:
            from reporter_identity_scope import scope_conflict_detail
            scope_conflict = scope_conflict_detail(
                context.get('left', members[:1]), context.get('right', members[1:]),
                trace=context.get('trace'), court_evidence=courts)
            if scope_conflict:
                detail, additional_evidence_ids = scope_conflict
                reason = 'incompatible_reporter_identity_scope'
            else:
                years = {row_year(m) for m in members if m.get('case_name_modal') and row_year(m) is not None}
                if years and max(years) - min(years) > 1:
                    reason = 'year_span'
                else:
                    neutral_source_keys = {m['merge_key'] for m in members
                                           if m.get('citation_kind') == 'neutral'}
                    neutral_roots = context.get('neutral_roots') or {}
                    neutrals = {neutral_roots.get(key, key) for key in neutral_source_keys}
                    if len(neutrals) > 1:
                        first = min(neutrals)
                        if any(not verified_bilingual_keys(first, key) for key in neutrals - {first}):
                            reason = 'different_neutral_numbers'
                    if not reason:
                        doc = next(iter(docs), '')
                        for key in neutral_source_keys:
                            protected = (registry or {}).get(key)
                            if protected and doc and doc not in protected[0].split(';'):
                                reason = 'registered_other_document'
                                break
    if not reason:
        return None
    return _block(context.get('trace'), context.get('phase', 'document_alias'),
                  context.get('left', members[:1]), context.get('right', members[1:]),
                  context.get('proposal'), reason, detail,
                  additional_evidence_ids=additional_evidence_ids)


def court_partition_constraints(known, trace=None):
    """Compile pairwise positive-court exclusions, without choosing a partition."""
    courts = sorted(known)
    return [_block(trace, 'court_partition', known[a], known[b], None,
                   'incompatible_positive_courts', {'left_court': a, 'right_court': b})
            for index, a in enumerate(courts) for b in courts[index + 1:]]


def document_holdout_constraints(members, targets, did, proof_ids, trace=None):
    """Require exact current proof-bound holdout annotations before exclusion."""
    proofs = set(proof_ids)
    if not proofs or any(did not in set(filter(None, m.get('document_alias_holdout_doc_ids', '').split('|')))
        or not proofs <= set(filter(None, m.get('document_alias_holdout_evidence_ids', '').split('|')))
        for m in members):
        raise ValueError('Document holdout constraint lacks exact current proof-bound facts')
    native_facts = trace.snapshot.native_proof_facts(did, proofs) if trace else ()
    return _block(trace, 'document_holdout', members, targets, None,
                  'explicit_or_inherited_document_holdout', {'decision_id': did,
                                                            'qualified_evidence_ids': sorted(proofs)},
                  additional_evidence_ids=native_facts)


def _connected_neutral_keys(keys):
    first = next(iter(keys)).split('|')
    if len(first) != 5:
        return False
    parent = {}
    def find(code):
        parent.setdefault(code, code)
        if parent[code] != code:
            parent[code] = find(parent[code])
        return parent[code]
    for pair in load_bilingual():
        a, b = sorted(pair)
        a, b = find(a), find(b)
        parent[max(a, b)] = min(a, b)
    for key in keys:
        parts = key.split('|')
        if len(parts) != 5 or parts[:2] + parts[3:] != first[:2] + first[3:] or find(parts[2]) != find(first[2]):
            return False
    return True


def atomic_link(members, trace=None):
    """Require exact identifier or legacy transitively bilingual neutral unit."""
    keys = {m['merge_key'] for m in members}
    first = members[0]['merge_key']
    if len(keys) == 1 and identifier_system_of(first):
        return _proposal(trace, 'atomic_unit', members[:1], members[1:], 'exact_identifier_key', 'explicit')
    if all(m.get('citation_kind') == 'neutral' for m in members) and _connected_neutral_keys(keys):
        return _proposal(trace, 'atomic_unit', members[:1], members[1:], 'exact_or_bilingual_neutral_key', 'explicit')
    return None


def name_year_link(members, trace=None, projections=None):
    """Validate original atomic-unit projections before proposing a window."""
    if projections is None:
        names = {nk(m.get('case_name_modal') or '') for m in members}
        years = [row_year(m) for m in members]
        if len(names) != 1 or not next(iter(names)) or any(y is None for y in years) or max(years) - min(years) > 1:
            return None
        detail = {}
    else:
        by_key = {row_key(m): m for m in members}
        checked, years, names = set(), set(), set()
        for member in members:
            projection = projections.get(row_key(member))
            if projection is None:
                return None
            name, year, unit_keys = projection
            unit_keys = tuple(unit_keys)
            if not set(unit_keys) <= by_key.keys():
                return None
            if unit_keys not in checked:
                unit = [by_key[key] for key in unit_keys]
                if len(unit) > 1 and atomic_link(unit) is None:
                    return None
                actual_names = {nk(m.get('case_name_modal') or '') for m in unit} - {''}
                actual_years = {row_year(m) for m in unit if row_year(m) is not None}
                if actual_names != {name} or actual_years != {year}:
                    return None
                checked.add(unit_keys)
            names.add(name)
            years.add(year)
        if len(names) != 1 or max(years) - min(years) > 1:
            return None
        detail = {'atomic_unit_projections': {key: projections[key] for key in sorted(by_key)}}
    return _proposal(trace, 'name_year_window', members[:1], members[1:],
                     'same_normalized_title_within_year_window', detail=detail)


def cocitation_link(left, right, left_sources, right_sources, bar, rule,
                    trace=None, phase='cocitation', comparison='product'):
    small = min(len(left_sources), len(right_sources))
    overlap = len(left_sources & right_sources)
    if comparison not in ('ratio', 'product'):
        raise ValueError('Unknown legacy co-citation comparator')
    supported = bool(small) and (overlap / small >= bar if comparison == 'ratio'
                                 else overlap >= bar * small)
    if not supported:
        return None
    return _proposal(trace, phase, left, right, rule,
                     detail={'overlap': overlap, 'left_sources': sorted(left_sources),
                             'right_sources': sorted(right_sources), 'bar': bar, 'comparison': comparison})


def document_alias_link(left, right, aliases, did, own_cites, trace=None,
                        phase='document_alias'):
    """Require qualified positive document evidence on both components."""
    for members in (left, right):
        found = False
        for m in members:
            key = m['merge_key']
            if aliases.get(key) != did:
                continue
            if any(p.get('identity_qualified') == 'true' and p.get('decision_id') == did
                   for p in own_cites.evidence[key]):
                found = True
        if not found:
            return None
    return _proposal(trace, phase, left, right, 'qualified_same_document_alias',
                     'explicit', {'decision_id': did})


def alias_root_link(left, right, did, left_witnesses, right_witnesses,
                    original_roots, left_root, target_root, trace=None):
    """Compile root equivalence from original annotated member witnesses."""
    for witnesses, expected_root in ((left_witnesses, left_root),
                                     (right_witnesses, target_root)):
        matched = False
        for member in witnesses:
            if (member.get('document_alias_decision_id') != did or
                original_roots.get(member['merge_key']) != expected_root):
                continue
            proof_ids = set(filter(None, member.get('document_alias_evidence_ids', '').split('|')))
            if not proof_ids:
                continue
            if trace:
                key = member['merge_key']
                if (trace.snapshot.qualified_aliases.get(key) != did or
                    not proof_ids <= trace.snapshot.qualified_proofs.get((key, did), set())):
                    raise ValueError('Alias root annotation lacks matching qualified source proofs')
            matched = True
        if not matched:
            return None
    return _proposal(trace, 'alias_root', list(left) + list(left_witnesses),
                     list(right) + list(right_witnesses), 'qualified_document_alias_root',
                     'explicit', {'decision_id': did, 'left_root': left_root,
                                  'target_root': target_root,
                                  'left_witnesses': sorted(row_key(m) for m in left_witnesses),
                                  'right_witnesses': sorted(row_key(m) for m in right_witnesses)})


def anchor_root_link(unit, target_rows, target, roots, root_kinds, trace=None):
    """Compile membership in an already accepted root, without choosing a root."""
    if target is None or any(roots.get(m['merge_key']) != target for m in unit):
        return None
    return _proposal(trace, 'anchor_root', unit, target_rows, 'accepted_anchor_root_membership',
                     detail={'target_root': target,
                             'root_kinds': {m['merge_key']: root_kinds.get(m['merge_key'], 'anchor')
                                            for m in unit}})


def _legacy_bucket_admission():
    """Internal direct-helper compatibility token; never emit as evidence."""
    return ConstraintEdge('must_link', 'legacy_bucket_admission')


def jurisdiction_constraint(a, b, left, right, trace=None, phase='jurisdiction'):
    """Compile only the historical jurisdiction heuristic, not court proof."""
    if a is None or b is None or (a and b and a != b):
        return _block(trace, phase, left, right, None, 'legacy_jurisdiction_compatibility',
                      {'left_jurisdiction': a, 'right_jurisdiction': b}, 'heuristic')
    return None
