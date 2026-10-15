"""Meaningful SQLite storage caps and stage-preflight regressions, in tiny fixtures."""
import contextlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import after_run
import common


class FoundationStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db_path = self.root / "data" / "fresh.db"
        self.root_patch = patch.object(common, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def test_default_small_project_database_is_not_blocked_and_records_cap(self):
        with common.storage_limits(min_free_bytes=0), common.capture_storage_reports() as reports:
            db = common.connect(self.db_path)
            with db:
                db.execute("CREATE TABLE values_table(value TEXT)")
                db.execute("INSERT INTO values_table VALUES('small fixture')")
            self.assertEqual(db.execute("SELECT value FROM values_table").fetchone()[0], "small fixture")
            self.assertEqual(db.execute("PRAGMA max_page_count").fetchone()[0], db.storage_report["max_page_count"])
            self.assertEqual(db.execute("PRAGMA temp_store").fetchone()[0], 2)
            self.assertEqual(db.storage_report["journal_mode"], "delete")
            self.assertTrue(db.storage_report["allowed"])
            self.assertEqual(len(reports), 1)
            db.close()

    def test_project_over_budget_is_blocked_before_db_creation(self):
        (self.root / "existing.bin").write_bytes(b"x" * 2000)
        with common.storage_limits(max_project_bytes=1000, min_free_bytes=0):
            with self.assertRaisesRegex(ValueError, "project peak exceeds"):
                common.connect(self.db_path)
        self.assertFalse(self.db_path.exists())

    def test_readonly_stays_available_when_budget_is_exhausted(self):
        with common.storage_limits(min_free_bytes=0):
            db = common.connect(self.db_path)
            db.execute("CREATE TABLE t(value TEXT)")
            db.execute("INSERT INTO t VALUES('retained')")
            db.commit()
            db.close()
        with common.storage_limits(max_project_bytes=1, min_free_bytes=0), \
             patch.object(common, "database_preflight", side_effect=AssertionError("Readonly must not preflight")):
            db = common.connect(self.db_path, readonly=True)
            self.assertEqual(db.execute("SELECT value FROM t").fetchone()[0], "retained")
            with self.assertRaises(sqlite3.OperationalError):
                db.execute("DELETE FROM t")
            db.close()

    def test_external_fixture_db_is_exempt_from_project_cap(self):
        other = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(other.cleanup)
        path = Path(other.name) / "fixture.db"
        with common.storage_limits(max_project_bytes=1, min_free_bytes=10**18), \
             patch.object(common, "database_preflight", side_effect=AssertionError("External fixture must not preflight")):
            db = common.connect(path)
            db.execute("CREATE TABLE t(value TEXT)")
            db.execute("INSERT INTO t VALUES('external')")
            db.commit()
            self.assertEqual(db.execute("SELECT value FROM t").fetchone()[0], "external")
            self.assertFalse(isinstance(db, common.GuardedConnection))
            db.close()

    def test_sqlite_cap_raises_clear_full_and_rolls_back_generation(self):
        with common.storage_limits(max_project_bytes=64 * 1024, min_free_bytes=0, journal_margin_bytes=4096):
            db = common.connect(self.db_path)
            db.execute("CREATE TABLE t(payload BLOB)")
            cap = db.storage_report
            with self.assertRaisesRegex(common.StorageCapacityError, "storage cap reached.*SQLITE_FULL") as caught:
                with db:
                    db.executemany("INSERT INTO t VALUES(?)", [(b"x" * 4096,) for _ in range(20)])
            self.assertEqual(caught.exception.sqlite_errorcode, sqlite3.SQLITE_FULL)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM t").fetchone()[0], 0)
            self.assertLessEqual(self.db_path.stat().st_size, cap["max_db_bytes"])
            projected = cap["project_bytes"] + cap["max_db_bytes"] - cap["current_db_bytes"] + cap["journal_reserve_bytes"]
            self.assertLessEqual(projected, cap["max_project_bytes"])
            db.close()

    def test_cursor_writes_cannot_bypass_cap_or_error_context(self):
        with common.storage_limits(max_project_bytes=64 * 1024, min_free_bytes=0, journal_margin_bytes=4096):
            db = common.connect(self.db_path)
            db.execute("CREATE TABLE t(payload BLOB)")
            cursor = db.cursor()
            with self.assertRaisesRegex(common.StorageCapacityError, "max_page_count"):
                with db:
                    cursor.executemany("INSERT INTO t VALUES(?)", [(b"x" * 8192,) for _ in range(10)])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM t").fetchone()[0], 0)
            db.close()

    def test_reopening_recalculates_capacity_after_other_project_growth(self):
        with common.storage_limits(max_project_bytes=512 * 1024, min_free_bytes=0, journal_margin_bytes=4096):
            db = common.connect(self.db_path)
            first = db.storage_report["max_page_count"]
            db.execute("CREATE TABLE t(value INTEGER)")
            db.close()
            (self.root / "other_output.bin").write_bytes(b"x" * (128 * 1024))
            db = common.connect(self.db_path)
            self.assertLess(db.storage_report["max_page_count"], first)
            db.close()

    def test_wal_requires_explicit_maintenance_but_readonly_remains_available(self):
        self.db_path.parent.mkdir()
        db = sqlite3.connect(self.db_path)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE t(value INTEGER)")
        db.commit()
        db.close()
        with common.storage_limits(min_free_bytes=0):
            with self.assertRaisesRegex(common.StorageCapacityError, "WAL mode"):
                common.connect(self.db_path)
            readonly = common.connect(self.db_path, readonly=True)
            self.assertEqual(readonly.execute("SELECT COUNT(*) FROM t").fetchone()[0], 0)
            readonly.close()

    def test_fresh_build_estimate_blocks_before_import_and_preserves_context(self):
        run = self.root / "run_fixture"
        run.mkdir()
        with patch.object(after_run.build, "build", side_effect=AssertionError("Import must not run")) as importer:
            with self.assertRaises(ValueError) as caught:
                after_run.run_all(run, self.db_path, max_project_bytes=1024 * 1024, min_free_bytes=0)
        importer.assert_not_called()
        self.assertFalse(self.db_path.exists())
        report = caught.exception.foundation_storage_report
        self.assertEqual(report["estimated_initial_peak_bytes"], 3 * 1024**3)
        self.assertEqual(report["failure_preflight"]["estimated_peak_bytes"], 3 * 1024**3)

    def test_scoped_policy_restores_after_explicit_override(self):
        original = dict(common.current_storage_policy())
        with common.storage_limits(max_project_bytes=123456, min_free_bytes=0):
            self.assertEqual(common.current_storage_policy()["max_project_bytes"], 123456)
        self.assertEqual(common.current_storage_policy(), original)

    def test_cli_invalid_peak_cannot_launch_pipeline_or_create_db(self):
        run = self.root / "run_fixture"
        with patch.object(after_run.subprocess, "run", side_effect=AssertionError("Pipeline must not run")) as pipeline, \
             contextlib.redirect_stderr(io.StringIO()) as stream:
            code = after_run.main(["--pipeline-out", str(run), "--db", str(self.db_path), "--estimated-peak-gb", "nan"])
        self.assertEqual(code, 1)
        pipeline.assert_not_called()
        self.assertEqual(json.loads(stream.getvalue())["status"], "failed")
        self.assertFalse(self.db_path.exists())


if __name__ == "__main__":
    unittest.main()
