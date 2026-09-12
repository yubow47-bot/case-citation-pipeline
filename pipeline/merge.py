# -*- coding: utf-8 -*-
"""merge.py — 归并层（规格 §9；candidates-2.0 路线加判决内重叠仲裁）

跨行统计。**不做跨判决的判断，不查任何法域表。**本层不加载 decisions/ 下的
任何文件——这是与分类层的分界线。

两条输入路线，按表头自动分派：
  * **candidates 路线**（表头含 candidate_id，candidates-2.0）：先做**判决内**
    重叠仲裁（同判决 = 同 (source_decision_citation, corpus_row_index)），再跨行
    聚合。仲裁规则（规格 §7 Stage 1 C）：
      - 同跨度同含义（同 merge_key）→ 只计一次；
      - 同跨度异含义 → 表证据唯一支持者胜出；证据相持或全无 → 整组
        span_alternative_undecided，全部不计（弃权，不硬猜）；
      - 结构性无效候选（rejected / 跨界解析且配对者有效）不进有效计数；
      - 表查不到不是结构错误——候选保留，进 undecided 或按他者让位；
      - 严格包含且共享字段相容（「3 All E.R. 12」⊂「3 All E.R. 12 (1968)」）→
        长者胜（containment-resolution 显式规则）；
      - 长候选横跨两条真引证 → 两条短候选可同时保留（重叠组不要求唯一赢家）；
        未打 D3 旗的部分重叠、字段不相容 → 双双 undecided，不硬选最长；
      - undecided 候选不得各自单独贡献 occurrence/dd；
      - 仲裁**绝不**回调 extract/classify。
  * **legacy 路线**（test_layers 迷你全链等既有输入，无 candidate_id 列）：
      与 v1.4 行为逐字一致（兼容钉住，约束五——既有测试期望值不动）。

用法
    python pipeline/merge.py --court SCC  --input data/classify_out/SCC/classified.csv  --output data/merge_out/SCC
    python pipeline/merge.py --court ONCA --input data/classify_out/ONCA/classified.csv --output data/merge_out/ONCA

candidates 路线输出
    <output>/merged.csv                主表（列同 §9.5），计数只含 counted 候选
    <output>/mentions_candidates.csv   逐候选仲裁台账：candidate_id → 仲裁状态/
                                       让位对象/注记（追溯主干，裁定层可回读）
    <output>/folded_log.csv            折叠日志（counted 行的印刷变体）
    <output>/decision_ids.csv          键 → 引用判决 id 并集（counted 行）
    <output>/manifest.json             参数与各项计数（约束九）

四条不变量（写表前断言，不过就拒绝写）
    1. 每个键 folded_log 计数之和 == 该键 occurrence_count
    2. distinct_decisions_count 是**并集基数**
    3. mentions_candidates.csv 行数 == 输入候选行数（约束五：不删候选）
    4. 每个键 decision_ids.csv 行数 == 该键 distinct_decisions_count

规格未定义、由实现补的决定（均须人复核）——legacy 路线的三条见 git 历史
（组内单值字段取众数、案名两级投票、第三个输出 decision_ids.csv），candidates
路线沿用同一批决定，另加：

  四、**同跨度异含义的计数归属**。一条提及同时有两种结构读法（如 2009 SCC 51
    的「年+代码+页」与「卷+缩写+页」）时，这条提及只该计一次。表证据恰好唯一
    支持一种读法 → 归它；相持或全无支持 → 谁也不归（整组 undecided，不计数）。
    把「弃权」落成 0 计数而非 0.5/重复计，是约束四（无证据不给判定）的计数版。
"""
import argparse
import csv
import datetime
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import nk                                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _relpath(p):
    """manifest 里记输入路径。跨盘符时（测试临时目录在 C:、仓库在 D:）relpath 会抛
    ValueError——而 manifest 写在数据文件之后，首版就这样留下有数据、无 manifest 的
    半成品输出（迷你全链首跑抓到）。退回绝对路径。"""
    try:
        return os.path.relpath(p, ROOT).replace("\\", "/")
    except ValueError:
        return os.path.abspath(p).replace("\\", "/")


MERGED_FIELDS = ["merge_key", "canonical_string", "abbreviation", "citation_kind",
                 "jurisdiction", "jurisdiction_confidence", "case_name_modal",
                 "occurrence_count", "distinct_decisions_count",
                 "case_name_agreement", "case_name_support", "variants_count",
                 "candidates_admitted", "candidates_rejected", "self_citation_of",
                 "self_case_name"]

FOLDED_FIELDS = ["merge_key", "raw_string", "count", "distinct_decisions_count"]

# 第三个输出文件，规格 §9.5 未列，由本实现补（理由见文件头「规格未定义」一节）
DECISION_FIELDS = ["merge_key", "source_decision_citation"]

# candidates 路线：逐候选仲裁台账（Stage 4 的追溯主干）
MENTION_FIELDS = ["candidate_id", "corpus_row_index", "source_decision_citation",
                  "raw_string", "shape_name", "match_start_offset",
                  "match_end_offset", "merge_key", "arbitration_status",
                  "superseded_by_candidate", "arbitration_note",
                  "citation_kind", "jurisdiction", "jurisdiction_confidence",
                  "parse_status", "structural_conflict", "rejected_reason",
                  "self_citation", "candidate_case_name"]

SHAPE_RANK = {name: i for i, name in enumerate([
    "shape_bracket", "shape_vol_page_year", "shape_year_vol_page",
    "shape_nominate", "shape_neutral_bare", "shape_vol_abbr_page",
    "shape_leading_abbr"])}


def build_merge_key(row):
    """§9.1：用结构化字段拼接，不对整条原始串做字符级压平。

    卷号缺失时**留空位而不是省略字段**——1978||ac||728 与 1978|1|ac||728 仍是
    两个不同的键。二者是否应视为同一引证（卷号缺失时的宽松匹配）是未决设计问题
    （PROBLEMS #2），本版按严格匹配处理，不做猜测性合并。

    认得的系列前缀并入缩写位（PROBLEMS #53）：`L.R. 6 Q.B. 1`（英国）与 `Q.R. 6 Q.B. 1`
    （魁北克）是两本汇编里的两个判决，不能同键；无前缀的 `6 Q.B. 1` 另成一键——它两边
    都可能是，并进任何一边都是替它猜。nk() 只留字母数字，故「.」作分隔不会撞。
    """
    year = row.get("year_start") or ""
    vol = row.get("vol") or ""
    abbr = nk(row.get("abbreviation") or "")
    prefix = nk(row.get("series_prefix") or "")
    if prefix:
        abbr = prefix + "." + abbr
    series = (row.get("series") or "").lower()
    page = row.get("page") or ""
    return "%s|%s|%s|%s|%s" % (year, vol, abbr, series, page)


# ------------------------------------------------ 键 v2（阶段 2：D4/D5）
_ORD_TAIL_RE = re.compile(r"(st|nd|rd|th)$")
# R2-5：nominate 括注的序数系列形（(2d) / (3rd) / (4th)）
_ORD_NOTE_RE = re.compile(r"^\(?\s*\d+(?:st|nd|rd|th|d)\s*\)?$")


def _canon_series(s):
    """序数系列正典化：裸「4th」/ 粘连「4d」/ 括注「(4d)」→ 同一值「4d」；
    2 与 3 不同；大小写与括号差异抹平。原写法保留在候选字段里。"""
    s = (s or "").strip().strip("()").lower()
    return _ORD_TAIL_RE.sub("d", s)


def _series_component(row):
    """键的系列槽（D4）。优先级：序数括注 > 裸/粘连序数 > 非序数括注。
    非序数括注（(N.S.)）是「新系列」，与无括注的同名汇编不是一本书——
    以 n: 前缀进键（与任何序数或缺失都不同键）。shape_nominate 的宽口径
    paren_note 是法院/法域标注（(Ont. C.A.) 类），不是系列身份，不进键；
    **例外（R2-5）**：nominate 括注本身是序数系列形（165 A. (2d) 82 (1960)
    的 (2d)）时按系列正典化进键——否则同一条引证的 nominate 读法与
    vol_page_year 读法因键不同被判成两种含义而双双弃权。"""
    if row.get("series_paren"):
        return _canon_series(row["series_paren"])
    if row.get("series"):
        return _canon_series(row["series"])
    note = (row.get("paren_note") or "").strip()
    if note:
        if row.get("shape_name") == "shape_nominate":
            if _ORD_NOTE_RE.match(note):
                return _canon_series(note)
            return ""
        return "n:" + nk(note)
    return ""


def build_merge_key_v2(row):
    """键 v2（candidates 路线专用；D4+D5）：
      * 系列槽 = 正典化序数或 n:<非序数括注>（D4）——47 D.L.R. (2d) 400 与
        47 D.L.R. (3d) 400 不再同键；缺失系列与显式系列不同键；
      * 页码槽 = 阿拉伯页原样，罗马页加 ro: 前缀（D5）——罗马 x 不与缺失
        同键、不与阿拉伯 10 同键；page_prefix/page_suffix 不进键、随候选
        字段与 mentions 台账保留。
    其余槽与 v1 同构（year|vol|abbr|series|page），decide 层的按槽解析不受影响。"""
    year = row.get("year_start") or ""
    vol = row.get("vol") or ""
    abbr = nk(row.get("abbreviation") or "")
    prefix = nk(row.get("series_prefix") or "")
    if prefix:
        abbr = prefix + "." + abbr
    if row.get("page_roman"):
        page = "ro:" + (row.get("page_roman") or "").strip().lower()
    else:
        page = row.get("page") or ""
    return "%s|%s|%s|%s|%s" % (year, vol, abbr, _series_component(row), page)


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


def _unknown_jur(j):
    return j in ("", "UNSUPPORTED")


# R2-2：可用支持分级。被拒 / 结构冲突未消 / 年卷歧义未决 / 法域 UNSUPPORTED 一律 0
# （这样的读法**没有可用支持**，lookup_mode 再 exact 也不许压过别的读法）；
# 法域已解析时 exact=2、其余（含缺 lookup_mode 元数据）=1——缺元数据不制造正支持。
def support_grade(row):
    if row.get("rejected_reason"):
        return 0
    if (row.get("parse_status") or "valid") != "valid":
        return 0
    j = row.get("jurisdiction") or ""
    if j in ("", "UNSUPPORTED"):
        return 0
    return 2 if (row.get("lookup_mode") or "") == "exact" else 1


def _fields_compatible(a, b):
    """两候选共享字段（双方都非空）nk 后是否相容。空对非空不算冲突——
    短候选少印一个槽是常态（「3 All E.R. 12」没有年份槽）。"""
    for f in ("vol", "page", "year_start"):
        fa, fb = (a.get(f) or "").strip(), (b.get(f) or "").strip()
        if fa and fb and fa != fb:
            return False
    ab_a = nk(a.get("abbr") or a.get("token") or "")
    ab_b = nk(b.get("abbr") or b.get("token") or "")
    if ab_a and ab_b and ab_a != ab_b:
        return False
    return True


# ============================================================ candidates 路线
def arbitrate_document(rows, stats):
    """一个判决（同 sdc + corpus_row_index）内的重叠仲裁（Round 2 订正版）。
    输入 rows：该判决全部已分类候选（任意顺序）；返回 {candidate_id: (status, note, superseded_by)}。

    状态：counted / rejected_row / self_citation_row / cross_boundary_invalid /
          alternative_same_key / alternative_weaker_support /
          alternative_unsupported_reading / alternative_dominated_by_support /
          alternative_contained / alternative_spanning_mismatch /
          span_alternative_undecided / overlap_undecided

    R2-2：支持分级 support_grade（exact=2 > 其余已解析=1 > 无可用支持=0）；
    同跨度先按键合并（同义多解析不自相打平），再在**不同含义**间比较：
    唯一最高档胜出，最高档打平 → 整组弃权。输家带支持 → weaker_alternative，
    无支持 → unsupported_reading。
    R2-3：不同跨度同规则——部分重叠/不相容包含中，严格更高支持档唯一起者胜，
    输家 dominated_by_support；同档 → 弃权。包含相容 → 长者胜；横跨 ≥2 条互不
    重叠短候选 → 长者让位。
    R2 终集合不变量：重叠不传递——支配关系收敛到**最终被计数**的含义上
    （链式重定向）；被消解/未决的候选不得再当唯一压制者（定点回收重算）。
    """
    out = {}
    by_id = {r["candidate_id"]: r for r in rows}
    order = sorted(rows, key=lambda r: (int(r["match_start_offset"]),
                                        -int(r["match_end_offset"]),
                                        SHAPE_RANK.get(r["shape_name"], 99),
                                        r["candidate_id"]))
    for r in rows:
        if r.get("rejected_reason"):
            out[r["candidate_id"]] = ("rejected_row", "", "")
        elif r.get("self_citation") == "true":
            out[r["candidate_id"]] = ("self_citation_row", "", "")

    # ---- A. D3 跨界解析的配对消解（R2：配对者须有**可用支持**才算有效替换；
    #         仅「在场且非 rejected」不再证明无效性——歧义跨界保持未决）----
    for r in rows:
        if (r.get("structural_conflict") == "cross_boundary_year_page"
                and r["candidate_id"] not in out):
            partner = by_id.get(r.get("conflict_with_candidate"))
            partner_status = out.get(partner["candidate_id"], ("", ""))[0] if partner else None
            if (partner is not None and partner is not r
                    and partner_status != "rejected_row"
                    and support_grade(partner) >= 1):
                out[r["candidate_id"]] = (
                    "cross_boundary_invalid",
                    "page %s read as year by supported partner; %s" % (
                        r.get("page"), r.get("conflict_note") or ""),
                    partner["candidate_id"])
                stats["cross_boundary_invalidated"] += 1
            else:
                # 配对者缺席/被拒/无可用支持：冲突未消解。候选保留（带旗、
                # 支持级 0——不得压制他人），交 B/C 常规规则
                stats["cross_boundary_unresolved"] += 1

    # ---- B. 同跨度组：先按键合并（同义多解析不自打平），再比不同含义 ----
    span_groups = defaultdict(list)
    for r in order:
        if r["candidate_id"] not in out:
            span_groups[(int(r["match_start_offset"]),
                         int(r["match_end_offset"]))].append(r)
    for span in sorted(span_groups):
        members = sorted(span_groups[span],
                         key=lambda r: (SHAPE_RANK.get(r["shape_name"], 99),
                                        r["candidate_id"]))
        # 按键合并：每个键取其成员中的最高支持档与代表行（同档取形状序、id 定序）
        bykey = {}
        for m in members:
            k = build_merge_key_v2(m)
            g = support_grade(m)
            cur = bykey.get(k)
            if cur is None or (g, -SHAPE_RANK.get(m["shape_name"], 99), m["candidate_id"]) > \
                    (cur[0], -SHAPE_RANK.get(cur[1]["shape_name"], 99), cur[1]["candidate_id"]):
                bykey[k] = (g, m)
        if len(bykey) == 1:
            (g, rep), = bykey.values()
            out[rep["candidate_id"]] = ("counted", "", "")
            for m in members:
                if m["candidate_id"] != rep["candidate_id"]:
                    out[m["candidate_id"]] = ("alternative_same_key",
                                              "same span, same meaning as %s"
                                              % rep["candidate_id"],
                                              rep["candidate_id"])
            stats["same_span_same_key_folded"] += len(members) - 1
            continue
        top = max(g for g, _ in bykey.values())
        winners = [k for k, (g, _) in bykey.items() if g == top]
        if len(winners) == 1 and top > 0:
            wkey = winners[0]
            rep = bykey[wkey][1]
            out[rep["candidate_id"]] = ("counted", "", "")
            for k, (g, m) in bykey.items():
                if k == wkey:
                    continue
                label = ("alternative_weaker_support" if g >= 1
                         else "alternative_unsupported_reading")
                out[m["candidate_id"]] = (
                    label, "span shared with %s; strictly higher support grade"
                    % rep["candidate_id"], rep["candidate_id"])
            for m in members:
                if (build_merge_key_v2(m) == wkey
                        and m["candidate_id"] != rep["candidate_id"]):
                    out[m["candidate_id"]] = ("alternative_same_key",
                                              "same span, same meaning as %s"
                                              % rep["candidate_id"],
                                              rep["candidate_id"])
            stats["same_span_resolved_by_support"] += 1
        else:
            for m in members:
                out[m["candidate_id"]] = (
                    "span_alternative_undecided",
                    "same span, %d readings, %s" % (
                        len(bykey),
                        "top-grade tie" if top > 0 else "no usable support"),
                    "")
            stats["same_span_abstained"] += 1

    # ---- C. 不同跨度间的重叠：支持支配 + 终集合定点收敛 ----
    live_rows = [r for r in order
                 if out.get(r["candidate_id"], ("",))[0] in ("", "counted")]
    live_rows.sort(key=lambda r: (int(r["match_start_offset"]),
                                  -int(r["match_end_offset"]),
                                  r["candidate_id"]))
    # 横跨检测：X 与 ≥2 条更短、互不重叠的候选重叠 → X 让位，短候选不受此对影响
    shorter_overlappers = defaultdict(list)
    for i, a in enumerate(live_rows):
        as_, ae = int(a["match_start_offset"]), int(a["match_end_offset"])
        for b in live_rows[i + 1:]:
            bs = int(b["match_start_offset"])
            if bs >= ae:
                break
            be = int(b["match_end_offset"])
            if as_ >= be:
                continue
            shorter_overlappers[a["candidate_id"]].append(b)
    spanning = set()
    len_of = {r["candidate_id"]: int(r["match_end_offset"]) - int(r["match_start_offset"])
              for r in live_rows}
    for cid, shorts in shorter_overlappers.items():
        shorts = [s for s in shorts if len_of[s["candidate_id"]] < len_of[cid]]
        if len(shorts) < 2:
            continue
        disjoint = True
        for i in range(len(shorts)):
            for j in range(i + 1, len(shorts)):
                ai, ae_ = int(shorts[i]["match_start_offset"]), int(shorts[i]["match_end_offset"])
                bi, be_ = int(shorts[j]["match_start_offset"]), int(shorts[j]["match_end_offset"])
                if ai < be_ and bi < ae_:
                    disjoint = False
        if disjoint:
            spanning.add(cid)
            stats["spanning_mismatch_detected"] += 1

    verdicts = defaultdict(list)          # cid -> [(kind, other_cid)]
    for i, a in enumerate(live_rows):
        as_, ae = int(a["match_start_offset"]), int(a["match_end_offset"])
        for b in live_rows[i + 1:]:
            bs = int(b["match_start_offset"])
            if bs >= ae:
                break
            be = int(b["match_end_offset"])
            if as_ >= be:
                continue
            if a["candidate_id"] in spanning and b["candidate_id"] not in spanning:
                verdicts[a["candidate_id"]].append(("spanning", b["candidate_id"]))
                continue
            if b["candidate_id"] in spanning and a["candidate_id"] not in spanning:
                verdicts[b["candidate_id"]].append(("spanning", a["candidate_id"]))
                continue
            ka, kb = build_merge_key_v2(a), build_merge_key_v2(b)
            if ka == kb:
                if (ae - as_) >= (be - bs):
                    verdicts[a["candidate_id"]].append(("rep", b["candidate_id"]))
                    verdicts[b["candidate_id"]].append(("yield", a["candidate_id"]))
                else:
                    verdicts[b["candidate_id"]].append(("rep", a["candidate_id"]))
                    verdicts[a["candidate_id"]].append(("yield", b["candidate_id"]))
                continue
            contained_a = as_ >= bs and ae <= be and (ae - as_) < (be - bs)
            contained_b = bs >= as_ and be <= ae and (be - bs) < (ae - as_)
            if (contained_a or contained_b) and _fields_compatible(
                    a if contained_a else b, b if contained_a else a):
                short, long_ = (a, b) if contained_a else (b, a)
                verdicts[short["candidate_id"]].append(("contained", long_["candidate_id"]))
                verdicts[long_["candidate_id"]].append(("rep", short["candidate_id"]))
                continue
            # 部分重叠或不相容包含（R2-3）：支持支配，严格更高档唯一起者胜
            ga, gb = support_grade(a), support_grade(b)
            if ga > gb and ga >= 1:
                verdicts[a["candidate_id"]].append(("rep", b["candidate_id"]))
                verdicts[b["candidate_id"]].append(("dominated", a["candidate_id"]))
            elif gb > ga and gb >= 1:
                verdicts[b["candidate_id"]].append(("rep", a["candidate_id"]))
                verdicts[a["candidate_id"]].append(("dominated", b["candidate_id"]))
            else:
                verdicts[a["candidate_id"]].append(("undecided", b["candidate_id"]))
                verdicts[b["candidate_id"]].append(("undecided", a["candidate_id"]))
                stats["partial_overlap_abstained"] += 1

    PRIORITY = {"undecided": 0, "contained": 1, "dominated": 2, "yield": 3,
                "spanning": 4, "rep": 5}
    DOMINATED_STATUS = {"contained": "alternative_contained",
                        "dominated": "alternative_dominated_by_support",
                        "yield": "alternative_same_key",
                        "spanning": "alternative_spanning_mismatch"}

    def pick(vs):
        kind = min((k for k, _ in vs), key=lambda k: PRIORITY[k])
        others = [o for k, o in vs if k == kind]
        # 同类多个压制者时确定性选取：优先「最终被计数」者（定点收敛后重选），
        # 否则跨度更长者，再按 id
        return kind, others

    def choose_other(cid, kind, others, counted_now):
        counted = [o for o in others if counted_now.get(o) == "counted"]
        pool = counted or others
        return sorted(pool, key=lambda o: (-len_of[o], o))[0]

    counted_now = {}
    final = {}
    # R2 终集合口径：支配类裁决（结构或支持）优先——被任何存活支配者压制的候选
    # 不再因「垃圾对垃圾的同档弃权」而逃逸成 undecided；有 rep 裁决 → 计数；
    # 只剩 undecided 对 → 才弃权（同档冲突的弃权是**残差**，不是最高优先级）。
    for r in live_rows:
        cid = r["candidate_id"]
        vs = verdicts.get(cid)
        if not vs:
            final[cid] = ("counted", "", "")
            counted_now[cid] = "counted"
            continue
        sup = [(k, o) for k, o in vs if k in DOMINATED_STATUS]
        reps = [o for k, o in vs if k == "rep"]
        und = [o for k, o in vs if k == "undecided"]
        if sup:
            final[cid] = ("__dominated__", sup)
            counted_now[cid] = "dominated"
        elif reps:
            final[cid] = ("counted", "", "")
            counted_now[cid] = "counted"
        elif und:
            final[cid] = ("overlap_undecided",
                          "conflicting overlap with %s; equal or no support" % und[0],
                          "")
            counted_now[cid] = "undecided"
        else:
            final[cid] = ("counted", "", "")
            counted_now[cid] = "counted"

    # 定点收敛：支配者必须最终被计数；被消解/未决者不得当唯一压制者
    rounds = 0
    changed = True
    while changed and rounds <= len(live_rows) + 5:
        changed = False
        rounds += 1
        for r in live_rows:
            cid = r["candidate_id"]
            v = final.get(cid)
            if not v or v[0] != "__dominated__":
                continue
            pairs = v[1]                       # [(kind, other_cid)]
            # 确定性选取压制者：优先「最终被计数」者，否则跨度更长者，再按 id
            counted = [(k, o) for k, o in pairs if counted_now.get(o) == "counted"]
            pool = counted or pairs
            k_t, target = sorted(pool, key=lambda ko: (-len_of[ko[1]], ko[1]))[0]
            tstat = counted_now.get(target)
            if tstat == "counted":
                final[cid] = (DOMINATED_STATUS[k_t],
                              DOMINATED_NOTE[k_t] % target, target)
                continue
            if tstat == "dominated":
                # 链式重定向：指向支配者的支配者（最终计数者）
                t_final = final.get(target)
                if t_final and t_final[0] == "__dominated__":
                    tcounted = [o for k, o in t_final[1]
                                if counted_now.get(o) == "counted"]
                    if tcounted:
                        t2 = sorted(tcounted, key=lambda o: (-len_of[o], o))[0]
                        final[cid] = (DOMINATED_STATUS[k_t],
                                      DOMINATED_NOTE[k_t] % t2, t2)
                        changed = True
                        continue
                final[cid] = (DOMINATED_STATUS[k_t],
                              DOMINATED_NOTE[k_t] % target, target)
                continue
            # tstat in (undecided,) 或支配者不在 live（被 D3/自引/拒绝排除）：
            # 移除指向它的支配裁决，重算本候选（R2：被消解/未决者不得当唯一压制者）
            remaining = [(k, o) for k, o in verdicts.get(cid, [])
                         if o != target or k not in DOMINATED_STATUS]
            verdicts[cid] = remaining
            stats["dominator_recycled"] += 1
            sup2 = [(k, o) for k, o in remaining if k in DOMINATED_STATUS]
            reps2 = [o for k, o in remaining if k == "rep"]
            und2 = [o for k, o in remaining if k == "undecided"]
            if sup2:
                final[cid] = ("__dominated__", sup2)
            elif reps2:
                final[cid] = ("counted", "", "")
                counted_now[cid] = "counted"
            elif und2:
                final[cid] = ("overlap_undecided",
                              "conflicting overlap with %s; equal or no support"
                              % und2[0], "")
                counted_now[cid] = "undecided"
            else:
                final[cid] = ("counted", "", "")
                counted_now[cid] = "counted"
            changed = True
    if changed:
        stats["arbitration_fixpoint_not_converged"] += 1

    for r in live_rows:
        cid = r["candidate_id"]
        v = final.get(cid)
        if v is None:
            out[cid] = ("counted", "", "")
        elif v[0] == "__dominated__":
            out[cid] = (DOMINATED_STATUS[v[1]], DOMINATED_NOTE[v[1]] % v[2], v[2])
            stats[{"contained": "contained_superseded",
                   "dominated": "dominated_by_support",
                   "yield": "same_key_folded_c",
                   "spanning": "spanning_mismatch_superseded"}[v[1]]] += 1
        else:
            out[cid] = v
            if v[0] == "overlap_undecided":
                stats["overlap_undecided_rows"] += 1
    return out


DOMINATED_NOTE = {
    "contained": "strict subset of compatible %s",
    "dominated": "overlapping reading with strictly weaker support than %s",
    "yield": "same meaning, shorter variant of %s",
    "spanning": "spans multiple shorter candidates incl. %s; overlap group keeps the shorts",
}


def run_candidates(args, stats):
    """candidates-2.0 主流程：判决内仲裁 → 跨行聚合。"""
    docs = defaultdict(list)
    with open(args.input, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            stats["input_candidates"] += 1
            docs[(row.get("source_decision_citation") or "",
                  row.get("corpus_row_index") or "")].append(row)
    stats["documents"] = len(docs)

    # 判决内仲裁（绝不回调 extract/classify）
    verdicts = {}
    for dkey in sorted(docs):
        verdicts.update(arbitrate_document(docs[dkey], stats))

    # 台账（逐候选一行，约束五：不删候选）+ 跨行聚合（只数 counted）
    mentions = []
    key_mapping = Counter()            # (old_key, new_key) -> 候选数
    per_key_counted = defaultdict(list)
    per_key_members = defaultdict(list)
    for dkey in sorted(docs):
        rows = sorted(docs[dkey], key=lambda r: (int(r["match_start_offset"]),
                                                 int(r["match_end_offset"]),
                                                 SHAPE_RANK.get(r["shape_name"], 99),
                                                 r["candidate_id"]))
        for row in rows:
            row = dict(row)
            status, note, sup = verdicts[row["candidate_id"]]
            row["arbitration_status"] = status
            row["arbitration_note"] = note
            row["superseded_by_candidate"] = sup
            # 旧键（v1：系列不捕获、罗马页落空）→ 新键（v2）映射；计数重建自
            # 新成员，绝不把旧键的 dd 拷到拆分出的新键上
            old_key = build_merge_key(row)
            new_key = build_merge_key_v2(row)
            row["merge_key"] = new_key
            key_mapping[(old_key, new_key)] += 1
            mentions.append({k: row.get(k, "") for k in MENTION_FIELDS})
            per_key_members[new_key].append(row)
            if status == "counted":
                per_key_counted[new_key].append(row)

    _emit(args, stats, per_key_counted, per_key_members, mentions,
          key_mapping)


def _emit(args, stats, per_key_counted, per_key_members, mentions,
          key_mapping=None):
    """聚合并写五张表。计数只看 counted；案名投票与自引归属用全键成员。"""
    merged, folded, decision_ids = [], [], []
    member_total = len(mentions)

    for key in sorted(per_key_counted):
        counted = per_key_counted[key]
        members = per_key_members[key]
        raw_cnt = Counter(m["raw_string"] for m in counted)
        top = max(raw_cnt.values())
        canonical = sorted(r for r, c in raw_cnt.items() if c == top)[0]

        occurrence = len(counted)
        decisions = {m["source_decision_citation"] for m in counted}
        dd = len(decisions)
        for did in sorted(decisions):
            decision_ids.append({"merge_key": key,
                                 "source_decision_citation": did})

        # 案名投票：非 rejected 且切出案名的候选（counted + 让位者 + 自引 + undecided）
        # 皆可投票，与 legacy 路线「自引照样投票」同口径
        valid = [m for m in members if not m.get("rejected_reason")
                 and m.get("candidate_case_name")]
        if valid:
            by_nk = defaultdict(list)
            for m in valid:
                by_nk[nk(m["candidate_case_name"])].append(m)
            recent = {k: max((int(m.get("source_decision_year") or 0)
                              if str(m.get("source_decision_year") or "").isdigit() else 0)
                             for m in v) for k, v in by_nk.items()}
            top_nk = max(sorted(by_nk), key=lambda k: (len(by_nk[k]), recent[k]))
            forms = Counter(m["candidate_case_name"] for m in by_nk[top_nk])
            best = max(forms.values())
            name_modal = sorted(f for f, c in forms.items() if c == best)[0]
            agreement = round(len(by_nk[top_nk]) / len(valid), 2)
            support = (round(len(by_nk[top_nk]) / max(occurrence, len(by_nk[top_nk])), 3)
                       if by_nk[top_nk] else 0.0)
            variants = len(by_nk)
        else:
            name_modal, agreement, support, variants = "", 0.0, 0.0, 0

        # 自引归属：这个键是语料里哪件判决自己头部印的引证（裁定层身份锚）
        own = sorted({m["source_decision_citation"] for m in members
                      if m.get("self_citation") == "true"})
        own_names = Counter(m["candidate_case_name"] for m in members
                            if m.get("self_citation") == "true"
                            and m.get("candidate_case_name")
                            and not m.get("name_rejected_reason"))
        own_name = min(own_names, key=lambda n: (-own_names[n], n)) if own_names else ""

        def pick_modal(field, tiebreak):
            return modal([m.get(field) or "" for m in counted], tiebreak)

        canon_row = next(m for m in counted if m["raw_string"] == canonical)
        if len({m.get("citation_kind") for m in counted}) > 1 or \
                len({m.get("jurisdiction") for m in counted}) > 1:
            stats["groups_with_internal_disagreement"] += 1
        merged.append({
            "merge_key": key,
            "canonical_string": canonical,
            "abbreviation": pick_modal("abbreviation", canon_row.get("abbreviation") or ""),
            "citation_kind": pick_modal("citation_kind", canon_row.get("citation_kind") or ""),
            "jurisdiction": pick_modal("jurisdiction", canon_row.get("jurisdiction") or ""),
            "jurisdiction_confidence": pick_modal("jurisdiction_confidence",
                                                  canon_row.get("jurisdiction_confidence") or ""),
            "case_name_modal": name_modal,
            "occurrence_count": occurrence,
            "distinct_decisions_count": dd,
            "case_name_agreement": agreement,
            "case_name_support": support,
            "variants_count": variants,
            "candidates_admitted": sum(1 for m in counted
                                       if m.get("candidate_case_name")),
            "candidates_rejected": sum(1 for m in counted
                                       if m.get("name_rejected_reason")),
            "self_citation_of": "|".join(own),
            "self_case_name": own_name,
        })

        per_raw = Counter(m["raw_string"] for m in counted)
        for raw in sorted(per_raw):
            folded.append({"merge_key": key, "raw_string": raw,
                           "count": per_raw[raw],
                           "distinct_decisions_count": len(
                               {m["source_decision_citation"] for m in counted
                                if m["raw_string"] == raw})})

        stats["occurrence_total"] += occurrence
        if occurrence == 0:
            stats["keys_zero_counted"] += 1

    stats["merge_keys"] = len(merged)
    stats["folded_rows"] = len(folded)
    if key_mapping is not None:
        # D4/D5 的键拆分账：一个旧键拆成几个新键、各带多少候选
        split = defaultdict(set)
        for (ok, nk_) in key_mapping:
            split[ok].add(nk_)
        stats["old_keys"] = len(split)
        stats["old_keys_split_into_multiple"] = sum(
            1 for v in split.values() if len(v) > 1)
        mapping_rows = [{"old_merge_key": ok, "new_merge_key": nk_,
                         "candidate_count": key_mapping[(ok, nk_)]}
                        for ok, nk_ in sorted(key_mapping)]
    else:
        mapping_rows = None

    # ---- 不变量 ----
    by_key_occ = {m["merge_key"]: m["occurrence_count"] for m in merged}
    fsum = Counter()
    for r in folded:
        fsum[r["merge_key"]] += r["count"]
    bad = [k for k, v in by_key_occ.items() if fsum[k] != v]
    assert not bad, "不变量1 破：folded 计数之和 != occurrence_count，键 %r" % bad[:5]
    assert member_total == stats["input_candidates"], \
        "不变量3 破：候选台账行数 %d != 输入 %d（约束五）" % (member_total, stats["input_candidates"])
    assert all(m["distinct_decisions_count"] <= m["occurrence_count"] for m in merged), \
        "不变量2 破：dd 大于 occurrence"
    idcnt = Counter(d["merge_key"] for d in decision_ids)
    bad = [m["merge_key"] for m in merged
           if idcnt[m["merge_key"]] != m["distinct_decisions_count"]]
    assert not bad, "不变量4 破：decision_ids 行数 != dd，键 %r" % bad[:5]
    stats["decision_id_rows"] = len(decision_ids)
    status_cnt = Counter(m["arbitration_status"] for m in mentions)
    stats["arbitration_status_counts"] = dict(sorted(status_cnt.items()))

    os.makedirs(args.output, exist_ok=True)
    for name, fields, rows in (("merged.csv", MERGED_FIELDS, merged),
                               ("mentions_candidates.csv", MENTION_FIELDS, mentions),
                               ("folded_log.csv", FOLDED_FIELDS, folded),
                               ("decision_ids.csv", DECISION_FIELDS, decision_ids)):
        if rows is None:
            continue
        path = os.path.join(args.output, name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, path)
    if mapping_rows is not None:
        path = os.path.join(args.output, "key_mapping.csv")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["old_merge_key", "new_merge_key",
                                              "candidate_count"])
            w.writeheader()
            w.writerows(mapping_rows)
        os.replace(tmp, path)

    manifest = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "court": args.court,
        "input": _relpath(args.input),
        "mode": "candidates",
        "spec_section": "9 + in-source arbitration",
        "stats": dict(sorted(stats.items())),
    }
    with open(os.path.join(args.output, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    print("court=%s  %d candidates -> %d merge keys -> %s"
          % (args.court, stats["input_candidates"], len(merged), args.output))
    for k, v in sorted(stats.items()):
        print("   %-40s %s" % (k, v))


# ================================================================ legacy 路线
def run_legacy(args, stats):
    """v1.4 行为逐字保留：test_layers 迷你全链等既有输入（无 candidate_id 列）。
    唯一改动是本函数化（原 main 主体），逻辑与期望值不动（约束五）。"""
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
                row.get("self_citation") == "true",
            ))

    merged, folded, decision_ids = [], [], []
    member_total = 0

    for key in sorted(groups):
        members = groups[key]
        member_total += len(members)

        # canonical_string：组内出现频次最高的 raw_string（§9.1，仅作展示用途）
        raw_cnt = Counter(m[0] for m in members)
        top = max(raw_cnt.values())
        canonical = sorted(r for r, c in raw_cnt.items() if c == top)[0]

        # §9.2 计数：只排除行级误报，不排除仅仅切不出案名的行。自引（PROBLEMS #54）
        # 是真引证但不是「别的判决引用了它」，也不计——判决头部必印自身引证，计入则
        # 语料里每件判决自带 dd+1，dd 恰是选取层唯一的门槛判据
        counted = [m for m in members if not m[3] and not m[10]]
        # 这个键是语料里哪件判决自己印的引证：裁定层据此认身份锚、剔自身（#54/#55）
        own = sorted({m[1] for m in members if m[10]})
        # 那件判决在自己头部印的案名：裁定层据此分辨「同名的另一件判决」与笔误（#55）
        own_names = Counter(m[5] for m in members if m[10] and m[5] and not m[4])
        own_name = min(own_names, key=lambda n: (-own_names[n], n)) if own_names else ""
        occurrence = len(counted)
        # 并集基数 —— 不是各变体取最大值（旧管线 bug），也不是相加
        decisions = {m[1] for m in counted}
        dd = len(decisions)
        # 判决 id 明细：裁定层做院内平行汇编合并时要靠它取真并集，不能相加
        for did in sorted(decisions):
            decision_ids.append({"merge_key": key, "source_decision_citation": did})

        # §9.3 案名众数投票：行级误报与切不出案名的行都排除
        # 自引行照样投案名票：判决头部印的正是它自己的案名，裁定层 §10.3 靠案名把
        # 它与平行引证连起来；只从计数里排除，不从投票里排除
        valid = [m for m in members if not m[3] and not m[4] and m[5]]
        if valid:
            # 两级投票（本实现对 §9.3 的补充，见文件头「规格未定义」一节）：
            # 先按 nk() 折叠拼写变体，再在胜出组内取最常见的印刷形输出。
            by_nk = defaultdict(list)
            for m in valid:
                by_nk[nk(m[5])].append(m)
            recent = {k: max((int(m[2]) if (m[2] or "").isdigit() else 0)
                             for m in v) for k, v in by_nk.items()}
            top_nk = max(sorted(by_nk), key=lambda k: (len(by_nk[k]), recent[k]))
            forms = Counter(m[5] for m in by_nk[top_nk])
            best = max(forms.values())
            name_modal = sorted(f for f, c in forms.items() if c == best)[0]
            agreement = round(len(by_nk[top_nk]) / len(valid), 2)
            support = (round(len(by_nk[top_nk]) / max(occurrence, len(by_nk[top_nk])), 3)
                       if by_nk[top_nk] else 0.0)
            variants = len(by_nk)
        else:
            name_modal, agreement, support, variants = "", 0.0, 0.0, 0

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
            "case_name_support": support,
            "variants_count": variants,
            "candidates_admitted": admitted,
            "candidates_rejected": rejected,
            "self_citation_of": "|".join(own),
            "self_case_name": own_name,
        })

        # 折叠日志：**全部**印刷变体都登记（含计数为 0 的）
        per_raw = defaultdict(list)
        for m in members:
            per_raw[m[0]].append(m)
        for raw in sorted(per_raw):
            c = [m for m in per_raw[raw] if not m[3] and not m[10]]
            folded.append({"merge_key": key, "raw_string": raw,
                           "count": len(c),
                           "distinct_decisions_count": len({m[1] for m in c})})

        stats["occurrence_total"] += occurrence
        stats["self_citation_rows"] += sum(1 for m in members if m[10])
        if occurrence == 0:
            if all(m[10] for m in members):
                stats["keys_only_self_citation"] += 1
            else:
                stats["groups_all_rejected"] += 1

    stats["merge_keys"] = len(merged)
    stats["folded_rows"] = len(folded)

    # ---- 四条不变量，不过就拒绝写表 ----
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
    idcnt = Counter(d["merge_key"] for d in decision_ids)
    bad = [m["merge_key"] for m in merged
           if idcnt[m["merge_key"]] != m["distinct_decisions_count"]]
    assert not bad, "不变量4 破：decision_ids 行数 != dd，键 %r" % bad[:5]
    stats["decision_id_rows"] = len(decision_ids)

    os.makedirs(args.output, exist_ok=True)
    for name, fields, rows in (("merged.csv", MERGED_FIELDS, merged),
                               ("folded_log.csv", FOLDED_FIELDS, folded),
                               ("decision_ids.csv", DECISION_FIELDS, decision_ids)):
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
        "input": _relpath(args.input),
        "mode": "legacy",
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


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--court", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    stats = Counter()
    with open(args.input, encoding="utf-8", newline="") as f:
        header = next(csv.reader(f))
    if "candidate_id" in header:
        run_candidates(args, stats)
    else:
        run_legacy(args, stats)


if __name__ == "__main__":
    main()
