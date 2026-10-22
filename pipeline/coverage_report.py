# -*- coding: utf-8 -*-
"""coverage_report.py — 候选、计数位置与最终关系的覆盖诊断（规格 §12.1）

    python pipeline/coverage_report.py --run-dir data/run_X

run 模式输出 coverage/summary.json 与 reporter.csv / neutral.csv / series.csv。
它在新 run 收尾封印前自动生成；已有 output_identity 的 complete run 不允许原地改写。
候选行只作诊断；计数位置只取 mentions_candidates.csv 的 counted 行；关系直接
读取 edges/citation_edges.csv。exact-span positions 不表示互不重叠的实体数，
这些产物也不提供未观察引证的分母，因此不报告全语料召回率。

以下单族命令保留为旧版候选诊断接口。

输出**尚未入表**的缩写 / 代码 / 前缀，按被多少份不同判决引用（dd）降序——让填表
永远知道「下一条该填哪个」，每填一批可对比候选诊断变化。

性质是**提案**（给人看的待办清单），不喂任何生产脚本，也不写 decisions/。

用法
    python pipeline/coverage_report.py --kind reporter \
        --classified data/classify_out/SCC/classified.csv data/classify_out/ONCA/classified.csv \
        --out data/coverage_out/reporter.csv
    --kind neutral / --kind series 同理

三种报告
    reporter  法域 UNSUPPORTED 的汇编缩写族（nk 归一）。区分「表里没有」与「表里有但
              判不出」——后者多是同形异义消不开（K.B. 英国/魁北克），要补的是区间，
              不是新行
    neutral   shape_neutral_bare 中法域 UNSUPPORTED 的裸代码族（normalize_code 归一）。
              方括号形态里的中立码候选要先分诊（汇编缩写去点后与之同形，AC 实为 A.C.），
              见 audit/neutral_triage.py
    series    被判 unrecognized_series_prefix 的前缀族（normalize_code 归一）。注意这一族里
              大半是结构骨架误报（See、Section、Vol.），正是这张表要拦的东西——排行靠前
              不等于该入表

与规格 §12 的出入
    规格写的输入是归并层 merged.csv；本实现读分类层 classified.csv——merged.csv 没有
    leading_abbr 与 shape_name，series / neutral 两种报告做不出来。dd 由逐行的
    source_decision_citation 直接取并集，与归并层 §9.2 同一口径（行级误报不计，series
    报告除外：它报的正是被行级拒绝的那批）。
"""
import argparse
import csv
import datetime
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import nk, normalize_code                      # noqa: E402
from artifacts import open_csv, replace_file                 # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECISIONS = os.path.join(ROOT, "decisions")

TABLE_OF = {"reporter": "reporter_jurisdiction.csv",
            "neutral": "neutral_court_codes.csv",
            "series": "series_prefix.csv"}

ARBITRATION_GROUPS = ("rejected_row", "self", "superseded", "alternative",
                      "conflict", "counted", "other")
FAMILY_FIELDS = ["rank", "family", "top_printed_form", "report_scope",
                 "candidate_rows", "candidate_exact_span_positions",
                 "candidate_distinct_sources", "counted_unsupported_positions",
                 "counted_unsupported_distinct_sources", "table_status",
                 "candidate_by_court", "counted_unsupported_by_court"] + [
                     "candidate_%s_rows" % group for group in ARBITRATION_GROUPS]


def table_keys(kind):
    path = os.path.join(DECISIONS, TABLE_OF[kind])
    keys = set()
    with open_csv(path) as f:
        for r in csv.DictReader(f):
            if kind == "reporter":
                for v in (r.get("abbreviation"), r.get("normalized_key")):
                    if v and v.strip():
                        keys.add(nk(v))
            elif kind == "neutral":
                if (r.get("court_code") or "").strip():
                    keys.add(normalize_code(r["court_code"]))
            else:
                for v in (r.get("canonical_prefix"), r.get("normalized_key")):
                    if v and v.strip():
                        keys.add(normalize_code(v))
    return keys


def family_of(kind, r):
    """返回 (归一键, 印刷形)；不属本报告的行返回 None。"""
    rej = r.get("rejected_reason") or ""
    if kind == "series":
        if "unrecognized_series_prefix" not in rej:
            return None
        printed = (r.get("leading_abbr") or "").strip()
        return normalize_code(printed), printed
    if rej or r.get("jurisdiction") != "UNSUPPORTED":
        return None
    if kind == "reporter":
        if r.get("citation_kind") != "reporter":
            return None
        printed = (r.get("abbreviation") or "").strip()
        return nk(printed), printed
    if r.get("shape_name") != "shape_neutral_bare":
        return None
    printed = (r.get("token") or "").strip()
    return normalize_code(printed), printed


def legacy_report(a):
    """Keep the single-family candidate diagnostic interface and CSV columns."""
    rows, dd, forms = Counter(), defaultdict(set), defaultdict(Counter)
    for p in a.classified:
        with open_csv(p) as f:
            for r in csv.DictReader(f):
                fam = family_of(a.kind, r)
                if not fam or not fam[0]:
                    continue
                key, printed = fam
                rows[key] += 1
                source = r.get("source_decision_citation") or ""
                if source:
                    dd[key].add(source)
                forms[key][printed] += 1

    in_table = table_keys(a.kind)
    total = sum(rows.values())
    order = sorted(rows, key=lambda k: (-len(dd[k]), -rows[k], k))

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    tmp = a.out + ".tmp"
    run = 0
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "family", "top_printed_form", "rows", "distinct_decisions",
                     "cum_pct_rows", "table_status"])
        for i, k in enumerate(order, 1):
            run += rows[k]
            w.writerow([i, k, forms[k].most_common(1)[0][0], rows[k], len(dd[k]),
                        round(run / total * 100, 2) if total else 0.0,
                        "in_table_unresolved" if k in in_table else "absent"])
    replace_file(tmp, a.out)

    print("kind=%s  待填 %d 行 / %d 族 -> %s" % (a.kind, total, len(order), a.out))
    run = 0
    for i, k in enumerate(order[:a.top], 1):
        run += rows[k]
        print("  %3d  %-16s %-22s rows %-7d dd %-6d cum %5.1f%%  %s"
              % (i, k[:16], forms[k].most_common(1)[0][0][:22], rows[k], len(dd[k]),
                 run / total * 100 if total else 0.0,
                 "表内判不出" if k in in_table else ""))


def position_key(court, row):
    return (court, row.get("source_decision_citation") or "",
            row.get("corpus_row_index") or "",
            row.get("match_start_offset") or "",
            row.get("match_end_offset") or "")


def arbitration_group(status):
    """Group existing ledger labels for display without changing arbitration."""
    if status == "counted":
        return "counted"
    if status == "rejected_row":
        return "rejected_row"
    if status == "self_citation_row" or status.startswith("self_"):
        return "self"
    if status in ("cross_boundary_invalid", "year_reread_as_vol_invalid") \
            or status.startswith("superseded"):
        return "superseded"
    if status.endswith("undecided") or status.startswith("conflict"):
        return "conflict"
    if status.startswith("alternative_"):
        return "alternative"
    return "other"


def new_position_stats():
    return {"rows": 0, "positions": set(), "sources": set()}


def add_position(stats, position, source):
    stats["rows"] += 1
    stats["positions"].add(position)
    if source:
        stats["sources"].add(source)


def position_metrics(stats):
    return {"rows": stats["rows"],
            "exact_span_positions": len(stats["positions"]),
            "distinct_sources": len(stats["sources"])}


def new_scope_stats():
    return {key: new_position_stats() for key in ("candidates", "counted", "unsupported")}


def counted_metrics(counted, unsupported):
    return {"positions": len(counted["positions"]),
            "distinct_sources": len(counted["sources"]),
            "unsupported_positions": len(unsupported["positions"]),
            "unsupported_distinct_sources": len(unsupported["sources"])}


def scope_metrics(stats):
    return {"candidates": position_metrics(stats["candidates"]),
            "counted_positions": counted_metrics(stats["counted"], stats["unsupported"])}


def relation_metrics(rows):
    return {"unique_relations": len(rows),
            "distinct_sources": len({key[0] for key in rows if key[0]})}


def relation_summary(path):
    """Summarize only the final edge artifact; identity and origin are separate."""
    rows, unique = 0, {}
    with open_csv(path) as f:
        for row in csv.DictReader(f):
            rows += 1
            key = (row.get("source_decision") or "",
                   row.get("resolved_cited_case") or "")
            attributes = (row.get("edge_support") or "",
                          row.get("foreign_status") or "",
                          row.get("origin_country") or "")
            if key in unique and unique[key] != attributes:
                raise ValueError("Conflicting classifications for citation edge %r" % (key,))
            unique[key] = attributes

    by_support = defaultdict(set)
    by_foreign = defaultdict(set)
    by_country_status = defaultdict(set)
    by_country = defaultdict(set)
    support_foreign = defaultdict(set)
    support_country_status = defaultdict(set)
    for key, (support, foreign, country) in unique.items():
        country_status = ("conflict" if foreign == "CONFLICT" else
                          "known" if country else "undetermined")
        by_support[support].add(key)
        by_foreign[foreign].add(key)
        by_country_status[country_status].add(key)
        if country:
            by_country[country].add(key)
        support_foreign[(support, foreign)].add(key)
        support_country_status[(support, country_status)].add(key)

    for support in ("supported", "heuristic_only"):
        by_support[support]
        for foreign in ("DOMESTIC_CA", "FOREIGN", "UNDETERMINED", "CONFLICT"):
            by_foreign[foreign]
            support_foreign[(support, foreign)]
        for country_status in ("known", "undetermined", "conflict"):
            by_country_status[country_status]
            support_country_status[(support, country_status)]
    return {
        "rows": rows, **relation_metrics(unique),
        "by_edge_support": {k: relation_metrics(v) for k, v in sorted(by_support.items())},
        "by_foreign_status": {k: relation_metrics(v) for k, v in sorted(by_foreign.items())},
        "by_origin_country_status": {
            k: relation_metrics(v) for k, v in sorted(by_country_status.items())},
        "by_origin_country": {k: relation_metrics(v) for k, v in sorted(by_country.items())},
        "by_edge_support_and_foreign_status": [
            {"edge_support": support, "foreign_status": foreign, **relation_metrics(v)}
            for (support, foreign), v in sorted(support_foreign.items())],
        "by_edge_support_and_origin_country_status": [
            {"edge_support": support, "origin_country_status": status, **relation_metrics(v)}
            for (support, status), v in sorted(support_country_status.items())],
    }


def new_family_stats():
    return {"candidates": new_position_stats(), "counted": new_position_stats(),
            "forms": Counter(), "groups": Counter(),
            "candidate_by_court": defaultdict(new_position_stats),
            "counted_unsupported_by_court": defaultdict(new_position_stats)}


def family_court_json(stats):
    return json.dumps({court: {"positions": len(value["positions"]),
                               "distinct_sources": len(value["sources"])}
                       for court, value in sorted(stats.items())}, ensure_ascii=False, sort_keys=True)


def write_family_report(path, kind, families):
    in_table = table_keys(kind)
    order = sorted(families, key=lambda key: (
        -len(families[key]["counted"]["sources"]),
        -len(families[key]["candidates"]["sources"]),
        -families[key]["candidates"]["rows"], key))
    tmp = str(path) + ".tmp"
    scope = ("rejected_diagnostic" if kind == "series" else
             "counted_unsupported_with_candidate_diagnostics")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FAMILY_FIELDS)
        writer.writeheader()
        for rank, key in enumerate(order, 1):
            stats = families[key]
            candidate = stats["candidates"]
            counted = stats["counted"]
            printed = sorted(stats["forms"], key=lambda s: (-stats["forms"][s], s))[0]
            writer.writerow({
                "rank": rank, "family": key, "top_printed_form": printed,
                "report_scope": scope, "candidate_rows": candidate["rows"],
                "candidate_exact_span_positions": len(candidate["positions"]),
                "candidate_distinct_sources": len(candidate["sources"]),
                "counted_unsupported_positions": len(counted["positions"]),
                "counted_unsupported_distinct_sources": len(counted["sources"]),
                "table_status": "in_table_unresolved" if key in in_table else "absent",
                "candidate_by_court": family_court_json(stats["candidate_by_court"]),
                "counted_unsupported_by_court": family_court_json(stats["counted_unsupported_by_court"]),
                **{"candidate_%s_rows" % group: stats["groups"][group]
                   for group in ARBITRATION_GROUPS},
            })
    replace_file(tmp, path)
    return {"path": "coverage/" + path.name, "families": len(order), "report_scope": scope}


def run_report(run_dir):
    run_dir = Path(run_dir).resolve()
    manifest_path = run_dir / "run_manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if manifest.get("status") == "complete" and "output_identity" in manifest:
            raise ValueError("Immutable sealed run: coverage report is generated during new-run finalization; cannot write into %s" % run_dir)
    classified_root = run_dir / "classify_out"
    courts = sorted(p.name for p in classified_root.iterdir() if p.is_dir())
    if not courts:
        raise ValueError("No court classified artifacts in %s" % classified_root)
    candidates = new_position_stats()
    counted = new_position_stats()
    unsupported = new_position_stats()
    by_status = defaultdict(new_position_stats)
    by_group = {group: new_position_stats() for group in ARBITRATION_GROUPS}
    by_jurisdiction = defaultdict(new_position_stats)
    by_court = defaultdict(new_scope_stats)
    by_shape = defaultdict(new_scope_stats)
    families = {kind: defaultdict(new_family_stats) for kind in TABLE_OF}
    inputs = {"courts": courts, "classified": [], "mentions": [],
              "edges": "edges/citation_edges.csv"}

    for court in courts:
        classified_path = classified_root / court / "classified.csv"
        mentions_path = run_dir / "merge_out" / court / "mentions_candidates.csv"
        inputs["classified"].append(classified_path.relative_to(run_dir).as_posix())
        inputs["mentions"].append(mentions_path.relative_to(run_dir).as_posix())
        # The ledger retains classification and arbitration but omits printed family
        # fields. Keep only qualifying candidate IDs for this per-court join.
        family_by_candidate = {}
        with open_csv(classified_path) as f:
            for row in csv.DictReader(f):
                for kind in TABLE_OF:
                    family = family_of(kind, row)
                    if family and family[0]:
                        family_by_candidate[row["candidate_id"]] = (kind, *family)
                        break
        with open_csv(mentions_path) as f:
            for row in csv.DictReader(f):
                position = position_key(court, row)
                source = row.get("source_decision_citation") or ""
                status = row.get("arbitration_status") or ""
                group = arbitration_group(status)
                add_position(candidates, position, source)
                add_position(by_status[status], position, source)
                add_position(by_group[group], position, source)
                scopes = (by_court[court], by_shape[row.get("shape_name") or ""])
                for scope in scopes:
                    add_position(scope["candidates"], position, source)
                is_counted_unsupported = status == "counted" and row.get("jurisdiction") == "UNSUPPORTED"
                if status == "counted":
                    add_position(counted, position, source)
                    add_position(by_jurisdiction[row.get("jurisdiction") or ""], position, source)
                    for scope in scopes:
                        add_position(scope["counted"], position, source)
                    if is_counted_unsupported:
                        add_position(unsupported, position, source)
                        for scope in scopes:
                            add_position(scope["unsupported"], position, source)
                family = family_by_candidate.get(row.get("candidate_id"))
                if family:
                    kind, key, printed = family
                    stats = families[kind][key]
                    add_position(stats["candidates"], position, source)
                    add_position(stats["candidate_by_court"][court], position, source)
                    stats["forms"][printed] += 1
                    stats["groups"][group] += 1
                    if is_counted_unsupported:
                        add_position(stats["counted"], position, source)
                        add_position(stats["counted_unsupported_by_court"][court], position, source)

    relations = relation_summary(run_dir / inputs["edges"])
    output = run_dir / "coverage"
    output.mkdir(exist_ok=True)
    family_reports = {kind: write_family_report(output / (kind + ".csv"), kind, families[kind])
                      for kind in TABLE_OF}
    summary = {
        "schema_version": "coverage-1.0",
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "run_dir": str(run_dir), "inputs": inputs,
        "definitions": {
            "candidate_rows": "All rows in the per-court mentions_candidates.csv ledger; diagnostic only.",
            "exact_span_position_key": ["court", "source_decision_citation", "corpus_row_index",
                                        "match_start_offset", "match_end_offset"],
            "exact_span_positions": "Distinct exact-span keys, not mutually non-overlapping entities.",
            "arbitration_breakdown": "Rows are partitioned by ledger status/group. Position and source sets may overlap across statuses, groups and families; do not add them.",
            "by_court_and_shape": "Per-court and original shape_name summaries use the same exact-span and counted denominators. A position may have multiple candidate shapes.",
            "arbitration_groups": {
                "rejected_row": "rejected_row", "self": "self_citation_row / self_*",
                "superseded": "cross_boundary_invalid / year_reread_as_vol_invalid / superseded*",
                "alternative": "alternative_*", "conflict": "*undecided / conflict*",
                "counted": "counted", "other": "Any remaining ledger status, retained explicitly."},
            "counted_positions": "Denominator: distinct exact-span keys of merge-ledger rows with arbitration_status=counted. This precedes final relation membership; later decide/edges processing may exclude self-citations. Use relations for final effective links.",
            "counted_unsupported_positions": "Subset of counted positions with jurisdiction=UNSUPPORTED; affected nonempty source citations are reported separately.",
            "relations": "Denominator: distinct (source_decision, resolved_cited_case) keys read directly from edges/citation_edges.csv; never inferred from candidate rows.",
            "origin_country_status": "conflict when foreign_status=CONFLICT; otherwise known when origin_country is present, undetermined when absent. Independent of edge_support.",
            "distinct_sources": "Distinct nonempty source citation strings within each reported set; an empty source does not count as a judgment.",
            "family_priority": "Descending counted_unsupported_distinct_sources, then candidate_distinct_sources, candidate_rows, family key.",
            "series": "Rejected unrecognized_series_prefix families are rejected diagnostics, not missed citations.",
            "recall": "No whole-corpus recall is claimed: unobserved citations have no measured denominator.",
        },
        "candidates": {
            **position_metrics(candidates),
            "by_arbitration_status": {k: position_metrics(v) for k, v in sorted(by_status.items())},
            "by_arbitration_group": {k: position_metrics(v) for k, v in by_group.items()},
        },
        "counted_positions": {
            **counted_metrics(counted, unsupported),
            "by_jurisdiction": {k: {"positions": len(v["positions"]),
                                     "distinct_sources": len(v["sources"])}
                                for k, v in sorted(by_jurisdiction.items())},
        },
        "by_court": {k: scope_metrics(v) for k, v in sorted(by_court.items())},
        "by_shape": {k: scope_metrics(v) for k, v in sorted(by_shape.items())},
        "relations": relations, "families": family_reports,
    }
    path = output / "summary.json"
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write("\n")
    replace_file(tmp, path)
    print("coverage: %d candidate rows / %d exact-span positions; %d counted positions (%d UNSUPPORTED); %d final relations -> %s"
          % (candidates["rows"], len(candidates["positions"]), len(counted["positions"]),
             len(unsupported["positions"]), relations["unique_relations"], output))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run-dir")
    mode.add_argument("--kind", choices=sorted(TABLE_OF))
    ap.add_argument("--classified", nargs="+")
    ap.add_argument("--out")
    ap.add_argument("--top", type=int, default=20)
    a = ap.parse_args(argv)
    if a.run_dir and (a.classified or a.out):
        ap.error("--run-dir writes coverage/ in that run; do not combine with --classified or --out")
    if a.kind and (not a.classified or not a.out):
        ap.error("--kind requires --classified and --out")
    csv.field_size_limit(10 ** 9)
    if a.run_dir:
        return run_report(a.run_dir)
    return legacy_report(a)


if __name__ == "__main__":
    main()
