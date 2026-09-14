# -*- coding: utf-8 -*-
"""临时探针：把简报里引用的「428,571 条加拿大汇编提及 / 72% UNDETERMINED」
在 r2i 上尽力复现（多个候选口径），以便口径对齐或明确记为不可复现。"""
import csv
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from normalize import nk  # noqa: E402

RUN = os.path.join(ROOT, "data", "run_20260913_r2i")
CA = {"CA", "ON", "QC", "BC", "AB", "NS", "NB", "MB", "SK", "NL", "PE",
      "YT", "NT", "NU"}

# 组状态
gstatus = {}
with open(os.path.join(RUN, "decide_out", "cross_court", "decided.csv"),
          encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        gstatus[r["merged_group_id"]] = r["group_origin_status"]
rowgroup = {}
with open(os.path.join(RUN, "decide_out", "cross_court", "decided.csv"),
          encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        rowgroup[(r["court"], r["merge_key"])] = r["merged_group_id"]

c = Counter()
in_table_ca = set()
with open(os.path.join(ROOT, "decisions", "reporter_jurisdiction.csv"),
          encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        if (r["jurisdiction"] or "").strip() in CA:
            in_table_ca.add(nk(r["abbreviation"]))

for court in ("SCC", "ONCA"):
    with open(os.path.join(RUN, "merge_out", court, "mentions_candidates.csv"),
              encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["citation_kind"] != "reporter":
                continue
            j = (r["jurisdiction"] or "").strip()
            g = rowgroup.get((court, r["merge_key"]), "")
            st = gstatus.get(g, "")
            counted = r["arbitration_status"] == "counted"
            ab = (r["merge_key"].split("|") + ["", "", ""])[2]
            c["all_statuses_reporter"] += 1
            if counted:
                c["counted_reporter"] += 1
            if j in CA:
                c["all_statuses_ca"] += 1
                if counted:
                    c["counted_ca"] += 1
                if st == "UNDETERMINED":
                    c["all_statuses_ca_undet"] += 1
                if counted and st == "UNDETERMINED":
                    c["counted_ca_undet"] += 1
            if ab in in_table_ca:
                if counted:
                    c["counted_intable_ca"] += 1
                    if st == "UNDETERMINED":
                        c["counted_intable_ca_undet"] += 1
                else:
                    c["all_statuses_intable_ca"] += 1
            if st == "UNDETERMINED":
                c["all_statuses_undet"] += 1
                if counted:
                    c["counted_undet"] += 1

for k in sorted(c):
    print("%-32s %d" % (k, c[k]))
print()
print("counted_ca undetermined share: %.1f%%" %
      (100.0 * c["counted_ca_undet"] / max(1, c["counted_ca"])))
print("all_statuses_ca undetermined share: %.1f%%" %
      (100.0 * c["all_statuses_ca_undet"] / max(1, c["all_statuses_ca"])))
