"""Offline corruption fixtures for the read-only run checker."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_run import check_run, TENTATIVE_FIELDS


class RunCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name) / "run_fixture"
        self.run.mkdir()
        self.write_json("run_manifest.json", {
            "status": "complete", "input_identity_verified_unchanged": True,
            "params": {"courts": ["SCC", "ONCA"], "limit_batches": None},
            "input_identity": {"fingerprint": "fixture", "files": {"fixture": "fixture"}}})
        self.members = [dict(merged_group_id="g1", is_primary="true", distinct_decisions_count="2",
                             kept="true", group_foreign_status="FOREIGN", group_origin_country="GB",
                             group_origin_status="DETERMINED"),
                        dict(merged_group_id="g2", is_primary="true", distinct_decisions_count="1",
                             kept="false", group_foreign_status="FOREIGN", group_origin_country="GB",
                             group_origin_status="DETERMINED")]
        self.write_rows("select_out/selected.csv", self.members)
        self.write_json("select_out/manifest.json", {"threshold_dd": 2, "stats": dict(
            rows_total=2, kept=1, dropped=1, groups_total=2, groups_kept=1)})
        self.effective = [dict(source_decision=s, merged_group_id=g, status="counted",
                               exclusion_reason="", identity_status=b)
                          for s, g, b in (("s1", "g1", "anchor"), ("s2", "g1", "anchor"), ("s1", "g2", "cocitation"))]
        self.effective.append(dict(source_decision="s0", merged_group_id="g1", status="excluded_self",
                                   exclusion_reason="group_self", identity_status="anchor"))
        self.write_rows("decide_out/cross_court/effective_sources.csv", self.effective)
        self.edges = [dict(source_decision=s, resolved_cited_case=g,
                           foreign_status="FOREIGN" if g == "g1" else "UNDETERMINED",
                           origin_country="GB" if g == "g1" else "", group_origin_country="GB",
                           group_origin_status="DETERMINED", group_foreign_status="FOREIGN",
                           edge_support="supported" if g == "g1" else "heuristic_only",
                           identity_status="anchor" if g == "g1" else "cocitation_candidate",
                           origin_evidence_ids="e1" if g == "g1" else "", mention_count="1",
                           mention_detail_key="SCC|2001||scc||1",
                           distinct_decisions_count="2" if g == "g1" else "1", case_name_modal="Example")
                      for s, g in (("s1", "g1"), ("s2", "g1"), ("s1", "g2"))]
        self.write_rows("edges/citation_edges.csv", self.edges)
        self.write_rows("edges/foreign_edges.csv", self.edges[:2])
        self.write_rows("edges/tentative_edges.csv", [{k: self.edges[2][k] for k in TENTATIVE_FIELDS}])
        self.write_rows("edges/self_excluded_edges.csv", [dict(source_decision="s0", resolved_cited_case="g1",
                                                               exclusion_reason="group_self")])
        self.write_json("edges/manifest.json", {"stats": dict(
            edges_total=3, edges_foreign=2, edges_domestic_ca=0, edges_undetermined=1, edges_conflict=0,
            edges_supported=2, edges_heuristic_only=1, self_excluded_sources=1, tentative_edges=1)})

    def write_json(self, relative, value):
        path = self.run / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def write_rows(self, relative, rows):
        path = self.run / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def codes(self):
        report = check_run(self.run)
        return report, {i["code"] for i in report["issues"] if i["severity"] == "error"}

    def test_consistent_run_and_no_mutation(self):
        before = {p: p.read_bytes() for p in self.run.rglob("*") if p.is_file()}
        report, codes = self.codes()
        self.assertEqual(report["status"], "passed", codes)
        self.assertEqual(report["metrics"]["edges_total"], 3)
        self.assertEqual(before, {p: p.read_bytes() for p in self.run.rglob("*") if p.is_file()})

    def test_same_count_wrong_source_is_detected(self):
        self.edges[0]["source_decision"] = "wrong_source"
        self.write_rows("edges/citation_edges.csv", self.edges)
        _, codes = self.codes()
        self.assertTrue({"effective_without_edge", "edge_without_effective"} <= codes)

    def test_zero_mentions_and_empty_provenance_are_rejected(self):
        self.edges[0].update(mention_count="0", mention_detail_key="")
        self.write_rows("edges/citation_edges.csv", self.edges)
        _, codes = self.codes()
        self.assertTrue({"edge_without_positive_mentions", "edge_without_mention_provenance"} <= codes)

    def test_self_citation_reintroduced(self):
        self.edges[0]["source_decision"] = "s0"
        self.write_rows("edges/citation_edges.csv", self.edges)
        _, codes = self.codes()
        self.assertIn("self_citation_reintroduced", codes)

    def test_foreign_cannot_inherit_from_heuristic(self):
        self.edges[2]["foreign_status"] = "FOREIGN"
        self.edges[2]["origin_country"] = "GB"
        self.write_rows("edges/citation_edges.csv", self.edges)
        _, codes = self.codes()
        self.assertTrue({"heuristic_origin_leak", "foreign_without_support"} <= codes)

    def test_duplicate_edges(self):
        self.write_rows("edges/citation_edges.csv", self.edges + [self.edges[0]])
        _, codes = self.codes()
        self.assertTrue({"duplicate_edges", "edge_dd_mismatch"} <= codes)

    def test_supported_flag_requires_effective_identity_evidence(self):
        self.effective[0]["identity_status"] = "cocitation"
        self.write_rows("decide_out/cross_court/effective_sources.csv", self.effective)
        _, codes = self.codes()
        self.assertIn("edge_identity_support_mismatch", codes)

    def test_displayed_identity_must_agree_with_effective_path(self):
        self.edges[0]["identity_status"] = "cocitation_candidate"
        self.write_rows("edges/citation_edges.csv", self.edges)
        self.write_rows("edges/foreign_edges.csv", self.edges[:2])
        _, codes = self.codes()
        self.assertIn("edge_identity_label_mismatch", codes)

    def test_selection_and_primary_contract(self):
        self.members[0]["is_primary"] = "false"
        self.members[1]["kept"] = "true"
        self.write_rows("select_out/selected.csv", self.members)
        _, codes = self.codes()
        self.assertTrue({"bad_primary", "threshold_mismatch"} <= codes)

    def test_zero_kept_is_a_valid_sparse_production_counter(self):
        for row in self.members:
            row["kept"] = "false"
        self.write_rows("select_out/selected.csv", self.members)
        self.write_json("select_out/manifest.json", {"threshold_dd": 10, "stats": dict(
            rows_total=2, dropped=2, groups_total=2, groups_kept=0)})
        report, codes = self.codes()
        self.assertEqual(report["status"], "passed", codes)

    def test_view_content_not_just_membership(self):
        wrong = dict(self.edges[0], origin_evidence_ids="wrong_evidence")
        self.write_rows("edges/foreign_edges.csv", [wrong, self.edges[1]])
        _, codes = self.codes()
        self.assertIn("view_content_mismatch", codes)

    def test_manifest_failure_and_missing_file(self):
        (self.run / "run_manifest.json").write_text("{broken", encoding="utf-8")
        (self.run / "edges/citation_edges.csv").unlink()
        _, codes = self.codes()
        self.assertTrue({"manifest_unreadable", "artifact_missing"} <= codes)

    def test_empty_run_manifest_cannot_pass(self):
        self.write_json("run_manifest.json", {})
        _, codes = self.codes()
        self.assertTrue({"run_not_complete", "inputs_not_verified", "input_identity_missing"} <= codes)

    def test_tentative_view_requires_even_empty_columns(self):
        row = {k: self.edges[2][k] for k in TENTATIVE_FIELDS if k != "origin_evidence_ids"}
        self.write_rows("edges/tentative_edges.csv", [row])
        _, codes = self.codes()
        self.assertIn("columns_missing", codes)

    def test_truncated_csv_fails_closed(self):
        with (self.run / "select_out/selected.csv").open("a", encoding="utf-8") as f:
            f.write('"unfinished')
        _, codes = self.codes()
        self.assertIn("artifact_unreadable", codes)

    def test_malformed_nested_manifest_fails_closed(self):
        self.write_json("select_out/manifest.json", {"threshold_dd": 2, "stats": []})
        _, codes = self.codes()
        self.assertIn("invalid_artifact_schema", codes)

    def test_output_seal_detects_same_length_content_change(self):
        path = self.run / "edges/foreign_edges.csv"
        files = {"edges/foreign_edges.csv": hashlib.sha256(path.read_bytes()).hexdigest()}
        manifest = json.loads((self.run / "run_manifest.json").read_text())
        manifest["output_identity"] = {"files": files, "fingerprint": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}
        self.write_json("run_manifest.json", manifest)
        self.assertEqual(self.codes()[0]["status"], "passed")
        path.write_bytes(path.read_bytes().replace(b"Example", b"Changed"))
        self.assertIn("sealed_artifact_changed", self.codes()[1])

    def test_gzip_is_checked_without_unpacking(self):
        for path in self.run.rglob("*.csv"):
            with gzip.open(str(path) + ".gz", "wb") as f:
                f.write(path.read_bytes())
            path.unlink()
        report, codes = self.codes()
        self.assertEqual(report["status"], "passed", codes)
        self.assertTrue(all(v["compressed"] for v in report["artifacts"].values()))
        self.assertFalse(list(self.run.rglob("*.csv")))


if __name__ == "__main__":
    unittest.main()
