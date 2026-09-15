# -*- coding: utf-8 -*-
"""71 个 kept 罗马页键里，多少确实混合了多个不同页码（= 多个不同判决）。"""
import collections
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from merge import build_merge_key  # noqa: E402

# 1) extracted.csv：罗马页行的 key -> 页码集合
key_pages = collections.defaultdict(set)
with open(os.path.join(ROOT, "data", "extract_out", "extracted.csv"),
          encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        if r["page_roman"]:
            k = build_merge_key({"year_start": r["year_start"], "vol": r["vol"],
                                 "abbreviation": r["abbr"], "series_prefix": "",
                                 "series": r["series"], "page": r["page"]})
            key_pages[k].add(r["page_roman"].lower())

# 2) selected.csv：kept=true 且页位为空的主组键
kept_keys = set()
with open(os.path.join(ROOT, "data", "select_out", "selected.csv"),
          encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        if (r["is_primary"] == "true" and r["kept"] == "true"
                and r["merge_key"].endswith("|")):
            kept_keys.add(r["merge_key"])

multi = {k: sorted(v) for k, v in key_pages.items()
         if k in kept_keys and len(v) > 1}
out = {"kept_empty_page_keys": len(kept_keys),
       "kept_keys_mixing_multiple_pages": len(multi),
       "max_pages": max((len(v) for v in multi.values()), default=0),
       "examples": [{"key": k, "pages": v} for k, v in
                    sorted(multi.items(), key=lambda kv: -len(kv[1]))[:6]],
       "single_page_kept_keys": len(kept_keys) - len(multi)}
print(json.dumps(out, ensure_ascii=False, indent=1))
