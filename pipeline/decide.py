# -*- coding: utf-8 -*-
"""decide.py — 裁定层（规格 §10）

唯一需要「先知道这是哪个案子」才能做判断的层，因此排在归并之后。四件事：

  §10.2 案件级来源判定  —— 查 case_origin.csv，**在成员串级别查，不在归并组级别查**
  §10.3 平行汇编合并    —— nk(案名) 相等 且 年份相差 <= 1（同一案件被多个 reporter 收录）
  §10.4 同名异案拆分    —— 名称相同、年份跨度大、各刊于不同 reporter
  §10.6 跨法院合并      —— 各院内部裁定跑完后，再用 §10.3 同一套逻辑跑一次

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
    <output>/decided.csv       归并层字段 + §10.7 的六列
    <output>/decision_ids.csv  按裁定后的组 id 重新组织，供跨法院轮再取并集
    <output>/manifest.json     参数与各项计数（约束九）

**不回改归并层的输出文件**（§10.5 的不可变日志模式）：归并层的输出是历史记录，
本层的输出是当前最佳判断。既保持单向性（约束六），又给下游纠正能力。

两处规格未定义、由实现补的决定（均须人复核）

  一、**dd 必须取真并集，不能相加**。§10.6 说「取双方并集（判决 id 带法院前缀，
    天然唯一）」——这话只对**跨法院**成立。§10.3 的平行汇编合并在**院内**进行，
    同一份判决常同时引用中立引用与汇编引用两种写法，相加就是重复计数。
    实测虚高 62~90%：R. v. Lacasse 相加 702 / 真并集 370，Housen 690/425，
    Sattva 601/322，R. v. Grant 520/282。而 dd 正是选取层（§11.1）唯一的门槛
    判据。故本层读 merge 层新增的 decision_ids.csv 取真并集。
    **occurrence_count 则相加**——它数的是「提及次数」，一份判决同时引用两种
    写法就是两次提及，相加正确。

  二、组内聚合后 occurrence_count / distinct_decisions_count **写在组内每一行上**
    （不是只写在代表行上）。理由：选取层按 dd 过门槛，任何一行被单独读到时都
    必须给出正确答案，否则同一个案子的两条平行引证会各自独立过门槛。
    is_primary 只标「展示时取哪一行」，不承担计数职责。
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

NEW_COLUMNS = ["case_origin", "deciding_court", "merged_group_id",
               "is_primary", "split_flag", "split_seq"]


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


def group_by_name_and_year(rows):
    """§10.3：nk(案名) 相等 且 年份相差 <= 1。年份用**接近**而非相等，因为不同
    reporter 的出版年份常相差一年。传递闭包：A~B、B~C 则 A、B、C 同组。

    无案名的行不参与合并（没有判同的依据），各自独立成组。
    """
    buckets = defaultdict(list)
    singles = []
    for r in rows:
        name = nk(r.get("case_name_modal") or "")
        y = year_of(r["merge_key"])
        if name and y is not None:
            buckets[name].append((y, r))
        else:
            singles.append([r])

    groups = list(singles)
    for name in sorted(buckets):
        items = sorted(buckets[name], key=lambda t: (t[0], t[1]["merge_key"]))
        cur = [items[0][1]]
        cur_y = items[0][0]
        for y, r in items[1:]:
            if y - cur_y <= 1:              # 与**前一个**比：传递闭包
                cur.append(r)
            else:
                groups.append(cur)
                cur = [r]
            cur_y = y
        groups.append(cur)
    return groups


def needs_split(members):
    """§10.4 同名异案拆分。典型场景是同名的多份 Attorney-General Reference：
    名称相同、年份跨度大、刊载于不同 reporter。"""
    if len(members) < 2:
        return False
    abbrs = {m.get("abbreviation") or "" for m in members}
    years = [y for y in (year_of(m["merge_key"]) for m in members) if y is not None]
    return len(abbrs) == len(members) and bool(years) and (max(years) - min(years)) > 1


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


def load_decision_ids(paths):
    idx = defaultdict(set)
    for p in paths:
        with open(p, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                idx[r["merge_key"]].add(r["source_decision_citation"])
    return idx


def adjudicate(rows, did_idx, origin_idx, folded_idx, prefix, stats,
               key_field="merge_key", redo_origin=True):
    """key_field：查 decision_ids 用哪个字段。跨法院轮用上一轮的 merged_group_id，
    但**年份始终从原始 merge_key 解析**——组 id 里没有年份，覆盖 merge_key 会让
    §10.3 的判同条件失效（首版就是这么写的，跨法院合并数为 0）。"""
    groups = group_by_name_and_year(rows)
    groups.sort(key=lambda g: min(m["merge_key"] for m in g))

    out, out_ids = [], []
    gseq = 0
    for members in groups:
        split = needs_split(members)
        if split:
            stats["groups_split_same_name"] += 1
            partitions = [[m] for m in members]      # 拆回各自独立
        else:
            partitions = [members]
            if len(members) > 1:
                stats["groups_merged_parallel"] += 1

        for si, part in enumerate(partitions):
            gid = "%s-G%06d" % (prefix, gseq)
            gseq += 1
            # dd 取真并集（不能相加，见文件头）；occurrence 相加（提及次数）
            ids = set()
            for m in part:
                ids |= did_idx.get(m[key_field], set())
            occ = sum(int(m["occurrence_count"]) for m in part)
            dd = len(ids)
            primary = max(part, key=lambda m: (int(m["occurrence_count"]),
                                               [-ord(c) for c in m["merge_key"]]))
            for m in part:
                r = dict(m)
                if redo_origin:
                    member_strings = folded_idx.get(m["merge_key"],
                                                    [m["canonical_string"]])
                    decide_case_origin(r, member_strings, origin_idx, stats)
                # 跨法院轮不重判来源地：院内轮已在成员串级别查过表，此处只有
                # canonical_string 可用，重判等于用更弱的证据覆盖更强的结论
                r["merged_group_id"] = gid
                r["is_primary"] = "true" if m is primary else "false"
                r["split_flag"] = "true" if split else "false"
                r["split_seq"] = si if split else ""
                r["occurrence_count"] = occ
                r["distinct_decisions_count"] = dd
                out.append(r)
            for did in sorted(ids):
                out_ids.append({"merge_key": gid, "source_decision_citation": did})
    stats["groups_out"] = gseq
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
        rows = []
        for p in a.inputs:
            rows.extend(read_csv(p))
        did_paths = [os.path.join(os.path.dirname(p), "decision_ids.csv")
                     for p in a.inputs]
        did_idx = load_decision_ids(did_paths)
        folded_idx = {}
        prefix, label = "XC", "cross_court"
    else:
        rows = read_csv(a.input)
        did_idx = load_decision_ids([a.decision_ids])
        folded_idx = defaultdict(list)
        for r in read_csv(a.folded_log):
            folded_idx[r["merge_key"]].append(r["raw_string"])
        prefix, label = a.court, a.court

    stats["input_rows"] = len(rows)
    out, out_ids = adjudicate(
        rows, did_idx, origin_idx, folded_idx, prefix, stats,
        key_field="merged_group_id" if a.cross_court else "merge_key",
        redo_origin=not a.cross_court)
    stats["output_rows"] = len(out)
    stats["decision_id_rows"] = len(out_ids)

    # 不变量：不删行（约束五）；组内 dd 不得超过组内 occurrence
    assert len(out) == len(rows), "不变量破：行数 %d != 输入 %d" % (len(out), len(rows))
    assert all(int(r["distinct_decisions_count"]) <= int(r["occurrence_count"])
               for r in out), "不变量破：dd 大于 occurrence，说明取了相加"

    os.makedirs(a.output, exist_ok=True)
    fields = [c for c in out[0].keys()] if out else []
    for name, flds, data in (("decided.csv", fields, out),
                             ("decision_ids.csv",
                              ["merge_key", "source_decision_citation"], out_ids)):
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
        "stats": dict(sorted(stats.items())),
    }
    with open(os.path.join(a.output, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    print("%s  %d rows -> %d groups -> %s" % (label, len(rows), stats["groups_out"], a.output))
    for k, v in sorted(stats.items()):
        print("   %-32s %d" % (k, v))


if __name__ == "__main__":
    main()
