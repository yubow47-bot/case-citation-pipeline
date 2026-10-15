"""Boundary checks for the standalone reader and replayable cohorts."""
import gzip
from contextlib import closing
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from tools.citation_context.cohort import read_cohort
from tools.citation_context.data import policy_from_manifest, rows, select_record


class ReaderBoundaries(unittest.TestCase):
    def test_historical_scope_does_not_silently_add_french(self):
        policy = policy_from_manifest({})
        selected = select_record({"citation_fr": "1999 CSC 1", "unofficial_text_fr": "texte"}, policy)
        self.assertEqual((selected["text"], selected["text_field"]), ("", "unofficial_text_en"))

    def test_fallback_is_per_field_with_original_text_unchanged(self):
        selected = select_record({"citation_en": "2002 SCC 33", "name_fr": "Nom",
                                  "unofficial_text_en": "  ", "unofficial_text_fr": "\nTexte é\n"}, "en_then_fr")
        self.assertEqual((selected["citation"], selected["name"], selected["text"]), ("2002 SCC 33", "Nom", "\nTexte é\n"))
        self.assertEqual((selected["language"], selected["text_field"]), ("fr", "unofficial_text_fr"))

    def test_csv_gzip_preserves_record_number_and_rejects_truncated_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mentions.csv"
            with gzip.open(str(path) + ".gz", "wt", encoding="utf-8", newline="") as stream:
                stream.write('name,start\n"Two\nlines",7\ntruncated\n')
            with closing(rows(path)) as records:
                self.assertEqual(next(records), (2, {"name": "Two\nlines", "start": "7"}))
                with self.assertRaisesRegex(ValueError, "Malformed ledger record 3"):
                    next(records)

    def test_cohort_cannot_cross_active_run_identity(self):
        source = SimpleNamespace(run_id="run_a", manifest={"input_identity": {"fingerprint": "fingerprint_a"}})
        cohort = {"schema": "citation_context_cohort_v1", "run_id": "run_a", "input_fingerprint": "fingerprint_b",
                  "source_ids": ["SCC_2002scc33"], "method": "exploration"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cohort.json"
            path.write_text(json.dumps(cohort), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "different active run"):
                read_cohort(path, source)
            cohort["input_fingerprint"] = "fingerprint_a"
            path.write_text(json.dumps(cohort), encoding="utf-8")
            self.assertEqual(read_cohort(path, source)[0], ["SCC_2002scc33"])


if __name__ == "__main__":
    unittest.main()
