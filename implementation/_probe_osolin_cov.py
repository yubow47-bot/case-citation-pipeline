# -*- coding: utf-8 -*-
"""临时（决定性测量）：Osolin 例——比较 r2i / r3d 三个键的 citing-decision 集合，
并手工计算共指派覆盖率 cov = |ids ∩ dec_ids| / min(|ids|, |dec_ids|)。"""
import csv
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = {"r2i": "data/run_20260913_r2i", "r3d": "data/run_20260913_r3d"}


def dids(tag):
    run = RUNS[tag]
    out = defaultdict(set)
    for court in ("SCC", "ONCA"):
        p = os.path.join(ROOT, run, "decide_out", court, "decision_ids.csv")
        for r in csv.DictReader(open(p, encoding="utf-8", newline="")):
            c, _, mk = (r["row_key"] or "").partition("|")
            out[(c, mk)].add(r["source_decision_citation"])
    return out


def rows_for(run, key):
    d = os.path.join(ROOT, run, "decide_out", "cross_court", "decided.csv")
    out = defaultdict(list)
    for r in csv.DictReader(open(d, encoding="utf-8", newline="")):
        if r["merge_key"] == key:
            out[(r["court"], key)].append(r)
    return out


SCR_ON, SCR_SC = "1993|4|scr||595", "1993|4|scr||595"
CASES = [
    ("r2i", [("ONCA", "1993|86|ccc|3d|481"), ("ONCA", SCR_ON), ("SCC", SCR_SC)]),
    ("r3d", [("ONCA", "|86|ccc|3d|481"), ("ONCA", SCR_ON), ("SCC", SCR_SC)]),
]
D = {t: dids(t) for t in RUNS}
for tag, keys in CASES:
    print("=== %s ===" % tag)
    sets = {}
    for court, k in keys:
        s = D[tag].get((court, k), set())
        sets[(court, k)] = s
        print("  %-5s %-22s citing decisions = %d" % (court, k, len(s)))
        for x in sorted(s)[:8]:
            print("        ", x)
    # 以 SCC scr 为根（dec_ids = 自己的 citing 集 ∪ own）
    root_ids = sets[("SCC", SCR_SC)]
    for court, k in keys:
        if (court, k) == ("SCC", SCR_SC):
            continue
        ids = sets[(court, k)]
        if not ids:
            print("  单元 %-5s %-22s ids 为空 → 无法指派" % (court, k))
            continue
        ov = len(ids & root_ids)
        cov = ov / min(len(ids), len(root_ids)) if root_ids else 0
        print("  单元 %-5s %-22s |ids|=%d  |root|=%d  交=%d  cov=%.2f  %s"
              % (court, k, len(ids), len(root_ids), ov, cov,
                 "ATTACH" if cov >= 0.8 else "PENDING(拆出)"))
