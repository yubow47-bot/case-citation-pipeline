# -*- coding: utf-8 -*-
"""R4 Stage 3：案件级人工核验批次的**队列构建**（只读 r4a 产出 + 决策表）。

队列构成（D4，上限 50 个引证身份 / 200 次查询，~4 查询/案）：
  A. 30 个：法院识别后仍 UNDETERMINED、含**混合汇编**键、按 dd 降序（每案取 dd 最大组）；
  B. 10 个：带 (P.C.) 标注、且**不在** case_origin.csv 已覆盖的 CanLII ukpc 库内
     （case_origin.csv 的 normalized_key 均来自 ukpc 库 → 用「已覆盖键」排除）；
  C. 10 个：边界案——H.L. 标注且 report 年在 1922–23 附近（H.L. 名 称 沿革边界），
     与 HCA/Nauru（Aust. H.C. 族标注）。
  排重：A/B/C 交集只入一次（优先级 B > C > A）。
输出：audit/findings/r4_case_batch_queue.json（含每案的引证、键、组、dd、标注原文）。
"""

import csv
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from normalize import nk                                        # noqa: E402

RUN = os.path.join(ROOT, "data", "run_20260914_r4a")
OUT = os.path.join(ROOT, "audit", "findings", "r4_case_batch_queue.json")

MIXED = {"ac", "appcas", "aller", "wlr", "kb", "qb", "ch", "chd", "qbd", "er",
         "lr.hl", "lr.qb", "lr.ch", "chapp", "lr.pc", "us", "clr", "nzlr",
         "alr", "sct", "led", "f", "f2d", "f3d"}


def main():
    # 已覆盖键（case_origin.csv 的 normalized_key = CanLII ukpc 库）
    covered = set()
    p = os.path.join(ROOT, "decisions", "case_origin.csv")
    for r in csv.DictReader(open(p, encoding="utf-8", newline="")):
        k = (r.get("normalized_key") or "").strip()
        if k:
            covered.add(k)

    # 逐组：找混合汇编键、组来源地、dd、标注
    groups = defaultdict(list)
    with open(os.path.join(RUN, "decide_out", "cross_court", "decided.csv"),
              encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            groups[r["merged_group_id"]].append(r)

    cases = {}
    for g, rs in groups.items():
        dd = int(rs[0].get("distinct_decisions_count") or 0)
        origin = rs[0].get("group_origin_status") or ""
        name = rs[0].get("case_name_modal") or ""
        for m in rs:
            p = m["merge_key"].split("|")
            if len(p) < 5 or p[2] not in MIXED:
                continue
            abbr = p[2]
            yr = m.get("year_printed") or p[0] or ""
            des = (m.get("court_designation_status") or "").strip()
            dc = (m.get("observed_deciding_court") or "").strip()
            cite = m.get("canonical_string") or ""
            cite_key = nk(cite)
            entry = cases.setdefault(
                cite_key, {"citation": cite, "normalized_key": cite_key,
                           "group": g, "dd": dd, "name": name,
                           "abbr": abbr, "year": yr,
                           "designation_status": des,
                           "designation_court": dc,
                           "covered_by_case_origin": cite_key in covered})
            entry["dd"] = max(entry["dd"], dd)

    undet = [c for c in cases.values()
             if c["dd"] > 0 and not c["covered_by_case_origin"]]
    a_queue = sorted([c for c in undet if c["abbr"] in MIXED],
                     key=lambda c: (-c["dd"], c["citation"]))[:30]
    pc_queue = [c for c in undet
                if c["designation_court"] == "Judicial Committee of the Privy Council"
                and c not in a_queue][:10]
    hl_boundary = [c for c in undet
                   if c["designation_court"] == "House of Lords"
                   and c["year"] and c["year"].isdigit()
                   and 1920 <= int(c["year"]) <= 1925
                   and c not in a_queue and c not in pc_queue][:5]
    hca_queue = [c for c in undet
                 if c["designation_court"] == "High Court of Australia"
                 and c not in a_queue and c not in pc_queue
                 and c not in hl_boundary][:5]

    queue = {
        "run": "data/run_20260914_r4a",
        "cap": {"max_identities": 50, "max_queries": 200,
                "max_queries_per_case": 4},
        "composition": {
            "A_still_undetermined_mixed_reporter_dd30": [
                dict(c, slot="A") for c in a_queue],
            "B_pc_outside_ukpc_coverage_10": [
                dict(c, slot="B") for c in pc_queue],
            "C_boundary_hl_1922_23_and_hca_nauru_10": [
                dict(c, slot="C") for c in (hl_boundary + hca_queue)],
        },
        "counts": {"A": len(a_queue), "B": len(pc_queue),
                   "C_hl": len(hl_boundary), "C_hca": len(hca_queue)},
    }
    total = len(a_queue) + len(pc_queue) + len(hl_boundary) + len(hca_queue)
    queue["total"] = total
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=1)
    print("queue total:", total, "(A %d / B %d / C_hl %d / C_hca %d)"
          % (len(a_queue), len(pc_queue), len(hl_boundary), len(hca_queue)))
    print("written:", os.path.relpath(OUT, ROOT))
    for slot in ("A_still_undetermined_mixed_reporter_dd30",
                 "B_pc_outside_ukpc_coverage_10",
                 "C_boundary_hl_1922_23_and_hca_nauru_10"):
        for c in queue["composition"][slot]:
            print("  [%s] %-34s dd=%-4d %s %s  des=%s" % (
                slot[0], c["citation"][:34], c["dd"], c["abbr"],
                c["year"], c["designation_court"] or "-"))


if __name__ == "__main__":
    main()
