# -*- coding: utf-8 -*-
"""decide.py — 裁定层（规格 §10）

唯一需要「先知道这是哪个案子」才能做判断的层，因此排在归并之后。四件事：

  §10.2 案件级来源判定  —— 查 case_origin.csv，**在成员串级别查，不在归并组级别查**
  §10.3 平行汇编合并    —— nk(案名) 相等 且 年份相差 <= 1（同一案件被多个 reporter 收录）
  §10.4 同名异案拆分    —— 链式合并串出的年份跨度 > 1 的组，按 ±1 年窗口拆开
  §10.6 跨法院合并      —— 各院内部裁定跑完后，再用同一套逻辑跑一次

用法
    # 院内
    python pipeline/decide.py --court SCC --input data/merge_out/SCC/merged.csv \
        --folded-log data/merge_out/SCC/folded_log.csv \
        --decision-ids data/merge_out/SCC/decision_ids.csv --output data/decide_out/SCC
    # 跨法院
    python pipeline/decide.py --cross-court \
        --inputs data/decide_out/SCC/decided.csv data/decide_out/ONCA/decided.csv \
        --output data/decide_out/cross_court

输出
    <output>/decided.csv       归并层字段 + court + key_occurrence_count + §10.7 的六列
    <output>/decision_ids.csv  **逐行**的判决 id（键 row_key = court|merge_key）
    <output>/manifest.json     参数与各项计数（约束九）

**不回改归并层的输出文件**（§10.5 的不可变日志模式）。

规格未定义、由实现补的决定（均须人复核，见 PROBLEMS #46/#47/#48）

  一、**dd 取真并集，不能相加**（#46）。§10.6「判决 id 带法院前缀，天然唯一」
    只对跨法院成立；院内平行汇编合并时同一份判决常同时引用两种写法，相加
    虚高 62~90%。dd 是选取层唯一的门槛判据。

  二、**计数一律从行的原始计数重算，判决 id 逐行携带**（#47）。首版院内轮把
    组合计值写到组内每一行上，跨法院轮又按行求和——每行都带着整组的数，
    于是被加了「组内行数」遍：跨法院 occurrence 总和虚高 1.59 倍（906,894
    vs 真值 570,671）。修法：key_occurrence_count 保留归并层给这一行的原始
    提及数，任何一轮的组合计都从它求和；判决 id 按 row_key 逐行存，组怎么
    切分都能精确取并集。**守恒不变量**：各组 occurrence 之和 == 各行原始计数
    之和——这一条首版没写，写了的「dd <= occurrence」反而因虚高更容易通过。

  三、**§10.4 的拆分条件放宽为「链的年份跨度 > 1」**（#48）。§10.3 的「相差
    <= 1 年」是两条引证之间的关系；做成链式传递闭包后，每年都有一件的常见
    案名会一路串下去（首版实测 R. v. Smith 2001-2023 共 93 个成员串成一个
    「案子」，R. v. Brown 66 个、R. v. Nguyen 54 个）。规格 §10.4 原条件要求
    「每个成员的汇编缩写都不同」，而这些成员共用 SCC/ONCA/C.C.C.，拆不开。
    一件真实案子的平行引证不会跨出一年，故跨度 > 1 的链必然连着不同的案子，
    按 ±1 年窗口切开，每段标 split_flag / split_seq，可追溯（§10.5）。
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
DECISIONS = os.path.join(ROOT, "decisions")


def load_case_origin():
    """空表不是故障（§13.4）。表空时全部落 UNDETERMINED，这是约束四要的行为。"""
    path = os.path.join(DECISIONS, "case_origin.csv")
    if not os.path.exists(path):
        return {}
    idx = {}
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            k = (r.get("normalized_key") or "").strip()
            if k:
                idx.setdefault(k, []).append(r)
    return idx


def year_of(merge_key):
    """归并键首字段即 year_start（§9.1）。merged.csv 没有独立年份列。"""
    head = merge_key.split("|", 1)[0]
    return int(head) if head.isdigit() else None


def row_key(r):
    """行的唯一身份。跨法院时 SCC 与 ONCA 可能各有一行同一个 merge_key，
    二者是两院判决里的不同提及，必须分开计。"""
    return "%s|%s" % (r["court"], r["merge_key"])


def key_occ(r):
    """这一行在归并层的原始提及数。首轮输入没有该列，取 occurrence_count。"""
    v = r.get("key_occurrence_count")
    return int(v) if v not in (None, "") else int(r["occurrence_count"])


def windows(items):
    """按 ±1 年窗口把已按年份排序的 (year, row) 切段，每段跨度 <= 1。"""
    parts, cur, start = [], [items[0]], items[0][0]
    for it in items[1:]:
        if it[0] - start <= 1:
            cur.append(it)
        else:
            parts.append(cur)
            cur, start = [it], it[0]
    parts.append(cur)
    return parts


def cluster_same_case(rows, stats):
    """§10.3 链式合并 + §10.4 跨度拆分。返回 [(members, split_flag, split_seq)]。

    无案名或无年份的行不参与合并（没有判同的依据），各自独立成组。
    """
    buckets, out = defaultdict(list), []
    for r in rows:
        name = nk(r.get("case_name_modal") or "")
        y = year_of(r["merge_key"])
        if name and y is not None:
            buckets[name].append((y, r))
        else:
            out.append(([r], False, ""))

    for name in sorted(buckets):
        items = sorted(buckets[name], key=lambda t: (t[0], row_key(t[1])))
        # §10.3：与**前一个**比相差 <= 1 年即连上（传递闭包）
        chains, cur = [], [items[0]]
        for it in items[1:]:
            if it[0] - cur[-1][0] <= 1:
                cur.append(it)
            else:
                chains.append(cur)
                cur = [it]
        chains.append(cur)

        for ch in chains:
            if ch[-1][0] - ch[0][0] <= 1:
                out.append(([r for _, r in ch], False, ""))
                if len(ch) > 1:
                    stats["groups_merged_parallel"] += 1
            else:
                # §10.4（放宽）：跨度 > 1 的链必然连着不同的案子
                stats["chains_split_by_span"] += 1
                for i, p in enumerate(windows(ch)):
                    out.append(([r for _, r in p], True, i))
                    stats["split_parts"] += 1
    return out


def decide_case_origin(row, member_strings, origin_idx, stats):
    """§10.2：**在成员串级别查表**，不在归并组级别查。
    未入表时标 UNDETERMINED，**不得默认取 jurisdiction 的值**——默认二者相等
    正是旧管线把加拿大 JCPC 案系统性错标为英国案的同一个错误。"""
    hits = []
    for s in member_strings:
        h = origin_idx.get(nk(s))
        if h and len(h) == 1:
            hits.append(h[0])
    if not hits:
        row["case_origin"] = "UNDETERMINED"
        row["deciding_court"] = ""
    elif len({h["case_origin"] for h in hits}) == 1:
        row["case_origin"] = hits[0]["case_origin"]
        row["deciding_court"] = hits[0].get("deciding_court") or ""
        stats["case_origin_determined"] += 1
    else:
        # CONFLICT 是有用信号，不是异常：说明归并层把两个不同的案子合并了
        row["case_origin"] = "CONFLICT"
        row["deciding_court"] = ""
        stats["case_origin_conflict"] += 1


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_decision_ids(path, court=None):
    """归并层的文件以 merge_key 为键（需补 court 前缀）；本层输出的文件已是 row_key。"""
    idx = defaultdict(set)
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            k = r["row_key"] if "row_key" in r else "%s|%s" % (court, r["merge_key"])
            idx[k].add(r["source_decision_citation"])
    return idx


def adjudicate(rows, did_idx, origin_idx, folded_idx, prefix, stats, redo_origin):
    clusters = cluster_same_case(rows, stats)
    clusters.sort(key=lambda c: min(row_key(m) for m in c[0]))

    out, out_ids = [], []
    for gseq, (members, split, seq) in enumerate(clusters):
        gid = "%s-G%06d" % (prefix, gseq)
        ids = set()
        for m in members:
            ids |= did_idx.get(row_key(m), set())
        occ = sum(key_occ(m) for m in members)
        primary = min(members, key=lambda m: (-key_occ(m), row_key(m)))

        # 残余过度合并探测器——**上界，不是判定**：同组出现两个不同的中立引用串。
        # 自检实测它混着三类：同一引证的笔误/OCR 变体（2002 SCC 33 与 SCC 3）、
        # 双语代码（2014 SCC 7 与 2014 CSC 7）、真正的不同判决（同名当事人在
        # 不同法院的判决，2017 SCC 17 与 2018 NBQB 255）。只有第三类是过度合并，
        # 分类细数见 PROBLEMS #49。首版注释写成「必然是两件案子」，是 overclaim
        neutral_keys = {m["merge_key"] for m in members
                        if m.get("citation_kind") == "neutral"}
        if len(neutral_keys) > 1:
            stats["groups_with_multiple_neutral_citations"] += 1

        for m in members:
            r = dict(m)
            r["key_occurrence_count"] = key_occ(m)
            if redo_origin:
                decide_case_origin(r, folded_idx.get(m["merge_key"],
                                                     [m["canonical_string"]]),
                                   origin_idx, stats)
            # 跨法院轮不重判来源地：院内轮已在成员串级别查过表，此处只有
            # canonical_string 可用，重判等于用更弱的证据覆盖更强的结论
            r["merged_group_id"] = gid
            r["is_primary"] = "true" if m is primary else "false"
            r["split_flag"] = "true" if split else "false"
            r["split_seq"] = seq
            r["occurrence_count"] = occ
            r["distinct_decisions_count"] = len(ids)
            out.append(r)
            for did in sorted(did_idx.get(row_key(m), ())):
                out_ids.append({"row_key": row_key(m), "source_decision_citation": did})
    stats["groups_out"] = len(clusters)
    return out, out_ids


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--court")
    ap.add_argument("--input")
    ap.add_argument("--folded-log")
    ap.add_argument("--decision-ids")
    ap.add_argument("--cross-court", action="store_true")
    ap.add_argument("--inputs", nargs="+")
    ap.add_argument("--output", required=True)
    a = ap.parse_args()

    stats = Counter()
    origin_idx = load_case_origin()

    if a.cross_court:
        rows, did_idx = [], defaultdict(set)
        for p in a.inputs:
            rows.extend(read_csv(p))
            for k, v in load_decision_ids(
                    os.path.join(os.path.dirname(p), "decision_ids.csv")).items():
                did_idx[k] |= v
        folded_idx = {}
        prefix, label, redo = "XC", "cross_court", False
    else:
        rows = read_csv(a.input)
        for r in rows:
            r["court"] = a.court
        did_idx = load_decision_ids(a.decision_ids, court=a.court)
        folded_idx = defaultdict(list)
        for r in read_csv(a.folded_log):
            folded_idx[r["merge_key"]].append(r["raw_string"])
        prefix, label, redo = a.court, a.court, True

    stats["input_rows"] = len(rows)
    in_occ_total = sum(key_occ(r) for r in rows)
    out, out_ids = adjudicate(rows, did_idx, origin_idx, folded_idx,
                              prefix, stats, redo)
    stats["output_rows"] = len(out)
    stats["decision_id_rows"] = len(out_ids)

    # ---- 不变量，不过就拒绝写表 ----
    assert len(out) == len(rows), "行数 %d != 输入 %d（约束五）" % (len(out), len(rows))
    grp_occ = {}
    for r in out:
        grp_occ[r["merged_group_id"]] = int(r["occurrence_count"])
    assert sum(grp_occ.values()) == in_occ_total, \
        "守恒破：各组 occurrence 之和 %d != 各行原始计数之和 %d（重复累加？）" \
        % (sum(grp_occ.values()), in_occ_total)
    assert all(int(r["distinct_decisions_count"]) <= int(r["occurrence_count"])
               for r in out), "dd 大于 occurrence，说明取了相加"
    spans = defaultdict(list)
    for r in out:
        y = year_of(r["merge_key"])
        if y is not None and r.get("case_name_modal"):
            spans[r["merged_group_id"]].append(y)
    wide = [g for g, ys in spans.items() if max(ys) - min(ys) > 1]
    assert not wide, "有组的年份跨度 > 1：%r" % wide[:5]

    os.makedirs(a.output, exist_ok=True)
    fields = list(out[0].keys()) if out else []
    for name, flds, data in (("decided.csv", fields, out),
                             ("decision_ids.csv",
                              ["row_key", "source_decision_citation"], out_ids)):
        path = os.path.join(a.output, name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=flds, extrasaction="ignore")
            w.writeheader()
            w.writerows(data)
        os.replace(tmp, path)

    manifest = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "mode": "cross_court" if a.cross_court else "in_court",
        "label": label,
        "spec_section": "10",
        "case_origin_table_rows": sum(len(v) for v in origin_idx.values()),
        "occurrence_total": in_occ_total,
        "stats": dict(sorted(stats.items())),
    }
    with open(os.path.join(a.output, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    print("%s  %d rows -> %d groups -> %s" % (label, len(rows), stats["groups_out"], a.output))
    for k, v in sorted(stats.items()):
        print("   %-40s %d" % (k, v))


if __name__ == "__main__":
    main()
