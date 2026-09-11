# -*- coding: utf-8 -*-
"""coverage_report.py — 填表优先级报告（规格 §12.1）

输出**尚未入表**的缩写 / 代码 / 前缀，按被多少份不同判决引用（dd）降序——让填表
永远知道「下一条该填哪个」，每填一批重跑一次看覆盖率涨了多少。

性质是**提案**（给人看的待办清单），不喂任何生产脚本，也不写 decisions/。

用法
    python pipeline/coverage_report.py --kind reporter \
        --classified data/classify_out/SCC/classified.csv data/classify_out/ONCA/classified.csv \
        --out data/coverage_out/reporter.csv
    --kind neutral / --kind series 同理

三种报告
    reporter  法域 UNSUPPORTED 的汇编缩写族（nk 归一）。区分「表里没有」与「表里有但
              判不出」——后者多是同形异义消不开（K.B. 英国/魁北克），要补的是区间，
              不是新行
    neutral   shape_neutral_bare 中法域 UNSUPPORTED 的裸代码族（normalize_code 归一）。
              方括号形态里的中立码候选要先分诊（汇编缩写去点后与之同形，AC 实为 A.C.），
              见 audit/neutral_triage.py
    series    被判 unrecognized_series_prefix 的前缀族（normalize_code 归一）。注意这一族里
              大半是结构骨架误报（See、Section、Vol.），正是这张表要拦的东西——排行靠前
              不等于该入表

与规格 §12 的出入
    规格写的输入是归并层 merged.csv；本实现读分类层 classified.csv——merged.csv 没有
    leading_abbr 与 shape_name，series / neutral 两种报告做不出来。dd 由逐行的
    source_decision_citation 直接取并集，与归并层 §9.2 同一口径（行级误报不计，series
    报告除外：它报的正是被行级拒绝的那批）。
"""
import argparse
import csv
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import nk, normalize_code                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECISIONS = os.path.join(ROOT, "decisions")

TABLE_OF = {"reporter": "reporter_jurisdiction.csv",
            "neutral": "neutral_court_codes.csv",
            "series": "series_prefix.csv"}


def table_keys(kind):
    path = os.path.join(DECISIONS, TABLE_OF[kind])
    keys = set()
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if kind == "reporter":
                for v in (r.get("abbreviation"), r.get("normalized_key")):
                    if v and v.strip():
                        keys.add(nk(v))
            elif kind == "neutral":
                if (r.get("court_code") or "").strip():
                    keys.add(normalize_code(r["court_code"]))
            else:
                for v in (r.get("canonical_prefix"), r.get("normalized_key")):
                    if v and v.strip():
                        keys.add(normalize_code(v))
    return keys


def family_of(kind, r):
    """返回 (归一键, 印刷形)；不属本报告的行返回 None。"""
    rej = r.get("rejected_reason") or ""
    if kind == "series":
        if "unrecognized_series_prefix" not in rej:
            return None
        printed = (r.get("leading_abbr") or "").strip()
        return normalize_code(printed), printed
    if rej or r.get("jurisdiction") != "UNSUPPORTED":
        return None
    if kind == "reporter":
        if r.get("citation_kind") != "reporter":
            return None
        printed = (r.get("abbreviation") or "").strip()
        return nk(printed), printed
    if r.get("shape_name") != "shape_neutral_bare":
        return None
    printed = (r.get("token") or "").strip()
    return normalize_code(printed), printed


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kind", required=True, choices=sorted(TABLE_OF))
    ap.add_argument("--classified", required=True, nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--top", type=int, default=20)
    a = ap.parse_args()
    csv.field_size_limit(10 ** 9)

    rows, dd, forms = Counter(), defaultdict(set), defaultdict(Counter)
    for p in a.classified:
        with open(p, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                fam = family_of(a.kind, r)
                if not fam or not fam[0]:
                    continue
                key, printed = fam
                rows[key] += 1
                dd[key].add(r.get("source_decision_citation") or "")
                forms[key][printed] += 1

    in_table = table_keys(a.kind)
    total = sum(rows.values())
    order = sorted(rows, key=lambda k: (-len(dd[k]), -rows[k], k))

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    tmp = a.out + ".tmp"
    run = 0
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "family", "top_printed_form", "rows", "distinct_decisions",
                     "cum_pct_rows", "table_status"])
        for i, k in enumerate(order, 1):
            run += rows[k]
            w.writerow([i, k, forms[k].most_common(1)[0][0], rows[k], len(dd[k]),
                        round(run / total * 100, 2) if total else 0.0,
                        "in_table_unresolved" if k in in_table else "absent"])
    os.replace(tmp, a.out)

    print("kind=%s  待填 %d 行 / %d 族 -> %s" % (a.kind, total, len(order), a.out))
    run = 0
    for i, k in enumerate(order[:a.top], 1):
        run += rows[k]
        print("  %3d  %-16s %-22s rows %-7d dd %-6d cum %5.1f%%  %s"
              % (i, k[:16], forms[k].most_common(1)[0][0][:22], rows[k], len(dd[k]),
                 run / total * 100 if total else 0.0,
                 "表内判不出" if k in in_table else ""))


if __name__ == "__main__":
    main()
