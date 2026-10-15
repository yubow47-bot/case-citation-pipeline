"""Reproducible exploration cohorts across courts, text fields and short forms."""
from __future__ import annotations

from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
import re
import sys

from tools.citation_context.data import ROOT, optional_arrow, policy_from_manifest, projection, select_record

MARKERS = re.compile(r"\b(?P<ibid>ibid\.)|\b(?P<id>id\.)|\b(?P<supra>supra)\b|\b(?P<precite>pr[eé]cit[eé](?:e)?s?)\b", re.I)


def sample_cohort(source, *, limit=120, seed="20261015", include=()):
    """Balance marker buckets for exploration, not precision/recall estimation."""
    if not 1 <= limit <= 200 or len(set(include)) > limit:
        raise ValueError("Cohort size must be 1–200 and fit every included source")
    policy = policy_from_manifest(source.manifest)
    buckets, available, coverage = defaultdict(list), {}, Counter()
    for court in source.manifest["params"]["courts"]:
        docs = {int(row["corpus_row"]): dict(row) for row in source.db.execute(
            "SELECT * FROM documents WHERE run_id=? AND court=? ORDER BY corpus_row", (source.run_id, court))}
        paths = {row["corpus_path"] for row in docs.values()}
        if len(paths) != 1:
            raise ValueError("Court has inconsistent or missing corpus path: " + court)
        path = Path(next(iter(paths)))
        before = path.stat()
        parquet = optional_arrow().ParquetFile(path)
        row_number = 0
        for batch in parquet.iter_batches(batch_size=16, columns=projection(parquet.schema_arrow.names)):
            for record in batch.to_pylist():
                doc = docs.get(row_number)
                row_number += 1
                if doc is None:
                    continue
                selected = select_record(record, policy)
                if not selected["text"].strip():
                    continue
                kinds = sorted({match.lastgroup for match in MARKERS.finditer(selected["text"])})
                item = {"source_id": doc["source_id"], "citation": doc["citation"], "court": court,
                        "corpus_row": row_number - 1, "text_field": selected["text_field"],
                        "marker_kinds": kinds, "text_characters": len(selected["text"])}
                available.setdefault(doc["source_id"], item)
                rank = hashlib.sha256((str(seed) + "\0" + doc["source_id"]).encode()).hexdigest()
                for kind in kinds or ["no_marker"]:
                    key = (court, selected["language"], kind)
                    buckets[key].append((rank, doc["source_id"]))
                    coverage["/".join(key)] += 1
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Corpus changed during cohort scan: " + court)
        print(f"Cohort scan {court}: {len(docs)} original document rows", file=sys.stderr, flush=True)
    selected_ids = list(dict.fromkeys(include))
    missing = set(selected_ids) - available.keys()
    if missing:
        raise ValueError("Included sources lack original text: " + ", ".join(sorted(missing)))
    selected_set = set(selected_ids)
    queues = {key: deque(source_id for _, source_id in sorted(values)) for key, values in sorted(buckets.items())}
    while len(selected_ids) < limit:
        changed = False
        for queue in queues.values():
            while queue and queue[0] in selected_set:
                queue.popleft()
            if queue and len(selected_ids) < limit:
                source_id = queue.popleft()
                selected_set.add(source_id)
                selected_ids.append(source_id)
                changed = True
        if not changed:
            break
    selected_rows = [available[source_id] for source_id in selected_ids]
    return {"schema": "citation_context_cohort_v1", "run_id": source.run_id,
            "input_fingerprint": source.manifest["input_identity"]["fingerprint"], "seed": str(seed),
            "method": "stable_hash_round_robin_court_text_language_marker", "probability_sample": False,
            "limitations": ["Purposeful exploration balances rare markers and French fallback fields; not a representative accuracy sample.",
                            "Markers can be non-case references; text field language does not establish actual prose language."],
            "included_sources": list(dict.fromkeys(include)), "source_ids": selected_ids,
            "scanned_buckets": dict(sorted(coverage.items())),
            "selection_counts": {"court": dict(Counter(row["court"] for row in selected_rows)),
                                 "text_field": dict(Counter(row["text_field"] for row in selected_rows)),
                                 "marker": dict(Counter(kind for row in selected_rows for kind in row["marker_kinds"]))},
            "documents": selected_rows}


def read_cohort(path, source):
    path = Path(path)
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Cohort file exceeds 2 MiB")
    raw = path.read_bytes()
    cohort = json.loads(raw)
    if cohort.get("schema") != "citation_context_cohort_v1":
        raise ValueError("Unsupported cohort schema")
    if (cohort.get("run_id") != source.run_id or
            cohort.get("input_fingerprint") != source.manifest["input_identity"]["fingerprint"]):
        raise ValueError("Cohort belongs to a different active run")
    ids = cohort.get("source_ids")
    if not isinstance(ids, list) or not 1 <= len(ids) <= 200 or any(not isinstance(value, str) for value in ids):
        raise ValueError("Cohort must contain 1–200 source IDs")
    return ids, {"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest(),
                 "method": cohort["method"], "seed": cohort.get("seed"), "selection_counts": cohort.get("selection_counts")}


def write_cohort(path, cohort):
    path = Path(path).resolve()
    if not any(root.resolve() in path.parents for root in (ROOT / "data/experiments", ROOT / "audit/findings")):
        raise ValueError("Cohort output must be a new file under data/experiments or audit/findings")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(cohort, stream, ensure_ascii=False, indent=2)
    return {"output": str(path), "sources": len(cohort["source_ids"]), **cohort["selection_counts"]}
