"""Run input fingerprints include every consumed corpus, including anchor-only input."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_all


class RunIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / "implementation")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "pipeline").mkdir()
        (self.root / "pipeline/a.py").write_text("x = 1\n")
        (self.root / "corpus").mkdir()
        (self.root / "corpus/TCC.parquet").write_bytes(b"target")
        (self.root / "corpus/SCC.parquet").write_bytes(b"anchor")

    def test_anchor_only_corpus_is_hashed(self):
        params = {"anchor_corpus": ["SCC"]}
        before = run_all.input_identity(self.root, ("TCC",), params)
        self.assertIn("corpus/SCC.parquet", before["files"])
        (self.root / "corpus/SCC.parquet").write_bytes(b"changed")
        self.assertFalse(run_all.verify_unchanged(before, self.root, ("TCC",), params)[0])

    def test_external_consumed_corpus_occupies_logical_corpus_key(self):
        external = self.root / "external"
        external.mkdir()
        (external / "TCC.parquet").write_bytes(b"actual-external")
        identity = run_all.input_identity(self.root, ("TCC",), {}, external)
        self.assertEqual(identity["files"]["corpus/TCC.parquet"], hashlib.sha256(b"actual-external").hexdigest())

    def test_snapshot_start_identity_not_mutated_by_verification(self):
        before = run_all.input_identity(self.root, ("TCC",), {})
        original = dict(before["files"])
        (self.root / "pipeline/a.py").write_text("x = 2\n")
        unchanged, now = run_all.verify_unchanged(before, self.root, ("TCC",), {})
        self.assertFalse(unchanged)
        self.assertEqual(before["files"], original)
        self.assertNotEqual(before["fingerprint"], now["fingerprint"])


if __name__ == "__main__":
    unittest.main()
