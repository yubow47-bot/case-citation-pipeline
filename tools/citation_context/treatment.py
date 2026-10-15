"""Experimental lexical cues, never verified treatment or human review labels.

Offsets are Python Unicode string offsets into the unchanged input. One observation
is emitted per cue, including cues with no uniquely supported citation target.
Sentence/clause boundaries, negation and attribution are deliberately small lexical
heuristics, not a parser. Signals inside supplied citation spans are ignored.

Clause membership supplies candidates, never a target by itself. Small directional
rules recognize a predicate's object or passive subject, including source-seeded
case-name mentions. Candidate, target and contextual mention IDs remain distinct.
Attribution evidence preserves the exact original spans used by each rule. Explicit
speakers and bounded reporting contexts are kept separate from the evaluated case;
unresolved speakers remain unknown. Edge summaries keep every evidence item and possible
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

from tools.citation_context.scopes import (quotation_scopes, quote_scope_at,
                                            quote_scope_evidence)


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
_SENTENCE = re.compile(r'[.!?]["”»]{0,3}(?=\s+(?:[A-ZÀ-ÖØ-Þ\d]|["“«])|$)|\n[ \t]*\n|\n(?=[ \t]*(?:\[\d{1,5}\]|\d{1,3}[.)]?[ \t]+(?=[A-ZÀ-ÖØ-Þ])))')
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
    r"(?:\s+for\s+(?:[^\W\d_]+\s+){0,4}[^\W\d_]+)?"
    r"(?:\s+(?:set\s+out|stated|enunciated|established|articulated|described|expressed))?"
    r"(?:\s+by\s+(?:the\s+)?(?:Supreme\s+Court\s+of\s+Canada|Court\s+of\s+Appeal|Court))?"
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
_REPORTED_INTRO = re.compile(r"(?:^|[,;:]\s*|\b(?:example|exemple)\s*,\s*|\b(?:this|the|our)\s+court\s+)(?:in|dans)\s*$", re.I)
_ACTOR_BRIDGE = r"\s+(?:(?:has|have|had|did|does|would|will|should|could|can|may|must|was|were|is|are|able\s+to|to|not|never|also|then|first|now|here|therefore|accordingly|previously|recently|expressly|directly|subsequently|consistently)\s+){0,5}"
_CAPITALIZED_WORD = r"[A-ZÀ-ÖØ-Þ][\w'’\-]*"
_NAMED_COURT_ACTOR = re.compile(
    r"(?<!\w)(?P<actor>(?:(?:the|The)\s+)?(?:" + _CAPITALIZED_WORD +
    r"\s+){1,5}Court(?:\s+of\s+" + _CAPITALIZED_WORD +
    r"(?:\s+" + _CAPITALIZED_WORD + r"){0,2})?)" + _ACTOR_BRIDGE + r"$")
_REPORTED_JUDGE_ACTOR = re.compile(
    r"(?<!\w)(?P<actor>(?:the\s+)?(?:trial|motions?|application|lower|appeal|appellate|chambers)\s+judge)" +
    _ACTOR_BRIDGE + r"$", re.I)
_REPORTED_JUDGE_GERUND = re.compile(
    r"(?<!\w)(?P<actor>(?:the\s+)?(?:trial|motions?|application|lower|appeal|appellate|chambers)\s+judge)"
    r"\s+(?:concluded|began|completed)\s+(?:his|her|the)\s+analysis\s+by\s+$", re.I)
_REPORTED_COURT_ERROR = re.compile(
    r"(?<!\w)(?P<actor>(?:the\s+)?(?:majority|minority)\s+of\s+(?:the\s+)?Court\s+of\s+Appeal)"
    r"\s+erred\s+in\s+$", re.I)
_NAMED_JUDGE_ACTOR = re.compile(
    r"(?<!\w)(?P<actor>(?:Mr\.?\s+Justice\s+" + _CAPITALIZED_WORD +
    r"|" + _CAPITALIZED_WORD + r"\s+(?:J\.A\.|C\.J\.C\.|C\.J\.|J\.)))" +
    _ACTOR_BRIDGE + r"$")
_CURRENT_ACTOR = re.compile(
    r"(?<!\w)(?P<actor>I|we|nous|je|this\s+Court|our\s+Court|notre\s+Cour|la\s+présente\s+Cour)" +
    _ACTOR_BRIDGE + r"$", re.I)
_PRONOUN_ACTOR = re.compile(
    r"(?<!\w)(?P<actor>he|she|it|they|some|others|il|elle|ils|elles)" +
    _ACTOR_BRIDGE + r"$", re.I)
_PARTY_ACTOR = re.compile(
    r"(?<!\w)(?P<actor>(?:(?:the|a|an|le|la|les)\s+)?(?:appellant|respondent|plaintiff|defendant|applicant|counsel|party|parties|appelant\w*|intimé\w*|demandeur\w*|défendeur\w*|avocat\w*))" +
    _ACTOR_BRIDGE + r"$", re.I)
_LOWER_COURT_ACTOR = re.compile(
    r"(?<!\w)(?P<actor>(?:the\s+)?(?:trial|lower|appellate|appeal)\s+court)" +
    _ACTOR_BRIDGE + r"$", re.I)
_POST_ACTOR = re.compile(
    r"\s*,\s*(?P<actor>he|she|it|they|I|we|the\s+(?:Supreme\s+Court(?:\s+of\s+Canada)?|Court|trial\s+judge|motion\s+judge))"
    r"\s+(?:(?:also|then|further|expressly|had|has)\s+){0,3}(?:held|noted|said|stated|concluded|found|observed)\b", re.I)
_OTHER_REASONING = re.compile(r"\b(?P<actor>(?:his|her|their|its)\s+(?:reasons|analysis|judgment|decision))\b[^.;]{0,100}?\b(?:in|to)\s*$", re.I)
_INDIRECT_ACTOR = re.compile(r"\b(?P<actor>him|her|them)\s+to\s*$", re.I)
_CASE_SUBJECT_REPORT = re.compile(r"\s+(?:involved|concerned|dealt\s+with|addressed|arose|held|stated|decided|said|explained)\b", re.I)
_HISTORICAL_CASE = re.compile(r"\b(?:in|dans)\s+(?:(?:the|le|la)\s+)?(?:\d{4}\s+)?(?:case|decision|judgment|arrêt)\s+(?:of|in|de)\s*$", re.I)
_QUOTE_INTRO = re.compile(r"\b(?:said|stated|held|wrote|explained|observed|noted|quoted|quoting|following\s+(?:passage|analysis|words)|as\s+follows|déclaré|écrit|suivant)\b", re.I)
# The selected corpus stores each extracted paragraph on one line.
_PARAGRAPH = re.compile(r"\r?\n")
_SPEAKER_RESET = re.compile(r"\b(?:I|we|nous|je|this\s+Court|our\s+Court|the\s+(?:appellant|respondent|applicant|trial\s+judge|motion\s+judge))\s+(?:(?:now|here|therefore|accordingly|also)\s+){0,2}(?:apply|follow|adopt|distinguish|consider|discuss|conclude|find|hold|submit|argue|would|will|must|have|are|am)\b", re.I)
_ATTEMPTED_ACTION = re.compile(r"\befforts\b[^.;!?]{0,100}\bto\b[^.;!?]{0,100}$", re.I)
_REJECTED_APPLICATION = re.compile(
    r"\s+(?:[\w'’\-]+\s+){0,3}(?:approach|test|rule|principle|reasoning|framework)"
    r"\s+(?:is|would\s+be)\s+not\s+(?:analytically\s+)?sound\b", re.I)
_SUGGESTED_ERROR = re.compile(r"\b(?:the\s+)?suggestion\s+that\b[^.;!?\n]{0,140}\berred\s+in\s*$", re.I)
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


def _name_start(text, mention, clause_start):
    """Include a supplied case title immediately preceding a citation-only span."""
    start = mention["start"]
    if mention.get("kind") != "full":
        return start
    for evidence in mention.get("source_aliases", []):
        a, b = evidence.get("start"), evidence.get("end")
        if (isinstance(a, int) and isinstance(b, int) and clause_start <= a < b <= start
                and start - b <= 60 and _PUNCTUATION_GAP.fullmatch(text[b:start])):
            # Supplied local-title spans can include an introductory court
            # phrase. Keep that phrase available as reporting evidence rather
            # than swallowing it into the grammatical case-name unit.
            introduction = re.match(r"(?:this|the|our)\s+Court\s+(?:in|dans)\s+", text[a:b], re.I)
            if introduction:
                a += introduction.end()
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


def _span_evidence(text, kind, start, end, **extra):
    return {"kind": kind, "start": start, "end": end, "raw": text[start:end], **extra}


def _scope_id(position, scopes):
    scope = quote_scope_at(position, scopes)
    return scope["scope_id"] if scope else None


def _reporting_seeds(text, mentions, sentences, scopes):
    """Explicit source cases, bounded to a paragraph and quotation voice.

    A source case is not a treatment target just because it introduces a passage.
    Ambiguous names and differing parallel targets retain their candidates without
    choosing an owner. No nearest-citation fallback is used.
    """
    paragraph_ends = [m.start() for m in _PARAGRAPH.finditer(text)] + [len(text)]
    seeds = []
    for a, b in sentences:
        units = _mention_units(text, [m for m in mentions if _overlaps(m, a, b)], a)
        for index, unit in enumerate(units):
            if all(_noncase(m) for m in unit["mentions"]):
                continue
            unit_scope = quote_scope_at(unit["start"], scopes)
            prefix_start = max(a, unit["start"] - 100)
            if unit_scope:
                prefix_start = max(prefix_start, unit_scope["content_start"])
            prefix = text[prefix_start:unit["start"]]
            prefix = re.sub(r'^\s*["“«]?\s*(?:\[\d{1,5}\]|\d{1,3}\.?)?\s*', "", prefix)
            historical = _HISTORICAL_CASE.search(prefix)
            introduction = _REPORTED_INTRO.search(prefix) or historical
            subject_report = (not prefix.strip(' \t\r\n"“«') and
                              _CASE_SUBJECT_REPORT.match(text, unit["end"], min(b, unit["end"] + 80)))
            if not introduction and not subject_report:
                continue
            source_units = [unit]
            for following in units[index + 1:]:
                gap = text[source_units[-1]["end"]:following["start"]]
                coordinated = re.search(r"\b(?:and|or|et|ou)\b|&", gap, re.I)
                parallel = all(m.get("kind") == "full" and re.match(r"\[?\d{4}\b", m["raw"])
                               for m in following["mentions"])
                if (len(gap) > 80 or not _LIST_GAP.fullmatch(gap) or
                        not (coordinated or parallel) or
                        _scope_id(following["start"], scopes) != _scope_id(unit["start"], scopes)):
                    break
                source_units.append(following)
            source_mentions = [m for item in source_units for m in item["mentions"]]
            targets = sorted({target for m in source_mentions for target in _candidate_targets(m)})
            linked = {_treatment_target(m) for m in source_mentions}
            target = next(iter(linked)) if len(linked) == 1 and None not in linked else None
            # The introduction itself is exact evidence, including the case name.
            evidence_start = unit["start"]
            if introduction:
                evidence_start = unit["start"] - len(prefix) + introduction.start()
            evidence_end = source_units[-1]["end"]
            mention_ids = [m["mention_id"] for m in source_mentions]
            seeds.append({
                "start": evidence_start, "end": evidence_end,
                "sentence_end": b,
                "paragraph_end": next(end for end in paragraph_ends if end >= evidence_end),
                "scope_id": _scope_id(unit["start"], scopes), "target_group_id": target,
                "mention_ids": mention_ids, "candidate_target_ids": targets,
                "evidence": _span_evidence(text, "reported_case_introduction", evidence_start, evidence_end,
                                           mention_ids=mention_ids, target_group_id=target),
                "rule": "historical_case_introduction" if historical else "explicit_case_introduction" if introduction else "case_subject_report",
            })
    return sorted(seeds, key=lambda item: (item["end"], item["start"]))


def _quotation_owners(text, scopes, seeds):
    """A colon introduction may own a balanced quote across a paragraph break.

    Nested quotations need their own explicit introduction. Outer ownership is
    never silently transferred to a different quoted author.
    """
    owners = {}
    for scope in scopes:
        opening = scope["start"]
        eligible = []
        for seed in seeds:
            if not 0 <= opening - seed["end"] <= 1000 or seed["scope_id"] != scope.get("parent_scope_id"):
                continue
            tail = text[seed["end"]:opening]
            before_colon = tail[:tail.rfind(":")]
            masked = _ABBREVIATION.sub(lambda match: match.group()[:-1] + " ", before_colon)
            if (not re.search(r":\s*$", tail) or _SPEAKER_RESET.search(tail) or
                    _PARAGRAPH.search(before_colon) or _SENTENCE.search(masked) or
                    not (_QUOTE_INTRO.search(tail) or re.fullmatch(r"[\s,;:()[\]\d.\-–—]*", tail))):
                continue
            eligible.append(seed)
        if eligible:
            owners[scope["scope_id"]] = eligible[-1]
    return owners


def _owner_at(text, signal_start, signal_end, selected, seeds, scope, quote_owners):
    selected_ids = {m["mention_id"] for unit in selected for m in unit["mentions"]}
    scope_id = scope["scope_id"] if scope else None
    eligible = [seed for seed in seeds if seed["scope_id"] == scope_id and
                0 <= signal_start - seed["end"] <= 2400 and signal_start <= seed["paragraph_end"] and
                not selected_ids.intersection(seed["mention_ids"])]
    if eligible:
        seed = eligible[-1]
        resets = _SPEAKER_RESET.finditer(text[seed["end"]:signal_end])
        if not any(seed["end"] + match.start() >= seed["sentence_end"] for match in resets):
            return seed
    return quote_owners.get(scope_id) if scope else None


def _actor_context(text, clause_start, signal_start, signal_end, selected, source_id):
    """Identify explicit syntax; pronouns supply a guard, never a guessed identity."""
    start = max(clause_start, signal_start - 180)
    prefix = text[start:signal_start]
    current_name = _CURRENT_COURTS.get(source_id.split("_", 1)[0])
    for pattern, speaker in ((_REPORTED_JUDGE_ACTOR, "reported_judge"),
                             (_REPORTED_JUDGE_GERUND, "reported_judge"),
                             (_REPORTED_COURT_ERROR, "reported_court"),
                             (_NAMED_JUDGE_ACTOR, "reported_judge"),
                             (_LOWER_COURT_ACTOR, "reported_court"),
                             (_NAMED_COURT_ACTOR, "reported_court"),
                             (_PARTY_ACTOR, "party"), (_CURRENT_ACTOR, "current_court"),
                             (_PRONOUN_ACTOR, "unknown"), (_OTHER_REASONING, "unknown"),
                             (_INDIRECT_ACTOR, "unknown")):
        match = pattern.search(prefix)
        if not match:
            continue
        words = [word.casefold() for word in _WORD.findall(match.group("actor"))]
        if pattern is _NAMED_COURT_ACTOR:
            normalized = " ".join(words[1:] if words[0] == "the" else words)
            if normalized == current_name:
                speaker = "current_court"
            elif not set(words) - _GENERIC_COURT_WORDS:
                continue
        a, b = start + match.start("actor"), start + match.end("actor")
        return speaker, _span_evidence(text, "speaker" if speaker == "current_court" else "reported_actor", a, b)
    # Fronted participles put the actor after the treatment object.
    if selected and text[signal_start:signal_end].casefold().endswith("ing"):
        end = max(unit["end"] for unit in selected)
        match = _POST_ACTOR.match(text[end:min(len(text), end + 180)])
        if match:
            a, b = end + match.start("actor"), end + match.end("actor")
            actor = text[a:b].casefold()
            speaker = "current_court" if actor in ("i", "we") else "reported_court" if "court" in actor else "reported_judge" if "judge" in actor else "unknown"
            return speaker, _span_evidence(text, "speaker" if speaker == "current_court" else "reported_actor", a, b)
    return "unknown", None


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
                       run_id: str, text_sha256: str, quote_scopes=None) -> list[dict]:
    """Return evidence-bearing, unverified lexical suggestions; never mutate inputs."""
    mentions = _valid_mentions(text, mentions)
    scopes = quotation_scopes(text) if quote_scopes is None else quote_scopes
    sentences = list(_sentences(text, mentions))
    reporting_seeds = _reporting_seeds(text, mentions, sentences, scopes)
    quote_owners = _quotation_owners(text, scopes, reporting_seeds)
    observations = []
    for sentence_start, sentence_end in sentences:
        sentence_text = text[sentence_start:sentence_end]
        sentence_mentions = [m for m in mentions if _overlaps(m, sentence_start, sentence_end)]
        context_flags = []
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
                    flags = ["experimental", "lexical_signal_only"] + context_flags
                    scope = quote_scope_at(signal_start, scopes)
                    if scope:
                        flags.append("quoted_or_reported")
                        if scope.get("uncertain"):
                            flags.append("quotation_scope_uncertain")
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
                    if any(_scope_id(unit["start"], scopes) != (scope["scope_id"] if scope else None) for unit in selected):
                        selected, rule, direction = [], "no_supported_predicate_target", None
                        flags.append("quotation_target_scope_mismatch")
                    speaker, actor = _actor_context(text, start, signal_start, signal_end, selected, source_id)
                    history_prefix = text[start:signal_start]
                    procedural_history = label in _PROCEDURAL and (
                        not history_prefix.strip() or re.search(r"[,;:(]\s*$", history_prefix))
                    if procedural_history:
                        # "Alpha, affirmed Beta" is a citation-history relation:
                        # Beta may be the affirming court's decision, not its object.
                        # Preserve both candidates instead of reversing it by guess.
                        selected, rule, direction = [], "procedural_citation_history", None
                        flags.append("procedural_history_direction_uncertain")
                    predicate_mentions = [m for unit in selected for m in unit["mentions"]]
                    predicate_candidates = sorted({target for m in predicate_mentions for target in _candidate_targets(m)})
                    unresolved = any(_treatment_target(m) is None and not _noncase(m) for m in predicate_mentions)
                    if any(_treatment_target(m) is None and not _noncase(m) and m not in predicate_mentions for m in local_mentions):
                        flags.append("unresolved_context_mention")
                    if any(_target(m) and _treatment_target(m) is None for m in local_mentions):
                        flags.append("noncase_authority_candidate")
                    owner = _owner_at(text, signal_start, signal_end, selected, reporting_seeds, scope, quote_owners)
                    # An explicit new voice stops narrative ownership. Inside a
                    # quotation, "we" is the quoted author's voice, not ours.
                    if (owner and not scope and actor and actor["start"] >= owner["end"] and
                            speaker in ("current_court", "party") and
                            (sentence_start >= owner["sentence_end"] or start > owner["end"] or
                             re.search(r"\b(?:now|here|in\s+this\s+case|present\s+appeal)\b", text[owner["end"]:signal_start], re.I))):
                        owner = None
                    # Historical source cases can follow the target, as in
                    # "applied Alpha in the 1973 case of Beta".
                    if not owner:
                        selected_ids = {m["mention_id"] for unit in selected for m in unit["mentions"]}
                        owner = next((seed for seed in reporting_seeds if seed["start"] >= signal_end and
                                      seed["end"] <= end and seed["scope_id"] == (scope["scope_id"] if scope else None) and
                                      not selected_ids.intersection(seed["mention_ids"]) and
                                      seed["rule"] == "historical_case_introduction"), None)
                    reported_ids = owner["mention_ids"][:] if owner else []
                    if owner:
                        flags.extend(("reported_decision_context", "quoted_or_reported"))
                    # Party/reporting cues are local to this clause and voice.
                    # A later "but we applied ..." does not inherit them.
                    context_start = max(start, scope["content_start"]) if scope else start
                    prefix = text[context_start:signal_start]
                    party_match = _PARTY.search(prefix)
                    if party_match:
                        flags.append("party_submission")
                        speaker = "party"
                        actor = _span_evidence(text, "party_submission", context_start + party_match.start(), context_start + party_match.end())
                    elif speaker == "party":
                        flags.append("party_submission")
                    if _REPORTED.search(prefix):
                        flags.append("quoted_or_reported")
                    if actor and speaker not in ("current_court", "party"):
                        flags.extend(("reported_actor_context", "quoted_or_reported"))
                        if speaker == "unknown":
                            flags.append("unresolved_actor")
                    if owner and speaker not in ("reported_court", "reported_judge", "party"):
                        speaker = "reported_case" if owner["target_group_id"] else "unknown"
                    if scope:
                        # Even an explicit I/we inside a quote cannot identify
                        # the current court as that passage's speaker.
                        speaker = "reported_case" if owner and owner["target_group_id"] else "unknown"
                    if speaker == "unknown":
                        flags.append("speaker_unattributed")
                    if _MODAL.search(text[max(start, signal_start - 100):signal_start]):
                        flags.append("conditional_or_modal")
                    attempted = _ATTEMPTED_ACTION.search(text[max(start, signal_start - 180):signal_start])
                    if attempted:
                        flags.append("attempted_action_context")
                    selected_end = max((unit["end"] for unit in selected), default=signal_end)
                    rejection = (_REJECTED_APPLICATION.match(text, selected_end, min(end, selected_end + 140))
                                 if label == "applied" and selected and text[signal_start:signal_end].casefold() == "applying" else None)
                    if rejection and _PARAGRAPH.search(text[signal_start:rejection.end()]):
                        rejection = None
                    if rejection:
                        flags.append("rejected_application_context")
                    suggested_error = _SUGGESTED_ERROR.search(text[max(start, signal_start - 180):signal_start])
                    if suggested_error:
                        flags.append("alleged_error_context")
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
                    if target and any(flag in flags for flag in ("negated", "party_submission", "quoted_or_reported", "dissent", "relief_application", "conditional_or_modal", "doctrinal_applicability", "attempted_action_context", "rejected_application_context", "alleged_error_context")):
                        status = "context_required"
                    mention_ids = [m["mention_id"] for m in local_mentions]
                    target_mention_ids = [m["mention_id"] for m in predicate_mentions if _treatment_target(m) == target] if target else []
                    context_ids = list(dict.fromkeys([mid for mid in mention_ids if mid not in target_mention_ids] + reported_ids))
                    speaker_evidence = [owner["evidence"]] if owner and speaker == "reported_case" else [actor] if actor else []
                    ownership_basis = {"rule": owner["rule"], "evidence": [owner["evidence"]]} if owner else None
                    attribution_basis = _attribution_evidence(text, selected, rule, direction, signal_start, signal_end, actor)
                    if attempted:
                        a = max(start, signal_start - 180) + attempted.start()
                        attribution_basis["evidence"].append(_span_evidence(text, "attempted_action_context", a, signal_end))
                    if rejection:
                        attribution_basis["evidence"].append(_span_evidence(text, "rejected_application_context", signal_start, rejection.end()))
                    if suggested_error:
                        a = max(start, signal_start - 180) + suggested_error.start()
                        attribution_basis["evidence"].append(_span_evidence(text, "alleged_error_context", a, signal_end))
                    if owner:
                        attribution_basis["evidence"].append(owner["evidence"])
                    observation = {
                        "source_id": source_id, "run_id": run_id, "text_sha256": text_sha256,
                        "target_group_id": target, "mention_ids": mention_ids,
                        "candidate_target_ids": candidates, "label": label, "status": status,
                        "evidence_start": start, "evidence_end": end,
                        "evidence_text": text[start:end], "signal_start": signal_start,
                        "signal_end": signal_end, "signal_text": text[signal_start:signal_end],
                        "flags": sorted(set(flags)), "method": "lexical-v3",
                        "provenance": "machine_suggestion", "assignment_reason": reason,
                        "attribution_scope": "quoted_statement" if scope else "party_submission" if "party_submission" in flags else "reported_decision" if owner or "reported_actor_context" in flags else "local_predicate" if selected else "unknown",
                        "speaker_attribution": speaker, "speaker_evidence": speaker_evidence,
                        "context_owner_group_id": owner["target_group_id"] if owner else None,
                        "context_owner_mention_ids": reported_ids,
                        "context_owner_candidate_target_ids": owner["candidate_target_ids"][:] if owner else [],
                        "context_owner_basis": ownership_basis,
                        "quote_scope": quote_scope_evidence(scope) if scope else None,
                        "negated": negated,
                        "reported_actor": actor if actor and actor["kind"] != "speaker" else None,
                        "candidate_mention_ids": mention_ids[:],
                        "predicate_candidate_mention_ids": [m["mention_id"] for m in predicate_mentions],
                        "predicate_candidate_target_ids": predicate_candidates,
                        "target_mention_ids": target_mention_ids,
                        "context_mention_ids": context_ids,
                        "reported_context_mention_ids": reported_ids,
                        "attribution_basis": attribution_basis,
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
        reported_sources = [o for o in observations if o.get("context_owner_group_id") == target]
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
            "reported_source_observation_ids": [o["observation_id"] for o in reported_sources],
            "reported_source_signals": [_signal_evidence(o) for o in reported_sources],
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
                "reported_source_evidence": [_signal_evidence(o) for o in reported_sources],
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
        "speaker_attribution": observation.get("speaker_attribution", "unknown"),
        "speaker_evidence": observation.get("speaker_evidence", []),
        "context_owner_group_id": observation.get("context_owner_group_id"),
        "context_owner_mention_ids": observation.get("context_owner_mention_ids", []),
        "context_owner_candidate_target_ids": observation.get("context_owner_candidate_target_ids", []),
        "context_owner_basis": observation.get("context_owner_basis"),
        "quote_scope": observation.get("quote_scope"),
        "attribution_basis": observation.get("attribution_basis"),
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
