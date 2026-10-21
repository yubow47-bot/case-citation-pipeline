"""jev_nodes.py — question builders and adoption rules for the eight Jev nodes.

method card 09, §3 of implementation/plan_jev_ab_20261020.md. Every option is
generated here from source text, rows or the registry; Jev only chooses. Each
builder returns None when the item is out of scope, so the selection rule lives
in code and is counted. Adoption follows the level/tier table:

  N8 source date      L1  T1  same provider year required; else L0 conflict flag
  N1 kept -> not case L2  T1  conservative
  N1 lexical reject -> case  L2  T2  assertive; only lexical rule families
  N2 case name        L1  T1  option must survive admit_candidate
  N5 name owner       L0 when equal to the rule name, else L2 T2
  N3 suffix meaning   L0  label only
  N6 identity         L2  T2  heuristic member -> model_confirmed (support only)
  N7 same ruling      L1  T1  (distinct -> L0 mark, never a split)
  N4 case history     L1  T1  same court, or a lower court in court_hierarchy.csv
"""
import csv
import hashlib
import os
import re
from pathlib import Path

import jev_client as jc

ROOT = Path(__file__).resolve().parents[1]
MARK_L, MARK_R = "⟦", "⟧"  # ⟦ ⟧

# ---------------------------------------------------------------- text windows

def window(text, start, end, left=400, right=200, limit=None):
    """Source text around [start, end) with the target marked by ⟦ ⟧."""
    a, b = max(0, start - left), min(len(text), end + right)
    out = (("..." if a else "") + text[a:start] + MARK_L + text[start:end] + MARK_R
           + text[end:b] + ("..." if b < len(text) else ""))
    if limit and len(out) > limit:
        out = out[-limit:]
    return out


def option_index(choice, prefix, n):
    """Zero-based index for a generated option label such as o3/n2/D1; None otherwise.

    Abstaining labels (none, no_name_here) share first letters with the option
    prefixes, so a strict pattern is required.
    """
    m = re.fullmatch(re.escape(prefix) + r"([1-9]\d*)", choice or "")
    if not m or int(m.group(1)) > n:
        return None
    return int(m.group(1)) - 1


def is_english(text_field):
    return not (text_field or "").endswith("_fr")


def audit_pick(key, rate):
    """Deterministic audit sample: the same rows are picked in every run."""
    if rate <= 0:
        return False
    h = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)
    return h < rate * 0xFFFFFFFF


# ------------------------------------------------------------- N1 candidate type
# #111: rejected_reason mixes "not a citation" with "a citation we do not count".
NOT_CITATION_REASONS = {"date_form", "abbreviated_date_form", "non_citation_word",
                        "versus_as_page", "party_initials", "docket_not_decision",
                        "federal_statute", "not_a_decision"}
# Lexical rule families: word lists and calendar shapes, the only rejections Jev may reverse.
LEXICAL_REASONS = {"date_form", "abbreviated_date_form", "non_citation_word",
                   "versus_as_page", "party_initials"}
N1_OPTIONS = {
    "case_citation": "A citation to a court or tribunal decision: a law report volume and page, a neutral citation, or an online database number",
    "case_citation_bad_span": "Part of a case citation, but the marked span cuts it off or includes extra words",
    "legislation": "A statute, regulation or rule",
    "secondary_source": "A journal article, book or other commentary",
    "date": "A calendar date or time",
    "docket_or_file_number": "A court docket, file or registry number",
    "internal_reference": "A paragraph, page, tab, exhibit or table-of-contents reference",
    "other": "Something else, such as an amount, address or account number",
}
N1_NOT_CASE = {"legislation", "secondary_source", "date", "docket_or_file_number",
               "internal_reference", "other"}


def reason_parts(value):
    return [p for p in (value or "").split("|") if p]


def row_status(rejected_reason):
    parts = reason_parts(rejected_reason)
    if not parts:
        return "citation_counted"
    if any(p in NOT_CITATION_REASONS or p.startswith("non_case_") for p in parts):
        return "not_citation"
    return "citation_uncounted"


def n1_scope(row, audit_rate, readmit=False, lexical_audit_rate=0.0):
    """Return (mode, level) or None. mode: readmit | reject | audit.

    Reversing a lexical rejection (readmit) is off by default: on BCCA+BCSC it
    asked 3,627 questions and reversed none. A small fixed sample of lexical
    rejections is audited instead, so a rule false-rejection rate stays measurable.
    """
    parts = reason_parts(row.get("rejected_reason"))
    cid = row["candidate_id"]
    if parts and all(p in LEXICAL_REASONS for p in parts):
        if readmit:
            return "readmit", "L2"
        return ("audit", "L0") if audit_pick("N1L|" + cid, lexical_audit_rate) else None
    if parts:
        return None
    if (row.get("jurisdiction") == "UNSUPPORTED" and not row.get("year_vol_ambiguity")
            and row.get("self_citation") != "true"):
        return "reject", "L2"
    return ("audit", "L0") if audit_pick("N1|" + cid, audit_rate) else None


def n1_question(with_agreement=False):
    """The agreement Noul is only needed at tier T2 (readmit and overlap confirmation)."""
    qs = {"candidate_type": jc.choice_question(
        "In this court judgment, what is the text inside ⟦ ⟧?", N1_OPTIONS)}
    if with_agreement:
        qs["is_case_citation"] = jc.noul_question(
            "The text inside ⟦ ⟧ is a citation to a court or tribunal decision.")
    return qs


def n1_decide(cfg, mode, response):
    answers = (response or {}).get("answers") or {}
    ans = answers.get("candidate_type")
    noul = (answers.get("is_case_citation") or {}).get("noul")
    choice = (ans or {}).get("choice")
    if mode == "audit":
        return "reject", "audit_only", choice
    if mode == "readmit":
        if choice != "case_citation":
            return "reject", "not_case_citation", choice
        if not jc.level_allowed(cfg, "L2"):
            return "reject", "level_disabled", choice
        d, why = jc.gate(cfg, "T2", ans, noul=noul)
        return d, why, choice
    if choice not in N1_NOT_CASE:
        return "reject", "is_or_part_of_case_citation", choice
    if not jc.level_allowed(cfg, "L2"):
        return "reject", "level_disabled", choice
    d, why = jc.gate(cfg, "T1", ans)
    return d, why, choice


# ----------------------------------------------------------------- N2 case name
_CAP_START = re.compile(r"(?:(?<=\s)|(?<=^)|(?<=[(\"'“‘]))(?:[A-ZÀ-Þ]|\d{6,}\s)")
_BOUNDARY = re.compile(r"[;:\n]|\.\s+(?=[A-Z][a-z]+\s)(?<!\bv\.\s)")


def _name_region(text, start, span=250):
    pre = text[max(0, start - span):start]
    # stop at the last hard boundary (semicolon, colon, line break)
    cut = max(pre.rfind(";"), pre.rfind(":"), pre.rfind("\n"))
    return pre[cut + 1:] if cut >= 0 else pre


def follows_citation(preceding):
    """A citation printed right after another citation is a parallel: it has no own name."""
    tail = (preceding or "").rstrip(" ,; ")
    return bool(tail) and (tail[-1].isdigit() or tail[-1] in ")]")


def n2_options(text, start, limit=12):
    region = _name_region(text, start)
    seen, opts = set(), []
    for m in _CAP_START.finditer(region):
        cand = region[m.start():].strip().rstrip(",;").strip()
        if 3 <= len(cand) <= 160 and cand not in seen:
            seen.add(cand)
            opts.append(cand)
    return opts[-limit:]  # the shortest candidates sit closest to the citation


def n2_scope(row):
    reasons = reason_parts(row.get("name_rejected_reason"))
    if row.get("rejected_reason") or row.get("self_citation") == "true":
        return None
    if not ({"no_separator_before_v", "no_v_structure"} & set(reasons)):
        return None
    if follows_citation(row.get("preceding_text")):
        return "parallel_after_citation"
    return "ask"


def n2_question(options):
    crit = {"o%d" % (i + 1): o for i, o in enumerate(options)}
    crit["no_name_here"] = ("No case name for this citation appears immediately before it "
                            "(e.g. a second parallel citation, a self-citation header or a bare reference)")
    return {"case_name": jc.choice_question(
        "Which option is exactly the case name (style of cause) of the decision cited in "
        "⟦ ⟧, with no surrounding prose?", crit)}


# ------------------------------------------------------------------ N5 owner
_NAME_IN_SEGMENT = re.compile(
    r"((?:[A-ZÀ-Þ][\w.'&’()-]*\s+){0,8}?[\w.'&’()-]*\s*\bv\.\s+[^,;\[\(\n]{1,120})")


def n5_names(text, start, span=400):
    pre = text[max(0, start - span):start]
    cut = pre.rfind("\n")
    pre = pre[cut + 1:] if cut >= 0 else pre
    if pre.count(";") < 1:
        return []
    names = []
    for m in _NAME_IN_SEGMENT.finditer(pre):
        n = m.group(1).strip().rstrip(",").strip()
        if n and n not in names:
            names.append(n)
    return names if len(names) >= 2 else []


def n5_question(names, current):
    crit = {"n%d" % (i + 1): n for i, n in enumerate(names)}
    crit["none"] = "None of these names belongs to the citation in ⟦ ⟧"
    qs = {"owner": jc.choice_question(
        "Which case name does the citation in ⟦ ⟧ belong to?", crit)}
    return qs


def n5_agreement(name):
    return {"owner_agrees": jc.noul_question(
        "The case name “%s” is the name of the decision cited in ⟦ ⟧." % name)}


# ------------------------------------------------------------- N3 suffix meaning
N3_OPTIONS = {
    "affirmed": "It was affirmed on appeal",
    "reversed_or_varied": "It was reversed, set aside or varied on appeal",
    "leave_refused": "Leave to appeal from it was refused",
    "leave_granted": "Leave to appeal from it was granted",
    "decision_maker": "It names the judge or panel, e.g. a chambers judge",
    "court_designation": "It names the court that decided it",
    "translation_or_version": "It describes a translation or version of the text",
    "other": "Something else",
}


def n3_questions(suffixes):
    return {"suffix_%d" % i: jc.choice_question(
        "What does the note “%s” printed with the citation in ⟦ ⟧ say about that cited decision?"
        % s, N3_OPTIONS) for i, s in enumerate(suffixes)}


# --------------------------------------------------------------- N8 source date
MONTHS = ("January|February|March|April|May|June|July|August|September|October|"
          "November|December|Jan\\.?|Feb\\.?|Mar\\.?|Apr\\.?|Jun\\.?|Jul\\.?|Aug\\.?|"
          "Sept?\\.?|Oct\\.?|Nov\\.?|Dec\\.?")
_MONTH_NO = {m[:3].lower(): i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
DATE_PATTERNS = [
    re.compile(r"\b(?P<y>1[89]\d\d|20\d\d)\s*:\s*(?P<m>%s)\s+(?P<d>\d{1,2})\b" % MONTHS),
    re.compile(r"\b(?P<m>%s)\s+(?P<d>\d{1,2}),?\s+(?P<y>1[89]\d\d|20\d\d)\b" % MONTHS),
    re.compile(r"\b(?P<d>\d{1,2})\s+(?P<m>%s)\s+(?P<y>1[89]\d\d|20\d\d)\b" % MONTHS),
    re.compile(r"\b(?P<y>1[89]\d\d|20\d\d)-(?P<mn>\d\d)-(?P<d>\d\d)\b"),
    re.compile(r"\bDate:\s*(?P<y>(?:19|20)\d\d)(?P<mn>\d\d)(?P<d>\d\d)\b"),
]


def header_dates(header, limit=12):
    """Every calendar date printed in the header, with its span (structural only)."""
    import datetime as dt
    found = {}
    for pat in DATE_PATTERNS:
        for m in pat.finditer(header):
            g = m.groupdict()
            month = int(g["mn"]) if g.get("mn") else _MONTH_NO.get(g["m"][:3].lower())
            try:
                day = dt.date(int(g["y"]), month, int(g["d"]))
            except (TypeError, ValueError):
                continue
            found.setdefault(m.start(), (m.start(), m.end(), day.isoformat()))
    spans, last_end = [], -1
    for s, e, iso in sorted(found.values()):  # drop overlaps (keep the earlier match)
        if s >= last_end:
            spans.append((s, e, iso))
            last_end = e
    # One option per distinct date: repeated printings must not split the probability.
    by_iso = {}
    for s, e, iso in spans:
        by_iso.setdefault(iso, []).append((s, e))
    return [(iso, places) for iso, places in by_iso.items()][:limit]


def n8_state(header, dates):
    label = {}
    for i, (_, places) in enumerate(dates, 1):
        for s, e in places:
            label[s] = (e, "D%d" % i)
    pieces, pos = [], 0
    for s in sorted(label):
        e, tag = label[s]
        pieces.append(header[pos:s] + "[%s] " % tag + header[s:e])
        pos = e
    pieces.append(header[pos:])
    return "".join(pieces)


def n8_question(dates):
    crit = {"D%d" % i: iso for i, (iso, _) in enumerate(dates, 1)}
    crit["none"] = "None of the marked dates is the date the judgment was delivered"
    return {"judgment_date": jc.choice_question(
        "Which marked date is the date this judgment was delivered (not a hearing, filing or publication date)?",
        crit)}


# ---------------------------------------------------------------- N6 identity
def n6_questions():
    return {
        "identity": jc.choice_question(
            "Does the citation described in `member` refer to the judgment described in `group_judgment`?",
            {"same_judgment": "Yes, the same judgment (possibly reported in a different place)",
             "different_judgment": "No, a different judgment (another case, or another decision in the same case)",
             "cannot_tell": "The information does not allow a determination"}),
        "identity_agrees": jc.noul_question(
            "`member` and `group_judgment` describe the same judgment."),
    }


# ----------------------------------------------------------------- N7 ruling
def n7_question():
    return {"same_ruling": jc.choice_question(
        "Do group A and group B cite the same judgment?",
        {"same_judgment": "The same judgment, reported in different places",
         "different_levels_same_case": "Different judgments in the same litigation, e.g. trial and appeal",
         "different_cases": "Different cases that happen to share a name",
         "cannot_tell": "The information does not allow a determination"})}


# ----------------------------------------------------------------- N4 history
N4_OPTIONS = {
    "under_appeal_or_earlier_in_this_case": "It is the decision under appeal, or an earlier ruling in this same proceeding (trial, motion, voir dire, prior appeal, leave decision)",
    "related_proceeding": "It is a separate but related proceeding between the same or overlapping parties",
    "precedent": "It is another case cited as authority or for comparison",
    "cannot_tell": "The text does not allow a determination",
}


def n4_questions():
    return {
        "relation": jc.choice_question(
            "How does the citing decision relate to the decision cited in ⟦ ⟧?", N4_OPTIONS),
        "explicitly_stated": jc.noul_question(
            "The passage explicitly says the cited decision is the one under appeal or an earlier ruling in this same case."),
    }


def court_canonicalizer(path=None):
    """Map a neutral court code to the decide-layer court id (CSC for SCC, CAF for FCA ...).

    Only verified bilingual equivalences are used; the first column is the id that
    group_deciding_court carries (court:csc, court:caf, court:cf, court:cci).
    """
    path = Path(path or ROOT / "decisions" / "bilingual_neutral_codes.csv")
    alias = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("verification_status") or "").startswith("verified"):
                alias[r["code_fr"].strip().upper()] = r["code_en"].strip().upper()

    def canon(code):
        code = (code or "").strip().upper()
        return alias.get(code, code)
    return canon


def load_court_hierarchy(path=None):
    """{(higher, lower)} with transitive closure. Rows without a source are refused (constraint 8)."""
    path = Path(path or ROOT / "decisions" / "court_hierarchy.csv")
    canon = court_canonicalizer()
    edges = set()
    if not path.exists():
        return edges
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if not (r.get("source") or "").strip() or not (r.get("source_locator") or "").strip():
                raise ValueError("court_hierarchy.csv row without source: %r" % r)
            edges.add((canon(r["higher_court"]), canon(r["lower_court"])))
    changed = True
    while changed:
        changed = False
        for a, b in list(edges):
            for c, d in list(edges):
                if b == c and (a, d) not in edges:
                    edges.add((a, d))
                    changed = True
    return edges


def history_eligible(citing_court, cited_court, citing_year, cited_year, hierarchy):
    if not cited_court or not citing_court:
        return False, "court_unknown"
    if citing_year and cited_year and int(cited_year) > int(citing_year):
        return False, "cited_later"
    if cited_court == citing_court or (citing_court, cited_court) in hierarchy:
        return True, ""
    return False, "hierarchy_unsupported"
