# -*- coding: utf-8 -*-
"""near_year_peers_audit.py — 「同名、年份相差 ≤1」的组对测量与验收（审计环，可重放；PROBLEMS #62 / Task 5）

同一件案子被两种写法印出来、而两种写法在**任何一份判决里都没同时出现过**时，数据里
没有任何东西把它们连起来（PROBLEMS #55 的零共引残余）。本仪器不改任何东西，只回答两件事：

1. **量**：kept 组之间，`nk(案名)` 相同、主行年份相差 ≤1 的组对有多少（**组级计数**：
   一对组算一对；按行计数会得出更大且口径不同的数字，引用时必须写明口径）。
2. **验**：这些组对是否在 `same_name_near_year_peers` 列里**两边都被标出**。

年份取主行的 `merge_key` 首字段（与 §10.3 判同案的年份同源）。

用法
    python audit/near_year_peers_audit.py                       # 现行 selected.csv
    python audit/near_year_peers_audit.py --input <selected.csv>
"""
import argparse
import csv
import io
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
csv.field_size_limit(10 ** 9)
from normalize import nk                                       # noqa: E402


def year_of(mk):
    h = (mk or "").split("|", 1)[0]
    return int(h) if h.isdigit() else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", default=os.path.join(ROOT, "data", "select_out", "selected.csv"))
    ap.add_argument("--examples", type=int, default=10)
    ap.add_argument("--out")
    a = ap.parse_args()

    groups = defaultdict(list)
    with io.open(a.input, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            groups[r["merged_group_id"]].append(r)
    prim = {g: next((m for m in ms if m["is_primary"] == "true"), ms[0]) for g, ms in groups.items()}

    by_name = defaultdict(list)
    for gid, p in prim.items():
        nm = nk(p.get("case_name_modal") or "")
        y = year_of(p.get("merge_key"))
        if nm and y is not None:
            by_name[nm].append((y, gid))

    kept_pairs, all_pairs = [], []
    for nm, items in by_name.items():
        items.sort()
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if abs(items[i][0] - items[j][0]) <= 1:
                    all_pairs.append((nm, items[i], items[j]))
                    if (prim[items[i][1]]["kept"] == "true" and prim[items[j][1]]["kept"] == "true"):
                        kept_pairs.append((nm, items[i], items[j]))

    has_col = "same_name_near_year_peers" in next(iter(prim.values()))
    missing = []
    if has_col:
        for nm, (ya, ga), (yb, gb) in kept_pairs:
            pa = prim[ga].get("same_name_near_year_peers") or ""
            pb = prim[gb].get("same_name_near_year_peers") or ""
            if gb not in pa.split(";") or ga not in pb.split(";"):
                missing.append((nm, ga, gb, pa, pb))

    rep = ["== 同名、年份相差 ≤1 的组对 ==",
           "  所有组（组级计数）：%d 对" % len(all_pairs),
           "  其中两边都过门槛（kept）：**%d 对**" % len(kept_pairs),
           "  列 `same_name_near_year_peers` 存在：%s" % ("是" if has_col else "否")]
    if has_col:
        rep.append("  未在两边都标出的 kept 组对：%d" % len(missing))
        for nm, ga, gb, pa, pb in missing[:a.examples]:
            rep.append("     %s：%s vs %s（列值 %r / %r）" % (nm, ga, gb, pa, pb))
    rep.append("\n  kept 组对示例（前 %d）：" % a.examples)
    for nm, (ya, ga), (yb, gb) in kept_pairs[:a.examples]:
        rep.append("     %-46s %s(%d)  <->  %s(%d)" % (nm[:44], ga, ya, gb, yb))
    text = "\n".join(rep)
    print(text)
    if a.out:
        io.open(a.out, "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
