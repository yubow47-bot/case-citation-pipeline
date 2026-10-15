"""Read-only lexical inventory of potential short references in the active corpus.

This does NOT resolve references, count missed citations, or label treatment.
It writes a small audit JSON outside the sealed run; no API calls or DB writes.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.citation_context.data import policy_from_manifest, projection, select_record

PATTERNS = {
    "ibid": r"\bibid\.",
    "id": r"\bid\.",
    "supra": r"\bsupra\b",
    "precite": r"\bpr[eé]cit[eé](?:e)?s?\b",
}


def sha_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory():
    pointer_bytes = (ROOT / "data/active_run.json").read_bytes()
    pointer = json.loads(pointer_bytes)
    run_dir = ROOT / pointer["run_directory"]
    manifest_path = run_dir / "extract_out/manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    policy = policy_from_manifest(manifest)
    regexes = {key: re.compile(value, re.I) for key, value in PATTERNS.items()}
    result = {
        "schema": "shortform_lexical_inventory_v1",
        "run_id": pointer["run_id"],
        "input_fingerprint": pointer["input_fingerprint"],
        "text_policy": policy,
        "patterns": PATTERNS,
        "unit": "selected corpus rows; lexical occurrences, not verified citations",
        "limitations": [
            "Patterns may match books, statutes, quoted speech, or non-reference text.",
            "Does not establish antecedents, new edges, recall, or treatment.",
            "Examples are the first two hits per court/language/pattern, not a probability sample.",
            "Only the declared patterns are inventoried; other short forms remain unmeasured.",
        ],
        "corpus": {},
        "by_court": {},
        "examples": [],
    }
    for court in manifest["params"]["courts"]:
        path = ROOT / "corpus" / (court + ".parquet")
        before = path.stat()
        expected_sha = manifest["corpus"][court]["sha256"]
        actual_sha = sha_file(path)
        if actual_sha != expected_sha:
            raise ValueError("Corpus differs from active extraction: " + court)
        result["corpus"][court] = {"path": str(path), "sha256": actual_sha}
        counts, docs, language_docs, example_counts = Counter(), Counter(), Counter(), Counter()
        rows, available, any_docs = 0, 0, 0
        parquet = pq.ParquetFile(path)
        for batch in parquet.iter_batches(batch_size=8, columns=projection(parquet.schema.names)):
            for record in batch.to_pylist():
                row_index = rows
                rows += 1
                selected = select_record(record, policy)
                text = selected["text"]
                if not selected["citation"].strip() or not text.strip():
                    continue
                available += 1
                language_docs[selected["language"]] += 1
                found_any = False
                for kind, regex in regexes.items():
                    matched = False
                    for match in regex.finditer(text):
                        counts[kind] += 1
                        matched = found_any = True
                        example_key = (selected["language"], kind)
                        if example_counts[example_key] < 2:
                            start, end = match.span()
                            a, b = max(0, start - 250), min(len(text), end + 350)
                            context = text[a:b]
                            result["examples"].append({
                                "court": court, "corpus_row": row_index,
                                "citation": selected["citation"], "kind": kind,
                                "text_field": selected["text_field"],
                                "match_start": start, "match_end": end,
                                "raw": text[start:end], "window_start": a, "window_end": b,
                                "context": context,
                                "context_sha256": hashlib.sha256(context.encode("utf-8")).hexdigest(),
                            })
                            example_counts[example_key] += 1
                    if matched:
                        docs[kind] += 1
                any_docs += found_any
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Corpus changed during inventory: " + court)
        result["by_court"][court] = {
            "corpus_rows": rows, "text_available_rows": available,
            "selected_language_rows": dict(language_docs),
            "rows_with_any_pattern": any_docs,
            "lexical_occurrences": {key: counts[key] for key in PATTERNS},
            "rows_by_pattern": {key: docs[key] for key in PATTERNS},
        }
    if (ROOT / "data/active_run.json").read_bytes() != pointer_bytes or manifest_path.read_bytes() != manifest_bytes:
        raise ValueError("Active run changed during inventory")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    findings = (ROOT / "audit/findings").resolve()
    if findings not in output.parents:
        parser.error("Output must be a new file under audit/findings")
    if output.exists():
        parser.error("Refusing to replace an existing audit")
    result = inventory()
    payload = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
    if len(payload) > 512 * 1024:
        raise ValueError("Inventory exceeds 512 KiB output budget")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(payload)
    print(json.dumps({"output": str(output), "by_court": result["by_court"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
