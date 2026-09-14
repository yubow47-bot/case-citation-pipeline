# -*- coding: utf-8 -*-
"""临时探针 3（只读）：reporter_jurisdiction.csv 与 court_or_reporter_scope.csv 结构核实。"""
import csv
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEC = os.path.join(ROOT, "decisions")


def load(name):
    with open(os.path.join(DEC, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


rj = load("reporter_jurisdiction.csv")
print("reporter_jurisdiction.csv rows=%d" % len(rj))
print("cols:", list(rj[0].keys()))
print("jurisdiction dist:", Counter(r["jurisdiction"] for r in rj).most_common())
print("confidence dist:", Counter(r["confidence"] for r in rj).most_common())
print("verification_level dist:", Counter(r["verification_level"] for r in rj).most_common())
has_vol = [r for r in rj if (r["vol_range_start"] or "").strip() or (r["vol_range_end"] or "").strip()]
has_yr = [r for r in rj if (r["year_range_start"] or "").strip() or (r["year_range_end"] or "").strip()]
print("rows with vol range: %d / %d" % (len(has_vol), len(rj)))
print("rows with year range: %d / %d" % (len(has_yr), len(rj)))

by = defaultdict(list)
for r in rj:
    by[r["abbreviation"].strip()].append(r)
multi = {k: v for k, v in by.items() if len(v) > 1}
print("abbreviations with >1 row: %d" % len(multi))
for k, v in sorted(multi.items(), key=lambda x: -len(x[1])):
    print("--- %s (%d rows)" % (k, len(v)))
    for r in v:
        print("    jur=%-4s vol=[%s,%s] year=[%s,%s] conf=%s ver=%s" % (
            r["jurisdiction"], r["vol_range_start"], r["vol_range_end"],
            r["year_range_start"], r["year_range_end"], r["confidence"],
            r["verification_level"]))

print()
sp = load("court_or_reporter_scope.csv")
print("court_or_reporter_scope.csv rows=%d" % len(sp))
print("cols:", list(sp[0].keys()))
for r in sp:
    print("  %-22s %-10s %-12s %s..%s ver=%s" % (
        r.get("printed_key"), r.get("origin_country_scope"),
        r.get("source_kind", ""), r.get("valid_from"), r.get("valid_to"),
        r.get("verification_status")))
