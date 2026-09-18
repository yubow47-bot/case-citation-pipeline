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

  五、**判决自身印的引证：是身份锚，且不计入自己的 dd**（#54/#55）。归并层的
    self_citation_of 记着「这个键是语料里哪件判决在自己头部印的引证」。
      · 1999 年前的最高法院判决没有中立引用，它自己的 S.C.R. 引证就是锚：
        [1957] S.C.R. 119 与 [1957] S.C.R. 531 同名同年，却是语料里两件判决，
        首版因「无中立锚不拆」合成一组。汇编锚只与同键合并，不走
        same_decision()——后者按中立引用解析、不看卷号
      · 中立锚的笔误规则加一道闸：键若是语料某判决自己的引证，且那件判决头部
        印的案名（self_case_name）就是这个键在本组里的名字，它就是同名的另一件
        判决，不是笔误——2007 ONCA 196 与 496 两件都印着 R. v. Maciel。头部名字
        对不上的照旧可当笔误：键 2008 ONCA 36 落在 R. v. Conway 组里，它自己的
        头部印的却是 Mickle v. Mickle，组里那些 36 是 326 的笔误。全量实测被当
        笔误并掉的语料判决 101 对：88 对头部名与组名一致，12 对不一致
      · 语料法院在开始印中立引用之前的「中立引用」不是判决身份（#56）：最高
        法院 2000 年才启用，1994 SCC 80 只能是噪声，它若当锚，会把 Mohan 的组
        拆成「两件判决」、让 C.C.C. 平行引证无处可归。判据两头都要正证据，都取
        语料里该院判决自己头部印的引证：该年早于它最早一次自印中立引用，**且**
        它在该年或之后仍在自印非中立引用（最高法院 1999 年还印 [1999] S.C.R.）。
        只凭前一条是缺证推断——语料缺了早年判决的头部就会误降真中立引用。只对
        语料法院成立，别的法院语料里没有它自己的判决
      · 剔自身只对组的**身份根**做：判决头部除了自身引证还印平行汇编、双语
        代码，分类层单行认不出，成组后才知道都是它自己。被当笔误并进别组的
        键不剔——那件判决若真引了本组，是真引用
      · 判决自身参与共引：头部把平行引证挨着自身中立引用印，这是它自己印的
        共引，故身份根的判决 id 集含它自身（只用于分派，dd 里剔除）

  六、**案名支持度随列流过本层，但不设闸**（PROBLEMS #60）。归并层输出的
     `case_name_support` = 赢家票数 / 计数行数，量的是「引用它的判决里有多少份
     站这个名字」——§9.3 的 `case_name_agreement` 量不到这一点（切不出案名的行是
     空票、不入分母，199 行里只有 1 行切出名字时 agreement 也是 1.0）。原计划按
     支持度设闸、不让低支持度的名字驱动 §10.3 的按名合并；**实测后撤掉**：见
     PROBLEMS #60——闸只影响 32 组，全部是把同一案子的平行汇编拆开，还新增 8 处
     「同一印刷串落两组」。低支持度的成因是「该案主要被中立引用引、不印案名」，
     不是名字错。列照旧输出，供人复核与将来的别的判据使用

  七、**同名、年份相差 ≤1 的同级组只标记、不合并**（PROBLEMS #62）。跨法院轮跑完后
     给每个组填 `same_name_near_year_peers` = 同名的其他组号（分号连接）。这一档混着
     两类东西：真不同的判决（R. v. John 每年一件）与同一判决的两种写法——后者在任何
     一份判决里都不同时出现，数据里没有信号可连（PROBLEMS #55 的零共引残余）。
     约束四：无证据不给判定，故只标给人看。`kept` 在选取层才定，故这一列对**所有**组
     算，读者按自己的门槛筛
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


# R4 Stage 3：案件级人工核验批次只消费「全部证明项齐备」的行——其余状态
# （unresolved_within_budget 等）不入表（约束四：无证据不给判定）。
CASE_ORIGIN_MANUAL_STATUS = frozenset(("verified_research_agent",))


def load_case_origin_manual():
    """decisions/case_origin_manual.csv → 与 case_origin.csv 同构的来源地行。

    行由人（本轮=研究代理）按四项证明逐案核验后写入：印刷引证 ↔ 判决对应、
    决定法院、上诉来源法院/法域、报告年 ≠ 判决年不混同。**只消费全部证明项
    齐备**的行；合并进 origin_idx 后走 case_record 最高优先级（与 case_origin.csv
    同级——若同一引证两表都有且来源地不一致，成员本地 CONFLICT，方向保守）。"""
    path = os.path.join(DECISIONS, "case_origin_manual.csv")
    if not os.path.exists(path):
        return {}
    out = defaultdict(list)
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("status") or "").strip() not in CASE_ORIGIN_MANUAL_STATUS:
                continue
            k = (r.get("normalized_key") or "").strip()
            if k:
                out[k].append(r)
    return out


def load_scope():
    """court_or_reporter_scope.csv：**source-verified、年代有界**的排他来源地规则
    （§9.2）。只有 verification_status 以 verified 开头的行参与推断——估计/名称
    推断行（旧 reporter_jurisdiction 196 行全档）一律不得升级为来源地事实。
    键 = nk(printed_key)——印刷事实，非计算分组标识。"""
    path = os.path.join(DECISIONS, "court_or_reporter_scope.csv")
    if not os.path.exists(path):
        return {}
    idx = {}
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if not (r.get("verification_status") or "").startswith("verified"):
                continue
            k = nk(r.get("printed_key") or "")
            if k:
                idx.setdefault(k, []).append(r)
    return idx


# ---- R3：排他汇编来源地（P1/P2/P2′）--------------------------------------
# 只有**已核实**的排他行参与推断。两档排他性（P2）：
#   exclusive_statute   有约束力的法律/宪制文本规定其刊登范围
#   exclusive_publisher 只有出版方自己的编辑方针（须带反例搜寻记录）
REPORTER_ORIGIN_ALLOWED_STATUSES = frozenset((
    "verified_exclusive_statute",
    "verified_exclusive_publisher",
))
REPORTER_ORIGIN_TIER = {
    "exclusive_statute": 2,
    "exclusive_publisher": 1,
}


def load_reporter_origin():
    """decisions/reporter_origin_scope.csv：排他汇编的**来源地**表（R3）。

    键 = nk(printed_abbreviation)——印刷事实。同形异义汇编（K.B./Q.B./C.P.…）
    在同一键下有多行，每行带**自己独立溯源**的 vol/year 窗口：**窗口匹配即消歧**。
    本函数与 _reporter_origin **都不读 classify 的 jurisdiction**——那条路会把
    一个未核实的消歧猜测洗成有出处的来源地结论（P1）。

    只有 verification_status ∈ REPORTER_ORIGIN_ALLOWED_STATUSES 的行参与推断；
    `verified_mixed` 等行只作档案（写明「这个汇编混合，不可作来源证据」）。"""
    path = os.path.join(DECISIONS, "reporter_origin_scope.csv")
    if not os.path.exists(path):
        return {}
    idx = {}
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            st = (r.get("verification_status") or "").strip()
            if st not in REPORTER_ORIGIN_ALLOWED_STATUSES:
                continue
            k = nk(r.get("printed_abbreviation") or "")
            if k:
                idx.setdefault(k, []).append(r)
    return idx


def _in_span(v, lo, hi):
    """闭区间；空界 = 该侧无约束。v/界非数字按不可判处理（调用方已先判可比性）。"""
    try:
        iv = int(v)
    except (TypeError, ValueError):
        return None
    for b, op in ((lo, "lo"), (hi, "hi")):
        try:
            ib = int(b)
        except (TypeError, ValueError):
            continue
        if op == "lo" and iv < ib:
            return False
        if op == "hi" and iv > ib:
            return False
    return True


def _reporter_window_ok(vol, year, row):
    """维度式包含：仅当**引证与表行该维度都有值**时才可判、才可否决。
    两维都不可比 → 该行无约束（它靠「排他性」本身作证据，窗口只用来切分候选）。
    行号/年号非数字 → 该维度不可判（不否决，也不据此命中）。"""
    vs = (row.get("vol_range_start") or "").strip()
    ve = (row.get("vol_range_end") or "").strip()
    ys = (row.get("year_range_start") or "").strip()
    ye = (row.get("year_range_end") or "").strip()
    if vol and (vs or ve):
        if _in_span(vol, vs, ve) is False:
            return False
    if year and (ys or ye):
        if _in_span(year, ys, ye) is False:
            return False
    return True


def _reporter_origin(row, reporter_idx, stats):
    """P1/P2′：排他汇编的来源地是**正面证据**，查表自查、**不读 classify 的
    jurisdiction**。

    适用条件：本行是 counted 的 reporter 解析（citation_kind=reporter，即该缩写
    不是法院中立码、也不是数据库标识符）。

    判定（窗口匹配即消歧）：
      * 候选 = 表内该缩写下所有**未被窗口否决**的行；
      * 恰一行命中 → 取该行来源地；basis=exclusive_reporter_scope；
      * ≥2 行命中且**国别一致** → 取该国（P2′：国别无歧义，细分仅在一致时取）；
      * ≥2 行命中且国别不同（含表行 origin_country 缺失）→ **UNDETERMINED**，
        并在审计列 member_origin_ambiguous_basis 记
        `exclusive_reporter_scope_ambiguous`（与「查不到证据」分开记，Stage 4
        单独计数）；**不得**用 classify 的 jurisdiction、投票或其他信号破这个平局；
      * 零行命中（窗口外/该缩写无表行）→ 保持 UNDETERMINED（普通无证据）。

    细分与证据行：证据行在两档间取高（exclusive_statute > exclusive_publisher，
    P2）。优先级只决定**单个行**用哪条证据，绝不裁决两行**国别不一致**的冲突。
    """
    if (row.get("citation_kind") or "") != "reporter":
        stats["reporter_scope_not_reporter_parse"] += 1
        return
    p = row["merge_key"].split("|")
    if len(p) < 5:
        return
    code = nk(p[2])
    # 白名单在规则内部再筛一次（不只依赖 load_reporter_origin）：未核实行
    # （estimated / name_inference）与 verified_mixed 档**永远**不产生来源地。
    cand = [r for r in reporter_idx.get(code, ())
            if (r.get("verification_status") or "").strip()
            in REPORTER_ORIGIN_ALLOWED_STATUSES]
    if not cand:
        return
    # R3 修复：窗口的「年」维度用**印出来的年份**（row_year），不是键首槽——连续编卷
    # 汇编的键已零化年槽，读键会让年窗永远不可比（等于放弃窗过滤）。
    year = "" if row_year(row) is None else str(row_year(row))
    vol = p[1]
    hit = [r for r in cand if _reporter_window_ok(vol, year, r)]
    if not hit:
        stats["reporter_scope_out_of_window"] += 1
        return
    countries = sorted({(r.get("origin_country") or "").strip() for r in hit
                        if (r.get("origin_country") or "").strip()})
    if len(countries) != 1:
        row["member_origin_ambiguous_basis"] = "exclusive_reporter_scope_ambiguous"
        stats["reporter_scope_ambiguous"] += 1
        return
    best = sorted(hit, key=lambda r: (
        -REPORTER_ORIGIN_TIER.get((r.get("exclusivity") or "").strip(), 0),
        (r.get("printed_abbreviation") or "").strip(),
        (r.get("origin_subdivision") or "").strip()))[0]
    subs = sorted({(r.get("origin_subdivision") or "").strip() for r in hit
                   if (r.get("origin_subdivision") or "").strip()})
    row["member_origin_country"] = countries[0]
    row["member_origin_status"] = "DETERMINED"
    row["member_origin_basis"] = "exclusive_reporter_scope"
    row["member_origin_evidence_ids"] = "reporter_scope:" + (
        best.get("printed_abbreviation") or code)
    row["member_origin_conflict_detail"] = ""
    row["member_origin_subdivision"] = subs[0] if len(subs) == 1 else ""
    row["member_origin_exclusivity"] = (best.get("exclusivity") or "").strip()
    row["deciding_court"] = (best.get("deciding_court") or "").strip()
    stats["case_origin_by_reporter_scope"] += 1
    if len(hit) > 1:
        stats["reporter_scope_multirow_same_country"] += 1
    if not ((best.get("vol_range_start") or "").strip()
            or (best.get("vol_range_end") or "").strip()
            or (best.get("year_range_start") or "").strip()
            or (best.get("year_range_end") or "").strip()):
        stats["reporter_scope_from_row_without_window"] += 1



def year_of(merge_key):
    """归并键首字段即 year_start（§9.1）。**仅用于中立码键与旧产出**——见 row_year()。"""
    head = merge_key.split("|", 1)[0]
    return int(head) if head.isdigit() else None


def row_year(row):
    """这一行用于**聚类/同年邻组**的年份。

    R3 修复（身份回归）：年份有两个用途——①身份键的一部分、②裁定层聚类的属性。
    连续编卷汇编（volume_system=continuous）的键被结构性零化（年槽置空，正确：年不是
    它的身份），但**印出来的年份**由归并层保留在 `year_printed` 列里。聚类必须读这一列，
    否则同案的平行引证（`[1991] 1 S.C.R. 742` 与 `(1991), 63 C.C.C. (3d) 1`）会因为
    后者键里没有年份而被拆成两个孤立组——这正是 r3c 的身份回归（R. v. W.(D.) 694 →
    548+151）。`year_printed` 缺列或为空时回退到键首槽（中立码键与旧产出走这条）。"""
    v = (row.get("year_printed") or "").strip()
    if v.isdigit():
        return int(v)
    return year_of(row["merge_key"])


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


# R2F：identifier 系统（数据库/厂商决策 ID）。加载verified行，键=nk(printed_token)。
ALLOWED_IDENTIFIER_STATUSES = {
    "verified_official_source",
    "verified_authoritative_manual",
}
_IDENTIFIER_CACHE = None


def load_identifier_systems():
    """identifier_systems.csv → {nk(token): system_name}，仅 database/vendor
    决策 ID 类（year_volume_reporter 的 DTC 按普通 reporter 语义处理；
    secondary_source 在分类层已拒绝）。缓存一次。"""
    global _IDENTIFIER_CACHE
    if _IDENTIFIER_CACHE is not None:
        return _IDENTIFIER_CACHE
    path = os.path.join(DECISIONS, "identifier_systems.csv")
    out = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("verification_status") or "").strip() \
                        not in ALLOWED_IDENTIFIER_STATUSES:
                    continue
                if (r.get("identifier_kind") or "").strip() not in (
                        "database_decision_id", "vendor_decision_id"):
                    continue
                tok = nk(r.get("printed_token") or "")
                sysname = (r.get("system_name") or "").strip()
                if tok and sysname:
                    out[tok] = sysname
    _IDENTIFIER_CACHE = out
    return out


def identifier_system_of(merge_key):
    """键的 identifier 系统名（无 → None）。键 v2 的 abbr 槽即印刷 token。"""
    p = merge_key.split("|")
    if len(p) < 3:
        return None
    return load_identifier_systems().get(nk(p[2]))


ALLOWED_BILINGUAL_STATUSES = {
    "verified_explicit_equivalence",
}


def load_bilingual():
    """R2 闭环 4.1：已核实的双语代码对（无方向、小写）。只有
    verification_status 精确属于 ALLOWED_BILINGUAL_STATUSES 的行参与身份等价——
    候选端点配对（同库 en+fr）**不**自动授权。结果缓存（同一进程一次加载）。"""
    global _BILINGUAL_CACHE
    if _BILINGUAL_CACHE is not None:
        return _BILINGUAL_CACHE
    path = os.path.join(DECISIONS, "bilingual_neutral_codes.csv")
    pairs = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("verification_status") or "").strip() \
                        not in ALLOWED_BILINGUAL_STATUSES:
                    continue
                a = nk(r.get("code_en") or "")
                b = nk(r.get("code_fr") or "")
                if a and b and a != b:
                    pairs.add(frozenset((a, b)))
    _BILINGUAL_CACHE = frozenset(pairs)
    return _BILINGUAL_CACHE


_BILINGUAL_CACHE = None


def parse_name_classes(raw):
    """PROBLEMS #88：解析归并层供的 `nk1:4|nk2:2` → {类名: 条数}。
    容错：空串、缺冒号、计数非数字的分段一律跳过（不造假数据，约束四）。"""
    out = {}
    for seg in (raw or "").split("|"):
        if ":" not in seg:
            continue
        n, _, cnt = seg.rpartition(":")
        if n and cnt.isdigit():
            out[n] = out.get(n, 0) + int(cnt)
    return out


def mixed_identity(k_classes, big_name):
    """PROBLEMS #88 三档判据。返回 "fold" / "holdout"。

    键 K 即将以笔误依据并进根 `big` 时，看 K 的提及**印出来的案名**：
      · 印的都与 big 同类                    → fold：纯笔误，照并（现状正确）
      · 一个名字都没印，或没有一个与 big 同类 → fold：本期不动（机制 A 与 #89 的地盘）
      · **既有 big 的名字、又有别的名字**      → holdout：一个印刷串承担两种身份，
        印刷证据自相矛盾 → 不并；上层再抑制它的案名（无证据不主张，约束四；
        不抑制会产生同名同年的对手组，把真组的平行引证挂靠打散——第一期实测）

    不引入任何计数阈值：一条反证也算反证（宁可漏，不可错）。"""
    if not big_name or not k_classes:
        return "fold"
    hit_big = big_name in k_classes
    hit_other = any(n != big_name for n in k_classes)
    return "holdout" if (hit_big and hit_other) else "fold"


def same_decision_kind(ka, ja, dda, kb, jb, ddb):
    """中立引用 ka（较小者）与 kb 是否同一判决；返回匹配依据：
    bilingual（双语代码）/ typo_number / typo_year / None。
    R2-1：依据必须显式可审——只有 bilingual 是「已核实的双语标识映射」，
    typo 两类是启发式，不得单独授权来源地传播。"""
    ya, ca, sa, na = _neutral_parts(ka)
    yb, cb, sb, nb = _neutral_parts(kb)
    if ya == yb and na == nb and sa == sb and ja and ja == jb:
        # R2 闭环 4.2：双语等价还须代码对精确存在于已核实双语表
        if frozenset((ca, cb)) in load_bilingual():
            return "bilingual"           # 同一判决的双语代码（SCC/CSC…）
        return None
    if (ca, sa) != (cb, sb) or 2 * dda > ddb:
        return None                      # 笔误必定比正确写法罕见
    # R2F：数据库/厂商序列号的一位之差 = 不同文档——identifier 键不做
    # one-edit / 年±1 塌缩（双语对已在上分支处理）
    if ca in load_identifier_systems() or cb in load_identifier_systems():
        return None
    if ya == yb and _one_edit(na, nb):
        return "typo_number"             # 号码错一位
    if na == nb and ya.isdigit() and yb.isdigit() and abs(int(ya) - int(yb)) == 1:
        return "typo_year"               # 年份错一年
    return None


def same_decision(ka, ja, dda, kb, jb, ddb):
    return same_decision_kind(ka, ja, dda, kb, jb, ddb) is not None


def _self_of(m):
    return {x for x in (m.get("self_citation_of") or "").split("|") if x}


def load_registry(path):
    """全局判决登记簿（PROBLEMS #88/#89）→ {merge_key: (decision_id, source_court)}。

    登记簿是**机器产物、可重建**（`<run>/registry/decision_registry.csv`，
    由 `pipeline/registry.py` 生成），不是人工判断表——约束八只管
    `decisions/` 下的人工表（规格 2.1）。多个判决 id 落同一个键时按
    「;」连接，保持确定性（同键多判决是登记簿要暴露的事实，不是要抹平的噪声）。

    不传 `--registry` → 空表 → 本层行为与改动前逐字节一致。"""
    idx = defaultdict(set)
    if path and os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                k = r.get("merge_key") or ""
                did = r.get("decision_id") or ""
                if k and did:
                    idx[k].add((did, r.get("source_court") or ""))
    return {k: (";".join(sorted(d for d, _c in v)),
                ";".join(sorted({c for _d, c in v if c})))
            for k, v in idx.items()}


def neutral_start(rows):
    """各语料法院的中立引用起用界（#56），取自判决自己头部印的引证：
    {法院码: (最早一次自印中立引用的年份, 最晚一次自印非中立引用的年份)}。"""
    first, last = {}, {}
    for r in rows:
        p = r["merge_key"].split("|")
        if not p[0].isdigit():
            continue
        for d in _self_of(r):
            code = d.split("_", 1)[0].lower()
            if r.get("citation_kind") == "neutral":
                first[code] = min(first.get(code, 9999), int(p[0]))
            else:
                last[code] = max(last.get(code, 0), int(p[0]))
    return {c: (first.get(c, 9999), last[c]) for c in last}


def _before_start(k, start):
    """该院那年还不出中立引用：早于它最早的自印中立引用，且它那年或之后仍自印非中立引用。"""
    p = k.split("|")
    if not start or not p[0].isdigit() or p[2] not in start:
        return False
    first, last = start[p[2]]
    return int(p[0]) < first and int(p[0]) <= last


def decisions_of(members, did_idx, start=None, registry=None,
                 typo_over=None, gate="literal", holdout=None):
    """把组内的身份锚归并成「判决」。返回 (root, anchor_ids, anchor_jur, own,
    root_kind)。root_kind[k] ∈ {bilingual, typo_number, typo_year}——k 被并进
    root[k] 的显式依据（R2-1：来源地传播只认 bilingual 这一种）。
    锚 = 中立引用，或语料某判决在自己头部印的引证（self_citation_of，#55）。
    own[k] 为锚 k 是哪件判决自己的引证；anchor_ids 不含它（dd 口径）。

    `registry`（#88/#89）：**run 级全局登记簿** {merge_key: (decision_id, court)}，
    覆盖所有已知真判决自印的引证（不限于本法院那一轮）。**只授权笔误闸使用**——
    `own` 另有三处用途（身份锚资格 `neu[k] or own[k]`、dd 自引排除 `selfd |= own[k]`
    #54、#56 起始年判据 `neu[k] and not own[k] and _before_start`），一处都不许掺
    （规格 2.3）。

    `gate` 只影响笔误闸里「登记簿命中」怎么参与判断（**默认 literal = 规格 2.3
    逐字写法**）：

      literal        in_registry = bool(own[k]) or k in registry
                     → 与 `and same_name[k]` 合并后恒等价于原条件，见 --registry-gate
      own_or_registry in_registry = bool(own[k]) or k in registry，且**闸门条件**
                     改为 `in_registry and same_name[k]` 的等价展开
                      `(own[k] or k in registry) and same_name[k]`
                     —— 这是规格 2.3 的**字面意图**（登记簿取代作用域内的 own），
                     但实测仍不动作：机制 B 那一档的 `same_name[k]` 恒为假。
      registered_only 闸门条件 = `(own[k] and same_name[k]) or (k in registry and not own[k])`
                     —— 「登记簿命中、而**本轮/本法院看不见**它是真判决」即挡住笔误。
                     实测这是唯一能修 #88 的取值（机制 A 的 own[k] 非空，完全不受影响）。

    三者的实测差别只在「本地看不见的登记簿命中」这一档：literal / own_or_registry
    放行（并组），registered_only 挡住（不并组）。

    `typo_over`（非 None 时收集）：机制 A（键是真判决自己的引证、**但头部案名与
    本组组名不一致**）在改动前后**都**仍可被当笔误并掉——这一档是既定权衡
    （decide.py 文件头五：全量 101 对里 88 对名字一致、12 对不一致），本次不动它，
    但它至今是隐形的。登记簿在场时把每一次这样的判断落进
    `<scope>/typo_over_registered.csv`，让它可审：每行 = 一个**键**被并进某个
    身份根的一次判断（键可能还并进了别的组，故行数可多于键数）。"""
    own, neu = defaultdict(set), defaultdict(bool)
    same_name = defaultdict(bool)      # 头部自印案名 == 本组里这个键的名字
    classes = defaultdict(dict)        # #88：键 → 提及印出的案名类分布
    kname = defaultdict(str)           # #88：键级案名（modal）
    for m in members:
        k = m["merge_key"]
        own[k] |= _self_of(m)
        neu[k] = neu[k] or m.get("citation_kind") == "neutral"
        sn = nk(m.get("self_case_name") or "")
        same_name[k] = same_name[k] or bool(sn and sn == nk(m.get("case_name_modal") or ""))
        for n_, c_ in parse_name_classes(m.get("name_classes")).items():
            classes[k][n_] = classes[k].get(n_, 0) + c_
        kname[k] = kname[k] or nk(m.get("case_name_modal") or "")
    for k in neu:
        if neu[k] and not own[k] and _before_start(k, start):
            neu[k] = False        # 该院那年还不出中立引用：不是身份锚，当普通单元（#56）
    anc, ajur = defaultdict(set), {}
    for m in members:
        k = m["merge_key"]
        if neu[k] or own[k]:
            anc[k] |= did_idx.get(row_key(m), set())
            ajur[k] = m.get("jurisdiction") or ""
    order = sorted(anc, key=lambda k: (-len(anc[k]), k))
    root, root_kind = {}, {}
    for i, k in enumerate(order):
        root[k] = k
        for big in order[:i]:
            if root[big] != big or not (neu[k] and neu[big]):
                continue          # 汇编锚只与同键合并：same_decision 按中立引用解析、不看卷号
            # #88/#89：登记簿命中 = 「这个键是某件真判决自己印的引证」。
            # own[k] 是本轮/本法院看得见的那一份，registry 是全局那一份；
            # **绝不回写进 own 本身**（规格 2.3）——own 另有三处用途。
            registered = bool(registry and k in registry)
            if gate == "literal":
                # 规格 2.3 的逐字写法。与 `and same_name[k]` 合并后，
                # `or k in registry` 这一支被同名闸挡死：key 能否被救只取决于
                # `own[k]`，而 `own` 正是作用域内那一份——**字面规则与现状等价**
                # （实测：主线全 run 0 键变化）。
                in_registry = bool(own[k]) or registered
                blocked = in_registry and same_name[k]
            elif gate == "own_or_registry":
                # 规格 2.3 的字面意图：登记簿**取代**作用域内的 own——闸门条件
                # 展开为 (own[k] or 登记簿命中) and same_name[k]。
                # 实测仍不动作：机制 B 那一档的 same_name[k] 恒为假。
                in_registry = bool(own[k]) or registered
                blocked = (bool(own[k]) or registered) and same_name[k]
            elif gate == "registered_only":
                # 唯一实测能修 #88 的取值：登记簿命中而**本轮/本法院看不见**它是
                # 真判决（own[k] 空）→ 它不是笔误，是别处的真判决（Chieu/Carlos）。
                # 机制 A（own[k] 非空）走原来的同名闸，结论逐字不变。
                in_registry = bool(own[k]) or registered
                blocked = (bool(own[k]) and same_name[k]) or (registered and not own[k])
            else:
                raise SystemExit("未知的 --registry-gate：%r" % gate)
            if blocked:
                continue          # 同名的另一件语料判决，不是笔误（见文件头五）
            kind = same_decision_kind(k, ajur[k], len(anc[k]), big, ajur[big],
                                      len(anc[big]))
            if kind and holdout is not None and mixed_identity(
                    classes.get(k) or {}, kname.get(big) or "") == "holdout":
                # PROBLEMS #88：一个印刷串承担两种身份 → 不并，留痕，案名交由
                # 上层抑制（mixed_identity_keys）。继续找下一个 big 也没有意义——
                # 证据矛盾是这个键自身的属性，不是它与某个根的关系。
                holdout.append((k, big, kname.get(big) or "",
                                "|".join("%s:%d" % kv for kv in
                                         sorted((classes.get(k) or {}).items(),
                                                key=lambda kv: (-kv[1], kv[0]))),
                                sum((classes.get(k) or {}).values()),
                                len(anc[k]), len(anc[big])))
                break
            if kind:
                if registered and not same_name[k]:
                    # 机制 A：维持现状（仍可当笔误），但留痕（规格 2.3）。
                    # 只对**登记簿命中**的键留痕——不传 --registry 时这份清单为空、
                    # 输出与改动前逐字节一致（判据 1）。
                    if typo_over is not None:
                        typo_over.append((k, big, in_registry, kind,
                                          len(anc[k]), len(anc[big])))
                root[k] = big
                root_kind[k] = kind
                break
    return root, anc, ajur, own, root_kind


BAR = 0.8   # 「几乎总是一起印」。待定审计实测覆盖率双峰，取 0.5 或 0.8 只差 6 条

# 案名支持度（归并层 `case_name_support` = 赢家票数 / 计数行数）**照常随列流过本层，
# 但不设闸**（PROBLEMS #60）。曾按支持度设闸、实测后撤掉：过门槛组里支持度 < 0.10 的
# 有 244 个（本行数字随每次重跑变，口径是「过门槛且切出案名的组，支持度 < 0.10」；
# #60 登记时的 268 是 #61 落地前那一版的数），闸一开只影响 32 组，而这 32 组**无一
# 例外**是同一案子的平行汇编被拆开（Kienapple 273→18+256、Lifchus 166→68+99、
# Suresh 66→63+12……），并且新增 8 处「同一印刷串落两组」——正是 #49 修掉的撕裂形态，
# 而消除 0 处。低支持度的成因是「这案子主要被中立引用引、不印案名」，不是名字错；
# 要判断名字可不可信得看别的证据。


def _unknown(j):
    return j in ("", "UNSUPPORTED")


def _compatible(a, b):
    """None = 单元内法域自相矛盾，与谁都不相容；空串 = 未知，与谁都相容。"""
    if a is None or b is None:
        return False
    return not a or not b or a == b


def _with_held(parts, held):
    """PROBLEMS #88：把被扣留的混合键接回返回值——按 merge_key 各自成一组，
    理由 `mixed_identity`。行不删（约束五），只是不与任何身份根同组。"""
    if not held:
        return parts
    bykey = defaultdict(list)
    for m in held:
        bykey[m["merge_key"]].append(m)
    return list(parts) + [(bykey[k], "mixed_identity") for k in sorted(bykey)]


def split_by_decision(members, did_idx, stats, start=None, registry=None,
                      typo_over=None, gate="literal", holdout=None):
    root, anc, ajur, own, root_kind = decisions_of(members, did_idx, start,
                                                   registry, typo_over, gate,
                                                   holdout)
    # PROBLEMS #88：混合键必须**退出身份根的竞争**，不能只是「不并进对方」。
    # 只做后者，它就成了本桶里的第二个身份根，桶从「单根搭车」路径掉进「多根共引
    # 分派」路径，真组的平行引证（无锚的汇编引证）失去搭车资格 → 掉成 singleton。
    # 第一期的 registered_only 正是栽在这里（Housen 的 211 D.L.R. (4th) 577
    # 602→21）。把它们整个移出本桶、各自成组，桶内其余成员的判定路径原样不变。
    held = []
    if holdout:
        mixed_here = {h[0] for h in holdout}
        if mixed_here and any(m["merge_key"] in mixed_here for m in members):
            keep = []
            for m in members:
                (held if m["merge_key"] in mixed_here else keep).append(m)
            if keep:
                # 重算：本桶少了被扣留的成员。typo_over/holdout 传 None——这一趟
                # 只为拿干净的根，留痕上一趟已经记过，不得重复计数。
                members = keep
                root, anc, ajur, own, root_kind = decisions_of(
                    members, did_idx, start, registry, None, gate, None)
            else:
                held = []
    stats["anchors_collapsed_as_variant"] += sum(1 for k, r in root.items() if k != r)
    decisions = sorted({root[k] for k in root}, key=lambda k: (-len(anc[k]), k))
    if len(decisions) < 2:
        # R2F：identifier 单元不随单锚无条件同组——跨系统连接必须过既有
        # 共引门槛（cov ≥ BAR），否则自成一组（无共引时两组、basis 如实记录）
        dec0 = decisions[0] if decisions else None
        dec_ids0 = (anc.get(dec0, set()) | own.get(dec0, set())) if dec0 else set()
        ride, pend = [], []
        bucket_keys = set()
        for m in sorted(members, key=row_key):
            if identifier_system_of(m["merge_key"]):
                ids_m = did_idx.get(row_key(m), set())
                if not ids_m or not dec_ids0:
                    cov = 0.0
                else:
                    cov = (len(ids_m & dec_ids0) /
                           min(len(ids_m), len(dec_ids0)))
                if cov >= BAR \
                        and not any(identifier_system_of(k) ==
                                    identifier_system_of(m["merge_key"])
                                    for k in bucket_keys):
                    ride.append(m)
                    bucket_keys.add(m["merge_key"])
                    continue
                pend.append([m])
                continue
            ride.append(m)
            bucket_keys.add(m["merge_key"])
        parts0 = []
        if ride:
            parts0.append((ride, ""))
        for pm in pend:
            parts0.append((pm, "identifier_uncoited"))
        if len(parts0) > 1:
            stats["clusters_identifier_split_uncoited"] += 1
            # identifier 单元之间、以及 identifier 单元与非锚成员之间的跨系统
            # 连接，走既有共引合并（overlap ≥ 0.8×较小集）；同系统 identifier
            # 对被守卫跳过（不同编号=不同文档）
            n_p = len(parts0)
            parent = list(range(n_p))

            def find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            for i in range(n_p):
                for j in range(i + 1, n_p):
                    ids_i = set()
                    for m in parts0[i][0]:
                        ids_i |= did_idx.get(row_key(m), set())
                    ids_j = set()
                    for m in parts0[j][0]:
                        ids_j |= did_idx.get(row_key(m), set())
                    small = min(len(ids_i), len(ids_j))
                    if not small or len(ids_i & ids_j) < BAR * small:
                        continue
                    sys_i = {identifier_system_of(m["merge_key"])
                             for m in parts0[i][0]}
                    sys_j = {identifier_system_of(m["merge_key"])
                             for m in parts0[j][0]}
                    if (sys_i & sys_j) - {None}:
                        continue      # 同系统 identifier 永不合并
                    parent[find(i)] = find(j)
            comps = defaultdict(list)
            for i in range(n_p):
                comps[find(i)].append(i)
            merged = []
            for comp in sorted(comps.values(),
                               key=lambda c: min(row_key(parts0[i][0][0])
                                                 for i in c)):
                g_rows = [m for i in comp for m in parts0[i][0]]
                reasons = sorted({parts0[i][1] for i in comp if parts0[i][1]})
                merged.append((g_rows, ";".join(reasons)))
            if len(merged) > 1:
                return merged
        return _with_held(parts0 if parts0 else [(members, "")], held)
    stats["clusters_split_by_decision"] += 1

    dec_ids = defaultdict(set)
    for k, r in root.items():
        dec_ids[r] |= anc[k]
    for r in decisions:
        dec_ids[r] |= own[r]           # 身份根自己印的共引（头部平行引证），见文件头五
    buckets = {d: [] for d in decisions}
    units = defaultdict(list)          # 同一印刷串同进同出
    for m in members:
        if m["merge_key"] in root:
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
            # R3 修复：这个平局裁决按「单元年份 == 判决年份」取。单元年份**不能读键首槽**
            # ——连续编卷汇编的年槽已被结构性零化，读键会永远得到空串、平局永远破不了，
            # 单元于是落进 pending 变成孤立无锚组（实测 R. v. Osolin 68 → 61+7）。
            uy = row_year(us[0])
            same_year = [d for d in top
                         if uy is not None and d.split("|", 1)[0] == str(uy)]
            if len(same_year) == 1:
                target = same_year[0]
                stats["units_tie_broken_by_year"] += 1
        if target is not None:
            # R2F：同系统 identifier 一组至多一个——目标桶已含同系统
            # identifier 时本单元不指派（留 pending，自成一组）
            usys = identifier_system_of(mk)
            if usys and any(identifier_system_of(m["merge_key"]) == usys
                            for m in buckets[target]):
                pending.append((us, ids, uj))
                stats["units_identifier_same_system_blocked"] += 1
            else:
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
            # R2F：同系统 identifier 两单元永不合并（不同编号=不同文档）
            sys_i = {identifier_system_of(m["merge_key"])
                     for m in pending[i][0]}
            sys_j = {identifier_system_of(m["merge_key"])
                     for m in pending[j][0]}
            common_sys = (sys_i & sys_j) - {None}
            if common_sys:
                stats["pending_identifier_same_system_skipped"] += 1
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
    return _with_held([(buckets[d], "decision") for d in decisions] +
                      [(g, "decision;unanchored") for g in pend_groups], held)


# ------------------------------------------------------------ §10.3 + §10.4
def cluster_same_case(rows, did_idx, stats, start=None, registry=None,
                      typo_over=None, gate="literal", holdout=None):
    """返回 [(members, split_reason, split_seq)]；split_reason 为空表示未拆。
    无案名或无年份的行不参与合并（没有判同的依据），各自独立成组。"""
    buckets, out = defaultdict(list), []
    for r in rows:
        name = nk(r.get("case_name_modal") or "")
        y = row_year(r)          # R3：用「印出来的年份」，不是键首槽（连续编卷键已零化）
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
                for sub, r1 in split_by_decision(rows_, did_idx, stats, start,
                                                 registry, typo_over, gate,
                                                 holdout):
                    reason = ";".join(x for x in (r0, r1) if x)
                    if reason:
                        out.append((sub, reason, seq))
                        seq += 1
                    else:
                        out.append((sub, "", ""))
                        if len(sub) > 1:
                            stats["groups_merged_parallel"] += 1
    return out


def decide_case_origin(row, member_strings, origin_idx, stats, scope_idx=None,
                       reporter_idx=None):
    """§10.2（R2-1 订正）：**成员级来源地观察**——只观察本行键自己，不继承组结论。
    结果写 member_origin_* 字段；组级结论由 aggregate_group_origin 从成员观察聚合。
    未入表时 UNDETERMINED，**不得默认取 jurisdiction 的值**。

    证据优先级（P2）：**案件级直接证据 > 法院/中立码排他范围 > 排他汇编范围
    （statute 档 > publisher 档）**。前三者由 citation_kind 结构性分开：本行要么是
    neutral/identifier（走 scope），要么是 reporter（走 R3 汇编范围），因此
    「scope 与汇编范围同时适用」在结构上不会发生；两档汇编排他性的先后只在
    **同一行有多条**命中行且国别一致时决定用哪条证据（P2），绝不裁决国别冲突。

    证据两级（D6）：
      1. 案件级直接证据（case_origin.csv，键=印刷引证）——**保留全部**命中行的
         evidence id（不只第一条）；多国并存 → 成员本地 CONFLICT（成员本地冲突
         不许被空 origin_country 隐瞒）。
      2. 法院排他来源地规则（court_or_reporter_scope.csv，§9.2）——仅当本行
         **已是被接受的 neutral 解析**（citation_kind=neutral，即经法院代码表
         证实）、代码在表、年代在窗内时适用。归并表只聚 counted 候选，故
         「解析已过仲裁」由上游结构保证。basis=court_scope_rule 与 1 分档。
      3. R3：排他汇编范围（reporter_origin_scope.csv）——仅当本行是
         citation_kind=reporter 时适用；**自查表、不读 classify 的 jurisdiction**
         （P1）。窗口匹配即消歧；异国重叠 → UNDETERMINED 且记审计列。
    约束七：FOREIGN 只来自正面排他规则，绝不来自「不在加拿大例外表」。
    UKPC/JCPC 等跨法域法院不在规则表 → UNDETERMINED（§9.3）。"""
    row["member_origin_ambiguous_basis"] = ""
    row["member_origin_exclusivity"] = ""
    hits = []
    for s in member_strings:
        for h in origin_idx.get(nk(s), []):
            if h not in hits:
                hits.append(h)
    evids = ["case_origin:" + (h.get("normalized_key") or "") for h in hits]

    def _country(h):
        # R4：两张案件级表列名不同——case_origin.csv 用 `case_origin`；
        # case_origin_manual.csv（任务书列名）用 `origin_country`。二者同义，
        # 都读；缺列不得静默当「无国家」（r4b 首轮即因只读 case_origin 而
        # 命中 0——连接上了却取不到国家）。
        return ((h.get("case_origin") or h.get("origin_country") or "")
                .strip())

    countries = sorted({_country(h) for h in hits if _country(h)})
    if len(countries) == 1:
        row["member_origin_country"] = countries[0]
        row["member_origin_status"] = "DETERMINED"
        row["member_origin_basis"] = "case_record"
        row["member_origin_evidence_ids"] = "|".join(evids)
        row["member_origin_conflict_detail"] = ""
        row["deciding_court"] = hits[0].get("deciding_court") or ""
        stats["case_origin_determined"] += 1
    elif len(countries) > 1:
        # 成员本地冲突：同一印刷串在表里指向两个来源国
        row["member_origin_country"] = ""
        row["member_origin_status"] = "CONFLICT"
        row["member_origin_basis"] = "case_record"
        row["member_origin_evidence_ids"] = "|".join(evids)
        row["member_origin_conflict_detail"] = ";".join(countries)
        row["member_origin_subdivision"] = ""
        stats["case_origin_conflict"] += 1
    else:
        row["member_origin_country"] = ""
        row["member_origin_status"] = "UNDETERMINED"
        row["member_origin_basis"] = ""
        row["member_origin_evidence_ids"] = ""
        row["member_origin_conflict_detail"] = ""
        row["member_origin_subdivision"] = ""
        row["deciding_court"] = ""
        if scope_idx:
            _scope_origin(row, scope_idx, stats)
        if row["member_origin_status"] == "UNDETERMINED" and reporter_idx:
            _reporter_origin(row, reporter_idx, stats)
        if row["member_origin_status"] == "UNDETERMINED":
            stats["case_origin_undetermined"] += 1
    row["origin_subdivision"] = row.get("member_origin_subdivision", "")


def _scope_origin(row, scope_idx, stats):
    """法院排他来源地规则（§9.2；R2-4 收紧适用条件）。
    适用条件（全部满足）：本行是被接受的 neutral 解析（citation_kind=neutral，
    即代码经法院代码表证实——「有年份+无卷号」本身**不是**引证种类的证明）；
    代码（键 v2 abbr 槽）在 scope 表且唯一；年代落在规则的标识符适用窗内。"""
    if (row.get("citation_kind") or "") not in ("neutral", "identifier"):
        stats["scope_not_neutral_parse"] += 1
        return
    p = row["merge_key"].split("|")
    if len(p) < 5 or not p[0].isdigit() or p[1]:
        return
    code = nk(p[2])
    rows_ = scope_idx.get(code)
    if not rows_ or len(rows_) != 1:
        return
    r = rows_[0]
    y = int(p[0])
    vf = int(r["valid_from"]) if (r.get("valid_from") or "").strip().isdigit() else 0
    vt = int(r["valid_to"]) if (r.get("valid_to") or "").strip().isdigit() else 9999
    if not (vf <= y <= vt):
        stats["scope_era_excluded"] += 1
        return
    oc = r["origin_country_scope"]
    row["member_origin_country"] = oc
    row["member_origin_status"] = "DETERMINED"
    row["member_origin_basis"] = "court_scope_rule"
    row["member_origin_evidence_ids"] = "scope:" + (r.get("printed_key") or code)
    row["member_origin_conflict_detail"] = ""
    row["member_origin_subdivision"] = r.get("origin_subdivision_scope") or ""
    row["deciding_court"] = r.get("deciding_court") or ""
    stats["case_origin_by_scope"] += 1


# ---- R2-1/R2-9：身份基础、组聚合、有效来源关联 ----
BASIS_RANK = {"anchor": 6, "singleton": 6, "same_citation": 5,
              "anchor_variant_bilingual": 4, "anchor_variant_typo_number": 3,
              "anchor_variant_typo_year": 3,
              "name_year": 2, "cocitation": 1, "unanchored": 1}
# 只有显式、可审计的身份等价规则才授权组内传播（R2 订正 §1）：
#   anchor/singleton = 键本身就是该身份（或唯一成员用直接证据）；
#   same_citation = 同一印刷标识（跨院同键）；
#   anchor_variant_bilingual = 已核实的双语标识映射。
# name_year / anchor_variant_typo / cocitation / unanchored 是启发式——保持可见、
# 保持暂定，不得把成员证据升成组结论。
ELIGIBLE_BASES = frozenset(("anchor", "singleton", "same_citation",
                            "anchor_variant_bilingual"))


def assign_identity_basis(members, did_idx, start, reason):
    """给组内每个成员行标 identity_basis（How it joined this identity）。
    reason 是该组的 split_reason（""=未拆，含 decision=按判决拆分指派，
    含 unanchored=无锚拼组）。"""
    root, anc, ajur, own, root_kind = decisions_of(members, did_idx, start)
    anchors = {k for k in anc if root.get(k) == k}
    keycount = Counter(m["merge_key"] for m in members)
    # R2 闭环 4.3：same_citation 只有在**全组只有一个 merge_key**时才成立——
    # 该键本身就是组的身份。组内存在多个不同键时，重复出现的非锚键保留其实际
    # 加入依据（typo 变体/name_year/共引），不因重复次数升级。
    single_key_group = len(keycount) == 1
    out = {}
    for m in members:
        k = m["merge_key"]
        if len(members) == 1:
            b = "singleton"
        elif k in anchors:
            b = "anchor"
        elif k in root and root[k] != k:
            b = "anchor_variant_" + root_kind.get(k, "typo")
        elif single_key_group:
            b = "same_citation"
        elif "unanchored" in (reason or ""):
            b = "unanchored"
        elif "identifier_uncoited" in (reason or ""):
            # R2F：identifier 单元经既有共引合并连入身份——basis=cocitation
            # （不参与来源传播，与跨系统连接规则一致）
            b = "cocitation"
        elif "decision" in (reason or ""):
            b = "cocitation"
        else:
            b = "name_year"
        out[row_key(m)] = b
    return out


def aggregate_group_origin(group_rows, stats):
    """R2-1：组级来源地 = 合格成员（ELIGIBLE_BASES）的成员级观察聚合。
    无正证据 → UNDETERMINED；恰一国 → 该国（带全部证据 id）；
    多国或合格成员本地未决冲突 → 整组 CONFLICT（证据全保留）。
    启发式成员（name_year/cocitation/typo）的证据**不**升组，记入
    noncore_origin_evidence 审计列。组级结果写到**每一行**（两轮都做）。"""
    core = [r for r in group_rows if r.get("identity_basis") in ELIGIBLE_BASES]
    pos = [r for r in core if r.get("member_origin_status") == "DETERMINED"
           and (r.get("member_origin_country") or "").strip()]
    conf = [r for r in core if r.get("member_origin_status") == "CONFLICT"]
    noncore = [r for r in group_rows if r.get("identity_basis") not in ELIGIBLE_BASES
               and r.get("member_origin_status") == "DETERMINED"]
    noncore_ev = ";".join(sorted(
        {"%s:%s:%s" % (r.get("identity_basis"), r.get("member_origin_country"),
                       r.get("member_origin_evidence_ids")) for r in noncore}))
    countries = sorted({r["member_origin_country"] for r in pos})
    eids, bases = [], []
    for r in (pos if len(countries) == 1 else pos + conf):
        for e in (r.get("member_origin_evidence_ids") or "").split("|"):
            if e and e not in eids:
                eids.append(e)
        if r.get("member_origin_basis") and r["member_origin_basis"] not in bases:
            bases.append(r["member_origin_basis"])
    if conf or len(countries) > 1:
        g_country = ""
        g_status = "CONFLICT"
        g_foreign = "CONFLICT"
        stats["origin_conflict_groups"] += 1
    elif len(countries) == 1:
        g_country = countries[0]
        g_status = "DETERMINED"
        g_foreign = "DOMESTIC_CA" if g_country == "CA" else "FOREIGN"
        stats["group_origin_determined"] += 1
    else:
        g_country = ""
        g_status = "UNDETERMINED"
        g_foreign = "UNDETERMINED"
        stats["group_origin_undetermined"] += 1
    subs = sorted({(r.get("member_origin_subdivision") or "").strip()
                   for r in pos})
    g_sub = subs[0] if len(subs) == 1 else ""
    for r in group_rows:
        r["origin_subdivision"] = g_sub
        r["group_origin_country"] = g_country
        r["group_origin_status"] = g_status
        r["group_foreign_status"] = g_foreign
        r["group_origin_basis"] = "+".join(bases)
        r["group_origin_evidence_ids"] = "|".join(eids)
        r["noncore_origin_evidence"] = noncore_ev
        # 兼容别名（round-1 列名保留，语义升为组级结论）
        r["foreign_status"] = g_foreign
        r["origin_country"] = g_country
        r["case_origin"] = g_country if g_status == "DETERMINED" else g_status
        r["origin_basis"] = "+".join(bases)
        r["origin_evidence_id"] = eids[0] if eids else ""


def build_effective_sources(group_rows, ids, selfd, did_idx, stats):
    """R2-9：显式的「有效来源→组」关联（decide 是唯一权威，edges 只消费它）。
    status=counted 的来源集合 == 该组的 dd 集合（同口径）；被剔的自引
    （excluded_self）保留在关联里供审计，不得作为普通边重现。"""
    all_d = set()
    for m in group_rows:
        all_d |= did_idx.get(row_key(m), set())
    out = []
    for d in sorted(all_d):
        via = [m for m in group_rows if d in did_idx.get(row_key(m), set())]
        best = max((BASIS_RANK.get(m.get("identity_basis") or "unanchored", 0),
                    m.get("identity_basis") or "unanchored") for m in via)
        excluded = d in selfd
        out.append({
            "merged_group_id": group_rows[0]["merged_group_id"],
            "source_decision": d,
            "status": "excluded_self" if excluded else "counted",
            "exclusion_reason": ("group's own decision (self-citation via "
                                 "identity root)") if excluded else "",
            "identity_status": best[1],
            "via_member_row_keys": "|".join(sorted(row_key(m) for m in via)),
        })
    n_counted = sum(1 for r in out if r["status"] == "counted")
    if n_counted != len(ids):
        stats["effective_source_count_mismatch"] += 1
    return out


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


def adjudicate(rows, did_idx, origin_idx, folded_idx, prefix, stats, redo_origin,
               scope_idx=None, reporter_idx=None, registry=None, typo_over=None,
               holdout=None,
               gate="literal"):
    start = neutral_start(rows)
    stats["neutral_rows_before_court_start"] = sum(
        1 for r in rows if r.get("citation_kind") == "neutral" and _before_start(r["merge_key"], start))
    clusters = cluster_same_case(rows, did_idx, stats, start, registry, typo_over,
                                 gate, holdout)
    # PROBLEMS #88：混合键的案名被自己的提及互相推翻（既印着折叠目标的名字、
    # 又印着别的名字）→ **不主张案名**（约束四：无证据不填值；约束五：行不删，
    # 只打标记）。这一步必须在按名挂靠之前做：不抹名，扣留下来的键会变成同名
    # 同年的对手组，把真组的平行引证挂靠打散（第一期实测 Housen 的
    # 211 D.L.R. (4th) 577 掉成 singleton）。
    if holdout:
        mixed = {h[0] for h in holdout}
        for r in rows:
            if r["merge_key"] in mixed and (r.get("case_name_modal") or ""):
                r["case_name_modal"] = ""
                prev = r.get("name_rejected_reason") or ""
                r["name_rejected_reason"] = (prev + "|mixed_identity"
                                             if prev else "mixed_identity")
                stats["mixed_identity_names_suppressed"] += 1
    clusters.sort(key=lambda c: min(row_key(m) for m in c[0]))

    out, out_ids, eff_rows = [], [], []
    for gseq, (members, reason, seq) in enumerate(clusters):
        gid = "%s-G%06d" % (prefix, gseq)
        ids = set()
        for m in members:
            ids |= did_idx.get(row_key(m), set())
        # 剔自身（#54）：只剔身份根——被当笔误并进本组的键，其判决若引了本组是真引用
        root, anc, ajur, own, root_kind = decisions_of(members, did_idx, start)
        selfd = set()
        for k, r in root.items():
            if k == r:
                selfd |= own[k]
        stats["self_ids_removed"] += len(ids & selfd)
        ids -= selfd
        occ = sum(key_occ(m) for m in members)
        primary = min(members, key=lambda m: (-key_occ(m), row_key(m)))

        # 上界计数（不是判定，混着笔误变体与双语代码，见 PROBLEMS #49）
        if len({m["merge_key"] for m in members
                if m.get("citation_kind") == "neutral"}) > 1:
            stats["groups_with_multiple_neutral_strings"] += 1

        # R2-1：逐成员身份基础（如何连到本组身份）——院内与跨院轮都算
        basis_map = assign_identity_basis(members, did_idx, start, reason)

        group_rows = []
        for m in members:
            r = dict(m)
            r["key_occurrence_count"] = key_occ(m)
            r["identity_basis"] = basis_map.get(row_key(m), "unanchored")
            if redo_origin:
                # 成员级观察（R2-1）：只看本行键自己的证据，不继承组结论
                decide_case_origin(r, folded_idx.get(m["merge_key"],
                                                     [m["canonical_string"]]),
                                   origin_idx, stats, scope_idx, reporter_idx)
            else:
                # 跨法院轮：成员观察沿用院内轮的 member_origin_*（组结论不作
                # 新成员证据）；缺列的输入按 UNDETERMINED 兜底
                for c, dv in (("member_origin_country", ""),
                              ("member_origin_status", "UNDETERMINED"),
                              ("member_origin_basis", ""),
                              ("member_origin_evidence_ids", ""),
                              ("member_origin_conflict_detail", ""),
                              ("member_origin_subdivision", ""),
                              ("member_origin_ambiguous_basis", ""),
                              ("member_origin_exclusivity", "")):
                    r.setdefault(c, dv)
                r.setdefault("deciding_court", "")
            # 跨法院轮不重判成员来源地：院内轮已在成员串级别查过表，此处只有
            # canonical_string 可用，重判等于用更弱的证据覆盖更强的结论
            r["merged_group_id"] = gid
            r["is_primary"] = "true" if m is primary else "false"
            r["split_flag"] = "true" if reason else "false"
            r["split_seq"] = seq
            r["split_reason"] = reason
            r["occurrence_count"] = occ
            r["distinct_decisions_count"] = len(ids)
            # PROBLEMS #62：同名、年份相差 ≤1 的**另一个组**（跨法院轮填，见 main）。
            r["same_name_near_year_peers"] = ""
            out.append(r)
            group_rows.append(r)
            for did in sorted(did_idx.get(row_key(m), ())):
                out_ids.append({"row_key": row_key(m), "source_decision_citation": did})

        # R2-1：组级来源地 = 合格成员证据聚合（两轮都做、写到每行；
        # 冲突检查在跨院合并之后同样执行）
        aggregate_group_origin(group_rows, stats)
        # R4（D1/D2）：法院标注 → 组级审计列（只经合格身份基础；绝不写来源地）
        add_court_designation_columns(group_rows, stats)

        # R2-9：显式的有效来源→组关联（edges 只消费本关联）
        eff_rows.extend(build_effective_sources(group_rows, ids, selfd,
                                                did_idx, stats))
    stats["groups_out"] = len(clusters)
    return out, out_ids, eff_rows


def add_court_designation_columns(group_rows, stats):
    """R4（D1/D2）：把键级 `observed_deciding_court` 提升为**组级审计列**。

    只经**合格身份基础**（ELIGIBLE_BASES）传播——法院标注不随 name_year/共引等
    启发式分组流动（D1；机制 (a)/(b) 的组员混合未修，见 B21/B20）。
    组内合格成员的法院标注**唯一** → 写出；≥2 个不同法院 → 冲突、不写法院；
    没有 → 空（= 没有证据）。
    ★纯审计：**绝不**写来源地（D2：无 court→origin 规则）。"""
    courts = {(m.get("observed_deciding_court") or "").strip()
              for m in group_rows
              if (m.get("identity_basis") or "") in ELIGIBLE_BASES
              and (m.get("observed_deciding_court") or "").strip()}
    court = next(iter(courts)) if len(courts) == 1 else ""
    conflict = "true" if len(courts) > 1 else ""
    for m in group_rows:
        m["group_observed_deciding_court"] = court
        m["group_observed_deciding_court_conflict"] = conflict
    if court:
        stats["groups_with_observed_deciding_court"] += 1
    if conflict:
        stats["groups_court_designation_conflict"] += 1


def add_peer_column(out, stats):
    """PROBLEMS #62：给每个组填 `same_name_near_year_peers`——同名（nk 后相等）、
    主行年份相差 ≤ 1 的**其他组**的组号，分号连接。

    只在跨法院轮调用（跨院合并跑完后才是最终分组；`kept` 在选取层才定，故这里对
    **所有**组算，读者按自己的 kept/dd 门槛筛）。不合并、只标记：这两类东西在数据里
    无法分辨——真不同的判决（R. v. John 每年一件）与同一判决的两种写法（从不在同一
    份判决里共现，见 PROBLEMS #55 的零共引残余）。
    """
    name, year = {}, {}
    for r in out:
        if r["is_primary"] == "true":
            gid = r["merged_group_id"]
            name[gid] = nk(r.get("case_name_modal") or "")
            year[gid] = row_year(r)     # R3：印出来的年份（见 row_year 的说明）
    by_name = defaultdict(list)
    for gid, nm in name.items():
        if nm and year.get(gid) is not None:
            by_name[nm].append(gid)
    peers = defaultdict(set)
    for nm, gids in by_name.items():
        gids = sorted(gids)
        for i, ga in enumerate(gids):
            for gb in gids[i + 1:]:
                if abs(year[ga] - year[gb]) <= 1:
                    peers[ga].add(gb)
                    peers[gb].add(ga)
    for r in out:
        p = peers.get(r["merged_group_id"])
        if p:
            r["same_name_near_year_peers"] = ";".join(sorted(p))
    stats["groups_with_near_year_peers"] = sum(1 for g in peers if peers[g])
    stats["groups_with_near_year_peers_max"] = max((len(v) for v in peers.values()), default=0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--court")
    ap.add_argument("--input")
    ap.add_argument("--folded-log")
    ap.add_argument("--decision-ids")
    ap.add_argument("--cross-court", action="store_true")
    ap.add_argument("--inputs", nargs="+")
    ap.add_argument("--registry", default=None,
                    help="全局判决登记簿（#88/#89）：<run>/registry/"
                         "decision_registry.csv。不传 = 空登记簿 = 行为不变；"
                         "**只授权笔误闸使用**（规格 2.3）")
    # 2026-09-17：用户裁定设为默认开启（PROBLEMS #88 销账）。--no-mixed-key-holdout
    # 关闭以复现关闭前逐字节一致的产物（判据 1 的对照仍可重放）。
    ap.add_argument("--mixed-key-holdout", action=argparse.BooleanOptionalAction,
                    default=True,
                    help="PROBLEMS #88：键的提及既印着折叠目标的案名、又印着别的"
                         "案名时（一个印刷串承担两种身份），不折叠并抑制其案名。"
                         "默认开启；--no-mixed-key-holdout 关闭以复现旧行为")
    ap.add_argument("--registry-gate", default="literal",
                    choices=("literal", "own_or_registry", "registered_only"),
                    help="登记簿在笔误闸里怎么参与：literal = 规格 2.3 逐字写法"
                         "（or k in registry 会被同名闸旁路，实测 0 键变化）；"
                         "own_or_registry = 规格 2.3 的字面意图；"
                         "registered_only = 登记簿命中但本地看不见它是真判决即挡住。"
                         "**三档均不能修 #88**（registered_only 会把真组的平行引证"
                         "挂靠打散，见 PROBLEMS #88 与 implementation/"
                         "report_88_89_registry.md）；保留供后续测量。默认 literal，"
                         "见 manifest.registry_gate")
    ap.add_argument("--output", required=True)
    a = ap.parse_args()

    stats = Counter()
    registry = load_registry(a.registry)
    stats["registry_keys"] = len(registry)
    typo_over = []
    # PROBLEMS #88：混合键留痕。**None = 规则关闭**（默认），传列表才启用——
    # 关闭时 decisions_of 的判据整段短路，产物与改动前逐字节一致。
    holdout = [] if a.mixed_key_holdout else None
    origin_idx = load_case_origin()
    # R4 Stage 3：人工核验批次并入同一 case_record 索引（同为案件级直接证据、
    # 最高优先级；两表冲突 → 成员本地 CONFLICT，方向保守）。
    manual_idx = load_case_origin_manual()
    for k, rows in manual_idx.items():
        origin_idx.setdefault(k, []).extend(rows)
    stats["case_origin_manual_rows"] = sum(len(v) for v in manual_idx.values())
    scope_idx = load_scope()
    reporter_idx = load_reporter_origin()
    stats["scope_rules_verified"] = sum(len(v) for v in scope_idx.values())
    stats["reporter_scope_rows_verified"] = sum(len(v)
                                                for v in reporter_idx.values())
    stats["reporter_scope_abbrs"] = len(reporter_idx)

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
    out, out_ids, eff_rows = adjudicate(rows, did_idx, origin_idx, folded_idx,
                                        prefix, stats, redo, scope_idx,
                                        reporter_idx, registry, typo_over,
                                        holdout,
                                        a.registry_gate)
    # PROBLEMS #62：同名、年份相差 ≤1 的同级组。只在跨法院轮算——跨院合并跑完才是
    # 最终分组；院内轮该列留空（它不是产品列，选取层读的是跨院产出）
    if a.cross_court:
        add_peer_column(out, stats)
    stats["output_rows"] = len(out)
    stats["decision_id_rows"] = len(out_ids)
    # #88/#89 机制 A 留痕：键是真判决自己的引证（登记簿命中或本轮 own）、
    # 但头部案名与本组组名不一致 → 仍被当笔误并掉。每行 = 一次这样的判断。
    stats["mixed_identity_holdouts"] = len(holdout or [])
    stats["mixed_identity_keys"] = len({r[0] for r in (holdout or [])})
    stats["typo_over_registered_decisions"] = len(typo_over)
    stats["typo_over_registered_keys"] = len({r[0] for r in typo_over})

    # ---- 不变量，不过就拒绝写表 ----
    assert len(out) == len(rows), "行数 %d != 输入 %d（约束五）" % (len(out), len(rows))
    # R2F：任一组内同系统 identifier 至多一个键（不同编号=不同文档）
    _ident_by_group = defaultdict(lambda: defaultdict(set))
    for r in out:
        if r.get("citation_kind") == "identifier":
            sysname = identifier_system_of(r["merge_key"])
            if sysname:
                _ident_by_group[r["merged_group_id"]][sysname].add(r["merge_key"])
    _bad = [(g, sy, ks) for g, per in _ident_by_group.items()
            for sy, ks in per.items() if len(ks) > 1]
    assert not _bad, "R2F 违约：组内含同系统多个 identifier 键 %r" % _bad[:3]
    groups = defaultdict(list)
    for r in out:
        groups[r["merged_group_id"]].append(r)
    assert sum(int(ms[0]["occurrence_count"]) for ms in groups.values()) == in_occ_total, \
        "守恒破：各组 occurrence 之和 != 各行原始计数之和 %d（重复累加？）" % in_occ_total
    assert all(int(r["distinct_decisions_count"]) <= int(r["occurrence_count"])
               for r in out), "dd 大于 occurrence，说明取了相加"
    wide = [g for g, ms in groups.items()
            if len({row_year(m) for m in ms
                    if m.get("case_name_modal") and row_year(m)}) > 0
            and (lambda ys: max(ys) - min(ys))(
                [row_year(m) for m in ms
                 if m.get("case_name_modal") and row_year(m)]) > 1]
    assert not wide, "有组的年份跨度 > 1：%r" % wide[:5]
    start = neutral_start(rows)
    multi = [g for g, ms in groups.items()
             if len(set(decisions_of(ms, did_idx, start)[0].values())) > 1]
    assert not multi, "有组仍含多个不同判决：%r" % multi[:5]

    os.makedirs(a.output, exist_ok=True)
    # PROBLEMS #88：`name_classes` 是归并层供给本层判据的**输入**列，不进本层产物
    # ——留着会把 decided.csv 的列整体后移，判据 1（默认关闭时逐字节一致）就废了。
    fields = [f for f in (list(out[0].keys()) if out else [])
              if f != "name_classes"]
    typo_rows = [{"merge_key": k, "folded_into": big,
                  "registry_decision_id": (registry.get(k, ("", ""))[0]
                                           if registry else ""),
                  "registry_source_court": (registry.get(k, ("", ""))[1]
                                            if registry else ""),
                  "typo_kind": kind, "key_anchor_ids": dda,
                  "folded_into_anchor_ids": ddb}
                 for k, big, _registered, kind, dda, ddb in typo_over]
    for name, flds, data in (("decided.csv", fields, out),
                             ("decision_ids.csv",
                              ["row_key", "source_decision_citation"], out_ids),
                             ("effective_sources.csv",
                              ["merged_group_id", "source_decision", "status",
                               "exclusion_reason", "identity_status",
                               "via_member_row_keys"], eff_rows),
                             # #88/#89 机制 A 的留痕清单（原先隐形）。不传
                             # --registry 时为空文件（只有表头），行为不变。
                             ("typo_over_registered.csv",
                              ["merge_key", "folded_into", "registry_decision_id",
                               "registry_source_court", "typo_kind",
                               "key_anchor_ids", "folded_into_anchor_ids"],
                              typo_rows),
                             # #88：混合键（一个印刷串承担两种身份）的扣留清单。
                             # 不传 --mixed-key-holdout 时为空文件（只有表头）。
                             ("mixed_identity_holdouts.csv",
                              ["merge_key", "folded_into", "folded_into_name",
                               "name_classes", "named_mentions",
                               "key_anchor_ids", "folded_into_anchor_ids"],
                              [{"merge_key": k, "folded_into": big,
                                "folded_into_name": bn, "name_classes": ncs,
                                "named_mentions": nm, "key_anchor_ids": dda,
                                "folded_into_anchor_ids": ddb}
                               for k, big, bn, ncs, nm, dda, ddb in (holdout or [])])):
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
        "registry_file": a.registry or "",
        "registry_gate": a.registry_gate,
        "mixed_key_holdout": bool(a.mixed_key_holdout),
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
