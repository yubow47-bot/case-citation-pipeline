# -*- coding: utf-8 -*-
"""decide.py — 裁定层（规格 §10）

唯一需要「先知道这是哪个案子」才能做判断的层，因此排在归并之后。四件事：

  §10.2 案件级来源判定  —— 查 case_origin.csv，**在成员串级别查，不在归并组级别查**
  §10.3 平行汇编合并    —— nk(案名) 相等 且 年份相差 <= 1（同一案件被多个 reporter 收录）
  §10.4 同名异案拆分    —— 两道：年份跨度 > 1 的链按 ±1 年窗口拆；窗口内含多个
                           不同判决（按中立引用识别）的，按判决拆
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
                               + split_reason（span / decision / unanchored 的组合）
    <output>/decision_ids.csv  **逐行**的判决 id（键 row_key = court|merge_key）
    <output>/manifest.json     参数与各项计数（约束九）

**不回改归并层的输出文件**（§10.5 的不可变日志模式）。

规格未定义、由实现补的决定（均须人复核，见 PROBLEMS #46/#47/#48/#49）

  一、**dd 取真并集，不能相加**（#46）。院内平行汇编合并时同一份判决常同时
    引用两种写法，相加虚高 62~90%。dd 是选取层唯一的门槛判据。

  二、**计数一律从行的原始计数重算，判决 id 逐行携带**（#47）。首版把组合计
    写到每一行上、跨法院轮又按行求和，occurrence 虚高 1.59 倍。守恒不变量
    （各组之和 == 各行原始计数之和）当时没写，写了的不等式反而更容易通过。

  三、**年份跨度 > 1 的链按 ±1 年窗口拆**（#48）。「相差 <= 1 年」做成传递
    闭包后，每年都有一件的常见案名一路串下去（R. v. Smith 2001-2023 共 93
    个成员成一组）。一件真实案子的平行引证不会跨出一年。

  四、**窗口内含多个不同判决的，按判决拆**（#49）。案名+年份判同分不开「同名
    当事人的不同判决」（R. v. Oland 的 2017 SCC 17 与 2018 NBQB 255、Vavilov
    的 2019 SCC 65 与一件 2020 ONCA）。判决的身份是它的中立引用：
      · 不同法院的中立引用 —— 必是不同判决（一件判决只属一个法院）
      · 同年同号、法域相同 —— 同一判决的双语代码（SCC/CSC、FC/CF）
      · 同代码、号码错一位或年份错一年、**且被引判决数不超过对方一半** ——
        笔误变体，并入对方（笔误天然比正确写法罕见；R. v. MacKay 2005 SCC
        75/79 引用量 4 对 3，不满足，保留分开——错也错在分开这个安全方向）
      · 其余 —— 不同判决（Wewaykum 2002 SCC 79 本案与 2003 SCC 45 回避申请）
    没有中立引用的行（汇编引证等）按**共引**分派：判决书惯例把平行引证挨着印
    （Name, 2017 SCC 17, [2017] 1 S.C.R. 250），这是印在纸上的事实。三条规则：
      · **同一印刷串同进同出**：同 merge_key 的行（来自两院）先并成一个单元、
        合并判决 id 再分派。判决 id 带法院前缀，两院同串行之间共引恒为 0，
        分开处理会把一件判决撕成两半（审计实测 Gladue 的 [1999] 1 S.C.R. 688
        裂成 dd 94 与 47）
      · **先按法域筛，再比共引**：只在与汇编法域相容的判决里挑。首版先挑共引
        最高者、再用法域否决，[2010] 3 S.C.R. 62（Imoro）因共引最高的是下级
        判决而被否决进待定，明明组里有相容的 2010 SCC 50
      · **重合系数 >= 0.8 才分派**（重合系数 = 共引判决数 / 两边中较少被引的
        那一边），过门槛的判决里取共引最多者。含义是「较少被引的那种写法几乎
        总与另一种一起印」。门槛依据：待定审计（以本单元为分母）实测覆盖率
        双峰——要么 0、要么 >= 0.8，中间几乎为空，取 0.5 或 0.8 只差 6 条。
        首版以本单元为分母，汇编是主流写法时先天过不了门槛（Wewaykum 的
        [2003] 2 S.C.R. 259 被 46 份判决引、其中立引用只 34 份，最高 0.74），
        且与下方拼组用的「较小集」口径不一致，故统一为较小集。
        膨胀面：本单元不比目标大时，一次分派最多新增本单元 20% 的被引判决，
        dd-1 的单元一个也加不进去；本单元更大时（汇编是主流写法），新增的
        正是这件判决本该有的引用——此时的风险类是「法域未知、无闸可拦的大
        单元」，manifest 单独计数（units_assigned_larger_than_target_unknown_jur）
      · **平票以印刷年份定归**：两个相容判决共引持平时，归年份与本单元相同的
        那个（平行汇编的年份与中立引用同年）。Wewaykum 的 [2003] 2 S.C.R. 259
        与 2002 SCC 79、2003 SCC 45 共引持平，年份定归后者
    共引**不用于**判两个中立引用是否同一判决：一审与上诉审同样总被一起引用
    （Pearson v. Boliden 的 2001 BCSC 1054 与 2002 BCCA 624 共引覆盖 100%）。
    分不下去的单元**不硬塞**，彼此按同一标准（重合 >= 0.8×较小集、法域相容）
    连边拼组、标 unanchored（无中立锚）——这就是那件没有中立引用的判决本身（1999 年前的最高
    法院判决全无中立引用，Gladue、Ewanchuk 皆是）。约束四：无证据不给判定。
    已知残余：法域表把「最高法院专属汇编」（S.C.R.）与「全国性汇编」（D.L.R.、
    C.C.C.）都标 CA（PROBLEMS #40），全国性汇编刊登的省级判决可能被分给最高
    法院。预演实测此类暴露 61 条中 59 条是 S.C.R.（正确），C.C.C.、F.C.R. 各 1 条。
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


# ------------------------------------------------------------ §10.4 按判决拆分
def _neutral_parts(merge_key):
    p = merge_key.split("|")          # year|vol|abbr|series|page
    return p[0], p[2], p[3], p[4]


def _one_edit(a, b):
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    s, l = (a, b) if len(a) < len(b) else (b, a)
    return any(l[:i] + l[i + 1:] == s for i in range(len(l)))


def same_decision(ka, ja, dda, kb, jb, ddb):
    """中立引用 ka（较小者）是否与 kb 为同一判决。判据全看印出来的串本身。"""
    ya, ca, sa, na = _neutral_parts(ka)
    yb, cb, sb, nb = _neutral_parts(kb)
    if ya == yb and na == nb and sa == sb and ja and ja == jb:
        return True                      # 同一判决的双语代码（SCC/CSC、FC/CF…）
    if (ca, sa) != (cb, sb) or 2 * dda > ddb:
        return False                     # 笔误必定比正确写法罕见
    if ya == yb and _one_edit(na, nb):
        return True                      # 号码错一位
    if na == nb and ya.isdigit() and yb.isdigit() and abs(int(ya) - int(yb)) == 1:
        return True                      # 年份错一年
    return False


def decisions_of(members, did_idx):
    """把组内的中立引用归并成「判决」。返回 (root, anchor_ids, anchor_jur)。"""
    anc, ajur = defaultdict(set), {}
    for m in members:
        if m.get("citation_kind") == "neutral":
            anc[m["merge_key"]] |= did_idx.get(row_key(m), set())
            ajur[m["merge_key"]] = m.get("jurisdiction") or ""
    order = sorted(anc, key=lambda k: (-len(anc[k]), k))
    root = {}
    for i, k in enumerate(order):
        root[k] = k
        for big in order[:i]:
            if root[big] == big and same_decision(k, ajur[k], len(anc[k]),
                                                  big, ajur[big], len(anc[big])):
                root[k] = big
                break
    return root, anc, ajur


BAR = 0.8   # 「几乎总是一起印」。待定审计实测覆盖率双峰，取 0.5 或 0.8 只差 6 条


def _unknown(j):
    return j in ("", "UNSUPPORTED")


def _compatible(a, b):
    """None = 单元内法域自相矛盾，与谁都不相容；空串 = 未知，与谁都相容。"""
    if a is None or b is None:
        return False
    return not a or not b or a == b


def split_by_decision(members, did_idx, stats):
    root, anc, ajur = decisions_of(members, did_idx)
    stats["anchors_collapsed_as_variant"] += sum(1 for k, r in root.items() if k != r)
    decisions = sorted({root[k] for k in root}, key=lambda k: (-len(anc[k]), k))
    if len(decisions) < 2:
        return [(members, "")]
    stats["clusters_split_by_decision"] += 1

    dec_ids = defaultdict(set)
    for k, r in root.items():
        dec_ids[r] |= anc[k]
    buckets = {d: [] for d in decisions}
    units = defaultdict(list)          # 同一印刷串同进同出
    for m in members:
        if m.get("citation_kind") == "neutral":
            buckets[root[m["merge_key"]]].append(m)
        else:
            units[m["merge_key"]].append(m)

    pending = []                       # (rows, ids, jurisdiction)
    for mk in sorted(units):
        us = units[mk]
        ids = set()
        for m in us:
            ids |= did_idx.get(row_key(m), set())
        known = {m.get("jurisdiction") for m in us if not _unknown(m.get("jurisdiction") or "")}
        if len(known) > 1:
            stats["units_unanchored_jurisdiction_disagree"] += 1
            pending.append((us, ids, None))
            continue
        uj = next(iter(known)) if known else ""
        ov = {d: len(ids & dec_ids[d]) for d in decisions}
        cov = {d: (ov[d] / min(len(ids), len(dec_ids[d]))
                   if ids and dec_ids[d] else 0.0) for d in decisions}
        good = sorted((d for d in decisions if _compatible(uj, ajur[d]) and cov[d] >= BAR),
                      key=lambda d: (-ov[d], d))
        target = None
        if len(good) == 1 or (len(good) > 1 and ov[good[0]] > ov[good[1]]):
            target = good[0]
        elif len(good) > 1:
            top = [d for d in good if ov[d] == ov[good[0]]]
            same_year = [d for d in top if d.split("|", 1)[0] == mk.split("|", 1)[0]]
            if len(same_year) == 1:
                target = same_year[0]
                stats["units_tie_broken_by_year"] += 1
        if target is not None:
            buckets[target].extend(us)
            stats["units_assigned_by_cocitation"] += 1
            stats["dd_added_by_assignment"] += len(ids - dec_ids[target])
            if len(ids) > len(dec_ids[target]):
                stats["units_assigned_larger_than_target"] += 1
                if not uj:
                    stats["units_assigned_larger_than_target_unknown_jur"] += 1
        else:
            if len(good) > 1:
                stats["units_unanchored_tie"] += 1
            elif any(cov[d] >= BAR for d in decisions):
                stats["units_unanchored_incompatible_only"] += 1
            else:
                stats["units_unanchored_weak_cocitation"] += 1
            pending.append((us, ids, uj))

    # 分不下去的单元彼此按同一标准拼组：它们是那件没有中立引用的判决本身
    n = len(pending)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if not _compatible(pending[i][2], pending[j][2]):
                continue
            a, b = pending[i][1], pending[j][1]
            small = min(len(a), len(b))
            if small and len(a & b) >= BAR * small:
                parent[find(i)] = find(j)
    comps = defaultdict(list)
    for i in range(n):
        comps[find(i)].append(i)
    pend_groups = [[m for i in c for m in pending[i][0]]
                   for c in sorted(comps.values(),
                                   key=lambda c: min(pending[i][0][0]["merge_key"] for i in c))]
    stats["rows_unanchored"] += sum(len(p[0]) for p in pending)
    stats["unanchored_groups"] += len(pend_groups)
    return ([(buckets[d], "decision") for d in decisions] +
            [(g, "decision;unanchored") for g in pend_groups])


# ------------------------------------------------------------ §10.3 + §10.4
def cluster_same_case(rows, did_idx, stats):
    """返回 [(members, split_reason, split_seq)]；split_reason 为空表示未拆。
    无案名或无年份的行不参与合并（没有判同的依据），各自独立成组。"""
    buckets, out = defaultdict(list), []
    for r in rows:
        name = nk(r.get("case_name_modal") or "")
        y = year_of(r["merge_key"])
        if name and y is not None:
            buckets[name].append((y, r))
        else:
            out.append(([r], "", ""))

    for name in sorted(buckets):
        items = sorted(buckets[name], key=lambda t: (t[0], row_key(t[1])))
        chains, cur = [], [items[0]]
        for it in items[1:]:                 # §10.3：与前一个比相差 <= 1 年即连上
            if it[0] - cur[-1][0] <= 1:
                cur.append(it)
            else:
                chains.append(cur)
                cur = [it]
        chains.append(cur)

        for ch in chains:
            if ch[-1][0] - ch[0][0] <= 1:
                parts = [([r for _, r in ch], "")]
            else:
                stats["chains_split_by_span"] += 1
                parts = [([r for _, r in p], "span") for p in windows(ch)]
            seq = 0
            for rows_, r0 in parts:
                for sub, r1 in split_by_decision(rows_, did_idx, stats):
                    reason = ";".join(x for x in (r0, r1) if x)
                    if reason:
                        out.append((sub, reason, seq))
                        seq += 1
                    else:
                        out.append((sub, "", ""))
                        if len(sub) > 1:
                            stats["groups_merged_parallel"] += 1
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
    clusters = cluster_same_case(rows, did_idx, stats)
    clusters.sort(key=lambda c: min(row_key(m) for m in c[0]))

    out, out_ids = [], []
    for gseq, (members, reason, seq) in enumerate(clusters):
        gid = "%s-G%06d" % (prefix, gseq)
        ids = set()
        for m in members:
            ids |= did_idx.get(row_key(m), set())
        occ = sum(key_occ(m) for m in members)
        primary = min(members, key=lambda m: (-key_occ(m), row_key(m)))

        # 上界计数（不是判定，混着笔误变体与双语代码，见 PROBLEMS #49）
        if len({m["merge_key"] for m in members
                if m.get("citation_kind") == "neutral"}) > 1:
            stats["groups_with_multiple_neutral_strings"] += 1

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
            r["split_flag"] = "true" if reason else "false"
            r["split_seq"] = seq
            r["split_reason"] = reason
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
    groups = defaultdict(list)
    for r in out:
        groups[r["merged_group_id"]].append(r)
    assert sum(int(ms[0]["occurrence_count"]) for ms in groups.values()) == in_occ_total, \
        "守恒破：各组 occurrence 之和 != 各行原始计数之和 %d（重复累加？）" % in_occ_total
    assert all(int(r["distinct_decisions_count"]) <= int(r["occurrence_count"])
               for r in out), "dd 大于 occurrence，说明取了相加"
    wide = [g for g, ms in groups.items()
            if len({year_of(m["merge_key"]) for m in ms
                    if m.get("case_name_modal") and year_of(m["merge_key"])}) > 0
            and (lambda ys: max(ys) - min(ys))(
                [year_of(m["merge_key"]) for m in ms
                 if m.get("case_name_modal") and year_of(m["merge_key"])]) > 1]
    assert not wide, "有组的年份跨度 > 1：%r" % wide[:5]
    multi = [g for g, ms in groups.items()
             if len(set(decisions_of(ms, did_idx)[0].values())) > 1]
    assert not multi, "有组仍含多个不同判决：%r" % multi[:5]

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
