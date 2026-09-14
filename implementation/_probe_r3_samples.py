# -*- coding: utf-8 -*-
"""临时：为 Stage 4 人工追溯抽取样本——每个新写缩写取 1 个 dd≥5 的新判定组。"""
import csv
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "data", "run_20260913_r3c")
NEW = ("dlr", "ccc", "or", "wwr", "rjq", "ar", "altalr", "rfl", "nsr", "nbr",
       "manr", "saskr", "nr", "excr")
grp = defaultdict(list)
with open(os.path.join(A, "decide_out", "cross_court", "decided.csv"),
          encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))
for r in rows:
    grp[r["merged_group_id"]].append(r)

picked = {}
for r in rows:
    if (r.get("member_origin_basis") or "") != "exclusive_reporter_scope":
        continue
    ab = r["merge_key"].split("|")[2]
    if ab not in NEW or ab in picked:
        continue
    if int(r["distinct_decisions_count"] or 0) < 5:
        continue
    picked[ab] = r
for ab in NEW:
    r = picked.get(ab)
    if not r:
        print("### %-8s 无可追溯样本（dd>=5）" % ab)
        continue
    print("### %-8s dd=%-4s occ=%-4s  %s" % (
        ab, r["distinct_decisions_count"], r["occurrence_count"],
        r["canonical_string"]))
    print("      案名=%r  来源地=%s/%s（细分=%r）" % (
        r["case_name_modal"][:60], r["member_origin_country"],
        r["member_origin_exclusivity"], r["member_origin_subdivision"]))
    print("      组内成员：%s" % " | ".join(
        m["merge_key"] for m in grp[r["merged_group_id"]][:5]))
