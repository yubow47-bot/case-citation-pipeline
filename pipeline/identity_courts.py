"""Positive court evidence for separating judgments of different courts.

Never uses the citing court, reporter publication country or a guessed abbreviation.
Missing evidence remains missing. These constraints do not prove case identity.
"""
import csv
from collections import defaultdict
from pathlib import Path
import re

DECISIONS = Path(__file__).resolve().parents[1] / "decisions"


def nk(value):
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


class CourtEvidence:
    def __init__(self, decisions=DECISIONS):
        decisions = Path(decisions)
        self.parent = {}
        self.known = set()
        self.scope = defaultdict(list)
        self.exact = defaultdict(list)
        for r in self.read(decisions / "neutral_court_codes.csv"):
            code = nk(r.get("court_code"))
            if code and r.get("source") and r.get("source_locator"):
                self.known.add(code)
                self.find(code)
        # A recognized printed designation is an explicit alias of its canonical
        # court, rather than a generic prefix or a name similarity heuristic.
        for r in self.read(decisions / "court_designations.csv"):
            if r.get("status") == "recognized" and r.get("canonical_court"):
                self.union(nk(r.get("normalized_key")), nk(r["canonical_court"]))
        for r in self.read(decisions / "bilingual_neutral_codes.csv"):
            if r.get("verification_status") == "verified_explicit_equivalence":
                self.union(nk(r.get("code_en")), nk(r.get("code_fr")))
        components = defaultdict(set)
        for code in self.known:
            components[self.find(code)].add(code)
        self.tokens = {}
        for alias in list(self.parent):
            known = components.get(self.find(alias))
            if known:
                self.tokens[alias] = "court:" + min(known)
        for r in self.read(decisions / "identity_court_scope.csv"):
            if r.get("verification_status") == "verified_existing_statute":
                self.scope[(r.get("citation_kind"), nk(r.get("printed_key")))].append(r)
        # A curated exact key is supported by a separately verified native
        # corpus span, never by the citing court or a national reporter label.
        for r in self.read(decisions / 'identity_court_facts.csv'):
            if r.get('verification_status') != 'verified_corpus_court':
                continue
            required = ('merge_key','canonical_court','source_corpus','corpus_row',
                        'text_field','source_decision','evidence_id','source_locator')
            hashes = ('corpus_sha256','text_sha256','span_sha256')
            if (any(not r.get(k) for k in required) or
                any(not re.fullmatch(r'[0-9a-f]{64}',r.get(k,'')) for k in hashes) or
                not r['corpus_row'].isdigit() or not r.get('span_start','').isdigit() or
                not r.get('span_end','').isdigit() or int(r['span_end'])<=int(r['span_start']) or
                r['text_field'] not in ('unofficial_text_en','unofficial_text_fr') or
                nk(r['canonical_court']) not in self.tokens):
                raise ValueError('Verified exact-key court fact lacks complete provenance')
            self.exact[r['merge_key']].append(r)

    @staticmethod
    def read(path):
        if not path.is_file():
            return []
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def find(self, item):
        self.parent.setdefault(item, item)
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, a, b):
        if a and b:
            a, b = self.find(a), self.find(b)
            self.parent[max(a, b)] = min(a, b)

    def evidence(self, row, before_start=False):
        evidence = defaultdict(set)
        parts = row["merge_key"].split("|")
        code = nk(parts[2]) if len(parts) >= 3 else ""
        kind = row.get("citation_kind", "")
        for fact in self.exact.get(row['merge_key'], []):
            token = self.tokens[nk(fact['canonical_court'])]
            evidence[token].add('verified_corpus_court:'+fact['evidence_id'])
        if kind == "neutral" and not before_start and code in self.known:
            evidence[self.tokens[code]].add("neutral_code:" + code)
        observed = row.get("observed_deciding_court") or ""
        if row.get("court_designation_conflict") not in ("true", True):
            token = self.tokens.get(nk(observed))
            if token:
                evidence[token].add("printed_court:" + observed)
        year = row.get("year_printed") or (parts[0] if parts else "")
        if str(year).isdigit():
            year = int(year)
            for rule in self.scope.get((kind, code), []):
                lower, upper = rule.get("year_start"), rule.get("year_end")
                if lower and year < int(lower) or upper and year > int(upper):
                    continue
                token = self.tokens.get(nk(rule["canonical_court"]))
                if token:
                    evidence[token].add("exclusive_court_scope:" + rule["printed_key"])
        return dict(evidence)


def partition(members, did_idx, evidence, row_key, stats, bar=0.8):
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
    if len(known) < 2:
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
            known[supported[0]].extend(rows)
            stats["identity_unknown_court_assigned_by_cocitation"] += 1
        else:
            unassigned.extend(rows)
            stats["identity_unknown_court_unassigned_units"] += 1
    result = [(known[c], "court_evidence") for c in sorted(known)]
    if unassigned:
        result.append((unassigned, "court_evidence;court_unassigned"))
    return result
