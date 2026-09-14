# -*- coding: utf-8 -*-
"""临时探针 2（只读）：mention 粒度口径核实——仲裁状态、种类、法域已解析率。
为 Stage 0 的 M1a/M1b 定义落地提供事实基础。"""
import csv
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "data", "run_20260913_r2i")


def scan(court):
    path = os.path.join(RUN, "merge_out", court, "mentions_candidates.csv")
    arb = Counter()
    kind_arb = Counter()
    jur_by_kind = Counter()
    abbr = Counter()
    abbr_jur = Counter()
    shape = Counter()
    vol_empty = Counter()
    n = 0
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            n += 1
            a = r["arbitration_status"]
            k = r["citation_kind"]
            j = (r["jurisdiction"] or "").strip()
            arb[a] += 1
            kind_arb[(k, a)] += 1
            if a == "counted":
                if j and j != "UNSUPPORTED":
                    jur_by_kind[(k, "resolved")] += 1
                else:
                    jur_by_kind[(k, "unresolved")] += 1
                if k == "reporter":
                    abbr[r["merge_key"].split("|")[2]] += 1
                    abbr_jur[(r["merge_key"].split("|")[2], j or "UNSUPPORTED")] += 1
                    shape[r["shape_name"]] += 1
                    vol = r["merge_key"].split("|")[1]
                    vol_empty[bool(vol)] += 1
    print("### %s  mentions=%d" % (court, n))
    print("  arbitration_status:", dict(arb.most_common()))
    print("  (kind,arb):", dict(kind_arb.most_common(12)))
    print("  counted by kind/jur:", dict(jur_by_kind.most_common()))
    print("  counted reporter shapes:", dict(shape.most_common()))
    print("  counted reporter vol slot non-empty:", dict(vol_empty))
    print("  top 25 counted reporter abbreviations (total):")
    for a, c in abbr.most_common(25):
        resolved = abbr_jur[(a, "")] + sum(v for (aa, jj), v in abbr_jur.items()
                                            if aa == a and jj not in ("", "UNSUPPORTED"))
        unres = abbr_jur[(a, "UNSUPPORTED")]
        print("    %-14s %8d   resolved=%-8d unsupported=%d" % (a, c, resolved, unres))
    return abbr


if __name__ == "__main__":
    tot = Counter()
    for c in ("SCC", "ONCA"):
        for k, v in scan(c).items():
            tot[k] += v
    print("### top 40 reporter abbreviations combined (counted mentions)")
    for a, c in tot.most_common(40):
        print("    %-14s %8d" % (a, c))
    print("TOTAL counted reporter mentions:", sum(tot.values()))
