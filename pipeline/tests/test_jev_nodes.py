"""Jev node selection, option generation and adoption (method card 09). No network.

Fixture sentences are short constructed examples in the shape of native text;
the joint-title and Morris/Mason facts used elsewhere are verified in
test_reporter_context_identity.py.
"""
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jev_client as jc
import jev_nodes as jn

CFG = jc.load_config()


def choice(top, p=0.95, others=("x",)):
    probs = {top: p}
    rest = (1 - p) / len(others)
    probs.update({o: rest for o in others})
    return {"type": "choice", "choice": top, "probabilities": probs}


class SelectionTests(unittest.TestCase):
    def test_row_status_separates_not_citation_from_uncounted(self):
        self.assertEqual(jn.row_status(""), "citation_counted")
        self.assertEqual(jn.row_status("date_form|non_citation_word"), "not_citation")
        self.assertEqual(jn.row_status("non_case_periodical"), "not_citation")
        self.assertEqual(jn.row_status("unrecognized_series_prefix"), "citation_uncounted")
        self.assertEqual(jn.row_status("unverified_id_prefix|date_form"), "not_citation")

    def test_n1_scope(self):
        date = {"candidate_id": "a", "rejected_reason": "date_form"}
        self.assertEqual(jn.n1_scope(date, 0, readmit=True), ("readmit", "L2"))
        # Readmission is off by default; lexical rejections are only sampled for audit.
        self.assertIsNone(jn.n1_scope(date, 0))
        self.assertEqual(jn.n1_scope(date, 0, lexical_audit_rate=1.0), ("audit", "L0"))
        self.assertIsNone(jn.n1_scope({"candidate_id": "a", "rejected_reason": "unrecognized_series_prefix"}, 1.0))
        self.assertEqual(sorted(jn.n1_question()), ["candidate_type"])
        self.assertEqual(sorted(jn.n1_question(True)), ["candidate_type", "is_case_citation"])
        self.assertIsNone(jn.n1_scope({"candidate_id": "a", "rejected_reason": "docket_not_decision"}, 0))
        self.assertEqual(jn.n1_scope({"candidate_id": "a", "jurisdiction": "UNSUPPORTED"}, 0), ("reject", "L2"))
        self.assertIsNone(jn.n1_scope({"candidate_id": "a", "jurisdiction": "UNSUPPORTED",
                                       "year_vol_ambiguity": "unresolved_year_vs_vol"}, 0))
        self.assertEqual(jn.n1_scope({"candidate_id": "a", "jurisdiction": "CA"}, 1.0), ("audit", "L0"))

    def test_n1_decide_tiers(self):
        resp = lambda c, noul: {"answers": {"candidate_type": choice(c, 0.97), "is_case_citation": {"noul": noul}}}
        self.assertEqual(jn.n1_decide(CFG, "readmit", resp("case_citation", 0.95))[0], "adopt")
        self.assertEqual(jn.n1_decide(CFG, "readmit", resp("case_citation", 0.4))[:2],
                         ("review", "agreement_check_failed"))
        self.assertEqual(jn.n1_decide(CFG, "reject", resp("date", 0.1))[0], "adopt")
        self.assertEqual(jn.n1_decide(CFG, "reject", resp("case_citation_bad_span", 0.9))[1],
                         "is_or_part_of_case_citation")
        self.assertEqual(jn.n1_decide(CFG, "audit", resp("date", 0.1))[:2], ("reject", "audit_only"))

    def test_n2_options_and_parallel_exclusion(self):
        text = "Since the Supreme Court’s 1980 decision in Pettkus v. Becker, [1980] 2 S.C.R. 834"
        opts = jn.n2_options(text, text.index("[1980]"))
        self.assertIn("Pettkus v. Becker", opts)
        self.assertTrue(jn.follows_citation("R. v. Suberu, 2009 SCC 33, [2009]"))
        self.assertFalse(jn.follows_citation("decision in Pettkus v. Becker, "))
        self.assertEqual(jn.n2_scope({"name_rejected_reason": "no_separator_before_v",
                                      "preceding_text": "in Pettkus v. Becker, "}), "ask")
        self.assertIsNone(jn.n2_scope({"name_rejected_reason": "no_separator_before_v",
                                       "rejected_reason": "date_form"}))

    def test_n5_names_need_a_string_citation(self):
        text = ("restraint of trade: Mason v. Provident Clothing & Supply Co. Ltd., [1913] A.C. 724; "
                "Morris v. Saxelby, [1916] 1 A.C. 688")
        names = jn.n5_names(text, text.index("[1916]"))
        self.assertTrue(any(n.startswith("Morris v. Saxelby") for n in names))
        self.assertTrue(any("Mason v. Provident" in n for n in names))
        self.assertEqual(jn.n5_names("in Pettkus v. Becker, [1980]", 25), [])

    def test_option_index_rejects_abstentions(self):
        # Regression: Jev answered "none" and the N5 parser read it as option n<int>.
        self.assertEqual(jn.option_index("n2", "n", 3), 1)
        self.assertIsNone(jn.option_index("none", "n", 3))
        self.assertIsNone(jn.option_index("no_name_here", "o", 3))
        self.assertIsNone(jn.option_index("o4", "o", 3))
        self.assertIsNone(jn.option_index("", "D", 3))

    def test_twin_spans_are_rejected_together(self):
        # Regression (run B2): "1980 Chev 4" was read as a neutral and as a
        # vol/abbr/page twin; rejecting only one twin let the other be counted.
        import pyarrow as pa
        import pyarrow.parquet as pq
        from collections import Counter
        from jev_classify import postpass, stamp_rule
        text = "Vehicle list: 1980 Chev 4 door sedan, blue."
        s = text.index("1980")
        e = s + len("1980 Chev 4")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pq.write_table(pa.table({"citation_en": ["2020 BCSC 1"], "name_en": ["A v. B"],
                                     "unofficial_text_en": [text]}), tmp / "BCSC.parquet")
            base = dict(corpus_row_index="0", source_decision_citation="BCSC_2020bcsc1",
                        match_start_offset=str(s), match_end_offset=str(e), rejected_reason="",
                        candidate_case_name="", name_rejected_reason="", preceding_text=text[:s],
                        self_citation="", suffix_annotations_json="[]")
            rows = [stamp_rule(dict(base, candidate_id="neutral", jurisdiction="UNSUPPORTED")),
                    stamp_rule(dict(base, candidate_id="volpage", jurisdiction="UNSUPPORTED",
                                    year_vol_ambiguity="unresolved_year_vs_vol"))]
            fields = list(rows[1])
            tmp_csv = tmp / "classified.csv.tmp"
            with tmp_csv.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                w.writerows(rows)
            t = lambda body: {"model": "m", "answers": {
                "candidate_type": choice("other", 0.97, ("case_citation", "date")),
                "is_case_citation": {"type": "noul", "noul": 0.02}}}
            cfg = dict(CFG, nodes={"N1_candidate_type": {"enabled": True, "spec_version": 1, "audit_rate": 0}})
            client = jc.JevClient("live", config=cfg, cache_path=tmp / "c.sqlite", transport=t)
            args = type("A", (), {"corpus": str(tmp / "BCSC.parquet"), "text_policy": "en_then_fr"})()
            postpass(str(tmp_csv), str(tmp / "classified.csv"), fields, args, client, Counter())
            client.close()
            with (tmp / "classified.csv").open(encoding="utf-8") as f:
                got = {r["candidate_id"]: r for r in csv.DictReader(f)}
            self.assertTrue(all(r["rejected_reason"] == "model_judged_not_case:other" for r in got.values()))
            self.assertTrue(all(r["rule_rejected_reason"] == "" for r in got.values()))

    def test_rejection_does_not_promote_unvetted_overlap(self):
        # Regression (run B3): rejecting "15 Stage 1" left the overlapping
        # "14 The Relevant Law. 15" uncontested in merge arbitration.
        import pyarrow as pa
        import pyarrow.parquet as pq
        from collections import Counter
        from jev_classify import postpass, stamp_rule
        text = "C. Parties. 14 The Relevant Law. 15 Stage 1 of the test"
        a_s, a_e = text.index("14 The"), text.index("15 Stage") + 2
        b_s, b_e = text.index("15 Stage"), text.index("Stage 1") + 7
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pq.write_table(pa.table({"citation_en": ["2020 BCSC 1"], "name_en": ["A v. B"],
                                     "unofficial_text_en": [text]}), tmp / "BCSC.parquet")
            base = dict(corpus_row_index="0", source_decision_citation="BCSC_2020bcsc1", rejected_reason="",
                        candidate_case_name="", name_rejected_reason="", self_citation="",
                        suffix_annotations_json="[]", year_vol_ambiguity="")
            rows = [stamp_rule(dict(base, candidate_id="toc_a", match_start_offset=str(a_s), match_end_offset=str(a_e),
                                    jurisdiction="CA", preceding_text=text[:a_s])),
                    stamp_rule(dict(base, candidate_id="toc_b", match_start_offset=str(b_s), match_end_offset=str(b_e),
                                    jurisdiction="UNSUPPORTED", preceding_text=text[:b_s]))]
            fields = list(rows[0])
            tmp_csv = tmp / "classified.csv.tmp"
            with tmp_csv.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                w.writerows(rows)
            t = lambda body: {"model": "m", "answers": {
                "candidate_type": choice("internal_reference", 0.95, ("case_citation", "date")),
                "is_case_citation": {"type": "noul", "noul": 0.03}}}
            # audit_rate 1.0: the competitor was already asked (audit only) in round 1;
            # its stored answer must still be judged by the overlap rule.
            for audit in (0, 1.0):
                cfg = dict(CFG, nodes={"N1_candidate_type": {"enabled": True, "spec_version": 1, "audit_rate": audit}})
                client = jc.JevClient("live", config=cfg, cache_path=tmp / ("c%s.sqlite" % audit), transport=t)
                args = type("A", (), {"corpus": str(tmp / "BCSC.parquet"), "text_policy": "en_then_fr"})()
                out = tmp / ("classified%s.csv" % audit)
                postpass(str(tmp_csv), str(out), fields, args, client, Counter(), keep_input=True)
                client.close()
                with out.open(encoding="utf-8") as f:
                    got = {r["candidate_id"]: r for r in csv.DictReader(f)}
                self.assertTrue(got["toc_b"]["rejected_reason"].startswith("model_judged_not_case"), audit)
                self.assertTrue(got["toc_a"]["rejected_reason"].startswith("model_"), audit)

    def test_header_dates_dedupe_and_label(self):
        header = "Judgment: 1990: May 31. Heard 1989: October 3. Delivered May 31, 1990."
        dates = jn.header_dates(header)
        self.assertEqual([d[0] for d in dates], ["1990-05-31", "1989-10-03"])
        state = jn.n8_state(header, dates)
        self.assertEqual(state.count("[D1]"), 2)
        self.assertIn("[D2] 1989: October 3", state)

    def test_history_precondition(self):
        canon = jn.court_canonicalizer()
        h = jn.load_court_hierarchy()
        self.assertEqual(jn.history_eligible(canon("BCCA"), canon("BCSC"), 2019, 2018, h), (True, ""))
        self.assertEqual(jn.history_eligible(canon("SCC"), canon("BCSC"), 2019, 2017, h), (True, ""))
        self.assertEqual(jn.history_eligible(canon("BCCA"), canon("BCSC"), 2019, 2020, h), (False, "cited_later"))
        self.assertEqual(jn.history_eligible(canon("BCSC"), canon("BCCA"), 2019, 2018, h)[1], "hierarchy_unsupported")
        self.assertEqual(jn.history_eligible(canon("FCA"), canon("TCC"), 2014, 2013, h), (True, ""))


class ClassifyPostpassTests(unittest.TestCase):
    """N2 adoption end-to-end on a one-document parquet; rule values stay in rule_* columns."""

    def test_case_name_adoption_keeps_rule_columns(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        from jev_classify import RULE_COLUMNS, postpass, stamp_rule
        text = "As this Court held in Pettkus v. Becker, [1980] 2 S.C.R. 834, the remedy applies."
        start = text.index("[1980]")
        end = start + len("[1980] 2 S.C.R. 834")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pq.write_table(pa.table({"citation_en": ["2020 BCCA 1"], "name_en": ["A v. B"],
                                     "unofficial_text_en": [text]}), tmp / "BCCA.parquet")
            row = stamp_rule({"candidate_id": "c1", "corpus_row_index": "0",
                              "source_decision_citation": "BCCA_2020bcca1",
                              "match_start_offset": str(start), "match_end_offset": str(end),
                              "rejected_reason": "", "candidate_case_name": "",
                              "name_rejected_reason": "no_separator_before_v",
                              "preceding_text": text[:start], "self_citation": "false",
                              "jurisdiction": "CA", "suffix_annotations_json": "[]"})
            fields = list(row)
            tmp_csv = tmp / "classified.csv.tmp"
            with tmp_csv.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                w.writerow(row)

            def transport(body):
                crit = body["questions"]["case_name"]["criteria"]
                key = next(k for k, v in crit.items() if v == "Pettkus v. Becker")
                return {"model": "jev-1.13.0", "answers": {"case_name": choice(key, 0.95, ("no_name_here",))}}
            cfg = dict(CFG, nodes={"N2_case_name": {"enabled": True, "spec_version": 1}})
            client = jc.JevClient("live", config=cfg, cache_path=tmp / "c.sqlite", transport=transport)
            args = type("A", (), {"corpus": str(tmp / "BCCA.parquet"), "text_policy": "en_then_fr"})()
            from collections import Counter
            stats = Counter()
            out = tmp / "classified.csv"
            postpass(str(tmp_csv), str(out), fields, args, client, stats)
            client.close()
            with out.open(encoding="utf-8") as f:
                got = next(csv.DictReader(f))
            self.assertEqual(got["candidate_case_name"], "Pettkus v. Becker")
            self.assertEqual(got["case_name_source"], "jev")
            self.assertEqual(got["name_rejected_reason"], "")
            self.assertEqual(got["rule_name_rejected_reason"], "no_separator_before_v")
            self.assertEqual(got["rule_candidate_case_name"], "")
            with (tmp / "jev" / "N2_case_name.csv").open(encoding="utf-8") as f:
                ledger = list(csv.DictReader(f))
            self.assertEqual(ledger[0]["adopted"], "true")
            self.assertTrue(set(RULE_COLUMNS) <= set(got))


if __name__ == "__main__":
    unittest.main()
