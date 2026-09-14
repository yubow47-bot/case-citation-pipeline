# -*- coding: utf-8 -*-
"""临时探针 5：独立复算边计数（不信 run 自述）+ 取 Stage 0 JSON 的零散键。"""
import csv
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "data", "run_20260913_r2i")

c = Counter()
with open(os.path.join(RUN, "edges", "citation_edges.csv"),
          encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        c[r.get("foreign_status") or ""] += 1
        c["edge_support:" + (r.get("edge_support") or "")] += 1
print("citation_edges.csv foreign_status:", dict(c.most_common()))
print("total edges:", sum(v for k, v in c.items() if not k.startswith("edge_support")))

d = json.load(open(os.path.join(ROOT, "data", "coverage_out",
                                "stage0_r2i.json"), encoding="utf-8"))
for k in ("M1a_abbr_distinct", "M1_netnew_abbr_distinct",
          "M1a_member_rows_unknown_in_decided", "kept_groups_by_foreign_status",
          "groups_by_status", "reporter_jurisdiction_rows"):
    print(k, "=", d.get(k))
