# -*- coding: utf-8 -*-
"""R4 Stage 2 断言：抽取跨度与 candidate_id 不变量（r3e vs r4a）+ 标注识别统计。
只读。candidate_id 已编码 court:row:start:end:shape → 集合相等即 (文档,起点,终点,形状)
集合相等。"""
import csv
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = {"r3e": "data/run_20260913_r3e", "r4a": "data/run_20260914_r4a"}


def cand_ids(run):
    s = set()
    for court in ("SCC", "ONCA"):
        p = os.path.join(ROOT, run, "extract_out", "candidates.csv")
        with open(p, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                s.add(r["candidate_id"])
    return s


def classify_stats(run):
    out = {}
    for court in ("SCC", "ONCA"):
        m = json.load(open(os.path.join(ROOT, run, "classify_out", court,
                                        "manifest.json"), encoding="utf-8"))
        for k, v in m["stats"].items():
            if k.startswith("court_designation"):
                out[k] = out.get(k, 0) + v
    return out


a = cand_ids(RUNS["r3e"])
b = cand_ids(RUNS["r4a"])
print("candidate_ids：r3e %d  r4a %d" % (len(a), len(b)))
print("  仅 r3e：%d" % len(a - b))
print("  仅 r4a：%d" % len(b - a))
print("  **不变量成立**" if a == b else "  **不变量破坏**")

print("\n标注识别统计（SCC+ONCA 合计）：")
for k, v in sorted(classify_stats(RUNS["r4a"]).items()):
    print("   %-46s %d" % (k, v))
