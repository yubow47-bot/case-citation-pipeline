"""Read-only checks of a pipeline run's counting and evidence contracts.

python tools/check_run.py --run data/run_NAME --output audit/findings/run_check.json

Reads plain CSV or CSV.gz without unpacking or changing the run. Exit 1 means
the artifacts violate a contract or cannot be checked; warnings do not imply
semantic citation accuracy. This tool uses only the Python standard library.
"""
import argparse
import ast
import csv
import datetime
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
csv.field_size_limit(10**9)


class RunCheck:
    def __init__(self, run):
        self.run = Path(run).resolve()
        self.issues = []
        self.metrics = {}
        self.artifacts = {}
        # Read the shared production contract as a literal, without importing
        # production modules or duplicating their list in this standalone tool.
        tree = ast.parse((ROOT / "pipeline" / "decide.py").read_text(encoding="utf-8-sig"))
        self.eligible_bases = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "ELIGIBLE_BASES" for t in node.targets):
                self.eligible_bases = frozenset(ast.literal_eval(node.value.args[0]))
        if self.eligible_bases is None:
            raise ValueError("Cannot read decide.ELIGIBLE_BASES contract")
        # Method card 09: a Jev-confirmed member (N6) also supports an edge.
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MODEL_ELIGIBLE_BASES" for t in node.targets):
                self.eligible_bases |= frozenset(ast.literal_eval(node.value.args[0]))
        tree = ast.parse((ROOT / "pipeline" / "edges.py").read_text(encoding="utf-8-sig"))
        self.candidate_labels = None
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "candidate_label":
                for item in ast.walk(node):
                    if isinstance(item, ast.Return) and isinstance(item.value, ast.Call):
                        func = item.value.func
                        if isinstance(func, ast.Attribute) and func.attr == "get" and isinstance(func.value, ast.Dict):
                            self.candidate_labels = ast.literal_eval(func.value)
        if self.candidate_labels is None:
            raise ValueError("Cannot read edges.candidate_label contract")

    def issue(self, severity, code, detail, count=1, examples=None):
        self.issues.append(dict(severity=severity, code=code, detail=detail,
                                count=count, examples=examples or []))

    def json_file(self, relative):
        path = self.run / relative
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(value, dict):
                raise ValueError("expected a JSON object")
            return value
        except (OSError, ValueError) as exc:
            self.issue("error", "manifest_unreadable", f"{relative}: {exc}")
            return {}

    def rows(self, relative, required):
        path = self.run / relative
        compressed = False
        if not path.is_file():
            path = Path(str(path) + ".gz")
            compressed = True
        if not path.is_file():
            self.issue("error", "artifact_missing", relative)
            return
        self.artifacts[relative] = dict(path=str(path), compressed=compressed,
                                       bytes=path.stat().st_size)
        try:
            opener = gzip.open if compressed else open
            with opener(path, "rt", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f, strict=True)
                if reader.fieldnames and len(set(reader.fieldnames)) != len(reader.fieldnames):
                    raise ValueError("duplicate CSV column names")
                missing = sorted(set(required) - set(reader.fieldnames or []))
                if missing:
                    self.issue("error", "columns_missing", f"{relative}: {missing}")
                    return
                for row in reader:
                    if None in row or any(v is None for v in row.values()):
                        raise ValueError(f"malformed CSV at line {reader.line_num}")
                    yield row
        except (OSError, EOFError, ValueError, csv.Error) as exc:
            self.issue("error", "artifact_unreadable", f"{relative}: {exc}")

    def equal(self, code, left, right, detail):
        if left != right:
            self.issue("error", code, detail + f"; actual={left}, expected={right}")

    def difference(self, code, left, right, detail):
        diff = left - right
        if diff:
            self.issue("error", code, detail, len(diff), sorted(diff)[:5])

    def snapshot(self, manifest):
        self.equal("run_not_complete", manifest.get("status"), "complete",
                   "Run status must be complete")
        if manifest.get("input_identity_verified_unchanged") is not True:
            self.issue("error", "inputs_not_verified", "Run did not record unchanged inputs")
        params = manifest.get("params", {})
        self.metrics["courts"] = params.get("courts", [])
        self.metrics["limit_batches"] = params.get("limit_batches")
        self.metrics["year_from"] = params.get("year_from")
        if params.get("limit_batches") is not None:
            self.issue("warning", "partial_run", "Batch-limited run; not a full-corpus result")
        identity = manifest.get("input_identity", {})
        if not identity.get("fingerprint") or not identity.get("files"):
            self.issue("error", "input_identity_missing", "No recorded input fingerprint/files")
        changed, missing = [], []
        for relative, expected in identity.get("files", {}).items():
            if not relative.startswith(("pipeline/", "decisions/")) and relative != "select_config.yaml":
                continue
            path = ROOT / relative
            if not path.is_file():
                missing.append(relative)
            elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                changed.append(relative)
        if changed or missing:
            self.issue("warning", "historical_inputs", "Current code/tables differ from the run snapshot; use its recorded version to reproduce",
                       len(changed) + len(missing), (changed + missing)[:10])
        seal = manifest.get("output_identity")
        if not seal:
            self.issue("warning", "outputs_unsealed", "Run manifest has no output content hashes; structural checks cannot establish that artifacts are the original bytes")
        else:
            files = seal.get("files", {})
            if not files:
                self.issue("error", "output_identity_empty", "Output seal must include artifacts")
            expected = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
            self.equal("output_identity_fingerprint", seal.get("fingerprint"), expected, "Output seal fingerprint")
            for relative, sha in files.items():
                path = (self.run / relative).resolve()
                if self.run not in path.parents or not path.is_file():
                    self.issue("error", "sealed_artifact_missing", relative)
                    continue
                digest = hashlib.sha256()
                with path.open("rb") as f:
                    for block in iter(lambda: f.read(1024 * 1024), b""):
                        digest.update(block)
                self.equal("sealed_artifact_changed", digest.hexdigest(), sha, relative)

    def tables(self):
        selection = self.json_file("select_out/manifest.json")
        edge_manifest = self.json_file("edges/manifest.json")
        threshold = selection.get("threshold_dd")
        if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold < 0:
            self.issue("error", "threshold_missing", "Select manifest must specify a nonnegative integer threshold_dd")
            threshold = None
        fields = ("merged_group_id", "is_primary", "distinct_decisions_count", "kept",
                  "group_foreign_status", "group_origin_country", "group_origin_status")
        groups = {}
        primaries = Counter()
        totals = Counter()
        for row in self.rows("select_out/selected.csv", fields):
            gid = row["merged_group_id"]
            try:
                dd = int(row["distinct_decisions_count"])
                if dd < 0 or not gid or row["kept"] not in ("true", "false") or row["is_primary"] not in ("true", "false"):
                    raise ValueError("empty group, negative DD or invalid boolean")
            except ValueError as exc:
                self.issue("error", "invalid_member", f"group={gid}: {exc}")
                continue
            attrs = (dd, row["kept"], row["group_foreign_status"],
                     row["group_origin_country"], row["group_origin_status"])
            if gid in groups and groups[gid] != attrs:
                totals["member_disagreement"] += 1
            groups.setdefault(gid, attrs)
            primaries[gid] += row["is_primary"] == "true"
            totals["rows_total"] += 1
            totals["kept" if row["kept"] == "true" else "dropped"] += 1
            if threshold is not None and (row["kept"] == "true") != (dd >= threshold):
                totals["threshold_mismatch"] += 1
        for code in ("member_disagreement", "threshold_mismatch"):
            if totals[code]:
                self.issue("error", code, "Member rows violate the group/selection contract", totals[code])
        bad_primary = [g for g in groups if primaries[g] != 1]
        if bad_primary:
            self.issue("error", "bad_primary", "Each group must have exactly one primary", len(bad_primary), bad_primary[:5])
        totals["groups_total"] = len(groups)
        totals["groups_kept"] = sum(g[1] == "true" for g in groups.values())
        for key in ("rows_total", "kept", "dropped", "groups_total", "groups_kept"):
            # The production Counter omits kept/dropped when their value is zero.
            default = 0 if key in ("kept", "dropped") else None
            self.equal("select_manifest_mismatch", totals[key], selection.get("stats", {}).get(key, default), key)
        self.metrics.update({k: totals[k] for k in ("rows_total", "groups_total", "groups_kept")})
        self.metrics["threshold_dd"] = threshold
        self.metrics["group_foreign_status"] = dict(Counter(g[2] for g in groups.values()))
        self.metrics["group_origin_status"] = dict(Counter(g[4] for g in groups.values()))

        effective, excluded, quarantined = {}, {}, {}
        effective_fields = ("merged_group_id", "source_decision", "status", "exclusion_reason", "identity_status")
        for row in self.rows("decide_out/cross_court/effective_sources.csv", effective_fields):
            pair = (row["source_decision"], row["merged_group_id"])
            if pair in effective or pair in excluded:
                totals["duplicate_effective"] += 1
            if row["status"] == "counted":
                effective[pair] = row["identity_status"]
            elif row["status"] == "excluded_source":
                quarantined[pair] = row["exclusion_reason"]
            elif row["status"] == "excluded_self":
                excluded[pair] = row["exclusion_reason"]
            else:
                totals["invalid_effective_status"] += 1
            if pair[1] not in groups or not pair[0]:
                totals["invalid_effective_reference"] += 1

        edges, foreign, tentative = {}, {}, {}
        per_group = Counter()
        statuses = Counter()
        supports = Counter()
        edge_fields = ("source_decision", "resolved_cited_case", "foreign_status", "edge_support",
                       "origin_country", "origin_evidence_ids", "group_origin_status",
                       "group_origin_country", "group_foreign_status", "distinct_decisions_count", "identity_status",
                       "mention_count", "mention_detail_key")
        for row in self.rows("edges/citation_edges.csv", edge_fields):
            pair = (row["source_decision"], row["resolved_cited_case"])
            if not str(row.get("mention_count", "")).isdigit() or int(row["mention_count"]) <= 0:
                totals["edge_without_positive_mentions"] += 1
            if not row.get("mention_detail_key", "").strip():
                totals["edge_without_mention_provenance"] += 1
            if pair in edges:
                totals["duplicate_edges"] += 1
            edges[pair] = row_digest(row)
            per_group[pair[1]] += 1
            statuses[row["foreign_status"]] += 1
            supports[row["edge_support"]] += 1
            attrs = groups.get(pair[1])
            if attrs is None:
                totals["edge_group_missing"] += 1
            elif (str(attrs[0]), attrs[2], attrs[3], attrs[4]) != (
                    row["distinct_decisions_count"], row["group_foreign_status"],
                    row["group_origin_country"], row["group_origin_status"]):
                totals["edge_group_disagreement"] += 1
            if row["edge_support"] == "heuristic_only":
                if ((row["foreign_status"] != "UNDETERMINED" or row["origin_country"] or row["origin_evidence_ids"])
                        and not (row.get("origin_basis", "").startswith("member:")
                                 and row["origin_evidence_ids"])):
                    totals["heuristic_origin_leak"] += 1
                if row["group_origin_status"] == "DETERMINED":
                    tentative[pair] = row_digest(row, TENTATIVE_FIELDS)
            elif row["edge_support"] != "supported":
                totals["invalid_edge_support"] += 1
            elif (attrs and not row.get("origin_basis", "").startswith("member:")
                  and (row["foreign_status"], row["origin_country"]) != (attrs[2], attrs[3])):
                totals["supported_origin_mismatch"] += 1
            if pair in effective and (row["edge_support"] == "supported") != (effective[pair] in self.eligible_bases):
                totals["edge_identity_support_mismatch"] += 1
            if pair in effective:
                basis = effective[pair]
                expected_label = basis if basis in self.eligible_bases else self.candidate_labels.get(basis, basis)
                if row["identity_status"] != expected_label:
                    totals["edge_identity_label_mismatch"] += 1
            if row["foreign_status"] not in ("FOREIGN", "DOMESTIC_CA", "UNDETERMINED", "CONFLICT"):
                totals["invalid_foreign_status"] += 1
            if row["foreign_status"] == "FOREIGN":
                foreign[pair] = edges[pair]
                if ((row["edge_support"] != "supported"
                     and not row.get("origin_basis", "").startswith("member:"))
                        or row["origin_country"] in ("", "CA") or not row["origin_evidence_ids"]):
                    totals["foreign_without_support"] += 1
            if pair in excluded:
                totals["self_citation_reintroduced"] += 1
        self.difference("effective_without_edge", set(effective), set(edges), "Counted sources missing from edges")
        self.difference("edge_without_effective", set(edges), set(effective), "Edges without a counted effective association")
        bad_dd = [gid for gid, attrs in groups.items() if per_group[gid] != attrs[0]]
        if bad_dd:
            self.issue("error", "edge_dd_mismatch", "Distinct edge sources must equal group DD", len(bad_dd), bad_dd[:5])
        self.check_view("edges/foreign_edges.csv", foreign)
        self.check_view("edges/tentative_edges.csv", tentative, TENTATIVE_FIELDS)
        observed_excluded = {}
        for row in self.rows("edges/self_excluded_edges.csv", ("source_decision", "resolved_cited_case", "exclusion_reason")):
            pair = (row["source_decision"], row["resolved_cited_case"])
            if pair in observed_excluded:
                totals["duplicate_self_view"] += 1
            observed_excluded[pair] = row["exclusion_reason"]
        self.difference("self_view_missing", set(excluded), set(observed_excluded), "Excluded sources missing from audit view")
        self.difference("self_view_extra", set(observed_excluded), set(excluded), "Audit view includes unknown excluded sources")
        if any(observed_excluded[p] != excluded[p] for p in set(excluded) & set(observed_excluded)):
            totals["self_view_reason_mismatch"] += 1
        if quarantined:
            observed_quarantine = {}
            for row in self.rows("edges/source_excluded_edges.csv", ("source_decision", "resolved_cited_case", "exclusion_reason")):
                pair = (row["source_decision"], row["resolved_cited_case"])
                if pair in observed_quarantine:
                    self.issue("error", "duplicate_source_exclusion", "Duplicate quarantined source link")
                observed_quarantine[pair] = row["exclusion_reason"]
            if observed_quarantine != quarantined:
                self.issue("error", "source_exclusion_mismatch", "Quarantined source links differ from their evidence")
            if set(quarantined) & set(edges):
                self.issue("error", "quarantined_source_reintroduced", "Unmeasurable sources cannot contribute edges")
        for code in ("duplicate_effective", "invalid_effective_status", "invalid_effective_reference", "duplicate_edges",
                     "edge_group_missing", "edge_group_disagreement", "heuristic_origin_leak", "invalid_edge_support",
                     "supported_origin_mismatch", "edge_identity_support_mismatch", "edge_identity_label_mismatch", "invalid_foreign_status",
                     "foreign_without_support", "self_citation_reintroduced", "duplicate_self_view", "self_view_reason_mismatch",
                     "edge_without_positive_mentions", "edge_without_mention_provenance"):
            if totals[code]:
                self.issue("error", code, "Effective membership/edge evidence contract violated", totals[code])
        actual = dict(edges_total=sum(statuses.values()), edges_foreign=statuses["FOREIGN"],
                      edges_domestic_ca=statuses["DOMESTIC_CA"], edges_undetermined=statuses["UNDETERMINED"],
                      edges_conflict=statuses["CONFLICT"], edges_supported=supports["supported"],
                      edges_heuristic_only=supports["heuristic_only"], self_excluded_sources=len(excluded),
                      tentative_edges=len(tentative))
        for key, count in actual.items():
            self.equal("edge_manifest_mismatch", count, edge_manifest.get("stats", {}).get(key, 0), key)
        self.metrics.update(actual)

    def check_view(self, relative, expected, fields=None):
        observed = {}
        required = fields or ("source_decision", "resolved_cited_case")
        for row in self.rows(relative, required):
            pair = (row["source_decision"], row["resolved_cited_case"])
            if pair in observed:
                self.issue("error", "duplicate_view_row", relative, examples=[pair])
            observed[pair] = row_digest(row, fields)
        self.difference("view_missing", set(expected), set(observed), relative)
        self.difference("view_extra", set(observed), set(expected), relative)
        changed = [p for p in set(observed) & set(expected) if observed[p] != expected[p]]
        if changed:
            self.issue("error", "view_content_mismatch", relative, len(changed), sorted(changed)[:5])

    def execute(self):
        manifest = self.json_file("run_manifest.json")
        try:
            self.snapshot(manifest)
            self.tables()
        except (TypeError, AttributeError, KeyError, ValueError) as exc:
            self.issue("error", "invalid_artifact_schema", str(exc))
        compressed = [k for k, v in self.artifacts.items() if v["compressed"]]
        if compressed:
            self.issue("warning", "compressed_artifacts", "Checked CSV.gz directly; foundation, research, quality and source tracing support these retained artifacts without decompression",
                       len(compressed), compressed)
        errors = sum(i["severity"] == "error" for i in self.issues)
        return dict(schema_version=1, checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    run_directory=str(self.run), status="failed" if errors else "passed",
                    scope="Artifact consistency only. No extraction recall, identity accuracy, corpus hash verification or statistical calibration.",
                    metrics=self.metrics, issues=self.issues, artifacts=self.artifacts)


TENTATIVE_FIELDS = ("source_decision", "resolved_cited_case", "identity_status", "group_origin_country",
                    "group_foreign_status", "origin_evidence_ids", "mention_count", "case_name_modal")


def row_digest(row, fields=None):
    values = {k: row.get(k, "") for k in fields} if fields else row
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def check_run(run):
    return RunCheck(run).execute()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", required=True)
    ap.add_argument("--output", help="JSON report path outside the checked run")
    args = ap.parse_args()
    run = Path(args.run).resolve()
    output = Path(args.output).resolve() if args.output else None
    if output and (output == run or run in output.parents):
        ap.error("Report output must be outside the checked run; run artifacts are read-only")
    report = check_run(run)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(1 if report["status"] == "failed" else 0)


if __name__ == "__main__":
    main()
