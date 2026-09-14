# -*- coding: utf-8 -*-
"""临时：追查 dd 下降的键——文档去哪了（计划要求 0 未解释）。"""
import csv
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "data", "run_20260913_r3a")
B = os.path.join(ROOT, "data", "run_20260913_r2i")


def load(d):
    rows, grp, dids = {}, defaultdict(list), defaultdict(set)
    for c in ("SCC", "ONCA"):
        p = os.path.join(d, "decide_out", c, "decided.csv")
        for r in csv.DictReader(open(p, encoding="utf-8", newline="")):
            rows[(c, r["merge_key"])] = r
            grp[(c, r["merged_group_id"])].append(r["merge_key"])
        for r in csv.DictReader(open(os.path.join(d, "decide_out", c,
                                                  "decision_ids.csv"),
                                     encoding="utf-8", newline="")):
            k = r.get("row_key") or ""
            court, _, mk = k.partition("|")
            dids[(court, mk)].add(r["source_decision_citation"])
    return rows, grp, dids


b_rows, b_grp, b_did = load(B)
a_rows, a_grp, a_did = load(A)

CASES = [("ONCA", "1998|160|dlr|4d|193"), ("ONCA", "1993|86|ccc|3d|481"),
         ("ONCA", "1985|2|scr||350"), ("ONCA", "1995|2|scr||967")]
for k in CASES:
    print("=" * 90)
    print("KEY", k, " dd before=%s after=%s"
          % (b_rows.get(k, {}).get("distinct_decisions_count"),
             a_rows.get(k, {}).get("distinct_decisions_count")))
    for tag, rows, grp, did in (("before", b_rows, b_grp, b_did),
                                ("after", a_rows, a_grp, a_did)):
        r = rows.get(k)
        if not r:
            print("  %s: key ABSENT" % tag)
            continue
        gid = r["merged_group_id"]
        gk = (k[0], gid)
        members = sorted(set(grp[gk]))
        lost = b_did.get(k, set()) - a_did.get(k, set())
        gained = a_did.get(k, set()) - b_did.get(k, set())
        print("  %s: dd=%s occ=%s group=%s members=%d %s"
              % (tag, r["distinct_decisions_count"], r["occurrence_count"], gid,
                 len(members), members[:6]))
        print("          group dd=%s  member rows with year: %s"
              % (r["distinct_decisions_count"],
                 [m.split("|")[0] or "(empty)" for m in members[:8]]))
        if lost:
            print("          docs lost %d e.g. %s" % (len(lost), sorted(lost)[:4]))
        if gained:
            print("          docs gained %d" % len(gained))
