"""Read the current research database and original texts without modifying either."""
from __future__ import annotations

from collections import defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

from pipeline.normalize import nk

ROOT = Path(__file__).resolve().parents[2]


def policy_from_manifest(manifest):
    """Mirror the recorded run's field policy, including historical English-only runs."""
    policy = manifest.get("params", {}).get("text_policy", "english_only")
    if policy not in ("english_only", "en_then_fr"):
        raise ValueError("Unknown corpus text_policy: " + str(policy))
    return policy


def projection(schema_names):
    return [base + "_" + language for base in ("citation", "name", "document_date", "unofficial_text")
            for language in ("en", "fr") if base + "_" + language in schema_names]


def select_record(record, policy):
    policy_from_manifest({"params": {"text_policy": policy}})
    def present(value):
        return bool(value.strip()) if isinstance(value, str) else value is not None
    result = {}
    for target, base in (("citation", "citation"), ("name", "name"), ("date", "document_date"), ("text", "unofficial_text")):
        field = base + "_en"
        if policy == "en_then_fr" and not present(record.get(field)) and present(record.get(base + "_fr")):
            field = base + "_fr"
        value = record.get(field)
        if target != "date":
            if value is not None and not isinstance(value, str):
                raise ValueError("Corpus " + field + " must be text or null")
            value = value or ""
        result[target], result[target + "_field"] = value, field
    result["language"] = result["text_field"].rsplit("_", 1)[1]
    return result


def optional_arrow():
    vendor = ROOT / "data/foundation_runtime"
    if vendor.is_dir() and str(vendor) not in sys.path:
        sys.path.append(str(vendor))
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ValueError("Original-text access requires installed/local pyarrow") from exc
    return pq


def rows(path):
    path = Path(path)
    if not path.is_file():
        path = Path(str(path) + ".gz")
    if not path.is_file():
        raise ValueError("Missing mention ledger: " + str(path))
    csv.field_size_limit(10**9)
    with (gzip.open if path.suffix == ".gz" else open)(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("Invalid ledger columns: " + str(path))
        for number, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Malformed ledger record {number}: {path}")
            yield number, row


class ContextSource:
    """Small read-only adapter; does not depend on optional research UI tooling."""

    @classmethod
    def sqlite(cls, path, run_id, run_dir):
        path, run_dir = Path(path).resolve(), Path(run_dir).resolve()
        if not path.is_file():
            raise ValueError("Research database does not exist: " + str(path))
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA query_only=ON")
            db.execute("PRAGMA temp_store=MEMORY")
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("BEGIN")
            record = db.execute("SELECT * FROM runs WHERE run_id=? AND status='ready'", (run_id,)).fetchone()
            if record is None:
                raise ValueError("Run is not ready in database: " + run_id)
            manifest = json.loads(record["manifest_json"])
            policy_from_manifest(manifest)
            if manifest.get("status") != "complete" or manifest.get("input_identity_verified_unchanged") is not True:
                raise ValueError("Active run must be complete with verified unchanged input identity")
            if not manifest.get("input_identity", {}).get("fingerprint") or manifest["input_identity"]["fingerprint"] != record["input_fingerprint"]:
                raise ValueError("Database run fingerprint differs from manifest")
            courts = manifest.get("params", {}).get("courts", [])
            if not courts or any(not re.fullmatch(r"[A-Z][A-Z0-9]*", court) for court in courts):
                raise ValueError("Run has no valid court scope")
            seal = manifest.get("output_identity")
            if seal and (not seal.get("files") or seal.get("fingerprint") != hashlib.sha256(json.dumps(seal["files"], sort_keys=True).encode()).hexdigest()):
                raise ValueError("Run output seal fingerprint is invalid")
            if json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8-sig")) != manifest:
                raise ValueError("Run directory manifest differs from database snapshot")
            source = cls()
            source.db, source.run_id, source.run_dir, source.manifest = db, run_id, run_dir, manifest
            source.provenance = {"db_path": str(path), "mode": "sqlite_readonly", "text_policy": policy_from_manifest(manifest)}
            db.create_function("research_casefold", 1, lambda value: str(value).casefold() if value is not None else None, deterministic=True)
            return source
        except Exception:
            db.close()
            raise

    def close(self):
        self.db.close()


def stable_id(prefix, *parts):
    value = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return prefix + hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def open_active():
    path = ROOT / "data/active_run.json"
    if path.stat().st_size > 65536:
        raise ValueError("Active pointer is too large")
    raw = path.read_bytes()
    pointer = json.loads(raw)
    for key in ("run_id", "db_path", "run_directory", "input_fingerprint"):
        if not isinstance(pointer.get(key), str) or not pointer[key]:
            raise ValueError("Missing active pointer field: " + key)
    source = ContextSource.sqlite(ROOT / pointer["db_path"], pointer["run_id"], ROOT / pointer["run_directory"])
    try:
        if source.manifest["input_identity"]["fingerprint"] != pointer["input_fingerprint"]:
            raise ValueError("Active pointer fingerprint differs from database")
        if path.read_bytes() != raw:
            raise ValueError("Active pointer changed during selection")
        return source, {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    except Exception:
        source.close()
        raise


def validate_pointer(snapshot):
    if hashlib.sha256(Path(snapshot["path"]).read_bytes()).hexdigest() != snapshot["sha256"]:
        raise ValueError("Active pointer changed during build; retry against the new run")


def select_documents(source, source_ids=(), group_id=None, courts=(), limit=24):
    if not 1 <= limit <= 200 or len(source_ids) > 200:
        raise ValueError("Experimental batches are limited to 1–200 source judgments")
    scope = source.manifest["params"]["courts"]
    if set(courts) - set(scope):
        raise ValueError("Requested court is outside the active run")
    courts = list(courts or scope)
    where, values = ["run_id=?", "court IN (" + ",".join("?" for _ in courts) + ")"], [source.run_id, *courts]
    if group_id:
        if not source.db.execute("SELECT 1 FROM case_groups WHERE run_id=? AND group_id=?", (source.run_id, group_id)).fetchone():
            raise ValueError("Group is not in the active run: " + group_id)
        where.append("source_id IN (SELECT source_decision FROM citation_edges WHERE run_id=? AND resolved_cited_case=?)")
        values.extend([source.run_id, group_id])
    if source_ids:
        placeholders = ",".join("?" for _ in source_ids)
        where.append(f"(source_id IN ({placeholders}) OR citation IN ({placeholders}))")
        values.extend([*source_ids, *source_ids])
    all_docs = [dict(row) for row in source.db.execute(
        "SELECT * FROM documents WHERE " + " AND ".join(where) + " ORDER BY court,corpus_row", values)]
    if source_ids:
        found = {value for row in all_docs for value in (row["source_id"], row["citation"])}
        missing = set(source_ids) - found
        if missing:
            raise ValueError("Source judgments not found in selected scope: " + ", ".join(sorted(missing)))
        selected_ids = {row["source_id"] for row in all_docs}
        method = "explicit_sources"
    else:
        by_court = {court: list(dict.fromkeys(row["source_id"] for row in all_docs if row["court"] == court)) for court in courts}
        ordered = []
        index = 0
        while len(ordered) < limit:
            next_ids = [by_court[court][index] for court in courts if len(by_court[court]) > index]
            if not next_ids:
                break
            ordered.extend(next_ids)
            index += 1
        selected_ids = set(ordered[:limit])
        method = "first_corpus_rows_round_robin_by_court"
    selected = [row for row in all_docs if row["source_id"] in selected_ids]
    if len(selected) > 400:
        raise ValueError("Too many duplicate corpus rows for a small experiment")
    if not selected:
        raise ValueError("No source judgments match the requested scope")
    return selected, {"method": method, "probability_sample": False, "source_ids": sorted(selected_ids),
                      "group_filter": group_id, "courts": courts, "document_rows": len(selected),
                      "scope_source_ids": len({row["source_id"] for row in all_docs})}


def read_anchors(source, documents):
    """Read every counted full-citation span in selected documents, including unlinked barriers."""
    source_ids = sorted({row["source_id"] for row in documents})
    slots = ",".join("?" for _ in source_ids)
    edge_map = {(row["source_decision"], row["resolved_cited_case"]): dict(row) for row in source.db.execute(
        f"SELECT * FROM citation_edges WHERE run_id=? AND source_decision IN ({slots})", [source.run_id, *source_ids])}
    members = {}
    for row in source.db.execute(
        f"SELECT court,merge_key,merged_group_id,case_name_modal,identity_basis FROM members WHERE run_id=? "
        f"AND merged_group_id IN (SELECT resolved_cited_case FROM citation_edges WHERE run_id=? AND source_decision IN ({slots}))",
        [source.run_id, source.run_id, *source_ids]):
        members[(row["court"], row["merge_key"])] = dict(row)
    wanted = {(row["court"], int(row["corpus_row"])): row["source_id"] for row in documents}
    anchors = defaultdict(list)
    for court in sorted({row["court"] for row in documents}):
        path = source.run_dir / "merge_out" / court / "mentions_candidates.csv"
        for record_number, row in rows(path):
            key = (court, int(row["corpus_row_index"]))
            if key not in wanted or row["arbitration_status"] != "counted":
                continue
            if row["source_decision_citation"] != wanted[key]:
                raise ValueError("Candidate source disagrees with document row")
            member = members.get((court, row["merge_key"]), {})
            group = member.get("merged_group_id")
            edge = edge_map.get((wanted[key], group))
            # Non-edge full references stay as barriers; self-excluded paths cannot become seeds.
            linked_group = group if edge else None
            local_name = row.get("candidate_case_name") or ""
            modal_name = member.get("case_name_modal") or ""
            anchors[key].append({
                "candidate_id": row["candidate_id"], "start": int(row["match_start_offset"]),
                "end": int(row["match_end_offset"]), "raw": row["raw_string"], "kind": "full",
                "target_group_id": linked_group, "resolution_status": "resolved" if edge else "blocked",
                "resolution_basis": "existing_counted_edge" if edge else "not_a_current_counted_edge",
                "candidate_target_ids": [], "antecedent_mention_ids": [],
                "case_name": local_name or modal_name, "aliases": list(dict.fromkeys(n for n in (local_name, modal_name) if n)),
                "identity_status": edge["identity_status"] if edge else None,
                "member_identity_basis": member.get("identity_basis"),
                "edge_support": edge["edge_support"] if edge else None, "counted_edge": bool(edge),
                "citation_kind": row["citation_kind"], "merge_key": row["merge_key"],
                "ledger_record": record_number, "ledger_path": str(path),
                "notes": [] if edge else ["Full reference retained as an antecedent barrier, not a counted case edge."],
                "detector": "production_ledger", "pinpoint": None,
            })
    return anchors, edge_map


def original_documents(source, documents):
    """Read only selected Parquet row groups; keep original text and original character offsets."""
    pq = optional_arrow()
    policy = policy_from_manifest(source.manifest)
    for court in sorted({row["court"] for row in documents}):
        wanted = {int(row["corpus_row"]): row for row in documents if row["court"] == court}
        paths = {str(Path(row["corpus_path"]).resolve()) for row in wanted.values()}
        if len(paths) != 1:
            raise ValueError("Selected court has inconsistent corpus paths")
        path = Path(next(iter(paths)))
        expected = source.manifest["input_identity"]["files"].get("corpus/" + court + ".parquet")
        if not expected:
            raise ValueError("Run has no corpus fingerprint: " + court)
        before = path.stat()
        parquet = pq.ParquetFile(path)
        columns = projection(parquet.schema_arrow.names)
        base = 0
        for group_index in range(parquet.num_row_groups):
            size = parquet.metadata.row_group(group_index).num_rows
            target_rows = {i for i in wanted if base <= i < base + size}
            if target_rows:
                offset = base
                for batch in parquet.iter_batches(batch_size=16, row_groups=[group_index], columns=columns):
                    for i, record in enumerate(batch.to_pylist(), offset):
                        if i not in target_rows:
                            continue
                        doc = dict(wanted[i])
                        selected = select_record(record, policy)
                        if court + "_" + nk(selected["citation"]) != doc["source_id"]:
                            raise ValueError("Original citation differs from selected document identity")
                        if not selected["text"].strip():
                            raise ValueError("Selected document has no available text: " + doc["source_id"])
                        text = selected["text"]
                        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
                        doc.update(text_field=selected["text_field"], language_field=selected["language"],
                                   text_sha256=sha, text_characters=len(text),
                                   document_id=stable_id("doc-", source.run_id, court, i, selected["text_field"], sha),
                                   corpus_sha256_recorded=expected,
                                   corpus_verification="recorded_run_fingerprint_and_live_span_checks; file_not_rehashed")
                        yield doc, text
                    offset += batch.num_rows
            base += size
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Corpus changed during reading: " + court)


def prepare_anchors(doc, text, anchors):
    result = []
    for anchor in anchors:
        anchor = dict(anchor)
        a, b = anchor["start"], anchor["end"]
        if not 0 <= a < b <= len(text) or re.sub(r"\s+", " ", text[a:b]).strip() != anchor["raw"]:
            raise ValueError("Full mention span differs from original text: " + anchor["candidate_id"])
        anchor["raw"] = text[a:b]
        anchor["mention_id"] = stable_id("m-", doc["document_id"], a, b, anchor["candidate_id"])
        result.append(anchor)
    return sorted(result, key=lambda row: (row["start"], row["end"], row["mention_id"]))
