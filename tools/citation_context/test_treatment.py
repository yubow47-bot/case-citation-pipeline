"""Small offline treatment contracts: offsets, abstention and uncertainty."""
import copy
import hashlib
import unittest

from tools.citation_context.treatment import suggest_treatments, summarize_edges


def mention(text, raw, target="case-a", *, mid="m1", kind="full", start=0, **extra):
    position = text.index(raw, start)
    return {"mention_id": mid, "start": position, "end": position + len(raw),
            "raw": raw, "kind": kind, "target_group_id": target,
            "resolution_status": "resolved" if target else "unresolved",
            "identity_status": "heuristic", "counted_edge": kind == "full", **extra}


def suggest(text, mentions):
    return suggest_treatments(text, mentions, source_id="source", run_id="run",
                              text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())


class TreatmentTests(unittest.TestCase):
    def test_unicode_offsets_and_determinism(self):
        text = "Énoncé ⚖. Nous avons appliqué École, 2020 ABC 1."
        mentions = [mention(text, "École, 2020 ABC 1")]
        frozen = copy.deepcopy(mentions)
        observations = suggest(text, mentions)
        self.assertEqual(observations, suggest(text, mentions))
        self.assertEqual(mentions, frozen)
        self.assertEqual(len(observations), 1)
        observation = observations[0]
        self.assertEqual(observation["label"], "applied")
        self.assertEqual(observation["target_group_id"], "case-a")
        for prefix in ("signal", "evidence"):
            self.assertEqual(text[observation[prefix + "_start"]:observation[prefix + "_end"]], observation[prefix + "_text"])

    def test_multiple_targets_abstain_in_citation_list(self):
        text = "We followed Alpha and Beta."
        mentions = [mention(text, "Alpha"), mention(text, "Beta", "case-b", mid="m2")]
        observation, = suggest(text, mentions)
        self.assertEqual(observation["status"], "ambiguous")
        self.assertIsNone(observation["target_group_id"])
        self.assertEqual(observation["candidate_target_ids"], ["case-a", "case-b"])

    def test_separate_local_clauses_and_coordinated_predicates(self):
        for separator in ("; ", " and ", ", but "):
            text = "We applied Alpha" + separator + "distinguished Beta."
            mentions = [mention(text, "Alpha"), mention(text, "Beta", "case-b", mid="m2")]
            observations = suggest(text, mentions)
            self.assertEqual([(o["label"], o["target_group_id"]) for o in observations],
                             [("applied", "case-a"), ("distinguished", "case-b")])

    def test_no_cross_sentence_or_semicolon_attachment(self):
        for separator in (". ", "; "):
            text = "See Alpha" + separator + "We applied the test."
            observation, = suggest(text, [mention(text, "Alpha")])
            self.assertIsNone(observation["target_group_id"])
            self.assertEqual(observation["assignment_reason"], "no_local_citation")

    def test_unresolved_short_prevents_unique_target_assignment(self):
        text = "We followed Alpha and ibid."
        mentions = [mention(text, "Alpha"), mention(text, "ibid.", None, mid="m2", kind="short")]
        observation, = suggest(text, mentions)
        self.assertIsNone(observation["target_group_id"])
        self.assertEqual(observation["status"], "ambiguous")
        self.assertIn("unresolved_target", observation["flags"])

    def test_short_resolution_must_be_explicit(self):
        text = "We followed Alpha."
        observation, = suggest(text, [mention(text, "Alpha", kind="short", resolution_status="ambiguous")])
        self.assertIsNone(observation["target_group_id"])

    def test_context_flags_require_review(self):
        examples = [
            ("The appellant submits that Alpha should be followed.", "party_submission"),
            ('The court wrote: “We followed Alpha.”', "quoted_or_reported"),
            ("In dissent, I followed Alpha.", "dissent"),
            ("We did not follow Alpha.", "negated"),
            ("Nous n’avons pas suivi Alpha.", "negated"),
        ]
        for text, flag in examples:
            with self.subTest(flag=flag):
                observation, = suggest(text, [mention(text, "Alpha")])
                self.assertIn(flag, observation["flags"])
                self.assertEqual(observation["status"], "context_required")
                self.assertEqual(observation["target_group_id"], "case-a")
                summary, = summarize_edges([mention(text, "Alpha")], [observation], source_id="source", run_id="run")
                self.assertEqual(summary["treatment_suggestions"], [])
                self.assertEqual(summary["context_required_labels"], [observation["label"]])
                self.assertEqual(summary["context_required_signals"][0]["observation_id"], observation["observation_id"])

    def test_parallel_citations_do_not_duplicate_signal(self):
        text = "We followed Alpha, 2020 ABC 1, [2020] 1 SCR 2."
        mentions = [mention(text, "2020 ABC 1"), mention(text, "[2020] 1 SCR 2", mid="m2")]
        observation, = suggest(text, mentions)
        self.assertEqual(observation["mention_ids"], ["m1", "m2"])

    def test_neutral_only_anchor_retains_attribution_before_case_title(self):
        text = "The appellant submits that R. v. Smith, 2001 SCC 2 should be followed."
        observation, = suggest(text, [mention(text, "2001 SCC 2")])
        self.assertEqual(observation["status"], "context_required")
        self.assertIn("party_submission", observation["flags"])

    def test_numbered_paragraph_stops_previous_signal_attachment(self):
        for label in ("[77]", "77", "77."):
            text = "We considered hardship.\n" + label + " Smith, 2001 SCC 2 concerned another issue."
            observation, = suggest(text, [mention(text, "2001 SCC 2")])
            self.assertIsNone(observation["target_group_id"])
            self.assertEqual(observation["mention_ids"], [])

    def test_relief_application_is_context_required(self):
        for application in ("applied in Washington to have the action dismissed",
                            "applied for an injunction", "applied to the Supreme Court"):
            text = "In Alpha, TCML " + application + "."
            observation, = suggest(text, [mention(text, "Alpha")])
            self.assertEqual(observation["status"], "context_required")
            self.assertIn("relief_application", observation["flags"])
            summary, = summarize_edges([mention(text, "Alpha")], [observation], source_id="source", run_id="run")
            self.assertEqual(summary["treatment_suggestions"], [])

    def test_mixed_and_procedural_labels_and_unknown_coverage(self):
        text = "We applied Alpha. Later, Alpha was distinguished. Alpha was affirmed. See Alpha."
        mentions = []
        cursor = 0
        for number in range(4):
            current = mention(text, "Alpha", mid="m" + str(number), start=cursor)
            mentions.append(current)
            cursor = current["end"]
        observations = suggest(text, mentions)
        summary, = summarize_edges(mentions, observations, source_id="source", run_id="run")
        self.assertEqual(summary["treatment_suggestions"], ["applied", "distinguished"])
        self.assertEqual(summary["procedural_labels"], ["affirmed"])
        self.assertEqual(summary["procedural_signals"][0]["label"], "affirmed")
        self.assertEqual(summary["coverage_status"], "partial_suggestions")
        self.assertEqual(summary["uncovered_mention_ids"], ["m3"])
        self.assertTrue(summary["counted_edge"])
        self.assertIn("procedural_signal", summary["flags"])
        self.assertTrue(summary["experimental"])
        self.assertNotIn("confidence", summary)
        self.assertEqual(summary["unknown_mention_count"], 1)
        self.assertEqual(summary["machine_summary"]["status"], "conflicting_signals")
        self.assertEqual(summary["label_conflicts"][0]["labels"], ["applied", "distinguished"])

    def test_reported_case_is_context_and_named_passive_subject_is_target(self):
        text = "For example, in R. v. Loyer, [1978] 2 S.C.R. 631, Kienapple was applied to bar convictions."
        mentions = [mention(text, "[1978] 2 S.C.R. 631", case_name="R. v. Loyer"),
                    mention(text, "Kienapple", "case-k", mid="m2", kind="case_name")]
        observation, = suggest(text, mentions)
        self.assertEqual(observation["target_group_id"], "case-k")
        self.assertEqual(observation["candidate_target_ids"], ["case-a", "case-k"])
        self.assertEqual(observation["target_mention_ids"], ["m2"])
        self.assertEqual(observation["context_mention_ids"], ["m1"])
        self.assertEqual(observation["reported_context_mention_ids"], ["m1"])
        self.assertEqual(observation["attribution_basis"]["rule"], "passive_subject")
        self.assertEqual(observation["attribution_scope"], "reported_decision")
        self.assertEqual(observation["status"], "context_required")
        for evidence in observation["attribution_basis"]["evidence"]:
            self.assertEqual(text[evidence["start"]:evidence["end"]], evidence["raw"])
        summaries = {row["target_group_id"]: row for row in summarize_edges(mentions, [observation], source_id="source", run_id="run")}
        self.assertEqual(summaries["case-a"]["covered_mention_ids"], [])
        self.assertEqual(summaries["case-a"]["unknown_mention_count"], 1)
        self.assertEqual(summaries["case-a"]["context_observation_ids"], [observation["observation_id"]])
        self.assertEqual(summaries["case-k"]["covered_mention_ids"], ["m2"])
        self.assertEqual(summaries["case-k"]["case_name_mention_count"], 1)
        self.assertEqual(summaries["case-k"]["short_mention_count"], 0)

    def test_lone_context_citation_is_not_a_predicate_target(self):
        text = "In R. v. Loyer, [1978] 2 S.C.R. 631, Kienapple was applied to bar convictions."
        observation, = suggest(text, [mention(text, "[1978] 2 S.C.R. 631", case_name="R. v. Loyer")])
        self.assertIsNone(observation["target_group_id"])
        self.assertEqual(observation["assignment_reason"], "no_supported_predicate_target")
        self.assertEqual(observation["target_mention_ids"], [])
        self.assertEqual(observation["candidate_mention_ids"], ["m1"])

    def test_direction_selects_active_object_over_cited_subject(self):
        text = "Alpha followed Beta."
        mentions = [mention(text, "Alpha"), mention(text, "Beta", "case-b", mid="m2")]
        observation, = suggest(text, mentions)
        self.assertEqual(observation["target_group_id"], "case-b")
        self.assertEqual(observation["target_mention_ids"], ["m2"])
        self.assertEqual(observation["attribution_basis"]["rule"], "active_object")

    def test_procedural_relative_does_not_inherit_named_principle(self):
        text = "The Court applied the Kienapple principle to the convictions, which were upheld on appeal."
        mentions = [mention(text, "Kienapple", "case-k", kind="case_name")]
        applied, upheld = suggest(text, mentions)
        self.assertEqual(applied["target_group_id"], "case-k")
        self.assertIsNone(upheld["target_group_id"])
        summary, = summarize_edges(mentions, [applied, upheld], source_id="source", run_id="run")
        self.assertEqual(summary["treatment_suggestions"], ["applied"])
        self.assertEqual(summary["procedural_signals"], [])
        self.assertEqual(summary["ambiguous_observation_ids"], [upheld["observation_id"]])

    def test_named_other_court_retains_target_as_reported_treatment(self):
        text = "The Manitoba Court of Appeal applied the Kienapple principle to the arson offence, which was upheld on appeal."
        mentions = [mention(text, "Kienapple", "case-k", kind="case_name")]
        applied, upheld = suggest(text, mentions)
        self.assertEqual(applied["target_group_id"], "case-k")
        self.assertEqual(applied["status"], "context_required")
        self.assertIn("reported_actor_context", applied["flags"])
        self.assertEqual(applied["attribution_scope"], "reported_decision")
        actor = applied["reported_actor"]
        self.assertEqual(actor["raw"], "The Manitoba Court of Appeal")
        self.assertEqual(text[actor["start"]:actor["end"]], actor["raw"])
        self.assertIn(actor, applied["attribution_basis"]["evidence"])
        self.assertIsNone(upheld["target_group_id"])
        summary, = summarize_edges(mentions, [applied, upheld], source_id="source", run_id="run")
        self.assertEqual(summary["treatment_suggestions"], [])
        self.assertEqual(summary["context_required_signals"][0]["reported_actor"], actor)

    def test_explicit_prior_judges_are_reported_actors(self):
        for actor, verb in (("The trial judge", "distinguished"), ("the motions judge", "applied"),
                            ("the lower judge", "followed"), ("the appeal judge", "then considered")):
            text = actor + " " + verb + " Alpha."
            observation, = suggest(text, [mention(text, "Alpha")])
            self.assertEqual(observation["target_group_id"], "case-a")
            self.assertEqual(observation["status"], "context_required")
            self.assertEqual(observation["reported_actor"]["raw"], actor)

    def test_generic_or_explicit_current_court_does_not_imply_reported_actor(self):
        for actor in ("The Court", "This Court", "Our Court", "The Supreme Court of Canada"):
            text = actor + " followed Alpha."
            observations = suggest_treatments(text, [mention(text, "Alpha")], source_id="SCC_example",
                                              run_id="run", text_sha256=hashlib.sha256(text.encode()).hexdigest())
            observation, = observations
            self.assertEqual(observation["status"], "suggested")
            self.assertIsNone(observation["reported_actor"])

    def test_procedural_citation_history_does_not_target_affirming_decision(self):
        text = "R. v. Smith, 2007 NSCA 19, affirmed 2009 SCC 5, [2009] 1 SCR 146."
        mentions = [mention(text, "2007 NSCA 19", case_name="R. v. Smith"),
                    mention(text, "2009 SCC 5", "case-b", mid="m2"),
                    mention(text, "[2009] 1 SCR 146", "case-b", mid="m3")]
        observation, = suggest(text, mentions)
        self.assertIsNone(observation["target_group_id"])
        self.assertEqual(observation["candidate_target_ids"], ["case-a", "case-b"])
        self.assertEqual(observation["candidate_mention_ids"], ["m1", "m2", "m3"])
        self.assertEqual(observation["assignment_reason"], "procedural_citation_history")
        self.assertIn("procedural_signal", observation["flags"])
        self.assertIn("procedural_history_direction_uncertain", observation["flags"])
        for summary in summarize_edges(mentions, [observation], source_id="source", run_id="run"):
            self.assertEqual(summary["treatment_suggestions"], [])
            self.assertEqual(summary["observation_ids"], [])
            self.assertEqual(summary["ambiguous_observation_ids"], [observation["observation_id"]])

    def test_active_procedural_actor_is_not_citation_history(self):
        text = "The trial judge affirmed Alpha."
        observation, = suggest(text, [mention(text, "Alpha")])
        self.assertEqual(observation["target_group_id"], "case-a")
        self.assertEqual(observation["assignment_reason"], "active_object")
        self.assertNotIn("procedural_history_direction_uncertain", observation["flags"])

    def test_french_procedural_object_does_not_attach_to_reported_case(self):
        text = "Dans Arsenault-Cameron, précité, les juges ont infirmé la décision du ministre."
        observation, = suggest(text, [mention(text, "Arsenault-Cameron, précité", kind="precite")])
        self.assertEqual(observation["label"], "reversed")
        self.assertIsNone(observation["target_group_id"])
        self.assertIn("procedural_signal", observation["flags"])

    def test_modal_and_doctrinal_subject_remain_context_required(self):
        for text in ("Kienapple principle will apply.", "Kienapple applies.", "We should follow Kienapple."):
            observation, = suggest(text, [mention(text, "Kienapple", kind="case_name")])
            self.assertEqual(observation["target_group_id"], "case-a")
            self.assertEqual(observation["status"], "context_required")
            self.assertTrue({"conditional_or_modal", "doctrinal_applicability"} & set(observation["flags"]))

    def test_neutral_only_anchor_uses_exact_supplied_title_for_active_object(self):
        text = "We followed R. v. Smith, 2001 SCC 2."
        observation, = suggest(text, [mention(text, "2001 SCC 2", case_name="R. v. Smith")])
        self.assertEqual(observation["target_group_id"], "case-a")
        self.assertEqual(observation["assignment_reason"], "active_object")

    def test_active_subject_is_not_mistaken_for_passive_treatment(self):
        for text in ("Alpha has criticized the test.", "Alpha should follow the rule.",
                     "Alpha is considering the issue."):
            observation, = suggest(text, [mention(text, "Alpha")])
            self.assertIsNone(observation["target_group_id"])

    def test_explicit_noncase_veto_does_not_remove_inherited_edge(self):
        text = 'We followed “A Published Article”, 2001 ABC 2.'
        authority = mention(text, '“A Published Article”, 2001 ABC 2',
                            short_identity_seed_allowed=False,
                            short_identity_seed_reason="quoted_title_before_citation")
        observation, = suggest(text, [authority])
        self.assertIsNone(observation["target_group_id"])
        self.assertEqual(observation["candidate_target_ids"], [])
        self.assertIn("noncase_authority_candidate", observation["flags"])
        summary, = summarize_edges([authority], [observation], source_id="source", run_id="run")
        self.assertEqual(summary["target_group_id"], "case-a")
        self.assertEqual(summary["treatment_suggestions"], [])
        self.assertEqual(summary["unknown_mention_count"], 1)

    def test_assignment_does_not_cover_other_mentions_of_same_case(self):
        text = "In Alpha, another Alpha was applied."
        first = mention(text, "Alpha")
        second = mention(text, "Alpha", mid="m2", start=first["end"])
        observation, = suggest(text, [first, second])
        self.assertEqual(observation["target_mention_ids"], ["m2"])
        summary, = summarize_edges([first, second], [observation], source_id="source", run_id="run")
        self.assertEqual(summary["covered_mention_ids"], ["m2"])
        self.assertEqual(summary["unknown_mention_ids"], ["m1"])
        self.assertEqual([row["status"] for row in summary["mention_treatments"]], ["unknown", "context_required"])

    def test_positive_and_negative_evidence_is_preserved_as_polarity_conflict(self):
        text = "We followed Alpha. We did not follow Alpha."
        first = mention(text, "Alpha")
        mentions = [first, mention(text, "Alpha", mid="m2", start=first["end"])]
        observations = suggest(text, mentions)
        summary, = summarize_edges(mentions, observations, source_id="source", run_id="run")
        self.assertEqual(summary["treatment_suggestions"], ["followed"])
        self.assertEqual(summary["context_required_labels"], ["followed"])
        self.assertEqual(summary["label_conflicts"][0]["reason"], "mixed_signal_polarity")
        self.assertEqual(len(summary["machine_summary"]["treatment_evidence"]), 1)
        self.assertEqual(len(summary["machine_summary"]["context_required_evidence"]), 1)

    def test_old_observations_can_still_be_summarized(self):
        text = "We followed Alpha."
        mentions = [mention(text, "Alpha")]
        observation, = suggest(text, mentions)
        observation.pop("target_mention_ids")
        observation.pop("candidate_mention_ids")
        summary, = summarize_edges(mentions, [observation], source_id="source", run_id="run")
        self.assertEqual(summary["covered_mention_ids"], ["m1"])
        self.assertEqual(summary["treatment_suggestions"], ["followed"])

    def test_citation_contents_and_settled_are_not_treatment(self):
        text = "The matter was settled in Followed v. Applied, 2020 ABC 1."
        self.assertEqual(suggest(text, [mention(text, "Followed v. Applied, 2020 ABC 1")]), [])

    def test_candidate_observation_preserved_without_assigning_edge_label(self):
        text = "We criticized Alpha and Beta."
        mentions = [mention(text, "Alpha"), mention(text, "Beta", "case-b", mid="m2")]
        observations = suggest(text, mentions)
        summaries = summarize_edges(mentions, observations, source_id="source", run_id="run")
        self.assertEqual(len(summaries), 2)
        for summary in summaries:
            self.assertEqual(summary["treatment_suggestions"], [])
            self.assertEqual(summary["coverage_status"], "no_suggestions")
            self.assertEqual(summary["ambiguous_observation_ids"], [observations[0]["observation_id"]])

    def test_speaker_requires_explicit_evidence_and_preserves_original_spans(self):
        for actor, expected in (("We", "current_court"), ("I", "current_court"),
                                ("This Court", "current_court"), ("The Court", "unknown")):
            text = actor + " followed Alpha."
            observation, = suggest(text, [mention(text, "Alpha")])
            self.assertEqual(observation["speaker_attribution"], expected)
            self.assertEqual(observation["status"], "suggested")
            for evidence in observation["speaker_evidence"]:
                self.assertEqual(text[evidence["start"]:evidence["end"]], evidence["raw"])
            self.assertEqual(bool(observation["speaker_evidence"]), expected == "current_court")

    def test_pronouns_guard_reported_treatment_without_inventing_identity(self):
        examples = ("She followed Alpha.", "It followed the reasoning in Alpha.",
                    "Some applied Alpha.", "Applying Alpha, he noted that the test was met.",
                    "Her reasons illustrate the difficulty in applying Alpha.",
                    "He found it incumbent upon him to follow Alpha.")
        for text in examples:
            with self.subTest(text=text):
                observation, = suggest(text, [mention(text, "Alpha")])
                self.assertEqual(observation["target_group_id"], "case-a")
                self.assertEqual(observation["speaker_attribution"], "unknown")
                self.assertEqual(observation["status"], "context_required")
                self.assertIn("unresolved_actor", observation["flags"])
                self.assertIsNone(observation["context_owner_group_id"])

    def test_fronted_participle_distinguishes_reported_and_explicit_current_actors(self):
        for actor, expected in (("the Supreme Court", "reported_court"), ("we", "current_court")):
            text = "Applying Alpha, " + actor + " held that the test was met."
            observation, = suggest(text, [mention(text, "Alpha")])
            self.assertEqual(observation["target_group_id"], "case-a")
            self.assertEqual(observation["speaker_attribution"], expected)
            self.assertEqual(observation["status"], "suggested" if expected == "current_court" else "context_required")

    def test_reported_judge_can_apply_a_described_test_from_explicit_case(self):
        text = "The trial judge concluded his analysis by applying the test for dangerous driving established by the Supreme Court of Canada in R. v. Alpha, 1993 SCC 1."
        observation, = suggest(text, [mention(text, "1993 SCC 1", case_name="R. v. Alpha")])
        self.assertEqual(observation["target_group_id"], "case-a")
        self.assertEqual(observation["attribution_basis"]["rule"], "active_object")
        self.assertEqual(observation["speaker_attribution"], "reported_judge")
        self.assertEqual(observation["status"], "context_required")
        self.assertEqual(observation["reported_actor"]["raw"], "The trial judge")

    def test_reported_case_owner_carries_within_paragraph_without_becoming_target(self):
        text = "In Alpha, the court set out the facts. It considered the alternatives. Accordingly, it was appropriate for the Court to apply Beta."
        mentions = [mention(text, "Alpha"), mention(text, "Beta", "case-b", mid="m2")]
        considered, applied = suggest(text, mentions)
        self.assertEqual(applied["target_group_id"], "case-b")
        self.assertEqual(applied["target_mention_ids"], ["m2"])
        self.assertEqual(applied["context_owner_group_id"], "case-a")
        self.assertEqual(applied["context_owner_mention_ids"], ["m1"])
        self.assertEqual(applied["context_mention_ids"], ["m1"])
        self.assertEqual(applied["status"], "context_required")
        for evidence in applied["context_owner_basis"]["evidence"]:
            self.assertEqual(text[evidence["start"]:evidence["end"]], evidence["raw"])
        summaries = {s["target_group_id"]: s for s in summarize_edges(mentions, [considered, applied], source_id="source", run_id="run")}
        source = summaries["case-a"]
        self.assertIn(applied["observation_id"], source["reported_source_observation_ids"])
        self.assertEqual(source["covered_mention_ids"], [])
        self.assertEqual(source["treatment_suggestions"], [])
        target_signal = summaries["case-b"]["context_required_signals"][0]
        self.assertEqual(target_signal["context_owner_group_id"], "case-a")
        self.assertEqual(target_signal["attribution_basis"], applied["attribution_basis"])

    def test_same_court_historical_source_is_distinct_from_evaluated_case(self):
        text = "This Court in Alpha, 2002 SCC 15, a negligence case, distinguished Beta."
        mentions = [mention(text, "2002 SCC 15", case_name="Alpha"),
                    mention(text, "Beta", "case-b", mid="m2")]
        observation, = suggest_treatments(text, mentions, source_id="SCC_source", run_id="run", text_sha256="hash")
        self.assertEqual(observation["target_group_id"], "case-b")
        self.assertEqual(observation["context_owner_group_id"], "case-a")
        self.assertEqual(observation["speaker_attribution"], "reported_case")
        self.assertEqual(observation["status"], "context_required")
        title = "This Court in Alpha"
        mentions[0]["source_aliases"] = [{"start": 0, "end": len(title), "raw": title, "origin": "local_case_title"}]
        observation, = suggest_treatments(text, mentions, source_id="SCC_source", run_id="run", text_sha256="hash")
        self.assertEqual(observation["context_owner_group_id"], "case-a")
        self.assertEqual(observation["status"], "context_required")

    def test_historical_source_after_predicate_does_not_reverse_target(self):
        text = "For example, the Court first applied Alpha in the 1973 case of Beta."
        mentions = [mention(text, "Alpha"), mention(text, "Beta", "case-b", mid="m2")]
        observation, = suggest(text, mentions)
        self.assertEqual(observation["target_group_id"], "case-a")
        self.assertEqual(observation["context_owner_group_id"], "case-b")
        self.assertEqual(observation["status"], "context_required")

    def test_case_subject_report_can_introduce_later_historical_treatment(self):
        text = 'Alpha involved an undercover operation. The Court was able to distinguish Beta.'
        mentions = [mention(text, "Alpha"), mention(text, "Beta", "case-b", mid="m2")]
        observation, = suggest(text, mentions)
        self.assertEqual(observation["target_group_id"], "case-b")
        self.assertEqual(observation["context_owner_group_id"], "case-a")
        self.assertEqual(observation["status"], "context_required")

    def test_context_owner_stops_at_paragraph_or_explicit_current_voice(self):
        for separator in ("\n[24] ", "\n\n", " "):
            text = "In Alpha, the court set out the facts." + separator + "We followed Beta."
            mentions = [mention(text, "Alpha"), mention(text, "Beta", "case-b", mid="m2")]
            observation, = suggest(text, mentions)
            self.assertIsNone(observation["context_owner_group_id"])
            self.assertEqual(observation["speaker_attribution"], "current_court")
            self.assertEqual(observation["status"], "suggested")
        for modifier in ("therefore ", "now ", "here "):
            text = "In Alpha, the court held that a rule governed. We " + modifier + "follow Beta."
            observation, = suggest(text, [mention(text, "Alpha"), mention(text, "Beta", "case-b", mid="m2")])
            self.assertIsNone(observation["context_owner_group_id"])
            self.assertEqual(observation["speaker_attribution"], "current_court")

    def test_same_sentence_historical_case_outranks_same_court_actor(self):
        text = "In Alpha, this Court applied Beta."
        observation, = suggest(text, [mention(text, "Alpha"), mention(text, "Beta", "case-b", mid="m2")])
        self.assertEqual(observation["context_owner_group_id"], "case-a")
        self.assertEqual(observation["speaker_attribution"], "reported_case")
        self.assertEqual(observation["status"], "context_required")

    def test_competing_source_introduction_retains_ambiguity(self):
        text = "In Alpha and Gamma, the court stated the rule. It followed Beta."
        mentions = [mention(text, "Alpha"), mention(text, "Gamma", "case-c", mid="m2"),
                    mention(text, "Beta", "case-b", mid="m3")]
        observation, = suggest(text, mentions)
        self.assertEqual(observation["target_group_id"], "case-b")
        self.assertIsNone(observation["context_owner_group_id"])
        self.assertEqual(observation["context_owner_candidate_target_ids"], ["case-a", "case-c"])
        self.assertEqual(observation["status"], "context_required")

    def test_quote_owner_is_explicit_source_and_quoted_we_is_not_current_court(self):
        text = 'In Alpha, the judge stated:\n\n“We followed Beta.” We followed Gamma.'
        mentions = [mention(text, "Alpha"), mention(text, "Beta", "case-b", mid="m2"),
                    mention(text, "Gamma", "case-c", mid="m3")]
        quoted, current = suggest(text, mentions)
        self.assertEqual(quoted["target_group_id"], "case-b")
        self.assertEqual(quoted["context_owner_group_id"], "case-a")
        self.assertEqual(quoted["speaker_attribution"], "reported_case")
        self.assertEqual(quoted["attribution_scope"], "quoted_statement")
        self.assertEqual(quoted["status"], "context_required")
        self.assertTrue(quoted["quote_scope"]["closed"])
        self.assertIsNone(current["context_owner_group_id"])
        self.assertEqual(current["speaker_attribution"], "current_court")
        self.assertEqual(current["status"], "suggested")

    def test_quote_source_does_not_jump_over_an_intervening_paragraph_or_sentence(self):
        for interruption in ("\n[20] Counsel said: ", ". The trial judge stated: "):
            text = "In Alpha, the court discussed negligence" + interruption + '“We applied Beta.”'
            _, quoted = suggest(text, [mention(text, "Alpha"), mention(text, "Beta", "case-b", mid="m2")])
            self.assertIsNone(quoted["context_owner_group_id"])
            self.assertEqual(quoted["speaker_attribution"], "unknown")

    def test_closed_quote_returns_to_explicit_current_court_in_same_paragraph(self):
        text = 'In Alpha, the judge stated: “We followed Beta.” We applied Gamma.'
        mentions = [mention(text, "Alpha"), mention(text, "Beta", "case-b", mid="m2"),
                    mention(text, "Gamma", "case-c", mid="m3")]
        quoted, current = suggest(text, mentions)
        self.assertEqual(quoted["context_owner_group_id"], "case-a")
        self.assertEqual(quoted["status"], "context_required")
        self.assertIsNone(current["context_owner_group_id"])
        self.assertEqual(current["speaker_attribution"], "current_court")
        self.assertEqual(current["status"], "suggested")

    def test_nested_quote_needs_own_explicit_owner(self):
        text = 'In Alpha, the judge stated: “We followed Beta. In Gamma, the judge stated: «We applied Delta.»”'
        mentions = [mention(text, name, "case-" + name.lower(), mid="m" + str(i))
                    for i, name in enumerate(("Alpha", "Beta", "Gamma", "Delta"))]
        outer, inner = suggest(text, mentions)
        self.assertEqual(outer["context_owner_group_id"], "case-alpha")
        self.assertEqual(inner["context_owner_group_id"], "case-gamma")
        self.assertEqual(inner["quote_scope"]["parent_scope_id"], outer["quote_scope"]["scope_id"])
        text = 'In Alpha, the judge stated: “He said «We followed Beta.»”'
        observation, = suggest(text, [mention(text, "Alpha"), mention(text, "Beta", "case-b", mid="m2")])
        self.assertIsNone(observation["context_owner_group_id"])
        self.assertEqual(observation["speaker_attribution"], "unknown")
        self.assertEqual(observation["status"], "context_required")

    def test_unclosed_quote_does_not_capture_later_paragraph_current_voice(self):
        text = '“We followed Alpha.\nWe followed Beta.'
        mentions = [mention(text, "Alpha"), mention(text, "Beta", "case-b", mid="m2")]
        quoted, current = suggest(text, mentions)
        self.assertTrue(quoted["quote_scope"]["uncertain"])
        self.assertEqual(quoted["status"], "context_required")
        self.assertIn("quotation_scope_uncertain", quoted["flags"])
        self.assertIsNone(current["quote_scope"])
        self.assertEqual(current["speaker_attribution"], "current_court")
        self.assertEqual(current["status"], "suggested")

    def test_party_clause_does_not_capture_current_court_clause(self):
        text = "The appellant submits that Alpha should be followed, but we applied Beta."
        mentions = [mention(text, "Alpha"), mention(text, "Beta", "case-b", mid="m2")]
        party, current = suggest(text, mentions)
        self.assertEqual(party["speaker_attribution"], "party")
        self.assertEqual(party["status"], "context_required")
        self.assertEqual(current["speaker_attribution"], "current_court")
        self.assertNotIn("party_submission", current["flags"])
        self.assertEqual(current["status"], "suggested")

    def test_efforts_to_distinguish_is_a_discussed_attempt_not_asserted_treatment(self):
        text = "The framework in Alpha represents the proper approach and efforts since then to explain, clarify, refine, extend, add to or distinguish Alpha have only muddied the waters."
        first = mention(text, "Alpha")
        mentions = [first, mention(text, "Alpha", mid="m2", start=first["end"])]
        observation, = suggest(text, mentions)
        self.assertEqual(observation["target_mention_ids"], ["m2"])
        self.assertEqual(observation["status"], "context_required")
        self.assertIn("attempted_action_context", observation["flags"])
        evidence = next(e for e in observation["attribution_basis"]["evidence"] if e["kind"] == "attempted_action_context")
        self.assertEqual(text[evidence["start"]:evidence["end"]], evidence["raw"])
        summary, = summarize_edges(mentions, [observation], source_id="source", run_id="run")
        self.assertEqual(summary["treatment_suggestions"], [])

    def test_post_predicate_rejection_of_application_preserves_target_without_asserting_application(self):
        text = 'Enacting a regulation is therefore not a "decision" in the Vavilov sense and applying the Vavilov reasonableness approach is not analytically sound.\n- Nothing in Vavilov evidences an intention to overrule or modify the Katz Group test'
        mentions = []
        cursor = 0
        for number in range(3):
            current = mention(text, "Vavilov", mid="m" + str(number), kind="case_name", start=cursor)
            mentions.append(current)
            cursor = current["end"]
        applied = next(o for o in suggest(text, mentions) if o["label"] == "applied")
        self.assertEqual(applied["target_mention_ids"], ["m1"])
        self.assertEqual(applied["target_group_id"], "case-a")
        self.assertEqual(applied["status"], "context_required")
        self.assertFalse(applied["negated"])
        self.assertIn("rejected_application_context", applied["flags"])
        evidence = next(e for e in applied["attribution_basis"]["evidence"] if e["kind"] == "rejected_application_context")
        self.assertEqual(evidence["raw"], "applying the Vavilov reasonableness approach is not analytically sound")
        self.assertEqual(text[evidence["start"]:evidence["end"]], evidence["raw"])
        summary, = summarize_edges(mentions, [applied], source_id="source", run_id="run")
        self.assertEqual(summary["treatment_suggestions"], [])
        self.assertEqual(summary["context_required_signals"][0]["attribution_basis"], applied["attribution_basis"])
        positive = "Applying the Vavilov reasonableness approach is analytically sound."
        observation, = suggest(positive, [mention(positive, "Vavilov", kind="case_name")])
        self.assertNotIn("rejected_application_context", observation["flags"])

    def test_suggestion_of_appeal_court_error_records_reported_actor_and_evaluated_target(self):
        text = "[4] The suggestion that the majority of the Court of Appeal erred in applying the test for unreasonable verdict set out in Corbett v. The Queen, [1975] 2 S.C.R. 275,"
        authority = mention(text, "[1975] 2 S.C.R. 275", case_name="Corbett v. The Queen")
        observation, = suggest(text, [authority])
        self.assertEqual(observation["target_group_id"], "case-a")
        self.assertEqual(observation["target_mention_ids"], ["m1"])
        self.assertEqual(observation["status"], "context_required")
        self.assertEqual(observation["speaker_attribution"], "reported_court")
        self.assertEqual(observation["reported_actor"]["raw"], "the majority of the Court of Appeal")
        self.assertIsNone(observation["context_owner_group_id"])
        self.assertIn("alleged_error_context", observation["flags"])
        self.assertNotIn("party_submission", observation["flags"])
        for evidence in observation["attribution_basis"]["evidence"]:
            self.assertEqual(text[evidence["start"]:evidence["end"]], evidence["raw"])
        summary, = summarize_edges([authority], [observation], source_id="source", run_id="run")
        self.assertEqual(summary["treatment_suggestions"], [])
        self.assertEqual(summary["context_required_signals"][0]["reported_actor"], observation["reported_actor"])


if __name__ == "__main__":
    unittest.main()
