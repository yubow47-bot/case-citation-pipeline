# -*- coding: utf-8 -*-
"""独立复测 astra 评价中的可检验数字（只读，不改任何产物）。
覆盖：selected.csv 组数/case_origin 分布、Almrei 行、罗马页码 merge key 塌缩
规模、decisions/case_origin.csv 的覆盖面。"""
import collections
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from merge import build_merge_key  # noqa: E402

FIELDS = ("merge_key", "canonical_string", "citation_kind", "jurisdiction",
          "jurisdiction_confidence", "case_origin", "dd", "kept",
          "occurrence_count", "distinct_decisions_count", "case_name_modal",
          "self_case_name", "self_citation_of", "is_primary")

out = {}

# ---- 1. selected.csv 组数与 case_origin 分布 -------------------------------
path = os.path.join(ROOT, "data", "select_out", "selected.csv")
cnt = {"all": 0, "primary": 0, "kept_primary": 0}
origin = {k: collections.Counter() for k in cnt}
almrei_rows = []
with open(path, encoding="utf-8", newline="") as f:
    for i, r in enumerate(csv.DictReader(f), 2):
        if r["is_primary"] == "true":
            seg = "kept_primary" if r["kept"] == "true" else "primary"
        else:
            seg = "all"
        cnt[seg] += 1
        origin[seg][r["case_origin"]] += 1
        if "2011 ONCA, 2011" in (r.get("canonical_string") or ""):
            row = {k: r.get(k, "") for k in FIELDS}
            row["csv_line"] = i
            almrei_rows.append(row)
out["selected_counts"] = cnt
out["case_origin"] = {k: dict(v) for k, v in origin.items()}
out["almrei_rows"] = almrei_rows[:5]

# ---- 2. 罗马页码 merge key 塌缩规模 ----------------------------------------
path = os.path.join(ROOT, "data", "extract_out", "extracted.csv")
roman_rows = 0
key_pages = collections.defaultdict(set)
with open(path, encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        if r["page_roman"]:
            roman_rows += 1
            key = build_merge_key(r)
            key_pages[key].add(r["page_roman"].lower())
out["roman_page_rows"] = roman_rows
out["roman_page_keys"] = len(key_pages)
out["roman_page_collapsed_keys"] = sum(1 for v in key_pages.values() if len(v) > 1)
out["roman_page_examples"] = [
    {"key": k, "pages": sorted(v)} for k, v in key_pages.items() if len(v) > 1
][:8]

# ---- 3. decisions/case_origin.csv 覆盖面 -----------------------------------
path = os.path.join(ROOT, "decisions", "case_origin.csv")
if os.path.exists(path):
    vals = collections.Counter()
    n = 0
    with open(path, encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        cols = rd.fieldnames
        for r in rd:
            n += 1
            vals[r.get("case_origin", "")] += 1
    out["case_origin_table"] = {"rows": n, "columns": cols, "values": dict(vals)}
else:
    out["case_origin_table"] = "MISSING"

# ---- 4. decisions/ 目录全貌 -------------------------------------------------
out["decisions_dir"] = sorted(os.listdir(os.path.join(ROOT, "decisions")))

print(json.dumps(out, ensure_ascii=False, indent=1))
