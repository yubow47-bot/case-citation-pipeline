# -*- coding: utf-8 -*-
"""diff_old_new.py — 旧生产产出（data/）vs 新隔离 run（data/run_20260912_stage2/）差分

产出 implementation/diff_report.md。只读，不改任何数据。
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD = os.path.join(ROOT, "data")
NEW = os.path.join(OLD, "run_20260912_final")
OUT = os.path.join(ROOT, "implementation", "diff_report.md")


def stats(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["stats"]


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main():
    L = []
    w = L.append
    w("# 旧 vs 新 差分报告（demo 修复轮，2026-09-12）\n")
    w("- 旧 = `data/`（v1.4 管线产出，金标钉住，未改）")
    w("- 新 = `data/run_20260912_stage2/`（candidates-2.0 + 判决内仲裁 + 键 v2）")
    w("- 金标 `golden_layers.json` 未重写；与本报告并存，--golden 的差分即预期中的 "
      "schema/口径变更，逐项见下。\n")

    # ---- 层级计数对照 ----
    w("## 1. 各层计数对照\n")
    w("| 层 | 旧 | 新 | 说明 |")
    w("|---|---|---|---|")
    old_m = json.load(open(os.path.join(OLD, "extract_out", "manifest.json"), encoding="utf-8"))
    new_m = json.load(open(os.path.join(NEW, "extract_out", "manifest.json"), encoding="utf-8"))
    ok = sum(old_m["merge"]["by_court"][c]["kept_rows"] for c in ("SCC", "ONCA"))
    os_ = sum(old_m["merge"]["by_court"][c]["superseded_rows"] for c in ("SCC", "ONCA"))
    w("| extract kept（旧去重路线） | %d | %s | 新路线 kept/superseded 概念退役：" % (ok, "—"))
    w("| extract candidates | — | %d | 全候选（重叠枚举+边界闸；旧 raw≈%d） |"
      % (new_m["merge"]["candidates"], ok + os_))
    for court in ("SCC", "ONCA"):
        o = stats(os.path.join(OLD, "merge_out", court, "manifest.json"))
        n = stats(os.path.join(NEW, "merge_out", court, "manifest.json"))
        w("| merge %s | %d keys / occ %d | %d keys / occ %d（counted 候选） | 键 v2 + 仲裁 |"
          % (court, o["merge_keys"], o["occurrence_total"],
             n["merge_keys"], n["occurrence_total"]))
    o = stats(os.path.join(OLD, "decide_out", "cross_court", "manifest.json"))
    n = stats(os.path.join(NEW, "decide_out", "cross_court", "manifest.json"))
    w("| decide 跨院组 | %d | %d | |" % (o["groups_out"], n["groups_out"]))
    o = json.load(open(os.path.join(OLD, "select_out", "manifest.json"), encoding="utf-8"))
    n = json.load(open(os.path.join(NEW, "select_out", "manifest.json"), encoding="utf-8"))
    w("| select 组 kept (dd≥5) | %d | %d | 门槛语义未动 |"
      % (o["stats"]["groups_kept"], n["stats"]["groups_kept"]))
    w("")

    # ---- 仲裁去向 ----
    w("## 2. 新路线仲裁去向（逐候选台账合计）\n")
    tot = Counter()
    for court in ("SCC", "ONCA"):
        n = stats(os.path.join(NEW, "merge_out", court, "manifest.json"))
        for k, v in n["arbitration_status_counts"].items():
            tot[k] += v
    w("| 状态 | 候选数 | 说明 |")
    w("|---|---|---|")
    for k in ("counted", "alternative_contained", "alternative_unsupported_reading",
              "span_alternative_undecided", "overlap_undecided",
              "alternative_spanning_mismatch", "alternative_same_key",
              "cross_boundary_invalid", "self_citation_row", "rejected_row"):
        w("| %s | %d | |" % (k, tot[k]))
    w("")
    w("弃权类（不硬猜，0 计数）：span_alternative_undecided %d + overlap_undecided %d。"
      "跨界误解析（D3）作废 %d 条。\n"
      % (tot["span_alternative_undecided"], tot["overlap_undecided"],
         tot["cross_boundary_invalid"]))

    # ---- 键拆分账 ----
    w("## 3. D4/D5 键拆分账\n")
    for court in ("SCC", "ONCA"):
        n = stats(os.path.join(NEW, "merge_out", court, "manifest.json"))
        w("- %s：旧键 %d 个，其中 %d 个拆成多个新键（系列括注/罗马页身份）；"
          "映射见 merge_out/%s/key_mapping.csv"
          % (court, n["old_keys"], n["old_keys_split_into_multiple"], court))
    w("")

    # ---- 专案核查 ----
    w("## 4. 专案核查（D1–D5 代表案例在两版的落点）\n")
    checks = []

    def find_in_new(court, substr):
        hits = []
        path = os.path.join(NEW, "merge_out", court, "merged.csv")
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if substr in r["canonical_string"] or substr in r["merge_key"]:
                    hits.append(r)
        return hits

    # Almrei：误解析 2011 ONCA, 2011 不再在表
    bad = find_in_new("ONCA", "2011||onca||2011")
    good = [r for r in find_in_new("ONCA", "2011||onca||779")]
    checks.append(("D3 Almrei：误解析页=2011 键不在新表", len(bad) == 0,
                   "命中 %d 行" % len(bad)))
    checks.append(("D3 Almrei：2011 ONCA 779 在新表", len(good) >= 1,
                   "occ=%s dd=%s" % (good[0]["occurrence_count"],
                                     good[0]["distinct_decisions_count"]) if good else "无"))

    # Kvello：2009 SCC 51
    kv = [r for r in find_in_new("SCC", "2009||scc||51")]
    checks.append(("Kvello：2009 SCC 51 单键存在（不按卷读法重计）", len(kv) == 1,
                   "keys=%d occ=%s" % (len(kv), kv[0]["occurrence_count"] if kv else "-")))

    # D4：D.L.R. 系列拆键
    dlr2 = [r for r in find_in_new("SCC", "|2d|") ]
    dlr3 = [r for r in find_in_new("SCC", "|3d|")]
    checks.append(("D4：键含系列槽 2d/3d 的组存在（拆分生效）",
                   len(dlr2) >= 1 and len(dlr3) >= 1,
                   "|2d| %d 组, |3d| %d 组" % (len(dlr2), len(dlr3))))

    # D5：罗马页键
    ro = [r for r in find_in_new("SCC", "ro:")]
    checks.append(("D5：罗马页键（ro:*）存在", len(ro) >= 1, "%d 组" % len(ro)))

    # 双计数抽查：occurrence >= dd 恒成立 + counted 行守恒
    ok_cons = True
    for court in ("SCC", "ONCA"):
        n = stats(os.path.join(NEW, "merge_out", court, "manifest.json"))
        menc = Counter()
        with open(os.path.join(NEW, "merge_out", court, "mentions_candidates.csv"),
                  encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r["arbitration_status"] == "counted":
                    menc[r["merge_key"]] += 1
        with open(os.path.join(NEW, "merge_out", court, "merged.csv"),
                  encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if menc[r["merge_key"]] != int(r["occurrence_count"]):
                    ok_cons = False
                    break
    checks.append(("防双计数：每键 counted 候选数 == occurrence_count（两院全表）",
                   ok_cons, "逐行核对通过" if ok_cons else "不一致！"))

    # 旧表里有、新表里消失的高频键（抽查 dd≥50 的旧组）
    w("\n| 核查项 | 结果 | 明细 |")
    w("|---|---|---|")
    for name, ok_, detail in checks:
        w("| %s | %s | %s |" % (name, "PASS" if ok_ else "**FAIL**", detail))
    w("")

    # ---- top 榜对照 ----
    w("## 5. dd 榜首对照（金标 top25 旧 vs 新 top15）\n")
    groups = defaultdict(list)
    with open(os.path.join(NEW, "decide_out", "cross_court", "decided.csv"),
              encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            groups[r["merged_group_id"]].append(r)
    top = sorted(groups.values(),
                 key=lambda ms: (-int(ms[0]["distinct_decisions_count"]),
                                 ms[0]["merged_group_id"]))[:15]
    w("| dd | occ | 案名 |")
    w("|---|---|---|")
    for ms in top:
        p = next((m for m in ms if m["is_primary"] == "true"), ms[0])
        w("| %s | %s | %s |" % (p["distinct_decisions_count"], p["occurrence_count"],
                                p["case_name_modal"]))
    w("\n（旧金标 top25 见 pipeline/tests/golden_layers.json；两版组数不同，逐组对照"
      "以 key_mapping.csv 为准。）")

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))
    print("written", OUT)
    for name, ok_, detail in checks:
        print(("PASS " if ok_ else "FAIL ") + name + " :: " + detail)


if __name__ == "__main__":
    main()
