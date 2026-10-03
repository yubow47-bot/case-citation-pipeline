# -*- coding: utf-8 -*-
"""test_layers.py — 分类 / 归并 / 裁定 / 选取四层的回归防线

用法
    python pipeline/tests/test_layers.py                 # 单元断言 + 迷你全链（合成数据，秒级）
    python pipeline/tests/test_layers.py --golden        # 当前 data/ 产出对照金标（全量差分）
    python pipeline/tests/test_layers.py --golden-write  # 显式重写金标（改了规则、复核过数字后才用）

失败即退出码非 0。每条断言钉着一个真实栽过的坑并注明 PROBLEMS 号——删断言前先读那一条。

分工：抽取层（七个正则）归 run_regression.py；本文件管第 2–5 层的规则与接线。
迷你全链不经抽取与分类，直接造 classified.csv 喂归并层，再走院内裁定、跨院裁定、
选取——#47 那种「每层单看都对、接起来才错」的缺陷，只有全链测得出来。

金标（golden_layers.json）是全量跑的摘要：各层 manifest 的计数 + 最终榜单前 25 组。
改规则后先跑全链、再跑 --golden 看差分；差分是预期内的、逐项复核过，才 --golden-write。
"""
import argparse
import csv
import io
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.dirname(HERE)
ROOT = os.path.dirname(PIPE)
sys.path.insert(0, PIPE)

import classify                                               # noqa: E402
import decide                                                 # noqa: E402
from normalize import nk                                      # noqa: E402

GOLDEN = os.path.join(HERE, "golden_layers.json")
PASSED = []


def check(cond, label):
    if not cond:
        raise AssertionError(label)
    PASSED.append(label)


# ============================================================ 分类层（单元）
def test_admit_candidate():
    def name(s):
        return classify.admit_candidate(s)[0]
    check(name("24] R. v. Smith") == "R. v. Smith", "#43 剥判决书段落编号残尾")
    check(name("3M Canada Inc. v. Smith") == "3M Canada Inc. v. Smith",
          "#43 裸数字开头不剥（会把 3M Canada 剥成 M Canada）")
    check(name("Housen v. Nikolaisen, 2002 SCC 33") == "Housen v. Nikolaisen",
          "#45 剥尾部吞进来的中立引用")
    check(name("Beall v. Smith (1873), L.R. 9 Ch. 85") == "Beall v. Smith",
          "#45 剥尾部吞进来的汇编引证")
    check(name("Voyageur (1969) Inc. v. Ally") == "Voyageur (1969) Inc. v. Ally",
          "#45 公司名里的成立年份不剥（二版把它剥成 Voyageur）")
    check(name("1420041 Ontario Inc. v. 1 King West Inc., 2012 ONSC 1")
          == "1420041 Ontario Inc. v. 1 King West Inc",
          "#45 编号公司里的数字不当年份（首版剥成 14）")
    check(name("Rapatax (1987) Inc. v. Cantax Corp. (1997), 14 C.P.C. 1")
          == "Rapatax (1987) Inc. v. Cantax Corp",
          "#45 公司年份保住、引证年份剥掉")
    check(name("Breakey v. Carter (1881) 7 Q.L.R. 286.\n[14] next") == "Breakey v. Carter",
          "#45 尾巴跨换行也剥（DOTALL，自检漏过 227 条）")
    check(name("Smith v. Jones, [1990] 2 S.C.R. 100") == "Smith v. Jones",
          "#45 方括号年份尾巴剥掉后不再被 has_bracketed_year 拒")
    check(name("R. v. R.E.M., 2008 SCC 51") == "R. v. R.E.M",
          "#45 缩写姓名也剥尾巴（首版的闸要 3 个连续字母，把它挡在门外）")
    check(name("R. v. Vu, 2013 SCC 60") == "R. v. Vu", "#45 两字姓也剥尾巴")
    check(name("R. v. Côté, 2011 SCC 46") == "R. v. Côté", "#45 带重音的姓也剥尾巴")
    # PROBLEMS #61：候选把左侧整句散文吞进来时切掉散文
    check(name("strict liability (presumably on the basis of Rylands v. Fletcher") == "Rylands v. Fletcher",
          "#61 左侧整句散文被切掉（Rylands 例一，实测 dd 8）")
    check(name("negligence, nuisance, and the rule in Rylands v. Fletcher") == "Rylands v. Fletcher",
          "#61 左侧整句散文被切掉（Rylands 例二，实测 dd 23）")
    check(name("This is not a new proposition. Lord Wright said in the seminal case of Heyman v. Darwins, Ltd")
          == "Heyman v. Darwins, Ltd", "#61 大写开头的散文同样切（不能只按小写判散文）")
    check(name("Issue estoppel was more particularly defined by Middleton J.A. of the Ontario Court "
               "of Appeal in McIntosh v. Parent") == "McIntosh v. Parent",
          "#61 切点取 in，不取更早的散文词（in/to/by 不是名称连接词）")
    check(name("Commission scolaire régionale de Chambly v. Bergevin")
          == "Commission scolaire régionale de Chambly v. Bergevin",
          "#61 法语机构名不动（左侧小写散文词不足 3 个，触发闸挡住）")
    check(name("Union des employés de commerce, local 503 v. Roy")
          == "Union des employés de commerce, local 503 v. Roy",
          "#61 当事人一侧含小写词、切点落在数字上：原样退回，不判无名（丢弃档会丢掉这个真案名）")
    check(name("Québec (Procureur général) v. Lambert") == "Québec (Procureur général) v. Lambert",
          "#61 「切点右侧必须像案名」的闸：général 是当事人一侧的一部分，不是切点")
    check(name("the subsequent case of Swiderski et al. v. Broy Engineering Ltd. et al")
          == "Swiderski et al. v. Broy Engineering Ltd. et al",
          "#61 不会把原告一侧切掉（et al. 是小写词，between 不像案名则往前退）")
    check(name("Thomson Newspapers Ltd. v. Canada (Director of Investigation and Research, Restrictive "
               "Trade Practices Commission)")
          == "Thomson Newspapers Ltd. v. Canada (Director of Investigation and Research, Restrictive "
             "Trade Practices Commission)",
          "#61 长机构名不动（实测 dd 100）")
    check(name("Voyageur (1969) Inc. v. Ally") == "Voyageur (1969) Inc. v. Ally", "#61 公司名年份不受影响")


def _row(shape, raw, **kw):
    r = {"shape_name": shape, "raw_string": raw, "token": "", "abbr": "", "leading_abbr": "",
         "vol": "", "year_start": "", "series": "", "page": "", "preceding_text": ""}
    r.update(kw)
    return r


def _classifier():
    court = [{"court_code": "SCC", "normalized_key": "SCC", "jurisdiction": "CA"},
             {"court_code": "FC", "normalized_key": "FC", "jurisdiction": "CA"}]

    def rep(abbr, jur, y0="", y1=""):
        return {"abbreviation": abbr, "normalized_key": nk(abbr), "jurisdiction": jur,
                "confidence": "estimated", "vol_range_start": "", "vol_range_end": "",
                "year_range_start": y0, "year_range_end": y1}
    reporter = [rep("F.C.", "CA"), rep("K.B.", "GB"), rep("K.B.", "QC"),
                rep("W.L.R.", "GB", "1953"), rep("W.L.R.", "CA", "1905", "1916"),
                rep("S.C.R.", "CA")]
    return classify.Classifier({"neutral_court_codes": court,
                                "reporter_jurisdiction": reporter,
                                "series_prefix": []}, Counter())


def test_classifier():
    c = _classifier()
    r = c.run_row(_row("shape_neutral_bare", "2019 SCC 65", token="SCC", year_start="2019", page="65"))
    check((r["citation_kind"], r["jurisdiction"], r["lookup_mode"]) == ("neutral", "CA", "exact"),
          "中立码精确命中")
    r = c.run_row(_row("shape_bracket", "[1979] 1 F.C. 103", token="F.C.", vol="1",
                       year_start="1979", page="103"))
    check((r["citation_kind"], r["jurisdiction"]) == ("reporter", "CA"),
          "#33 带卷号的 F.C. 不走归一退路撞中立码 FC，按汇编定法域")
    r = c.run_row(_row("shape_bracket", "[2002] S.C.C. 79", token="S.C.C.", year_start="2002", page="79"))
    check((r["citation_kind"], r["jurisdiction"], r["lookup_mode"])
          == ("ambiguous", "UNSUPPORTED", "normalized"),
          "#36 归一命中不是印刷事实，不下判定")
    r = c.run_row(_row("shape_neutral_bare", "2010 FC 30", token="FC", year_start="2010", page="30"))
    check((r["citation_kind"], r["jurisdiction"], r["rejected_reason"]) == ("neutral", "CA", ""),
          "#41 精确中立码胜过归一汇编，不判 table_conflict")
    # ---- PROBLEMS #105：补零是同一个号码（BCCA_2003bcca443 头部印 `2003 BCCA 0443`）
    r = c.run_row(_row("shape_neutral_bare", "2003 SCC 05", token="SCC", year_start="2003", page="05",
                       source_decision_citation="SCC_2003scc5"))
    check(r.get("self_citation") == "true", "#105 头部补零写法 `2003 SCC 05` == 判决自身 2003scc5，标自引")
    r = c.run_row(_row("shape_neutral_bare", "2003 SCC 50", token="SCC", year_start="2003", page="50",
                       source_decision_citation="SCC_2003scc5"))
    check(r.get("self_citation") != "true", "#105 5 与 50 不是同一个号码，不标自引")
    r = c.run_row(_row("shape_bracket", "[1920] 1 K.B. 257", token="K.B.", vol="1",
                       year_start="1920", page="257"))
    check(r["jurisdiction"] == "UNSUPPORTED", "同形异义无区间可消，不猜")
    for year, want in (("1960", "GB"), ("1910", "CA"), ("1930", "UNSUPPORTED")):
        r = c.run_row(_row("shape_bracket", "[%s] 1 W.L.R. 5" % year, token="W.L.R.", vol="1",
                           year_start=year, page="5"))
        check(r["jurisdiction"] == want, "§8.6 年份区间消歧：%s 年的 W.L.R. -> %s" % (year, want))
    r = c.run_row(_row("shape_leading_abbr", "R.P. 2012 SCC 22", leading_abbr="R.P.", abbr="SCC",
                       vol="2012", page="22",
                       preceding_text="v.\nR.P. Respondent\nIndexed as: R. v. "))
    check("party_initials" in r["rejected_reason"], "#37 当事人姓名缩写被抽成前缀：精确口径命中")
    r = c.run_row(_row("shape_vol_abbr_page", "1 S.C.R. 742", abbr="S.C.R.", vol="1",
                       year_start="1991", page="742",
                       preceding_text="As held in R. v. A.B., the rule is settled; see "))
    check("party_initials" not in (r["rejected_reason"] or ""),
          "#37 前文别处出现 R. v. A.B. 不误杀（宽口径会误杀 15,999 行）")

    # ---- PROBLEMS #85：日期形态 date_form（分类层行级拒绝，不删行）
    r = c.run_row(_row("shape_vol_abbr_page", "1 June 2007", abbr="June", vol="1", page="2007"))
    check(("date_form" in r["rejected_reason"]) and r["citation_kind"] == "reporter"
          and r["page"] == "2007",
          "#85 日期 `1 June 2007`（卷 缩写 页）按 date_form 拒；行不删、字段照填（约束五）")
    r = c.run_row(_row("shape_vol_abbr_page", "24 November, 1998", abbr="November", vol="24",
                       page="1998"))
    check("date_form" in r["rejected_reason"], "#85 全称月份忽略尾逗号（`24 November, 1998`）")
    r = c.run_row(_row("shape_vol_abbr_page", "25 December, 1990", abbr="December", vol="25",
                       page="1990"))
    check("date_form" in r["rejected_reason"], "#85 12 个全称月份都在集合里（December）")
    r = c.run_row(_row("shape_leading_abbr", "Vancouver, British Columbia 1 June 2007",
                       leading_abbr="Columbia", abbr="June", vol="1", page="2007"))
    check("date_form" in r["rejected_reason"],
          "#85 第二条读法同样拦：`Columbia 1 June 2007` 的前置缩写槽也是月份")
    for raw, ab, v, p in (("90 March 17", "March", "90", "17"),
                          ("21 March 45", "March", "21", "45"),
                          ("29 June 16", "June", "29", "16"),
                          ("31 December 21", "December", "31", "21"),
                          ("32 May 2001", "May", "32", "2001"),
                          ("5 May 2100", "May", "5", "2100")):
        r = c.run_row(_row("shape_vol_abbr_page", raw, abbr=ab, vol=v, page=p))
        check("date_form" not in (r["rejected_reason"] or ""),
              "#85 三条件不齐不拦：%s（卷 1-31 与页 1600-2099 两界都要成立）" % raw)
    r = c.run_row(_row("shape_vol_abbr_page", "28 Feb. 1995", abbr="Feb.", vol="28", page="1995"))
    check("date_form" not in (r["rejected_reason"] or ""),
          "#85 缩写月份刻意不拦（#86：与报告集缩写同形，留第二期）")
    r = c.run_row(_row("shape_vol_abbr_page", "22 Janvier 1834", abbr="Janvier", vol="22", page="1834"))
    check("date_form" not in (r["rejected_reason"] or ""),
          "#85 法文月份刻意不拦（留第二期）")
    r = c.run_row(_row("shape_vol_abbr_page", "1 S.C.R. 1600", abbr="S.C.R.", vol="1", page="1600"))
    check("date_form" not in (r["rejected_reason"] or ""),
          "#85 真汇编引证不受影响（缩写不是月份全称）")
    r = c.run_row(_row("shape_vol_abbr_page", "15 January 1998", abbr="K.B.", vol="15", page="1998"))
    check((r["rejected_reason"] or "") == "",
          "#85 缩写非月份全称（K.B.）不触发 date_form，即使卷/页落在日期区间内")
    # 注：本函数只测单行分类，测不到跨候选的仲裁结果。归并层的"腾位"效应
    # （被拒行退出竞争后，同 span 的另一垃圾候选可能从 overlap_undecided 转判
    # counted）已用干净 A/B 在真实数据上复核，见 PROBLEMS #85 订正记录——
    # 5 行命中，均 occurrence=1/dd=1/kept=false，不进保留表。


def test_disambiguation():
    court = [{"court_code": "SCC", "normalized_key": "SCC", "jurisdiction": "CA"}]

    def rep(abbr, jur, v0="", v1="", y0="", y1=""):
        return {"abbreviation": abbr, "normalized_key": nk(abbr), "jurisdiction": jur,
                "confidence": "estimated", "vol_range_start": v0, "vol_range_end": v1,
                "year_range_start": y0, "year_range_end": y1}
    reporter = [rep("K.B.", "GB", "0", "4", "1901", "1952"), rep("K.B.", "QC", "5", "100", "1896", "1941"),
                rep("K.B.", "QC", "0", "0", "1942", "1970"),
                rep("Q.B.", "GB", "1", "18", "1841", "1852"), rep("Q.B.", "GB", "0", "3", "1952", "2030"),
                rep("Q.B.", "QC", "3", "11", "1893", "1901"), rep("Q.B.", "QC", "0", "0", "1942", "1969"),
                rep("Ex.", "GB"),
                rep("C. & P.", "GB", "1", "9", "1823", "1841"),
                rep("C.P.", "GB", "1", "10", "1865", "1876"), rep("C.P.", "QC", "0", "0", "1965", "1990")]
    prefix = [{"canonical_prefix": "Q.R.", "normalized_key": "QR", "jurisdiction": "QC"},
              {"canonical_prefix": "L.R.", "normalized_key": "LR", "jurisdiction": "GB"}]
    c = classify.Classifier({"neutral_court_codes": court, "reporter_jurisdiction": reporter,
                             "series_prefix": prefix}, Counter())
    r = c.run_row(_row("shape_leading_abbr", "Q.R. 56 K.B. 520", leading_abbr="Q.R.", abbr="K.B.",
                       vol="56", page="520"))
    check((r["jurisdiction"], r["disambiguated_by"], r["rejected_reason"]) == ("QC", "series_prefix", ""),
          "#52 前缀消歧：Q.R. + K.B. -> 魁北克，且前缀认得不再被拒")
    r = c.run_row(_row("shape_leading_abbr", "L.R. 3 Q.B. 141", leading_abbr="L.R.", abbr="Q.B.",
                       vol="3", page="141"))
    check(r["jurisdiction"] == "GB", "#52 前缀消歧：L.R. + Q.B. -> 英国")
    r = c.run_row(_row("shape_bracket", "[1920] 1 K.B. 257", token="K.B.", vol="1",
                       year_start="1920", page="257"))
    check((r["jurisdiction"], r["disambiguated_by"], r["jurisdiction_confidence"])
          == ("GB", "vol_year", "estimated"),
          "#52 卷号年份区间：[1920] 1 K.B. -> 英国；消歧不抬高表行成色")
    r = c.run_row(_row("shape_year_vol_page", "(1928), 45 K.B. 129", abbr="K.B.", vol="45",
                       year_start="1928", page="129"))
    check(r["jurisdiction"] == "QC", "#52 卷号年份区间：(1928), 45 K.B. -> 魁北克")
    r = c.run_row(_row("shape_bracket", "[1935] K.B. 5", token="K.B.", year_start="1935", page="5"))
    check((r["jurisdiction"], r["vol_missing"], r["disambiguated_by"]) == ("GB", "true", "novol_year"),
          "#52 不印卷号是印刷事实：1942 年前魁北克 K.B. 恒印卷号，[1935] K.B. 只能是英国")
    r = c.run_row(_row("shape_bracket", "[1943] K.B. 607", token="K.B.", year_start="1943", page="607"))
    check(r["jurisdiction"] == "UNSUPPORTED",
          "#52 1942–1952 英国与魁北克都印 [年] K.B.，两边都落，不猜")
    r = c.run_row(_row("shape_bracket", "[1975] Q.B. 326", token="Q.B.", year_start="1975", page="326"))
    check(r["jurisdiction"] == "GB", "#52 同一法域多段区间：1975 年的 Q.B. 落英国后一段")
    r = c.run_row(_row("shape_bracket", "[1962] Q.B. 277", token="Q.B.", year_start="1962", page="277"))
    check(r["jurisdiction"] == "UNSUPPORTED", "#52 [1962] Q.B. 不印卷号：英国与魁北克年份系列重叠，不猜")
    r = c.run_row(_row("shape_bracket", "[1962] 2 Q.B. 26", token="Q.B.", vol="2", year_start="1962", page="26"))
    check(r["jurisdiction"] == "GB", "#52 [1962] 2 Q.B. 印了卷号，魁北克年份系列不印，只能是英国")
    r = c.run_row(_row("shape_vol_abbr_page", "45 K.B. 198", abbr="K.B.", vol="45", page="198"))
    check((r["jurisdiction"], r["disambiguated_by"]) == ("QC", "vol_only"),
          "#52 无年份只凭卷号：英国 K.B. 每年至多 4 卷，45 卷只能是魁北克")
    r = c.run_row(_row("shape_vol_abbr_page", "3 Q.B. 5", abbr="Q.B.", vol="3", page="5"))
    check(r["jurisdiction"] == "UNSUPPORTED", "#52 无年份且卷号两边都落，不猜")
    r = c.run_row(_row("shape_leading_abbr", "Q.R. 3 Ex. 1", leading_abbr="Q.R.", abbr="Ex.",
                       vol="3", page="1"))
    check(r["jurisdiction"] == "UNSUPPORTED", "#52 前缀与表冲突不下判定（Q.R. 前缀配英国 Ex.）")
    r = c.run_row(_row("shape_bracket", "[1981] C.P. 292", token="C.P.", year_start="1981", page="292"))
    check(r["jurisdiction"] == "QC",
          "#52 [1981] C.P. 是魁北克省级法院——入表前经归一键误落 C. & P.（英国）")
    r = c.run_row(_row("shape_vol_abbr_page", "5 C. & P. 190", abbr="C. & P.", vol="5",
                       year_start="1831", page="190"))
    check(r["jurisdiction"] == "GB", "#52 C. & P. 精确命中本行，不被 C.P. 的两行干扰")

    import merge
    keys = {merge.build_merge_key(c.run_row(_row("shape_leading_abbr", raw, leading_abbr=p, abbr="Q.B.",
                                                  vol="6", page="1")))
            for raw, p in (("L.R. 6 Q.B. 1", "L.R."), ("Q.R. 6 Q.B. 1", "Q.R."))}
    keys.add(merge.build_merge_key(c.run_row(_row("shape_vol_abbr_page", "6 Q.B. 1", abbr="Q.B.",
                                                  vol="6", page="1"))))
    check(keys == {"|6|lr.qb||1", "|6|qr.qb||1", "|6|qb||1"},
          "#53 归并键带系列前缀：L.R./Q.R./无前缀的 6 Q.B. 1 是三个键，英国与魁北克不同组")
    check(merge.build_merge_key({"year_start": "1978", "vol": "1", "abbreviation": "A.C.", "page": "728"})
          == "1978|1|ac||728", "#53 无前缀的行归并键逐字节不变")

    r = c.run_row(_row("shape_neutral_bare", "2019 SCC 5", token="SCC", year_start="2019", page="5",
                       source_decision_citation="SCC_2019scc5"))
    check((r["self_citation"], r["rejected_reason"]) == ("true", ""),
          "#54 判决头部印的自身引证打 self_citation，且不进 rejected_reason（它是真引证）")
    r = c.run_row(_row("shape_neutral_bare", "2019 SCC 6", token="SCC", year_start="2019", page="6",
                       source_decision_citation="SCC_2019scc5"))
    check(r["self_citation"] == "", "#54 引别的判决不打")

    r = c.run_row(_row("shape_bracket", "[1985] 2 S.C.R. 486", token="S.C.R.", vol="2", year_start="1985",
                       page="486", preceding_text="Hunter v. Southam Inc., [1984] 2 S.C.R. 145; R. v. Big M "
                       "Drug Mart Ltd., [1985] 1 S.C.R. 295; Re B.C. Motor Vehicle Act, "))
    check(r["candidate_case_name"] == "Re B.C. Motor Vehicle Act" and "Big M" not in r["candidate_case_name"],
          "#57/#58 Re B.C. Motor Vehicle Act 的引证不借 Big M 的名字；#58 起改取它自己那一段的名字")
    r = c.run_row(_row("shape_bracket", "[2002] 2 S.C.R. 235", token="S.C.R.", vol="2", year_start="2002",
                       page="235", preceding_text="; Housen v. Nikolaisen, 2002 SCC 33; "))
    check(r["candidate_case_name"] == "Housen v. Nikolaisen",
          "#57 分号后紧接引证是平行引证，案名照切（#45 剥尾照旧）")
    r = c.run_row(_row("shape_bracket", "[1991] 3 S.C.R. 387", token="S.C.R.", vol="3", year_start="1991",
                       page="387", preceding_text="; R. v. Grover (1990), 56 C.C.C. (3d) 532 (Ont. C.A.); aff\'d "))
    check(r["candidate_case_name"] == "R. v. Grover", "#57 分号后是本案上诉沿革（aff'd）：仍属分号前的案名")
    check(not classify._HISTORY_RE.match("Revenue Canada") and not classify._HISTORY_RE.match("Varity Corp")
          and not classify._HISTORY_RE.match("Re B.C. Motor Vehicle Act"),
          "#57 沿革词表只认完整的沿革词，不吞 Revenue、Varity、Re 起头的案名")


def test_case_name_markers():
    """PROBLEMS #58：没有 v. 的案名。标记只在**引证所在那一段**的段首/段尾认，
    且只在段内没有 v. 时启用；标记后面接着散文要切断或拒收。"""
    c = _classifier()

    def name(pre, raw="[1985] 2 S.C.R. 486", tok="S.C.R.", vol="2", year="1985", page="486"):
        return c.run_row(_row("shape_bracket", raw, token=tok, vol=vol, year_start=year,
                              page=page, preceding_text=pre))["candidate_case_name"]

    # 三种前缀标记 + 后缀 (Re) + 魁北克匿名名
    check(name("Referred to: Reference re Secession of Quebec, ") == "Reference re Secession of Quebec",
          "#58 Reference re X：取标记起的那一段（1896 那类跨句吞并同时被挡住）")
    check(name("Considered: Re B.C. Motor Vehicle Act, ") == "Re B.C. Motor Vehicle Act", "#58 Re X")
    check(name("In re Estate of Brown (deceased), ") == "In re Estate of Brown", "#58 In re X")
    check(name("Ex parte Adamson, ") == "Ex parte Adamson", "#58 Ex parte X")
    check(name("Rizzo & Rizzo Shoes Ltd. (Re), ") == "Rizzo & Rizzo Shoes Ltd. (Re)", "#58 X (Re) 后缀形")
    check(name("Droit de la famille — 103038, 2010 QCCA 2074, ") == "Droit de la famille — 103038",
          "#58 魁北克匿名名（法语 famille 是小写，不走「像案名」的走词判据）")
    check(name("LSJPA — 1037, 2010 QCCA 1627, ") == "LSJPA — 1037", "#58 LSJPA 匿名名（破折号含 en dash）")
    check(name("Re Residential Tenancies Act, 1979, ") == "Re Residential Tenancies Act, 1979",
          "#58 段内是「, 1979」而非引证形态：不当尾巴剥掉")

    # 散文必须挡住
    check(name("Re the question whether the trial judge erred, ") == "",
          "#58 标记后不是大写词：散文不成名（Re the question…）")
    check(name("Re Schabas and Caput of the University of Toronto[22], which is referred to by Macdonald, J.A., in ")
          == "Re Schabas and Caput of the University of Toronto[22]",
          "#58 标记后接着散文（, which is referred to by…）：在句子边界切断")
    check(name("relying on several cases including Nortel Networks Corp. (Re), ")
          == "Nortel Networks Corp. (Re)",
          "#58 X (Re) 从右往左收：段首是散文时只取案名那一段（未加此闸时 2,750 行里大半是整句）")

    # 段内有 v. 时不走标记路（否则「…citing Rizzo & Rizzo Shoes Ltd. (Re)」这类段会被
    # 整段吞下）。**输入必须真的含 v.**：上一版用的是 `see Vavilov, 2019 SCC 65, at
    # para. 117, citing Rizzo & Rizzo Shoes Ltd. (Re)`——「Vavilov」不匹配 V_RE，段里
    # 其实没有 v.，走的仍是标记路，而断言只写了「不等于整段」，恒真、等于没测。
    # 这一版显式钉住「段内确有 v.、且标记确实认得这段」，再钉住生产线给出的是 v. 路
    # 的结果而不是标记路的结果（两条路在这里给出的名字不同，故断言有区分力）。
    pre_gate = ("; see Housen v. Nikolaisen, citing Rizzo & Rizzo Shoes Ltd. (Re), ")
    seg_gate = classify._cite_segment(pre_gate)
    check(bool(classify.V_RE.search(seg_gate)) and classify._marker_of(seg_gate) == "tail_re",
          "#58 闸的测试输入确实「段内有 v. 且段尾是 (Re) 形」——段内没 v. 就没有区分力")
    r = c.run_row(_row("shape_bracket", "[1998] 1 S.C.R. 27", token="S.C.R.", vol="1", year_start="1998",
                       page="27", preceding_text=pre_gate))
    check(r["candidate_case_name"] == "Housen v. Nikolaisen, citing Rizzo & Rizzo Shoes Ltd. (Re)",
          "#58 段内有 v.：标记路不启用，交回 v. 路（若启用会切出 Rizzo & Rizzo Shoes Ltd. (Re)）")
    # 分号是段边界：前一段的 v. 不影响本段
    r = c.run_row(_row("shape_bracket", "[1998] 2 S.C.R. 217", token="S.C.R.", vol="2", year_start="1998",
                       page="217", preceding_text="1198; Air Canada v. British Columbia, [1989] 1 S.C.R. 1161."
                       "\nBy Binnie J.\nReferred to: Reference re Secession of Quebec, "))
    check(r["candidate_case_name"] == "Reference re Secession of Quebec",
          "#58 Secession 验收例：不再借用 Air Canada v. British Columbia")
    # 无标记仍是无 v. 结构
    check(name("the manipulation of an end and not a means, ") == "",
          "#58 段首无标记：照旧 no_v_structure，不给默认值")


# ============================================================ 裁定层（单元）
def _k(year, code, num):
    return "%s||%s||%s" % (year, code, num)


def test_own_citations_loader():
    import tempfile as _t
    d = _t.mkdtemp(prefix="own_cites_")
    p = os.path.join(d, "decision_own_citations.csv")
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write("merge_key,decision_id,source_court,field\n"
                "2003|1|scr||39,SCC_2003scc5,SCC,citation2_en\n"
                "2003||scc||5,SCC_2003scc5,SCC,citation_en\n")
    idx = decide.load_own_citations(p)
    check(idx["2003|1|scr||39"] == {"SCC_2003scc5"} and len(idx) == 2,
          "#105 判决自己印的引证表：并行引证与自身引证都按键归到判决 id")
    check(not decide.load_own_citations(None) and not decide.load_own_citations(p + ".nope"),
          "#105 不传/文件不存在 -> 空表（行为与改动前一致）")


def test_own_citation_rule():
    """#105：裁定层「只在提及自己的来源判决不计 DD」——直接测规则函数 own_citation_self_ids。
    成员 = 本组的键；did_idx = 键 -> 提及它的来源判决；own_cites = 键 -> 把它印在自己头部的判决。"""
    def mem(court, key):
        return {"court": court, "merge_key": key}

    members = [mem("SCC", "2003||scc||5"), mem("SCC", "2003|1|scr||39"), mem("ONCA", "2002|58|or|3d|1")]
    did = {"SCC|2003||scc||5": {"A", "X"},
           "SCC|2003|1|scr||39": {"SELF", "X"},         # SELF 只经由自己头部印的并行引证提及本组
           "ONCA|2002|58|or|3d|1": {"BOTH", "X"}}        # BOTH 既经由自己的键、又经由下级判决的键
    own = {"2003|1|scr||39": {"SELF", "BOTH"}}
    did["SCC|2003|1|scr||39"].add("BOTH")
    ids = {"A", "X", "SELF", "BOTH"}

    def run(own_cites, root_kind=None):
        return decide.own_citation_self_ids(members, did, ids, own_cites, root_kind or {}, Counter())

    check(run(own) == {"SELF"},
          "#105 只经由自己印的键提及本组 -> 剔（SELF）；还经由别的键提及 -> 保留，即审理历史（BOTH，用户裁定计入 DD）")
    check("X" not in run(own) and "A" not in run(own),
          "#105 与自己印的键无关的来源判决一概不动")
    check(run({}) == set() and run(None) == set(),
          "#105 没有自引表 -> 空集（行为与改动前一致）")
    check(run(own, {"2003|1|scr||39": "typo_number"}) == set(),
          "#105 笔误并入的键不算判决自己的键（#54 原意：并进来的键可能是另一件判决）")
    check(run({"2003|1|scr||39": {"SOMEONE_ELSE"}}) == set(),
          "#105 这个键是别的判决自己印的 -> 不剔")
    st = Counter()
    decide.own_citation_self_ids(members, did, ids, own, {}, st)
    check((st["self_ids_removed_own_citation"], st["own_key_plus_other_key_kept"]) == (1, 1),
          "#105 统计口径：剔 1、因另有别的键而保留 1")


def test_decide_units():
    check(decide._one_edit("33", "3") and decide._one_edit("18", "19")
          and not decide._one_edit("79", "45"), "_one_edit：错一位才算")
    check(decide.same_decision(_k(2002, "scc", 3), "CA", 1, _k(2002, "scc", 33), "CA", 445),
          "#49 号码掉一位且罕见 -> 笔误并入（Housen）")
    check(not decide.same_decision(_k(2005, "scc", 79), "CA", 3, _k(2005, "scc", 75), "CA", 4),
          "#49 规模闸：引用量相近不当笔误（MacKay）")
    # ---- PROBLEMS #88：混合键三档判据（一个印刷串承担两种身份）
    check(decide.parse_name_classes("a:4|b:2") == {"a": 4, "b": 2}
          and decide.parse_name_classes("") == {}
          and decide.parse_name_classes("坏数据|c:x|d:3") == {"d": 3},
          "#88 name_classes 解析：坏分段跳过、不造假数据")
    check(decide.mixed_identity({"housenvnikolaisen": 1}, "housenvnikolaisen") == "fold",
          "#88 第一档：提及只印折叠目标的名字 → 纯笔误，照并（2002 SCC 35 实测如此）")
    check(decide.mixed_identity({}, "housenvnikolaisen") == "fold"
          and decide.mixed_identity({"rvsmith": 3}, "housenvnikolaisen") == "fold",
          "#88 第二档：无名、或没有一个与目标同名 → 本期不动（机制 A 与 #89 的地盘）")
    check(decide.mixed_identity({"housenvnikolaisen": 4, "chieuvcanada": 2},
                                "housenvnikolaisen") == "holdout",
          "#88 第三档：既印 Housen 又印 Chieu → 扣留（2002 SCC 3 实测 4:2）")
    check(decide.mixed_identity({"housenvnikolaisen": 4, "chieuvcanada": 1},
                                "housenvnikolaisen") == "holdout",
          "#88 不设计数阈值：一条反证也算反证（宁可漏，不可错）")
    check(decide.mixed_identity({"a": 1}, "") == "fold",
          "#88 折叠目标无案名时不触发（没有可比对的证据）")
    check(decide.same_decision(_k(2014, "scc", 7), "CA", 3, _k(2014, "csc", 7), "CA", 5),
          "#49 双语代码同一判决，不看规模（SCC/CSC）")
    check(decide.same_decision(_k(2005, "scc", 20), "CA", 1, _k(2006, "scc", 20), "CA", 18),
          "#49 年份错一年（Placer Dome）")
    check(not decide.same_decision(_k(2002, "scc", 79), "CA", 24, _k(2003, "scc", 45), "CA", 34),
          "#49 号码全不同是不同判决（Wewaykum 本案与回避申请）")
    check(not decide.same_decision(_k(2017, "scc", 17), "CA", 1, _k(2018, "nbqb", 17), "NB", 151),
          "#49 不同法院必是不同判决")
    ms = [{"merge_key": "1957||scr||119", "citation_kind": "reporter", "court": "ONCA",
           "jurisdiction": "CA", "self_citation_of": "SCC_1957scr119"},
          {"merge_key": "1957||scr||531", "citation_kind": "reporter", "court": "ONCA",
           "jurisdiction": "CA", "self_citation_of": "SCC_1957scr531"},
          {"merge_key": "1957|1|scr||119", "citation_kind": "reporter", "court": "ONCA",
           "jurisdiction": "CA", "self_citation_of": "SCC_19571scr119"}]
    root = decide.decisions_of(ms, {})[0]
    check(len(set(root.values())) == 3,
          "#55 判决自身的汇编引证是锚，且汇编锚只与同键合并（卷号不同也不并）")

    def neu(k, own, own_name, name):
        return {"merge_key": k, "citation_kind": "neutral", "court": "ONCA", "jurisdiction": "CA",
                "self_citation_of": own, "self_case_name": own_name, "case_name_modal": name}
    did = {"ONCA|2007||onca||196": {"a", "b", "c", "d"}, "ONCA|2007||onca||496": {"e"},
           "ONCA|2002||scc||33": {"h1", "h2", "h3", "h4"}, "ONCA|2002||scc||3": {"h5"}}
    root = decide.decisions_of([neu("2007||onca||196", "ONCA_2007onca196", "R. v. Maciel", "R. v. Maciel"),
                                neu("2007||onca||496", "ONCA_2007onca496", "R. v. Maciel", "R. v. Maciel")],
                               did)[0]
    check(len(set(root.values())) == 2,
          "#55 两件同名语料判决（头部都印 R. v. Maciel）号码差一位也不当笔误")
    root = decide.decisions_of([neu("2002||scc||33", "", "", "Housen v. Nikolaisen"),
                                neu("2002||scc||3", "SCC_2002scc3", "R. v. X", "Housen v. Nikolaisen")],
                               did)[0]
    check(len(set(root.values())) == 1,
          "#55 键是另一件判决的自引、但它头部印的名字对不上本组：组里的是笔误，照旧并入 Housen")
    # #88/#89：run 级登记簿只授权笔误闸。真实矩阵（实测主线 run_20260916_85date）：
    #   * `2002||scc||3` 在 **SCC 轮**带着自引与自己的案名（Chieu v. Canada）；
    #   * 但在 **ONCA 轮**（以及跨院轮里 ONCA 那一侧）那一行的 self_case_name 是空的，
    #     而组名是 Housen v. Nikolaisen → same_name 恒为假。
    # 于是规格 2.3 的闸门 `if in_registry and same_name[k]` 对这一档**永远放行**，
    # 无论 in_registry 怎么算：登记簿里补上 k 也救不了它（--registry-gate 两种取值
    # 都验在下面）。
    g = [neu("2002||scc||33", "SCC_2002scc33", "Housen v. Nikolaisen",
             "Housen v. Nikolaisen"),
         neu("2002||scc||3", "", "", "Housen v. Nikolaisen")]
    reg = {"2002||scc||3": ("SCC_2002scc3", "SCC")}
    root = decide.decisions_of(g, did)[0]
    check(len(set(root.values())) == 1,
          "#88 无登记簿：本地看不见的自引键照旧被当号码笔误并掉（跨院失明的形态）")
    for gate in ("literal", "own_or_registry"):
        root = decide.decisions_of(g, did, None, reg, None, gate)[0]
        check(len(set(root.values())) == 1,
              "#88 登记簿命中仍救不了（%s）：same_name 为假，闸门不动作" % gate)
    # 闸门真正生效的那一档：**登记簿那件判决自己印的案名 == 本组组名**，而本组
    # 那一行没有 self_case_name（真实形态：2008 ONCA 36 / R. v. Maciel 那一类）。
    # 注意 self_case_name ≠ case_name_modal 的写法不生效——那正是机制 A。
    g2 = [neu("2002||scc||33", "SCC_2002scc33", "Housen v. Nikolaisen",
              "Housen v. Nikolaisen"),
          neu("2002||scc||3", "", "Housen v. Nikolaisen", "Housen v. Nikolaisen")]
    root = decide.decisions_of(g2, did, None, reg, None, "literal")[0]
    check(len(set(root.values())) == 2,
          "#88 闸门生效档：登记簿那件判决自印案名 == 组名 → 不再被并")
    _r, anc, _j, own, _kk = decide.decisions_of(g2, did, None, reg, None, "literal")
    check(own["2002||scc||3"] == set() and anc["2002||scc||3"] == {"h5"},
          "#88 登记簿不掺 own：锚资格与 dd 仍按本层自己的证据算")
    # 机制 A：登记簿命中但头部案名与本组组名不一致 → 仍可当笔误（两种 gate 同结论）
    g3 = [neu("2002||scc||33", "", "", "R. v. Conway"),
          neu("2002||scc||3", "SCC_2002scc3", "Mickle v. Mickle", "R. v. Conway")]
    for gate in ("literal", "own_or_registry"):
        root = decide.decisions_of(g3, did, None, reg, None, gate)[0]
        check(len(set(root.values())) == 1,
              "#88 机制 A 不动（%s）：登记簿命中但头部名对不上，仍按笔误并入" % gate)

    mohan = [{"merge_key": "1994|2|scr||9", "citation_kind": "reporter", "court": "SCC",
              "jurisdiction": "CA", "self_citation_of": "SCC_19942scr9"},
             {"merge_key": "1994||scc||80", "citation_kind": "neutral", "court": "ONCA",
              "jurisdiction": "CA", "self_citation_of": ""},
             {"merge_key": "2000||scc||1", "citation_kind": "neutral", "court": "SCC",
              "jurisdiction": "CA", "self_citation_of": "SCC_2000scc1"}]
    start = decide.neutral_start(mohan)
    check(start == {"scc": (2000, 1994)},
          "#56 起用界取语料判决自己头部印的引证：最早自印中立 2000、最晚自印非中立 1994")
    check(not decide._before_start("2005||scc||75", {"scc": (2015, 1957)}),
          "#56 缺证不降：语料只见 2015 年的自印中立引用，但 1957 年后再无自印非中立引用")
    check(len(set(decide.decisions_of(mohan[:2], {})[0].values())) == 2
          and len(set(decide.decisions_of(mohan[:2], {}, start)[0].values())) == 1,
          "#56 最高法院 2000 年前的「中立引用」（1994 SCC 80）不当判决身份锚")
    parts = decide.windows([(2001, "a"), (2002, "b"), (2003, "c"), (2004, "d")])
    check([[x for _, x in p] for p in parts] == [["a", "b"], ["c", "d"]], "#48 ±1 年窗口切段")


# ============================================================ 迷你全链
MINI_FIELDS = ["raw_string", "source_decision_citation", "source_decision_year",
               "rejected_reason", "name_rejected_reason", "candidate_case_name",
               "self_case_name", "abbreviation", "citation_kind", "jurisdiction",
               "jurisdiction_confidence",
               "year_start", "year_printed", "vol", "series", "page", "self_citation"]


def _m(court, did, raw, kind, abbr, jur, year, page, vol="", name="", rej="", own=False):
    return {"self_citation": "true" if own else "",
            "raw_string": raw, "source_decision_citation": "%s_%s" % (court, did),
            "source_decision_year": "2020", "rejected_reason": rej, "name_rejected_reason": "",
            "candidate_case_name": name, "abbreviation": abbr, "citation_kind": kind,
            "jurisdiction": jur, "jurisdiction_confidence": "confirmed" if kind == "neutral" else "estimated",
            "year_start": str(year), "vol": vol, "series": "", "page": str(page),
            # 裁定层按**印出来的年份**聚类（R3：连续编卷的键首槽已零化），
            # 故这一列必须给；缺列会让该键落进「无年份」桶、永不参与案名/笔误判定。
            "year_printed": str(year)}


def _neu(court, did, year, code, num, jur, name):
    return _m(court, did, "%s %s %s" % (year, code, num), "neutral", code, jur, year, num, name=name)


def _write(path, rows):
    """写 classified.csv。

    `self_case_name` 在真实管线里**不是输入列**——归并层从**自引行**的
    `candidate_case_name` 现算（merge.py 的 `own_names`：只有 self_citation=true
    的行出自己头部印的案名）。本测试用具类此口径：`_case_name` 记「这件判决自己
    印的案名」，自引行才落到 `self_case_name` 列。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MINI_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            r = dict(r)
            r["self_case_name"] = (r.pop("_case_name", r["candidate_case_name"])
                                   if r.get("self_citation") == "true" else "")
            w.writerow(r)


def _rep(court, did, year, vol, abbr, page, jur, name):
    raw = "[%s] %s%s %s" % (year, (vol + " ") if vol else "", abbr, page)
    return _m(court, did, raw, "reporter", abbr, jur, year, page, vol=vol, name=name)


def _mini_rows():
    scc, onca = [], []
    # Lacasse：中立引用与汇编挨着印，dd 取并集（#46）；两院同串跨院合并（#47）
    for i, nm in enumerate(["R. v. Lacasse"] * 3 + ["R v. Lacasse"], 1):
        onca += [_neu("ONCA", "L%d" % i, 2015, "SCC", 64, "CA", nm),
                 _rep("ONCA", "L%d" % i, 2015, "3", "S.C.R.", 1089, "CA", nm)]
    scc.append(_neu("SCC", "L9", 2015, "SCC", 64, "CA", "R. v. Lacasse"))
    # Lacasse 自己：头部印自身中立引用（分类层认得，打标记）与平行 S.C.R.（认不得）（#54）
    own = _neu("SCC", "2015scc64", 2015, "SCC", 64, "CA", "R. v. Lacasse")
    own["self_citation"] = "true"
    scc += [own, _rep("SCC", "2015scc64", 2015, "3", "S.C.R.", 1089, "CA", "R. v. Lacasse")]
    # Beaver：1957 年两件同名最高法院判决，都在语料里，无中立引用（#55）
    for did, page, citers in (("1957scr119", 119, ("B1",)), ("1957scr531", 531, ("B2", "B3"))):
        b = _rep("SCC", did, 1957, "", "S.C.R.", page, "CA", "Beaver v. The Queen")
        b["self_citation"] = "true"
        scc.append(b)
        for x in citers:
            onca.append(_rep("ONCA", x, 1957, "", "S.C.R.", page, "CA", "Beaver v. The Queen"))
    onca.append(_m("ONCA", "L1", "L.R. 3 H.L. 1", "reporter", "H.L.", "UNSUPPORTED", 1868, 1,
                   vol="3", rej="unrecognized_series_prefix"))
    # R. v. Smith：每年一件、链式串起来，跨度 > 1 必须切开（#48）
    for i, y in enumerate(range(2001, 2005), 1):
        onca.append(_rep("ONCA", "S%d" % i, y, "5", "O.R.", 100 + i, "ON", "R. v. Smith"))
    # Oland：最高法院判决与下级判决同名同窗，按判决拆开；审级历史共引不得并判决（#49）
    for i in (1, 2, 3):
        scc += [_neu("SCC", "O%d" % i, 2017, "SCC", 17, "CA", "R. v. Oland"),
                _rep("SCC", "O%d" % i, 2017, "1", "S.C.R.", 250, "CA", "R. v. Oland")]
    scc += [_neu("SCC", "O1", 2018, "NBQB", 255, "NB", "R. v. Oland"),
            _neu("SCC", "O4", 2018, "NBQB", 255, "NB", "R. v. Oland")]
    # Housen 笔误并入；MacKay 引用量相近不并（#49）
    for i in range(1, 7):
        scc.append(_neu("SCC", "H%d" % i, 2002, "SCC", 33, "CA", "Housen v. Nikolaisen"))
    scc.append(_neu("SCC", "H7", 2002, "SCC", 3, "CA", "Housen v. Nikolaisen"))
    for i in range(1, 5):
        scc.append(_neu("SCC", "M%d" % i, 2005, "SCC", 75, "CA", "R. v. MacKay"))
    for i in range(5, 8):
        scc.append(_neu("SCC", "M%d" % i, 2005, "SCC", 79, "CA", "R. v. MacKay"))
    # Hryniak 双语代码（#49）
    for i in range(1, 4):
        scc.append(_neu("SCC", "Y%d" % i, 2014, "SCC", 7, "CA", "Hryniak v. Mauldin"))
    for i in range(4, 9):
        scc.append(_neu("SCC", "Y%d" % i, 2014, "CSC", 7, "CA", "Hryniak v. Mauldin"))
    # Gladue：两院同一印刷串必须同进同出，否则被撕成两半（#49 单元）
    for i in (1, 2, 3):
        scc.append(_rep("SCC", "G%d" % i, 1999, "1", "S.C.R.", 688, "CA", "R. v. Gladue"))
    for i in (4, 5):
        onca.append(_rep("ONCA", "G%d" % i, 1999, "1", "S.C.R.", 688, "CA", "R. v. Gladue"))
    scc += [_neu("SCC", "G9", 2000, "SCC", 31, "CA", "R. v. Gladue"),
            _neu("SCC", "G8", 1999, "ABCA", 279, "AB", "R. v. Gladue")]
    # Imoro：先按法域筛再比共引——共引最高的下级判决法域不相容（#49）
    for i in range(1, 6):
        onca += [_neu("ONCA", "I%d" % i, 2010, "ONCA", 122, "ON", "R. v. Imoro"),
                 _rep("ONCA", "I%d" % i, 2010, "3", "S.C.R.", 62, "CA", "R. v. Imoro")]
    for i in range(1, 5):
        onca.append(_neu("ONCA", "I%d" % i, 2010, "SCC", 50, "CA", "R. v. Imoro"))
    # Wewaykum：共引持平，以印刷年份定归（#49）
    for i in range(1, 5):
        scc += [_neu("SCC", "W%d" % i, 2002, "SCC", 79, "CA", "Wewaykum Indian Band v. Canada"),
                _neu("SCC", "W%d" % i, 2003, "SCC", 45, "CA", "Wewaykum Indian Band v. Canada"),
                _rep("SCC", "W%d" % i, 2003, "2", "S.C.R.", 259, "CA", "Wewaykum Indian Band v. Canada")]
    # 孤例：dd 1，过不了门槛
    scc.append(_neu("SCC", "Z1", 2011, "SCC", 99, "CA", "Lonely v. Case"))
    return scc, onca


def _run(script, *args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, os.path.join(PIPE, script)] + list(args),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    if p.returncode != 0:
        raise AssertionError("%s 退出码 %d：\n%s" % (script, p.returncode, p.stderr[-3000:]))


def _read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_mini_chain():
    scc, onca = _mini_rows()
    tmp = tempfile.mkdtemp(prefix="test_layers_")
    for court, rows in (("SCC", scc), ("ONCA", onca)):
        _write(os.path.join(tmp, "classify", court, "classified.csv"), rows)
        _run("merge.py", "--court", court,
             "--input", os.path.join(tmp, "classify", court, "classified.csv"),
             "--output", os.path.join(tmp, "merge", court))
        _run("decide.py", "--court", court,
             "--input", os.path.join(tmp, "merge", court, "merged.csv"),
             "--folded-log", os.path.join(tmp, "merge", court, "folded_log.csv"),
             "--decision-ids", os.path.join(tmp, "merge", court, "decision_ids.csv"),
             "--output", os.path.join(tmp, "decide", court))
    _run("decide.py", "--cross-court",
         "--inputs", os.path.join(tmp, "decide", "SCC", "decided.csv"),
         os.path.join(tmp, "decide", "ONCA", "decided.csv"),
         "--output", os.path.join(tmp, "decide", "cross"))
    cfg = os.path.join(tmp, "select.yaml")
    with open(cfg, "w", encoding="utf-8") as f:
        f.write("t:\n  threshold_dd: 2\n")
    _run("select.py", "--input", os.path.join(tmp, "decide", "cross", "decided.csv"),
         "--config", cfg, "--profile", "t", "--output", os.path.join(tmp, "select"))

    # ---- 归并层
    merged = {r["merge_key"]: r for r in _read(os.path.join(tmp, "merge", "ONCA", "merged.csv"))}
    lac = merged["2015||scc||64"]
    check((lac["occurrence_count"], lac["distinct_decisions_count"]) == ("4", "4"),
          "归并层计数：四份判决各引一次")
    check((lac["case_name_modal"], lac["variants_count"], lac["case_name_agreement"])
          == ("R. v. Lacasse", "1", "1.0"),
          "#44 案名两级投票：R v. Lacasse 与 R. v. Lacasse 折成一票")
    folded = _read(os.path.join(tmp, "merge", "ONCA", "folded_log.csv"))
    hl = [r for r in folded if r["raw_string"] == "L.R. 3 H.L. 1"]
    check(len(hl) == 1 and hl[0]["count"] == "0",
          "约束五：行级拒绝的行留在折叠日志里、计数为 0")

    # ---- 跨院裁定
    rows = _read(os.path.join(tmp, "decide", "cross", "decided.csv"))
    gid = defaultdict(set)
    groups = defaultdict(list)
    for r in rows:
        gid[r["merge_key"]].add(r["merged_group_id"])
        groups[r["merged_group_id"]].append(r)

    def one(mk):
        s = gid[mk]
        check(len(s) == 1, "同一印刷串只落一个组：%s" % mk)
        return next(iter(s))

    g = groups[one("2015||scc||64")]
    check(any(r["merge_key"] == "2015|3|scr||1089" for r in g), "平行汇编与中立引用同组")
    check((g[0]["distinct_decisions_count"], g[0]["occurrence_count"]) == ("5", "10"),
          "#46 dd 取并集（5，不是相加）；#54 Lacasse 自己头部的两处不进 dd——中立引用在归并层"
          "按标记排除，平行 S.C.R. 在裁定层按身份根剔除（occurrence 仍含后者一次，10）")
    smerged = {r["merge_key"]: r for r in _read(os.path.join(tmp, "merge", "SCC", "merged.csv"))}
    check((smerged["2015||scc||64"]["occurrence_count"], smerged["2015||scc||64"]["self_citation_of"])
          == ("1", "SCC_2015scc64"),
          "#54 归并层：自引不计数，键上记着它是哪件判决自己的引证")
    counted = sum(1 for r in scc + onca if not r["rejected_reason"] and r["self_citation"] != "true")
    check(sum(int(ms[0]["occurrence_count"]) for ms in groups.values()) == counted,
          "#47 守恒：各组 occurrence 之和 == 计数行总数")
    smith = [ms for ms in groups.values() if ms[0]["case_name_modal"] == "R. v. Smith"]
    check(len(smith) == 2 and all("span" in ms[0]["split_reason"] for ms in smith),
          "#48 每年一件的常见案名按 ±1 年窗口切开")
    check(one("2017||scc||17") == one("2017|1|scr||250") != one("2018||nbqb||255"),
          "#49 Oland：汇编随最高法院判决走，下级判决分开（审级历史共引不并判决）")
    check(one("2002||scc||33") == one("2002||scc||3"), "#49 Housen 笔误变体并入")
    check(one("2005||scc||75") != one("2005||scc||79"), "#49 MacKay 引用量相近保留分开")
    check(one("2014||scc||7") == one("2014||csc||7"), "#49 Hryniak 双语代码同组")
    gl = groups[one("1999|1|scr||688")]
    check(sorted(r["court"] for r in gl if r["merge_key"] == "1999|1|scr||688") == ["ONCA", "SCC"]
          and "unanchored" in gl[0]["split_reason"] and gl[0]["distinct_decisions_count"] == "5",
          "#49 Gladue：两院同一印刷串同进同出，作为无中立锚的判决自成一组（dd 5）")
    check(one("2010|3|scr||62") == one("2010||scc||50") != one("2010||onca||122"),
          "#49 Imoro：先按法域筛再比共引，S.C.R. 归最高法院判决")
    check(one("2003|2|scr||259") == one("2003||scc||45") != one("2002||scc||79"),
          "#49 Wewaykum：共引持平以印刷年份定归")
    b1, b2 = groups[one("1957||scr||119")], groups[one("1957||scr||531")]
    check(b1 is not b2 and (b1[0]["distinct_decisions_count"], b2[0]["distinct_decisions_count"])
          == ("1", "2"), "#55 Beaver：两件同名同年的语料判决分开，各自不数自己")
    did = decide.load_decision_ids(os.path.join(tmp, "decide", "cross", "decision_ids.csv"))
    check(all(len(set(decide.decisions_of(ms, did)[0].values())) <= 1 for ms in groups.values()),
          "#49 硬不变量：任何一组不含两个不同判决（按裁定层同一判据复算）")

    # ---- 选取层
    sel = {r["merge_key"]: r["kept"] for r in _read(os.path.join(tmp, "select", "selected.csv"))}
    check(sel["2011||scc||99"] == "false" and sel["1999|1|scr||688"] == "true",
          "选取层：dd 过门槛才 kept，不删行")


# ============================================================ #88/#89 全局登记簿
def _mini_rows_registry():
    """#88 的院内形态（实测主线 ONCA 轮的字面复刻）：

      * `2002||onca||3` —— 被印错的那件（Housen 位）：6 行**引它**的提及
        （occ=6、dd=6，自引行不计）；
      * `2002||onca||4` —— 机制 B 的键：只有自己头部那一处自引，本地
        `own[k]` 非空但它自己就是被当笔误并掉的那一件；
      * `2002||onca||5` —— 机制 A 的键：自引行的 `_case_name`（R. v. Cyr）与
        本组组名不一致，真实先例 2008 ONCA 36 落在 R. v. Conway 组。
        （它另有 2 行**引它**的提及：没有正证据的键不算锚——设这个键是为了让
        「机制 A 仍可当笔误」这条断言真的走到闸门里，而不是被假阴性放过。）"""
    onca = [_neu("ONCA", "O%d" % i, 2002, "ONCA", 3, "ON", "Housen v. Nikolaisen")
            for i in range(1, 7)]
    onca.append(_neu("ONCA", "O7", 2002, "ONCA", 4, "ON", "Housen v. Nikolaisen"))
    o8 = _neu("ONCA", "O8", 2002, "ONCA", 5, "ON", "Housen v. Nikolaisen")
    o8["self_citation"] = "true"
    o8["_case_name"] = "R. v. Cyr"
    onca.append(o8)
    for i in (9, 10):
        onca.append(_neu("ONCA", "O%d" % i, 2005, "ONCA", 5, "ON",
                         "Housen v. Nikolaisen"))
    scc = [_neu("SCC", "2002scc33", 2002, "SCC", 33, "CA", "Housen v. Nikolaisen"),
           _neu("SCC", "2002scc3", 2002, "SCC", 3, "CA",
                "Chieu v. Canada (Minister of Citizenship and Immigration)"),
           _neu("SCC", "2002scc35", 2002, "SCC", 35, "CA", "R. v. Carlos")]
    for r in scc:
        r["self_citation"] = "true"
    return scc, onca


def test_registry_gate():
    """#88/#89 的**闸门语义**（单元级，用真实矩阵搭）：

      * 机制 B 的键（本地那一轮看不见它的自引、且 `same_name` 为假）**救不了**——
        规格 2.3 的 `if in_registry and same_name[k]` 对它永远放行，`--registry-gate`
        两种取值都验过（见 check 标签）；
      * 闸门真正生效的是「登记簿那件判决自印案名 == 本组组名」那一档；
      * 机制 A（登记簿命中但头部名对不上）**不动**，仍可当笔误；
      * 登记簿不掺 `own`（另有三处用途只看 own，规格 2.3）。"""
    g = [{"merge_key": "2002||scc||33", "citation_kind": "neutral", "court": "ONCA",
          "jurisdiction": "CA", "self_citation_of": "SCC_2002scc33",
          "self_case_name": "Housen v. Nikolaisen",
          "case_name_modal": "Housen v. Nikolaisen"},
         {"merge_key": "2002||scc||3", "citation_kind": "neutral", "court": "ONCA",
          "jurisdiction": "CA", "self_citation_of": "", "self_case_name": "",
          "case_name_modal": "Housen v. Nikolaisen"}]
    did = {"ONCA|2002||scc||33": {"h1", "h2", "h3", "h4"},
           "ONCA|2002||scc||3": {"h5"}}
    reg = {"2002||scc||3": ("SCC_2002scc3", "SCC")}
    check(decide.load_registry(os.path.join(tempfile.gettempdir(), "不存在.csv")) == {},
          "#88 登记簿缺文件 = 空表（不传 --registry 时行为不变）")
    root = decide.decisions_of(g, did)[0]
    check(len(set(root.values())) == 1,
          "#88 无登记簿：本地看不见的自引键照旧被当号码笔误并掉（跨院失明的形态）")
    for gate in ("literal", "own_or_registry"):
        root = decide.decisions_of(g, did, None, reg, None, gate)[0]
        check(len(set(root.values())) == 1,
              "#89 登记簿命中仍救不了（%s）：same_name 为假，闸门不动作" % gate)
    # 闸门生效档：登记簿那件判决自印案名 == 本组组名（本组那一行 self_case_name 为空）
    g2 = [dict(g[0]), dict(g[1], self_case_name="Housen v. Nikolaisen")]
    root = decide.decisions_of(g2, did, None, reg, None, "literal")[0]
    check(len(set(root.values())) == 2,
          "#88 闸门生效档：登记簿那件判决自印案名 == 组名 → 不再被并")
    # registered_only：登记簿命中、本轮看不见它是真判决 → 挡住（唯一能修 #88 的取值）
    root = decide.decisions_of(g, did, None, reg, None, "registered_only")[0]
    check(len(set(root.values())) == 2,
          "#88 registered_only：本地看不见的登记簿命中被挡住（Chieu 不再并进 Housen）")
    _r, anc, _j, own, _kk = decide.decisions_of(g, did, None, reg, None,
                                                "registered_only")
    check(own["2002||scc||3"] == set() and anc["2002||scc||3"] == {"h5"},
          "#88 登记簿不掺 own：锚资格与 dd 仍按本层自己的证据算")
    # registered_only 不动机制 A：own 非空时走原来的同名闸
    g3 = [{"merge_key": "2002||scc||33", "citation_kind": "neutral", "court": "ONCA",
           "jurisdiction": "CA", "self_citation_of": "", "self_case_name": "",
           "case_name_modal": "R. v. Conway"},
          {"merge_key": "2002||scc||3", "citation_kind": "neutral", "court": "ONCA",
           "jurisdiction": "CA", "self_citation_of": "SCC_2002scc3",
           "self_case_name": "Mickle v. Mickle", "case_name_modal": "R. v. Conway"}]
    for gate in ("literal", "own_or_registry", "registered_only"):
        root = decide.decisions_of(g3, did, None, reg, None, gate)[0]
        check(len(set(root.values())) == 1,
              "#88 机制 A 不动（%s）：登记簿命中但头部名对不上，仍按笔误并入" % gate)


def test_registry_audit():
    """#88：机制 A 的留痕清单（原先隐形）——`decisions_of` 在把「登记簿命中、
    但头部案名与组名不一致」的键当笔误并掉时，必须留下可审的一行。

    这里直接喂一组**手搭的成员行**（真实形态：键 `2008 ONCA 36` 真判决
    Mickle v. Mickle 落在 R. v. Conway 组），绕开抽取/归并两层——
    与 `test_decide_units` 的既有做法一致。"""
    rows = [{"merge_key": "2008||onca||326", "citation_kind": "neutral",
             "court": "ONCA", "jurisdiction": "ON",
             "self_citation_of": "", "self_case_name": "",
             "case_name_modal": "R. v. Conway"},
            {"merge_key": "2008||onca||36", "citation_kind": "neutral",
             "court": "ONCA", "jurisdiction": "ON",
             "self_citation_of": "ONCA_2008onca36",
             "self_case_name": "Mickle v. Mickle",
             "case_name_modal": "R. v. Conway"}]
    did = {"ONCA|2008||onca||326": {"a", "b", "c", "d"},
           "ONCA|2008||onca||36": {"e"}}
    registry = {"2008||onca||36": ("ONCA_2008onca36", "ONCA")}

    audit = []
    root, _anc, _j, own, kind = decide.decisions_of(rows, did, None, registry, audit)
    check(root["2008||onca||36"] == "2008||onca||326"
          and kind["2008||onca||36"] == "typo_number",
          "#88 机制 A：登记簿命中但头部案名与组名不一致 → 仍按笔误并入（不动）")
    check(own["2008||onca||36"] == {"ONCA_2008onca36"},
          "#88 留痕用例的 own 非空（机制 A 的定义性特征）")
    check(len(audit) == 1 and audit[0][0] == "2008||onca||36"
          and audit[0][1] == "2008||onca||326",
          "#88 机制 A 从隐形变可审：每一次「登记簿命中却仍当笔误」进 audit_rows")
    # 不传登记簿：同一对被并掉但不留痕（改动前行为）
    audit2 = []
    decide.decisions_of(rows, did, None, None, audit2)
    check(audit2 == [],
          "#88 无登记簿时 audit_rows 为空（无登记簿 = 行为不变）")



# ============================================================ 金标（全量差分）
def _stats(path):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)["stats"]


def snapshot():
    D = os.path.join(ROOT, "data")
    snap = {}
    for c in ("SCC", "ONCA"):
        snap["classify_" + c] = _stats(os.path.join(D, "classify_out", c, "manifest.json"))
        snap["merge_" + c] = _stats(os.path.join(D, "merge_out", c, "manifest.json"))
        snap["decide_" + c] = _stats(os.path.join(D, "decide_out", c, "manifest.json"))
    snap["decide_cross"] = _stats(os.path.join(D, "decide_out", "cross_court", "manifest.json"))
    with io.open(os.path.join(D, "select_out", "manifest.json"), encoding="utf-8") as f:
        sel = json.load(f)
    snap["select"] = {"threshold_dd": sel["threshold_dd"], "stats": sel["stats"],
                      "dd_profile": sel["dd_profile"]}
    groups = defaultdict(list)
    with open(os.path.join(D, "decide_out", "cross_court", "decided.csv"),
              encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            groups[r["merged_group_id"]].append(r)
    top = sorted(groups.values(),
                 key=lambda ms: (-int(ms[0]["distinct_decisions_count"]), ms[0]["merged_group_id"]))
    snap["top25"] = []
    for ms in top[:25]:
        p = next((m for m in ms if m["is_primary"] == "true"), ms[0])
        snap["top25"].append([int(p["distinct_decisions_count"]), int(p["occurrence_count"]),
                              p["case_name_modal"],
                              sorted({m["merge_key"] for m in ms if m["citation_kind"] == "neutral"})])
    return snap


def golden(write):
    snap = snapshot()
    if write:
        with io.open(GOLDEN, "w", encoding="utf-8", newline="\n") as f:
            json.dump(snap, f, ensure_ascii=False, indent=1, sort_keys=True)
        print("金标已重写 -> %s" % GOLDEN)
        return 0
    with io.open(GOLDEN, encoding="utf-8") as f:
        gold = json.load(f)
    diffs = []
    for section in sorted(set(gold) | set(snap)):
        a, b = gold.get(section), snap.get(section)
        if a == b:
            continue
        if isinstance(a, dict) and isinstance(b, dict):
            for k in sorted(set(a) | set(b)):
                if a.get(k) != b.get(k):
                    diffs.append("%s.%s: 金标 %r -> 现在 %r" % (section, k, a.get(k), b.get(k)))
        else:
            diffs.append("%s: 与金标不同" % section)
    if diffs:
        print("与金标的差分 %d 处：" % len(diffs))
        for d in diffs:
            print("  " + d)
        print("逐项复核：预期内的差分才 --golden-write，否则是回归。")
        return 1
    print("全量产出与金标一致。")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--golden", action="store_true")
    g.add_argument("--golden-write", action="store_true")
    a = ap.parse_args()
    if a.golden or a.golden_write:
        sys.exit(golden(a.golden_write))
    for t in (test_admit_candidate, test_classifier, test_disambiguation,
              test_case_name_markers, test_own_citations_loader, test_own_citation_rule, test_decide_units, test_registry_gate,
              test_registry_audit, test_mini_chain):
        t()
    print("全部通过：%d 条断言" % len(PASSED))


if __name__ == "__main__":
    main()
