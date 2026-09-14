# -*- coding: utf-8 -*-
"""临时校验：reporter_origin_scope.csv 的字段数、键口径与可写行纪律（只读）。"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from normalize import nk  # noqa: E402

p = os.path.join(ROOT, "decisions", "reporter_origin_scope.csv")
rows = list(csv.DictReader(open(p, encoding="utf-8", newline="")))
cols = list(csv.reader(open(p, encoding="utf-8", newline="")))
bad = 0
print("rows=%d cols=%d" % (len(rows), len(cols[0])))
for i, raw in enumerate(cols):
    if len(raw) != len(cols[0]):
        print("  !! line %d has %d fields" % (i + 1, len(raw)))
        bad += 1
ok = {"verified_exclusive_statute", "verified_exclusive_publisher"}
for r in rows:
    pa = (r.get("printed_abbreviation") or "").strip()
    nkv = (r.get("normalized_key") or "").strip()
    st = (r.get("verification_status") or "").strip()
    flag = []
    if nk(pa) != nk(nkv):
        flag.append("key mismatch nk(%r)=%s vs %s" % (pa, nk(pa), nk(nkv)))
    if st == "verified_mixed":
        if (r.get("origin_country") or "").strip():
            flag.append("mixed row has origin_country")
    elif st in ok:
        if not (r.get("origin_country") or "").strip():
            flag.append("writable row lacks origin_country")
        if (r.get("exclusivity") or "").strip() not in ("exclusive_statute",
                                                        "exclusive_publisher"):
            flag.append("writable row bad exclusivity")
        if not any((r.get(k) or "").strip() for k in
                   ("vol_range_start", "vol_range_end", "year_range_start",
                    "year_range_end")):
            flag.append("writable row has NO window")
        if (r.get("exclusivity") or "").strip() == "exclusive_publisher" \
                and not (r.get("counter_example_check") or "").strip():
            flag.append("publisher row lacks counter_example_check")
        if (r.get("volume_system") or "").strip() not in ("year_volume",
                                                          "continuous", ""):
            flag.append("writable row bad volume_system")
    else:
        flag.append("unknown verification_status")
    if not (r.get("source") or "").strip() or not (r.get("source_locator") or "").strip():
        flag.append("missing source/locator")
    print("  %-14s %-28s %-6s %s" % (pa, st,
                                     (r.get("exclusivity") or ""),
                                     "OK" if not flag else " | ".join(flag)))
    bad += len(flag)
print("problems:", bad)
