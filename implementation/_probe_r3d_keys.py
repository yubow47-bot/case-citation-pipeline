# -*- coding: utf-8 -*-
"""临时：逐键对照 r2i 与 r3d——看残余拆分到底是哪一步造成的。
用法：python implementation/_probe_r3d_keys.py
"""
import csv
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = {"r2i": "data/run_20260913_r2i", "r3d": "data/run_20260913_r3d"}
KEYS = ["ccc|3d|481", "ccc|3d|97", "ccc|3d|79", "ccc|3d|237", "scr||595",
        "scr||344", "scr||178"]


def collect(run, pat):
    rows = defaultdict(list)
    d = os.path.join(ROOT, run, "decide_out", "cross_court", "decided.csv")
    with open(d, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if pat in r["merge_key"]:
                rows[r["merge_key"]].append(r)
    did = defaultdict(set)
    for court in ("SCC", "ONCA"):
        p = os.path.join(ROOT, run, "decide_out", court, "decision_ids.csv")
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(open(p, encoding="utf-8", newline="")):
            k = r["row_key"] or ""
            c, _, mk = k.partition("|")
            if pat in mk:
                did[(c, mk)].add(r["source_decision_citation"])
    return rows, did


for pat in ("ccc|3d|481", "ccc|3d|97", "ccc|3d|237"):
    print("=" * 100)
    print("PATTERN:", pat)
    for tag, run in RUNS.items():
        rows, did = collect(run, pat)
        print("  --- %s ---" % tag)
        for k, rs in sorted(rows.items()):
            r0 = rs[0]
            print("   %-24s dd=%-4s occ=%-4s gid=%-12s name=%r yp=%r split=%r"
                  % (k, r0["distinct_decisions_count"], r0["occurrence_count"],
                     r0["merged_group_id"], (r0.get("case_name_modal") or "")[:28],
                     r0.get("year_printed") or "-",
                     (r0.get("split_reason") or "")[:22]))
            for rr in rs:
                ds = did.get((rr["court"], k), set())
                print("        court=%-5s rows=%d decisions=%d %s"
                      % (rr["court"], len(rs), len(ds), sorted(ds)[:3]))
