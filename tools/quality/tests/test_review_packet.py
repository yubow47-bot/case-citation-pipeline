"""Small offline checks for complete, immutable review evidence packets."""
import csv
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools/research"))

from tools.research.fixture import create_fixture, write_csv
from tools.research.core import rows
from tools.quality import common, sample, review_packet


class ReviewPacketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".review-packet-test-", dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.paths = create_fixture(self.base, with_parquet=True)
        self.run = Path(self.paths["run"])
        edge_path = self.run / "edges/citation_edges.csv.gz"
        edges = [r for _, r in rows(edge_path)
                 if r["resolved_cited_case"] == "XC-G000001" and r["source_decision"] in
                 ("SCC_2000scc1", "ONCA_2011onca1")]
        for edge in edges:
            edge["mention_count"] = "2" if edge["source_decision"].startswith("SCC_") else "1"
        write_csv(edge_path, list(edges[0]), edges)
        ledger = self.run / "merge_out/SCC/mentions_candidates.csv.gz"
        mentions = [r for _, r in rows(ledger)]
        mentions.append({**mentions[-1], "candidate_id": "second-counted-occurrence"})
        write_csv(ledger, list(mentions[0]), mentions)
        source = common.open_source(run=self.run)
        self.db_path = self.base / "review.db"
        destination = sqlite3.connect(self.db_path)
        source.db.backup(destination)
        destination.execute("CREATE TABLE runs(run_id TEXT,source_directory TEXT,input_fingerprint TEXT,manifest_json TEXT,imported_at TEXT,status TEXT)")
        destination.execute("CREATE TABLE artifacts(run_id TEXT,relative_path TEXT,sha256 TEXT,row_count INTEGER)")
        destination.execute("INSERT INTO runs VALUES(?,?,?,?,?,?)", (
            source.run_id, str(self.run), source.manifest["input_identity"]["fingerprint"],
            json.dumps(source.manifest), "2026-10-15", "ready"))
        for relative in ("select_out/selected.csv", "edges/citation_edges.csv"):
            destination.execute("INSERT INTO artifacts VALUES(?,?,?,?)", (
                source.run_id, relative, common.artifact_digest(self.run / relative), len(edges)))
        destination.commit()
        destination.close()
        source.close()
        source = common.open_source(db=self.db_path)
        self.samples = sample.stratified_sample(source, with_text=True)
        source.close()
        self.samples_path = self.base / "samples.json"
        self.samples_path.write_text(json.dumps(self.samples, ensure_ascii=False), encoding="utf-8")
        self.output = self.base / "review_output"

    def build(self):
        return review_packet.build_packet(self.samples_path, self.db_path, self.output)

    def records(self):
        return [json.loads(line) for path in sorted(self.output.glob("batch_*.jsonl"))
                for line in path.read_text(encoding="utf-8").splitlines()]

    def test_all_occurrences_members_and_immutable_design_are_retained(self):
        before = {p: common.file_hash(p) for p in (
            self.samples_path, self.db_path, *Path(self.paths["corpus"]).glob("*.parquet"))}
        report = self.build()
        self.assertEqual(report["samples"], 2)
        self.assertEqual(report["counted_occurrences"], 3)
        self.assertEqual(report["occurrence_status"], {"original_text_verified": 3})
        originals = {r["sample_id"]: r for r in self.samples["records"]}
        records = self.records()
        self.assertEqual(len(records), 2)
        for record in records:
            self.assertEqual(record["sample"], originals[record["sample_id"]])
            self.assertEqual(len(record["members"]), 2)
            self.assertEqual(record["record_hash"], record["sample"]["record_hash"])
            self.assertEqual(record["packet_record_sha256"], common.canonical_hash(
                {k: v for k, v in record.items() if k != "packet_record_sha256"}))
            self.assertTrue(record["occurrence_coverage"]["all_counted_occurrences_retained"])
            for occurrence in record["occurrences"]:
                self.assertEqual(occurrence["status"], "original_text_verified")
                self.assertTrue(occurrence["original_context"]["mention_fully_included"])
        self.assertEqual(before, {p: common.file_hash(p) for p in before})
        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        for name, expected in manifest["files"].items():
            self.assertEqual(common.file_hash(self.output / name), expected["sha256"])
        with (self.output / "labels_template.csv").open(encoding="utf-8", newline="") as stream:
            labels = list(csv.DictReader(stream))
        self.assertEqual({r["sample_id"] for r in labels}, set(originals))
        self.assertTrue(all(not row["label_method"] for row in labels))

    def test_existing_directory_is_not_overwritten(self):
        self.output.mkdir()
        keep = self.output / "keep.txt"
        keep.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.build()
        self.assertEqual(keep.read_text(encoding="utf-8"), "keep")

    def test_changed_sample_record_is_rejected(self):
        self.samples["records"][0]["fold"] = "holdout" if self.samples["records"][0]["fold"] == "train" else "train"
        self.samples_path.write_text(json.dumps(self.samples), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_changed_original_corpus_is_rejected(self):
        path = Path(self.paths["corpus"]) / "SCC.parquet"
        with path.open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ValueError, "corpus differs"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_occurrence_bound_fails_without_dropping_records(self):
        with mock.patch.object(review_packet, "MAX_OCCURRENCES", 1):
            with self.assertRaisesRegex(ValueError, "no occurrences were silently dropped"):
                self.build()
        self.assertFalse(self.output.exists())

    def test_package_bound_fails_before_writing(self):
        with mock.patch.object(review_packet, "MAX_PACKAGE_BYTES", 1):
            with self.assertRaisesRegex(ValueError, "32 MiB"):
                self.build()
        self.assertFalse(self.output.exists())

    def test_context_keeps_whole_paragraph_and_marks_oversize_clips(self):
        text = "Introduction.\n\n[1] The court explains 😀 Alpha v Beta here.\n\n[2] The next paragraph."
        start = text.index("Alpha")
        result = review_packet.paragraph_context(text, start, start + 5, limit=100)
        self.assertIn("[1] The court", result["text"])
        self.assertFalse(result["paragraph_clipped"])
        long_text = "x" * 3000 + "Alpha" + "y" * 3000
        clipped = review_packet.paragraph_context(long_text, 3000, 3005)
        self.assertEqual(len(clipped["text"]), 2400)
        self.assertTrue(clipped["paragraph_clipped"])
        self.assertTrue(clipped["mention_fully_included"])


if __name__ == "__main__":
    unittest.main()
