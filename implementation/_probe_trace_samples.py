# -*- coding: utf-8 -*-
"""临时：为 Stage 4 的人工追溯挑样本——新增 exclusive_reporter_scope 判定里
按缩写/规模分层各取几例，并打印组内成员与案名，供逐条对照原文。"""
import csv
import json
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "data", "run_20260913_r3a")

changed = list(csv.DictReader(open(os.path.join(
    ROOT, "data", "coverage_out", "r3_blast_origin_changes.csv"),
    encoding="utf-8", newline="")))
rs = [c for c in changed if c["after"].endswith("exclusive_reporter_scope")]
print("新增 exclusive_reporter_scope 的成员行：%d" % len(rs))
by_abbr = Counter(c["merge_key"].split("|")[2] for c in rs)
print("按缩写：", dict(by_abbr.most_common()))

# 读新 run 的成员与组
mem, grp = {}, defaultdict(list)
with open(os.path.join(A, "decide_out", "cross_court", "decided.csv"),
          encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        mem[(r["court"], r["merge_key"])] = r
        grp[r["merged_group_id"]].append(r)

NEWDOM = [c for c in changed
          if c["before"].startswith("/UNDETERMINED")
          and c["after"].startswith("CA/")]
print("UNDETERMINED→CA 的成员行：%d" % len(NEWDOM))

# 分层取样：每个缩写取 1 例 dd 最大 + 1 例 dd=1
pick = []
for ab in sorted(by_abbr):
    cand = [c for c in rs if c["merge_key"].split("|")[2] == ab]
    cand.sort(key=lambda c: -int(mem[(c["court"], c["merge_key"])]
                                 ["distinct_decisions_count"]))
    pick.extend(cand[:2])
print("\n样本（%d）：" % len(pick))
for c in pick:
    k = (c["court"], c["merge_key"])
    r = mem[k]
    g = r["merged_group_id"]
    members = grp[g]
    print("-" * 92)
    print("key=%s  court=%s  group=%s  dd=%s  occ=%s"
          % (c["merge_key"], c["court"], g, r["distinct_decisions_count"],
             r["occurrence_count"]))
    print("  canonical=%r  案名=%r  basis: %s → %s  exclusivity=%s"
          % (r["canonical_string"], r["case_name_modal"], c["before"], c["after"],
             r["member_origin_exclusivity"]))
    print("  组内成员：")
    for m in members:
        print("     %-34s kind=%-9s basis=%-24s %s"
              % (m["merge_key"], m["citation_kind"], m["identity_basis"],
                 (m["case_name_modal"] or "")[:40]))
