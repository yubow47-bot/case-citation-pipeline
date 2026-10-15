"""Conservative, dependency-free experimental short-reference resolution.

These rules produce review evidence, never production citation edges. Offsets
always refer to the original Python Unicode string. Named references search all
earlier full anchors in the document; ibid/id accept a short citation-like gap.
Quotation, footnote and non-case detection are deliberately lexical approximations.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata


DETECTOR = "rules-v2"
MAX_IMMEDIATE_GAP = 220
_MARKER = re.compile(
    r"(?<!\w)(?P<ibid>ibid\.?)(?!\w)|(?<!\w)(?P<id>id\.)(?![A-Za-z])|"
    r"(?<!\w)(?P<supra>supra)(?!\w)|"
    r"(?<!\w)(?P<precite>pr[eé]cit[eé](?:e)?s?)(?!\w)", re.I)
_NOTE = re.compile(r"\s*,?\s*(?:notes?|n\.?|footnotes?|fn\.?)\s*(\d+)\b", re.I)
_NUMBER = r"\d+(?:\.\d+)*(?:\s*(?:[-–]|à)\s*\d+(?:\.\d+)*)?"
_PIN = re.compile(
    r"\s*,?\s*(?:(?:at|à|au|aux)\s+)?(?:(?:la|le|les)\s+)?"
    r"(?:paras?\.?|paragraphs?|paragraphes?|par\.?|pp?\.?|pages?)\s*"
    + _NUMBER + r"(?:\s*(?:,|and|et)\s*" + _NUMBER + r")*|"
    r"\s*,?\s*(?:at|à)\s+" + _NUMBER, re.I)
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_NAME_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_VERSUS = re.compile(r"(?<!\w)(?:v\.?|vs\.?|c\.)\s+", re.I)
_REFERENCE_TITLE = re.compile(r"\b(?:Renvoi\b|Reference\s+[Rr]e\b|Re\s+(?=[A-ZÀ-ÖØ-Þ]))")
_TITLE_CONNECTORS = frozenset((
    "a an and at au aux d de des du en et for in l la le les of on or sur the to "
    "à hospitalier"
).split())
_TITLE_LEAD = re.compile(r"^(?:(?:In|Dans|See|Voir|Cf|En)\s+|(?:de|du|des|dans|in|sur)\s+)+")
_EXPLICIT_SHORTNAME = re.compile(
    r"^\s*,?\s*\(\s*(?:(?:ci[- ]apr[eè]s|hereinafter)\s*[, :]?\s*)?"
    r"(?:(?:le|la|the)\s+)?[«“\"']\s*(?P<name>[^»”\"'\n]{2,160}?)\s*[»”\"']\s*\)", re.I)
_FOOTNOTE = re.compile(r"(?m)^[ \t]*(?:\[(\d+)\]|(\d+)[.)]|(\d+)[ \t]+)(?=\s*\S)")
_FOOTNOTE_SECTION = re.compile(r"(?mi)^[ \t]*(?:footnotes|notes de bas de page)[ \t]*:?[ \t]*$")
_NONCASE = re.compile(
    r"\b(?:act|code|statute|regulations?|treatise|book|ouvrage|loi|règlement|"
    r"reglement|lettre|letters?|débentures?|debentures?|dispositions?|"
    r"articles?|alinéas?|alineas?|convention|contrat|contract|rapport|report)\b", re.I)
_GAP_WORDS = frozenset((
    "at para paras paragraph paragraphs par p pp page pages and et a au aux "
    "see also voir cf n note notes footnote footnotes fn ibidem"
).split())
_GENERIC_NAMES = {
    "r", "rex", "regina", "the queen", "queen", "the king", "king", "la reine", "le roi",
    "the crown", "crown", "sa majeste", "her majesty", "his majesty", "the court", "court",
}
_BARE_GENERIC_NAMES = _GENERIC_NAMES | {
    "canada", "ontario", "quebec", "alberta", "manitoba", "saskatchewan",
    "british columbia", "nova scotia", "new brunswick", "newfoundland",
    "prince edward island", "attorney general", "procureur general",
    "supreme court", "court of appeal", "cour supreme", "cour d appel",
    "judge", "judges", "justice", "justices", "juge", "juges",
}


def _fold(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value).casefold()
                   if not unicodedata.combining(c))


def _tokens(value):
    return tuple(_fold(m.group()) for m in _WORD.finditer(value))


def _name_tokens(value):
    # Numeric reference-title parts must remain distinct: Loi 30 is not Loi 31.
    return tuple(_fold(m.group()) for m in _NAME_WORD.finditer(value))


def _mask_qualifiers(value):
    """Hide balanced parenthetical qualifiers without changing source offsets."""
    chars, stack = list(value), []
    for i, char in enumerate(value):
        if char == "(":
            stack.append(i)
        elif char == ")":
            if not stack:
                return None
            start = stack.pop()
            chars[start:i + 1] = " " * (i + 1 - start)
    return None if stack else "".join(chars)


def _local_title(text, anchor, lower):
    """Find a printed case title immediately before a full citation, never translate it."""
    lower = max(lower, anchor["start"] - 400)
    prefix = text[lower:anchor["start"]].rstrip(" ,\t\r\n(")
    if not prefix or any(c in prefix[-1:] for c in '"“”«»'):
        return None
    # Full reference titles are recognizably different from ordinary statutory
    # mentions. Comma-separated alternative descriptions retain their own spans.
    references = list(_REFERENCE_TITLE.finditer(prefix))
    if references:
        start = references[-1].start()
        title = prefix[start:]
        if (len(title) <= 280 and not re.search(r"[;\n\r!?«»“”\"]", title)
                and _mask_qualifiers(title) is not None):
            return lower + start, lower + len(prefix)
    versus = list(_VERSUS.finditer(prefix))
    if not versus:
        return None
    separator = versus[-1]
    masked = _mask_qualifiers(prefix)
    if masked is None:
        return None
    right = list(_NAME_WORD.finditer(masked, separator.end()))
    if not right or any(not (m.group()[0].isupper() or _fold(m.group()) in _TITLE_CONNECTORS)
                        for m in right):
        return None
    if re.search(r"[;!?«»“”\"]|\n\s*\n", prefix[separator.end():]):
        return None
    left = list(_NAME_WORD.finditer(masked, 0, separator.start()))
    if not left:
        return None
    first, boundary = left[-1].start(), separator.start()
    for word in reversed(left):
        if (not (word.group()[0].isupper() or _fold(word.group()) in _TITLE_CONNECTORS)
                or re.search(r"[,;:!?]|\n", prefix[word.end():boundary])):
            break
        first, boundary = word.start(), word.start()
    title = prefix[first:]
    leading = _TITLE_LEAD.match(title)
    if leading:
        first += leading.end()
        title = prefix[first:]
    if (len(title) > 280 or not title or not title[0].isupper()
            or not list(_NAME_WORD.finditer(prefix[first:separator.start()]))):
        return None
    return lower + first, lower + len(prefix)


def _quoted_title_before(text, anchor, quote_ranges):
    """Quoted article/book titles immediately followed by a citation cannot seed a case."""
    for start, end in reversed(quote_ranges):
        if end > anchor["start"]:
            continue
        gap = text[end:anchor["start"]]
        if len(gap) > 24:
            break
        if re.fullmatch(r"[\s,]*(?:\(\d{4}\)[\s,]*)?", gap):
            if len(_tokens(text[start + 1:end - 1])) >= 3:
                return start, end
    return None


def enrich_anchors(text: str, anchors: list[dict]) -> list[dict]:
    """Copy anchors and add auditable source aliases without altering production identity.

    ``source_aliases`` contains original ``start/end/raw/origin`` evidence. A
    quoted title adjoining a full reference sets ``short_identity_seed_allowed``
    false, while its production target and original aliases remain intact.
    Reapplying this helper is safe; callers may persist its additive fields.
    """
    result = sorted((dict(a) for a in anchors), key=lambda a: (a["start"], a["end"]))
    quotes = _quoted_ranges(text)
    previous_end = 0
    for index, anchor in enumerate(result):
        if not (isinstance(anchor["start"], int) and isinstance(anchor["end"], int)
                and 0 <= anchor["start"] < anchor["end"] <= len(text)):
            raise ValueError("Anchor offsets must be valid original-text half-open spans")
        evidence = []
        quoted_title = _quoted_title_before(text, anchor, quotes)
        anchor["short_identity_seed_allowed"] = not bool(quoted_title)
        anchor["short_identity_seed_reason"] = "quoted_title_before_citation" if quoted_title else "full_case_anchor"
        anchor["local_case_name"] = None
        title_span = _local_title(text, anchor, previous_end) if not quoted_title else None
        if title_span:
            start, end = title_span
            anchor["local_case_name"] = text[start:end]
            evidence.append({"start": start, "end": end, "raw": text[start:end], "origin": "local_case_title"})
            # A printed reference heading before a comma is an explicit local
            # title, not a first-word/surname abbreviation.
            if _REFERENCE_TITLE.match(text[start:end]) and "," in text[start:end]:
                head_end = start + text[start:end].index(",")
                evidence.append({"start": start, "end": head_end, "raw": text[start:head_end],
                                 "origin": "local_reference_title_head"})
        upper = min(len(text), anchor["end"] + 200)
        following = [a["start"] for a in result[index + 1:] if a["start"] >= anchor["end"]]
        if following:
            upper = min(upper, following[0])
        declaration = _EXPLICIT_SHORTNAME.match(text[anchor["end"]:upper]) if not quoted_title else None
        if declaration:
            start, end = (anchor["end"] + p for p in declaration.span("name"))
            evidence.append({"start": start, "end": end, "raw": text[start:end], "origin": "explicit_shortname"})
        anchor["source_aliases"] = evidence
        previous_end = max(previous_end, anchor["end"])
    return result


def _aliases(anchor):
    if anchor.get("short_identity_seed_allowed") is False:
        return {}
    supplied = list(anchor.get("aliases") or [])
    name = anchor.get("case_name") or ""
    if name:
        supplied.append(name)
    supplied.extend(row["raw"] for row in anchor.get("source_aliases", []))
    values = []
    for value in supplied:
        if not isinstance(value, str):
            continue
        values.append(value)
        values.extend(re.split(r"\s+(?:v\.?|vs\.?|c\.)\s+", value, flags=re.I))
    # False marks an exact title/party alias; True records an explicit shortened
    # variant. Never invent first-word or surname-only aliases.
    result = {}
    for value in values:
        tokens = _name_tokens(value)
        if tokens and any(t.isalpha() for t in tokens) and " ".join(tokens) not in _GENERIC_NAMES:
            result[tokens] = False
    for value in values:
        shortened = value
        while re.search(r"\([^()]*\)", shortened):
            shortened = re.sub(r"\([^()]*\)", " ", shortened)
        if "(" in shortened or ")" in shortened:
            continue  # Unbalanced qualifiers do not justify a canonical alias.
        shortened = shortened.rstrip(" .,\t\r\n")
        while True:
            stripped = re.sub(r"\b(?:inc|ltd|limited|corp|corporation)\.?\s*$", "", shortened, flags=re.I).rstrip(" .,\t\r\n")
            if stripped == shortened:
                break
            shortened = stripped
        tokens = _name_tokens(shortened)
        if (shortened != value and tokens
                and not (len(tokens) == 1 and len(tokens[0]) == 1)
                and " ".join(tokens) not in _GENERIC_NAMES):
            result.setdefault(tokens, True)
    return result


def _citation_gap(value):
    """Accept pinpoints and citation connectors, never arbitrary prose."""
    if len(value) > MAX_IMMEDIATE_GAP or re.search(r"\n\s*\n", value):
        return False
    if any(c in value for c in '\"“”«»') or _NONCASE.search(value):
        return False
    return all(word in _GAP_WORDS for word in _tokens(value))


def _quoted_ranges(text):
    # Do not interpret apostrophes as quotation marks in party names or French.
    stack, spans = [], []
    pairs = {"“": "”", "«": "»", '"': '"'}
    for i, char in enumerate(text):
        if stack and char == stack[-1][0]:
            _, start = stack.pop()
            spans.append((start, i + 1))
        elif char in pairs:
            stack.append((pairs[char], i))
    spans.extend((start, len(text)) for _, start in stack)
    return sorted(spans)


def _in_quote(position, ranges):
    return any(start <= position < end for start, end in ranges)


def _record(text, start, end, marker_start, marker_end, kind, source_id, run_id, text_sha256):
    key = json.dumps([run_id, source_id, text_sha256, start, end, kind],
                     ensure_ascii=False, separators=(",", ":"))
    return {
        "mention_id": "short_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24],
        "kind": kind, "start": start, "end": end, "raw": text[start:end],
        "target_group_id": None, "resolution_status": "unresolved",
        "resolution_basis": "no_prior_case_antecedent",
        "antecedent_mention_ids": [], "candidate_target_ids": [], "notes": [],
        "pinpoint": None, "detector": DETECTOR,
        "marker_start": marker_start, "marker_end": marker_end,
    }


def _set_result(record, antecedents, basis, *, status=None):
    ids = sorted({str(a["target_group_id"]) for a in antecedents if a.get("target_group_id")})
    record["candidate_target_ids"] = ids
    record["antecedent_mention_ids"] = sorted({str(a["mention_id"]) for a in antecedents
                                                if a.get("mention_id")})
    if status is None:
        status = "resolved" if len(ids) == 1 else "ambiguous" if len(ids) > 1 else "unresolved"
    record["resolution_status"] = status
    record["resolution_basis"] = basis
    record["target_group_id"] = ids[0] if status == "resolved" and len(ids) == 1 else None
    evidence = {(row["start"], row["end"], row["origin"]): dict(row)
                for anchor in antecedents for row in anchor.get("source_aliases", [])}
    if evidence:
        record["alias_evidence"] = [evidence[key] for key in sorted(evidence)]


def _completed_list_boundary(text, start, earlier, shorts):
    """Require a completed citation before a comma-and/et list connector."""
    prior = [a for a in [*earlier, *shorts] if a["end"] <= start]
    if not prior:
        return None
    last = max(prior, key=lambda a: (a["end"], a["start"]))
    gap = text[last["end"]:start]
    connector = re.fullmatch(r"(?P<tail>.{0,220}?)\s*[,;]\s*(?:and|et)\s*", gap, re.I | re.S)
    if not connector:
        return None
    tail = connector.group("tail")
    # Court qualifiers printed after full citations are part of the completed
    # reference; arbitrary prose or another unrecognized name is not.
    court = re.compile(r"\s*\((?:[A-Za-z]{1,6}\.?(?:\s+|(?=C\.))){0,3}"
                       r"(?:C\.?\s*A\.?|S\.?\s*C\.?\s*C\.?|H\.?\s*L\.?|P\.?\s*C\.?)\)\s*")
    for _ in range(2):
        qualifier = court.match(tail)
        pinpoint = _PIN.match(tail)
        consumed = qualifier.end() if qualifier else pinpoint.end() if pinpoint else 0
        if not consumed:
            break
        tail = tail[consumed:]
    if tail.strip(" ,\t\r\n"):
        return None
    return {"mention_id": last.get("mention_id"), "start": last["start"], "end": last["end"],
            "connector_start": last["end"], "connector_end": start, "connector_raw": gap}


def _named_candidates(text, marker_start, earlier, shorts=(), evidence=None):
    """Match complete alias tokens at the end of the immediate name prefix."""
    prefix_start = max(0, marker_start - 180)
    prefix = text[prefix_start:marker_start]
    words = list(_NAME_WORD.finditer(prefix))
    normalized = tuple(_fold(m.group()) for m in words)
    matches = []
    for anchor in earlier:
        for alias, normalized_short in _aliases(anchor).items():
            if len(alias) > len(words):
                continue
            tail = normalized[-len(alias):]
            separator_normalized = (len(alias) > 2 and alias[0] == tail[0] == "r"
                                    and alias[1] in {"c", "v"} and tail[1] in {"c", "v"}
                                    and alias[1] != tail[1] and alias[2:] == tail[2:])
            if tail == alias or separator_normalized:
                start = prefix_start + words[-len(alias)].start()
                if start >= 2 and text[start - 1] in "-–'’" and text[start - 2].isalpha():
                    continue  # Do not match a suffix inside another party's name.
                # Only whitespace/comma may separate the name from its marker.
                if re.fullmatch(r"[\s,]*", text[prefix_start + words[-1].end():marker_start]):
                    matches.append((start, anchor, normalized_short, separator_normalized))
    if not matches:
        return [], marker_start, False, False
    start = min(item[0] for item in matches)
    candidates = [anchor for pos, anchor, _, _ in matches if pos == start]
    normalized_short = any(short for pos, _, short, _ in matches if pos == start)
    if evidence is not None and any(syntax for pos, _, _, syntax in matches if pos == start):
        evidence["case_title_separator_normalized"] = True
    before = text[max(0, start - 80):start]
    # A matching surname cannot stand in for a different, unrecognized case title.
    compound = bool(re.search(r"\b(?:v|vs|c|and|et)\.?\s*$", before, re.I))
    if re.search(r";\s*(?:and|et)\s*$", before, re.I):
        compound = False  # ``Smith, supra; and Brown, supra`` is a clear list.
    elif compound and re.search(r"\b(?:and|et)\s*$", before, re.I):
        boundary = _completed_list_boundary(text, start, earlier, shorts)
        if boundary:
            compound = False
            if evidence is not None:
                evidence["list_boundary_evidence"] = boundary
    return candidates, start, compound, normalized_short


def _multiple_named_candidates(text, marker_start, earlier):
    """Keep two-authority lists as candidates; partial party prefixes never resolve."""
    lower = max(0, marker_start - 180)
    prefix = text[lower:marker_start]
    match = re.search(
        r"(?P<first>[A-ZÀ-ÖØ-Þ][\w’'\-‑]+(?:\s+[A-ZÀ-ÖØ-Þ][\w’'\-‑]+){0,3})"
        r"\s+(?:and|et)\s+(?P<second>[A-ZÀ-ÖØ-Þ][\w’'\-‑]+"
        r"(?:\s+[A-ZÀ-ÖØ-Þ][\w’'\-‑]+){0,3})\s*,?\s*$", prefix)
    if not match:
        return [], marker_start
    candidates = []
    for part in (match.group("first"), match.group("second")):
        tokens = _name_tokens(part)
        local = []
        for anchor in earlier:
            for alias in _aliases(anchor):
                if alias == tokens or (len(tokens[0]) >= 4 and alias[:len(tokens)] == tokens):
                    local.append(anchor)
                    break
        if not local:
            return [], marker_start
        candidates.extend(local)
    return candidates, lower + match.start("first")


def _footnote_candidates(text, marker_start, note_number, earlier):
    labels = list(_FOOTNOTE.finditer(text, 0, marker_start))
    matches = []
    noncase = False
    explicit_section = False
    for i, label in enumerate(labels):
        number = next(g for g in label.groups() if g is not None)
        if int(number) != note_number:
            continue
        end = labels[i + 1].start() if i + 1 < len(labels) else marker_start
        local = [a for a in earlier if label.end() <= a["start"] and a["end"] <= end]
        matches.extend(local)
        # Remove known full-anchor spans, then inspect the remaining note prose
        # for explicit non-case authorities. Unknown case candidates should also
        # be supplied by the caller as unlinked anchors.
        remainder, position = [], label.end()
        for anchor in sorted(local, key=lambda a: a["start"]):
            remainder.append(text[position:anchor["start"]])
            position = max(position, anchor["end"])
        remainder.append(text[position:end])
        noncase = noncase or bool(_NONCASE.search(" ".join(remainder)))
        explicit_section = explicit_section or bool(_FOOTNOTE_SECTION.search(text, 0, label.start()))
    return matches, noncase, explicit_section


def _immediate(text, record, anchors, shorts, quote_ranges):
    start = record["marker_start"]
    prior = [a for a in anchors if a["end"] <= start]
    prior.extend(s for s in shorts if s["end"] <= start)
    if not prior:
        return
    prior.sort(key=lambda a: (a["end"], a["start"]))
    last = prior[-1]
    gap = text[last["end"]:start]
    if not _citation_gap(gap):
        record["resolution_basis"] = "immediate_context_barrier"
        record["notes"].append("Intervening prose, an unknown authority, quotation, or distance blocks adjacency.")
        return
    if last.get("detector") == DETECTOR:
        if last["resolution_status"] != "resolved":
            _set_result(record, [last], "prior_short_reference_not_resolved",
                        status="ambiguous" if last["resolution_status"] == "ambiguous" else "unresolved")
            record["candidate_target_ids"] = last["candidate_target_ids"][:]
            return
        _set_result(record, [last], "immediate_resolved_short_reference")
        return
    cluster = [last]
    boundary = last["start"]
    for item in reversed(prior[:-1]):
        if item.get("detector") == DETECTOR or item["end"] > boundary:
            # Overlapping parallel anchors still describe one citation cluster.
            if item.get("detector") != DETECTOR and item["end"] > boundary:
                cluster.append(item)
                boundary = min(boundary, item["start"])
                continue
            break
        if not _citation_gap(text[item["end"]:boundary]):
            break
        cluster.append(item)
        boundary = item["start"]
    if any(a.get("short_identity_seed_allowed") is False for a in cluster):
        _set_result(record, cluster, "noncase_identity_seed_barrier", status="blocked")
    elif any(not a.get("target_group_id") for a in cluster):
        _set_result(record, cluster, "immediate_unlinked_authority_barrier", status="blocked")
    elif any(_in_quote(a["start"], quote_ranges) for a in cluster):
        _set_result(record, cluster, "quoted_antecedent_barrier", status="blocked")
    else:
        _set_result(record, cluster, "immediate_full_citation_cluster")


def resolve_document(text: str, anchors: list[dict], *, source_id: str,
                     run_id: str, text_sha256: str) -> list[dict]:
    """Return all lexical short mentions with conservative resolution evidence.

    Anchors use original half-open ``start``/``end`` offsets. A nonempty target
    group makes an identity usable; unlinked anchors are retained as barriers.
    No caller objects are modified. Generic royal party names are never aliases.
    """
    anchors = enrich_anchors(text, anchors)
    quote_ranges = _quoted_ranges(text)
    records = []
    for match in _MARKER.finditer(text):
        kind = match.lastgroup
        marker_start, marker_end = match.span()
        end = marker_end
        note = _NOTE.match(text, end) if kind in {"supra", "precite"} else None
        if note:
            end = note.end()
        pin = _PIN.match(text, end)
        if pin:
            end = pin.end()
        earlier = [a for a in anchors if a["end"] <= marker_start]
        named_evidence = {}
        named, start, compound, normalized_short = _named_candidates(text, marker_start, earlier, records, named_evidence) if kind in {"supra", "precite"} else ([], marker_start, False, False)
        multiple, multiple_start = _multiple_named_candidates(text, marker_start, earlier) if kind in {"supra", "precite"} else ([], marker_start)
        if multiple:
            named, start, compound = multiple, multiple_start, True
        record = _record(text, start, end, marker_start, marker_end, kind,
                         source_id, run_id, text_sha256)
        record.update(named_evidence)
        if pin:
            record["pinpoint"] = pin.group().strip(" ,\t\r\n")
        if note:
            record["footnote_number"] = int(note.group(1))
        if normalized_short:
            record["notes"].append("Matched an explicit short-party alias after removing balanced parentheses and/or trailing Inc/Ltd/Limited/Corp/Corporation; no surname or first-word expansion.")
        if named_evidence.get("case_title_separator_normalized"):
            record["notes"].append("Matched the complete royal case title with c./v. separator syntax normalized; every party-name token is unchanged.")
        local_prefix = text[max(0, marker_start - 100):marker_start]
        # Decimal reporter substitutions such as ``20 id.226`` are not case ibid.
        reporter_id = kind == "id" and (re.search(r"\d+\s*$", local_prefix)
                                         or re.match(r"\d", text[marker_end:]))
        noncase_prefix = re.split(r"[.;\n]", local_prefix)[-1]
        if reporter_id:
            record["resolution_status"] = "blocked"
            record["resolution_basis"] = "reporter_id_substitution"
        elif kind == "id" and match.group().isupper():
            record["resolution_status"] = "blocked"
            record["resolution_basis"] = "all_caps_id_nonreference_risk"
        elif _in_quote(marker_start, quote_ranges):
            record["resolution_status"] = "blocked"
            record["resolution_basis"] = "quoted_short_reference"
            record["notes"].append("Lexical double-quote/guillemet heuristic; quotation attribution is not inferred.")
        elif (_NONCASE.search(noncase_prefix) and not named
              and not _REFERENCE_TITLE.search(noncase_prefix)):
            record["resolution_status"] = "blocked"
            record["resolution_basis"] = "apparent_noncase_reference"
        elif kind in {"ibid", "id"}:
            _immediate(text, record, anchors, records, quote_ranges)
        elif compound:
            _set_result(record, named, "multiple_named_authorities" if multiple else "unrecognized_or_compound_case_name", status="ambiguous")
            if multiple:
                record["notes"].append("An explicit authority list keeps all matching targets for review; partial party-name prefixes do not establish a link.")
        elif note:
            noted, noncase_note, explicit_section = _footnote_candidates(text, marker_start, int(note.group(1)), earlier)
            if named:
                named_targets = {a.get("target_group_id") for a in named if a.get("target_group_id")}
                note_targets = {a.get("target_group_id") for a in noted if a.get("target_group_id")}
                if not noted:
                    _set_result(record, named, "explicit_note_has_no_prior_case_anchor", status="unresolved")
                elif named_targets != note_targets:
                    _set_result(record, named + noted, "named_and_footnote_antecedents_conflict", status="ambiguous")
                else:
                    _set_result(record, named + noted, "named_and_explicit_footnote_antecedent")
            else:
                _set_result(record, noted, "explicit_footnote_antecedent")
                if noted and not explicit_section:
                    _set_result(record, noted, "numeric_label_may_be_paragraph", status="ambiguous")
            if any(not a.get("target_group_id") for a in noted):
                _set_result(record, noted, "explicit_footnote_unlinked_authority", status="blocked")
            elif noncase_note:
                _set_result(record, named + noted, "explicit_footnote_noncase_authority", status="blocked")
            record["notes"].append("Footnotes are approximated by line-start numeric labels; paragraph labels may look identical.")
        elif named:
            _set_result(record, named, "named_prior_normalized_short_party" if normalized_short else "named_unique_prior_antecedent")
            if any(not a.get("target_group_id") for a in named):
                _set_result(record, named, "named_unlinked_authority", status="blocked")
        else:
            record["resolution_basis"] = ("case_title_without_prior_anchor" if _REFERENCE_TITLE.search(noncase_prefix)
                                          else "named_or_explicit_note_antecedent_required")
        if record["resolution_status"] == "resolved":
            antecedent_ids = set(record["antecedent_mention_ids"])
            if any(a.get("mention_id") in antecedent_ids and a.get("short_identity_seed_allowed") is False
                   for a in earlier):
                record["resolution_status"] = "blocked"
                record["resolution_basis"] = "noncase_identity_seed_barrier"
                record["target_group_id"] = None
            elif any(a.get("mention_id") in antecedent_ids and not a.get("target_group_id") for a in earlier):
                record["resolution_status"] = "blocked"
                record["resolution_basis"] = "unlinked_antecedent_barrier"
                record["target_group_id"] = None
            elif any(a.get("mention_id") in antecedent_ids and _in_quote(a["start"], quote_ranges)
                   for a in earlier):
                record["resolution_status"] = "blocked"
                record["resolution_basis"] = "quoted_antecedent_barrier"
                record["target_group_id"] = None
        records.append(record)
    # Regex matches are unique; this also guarantees deterministic span order when
    # a known named prefix extends a marker to the left.
    return sorted(records, key=lambda r: (r["start"], r["end"], r["kind"]))


def resolve_named_mentions(text: str, anchors: list[dict], *, exclude_spans=(),
                           source_id="", run_id="", text_sha256=None) -> list[dict]:
    """Find possible bare case names using exact aliases of prior full anchors.

    This optional layer is reported separately from marked short references.
    Local full-title/declaration spans and caller exclusions do not become new
    mentions. No first-word/surname aliases are created, generic geographical
    party names are excluded, and collisions and quotations remain explicit.
    """
    anchors = enrich_anchors(text, anchors)
    excluded = list(exclude_spans)
    excluded.extend((a["start"], a["end"]) for a in anchors)
    excluded.extend((e["start"], e["end"]) for a in anchors for e in a["source_aliases"])
    words = list(_NAME_WORD.finditer(text))
    tokens = tuple(_fold(word.group()) for word in words)
    by_first = {}
    for anchor in anchors:
        for alias in _aliases(anchor):
            if (" ".join(alias) in _BARE_GENERIC_NAMES or not any(len(t) >= 3 for t in alias)
                    or len(alias) == 1 and len(alias[0]) < 4):
                continue
            by_first.setdefault(alias[0], {}).setdefault(alias, []).append(anchor)
    quotes = _quoted_ranges(text)
    sha = text_sha256 or hashlib.sha256(text.encode("utf-8")).hexdigest()
    matches = []
    for index, word in enumerate(words):
        if not word.group()[0].isupper():
            continue
        for alias, seeds in by_first.get(tokens[index], {}).items():
            limit = index + len(alias)
            if limit > len(words) or tokens[index:limit] != alias:
                continue
            start, end = word.start(), words[limit - 1].end()
            # A token suffix in O'Smith or Toneguzzo-Smith is not Smith.
            if (start >= 2 and text[start - 1] in "-‑–'’" and text[start - 2].isalpha()
                    or end + 1 < len(text) and text[end] in "-‑–'’" and text[end + 1].isalpha()):
                continue
            if any(a < end and start < b for a, b in excluded):
                continue
            if re.search(r"[;!?«»“”\"]|\n\s*\n", text[start:end]):
                continue
            earlier = [a for a in seeds if a["end"] <= start]
            if earlier:
                matches.append((start, end, earlier))
    # Keep the most complete alias at a surface occurrence, avoiding a second
    # party-name mention inside an already recognized complete case title.
    chosen = []
    for start, end, seeds in sorted(matches, key=lambda item: (item[0], -item[1])):
        if chosen and start < chosen[-1][1]:
            if (start, end) == chosen[-1][:2]:
                chosen[-1][2].extend(seeds)
            continue
        chosen.append((start, end, list(seeds)))
    records = []
    for start, end, seeds in chosen:
        record = _record(text, start, end, None, None, "case_name", source_id, run_id, sha)
        _set_result(record, seeds, "exact_prior_source_case_alias")
        record["matched_alias"] = text[start:end]
        before = text[max(0, start - 60):start]
        after = text[end:min(len(text), end + 40)]
        person_context = re.search(
            r"\b(?:mr|ms|mrs|justice|juge|monsieur|madame|mme|mlle|m)\.?\s*$", before, re.I)
        investigation_context = (re.match(r"\s+(?:investigation|enqu[eê]te)\b", after, re.I)
                                 or re.search(r"\benqu[eê]te(?:\s+sur)?\s+$", before, re.I))
        if _in_quote(start, quotes):
            _set_result(record, seeds, "quoted_case_name_reference", status="blocked")
        elif person_context or investigation_context:
            _set_result(record, seeds, "person_or_investigation_name_context", status="blocked")
            record["notes"].append("An adjacent honorific or investigation label identifies a person/entity usage; the prior case alias remains a review candidate only.")
        elif any(not a.get("target_group_id") for a in seeds):
            _set_result(record, seeds, "named_unlinked_authority", status="blocked")
        elif re.search(r"\b(?:v|vs|c)\.?\s*$", before, re.I):
            _set_result(record, seeds, "unrecognized_case_title", status="ambiguous")
        elif any(_in_quote(a["start"], quotes) for a in seeds):
            _set_result(record, seeds, "quoted_antecedent_barrier", status="blocked")
        records.append(record)
    return records
