"""Jev in decide (N6, N7) and edges (N4) with a fake transport. No network."""
from collections import Counter
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jev_client as jc

CFG = jc.load_config()


def answer(top, p=0.96, others=("x",)):
    probs = {top: p}
    probs.update({o: (1 - p) / len(others) for o in others})
    return {"type": "choice", "choice": top, "probabilities": probs}


def row(gid, key, basis, primary=False, **extra):
    r = {"merged_group_id": gid, "merge_key": key, "court": "BCCA", "identity_basis": basis,
         "is_primary": "true" if primary else "false", "case_name_modal": "Smith v. Jones",
         "canonical_string": key, "year_printed": "1995", "ruling_identity_status": "",
         "same_name_near_year_peers": "", "observed_deciding_court": ""}
    r.update(extra)
    return r


class DecideTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def client(self, transport, cfg=CFG):
        c = jc.JevClient("live", config=cfg, cache_path=self.tmp / "c.sqlite", transport=transport)
        self.addCleanup(c.close)
        return c

    def test_n6_confirms_only_with_agreement_and_never_moves_members(self):
        import jev_decide
        out = [row("G1", "1995||bcj||1", "anchor", True), row("G1", "|10|bclr|3d|1", "name_year")]
        eff = [{"merged_group_id": "G1", "source_decision": "S1", "identity_status": "name_year",
                "via_member_row_keys": "BCCA||10|bclr|3d|1"}]
        jev_decide.stamp_rule(out)

        def agree(body):
            return {"model": "jev-1.13.0", "answers": {
                "identity": answer("same_judgment", 0.97, ("different_judgment", "cannot_tell")),
                "identity_agrees": {"type": "noul", "noul": 0.95}}}
        stats = Counter()
        jev_decide.apply(out, eff, self.tmp, self.client(agree), stats, output=str(self.tmp))
        self.assertEqual(out[1]["identity_basis"], "model_confirmed")
        self.assertEqual(out[1]["rule_identity_basis"], "name_year")
        self.assertEqual(eff[0]["identity_status"], "model_confirmed")
        self.assertEqual({r["merged_group_id"] for r in out}, {"G1"})

    def test_n6_switch_off_and_failed_agreement_keep_rule(self):
        import jev_decide
        for cfg, noul in ((dict(CFG, count_model_confirmed=False), 0.99), (CFG, 0.3)):
            out = [row("G1", "a", "anchor", True), row("G1", "b", "name_year")]
            jev_decide.stamp_rule(out)
            t = lambda body: {"model": "m", "answers": {
                "identity": answer("same_judgment", 0.97, ("different_judgment", "cannot_tell")),
                "identity_agrees": {"type": "noul", "noul": noul}}}
            c = jc.JevClient("live", config=cfg, cache_path=self.tmp / ("c%s.sqlite" % noul), transport=t)
            self.addCleanup(c.close)
            jev_decide.apply(out, [], self.tmp, c, Counter())
            self.assertEqual(out[1]["identity_basis"], "name_year")

    def test_n7_marks_but_never_splits(self):
        import jev_decide
        out = [row("G1", "a", "anchor", True, ruling_identity_status="uncertain_ruling_identity", year_printed="1995"),
               row("G1", "b", "anchor", ruling_identity_status="uncertain_ruling_identity", year_printed="1996")]
        jev_decide.stamp_rule(out)
        t = lambda body: {"model": "m", "answers": {"same_ruling": answer(
            "different_levels_same_case", 0.95, ("same_judgment", "different_cases", "cannot_tell"))}}
        jev_decide.apply(out, [], self.tmp, self.client(t), Counter())
        self.assertTrue(all(r["merged_group_id"] == "G1" for r in out))
        self.assertTrue(all(r["ruling_identity_status"] == "uncertain_ruling_identity" for r in out))
        self.assertTrue(all(r["model_ruling_relation"] == "model_distinct_ruling" for r in out))


class EdgesTests(unittest.TestCase):
    def test_n4_marks_history_only_inside_the_hierarchy(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        import jev_edges
        text = "[16] The trial judge's reasons are reported at Xu v. Chu, 2018 BCSC 2222. Mr. Xu sought..."
        s = text.index("2018 BCSC")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pq.write_table(pa.table({"citation_en": ["2019 BCCA 414"], "name_en": ["Xu v. Chu"],
                                     "unofficial_text_en": [text]}), tmp / "BCCA.parquet")
            rows = [{"source_decision": "BCCA_2019bcca414", "resolved_cited_case": "G1",
                     "history_basis": "none", "own_case_history_pair": "false", "history_assessment": "x"},
                    {"source_decision": "BCCA_2019bcca414", "resolved_cited_case": "G2",
                     "history_basis": "none", "own_case_history_pair": "false", "history_assessment": "x"},
                    {"source_decision": "BCCA_2019bcca414", "resolved_cited_case": "G3",
                     "history_basis": "none", "own_case_history_pair": "false", "history_assessment": "x"}]
            groups = {"G1": {"deciding_court": "court:bcsc", "year": "2018", "case_name_modal": "Xu v. Chu"},
                      "G2": {"deciding_court": "court:onca", "year": "2018", "case_name_modal": "Other"},
                      # In the hierarchy, but its parties share nothing with Xu v. Chu.
                      "G3": {"deciding_court": "court:bcsc", "year": "2018", "case_name_modal": "Smith v. Jones"}}
            first = {("BCCA_2019bcca414", "G1"): ("BCCA", 0, s, s + 14),
                     ("BCCA_2019bcca414", "G2"): ("BCCA", 0, s, s + 14),
                     ("BCCA_2019bcca414", "G3"): ("BCCA", 0, s, s + 14)}
            t = lambda body: {"model": "m", "answers": {
                "relation": answer("under_appeal_or_earlier_in_this_case", 0.93,
                                   ("related_proceeding", "precedent", "cannot_tell")),
                "explicitly_stated": {"type": "noul", "noul": 0.9}}}
            c = jc.JevClient("live", config=CFG, cache_path=tmp / "c.sqlite", transport=t)
            stats = Counter()
            jev_edges.apply(rows, groups, first, str(tmp), "en_then_fr", c, stats, str(tmp))
            c.close()
            self.assertEqual((rows[0]["history_basis"], rows[0]["own_case_history_pair"]), ("model", "true"))
            self.assertEqual(rows[1]["history_basis"], "none")  # ONCA is not below BCCA
            self.assertEqual(stats["jev_N4_excluded_hierarchy_unsupported"], 1)
            self.assertEqual(rows[2]["history_basis"], "none")
            self.assertEqual(stats["jev_N4_excluded_party_names_disjoint"], 1)
            self.assertEqual(stats["jev_N4_L1_adopted"], 1)  # only G1 was asked


if __name__ == "__main__":
    unittest.main()
