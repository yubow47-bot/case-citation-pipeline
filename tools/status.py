"""Small read-only project/run/search status; no hashes or artifact scans by default."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile

try:
    from .storage import inventory, _link, DEFAULT_MAX_PROJECT_BYTES, DEFAULT_MIN_FREE_BYTES
except ImportError:
    from storage import inventory, _link, DEFAULT_MAX_PROJECT_BYTES, DEFAULT_MIN_FREE_BYTES

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from pipeline.corpus_fields import policy_from_manifest
MAX_JSON_BYTES = 2 * 1024 * 1024
REQUIRED_COMPONENTS = ("import", "relations", "cases", "edges", "methods", "acceptance")
VECTOR_COMPONENTS = ("vectors_cases", "vectors_methods", "vectors_edges")
MAX_RUNS = 100
MAX_REVIEW_SUPPLEMENTS = 8


def absolute(path, root):
    value = Path(path)
    return Path(os.path.abspath(value if value.is_absolute() else root / value))


def linked_path(path):
    # Check parents before descendants, and permit as-yet uncreated output paths.
    for part in reversed((Path(path), *Path(path).parents)):
        try:
            if _link(part):
                return True
        except FileNotFoundError:
            pass
    return False


def bounded_json(path):
    path = Path(path)
    if linked_path(path):
        raise ValueError("Refusing linked JSON metadata: " + str(path))
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("Metadata JSON exceeds the 2 MiB limit: " + str(path))
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Metadata must be a JSON object: " + str(path))
    return data


def path_state(path, root):
    path = absolute(path, root)
    result = {"path": str(path), "exists": path.exists(), "link_or_reparse": False,
              "outside_project_root": root not in path.parents and path != root}
    try:
        result["link_or_reparse"] = _link(path)
        if path.is_file():
            meta = path.stat()
            result["bytes"] = meta.st_size
            result["mtime_ns"] = meta.st_mtime_ns
    except FileNotFoundError:
        pass
    return result


def alias_state(path, root):
    result = {"run_id": path.name, "path": str(path), "kind": "alias_not_followed",
              "manifest_status": "not_read", "counted_in_project_bytes": False,
              "target": None, "external_alias": None}
    try:
        target = os.readlink(path)
        result["target"] = target
        # Windows readlink may return the extended-path prefix for junctions.
        plain = target[4:] if target.startswith("\\\\?\\") else target
        destination = absolute(plain, path.parent)
        result["external_alias"] = root != destination and root not in destination.parents
    except OSError as exc:
        result["target_read_error"] = str(exc)
    return result


def run_summary(run_id, manifest, directory, root):
    params = manifest.get("params", {})
    if not isinstance(params, dict):
        params = {}
    identity = manifest.get("input_identity", {})
    if not isinstance(identity, dict):
        identity = {}
    files = identity.get("files", {})
    if not isinstance(files, dict):
        files = {}
    courts = params.get("courts", [])
    return {"run_id": run_id, "source_directory": str(directory),
            "source_directory_state": path_state(directory, root),
            "manifest_status": manifest.get("status", "unknown"),
            "input_fingerprint": identity.get("fingerprint"),
            "input_identity_verified_unchanged": manifest.get("input_identity_verified_unchanged") is True,
            "courts": courts, "year_from": params.get("year_from"),
            "year_to": params.get("year_to"), "limit_batches": params.get("limit_batches"),
            "batch_size": params.get("batch_size"),
            "text_policy": policy_from_manifest(manifest),
            "text_selection": "English only" if policy_from_manifest(manifest) == 'english_only' else "Prefer nonempty English; otherwise French. One selected text per corpus row.",
            "partial_run": params.get("limit_batches") is not None or params.get("year_from") is not None or params.get("year_to") is not None,
            "corpus_directory": params.get("corpus_dir"),
            "corpus_input_paths_and_recorded_hashes": [{"logical_path": p, "sha256": sha}
                for p, sha in sorted(files.items()) if p.startswith("corpus/")],
            "output_seal_recorded": bool(manifest.get("output_identity")),
            "processing_scope_note": "Corpus rows describe the metadata universe, including rows with no selected text. They are not a processed nonempty-text denominator; language policy and date/batch limits constrain extraction."}


def list_local_runs(root):
    data = root / "data"
    result = {"directory": str(data), "entries": [], "truncated": False,
              "external_aliases_followed": False}
    if not data.exists():
        result["status"] = "missing"
        return result
    if _link(data):
        result["status"] = "data_directory_is_alias_not_followed"
        return result
    result["status"] = "listed"
    with os.scandir(data) as it:
        entries = sorted(it, key=lambda e: e.name)
    candidates = [e for e in entries if e.name.startswith("run_")]
    result["total_run_entries"] = len(candidates)
    for entry in candidates[:MAX_RUNS]:
        path = Path(entry.path)
        if _link(path):
            result["entries"].append(alias_state(path, root))
            continue
        if not entry.is_dir(follow_symlinks=False):
            continue
        row = {"run_id": path.name, "path": str(path), "kind": "local_run",
               "counted_in_project_bytes": True}
        try:
            manifest = bounded_json(path / "run_manifest.json")
            row.update(run_summary(path.name, manifest, path, root))
            # Small fixed sidecars only; do not open any CSV or scan corpus files.
            selected = path / "select_out" / "manifest.json"
            edges = path / "edges" / "manifest.json"
            for name, sidecar in (("selection", selected), ("edges", edges)):
                if sidecar.is_file() and not _link(sidecar):
                    value = bounded_json(sidecar)
                    row[name] = {"stats": value.get("stats"), "threshold_dd": value.get("threshold_dd")}
        except (OSError, ValueError) as exc:
            row["manifest_status"] = "unreadable_or_missing"
            row["error"] = str(exc)
        result["entries"].append(row)
    result["truncated"] = len(candidates) > MAX_RUNS
    return result


def active_pointer(root):
    path = root / "data" / "active_run.json"
    result = {"path": str(path), "status": "missing", "value": None}
    if not path.exists():
        return result
    try:
        if _link(root / "data"):
            raise ValueError("Active pointer is beneath a linked data directory")
        value = bounded_json(path)
        for name in ("run_id", "db", "db_path", "run_directory", "input_fingerprint"):
            if name in value and (not isinstance(value[name], str) or not value[name].strip()):
                raise ValueError("Active pointer field must be a nonempty string: " + name)
        if "db" in value and "db_path" in value and value["db"] != value["db_path"]:
            raise ValueError("Active pointer has conflicting db and db_path")
        result.update(status="read", value=value)
    except (OSError, ValueError) as exc:
        result.update(status="invalid", error=str(exc))
    return result


def label_status(db, tables, run_id):
    result = {"status": "not_recorded", "manual_accuracy": "not_assessed_by_status_tool",
              "warning": "Existing score weights or label counts do not prove current-run semantic accuracy."}
    if "review_samples" not in tables or "review_labels" not in tables:
        return result
    sample_columns = {r[1] for r in db.execute("PRAGMA table_info(review_samples)")}
    label_columns = {r[1] for r in db.execute("PRAGMA table_info(review_labels)")}
    if not {"sample_id", "run_id"} <= sample_columns or "sample_id" not in label_columns:
        result["status"] = "unknown_schema"
        return result
    samples = db.execute("SELECT COUNT(*) FROM review_samples WHERE run_id=?", (run_id,)).fetchone()[0]
    labels = db.execute("SELECT COUNT(*) FROM review_labels l JOIN review_samples s ON s.sample_id=l.sample_id WHERE s.run_id=?", (run_id,)).fetchone()[0]
    result.update(sample_records=samples, linked_label_records=labels,
                  status="unlabeled" if not labels else "labels_present_not_independently_verified")
    if "verdict" in label_columns:
        result["verdict_counts"] = {r[0]: r[1] for r in db.execute(
            "SELECT l.verdict,COUNT(*) FROM review_labels l JOIN review_samples s ON s.sample_id=l.sample_id WHERE s.run_id=? GROUP BY l.verdict", (run_id,))}
    for column, key in (("reviewer", "labels_missing_reviewer"), ("evidence_locator", "labels_missing_evidence_locator")):
        if column in label_columns:
            result[key] = db.execute(f"SELECT COUNT(*) FROM review_labels l JOIN review_samples s ON s.sample_id=l.sample_id WHERE s.run_id=? AND trim(l.{column})=''", (run_id,)).fetchone()[0]
    return result


def component_states(db, tables, run_id):
    records = {}
    if "run_components" in tables:
        for record in db.execute("SELECT * FROM run_components WHERE run_id=? ORDER BY component", (run_id,)):
            record = dict(record)
            details = record.pop("details_json", "{}")
            try:
                value = json.loads(details)
                # No huge generation payloads in a status report; preserve useful scalar receipt fields.
                record["details_summary"] = {k: v for k, v in value.items() if isinstance(v, (str, int, float, bool)) or v is None} if isinstance(value, dict) else {}
                record["details_summary"] = {k: (v[:2000] if isinstance(v, str) else v) for k, v in list(record["details_summary"].items())[:30]}
            except (ValueError, TypeError):
                record["details_parse_error"] = True
            records[record["component"]] = record
    lifecycle = "recorded" if records else "schema_present_no_generations" if "run_components" in tables else "legacy_unverified"
    all_names = sorted(set(REQUIRED_COMPONENTS + VECTOR_COMPONENTS) | set(records))
    rows = [records.get(name, {"component": name, "generation": None,
            "status": "legacy_unverified" if lifecycle == "legacy_unverified" else "missing",
            "source_fingerprint": None}) for name in all_names]
    state_map = {r["component"]: r["status"] for r in rows}
    complete = {r["component"]: bool(isinstance(r.get("generation"), int) and r["generation"] > 0 and r.get("source_fingerprint")) for r in rows}
    return {"lifecycle": lifecycle, "records": rows,
            "keyword_components_ready": lifecycle == "recorded" and all(state_map[c] == "ready" and complete[c] for c in REQUIRED_COMPONENTS),
            "vector_components_ready": lifecycle == "recorded" and all(state_map[c] == "ready" and complete[c] for c in VECTOR_COMPONENTS),
            "vectors_missing_or_stale": [c for c in VECTOR_COMPONENTS if state_map[c] != "ready" or not complete[c]],
            "components_with_incomplete_generation_metadata": [c for c in all_names if not complete[c]]}


def database_status(path, root, pointer_run_id=None, pointer_fingerprint=None):
    path = absolute(path, root)
    result = {"path": str(path), "exists": path.is_file(), "read_only": True,
              "content_hash_verified": False, "runs": [], "current_run_id": None}
    if not path.is_file():
        result["status"] = "missing"
        return result
    result["bytes"] = path.stat().st_size  # Reporting DB length does not add it to root inventory.
    result["outside_project_root"] = root not in path.parents
    try:
        db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA temp_store=MEMORY")
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("BEGIN")
        try:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "runs" not in tables:
                raise ValueError("Database has no runs table")
            total = db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            records = db.execute("SELECT * FROM runs ORDER BY run_id LIMIT ?", (MAX_RUNS,)).fetchall()
            result.update(status="read", total_runs=total, truncated=total > len(records))
            for row in records:
                row = dict(row)
                run_id = row["run_id"]
                try:
                    manifest = json.loads(row["manifest_json"])
                    if not isinstance(manifest, dict):
                        raise ValueError("Run manifest is not an object")
                    summary = run_summary(run_id, manifest, row["source_directory"], root)
                except (ValueError, TypeError, KeyError) as exc:
                    summary = {"run_id": run_id, "manifest_status": "invalid", "error": str(exc)}
                summary.update(db_run_status=row.get("status"), imported_at=row.get("imported_at"),
                               db_input_fingerprint=row.get("input_fingerprint"))
                summary["fingerprint_agrees_with_manifest"] = bool(summary.get("input_fingerprint") and summary.get("input_fingerprint") == row.get("input_fingerprint"))
                summary["components"] = component_states(db, tables, run_id)
                summary["keyword_ready_verified_metadata"] = bool(row.get("status") == "ready" and
                    summary["components"]["keyword_components_ready"] and summary["fingerprint_agrees_with_manifest"] and
                    summary.get("manifest_status") == "complete" and summary.get("input_identity_verified_unchanged"))
                if "run_sources" in tables:
                    columns = {r[1] for r in db.execute("PRAGMA table_info(run_sources)")}
                    if {"run_id", "logical_path", "actual_path", "sha256"} <= columns:
                        count = db.execute("SELECT COUNT(*) FROM run_sources WHERE run_id=?", (run_id,)).fetchone()[0]
                        sources = []
                        for r in db.execute("SELECT * FROM run_sources WHERE run_id=? ORDER BY logical_path LIMIT 200", (run_id,)):
                            source = dict(r)
                            source["path_state"] = path_state(source["actual_path"], root)
                            source["recorded_hash_reverified"] = False
                            source["physical_size_matches_recorded"] = (source["size_bytes"] == source["path_state"]["bytes"]
                                if "size_bytes" in source and "bytes" in source["path_state"] else None)
                            sources.append(source)
                        summary["sources"] = {"count": count, "records": sources, "truncated": count > len(sources)}
                        summary["traceback_sources_available"] = count > 0 and not count > len(sources) and all(s["path_state"]["exists"] for s in sources)
                    else:
                        summary["sources"] = {"status": "unknown_schema"}
                else:
                    summary["sources"] = {"status": "legacy_not_recorded"}
                summary["manual_calibration"] = label_status(db, tables, run_id)
                if "scores" in tables:
                    score_columns = {r[1] for r in db.execute("PRAGMA table_info(scores)")}
                    if {"run_id", "scoring_version", "status"} <= score_columns:
                        summary["stored_score_versions"] = [dict(r) for r in db.execute(
                            "SELECT scoring_version,status,COUNT(*) records FROM scores WHERE run_id=? GROUP BY 1,2 LIMIT 20", (run_id,))]
                result["runs"].append(summary)
            available = {r["run_id"]: r for r in result["runs"]}
            if pointer_run_id:
                result["selection"] = "active_pointer"
                result["current_run_id"] = pointer_run_id if pointer_run_id in available else None
                result["pointer_run_present"] = pointer_run_id in available
                if pointer_run_id in available and pointer_fingerprint:
                    result["pointer_fingerprint_matches"] = available[pointer_run_id].get("db_input_fingerprint") == pointer_fingerprint
            elif len(available) == 1:
                result.update(selection="only_imported_run", current_run_id=next(iter(available)))
            else:
                result["selection"] = "multiple_runs_no_active_selection"
        finally:
            db.close()
    except (OSError, ValueError, sqlite3.Error, KeyError) as exc:
        result.update(status="unreadable_or_incompatible", error=str(exc))
    return result


def metadata_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def review_package(root, declared, pointer_value, package_id):
    """Bind small packet metadata; never combine frames or re-evaluate labels."""
    summaries, documents, issues = [], {}, []
    for kind in ("samples", "labels", "evaluation"):
        relative = declared.get(kind) or declared.get(kind + "_packet")
        if not relative:
            continue
        if not isinstance(relative, str):
            summaries.append({"kind": kind, "status": "invalid_pointer", "error": "Review packet path must be a string"})
            issues.append(kind + " packet path is invalid")
            continue
        path = absolute(relative, root)
        summary = {"kind": kind, "path": str(path), "status": "missing"}
        if linked_path(path):
            summary.update(status="unreadable", error="Refusing linked JSON metadata: " + str(path))
        elif path.is_file():
            try:
                data = bounded_json(path)
                documents[kind] = data
                summary.update(status="present_not_reassessed", schema=data.get("schema") or data.get("schema_version"),
                               run_id=data.get("run_id"), frame_id=data.get("frame_id"), bytes=path.stat().st_size,
                               canonical_metadata_sha256=metadata_hash(data))
                for array in ("records", "labels"):
                    if isinstance(data.get(array), list):
                        summary[array + "_count"] = len(data[array])
                for field in ("status", "label_status", "labelled", "labeled", "reviewed_count",
                              "frame_N", "sample_n", "sampled_n", "labelled_n", "labelled_records",
                              "population_calibration_status", "population_inference_allowed"):
                    if isinstance(data.get(field), (str, int, bool)):
                        summary["declared_" + field] = data[field]
            except (OSError, ValueError) as exc:
                summary.update(status="unreadable", error=str(exc))
        if summary["status"] in ("missing", "unreadable"):
            issues.append(kind + " packet is " + summary["status"])
        summaries.append(summary)
    modern = {"samples": "quality_sample_v1", "labels": "quality_labels_v1",
              "evaluation": "quality_evaluation_v1"}
    checks = {}
    samples = documents.get("samples", {})
    if any(data.get("schema") in modern.values() for data in documents.values()):
        checks["complete_current_packet_set"] = all(documents.get(k, {}).get("schema") == v for k, v in modern.items())
        checks["same_nonempty_frame_id"] = bool(samples.get("frame_id")) and all(
            data.get("frame_id") == samples["frame_id"] for data in documents.values())
        expected_run = pointer_value.get("run_id")
        checks["run_matches_active_pointer"] = bool(expected_run) and all(
            data.get("run_id") == expected_run for data in documents.values())
        identity = samples.get("input_identity") or {}
        checks["sample_input_matches_active_pointer"] = bool(pointer_value.get("input_fingerprint")) and isinstance(identity, dict) and identity.get("input_fingerprint") == pointer_value["input_fingerprint"]
        sample_sha = metadata_hash(samples)
        for kind in ("labels", "evaluation"):
            checks[kind + "_bound_to_sample_content"] = documents.get(kind, {}).get("samples_hash") == sample_sha
        labels = documents.get("labels", {})
        labels_sha = labels.get("content_hash")
        checks["labels_content_hash_matches"] = bool(labels_sha) and labels_sha == metadata_hash({k: v for k, v in labels.items() if k != "content_hash"})
        checks["evaluation_bound_to_labels_content"] = bool(labels_sha) and documents.get("evaluation", {}).get("labels_hash") == labels_sha
        issues.extend("Metadata binding failed: " + key for key, matched in checks.items() if not matched)
    return {"id": package_id, "status": "attention" if issues else "declared_packets",
            "packets": summaries, "frame_id": samples.get("frame_id"),
            "parent_frame_id": samples.get("parent_frame_id"),
            "parent_samples_hash": samples.get("parent_samples_hash"),
            "supplement_id": samples.get("supplement_id"),
            "binding_status": "matches_declared_metadata" if checks and all(checks.values()) else "mismatch_or_incomplete" if checks else "legacy_or_unspecified_schema_not_bound",
            "metadata_binding_checks": checks, "issues": issues, "manual_accuracy": "not_assessed"}


def declared_quality(root, pointer):
    value = pointer.get("value") or {}
    declared = value.get("quality", {})
    if not isinstance(declared, dict):
        return {"status": "attention", "issues": ["quality must be an object"], "manual_accuracy": "not_assessed"}
    if not declared:
        return {"status": "no_external_review_packets_declared", "manual_accuracy": "not_assessed"}
    primary = review_package(root, declared, value, "primary")
    packages, issues = [], list(primary["issues"])
    supplements = declared.get("supplements", [])
    if not isinstance(supplements, list) or len(supplements) > MAX_REVIEW_SUPPLEMENTS:
        issues.append("quality.supplements must be a list of at most eight independent packages")
        supplements = []
    ids, frames = {"primary"}, {primary["frame_id"]} if primary["frame_id"] else set()
    for extra in supplements:
        if not isinstance(extra, dict) or not isinstance(extra.get("id"), str) or not extra["id"].strip() or extra["id"] in ids:
            issues.append("Supplement requires a unique nonempty id")
            continue
        ids.add(extra["id"])
        package = review_package(root, extra, value, extra["id"])
        if package["parent_frame_id"] is not None or package["parent_samples_hash"] is not None:
            primary_sample = next((p for p in primary["packets"] if p["kind"] == "samples"), {})
            bindings = package["metadata_binding_checks"]
            bindings["parent_frame_matches_primary"] = bool(primary["frame_id"]) and package["parent_frame_id"] == primary["frame_id"]
            bindings["parent_sample_content_matches_primary"] = bool(primary_sample.get("canonical_metadata_sha256")) and package["parent_samples_hash"] == primary_sample["canonical_metadata_sha256"]
            bindings["supplement_id_matches_pointer"] = package["supplement_id"] == extra["id"]
            for key in ("parent_frame_matches_primary", "parent_sample_content_matches_primary", "supplement_id_matches_pointer"):
                if not bindings[key]:
                    package["issues"].append("Metadata binding failed: " + key)
            if package["issues"]:
                package["status"] = "attention"
                package["binding_status"] = "mismatch_or_incomplete"
        frame = package["frame_id"]
        if frame and frame in frames:
            package["issues"].append("Duplicate frame across declared packages; samples must not be counted twice")
            package["status"] = "attention"
        if frame:
            frames.add(frame)
        issues.extend(extra["id"] + ": " + issue for issue in package["issues"])
        packages.append(package)
    return {**primary, "status": "attention" if issues else "declared_packets",
            "supplements": packages, "issues": issues,
            "frames_combined": False, "manual_accuracy": "not_assessed",
            "note": "Small packet metadata bindings are checked. Original evidence and labels are not reassessed; independent sampling frames and their weights are never combined."}


def status_report(root=ROOT, db_path=None, verify_run=None):
    root = Path(os.path.abspath(root))
    measured = inventory(root)
    free = shutil.disk_usage(root).free
    budget = {"max_project_bytes": DEFAULT_MAX_PROJECT_BYTES,
              "project_bytes": measured["total_bytes"], "within_budget": measured["total_bytes"] <= DEFAULT_MAX_PROJECT_BYTES,
              "headroom_bytes": DEFAULT_MAX_PROJECT_BYTES - measured["total_bytes"],
              "free_disk_bytes": free, "min_free_bytes": DEFAULT_MIN_FREE_BYTES,
              "free_reserve_satisfied": free >= DEFAULT_MIN_FREE_BYTES,
              "new_large_artifacts_authorized_by_this_report": False}
    pointer = active_pointer(root)
    value = pointer.get("value") or {}
    default_db = value.get("db_path") or value.get("db") or "data/foundation/research.db"
    selected = absolute(db_path or default_db, root)
    db = database_status(selected, root, value.get("run_id") if not db_path else None,
                         value.get("input_fingerprint") if not db_path else None)
    db["selected_via"] = "explicit_db" if db_path else "active_pointer" if value.get("db_path") or value.get("db") else "default_foundation_db"
    if not db_path and value.get("run_directory") and db.get("current_run_id"):
        current = next((r for r in db["runs"] if r["run_id"] == db["current_run_id"]), {})
        db["pointer_source_directory_matches"] = absolute(value["run_directory"], root) == absolute(current.get("source_directory") or ".", root)
    warnings = []
    if not budget["within_budget"]:
        warnings.append("Project exceeds the 12 GiB logical-file budget; no expansion is approved by this status report.")
    if not budget["free_reserve_satisfied"]:
        warnings.append("Disk free space is below the 2 GiB reserve.")
    if pointer["status"] == "invalid":
        warnings.append("Active run pointer is invalid; fallback database is reported without silently accepting the pointer.")
    if db.get("pointer_run_present") is False or db.get("pointer_fingerprint_matches") is False or db.get("pointer_source_directory_matches") is False:
        warnings.append("Active pointer does not agree with the selected database run identity.")
    if db["status"] != "read":
        warnings.append("Results database is missing/unreadable; pipeline runs and storage inventory remain inspectable.")
    for run in db["runs"]:
        if not run.get("keyword_ready_verified_metadata"):
            warnings.append("Run " + run["run_id"] + " has legacy/incomplete/inconsistent keyword readiness metadata.")
        if run.get("traceback_sources_available") is False:
            warnings.append("Run " + run["run_id"] + " has missing/unlisted traceback source paths; stored passages and original-source availability are separate.")
    local_runs = list_local_runs(root)
    local_directories = {str(absolute(r["path"], root)): r for r in local_runs["entries"] if r["kind"] == "local_run"}
    for run in db["runs"]:
        directory = absolute(run.get("source_directory") or ".", root)
        local = local_directories.get(str(directory))
        if local:
            same_identity = bool(local.get("input_fingerprint") and local.get("input_fingerprint") == run.get("db_input_fingerprint"))
            same_scope = all(local.get(key) == run.get(key) for key in ("courts", "year_from", "year_to", "limit_batches", "text_policy"))
            run["local_manifest_identity_matches"] = same_identity
            run["local_manifest_scope_matches"] = same_scope
            if not same_identity or not same_scope:
                warnings.append("Run " + run["run_id"] + " local manifest identity/scope differs from the database snapshot.")
    quality = declared_quality(root, pointer)
    if quality["status"] == "attention":
        warnings.append("Declared quality packets have missing, inconsistent or invalid metadata; inspect declared_manual_review.issues.")
    report = {"schema_version": "project-status-v1", "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "root": str(root), "status": "attention" if warnings else "reported",
              "inventory": measured, "storage_budget": budget,
              "active_pointer": pointer, "local_runs": local_runs, "database": db,
              "declared_manual_review": quality, "warnings": warnings,
              "verification_scope": "Default status reads directory/file metadata, small manifests, and DB lifecycle/label counts. No corpus, CSV, embedding cache or DB content hashes are scanned. Recorded ready metadata is not an independent semantic accuracy test.",
              "core_run_check": None}
    if verify_run:
        run = absolute(verify_run, root)
        ancestors = [run, *[p for p in run.parents if p != root and root in p.parents]]
        if any(_link(path) for path in ancestors):
            raise ValueError("--verify-run must name a plain local directory; external aliases are not followed")
        if root not in run.parents:
            raise ValueError("--verify-run must remain inside the declared project root")
        try:
            from .check_run import check_run
        except ImportError:
            from check_run import check_run
        report["core_run_check"] = check_run(run)
        report["verification_scope"] += " Explicit --verify-run additionally scans the named run artifacts and its output seal using check_run."
        if report["core_run_check"]["status"] != "passed":
            report["status"] = "attention"
    if len((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError("Status output exceeds 2 MiB; select a narrower project root/database")
    return report


def write_status(path, report):
    path = Path(os.path.abspath(path))
    root = Path(report["root"])
    if linked_path(path):
        raise ValueError("Status output must not traverse links or junctions")
    if path.suffix.lower() != ".json":
        raise ValueError("Status output must be a .json file")
    inputs = {Path(report["active_pointer"]["path"]), Path(report["database"]["path"])}
    inputs.update(Path(p["path"]) for p in report.get("declared_manual_review", {}).get("packets", []) if p.get("path"))
    for package in report.get("declared_manual_review", {}).get("supplements", []):
        inputs.update(Path(p["path"]) for p in package.get("packets", []) if p.get("path"))
    if path in inputs:
        raise ValueError("Status output would overwrite an input")
    protected = [root / "corpus"]
    for run in report["local_runs"]["entries"]:
        protected.append(Path(run["path"]))
    for run in report["database"]["runs"]:
        if run.get("source_directory"):
            protected.append(absolute(run["source_directory"], root))
        if run.get("corpus_directory"):
            protected.append(absolute(run["corpus_directory"], root))
    if any(path == directory or directory in path.parents for directory in protected):
        raise ValueError("Status output must be outside source run/corpus directories")
    payload = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(payload) > MAX_JSON_BYTES:
        raise ValueError("Status output exceeds 2 MiB")
    existing = path.parent
    while not existing.exists():
        existing = existing.parent
    if shutil.disk_usage(existing).free < len(payload) + 1024 * 1024:
        raise ValueError("Insufficient space for bounded status report")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--db")
    parser.add_argument("--output", help="Fixed JSON path, maximum 2 MiB, overwritten atomically")
    parser.add_argument("--verify-run", help="Explicitly scan/check one plain local run; optional expensive verification")
    args = parser.parse_args(argv)
    try:
        report = status_report(args.root, args.db, args.verify_run)
        if args.output:
            write_status(args.output, report)
            print(json.dumps({"status": report["status"], "output": str(Path(args.output).absolute()),
                              "project_bytes": report["inventory"]["total_bytes"],
                              "within_12gib_budget": report["storage_budget"]["within_budget"],
                              "current_run_id": report["database"]["current_run_id"]}, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if report["core_run_check"] and report["core_run_check"]["status"] != "passed" else 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
