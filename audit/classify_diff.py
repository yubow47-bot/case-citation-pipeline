# -*- coding: utf-8 -*-
"""classify_diff.py — 分类层产出的全量逐行差分（审计环，可重放）

改 `pipeline/classify.py` 前后各留一份 `classified.csv`，本工具按**行序号**逐行比对
（抽取层输入不变，故行序稳定），把变化分档数出来——本项目历史上抽样漏过一次 145 行的
回归，故一律全量。

用法
    # 改动前
    python audit/classify_diff.py --snapshot data/audit/before_task2
    #   改 pipeline/classify.py、重跑 classify.py
    python audit/classify_diff.py --before data/audit/before_task2 --after data/classify_out

分档（案名）：
    无名 -> 有名      （本次修复要的：只准出现这一档）
    有名 -> 同名
    有名 -> 不同名    **必须为 0**（改坏了别人的名字）
    有名 -> 无名      **必须为 0**
    无名 -> 无名      （再看拒绝理由有没有变）
其余字段（jurisdiction / citation_kind / lookup_mode / rejected_reason）另列一档，
非本层意图的变动必须解释。
"""
import argparse
import csv
import io
import os
import shutil
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv.field_size_limit(10 ** 9)
COURTS = ("SCC", "ONCA")
WATCH = ["jurisdiction", "citation_kind", "lookup_mode", "rejected_reason",
         "jurisdiction_confidence", "disambiguated_by", "vol_missing", "series_prefix"]


def snapshot(dest):
    for c in COURTS:
        src = os.path.join(ROOT, "data", "classify_out", c, "classified.csv")
        if not os.path.exists(src):
            continue
        os.makedirs(os.path.join(dest, c), exist_ok=True)
        shutil.copy2(src, os.path.join(dest, c, "classified.csv"))
        print("快照 %s -> %s" % (src, os.path.join(dest, c, "classified.csv")))


def rows(path):
    with io.open(path, encoding="utf-8", newline="") as f:
        for i, r in enumerate(csv.DictReader(f)):
            yield i, r


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--snapshot")
    g.add_argument("--before")
    ap.add_argument("--after", default=os.path.join(ROOT, "data", "classify_out"))
    ap.add_argument("--samples", type=int, default=6)
    ap.add_argument("--allow-renames", action="store_true",
                    help="改名已逐条复核并说明（如 #58 收回借名）：此时只有「丢了名字」才算回归")
    a = ap.parse_args()
    if a.snapshot:
        snapshot(a.snapshot)
        return

    bad = 0
    for c in COURTS:
        p_old = os.path.join(a.before, c, "classified.csv")
        p_new = os.path.join(a.after, c, "classified.csv")
        if not (os.path.exists(p_old) and os.path.exists(p_new)):
            print("[%s] 缺一边，跳过" % c)
            continue
        buckets, examples = Counter(), {}
        other, other_ex = Counter(), {}
        n = 0
        for (i, o) in rows(p_old):
            n += 1
        n2 = 0
        old_iter = rows(p_old)
        new_iter = rows(p_new)
        for (i, o), (j, nw) in zip(old_iter, new_iter):
            n2 += 1
            assert i == j
            on, nn = (o.get("candidate_case_name") or ""), (nw.get("candidate_case_name") or "")
            if not on and nn:
                k = "无名 -> 有名"
            elif on and nn == on:
                k = "有名 -> 同名"
            elif on and nn and nn != on:
                k = "有名 -> 不同名 **"
            elif on and not nn:
                k = "有名 -> 无名 **"
            else:
                k = "无名 -> 无名"
            buckets[k] += 1
            if k not in ("有名 -> 同名",) and len(examples.get(k, [])) < a.samples:
                examples.setdefault(k, []).append(
                    (o.get("source_decision_citation"), o.get("raw_string"), on, nn,
                     o.get("name_rejected_reason"), nw.get("name_rejected_reason")))
            for f in WATCH:
                if (o.get(f) or "") != (nw.get(f) or ""):
                    kk = "%s: %s -> %s" % (f, o.get(f), nw.get(f))
                    other[kk] += 1
                    if len(other_ex.get(kk, [])) < 3:
                        other_ex.setdefault(kk, []).append((o.get("raw_string"), on, nn))
        print("\n===== %s：旧 %d 行 / 新 %d 行 =====" % (c, n, n2))
        for k in ("无名 -> 有名", "有名 -> 同名", "有名 -> 不同名 **", "有名 -> 无名 **", "无名 -> 无名"):
            if buckets.get(k) or k.startswith("有名 -> 不同名") or k.startswith("有名 -> 无名"):
                print("  %-18s %7d" % (k, buckets.get(k, 0)))
                for e in examples.get(k, []):
                    print("      [%s] raw=%r\n          旧名=%r(%s) -> 新名=%r(%s)"
                          % (e[0], e[1][:40], e[2][:60], e[4], e[3][:60], e[5]))
        if other:
            print("  其他字段变动：")
            for k, v in other.most_common(20):
                print("    %-52s %7d" % (k, v))
                for raw, on, nn in other_ex[k][:2]:
                    print("        raw=%r 旧名=%r 新名=%r" % (raw[:40], on[:40], nn[:40]))
        else:
            print("  其他字段：零变动")
        if buckets.get("有名 -> 无名 **") or (buckets.get("有名 -> 不同名 **") and not a.allow_renames):
            bad = 1
    if bad:
        print("\n有名字被改动或丢失——这是回归，停下来查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
