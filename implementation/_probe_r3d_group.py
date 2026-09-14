# -*- coding: utf-8 -*-
"""临时：给定 (run, 精确键) → 打印该键所在组的全部成员（键/案名/年份/拆分原因）。
用于判断 r3d 残余拆分是哪一步造成的。"""
import csv
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = [
    ("r2i", "1993|86|ccc|3d|481", "1993|86|ccc|3d|481"),
    ("r3d", "|86|ccc|3d|481", "|86|ccc|3d|481"),
    ("r2i", "2001|155|ccc|3d|97", "2001|155|ccc|3d|97"),
    ("r3d", "|155|ccc|3d|97", "|155|ccc|3d|97"),
    ("r2i", "1995|99|ccc|3d|237", "1995|99|ccc|3d|237"),
    ("r3d", "|99|ccc|3d|237", "|99|ccc|3d|237"),
]


def group_of(tag, key):
    run = {"r2i": "data/run_20260913_r2i", "r3d": "data/run_20260913_r3d"}[tag]
    d = os.path.join(ROOT, run, "decide_out", "cross_court", "decided.csv")
    rows = list(csv.DictReader(open(d, encoding="utf-8", newline="")))
    hit = [r for r in rows if r["merge_key"] == key]
    if not hit:
        return None, []
    gid = hit[0]["merged_group_id"]
    return hit[0], [r for r in rows if r["merged_group_id"] == gid]


for run, key, _ in CASES:
    r0, grp = group_of(run, key)
    print("=" * 96)
    if r0 is None:
        print("%s  %-22s  **键不存在**" % (run, key))
        continue
    print("%s  %-22s  dd=%s occ=%s gid=%s name=%r yp=%r split=%r"
          % (run, key, r0["distinct_decisions_count"], r0["occurrence_count"],
             r0["merged_group_id"], (r0.get("case_name_modal") or "")[:30],
             r0.get("year_printed") or "-", r0.get("split_reason") or ""))
    print("   组内成员（%d 行 / %d 键）："
          % (len(grp), len({(m["court"], m["merge_key"]) for m in grp})))
    for m in sorted(grp, key=lambda x: (x["court"], x["merge_key"])):
        print("      %-5s %-24s name=%-30r yp=%r basis=%s"
              % (m["court"], m["merge_key"], (m.get("case_name_modal") or "")[:30],
                 m.get("year_printed") or "-", m.get("identity_basis") or ""))
