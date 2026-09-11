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


# ============================================================ 裁定层（单元）
def _k(year, code, num):
    return "%s||%s||%s" % (year, code, num)


def test_decide_units():
    check(decide._one_edit("33", "3") and decide._one_edit("18", "19")
          and not decide._one_edit("79", "45"), "_one_edit：错一位才算")
    check(decide.same_decision(_k(2002, "scc", 3), "CA", 1, _k(2002, "scc", 33), "CA", 445),
          "#49 号码掉一位且罕见 -> 笔误并入（Housen）")
    check(not decide.same_decision(_k(2005, "scc", 79), "CA", 3, _k(2005, "scc", 75), "CA", 4),
          "#49 规模闸：引用量相近不当笔误（MacKay）")
    check(decide.same_decision(_k(2014, "scc", 7), "CA", 3, _k(2014, "csc", 7), "CA", 5),
          "#49 双语代码同一判决，不看规模（SCC/CSC）")
    check(decide.same_decision(_k(2005, "scc", 20), "CA", 1, _k(2006, "scc", 20), "CA", 18),
          "#49 年份错一年（Placer Dome）")
    check(not decide.same_decision(_k(2002, "scc", 79), "CA", 24, _k(2003, "scc", 45), "CA", 34),
          "#49 号码全不同是不同判决（Wewaykum 本案与回避申请）")
    check(not decide.same_decision(_k(2017, "scc", 17), "CA", 1, _k(2018, "nbqb", 17), "NB", 151),
          "#49 不同法院必是不同判决")
    parts = decide.windows([(2001, "a"), (2002, "b"), (2003, "c"), (2004, "d")])
    check([[x for _, x in p] for p in parts] == [["a", "b"], ["c", "d"]], "#48 ±1 年窗口切段")


# ============================================================ 迷你全链
MINI_FIELDS = ["raw_string", "source_decision_citation", "source_decision_year",
               "rejected_reason", "name_rejected_reason", "candidate_case_name",
               "abbreviation", "citation_kind", "jurisdiction", "jurisdiction_confidence",
               "year_start", "vol", "series", "page"]


def _m(court, did, raw, kind, abbr, jur, year, page, vol="", name="", rej=""):
    return {"raw_string": raw, "source_decision_citation": "%s_%s" % (court, did),
            "source_decision_year": "2020", "rejected_reason": rej, "name_rejected_reason": "",
            "candidate_case_name": name, "abbreviation": abbr, "citation_kind": kind,
            "jurisdiction": jur, "jurisdiction_confidence": "confirmed" if kind == "neutral" else "estimated",
            "year_start": str(year), "vol": vol, "series": "", "page": str(page)}


def _neu(court, did, year, code, num, jur, name):
    return _m(court, did, "%s %s %s" % (year, code, num), "neutral", code, jur, year, num, name=name)


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


def _write(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MINI_FIELDS)
        w.writeheader()
        w.writerows(rows)


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
    check((g[0]["distinct_decisions_count"], g[0]["occurrence_count"]) == ("5", "9"),
          "#46 dd 取并集（5，不是相加的 9）；#47 跨院 occurrence 不重复累加（9）")
    counted = sum(1 for r in scc + onca if not r["rejected_reason"])
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
    did = decide.load_decision_ids(os.path.join(tmp, "decide", "cross", "decision_ids.csv"))
    check(all(len(set(decide.decisions_of(ms, did)[0].values())) <= 1 for ms in groups.values()),
          "#49 硬不变量：任何一组不含两个不同判决（按裁定层同一判据复算）")

    # ---- 选取层
    sel = {r["merge_key"]: r["kept"] for r in _read(os.path.join(tmp, "select", "selected.csv"))}
    check(sel["2011||scc||99"] == "false" and sel["1999|1|scr||688"] == "true",
          "选取层：dd 过门槛才 kept，不删行")



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
              test_decide_units, test_mini_chain):
        t()
    print("全部通过：%d 条断言" % len(PASSED))


if __name__ == "__main__":
    main()
