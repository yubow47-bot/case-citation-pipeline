# -*- coding: utf-8 -*-
"""PROBLEMS #99：`[YYYY] FCA N`（方括号年份）是澳大利亚联邦法院的印刷形，不得判给加拿大；
加拿大 `YYYY FCA N`（无方括号）照旧；其他中立码的方括号形不受影响。"""
import os
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from pipeline import classify, extract  # noqa: E402

COURTS = [{"court_code": c, "normalized_key": c, "jurisdiction": "CA"} for c in ("SCC", "FCA")]
clf = classify.Classifier({"neutral_court_codes": COURTS, "reporter_jurisdiction": [], "series_prefix": [],
                           "id_prefixes": classify.load_id_prefixes(),
                           "non_citation_words": classify.load_non_citation_words()}, Counter())
FAILED = []


def run(text, shape):
    out = [clf.run_row(dict(c, candidate_case_name="")) for c in extract.extract_candidates(text, "", 2010, 0, "X")[0]
           if c["shape_name"] == shape]
    return out[0] if out else None


r = run("see GEC Marconi, [2003] FCA 50 at", "shape_bracket")
if not r or r["jurisdiction"] != "UNSUPPORTED" or "bracketed_year_foreign_form" not in r["rejected_reason"]:
    FAILED.append("[2003] FCA 50 应被保留不判：%r" % (r,))
r = run("see Smith, 2003 FCA 50 at", "shape_neutral_bare")
if not r or r["jurisdiction"] != "CA" or r["citation_kind"] != "neutral":
    FAILED.append("2003 FCA 50 应仍判 CA：%r" % (r,))
r = run("see Smith, [2003] SCC 5 at", "shape_bracket")
if not r or r["jurisdiction"] != "CA":
    FAILED.append("[2003] SCC 5 不应受影响：%r" % (r,))

# PROBLEMS #104：`[年] 卷 FC 页` 是 Federal Court Reports，不是中立码；卷号=年号的重复写法保留
REP = [{"abbreviation": "F.C.", "normalized_key": "fc", "jurisdiction": "CA", "vol_range_start": "",
        "vol_range_end": "", "year_range_start": "", "year_range_end": ""}]
clf2 = classify.Classifier({"neutral_court_codes": COURTS + [{"court_code": "ABCA", "normalized_key": "ABCA",
                            "jurisdiction": "CA"}, {"court_code": "FC", "normalized_key": "FC", "jurisdiction": "CA"}],
                            "reporter_jurisdiction": REP, "series_prefix": [],
                            "id_prefixes": classify.load_id_prefixes(),
                            "non_citation_words": classify.load_non_citation_words()}, Counter())
for text, kind in [("see Still, [1998] 1 FC 549 at", "reporter"), ("see X, [1999] 1999 ABCA 305 at", "neutral")]:
    cs = [clf2.run_row(dict(c, candidate_case_name="")) for c in extract.extract_candidates(text, "", 2010, 0, "X")[0]
          if c["shape_name"] == "shape_bracket"]
    if not cs or cs[0]["citation_kind"] != kind:
        FAILED.append("%r 应为 %s：%r" % (text, kind, cs[:1]))

print("全部通过：5 条断言") if not FAILED else None
for f in FAILED:
    print("FAIL: " + f)
sys.exit(1 if FAILED else 0)
