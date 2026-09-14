# -*- coding: utf-8 -*-
"""临时探针：看指定缩写的 merge_key 形状（槽位分布），判断哪条规则路径可行。"""
import csv
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "data", "run_20260913_r2i")
WANT = {"oj", "scca", "canscr", "fc", "fcr", "scr", "dlr", "or", "ojc"}
keys = {w: Counter() for w in WANT}
kind = {w: Counter() for w in WANT}
for court in ("SCC", "ONCA"):
    with open(os.path.join(RUN, "merge_out", court, "mentions_candidates.csv"),
              encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["arbitration_status"] != "counted":
                continue
            p = r["merge_key"].split("|")
            if len(p) < 5 or p[2] not in WANT:
                continue
            keys[p[2]][r["merge_key"]] += 1
            kind[p[2]][(r["citation_kind"], "vol_empty" if not p[1] else "vol_set")] += 1
for w in sorted(WANT):
    print("### %s  kinds=%s" % (w, dict(kind[w].most_common())))
    for k, n in keys[w].most_common(6):
        print("      %6d  %s" % (n, k))
