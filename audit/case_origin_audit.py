# -*- coding: utf-8 -*-
"""case_origin_audit.py — 来源地判定的全量前后差分（审计环，可重放）

用途：填 decisions/case_origin.csv 之后、重跑裁定层之前先快照，重跑后再对一次，
把「哪些行的来源地从 UNDETERMINED 变成了 CA」逐行数出来（约束九：数字须可重放）。
不做抽样——本项目历史上抽样漏过一次 145 行的回归。

用法
    python audit/case_origin_audit.py --snapshot data/audit/case_origin_before.tsv
    #   ... 重跑 decide.py / select.py ...
    python audit/case_origin_audit.py --diff data/audit/case_origin_before.tsv

快照键是 `row_key = court|merge_key`（裁定层给每行的唯一身份），值取
`merged_group_id \t case_origin \t deciding_court`。
"""
import argparse
import csv
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv.field_size_limit(10 ** 9)

TARGETS = [("decide_out/SCC/decided.csv", "court,merge_key"),
           ("decide_out/ONCA/decided.csv", "court,merge_key"),
           ("decide_out/cross_court/decided.csv", "court,merge_key"),
           ("select_out/selected.csv", "court,merge_key")]


def read_rows(path):
    with io.open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            yield r


def snapshot(out_path):
    lines = []
    for rel, _ in TARGETS:
        p = os.path.join(ROOT, "data", rel)
        if not os.path.exists(p):
            continue
        for r in read_rows(p):
            rk = "%s|%s" % (r.get("court") or "", r.get("merge_key") or "")
            lines.append("%s\t%s\t%s\t%s\t%s"
                         % (rel, rk, r.get("merged_group_id") or "",
                            r.get("case_origin") or "", r.get("deciding_court") or ""))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with io.open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("快照 %d 行 -> %s" % (len(lines), out_path))


def diff(old_path):
    old = {}
    with io.open(old_path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 5:
                old[(parts[0], parts[1])] = (parts[2], parts[3], parts[4])
    new = {}
    for rel, _ in TARGETS:
        p = os.path.join(ROOT, "data", rel)
        if not os.path.exists(p):
            continue
        for r in read_rows(p):
            rk = "%s|%s" % (r.get("court") or "", r.get("merge_key") or "")
            new[(rel, rk)] = (r.get("merged_group_id") or "",
                              r.get("case_origin") or "", r.get("deciding_court") or "")

    only_old = sorted(set(old) - set(new))
    only_new = sorted(set(new) - set(old))
    buckets = {}
    examples = {}
    for k in sorted(set(old) & set(new)):
        if old[k] == new[k]:
            continue
        o, n = old[k], new[k]
        if o[0] != n[0]:
            name = "组号变了（裁定层重新分组）"
        elif o[1] == n[1]:
            name = "deciding_court 变了"
        elif o[1] == "UNDETERMINED":
            name = "UNDETERMINED -> %s" % n[1]
        elif n[1] == "UNDETERMINED":
            name = "%s -> UNDETERMINED" % o[1]
        else:
            name = "%s -> %s" % (o[1], n[1])
        buckets[name] = buckets.get(name, 0) + 1
        examples.setdefault(name, []).append((k, o, n))

    print("== 全量行差分 ==")
    print("  旧 %d 行 / 新 %d 行" % (len(old), len(new)))
    print("  只在旧：%d    只在新：%d" % (len(only_old), len(only_new)))
    if only_old:
        print("   例：%r" % (only_old[:5],))
    if only_new:
        print("   例：%r" % (only_new[:5],))
    for name in sorted(buckets, key=lambda x: -buckets[x]):
        print("  %-34s %6d" % (name, buckets[name]))
        for k, o, n in examples[name][:3]:
            print("      %s  旧%s/%s -> 新%s/%s" % (k, o[0], o[1], n[0], n[1]))
    print("\n按文件分：")
    per = {}
    for (rel, rk) in set(old) & set(new):
        if old[(rel, rk)] != new[(rel, rk)]:
            per[rel] = per.get(rel, 0) + 1
    for rel in sorted(per):
        print("  %-34s %6d" % (rel, per[rel]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--snapshot")
    g.add_argument("--diff")
    a = ap.parse_args()
    if a.snapshot:
        snapshot(a.snapshot)
    else:
        diff(a.diff)


if __name__ == "__main__":
    sys.exit(main())
