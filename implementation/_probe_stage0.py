# -*- coding: utf-8 -*-
"""临时：打印 Stage 0 JSON 的关键明细段（只读）。"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(ROOT, "data", "coverage_out", "stage0_r2i.json")
d = json.load(open(p, encoding="utf-8"))

print("### M1a top 40 abbr (mentions)")
for a, n in d["M1a_top40_abbr"]:
    print("   %-14s %8d" % (a, n))

print("\n### net-new UNDETERMINED groups: top 40 abbr (mentions in those groups)")
for a, n in d["M1_netnew_top40_abbr"]:
    print("   %-14s %8d" % (a, n))

print("\n### net-new groups by abbr (GROUP-level count, top 40)")
for a, n in d["M1_netnew_groups_by_abbr_top40"]:
    print("   %-14s %8d" % (a, n))

print("\n### blocked-by-ineligible-basis groups:", d["M1_blocked_by_ineligible_basis_groups"])
print("    combo:", d["M1_blocked_by_ineligible_basis_combo_top20"])
print("    undetermined groups with M1a(any basis):",
      d["M1_undetermined_groups_with_m1a_any_basis"],
      " determined:", d["M1_determined_groups_with_m1a_any_basis"])
print("    netnew clean:", d["M1_netnew_clean_single_country_groups"],
      " multicountry:", d["M1_netnew_multicountry_would_conflict_groups"],
      " kept-clean:", d["M1_netnew_clean_kept_groups_dd_ge_5"])

print("\n### conflict-risk proxy top 30")
for r in d["M1_conflict_risk_top30"]:
    print("   group=%-4s mention=%-4s abbr=%-10s n=%d" % (
        r["group_country"], r["mention_country"], r["abbr"], r["mentions"]))

print("\n### sensitivity: top 20 unresolved-jurisdiction abbr")
for a, n in d["M1a_sensitivity_top20_unresolved_abbr"]:
    print("   %-14s %8d" % (a, n))

print("\n### M2 top 30")
for r in d["M2_top30"]:
    print("   %-14s n=%-8d homo=%d %s" % (
        r["abbr"], r["mentions"], r["homograph_rows"],
        ",".join("%s:%d" % kv for kv in list(r["jurisdiction"].items())[:6])))

print("\n### M4 homograph detail")
print("   totals:", d["M4_totals_combos"])
for r in d["M4_homograph_reporters"]:
    print("   %-10s rows=%-3d origins=%-18s unconstrained=%-2d combos=%-5d "
          "out=%-4d uniq=%-5d amb=%-4d | mentions out=%-4d uniq=%-5d amb=%-4d"
          % (r["abbr"], r["table_rows"], ",".join(r["table_origins"]),
             r["unconstrained_rows"], r["observed_combos"],
             r["combos_out_of_window"], r["combos_unique"], r["combos_ambiguous"],
             r["mentions_out_of_window"], r["mentions_unique"],
             r["mentions_ambiguous"]))

print("\n### M3 unique-year merge examples")
for e in d["M3_examples_unique_year"]:
    print("   %-5s %-10s ser=%-6s vol=%-5s page=%-6s year=%-5s empty=%d rows=%d %s"
          % (e["court"], e["abbr"], e["series"], e["vol"], e["page"], e["year"],
             e["empty_year_rows"], e["rows"], e["merge_keys"]))

print("\n### M3 multi-year abstain examples")
for e in d["M3_examples_multi_year_abstain"]:
    print("   %-5s %-10s ser=%-6s vol=%-5s page=%-6s years=%s rows=%d"
          % (e["court"], e["abbr"], e["series"], e["vol"], e["page"],
             e["years"], e["rows"]))

print("\n### M3 unique-year top 20 abbr")
for a, n in d["M3_unique_year_top20_abbr"]:
    print("   %-14s %5d" % (a, n))
print("\n### M3 multi-year top 20 abbr")
for a, n in d["M3_multi_year_top20_abbr"]:
    print("   %-14s %5d" % (a, n))
print("\n### M3 multi-year WITH empty variant top 20 abbr")
for a, n in d["M3_multi_year_with_empty_variant_top20_abbr"]:
    print("   %-14s %5d" % (a, n))
print("\n### M3 unexpected same-year multi-row examples")
for e in d["M3_examples_unexpected_same_year_multi_row"]:
    print("   ", e)

print("\n### per court", d["per_court"])
print("### reporter_jurisdiction homographs", d["reporter_jurisdiction_homograph_abbrs"])
