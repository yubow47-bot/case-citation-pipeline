# -*- coding: utf-8 -*-
"""临时：诊断 r3d 的**残余**拆分——(a) 连续编卷键的 year_printed 填充率；
(b) 指定案名在两轮里的分组构成（判断残余是「损失」还是「纠正」）。"""
import csv
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from normalize import nk                                        # noqa: E402
from decide import load_reporter_origin, row_year               # noqa: E402

CONT = set()
for k, rows in load_reporter_origin().items():
    vs = {(r.get("volume_system") or "").strip() for r in rows}
    vs.discard("")
    if vs == {"continuous"}:
        CONT.add(k)
print("连续编卷缩写:", ",".join(sorted(CONT)))

# (a) merged.csv 里连续编卷键的 year_printed 填充率
for court in ("SCC", "ONCA"):
    p = os.path.join(ROOT, "data", "run_20260913_r3d", "merge_out", court,
                     "merged.csv")
    tot = with_yp = 0
    ex = []
    for r in csv.DictReader(open(p, encoding="utf-8", newline="")):
        k = r["merge_key"].split("|")
        if len(k) >= 5 and k[2] in CONT and not k[0]:
            tot += 1
            if (r.get("year_printed") or "").strip():
                with_yp += 1
            elif len(ex) < 5:
                ex.append((r["merge_key"], r["canonical_string"]))
    print("%s：连续编卷·年槽为空的键 %d，其中 year_printed 非空 %d（%.1f%%）"
          % (court, tot, with_yp, 100.0 * with_yp / max(tot, 1)))
    for e in ex:
        print("    空例：%s  %r" % e)

# (b) 指定案名在两轮的分组构成
NAMES = ["rvsawyer", "rvcourt", "rvosolin", "libmanvthequeen",
         "rvtennantandnaccarato", "rvrarru", "rvwd"]


def groups_of(run_dir, want):
    out = defaultdict(list)
    with open(os.path.join(run_dir, "decide_out", "cross_court", "decided.csv"),
              encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            nm = nk(r.get("case_name_modal") or "")
            if nm in want:
                out[r["merged_group_id"]].append(r)
    return {g: rs for g, rs in out.items()}


for nm in NAMES:
    print("\n=== %s ===" % nm)
    for tag, d in (("r2i", "data/run_20260913_r2i"),
                   ("r3d", "data/run_20260913_r3d")):
        gs = groups_of(os.path.join(ROOT, d), {nm})
        print("  %s：%d 组" % (tag, len(gs)))
        for g, rs in sorted(gs.items(), key=lambda kv: -int(kv[1][0]["distinct_decisions_count"])):
            dd = rs[0]["distinct_decisions_count"]
            keys = sorted({(m["court"], m["merge_key"]) for m in rs})
            yp = sorted({(m.get("year_printed") or "-") for m in rs})
            print("     dd=%-4s keys=%d yp=%s split=%r  %s"
                  % (dd, len(keys), yp[:6], rs[0].get("split_reason") or "",
                     " ".join("%s|%s" % k for k in keys[:6])))
