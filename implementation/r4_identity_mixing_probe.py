# -*- coding: utf-8 -*-
"""R4 Stage 1 探针（只读）：测量 r3e 上两个「身份混合」机制的规模。

机制 (a)（B12）：单锚簇无条件吸收不同实例的判决。
  split_by_decision 在 len(decisions)<2 时让**所有非 identifier 成员**无条件搭车
  （decide.py 原 line 606）。典型：语料 SCC 判决（self-citation 锚）吸收它的
  枢密院上诉（A.C./App. Cas. 印刷形，年份=判决年+1）——两件不同判决并成一组。

机制 (b)：
  (b)(i)  键合并后键级案名众数翻转（|155|ccc|3d|97 Sawyer→Pan）——
          以「同一键在 r2i 与 r3e 的 case_name_modal 不同」计。
  (b)(ii) 无年自印形式成为自己的锚（Osolin 68→61+7）——
          以「年槽为空但 self_citation_of 非空的锚」计。

同时测算**拟议最小规则**的爆炸半径：
  拟议规则（窄变体）：单锚簇中，`year_printed != 锚年份` 的搭车成员改走既有指派路径
  （法域相容 + 共引 cov ≥ BAR=0.8，min 归一），同年搭车者维持原状。
  → 对每个异年搭车成员算 cov，cov < BAR 即「会被拆出」。

用法：python implementation/r4_identity_mixing_probe.py [--run-dir …] [--before …]
"""

import argparse
import csv
import json
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAR = 0.8


def load(run):
    d = os.path.join(ROOT, run, "decide_out", "cross_court", "decided.csv")
    groups = defaultdict(list)
    with open(d, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            groups[r["merged_group_id"]].append(r)
    did = defaultdict(set)
    for court in ("SCC", "ONCA"):
        p = os.path.join(ROOT, run, "decide_out", court, "decision_ids.csv")
        for r in csv.DictReader(open(p, encoding="utf-8", newline="")):
            c, _, mk = (r["row_key"] or "").partition("|")
            did[(c, mk)].add(r["source_decision_citation"])
    return groups, did


def key_year(m):
    return (m.get("year_printed") or "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default="data/run_20260913_r3e")
    ap.add_argument("--before", default="data/run_20260913_r2i")
    a = ap.parse_args()
    rd = a.run_dir if os.path.isabs(a.run_dir) else os.path.join(ROOT, a.run_dir)
    groups, did = load(rd)

    # ---------- 机制 (a)：单锚簇 + 搭车者 ----------
    single_anchor_groups = 0
    riders_total = 0
    same_year_riders = 0
    diff_year_riders = 0
    would_split = 0
    would_split_dd = 0
    would_split_kept_groups = set()
    b12_groups = set()
    b12_riders = 0
    b12_would_split = 0
    examples = []
    zero_anchor_groups = 0
    no_anchor_riders = 0
    groups_with_riders = 0
    for g, ms in groups.items():
        keys = {}
        for m in ms:
            k = (m["court"], m["merge_key"])
            keys.setdefault(k, m)
        anchors = {k: m for k, m in keys.items()
                   if m.get("citation_kind") == "neutral"
                   or (m.get("self_citation_of") or "").strip()}
        riders = [m for k, m in keys.items() if k not in anchors]
        if not riders:
            continue
        groups_with_riders += 1
        if not anchors:
            zero_anchor_groups += 1
            no_anchor_riders += len(riders)
            continue
        if len(anchors) > 1:
            continue                      # 多锚：split_by_decision 已按决策拆分
        single_anchor_groups += 1
        am = next(iter(anchors.values()))
        a_key = next(iter(anchors))
        a_dec = set()
        for m in anchors.values():
            a_dec |= did.get((m["court"], m["merge_key"]), set())
        a_year = key_year(am)
        for m in riders:
            riders_total += 1
            ry = key_year(m)
            ids = did.get((m["court"], m["merge_key"]), set())
            cov = (len(ids & a_dec) / min(len(ids), len(a_dec))
                   if ids and a_dec else 0.0)
            if ry == a_year:
                same_year_riders += 1
                continue
            diff_year_riders += 1
            dd = int(m.get("distinct_decisions_count") or 0)
            foreign = m.get("citation_kind") == "reporter" and \
                nk_(m.get("abbreviation")) in (
                    "ac", "appcas", "aller", "wlr", "kb", "qb", "ch", "chd",
                    "qbd", "er", "lrhl", "lrqb", "lrch", "chapp", "lrpc",
                    "us", "clr", "nzlr", "alr", "sct", "led", "f", "f2d", "f3d")
            is_b12 = foreign and a_year and ry and ry != a_year
            if is_b12:
                b12_groups.add(g)
                b12_riders += 1
            if cov < BAR:
                would_split += 1
                would_split_dd += dd
                would_split_kept_groups.add(g)
                if is_b12:
                    b12_would_split += 1
                if len(examples) < 12:
                    examples.append({
                        "group": g, "rider": m["merge_key"], "abbr":
                            m.get("abbreviation"), "rider_year": ry,
                        "anchor": a_key[1], "anchor_year": a_year,
                        "dd": dd, "cov": round(cov, 3), "kept": dd >= 5,
                        "foreign_mixed": is_b12})

    kept_groups = {g for g, ms in groups.items()
                   if any(int(m.get("distinct_decisions_count") or 0) >= 5
                          for m in ms)}
    print("=== 机制 (a)：单锚簇 + 搭车者（r3e） ===")
    print("  有搭车者的组 %d；其中单锚簇 %d（无锚簇 %d，另计）"
          % (groups_with_riders, single_anchor_groups, zero_anchor_groups))
    print("  搭车成员 %d：同年 %d / 异年 %d" % (riders_total, same_year_riders,
                                              diff_year_riders))
    print("  拟议窄规则（异年者改走 cov≥BAR 指派）：会被拆出 **%d** 个搭车成员、"
          "涉及 **%d** 组（kept 组 %d）；受影响 dd 合计 %d"
          % (would_split, len(would_split_kept_groups),
             len(would_split_kept_groups & kept_groups), would_split_dd))
    print("  B12 子集（外国混合汇编、异年搭车）：%d 组 / %d 个搭车成员，"
          "其中会被拆出 **%d**" % (len(b12_groups), b12_riders, b12_would_split))
    print("  会拆出的样例：")
    for e in examples:
        print("    ", e)

    # ---------- 机制 (b)(ii)：无年自印锚 ----------
    undated_self_anchor_groups = 0
    undated_self_anchor_examples = []
    for g, ms in groups.items():
        hit = [m for m in ms
               if not key_year(m) and (m.get("self_citation_of") or "").strip()]
        if hit:
            undated_self_anchor_groups += 1
            if len(undated_self_anchor_examples) < 6:
                undated_self_anchor_examples.append(
                    {"group": g, "dd": ms[0]["distinct_decisions_count"],
                     "key": hit[0]["merge_key"],
                     "self": hit[0].get("self_citation_of")})
    print("\n=== 机制 (b)(ii)：无年自印形式成为自己的锚 ===")
    print("  组数 %d" % undated_self_anchor_groups)
    for e in undated_self_anchor_examples:
        print("    ", e)

    # ---------- 机制 (b)(i)：键级案名翻转（跨 run 同键直接比，不经组号） ----------
    b_groups, _ = load(a.before if os.path.isabs(a.before)
                       else os.path.join(ROOT, a.before))
    b_name_by_key = {}
    for ms in b_groups.values():
        for m in ms:
            b_name_by_key[(m["court"], m["merge_key"])] = \
                (m.get("case_name_modal") or "")
    flips = 0
    flip_examples = []
    common_keys = 0
    for ms in groups.values():
        for m in ms:
            k = (m["court"], m["merge_key"])
            old = b_name_by_key.get(k)
            if old is None:
                continue
            common_keys += 1
            n1 = nk_(m.get("case_name_modal"))
            n2 = nk_(old)
            if n1 and n2 and n1 != n2:
                flips += 1
                if len(flip_examples) < 6:
                    flip_examples.append({"key": m["merge_key"],
                                          "r3e": m.get("case_name_modal"),
                                          "r2i": old})
    print("\n=== 机制 (b)(i)：同键案名翻转（跨 run） ===")
    print("  两轮同键 %d 个；案名翻转 %d 个" % (common_keys, flips))
    for e in flip_examples:
        print("    ", e)

    out = {"single_anchor_groups": single_anchor_groups,
           "riders_total": riders_total,
           "same_year_riders": same_year_riders,
           "diff_year_riders": diff_year_riders,
           "would_split_riders": would_split,
           "would_split_dd": would_split_dd,
           "would_split_groups": len(would_split_kept_groups),
           "would_split_kept_groups":
               len(would_split_kept_groups & kept_groups),
           "b12_groups": len(b12_groups), "b12_riders": b12_riders,
           "b12_would_split": b12_would_split,
           "undated_self_anchor_groups": undated_self_anchor_groups,
           "name_flips": flips,
           "examples": examples}
    p = os.path.join(ROOT, "data", "coverage_out", "r4_identity_mixing_probe.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\nwritten:", os.path.relpath(p, ROOT))


def nk_(s):
    import re
    return re.sub(r"[^A-Za-z0-9]", "", (s or "")).lower()


if __name__ == "__main__":
    main()
