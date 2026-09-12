# -*- coding: utf-8 -*-
"""preview_vs_prod.py — 预演实现与生产线实现的逐行等价性检查（审计环，可重放）

预演（`audit/preview_case_name.py`）与落在 `pipeline/classify.py` 里的实现是两份代码，
数字若不同必须能逐行解释。本工具把两份都跑一遍，只在**结果不同**的行上打印差异，
并按「差异是否由前导字符集不同引起」分类：

    生产线的段首剥离集是 `_ADMIT_LEAD_CHARS = {[ ( « " ' ‘ “ … .}`（含 `[` 与 `(`），
    预演用的是 `" \\t\\r\\n\\"'‘“«…."`（不含 `[` `(`）。段首是 `[`/`(` 时两者看到的
    段不同，标记判定可能因此不同。

用法
    python audit/preview_vs_prod.py [--samples 30]
"""
import argparse
import csv
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
csv.field_size_limit(10 ** 9)

import classify                                                    # noqa: E402
from preview_case_name import new_name                             # noqa: E402

BRACKET = re.compile(r"^[\s\[(«\"'‘“«….]+")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--samples", type=int, default=30)
    a = ap.parse_args()
    n, diff, explained = 0, 0, 0
    out = []
    for court in ("SCC", "ONCA"):
        with io.open(os.path.join(ROOT, "data", "classify_out", court, "classified.csv"),
                     encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                n += 1
                pre = r["preceding_text"] or ""
                pv, _, _ = new_name(pre, "marker_if_no_v")
                row = {"preceding_text": pre, "candidate_case_name": ""}
                classify.split_case_name(row)
                pr = row.get("candidate_case_name") or ""
                if pv == pr:
                    continue
                diff += 1
                # 段首剥离集差异能否解释：把段首的 [ ( 也剥掉后两边应看见同一段
                seg_sep = max(pre.rfind(";"), pre.rfind(":"), pre.rfind("\n"))
                tail = pre[seg_sep + 1:]
                lead = BRACKET.match(tail)
                lead = lead.group(0) if lead else ""
                if "[" in lead or "(" in lead:
                    explained += 1
                if len(out) < a.samples:
                    out.append("[%s] %s raw=%r\n    预演=%r\n    生产线=%r\n    seg首=%r"
                               % (court, r["source_decision_citation"], r["raw_string"], pv, pr, lead))
    print("总行 %d，两份实现不一致 %d 行，其中段首含 [ 或 ( 的 %d 行" % (n, diff, explained))
    print("\n\n".join(out))
    if diff and explained != diff:
        print("\n有 %d 行无法用前导字符集解释——必须查清。" % (diff - explained))
        return 1


if __name__ == "__main__":
    sys.exit(main())
