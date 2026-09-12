# -*- coding: utf-8 -*-
"""gate_effect_audit.py — 案名支持度闸的**逐组**效应（审计环，可重放；Task 3）

支持度闸改变分组的组只有几十个，值得逐组摊开看：闸把哪些组合拆开了、拆开后两边
分别是什么名字/引证/年份。据此判断闸是**挡住了错并**（两件不同判决被一个低支持度的
名字并到一起）还是**拆散了本该在一起的平行引证**（少算方向）。

    python audit/gate_effect_audit.py --before <不设闸的 selected.csv> --after <设闸的 selected.csv>
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
    return groups


def info(gid, ms):
    p = next((m for m in ms if m["is_primary"] == "true"), ms[0])
    return {"gid": gid, "name": p["case_name_modal"], "dd": int(p["distinct_decisions_count"]),
            "kept": p["kept"],
            "keys": sorted({m["merge_key"] for m in ms}),
            "neutral": sorted({m["merge_key"] for m in ms if m["citation_kind"] == "neutral"}),
            "support": p.get("case_name_support", "")}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    old, new = load(a.before), load(a.after)
    fp_old = {frozenset((m["court"], m["merge_key"]) for m in ms): g
              for g, ms in old.items()}
    fp_new = {}
    for g, ms in new.items():
        fp_new[frozenset((m["court"], m["merge_key"]) for m in ms)] = g
    gone = [k for k in fp_old if k not in fp_new]
    rep = ["== 支持度闸的逐组效应 ==",
           "旧 %d 组 / 新 %d 组；指纹消失 %d 组" % (len(old), len(new), len(gone))]
    for k in sorted(gone, key=lambda k: -info(fp_old[k], old[fp_old[k]])["dd"]):
        o = info(fp_old[k], old[fp_old[k]])
        rep.append("\n-- 旧组 %s  dd=%d kept=%s 支持度=%s" % (o["gid"], o["dd"], o["kept"], o["support"]))
        rep.append("   名 %r" % o["name"][:80])
        rep.append("   键 %s" % ("; ".join(o["keys"])[:200]))
        # 成员现在落在哪些新组里
        for (court, mk) in sorted(k):
            for fk, gid in fp_new.items():
                if (court, mk) in fk:
                    n = info(gid, new[gid])
                    rep.append("   新组 %s dd=%-4d kept=%-5s 支持度=%-6s 名 %r"
                               % (gid, n["dd"], n["kept"], n["support"], n["name"][:60]))
                    rep.append("        键 %s" % ("; ".join(n["keys"])[:180]))
                    break
    text = "\n".join(rep)
    print(text[:6000])
    if a.out:
        io.open(a.out, "w", encoding="utf-8").write(text + "\n")
        print("\n全量 -> %s" % a.out)


if __name__ == "__main__":
    sys.exit(main())
