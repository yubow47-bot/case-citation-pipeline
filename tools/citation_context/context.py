"""Build and inspect small experimental citation-context packages from the active run."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.citation_context import VERSION
from tools.citation_context.data import (open_active, original_documents, prepare_anchors,
                                         read_anchors, select_documents, stable_id, validate_pointer)
from tools.citation_context.shortforms import enrich_anchors, resolve_document, resolve_named_mentions
from tools.citation_context.scopes import quotation_scopes, quote_scope_at, quote_scope_evidence
from tools.citation_context.treatment import suggest_treatments, summarize_edges

MAX_PACKAGE_BYTES = 96 * 1024 * 1024
SHORT_KINDS = {"ibid", "id", "supra", "precite"}


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def remap_mention_ids(record, id_map):
    """Salt reference IDs inside nested evidence without changing original text."""
    for key, value in record.items():
        if isinstance(value, dict):
            remap_mention_ids(value, id_map)
        elif isinstance(value, list):
            if key == "mention_ids" or key.endswith("_mention_ids"):
                record[key] = [id_map.get(item, item) for item in value]
            else:
                for item in value:
                    if isinstance(item, dict):
                        remap_mention_ids(item, id_map)
        elif isinstance(value, str) and (key == "mention_id" or key.endswith("_mention_id")):
            record[key] = id_map.get(value, value)


def contextualize(doc, text, mentions, quote_scopes=None):
    """Attach display windows and explicit adjacent parallel-reference event IDs."""
    previous = None
    for mention in mentions:
        start, end = mention["start"], mention["end"]
        if not 0 <= start < end <= len(text) or text[start:end] != mention["raw"]:
            raise ValueError("Short-reference or full-reference span disagrees with original text")
        before, after = max(0, start - 220), min(len(text), end + 240)
        mention.update(document_id=doc["document_id"], source_id=doc["source_id"], run_id=doc["run_id"],
                       text_sha256=doc["text_sha256"], text_field=doc["text_field"],
                       context={"start": before, "end": after, "text": text[before:after]})
        position = mention.get("marker_start") if mention.get("marker_start") is not None else start
        mention.setdefault("quotation_scope", quote_scope_evidence(quote_scope_at(position, quote_scopes or [])))
        same_event = (previous and mention["kind"] == previous["kind"] == "full" and
                      mention.get("target_group_id") and mention.get("target_group_id") == previous.get("target_group_id") and
                      0 <= start - previous["end"] <= 60 and
                      re.fullmatch(r"[\s,;:()\[\].\-–]*", text[previous["end"]:start]))
        mention["event_id"] = previous["event_id"] if same_event else stable_id("event-", doc["document_id"], mention["mention_id"])
        previous = mention


def build_package(source, documents, selection, pointer):
    code_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob("*.py") if not p.name.startswith("test_")}
    anchors_by_doc, edges_by_key = read_anchors(source, documents)
    out_docs, out_mentions, out_observations, out_edges = [], [], [], []
    running_bytes = 0
    for doc, text in original_documents(source, documents):
        quote_scopes = quotation_scopes(text)
        doc["quotation_scopes"] = [quote_scope_evidence(scope) for scope in quote_scopes]
        anchors = prepare_anchors(doc, text, anchors_by_doc[(doc["court"], int(doc["corpus_row"]))])
        anchors = enrich_anchors(text, anchors, quote_scopes=quote_scopes)
        short = resolve_document(text, anchors, source_id=doc["source_id"], run_id=source.run_id, text_sha256=doc["text_sha256"], quote_scopes=quote_scopes)
        named = resolve_named_mentions(text, anchors, exclude_spans=[(m["start"], m["end"]) for m in anchors + short], quote_scopes=quote_scopes)
        additions = short + named
        id_map = {row["mention_id"]: stable_id("m-", doc["document_id"], row["mention_id"]) for row in additions}
        for row in additions:
            remap_mention_ids(row, id_map)
            edge = edges_by_key.get((doc["source_id"], row.get("target_group_id")))
            if row.get("target_group_id") and (row["resolution_status"] != "resolved" or not edge):
                raise ValueError("Context reference cannot invent a production target or edge")
            row.update(identity_status=edge["identity_status"] if edge else None,
                       edge_support=edge["edge_support"] if edge else None,
                       counted_edge=bool(edge))
        mentions = sorted(anchors + additions, key=lambda row: (row["start"], row["end"], row["mention_id"]))
        contextualize(doc, text, mentions, quote_scopes)
        observations = suggest_treatments(text, mentions, source_id=doc["source_id"], run_id=source.run_id, text_sha256=doc["text_sha256"], quote_scopes=quote_scopes)
        for observation in observations:
            observation["observation_id"] = stable_id("obs-", doc["document_id"], observation["observation_id"])
            observation["document_id"] = doc["document_id"]
            a, b = observation["evidence_start"], observation["evidence_end"]
            if not 0 <= a <= b <= len(text) or text[a:b] != observation["evidence_text"]:
                raise ValueError("Treatment evidence differs from original text")
        summaries = summarize_edges(mentions, observations, source_id=doc["source_id"], run_id=source.run_id)
        for summary in summaries:
            target = summary["target_group_id"]
            edge = edges_by_key[(doc["source_id"], target)]
            summary.update(document_id=doc["document_id"], edge_id=stable_id("edge-", doc["document_id"], target),
                           name=edge["case_name_modal"], edge_support=edge["edge_support"],
                           production_mention_count=int(edge["mention_count"]),
                           production_dd=int(edge["distinct_decisions_count"]),
                           production_dd_changed=False,
                           reference_event_count=len({m["event_id"] for m in mentions if m.get("target_group_id") == target}))
        # Persist both directions of the evidence relationship for offline inspection.
        edge_ids = {edge["target_group_id"]: edge["edge_id"] for edge in summaries}
        assigned, candidates, source_contexts = {}, {}, {}
        for observation in observations:
            observation["edge_id"] = edge_ids.get(observation.get("target_group_id"))
            observation["context_owner_edge_id"] = edge_ids.get(observation.get("context_owner_group_id"))
            observation["context_owner_candidate_edge_ids"] = [edge_ids[target] for target in observation.get("context_owner_candidate_target_ids", []) if target in edge_ids]
            observation["candidate_edge_ids"] = [edge_ids[target] for target in observation.get("candidate_target_ids", []) if target in edge_ids]
            for mention_id in observation.get("target_mention_ids", []):
                assigned.setdefault(mention_id, []).append(observation["observation_id"])
            for mention_id in observation.get("candidate_mention_ids", observation.get("mention_ids", [])):
                if mention_id not in observation.get("target_mention_ids", []):
                    candidates.setdefault(mention_id, []).append(observation["observation_id"])
            for mention_id in observation.get("context_owner_mention_ids", []):
                source_contexts.setdefault(mention_id, []).append(observation["observation_id"])
        for mention in mentions:
            mention["edge_id"] = edge_ids.get(mention.get("target_group_id"))
            mention["assigned_observation_ids"] = assigned.get(mention["mention_id"], [])
            mention["candidate_observation_ids"] = candidates.get(mention["mention_id"], [])
            mention["source_context_observation_ids"] = source_contexts.get(mention["mention_id"], [])
        doc["counts"] = {"full_linked_mentions": sum(bool(m["target_group_id"]) for m in anchors),
                         "full_unlinked_barriers": sum(not m["target_group_id"] for m in anchors),
                         "short_references": len(short), "short_resolved": sum(m["resolution_status"] == "resolved" for m in short),
                         "case_name_mentions": len(named), "case_name_resolved": sum(m["resolution_status"] == "resolved" for m in named),
                         "quotation_scopes": len(quote_scopes), "uncertain_quotation_scopes": sum(bool(scope.get("uncertain")) for scope in quote_scopes),
                         "treatment_observations": len(observations), "target_edges": len(summaries)}
        running_bytes += sum(len(json_text(value).encode("utf-8")) for value in [doc, *mentions, *observations, *summaries])
        if running_bytes > MAX_PACKAGE_BYTES // 2:
            raise ValueError("Batch is too large for the 96 MiB package budget; select fewer documents")
        out_docs.append(doc)
        out_mentions.extend(mentions)
        out_observations.extend(observations)
        out_edges.extend(summaries)
        print(f"{doc['citation']}: {len(anchors)} full, {len(short)} short, {len(named)} names, {len(observations)} signals", file=sys.stderr, flush=True)
    validate_pointer(pointer)
    if code_hashes != {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob("*.py") if not p.name.startswith("test_")}:
        raise ValueError("Context code changed during build; rerun with a stable code version")
    short = [m for m in out_mentions if m["kind"] in SHORT_KINDS]
    named = [m for m in out_mentions if m["kind"] == "case_name"]
    manifest = {
        "schema": VERSION, "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": source.run_id, "input_fingerprint": source.manifest["input_identity"]["fingerprint"],
        "run_directory": str(source.run_dir), "db_path": source.provenance["db_path"],
        "active_pointer": pointer, "selection": selection, "experimental": True,
        "configuration": {"shortforms": "rules-v3", "treatment": "lexical-context-v3", "quotation_scopes": "bounded-scopes-v1", "context_before": 220, "context_after": 240},
        "coverage": "Selected original document rows; arbitration-counted full spans, short-reference markers and source-seeded case names. Not all citations or independently verified treatment.",
        "limitations": [
            "Existing production identity decisions are inherited, including heuristic paths.",
            "Only existing counted targets seed resolution; this version enriches existing edges and does not recover new case identities.",
            "Ambiguous and blocked short references remain in the output.",
            "Treatment outputs are machine lexical suggestions, not human labels or legal conclusions.",
            "No signal does not establish neutral treatment; speaker/proposition context is incomplete.",
            "Per-document edge summaries retain corpus row identity; duplicate source rows must not be added as separate DD.",
            "Original text hashes and live full-span checks are recorded; corpus files are not fully rehashed for every experiment.",
        ],
        "summary": {
            "document_rows": len(out_docs), "source_judgments": len({d["source_id"] for d in out_docs}),
            "full_linked_mentions": sum(d["counts"]["full_linked_mentions"] for d in out_docs),
            "full_unlinked_barriers": sum(d["counts"]["full_unlinked_barriers"] for d in out_docs),
            "short_references": len(short), "short_by_kind": dict(Counter(m["kind"] for m in short)),
            "short_resolved": sum(m["resolution_status"] == "resolved" for m in short),
            "short_by_status": dict(Counter(m["resolution_status"] for m in short)),
            "short_by_basis": dict(Counter(m["resolution_basis"] for m in short)),
            "short_by_kind_status": {kind: dict(Counter(m["resolution_status"] for m in short if m["kind"] == kind)) for kind in sorted(SHORT_KINDS)},
            "quoted_short_references": sum(bool(m.get("quotation_scope")) for m in short),
            "quoted_short_resolved": sum(bool(m.get("quotation_scope")) and m["resolution_status"] == "resolved" for m in short),
            "case_name_mentions": len(named), "case_name_by_status": dict(Counter(m["resolution_status"] for m in named)),
            "case_name_resolved": sum(m["resolution_status"] == "resolved" for m in named),
            "observations": len(out_observations), "observations_by_status": dict(Counter(o["status"] for o in out_observations)),
            "observations_by_speaker": dict(Counter(o.get("speaker_attribution", "unknown") for o in out_observations)),
            "observations_with_context_owner": sum(bool(o.get("context_owner_group_id")) for o in out_observations),
            "edges_with_suggestions": sum(bool(e.get("treatment_suggestions")) for e in out_edges),
            "edges_with_procedural_signals": sum(bool(e.get("procedural_signals")) for e in out_edges),
            "document_target_edges": len(out_edges), "new_production_edges": 0, "production_dd_changed": False,
        },
        "code_sha256": code_hashes,
    }
    return manifest, out_docs, out_mentions, out_observations, out_edges


def output_directory(output):
    output = Path(output).resolve()
    allowed = [(ROOT / "data/experiments").resolve(), (ROOT / "audit/findings").resolve()]
    if not any(parent in output.parents for parent in allowed):
        raise ValueError("Choose a new subdirectory under data/experiments or audit/findings")
    if output.exists():
        raise ValueError("Output directory already exists; inspect it or choose a new experiment name")
    return output


def write_package(output, package):
    from tools.citation_context.report import render_report
    output = output_directory(output)
    manifest, documents, mentions, observations, edges = package
    contents = {name + ".jsonl": "".join(json_text(row) + "\n" for row in values)
                for name, values in (("documents", documents), ("mentions", mentions), ("observations", observations), ("edges", edges))}
    contents["report.html"] = render_report(*package)
    payloads = {name: value.encode("utf-8") for name, value in contents.items()}
    manifest["files"] = {name: {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()} for name, value in payloads.items()}
    payloads["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    if sum(map(len, payloads.values())) > MAX_PACKAGE_BYTES:
        raise ValueError("Output exceeds 96 MiB; select fewer source documents")
    output.mkdir(parents=True, exist_ok=False)
    # Manifest is published last: a failed package is visibly incomplete.
    for name, value in payloads.items():
        (output / name).write_bytes(value)
    return {"output": str(output), **manifest["summary"]}


def inspect_package(args):
    folder = Path(args.package)
    if (folder / "manifest.json").stat().st_size > 1024 * 1024:
        raise ValueError("Package manifest exceeds size budget")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") not in (VERSION, "citation-context-v1", "citation-context-v2"):
        raise ValueError("Unsupported context package")
    filename = args.table + ".jsonl"
    path = folder / filename
    if path.stat().st_size > MAX_PACKAGE_BYTES:
        raise ValueError("Package file exceeds size budget")
    raw = path.read_bytes()
    expected = manifest.get("files", {}).get(filename, {})
    if hashlib.sha256(raw).hexdigest() != expected.get("sha256"):
        raise ValueError("Package contents differ from manifest")
    result, total = [], 0
    counts = {key: Counter() for key in ("kind", "status", "resolution_basis", "speaker_attribution")}
    for line in raw.decode("utf-8").splitlines():
        row = json.loads(line)
        if args.source and row.get("source_id") != args.source:
            continue
        if args.group and row.get("target_group_id") != args.group and args.group not in row.get("candidate_target_ids", []):
            if row.get("context_owner_group_id") != args.group and args.group not in row.get("context_owner_candidate_target_ids", []):
                continue
        if args.unresolved and (row.get("kind") not in SHORT_KINDS or row.get("resolution_status") == "resolved"):
            continue
        if getattr(args, "kind", None) and row.get("kind") not in args.kind:
            continue
        status = row.get("resolution_status", row.get("status"))
        if getattr(args, "status", None) and status not in args.status:
            continue
        if getattr(args, "basis", None) and row.get("resolution_basis") != args.basis:
            continue
        if getattr(args, "speaker", None) and row.get("speaker_attribution") != args.speaker:
            continue
        if getattr(args, "quoted", False) and not (row.get("quotation_scope") or row.get("quote_scope")):
            continue
        total += 1
        for key in counts:
            value = status if key == "status" else row.get(key)
            if value is not None:
                counts[key][str(value)] += 1
        if not getattr(args, "summary_only", False) and len(result) < args.limit:
            result.append(row)
    return {"run_id": manifest["run_id"], "table": args.table, "matching_records": total,
            "breakdown": {key: dict(sorted(value.items())) for key, value in counts.items() if value},
            "shown": len(result), "records": result}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Create a small original-text experiment")
    build.add_argument("--source", action="append", default=[], help="Source ID or exact citation; repeatable")
    build.add_argument("--sources-file", help="Reproducible JSON cohort produced by the cohort command")
    build.add_argument("--group", help="Read source judgments citing this current-run group")
    build.add_argument("--court", action="append", default=[])
    build.add_argument("--limit", type=int, default=24, help="Maximum sources unless --source is explicit (1–200)")
    build.add_argument("--output-dir", required=True)
    sources = commands.add_parser("sources", help="Find source judgments by recorded name or citation")
    sources.add_argument("query", nargs="?", default="")
    sources.add_argument("--court")
    sources.add_argument("--limit", type=int, default=20)
    cohort = commands.add_parser("cohort", help="Scan local corpus to select a diverse short-reference exploration cohort")
    cohort.add_argument("--limit", type=int, default=120)
    cohort.add_argument("--seed", default="20261015")
    cohort.add_argument("--include-package", help="Retain source IDs from an earlier experiment manifest")
    cohort.add_argument("--output", required=True)
    inspect = commands.add_parser("inspect", help="Filter a previously built package, without reading the corpus")
    inspect.add_argument("package")
    inspect.add_argument("--table", choices=("documents", "mentions", "observations", "edges"), default="mentions")
    inspect.add_argument("--source")
    inspect.add_argument("--group")
    inspect.add_argument("--unresolved", action="store_true")
    inspect.add_argument("--kind", action="append", choices=("full", "ibid", "id", "supra", "precite", "case_name"), help="Mention kind; repeatable")
    inspect.add_argument("--status", action="append", help="Mention resolution status or observation status; repeatable")
    inspect.add_argument("--basis", help="Exact short-reference resolution basis")
    inspect.add_argument("--speaker", help="Exact observation speaker attribution")
    inspect.add_argument("--quoted", action="store_true", help="Only records in detected reliable or uncertain quotation scopes")
    inspect.add_argument("--summary-only", action="store_true", help="Count all matching records without printing individual records")
    inspect.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 200:
        parser.error("--limit must be between 1 and 200")
    source = None
    try:
        if args.command == "inspect":
            if (args.unresolved or args.kind or args.basis) and args.table != "mentions":
                raise ValueError("--unresolved, --kind and --basis apply to the mentions table")
            if args.speaker and args.table != "observations":
                raise ValueError("--speaker applies to the observations table")
            if args.status and args.table not in ("mentions", "observations"):
                raise ValueError("--status applies to mentions or observations")
            if args.quoted and args.table not in ("mentions", "observations"):
                raise ValueError("--quoted applies to mentions or observations")
            result = inspect_package(args)
        else:
            if args.command == "build":
                output_directory(args.output_dir)
            source, pointer = open_active()
            if args.command == "cohort":
                from tools.citation_context.cohort import sample_cohort, write_cohort
                include = []
                if args.include_package:
                    path = Path(args.include_package) / "manifest.json"
                    if path.stat().st_size > 1024 * 1024:
                        raise ValueError("Package manifest exceeds size budget")
                    previous = json.loads(path.read_text(encoding="utf-8"))
                    if previous.get("run_id") != source.run_id or previous.get("input_fingerprint") != source.manifest["input_identity"]["fingerprint"]:
                        raise ValueError("Included package belongs to a different active run")
                    include = previous["selection"]["source_ids"]
                selection = sample_cohort(source, limit=args.limit, seed=args.seed, include=include)
                validate_pointer(pointer)
                result = write_cohort(args.output, selection)
            elif args.command == "sources":
                sql = "SELECT source_id,court,corpus_row,citation,name FROM documents WHERE run_id=? AND (instr(research_casefold(name),?)>0 OR instr(research_casefold(citation),?)>0)"
                values = [source.run_id, args.query.casefold(), args.query.casefold()]
                if args.court:
                    sql += " AND court=?"
                    values.append(args.court)
                sql += " ORDER BY court,corpus_row LIMIT ?"
                result = {"run_id": source.run_id, "documents": [dict(row) for row in source.db.execute(sql, [*values, args.limit])]}
            else:
                cohort_provenance = None
                if args.sources_file:
                    from tools.citation_context.cohort import read_cohort
                    if args.source:
                        raise ValueError("Choose either --source or --sources-file")
                    args.source, cohort_provenance = read_cohort(args.sources_file, source)
                documents, selection = select_documents(source, args.source, args.group, args.court, args.limit)
                if cohort_provenance:
                    selection["cohort"] = cohort_provenance
                result = write_package(args.output_dir, build_package(source, documents, selection, pointer))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 1
    finally:
        if source is not None:
            source.close()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
