"""Experimental lexical cues, never verified treatment or human review labels.

Offsets are Python Unicode string offsets into the unchanged input. One observation
is emitted per cue, including cues with no uniquely supported citation target.
Sentence/clause boundaries, negation and attribution are deliberately small lexical
heuristics, not a parser. Signals inside supplied citation spans are ignored.

Clause membership supplies candidates, never a target by itself. Small directional
rules recognize a predicate's object or passive subject, including source-seeded
case-name mentions. Candidate, target and contextual mention IDs remain distinct.
Attribution evidence preserves the exact original spans used by each rule; speaker
identity remains unknown. Edge summaries keep every evidence item and possible
label conflict instead of selecting a winning treatment. Procedural affirmed /
reversed cues are separate from substantive treatment suggestions. Coverage counts
assigned lexical evidence, not verified treatment or human review.
Treatment labels are lexical vocabulary, independent of the
manual quality labels and production DD. No score or confidence is manufactured.
"""
from __future__ import annotations

import hashlib
import json
import re


_VOCABULARY = {
    "applied": r"appl(?:ied|y|ying|ies)|appliqu(?:é(?:e?s)?|er|e|ent|ait)",
    "followed": r"follow(?:ed)?|suiv(?:i(?:e?s)?|re|ons|ent)",
    "adopted": r"adopt(?:ed|ing)?|adopt(?:é(?:e?s)?|er|e|ent)",
    "distinguished": r"distinguish(?:ed|es|ing)?|distingu(?:é(?:e?s)?|er|e|ent)",
    "criticized": r"critici[sz](?:ed|es|ing|e)|critiqu(?:é(?:e?s)?|er|e|ent)",
    "overruled": r"overrul(?:ed|es|ing|e)",
    "considered": r"consider(?:ed|ing|s)?|consid(?:é|e)r(?:é(?:e?s)?|er|e|ent)|examin(?:é(?:e?s)?|er|e|ent)",
    "discussed": r"discuss(?:ed|es|ing)?|discut(?:é(?:e?s)?|er|e|ent)",
    "mentioned": r"mention(?:ed|ing|s)?|mentionn(?:é(?:e?s)?|er|e|ent)|cit(?:é(?:e?s)?|er)",
    "affirmed": r"affirm(?:ed|ing|s)?|upheld|confirm(?:é(?:e?s)?|er|e|ent)",
    "reversed": r"revers(?:ed|es|ing|e)|overturned|infirm(?:é(?:e?s)?|er|e|ent)|renvers(?:é(?:e?s)?|er|e|ent)",
}
_SIGNALS = [(label, re.compile(r"(?<!\w)(?:" + pattern + r")(?!\w)", re.I))
            for label, pattern in _VOCABULARY.items()]
_SENTENCE = re.compile(r'[.!?](?=\s+(?:[A-ZÀ-ÖØ-Þ\d]|["“«])|$)|\n[ \t]*\n|\n(?=[ \t]*(?:\[\d{1,5}\]|\d{1,3}[.)]?[ \t]+(?=[A-ZÀ-ÖØ-Þ])))')
_ABBREVIATION = re.compile(r"(?<!\w)(?:[A-Za-zÀ-ÖØ-öø-ÿ]|Inc|Ltd|Corp|Dr|Mr|Mrs|Ms|Mme|Me|No|Nos|para|paras|art|al|JJ|CJ|LJ)\.", re.I)
_CLAUSE = re.compile(r";|(?:,\s*)?\b(?:but|however|whereas|mais|cependant|tandis\s+que)\b", re.I)
_AND = re.compile(r"\b(?:and|et)\b", re.I)
_PARTY = re.compile(r"\b(?:appellant|respondent|plaintiff|defendant|applicant|counsel|party|parties|appelant\w*|intimé\w*|demandeur\w*|défendeur\w*|avocat\w*)\b.{0,100}?\b(?:argu\w*|submit\w*|contend\w*|assert\w*|soutien\w*|prétend\w*|plaid\w*|fait\s+valoir)\b", re.I | re.S)
_REPORTED = re.compile(r"\b(?:quot(?:ed|ing)|according\s+to|as\s+(?:stated|held|said)|selon|citant|cité\s+par)\b", re.I)
_DISSENT = re.compile(r"\b(?:dissent\w*|dissiden\w*|minority|minoritaire)\b", re.I)
_NEGATION = re.compile(r"\b(?:not|never|neither|cannot|no\s+longer|pas|jamais|aucunement)\b|\b\w+n['’]t\b|\b(?:declin\w*|refus\w*)\s+to\s*(?:\w+\s+){0,2}$|\bn['’](?:\w+\s+){0,2}$", re.I)
_RELIEF_APPLICATION = re.compile(r"appl(?:ied|y|ying)\s+(?:for\b|to\s+(?:(?:the|a|an)\s+)?(?:\w+\s+){0,5}(?:court|tribunal|judge)\b|(?:in\s+.{1,80}?\s+)?to\s+(?:have|obtain|seek|dismiss|strike|stay)\b)", re.I)
_PROCEDURAL = frozenset(("affirmed", "reversed"))
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_PUNCTUATION_GAP = re.compile(r"[\s,;:()[\].\-–—]*")
_LIST_GAP = re.compile(r"\s*(?:,\s*(?:(?:and|or|et|ou)\s+)?|(?:and|or|et|ou|as\s+well\s+as|ainsi\s+que|&)\s+)(?:(?:the|le|la|les)\s+)?", re.I)
_DETERMINER = r"(?:the|a|an|le|la|les|ce|cette|cet|ces|l['’])"
_ADVERB = r"(?:also|again|expressly|directly|consistently|repeatedly|carefully|recently|specifically|fully|further|respectfully|then|également|expressément)"
_LEGAL_OBJECT = r"(?:decisions?|judgments?|cases?|reasoning|rules?|principles?|tests?|approach|analysis|holdings?|dicta?|observations?|comments?|statements?|definitions?|expressions?|rationale|views?|propositions?|conclusions?|criteria|doctrine|décisions?|arrêts?|raisonnement|règles?|principes?|critères?|conclusions?)"
_DIRECT_OBJECT = re.compile(r"[\s(\[\"“«]*(?:" + _ADVERB + r"\s+)*(?:" + _DETERMINER + r"\s*)?", re.I)
_CONTENT_OBJECT = re.compile(
    r"\s*(?:" + _ADVERB + r"\s+)*(?:" + _DETERMINER + r"\s+)?" + _LEGAL_OBJECT +
    r"(?:\s+(?:set\s+out|stated|enunciated|established|articulated|described|expressed))?"
    r"\s+(?:in|from|of|dans|de|du|des)\s+(?:" + _DETERMINER + r"\s+(?:case|decision|judgment|arrêt)\s+(?:of|in|de)\s+)?", re.I)
_PASSIVE_BRIDGE = re.compile(
    r"[\s,():\-–—]*(?:(?:which|that|qui)\s+)?"
    r"(?:(?:is|are|was|were|be|been|being|has|have|had|should|would|could|can|may|might|must|ought|to|"
    r"not|never|no\s+longer|also|often|expressly|clearly|subsequently|later|consistently|explicitly|fully|repeatedly|"
    r"a|ont|est|sont|été|être|fut|était|étaient|pas|jamais|ne|n['’])\s+){1,8}", re.I)
_PASSIVE_AUXILIARY = re.compile(r"\b(?:is|are|was|were|be|been|being|est|sont|été|être|fut|était|étaient)\b", re.I)
_PARTICIPLE = re.compile(
    r"(?:applied|followed|adopted|distinguished|critici[sz]ed|overruled|considered|discussed|mentioned|affirmed|upheld|reversed|overturned|"
    r"(?:appliqu|adopt|distingu|critiqu|considér|examin|discut|mentionn|cit|confirm|infirm|renvers)é(?:e?s)?|suivi(?:e?s)?)", re.I)
_DOCTRINE_BRIDGE = re.compile(
    r"\s*(?:principles?|rules?|tests?|doctrine|approach|reasoning|principes?|règles?|critères?)?\s*"
    r"(?:(?:will|would|can|could|may|might|should|must|ought\s+to|does|did|not|never|also|still)\s+)*", re.I)
_MODAL = re.compile(r"\b(?:will|would|should|could|may|might|must|ought|if|when|si|devrait|pourrait)\b(?:\W+\w+){0,6}\W*$", re.I)
_REPORTED_INTRO = re.compile(r"(?:^|[,;:]\s*|\b(?:example|exemple)\s*,\s*)(?:in|dans)\s*$", re.I)
_ACTOR_BRIDGE = r"\s+(?:(?:has|have|had|did|does|not|never|also|then|previously|recently|expressly|directly|subsequently|consistently)\s+){0,4}"
_CAPITALIZED_WORD = r"[A-ZÀ-ÖØ-Þ][\w'’\-]*"
_NAMED_COURT_ACTOR = re.compile(
    r"(?<!\w)(?P<actor>(?:(?:the|The)\s+)?(?:" + _CAPITALIZED_WORD +
    r"\s+){1,5}Court(?:\s+of\s+" + _CAPITALIZED_WORD +
    r"(?:\s+" + _CAPITALIZED_WORD + r"){0,2})?)" + _ACTOR_BRIDGE + r"$")
_REPORTED_JUDGE_ACTOR = re.compile(
    r"(?<!\w)(?P<actor>(?:the\s+)?(?:trial|motions?|lower|appeal|appellate|chambers)\s+judge)" +
    _ACTOR_BRIDGE + r"$", re.I)
_GENERIC_COURT_WORDS = frozenset("the this our court supreme appeal appeals superior justice high provincial federal district of".split())
_CURRENT_COURTS = {"SCC": "supreme court of canada", "ONCA": "ontario court of appeal",
                   "BCCA": "british columbia court of appeal"}


def _stable_id(prefix, payload):
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return prefix + hashlib.sha256(encoded).hexdigest()[:24]


def _trim(text, start, end):
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _overlaps(mention, start, end):
    return mention["start"] < end and mention["end"] > start


def _valid_mentions(text, mentions):
    result = []
    for mention in mentions:
        start, end = mention.get("start"), mention.get("end")
        if (isinstance(start, bool) or isinstance(end, bool) or
                not isinstance(start, int) or not isinstance(end, int) or
                not 0 <= start < end <= len(text)):
            raise ValueError("Mention offsets must select a nonempty original-text span")
        if not isinstance(mention.get("mention_id"), str) or not mention["mention_id"]:
            raise ValueError("Mention requires mention_id")
        result.append(mention)
    return sorted(result, key=lambda item: (item["start"], item["end"], item["mention_id"]))


def _target(mention):
    if mention.get("kind") != "full" and mention.get("resolution_status") != "resolved":
        return None
    target = mention.get("target_group_id")
    return target if isinstance(target, str) and target else None


def _noncase(mention):
    return (mention.get("short_identity_seed_allowed") is False and
            mention.get("short_identity_seed_reason") == "quoted_title_before_citation")


def _treatment_target(mention):
    # Keep inherited production targets in summaries while excluding an explicit
    # source-local noncase-title veto from precedent-treatment attribution.
    if _noncase(mention):
        return None
    return _target(mention)


def _candidate_targets(mention):
    if _noncase(mention):
        return []
    target = _treatment_target(mention)
    return [target] if target else [value for value in mention.get("candidate_target_ids", [])
                                  if isinstance(value, str) and value]


def _sentences(text, mentions):
    # Hide punctuation within citation spans without changing any offsets.
    masked = list(text)
    for mention in mentions:
        masked[mention["start"]:mention["end"]] = " " * (mention["end"] - mention["start"])
    # Ledger anchors can contain only the neutral citation. Preserve party and
    # quotation cues preceding case titles such as "R. v. Smith, 2001 SCC 2".
    for abbreviation in _ABBREVIATION.finditer(text):
        masked[abbreviation.end() - 1] = " "
    start = 0
    for boundary in _SENTENCE.finditer("".join(masked)):
        end = boundary.end()
        yield _trim(text, start, end)
        start = end
    if start < len(text):
        yield _trim(text, start, len(text))


def _clauses(text, start, end, mentions):
    boundaries = [(m.start() + start, m.end() + start)
                  for m in _CLAUSE.finditer(text[start:end])]
    # A citation list ("followed Alpha and Beta") is not two clauses. Require
    # both a citation and a lexical predicate on each side before splitting.
    for match in _AND.finditer(text[start:end]):
        left, right = start + match.start(), start + match.end()
        left_signal = any(p.search(text, start, left) for _, p in _SIGNALS)
        right_signal = any(p.search(text, right, end) for _, p in _SIGNALS)
        if (left_signal and right_signal and
                any(_overlaps(m, start, left) for m in mentions) and
                any(_overlaps(m, right, end) for m in mentions)):
            boundaries.append((left, right))
    cursor = start
    for left, right in sorted(boundaries):
        if left < cursor or any(_overlaps(m, left, right) for m in mentions):
            continue
        if left > cursor:
            yield _trim(text, cursor, left)
        cursor = right
    if cursor < end:
        yield _trim(text, cursor, end)


def _quote_ranges(text):
    ranges = []
    for opening, closing in [('"', '"'), ('“', '”'), ('«', '»')]:
        cursor = 0
        while True:
            start = text.find(opening, cursor)
            if start < 0:
                break
            end = text.find(closing, start + 1)
            if end < 0:
                break
            ranges.append((start, end + 1))
            cursor = end + 1
    return ranges


def _name_start(text, mention, clause_start):
    """Include a supplied case title immediately preceding a citation-only span."""
    start = mention["start"]
    if mention.get("kind") != "full":
        return start
    for evidence in mention.get("source_aliases", []):
        a, b = evidence.get("start"), evidence.get("end")
        if (isinstance(a, int) and isinstance(b, int) and clause_start <= a < b <= start
                and start - b <= 60 and _PUNCTUATION_GAP.fullmatch(text[b:start])):
            start = min(start, a)
    # Older packages have no source_aliases. Exact supplied title tokens are a
    # compatible fallback, not a newly guessed surname or case identity.
    values = [mention.get("case_name"), *(mention.get("aliases") or [])]
    for value in values:
        if not isinstance(value, str):
            continue
        words = _WORD.findall(value)
        if not words or any(char.isdigit() for char in value):
            continue
        title = r"(?<!\w)" + r"[\s.,'’()\-–]+".join(re.escape(word) for word in words) + r"(?!\w)"
        prefix_start = max(clause_start, mention["start"] - 200)
        for match in re.finditer(title, text[prefix_start:mention["start"]], re.I):
            a, b = prefix_start + match.start(), prefix_start + match.end()
            tail = text[b:mention["start"]]
            if re.fullmatch(r"[\s,.;:()[\]\-–]*(?:\(\d{4}\)[\s,]*)?", tail):
                start = min(start, a)
    return start


def _mention_units(text, mentions, clause_start):
    """Parallel full citations and an overlapping name are one grammatical unit."""
    units = []
    for mention in mentions:
        start = _name_start(text, mention, clause_start)
        target = _treatment_target(mention)
        previous = units[-1] if units else None
        same_target = previous and target and previous["target"] == target
        if (same_target and (start < previous["end"] or
                (start - previous["end"] <= 60 and
                 _PUNCTUATION_GAP.fullmatch(text[previous["end"]:start])))):
            previous["end"] = max(previous["end"], mention["end"])
            previous["mentions"].append(mention)
        else:
            units.append({"start": start, "end": mention["end"], "target": target,
                          "mentions": [mention]})
    return units


def _predicate_targets(text, units, signal_start, signal_end, label):
    """Return bounded grammatical candidates, with no unique-clause fallback."""
    following = [unit for unit in units if unit["start"] >= signal_end]
    if following:
        first = following[0]
        gap = text[signal_end:first["start"]]
        if len(gap) <= 180 and (_DIRECT_OBJECT.fullmatch(gap) or _CONTENT_OBJECT.fullmatch(gap)):
            selected = [first]
            for unit in following[1:]:
                gap = text[selected[-1]["end"]:unit["start"]]
                if len(gap) > 80 or not _LIST_GAP.fullmatch(gap):
                    break
                selected.append(unit)
            return selected, "active_object", "after"
    preceding = [unit for unit in units if unit["end"] <= signal_start]
    if preceding:
        last = preceding[-1]
        gap = text[last["end"]:signal_start]
        if (len(gap) <= 150 and _PASSIVE_BRIDGE.fullmatch(gap) and
                _PASSIVE_AUXILIARY.search(gap) and _PARTICIPLE.fullmatch(text[signal_start:signal_end])):
            selected = [last]
            for unit in reversed(preceding[:-1]):
                gap = text[unit["end"]:selected[0]["start"]]
                if (len(gap) > 80 or not _LIST_GAP.fullmatch(gap) or
                        _REPORTED_INTRO.search(text[max(0, unit["start"] - 50):unit["start"]])):
                    break
                selected.insert(0, unit)
            return selected, "passive_subject", "before"
        # A named doctrine can itself "apply". This is conditional applicability,
        # not evidence that the present court has applied it to the facts.
        if label == "applied" and len(gap) <= 100 and _DOCTRINE_BRIDGE.fullmatch(gap):
            return [last], "doctrinal_subject", "before"
    return [], "no_supported_predicate_target", None


def _reported_context(text, units, selected, clause_start, signal_start):
    selected_ids = {m["mention_id"] for unit in selected for m in unit["mentions"]}
    for unit in units:
        if unit["end"] > signal_start or any(m["mention_id"] in selected_ids for m in unit["mentions"]):
            continue
        prefix = text[max(clause_start, unit["start"] - 50):unit["start"]]
        if _REPORTED_INTRO.search(prefix):
            return [m["mention_id"] for m in unit["mentions"]]
    return []


def _reported_actor(text, clause_start, signal_start, source_id):
    """Recognize explicit lower-court actors, leaving pronouns/generic Court unknown."""
    start = max(clause_start, signal_start - 140)
    prefix = text[start:signal_start]
    for pattern in (_REPORTED_JUDGE_ACTOR, _NAMED_COURT_ACTOR):
        match = pattern.search(prefix)
        if not match:
            continue
        actor = match.group("actor")
        words = [word.casefold() for word in _WORD.findall(actor)]
        if pattern is _NAMED_COURT_ACTOR:
            if not set(words) - _GENERIC_COURT_WORDS:
                continue
            normalized = " ".join(words[1:] if words[0] == "the" else words)
            if normalized == _CURRENT_COURTS.get(source_id.split("_", 1)[0]):
                continue
        a, b = start + match.start("actor"), start + match.end("actor")
        return {"kind": "reported_actor", "start": a, "end": b, "raw": text[a:b]}
    return None


def _attribution_evidence(text, selected, rule, direction, signal_start, signal_end, actor=None):
    evidence = [{"kind": "lexical_predicate", "start": signal_start,
                 "end": signal_end, "raw": text[signal_start:signal_end]}]
    evidence.extend({"kind": "predicate_candidate", "start": unit["start"],
                     "end": unit["end"], "raw": text[unit["start"]:unit["end"]],
                     "mention_ids": [m["mention_id"] for m in unit["mentions"]],
                     "target_group_id": unit["target"]} for unit in selected)
    if actor:
        evidence.append(actor)
    return {"rule": rule, "direction": direction, "evidence": evidence}


def suggest_treatments(text: str, mentions: list[dict], *, source_id: str,
                       run_id: str, text_sha256: str) -> list[dict]:
    """Return evidence-bearing, unverified lexical suggestions; never mutate inputs."""
    mentions = _valid_mentions(text, mentions)
    quotes = _quote_ranges(text)
    observations = []
    for sentence_start, sentence_end in _sentences(text, mentions):
        sentence_text = text[sentence_start:sentence_end]
        sentence_mentions = [m for m in mentions if _overlaps(m, sentence_start, sentence_end)]
        context_flags = []
        if _PARTY.search(sentence_text):
            context_flags.append("party_submission")
        if _REPORTED.search(sentence_text):
            context_flags.append("quoted_or_reported")
        if _DISSENT.search(sentence_text):
            context_flags.append("dissent")
        for start, end in _clauses(text, sentence_start, sentence_end, sentence_mentions):
            local_mentions = [m for m in sentence_mentions if _overlaps(m, start, end)]
            candidates = sorted({target for m in local_mentions for target in _candidate_targets(m)})
            units = _mention_units(text, local_mentions, start)
            for label, pattern in _SIGNALS:
                for match in pattern.finditer(text, start, end):
                    signal_start, signal_end = match.span()
                    if any(_overlaps(m, signal_start, signal_end) for m in mentions):
                        continue
                    flags = ["experimental", "lexical_signal_only", "speaker_unattributed"] + context_flags
                    if any(a <= signal_start < b for a, b in quotes):
                        flags.append("quoted_or_reported")
                    before = text[max(start, signal_start - 75):signal_start]
                    # Limit negation to a short local window, and never infer polarity.
                    before = " ".join(before.split()[-6:])
                    negated = bool(_NEGATION.search(before))
                    if negated:
                        flags.append("negated")
                    if label in _PROCEDURAL:
                        flags.append("procedural_signal")
                    if label == "applied" and _RELIEF_APPLICATION.match(text[signal_start:min(end, signal_start + 220)]):
                        flags.append("relief_application")
                    selected, rule, direction = _predicate_targets(text, units, signal_start, signal_end, label)
                    actor = _reported_actor(text, start, signal_start, source_id) if rule == "active_object" else None
                    if actor:
                        flags.extend(("reported_actor_context", "quoted_or_reported"))
                    history_prefix = text[start:signal_start]
                    procedural_history = label in _PROCEDURAL and (
                        not history_prefix.strip() or re.search(r"[,;:(]\s*$", history_prefix))
                    if procedural_history:
                        # "Alpha, affirmed Beta" is a citation-history relation:
                        # Beta may be the affirming court's decision, not its object.
                        # Preserve both candidates instead of reversing it by guess.
                        selected, rule, direction, actor = [], "procedural_citation_history", None, None
                        flags.append("procedural_history_direction_uncertain")
                    predicate_mentions = [m for unit in selected for m in unit["mentions"]]
                    predicate_candidates = sorted({target for m in predicate_mentions for target in _candidate_targets(m)})
                    unresolved = any(_treatment_target(m) is None and not _noncase(m) for m in predicate_mentions)
                    if any(_treatment_target(m) is None and not _noncase(m) and m not in predicate_mentions for m in local_mentions):
                        flags.append("unresolved_context_mention")
                    if any(_target(m) and _treatment_target(m) is None for m in local_mentions):
                        flags.append("noncase_authority_candidate")
                    reported_ids = _reported_context(text, units, selected, start, signal_start)
                    if reported_ids:
                        flags.extend(("reported_decision_context", "quoted_or_reported"))
                    if _MODAL.search(text[max(start, signal_start - 100):signal_start]):
                        flags.append("conditional_or_modal")
                    if rule == "doctrinal_subject":
                        flags.append("doctrinal_applicability")
                    if unresolved:
                        flags.append("unresolved_target")
                    target = None
                    if len(predicate_candidates) > 1:
                        status, reason = "ambiguous", "multiple_predicate_targets"
                        flags.append("ambiguous_target")
                    elif unresolved:
                        status, reason = "ambiguous", "unresolved_predicate_mention"
                        flags.append("unresolved_target")
                    elif predicate_candidates:
                        target = predicate_candidates[0]
                        status, reason = "suggested", rule
                    elif not local_mentions:
                        status, reason = "context_required", "no_local_citation"
                        flags.append("no_local_citation")
                    else:
                        status, reason = "context_required", "procedural_citation_history" if procedural_history else "no_supported_predicate_target"
                        flags.append("candidate_only")
                        if len(candidates) > 1:
                            status = "ambiguous"
                            flags.append("ambiguous_target")
                        if any(_treatment_target(m) is None and not _noncase(m) for m in local_mentions):
                            status = "ambiguous"
                            flags.append("unresolved_target")
                    if target and any(flag in flags for flag in ("negated", "party_submission", "quoted_or_reported", "dissent", "relief_application", "conditional_or_modal", "doctrinal_applicability")):
                        status = "context_required"
                    mention_ids = [m["mention_id"] for m in local_mentions]
                    target_mention_ids = [m["mention_id"] for m in predicate_mentions if _treatment_target(m) == target] if target else []
                    observation = {
                        "source_id": source_id, "run_id": run_id, "text_sha256": text_sha256,
                        "target_group_id": target, "mention_ids": mention_ids,
                        "candidate_target_ids": candidates, "label": label, "status": status,
                        "evidence_start": start, "evidence_end": end,
                        "evidence_text": text[start:end], "signal_start": signal_start,
                        "signal_end": signal_end, "signal_text": text[signal_start:signal_end],
                        "flags": sorted(set(flags)), "method": "lexical-v2",
                        "provenance": "machine_suggestion", "assignment_reason": reason,
                        "attribution_scope": "reported_decision" if reported_ids or actor else "local_predicate" if selected else "unknown",
                        "speaker_attribution": "unknown", "negated": negated,
                        "reported_actor": actor,
                        "candidate_mention_ids": mention_ids[:],
                        "predicate_candidate_mention_ids": [m["mention_id"] for m in predicate_mentions],
                        "predicate_candidate_target_ids": predicate_candidates,
                        "target_mention_ids": target_mention_ids,
                        "context_mention_ids": [mid for mid in mention_ids if mid not in target_mention_ids],
                        "reported_context_mention_ids": reported_ids,
                        "attribution_basis": _attribution_evidence(text, selected, rule, direction, signal_start, signal_end, actor),
                    }
                    observation["observation_id"] = _stable_id("obs_", {
                        key: observation[key] for key in ("source_id", "run_id", "text_sha256", "label",
                                                         "signal_start", "signal_end", "target_group_id",
                                                         "mention_ids", "candidate_target_ids")})
                    observations.append(observation)
    return sorted(observations, key=lambda item: (item["signal_start"], item["signal_end"], item["label"]))


def summarize_edges(mentions: list[dict], observations: list[dict], *, source_id: str,
                    run_id: str) -> list[dict]:
    """Summarize supplied target groups without creating a production edge."""
    targets = sorted({_target(m) for m in mentions if _target(m)})
    summaries = []
    for target in targets:
        linked = [m for m in mentions if _target(m) == target]
        assigned = [o for o in observations if o.get("target_group_id") == target]
        ambiguous = [o for o in observations if o.get("target_group_id") is None and target in o.get("candidate_target_ids", [])]
        contextual = [o for o in observations if o.get("target_group_id") not in (None, target)
                      and target in o.get("candidate_target_ids", [])]
        mention_ids = list(dict.fromkeys(m["mention_id"] for m in linked))
        covered = sorted({mid for o in assigned for mid in _assigned_mentions(o) if mid in mention_ids})
        uncovered = [mid for mid in mention_ids if mid not in covered]
        flags = {flag for o in assigned + ambiguous for flag in o.get("flags", [])}
        flags.update(("experimental", "lexical_coverage_not_validation"))
        if uncovered:
            flags.add("unknown_treatment_for_uncovered_mentions")
        direct = [o for o in assigned if _direct(o) and not _procedural(o)]
        procedural = [o for o in assigned if _procedural(o)]
        requiring_context = [o for o in assigned if not _direct(o)]
        labels = sorted({o["label"] for o in direct})
        if len({o["label"] for o in assigned if not _procedural(o)}) > 1:
            flags.add("multiple_treatment_suggestions")
        conflicts = _label_conflicts(assigned)
        if conflicts:
            flags.add("potentially_conflicting_treatment_signals")
        mention_treatments = []
        for mid in mention_ids:
            evidence = [o for o in assigned if mid in _assigned_mentions(o)]
            candidates_for_mention = [o for o in ambiguous if mid in o.get("candidate_mention_ids", o.get("mention_ids", []))]
            context_for_mention = [o for o in contextual if mid in o.get("context_mention_ids", o.get("mention_ids", []))]
            status = ("suggested" if any(_direct(o) and not _procedural(o) for o in evidence) else
                      "context_required" if any(not _direct(o) for o in evidence) else
                      "procedural_only" if evidence else "unknown")
            mention_treatments.append({
                "mention_id": mid, "status": status,
                "observation_ids": [o["observation_id"] for o in evidence],
                "candidate_observation_ids": [o["observation_id"] for o in candidates_for_mention],
                "context_observation_ids": [o["observation_id"] for o in context_for_mention],
            })
        machine_status = ("conflicting_signals" if conflicts else
                          "suggestions_with_context" if direct and requiring_context else
                          "suggestions" if direct else
                          "context_required" if requiring_context else
                          "procedural_only" if procedural else "unknown")
        summaries.append({
            "source_id": source_id, "run_id": run_id, "target_group_id": target,
            "full_mention_count": sum(m.get("kind") == "full" for m in linked),
            "short_mention_count": sum(m.get("kind") not in ("full", "case_name") for m in linked),
            "case_name_mention_count": sum(m.get("kind") == "case_name" for m in linked),
            "mention_ids": mention_ids, "treatment_suggestions": labels,
            "context_required_labels": sorted({o["label"] for o in requiring_context}),
            "context_required_signals": [_signal_evidence(o) for o in requiring_context],
            "treatment_signals": [_signal_evidence(o) for o in direct],
            "procedural_labels": sorted({o["label"] for o in procedural}),
            "procedural_signals": [_signal_evidence(o) for o in procedural],
            "observation_ids": list(dict.fromkeys(o["observation_id"] for o in assigned)),
            "ambiguous_observation_ids": list(dict.fromkeys(o["observation_id"] for o in ambiguous)),
            "context_observation_ids": list(dict.fromkeys(o["observation_id"] for o in contextual)),
            "covered_mention_ids": covered, "uncovered_mention_ids": uncovered,
            "unknown_mention_ids": uncovered[:], "unknown_mention_count": len(uncovered),
            "mention_treatments": mention_treatments, "label_conflicts": conflicts,
            "machine_summary": {
                "status": machine_status, "provenance": "machine_suggestion",
                "treatment_evidence": [_signal_evidence(o) for o in direct],
                "context_required_evidence": [_signal_evidence(o) for o in requiring_context],
                "procedural_evidence": [_signal_evidence(o) for o in procedural],
                "candidate_evidence": [_signal_evidence(o) for o in ambiguous],
                "context_evidence": [_signal_evidence(o) for o in contextual],
                "label_conflicts": conflicts, "unknown_mention_count": len(uncovered),
            },
            "coverage_status": "no_suggestions" if not covered else "partial_suggestions" if uncovered else "suggestions_for_all_mentions",
            "identity_statuses": sorted({str(m["identity_status"]) for m in linked if m.get("identity_status") is not None}),
            "counted_edge": any(m.get("counted_edge") is True for m in linked),
            "flags": sorted(flags), "experimental": True,
        })
    return summaries


def _assigned_mentions(observation):
    # Support existing v1 observations when callers summarize an older package.
    return observation.get("target_mention_ids", observation.get("mention_ids", []))


def _procedural(observation):
    return observation.get("label") in _PROCEDURAL or "procedural_signal" in observation.get("flags", [])


def _direct(observation):
    return (observation.get("status") == "suggested" and not observation.get("negated")
            and "negated" not in observation.get("flags", []))


def _signal_evidence(observation):
    return {
        "observation_id": observation["observation_id"], "label": observation["label"],
        "target_group_id": observation.get("target_group_id"),
        "status": observation.get("status"), "negated": observation.get("negated", False),
        "flags": observation.get("flags", []),
        "signal_start": observation.get("signal_start"), "signal_end": observation.get("signal_end"),
        "signal_text": observation.get("signal_text"),
        "mention_ids": list(_assigned_mentions(observation)) if observation.get("target_group_id") else [],
        "candidate_mention_ids": observation.get("candidate_mention_ids", observation.get("mention_ids", [])),
        "assignment_reason": observation.get("assignment_reason"),
        "attribution_scope": observation.get("attribution_scope", "unknown"),
        "reported_actor": observation.get("reported_actor"),
        "provenance": "machine_suggestion",
    }


def _label_conflicts(observations):
    """Expose potentially different directions/polarities without resolving them."""
    substantive = [o for o in observations if not _procedural(o)]
    positive = [o for o in substantive if not o.get("negated") and "negated" not in o.get("flags", [])]
    supportive = [o for o in positive if o["label"] in ("applied", "followed", "adopted")]
    adverse = [o for o in positive if o["label"] in ("distinguished", "criticized", "overruled")]
    conflicts = []
    if supportive and adverse:
        evidence = supportive + adverse
        conflicts.append({"reason": "different_lexical_treatment_directions", "requires_context": True,
                          "labels": sorted({o["label"] for o in evidence}),
                          "observation_ids": list(dict.fromkeys(o["observation_id"] for o in evidence))})
    for label in sorted({o["label"] for o in substantive}):
        evidence = [o for o in substantive if o["label"] == label]
        polarities = {bool(o.get("negated") or "negated" in o.get("flags", [])) for o in evidence}
        if len(polarities) > 1:
            conflicts.append({"reason": "mixed_signal_polarity", "requires_context": True,
                              "labels": [label], "observation_ids": [o["observation_id"] for o in evidence]})
    return conflicts
