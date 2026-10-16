"""Scoped identity facts and source provenance; no identity partition decisions."""
import csv
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

from normalize import nk
from artifacts import open_csv, resolve as resolve_artifact, sha256_logical_csv_bytes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DECISIONS = os.path.join(ROOT, "decisions")

SEPARATION_FIELDS = ('merge_key','target_decision_id','target_qualified_evidence_ids',
    'verification_status','source_court','source_decision','source_corpus','corpus_sha256',
    'corpus_row','text_field','text_sha256','span_start','span_end','span_sha256',
    'source_locator','evidence_id')

CASE_ORIGIN_MANUAL_STATUS = frozenset(("verified_research_agent",))

REPORTER_ORIGIN_ALLOWED_STATUSES = frozenset((
    "verified_exclusive_statute",
    "verified_exclusive_publisher",
))

ALLOWED_IDENTIFIER_STATUSES = {
    "verified_official_source",
    "verified_authoritative_manual",
}

_IDENTIFIER_CACHE = None

ALLOWED_BILINGUAL_STATUSES = {
    "verified_explicit_equivalence",
}

_BILINGUAL_CACHE = None

def load_identity_separations(path=None):
    """Read exact, source-bound non-identity facts; never infer a deciding court.

    Every row is a reviewed negative claim against one qualified document,
    bound to its complete current metadata/header proof set. Bad or stale
    claims fail closed rather than allowing a heuristic merge to reappear.
    """
    path = path or os.path.join(DECISIONS,'identity_separations.csv')
    if os.path.getsize(path) > 1024*1024:
        raise ValueError('Identity separation table exceeds the byte budget')
    facts, pairs, evidence_ids = [],set(),set()
    with open(path,encoding='utf-8-sig',newline='') as source:
        reader=csv.DictReader(source,strict=True)
        if tuple(reader.fieldnames or ()) != SEPARATION_FIELDS:
            raise ValueError('Identity separation columns are missing, duplicate or unexpected')
        for row in reader:
            if None in row or any(not value for value in row.values()):
                raise ValueError('Identity separation lacks complete provenance')
            hashes=('corpus_sha256','text_sha256','span_sha256')
            proofs=row['target_qualified_evidence_ids'].split('|')
            pair=(row['merge_key'],row['target_decision_id'])
            expected='sep:'+hashlib.sha256(json.dumps({k:v for k,v in row.items() if k!='evidence_id'},
                ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
            if (row['verification_status']!='verified_native_distinct_judgment' or
                len(row['merge_key'].split('|'))!=5 or not any(row['merge_key'].split('|')) or
                any(not re.fullmatch(r'[0-9a-f]{64}',row[k]) for k in hashes) or
                not row['corpus_row'].isdigit() or not row['span_start'].isdigit() or
                not row['span_end'].isdigit() or int(row['span_end'])<=int(row['span_start']) or
                row['text_field'] not in ('unofficial_text_en','unofficial_text_fr') or
                not re.fullmatch(r'[A-Z][A-Z0-9]*_.+',row['target_decision_id']) or
                not re.fullmatch(r'[A-Z][A-Z0-9]*_.+',row['source_decision']) or
                row['source_court'] != row['source_decision'].split('_',1)[0] or
                row['source_corpus'] != 'corpus/'+row['source_court']+'.parquet' or
                not row['source_locator'].startswith('audit/findings/') or
                '..' in row['source_locator'].replace('\\','/').split('/') or
                len(proofs)<2 or len(proofs)!=len(set(proofs)) or
                any(not re.fullmatch(r'own:[0-9a-f]{64}',proof) for proof in proofs) or
                row['evidence_id']!=expected or pair in pairs or row['evidence_id'] in evidence_ids):
                raise ValueError('Identity separation has malformed, duplicate or corrupt provenance')
            facts.append(row)
            pairs.add(pair)
            evidence_ids.add(row['evidence_id'])
    return facts

def load_case_origin():
    """Load exact case-origin source rows without inferring missing facts."""
    path = os.path.join(DECISIONS, "case_origin.csv")
    if not os.path.exists(path):
        return {}
    idx = {}
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            k = (r.get("normalized_key") or "").strip()
            if k:
                idx.setdefault(k, []).append(r)
    return idx

def load_case_origin_manual():
    """Load only fully verified manual case-origin rows into the same source index."""
    path = os.path.join(DECISIONS, "case_origin_manual.csv")
    if not os.path.exists(path):
        return {}
    out = defaultdict(list)
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("status") or "").strip() not in CASE_ORIGIN_MANUAL_STATUS:
                continue
            k = (r.get("normalized_key") or "").strip()
            if k:
                out[k].append(r)
    return out

def load_scope():
    """Load source-verified court/reporter origin rules; estimated rows cannot supply facts."""
    path = os.path.join(DECISIONS, "court_or_reporter_scope.csv")
    if not os.path.exists(path):
        return {}
    idx = {}
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if not (r.get("verification_status") or "").startswith("verified"):
                continue
            k = nk(r.get("printed_key") or "")
            if k:
                idx.setdefault(k, []).append(r)
    return idx

def load_reporter_origin():
    """Load verified exclusive reporter-origin rules with their own volume/year windows."""
    path = os.path.join(DECISIONS, "reporter_origin_scope.csv")
    if not os.path.exists(path):
        return {}
    idx = {}
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            st = (r.get("verification_status") or "").strip()
            if st not in REPORTER_ORIGIN_ALLOWED_STATUSES:
                continue
            k = nk(r.get("printed_abbreviation") or "")
            if k:
                idx.setdefault(k, []).append(r)
    return idx

def year_of(merge_key):
    """Read the year slot of a neutral key or historical output."""
    head = merge_key.split("|", 1)[0]
    return int(head) if head.isdigit() else None

def row_year(row):
    """Use the printed year, falling back to the key year only when absent. Continuous-volume reporter keys deliberately omit their year slot."""
    v = (row.get("year_printed") or "").strip()
    if v.isdigit():
        return int(v)
    return year_of(row["merge_key"])

def row_key(r):
    """Keep each citing court and full merge key as a separate observation."""
    return "%s|%s" % (r["court"], r["merge_key"])

def key_occ(r):
    """Read the original key mention count, rather than an accumulated group count."""
    v = r.get("key_occurrence_count")
    return int(v) if v not in (None, "") else int(r["occurrence_count"])

def _neutral_parts(merge_key):
    p = merge_key.split("|")          # year|vol|abbr|series|page
    return p[0], p[2], p[3], p[4]

def load_identifier_systems():
    """Cache verified database/vendor identifier systems. Year-volume reporters retain reporter semantics."""
    global _IDENTIFIER_CACHE
    if _IDENTIFIER_CACHE is not None:
        return _IDENTIFIER_CACHE
    path = os.path.join(DECISIONS, "identifier_systems.csv")
    out = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("verification_status") or "").strip()\
                        not in ALLOWED_IDENTIFIER_STATUSES:
                    continue
                if (r.get("identifier_kind") or "").strip() not in (
                        "database_decision_id", "vendor_decision_id"):
                    continue
                tok = nk(r.get("printed_token") or "")
                sysname = (r.get("system_name") or "").strip()
                if tok and sysname:
                    out[tok] = sysname
    _IDENTIFIER_CACHE = out
    return out

def identifier_system_of(merge_key):
    """Read the verified identifier system for the exact key abbreviation slot."""
    p = merge_key.split("|")
    if len(p) < 3:
        return None
    return load_identifier_systems().get(nk(p[2]))

_BILINGUAL_REPORTER_CACHE = None


def load_bilingual_reporters():
    """PROBLEMS #139: verified French reporter titles -> English key part (rcs -> scr)."""
    global _BILINGUAL_REPORTER_CACHE
    if _BILINGUAL_REPORTER_CACHE is not None:
        return _BILINGUAL_REPORTER_CACHE
    path = os.path.join(DECISIONS, "bilingual_reporter_abbreviations.csv")
    out = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("verification_status") or "").strip() != "verified_corpus_metadata":
                    continue
                if not (r.get("source") and r.get("source_locator")):
                    raise ValueError("Bilingual reporter row lacks source")
                out[nk(r.get("abbreviation_fr") or "")] = nk(r.get("abbreviation_en") or "")
    _BILINGUAL_REPORTER_CACHE = out
    return out


def load_bilingual():
    """Cache only explicitly verified bilingual code equivalences, without direction."""
    global _BILINGUAL_CACHE
    if _BILINGUAL_CACHE is not None:
        return _BILINGUAL_CACHE
    path = os.path.join(DECISIONS, "bilingual_neutral_codes.csv")
    pairs = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("verification_status") or "").strip()\
                        not in ALLOWED_BILINGUAL_STATUSES:
                    continue
                a = nk(r.get("code_en") or "")
                b = nk(r.get("code_fr") or "")
                if a and b and a != b:
                    pairs.add(frozenset((a, b)))
    _BILINGUAL_CACHE = frozenset(pairs)
    return _BILINGUAL_CACHE

def parse_name_classes(raw):
    """Read printed name-class counts. Ignore malformed segments rather than inventing evidence."""
    out = {}
    for seg in (raw or "").split("|"):
        if ":" not in seg:
            continue
        n, _, cnt = seg.rpartition(":")
        if n and cnt.isdigit():
            out[n] = out.get(n, 0) + int(cnt)
    return out

def _self_of(m):
    return {x for x in (m.get("self_citation_of") or "").split("|") if x}

def load_registry(path):
    """Load exact registry key claims, retaining all document IDs and source courts in deterministic semicolon order. Registry claims authorize only the configured typo guard; they never become local self-citation roots."""
    idx = defaultdict(set)
    if path and (os.path.exists(path) or os.path.exists(path+'.gz')):
        with open_csv(path) as f:
            for r in csv.DictReader(f):
                k = r.get("merge_key") or ""
                did = r.get("decision_id") or ""
                if k and did:
                    idx[k].add((did, r.get("source_court") or ""))
    return {k: (";".join(sorted(d for d, _c in v)),
                ";".join(sorted({c for _d, c in v if c})))
            for k, v in idx.items()}

class OwnCitations(defaultdict):
    """Self-citation facts plus separately qualified, sealed document aliases."""
    def __init__(self):
        super().__init__(set)
        self.aliases = {}
        self.evidence = defaultdict(list)
        self.diagnostics = Counter()

def load_own_citations(path):
    """Load self-citation facts and separately qualified source-unique metadata/header document aliases. Legacy rows supply self-exclusion only, without changing local anchor eligibility or the typo guard."""
    idx = OwnCitations()
    qualified = defaultdict(list)
    if path and (os.path.exists(path) or os.path.exists(path+'.gz')):
        with open_csv(path) as f:
            for r in csv.DictReader(f):
                if r.get("merge_key") and r.get("decision_id"):
                    if r.get('evidence_id'):
                        expected = 'own:'+hashlib.sha256(json.dumps({k:str(v) for k,v in r.items() if k != 'evidence_id'},
                            ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
                        if r['evidence_id'] != expected:
                            raise ValueError('Own-citation evidence hash mismatch')
                    idx.diagnostics['claim_'+r.get('claim_status', 'legacy_self_only')] += 1
                    if r.get('claim_status', '').startswith('rejected_'):
                        continue
                    idx[r["merge_key"]].add(r["decision_id"])
                    idx.evidence[r['merge_key']].append(r)
                    if r.get('identity_qualified') == 'true':
                        required = ('corpus_sha256','field_sha256','text_sha256','header_raw_sha256','evidence_id','header_boundary')
                        if (r.get('claim_status') != 'qualified_metadata_header' or any(not r.get(k) for k in required)
                            or not r.get('corpus_row', '').isdigit() or not r.get('header_start', '').isdigit()
                            or not r.get('header_match_end', '').isdigit() or not r.get('header_end', '').isdigit()
                            or not 0 <= int(r['header_start']) < int(r['header_match_end']) <= int(r['header_end'])):
                            raise ValueError('Qualified document alias lacks complete header provenance')
                        qualified[r['merge_key']].append(r)
    for key, evidence in qualified.items():
        ids = {r['decision_id'] for r in evidence}
        # EN and FR header proofs may have different text hashes for one source.
        sources = {(r['source_court'],r['corpus_row'],r['corpus_sha256']) for r in evidence}
        if len(ids) == len(sources) == len(idx[key]) == 1:
            idx.aliases[key] = next(iter(ids))
        else:
            idx.diagnostics['ambiguous_qualified_alias_keys'] += 1
    return idx

def neutral_start(rows):
    """Collect each court's earliest self-printed neutral year and latest self-printed non-neutral year."""
    first, last = {}, {}
    for r in rows:
        p = r["merge_key"].split("|")
        if not p[0].isdigit():
            continue
        for d in _self_of(r):
            code = d.split("_", 1)[0].lower()
            if r.get("citation_kind") == "neutral":
                first[code] = min(first.get(code, 9999), int(p[0]))
            else:
                last[code] = max(last.get(code, 0), int(p[0]))
    return {c: (first.get(c, 9999), last[c]) for c in last}

def _before_start(k, start):
    """Require both missing neutral adoption and positive non-neutral printing evidence before demoting a historical neutral anchor."""
    p = k.split("|")
    if not start or not p[0].isdigit() or p[2] not in start:
        return False
    first, last = start[p[2]]
    return int(p[0]) < first and int(p[0]) <= last

def read_csv(path):
    with open_csv(path) as f:
        return list(csv.DictReader(f))

def load_decision_ids(path, court=None):
    """Read exact citing source IDs, with court scope on merge input rows."""
    idx = defaultdict(set)
    with open_csv(path) as f:
        for r in csv.DictReader(f):
            k = r["row_key"] if "row_key" in r else "%s|%s" % (court, r["merge_key"])
            idx[k].add(r["source_decision_citation"])
    return idx

def _court_nk(value):
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())

class CourtEvidence:
    def __init__(self, decisions=Path(DECISIONS)):
        decisions = Path(decisions)
        self.parent = {}
        self.known = set()
        self.scope = defaultdict(list)
        self.exact = defaultdict(list)
        for r in self.read(decisions / "neutral_court_codes.csv"):
            code = _court_nk(r.get("court_code"))
            if code and r.get("source") and r.get("source_locator"):
                self.known.add(code)
                self.find(code)
        # A recognized printed designation is an explicit alias of its canonical
        # court, rather than a generic prefix or a name similarity heuristic.
        for r in self.read(decisions / "court_designations.csv"):
            if r.get("status") == "recognized" and r.get("canonical_court"):
                self.union(_court_nk(r.get("normalized_key")), _court_nk(r["canonical_court"]))
        for r in self.read(decisions / "bilingual_neutral_codes.csv"):
            if r.get("verification_status") == "verified_explicit_equivalence":
                self.union(_court_nk(r.get("code_en")), _court_nk(r.get("code_fr")))
        # A designation reaches a court code only through an explicit sourced
        # row. Matching normalized strings (B.C.C.A. = BCCA) is a coincidence
        # that leaves Ont.C.A. and P.C. without any court token.
        for r in self.read(decisions / "court_designation_codes.csv"):
            if r.get("verification_status") != "verified_official_source":
                continue
            code = _court_nk(r.get("court_code"))
            if not (r.get("source") and r.get("source_locator")) or code not in self.known:
                raise ValueError("Court designation code row lacks a source or a known court code")
            self.union(_court_nk(r.get("normalized_key")), code)
        components = defaultdict(set)
        for code in self.known:
            components[self.find(code)].add(code)
        self.tokens = {}
        for alias in list(self.parent):
            known = components.get(self.find(alias))
            if known:
                self.tokens[alias] = "court:" + min(known)
        for r in self.read(decisions / "identity_court_scope.csv"):
            # PROBLEMS #141: a print-evidence row names a leave-only SCC reporter.
            if r.get("verification_status") in ("verified_existing_statute", "verified_print_evidence"):
                self.scope[(r.get("citation_kind"), _court_nk(r.get("printed_key")))].append(r)
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
                _court_nk(r['canonical_court']) not in self.tokens):
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
        code = _court_nk(parts[2]) if len(parts) >= 3 else ""
        kind = row.get("citation_kind", "")
        for fact in self.exact.get(row['merge_key'], []):
            token = self.tokens[_court_nk(fact['canonical_court'])]
            evidence[token].add('verified_corpus_court:'+fact['evidence_id'])
        if kind == "neutral" and not before_start and code in self.known:
            evidence[self.tokens[code]].add("neutral_code:" + code)
        observed = row.get("observed_deciding_court") or ""
        if row.get("court_designation_conflict") not in ("true", True):
            token = self.tokens.get(_court_nk(observed))
            if token:
                evidence[token].add("printed_court:" + observed)
        year = row.get("year_printed") or (parts[0] if parts else "")
        if str(year).isdigit():
            year = int(year)
            for rule in self.scope.get((kind, code), []):
                lower, upper = rule.get("year_start"), rule.get("year_end")
                if lower and year < int(lower) or upper and year > int(upper):
                    continue
                token = self.tokens.get(_court_nk(rule["canonical_court"]))
                if token:
                    evidence[token].add("exclusive_court_scope:" + rule["printed_key"])
        return dict(evidence)

FACT_FIELDS = ('evidence_id', 'scope', 'court', 'row_key', 'merge_key',
               'fact_kind', 'value_json', 'sources_json')

def canonical_json(value):
    """Serialize source facts deterministically without changing their values."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def fact_id(payload):
    return 'fact:' + hashlib.sha256(canonical_json(payload).encode('utf-8')).hexdigest()

class EvidenceSnapshot:
    """Immutable scoped observations taken before solver annotations mutate rows."""
    ROW_FIELDS = ('citation_kind', 'case_name_modal', 'year_printed', 'name_classes',
                  'self_citation_of', 'self_case_name', 'jurisdiction',
                  'observed_deciding_court', 'court_designation_conflict',
                  'identity_court_conflict', 'identity_court_evidence',
                  'document_alias_holdout_doc_ids', 'document_alias_holdout_evidence_ids',
                  'identity_separation_evidence_ids', 'key_occurrence_count',
                  'occurrence_count', 'canonical_string')
    POLICY_FILES = ('identifier_systems.csv', 'bilingual_neutral_codes.csv',
                    'neutral_court_codes.csv', 'court_designations.csv',
                    'court_designation_codes.csv', 'court_designation_reporter_scope.csv',
                    'identity_court_scope.csv', 'identity_court_facts.csv',
                    'identity_separations.csv', 'bilingual_reporter_abbreviations.csv',
                    'reporter_identity_court_sets.csv')

    def __init__(self, rows, did_idx, scope, registry=None, own_cites=None,
                 separations=None, history=None, pair_separations=None):
        self.scope, self.records = scope, []
        self.evidence_ids = set()
        self.qualified_native_facts = defaultdict(set)
        self.qualified_aliases = dict(getattr(own_cites, 'aliases', {}))
        self.qualified_proofs = defaultdict(set)
        self.by_row, self.by_key = defaultdict(set), defaultdict(set)
        self.policy_ids = set()
        self.policy_records = []
        self.policy_candidates = defaultdict(list)
        self.policy_exact = defaultdict(list)
        self.policy_cache = {}
        self.history_facts_by_instance = {}
        self.bilingual_reporter_facts = {}
        self.pair_cannot_links = []
        self.reporter_scope_by_row = {}
        for row in rows:
            key = row_key(row)
            self.add(row.get('court', ''), key, row['merge_key'], 'row_observation',
                     {name: row.get(name, '') for name in self.ROW_FIELDS},
                     {'input_row_key': key, 'source_decision_ids': sorted(did_idx.get(key, ()))})
        for key, value in sorted((registry or {}).items()):
            self.add('', '', key, 'registry_claim', value,
                     {'artifact': 'registry/decision_registry.csv', 'merge_key': key})
        for key, values in sorted(getattr(own_cites, 'evidence', {}).items()):
            for proof in sorted(values, key=canonical_json):
                if proof.get('identity_qualified') == 'true' and proof.get('evidence_id'):
                    self.qualified_proofs[(key, proof['decision_id'])].add(proof['evidence_id'])
                proof_fact = self.add('', '', key, 'own_citation_proof', proof,
                         {'artifact': 'registry/decision_own_citations.csv',
                          'native_evidence_id': proof.get('evidence_id', '')})
                if proof.get('identity_qualified') == 'true' and proof.get('evidence_id'):
                    self.qualified_native_facts[(proof['decision_id'], proof['evidence_id'])].add(proof_fact)
        for index, proof in enumerate(separations or ()):
            self.add('', '', proof['merge_key'], 'reviewed_separation', proof,
                     {'artifact': 'decisions/identity_separations.csv', 'record': index + 2})
        for name in self.POLICY_FILES:
            path = Path(DECISIONS) / name
            if not path.is_file():
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with path.open(encoding='utf-8-sig', newline='') as source:
                for index, policy in enumerate(csv.DictReader(source), 2):
                    eid = self.add('', '', policy.get('merge_key', ''), 'policy_record', policy,
                                   {'artifact': 'decisions/' + name, 'record': index,
                                    'sha256': digest})
                    self.policy_ids.add(eid)
                    self.policy_records.append((eid, name, policy))
                    if name == 'bilingual_reporter_abbreviations.csv' and (policy.get('verification_status') or '').strip() == 'verified_corpus_metadata':
                        alias = nk(policy.get('normalized_fr') or '')
                        target = nk(policy.get('normalized_en') or '')
                        if not alias or not target or alias == target:
                            raise ValueError('Verified bilingual reporter policy has invalid normalized keys')
                        if nk(policy.get('abbreviation_fr') or '') != alias or nk(policy.get('abbreviation_en') or '') != target:
                            raise ValueError('Bilingual reporter policy normalized keys do not match printed abbreviations')
                        if not (policy.get('source') and policy.get('source_locator')):
                            raise ValueError('Verified bilingual reporter policy lacks a source locator')
                        prior = self.bilingual_reporter_facts.get(alias)
                        if prior and prior['target'] != target:
                            raise ValueError('Conflicting verified bilingual reporter mappings')
                        self.bilingual_reporter_facts[alias] = {'target': target, 'evidence_id': eid, 'record': policy}
        for record in self.policy_records:
            eid, name, policy = record
            if policy.get('merge_key'):
                self.policy_exact[policy['merge_key']].append(record)
            else:
                for code in {nk(policy.get(field) or '') for field in
                             ('printed_token', 'code_en', 'code_fr', 'court_code',
                              'normalized_key', 'canonical_court', 'printed_key')} - {''}:
                    self.policy_candidates[code].append(record)
        self._add_history_facts(history or {})
        self._add_pair_separation_facts(pair_separations or ())
        from identity_courts import CourtEvidence
        courts = CourtEvidence()
        from reporter_identity_scope import load_scope_rules, scope_evidence, allowed_courts
        scope_rules = load_scope_rules()
        scope_policy_ids = {policy.get('rule_id'): eid
                            for eid, name, policy in self.policy_records
                            if name == 'reporter_identity_court_sets.csv'}
        starts = neutral_start(rows)
        for row in rows:
            scopes = scope_evidence(row, scope_rules, court_tokens=courts.tokens)
            scope_fact_ids = []
            for scope_fact in scopes:
                policy_eid = scope_policy_ids.get(scope_fact['rule_id'])
                if not policy_eid:
                    raise ValueError('Reporter court envelope lacks its exact policy snapshot fact')
                scope_value = dict(scope_fact, policy_evidence_id=policy_eid)
                scope_fact_ids.append(self.add(
                    row.get('court', ''), row_key(row), row['merge_key'],
                    'reporter_identity_court_envelope', scope_value,
                    {'artifact': scope_fact['source_locator'].split('#', 1)[0],
                     'rule_id': scope_fact['rule_id'],
                     'policy_evidence_id': policy_eid,
                     'evidence_sha256': scope_fact['evidence_sha256']}))
            self.reporter_scope_by_row[row_key(row)] = {
                'allowed_courts': sorted(allowed_courts(
                    row, scope_rules, court_tokens=courts.tokens)),
                'evidence_ids': sorted(scope_fact_ids)}
            found = courts.evidence(row, before_start=(not _self_of(row) and
                                    _before_start(row['merge_key'], starts)))
            self.add(row.get('court', ''), row_key(row), row['merge_key'],
                     'court_observation', {token: sorted(ids) for token, ids in found.items()},
                     {'input_row_key': row_key(row), 'phase': 'cluster',
                      'policy_evidence_ids': self.applicable_policies(row, 'court')})
            alias_found = courts.evidence(row)
            if alias_found != found:
                self.add(row.get('court', ''), row_key(row), row['merge_key'],
                         'court_observation', {token: sorted(ids) for token, ids in alias_found.items()},
                         {'input_row_key': row_key(row), 'phase': 'document_alias',
                          'policy_evidence_ids': self.applicable_policies(row, 'court')})

    def reporter_scope_info(self, row):
        return self.reporter_scope_by_row.get(
            row_key(row), {'allowed_courts': [], 'evidence_ids': []})

    def add(self, court, key, merge_key, kind, value, sources):
        payload = {'scope': self.scope, 'court': court, 'row_key': key,
                   'merge_key': merge_key, 'fact_kind': kind,
                   'value_json': canonical_json(value), 'sources_json': canonical_json(sources)}
        eid = fact_id(payload)
        self.records.append({'evidence_id': eid, **payload})
        self.evidence_ids.add(eid)
        if key:
            self.by_row[key].add(eid)
        if merge_key and not key:
            self.by_key[merge_key].add(eid)
        return eid

    def bilingual_reporter_fact(self, alias, target):
        mapping = self.bilingual_reporter_facts.get(nk(alias))
        if not mapping or mapping['target'] != nk(target):
            raise ValueError('Bilingual reporter normalization lacks the exact verified policy fact')
        return mapping['evidence_id']

    def _add_history_facts(self, history):
        expected_fields = {'source_decision_citation', 'corpus_row_index', 'instance',
                           'side', 'merge_key', 'candidate_id', 'connector',
                           'connector_sha256', 'source_locator'}
        source_hashes = {}
        source_rows = {}
        for instance, record in sorted(history.items()):
            before = set(record.get('before', ()))
            after = set(record.get('after', ()))
            rows = record.get('records') or ()
            if not before or not after or before & after or not rows:
                raise ValueError('History instance lacks a complete, non-overlapping provenance record')
            observed = {'before': set(), 'after': set()}
            fact_ids = []
            for item in rows:
                if not expected_fields <= set(item):
                    raise ValueError('History provenance record is missing required fields')
                if item['instance'] != instance or item['side'] not in observed:
                    raise ValueError('History provenance record is bound to the wrong instance or side')
                if not item['source_decision_citation'] or not item['candidate_id'] or not item['merge_key'] or not item['connector']:
                    raise ValueError('History provenance record has an empty source, candidate, key, or connector')
                locator = item['source_locator']
                if (not isinstance(locator, dict) or not locator.get('artifact')
                        or not locator.get('resolved_artifact') or not locator.get('record')):
                    raise ValueError('History provenance record lacks a verifiable source locator')
                if not isinstance(locator.get('sha256'), str) or len(locator['sha256']) != 64:
                    raise ValueError('History source locator lacks a SHA-256 digest')
                if locator.get('hash_scope') != 'logical_csv_bytes':
                    raise ValueError('History source locator must hash logical CSV bytes')
                artifact = locator['resolved_artifact']
                logical_artifact = locator['artifact']
                if not isinstance(logical_artifact, str) or not isinstance(artifact, str):
                    raise ValueError('History source locator paths must be strings')
                if logical_artifact not in source_hashes:
                    source_hashes[logical_artifact] = sha256_logical_csv_bytes(logical_artifact)
                if source_hashes[logical_artifact] != locator['sha256']:
                    raise ValueError('History source artifact changed after it was loaded')
                try:
                    source_record_no = int(locator['record'])
                except (TypeError, ValueError):
                    raise ValueError('History source locator record is not an integer')
                if source_record_no < 2:
                    raise ValueError('History source locator record must identify a data row')
                if logical_artifact not in source_rows:
                    with open_csv(logical_artifact) as stream:
                        reader = csv.DictReader(stream, strict=True)
                        source_rows[logical_artifact] = {
                            record_no: source_row
                            for record_no, source_row in enumerate(reader, start=2)
                        }
                source_record = source_rows[logical_artifact].get(source_record_no)
                if source_record is None or None in source_record:
                    raise ValueError('History source locator does not identify a complete CSV row')
                for field in ('source_decision_citation', 'corpus_row_index', 'instance',
                              'side', 'merge_key', 'candidate_id'):
                    if (source_record.get(field) or '').strip() != item[field]:
                        raise ValueError('History source locator is bound to a different source row')
                if (source_record.get('connector') or '') != item['connector']:
                    raise ValueError('History connector differs from its located source row')
                connector_hash = hashlib.sha256(item['connector'].encode('utf-8')).hexdigest()
                if connector_hash != item['connector_sha256']:
                    raise ValueError('History connector hash does not match its value')
                observed[item['side']].add(item['merge_key'])
                payload = {field: item[field] for field in sorted(expected_fields)}
                fact_ids.append(self.add('', '', item['merge_key'], 'appeal_history_instance', payload, locator))
            if observed != {'before': before, 'after': after}:
                raise ValueError('History evidence records do not bind to the declared before/after keys')
            if len({(r['source_decision_citation'], r['corpus_row_index'], r['connector'], r['connector_sha256']) for r in rows}) != 1:
                raise ValueError('History instance mixes source documents or connector values')
            supplied = record.get('evidence_ids')
            if supplied is not None and set(supplied) != set(fact_ids):
                raise ValueError('History instance evidence IDs do not match immutable source facts')
            self.history_facts_by_instance[instance] = tuple(sorted(fact_ids))

    def _add_pair_separation_facts(self, separations):
        seen = set()
        for separation in separations:
            left = separation.get('left_merge_key')
            right = separation.get('right_merge_key')
            relation_type = separation.get('relation_type')
            table_evidence_id = separation.get('table_evidence_id')
            source_detail = separation.get('source_detail')
            if not left or not right or left == right or not relation_type:
                raise ValueError('Verified pair separation has invalid keys or relation type')
            if not table_evidence_id or not isinstance(source_detail, dict) or not source_detail:
                raise ValueError('Verified pair separation lacks native evidence provenance')
            from identity_pairs import evidence_id as pair_table_evidence_id
            table_record = {k: v for k, v in separation.items()
                            if k not in ('table_evidence_id', 'source_detail')}
            if (separation.get('evidence_id') != table_evidence_id
                    or pair_table_evidence_id(table_record) != table_evidence_id):
                raise ValueError('Verified pair separation changed after native source validation')
            try:
                table_right_source = json.loads(separation['right_proof_json'])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError('Verified pair separation has an invalid table-bound right source proof') from exc
            expected_source = {'artifact': 'decisions/identity_pair_separations.csv',
                               'table_evidence_id': table_evidence_id,
                               'source_corpus': separation.get('source_corpus'),
                               'corpus_row': separation.get('corpus_row'),
                               'source_decision': separation.get('source_decision'),
                               'text_field': separation.get('text_field'),
                               'span_start': separation.get('span_start'),
                               'span_end': separation.get('span_end'),
                               'span_sha256': separation.get('span_sha256'),
                               'right_source': table_right_source,
                               'source_locator': separation.get('source_locator')}
            if source_detail != expected_source:
                raise ValueError('Verified pair separation source detail is misbound')
            signature = (left, right, relation_type, table_evidence_id)
            if signature in seen:
                continue
            seen.add(signature)
            value = dict(separation)
            eid = self.add('', '', left, 'verified_pair_separation', value, source_detail)
            self.pair_cannot_links.append({
                'left_merge_key': left, 'right_merge_key': right,
                'relation_type': relation_type, 'evidence_id': eid,
                'source_detail': source_detail, 'table_evidence_id': table_evidence_id})

    def history_instance_facts(self, instance):
        facts = self.history_facts_by_instance.get(instance)
        if not facts:
            raise ValueError('History constraint references an instance without snapshot facts')
        return facts

    def native_proof_facts(self, decision_id, native_evidence_ids):
        """Resolve every native proof only within its exact qualified document."""
        requested = set(native_evidence_ids)
        if not decision_id or not requested:
            raise ValueError('Target document and complete native proof IDs are required')
        facts = set()
        for native_id in sorted(requested):
            exact = self.qualified_native_facts.get((decision_id, native_id))
            if not exact:
                raise ValueError('Target native proof is missing, unqualified or bound to another document')
            facts.update(exact)
        return sorted(facts)

    def applicable_policies(self, row, rule):
        parts = row['merge_key'].split('|')
        code = nk(parts[2]) if len(parts) > 2 else ''
        observed = nk(row.get('observed_deciding_court') or '')
        year = row_year(row)
        cache_key = (row['merge_key'], row.get('citation_kind'), observed, year)
        if cache_key in self.policy_cache:
            return self.policy_cache[cache_key]
        result = []
        candidates = self.policy_candidates.get(code, []) + self.policy_candidates.get(observed, []) + self.policy_exact.get(row['merge_key'], [])
        for eid, name, policy in candidates:
            applies = False
            if name == 'identifier_systems.csv':
                applies = nk(policy.get('printed_token') or '') == code
            elif name == 'bilingual_neutral_codes.csv':
                applies = code in (nk(policy.get('code_en') or ''), nk(policy.get('code_fr') or ''))
            elif name == 'neutral_court_codes.csv':
                applies = code == nk(policy.get('court_code') or '')
            elif name in ('court_designations.csv', 'court_designation_codes.csv',
                          'court_designation_reporter_scope.csv'):
                applies = bool(observed) and observed in (
                    nk(policy.get('normalized_key') or ''), nk(policy.get('canonical_court') or ''))
            elif name == 'identity_court_scope.csv':
                lower, upper = policy.get('year_start'), policy.get('year_end')
                applies = (row.get('citation_kind') == policy.get('citation_kind') and
                    code == nk(policy.get('printed_key') or '') and year is not None and
                    not (lower and year < int(lower) or upper and year > int(upper)))
            else:
                applies = policy.get('merge_key') == row['merge_key']
            if applies:
                result.append(eid)
        self.policy_cache[cache_key] = sorted(set(result))
        return self.policy_cache[cache_key]

    def refs(self, members, rule=''):

        """Return observed evidence for these exact rows and their source claims."""
        ids = set()
        for member in members:
            ids.update(self.by_row.get(row_key(member), ()))
            ids.update(self.by_key.get(member['merge_key'], ()))
            ids.update(self.applicable_policies(member, rule))
        return sorted(ids)

