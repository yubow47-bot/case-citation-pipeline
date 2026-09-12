# -*- coding: utf-8 -*-
"""one_vote_audit.py — 「一票定名」的测量（审计环，可重放；PROBLEMS #58 之后的 Task 3）

归并层的案名投票里，切不出案名的行**不投票**（空票不算反对票）。于是只要 199 行里有
1 行切出了名字、其余 198 行空票，那一票就以 `case_name_agreement = 1.0` 获胜——这个
1.0 说的是「有意见的那 1 行里 100% 同意」，不是「引用它的 199 份判决里 100% 同意」。
裁定层 §10.3 又按案名判同案，一个借来的名字会把两件判决并到一起（PROBLEMS #57）。

本仪器只看不改：读归并层与裁定层产出，算每个**过门槛组的代表行**的名字支持度

    case_name_support = 赢家名字的票数 / 该键的计数行数

赢家票数没有单独输出，但 `case_name_agreement * candidates_admitted` 就是它
（agreement 的分母是「投了票的行」，admitted 就是投了票的行数），故可无损还原。
分母取 `key_occurrence_count`（裁定层的原始提及数，即归并层的 counted 行数）。

用法
    python audit/one_vote_audit.py                 # 分档 + 榜单
    python audit/one_vote_audit.py --top 40
"""
import argparse
import csv
import io
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv.field_size_limit(10 ** 9)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--min-votes", type=int, default=1)
    ap.add_argument("--input", default=os.path.join(ROOT, "data", "select_out", "selected.csv"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "audit", "one_vote_offenders.txt"))
    a = ap.parse_args()

    rows = list(csv.DictReader(io.open(a.input, encoding="utf-8", newline="")))
    groups = defaultdict(list)
    for r in rows:
        groups[r["merged_group_id"]].append(r)

    kept, offenders = 0, []
    hist = Counter()
    for gid, ms in groups.items():
        p = next((m for m in ms if m["is_primary"] == "true"), ms[0])
        if p["kept"] != "true":
            continue
        kept += 1
        try:
            occ = int(p["key_occurrence_count"] or p["occurrence_count"])
            adm = int(p["candidates_admitted"] or 0)
            agr = float(p["case_name_agreement"] or 0)
        except ValueError:
            continue
        if not p["case_name_modal"]:
            hist["无名字"] += 1
            continue
        if occ <= 0:
            continue
        votes = int(round(agr * adm))
        if votes < a.min_votes:
            hist["票数 < 门槛"] += 1
            continue
        sup = votes / occ
        band = ("<0.05" if sup < 0.05 else "0.05-0.1" if sup < 0.1 else
                "0.1-0.25" if sup < 0.25 else "0.25-0.5" if sup < 0.5 else
                "0.5-0.9" if sup < 0.9 else ">=0.9")
        hist[band] += 1
        if sup < 0.1:
            offenders.append((int(p["distinct_decisions_count"]), gid, p["case_name_modal"],
                              votes, occ, round(sup, 3), p["canonical_string"]))

    print("过门槛组 %d" % kept)
    print("名字支持度分档（票数 / 计数行数）：")
    for k in ("无名字", "票数 < 门槛", "<0.05", "0.05-0.1", "0.1-0.25", "0.25-0.5", "0.5-0.9", ">=0.9"):
        if hist[k]:
            print("  %-14s %6d" % (k, hist[k]))
    offenders.sort(reverse=True)
    print("\n支持度 < 0.10 的过门槛组：%d 个（按 dd 降序前 %d）" % (len(offenders), a.top))
    print("  %-6s %-8s %-8s %-6s %-6s %s" % ("dd", "票", "行数", "支持", "组", "名字"))
    for dd, gid, name, votes, occ, sup, cs in offenders[:a.top]:
        print("  %-6d %-8d %-8d %-6.3f %-6s %s" % (dd, votes, occ, sup, gid, name[:60]))
    if offenders:
        io.open(a.out, "w", encoding="utf-8").write(
            "\n".join("%d\t%d\t%d\t%.4f\t%s\t%s\t%s" % (dd, votes, occ, sup, gid, name, cs)
                      for dd, gid, name, votes, occ, sup, cs in offenders) + "\n")
        print("\n全量 -> %s" % a.out)


if __name__ == "__main__":
    sys.exit(main())
