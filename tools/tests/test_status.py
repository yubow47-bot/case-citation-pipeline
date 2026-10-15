"""Small offline status fixtures; no corpus/API or large temporary files."""
import contextlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import status as project_status
import storage


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "data" / "run_fixture"
        self.run.mkdir(parents=True)
        self.manifest = {"status": "complete", "input_identity_verified_unchanged": True,
                         "input_identity": {"fingerprint": "fixture-fingerprint", "files": {"corpus/SCC.parquet": "recorded-sha"}},
                         "params": {"courts": ["SCC"], "year_from": 2000, "limit_batches": 1,
                                    "batch_size": 5, "corpus_dir": str(self.root / "corpus")}}
        (self.run / "run_manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        self.db_path = self.root / "data" / "foundation" / "research.db"
        self.db_path.parent.mkdir()
        db = sqlite3.connect(self.db_path)
        db.executescript("""
        CREATE TABLE runs(run_id TEXT PRIMARY KEY,source_directory TEXT,input_fingerprint TEXT,manifest_json TEXT,imported_at TEXT,status TEXT);
        CREATE TABLE review_samples(sample_id TEXT PRIMARY KEY,run_id TEXT);
        CREATE TABLE review_labels(sample_id TEXT PRIMARY KEY,verdict TEXT,reviewer TEXT,evidence_locator TEXT);
        CREATE TABLE scores(run_id TEXT,scoring_version TEXT,status TEXT);
        """)
        db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?)", ("run_fixture", str(self.run), "fixture-fingerprint", json.dumps(self.manifest), "2026-10-14T00:00:00Z", "ready"))
        db.commit()
        db.close()

    def state_schema(self, states=None):
        db = sqlite3.connect(self.db_path)
        db.executescript("""
        CREATE TABLE run_components(run_id TEXT,component TEXT,generation INTEGER,status TEXT,source_fingerprint TEXT,details_json TEXT,updated_at TEXT);
        CREATE TABLE run_sources(run_id TEXT,logical_path TEXT,actual_path TEXT,sha256 TEXT,physical_sha256 TEXT,size_bytes INTEGER,compression TEXT);
        """)
        states = states if states is not None else {c: "ready" for c in project_status.REQUIRED_COMPONENTS}
        for name, state in states.items():
            db.execute("INSERT INTO run_components VALUES(?,?,?,?,?,?,?)", ("run_fixture", name, 3, state, "component-sha", json.dumps({"records": 5, "nested": {"large": "ignored"}}), "2026-10-14"))
        corpus = self.root / "corpus" / "SCC.parquet"
        corpus.parent.mkdir()
        corpus.write_bytes(b"tiny-not-a-real-parquet")
        db.execute("INSERT INTO run_sources VALUES(?,?,?,?,?,?,?)", ("run_fixture", "corpus/SCC.parquet", str(corpus), "recorded-logical-sha", "recorded-physical-sha", corpus.stat().st_size, "none"))
        db.commit()
        db.close()

    def pointer(self, **values):
        payload = {"run_id": "run_fixture", "db_path": "data/foundation/research.db",
                   "run_directory": "data/run_fixture", "input_fingerprint": "fixture-fingerprint", **values}
        (self.root / "data" / "active_run.json").write_text(json.dumps(payload), encoding="utf-8")

    def report(self, **kwargs):
        return project_status.status_report(self.root, **kwargs)

    def test_legacy_ready_is_not_current_keyword_or_vector_ready(self):
        report = self.report()
        run = report["database"]["runs"][0]
        self.assertEqual(run["db_run_status"], "ready")
        self.assertEqual(run["components"]["lifecycle"], "legacy_unverified")
        self.assertFalse(run["keyword_ready_verified_metadata"])
        self.assertFalse(run["components"]["vector_components_ready"])
        self.assertEqual(run["manual_calibration"]["status"], "unlabeled")
        self.assertTrue(run["partial_run"])
        self.assertEqual(run["courts"], ["SCC"])
        self.assertEqual(run["year_from"], 2000)

    def test_fresh_keyword_and_vector_states_are_independent(self):
        states = {c: "ready" for c in project_status.REQUIRED_COMPONENTS}
        states.update(vectors_cases="missing", vectors_methods="stale", vectors_edges="failed")
        self.state_schema(states)
        self.pointer()
        report = self.report()
        run = report["database"]["runs"][0]
        self.assertTrue(run["keyword_ready_verified_metadata"])
        self.assertFalse(run["components"]["vector_components_ready"])
        self.assertEqual(run["components"]["vectors_missing_or_stale"], list(project_status.VECTOR_COMPONENTS))
        self.assertEqual(report["database"]["selection"], "active_pointer")
        self.assertTrue(report["database"]["pointer_fingerprint_matches"])
        self.assertTrue(run["traceback_sources_available"])
        self.assertFalse(run["sources"]["records"][0]["recorded_hash_reverified"])
        self.assertTrue(run["sources"]["records"][0]["physical_size_matches_recorded"])
        self.assertEqual(run["components"]["records"][0]["generation"], 3)

    def test_incomplete_or_empty_generations_do_not_become_ready(self):
        self.state_schema({"import": "ready", "cases": "building", "acceptance": "stale"})
        run = self.report()["database"]["runs"][0]
        self.assertFalse(run["keyword_ready_verified_metadata"])
        components = {r["component"]: r for r in run["components"]["records"]}
        self.assertEqual(components["edges"]["status"], "missing")
        db = sqlite3.connect(self.db_path)
        db.execute("DELETE FROM run_components")
        db.commit()
        db.close()
        run = self.report()["database"]["runs"][0]
        self.assertEqual(run["components"]["lifecycle"], "schema_present_no_generations")
        self.assertTrue(all(c["status"] == "missing" for c in run["components"]["records"]))

    def test_pointer_mismatch_is_explicit_and_db_override_does_not_use_it(self):
        self.pointer(input_fingerprint="wrong")
        report = self.report()
        self.assertFalse(report["database"]["pointer_fingerprint_matches"])
        self.assertTrue(any("pointer does not agree" in x for x in report["warnings"]))
        report = self.report(db_path=self.db_path)
        self.assertEqual(report["database"]["selected_via"], "explicit_db")
        self.assertNotIn("pointer_fingerprint_matches", report["database"])

    def test_invalid_pointer_and_missing_db_are_reportable(self):
        (self.root / "data" / "active_run.json").write_text("{broken", encoding="utf-8")
        report = self.report()
        self.assertEqual(report["active_pointer"]["status"], "invalid")
        self.assertEqual(report["database"]["status"], "read")
        self.db_path.unlink()
        report = self.report()
        self.assertEqual(report["database"]["status"], "missing")
        self.assertTrue(report["local_runs"]["entries"])

    def test_pointer_type_errors_do_not_crash_or_select_an_unintended_db(self):
        self.pointer(db_path={"invalid": "path"})
        report = self.report()
        self.assertEqual(report["active_pointer"]["status"], "invalid")
        self.assertEqual(report["database"]["selected_via"], "default_foundation_db")

    def test_missing_traceback_and_local_manifest_scope_change_are_visible(self):
        self.state_schema()
        (self.root / "corpus" / "SCC.parquet").unlink()
        manifest = {**self.manifest, "params": {**self.manifest["params"], "courts": ["ONCA"]}}
        (self.run / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        report = self.report()
        run = report["database"]["runs"][0]
        self.assertTrue(run["keyword_ready_verified_metadata"])
        self.assertFalse(run["traceback_sources_available"])
        self.assertFalse(run["local_manifest_scope_matches"])
        self.assertTrue(any("local manifest" in x for x in report["warnings"]))

    def test_ready_state_without_a_generation_or_fingerprint_is_incomplete(self):
        self.state_schema()
        db = sqlite3.connect(self.db_path)
        db.execute("UPDATE run_components SET generation=0,source_fingerprint='' WHERE component='edges'")
        db.commit()
        db.close()
        run = self.report()["database"]["runs"][0]
        self.assertFalse(run["keyword_ready_verified_metadata"])
        self.assertIn("edges", run["components"]["components_with_incomplete_generation_metadata"])

    def test_no_large_hash_or_core_artifact_scan_by_default(self):
        self.state_schema()
        # Fake parquet is intentionally unreadable. Default status still succeeds.
        with mock.patch("check_run.check_run", side_effect=AssertionError("unexpected full artifact scan")):
            before = self.db_path.read_bytes()
            report = self.report()
            self.assertEqual(report["database"]["status"], "read")
            self.assertIsNone(report["core_run_check"])
            self.assertEqual(before, self.db_path.read_bytes())

    def test_reparse_alias_is_listed_but_not_followed_or_counted(self):
        alias = self.root / "data" / "run_external"
        alias.mkdir()
        (alias / "do_not_read.bin").write_bytes(b"x" * 1024)
        (alias / "run_manifest.json").write_text("{invalid external JSON", encoding="utf-8")
        old_storage_link = storage._link
        old_status_link = project_status._link
        def storage_link(path, st=None):
            return Path(path) == alias or old_storage_link(path, st)
        def status_link(path, st=None):
            return Path(path) == alias or old_status_link(path, st)
        external = self.root.parent / "outside_E_project"
        with mock.patch.object(storage, "_link", side_effect=storage_link), \
             mock.patch.object(project_status, "_link", side_effect=status_link), \
             mock.patch.object(project_status.os, "readlink", return_value=str(external)):
            report = self.report()
        entry = next(r for r in report["local_runs"]["entries"] if r["run_id"] == "run_external")
        self.assertEqual(entry["kind"], "alias_not_followed")
        self.assertTrue(entry["external_alias"])
        self.assertFalse(entry["counted_in_project_bytes"])
        self.assertEqual(entry["manifest_status"], "not_read")
        self.assertEqual(report["inventory"]["skipped_link_count"], 1)
        self.assertTrue(all("do_not_read.bin" not in r["path"] for r in report["inventory"]["largest_files"]))

    def test_budget_exceeded_and_low_reserve_are_attention_only(self):
        measured = storage.inventory(self.root)
        measured["total_bytes"] = 13 * storage.GiB
        usage = shutil_usage(20 * storage.GiB, 19 * storage.GiB, storage.GiB)
        with mock.patch.object(project_status, "inventory", return_value=measured), \
             mock.patch.object(project_status.shutil, "disk_usage", return_value=usage):
            report = self.report()
        self.assertFalse(report["storage_budget"]["within_budget"])
        self.assertFalse(report["storage_budget"]["free_reserve_satisfied"])
        self.assertFalse(report["storage_budget"]["new_large_artifacts_authorized_by_this_report"])
        self.assertEqual(report["status"], "attention")

    def test_manual_labels_and_scores_do_not_imply_current_accuracy(self):
        db = sqlite3.connect(self.db_path)
        db.execute("INSERT INTO review_samples VALUES('s1','run_fixture')")
        db.execute("INSERT INTO review_labels VALUES('s1','correct','','')")
        db.execute("INSERT INTO scores VALUES('run_fixture','old-experimental','experimental')")
        db.commit()
        db.close()
        run = self.report()["database"]["runs"][0]
        labels = run["manual_calibration"]
        self.assertEqual(labels["linked_label_records"], 1)
        self.assertEqual(labels["labels_missing_reviewer"], 1)
        self.assertEqual(labels["status"], "labels_present_not_independently_verified")
        self.assertEqual(labels["manual_accuracy"], "not_assessed_by_status_tool")
        self.assertEqual(run["stored_score_versions"][0]["status"], "experimental")

    def test_declared_quality_packets_are_bounded_metadata_only(self):
        packet = self.root / "labels.json"
        packet.write_text(json.dumps({"schema": "quality-labels-v1", "frame_id": "frame", "records": [{"label": "unreviewed"}]}), encoding="utf-8")
        self.pointer(quality={"labels": "labels.json"})
        report = self.report()
        summary = report["declared_manual_review"]["packets"][0]
        self.assertEqual(summary["records_count"], 1)
        self.assertEqual(summary["status"], "present_not_reassessed")
        self.assertEqual(report["declared_manual_review"]["manual_accuracy"], "not_assessed")

    def quality_package(self, name="primary", frame="frame"):
        folder = self.root / name
        folder.mkdir(exist_ok=True)
        samples = {"schema": "quality_sample_v1", "run_id": "run_fixture", "frame_id": frame,
                   "input_identity": {"input_fingerprint": "fixture-fingerprint"},
                   "frame_N": 1, "sample_n": 1, "records": [{"source": "original evidence is not reassessed"}]}
        labels = {"schema": "quality_labels_v1", "run_id": "run_fixture", "frame_id": frame,
                  "samples_hash": project_status.metadata_hash(samples), "records": []}
        labels["content_hash"] = project_status.metadata_hash(labels)
        evaluation = {"schema": "quality_evaluation_v1", "run_id": "run_fixture", "frame_id": frame,
                      "samples_hash": project_status.metadata_hash(samples), "labels_hash": labels["content_hash"],
                      "labelled_n": 0, "population_calibration_status": "not_calibrated"}
        result = {}
        for kind, payload in (("samples", samples), ("labels", labels), ("evaluation", evaluation)):
            path = folder / (kind + ".json")
            path.write_text(json.dumps(payload), encoding="utf-8")
            result[kind] = str(path.relative_to(self.root))
        return result

    def test_independent_review_frames_are_bound_but_not_combined(self):
        primary = self.quality_package()
        supplement = self.quality_package("fr", "fr-frame")
        self.pointer(quality={**primary, "supplements": [{"id": "selected_french_v1", **supplement}]})
        quality = self.report()["declared_manual_review"]
        self.assertEqual(quality["binding_status"], "matches_declared_metadata")
        self.assertEqual(quality["supplements"][0]["binding_status"], "matches_declared_metadata")
        self.assertEqual(quality["status"], "declared_packets")
        self.assertFalse(quality["frames_combined"])
        self.assertEqual(quality["manual_accuracy"], "not_assessed")
        self.assertEqual(quality["packets"][2]["declared_population_calibration_status"], "not_calibrated")

    def test_declared_model_review_provenance_does_not_change_database_manual_counts(self):
        primary = self.quality_package()
        label_path = self.root / primary["labels"]
        labels = json.loads(label_path.read_text(encoding="utf-8"))
        labels.update(label_method="model", labelled_records=1,
                      label_counts_by_method={"manual": 0, "model": 1},
                      records=[{"sample_id": "fixture-model-assessment", "label_method": "model"}])
        labels["content_hash"] = project_status.metadata_hash({k: v for k, v in labels.items() if k != "content_hash"})
        label_path.write_text(json.dumps(labels), encoding="utf-8")
        evaluation_path = self.root / primary["evaluation"]
        evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
        evaluation.update(label_method="model", labelled_n=1, manual_reviewed_n=0, model_reviewed_n=1,
                          label_counts_by_method={"manual": 0, "model": 1}, labels_hash=labels["content_hash"])
        evaluation_path.write_text(json.dumps(evaluation), encoding="utf-8")
        self.pointer(quality=primary)
        report = self.report()
        quality = report["declared_manual_review"]
        self.assertEqual(quality["binding_status"], "matches_declared_metadata")
        label_summary = next(p for p in quality["packets"] if p["kind"] == "labels")
        self.assertEqual(label_summary["declared_label_method"], "model")
        self.assertEqual(label_summary["declared_label_counts_by_method"], {"manual": 0, "model": 1})
        evaluation_summary = next(p for p in quality["packets"] if p["kind"] == "evaluation")
        self.assertEqual(evaluation_summary["declared_manual_reviewed_n"], 0)
        self.assertEqual(evaluation_summary["declared_model_reviewed_n"], 1)
        self.assertEqual(report["database"]["runs"][0]["manual_calibration"]["linked_label_records"], 0)

    def test_stale_sample_or_labels_metadata_is_attention(self):
        primary = self.quality_package()
        self.pointer(quality=primary)
        packet = self.root / primary["samples"]
        samples = json.loads(packet.read_text(encoding="utf-8"))
        samples["records"].append({"source": "changed"})
        packet.write_text(json.dumps(samples), encoding="utf-8")
        report = self.report()
        checks = report["declared_manual_review"]["metadata_binding_checks"]
        self.assertFalse(checks["labels_bound_to_sample_content"])
        self.assertFalse(checks["evaluation_bound_to_sample_content"])
        self.assertEqual(report["status"], "attention")
        packet = self.root / primary["labels"]
        labels = json.loads(packet.read_text(encoding="utf-8"))
        labels["records"].append({"verdict": "correct"})
        packet.write_text(json.dumps(labels), encoding="utf-8")
        self.assertFalse(self.report()["declared_manual_review"]["metadata_binding_checks"]["labels_content_hash_matches"])

    def test_review_frame_run_and_input_mismatches_are_explicit(self):
        primary = self.quality_package()
        packet = self.root / primary["evaluation"]
        evaluation = json.loads(packet.read_text(encoding="utf-8"))
        evaluation.update(frame_id="other-frame", run_id="other-run")
        packet.write_text(json.dumps(evaluation), encoding="utf-8")
        self.pointer(quality=primary, input_fingerprint="other-fingerprint")
        checks = self.report()["declared_manual_review"]["metadata_binding_checks"]
        self.assertFalse(checks["same_nonempty_frame_id"])
        self.assertFalse(checks["run_matches_active_pointer"])
        self.assertFalse(checks["sample_input_matches_active_pointer"])

    def test_review_supplements_are_bounded_unique_and_protected_from_output(self):
        primary = self.quality_package()
        supplement = self.quality_package("fr", "fr-frame")
        self.pointer(quality={**primary, "supplements": [{"id": "fr", **supplement}]})
        report = self.report()
        with self.assertRaisesRegex(ValueError, "overwrite an input"):
            project_status.write_status(self.root / supplement["samples"], report)
        self.pointer(quality={**primary, "supplements": [{"id": "same", **primary}, {"id": "same", **supplement}]})
        issues = self.report()["declared_manual_review"]["issues"]
        self.assertTrue(any("Duplicate frame" in issue for issue in issues))
        self.assertTrue(any("unique nonempty id" in issue for issue in issues))
        self.pointer(quality={**primary, "supplements": [supplement] * 9})
        self.assertEqual(self.report()["declared_manual_review"]["supplements"], [])
        self.assertIn("at most eight", self.report()["declared_manual_review"]["issues"][0])

    def test_linked_review_parent_is_never_read(self):
        primary = self.quality_package()
        self.pointer(quality=primary)
        real_link = project_status._link
        with mock.patch.object(project_status, "_link", side_effect=lambda p: Path(p) == self.root / "primary" or real_link(p)):
            quality = project_status.declared_quality(self.root, project_status.active_pointer(self.root))
        self.assertTrue(all(packet["status"] == "unreadable" for packet in quality["packets"]))
        self.assertTrue(all("Refusing linked" in packet["error"] for packet in quality["packets"]))

    def test_supplement_parent_binding_rejects_a_changed_primary(self):
        primary = self.quality_package()
        supplement = self.quality_package("fr", "fr-frame")
        source = json.loads((self.root / primary["samples"]).read_text(encoding="utf-8"))
        packet = self.root / supplement["samples"]
        samples = json.loads(packet.read_text(encoding="utf-8"))
        samples.update(parent_frame_id="frame", parent_samples_hash=project_status.metadata_hash(source), supplement_id="fr")
        packet.write_text(json.dumps(samples), encoding="utf-8")
        # These changes intentionally leave stale labels; parent checks remain independent.
        self.pointer(quality={**primary, "supplements": [{"id": "fr", **supplement}]})
        checks = self.report()["declared_manual_review"]["supplements"][0]["metadata_binding_checks"]
        self.assertTrue(checks["parent_frame_matches_primary"])
        self.assertTrue(checks["parent_sample_content_matches_primary"])
        self.assertTrue(checks["supplement_id_matches_pointer"])
        source["records"].clear()
        (self.root / primary["samples"]).write_text(json.dumps(source), encoding="utf-8")
        checks = self.report()["declared_manual_review"]["supplements"][0]["metadata_binding_checks"]
        self.assertFalse(checks["parent_sample_content_matches_primary"])

    def test_language_scope_change_and_invalid_quality_are_attention(self):
        manifest = {**self.manifest, "params": {**self.manifest["params"], "text_policy": "en_then_fr"}}
        (self.run / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        report = self.report()
        self.assertFalse(report["database"]["runs"][0]["local_manifest_scope_matches"])
        self.pointer(quality=["wrong-type"])
        self.assertEqual(self.report()["declared_manual_review"]["status"], "attention")

    def test_output_refuses_linked_parent(self):
        report = self.report()
        folder = self.root / "linked"
        folder.mkdir()
        real_link = project_status._link
        with mock.patch.object(project_status, "_link", side_effect=lambda p: Path(p) == folder or real_link(p)):
            with self.assertRaisesRegex(ValueError, "traverse links"):
                project_status.write_status(folder / "status.json", report)

    def test_verify_run_is_explicit_and_disallows_external_scope(self):
        with mock.patch("check_run.check_run", return_value={"status": "passed", "metrics": {"edges_total": 1}}) as checker:
            report = self.report(verify_run=self.run)
        checker.assert_called_once_with(self.run)
        self.assertEqual(report["core_run_check"]["status"], "passed")
        with self.assertRaisesRegex(ValueError, "inside the declared"):
            self.report(verify_run=self.root.parent)

    def test_output_is_small_fixed_and_protects_inputs(self):
        self.pointer()
        report = self.report()
        output = self.root / "status.json"
        project_status.write_status(output, report)
        self.assertLess(output.stat().st_size, project_status.MAX_JSON_BYTES)
        project_status.write_status(output, report)
        self.assertFalse(list(self.root.glob("status.json.*.tmp")))
        with self.assertRaisesRegex(ValueError, "overwrite an input"):
            project_status.write_status(self.root / "data" / "active_run.json", report)
        with self.assertRaisesRegex(ValueError, "outside source"):
            project_status.write_status(self.run / "run_manifest.json", report)

    def test_cli_summary_and_core_failure_exit(self):
        output = self.root / "status.json"
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            code = project_status.main(["--root", str(self.root), "--output", str(output)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stream.getvalue())["current_run_id"], "run_fixture")
        with mock.patch("check_run.check_run", return_value={"status": "failed"}), contextlib.redirect_stdout(io.StringIO()):
            code = project_status.main(["--root", str(self.root), "--verify-run", str(self.run)])
        self.assertEqual(code, 1)


    def test_language_scope_is_manifest_bound_with_legacy_english_default(self):
        legacy = project_status.run_summary('run_fixture', self.manifest, self.run, self.root)
        self.assertEqual(legacy['text_policy'], 'english_only')
        current = json.loads(json.dumps(self.manifest))
        current['params']['text_policy'] = 'en_then_fr'
        fallback = project_status.run_summary('run_fixture', current, self.run, self.root)
        self.assertEqual(fallback['text_policy'], 'en_then_fr')
        self.assertIn('One selected text', fallback['text_selection'])
        self.assertIn('metadata', fallback['processing_scope_note'])
        current['params']['text_policy'] = 'guess_language'
        with self.assertRaisesRegex(ValueError, 'Unknown corpus text_policy'):
            project_status.run_summary('run_fixture', current, self.run, self.root)


def shutil_usage(total, used, free):
    from collections import namedtuple
    return namedtuple("usage", "total used free")(total, used, free)


if __name__ == "__main__":
    unittest.main()
