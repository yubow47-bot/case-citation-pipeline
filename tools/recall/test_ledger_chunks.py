"""Offline chunking contracts using synthetic text and an isolated debt fixture."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("recall_ledger_builder", Path(__file__).with_name("build.py"))
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
sources = builder.sources


def marked(current, history):
    start, end, old_start, old_end = builder.LEDGER_MARKERS
    return "\n".join((start, current, end, old_start, history, old_end))


class LedgerChunkTests(unittest.TestCase):
    def test_current_and_history_are_one_logical_entry_with_current_first(self):
        current = "| 85 | IMPLEMENTED | Current repair and evidence | No open code task |"
        history = "| 85 | Historical date-shaped citation problem | Registered, unresolved |"
        chunks = list(builder.chunks_from_problem_text(marked(current, history)))
        self.assertEqual(len(chunks), 1)
        self.assertTrue(chunks[0]["locator"].endswith("#85"))
        self.assertLess(chunks[0]["text"].index(current), chunks[0]["text"].index(history))
        self.assertIn("HISTORICAL RECORD: earlier wording is not current status.", chunks[0]["text"])

    def test_marked_sections_ignore_other_tables_and_keep_unmatched_ids_explicit(self):
        text = "| 999 | Unrelated introductory table |\n" + marked(
            "| 2 | OPEN | Current-only entry | Investigate |", "| 1 | Old-only entry | Old handling |")
        chunks = list(builder.chunks_from_problem_text(text))
        self.assertEqual([c["locator"].split("#")[-1] for c in chunks], ["1", "2"])
        self.assertIn("No current index row recorded", chunks[0]["text"])
        self.assertIn("No historical row is recorded", chunks[1]["text"])

    def test_legacy_fallback_tolerates_missing_final_pipe_and_embedded_code_pipes(self):
        row = "| 85 | Legacy pattern `a|b` and missing trailing table pipe | Fixed later"
        chunks = list(builder.chunks_from_problem_text(row + "\n" + row))
        self.assertEqual(len(chunks), 1)
        self.assertTrue(chunks[0]["locator"].endswith("#85"))
        self.assertIn(row, chunks[0]["text"])
        self.assertIn("Legacy ledger format", chunks[0]["text"])

    def test_repeated_id_rows_preserve_both_records_without_duplicate_entry(self):
        rows = "| 1 | First old observation | Old handling |\n| 1 | Additional observation | Later handling |"
        records = list(builder.problem_records(rows))
        self.assertEqual(len(records), 1)
        self.assertEqual(len(records[0][1]["history"]), 2)
        self.assertEqual(len(list(builder.chunks_from_problem_text(rows))), 1)

    def test_incomplete_repeated_or_out_of_order_markers_fail_closed(self):
        text = marked("| 1 | OPEN | Current | Next |", "| 1 | Old | Old |")
        broken = (
            text.replace(builder.LEDGER_MARKERS[1], ""),
            text + "\n" + builder.LEDGER_MARKERS[0],
            text.replace(builder.LEDGER_MARKERS[0], "TEMP").replace(
                builder.LEDGER_MARKERS[1], builder.LEDGER_MARKERS[0]).replace(
                    "TEMP", builder.LEDGER_MARKERS[1]),
        )
        for item in broken:
            with self.subTest(item=item), self.assertRaises(ValueError):
                list(builder.chunks_from_problem_text(item))

    def assert_content_retained(self, original, chunks):
        # Every short content block must survive a cut, including the final tail.
        for offset in range(0, len(original), 24):
            block = original[offset:offset + 24]
            self.assertTrue(any(block in chunk["text"] for chunk in chunks), block)

    def test_every_long_history_piece_repeats_current_and_history_role_within_limit(self):
        current = "| 85 | IMPLEMENTED | Use the current repair | No open code task |"
        history = "| 85 | " + " ".join("old-evidence-%04d" % n for n in range(600)) + " | Short final tail |"
        chunks = list(builder.chunks_from_problem_text(marked(current, history)))
        self.assertGreater(len(chunks), 2)
        self.assertEqual(len({c["locator"] for c in chunks}), len(chunks))
        self.assertTrue(chunks[0]["locator"].endswith("#85"))
        for number, chunk in enumerate(chunks, 1):
            self.assertLessEqual(len(chunk["text"]), sources.MAX_CHARS)
            self.assertIn(current, chunk["text"])
            self.assertIn("Record section: HISTORICAL RECORD", chunk["text"])
            if number > 1:
                self.assertTrue(chunk["locator"].endswith("#85~%d" % number))
        self.assert_content_retained(history, chunks)

    def test_oversized_current_row_keeps_complete_detail_and_bounded_context(self):
        current = "| 1 | OPEN | " + " ".join("current-evidence-%04d" % n for n in range(180)) + " | Final close condition |"
        history = "| 1 | Old observation | Old disposition |"
        chunks = list(builder.chunks_from_problem_text(marked(current, history)))
        self.assertGreater(len(chunks), 2)
        self.assertEqual(len({c["locator"] for c in chunks}), len(chunks))
        for chunk in chunks:
            self.assertLessEqual(len(chunk["text"]), sources.MAX_CHARS)
            self.assertTrue(chunk["text"].startswith("Current index"))
            self.assertIn("HISTORICAL RECORD: earlier wording is not current status.", chunk["text"])
        self.assert_content_retained(current, chunks)
        self.assertIn(history, chunks[-1]["text"])


class DebtChunkTests(unittest.TestCase):
    def test_every_debt_piece_has_historical_notice_and_preserves_content(self):
        long_body = " ".join("debt-observation-%04d" % n for n in range(250))
        long_row = "| 1 | " + " ".join("old-row-%04d" % n for n in range(250)) + " | Old decision |"
        with tempfile.TemporaryDirectory(prefix="recall-ledger-fixture-", dir=ROOT/"implementation") as temp:
            fixture = Path(temp)/"DEBT_LEDGER.md"
            fixture.write_text("# Historical debt\n" + long_body + "\n" + long_row, encoding="utf-8")
            with patch.object(sources, "ROOT", temp):
                chunks = list(sources.chunk_debt())
        self.assertGreater(len(chunks), 3)
        for chunk in chunks:
            self.assertTrue(chunk["text"].startswith(sources.DEBT_HISTORY_NOTICE))
            self.assertLessEqual(len(chunk["text"]), sources.MAX_CHARS)
        for original in (long_body, long_row):
            for offset in range(0, len(original), 24):
                block = original[offset:offset + 24]
                self.assertTrue(any(block in chunk["text"] for chunk in chunks), block)


if __name__ == "__main__":
    unittest.main()
