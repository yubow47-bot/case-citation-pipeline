# -*- coding: utf-8 -*-
"""临时探针：列出指定缩写（citation_kind=reporter, counted）的印刷形样本与量级，
用于 Stage 1 合并时的「这个键到底印的是什么」核对。"""
import csv
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "data", "run_20260913_r2i")
WANT = ("fc", "fcr", "fca", "fct", "scr", "canscr", "scca", "dlr", "or", "oj",
        "ccc", "wwr", "oac", "cr", "bclr", "ar", "rfl", "qr.kb", "ontlr", "olr",
        "manr", "nsr", "nbr", "mplr", "bcj", "excr", "cbr", "crr", "cpc")

samples = {w: Counter() for w in WANT}
tot = Counter()
yrs = {w: [None, None] for w in WANT}
vols = {w: [None, None] for w in WANT}
for court in ("SCC", "ONCA"):
    with open(os.path.join(RUN, "merge_out", court, "mentions_candidates.csv"),
              encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["arbitration_status"] != "counted" or r["citation_kind"] != "reporter":
                continue
            p = r["merge_key"].split("|")
            if len(p) < 5:
                continue
            ab = p[2]
            if ab not in samples:
                continue
            tot[ab] += 1
            samples[ab][r["raw_string"]] += 1
            y, v = p[0], p[1]
            if y.isdigit():
                iy = int(y)
                yrs[ab][0] = iy if yrs[ab][0] is None else min(yrs[ab][0], iy)
                yrs[ab][1] = iy if yrs[ab][1] is None else max(yrs[ab][1], iy)
            if v.isdigit():
                iv = int(v)
                vols[ab][0] = iv if vols[ab][0] is None else min(vols[ab][0], iv)
                vols[ab][1] = iv if vols[ab][1] is None else max(vols[ab][1], iv)

for w in WANT:
    if not tot[w]:
        print("### %-8s (no counted reporter mentions)" % w)
        continue
    print("### %-8s mentions=%-7d vol=%s year=%s" % (w, tot[w], vols[w], yrs[w]))
    for s, n in samples[w].most_common(8):
        print("      %6d  %s" % (n, s))
