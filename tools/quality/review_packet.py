"""Build bounded, offline evidence batches for an unchanged citation-quality sample."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import io
import json
from pathlib import Path
import re
import sqlite3
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.quality.common import (
    canonical_hash, open_source, frame_identity, verify_unchanged, protected_output,
    brief_edge,
)
from tools.quality.labels import _load_samples, _csv_identity, CSV_FIELDS, MANUAL_FIELDS
from tools.research.core import (
    rows, csv_path, file_hash, optional_arrow, verify_original_record, sha_text,
)
from tools.foundation.common import artifact_digest
from pipeline.corpus_fields import policy_from_manifest, projection, select_record

MAX_PACKAGE_BYTES = 32 * 1024 * 1024
MAX_CONTEXT_CHARS = 2400
MAX_OCCURRENCES = 12
BATCHES = 3
PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n|\n(?=[ \t]*(?:\[\d+[a-z]?\]|\d+[.)][ \t]))", re.I)
PROOF_TABLES = (
    "neutral_court_codes.csv", "court_designations.csv", "bilingual_neutral_codes.csv",
    "identity_court_scope.csv", "identity_court_facts.csv", "identity_separations.csv",
)


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _snapshot(path):
    info = Path(path).stat()
    return [info.st_size, info.st_mtime_ns]


def _new_output(path, source, samples_path):
    candidate = Path(path).absolute()
    for parent in (candidate, *candidate.parents):
        if parent.exists():
            info = parent.lstat()
            if parent.is_symlink() or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError("Output path contains a link or junction")
    target = protected_output(candidate, (samples_path,), source)
    if target.exists():
        raise ValueError("Output directory already exists; choose a new directory")
    return target


def paragraph_context(text, start, end, limit=MAX_CONTEXT_CHARS):
    """Retain whole paragraphs and neighbors when they fit; expose every clip."""
    if not 0 <= start < end <= len(text) or limit < 1:
        raise ValueError("Invalid original-text context coordinates or limit")
    breaks = list(PARAGRAPH_BREAK.finditer(text))
    before = [m for m in breaks if m.end() <= start]
    after = [m for m in breaks if m.start() >= end]
    para_start = before[-1].end() if before else 0
    para_end = after[0].start() if after else len(text)
    lo, hi = para_start, para_end
    if hi - lo > limit:
        lo = max(para_start, start - max(0, (limit - (end - start)) // 2))
        hi = min(para_end, lo + limit)
        lo = max(para_start, hi - limit)
    else:
        previous = before[-2].end() if len(before) > 1 else 0
        following = after[1].start() if len(after) > 1 else len(text)
        if hi - previous <= limit:
            lo = previous
        if following - lo <= limit:
            hi = following
    value = text[lo:hi]
    return {
        "start": lo, "end": hi, "text": value, "sha256": sha_text(value),
        "paragraph_start": para_start, "paragraph_end": para_end,
        "paragraph_clipped": lo > para_start or hi < para_end,
        "mention_fully_included": lo <= start and end <= hi,
        "includes_previous_paragraph": lo < para_start,
        "includes_next_paragraph": hi > para_end,
        "coordinate_system": "zero-based Unicode code points, half-open in the stated original text field",
    }


def _bound_artifact(source, relative, expected, snapshots):
    path = csv_path(source.run_dir / relative)
    before = _snapshot(path)
    actual = artifact_digest(path)
    if expected and actual != expected:
        raise ValueError("Artifact differs from its recorded snapshot: " + relative)
    imported = next((r for r in source.provenance.get("run_sources", []) if r["logical_path"] == relative), None)
    if imported and imported["sha256"] != actual:
        raise ValueError("Artifact differs from its imported snapshot: " + relative)
    if _snapshot(path) != before:
        raise ValueError("Artifact changed while hashing: " + relative)
    snapshots[str(path)] = before
    return path, actual


def _members(source, group_ids):
    result = {}
    for gid in sorted(group_ids):
        found = [dict(r) for r in source.db.execute(
            "SELECT * FROM members WHERE run_id=? AND merged_group_id=? ORDER BY row_number",
            (source.run_id, gid))]
        if not found:
            raise ValueError("Sample group has no members: " + gid)
        result[gid] = found
    return result


def _mentions(source, samples, members, snapshots):
    desired = {}
    key_groups = defaultdict(set)
    for gid, group_members in members.items():
        for member in group_members:
            key_groups[(member["court"], member["merge_key"])].add(gid)
    for record in samples["records"]:
        edge = record["edge"]
        key = (edge["source_decision"], edge["resolved_cited_case"])
        if key in desired:
            raise ValueError("Duplicate sampled edge")
        current = source.db.execute(
            "SELECT * FROM citation_edges WHERE run_id=? AND source_decision=? AND resolved_cited_case=?",
            (source.run_id, *key)).fetchone()
        if current is None or brief_edge(dict(current)) != edge:
            raise ValueError("Sample edge differs from the imported edge: " + record["sample_id"])
        if int(current["row_number"]) != record["source_locator"]["record"]:
            raise ValueError("Sample edge record locator differs from the imported edge")
        desired[key] = {"edge": dict(current), "occurrences": [], "documents": [
            dict(r) for r in source.db.execute(
                "SELECT * FROM documents WHERE run_id=? AND source_id=? ORDER BY court,corpus_row",
                (source.run_id, key[0]))]}
    ledger_hashes = {}
    for court in sorted({court for court, _ in key_groups}):
        relative = "merge_out/" + court + "/mentions_candidates.csv"
        path, digest = _bound_artifact(
            source, relative, samples.get("evidence_ledger_sha256", {}).get(relative), snapshots)
        ledger_hashes[relative] = digest
        for number, candidate in rows(path, (
            "source_decision_citation", "merge_key", "arbitration_status", "candidate_id",
            "corpus_row_index", "match_start_offset", "match_end_offset", "raw_string")):
            if candidate["arbitration_status"] != "counted":
                continue
            for gid in key_groups.get((court, candidate["merge_key"]), ()):
                key = (candidate["source_decision_citation"], gid)
                if key not in desired:
                    continue
                row, start, end = [int(candidate[k]) for k in (
                    "corpus_row_index", "match_start_offset", "match_end_offset")]
                if row < 0 or not 0 <= start < end:
                    raise ValueError("Invalid counted mention coordinates")
                if not any(d["court"] == court and int(d["corpus_row"]) == row for d in desired[key]["documents"]):
                    raise ValueError("Counted mention has no matching imported source document")
                occurrence = {
                    "source_decision": key[0], "cited_group_id": gid,
                    "candidate": {**candidate, "csv_record_number": number,
                        "row_sha256": canonical_hash(candidate), "ledger_logical_path": relative,
                        "ledger_logical_sha256": digest},
                    "span": {"court": court, "corpus_row": row, "start": start, "end": end},
                    "status": "original_text_not_read", "limitations": [],
                }
                desired[key]["occurrences"].append(occurrence)
                if len(desired[key]["occurrences"]) > MAX_OCCURRENCES:
                    raise ValueError("Sample edge exceeds the occurrence bound; no occurrences were silently dropped")
    for record in samples["records"]:
        key = (record["edge"]["source_decision"], record["edge"]["resolved_cited_case"])
        occurrences = desired[key]["occurrences"]
        if len(occurrences) != int(record["edge"]["mention_count"]):
            raise ValueError("Counted mention census differs from the sampled edge: " + record["sample_id"])
        original = record.get("evidence", {}).get("candidate")
        if original and not any(o["candidate"]["row_sha256"] == original["row_sha256"] for o in occurrences):
            raise ValueError("Original sampled evidence is not in the complete mention census")
    return desired, ledger_hashes


def _registry_proofs(source, members, snapshots):
    keys = {r["merge_key"] for group in members.values() for r in group}
    proof_by_key = defaultdict(list)
    relative = "registry/decision_own_citations.csv"
    try:
        csv_path(source.run_dir / relative)
    except ValueError:
        return proof_by_key, {"status": "not_available"}
    expected = next((r["sha256"] for r in source.provenance.get("run_sources", [])
                     if r["logical_path"] == relative), None)
    path, digest = _bound_artifact(source, relative, expected, snapshots)
    for number, row in rows(path, ("merge_key", "decision_id")):
        if row["merge_key"] not in keys:
            continue
        if row.get("evidence_id") and row["evidence_id"] != "own:" + canonical_hash(
                {k: str(v) for k, v in row.items() if k != "evidence_id"}):
            raise ValueError("Registry evidence ID is not bound to its record")
        proof = {
            "recorded_claim": row,
            "locator": {"logical_path": relative, "logical_sha256": digest,
                        "csv_record_number": number, "row_sha256": canonical_hash(row)},
            "native_documents": [dict(r) for r in source.db.execute(
                "SELECT * FROM documents WHERE run_id=? AND source_id=? ORDER BY court,corpus_row",
                (source.run_id, row["decision_id"]))],
            "verification": {"status": "original_corpus_not_read"},
        }
        proof_by_key[row["merge_key"]].append(proof)
    return proof_by_key, {"status": "recorded_registry_read", "logical_sha256": digest}


def _nk(value):
    return re.sub("[^a-z0-9]", "", str(value or "").lower())


def _court_proofs(source, members, snapshots):
    result = defaultdict(list)
    identities = {}
    for gid, group in members.items():
        identities[gid] = {
            "keys": {m["merge_key"] for m in group},
            "codes": {_nk(m["merge_key"].split("|")[2]) for m in group if len(m["merge_key"].split("|")) >= 3},
            "designations": {_nk(m.get("observed_deciding_court")) for m in group} - {""},
            "evidence_ids": {v for m in group for k, val in m.items() if "evidence_id" in k for v in str(val or "").split("|")} - {""},
        }
    for name in PROOF_TABLES:
        relative = "decisions/" + name
        expected = source.manifest["input_identity"].get("files", {}).get(relative)
        path = ROOT / relative
        if not expected or not path.is_file():
            continue
        before = _snapshot(path)
        if file_hash(path) != expected or _snapshot(path) != before:
            raise ValueError("Court proof table differs from the run input: " + relative)
        snapshots[str(path)] = before
        for number, row in rows(path):
            for gid, identity in identities.items():
                match = row.get("merge_key") in identity["keys"] or row.get("evidence_id") in identity["evidence_ids"]
                if name == "neutral_court_codes.csv":
                    match = _nk(row.get("court_code")) in identity["codes"]
                elif name == "court_designations.csv":
                    match = _nk(row.get("normalized_key")) in identity["designations"]
                elif name == "bilingual_neutral_codes.csv":
                    match = bool({_nk(row.get("code_en")), _nk(row.get("code_fr"))} & identity["codes"])
                elif name == "identity_court_scope.csv":
                    match = _nk(row.get("printed_key")) in identity["codes"]
                if match:
                    result[gid].append({
                        "recorded_claim": row,
                        "locator": {"logical_path": relative, "sha256": expected,
                                    "csv_record_number": number, "row_sha256": canonical_hash(row)},
                        "verification": {"status": "run_bound_table_claim"},
                    })
    return result


def _native_proof(record, proof, court, policy):
    claim = proof["recorded_claim"]
    selected = select_record(record, policy)
    source_id = court + "_" + re.sub("[^A-Za-z0-9]", "", selected["citation"]).lower()
    text = record.get(claim.get("text_field")) or ""
    checks = {
        "source_id": source_id == claim.get("decision_id", claim.get("source_decision")),
        "text_sha256": sha_text(text) == claim.get("text_sha256"),
    }
    if "field" in claim:
        value = record.get(claim["field"]) or ""
        checks["field_sha256"] = sha_text(value) == claim.get("field_sha256")
        checks["source_citation_sha256"] = sha_text(selected["citation"]) == claim.get("source_citation_sha256")
        start, end = claim.get("header_start"), claim.get("header_match_end")
        expected_span = claim.get("header_raw_sha256")
        proof["metadata_field_value"] = value
    else:
        start, end = claim.get("span_start"), claim.get("span_end")
        expected_span = claim.get("span_sha256")
    start, end = (int(start), int(end)) if str(start).isdigit() and str(end).isdigit() else (None, None)
    if start is not None and 0 <= start < end <= len(text):
        original = text[start:end]
        hashed_span = re.sub(r"\s+", " ", original).strip() if "field" in claim else original
        checks["span_sha256"] = sha_text(hashed_span) == expected_span
        proof["original_context"] = paragraph_context(text, start, end)
        proof["original_context"].update(text_field=claim["text_field"], language=claim["text_field"].rsplit("_", 1)[-1])
    elif expected_span:
        checks["span_sha256"] = False
    proof["native_metadata"] = {
        k: str(selected[k] or "") for k in ("citation", "name", "date", "citation_field", "name_field", "date_field")
    }
    proof["verification"] = {
        "status": "original_fields_and_span_verified" if checks and all(checks.values()) and expected_span
                  else "original_metadata_checked_incomplete_or_mismatched_header",
        "checks": checks, "source_text_sha256": sha_text(text), "text_field": claim.get("text_field"),
        "identity_qualification": claim.get("identity_qualified", "not_a_registry_alias"),
        "note": "Rechecking original fields verifies this recorded proof's bytes, not the correctness of every group member.",
    }


def _verify_corpus(source, edges, registry_proofs, court_proofs, snapshots):
    tasks = defaultdict(lambda: defaultdict(list))
    for edge in edges.values():
        for item in edge["occurrences"]:
            tasks[item["span"]["court"]][item["span"]["corpus_row"]].append(("occurrence", item))
    for proofs in registry_proofs.values():
        for proof in proofs:
            claim = proof["recorded_claim"]
            if str(claim.get("corpus_row", "")).isdigit() and claim.get("text_field"):
                tasks[claim["source_court"]][int(claim["corpus_row"])].append(("native", proof))
    for proofs in court_proofs.values():
        for proof in proofs:
            claim = proof["recorded_claim"]
            if str(claim.get("corpus_row", "")).isdigit() and claim.get("text_field"):
                tasks[claim["source_court"]][int(claim["corpus_row"])].append(("native", proof))
    policy = policy_from_manifest(source.manifest)
    sources = {r["logical_path"]: r for r in source.provenance.get("run_sources", [])}
    verified_files = {}
    for court, pending in sorted(tasks.items()):
        logical = "corpus/" + court + ".parquet"
        path = Path(sources.get(logical, {}).get("actual_path") or
                    Path(source.manifest["params"].get("corpus_dir") or ROOT / "corpus") / (court + ".parquet"))
        expected = source.manifest["input_identity"].get("files", {}).get(logical)
        before = _snapshot(path)
        actual = file_hash(path)
        if not expected or actual != expected or _snapshot(path) != before:
            raise ValueError("Original corpus differs from its run input: " + logical)
        snapshots[str(path)] = before
        verified_files[logical] = {"path": str(path.resolve()), "sha256": actual, "matches_run": True}
        pf = optional_arrow().ParquetFile(path)
        columns = list(dict.fromkeys(projection(pf.schema_arrow.names, include_text=True) +
                       [name for name in ("citation2_en", "citation2_fr") if name in pf.schema_arrow.names]))
        global_start = 0
        requested_rows = len(pending)
        for group in range(pf.metadata.num_row_groups):
            count = pf.metadata.row_group(group).num_rows
            needed = {row - global_start: values for row, values in pending.items()
                      if global_start <= row < global_start + count}
            if needed:
                local_start = 0
                for batch in pf.iter_batches(batch_size=8, row_groups=[group], columns=columns):
                    for local, record in enumerate(batch.to_pylist(), local_start):
                        for kind, item in needed.pop(local, []):
                            if kind == "occurrence":
                                verify_original_record(source, item, court, record, policy)
                                if item["status"] == "original_text_verified":
                                    text = select_record(record, policy)["text"]
                                    item["original_context"] = paragraph_context(text, item["span"]["start"], item["span"]["end"])
                                    item["original_context"].update(
                                        text_field=item["span"]["text_field"], language=item["span"]["language"])
                                item.pop("quote", None)
                                item.pop("quote_span", None)
                                item.pop("quote_sha256", None)
                            else:
                                claim = item["recorded_claim"]
                                if claim.get("corpus_sha256") and claim["corpus_sha256"] != actual:
                                    raise ValueError("Native proof corpus hash contradicts its run")
                                _native_proof(record, item, court, policy)
                            item["corpus_verification"] = verified_files[logical]
                    local_start += batch.num_rows
                    if not needed:
                        break
            global_start += count
        verify_unchanged({str(path): before})
        print(json.dumps({"corpus_verified": logical, "requested_rows": requested_rows}), file=sys.stderr)
    return verified_files


def build_packet(samples_path, db_path, output_dir):
    samples_path = Path(samples_path).resolve()
    samples_sha = file_hash(samples_path)
    samples, _ = _load_samples(samples_path)
    source = open_source(db=db_path, run_id=samples["run_id"])
    try:
        target = _new_output(output_dir, source, samples_path)
        frame_id, identity, snapshots = frame_identity(source)
        if frame_id != samples["frame_id"] or identity != samples["input_identity"]:
            raise ValueError("Sample design does not match the selected database/run")
        members = _members(source, {r["edge"]["resolved_cited_case"] for r in samples["records"]})
        edges, ledger_hashes = _mentions(source, samples, members, snapshots)
        registry, registry_status = _registry_proofs(source, members, snapshots)
        court = _court_proofs(source, members, snapshots)
        corpus = _verify_corpus(source, edges, registry, court, snapshots)
        lines = [[] for _ in range(BATCHES)]
        statuses, context_clips = Counter(), 0
        for index, rec in enumerate(samples["records"]):
            gid = rec["edge"]["resolved_cited_case"]
            edge = edges[(rec["edge"]["source_decision"], gid)]
            occurrences = edge["occurrences"]
            statuses.update(o["status"] for o in occurrences)
            context_clips += sum(o.get("original_context", {}).get("paragraph_clipped", False) for o in occurrences)
            group = dict(source.db.execute("SELECT * FROM case_groups WHERE run_id=? AND group_id=?",
                                           (source.run_id, gid)).fetchone())
            keys = {m["merge_key"] for m in members[gid]}
            packet = {
                "schema": "quality_review_evidence_record_v1", "sample_id": rec["sample_id"],
                "record_hash": rec["record_hash"], "sample": rec, "current_edge": edge["edge"],
                "group": group, "members": members[gid],
                "member_source_logical_sha256": identity["artifact_logical_sha256"]["select_out/selected.csv"],
                "source_documents": edge["documents"], "occurrences": occurrences,
                "occurrence_coverage": {"declared": int(rec["edge"]["mention_count"]),
                                        "retained": len(occurrences), "all_counted_occurrences_retained": True},
                "native_document_proofs": [p for key in sorted(keys) for p in registry.get(key, [])],
                "court_proofs": court.get(gid, []),
                "limitations": [
                    "Stored group membership, identity basis and court/origin values are machine claims to review.",
                    "A citing court or bare CanLII identifier does not by itself prove the cited judgment's country.",
                    "Read every occurrence, including quotation, party submissions and procedural history, before assigning treatment.",
                    "Clipped paragraphs require a larger original passage before making a conclusion that depends on omitted text.",
                    "The sampled edge has one inclusion weight regardless of its number of occurrences or members.",
                ],
            }
            packet["packet_record_sha256"] = canonical_hash(packet)
            lines[index % BATCHES].append(_json_bytes(packet))
        outputs = {f"batch_{index+1:02d}.jsonl": b"".join(batch) for index, batch in enumerate(lines)}
        csv_text = io.StringIO(newline="")
        writer = csv.DictWriter(csv_text, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for rec in samples["records"]:
            writer.writerow(dict(_csv_identity(rec), **{name: "" for name in MANUAL_FIELDS}))
        outputs["labels_template.csv"] = csv_text.getvalue().encode("utf-8")
        manifest = {
            "schema": "quality_review_evidence_manifest_v1", "status": "complete",
            "run_id": samples["run_id"], "frame_id": frame_id,
            "samples": {"path": str(samples_path), "file_sha256": samples_sha,
                        "canonical_sha256": canonical_hash(samples), "records": len(samples["records"])},
            "sample_metadata": {k: v for k, v in samples.items() if k != "records"},
            "input_identity": identity, "database": source.provenance,
            "ledger_logical_sha256": ledger_hashes, "corpus_verified": corpus,
            "registry": registry_status,
            "counts": {"samples": len(samples["records"]), "groups": len(members),
                       "distinct_group_members": sum(len(v) for v in members.values()),
                       "counted_occurrences": sum(len(v["occurrences"]) for v in edges.values()),
                       "occurrence_status": dict(statuses), "clipped_occurrence_paragraphs": context_clips},
            "limits": {"package_bytes": MAX_PACKAGE_BYTES, "context_characters": MAX_CONTEXT_CHARS,
                       "occurrences_per_edge": MAX_OCCURRENCES, "no_silent_occurrence_truncation": True},
            "files": {name: {"bytes": len(payload), "sha256": __import__("hashlib").sha256(payload).hexdigest(),
                             **({"records": len(lines[int(name[6:8])-1])} if name.endswith(".jsonl") else {})}
                      for name, payload in outputs.items()},
            "label_status": "No labels or model calls are produced by this evidence builder.",
        }
        outputs["manifest.json"] = _json_bytes(manifest)
        total = sum(len(v) for v in outputs.values())
        if total > MAX_PACKAGE_BYTES:
            raise ValueError(f"Evidence package exceeds its 32 MiB bound ({total} bytes); no package written")
        verify_unchanged(snapshots)
        if file_hash(samples_path) != samples_sha:
            raise ValueError("Original sample changed while building evidence")
        target.mkdir(parents=True, exist_ok=False)
        created = []
        try:
            for name, payload in outputs.items():
                with (target / name).open("xb") as stream:
                    stream.write(payload)
                created.append(target / name)
        except BaseException:
            for path in created:
                path.unlink()
            target.rmdir()
            raise
        return {"output_directory": str(target), "package_bytes": total, **manifest["counts"],
                "batches": [str(target / f"batch_{i+1:02d}.jsonl") for i in range(BATCHES)]}
    finally:
        source.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build_packet(args.samples, args.db, args.output_dir), ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
