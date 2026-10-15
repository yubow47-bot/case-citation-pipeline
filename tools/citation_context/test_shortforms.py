"""Small adversarial fixtures for the experimental short-reference rules."""
import copy
import hashlib
import unittest

try:
    from .shortforms import enrich_anchors, resolve_document, resolve_named_mentions
except ImportError:
    from shortforms import enrich_anchors, resolve_document, resolve_named_mentions


def anchor(text, raw, target="case-a", name="R. v. Smith", mention_id="full-a", aliases=None):
    start = text.index(raw)
    return {"mention_id": mention_id, "start": start, "end": start + len(raw),
            "raw": raw, "target_group_id": target, "candidate_id": mention_id,
            "case_name": name, "aliases": aliases or [], "identity_status": "resolved",
            "edge_support": "citation", "counted_edge": bool(target)}


def resolve(text, anchors=(), **kwargs):
    return resolve_document(text, list(anchors), source_id=kwargs.get("source_id", "source"),
                            run_id="run", text_sha256=hashlib.sha256(text.encode()).hexdigest())


class ShortformTests(unittest.TestCase):
    def test_unicode_offsets_pinpoints_chain_and_determinism(self):
        text = "É😀 Smith, 2001 SCC 2. Ibid., at para. 12. Id. at 14."
        anchors = [anchor(text, "Smith, 2001 SCC 2")]
        original = copy.deepcopy(anchors)
        records = resolve(text, anchors)
        self.assertEqual([r["target_group_id"] for r in records], ["case-a", "case-a"])
        self.assertEqual(records[0]["pinpoint"], "at para. 12")
        self.assertEqual(records[1]["antecedent_mention_ids"], [records[0]["mention_id"]])
        for record in records:
            self.assertEqual(text[record["start"]:record["end"]], record["raw"])
        self.assertEqual(records, resolve(text, anchors))
        self.assertNotEqual(records[0]["mention_id"], resolve(text, anchors, source_id="other")[0]["mention_id"])
        self.assertEqual(anchors, original)

    def test_parallel_anchors_same_group_and_distinct_groups(self):
        text = "Smith, 2001 SCC 2, [2001] 1 S.C.R. 3. Ibid."
        anchors = [anchor(text, "2001 SCC 2"),
                   anchor(text, "[2001] 1 S.C.R. 3", mention_id="parallel")]
        result = resolve(text, anchors)[0]
        self.assertEqual(result["resolution_status"], "resolved")
        self.assertEqual(result["antecedent_mention_ids"], ["full-a", "parallel"])
        anchors[1]["target_group_id"] = "case-b"
        result = resolve(text, anchors)[0]
        self.assertEqual(result["resolution_status"], "ambiguous")
        self.assertIsNone(result["target_group_id"])
        self.assertEqual(result["candidate_target_ids"], ["case-a", "case-b"])

    def test_intervening_unknown_authority_and_unresolved_chain(self):
        text = "Smith, 2001 SCC 2; Jones v. Brown, 1988 XYZ 9. Ibid. Id. at 3."
        results = resolve(text, [anchor(text, "Smith, 2001 SCC 2")])
        self.assertEqual([r["resolution_status"] for r in results], ["unresolved", "unresolved"])
        self.assertEqual(results[1]["resolution_basis"], "prior_short_reference_not_resolved")
        self.assertEqual(results[1]["antecedent_mention_ids"], [results[0]["mention_id"]])

    def test_unlinked_full_anchor_is_a_barrier(self):
        text = "Smith, 2001 SCC 2; Unknown, 2002 ABC 3. Ibid."
        result = resolve(text, [anchor(text, "Smith, 2001 SCC 2"),
                                anchor(text, "Unknown, 2002 ABC 3", target=None,
                                       name="Unknown", mention_id="unlinked")])[0]
        self.assertEqual(result["resolution_status"], "blocked")
        self.assertIsNone(result["target_group_id"])

    def test_named_supra_collisions_boundaries_and_generic_royal_names(self):
        text = "R. v. Smith, 2001 SCC 2. R. v. Brown, 2002 SCC 3. Smith, supra. Smithson, supra. R., supra."
        anchors = [anchor(text, "2001 SCC 2"),
                   anchor(text, "2002 SCC 3", target="case-b", name="R. v. Brown", mention_id="b")]
        results = resolve(text, anchors)
        self.assertEqual(results[0]["target_group_id"], "case-a")
        self.assertEqual(results[0]["raw"], "Smith, supra")
        self.assertTrue(all(r["resolution_status"] == "unresolved" for r in results[1:]))
        anchors.append(anchor(text, "R. v. Brown", target="case-c", name="Jones v. Smith", mention_id="c"))
        result = resolve(text, anchors)[0]
        self.assertEqual(result["resolution_status"], "ambiguous")
        self.assertEqual(result["candidate_target_ids"], ["case-a", "case-c"])

    def test_unrecognized_other_party_cannot_use_known_surname(self):
        text = "R. v. Smith, 2001 SCC 2. Jones v. Smith, supra."
        result = resolve(text, [anchor(text, "2001 SCC 2")])[0]
        self.assertEqual(result["resolution_status"], "ambiguous")
        self.assertIsNone(result["target_group_id"])

    def test_supra_only_sees_prior_anchors_and_bare_supra_stays_unresolved(self):
        text = "Smith, supra. R. v. Smith, 2001 SCC 2. supra."
        results = resolve(text, [anchor(text, "2001 SCC 2")])
        self.assertEqual([r["resolution_status"] for r in results], ["unresolved", "unresolved"])

    def test_named_antecedents_search_whole_prior_document_and_keep_old_collisions(self):
        text = "Schwartz, 2001 SCC 2. " + "ordinary text " * 1000 + "Schwartz, supra."
        anchors = [anchor(text, "2001 SCC 2", name="Schwartz")]
        self.assertEqual(resolve(text, anchors)[0]["target_group_id"], "case-a")
        anchors.append(anchor(text, "ordinary text", target="case-b", name="Schwartz", mention_id="b"))
        result = resolve(text, anchors)[0]
        self.assertEqual(result["resolution_status"], "ambiguous")
        self.assertEqual(result["candidate_target_ids"], ["case-a", "case-b"])

    def test_balanced_qualifiers_and_explicit_corporate_suffix_short_parties(self):
        text = "2001 SCC 2. 2002 SCC 3. 2003 SCC 4. Southam, supra. Gottardo Properties, supra. Toneguzzo-Norvell, supra."
        anchors = [
            anchor(text, "2001 SCC 2", name="Canada (Director of Investigation) v. Southam Inc."),
            anchor(text, "2002 SCC 3", target="case-b", name="Gottardo Properties (Dome) Inc.", mention_id="b"),
            anchor(text, "2003 SCC 4", target="case-c", name="Toneguzzo-Norvell (Guardian ad litem of) v. Burnaby Hospital", mention_id="c"),
        ]
        results = resolve(text, anchors)
        self.assertEqual([r["target_group_id"] for r in results], ["case-a", "case-b", "case-c"])
        self.assertTrue(all(r["resolution_basis"] == "named_prior_normalized_short_party" for r in results))
        self.assertTrue(all(r["notes"] for r in results))

    def test_short_party_collisions_and_no_firstword_or_surname_generalization(self):
        text = "2001 SCC 2. 2002 SCC 3. 2003 SCC 4. Gottardo Properties, supra. Gottardo, supra. Norvell, supra. W, supra."
        anchors = [anchor(text, "2001 SCC 2", name="Gottardo Properties (Dome) Inc."),
                   anchor(text, "2002 SCC 3", target="case-b", name="Other", mention_id="b",
                          aliases=["Gottardo Properties (North) Limited"]),
                   anchor(text, "2003 SCC 4", target="case-c", name="W.(D.)", mention_id="c")]
        first, second, third, fourth = resolve(text, anchors)
        self.assertEqual(first["resolution_status"], "ambiguous")
        self.assertEqual(first["candidate_target_ids"], ["case-a", "case-b"])
        self.assertEqual([r["resolution_status"] for r in (second, third, fourth)], ["unresolved"] * 3)
        text = "2001 SCC 2. Toneguzzo-Smith, supra. O'Smith, supra."
        results = resolve(text, [anchor(text, "2001 SCC 2")])
        self.assertTrue(all(r["target_group_id"] is None for r in results))

    def test_explicit_footnote_and_named_footnote_conflict(self):
        text = "Footnotes\n1 Smith, 2001 SCC 2.\n2 Brown, 2002 SCC 3.\n3 Supra note 1, at para. 4. Brown, supra note 1."
        anchors = [anchor(text, "Smith, 2001 SCC 2"),
                   anchor(text, "Brown, 2002 SCC 3", target="case-b", name="Brown", mention_id="b")]
        first, second = resolve(text, anchors)
        self.assertEqual(first["target_group_id"], "case-a")
        self.assertEqual(first["footnote_number"], 1)
        self.assertEqual(first["pinpoint"], "at para. 4")
        self.assertEqual(second["resolution_status"], "ambiguous")
        self.assertEqual(second["resolution_basis"], "named_and_footnote_antecedents_conflict")

    def test_numeric_paragraph_labels_are_not_verified_footnotes(self):
        text = "[1] Smith, 2001 SCC 2.\n[2] Supra note 1. Smith, supra note 1."
        first, named = resolve(text, [anchor(text, "Smith, 2001 SCC 2")])
        self.assertEqual(first["resolution_status"], "ambiguous")
        self.assertEqual(first["candidate_target_ids"], ["case-a"])
        self.assertIsNone(first["target_group_id"])
        self.assertEqual(named["target_group_id"], "case-a")

    def test_footnote_with_book_and_quoted_named_antecedent_are_blocked(self):
        text = "Footnotes\n1 Smith, 2001 SCC 2; a treatise by Demogue.\n2 Supra note 1."
        result = resolve(text, [anchor(text, "Smith, 2001 SCC 2")])[0]
        self.assertEqual(result["resolution_basis"], "explicit_footnote_noncase_authority")
        self.assertIsNone(result["target_group_id"])
        text = "“Smith, 2001 SCC 2.” Smith, supra."
        result = resolve(text, [anchor(text, "Smith, 2001 SCC 2")])[0]
        self.assertEqual(result["resolution_status"], "blocked")
        self.assertEqual(result["resolution_basis"], "quoted_antecedent_barrier")

    def test_french_and_english_variants_are_always_detected(self):
        text = "Émond, 2001 CSC 2. Émond, précité, au par. 9; Emond, precitee; précités; précitées; ibid.; id."
        results = resolve(text, [anchor(text, "2001 CSC 2", name="Émond")])
        self.assertEqual([r["kind"] for r in results], ["precite"] * 4 + ["ibid", "id"])
        self.assertEqual([r["target_group_id"] for r in results[:2]], ["case-a", "case-a"])
        self.assertEqual(results[0]["pinpoint"], "au par. 9")
        self.assertIsNone(results[-1]["target_group_id"])

    def test_real_inventory_noncase_and_reporter_traps(self):
        text = ("R. v. Smith (1978), 15 Nfld. & P.E.I.R. 115 (Nfld. C.A.), a decision "
                "under the now repealed Narcotic Control Act, supra. "
                "les débentures précitées; la lettre précitée; voir 8 id.174; "
                "19 Isambert,425;20 id.226; false ID. Consider; Novelty ID. Yes.")
        results = resolve(text, [anchor(text, "15 Nfld. & P.E.I.R. 115")])
        self.assertEqual(len(results), 7)
        self.assertTrue(all(r["resolution_status"] == "blocked" for r in results))
        self.assertTrue(all(r["target_group_id"] is None for r in results))
        self.assertEqual(results[3]["resolution_basis"], "reporter_id_substitution")

    def test_quotes_and_large_or_prose_gaps(self):
        text = "Smith, 2001 SCC 2. “Ibid. at 3.” The conclusion follows. Ibid."
        results = resolve(text, [anchor(text, "Smith, 2001 SCC 2")])
        self.assertEqual(results[0]["resolution_status"], "blocked")
        self.assertEqual(results[1]["resolution_status"], "unresolved")
        text = "Smith, 2001 SCC 2.\n\nIbid."
        self.assertEqual(resolve(text, [anchor(text, "Smith, 2001 SCC 2")])[0]["resolution_status"], "unresolved")

    def test_original_french_titles_and_explicit_shortname_enrich_without_mutation(self):
        text = ("Dans l’affaire du Renvoi relatif à la sécession du Québec, [1998] 2 R.C.S. 217 "
                "(le « Renvoi relatif à la sécession »). Société des Acadiens c. Association of Parents, "
                "[1986] 1 R.C.S. 549. Dans Mahe c. Alberta, [1990] 1 R.C.S. 342. "
                "Renvoi relatif à la sécession, précité; Société des Acadiens, précité; Mahe, précité.")
        anchors = [anchor(text, "[1998] 2 R.C.S. 217", name=""),
                   anchor(text, "[1986] 1 R.C.S. 549", name="", target="case-b", mention_id="b"),
                   anchor(text, "[1990] 1 R.C.S. 342", name="", target="case-c", mention_id="c")]
        original = copy.deepcopy(anchors)
        enriched = enrich_anchors(text, anchors)
        self.assertEqual(enriched[0]["local_case_name"], "Renvoi relatif à la sécession du Québec")
        self.assertEqual(enriched[1]["local_case_name"], "Société des Acadiens c. Association of Parents")
        self.assertEqual(enriched[2]["local_case_name"], "Mahe c. Alberta")
        self.assertEqual(enriched, enrich_anchors(text, enriched))
        self.assertEqual(anchors, original)
        records = resolve(text, enriched)
        self.assertEqual([r["target_group_id"] for r in records], ["case-a", "case-b", "case-c"])
        self.assertTrue(any(e["origin"] == "explicit_shortname" for e in records[0]["alias_evidence"]))
        for a in enriched:
            for evidence in a["source_aliases"]:
                self.assertEqual(text[evidence["start"]:evidence["end"]], evidence["raw"])

    def test_numeric_reference_titles_do_not_conflate_and_case_titles_are_not_statutes(self):
        text = ("Renvoi relatif au projet de Loi 30, An Act to Amend the Education Act (Ont.), "
                "[1987] 1 R.C.S. 1148. Renvoi relatif au projet de loi 30, précité. "
                "Renvoi relatif au projet de loi 31, précité. Dans Re Adoption Act of Ontario, supra.")
        records = resolve(text, [anchor(text, "[1987] 1 R.C.S. 1148", name="")])
        self.assertEqual(records[0]["target_group_id"], "case-a")
        self.assertIsNone(records[1]["target_group_id"])
        self.assertEqual(records[2]["resolution_status"], "unresolved")
        self.assertEqual(records[2]["resolution_basis"], "case_title_without_prior_anchor")

    def test_semicolon_list_connector_and_true_multiple_authority_candidates(self):
        text = ("2001 SCC 2. 2002 SCC 3. 2003 SCC 4. 2004 SCC 5. "
                "Southam, supra; and Nova Scotia Pharmaceutical Society, supra. "
                "Morguard and Amchem, supra.")
        anchors = [anchor(text, "2001 SCC 2", name="Southam Inc."),
                   anchor(text, "2002 SCC 3", name="R. v. Nova Scotia Pharmaceutical Society", target="case-b", mention_id="b"),
                   anchor(text, "2003 SCC 4", name="Morguard Investments Ltd. v. De Savoye", target="case-c", mention_id="c"),
                   anchor(text, "2004 SCC 5", name="Amchem Products Inc. v. British Columbia", target="case-d", mention_id="d")]
        first, second, multiple = resolve(text, anchors)
        self.assertEqual([first["target_group_id"], second["target_group_id"]], ["case-a", "case-b"])
        self.assertEqual(multiple["raw"], "Morguard and Amchem, supra")
        self.assertEqual(multiple["resolution_status"], "ambiguous")
        self.assertEqual(multiple["candidate_target_ids"], ["case-c", "case-d"])
        self.assertIsNone(multiple["target_group_id"])

    def test_article_case_name_is_vetoed_but_production_anchor_is_preserved(self):
        text = ("Baker c. Canada (Ministère de la citoyenneté), [1999] 2 R.C.S. 817; "
                "Dyzenhaus et Fox-Decent, « Rethinking the Process/Substance Distinction: "
                "Baker v. Canada » (2001), 51 U.T.L.J. 193. Ibid. Baker, précité.")
        anchors = [anchor(text, "[1999] 2 R.C.S. 817", name=""),
                   anchor(text, "(2001), 51 U.T.L.J. 193", name="Baker v. Canada »", target="article", mention_id="article")]
        enriched = enrich_anchors(text, anchors)
        self.assertFalse(enriched[1]["short_identity_seed_allowed"])
        self.assertEqual(enriched[1]["target_group_id"], "article")
        self.assertEqual(enriched[1]["case_name"], "Baker v. Canada »")
        ibid, baker = resolve(text, enriched)
        self.assertEqual(ibid["resolution_status"], "blocked")
        self.assertEqual(ibid["resolution_basis"], "noncase_identity_seed_barrier")
        self.assertEqual(baker["target_group_id"], "case-a")
        self.assertNotIn("article", baker["candidate_target_ids"])

    def test_case_name_layer_keeps_separate_counts_and_source_antecedents(self):
        text = ("Smith was discussed. R. v. Smith, 2001 SCC 2. "
                "We followed R. v. Smith, 2002 SCC 3. Smith was applied. "
                "Smith, supra. Canada was mentioned. Smithson and O'Smith are people.")
        anchors = [anchor(text, "2001 SCC 2"), anchor(text, "2002 SCC 3", mention_id="parallel")]
        shorts = resolve(text, anchors)
        records = resolve_named_mentions(text, anchors, exclude_spans=[(r["start"], r["end"]) for r in shorts])
        self.assertEqual([r["raw"] for r in records], ["Smith"])
        self.assertEqual(records[0]["kind"], "case_name")
        self.assertEqual(records[0]["target_group_id"], "case-a")
        self.assertEqual(records[0]["antecedent_mention_ids"], ["full-a", "parallel"])
        self.assertEqual(records, resolve_named_mentions(text, anchors, exclude_spans=[(r["start"], r["end"]) for r in shorts]))

    def test_footnote_reference_cannot_bypass_noncase_seed_veto(self):
        text = "Footnotes\n1. Author, « Rethinking Baker v. Canada » (2001), 51 U.T.L.J. 193.\n2. Supra note 1."
        records = resolve(text, [anchor(text, "(2001), 51 U.T.L.J. 193", name="Baker v. Canada »")])
        self.assertEqual(records[0]["resolution_status"], "blocked")
        self.assertEqual(records[0]["resolution_basis"], "noncase_identity_seed_barrier")

    def test_bare_names_keep_collisions_quotes_and_generic_parties_conservative(self):
        text = "2001 SCC 2. 2002 SCC 3. Smith was applied. “Smith was followed.” Canada considered Smith."
        anchors = [anchor(text, "2001 SCC 2", name="Smith v. Canada"),
                   anchor(text, "2002 SCC 3", name="Jones v. Smith", target="case-b", mention_id="b")]
        records = resolve_named_mentions(text, anchors)
        self.assertEqual([r["raw"] for r in records], ["Smith"] * 3)
        self.assertEqual([r["resolution_status"] for r in records], ["ambiguous", "blocked", "ambiguous"])
        self.assertTrue(all(r["candidate_target_ids"] == ["case-a", "case-b"] for r in records))
        self.assertTrue(all(r["target_group_id"] is None for r in records))

    def test_local_title_does_not_invent_mont_sinai_or_single_word_shortnames(self):
        text = ("Centre hospitalier Mont-Sinaï c. Québec (Ministre de la Santé), 2001 C.S.C. 41. "
                "Mont-Sinaï, précité. Centre hospitalier Mont-Sinaï, précité.")
        anchors = [anchor(text, "2001 C.S.C. 41", name="")]
        abbreviated, exact = resolve(text, anchors)
        self.assertIsNone(abbreviated["target_group_id"])
        self.assertEqual(exact["target_group_id"], "case-a")

    def test_comma_lists_require_a_completed_reference_boundary(self):
        text = ("2001 SCC 2. 2002 SCC 3. Whiten, supra, at paras. 98 and 100, and Hill, supra. "
                "Whiten, supra, although Jones and Hill, supra. Whiten and Hill, supra.")
        anchors = [anchor(text, "2001 SCC 2", name="Whiten"),
                   anchor(text, "2002 SCC 3", name="Hill", target="case-b", mention_id="b")]
        records = resolve(text, anchors)
        self.assertEqual(records[1]["target_group_id"], "case-b")
        boundary = records[1]["list_boundary_evidence"]
        self.assertEqual(boundary["mention_id"], records[0]["mention_id"])
        self.assertEqual(text[boundary["connector_start"]:boundary["connector_end"]], ", and ")
        self.assertEqual(records[3]["resolution_status"], "ambiguous")
        self.assertNotIn("list_boundary_evidence", records[3])
        self.assertEqual(records[4]["resolution_status"], "ambiguous")
        self.assertEqual(records[4]["candidate_target_ids"], ["case-a", "case-b"])

    def test_full_citation_and_court_qualifier_complete_a_comma_list_item(self):
        text = "2001 SCC 2. Bailey (1983), 4 C.C.C. (3d) 21 (Ont. C.A.), and Voykin, supra."
        anchors = [anchor(text, "2001 SCC 2", name="Voykin"),
                   anchor(text, "(1983), 4 C.C.C. (3d) 21", name="Bailey", target="case-b", mention_id="b")]
        result = resolve(text, anchors)[0]
        self.assertEqual(result["target_group_id"], "case-a")
        self.assertEqual(result["list_boundary_evidence"]["mention_id"], "b")

    def test_complete_royal_titles_allow_c_v_syntax_but_no_party_substitution(self):
        text = ("Dans R. c. Boisjoly, [1972] R.C.S. 42. "
                "R. v. Boisjoly, supra. Jones v. Boisjoly, supra.")
        anchors = [anchor(text, "[1972] R.C.S. 42", name="")]
        royal, other = resolve(text, anchors)
        self.assertEqual(royal["raw"], "R. v. Boisjoly, supra")
        self.assertEqual(royal["target_group_id"], "case-a")
        self.assertTrue(royal["case_title_separator_normalized"])
        self.assertEqual(other["resolution_status"], "ambiguous")
        self.assertIsNone(other["target_group_id"])
        anchors.append(anchor(text, "[1972] R.C.S. 42", name="R. c. Boisjoly", target="case-b", mention_id="b"))
        self.assertEqual(resolve(text, anchors)[0]["resolution_status"], "ambiguous")

    def test_french_pinpoint_articles_and_ranges_preserve_the_complete_span(self):
        text = "2001 CSC 2. Émond, précité, à la p. 261. Émond, précité, aux pp. 67 à 70."
        records = resolve(text, [anchor(text, "2001 CSC 2", name="Émond")])
        self.assertEqual([r["pinpoint"] for r in records], ["à la p. 261", "aux pp. 67 à 70"])
        self.assertEqual(records[1]["raw"], "Émond, précité, aux pp. 67 à 70")

    def test_generic_judicial_roles_are_not_bare_case_names_but_marked_names_remain(self):
        text = ("Judges v. Attorney-General of Saskatchewan, 1937 ABC 209. "
                "Judges Act; Judges were appointed; Justice considered Judges. Judges, supra.")
        anchors = [anchor(text, "1937 ABC 209", name="Judges v. Attorney-General of Saskatchewan")]
        shorts = resolve(text, anchors)
        self.assertEqual(shorts[0]["target_group_id"], "case-a")
        bare = resolve_named_mentions(text, anchors, exclude_spans=[(r["start"], r["end"]) for r in shorts])
        self.assertEqual(bare, [])

    def test_bare_fisher_honorifics_and_investigation_keep_candidates_without_links(self):
        text = ("R. v. Fisher, 2001 SCC 2. Mr. Fisher; Ms Fisher; Mrs. Fisher; "
                "Justice Fisher; le juge Fisher; M. Fisher; Mme Fisher; "
                "the Fisher Investigation; enquête sur Fisher.")
        anchors = [anchor(text, "2001 SCC 2", name="R. v. Fisher")]
        records = resolve_named_mentions(text, anchors)
        self.assertEqual(len(records), 9)
        self.assertTrue(all(r["resolution_basis"] == "person_or_investigation_name_context" for r in records))
        self.assertTrue(all(r["resolution_status"] == "blocked" for r in records))
        self.assertTrue(all(r["candidate_target_ids"] == ["case-a"] for r in records))
        self.assertTrue(all(r["target_group_id"] is None for r in records))

    def test_fisher_legal_reference_remains_available_after_person_context_guard(self):
        text = "R. v. Fisher, 2001 SCC 2. We applied Fisher. The Fisher principle was followed."
        records = resolve_named_mentions(text, [anchor(text, "2001 SCC 2", name="R. v. Fisher")])
        self.assertEqual([r["raw"] for r in records], ["Fisher", "Fisher"])
        self.assertTrue(all(r["resolution_status"] == "resolved" for r in records))
        self.assertTrue(all(r["target_group_id"] == "case-a" for r in records))


if __name__ == "__main__":
    unittest.main()
