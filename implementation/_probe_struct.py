# -*- coding: utf-8 -*-
"""临时探针 4：结构冲突旗分布（供账本 B13「年读作卷」规模复核）+ M3 异常族明细。"""
import csv
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "data", "run_20260913_r2i")

c = Counter()
for court in ("SCC", "ONCA"):
    with open(os.path.join(RUN, "merge_out", court, "mentions_candidates.csv"),
              encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            sc = (r.get("structural_conflict") or "").strip()
            if sc:
                c["all|" + sc] += 1
                if r["arbitration_status"] == "counted":
                    c["counted|" + sc] += 1
for k in sorted(c):
    print("%-40s %d" % (k, c[k]))

d = json.load(open(os.path.join(ROOT, "data", "coverage_out",
                                "stage0_r2i.json"), encoding="utf-8"))
print("\nM3 unexpected same-year multi-row examples:")
for e in d["M3_examples_unexpected_same_year_multi_row"]:
    print("  ", e)
print("\nM3 unique-year top20:")
for a, n in d["M3_unique_year_top20_abbr"]:
    print("   %-14s %5d" % (a, n))
print("\nM3 multi-year top20:")
for a, n in d["M3_multi_year_top20_abbr"]:
    print("   %-14s %5d" % (a, n))
print("\nM3 multi-year WITH empty variant top20:")
for a, n in d["M3_multi_year_with_empty_variant_top20_abbr"]:
    print("   %-14s %5d" % (a, n))
print("\nM4 detail:")
for r in d["M4_homograph_reporters"]:
    print("   %-10s rows=%-3d origins=%-16s unc=%-2d combos=%-5d out=%-4d "
          "uniq=%-5d amb=%-4d (same-country %-4d / diff %-4d) | mentions "
          "out=%-4d uniq=%-5d amb=%-4d (same %-4d / diff %-4d)"
          % (r["abbr"], r["table_rows"], ",".join(r["table_origins"]),
             r["unconstrained_rows"], r["observed_combos"],
             r["combos_out_of_window"], r["combos_unique"], r["combos_ambiguous"],
             r["combos_ambiguous_same_country"],
             r["combos_ambiguous_diff_country"],
             r["mentions_out_of_window"], r["mentions_unique"],
             r["mentions_ambiguous"], r["mentions_ambiguous_same_country"],
             r["mentions_ambiguous_diff_country"]))
