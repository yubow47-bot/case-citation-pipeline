# -*- coding: utf-8 -*-
"""r2closure_sensitivity.py — §8 案名投票三口径敏感性分析（只比较，不改生产规则）

用法：python implementation/r2closure_sensitivity.py <r2d_run_dir>

对每个口径（A=current 生产口径 / B=dedup_position 同一出现位置去重 /
C=counted_only 仅 counted 候选投票）：
  merge(共享 classify 输入, --name-vote-pool X) → decide 院内×2 → 跨院 → select → edges
全部写进 <r2d>/sensitivity_<X>/，不覆盖主运行产物。

case_name_modal 的生成与消费路径（先记录）：
  生成：merge._emit 的两级投票（nk 折叠拼写变体→票数最多→印刷形众数），
       池口径由 --name-vote-pool 决定（本参数即本轮敏感性的唯一自变量）；
  消费：decide.cluster_same_case 以 nk(case_name_modal) 作为案件聚类的
       分桶键（§10.3 同名 + 年份 ±1 连链）——**case_name_modal 实际参与
       案件聚类**，不是纯展示列。
B 口径的位置稳定键 = (source_decision_citation, corpus_row_index,
match_start_offset, match_end_offset)；同位置多个 nk 互异案名 → 该位置弃权
（确定、可审计、与输入顺序无关）。
"""
import csv
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COURTS = ("SCC", "ONCA")
REGIMES = ("current", "dedup_position", "counted_only")


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def run(cmd):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable] + cmd, cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    if p.returncode != 0:
        raise SystemExit("FAIL %s\n%s" % (cmd, p.stderr[-2000:]))


def pipeline_for(r2d, regime):
    base = os.path.join(r2d, "sensitivity_%s" % regime)
    for court in COURTS:
        run([os.path.join("pipeline", "merge.py"), "--court", court,
             "--input", os.path.join(r2d, "classify_out", court, "classified.csv"),
             "--output", os.path.join(base, "merge_out", court),
             "--name-vote-pool", regime])
    for court in COURTS:
        run([os.path.join("pipeline", "decide.py"), "--court", court,
             "--input", os.path.join(base, "merge_out", court, "merged.csv"),
             "--folded-log", os.path.join(base, "merge_out", court, "folded_log.csv"),
             "--decision-ids", os.path.join(base, "merge_out", court, "decision_ids.csv"),
             "--output", os.path.join(base, "decide_out", court)])
    run([os.path.join("pipeline", "decide.py"), "--cross-court",
         "--inputs"] + [os.path.join(base, "decide_out", c, "decided.csv")
                        for c in COURTS] +
        ["--output", os.path.join(base, "decide_out", "cross_court")])
    run([os.path.join("pipeline", "select.py"),
         "--input", os.path.join(base, "decide_out", "cross_court", "decided.csv"),
         "--config", os.path.join(ROOT, "select_config.yaml"),
         "--profile", "default", "--output", os.path.join(base, "select_out")])
    run([os.path.join("pipeline", "edges.py"),
         "--decided", os.path.join(base, "decide_out", "cross_court", "decided.csv"),
         "--effective", os.path.join(base, "decide_out", "cross_court",
                                     "effective_sources.csv"),
         "--merge-out", os.path.join(base, "merge_out"),
         "--output", os.path.join(base, "edges")])
    return base


def groups_of(path):
    g = defaultdict(list)
    for r in rows(os.path.join(path, "decide_out", "cross_court", "decided.csv")):
        g[r["merged_group_id"]].append(r)
    out = {}
    for gid, ms in g.items():
        key = frozenset("%s|%s" % (m.get("court") or "", m["merge_key"])
                        for m in ms)
        p = next((m for m in ms if m["is_primary"] == "true"), ms[0])
        out[key] = {"gid": gid, "modal": p.get("case_name_modal") or "",
                    "dd": int(p["distinct_decisions_count"] or 0),
                    "origin": (p.get("group_origin_status"),
                               p.get("group_origin_country"))}
    return out


def edges_of(path):
    return {(e["source_decision"], e["resolved_cited_case"]): e
            for e in rows(os.path.join(path, "edges", "citation_edges.csv"))}


def main(r2d, reuse=False):
    outdir = os.path.join(r2d, "audit")
    os.makedirs(outdir, exist_ok=True)
    results = {}
    for regime in REGIMES:
        base = os.path.join(r2d, "sensitivity_%s" % regime)
        if not (reuse and os.path.isdir(base)):
            base = pipeline_for(r2d, regime)
        g = groups_of(base)
        sel_rows = rows(os.path.join(base, "select_out", "selected.csv"))
        sel = Counter(r["kept"] for r in sel_rows)
        # R2 闭环订正（评审指出）：kept 行数 ≠ kept 组数——组数取自 select
        # manifest 的 groups_kept（按组聚合后的 dd≥5 组数），行数单列
        sel_manifest = json.load(open(os.path.join(
            base, "select_out", "manifest.json"), encoding="utf-8"))["stats"]
        ed = edges_of(base)
        fc = Counter(e["foreign_status"] for e in ed.values())
        results[regime] = {
            "base": base, "groups": g, "n_groups": len(g),
            "kept_rows": sel["true"] if "true" in sel else 0,
            "kept_groups": sel_manifest["groups_kept"],
            "edges": len(ed), "foreign": fc.get("FOREIGN", 0),
            "domestic": fc.get("DOMESTIC_CA", 0),
            "undetermined": fc.get("UNDETERMINED", 0)}

    # 两两比较（B、C 各对 A）
    comparison = {}
    for other in ("dedup_position", "counted_only"):
        a, b = results["current"]["groups"], results[other]["groups"]
        common = set(a) & set(b)
        only_a, only_b = set(a) - set(b), set(b) - set(a)
        modal_changed = [k for k in common if a[k]["modal"] != b[k]["modal"]]
        dd_changed = [k for k in common if a[k]["dd"] != b[k]["dd"]]
        origin_changed = [k for k in common if a[k]["origin"] != b[k]["origin"]]
        crossed = [k for k in common if (a[k]["dd"] >= 5) != (b[k]["dd"] >= 5)]
        # 未匹配组（拆分/合并）的单侧 dd 合计——它们不在逐组比较覆盖内
        unmatched_dd = {
            "A_only_dd_sum": sum(a[k]["dd"] for k in only_a),
            "B_only_dd_sum": sum(b[k]["dd"] for k in only_b)}
        comparison[other] = {
            "coverage_note": ("dd/门槛/来源比较只覆盖成员集合完全一致的组；"
                              "未匹配组因拆分/合并无法逐组对应，单列 dd 合计"),
            "groups_common": len(common),
            "groups_only_in_A": len(only_a),
            "groups_only_in_B": len(only_b),
            "unmatched_dd_sums": unmatched_dd,
            "modal_name_changed": len(modal_changed),
            "dd_changed": len(dd_changed),
            "threshold_dd5_crossed": len(crossed),
            "group_origin_changed": len(origin_changed),
            "stable_ratio": round(len(common) / max(1, max(len(a), len(b))), 4),
            "samples_modal_changed": [{"member_keys": ";".join(sorted(k)[:4]),
                                       "A": a[k]["modal"], other: b[k]["modal"]}
                                      for k in sorted(modal_changed)[:20]],
            "samples_threshold_crossed": [{"member_keys": ";".join(sorted(k)[:4]),
                                           "A_dd": a[k]["dd"],
                                           other + "_dd": b[k]["dd"]}
                                          for k in sorted(crossed)[:20]]}
    # 边比较
    for other in ("dedup_position", "counted_only"):
        ea = {(e["source_decision"], e["mention_detail_key"]): e
              for e in rows(os.path.join(results["current"]["base"], "edges",
                                         "citation_edges.csv"))}
        eb = {(e["source_decision"], e["mention_detail_key"]): e
              for e in rows(os.path.join(results[other]["base"], "edges",
                                         "citation_edges.csv"))}
        comparison[other]["edges_only_in_A"] = len(set(ea) - set(eb))
        comparison[other]["edges_only_in_B"] = len(set(eb) - set(ea))
        comparison[other]["foreign_only_in_A"] = sum(
            1 for k in set(ea) - set(eb) if ea[k]["foreign_status"] == "FOREIGN")
        comparison[other]["foreign_only_in_B"] = sum(
            1 for k in set(eb) - set(ea) if eb[k]["foreign_status"] == "FOREIGN")

    summary = {
        "method_note": ("只比较不改生产规则；A=现行口径（生产产物即 A）；"
                        "B=dedup_position；C=counted_only。位置稳定键与弃权规则"
                        "见文件头。"),
        "regimes": {k: {x: v for x, v in d.items() if x != "groups"}
                    for k, d in results.items()},
        "comparison_vs_current": comparison,
    }
    with open(os.path.join(outdir, "case_name_sensitivity_summary.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    gr = []
    for other in ("dedup_position", "counted_only"):
        a, b = results["current"]["groups"], results[other]["groups"]
        for k in sorted(set(a) | set(b))[:0]:
            pass
    # 组级明细（限差異組，控制文件大小）
    for other in ("dedup_position", "counted_only"):
        a, b = results["current"]["groups"], results[other]["groups"]
        for k in sorted(set(a) & set(b)):
            if a[k]["modal"] != b[k]["modal"] or a[k]["dd"] != b[k]["dd"] \
                    or a[k]["origin"] != b[k]["origin"]:
                gr.append({"regime": other,
                           "member_keys": ";".join(sorted(k)[:4]),
                           "A_modal": a[k]["modal"], "B_modal": b[k]["modal"],
                           "A_dd": a[k]["dd"], "B_dd": b[k]["dd"],
                           "A_origin": "/".join(a[k]["origin"]),
                           "B_origin": "/".join(b[k]["origin"])})
    with open(os.path.join(outdir, "case_name_sensitivity_groups.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["regime", "member_keys", "A_modal",
                                          "B_modal", "A_dd", "B_dd",
                                          "A_origin", "B_origin"])
        w.writeheader()
        w.writerows(gr[:5000])
    print(json.dumps(summary["regimes"], ensure_ascii=False, indent=1))
    print(json.dumps(comparison, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main(sys.argv[1], reuse="--reuse" in sys.argv)
