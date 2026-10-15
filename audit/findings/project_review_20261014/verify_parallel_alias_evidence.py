"""Bounded independent evidence audit. No production changes or derived databases.

Run from the D project root:
  python audit/findings/project_review_20261014/verify_parallel_alias_evidence.py
Only the fixed small JSON receipt beside this script is overwritten.
"""
import collections
import csv
import gzip
import hashlib
import json
import pathlib
import re
import sys

import pyarrow.parquet as pq

ROOT = pathlib.Path(__file__).resolve().parents[3]
RUN = ROOT / "data/run_20261014_reliable_v2"
sys.path.insert(0, str(ROOT / "pipeline"))
import registry
import extract
import merge


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def rows(relative):
    path = RUN / relative
    if not path.exists():
        path = pathlib.Path(str(path) + ".gz")
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        for record, row in enumerate(csv.DictReader(handle), 1):
            yield record, row


def text_digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main():
    manifest = json.loads((RUN / "run_manifest.json").read_text(encoding="utf-8"))
    specs = [
        ("Housen", 2784, "2002||scc||33", "2002|2|scr||235", "SCC_2002scc33"),
        ("Bell ExpressVu", 2804, "2002||scc||42", "2002|2|scr||559", "SCC_2002scc42"),
        ("Biniaris", 6653, "2000||scc||15", "2000|1|scr||381", "SCC_2000scc15"),
    ]
    wanted = {key for _, _, neutral, report, _ in specs for key in (neutral, report)}
    classifier, _, _ = registry.build_classifier()
    found = collections.defaultdict(list)
    cache = {}
    corpus = []
    for court in ["SCC", "ONCA", "BCCA"]:
        path = ROOT / "corpus" / (court + ".parquet")
        expected = manifest["input_identity"]["files"]["corpus/" + court + ".parquet"]
        actual = digest(path)
        if actual != expected:
            raise RuntimeError("Corpus changed since V2: " + court)
        pf = pq.ParquetFile(path)
        columns = [c for c in ("citation_en", "citation2_en", "name_en", "document_date_en")
                   if c in pf.schema_arrow.names]
        offset = 0
        for batch in pf.iter_batches(batch_size=2000, columns=columns):
            data = batch.to_pydict()
            for index, primary in enumerate(data["citation_en"]):
                for field in ("citation_en", "citation2_en"):
                    value = data[field][index] if field in data else None
                    if not value:
                        continue
                    cache_key = (court, value)
                    if cache_key not in cache:
                        kept, _ = extract.process_text(
                            value, extract.source_decision_citation(court, value), "")
                        key = None
                        if len(kept) == 1:
                            classified = classifier.run_row(dict(kept[0]))
                            if not classified.get("rejected_reason"):
                                key = merge.build_merge_key_v2(classified)
                        cache[cache_key] = key
                    key = cache[cache_key]
                    if key in wanted:
                        found[key].append({
                            "court": court, "corpus_row": offset + index, "field": field,
                            "raw": value, "primary_citation": primary,
                            "source_id": extract.source_decision_citation(court, primary or ""),
                            "name": data.get("name_en", [""] * batch.num_rows)[index],
                            "date": str(data.get("document_date_en", [""] * batch.num_rows)[index]),
                        })
            offset += batch.num_rows
        corpus.append({"path": str(path), "logical_path": "corpus/" + court + ".parquet",
                       "sha256": actual, "matches_run_manifest": True, "rows": offset})

    selected = collections.defaultdict(list)
    for record, row in rows("select_out/selected.csv"):
        if row["merge_key"] in wanted:
            selected[row["merge_key"]].append({"record": record, **{
                key: row[key] for key in ("merge_key", "merged_group_id", "court",
                "self_citation_of", "distinct_decisions_count", "identity_basis", "split_reason")}})
    group_ids = {r["merged_group_id"] for item in selected.values() for r in item}
    source_sets = collections.defaultdict(set)
    for _, row in rows("edges/citation_edges.csv"):
        group = row.get("resolved_cited_case") or row.get("cited_group_id") or row.get("merged_group_id") or row.get("group_id")
        if group in group_ids:
            source = row.get("source_decision_citation") or row.get("source_decision") or row.get("source_id")
            if not source:
                raise RuntimeError("Unrecognized edge source schema")
            source_sets[group].add(source)
    key_source_sets = collections.defaultdict(set)
    for court in ("SCC", "ONCA", "BCCA"):
        for _, row in rows("merge_out/" + court + "/decision_ids.csv"):
            if row["merge_key"] in wanted | {"2002||scc||35"}:
                key_source_sets[row["merge_key"]].add(row["source_decision_citation"])

    own = collections.defaultdict(list)
    for record, row in rows("registry/decision_own_citations.csv"):
        if row["merge_key"] in wanted:
            own[row["merge_key"]].append({"record": record, **row})
    merged = collections.defaultdict(list)
    for record, row in rows("merge_out/SCC/merged.csv"):
        if row["merge_key"] in wanted:
            merged[row["merge_key"]].append({"record": record, **{k: row[k] for k in
                ("merge_key", "self_citation_of", "self_case_name", "distinct_decisions_count")}})

    pf = pq.ParquetFile(ROOT / "corpus/SCC.parquet")
    text_rows = {}
    target_rows = {r for _, r, _, _, _ in specs} | {2796, 6650}
    offset = 0
    for rg in range(pf.metadata.num_row_groups):
        size = pf.metadata.row_group(rg).num_rows
        targets = [r for r in target_rows if offset <= r < offset + size]
        if targets:
            table = pf.read_row_group(rg, columns=["citation_en", "citation2_en", "name_en",
                "document_date_en", "unofficial_text_en"])
            for row in targets:
                text_rows[row] = table.slice(row - offset, 1).to_pylist()[0]
        offset += size

    cases = []
    for name, row, neutral, report, source_id in specs:
        metadata = dict(text_rows[row])
        text = metadata.pop("unofficial_text_en")
        spans = []
        for field in ("citation_en", "citation2_en"):
            raw = metadata[field]
            position = text.index(raw)
            spans.append({"field": field, "start": position, "end": position + len(raw),
                          "raw": raw, "sha256": text_digest(raw)})
        markers = [{"start": m.start(), "end": m.end(), "line": m.group(0)} for m in
            re.finditer(r"(?im)^(?:Decision Content|Held\b[^\n]*|Cases Cited[^\n]*|"
                        r"Statutes and Regulations Cited[^\n]*|The judgment[^\n]*|"
                        r"The reasons[^\n]*|Judgment[^\n]*)$", text)]
        boundary = next(m for m in markers if m["line"] == "Decision Content")
        a = source_sets[selected[neutral][0]["merged_group_id"]]
        b = source_sets[selected[report][0]["merged_group_id"]]
        key_a, key_b = key_source_sets[neutral], key_source_sets[report]
        cases.append({
            "name": name, "corpus_row": row, "source_id": source_id,
            "neutral_key": neutral, "reporter_key": report, "metadata": metadata,
            "metadata_key_matches": {neutral: found[neutral], report: found[report]},
            "mapping_unique_across_all_three_court_metadata": all(
                len(found[k]) == 1 and found[k][0]["source_id"] == source_id
                for k in (neutral, report)),
            "header_first_1500": text[:1500], "header_sha256": text_digest(text[:1500]),
            "full_text_sha256": text_digest(text), "metadata_header_spans": spans,
            "metadata_header_boundary": boundary,
            "both_keys_before_explicit_metadata_boundary": all(s["end"] <= boundary["start"] for s in spans),
            "body_section_markers": markers[:12], "v2_own_citation_rows": dict(
                (k, own[k]) for k in (neutral, report)),
            "v2_scc_merged_rows": dict((k, merged[k]) for k in (neutral, report)),
            "v2_selected_members": dict((k, selected[k]) for k in (neutral, report)),
            "v2_source_set_diagnostics": {
                "neutral_group": len(a), "reporter_group": len(b),
                "intersection": len(a & b), "overlap_smaller": len(a & b) / min(len(a), len(b)),
                "union": len(a | b), "union_excluding_own_source": len((a | b) - {source_id}),
                "own_source_in_neutral_group": source_id in a,
                "own_source_in_reporter_group": source_id in b,
                "warning": "Group unions include other inferred aliases and are diagnostics, not ground truth.",
            },
            "v2_exact_key_source_sets": {
                "neutral_key": len(key_a), "reporter_key": len(key_b),
                "intersection": len(key_a & key_b), "union": len(key_a | key_b),
                "pair_union_excluding_own_source": len((key_a | key_b) - {source_id}),
                "own_source_in_neutral_key": source_id in key_a,
                "own_source_in_reporter_key": source_id in key_b,
                "neutral_group_extra_sources": sorted(a - key_a),
                "reporter_group_extra_sources": sorted(b - key_b),
                "basis": "Union of actual merge_out/<court>/decision_ids.csv(.gz) rows for these two exact keys, then exclude this verified source decision only. Not an inferred group total.",
            },
        })
    negative = dict(text_rows[2796])
    text = negative.pop("unofficial_text_en")
    negative.update({"corpus_row": 2796, "source_id": "SCC_2002scc35",
        "full_text_sha256": text_digest(text), "header_first_1500": text[:1500],
        "warning": "2002 SCC 35 R. v. Carlos is distinct from Housen 2002 SCC 33; V2 Housen's ONCA member still labels SCC35 anchor_variant_typo_number."})
    negative_key = "2002||scc||35"
    trace = {}
    for relative in ("classify_out/SCC/classified.csv", "merge_out/SCC/mentions_candidates.csv"):
        fields = ("candidate_id", "source_decision_citation", "raw_string", "self_citation",
                  "merge_key", "arbitration_status", "rejected_reason")
        trace[relative] = [{"record": number, **{k: item[k] for k in fields if k in item}}
            for number, item in rows(relative)
            if item.get("source_decision_citation") == "SCC_2002scc35"
            and item.get("raw_string") == "2002 SCC 35"
            and item.get("shape_name") == "shape_neutral_bare"]
    for relative in ("merge_out/SCC/merged.csv", "registry/decision_registry.csv",
                     "registry/decision_own_citations.csv"):
        trace[relative] = [{"record": number, **item} for number, item in rows(relative)
                           if item.get("merge_key") == negative_key]
    registry_manifest = json.loads((RUN / "registry/manifest.json").read_text(encoding="utf-8"))
    negative["registry_omission_trace"] = trace
    negative["registry_manifest_scope"] = {k: registry_manifest[k] for k in
        ("by_source", "anchor_courts", "extracted_courts", "corpus_stats")}
    negative["registry_omission_explanation"] = (
        "Actual V2 full build: the neutral appears as self_citation_row only, and SCC merged "
        "omits the key because merge._emit iterates per_key_counted. The registry takes its "
        "real neutral keys only from emitted merged self_citation_of rows; active corpus metadata "
        "is not unioned (no anchor_courts/corpus_stats). Thus the registered guard misses a real "
        "primary-metadata decision. The independent own metadata table contains it. "
        "A plain-only reader would separately fail a later replay after compaction, but did not "
        "cause this original omission because original registry ran before compaction."
    )
    reporter_negative = dict(text_rows[6650])
    text = reporter_negative.pop("unofficial_text_en")
    reporter_negative.update({"corpus_row": 6650, "source_id": "SCC_2000scc17",
        "full_text_sha256": text_digest(text), "header_first_1500": text[:1500],
        "warning": "2000 SCC 17 / [2000] 1 SCR 439 R. v. A.G. is distinct from Biniaris 2000 SCC 15 / [2000] 1 SCR 381. V2 reporter381 group incorrectly also contains a reporter439 member carrying the Biniaris modal name; aliases must split existing incompatible document claims, not merely reject future unions."})
    receipt = {
        "schema": "independent_parallel_alias_evidence_v1", "run_directory": str(RUN),
        "run_input_fingerprint": manifest["input_identity"]["fingerprint"],
        "run_manifest_sha256": digest(RUN / "run_manifest.json"),
        "scope": "All citation_en and citation2_en metadata in all SCC/ONCA/BCCA corpus rows; Unicode code point text offsets, end exclusive.",
        "unique_metadata_fields_parsed": len(cache), "corpus_sources": corpus, "cases": cases,
        "negative_registered_neutral_example": negative,
        "negative_distinct_reporter_document": reporter_negative,
        "review": [
            "Use explicit unique source-bound parallel alias evidence; preserve the neutral-only typo registry and BAR=0.8.",
            "Reject ambiguous key-to-source mappings and invalid source IDs; parse complete metadata fields.",
            "Before any union, enforce component-wide distinct real neutral IDs, same-system identifiers, and positive deciding-court conflicts, including heuristic typo routes.",
            "Already formed clusters with two verified distinct document claims must be separated before alias joining; new-union guards alone preserve an existing wrong reporter cluster.",
            "Require both legal keys in clearly labeled own metadata/header before an explicit section boundary. Unknown boundary does not establish document identity.",
            "Historical Housen 1534 and Biniaris 440 include additional unsupported or inferred variants; do not restore counts without evidence.",
        ],
        "reproduce": "python audit/findings/project_review_20261014/verify_parallel_alias_evidence.py",
        "reproduction_script_sha256": digest(pathlib.Path(__file__)),
    }
    target = pathlib.Path(__file__).with_name("parallel_alias_evidence_20261014.json")
    data = json.dumps(receipt, ensure_ascii=False, indent=2, default=str) + "\n"
    if len(data.encode("utf-8")) > 256 * 1024:
        raise RuntimeError("Unexpected evidence receipt size")
    target.write_text(data, encoding="utf-8")
    print(json.dumps({"receipt": str(target), "bytes": len(data.encode('utf-8')),
        "cases": [{"name": c["name"], "unique": c["mapping_unique_across_all_three_court_metadata"],
                   "before_boundary": c["both_keys_before_explicit_metadata_boundary"],
                   "spans": c["metadata_header_spans"]} for c in cases]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
