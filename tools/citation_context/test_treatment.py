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


if __name__ == "__main__":
    unittest.main()
