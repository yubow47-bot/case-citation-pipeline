"""Coverage diagnostics keep candidate, counted-position and final-edge units separate."""
import contextlib
import csv
import gzip
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import coverage_report


class CoverageReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parents[2] / "implementation")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tables = self.root / "decisions"
        self.tables.mkdir()
        self.write_csv(self.tables / "reporter_jurisdiction.csv",
                       [{"abbreviation": "A.A.", "normalized_key": "aa"}], compressed=True)
        self.write_csv(self.tables / "neutral_court_codes.csv", [{"court_code": "NC"}], compressed=True)
        self.write_csv(self.tables / "series_prefix.csv",
                       [{"canonical_prefix": "Known", "normalized_key": "known"}], compressed=True)
        self.table_patch = patch.object(coverage_report, "DECISIONS", str(self.tables))
        self.table_patch.start()
        self.addCleanup(self.table_patch.stop)

    def write_csv(self, path, rows, compressed=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = sorted({key for row in rows for key in row})
        if compressed:
            path = Path(str(path) + ".gz")
        opener = gzip.open if compressed else open
        with opener(path, "wt", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def candidate(self, cid, source="S1", start=0, status="counted", family="XX", **extra):
        row = dict(candidate_id=cid, source_decision_citation=source, corpus_row_index="1",
                   match_start_offset=str(start), match_end_offset=str(start + 10),
                   arbitration_status=status, citation_kind="reporter", jurisdiction="UNSUPPORTED",
                   abbreviation=family, shape_name="shape_vol_abbr_page", rejected_reason="")
        row.update(extra)
        return row

    def make_run(self):
        rows = [
            self.candidate("c1"),
            self.candidate("c2", status="alternative_same_key"),
            self.candidate("c3", status="alternative_unsupported_reading", family="YY"),
            self.candidate("c4", start=5, status="overlap_undecided", family="HOT"),
            self.candidate("c5", source="S2"),
            self.candidate("c6", source="S3", status="alternative_unsupported_reading", family="HOT"),
            self.candidate("c7", source="S4", status="alternative_unsupported_reading", family="HOT"),
            self.candidate("c8", source="S5", status="alternative_unsupported_reading", family="HOT"),
            self.candidate("c9", start=20, family="", citation_kind="neutral",
                           shape_name="shape_neutral_bare", token="NC"),
            self.candidate("c10", start=40, family="A.A."),
            self.candidate("c11", start=60, jurisdiction="CA", family="CA REPORTER"),
            self.candidate("c12", start=80, status="rejected_row", family="",
                           leading_abbr="See", rejected_reason="unrecognized_series_prefix"),
            self.candidate("c13", source="", start=100, family="EMPTY"),
            self.candidate("c14", start=120, status="self_citation_row"),
            self.candidate("c15", start=140, status="cross_boundary_invalid"),
            self.candidate("c16", start=160, status="year_reread_as_vol_invalid"),
        ]
        # Same source, row and offsets in another court remain another position.
        courts = {"ONCA": rows, "BCCA": [self.candidate("bc1")]}
        for court, candidates in courts.items():
            self.write_csv(self.root / "classify_out" / court / "classified.csv", candidates,
                           compressed=court == "BCCA")
            mentions = [{key: value for key, value in row.items()
                         if key not in ("abbreviation", "token", "leading_abbr")}
                        for row in candidates]
            self.write_csv(self.root / "merge_out" / court / "mentions_candidates.csv", mentions,
                           compressed=True)
        edges = [
            dict(source_decision="S1", resolved_cited_case="G1", edge_support="supported",
                 foreign_status="DOMESTIC_CA", origin_country="CA"),
            dict(source_decision="S1", resolved_cited_case="G2", edge_support="heuristic_only",
                 foreign_status="FOREIGN", origin_country="GB"),
            dict(source_decision="S2", resolved_cited_case="G3", edge_support="supported",
                 foreign_status="UNDETERMINED", origin_country=""),
            dict(source_decision="S3", resolved_cited_case="G4", edge_support="heuristic_only",
                 foreign_status="CONFLICT", origin_country=""),
            dict(source_decision="", resolved_cited_case="G5", edge_support="heuristic_only",
                 foreign_status="FOREIGN", origin_country="AU"),
        ]
        edges.append(dict(edges[1]))
        self.write_csv(self.root / "edges" / "citation_edges.csv", edges, compressed=True)

    def test_run_separates_units_and_ranks_counted_affected_sources_first(self):
        self.make_run()
        with contextlib.redirect_stdout(io.StringIO()):
            coverage_report.main(["--run-dir", str(self.root)])
        output = self.root / "coverage"
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        candidates = summary["candidates"]
        self.assertEqual((candidates["rows"], candidates["exact_span_positions"],
                          candidates["distinct_sources"]), (17, 15, 5))
        groups = candidates["by_arbitration_group"]
        self.assertEqual({key: value["rows"] for key, value in groups.items()},
                         dict(rejected_row=1, self=1, superseded=2, alternative=5,
                              conflict=1, counted=7, other=0))
        self.assertGreater(sum(value["exact_span_positions"] for value in groups.values()),
                           candidates["exact_span_positions"])
        self.assertEqual(summary["counted_positions"], {
            "positions": 7, "distinct_sources": 2, "unsupported_positions": 6,
            "unsupported_distinct_sources": 2,
            "by_jurisdiction": {"CA": {"positions": 1, "distinct_sources": 1},
                                "UNSUPPORTED": {"positions": 6, "distinct_sources": 2}}})
        self.assertEqual(summary["by_court"]["ONCA"], {
            "candidates": {"rows": 16, "exact_span_positions": 14, "distinct_sources": 5},
            "counted_positions": {"positions": 6, "distinct_sources": 2,
                                  "unsupported_positions": 5, "unsupported_distinct_sources": 2}})
        self.assertEqual(summary["by_court"]["BCCA"]["counted_positions"], {
            "positions": 1, "distinct_sources": 1,
            "unsupported_positions": 1, "unsupported_distinct_sources": 1})
        self.assertEqual(summary["by_shape"]["shape_neutral_bare"], {
            "candidates": {"rows": 1, "exact_span_positions": 1, "distinct_sources": 1},
            "counted_positions": {"positions": 1, "distinct_sources": 1,
                                  "unsupported_positions": 1, "unsupported_distinct_sources": 1}})
        self.assertEqual(summary["by_shape"]["shape_vol_abbr_page"]["candidates"]["rows"], 16)
        relations = summary["relations"]
        self.assertEqual((relations["rows"], relations["unique_relations"],
                          relations["distinct_sources"]), (6, 5, 3))
        self.assertEqual(relations["by_edge_support"]["heuristic_only"],
                         {"unique_relations": 3, "distinct_sources": 2})
        self.assertEqual(relations["by_origin_country_status"]["known"]["unique_relations"], 3)
        joint = {(row["edge_support"], row["foreign_status"]): row
                 for row in relations["by_edge_support_and_foreign_status"]}
        self.assertEqual(joint[("heuristic_only", "FOREIGN")]["unique_relations"], 2)
        self.assertEqual(joint[("heuristic_only", "FOREIGN")]["distinct_sources"], 1)
        with (output / "reporter.csv").open(encoding="utf-8", newline="") as f:
            families = list(csv.DictReader(f))
        self.assertEqual(families[0]["family"], "xx")
        self.assertEqual(families[0]["counted_unsupported_positions"], "3")
        self.assertEqual(families[0]["counted_unsupported_distinct_sources"], "2")
        self.assertEqual(json.loads(families[0]["counted_unsupported_by_court"]), {
            "BCCA": {"positions": 1, "distinct_sources": 1},
            "ONCA": {"positions": 2, "distinct_sources": 2}})
        self.assertEqual(json.loads(families[0]["candidate_by_court"])["ONCA"]["positions"], 5)
        by_family = {row["family"]: row for row in families}
        self.assertLess(int(by_family["aa"]["rank"]), int(by_family["hot"]["rank"]))
        self.assertEqual(by_family["aa"]["table_status"], "in_table_unresolved")
        self.assertEqual(by_family["xx"]["table_status"], "absent")
        self.assertEqual(by_family["empty"]["candidate_distinct_sources"], "0")
        with (output / "neutral.csv").open(encoding="utf-8", newline="") as f:
            neutral = list(csv.DictReader(f))
        self.assertEqual(neutral[0]["counted_unsupported_positions"], "1")
        with (output / "series.csv").open(encoding="utf-8", newline="") as f:
            series = list(csv.DictReader(f))
        self.assertEqual(series[0]["report_scope"], "rejected_diagnostic")
        self.assertEqual(series[0]["candidate_rejected_row_rows"], "1")
        self.assertEqual(series[0]["counted_unsupported_positions"], "0")
        self.assertIn("not mutually non-overlapping", summary["definitions"]["exact_span_positions"])

    def test_legacy_mode_reads_compressed_csv_and_keeps_existing_columns(self):
        path = self.root / "classified.csv"
        self.write_csv(path, [self.candidate("c1", family="A.A."),
                              self.candidate("c2", source="", family="A.A.")], compressed=True)
        output = self.root / "legacy.csv"
        with contextlib.redirect_stdout(io.StringIO()):
            coverage_report.main(["--kind", "reporter", "--classified", str(path),
                                  "--out", str(output)])
        with output.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(reader.fieldnames, ["rank", "family", "top_printed_form", "rows",
                                                 "distinct_decisions", "cum_pct_rows", "table_status"])
        self.assertEqual(rows[0]["rows"], "2")
        self.assertEqual(rows[0]["distinct_decisions"], "1")
        self.assertEqual(rows[0]["table_status"], "in_table_unresolved")

    def test_sealed_run_is_rejected_before_output_is_created(self):
        (self.root / "run_manifest.json").write_text(json.dumps({
            "status": "complete", "output_identity": {"files": {"existing.csv": "hash"}}}),
            encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Immutable sealed run"):
            coverage_report.run_report(self.root)
        self.assertFalse((self.root / "coverage").exists())


if __name__ == "__main__":
    unittest.main()
