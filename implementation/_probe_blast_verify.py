# -*- coding: utf-8 -*-
"""临时：把 blast 的 group_only 桶追到根（是否都由同组某个 reporter_scope 成员引起），
并核对 occurrence/dd 守恒（身份修复不得虚增计数）。"""
import csv
import json
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "data", "run_20260913_r3a")
B = os.path.join(ROOT, "data", "run_20260913_r2i")

# ---- 1. merge manifest 计数对照 ----
for tag, d in (("r2i", B), ("r3a", A)):
    ms = {}
    for c in ("SCC", "ONCA"):
        m = json.load(open(os.path.join(d, "merge_out", c, "manifest.json"),
                           encoding="utf-8"))
        ms[c] = {k: m["stats"].get(k) for k in
                 ("occurrence_total", "merge_keys", "decision_id_rows",
                  "groups_with_internal_disagreement",
                  "reporter_identity_year_zeroed_rows",
                  "reporter_identity_year_filled_rows",
                  "reporter_identity_year_fill_families",
                  "reporter_identity_year_fill_families_abstained")}
    print("### %s merge:" % tag)
    for c, v in ms.items():
        print("   %-5s %s" % (c, v))

# ---- 2. 组内：哪些组有 reporter_scope 成员；group_only 行能否归因 ----
members = {}
gsig = defaultdict(list)
with open(os.path.join(A, "decide_out", "cross_court", "decided.csv"),
          encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        members[(r["court"], r["merge_key"])] = r
        gsig[r["merged_group_id"]].append((r["court"], r["merge_key"]))
grp_has_rs = {}
for g, rows in gsig.items():
    grp_has_rs[g] = any(
        (members[k].get("member_origin_basis") or "") == "exclusive_reporter_scope"
        for k in rows)
print("\n### 组内是否有 exclusive_reporter_scope 成员：有 %d 组 / 共 %d 组"
      % (sum(1 for v in grp_has_rs.values() if v), len(grp_has_rs)))

# 复算 blast 的 group_only 桶：成员行自身 origin 字段未变但组结论变了
blast = json.load(open(os.path.join(ROOT, "data", "coverage_out", "r3_blast.json"),
                       encoding="utf-8"))
print("blast attribution:", blast["members"]["attribution"])

b_members = {}
with open(os.path.join(B, "decide_out", "cross_court", "decided.csv"),
          encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        b_members[(r["court"], r["merge_key"])] = r
group_only, unexplained = [], []
for k in sorted(set(b_members) & set(members)):
    bv, av = b_members[k], members[k]
    same_origin = ((bv.get("member_origin_country"), bv.get("member_origin_status"),
                    bv.get("member_origin_basis")) ==
                   (av.get("member_origin_country"), av.get("member_origin_status"),
                    av.get("member_origin_basis")))
    g_changed = (bv.get("group_foreign_status") != av.get("group_foreign_status"))
    if g_changed and same_origin:
        gid = av["merged_group_id"]
        if grp_has_rs.get(gid):
            group_only.append(k)
        else:
            unexplained.append((k, bv.get("group_foreign_status"),
                                av.get("group_foreign_status")))
print("组结论变而自身证据未变的行：%d；其中同组有 reporter_scope 成员 = %d；**未解释 %d**"
      % (len(group_only) + len(unexplained), len(group_only), len(unexplained)))
for u in unexplained[:10]:
    print("   UNEXPLAINED:", u)

# ---- 3. dd 变化里被身份修复影响的 ----
print("\n### dd 变化样例（前 5，看是否为身份合并所致）")
sel_a, sel_b = {}, {}
for tag, d, out in (("b", B, sel_b), ("a", A, sel_a)):
    for r in csv.DictReader(open(os.path.join(d, "select_out", "selected.csv"),
                                 encoding="utf-8", newline="")):
        out[(r["court"], r["merge_key"])] = int(r["distinct_decisions_count"] or 0)
diff = [(k, sel_b[k], sel_a[k]) for k in set(sel_a) & set(sel_b)
        if sel_a[k] != sel_b[k]]
print("   dd 变化行数 %d（升 %d / 降 %d）" % (
    len(diff), sum(1 for _, x, y in diff if y > x),
    sum(1 for _, x, y in diff if y < x)))
for k, x, y in sorted(diff, key=lambda t: -abs(t[2] - t[1]))[:5]:
    print("   %-40s dd %d -> %d" % (k[0] + "|" + k[1], x, y))
