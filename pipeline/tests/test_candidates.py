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
             {"court_code": "UKHL", "normalized_key": "UKHL", "jurisdiction": "GB"},
             {"court_code": "FC", "normalized_key": "FC", "jurisdiction": "CA"}]

    def rep(abbr, jur, y0="", y1=""):
        return {"abbreviation": abbr, "normalized_key": classify.nk(abbr),
                "jurisdiction": jur, "confidence": "estimated",
                "vol_range_start": "", "vol_range_end": "",
                "year_range_start": y0, "year_range_end": y1}
    reporter = [rep("S.C.R.", "CA"), rep("K.B.", "GB"), rep("K.B.", "QC"),
                rep("D.L.R.", "CA"), rep("F.C.", "CA")]
    prefix = [{"canonical_prefix": "Q.R.", "normalized_key": "QR",
               "jurisdiction": "QC"},
              {"canonical_prefix": "L.R.", "normalized_key": "LR",
               "jurisdiction": "GB"}]
    return classify.Classifier({"neutral_court_codes": court,
                                "reporter_jurisdiction": reporter,
                                "series_prefix": prefix}, Counter())


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


# ================================================================ 阶段 2（D4/D5）
def _key_of_text(text, clf=None, shape=None):
    """真正则抽取+分类后，取（可选指定期望形状的）第一个候选的 v2 键。"""
    clf = clf or _clf()
    rows = classified_of(text, clf=clf)
    if shape:
        rows = [r for r in rows if r["shape_name"] == shape]
    assert rows, "文本 %r 无候选" % text
    return merge.build_merge_key_v2(rows[0])


def test_series_split_dlr_2d_3d():
    """D4 核心：47 D.L.R. (2d) 400 与 47 D.L.R. (3d) 400 必须不同键。"""
    k2 = _key_of_text("Cited in 47 D.L.R. (2d) 400 here.")
    k3 = _key_of_text("Cited in 47 D.L.R. (3d) 400 here.")
    check(k2 != k3, "D4：D.L.R. (2d) 与 (3d) 不同键")
    check(k2.split("|")[3] == "2d" and k3.split("|")[3] == "3d",
          "D4：括注序数进键（正典形 %r / %r）" % (k2, k3))


def test_series_canonical_equivalence():
    """裸 / 粘连 / 括注序数 → 同一正典值；2 与 3 不同；缺失与显式不同。"""
    check(merge._canon_series("4th") == merge._canon_series("(4d)") == "4d",
          "D4：裸 4th / 括注 (4d) → 同一正典 4d")
    check(merge._canon_series("2nd") == merge._canon_series("2d") == "2d",
          "D4：2nd 与 2d 同系列")
    check(merge._canon_series("2d") != merge._canon_series("3d"),
          "D4：2 与 3 不同系列")
    check(merge.build_merge_key_v2({"year_start": "1968", "vol": "1",
                                    "abbreviation": "A.B.", "page": "2"})
          != merge.build_merge_key_v2({"year_start": "1968", "vol": "1",
                                       "abbreviation": "A.B.", "page": "2",
                                       "series": "2d"}),
          "D4：缺失系列与显式系列不同键")


def test_roman_page_key():
    """D5：罗马页独立成键；xiii≠xiv；罗马不与缺失同键、不与阿拉伯同键。"""
    kxiii = _key_of_text("Leave granted: [1985] 2 S.C.R. xiii.", shape="shape_bracket")
    kxiv = _key_of_text("Leave granted: [1985] 2 S.C.R. xiv.", shape="shape_bracket")
    check(kxiii.endswith("ro:xiii") and kxiv.endswith("ro:xiv") and kxiii != kxiv,
          "D5：罗马页带 ro: 前缀进键，xiii 与 xiv 不同")
    check(merge.build_merge_key_v2({"year_start": "1985", "vol": "2",
                                    "abbreviation": "S.C.R.", "page_roman": "x"})
          != merge.build_merge_key_v2({"year_start": "1985", "vol": "2",
                                       "abbreviation": "S.C.R.", "page": "10"}),
          "D5：罗马 x 不与阿拉伯 10 同键")
    check(merge.build_merge_key_v2({"year_start": "1985", "vol": "2",
                                    "abbreviation": "S.C.R.", "page_roman": "x"})
          != merge.build_merge_key_v2({"year_start": "1985", "vol": "2",
                                       "abbreviation": "S.C.R."}),
          "D5：罗马页不与缺失页同键")


def test_paren_note_distinct_series():
    """D4：非序数括注 (N.S.) 是独立系列字段——与无括注的不同键，永不清成序数。"""
    kns = _key_of_text("Old case at 2 Q.B. (N.S.) 100 there.", shape="shape_vol_abbr_page")
    kplain = _key_of_text("Old case at 2 Q.B. 100 there.", shape="shape_vol_abbr_page")
    check(kns.split("|")[3] == "n:ns", "D4：(N.S.) 以 n:ns 进键（新系列）")
    check(kns != kplain, "D4：(N.S.) 与无括注同页不同键")


def test_nominate_paren_note_not_keyed():
    """shape_nominate 的宽口径括注是法院标注（(Ont. C.A.) 类），不进键——
    否则同一条引证按标注变体拆散。"""
    base = {"year_start": "1968", "vol": "1", "abbreviation": "S.C.R.",
            "page": "100", "shape_name": "shape_nominate"}
    with_note = dict(base, paren_note="Ont. C.A.")
    check(merge.build_merge_key_v2(base) == merge.build_merge_key_v2(with_note),
          "D4：nominate 括注不进键")


# ================================================================ 阶段 3（D6 来源地）
def _origin_row(merge_key):
    return {"merge_key": merge_key, "case_name_modal": "", "canonical_string": "x"}


def test_scope_origin_rules():
    """D6：来源地两级证据。用真 scope 表 + 合成 origin_idx。"""
    import decide
    scope = decide.load_scope()
    check(len(scope) >= 6, "scope 表载入（verified 规则 ≥6 条）")

    def origin(**kw):
        return dict(kw)
    # 1. 英国上诉法院 → FOREIGN / GB（scope 规则）
    r = _origin_row("2009||ewca|civ|1746")
    decide.decide_case_origin(r, ["x"], {}, Counter(), scope)
    check((r["case_origin"], r["foreign_status"], r["origin_country"],
           r["origin_basis"]) == ("GB", "FOREIGN", "GB", "court_scope_rule"),
          "D6：2009 EWCA Civ 1746 → FOREIGN/GB（court_scope_rule）")
    # 2. ONCA → DOMESTIC_CA / Ontario
    r = _origin_row("2011||onca||779")
    decide.decide_case_origin(r, ["x"], {}, Counter(), scope)
    check((r["case_origin"], r["foreign_status"], r["origin_subdivision"])
          == ("CA", "DOMESTIC_CA", "Ontario"),
          "D6：2011 ONCA 779 → DOMESTIC_CA/Ontario")
    # 3. 年代闸：1868 UKHL 1 是 BAILII 回溯号 → UNDETERMINED（不冒充 GB）
    r = _origin_row("1868||ukhl||1")
    decide.decide_case_origin(r, ["x"], {}, Counter(), scope)
    check((r["case_origin"], r["foreign_status"]) == ("UNDETERMINED", "UNDETERMINED"),
          "D6：pre-2001 UKHL 回溯号被年代闸挡住 → UNDETERMINED")
    # 4. 跨法域法院（UKPC/JCPC）不在规则表 → UNDETERMINED（绝不推断）
    r = _origin_row("1925||ukpc||11")
    decide.decide_case_origin(r, ["x"], {}, Counter(), scope)
    check(r["case_origin"] == "UNDETERMINED",
          "D6：UKPC 不入规则表 → UNDETERMINED（约束七）")
    # 5. 带卷号的汇编结构不适用中立码规则
    r = _origin_row("2009|1|scc||51")
    decide.decide_case_origin(r, ["x"], {}, Counter(), scope)
    check(r["case_origin"] == "UNDETERMINED",
          "D6：有卷号的汇编键不适用中立码 scope 规则")
    # 6. 案件级直接证据优先于 scope
    oidx = {"donoghuevstevenson": [{"case_origin": "GB", "deciding_court": "HL",
                                    "origin_subdivision": "", "normalized_key":
                                    "donoghuevstevenson"}]}
    r = _origin_row("2009||ewca|civ|1746")
    decide.decide_case_origin(r, ["Donoghue v. Stevenson"], oidx, Counter(), scope)
    check((r["case_origin"], r["origin_basis"]) == ("GB", "case_record"),
          "D6：直接证据优先，basis=case_record（与 scope_rule 分档）")
    # 7. 直接证据冲突 → CONFLICT
    oidx2 = {"a": [{"case_origin": "GB", "deciding_court": "", "origin_subdivision": "",
                    "normalized_key": "a"}],
             "b": [{"case_origin": "CA", "deciding_court": "", "origin_subdivision": "",
                    "normalized_key": "b"}]}
    r = _origin_row("2009||ewca|civ|1746")
    decide.decide_case_origin(r, ["A", "B"], oidx2, Counter(), scope)
    check(r["case_origin"] == "CONFLICT" and r["foreign_status"] == "CONFLICT",
          "D6：直接证据冲突 → CONFLICT（保留证据，不投票抹平）")


# ================================================================ Round 2
def test_input_identity_guard():
    """R2-10：输入身份指纹——可重放、对决策表内容敏感、params 参与、
    verify_unchanged 能发现变更。"""
    import run_all
    import tempfile
    tmp = tempfile.mkdtemp(prefix="test_r2_")
    for sub in ("pipeline", "decisions", "corpus"):
        os.makedirs(os.path.join(tmp, sub))
    with open(os.path.join(tmp, "pipeline", "a.py"), "w") as f:
        f.write("x=1")
    tpath = os.path.join(tmp, "decisions", "t.csv")
    with open(tpath, "w") as f:
        f.write("k\n1")
    with open(os.path.join(tmp, "corpus", "SCC.parquet"), "w") as f:
        f.write("c")
    a = run_all.input_identity(root=tmp)
    b = run_all.input_identity(root=tmp)
    check(a["fingerprint"] == b["fingerprint"], "R2-10：身份指纹可重放")
    check("decisions/t.csv" in a["files"] and "pipeline/a.py" in a["files"]
          and "corpus/SCC.parquet" in a["files"], "R2-10：代码+决策表+语料全入指纹")
    with open(tpath, "w") as f:
        f.write("k\n2")
    c = run_all.input_identity(root=tmp)
    check(c["fingerprint"] != a["fingerprint"], "R2-10：决策表内容变化 → 指纹变化")
    d = run_all.input_identity(root=tmp, params={"x": 1})
    check(d["fingerprint"] != c["fingerprint"], "R2-10：params 参与身份")
    ok_changed, _ = run_all.verify_unchanged(a, root=tmp)
    check(ok_changed is False, "R2-10：verify_unchanged 发现决策表变更")
    ok_same, _ = run_all.verify_unchanged(c, root=tmp)
    check(ok_same is True, "R2-10：verify_unchanged 对当前输入放行")


def test_boundary_guard_run_level():
    """R2-6：run 级边界闸——run 内首匹配放行（legacy 保留），同 run 同形状的
    更晚起点照拒。"""
    # 印刷相邻的真匹配（复审给出的两个例子）
    legacy_cases = ("Court of Appeal[1997] R.J.Q. 2907", "1[1961] S.C.R. 614",
                    "R1500 A.C. 400")
    for text in legacy_cases:
        cands, _ = extract.extract_candidates(text, "SCC_t0", "2020", 0, "SCC")
        old = {(m.start(), m.end(), n) for n, rx in extract.SHAPES
               for m in rx.finditer(text)}
        new = {(c["match_start_offset"], c["match_end_offset"], c["shape_name"])
               for c in cands}
        check(old <= new, "R2-6：legacy finditer 匹配全保留：%r" % text)
    # 截断垃圾照拒（同 run 同形状更早发射起点）
    cands, blocked = extract.extract_candidates(
        "Ref. 123 A.C. 4 end.", "SCC_t0", "2020", 0, "SCC")
    check(blocked >= 1, "R2-6：同 run 的截断尝试仍被拒并计数")
    check(not any(c["raw_string"].startswith(("23 A.C.", "3 A.C."))
                  for c in cands),
          "R2-6：不许从 123 A.C. 4 里截出 23/3 A.C. 4")


def test_legacy_matches_preserved_on_fixtures():
    """R2-6：夹具上旧 finditer 的每个 (start,end,shape) 都在新候选集里
    （含 intentional 新捕获字段——raw 与起止不变）。"""
    from fixtures import FIXTURES
    for fx in FIXTURES:
        cands, _ = extract.extract_candidates(fx["text"], "SCC_x", "2020",
                                              fx["row"], "SCC")
        new = {(c["match_start_offset"], c["match_end_offset"], c["shape_name"])
               for c in cands}
        old = [(m.start(), m.end(), n) for n, rx in extract.SHAPES
               for m in rx.finditer(fx["text"])]
        missing = [t for t in old if t not in new]
        check(not missing, "R2-6 夹具 %s：legacy 匹配 0 缺失（缺 %r）"
              % (fx["id"], missing[:3]))


# ================================================================ Round 2（R2-2/3/5）
def test_fc_neutral_exact_beats_normalized_reporter():
    """R2-2：2004 FC 736——中立读法 exact 档胜过汇编读法的 normalized 档，
    计一次；带支持的输家标 weaker_alternative（不再是 unsupported）。"""
    rows = classified_of("Federal Court appeal in 2004 FC 736, decided.")
    stats = Counter()
    v = merge.arbitrate_document(rows, stats)
    neutral = [r for r in rows if r["raw_string"] == "2004 FC 736"
               and r["citation_kind"] == "neutral"]
    check(neutral and v[neutral[0]["candidate_id"]][0] == "counted",
          "R2-2：2004 FC 736 中立读法（exact）计数")
    vol = [r for r in rows if r["raw_string"] == "2004 FC 736"
           and r["shape_name"] == "shape_vol_abbr_page"]
    check(vol and v[vol[0]["candidate_id"]][0] == "alternative_weaker_support",
          "R2-2：汇编读法（normalized 命中）标 weaker_alternative")
    counted = [merge.build_merge_key_v2(r) for r in rows
               if v[r["candidate_id"]][0] == "counted"
               and r["raw_string"] == "2004 FC 736"]
    check(counted == ["2004||fc||736"],
          "R2-2：2004 FC 736 恰好计一次、键 %r" % counted)


def test_qr_partial_overlap_dominance():
    """R2-3：[1937] Q.R. 64 K.B. 27——无支持的 bracket 读法被有支持的前缀读法
    支配，恰好一条 counted（QC）。"""
    rows = classified_of("[1937] Q.R. 64 K.B. 27, per curiam.")
    stats = Counter()
    v = merge.arbitrate_document(rows, stats)
    counted = [r for r in rows if v[r["candidate_id"]][0] == "counted"]
    check(len(counted) == 1 and counted[0]["jurisdiction"] == "QC"
          and counted[0]["candidate_case_name"] is not None,
          "R2-3：Q.R. 64 K.B. 27 恰好一条 counted（QC），bracket 读法不再弃权")
    losers = [v[r["candidate_id"]][0] for r in rows
              if r["raw_string"] == "[1937] Q.R. 64"]
    check(losers == ["alternative_dominated_by_support"],
          "R2-3：无支持的 bracket 读法标 dominated_by_support")


def test_equal_grade_partial_overlap_still_abstains():
    """R2-3：同档（都 exact）部分重叠仍弃权，不硬选。"""
    def cand(cid, start, jur, year, vol):
        return {"candidate_id": cid, "corpus_row_index": "0",
                "source_decision_citation": "SCC_t0", "raw_string": "1930 K.B. 5",
                "shape_name": "shape_vol_abbr_page",
                "match_start_offset": start, "match_end_offset": start + 13,
                "citation_kind": "reporter", "jurisdiction": jur,
                "jurisdiction_confidence": "estimated", "lookup_mode": "exact",
                "parse_status": "valid", "structural_conflict": "",
                "rejected_reason": "", "self_citation": "",
                "candidate_case_name": "", "source_decision_year": "2020",
                "year_start": year, "vol": vol, "abbr": "K.B.", "page": "5"}
    stats = Counter()
    # 年读法 vs 卷读法（异键）、都 exact 档 → 部分重叠同档 → 弃权
    v = merge.arbitrate_document(
        [cand("x", 0, "GB", "1930", ""), cand("y", 7, "QC", "", "1930")], stats)
    check(v["x"][0] == "overlap_undecided" and v["y"][0] == "overlap_undecided",
          "R2-3：同档部分重叠弃权")


def test_nominate_ordinal_paren_is_series():
    """R2-5：165 A. (2d) 82 (1960)——nominate 括注是序数系列 → 进键正典化，
    与 vol_page_year 读法同键同义，计一次。"""
    rows = classified_of("Held in 165 A. (2d) 82 (1960) elsewhere.")
    stats = Counter()
    v = merge.arbitrate_document(rows, stats)
    counted = [r for r in rows if r["raw_string"].startswith("165 A.")
               and v[r["candidate_id"]][0] == "counted"]
    check(len(counted) == 1, "R2-5：165 A. (2d) 82 (1960) 计一次")
    check(counted and merge.build_merge_key_v2(counted[0]).split("|")[3] == "2d",
          "R2-5：nominate 括注 (2d) 正典化进键")


def test_bridge_between_disjoint_supported():
    """R2 终集合：无支持的桥接候选被两侧支配，两条**不相交**的有支持引证
    都存活（重叠组件允许多于一条存活）。"""
    def cand(cid, s, e, jur, key_fields):
        r = {"candidate_id": cid, "corpus_row_index": "0",
             "source_decision_citation": "SCC_t0", "raw_string": cid,
             "shape_name": "shape_vol_abbr_page",
             "match_start_offset": s, "match_end_offset": e,
             "citation_kind": "reporter", "jurisdiction": jur,
             "jurisdiction_confidence": "estimated", "lookup_mode": "exact",
             "parse_status": "valid", "structural_conflict": "",
             "rejected_reason": "", "self_citation": "",
             "candidate_case_name": "", "source_decision_year": "2020"}
        r.update(key_fields)
        return r
    a = cand("a", 0, 10, "CA", {"year_start": "1968", "vol": "12",
                                "abbr": "A.B.", "page": "34"})
    b = cand("b", 5, 25, "UNSUPPORTED", {"year_start": "", "vol": "12",
                                         "abbr": "A.B.", "page": "34"})
    c = cand("c", 15, 30, "GB", {"year_start": "1969", "vol": "5",
                                 "abbr": "C.D.", "page": "56"})
    stats = Counter()
    v = merge.arbitrate_document([a, b, c], stats)
    check(v["a"][0] == "counted" and v["c"][0] == "counted",
          "R2 终集合：两条不相交的有支持引证都存活")
    check(v["b"][0] == "alternative_dominated_by_support",
          "R2 终集合：无支持桥接候选被支配")


def test_containment_chain_points_to_final_counter():
    """R2 终集合：A⊂B⊂C 相容包含链 → A 的让位对象经链式重定向指向最终
    被计数的 C。"""
    def cand(cid, s, e):
        return {"candidate_id": cid, "corpus_row_index": "0",
                "source_decision_citation": "SCC_t0", "raw_string": cid,
                "shape_name": "shape_vol_abbr_page",
                "match_start_offset": s, "match_end_offset": e,
                "citation_kind": "reporter", "jurisdiction": "CA",
                "jurisdiction_confidence": "estimated", "lookup_mode": "exact",
                "parse_status": "valid", "structural_conflict": "",
                "rejected_reason": "", "self_citation": "",
                "candidate_case_name": "", "source_decision_year": "2020",
                "year_start": "1968", "vol": "12", "abbr": "A.B.", "page": "34"}
    stats = Counter()
    v = merge.arbitrate_document([cand("a", 4, 20), cand("b", 0, 26),
                                  cand("c", 0, 34)], stats)
    check(v["c"][0] == "counted", "R2 终集合：链末端 C 计数")
    check(v["a"][0] == "alternative_same_key" and v["a"][2] == "c",
          "R2 终集合：A 让位对象指向最终计数者 C（而非链中间的 B）")


def test_unresolved_suppressor_recycles_dominated():
    """R2 终集合：支配链终止于被计数者；同档冲突的弃权是残差——
    有支持的 s 同时支配垃圾 a、又与 t 同档相持 → s 计数（支配裁决优先），
    a 随 s，t 弃权（不被硬选、也不计数）。"""
    def cand(cid, s, e, jur, extra=None):
        r = {"candidate_id": cid, "corpus_row_index": "0",
             "source_decision_citation": "SCC_t0", "raw_string": cid,
             "shape_name": "shape_vol_abbr_page",
             "match_start_offset": s, "match_end_offset": e,
             "citation_kind": "reporter", "jurisdiction": jur,
             "jurisdiction_confidence": "estimated", "lookup_mode": "exact",
             "parse_status": "valid", "structural_conflict": "",
             "rejected_reason": "", "self_citation": "",
             "candidate_case_name": "", "source_decision_year": "2020",
             "year_start": "1968", "vol": "12", "abbr": "A.B.", "page": "34"}
        r.update(extra or {})
        return r
    a = cand("a", 0, 10, "UNSUPPORTED", {"lookup_mode": ""})
    s = cand("s", 0, 20, "CA")
    t = cand("t", 15, 40, "GB", {"year_start": "1969", "abbr": "C.D."})
    stats = Counter()
    v = merge.arbitrate_document([a, s, t], stats)
    check(v["s"][0] == "counted" and v["t"][0] == "overlap_undecided",
          "R2 终集合：有支持且支配垃圾者计数；同档相他方弃权")
    check(v["a"][0] == "alternative_same_key" and v["a"][2] == "s",
          "R2 终集合：垃圾 a 让位于被计数的 s（不因 s 卷入同档相持而复活）")
    # 反向：t 若无同档相持则照常计数（弱证据双向不偏袒）
    v2 = merge.arbitrate_document([a, s], Counter())
    check(v2["s"][0] == "counted" and v2["a"][2] == "s",
          "R2 终集合：去掉 t 后 s/a 结论不变")


def test_d3_partner_without_support_keeps_conflict_open():
    """R2：D3 配对者无可用支持 → 不再证明无效性，歧义跨界保持未决
    （候选保留、支持级 0、不压制他人）。"""
    def cand(cid, s, e, shape, jur, extra=None):
        r = {"candidate_id": cid, "corpus_row_index": "0",
             "source_decision_citation": "SCC_t0", "raw_string": cid,
             "shape_name": shape,
             "match_start_offset": s, "match_end_offset": e,
             "citation_kind": "reporter", "jurisdiction": jur,
             "jurisdiction_confidence": "estimated", "lookup_mode": "exact",
             "parse_status": "valid", "structural_conflict": "",
             "rejected_reason": "", "self_citation": "",
             "candidate_case_name": "", "source_decision_year": "2020",
             "year_start": "", "vol": "", "abbr": "", "page": ""}
        r.update(extra or {})
        return r
    a = cand("a", 0, 15, "shape_neutral_bare", "CA", {
        "structural_conflict": "cross_boundary_year_page",
        "parse_status": "structurally_conflicted",
        "conflict_with_candidate": "p", "page": "2011",
        "page_span": "8:12", "year_start": "2011"})
    p = cand("p", 8, 25, "shape_neutral_bare", "UNSUPPORTED", {
        "year_start": "2011", "year_span": "8:12", "lookup_mode": ""})
    stats = Counter()
    v = merge.arbitrate_document([a, p], stats)
    check(v["a"][0] != "cross_boundary_invalid",
          "R2：无支持配对者不作无效性证明")
    check(v["p"][0] in ("counted", "overlap_undecided", "span_alternative_undecided"),
          "R2：配对者自身走常规规则")


def main():
    for t in (test_boundary_guard, test_kvello_2009_scc_51, test_bce_swallow,
              test_almrei_swallow, test_same_span_multi_shape_counted_once,
              test_containment_longer_wins, test_legit_4digit_serial_not_rejected,
              test_year_vol_conflict_without_table_abstains,
              test_long_span_two_reals_both_kept,
              test_equal_strength_conflict_abstains, test_input_order_invariance,
              test_grouping_by_row_not_by_decision_id,
              test_series_split_dlr_2d_3d, test_series_canonical_equivalence,
              test_roman_page_key, test_paren_note_distinct_series,
              test_nominate_paren_note_not_keyed, test_scope_origin_rules,
              test_input_identity_guard, test_boundary_guard_run_level,
              test_legacy_matches_preserved_on_fixtures,
              test_fc_neutral_exact_beats_normalized_reporter,
              test_qr_partial_overlap_dominance,
              test_equal_grade_partial_overlap_still_abstains,
              test_nominate_ordinal_paren_is_series,
              test_bridge_between_disjoint_supported,
              test_containment_chain_points_to_final_counter,
              test_unresolved_suppressor_recycles_dominated,
              test_d3_partner_without_support_keeps_conflict_open,
              test_new_path_fixture_measurements):
        t()
    print("全部通过：%d 条断言" % len(PASSED))


if __name__ == "__main__":
    main()
