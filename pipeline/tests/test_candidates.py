# -*- coding: utf-8 -*-
"""test_candidates.py — candidates-2.0 全候选路线的回归防线（阶段 1/2 新增）

用法
    python pipeline/tests/test_candidates.py

与 test_layers.py 的分工：那边钉住 legacy 路线（v1.4 旧去重 + 旧归并），期望值不动；
本文件钉住**新全候选路线**：重叠枚举 + 边界闸 + D3 跨界标注 + 逐候选分类 +
判决内仲裁。期望值全部按新路线实测重定，不沿用旧夹具阈值。

测试分两档：
  * 集成档：真七形状正则 + 真分类器 + 真仲裁函数（Kvello / BCE / Almrei 等）；
  * 单元档：仲裁函数的合围规则用手工候选行钉（合成数据，只测规则本身，
    绝不作为真实数据结果出展示）。
"""
import copy
import os
import random
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.dirname(HERE)
sys.path.insert(0, PIPE)
sys.path.insert(0, HERE)

import extract                                    # noqa: E402
import merge                                      # noqa: E402
import classify                                   # noqa: E402

PASSED = []


def check(cond, label):
    if not cond:
        raise AssertionError(label)
    PASSED.append(label)


def _clf():
    court = [{"court_code": "SCC", "normalized_key": "SCC", "jurisdiction": "CA"},
             {"court_code": "ONCA", "normalized_key": "ONCA", "jurisdiction": "CA"},
             {"court_code": "UKHL", "normalized_key": "UKHL", "jurisdiction": "GB"}]

    def rep(abbr, jur, y0="", y1=""):
        return {"abbreviation": abbr, "normalized_key": classify.nk(abbr),
                "jurisdiction": jur, "confidence": "estimated",
                "vol_range_start": "", "vol_range_end": "",
                "year_range_start": y0, "year_range_end": y1}
    reporter = [rep("S.C.R.", "CA"), rep("K.B.", "GB"), rep("K.B.", "QC"),
                rep("D.L.R.", "CA")]
    return classify.Classifier({"neutral_court_codes": court,
                                "reporter_jurisdiction": reporter,
                                "series_prefix": []}, Counter())


def candidates_of(text, court="SCC", row=0):
    """真七形状重叠枚举 + D3 标注。返回候选行列表。"""
    sdc = "%s_testcase%d" % (court, row)
    cands, blocked = extract.extract_candidates(text, sdc, "2020", row, court)
    extract.annotate_cross_boundary(cands, text)
    return cands


def classified_of(text, court="SCC", row=0, clf=None):
    """抽取 + 逐候选分类（不仲裁）。"""
    clf = clf or _clf()
    return [clf.run_row(dict(c)) for c in candidates_of(text, court, row)]


def arbitrated(text, court="SCC", row=0, clf=None):
    """抽取 + 分类 + 判决内仲裁。返回 {candidate_id: status} 与统计。"""
    rows = classified_of(text, court, row, clf)
    stats = Counter()
    verdicts = merge.arbitrate_document(rows, stats)
    return rows, verdicts, stats


def counted_raws(verdicts, rows):
    return sorted(r["raw_string"] for r in rows
                  if verdicts[r["candidate_id"]][0] == "counted")


def status_of(verdicts, rows, raw, shape=None):
    hits = [verdicts[r["candidate_id"]][0] for r in rows
            if r["raw_string"] == raw
            and (shape is None or r["shape_name"] == shape)]
    assert len(hits) == 1, "raw %r（shape=%r）命中 %d 个候选（应唯一）" % (raw, shape, len(hits))
    return hits[0]


# ================================================================ 集成档
def test_kvello_2009_scc_51():
    """Kvello Estate：2009 SCC 51 同跨度两读法，表证据唯一支持年读法 → 计一次。"""
    text = "Estate of Kvello, 2009 SCC 51, at para. 12."
    rows, verdicts, stats = arbitrated(text)
    check(status_of(verdicts, rows, "2009 SCC 51", shape="shape_vol_abbr_page") in
          ("alternative_unsupported_reading", "alternative_same_key",
           "alternative_contained"),
          "Kvello：非胜出读法让位（不与胜者重复计数）")
    neutral = [r for r in rows if r["raw_string"] == "2009 SCC 51"
               and r["citation_kind"] == "neutral"]
    check(len(neutral) == 1 and verdicts[neutral[0]["candidate_id"]][0] == "counted",
          "Kvello：中立读法靠表胜出且计入一次")
    vol = [r for r in rows if r["raw_string"] == "2009 SCC 51"
           and r["shape_name"] == "shape_vol_abbr_page"]
    check(vol and vol[0]["parse_status"] == "ambiguous_year_vol"
          and vol[0]["year_vol_ambiguity"] == "unresolved_year_vs_vol",
          "Kvello：卷读法在分类层标 ambiguous_year_vol（查不到表，不默认年）")


def test_bce_swallow():
    """BCE：重叠枚举复活被吞的 2008 SCC 69；长误匹配被 D3 旗消解。"""
    text = "BCE Inc. v. 1976 Debenture Holders, 2008 SCC 69, at para. 5."
    rows, verdicts, stats = arbitrated(text)
    check(any(r["raw_string"] == "2008 SCC 69" for r in rows),
          "BCE：重叠扫描产出被旧扫描吞掉的 2008 SCC 69")
    long_bad = [r for r in rows if r["raw_string"] == "1976 Debenture Holders, 2008"]
    check(len(long_bad) >= 1
          and all(r["structural_conflict"] == "cross_boundary_year_page"
                  for r in long_bad),
          "BCE：长误匹配（两种形状读法）都打 D3 跨界旗")
    check(all(v[0] == "cross_boundary_invalid"
              for v in (verdicts[r["candidate_id"]] for r in long_bad)),
          "BCE：长误匹配全部仲裁为 cross_boundary_invalid（配对者有效）")
    check(status_of(verdicts, rows, "2008 SCC 69", shape="shape_neutral_bare")
          == "counted",
          "BCE：真引证 2008 SCC 69 计入")


def test_almrei_swallow():
    """Almrei：`2011 ONCA, 2011` 跨界误解析不再坐进最终表。"""
    text = "Almrei v. Canada (Attorney General), 2011 ONCA, 2011 ONCA 779"
    rows, verdicts, stats = arbitrated(text)
    bad = [r for r in rows if r["raw_string"] == "2011 ONCA, 2011"]
    check(bad and all(v[0] == "cross_boundary_invalid"
                      for v in (verdicts[r["candidate_id"]] for r in bad)),
          "Almrei：跨界误解析两种形状读法全部 invalidated")
    good = [r for r in rows if r["raw_string"] == "2011 ONCA 779"]
    check(good and verdicts[good[0]["candidate_id"]][0] == "counted",
          "Almrei：完整中立候选 2011 ONCA 779 计入")
    keys = {merge.build_merge_key(r) for r in rows
            if verdicts[r["candidate_id"]][0] == "counted"}
    check("|2011||onca||" not in "|".join(keys).replace("2011||onca||2011", "HIT")
          or not any(k.split("|")[4] == "2011" and k.split("|")[2] == "onca"
                     for k in keys),
          "Almrei：误解析的页=2011 键不进计数")


def test_same_span_multi_shape_counted_once():
    """同跨度多形状 → 只计一次，不重复计。"""
    text = "As held in 2019 SCC 65 and later cases."
    rows, verdicts, stats = arbitrated(text)
    same = [r for r in rows if r["raw_string"] == "2019 SCC 65"]
    check(len(same) >= 2, "2019 SCC 65：同跨度确实产出多个形状候选")
    counted = [r for r in same if verdicts[r["candidate_id"]][0] == "counted"]
    check(len(counted) == 1, "同跨度多形状只计一次（其余让位）")


def test_containment_longer_wins():
    """「3 All E.R. 12」⊂「3 All E.R. 12 (1968)」且共享字段相容 → 长者胜。"""
    text = "See Smith 3 All E.R. 12 (1968) elsewhere."
    rows, verdicts, stats = arbitrated(text)
    check(status_of(verdicts, rows, "3 All E.R. 12 (1968)") == "counted",
          "包含消解：带年份的长候选计入")
    check(status_of(verdicts, rows, "3 All E.R. 12") == "alternative_contained",
          "包含消解：被包含的短候选让位")


def test_legit_4digit_serial_not_rejected():
    """真 4 位页码（邻接处没有把同一 token 当年份的中立候选）不挨整刀：
    保留、计数、结构解析 valid——D3 旗是「关系旗」，不是对一切 4 位数字的怀疑。"""
    text = "Reported at [1996] 2 S.C.R. 1997 in full."
    rows, verdicts, stats = arbitrated(text)
    c = [r for r in rows if r["raw_string"] == "[1996] 2 S.C.R. 1997"]
    check(c and verdicts[c[0]["candidate_id"]][0] == "counted",
          "真 4 位页码：无跨界关系则保留并计数")
    check(c and c[0]["structural_conflict"] == "" and c[0]["parse_status"] == "valid",
          "真 4 位页码：不因数字位数挨打（无配对者即无旗）")


def test_year_vol_conflict_without_table_abstains():
    """代码不在任何表：同跨度两读法全 UNSUPPORTED → 弃权（span_alternative_undecided），
    不默认任何一方，也不重复计数。"""
    text = "Mentioned in passing: 2009 XYZ 51 per counsel."
    rows, verdicts, stats = arbitrated(text)
    same = [r for r in rows if r["raw_string"] == "2009 XYZ 51"]
    check(same and all(verdicts[r["candidate_id"]][0] == "span_alternative_undecided"
                       for r in same),
          "无表证据的同跨度两读法：整组弃权")
    check(stats.get("same_span_abstained", 0) >= 1,
          "弃权入统计（可审计）")


def test_long_span_two_reals_both_kept():
    """单元档（合成候选行）：长误匹配横跨两条互不重叠的真候选 → 两条短候选都保留，
    长者不赢（重叠组不要求唯一赢家，也不硬选最长）。"""
    def cand(cid, start, end, raw, key_fields):
        r = {"candidate_id": cid, "corpus_row_index": "0",
             "source_decision_citation": "SCC_t0", "raw_string": raw,
             "shape_name": "shape_vol_abbr_page",
             "match_start_offset": start, "match_end_offset": end,
             "citation_kind": "reporter", "jurisdiction": "CA",
             "jurisdiction_confidence": "estimated", "parse_status": "valid",
             "structural_conflict": "", "rejected_reason": "", "self_citation": "",
             "candidate_case_name": "", "source_decision_year": "2020"}
        r.update(key_fields)
        return r
    a = cand("a", 4, 20, "12 A.B. 34", {"year_start": "1968", "vol": "12",
                                        "abbr": "A.B.", "page": "34"})
    b = cand("b", 26, 42, "5 C.D. 56", {"year_start": "1969", "vol": "5",
                                        "abbr": "C.D.", "page": "56"})
    L = cand("L", 0, 60, "12 A.B. 34 (1968) and 5 C.D. 56", {
        "year_start": "", "vol": "12", "abbr": "A.B.", "page": "34"})
    stats = Counter()
    v = merge.arbitrate_document([L, a, b], stats)
    check(v["a"][0] == "counted" and v["b"][0] == "counted",
          "长误匹配横跨两真候选：两条短候选同时保留")
    check(v["L"][0] != "counted",
          "长误匹配本身不凭跨度取胜")


def test_equal_strength_conflict_abstains():
    """单元档：同跨度、两种含义、双方都有表支持且法域冲突 → 弃权。"""
    def cand(cid, kind, jur, year, vol):
        return {"candidate_id": cid, "corpus_row_index": "0",
                "source_decision_citation": "SCC_t0",
                "raw_string": "1930 K.B. 5", "shape_name": "shape_vol_abbr_page",
                "match_start_offset": 0, "match_end_offset": 13,
                "citation_kind": kind, "jurisdiction": jur,
                "jurisdiction_confidence": "estimated", "parse_status": "valid",
                "structural_conflict": "", "rejected_reason": "",
                "self_citation": "", "candidate_case_name": "",
                "source_decision_year": "2020",
                "year_start": year, "vol": vol, "abbr": "K.B.", "page": "5"}
    stats = Counter()
    # 年读法（year=1930, 无卷）vs 卷读法（vol=1930, 无年）：异键、双方都有表支持且冲突
    v = merge.arbitrate_document(
        [cand("x", "reporter", "GB", "1930", ""),
         cand("y", "reporter", "QC", "", "1930")], stats)
    check(v["x"][0] == "span_alternative_undecided"
          and v["y"][0] == "span_alternative_undecided",
          "同跨度异含义、证据相持：双双弃权，不硬选")


def test_input_order_invariance():
    """候选输入顺序不影响仲裁结果（打乱三次全同）。"""
    text = ("Estate of Kvello, 2009 SCC 51, 2009 SCC 52; see also "
            "BCE Inc. v. 1976 Debenture Holders, 2008 SCC 69.")
    base = None
    for seed in range(3):
        rows = classified_of(text, row=0)
        rnd = random.Random(seed)
        rnd.shuffle(rows)
        stats = Counter()
        v = merge.arbitrate_document(rows, stats)
        got = sorted((r["candidate_id"], v[r["candidate_id"]][0],
                      v[r["candidate_id"]][2]) for r in rows)
        if base is None:
            base = got
        check(got == base, "打乱输入（seed=%d）仲裁结果不变" % seed)


def test_boundary_guard():
    """边界闸：不许从 123 A.C. 4 里截出 23 A.C. 4；闸拦下数入统计。"""
    cands, blocked = extract.extract_candidates(
        "Ref. 123 A.C. 4 end.", "SCC_t0", "2020", 0, "SCC")
    check(blocked >= 1, "边界闸：截断尝试被拦下并入计数")
    check(not any(c["raw_string"].startswith(("23 A.C.", "3 A.C."))
                  for c in cands),
          "边界闸：不许从 123 A.C. 4 里截出 23 A.C. 4 / 3 A.C. 4")
    text2 = "BCE Inc. v. 1976 Debenture Holders, 2008 SCC 69"
    cands2, _ = extract.extract_candidates(text2, "SCC_t0", "2020", 0, "SCC")
    raws = {c["raw_string"] for c in cands2}
    check("2008 SCC 69" in raws, "重叠枚举产出被旧扫描吞掉的候选")
    check(not any(c["raw_string"].startswith("976 ") for c in cands2),
          "边界闸：不出 976 Debenture… 截断垃圾")


def test_grouping_by_row_not_by_decision_id():
    """62 份 SCC 文档共享 sdc=SCC_ 时，不同文档（corpus_row_index 不同）的候选
    不得互相仲裁。走 run_candidates 真路径：同 sdc、不同 row 的重叠候选都计数。"""
    import csv as _csv
    import tempfile
    base = {"candidate_id": "", "corpus_row_index": "0",
            "match_start_offset": "0", "match_end_offset": "10",
            "source_decision_citation": "SCC_",
            "source_decision_year": "2020", "raw_string": "12 A.B. 34",
            "shape_name": "shape_vol_abbr_page", "token": "", "leading_abbr": "",
            "serial_marker": "", "page_prefix": "", "page_roman": "",
            "page_suffix": "", "series": "", "series_paren": "", "paren_note": "",
            "year_raw": "1968", "year_start": "1968",
            "year_span": "-1:-1", "page_span": "-1:-1", "vol_span": "-1:-1",
            "abbr_span": "-1:-1", "parse_signature": "test",
            "preceding_text": "", "structural_conflict": "",
            "conflict_with_candidate": "", "conflict_note": "",
            "citation_kind": "reporter", "jurisdiction": "CA",
            "jurisdiction_confidence": "estimated", "lookup_mode": "exact",
            "vol_missing": "", "series_prefix": "", "candidate_case_name": "",
            "rejected_reason": "", "name_rejected_reason": "", "disambiguated_by": "",
            "self_citation": "", "parse_status": "valid", "year_vol_ambiguity": ""}
    rows = []
    for i, (row, start) in enumerate((("0", "0"), ("1", "0"))):
        r = dict(base)
        r["candidate_id"] = "SCC:%s:0:10:shape_vol_abbr_page" % row
        r["corpus_row_index"] = row
        r["match_start_offset"] = start
        r["match_end_offset"] = str(int(start) + 10)
        rows.append(r)
    tmp = tempfile.mkdtemp(prefix="test_cand_")
    inp = os.path.join(tmp, "classified.csv")
    with open(inp, "w", encoding="utf-8", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=list(base.keys()))
        w.writeheader()
        w.writerows(rows)
    outd = os.path.join(tmp, "out")
    stats = Counter()
    class _A:
        court = "SCC"
        input = inp
        output = outd
    merge.run_candidates(_A, stats)
    import json
    m = json.load(open(os.path.join(outd, "manifest.json"), encoding="utf-8"))
    check(m["stats"]["documents"] == 2,
          "run_candidates 按 (sdc, row_index) 分文档：2 个文档")
    merged = list(_csv.DictReader(open(os.path.join(outd, "merged.csv"),
                                       encoding="utf-8", newline="")))
    check(len(merged) == 1 and merged[0]["occurrence_count"] == "2"
          and merged[0]["distinct_decisions_count"] == "1",
          "同 sdc 不同语料行的重叠候选互不仲裁（occ 2 / dd 1）")


def test_new_path_fixture_measurements():
    """新路线夹具计档（独立于旧 A18/B15/C27/D6/E0/F0——那是旧去重路线的
    legacy/diagnostic 检查，两套数字并存，互不挪用）。断言：
      * 正夹具：真表分类 + 仲裁后的 exact 命中 **不低于** 旧路线（全候选
        路线只许多不许少——少 = 仲裁吞了旧路线已有的正确候选，回归）；
      * 负夹具（E/F）：真值为空，exact 恒 0； counted 计数即负对照误报量，
        实测值钉在下方（改规则后复核再改）。"""
    from fixtures import FIXTURES
    from truth import TRUTH
    tables = {n: classify.load_table(n + ".csv") for n in
              ("neutral_court_codes", "reporter_jurisdiction", "series_prefix")}
    clf = classify.Classifier(tables, Counter())
    out = {}
    for fx in FIXTURES:
        rows = classified_of(fx["text"], court="SCC", row=fx["row"], clf=clf)
        stats = Counter()
        v = merge.arbitrate_document(rows, stats)
        counted = [r for r in rows if v[r["candidate_id"]][0] == "counted"]
        exact = sum(1 for ti in TRUTH["fixtures"].get(fx["id"], {}).get("items", [])
                    if any(r["raw_string"] == ti["what"] for r in counted))
        out[fx["id"]] = (exact, len(counted))
    OLD = {"A_1877_1899_footnotes": 18, "B_1930_1940_footnotes": 15,
           "C_1960s_parallel_cites": 27, "D_cases_cited_block": 6,
           "E_prose_negative": 0, "F_statute_biblio_negative": 0}
    NEW_FP_CEILING = {"E_prose_negative": 0, "F_statute_biblio_negative": 6}
    for fid, old_expect in OLD.items():
        exact, n_counted = out[fid]
        if fid in NEW_FP_CEILING:
            check(n_counted <= NEW_FP_CEILING[fid],
                  "新路线负夹具 %s：counted=%d（误报上限 %d）"
                  % (fid, n_counted, NEW_FP_CEILING[fid]))
        else:
            check(exact >= old_expect,
                  "新路线夹具 %s：exact=%d 不得低于旧路线 %d（多了是新路线的增益，"
                  "少了是仲裁吞错）" % (fid, exact, old_expect))


def main():
    for t in (test_boundary_guard, test_kvello_2009_scc_51, test_bce_swallow,
              test_almrei_swallow, test_same_span_multi_shape_counted_once,
              test_containment_longer_wins, test_legit_4digit_serial_not_rejected,
              test_year_vol_conflict_without_table_abstains,
              test_long_span_two_reals_both_kept,
              test_equal_strength_conflict_abstains, test_input_order_invariance,
              test_grouping_by_row_not_by_decision_id,
              test_new_path_fixture_measurements):
        t()
    print("全部通过：%d 条断言" % len(PASSED))


if __name__ == "__main__":
    main()
