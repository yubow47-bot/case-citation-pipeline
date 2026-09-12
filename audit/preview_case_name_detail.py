# -*- coding: utf-8 -*-
"""preview_case_name_detail.py — 预演的明细器：把所有「改名」行与两模式差异行摊开

    python audit/preview_case_name_detail.py --renames data/audit/task2_renames.txt
    python audit/preview_case_name_detail.py --mode-diff data/audit/task2_modediff.txt
"""
import argparse
import csv
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
csv.field_size_limit(10 ** 9)

from preview_case_name import new_name, segment, marker_of   # noqa: E402
import classify                                              # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--renames")
    ap.add_argument("--mode-diff")
    ap.add_argument("--gains")
    ap.add_argument("--mode", default="marker_if_no_v",
                    choices=["marker_first", "marker_if_no_v"])
    a = ap.parse_args()
    out, gained = [], []
    for court in ("SCC", "ONCA"):
        p = os.path.join(ROOT, "data", "classify_out", court, "classified.csv")
        with io.open(p, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                old = (r.get("candidate_case_name") or "").strip()
                pre = r.get("preceding_text") or ""
                n1, r1, m1 = new_name(pre, a.mode)
                if a.renames and old and n1 and n1 != old:
                    out.append("[%s] %s\n    raw  = %s\n    旧   = %s\n    新   = %s\n    seg  = %s\n    tail = %r"
                               % (court, r.get("source_decision_citation"), r.get("raw_string"),
                                  old, n1, m1, pre[-200:]))
                if a.mode_diff:
                    n2, _, _ = new_name(pre, "marker_first" if a.mode == "marker_if_no_v"
                                        else "marker_if_no_v")
                    if n1 != n2:
                        out.append("[%s] MODEDIFF\n    raw  = %s\n    本模式 = %r\n    另一模式 = %r\n    seg  = %r\n    tail = %r"
                                   % (court, r.get("raw_string"), n1, n2, m1, pre[-200:]))
                if a.gains and not old and n1 and (a.gains == "-" or m1 == a.gains):
                    gained.append((len(n1), court, m1, r.get("raw_string"), n1,
                                   r.get("name_rejected_reason"), pre[-150:]))
    if a.gains:
        gained.sort(key=lambda t: -t[0])
        out = ["[长 %d] %s GAIN(%s) raw=%s\n    名 = %r\n    理由 = %s\n    tail = %r"
               % (L, c, m, raw, n, rej, pre) for (L, c, m, raw, n, rej, pre) in gained]
        print("gain 合计 %d 行，最长 %d 字符" % (len(gained), gained[0][0] if gained else 0))
    dest = a.renames or a.mode_diff or ("data/audit/task2_gains_%s.txt" % a.gains)
    io.open(dest, "w", encoding="utf-8").write("\n\n".join(out) + "\n")
    print("%d 条 -> %s" % (len(out), dest))


if __name__ == "__main__":
    sys.exit(main())
