# -*- coding: utf-8 -*-
"""复测补丁：罗马页码塌缩（修正 abbr 字段映射）+ folded_log 系列冲突数。"""
import collections
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from merge import build_merge_key  # noqa: E402

out = {}

# ---- 罗马页码塌缩（用 extracted.csv 的 abbr 填 abbreviation）---------------
path = os.path.join(ROOT, "data", "extract_out", "extracted.csv")
roman_rows = 0
key_pages = collections.defaultdict(set)
samples = []
with open(path, encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        if r["page_roman"]:
            roman_rows += 1
            k = build_merge_key({"year_start": r["year_start"], "vol": r["vol"],
                                 "abbreviation": r["abbr"], "series_prefix": "",
                                 "series": r["series"], "page": r["page"]})
            key_pages[k].add(r["page_roman"].lower())
            if len(samples) < 3:
                samples.append({"raw": r["raw_string"], "shape": r["shape_name"],
                                "key": k})
out["roman_rows"] = roman_rows
out["roman_keys"] = len(key_pages)
out["collapsed_keys"] = sum(1 for v in key_pages.values() if len(v) > 1)
out["max_pages_in_one_key"] = max(len(v) for v in key_pages.values())
out["samples"] = samples
top5 = sorted(((k, v) for k, v in key_pages.items() if len(v) > 1),
              key=lambda item: -len(item[1]))[:5]
out["examples"] = [{"key": k, "pages": sorted(v)} for k, v in top5]

# ---- 幻影键进了最终保留集多少（kept=true 且页位为空 = 罗马页键）------------
path = os.path.join(ROOT, "data", "select_out", "selected.csv")
kept_roman = []
with open(path, encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        if (r["is_primary"] == "true" and r["kept"] == "true"
                and r["merge_key"].endswith("|")
                and r["merge_key"].count("|") == 4):
            tail = r["merge_key"].rsplit("|", 1)[1]
            if tail == "":
                kept_roman.append({"key": r["merge_key"],
                                   "dd": r.get("dd") or r.get("distinct_decisions_count"),
                                   "canonical": r["canonical_string"],
                                   "occ": r["occurrence_count"]})
out["kept_keys_with_empty_page"] = len(kept_roman)
out["kept_roman_examples"] = kept_roman[:8]

# ---- folded_log 系列冲突复测（同 astra 方法）-------------------------------
for court in ("SCC", "ONCA"):
    grouped = collections.defaultdict(set)
    with open(os.path.join(ROOT, "data", "merge_out", court,
                           "folded_log.csv"), encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            m = re.search(r"\(\s*(\d+)(?:st|nd|rd|th|d)\s*\)", row["raw_string"])
            if m:
                grouped[row["merge_key"]].add(m.group(1))
    conf = {k: sorted(v) for k, v in grouped.items() if len(v) > 1}
    out[f"{court}_series_conflict_keys"] = len(conf)

print(json.dumps(out, ensure_ascii=False, indent=1))
