# -*- coding: utf-8 -*-
"""merge.py — 归并层（规格 §9）

跨行统计。**只做计数和投票，不判断，不查任何表。**本层不加载 decisions/ 下的
任何文件——这是与分类层的分界线。

用法
    python pipeline/merge.py --court SCC  --input data/classify_out/SCC/classified.csv  --output data/merge_out/SCC
    python pipeline/merge.py --court ONCA --input data/classify_out/ONCA/classified.csv --output data/merge_out/ONCA

输出
    <output>/merged.csv      主表，列见 §9.5
    <output>/folded_log.csv  折叠日志：每个归并键吞并了哪些原始写法（§9.5）
    <output>/manifest.json   参数与各项计数（约束九：数字须可重放）

三条不变量（写表前断言，不过就拒绝写）
    1. 每个键的 folded_log 计数之和 == 该键的 occurrence_count
    2. distinct_decisions_count 是**并集基数**，既不是各变体取最大值（旧管线的
       bug），也不是相加（重复计数）
    3. 行数守恒：merged 各键的成员数之和 == 输入行数（约束五：不删行）

一处规格未定义、由实现补的决定（须人复核）
    归并键用 nk(abbreviation)，故 FC 与 F.C. 同键、会进同一组，但二者在分类层
    可能得到不同的 citation_kind / jurisdiction（实测 SCC 12.6 万组中 3 组如此，
    典型是 2002 SCC 79 判 CA、[2002] S.C.C. 79 按 PROBLEMS #36 撤回判 UNSUPPORTED）。
    §9.5 的列清单要求每个键给出单值，但规格没说取谁。
    **本实现：按计数行取众数；平票时取 canonical_string 所在行的值**（确定性、
    只用组内数据、不新增列）。不一致的组数报进 manifest，不静默。
    本层不做裁决——真正的处置属裁定层（§10）的职责。
"""
import argparse
import csv
import datetime
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import nk                                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MERGED_FIELDS = ["merge_key", "canonical_string", "abbreviation", "citation_kind",
                 "jurisdiction", "jurisdiction_confidence", "case_name_modal",
                 "occurrence_count", "distinct_decisions_count",
                 "case_name_agreement", "variants_count",
                 "candidates_admitted", "candidates_rejected"]

FOLDED_FIELDS = ["merge_key", "raw_string", "count", "distinct_decisions_count"]


def build_merge_key(row):
    """§9.1：用结构化字段拼接，不对整条原始串做字符级压平。

    卷号缺失时**留空位而不是省略字段**——1978||ac||728 与 1978|1|ac||728 仍是
    两个不同的键。二者是否应视为同一引证（卷号缺失时的宽松匹配）是未决设计问题
    （PROBLEMS #2），本版按严格匹配处理，不做猜测性合并。
    """
    year = row.get("year_start") or ""
    vol = row.get("vol") or ""
    abbr = nk(row.get("abbreviation") or "")
    series = (row.get("series") or "").lower()
    page = row.get("page") or ""
    return "%s|%s|%s|%s|%s" % (year, vol, abbr, series, page)


def modal(values, tiebreak):
    """众数；平票时取 tiebreak 给出的值（若它在候选内），否则取字典序最小者
    —— 必须确定性，不能依赖 dict 插入序。"""
    if not values:
        return ""
    cnt = Counter(values)
    top = max(cnt.values())
    winners = sorted(v for v, c in cnt.items() if c == top)
    if len(winners) == 1:
        return winners[0]
    return tiebreak if tiebreak in winners else winners[0]


class Group(object):
    __slots__ = ("rows",)

    def __init__(self):
        self.rows = []


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--court", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    stats = Counter()
    groups = defaultdict(list)

    with open(args.input, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            stats["input_rows"] += 1
            groups[build_merge_key(row)].append((
                row.get("raw_string") or "",
                row.get("source_decision_citation") or "",
                row.get("source_decision_year") or "",
                row.get("rejected_reason") or "",
                row.get("name_rejected_reason") or "",
                row.get("candidate_case_name") or "",
                row.get("abbreviation") or "",
                row.get("citation_kind") or "",
                row.get("jurisdiction") or "",
                row.get("jurisdiction_confidence") or "",
            ))

    merged, folded = [], []
    member_total = 0

    for key in sorted(groups):
        members = groups[key]
        member_total += len(members)

        # canonical_string：组内出现频次最高的 raw_string（§9.1，仅作展示用途）
        raw_cnt = Counter(m[0] for m in members)
        top = max(raw_cnt.values())
        canonical = sorted(r for r, c in raw_cnt.items() if c == top)[0]

        # §9.2 计数：只排除行级误报，不排除仅仅切不出案名的行
        counted = [m for m in members if not m[3]]
        occurrence = len(counted)
        # 并集基数 —— 不是各变体取最大值（旧管线 bug），也不是相加
        dd = len({m[1] for m in counted})

        # §9.3 案名众数投票：行级误报与切不出案名的行都排除
        valid = [m for m in counted if not m[4] and m[5]]
        if valid:
            name_cnt = Counter(m[5] for m in valid)
            recent = {}
            for m in valid:
                y = int(m[2]) if (m[2] or "").isdigit() else 0
                recent[m[5]] = max(recent.get(m[5], 0), y)
            # 排序键（出现次数，最近出现年份）：票数相同时取更近期的写法
            name_modal = max(sorted(name_cnt.items()),
                             key=lambda kv: (kv[1], recent[kv[0]]))[0]
            agreement = round(name_cnt[name_modal] / len(valid), 2)
            variants = len(name_cnt)
        else:
            name_modal, agreement, variants = "", 0.0, 0

        # §9.4 质量列：只输出，本层不用它们筛任何行
        base = counted or members
        admitted = sum(1 for m in base if m[5])
        rejected = sum(1 for m in base if m[4])

        # 组内单值字段：按计数行取众数，平票取 canonical 所在行的值
        canon_row = next(m for m in members if m[0] == canonical)
        if len({m[7] for m in counted}) > 1 or len({m[8] for m in counted}) > 1:
            stats["groups_with_internal_disagreement"] += 1
        pick = counted or members
        merged.append({
            "merge_key": key,
            "canonical_string": canonical,
            "abbreviation": modal([m[6] for m in pick], canon_row[6]),
            "citation_kind": modal([m[7] for m in pick], canon_row[7]),
            "jurisdiction": modal([m[8] for m in pick], canon_row[8]),
            "jurisdiction_confidence": modal([m[9] for m in pick], canon_row[9]),
            "case_name_modal": name_modal,
            "occurrence_count": occurrence,
            "distinct_decisions_count": dd,
            "case_name_agreement": agreement,
            "variants_count": variants,
            "candidates_admitted": admitted,
            "candidates_rejected": rejected,
        })

        # 折叠日志：**全部**印刷变体都登记（含计数为 0 的），回答「这个键吞并了
        # 哪些写法」；count 只数计数行，故其组内之和恒等于 occurrence_count
        per_raw = defaultdict(list)
        for m in members:
            per_raw[m[0]].append(m)
        for raw in sorted(per_raw):
            c = [m for m in per_raw[raw] if not m[3]]
            folded.append({"merge_key": key, "raw_string": raw,
                           "count": len(c),
                           "distinct_decisions_count": len({m[1] for m in c})})

        stats["occurrence_total"] += occurrence
        if occurrence == 0:
            stats["groups_all_rejected"] += 1

    stats["merge_keys"] = len(merged)
    stats["folded_rows"] = len(folded)

    # ---- 三条不变量，不过就拒绝写表 ----
    by_key_occ = {m["merge_key"]: m["occurrence_count"] for m in merged}
    fsum = Counter()
    for r in folded:
        fsum[r["merge_key"]] += r["count"]
    bad = [k for k, v in by_key_occ.items() if fsum[k] != v]
    assert not bad, "不变量1 破：folded 计数之和 != occurrence_count，键 %r" % bad[:5]
    assert member_total == stats["input_rows"], \
        "不变量3 破：成员数之和 %d != 输入行数 %d（约束五）" % (member_total, stats["input_rows"])
    assert all(m["distinct_decisions_count"] <= m["occurrence_count"] for m in merged), \
        "不变量2 破：dd 大于 occurrence，说明取了相加而非并集"

    os.makedirs(args.output, exist_ok=True)
    for name, fields, rows in (("merged.csv", MERGED_FIELDS, merged),
                               ("folded_log.csv", FOLDED_FIELDS, folded)):
        path = os.path.join(args.output, name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, path)

    manifest = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "court": args.court,
        "input": os.path.relpath(args.input, ROOT).replace("\\", "/"),
        "spec_section": "9",
        "stats": dict(sorted(stats.items())),
    }
    with open(os.path.join(args.output, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    print("court=%s  %d rows -> %d merge keys -> %s"
          % (args.court, stats["input_rows"], len(merged), args.output))
    for k, v in sorted(stats.items()):
        print("   %-34s %d" % (k, v))


if __name__ == "__main__":
    main()
