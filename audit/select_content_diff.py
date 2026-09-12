# -*- coding: utf-8 -*-
"""select_content_diff.py — 选取层产出的**内容级**前后差分（审计环，可重放）

计数不变也可能藏着一件案子被另一件替换掉（本项目栽过），故除了行数/组数，还要按
**组的成员引证集合**对齐两组产出，逐组比（案名、canonical_string、dd、kept）。

组的标识 `merged_group_id` 会随算法变化，不能用；成员 merge_key 是印刷引证串，
跨版本稳定，用它作组的指纹。

用法
    python audit/select_content_diff.py --before <旧 selected.csv> --after <新 selected.csv>
"""
import argparse
import csv
import io
import os
import sys
from collections import defaultdict

csv.field_size_limit(10 ** 9)


def load(path):
    groups = defaultdict(list)
    with io.open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            groups[r["merged_group_id"]].append(r)
    out = {}
    for gid, ms in groups.items():
        p = next((m for m in ms if m["is_primary"] == "true"), ms[0])
        # 指纹必须带 court：同一个印刷串（merge_key）会同时出现在两院的产出里
        fp = frozenset((m["court"], m["merge_key"]) for m in ms)
        out[fp] = {"gid": gid, "kept": p["kept"],
                   "name": p["case_name_modal"], "canon": p["canonical_string"],
                   "dd": int(p["distinct_decisions_count"]),
                   "occ": int(p["occurrence_count"])}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--samples", type=int, default=15)
    ap.add_argument("--out")
    a = ap.parse_args()
    old, new = load(a.before), load(a.after)
    only_old = [k for k in old if k not in new]
    only_new = [k for k in new if k not in old]
    same, name_changed, dd_changed, kept_changed = 0, [], [], []
    for k in old:
        if k not in new:
            continue
        o, n = old[k], new[k]
        if o["name"] == n["name"] and o["dd"] == n["dd"] and o["kept"] == n["kept"]:
            same += 1
            continue
        if o["name"] != n["name"]:
            name_changed.append((o, n))
        if o["dd"] != n["dd"]:
            dd_changed.append((o, n))
        if o["kept"] != n["kept"]:
            kept_changed.append((o, n))
    gained = [x for x in name_changed if not x[0]["name"] and x[1]["name"]]
    renamed = [x for x in name_changed if x[0]["name"] and x[1]["name"]]
    lost = [x for x in name_changed if x[0]["name"] and not x[1]["name"]]
    rep = ["== 选取层内容差分 ==",
           "  旧 %d 组 / 新 %d 组" % (len(old), len(new)),
           "  指纹相同且内容一致：%d" % same,
           "  案名变了：%d（其中 无名->有名 %d、改名 %d、有名->无名 %d）"
           % (len(name_changed), len(gained), len(renamed), len(lost)),
           "  dd 变了：%d     kept 变了：%d" % (len(dd_changed), len(kept_changed)),
           "  只在旧（组成员集合消失）：%d" % len(only_old),
           "  只在新（组成员集合新增）：%d" % len(only_new)]
    for label, bucket in (("改名", renamed), ("有名->无名", lost), ("无名->有名", gained[:8]),
                          ("dd 变了", dd_changed), ("kept 变了", kept_changed)):
        rep.append("\n-- %s（前 %d）--" % (label, a.samples))
        for o, n in bucket[:a.samples]:
            rep.append("   旧 dd=%-4d kept=%-5s %r\n   新 dd=%-4d kept=%-5s %r"
                       % (o["dd"], o["kept"], o["name"][:70], n["dd"], n["kept"], n["name"][:70]))
    rep.append("\n-- 只在旧（前 %d）--" % a.samples)
    for k in only_old[:a.samples]:
        rep.append("   dd=%-4d kept=%-5s %r  %r" % (old[k]["dd"], old[k]["kept"], old[k]["name"][:60],
                                                   old[k]["canon"][:40]))
    rep.append("\n-- 只在新（前 %d）--" % a.samples)
    for k in only_new[:a.samples]:
        rep.append("   dd=%-4d kept=%-5s %r  %r" % (new[k]["dd"], new[k]["kept"], new[k]["name"][:60],
                                                   new[k]["canon"][:40]))
    text = "\n".join(rep)
    print(text)
    if a.out:
        io.open(a.out, "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
