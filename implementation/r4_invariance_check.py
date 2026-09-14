# -*- coding: utf-8 -*-
"""R4 Stage 2/4 断言：抽取跨度与 candidate_id 不变量（r3e vs r4c）+ 标注识别统计。

只读。candidate_id 已编码 court:row:start:end:shape → 集合相等即
(文档, 起点, 终点, 形状) 集合相等（任务书要求的全语料不变量断言）。
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = {"r3e": "data/run_20260913_r3e", "r4c": "data/run_20260914_r4c"}


def cand_ids(run):
    s = set()
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
b = cand_ids(RUNS["r4c"])
print("candidate_ids: r3e %d  r4c %d" % (len(a), len(b)))
print("  only in r3e: %d" % len(a - b))
print("  only in r4c: %d" % len(b - a))
print("  INVARIANT HOLDS" if a == b else "  INVARIANT BROKEN")

print("\ndesignation recognition (SCC+ONCA):")
for k, v in sorted(classify_stats(RUNS["r4c"]).items()):
    print("   %-48s %d" % (k, v))