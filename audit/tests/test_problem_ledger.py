"""Offline fixtures for the ledger's structural and non-destructive edit contract."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from audit import append_problems_entry as edit
from audit import check_problem_ledger as check


def ledger_text(current=None, history=None):
    current = current or ["| 1 | OPEN | Measured issue. | Recheck the source. |"]
    history = history or ["| 1 | Printed `court|merge_key` and escaped a\\|b. | Not fixed. |"]
    return "\r\n".join([
        "# Human ledger", "", "<!-- ledger-current:start -->",
        "| # | 状态 | 当前结论与证据 | 下一步 / 关闭条件 |", "|---|---|---|---|",
        *current, "<!-- ledger-current:end -->", "", "<!-- ledger-history:start -->",
        "| # | Problem | Current handling |", "|---|------|---------|",
        *history, "<!-- ledger-history:end -->", "", "Footer retained.", ""])


class LedgerFixtures(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ledger-test-", dir=check.ROOT / "implementation")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.ledger = self.root / "ledger.md"
        self.ledger.write_bytes(ledger_text().encode("utf-8"))
        self.history = self.root / "history.txt"
        self.current = self.root / "current.txt"
        self.history.write_text("| 2 | New issue. | Awaiting verification. |\n", encoding="utf-8")
        self.current.write_text("| 2 | IMPLEMENTED | Code landed. | Measure the full run. |\n", encoding="utf-8")

    def run_edit(self, **kwargs):
        with redirect_stdout(io.StringIO()):
            return edit.apply_change(self.ledger, self.history, self.current, root=self.root, **kwargs)

    def assert_edit_rejected(self, **kwargs):
        before = self.ledger.read_bytes()
        with self.assertRaises(check.LedgerError):
            self.run_edit(**kwargs)
        self.assertEqual(before, self.ledger.read_bytes())
        self.assertFalse(list(self.root.glob("ledger.md.*.tmp")))

    def test_append_preserves_old_bytes_and_inserts_inside_both_markers(self):
        old_history = ledger_text().split("\r\n")[11]
        result = self.run_edit()
        raw = self.ledger.read_bytes()
        self.assertEqual(result["counts"]["history"], 2)
        self.assertIn(old_history.encode("utf-8"), raw)
        self.assertIn(b"| 2 | New issue. | Awaiting verification. |\r\n<!-- ledger-history:end -->", raw)
        self.assertTrue(raw.endswith(b"Footer retained.\r\n"))
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))

    def test_dry_run_does_not_write(self):
        before = self.ledger.read_bytes()
        self.run_edit(dry_run=True)
        self.assertEqual(before, self.ledger.read_bytes())

    def test_duplicate_gap_and_non_table_fragments_leave_original_unchanged(self):
        for fragment in ("| 1 | Duplicate. | No. |", "| 3 | Gap. | No. |",
                         "| 2 | Valid. | No. |\nprose outside table",
                         "| 2 | Missing last delimiter | no tail",
                         "| 2 | One. | No. |\n| 2 | Duplicate. | No. |"):
            with self.subTest(fragment=fragment):
                self.history.write_text(fragment, encoding="utf-8")
                self.assert_edit_rejected()

    def test_missing_current_review_is_rejected(self):
        before = self.ledger.read_bytes()
        with self.assertRaises(check.LedgerError):
            edit.apply_change(self.ledger, self.history, None, root=self.root)
        self.assertEqual(before, self.ledger.read_bytes())

    def test_current_fragment_must_match_history_ids_status_and_required_fields(self):
        for fragment in ("| 3 | OPEN | Wrong ID. | Check. |",
                         "| 2 | FIXED | Unsupported state. | Check. |",
                         "| 2 | OPEN | Missing action. | |",
                         "| 2 | OPEN | [missing](docs/missing.md) | Check. |"):
            with self.subTest(fragment=fragment):
                self.current.write_text(fragment, encoding="utf-8")
                self.assert_edit_rejected()

    def test_replacement_cannot_change_id_or_accept_multiple_history_rows(self):
        self.current.write_text("| 1 | PARTIAL | Reviewed. | Rerun. |", encoding="utf-8")
        self.assert_edit_rejected(replace_row=1)
        self.history.write_text("| 1 | Changed. | No. |\n| 2 | Extra. | No. |", encoding="utf-8")
        self.assert_edit_rejected(replace_row=1)

    def test_replace_row_updates_both_tables_and_keeps_footer(self):
        self.current.write_text("| 1 | PARTIAL | Reviewed. | Rerun. |", encoding="utf-8")
        self.history.write_text("| 1 | Unicode 问题 and `x|y`. | Corrected. |", encoding="utf-8")
        self.run_edit(replace_row=1)
        self.assertIn("Unicode 问题 and `x|y`", self.ledger.read_text(encoding="utf-8"))
        self.assertEqual(check.check_ledger(self.ledger, self.root)["status"], "passed")

    def test_disposition_preserves_problem_cell_and_accepts_code_pipe(self):
        history = "| 1 |   Exact problem spacing `a|b`   | Previous disposition. |"
        self.ledger.write_bytes(ledger_text(history=[history]).encode("utf-8"))
        self.history.write_text("Changed `x|y` and a\\|b.", encoding="utf-8")
        self.current.write_text("| 1 | PARTIAL | Reviewed. | Rerun. |", encoding="utf-8")
        self.run_edit(set_disposition=1)
        self.assertIn("| 1 |   Exact problem spacing `a|b`   | Changed `x|y` and a\\|b. |",
                      self.ledger.read_text(encoding="utf-8"))

    def test_disposition_rejects_extra_cell_and_multiple_lines(self):
        self.current.write_text("| 1 | PARTIAL | Reviewed. | Rerun. |", encoding="utf-8")
        for value in ("one | two", "line one\nline two"):
            with self.subTest(value=value):
                self.history.write_text(value, encoding="utf-8")
                self.assert_edit_rejected(set_disposition=1)

    def test_malformed_existing_ledger_lf_missing_marker_gap_and_missing_tail_rejected(self):
        variants = [ledger_text().replace("\r\n", "\n"),
                    ledger_text().replace("<!-- ledger-history:end -->", ""),
                    ledger_text().replace("| 1 | Printed", "| 2 | Printed"),
                    ledger_text().replace("| Not fixed. |", "| Not fixed.")]
        for text in variants:
            with self.subTest(text=text[:60]):
                self.ledger.write_bytes(text.encode("utf-8"))
                self.assert_edit_rejected()

    def test_parser_ignores_code_pipe_escaped_pipe_and_long_code_delimiter(self):
        self.assertEqual(check.table_cells("| 1 | `a|b` and x\\|y | ``a`|b`` |"),
                         ["1", "`a|b` and x\\|y", "``a`|b``"])
        with self.assertRaises(check.LedgerError):
            check.table_cells("| 85 | missing last separator | disposition")

    def test_checker_rejects_duplicate_index_id_and_table_outside_markers(self):
        for text in (ledger_text(current=["| 1 | OPEN | One. | Check. |"] * 2),
                     ledger_text() + "| 2 | Outside table. | No. |\r\n"):
            with self.subTest(text=text[:60]):
                self.ledger.write_bytes(text.encode("utf-8"))
                self.assertEqual(check.check_ledger(self.ledger, self.root)["status"], "failed")

    def test_history_missing_path_is_warning_and_current_missing_evidence_is_error(self):
        self.ledger.write_bytes(ledger_text(history=["| 1 | `audit/missing.py` | Historical. |"]).encode("utf-8"))
        result = check.check_ledger(self.ledger, self.root)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(result["warnings"]), 1)
        self.ledger.write_bytes(ledger_text(current=["| 1 | OPEN | [evidence](audit/missing.py) | Check. |"]).encode("utf-8"))
        self.assertEqual(check.check_ledger(self.ledger, self.root)["status"], "failed")

    def test_existing_links_with_fragments_spaces_parentheses_and_external_urls(self):
        evidence = self.root / "proof (one).md"
        evidence.write_text("evidence", encoding="utf-8")
        current = "| 1 | IMPLEMENTED | [one](proof%20(one).md#anchor) [two](<proof (one).md>) [web](https://example.test/x) | Review. |"
        self.ledger.write_bytes(ledger_text(current=[current]).encode("utf-8"))
        self.assertEqual(check.check_ledger(self.ledger, self.root)["status"], "passed")
        self.assertEqual(check.local_link("../escape.md", self.ledger, self.root)[1],
                         "local evidence link escapes repository: ../escape.md")

    def test_mutually_exclusive_modes_reject_before_write(self):
        self.assert_edit_rejected(replace_row=1, set_disposition=1)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            edit.main(["--fragment", str(self.history), "--current-fragment", str(self.current),
                       "--replace-row", "1", "--set-disposition", "1"])
        self.assertEqual(error.exception.code, 2)

    def test_json_report_is_explicit_and_cannot_overwrite_ledger(self):
        report = self.root / "report.json"
        with redirect_stdout(io.StringIO()):
            code = check.main(["--ledger", str(self.ledger), "--json", str(report)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"], "passed")
        before = self.ledger.read_bytes()
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            check.main(["--ledger", str(self.ledger), "--json", str(self.ledger)])
        self.assertEqual(before, self.ledger.read_bytes())

    def test_concurrent_edit_is_not_overwritten(self):
        original_replace = edit.os.fsync

        def another_edit(fd):
            original_replace(fd)
            self.ledger.write_bytes(b"another human edit\r\n")

        with patch.object(edit.os, "fsync", side_effect=another_edit):
            with self.assertRaisesRegex(check.LedgerError, "changed during maintenance"):
                self.run_edit()
        self.assertEqual(self.ledger.read_bytes(), b"another human edit\r\n")
        self.assertFalse(list(self.root.glob("ledger.md.*.tmp")))


if __name__ == "__main__":
    unittest.main()
