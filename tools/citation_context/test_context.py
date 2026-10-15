"""Cross-layer identity and inspection contracts."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from tools.citation_context.context import inspect_package, remap_mention_ids


class ContextContracts(unittest.TestCase):
    def test_nested_evidence_ids_change_without_altering_raw_text(self):
        record = {"mention_id": "short-a", "raw": "short-a", "antecedent_mention_ids": ["full-a", "short-b"],
                  "quote_bridge": {"source_mention_id": "short-b", "evidence": [{"mention_ids": ["short-b"], "raw": "short-b"}]}}
        remap_mention_ids(record, {"short-a": "doc-a", "short-b": "doc-b"})
        self.assertEqual(record["mention_id"], "doc-a")
        self.assertEqual(record["antecedent_mention_ids"], ["full-a", "doc-b"])
        self.assertEqual(record["quote_bridge"]["source_mention_id"], "doc-b")
        self.assertEqual(record["quote_bridge"]["evidence"], [{"mention_ids": ["doc-b"], "raw": "short-b"}])
        self.assertEqual(record["raw"], "short-a")

    def test_inspect_source_owner_and_summary_are_not_limited_to_display_rows(self):
        records = [{"source_id": "SCC_test", "target_group_id": "beta", "context_owner_group_id": "alpha",
                    "candidate_target_ids": ["beta"], "status": "context_required", "speaker_attribution": "reported_case"} for _ in range(3)]
        raw = "".join(json.dumps(record) + "\n" for record in records).encode()
        manifest = {"schema": "citation-context-v3", "run_id": "test", "files": {"observations.jsonl": {"sha256": hashlib.sha256(raw).hexdigest()}}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (path / "observations.jsonl").write_bytes(raw)
            args = SimpleNamespace(package=directory, table="observations", source=None, group="alpha", unresolved=False,
                                   kind=None, status=["context_required"], basis=None, speaker="reported_case", quoted=False,
                                   summary_only=False, limit=1)
            result = inspect_package(args)
            self.assertEqual((result["matching_records"], result["shown"]), (3, 1))
            self.assertEqual(result["breakdown"]["speaker_attribution"], {"reported_case": 3})
            args.summary_only = True
            self.assertEqual(inspect_package(args)["records"], [])


if __name__ == "__main__":
    unittest.main()
