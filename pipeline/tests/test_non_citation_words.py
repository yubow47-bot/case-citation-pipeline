# -*- coding: utf-8 -*-
"""test_non_citation_words.py — decisions/non_citation_words.csv 驱动的拒收规则回归防线。

结构词/日历词/案名片段被 shape_vol_abbr_page 读成「卷 缩写 页」（`7 Section 69`、
`3 See Villani v`、`1 May 2014`）：classify step2 标 rejected_reason=non_citation_word。
三条防线：
  A. 正例：真实样例被拒；
  B. 反例：真汇编、`ON CA` 括注、大写 `C` 末词、已登记汇编同名词都不被拒（区分大小写 + 安全阀）；
  C. 表自检：表里每个 whole 词都不与 reporter_jurisdiction 撞键。
用法：python pipeline/tests/test_non_citation_words.py    失败即退出码非 0。
"""
import csv
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.dirname(HERE)
ROOT = os.path.dirname(PIPE)
sys.path.insert(0, PIPE)
sys.path.insert(0, HERE)

import classify                                   # noqa: E402
import extract                                    # noqa: E402

FAILED = []
PASSED_N = 0


def check(name, cond, detail=""):
    global PASSED_N
    if cond:
        PASSED_N += 1
    else:
        FAILED.append("%s %s" % (name, detail))


REPORTERS = [{"abbreviation": a, "normalized_key": classify.nk(a), "jurisdiction": "CA",
              "vol_range_start": "", "vol_range_end": "", "year_range_start": "", "year_range_end": ""}
             for a in ("C.C.C.", "K.B.", "S.C.R.")]
COURTS = [{"court_code": c, "normalized_key": c, "jurisdiction": "CA"} for c in ("SCC", "ONCA", "FCA")]


def make(reporters=None):
    return classify.Classifier({"neutral_court_codes": COURTS, "reporter_jurisdiction": reporters or REPORTERS,
                                "series_prefix": [], "id_prefixes": classify.load_id_prefixes(),
                                "non_citation_words": classify.load_non_citation_words()}, Counter())


def reasons(clf, text, shape="shape_vol_abbr_page", abbr=None):
    cands = [c for c in extract.extract_candidates(text, "", 2010, 0, "SST")[0] if c["shape_name"] == shape
             and (abbr is None or c["abbr"] == abbr or c["token"] == abbr)]
    if not cands:
        return None
    return [clf.run_row(dict(c, candidate_case_name=""))["rejected_reason"] for c in cands]


clf = make()
# ---- A. 正例（缩写位是结构词/日历词/案名片段）----
for text, abbr in [
    ("Footnote 7 Section 69 of the Act", "Section"),
    ("33 Footnote 29", "Footnote"),
    ("hearing 4 See Mishibinijima v Canada", None),         # 首词 See
    ("held on 30 On November 3, 2007", None),                # 首词 On
    ("Exhibit 5 12 April 1 was filed", "April"),             # 月份整词
    ("table 2 X 3 mm", "X"),                                 # 关税表
    ("In 10 In January 2019 the Tribunal", None),            # 第二批：In + 月份
    ("Exhibit 000 Total 11 amount", "Total"),
    ("filed 000 Dec. 2007 at", "Dec."),
    ("held 62 The December 12 hearing", "The December"),     # The + 月份：整词
    ("Notice 16 Villani v Canada", None),                    # 单字符罗马页 v（无句点的 versus）
    ("see 620247 Ontario Ltd. v Smith", None),               # 编号公司
]:
    r = reasons(clf, text, abbr=abbr)
    check("A 拒收 %r" % text, r and all(("non_citation_word" in x or "versus_as_page" in x) for x in r),
          "got=%r" % (r,))

# ---- B. 反例 ----
for text, shape, abbr in [
    ("[1928] 2 K.B. 100", "shape_bracket", "K.B."),
    ("R. v. Smith, 20 C.C.C. 1", "shape_vol_abbr_page", "C.C.C."),
    ("see 50 Cl. C 99 for", "shape_vol_abbr_page", None),                # 末词大写 C ≠ 案名分隔符 c.
    ("[1983] 2 S.C.R. v", "shape_bracket", "S.C.R."),             # 真罗马页：缩写已登记，不是 versus
    ("Browne v. Dunn (1893), 6 The Reports 67 (H.L.)", "shape_vol_abbr_page", None),   # 首词 The 的案例汇编（2026-10-03 误杀；期刊不在本项目范围，测试不对期刊表态）
    ("[1952] 1 The Times L.R. 101", "shape_vol_abbr_page", None),
]:
    r = reasons(clf, text, shape=shape, abbr=abbr)
    check("B 不拒收 %r" % text, r is not None and all("non_citation_word" not in x for x in r), "got=%r" % (r,))

# 安全阀：与拒收词同名的「已登记汇编」不被拒（单独造一个登记了 Section 的分类器）
clf2 = make(REPORTERS + [{"abbreviation": "Section", "normalized_key": "section", "jurisdiction": "CA",
                          "vol_range_start": "", "vol_range_end": "", "year_range_start": "", "year_range_end": ""}])
r = reasons(clf2, "Lloyd v. Lloyd, 5 Section 7", abbr="Section")
check("B 安全阀：已登记汇编 Section 不被拒", r is not None and all("non_citation_word" not in x for x in r), "got=%r" % (r,))

# ON CA 括注（安省上诉法院）：大小写区分，首词 ON ≠ On
r = reasons(clf, "Roy v. Gagnon, 2011 ON CA 526", shape="shape_vol_abbr_page")
check("B ON CA 不被首词 On 误杀", r is None or all("non_citation_word" not in x for x in r), "got=%r" % (r,))

# ---- C. 表自检 ----
rep_keys = {r["normalized_key"] for r in csv.DictReader(
    open(os.path.join(ROOT, "decisions", "reporter_jurisdiction.csv"), encoding="utf-8"))}
tbl = list(csv.DictReader(open(os.path.join(ROOT, "decisions", "non_citation_words.csv"), encoding="utf-8")))
check("C 表非空", len(tbl) > 20, "rows=%d" % len(tbl))
for r in tbl:
    check("C 每行带出处与观测计数 %s/%s" % (r["word"], r["match_type"]),
          r["source"].strip() and r["source_locator"].strip() and int(r["observed_count"]) > 0)
    if r["match_type"] == "whole":
        check("C 整词不与已登记汇编撞键 %s" % r["word"], classify.nk(r["word"]) not in rep_keys)

print("全部通过：%d 条断言" % PASSED_N) if not FAILED else None
for f in FAILED:
    print("FAIL: " + f)
sys.exit(1 if FAILED else 0)
