# -*- coding: utf-8 -*-
"""临时：Quebec/Ontario 候选缩写的印刷形样本与年/卷/系列分布（写表前核对）。"""
import csv
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "data", "run_20260913_r3a")
WANT = ("rjq", "queqb", "cs", "qr.kb", "qr.sc", "ucqb", "or", "oac", "oj",
        "br", "rp", "lcjur")
samples = {w: Counter() for w in WANT}
ser = {w: Counter() for w in WANT}
yr = {w: Counter() for w in WANT}
kind = {w: Counter() for w in WANT}
for court in ("SCC", "ONCA"):
    with open(os.path.join(RUN, "merge_out", court, "mentions_candidates.csv"),
              encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["arbitration_status"] != "counted":
                continue
            p = r["merge_key"].split("|")
            if len(p) < 5 or p[2] not in samples:
                continue
            w = p[2]
            samples[w][r["raw_string"]] += 1
            ser[w][p[3] or "(none)"] += 1
            yr[w][p[0] or "(empty)"] += 1
            kind[w][r["citation_kind"]] += 1
for w in WANT:
    if not samples[w]:
        print("### %-8s (none)" % w)
        continue
    print("### %-8s kinds=%s series=%s" % (w, dict(kind[w].most_common(3)),
                                           dict(ser[w].most_common(6))))
    y = sorted(k for k in yr[w] if k != "(empty)")
    print("     years: %s..%s  (empty %d)  distinct=%d"
          % (y[0] if y else "-", y[-1] if y else "-", yr[w]["(empty)"], len(y)))
    for s, n in samples[w].most_common(6):
        print("     %6d  %s" % (n, s))
