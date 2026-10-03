# -*- coding: utf-8 -*-
"""test_registered_id.py — v1.6（PROBLEMS #107）两个表驱动形状的回归防线。

  shape_registered_id  decisions/id_prefixes.csv 驱动：登记前缀+编号，无年份槽
  shape_neutral_glued  年份+法院码+序号无空格粘连（2005TCC640）

三层断言：
  A. 每个前缀至少 1 正例（逐字取自语料残差挖掘或格式定义）+ 反例；
  B. 噪声家族结构性不中：SST 证据页码 GD2-11、证物号 Exhibit PR-2009-080-09、
     招标号 EP-803-183135/G、纯年份 CP 2005、EYB…DEV 文章号；
  C. classify：docket 保留不计数（rejected_reason=docket_not_decision）；
     decision 型按 identifier；未核实行法域一律 UNSUPPORTED。

用法：python pipeline/tests/test_registered_id.py     失败即退出码非 0。
"""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.dirname(HERE)
sys.path.insert(0, PIPE)
sys.path.insert(0, HERE)

import classify                                   # noqa: E402
import extract                                    # noqa: E402
import shapes                                     # noqa: E402

FAILED = []
PASSED_N = 0


def check(name, cond, detail=""):
    global PASSED_N
    if cond:
        PASSED_N += 1
    else:
        FAILED.append("%s %s" % (name, detail))


def new_shapes(text):
    cands = extract.extract_candidates(text, "", 2010, 0, "TCC")[0]
    return [c for c in cands if c["shape_name"] in ("shape_registered_id", "shape_neutral_glued")]


# ---- A. 正例：(原文, 期望 token, 期望 page) ----
POS = [
    ("Walford, A-263-78, December 5, 1978.", "A-", "263-78"),
    ("Pincombe v. Canada (A.G.), (1995), A-675-94", "A-", "675-94"),
    ("A‑263‑78 x", "A-", "263-78"),                  # U+2011 非断行连字符（SST 实测）
    ("Court File T-1334-09)", "T-", "1334-09"),
    ("IMM-1234-20", "IMM-", "1234-20"),
    ("Resources Development, CP 20466 (PAB)", "CP", "20466"),
    ("CP20748, 2003", "CP", "20748"),
    ("PSSRB File No. 168-02-37 (19731120)", "PSSRB File No.", "168-02-37"),
    ("PSLRB Files 547-02-4 to 547-02-06", "PSSRB File No.", "547-02-4"),
    ("Panel Report, WT/DS440/R at para. 7.2", "WT/DS", "440"),
    ("Agency (8 March 2019), AP-2017-052 (CITT)", "AP-", "2017-052"),
    ("Inquiry No. NQ-2000-005 (CITT)", "NQ-", "2000-005"),
    ("Reference number AD-16-785 Member", "AD-", "16-785"),
    ("Commission, GE-16-1958, February 20, 2017", "GE-", "16-1958"),
    ("Tremblay c. Roy, AZ-50234567 (C.A.)", "AZ-", "50234567"),
    ("Roy c. Gagnon, J.E. 2004-1234 (C.S.)", "J.E.", "2004-1234"),
    ("Syndicat c. X, D.T.E. 2003T-123.", "D.T.E.", "2003T-123"),
    ("Untel c. Untel, REJB 1998-07890.", "REJB", "1998-07890"),
    ("Untel c. Untel, EYB 2004-12345 (C.A.)", "EYB", "2004-12345"),
    # 零星漏抓（2026-10-03 复查）
    ("Von Der Kammer v MNHW (July 19, 1991), CP 1916, CEB", "CP", "1916"),      # 年份样 CP 号
    ("Vaughn v. Minister, CP 1971 (May 1992): It", "CP", "1971"),
    ("Decoux (Appeal CP2046, decided July", "CP", "2046"),
    ("PSSRB File No. 100-1 (19920331); Ma", "PSSRB File No.", "100-1"),        # 两段号
    ("Smith, PSSRB File No. 166-02�C3017 (19771007", "PSSRB File No.", "166-02-3017"),  # 破损破折号
    ("(18 November 2011), AP-010-063 (CITT). 5", "AP-", "010-063"),            # CITT 笔误年份
    ("PR-2013-005 and PR-0213-008 (CITT) at", "PR-", "0213-008"),
    ("Latremouille v. Union, 50 di 197; citing", "50 DI", "197"),              # CLRB 汇编，卷号进 token
    ("Provost Cartage Inc. (1985), 61 di 77 (CLRB no. 517)", "61 DI", "77"),
]
for text, tok, page in POS:
    got = [(c["token"], c["page"]) for c in new_shapes(text) if c["shape_name"] == "shape_registered_id"]
    check("A 正例 %r" % text, (tok, page) in got, "got=%r" % got)

# 粘连中立：与 neutral_bare 同构（token=法院码，page=序号，year）
g = [c for c in new_shapes("Yaskiel v. The Queen, 2005TCC640.") if c["shape_name"] == "shape_neutral_glued"]
check("A 粘连中立 2005TCC640", len(g) == 1 and (g[0]["token"], g[0]["page"], g[0]["year_raw"]) == ("TCC", "640", "2005"),
      "got=%r" % g)
g = [c for c in new_shapes("Carroll, 2011FC1092 para 14") if c["shape_name"] == "shape_neutral_glued"]
check("A 粘连中立 2011FC1092", len(g) == 1 and g[0]["token"] == "FC", "got=%r" % g)

# ---- B. 反例：结构性不中 ----
NEG = [
    "GD2-11 to GD2-13", "AD1-13", "IS3-14 to 20",            # SST 证据页码
    "Tribunal Exhibit PR-2009-080-09",                        # CITT 证物号（三段）
    "Solicitation No. EP-803-183135/G", "Solicitation No. W8472-085129/A",
    "CP 2005 results",                                        # 纯年份
    "EYB2005DEV1234",                                         # 学术文章号
    "Q1-06", "Pages 66-67", "Tabs 37-38",
    "CA-123-45",                                              # 前缀嵌在更长 token 内
    "A-1234567-94",                                           # 位数超界
    "Solicitation No. EP-803-1234/A",                         # CITT 招标号的斜杠续接
    "12005TCC640",                                            # 粘连年份前再有数字
    "2005ABCDEF640",                                          # 非登记法院码
]
for text in NEG:
    check("B 反例 %r" % text, not new_shapes(text), "got=%r" % [c["raw_string"] for c in new_shapes(text)])

# 既有形状不受影响：同一段里的常规引证仍照抽
base = extract.extract_candidates("Roy c. Gagnon, 2010 QCCA 123, and A-263-78.", "", 2010, 0, "TCC")[0]
check("A 并存：常规中立引证与案卷号同段互不挤占",
      {"shape_neutral_bare", "shape_registered_id"} <= {c["shape_name"] for c in base})


# ---- C. classify ----
def _clf():
    court = [{"court_code": "TCC", "normalized_key": "TCC", "jurisdiction": "CA"}]
    return classify.Classifier({"neutral_court_codes": court, "reporter_jurisdiction": [],
                                "series_prefix": [], "id_prefixes": classify.load_id_prefixes()},
                               Counter())


def _row(text):
    cand = [c for c in new_shapes(text) if c["shape_name"] == "shape_registered_id"][0]
    row = dict(cand)
    row.setdefault("candidate_case_name", "")
    return row


clf = _clf()
r = clf.run_row(_row("Walford, A-263-78, December 5, 1978."))
check("C docket：kind=docket", r["citation_kind"] == "docket", "got=%r" % r["citation_kind"])
check("C docket：保留不计数（rejected_reason）", "docket_not_decision" in (r.get("rejected_reason") or ""),
      "got=%r" % r.get("rejected_reason"))
check("C 未核实行法域 UNSUPPORTED", r["jurisdiction"] == "UNSUPPORTED", "got=%r" % r["jurisdiction"])
r = clf.run_row(_row("Agency (8 March 2019), AP-2017-052 (CITT)"))
check("C {prefix} 行反查：AP- → docket", r["citation_kind"] == "docket" and r["abbreviation"] == "AP-",
      "got=%r" % ((r["citation_kind"], r["abbreviation"]),))
r = clf.run_row(_row("Tremblay c. Roy, AZ-50234567 (C.A.)"))
check("C decision 型未核实：kind=identifier，保留但不计数（unverified_id_prefix）",
      r["citation_kind"] == "identifier" and "unverified_id_prefix" in (r.get("rejected_reason") or ""),
      "got=%r" % ((r["citation_kind"], r.get("rejected_reason")),))
check("C decision 型未核实：法域 UNSUPPORTED", r["jurisdiction"] == "UNSUPPORTED", "got=%r" % r["jurisdiction"])

# decision 型核实后转为计数：构造一张 verified 的表行，同一条 AZ- 不再被拒、法域套用
_rows_v = [dict(r, verification_status="verified_official_source") if r["prefix_id"] == "QC_AZ" else r
           for r in shapes.ID_PREFIX_ROWS]
import re as _re
_idp = []
for r_ in _rows_v:
    canon = r_["canonical_token"]
    pat = (_re.escape(canon).replace(_re.escape("{prefix}"), "(?:" + r_["prefix_regex"] + ")")
           if "{prefix}" in canon else _re.escape(canon))
    _idp.append((_re.compile(pat, _re.I), r_))
_clf_v = classify.Classifier({"neutral_court_codes": [], "reporter_jurisdiction": [], "series_prefix": [],
                              "id_prefixes": _idp}, Counter())
r = _clf_v.run_row(_row("Tremblay c. Roy, AZ-50234567 (C.A.)"))
check("C decision 型核实后：计数且套用法域 QC",
      r["citation_kind"] == "identifier" and not r.get("rejected_reason") and r["jurisdiction"] == "QC",
      "got=%r" % ((r["citation_kind"], r.get("rejected_reason"), r["jurisdiction"]),))

# 年份区间括注
for text, tok, yr, pg in [("Taylor, [1956] C.T.C. 189", "C.T.C.", "1956", "189"),
                          ("M.N.R. v. Taylor, [1956-60] Ex.C.R. 3, at pages 26", "Ex.C.R.", "1956", "3"),
                          ("King v. Plotkins, [1938-39] C.T.C. 138 (Ex.", "C.T.C.", "1938", "138")]:
    got = [c for c in extract.extract_candidates(text, "", 2010, 0, "TCC")[0]
           if c["shape_name"] in ("shape_bracket", "shape_bracket_range")]
    check("A 区间括注 %r" % text, any((c["token"], c["year_raw"], c["page"]) == (tok, yr, pg) for c in got),
          "got=%r" % [(c["shape_name"], c["token"], c["year_raw"], c["page"]) for c in got])

# 表里每一行都必须有可反查的规范 token（表与抽取同步的防线）
for row in shapes.ID_PREFIX_ROWS:
    ex = row["example"]
    got = [c for c in new_shapes(ex) if c["shape_name"] == "shape_registered_id"]
    check("D 表行自检 %s 的 example %r 必须被自己抽到" % (row["prefix_id"], ex), bool(got),
          "got=%r" % [c["raw_string"] for c in got])
    if got:
        rr = clf.run_row(dict(got[0], candidate_case_name=""))
        check("D 表行 %s 分类可反查" % row["prefix_id"], rr["citation_kind"] in ("docket", "identifier"),
              "got=%r" % rr["citation_kind"])

print("全部通过：%d 条断言" % PASSED_N) if not FAILED else None
for f in FAILED:
    print("FAIL: " + f)
sys.exit(1 if FAILED else 0)
