# -*- coding: utf-8 -*-
"""两次 run 的差分验收（沿用 #85 教训：同时查「既有键变大」与「全新键出现」）。
用法：python audit/diff_runs.py OLD_RUN NEW_RUN"""
import csv, os, sys, collections
csv.field_size_limit(10**9)
old, new = sys.argv[1], sys.argv[2]

def rows(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

# 1 候选层：旧候选必须是新候选的子集（同 candidate_id、同关键字段）
o = {r["candidate_id"]: r for r in rows(os.path.join(old, "extract_out", "candidates.csv"))}
n = {r["candidate_id"]: r for r in rows(os.path.join(new, "extract_out", "candidates.csv"))}
added = [r for k, r in n.items() if k not in o]
lost = [k for k in o if k not in n]
changed = [k for k in o if k in n and (o[k]["raw_string"], o[k]["parse_signature"]) != (n[k]["raw_string"], n[k]["parse_signature"])]
print("候选：旧 %d 新 %d | 新增 %d 丢失 %d 改变 %d" % (len(o), len(n), len(added), len(lost), len(changed)))
print("新增按形状：", dict(collections.Counter(r["shape_name"] for r in added)))
print("新增按法院：", dict(collections.Counter(r["candidate_id"].split(":")[0] for r in added)))

# 2 归并层：既有键变化 / 全新键
for court in sorted(os.listdir(os.path.join(new, "merge_out"))):
    po = os.path.join(old, "merge_out", court, "merged.csv")
    pn = os.path.join(new, "merge_out", court, "merged.csv")
    mo = {r["merge_key"]: r for r in rows(po)}
    mn = {r["merge_key"]: r for r in rows(pn)}
    grew = [k for k in mo if k in mn and (mo[k]["occurrence_count"], mo[k]["distinct_decisions_count"]) != (mn[k]["occurrence_count"], mn[k]["distinct_decisions_count"])]
    gone = [k for k in mo if k not in mn]
    fresh = [k for k in mn if k not in mo]
    kinds = collections.Counter(mn[k]["citation_kind"] for k in fresh)
    print("%s 归并键：旧 %d 新 %d | 既有键计数变化 %d | 消失 %d | 全新键 %d %s" % (court, len(mo), len(mn), len(grew), len(gone), len(fresh), dict(kinds)))
    for k in grew[:5]:
        print("   变化", k, (mo[k]["occurrence_count"], mo[k]["distinct_decisions_count"]), "->", (mn[k]["occurrence_count"], mn[k]["distinct_decisions_count"]))
    for k in fresh[:6]:
        print("   新键", k, mn[k]["canonical_string"], mn[k]["citation_kind"], mn[k]["occurrence_count"])

# 3 裁定/边
for rel in (("decide_out", "cross_court", "decided.csv"), ("edges", "edges.csv")):
    po, pn = os.path.join(old, *rel), os.path.join(new, *rel)
    if os.path.exists(po) and os.path.exists(pn):
        print(rel[-1], "行数 旧 %d 新 %d" % (len(rows(po)), len(rows(pn))))
