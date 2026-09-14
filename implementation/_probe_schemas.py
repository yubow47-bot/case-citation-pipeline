# -*- coding: utf-8 -*-
"""临时探针（只读）：打印各层产物列名与样例，供 Stage 0 口径落地前核实。"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "data", "run_20260913_r2i")


def head(path, n=2):
    print("=" * 100)
    print("FILE:", os.path.relpath(path, ROOT))
    if not os.path.exists(path):
        print("  (missing)")
        return
    with open(path, encoding="utf-8", newline="") as f:
        rd = csv.reader(f)
        try:
            cols = next(rd)
        except StopIteration:
            print("  (empty)")
            return
        print("  ncols=%d" % len(cols))
        print("  cols:", cols)
        for i, row in enumerate(rd):
            if i >= n:
                break
            print("  row%d:" % i, row)


def count_rows(path):
    n = 0
    with open(path, encoding="utf-8", newline="") as f:
        rd = csv.reader(f)
        next(rd, None)
        for _ in rd:
            n += 1
    return n


if __name__ == "__main__":
    for p in [
        "merge_out/SCC/merged.csv",
        "merge_out/SCC/mentions_candidates.csv",
        "classify_out/SCC/classified.csv",
        "decide_out/SCC/decided.csv",
        "decide_out/cross_court/decided.csv",
        "decide_out/cross_court/effective_sources.csv",
        "edges/foreign_edges.csv",
        "select_out/selected.csv",
    ]:
        head(os.path.join(RUN, p))
    print("=" * 100)
    for p in ["merge_out/SCC/merged.csv", "merge_out/ONCA/merged.csv",
              "classify_out/SCC/classified.csv", "classify_out/ONCA/classified.csv",
              "decide_out/cross_court/decided.csv"]:
        fp = os.path.join(RUN, p)
        if os.path.exists(fp):
            print("rows %-55s %d" % (p, count_rows(fp)))
