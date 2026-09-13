# -*- coding: utf-8 -*-
"""build_demo_examples.py — 从真实运行产物生成演示样例文档（阶段 4）

只读 run 产物，产出 implementation/demo_examples.md。全部样例为真数据；
合成数据只存在于测试套件（test_candidates.py）且明确标注。
"""
import csv
import os
import subprocess
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RUN = os.path.join(ROOT, "data", "run_20260912_r2c")
OUT = os.path.join(HERE, "demo_examples.md")


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main():
    dec = rows(os.path.join(RUN, "decide_out", "cross_court", "decided.csv"))
    edges = rows(os.path.join(RUN, "edges", "citation_edges.csv"))
    foreign = rows(os.path.join(RUN, "edges", "foreign_edges.csv"))
    groups = defaultdict(list)
    for r in dec:
        groups[r["merged_group_id"]].append(r)

    def primary(gid):
        ms = groups[gid]
        return next((m for m in ms if m["is_primary"] == "true"), ms[0])

    by_gid = defaultdict(list)
    for e in edges:
        by_gid[e["resolved_cited_case"]].append(e)

    def top_citers(gid, n=3):
        es = sorted(by_gid[gid], key=lambda e: -int(e["mention_count"]))[:n]
        return es

    L = []
    w = L.append

    w("# 演示样例（真实运行产物，data/run_20260912_r2c）\n")
    w("全部来自本轮全量运行的真实语料数据；测试用合成数据只在 pipeline/tests/ 并明确标注。\n")

    # ---- 1 外国案 ----
    w("## 1. 外国来源案件 + 引用它的判决\n")
    th = [e for e in foreign if e["case_name_modal"] == "Thorner v. Major"]
    gid = th[0]["resolved_cited_case"]
    p = primary(gid)
    w("**Thorner v. Major** [2009] UKHL 18（英国上议院）——组 `%s`" % gid)
    w("- foreign_status=FOREIGN，origin_country=GB，basis=`court_scope_rule`，"
      "evidence=`scope:UKHL`（decisions/court_or_reporter_scope.csv：UKHL 中立引用 "
      "2001 年起由法院签发；本例 2009 在窗内）")
    w("- 同组平行汇编（身份由裁定层合并）：%s"
      % ", ".join("`%s`" % k for k in sorted({m["merge_key"] for m in groups[gid]})))
    w("- dd=%s，occurrence=%s；引用它的判决（按提及次数前 3）：" % (p["distinct_decisions_count"], p["occurrence_count"]))
    for e in top_citers(gid):
        w("  - `%s`：提及 %s 次（mention_detail_key 可回连逐候选台账）"
          % (e["source_decision"], e["mention_count"]))
    w("")

    # ---- 2 国内案 ----
    gid2 = "XC-G032199"          # R. v. Lacasse dd 396
    p2 = primary(gid2)
    w("## 2. 国内来源案件（DOMESTIC_CA）\n")
    w("**%s**（组 `%s`）：foreign_status=DOMESTIC_CA，origin_country=CA，basis=`%s`，"
      "evidence=`%s`；dd=%s" % (p2["case_name_modal"], gid2, p2["origin_basis"],
                                p2["origin_evidence_id"], p2["distinct_decisions_count"]))
    w("- 来源地证据：组内中立引用键 `%s` 落 SCC 排他规则（加拿大最高法院只审理"
      "源自加拿大法院体系的案件）"
      % next((k for k in (m["merge_key"] for m in groups[gid2]) if "scc" in k), ""))
    for e in top_citers(gid2, 2):
        w("  - 引用方 `%s`：提及 %s 次" % (e["source_decision"], e["mention_count"]))
    w("")

    # ---- 3 未知案 ----
    gid3 = "XC-G009597"          # R. v. W.(D.) dd 693
    p3 = primary(gid3)
    w("## 3. 显式未知（UNKNOWN ≠ 错误，也 ≠ 外国）\n")
    w("**%s**（组 `%s`，dd=%s）：foreign_status=**UNDETERMINED**。该案 1991 年判决，"
      "引用它的判决只有 S.C.R./C.C.C. 汇编式引证（无中立代码），不在 case_origin 表、"
      "也不适用任何 scope 规则——按约束四不填默认值，显式留未知。"
      % (p3["case_name_modal"], gid3, p3["distinct_decisions_count"]))
    w("")

    # ---- 4 坏解析修正轨迹（Almrei）----
    w("## 4. 已知坏解析的完整修正轨迹（D1/D2/D3）\n")
    bad_hits = []
    good_hits = []
    for court in ("SCC", "ONCA"):
        path = os.path.join(RUN, "merge_out", court, "mentions_candidates.csv")
        for m in rows(path):
            if m["raw_string"] == "2011 ONCA, 2011":
                bad_hits.append((court, m))
            elif (m["raw_string"] == "2011 ONCA 779"
                  and m["corpus_row_index"] == "19881"):
                good_hits.append((court, m))
    if bad_hits:
        court0, m0 = bad_hits[0]
        w("引证文本 `…Almrei v. Canada (Attorney General) 2011 ONCA, 2011 ONCA 779…`"
          "（引用方判决：%s，语料行 %s）。旧管线（非重叠扫描 + 最长跨度去重）的"
          "winner 是 `2011 ONCA, 2011`（把下一个引证的年份误当自己的页码），"
          "曾以 dd=1、kept=false 坐进最终表。新路线的仲裁台账："
          % (m0["source_decision_citation"], m0["corpus_row_index"]))
        for c, m in bad_hits:
            w("  - `%s`：raw=%r shape=%s → **%s**（D3 旗 cross_boundary_year_page；"
              "让位于 %s）"
              % (m["candidate_id"], m["raw_string"], m["shape_name"],
                 m["arbitration_status"], m["superseded_by_candidate"]))
        for c, m in good_hits:
            if m["arbitration_status"] == "counted":
                w("  - `%s`：raw=%r shape=%s → **counted**（真引证，键 `2011||onca||779`"
                  "进最终表；同跨度的卷读法 alternative_unsupported_reading）"
                  % (m["candidate_id"], m["raw_string"], m["shape_name"]))
                w("  - 复现命令：`python pipeline/traceback.py --run-dir "
                  "data/run_20260912_r2c --candidate-id %s`" % m["candidate_id"])
    else:
        w("（未在台账找到 Almrei 坏解析样例——检查 run 产物）")
    w("")

    # ---- 5 追溯方法 ----
    w("## 5. 从最终结果回到原文与判断依据\n")
    w("```")
    w("# 粗搜（按案名/原文串找 candidate_id）")
    w("python pipeline/traceback.py --run-dir data/run_20260912_r2c --search Thorner")
    w("# 深查：回显分类证据 + 仲裁状态 + 原文窗口（<<…>> 标出候选跨度）")
    w("python pipeline/traceback.py --run-dir data/run_20260912_r2c \\")
    w("    --candidate-id <台账里的 candidate_id>")
    w("# 台账：merge_out/{SCC,ONCA}/mentions_candidates.csv（逐候选仲裁状态）")
    w("# 边：edges/citation_edges.csv；mention_detail_key 回连上表")
    w("```")

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))
    print("written", OUT)
    print("thorner citers:", [(e["source_decision"], e["mention_count"])
                               for e in top_citers(gid)])
    print("almrei bad:", [(m["candidate_id"], m["arbitration_status"])
                          for c, m in bad_hits])


if __name__ == "__main__":
    main()
