"""Verified reporter court envelopes, used only to forbid incompatible identities.

An envelope is not a positive court assignment or origin evidence. Unknown or
out-of-window rows supply no constraint. SCC appeal/leave reports and Yukon
reports are deliberately included where native citations disprove a narrower set.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

DEFAULT_RULES = Path(__file__).resolve().parents[1]/'decisions/reporter_identity_court_sets.csv'


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


@dataclass(frozen=True)
class ScopeRule:
    rule_id: str
    normalized_reporter: str
    allowed_codes: tuple[str, ...]
    year_start: int
    year_end: int | None
    evidence_json: str
    evidence_sha256: str


def load_scope_rules(path=DEFAULT_RULES):
    rules = []
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        for record in csv.DictReader(stream):
            if record['verification_status'] != 'verified_court_envelope':
                continue
            codes = tuple(record['allowed_court_codes'].split(';'))
            evidence = json.loads(record['evidence_json'])
            digest = hashlib.sha256(canonical_json(evidence).encode()).hexdigest()
            if (not record['rule_id'] or not re.fullmatch('[a-z0-9]+', record['normalized_reporter'])
                    or not codes or any(not re.fullmatch('[A-Z]+', c) for c in codes)
                    or not evidence.get('sources') or digest != record['evidence_sha256']):
                raise ValueError('Invalid reporter court-envelope provenance')
            lower = int(record['year_start'])
            upper = int(record['year_end']) if record['year_end'] else None
            if lower < 1600 or (upper is not None and upper < lower):
                raise ValueError('Invalid reporter court-envelope year window')
            if (list(codes) != evidence.get('court_codes')
                    or record['normalized_reporter'] != evidence.get('normalized_reporter')
                    or lower != evidence.get('year_start') or upper != evidence.get('year_end')):
                raise ValueError('Reporter court-envelope fields disagree with hashed provenance')
            rules.append(ScopeRule(record['rule_id'], record['normalized_reporter'], codes,
                                   lower, upper, canonical_json(evidence), digest))
    if not rules or len({r.rule_id for r in rules}) != len(rules):
        raise ValueError('Reporter court-envelope policy must be nonempty with unique rule IDs')
    return tuple(rules)


@lru_cache(maxsize=1)
def default_rules():
    return load_scope_rules()


def matching_rules(row, rules=None):
    parts = (row.get('merge_key') or '').split('|')
    if row.get('citation_kind') != 'reporter' or len(parts) != 5:
        return ()
    year = str(row.get('year_printed') or parts[0])
    if not re.fullmatch(r'\d{4}', year):
        return ()
    year = int(year)
    return tuple(rule for rule in (default_rules() if rules is None else rules)
                 if parts[2] == rule.normalized_reporter and year >= rule.year_start
                 and (rule.year_end is None or year <= rule.year_end))


def scope_evidence(row, rules=None, court_tokens=None):
    result = []
    for rule in matching_rules(row, rules):
        codes = [code.lower() for code in rule.allowed_codes]
        if court_tokens is None:
            allowed = ['court:'+code for code in codes]
        else:
            # Dropping an unrecognized member would narrow a verified envelope.
            # Abstain for the entire rule instead of inventing a stronger denial.
            if any(not court_tokens.get(code) for code in codes):
                return ()
            allowed = [court_tokens[code] for code in codes]
        result.append({'rule_id': rule.rule_id, 'allowed_courts': sorted(set(allowed)),
            'evidence': json.loads(rule.evidence_json), 'evidence_sha256': rule.evidence_sha256,
            'source_locator': 'decisions/reporter_identity_court_sets.csv#'+rule.rule_id})
    return tuple(result)


def allowed_courts(row, rules=None, court_tokens=None):
    """Return the conservative union of matching envelopes; empty means unknown."""
    return frozenset(token for fact in scope_evidence(row, rules, court_tokens)
                     for token in fact['allowed_courts'])


def scope_conflict(left, right):
    """Only two known, disjoint envelopes justify a cannot-link."""
    return bool(left and right and set(left).isdisjoint(right))


def scope_conflict_detail(left_rows, right_rows, trace=None, court_evidence=None):
    """Return the first evidence-backed scope/positive-court cannot-link.

    Reporter envelopes constrain a decision's possible court; they are never
    treated as positive court observations. A conflict exists only when two
    known envelopes do not intersect, or a known positive court falls outside
    the other component's envelope.
    """
    from identity_evidence import row_key
    if court_evidence is None:
        from identity_courts import CourtEvidence
        court_evidence = CourtEvidence()

    def observation(row):
        if trace is not None:
            info = trace.snapshot.reporter_scope_info(row)
            allowed = set(info['allowed_courts'])
            evidence_ids = set(info['evidence_ids'])
        else:
            facts = scope_evidence(row, court_tokens=court_evidence.tokens)
            allowed = {token for fact in facts for token in fact['allowed_courts']}
            evidence_ids = set()
        positives = set(court_evidence.evidence(row))
        return allowed, evidence_ids, positives

    left_observations = [(row, observation(row)) for row in left_rows]
    right_observations = [(row, observation(row)) for row in right_rows]
    for left, (left_allowed, left_refs, left_positive) in left_observations:
        for right, (right_allowed, right_refs, right_positive) in right_observations:
            basis = ''
            if scope_conflict(left_allowed, right_allowed):
                basis = 'disjoint_reporter_envelopes'
            elif (left_allowed and right_positive
                  and left_allowed.isdisjoint(right_positive)):
                basis = 'right_positive_court_outside_left_envelope'
            elif (right_allowed and left_positive
                  and right_allowed.isdisjoint(left_positive)):
                basis = 'left_positive_court_outside_right_envelope'
            if basis:
                detail = {
                    'basis': basis,
                    'left_row_key': row_key(left),
                    'right_row_key': row_key(right),
                    'left_allowed_courts': sorted(left_allowed),
                    'right_allowed_courts': sorted(right_allowed),
                    'left_positive_courts': sorted(left_positive),
                    'right_positive_courts': sorted(right_positive),
                    'scope_evidence_ids': sorted(left_refs | right_refs),
                }
                return detail, sorted(left_refs | right_refs)
    return None
