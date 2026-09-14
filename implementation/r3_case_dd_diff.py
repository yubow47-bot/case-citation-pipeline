# -*- coding: utf-8 -*-
"""R3 身份回归仪器（只读）：按**案名最大组 dd** 比较两轮 + 孤立组规模 + 分离成因归属。

口径（复核人指定，也是本轮验收口径）：
  1. 每 run 按组取 dd，用组内主行案名（nk 归一）归名；每个案名取它**最大组的 dd**，
     比较两轮同名读数 → 升/降/持平。
  2. 孤立组两种口径：
     A = 全成员键年槽为空 **且** 全为「连续编卷」（运行时口径：volume_system=continuous）
     B = 全成员键年槽为空（不限缩写）
  3. 分离成因：**比较成员集合**（不用 merged_group_id——它是每轮重新编号的，拿它判
     「键换了组」会把整轮重编号都算成变化）。统计「前一轮同组、后一轮不同组」的成员对，
     并看其中多少涉及「年槽为空的连续编卷键」。

用法：
  python implementation/r3_case_dd_diff.py --before <run> --after <run> [--show-top N]
"""

import argparse
import csv
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from normalize import nk                                        # noqa: E402
from decide import load_reporter_origin                         # noqa: E402


def abbr_of(k):
    p = k.split("|")
    return p[2] if len(p) >= 5 else ""


def year_of_key(k):
    p = k.split("|")
    return p[0] if len(p) >= 5 else ""


def continuous_abbrs():
    """运行时口径的「连续编卷」缩写（= 会让 merge 零化年槽的那些）。"""
    out = set()
    for k, rows in load_reporter_origin().items():
        vs = {(r.get("volume_system") or "").strip() for r in rows}
        vs.discard("")
        if vs == {"continuous"}:
            out.add(k)
    return out


def load(run_dir):
    """→ (name_dd, of_key_members, gid_dd, gid_name, isoA, isoB)"""
    mem, dd, nm = defaultdict(list), {}, {}
    with open(os.path.join(run_dir, "decide_out", "cross_court", "decided.csv"),
              encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            g = r["merged_group_id"]
            mem[g].append(r["merge_key"])
            dd[g] = int(r["distinct_decisions_count"] or 0)
            if r.get("is_primary") == "true":
                nm[g] = nk(r.get("case_name_modal") or "")
            else:
                nm.setdefault(g, nk(r.get("case_name_modal") or ""))
    name_dd = {}
    for g, d in dd.items():
        n = nm.get(g) or ""
        if n:
            name_dd[n] = max(name_dd.get(n, 0), d)
    of_key = {k: frozenset(ks) for g, ks in mem.items() for k in ks}
    return name_dd, of_key, dd, nm, mem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--show-top", type=int, default=10)
    a = ap.parse_args()
    p = (lambda x: x if os.path.isabs(x) else os.path.join(ROOT, x))
    b_dir, a_dir = p(a.before), p(a.after)
    cont = continuous_abbrs()
    print("运行时「连续编卷」缩写（merge 会零化其年槽）：%s" % ",".join(sorted(cont)))

    b_name, b_of, b_dd, b_nm, b_mem = load(b_dir)
    a_name, a_of, a_dd, a_nm, a_mem = load(a_dir)
    print("组数：before %d  after %d" % (len(b_dd), len(a_dd)))

    common = set(b_name) & set(a_name)
    down = [n for n in common if a_name[n] < b_name[n]]
    up = [n for n in common if a_name[n] > b_name[n]]
    print("\n【1】按案名比较最大组 dd（共同案名 %d）" % len(common))
    print("  下降 **%d** 个（原本 dd>=5 的 %d 个），合计少 **%d**"
          % (len(down), sum(1 for n in down if b_name[n] >= 5),
             sum(b_name[n] - a_name[n] for n in down)))
    print("  上升 %d 个，合计多 %d；只在前 %d / 只在后 %d"
          % (len(up), sum(a_name[n] - b_name[n] for n in up),
             len(set(b_name) - set(a_name)), len(set(a_name) - set(b_name))))
    for n in sorted(down, key=lambda n: a_name[n] - b_name[n])[:a.show_top]:
        print("    %-32s %5d → %-5d（−%d）" % (n[:32], b_name[n], a_name[n],
                                               b_name[n] - a_name[n]))

    def iso(mem):
        A = B = 0
        for g, ks in mem.items():
            if all(not year_of_key(k) for k in ks):
                B += 1
                if all(abbr_of(k) in cont for k in ks):
                    A += 1
        return A, B

    def named_kept(mem, nm, dd, only_cont):
        return sum(1 for g, ks in mem.items()
                   if all(not year_of_key(k) for k in ks)
                   and (not only_cont or all(abbr_of(k) in cont for k in ks))
                   and (nm.get(g) or "") and dd.get(g, 0) >= 5)

    bA, bB = iso(b_mem)
    aA, aB = iso(a_mem)
    print("\n【2】孤立组（全成员键年槽为空）")
    print("  口径 A（且全为连续编卷）：before %d → after %d" % (bA, aA))
    print("  口径 B（不限缩写）    ：before %d → after **%d**" % (bB, aB))
    print("  口径 B 中「有案名且 dd>=5」：before %d → after **%d**"
          % (named_kept(b_mem, b_nm, b_dd, False),
             named_kept(a_mem, a_nm, a_dd, False)))

    seen, seps, cont_side = set(), 0, 0
    pair_counter = Counter()
    for k in set(b_of) & set(a_of):
        for l in b_of[k] - a_of[k]:
            pr = tuple(sorted((k, l)))
            if pr in seen:
                continue
            seen.add(pr)
            seps += 1
            ak, al = abbr_of(k), abbr_of(l)
            if (not year_of_key(k) and ak in cont) or \
               (not year_of_key(l) and al in cont):
                cont_side += 1
            pair_counter[(ak, al)] += 1
    print("\n【3】分离成因：前一轮同组、后一轮不同组的成员对")
    print("  共 **%d** 对；其中至少一侧是「年槽空的连续编卷键」：**%d（%.1f%%）**"
          % (seps, cont_side, 100.0 * cont_side / max(seps, 1)))
    for (x, y), v in pair_counter.most_common(12):
        print("    %-8s × %-8s %6d" % (x, y, v))


if __name__ == "__main__":
    main()
