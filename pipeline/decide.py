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
import hashlib
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import nk                                      # noqa: E402
from artifacts import open_csv                               # noqa: E402
from identity_constraints import ConstraintLedger
from identity_evidence import EvidenceSnapshot
from identity_evidence import (
    load_identity_separations,
    load_case_origin,
    load_case_origin_manual,
    load_scope,
    load_reporter_origin,
    year_of,
    row_year,
    row_key,
    key_occ,
    _neutral_parts,
    load_identifier_systems,
    identifier_system_of,
    load_bilingual,
    parse_name_classes,
    _self_of,
    load_registry,
    OwnCitations,
    load_own_citations,
    neutral_start,
    _before_start,
    read_csv,
    load_decision_ids,
    ROOT,
    DECISIONS,
    SEPARATION_FIELDS,
    CASE_ORIGIN_MANUAL_STATUS,
    REPORTER_ORIGIN_ALLOWED_STATUSES,
    ALLOWED_IDENTIFIER_STATUSES,
    _IDENTIFIER_CACHE,
    ALLOWED_BILINGUAL_STATUSES,
    _BILINGUAL_CACHE)
from identity_solve import (
    windows,
    _one_edit,
    mixed_identity,
    verified_bilingual_keys,
    same_decision_kind,
    same_decision,
    decisions_of,
    _unknown,
    _compatible,
    _with_held,
    _identifier_keys,
    _combined_identifier_keys,
    split_by_decision,
    cluster_same_case,
    merge_document_alias_clusters,
    assign_identity_basis,
    solve_identity)









# R4 Stage 3：案件级人工核验批次只消费「全部证明项齐备」的行——其余状态
# （unresolved_within_budget 等）不入表（约束四：无证据不给判定）。






# ---- R3：排他汇编来源地（P1/P2/P2′）--------------------------------------
# 只有**已核实**的排他行参与推断。两档排他性（P2）：
#   exclusive_statute   有约束力的法律/宪制文本规定其刊登范围
#   exclusive_publisher 只有出版方自己的编辑方针（须带反例搜寻记录）
REPORTER_ORIGIN_TIER = {
    "exclusive_statute": 2,
    "exclusive_publisher": 1,
}




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













# ------------------------------------------------------------ §10.4 按判决拆分




# R2F：identifier 系统（数据库/厂商决策 ID）。加载verified行，键=nk(printed_token)。






























def own_citation_self_ids(members, did_idx, ids, own_cites, root_kind, stats):
    """PROBLEMS #105：返回应从本组 DD 里剔掉的「只在提及自己」的来源判决 id。

    own_cites = {merge_key: {判决 id}}：每件判决自己印的引证（citation_en / citation2_en）。
    某来源判决 d 提及本组**只**经过它自己印的那些键（头部并行引证 `[2003] 1 S.C.R. 39`、
    补零写法等）→ 它在提及自己，不计 DD。只要 d 还经由别的键提及本组（例：SCC 判决引用了
    自己上诉自的下级判决，下级判决的报告引注是另一个键），那就是对另一份判决的真实提及，
    照常计入——用户裁定（2026-10-03）：审理历史关系计入 DD，之后按关系类型标记筛选。
    笔误并入的键不算 d 自己的键（#54 的原意：被当笔误并进来的键可能是另一件判决）。
    own_cites 为空 → 返回空集（行为与改动前一致）。"""
    out = set()
    if not own_cites:
        return out
    via = defaultdict(set)             # 来源判决 -> 它经由哪些键提及本组
    for m in members:
        for d in did_idx.get(row_key(m), ()):
            via[d].add(m["merge_key"])
    for d in sorted(ids):
        own_keys = {k for k in via[d]
                    if d in own_cites.get(k, ())
                    and root_kind.get(k) not in ("typo_number", "typo_year")}
        if own_keys and via[d] <= own_keys:
            stats["self_ids_removed_own_citation"] += 1
            out.add(d)
        elif own_keys:
            stats["own_key_plus_other_key_kept"] += 1   # 自己的键之外还有别的键：保留
    return out








BAR = 0.8   # 「几乎总是一起印」。待定审计实测覆盖率双峰，取 0.5 或 0.8 只差 6 条

# 案名支持度（归并层 `case_name_support` = 赢家票数 / 计数行数）**照常随列流过本层，
# 但不设闸**（PROBLEMS #60）。曾按支持度设闸、实测后撤掉：过门槛组里支持度 < 0.10 的
# 有 244 个（本行数字随每次重跑变，口径是「过门槛且切出案名的组，支持度 < 0.10」；
# #60 登记时的 268 是 #61 落地前那一版的数），闸一开只影响 32 组，而这 32 组**无一
# 例外**是同一案子的平行汇编被拆开（Kienapple 273→18+256、Lifchus 166→68+99、
# Suresh 66→63+12……），并且新增 8 处「同一印刷串落两组」——正是 #49 修掉的撕裂形态，
# 而消除 0 处。低支持度的成因是「这案子主要被中立引用引、不印案名」，不是名字错；
# 要判断名字可不可信得看别的证据。














# ------------------------------------------------------------ §10.3 + §10.4


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
BASIS_RANK = {"anchor": 6, "singleton": 6, "document_alias": 6, "same_citation": 5,
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
                            "anchor_variant_bilingual", "document_alias"))




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
    # A local conflict still supplies essential evidence even when another core
    # member has one determined country. Group status and evidence must agree.
    for r in pos + conf:
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








def adjudicate(rows, did_idx, origin_idx, folded_idx, prefix, stats, redo_origin,
               scope_idx=None, reporter_idx=None, registry=None, typo_over=None,
               holdout=None,
               gate="literal", own_cites=None, identity_separations=None, trace=None):
    if trace is None:
        trace = ConstraintLedger(EvidenceSnapshot(rows, did_idx, prefix, registry,
                                                  own_cites, identity_separations))
    clusters, start = solve_identity(rows, did_idx, prefix, stats, registry,
                                    typo_over, holdout, gate, own_cites,
                                    identity_separations, trace)

    out, out_ids, eff_rows = [], [], []
    for gseq, (members, reason, seq) in enumerate(clusters):
        gid = "%s-G%06d" % (prefix, gseq)
        trace.event('assigned_group_id', members, 'assigned', reason, group_id=gid)
        ids = set()
        for m in members:
            ids |= did_idx.get(row_key(m), set())
        # 剔自身（#54）：只剔身份根——被当笔误并进本组的键，其判决若引了本组是真引用
        root, anc, ajur, own, root_kind = decisions_of(members, did_idx, start)
        selfd = set()
        for k, r in root.items():
            if k == r:
                selfd |= own[k]
        selfd |= own_citation_self_ids(members, did_idx, ids - selfd, own_cites, root_kind, stats)
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
    ap.add_argument("--own-citations", default=None,
                    help="判决自己印的引证表（<run>/registry/decision_own_citations.csv）："
                         "剔自引；仅新qualified metadata/header证据可连接平行身份；旧四列只剔自引")
    # 2026-09-17：用户裁定设为默认开启（PROBLEMS #88 销账）。--no-mixed-key-holdout
    # 关闭以复现关闭前逐字节一致的产物（判据 1 的对照仍可重放）。
    ap.add_argument("--mixed-key-holdout", action=argparse.BooleanOptionalAction,
                    default=True,
                    help="PROBLEMS #88：键的提及既印着折叠目标的案名、又印着别的"
                         "案名时（一个印刷串承担两种身份），不折叠并抑制其案名。"
                         "默认开启；--no-mixed-key-holdout 关闭以复现旧行为")
    ap.add_argument("--registry-gate", default="literal",
                    choices=("literal", "own_or_registry", "registered_only", "registered"),
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
    own_cites = load_own_citations(a.own_citations)
    separations = load_identity_separations()
    separations_path = os.path.join(DECISIONS,'identity_separations.csv')
    with open(separations_path,'rb') as separation_source:
        separations_sha256 = hashlib.sha256(separation_source.read()).hexdigest()
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
    trace = ConstraintLedger(EvidenceSnapshot(rows, did_idx, prefix, registry,
                                             own_cites, separations), a.output)
    out, out_ids, eff_rows = adjudicate(rows, did_idx, origin_idx, folded_idx,
                                        prefix, stats, redo, scope_idx,
                                        reporter_idx, registry, typo_over,
                                        holdout,
                                        a.registry_gate, own_cites, separations, trace)
    trace_manifest = trace.close()
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
             if len(set(decisions_of(ms, did_idx, start, registry, None,
                                     a.registry_gate)[0].values())) > 1]
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
        "schema_version": 14,
        "identity_trace": trace_manifest,
        "document_alias_policy": "Qualified source-unique metadata/header proof only; whole-component neutral/vendor/court cannot-links remain enforced.",
        "registry_file": a.registry or "",
        "own_citations_file": a.own_citations or "",
        "identity_separations_file": separations_path,
        "identity_separations_sha256": separations_sha256,
        "identity_separations": separations,
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
