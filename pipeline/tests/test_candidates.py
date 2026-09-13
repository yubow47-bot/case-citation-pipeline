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
import csv
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
def _origin_row(merge_key, kind="neutral"):
    return {"merge_key": merge_key, "case_name_modal": "", "canonical_string": "x",
            "citation_kind": kind}


def test_scope_origin_rules():
    """D6（R2-4 收紧后）：来源地两级证据。真 scope 表 + 合成 origin_idx。
    scope 只适用于**已被接受的 neutral 解析**（citation_kind=neutral）；
    年代闸用**标识符适用期**（SCC 2000 / ONCA 2007 / UK 系 2001）。"""
    import decide
    scope = decide.load_scope()
    check(len(scope) >= 9, "scope 表载入（verified 规则 ≥9 条，含分辑行）")

    def origin(**kw):
        return dict(kw)
    # 1. 英国上诉法院民事分辑（印刷形 EWCA Civ，语料实测键 ewcaciv）→ FOREIGN/GB
    r = _origin_row("2002||ewcaciv||1096")
    decide.decide_case_origin(r, ["x"], {}, Counter(), scope)
    check((r["member_origin_country"], r["member_origin_status"],
           r["member_origin_basis"]) == ("GB", "DETERMINED", "court_scope_rule"),
          "R2-4：EWCA Civ 分辑行 → FOREIGN/GB（court_scope_rule）")
    # 1b. 非 neutral 解析（reporter/UNSUPPORTED）不适用 scope 规则
    r = _origin_row("2009||ewca|civ|1746", kind="reporter")
    decide.decide_case_origin(r, ["x"], {}, Counter(), scope)
    check(r["member_origin_status"] == "UNDETERMINED",
          "R2-4：未接受为 neutral 解析的键不适用 scope（年头+空卷不证明引证种类）")
    # 2. ONCA → DOMESTIC_CA / Ontario
    r = _origin_row("2011||onca||779")
    decide.decide_case_origin(r, ["x"], {}, Counter(), scope)
    check((r["member_origin_country"], r["member_origin_status"],
           r["origin_subdivision"]) == ("CA", "DETERMINED", "Ontario"),
          "D6：2011 ONCA 779 → DOMESTIC_CA/Ontario")
    # 2b. 标识符适用期：ONCA 中立引用 2007 年 1 月起 → 2005 年的键不适用
    r = _origin_row("2005||onca||1")
    decide.decide_case_origin(r, ["x"], {}, Counter(), scope)
    check(r["member_origin_status"] == "UNDETERMINED",
          "R2-4：pre-2007 的 ONCA 键被标识符年代闸挡住 → UNDETERMINED")
    # 3. 年代闸：1868 UKHL 1 是 BAILII 回溯号 → UNDETERMINED（不冒充 GB）
    r = _origin_row("1868||ukhl||1")
    decide.decide_case_origin(r, ["x"], {}, Counter(), scope)
    check(r["member_origin_status"] == "UNDETERMINED",
          "D6：pre-2001 UKHL 回溯号被年代闸挡住 → UNDETERMINED")
    # 4. 跨法域法院（UKPC/JCPC）不在规则表 → UNDETERMINED（绝不推断）
    r = _origin_row("1925||ukpc||11")
    decide.decide_case_origin(r, ["x"], {}, Counter(), scope)
    check(r["member_origin_status"] == "UNDETERMINED",
          "D6：UKPC 不入规则表 → UNDETERMINED（约束七）")
    # 5. 带卷号的汇编结构不适用中立码规则
    r = _origin_row("2009|1|scc||51")
    decide.decide_case_origin(r, ["x"], {}, Counter(), scope)
    check(r["member_origin_status"] == "UNDETERMINED",
          "D6：有卷号的汇编键不适用中立码 scope 规则")
    # 6. 案件级直接证据优先于 scope
    oidx = {"donoghuevstevenson": [{"case_origin": "GB", "deciding_court": "HL",
                                    "origin_subdivision": "", "normalized_key":
                                    "donoghuevstevenson"}]}
    r = _origin_row("2002||ewcaciv||1096")
    decide.decide_case_origin(r, ["Donoghue v. Stevenson"], oidx, Counter(), scope)
    check((r["member_origin_country"], r["member_origin_basis"]) ==
          ("GB", "case_record"),
          "D6：直接证据优先，basis=case_record（与 scope_rule 分档）")
    # 7. 直接证据冲突 → 成员本地 CONFLICT（保留全部证据 id）
    oidx2 = {"a": [{"case_origin": "GB", "deciding_court": "", "origin_subdivision": "",
                    "normalized_key": "a"}],
             "b": [{"case_origin": "CA", "deciding_court": "", "origin_subdivision": "",
                    "normalized_key": "b"}]}
    r = _origin_row("2002||ewcaciv||1096")
    decide.decide_case_origin(r, ["A", "B"], oidx2, Counter(), scope)
    check(r["member_origin_status"] == "CONFLICT"
          and r["member_origin_conflict_detail"] == "CA;GB"
          and r["member_origin_evidence_ids"] == "case_origin:a|case_origin:b",
          "D6：直接证据冲突 → 成员本地 CONFLICT（全部证据 id 保留）")


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
    """【R2 闭环反例 F——本轮唯一预授权修改旧期望的测试】

    修改前（R2 中期口径）断言：s 与 t 同档相持时，s 因另支配垃圾 a 仍 counted、
    a 以 alternative_same_key 指向 s、t overlap_undecided。
    修改理由：grounded 终态语义（本轮任务二）下，s 的同档冲突未决时 s 不得
    counted——「压制者本身未决」的 a 也必须保持未决，否则中间胜负关系会漏成
    最终计数。旧行为把 s 的另一条支配裁决当成了打破同档相持的证据，那是
    多前提拆单边的错误。

    新断言：
      第一段（s 与 t 同档相持）：s、t、a 都不得 counted；a 为
      overlap_undecided，备注写明压制者本身未决。
      第二段（移除 t，保留原语义）：s 无攻击者 → counted；a 指向 s。
    """
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
    check(v["s"][0] != "counted" and v["t"][0] != "counted"
          and v["a"][0] != "counted",
          "闭环反例F：同档相持的 s/t 与其受压者 a 都不得 counted")
    check(v["a"][0] == "overlap_undecided" and "未决" in v["a"][1],
          "闭环反例F：a 为 overlap_undecided，备注压制者本身未决（%r）" % (v["a"][1],))
    check(v["s"][0] == "overlap_undecided" and v["t"][0] == "overlap_undecided",
          "闭环反例F：s/t 纯同档环保持 UNDEC（不用形状顺序破环）")
    # 第二段（保留原语义）：移除 t → s counted，a 指向 s
    v2 = merge.arbitrate_document([a, s], Counter())
    check(v2["s"][0] == "counted" and v2["a"][0] == "alternative_same_key"
          and v2["a"][2] == "s",
          "闭环反例F：移除 t 后 s counted、a 指向 s（隔离无攻击者即 IN）")


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


# ============================================================ R2 闭环（身份授权）
def test_bilingual_explicit_table_only():
    """R2 闭环反例 1-3：只有显式已核实双语表授权 bilingual。
    1) 任意假代码不得 bilingual；2) SCC/CSC（本地有同案双语证据）仍 bilingual；
    3) ABQB/ABKB（改名代码）不得 bilingual。"""
    import decide
    pairs = decide.load_bilingual()
    check(("scc", "csc") in pairs or frozenset(("scc", "csc")) in pairs,
          "闭环：SCC/CSC 在已核实双语对中（本地证据：2014 CSC 7 = 2014 SCC 7）")
    check(decide.same_decision_kind("2001||abc||1", "CA", 1,
                                    "2001||xyz||1", "CA", 1) is None,
          "闭环：假代码 abc/xyz 不得 bilingual")
    check(decide.same_decision_kind("2014||scc||7", "CA", 5,
                                    "2014||csc||7", "CA", 3) == "bilingual",
          "闭环：SCC/CSC 同年同号仍 bilingual")
    check(decide.same_decision_kind("2017||abqb||812", "AB", 1,
                                    "2017||abkb||812", "AB", 1) is None,
          "闭环：ABQB/ABKB（改名/时代转换）不得 bilingual")
    check(not any("abqb" in p for p in pairs),
          "闭环：改名代码不进已核实双语对")


def _brow(rid, merge_key, basis, status="UNDETERMINED", country="", evid="",
          mbasis="", gid="XC-B1", court="SCC"):
    return {"row_key": rid, "merge_key": merge_key, "merged_group_id": gid,
            "identity_basis": basis, "member_origin_status": status,
            "member_origin_country": country, "member_origin_evidence_ids": evid,
            "member_origin_basis": mbasis, "member_origin_conflict_detail": "",
            "member_origin_subdivision": "", "case_name_modal": "X v. Y",
            "citation_kind": "neutral",
            "distinct_decisions_count": "3", "court": court,
            "group_foreign_status": "", "group_origin_country": "",
            "group_origin_status": "", "group_origin_basis": "",
            "group_origin_evidence_ids": "", "noncore_origin_evidence": "",
            "foreign_status": "", "origin_country": "", "case_origin": "",
            "origin_basis": "", "origin_evidence_id": "", "deciding_court": ""}


def test_same_citation_requires_single_key_group():
    """R2 闭环反例 4：锚 K1 + 弱键 K2×2（两法院、案名/共引加入）——
    K2 不得标 same_citation；弱连接的外国证据不得把组判成 FOREIGN。"""
    import decide
    k1 = _brow("SCC|2009||ukhl||18", "2009||ukhl||18", "anchor")
    k2a = _brow("SCC|2009|3|aller||945", "2009|3|aller||945", "", court="SCC")
    k2b = _brow("ONCA|2009|3|aller||945", "2009|3|aller||945", "", court="ONCA")
    # 弱成员是汇编引证（生产里两个 neutral 键会被 split_by_decision 拆开，
    # 不会同组）——本测试钉的是「非锚成员重复出现 ≠ same_citation」
    for r in (k2a, k2b):
        r["citation_kind"] = "reporter"
    members = [k1, k2a, k2b]
    did_idx = {}
    basis = decide.assign_identity_basis(members, did_idx, None, "")
    check(basis["SCC|2009|3|aller||945"] != "same_citation"
          and basis["ONCA|2009|3|aller||945"] != "same_citation",
          "闭环：重复出现的弱键不因 keycount>1 升级 same_citation")
    # K2 弱成员带外国证据 → 组仍不得 FOREIGN（无合格成员证据）
    for r, ctry in ((k2a, "GB"), (k2b, "GB")):
        r["member_origin_status"] = "DETERMINED"
        r["member_origin_country"] = ctry
        r["member_origin_evidence_ids"] = "scope:FAKE"
        r["member_origin_basis"] = "court_scope_rule"
    # K1 无证据；K2 的身份连接由 assign_identity_basis 决定（非锚）
    basis = decide.assign_identity_basis(members, did_idx, None, "")
    for r in members:
        r["identity_basis"] = basis[r["row_key"]]
    decide.aggregate_group_origin(members, Counter())
    check(k1["group_foreign_status"] == "UNDETERMINED",
          "闭环：仅弱连接成员带证据 → 组 UNDETERMINED（弱连接不得传播 FOREIGN）")
    check("name_year:GB:scope:FAKE" in (k1["noncore_origin_evidence"] or ""),
          "闭环：弱成员证据进 noncore 审计列（basis:国别:证据id）")


def test_same_citation_single_key_group():
    """R2 闭环反例 5：全组只有一个 merge_key（K2×2，两法院同印刷串）→
    same_citation 合格，证据可传播。"""
    import decide
    a = _brow("SCC|2009|3|aller||945", "2009|3|aller||945", "", court="SCC",
              status="DETERMINED", country="GB", evid="scope:X",
              mbasis="court_scope_rule")
    b = _brow("ONCA|2009|3|aller||945", "2009|3|aller||945", "", court="ONCA")
    # 单键组的键本身不是中立锚（汇编串）——若它是锚会先标 anchor（同样合格）
    for r in (a, b):
        r["citation_kind"] = "reporter"
    members = [a, b]
    basis = decide.assign_identity_basis(members, {}, None, "")
    check(basis["SCC|2009|3|aller||945"] == "same_citation"
          and basis["ONCA|2009|3|aller||945"] == "same_citation",
          "闭环：单键组（同印刷串跨法院）→ same_citation")
    for r in members:
        r["identity_basis"] = basis[r["row_key"]]
    decide.aggregate_group_origin(members, Counter())
    check(a["group_foreign_status"] == "FOREIGN",
          "闭环：单键组 same_citation 证据可传播")


def test_typo_variant_twice_stays_variant():
    """R2 闭环反例 6：出现两次的 typo 变体键标 anchor_variant_typo_*，
    不得 same_citation、不得传播。"""
    import decide
    k1 = _brow("SCC|2002||scc||33", "2002||scc||33", "anchor")
    t1 = _brow("SCC|2002||scc||3", "2002||scc||3", "", court="SCC",
               status="DETERMINED", country="GB", evid="scope:FAKE",
               mbasis="court_scope_rule")
    t2 = _brow("ONCA|2002||scc||3", "2002||scc||3", "", court="ONCA")
    members = [k1, t1, t2]
    # 锚键（33）在生产里被更多判决引用（dd 更大）→ 它是 root，3 是变体
    did_idx = {"SCC|2002||scc||3": set(), "ONCA|2002||scc||3": set(),
               "SCC|2002||scc||33": {"d1", "d2", "d3", "d4"}}
    basis = decide.assign_identity_basis(members, did_idx, None, "")
    check(basis["SCC|2002||scc||3"].startswith("anchor_variant_typo")
          and basis["ONCA|2002||scc||3"].startswith("anchor_variant_typo"),
          "闭环：typo 变体重复出现仍标 anchor_variant_typo_*（得到 %r/%r）"
          % (basis["SCC|2002||scc||3"], basis["ONCA|2002||scc||3"]))
    check(not any(b == "same_citation" for b in basis.values()),
          "闭环：typo 变体不得 same_citation")
    for r in members:
        r["identity_basis"] = basis[r["row_key"]]
    decide.aggregate_group_origin(members, Counter())
    check(k1["group_foreign_status"] == "UNDETERMINED",
          "闭环：typo 变体的外国证据不得传播")


def test_eligible_bases_shared_between_decide_and_edges():
    """R2 闭环 4.4：edges 与 decide 使用同一合格基础集合。"""
    import decide
    import edges
    check(edges.ELIGIBLE_BASES is decide.ELIGIBLE_BASES
          or edges.ELIGIBLE_BASES == decide.ELIGIBLE_BASES,
          "闭环：edges.ELIGIBLE_BASES 与 decide.ELIGIBLE_BASES 为同一集合")



# ============================================================ R2 闭环（仲裁终态）
def _acand(cid, s, e, jur, grade="exact", key=None, extra=None):
    r = {"candidate_id": cid, "corpus_row_index": "0",
         "source_decision_citation": "SCC_t0", "raw_string": cid,
         "shape_name": "shape_vol_abbr_page",
         "match_start_offset": s, "match_end_offset": e,
         "citation_kind": "reporter", "jurisdiction": jur,
         "jurisdiction_confidence": "estimated", "lookup_mode": grade,
         "parse_status": "valid", "structural_conflict": "",
         "rejected_reason": "", "self_citation": "",
         "candidate_case_name": "", "source_decision_year": "2020",
         "year_start": "1968", "vol": "12", "abbr": "A.B.", "page": "34"}
    if key:
        r.update(key)
    r.update(extra or {})
    return r


def test_counterexample_a_win_weak_cannot_break_equal_tie():
    """闭环反例 A：A、B 部分重叠异键均 exact（互相冲突）；各自包含一个弱候选。
    期望：A、B、两条弱候选都不得 counted；非 undecided 的 loser 只能指向 counted。"""
    A = _acand("A", 0, 20, "CA")
    B = _acand("B", 12, 32, "GB", key={"abbr": "C.D.", "year_start": "1969"})
    a1 = _acand("a1", 2, 10, "UNSUPPORTED", grade="", key={"page": "30"})
    b1 = _acand("b1", 14, 22, "UNSUPPORTED", grade="", key={"page": "30"})
    stats = Counter()
    v = merge.arbitrate_document([A, B, a1, b1], stats)
    counted = [c for c, vv in v.items() if vv[0] == "counted"]
    check(not counted, "闭环A：无任何 counted（%r）" % counted)
    for c in ("A", "B"):
        check(v[c][0] == "overlap_undecided",
              "闭环A：%s 为 overlap_undecided（%r）" % (c, v[c][0]))
    for c in ("a1", "b1"):
        check(v[c][0] == "overlap_undecided" and "未决" in v[c][1],
              "闭环A：弱候选 %s 因压制者未决而 undecided（%r %r）" % (c, v[c][0], v[c][1]))


def test_counterexample_b_no_cross_redirect():
    """闭环反例 B：A exact → B normalized → C unsupported；A 与 C 不重叠。
    期望：A counted；B 被 A 支配；C counted（孤立无支持可计数——既有口径）；
    C 不得指向 A。"""
    A = _acand("A", 0, 15, "CA")
    B = _acand("B", 3, 18, "CA", grade="")          # normalized 档
    C = _acand("C", 40, 55, "CA", key={"abbr": "C.D.", "year_start": "1969"})
    # C 与 A/B 都不重叠；B 攻击 C 的关系来自旧代码的支配规则——本反例里
    # B 与 C 重叠才构成链；把 B 放到与 C 重叠但与 A 也重叠的位置
    B2 = _acand("B", 3, 45, "CA", grade="")         # B 跨搭 A 与 C
    stats = Counter()
    v = merge.arbitrate_document([A, B2, C], stats)
    check(v["A"][0] == "counted", "闭环B：A counted")
    check(v["B"][0] in ("alternative_dominated_by_support",
                        "alternative_weaker_support"),
          "闭环B：B 被 A 支配（%r）" % v["B"][0])
    check(v["C"][0] == "counted",
          "闭环B：C counted（压制者 B 最终 OUT，弱候选按既有口径回收）")
    check(v["C"][2] != "A",
          "闭环B：C 不得被重定向到与它不重叠的 A（%r）" % (v["C"][2],))


def test_counterexample_c_d3_partner_unresolved():
    """闭环反例 C：D 被判跨界解析；其配对者 P 与 Q 同跨度异键同档相持。
    期望：P、Q 未决；D 不得 cross_boundary_invalid，应为 overlap_undecided
    且备注指出跨界配对者未决。"""
    D = _acand("D", 0, 15, "CA", extra={
        "structural_conflict": "cross_boundary_year_page",
        "conflict_with_candidate": "P", "page": "2011",
        "page_span": "8:12", "year_start": "2011"})
    P = _acand("P", 8, 25, "CA", key={"abbr": "P.Q.", "year_start": "2011"})
    Q = _acand("Q", 8, 25, "GB", key={"abbr": "Q.R.", "year_start": "2011"})
    # P 与 D 同键（配对者通常与 D 同码同号）——把 P/Q 设成同跨度异键相持
    stats = Counter()
    v = merge.arbitrate_document([D, P, Q], stats)
    check(v["P"][0] != "counted" and v["Q"][0] != "counted",
          "闭环C：P/Q 同档相持未决")
    check(v["D"][0] == "overlap_undecided",
          "闭环C：D 不得 cross_boundary_invalid（%r）" % v["D"][0])
    check("配对者" in v["D"][1] or "未决" in v["D"][1],
          "闭环C：备注指出跨界配对者未决（%r）" % (v["D"][1],))


def test_counterexample_d_bstep_loser_not_pointing_to_uncounted():
    """闭环反例 D：同跨度弱读法 W 让位于代表 R；R 在跨跨度竞争中与 T 同档
    相持。期望：W 不得指向未计数的 R；W 为 undecided（或指向另一个有直接
    有效依据的 counted 攻击者）。"""
    W = _acand("W", 0, 10, "CA", grade="")
    R = _acand("R", 0, 20, "CA")
    T = _acand("T", 15, 45, "GB", key={"abbr": "C.D.", "year_start": "1969"})
    stats = Counter()
    v = merge.arbitrate_document([W, R, T], stats)
    check(v["R"][0] != "counted" and v["T"][0] != "counted",
          "闭环D：R/T 同档相持未决")
    if v["W"][0] != "overlap_undecided":
        check(v["W"][2] and v[v["W"][2]][0] == "counted"
              and v["W"][2] != "R",
              "闭环D：W 的替代对象必须是最终 counted 且非 R（%r -> %r）"
              % (v["W"][0], v["W"][2]))
    else:
        check("未决" in v["W"][1],
              "闭环D：W 因压制者未决而 undecided（%r）" % (v["W"][1],))


def test_counterexample_e_same_span_undecided_still_competes():
    """闭环反例 E：X、Y 同跨度异键同档打平；Z 与该跨度部分重叠且同档。
    期望：Z 不得因 X/Y 早期未决而直接 counted；相关节点保持 undecided。"""
    X = _acand("X", 0, 20, "CA")
    Y = _acand("Y", 0, 20, "GB", key={"abbr": "C.D.", "year_start": "1969"})
    Z = _acand("Z", 12, 40, "CA", key={"abbr": "E.F.", "year_start": "1970"})
    stats = Counter()
    v = merge.arbitrate_document([X, Y, Z], stats)
    counted = [c for c, vv in v.items() if vv[0] == "counted"]
    check(not counted, "闭环E：同档三方冲突无 counted（%r）" % counted)
    for c in ("X", "Y", "Z"):
        check(v[c][0] in ("span_alternative_undecided", "overlap_undecided"),
              "闭环E：%s undecided（%r）" % (c, v[c][0]))


def test_counterexample_g_input_order_invariance_complex():
    """闭环反例 G：三个以上复杂反例在多种输入排列下结果完全一致（按
    candidate_id 对齐）。"""
    import random
    scenarios = {
        "A_tie_with_weak": [_acand("A", 0, 20, "CA"),
                            _acand("B", 12, 32, "GB", key={"abbr": "C.D.",
                                                           "year_start": "1969"}),
                            _acand("a1", 2, 10, "UNSUPPORTED", grade="",
                                   key={"page": "30"}),
                            _acand("b1", 14, 22, "UNSUPPORTED", grade="",
                                   key={"page": "30"})],
        "chain": [_acand("A", 0, 15, "CA"),
                  _acand("B", 3, 45, "CA", grade=""),
                  _acand("C", 40, 55, "CA", key={"abbr": "C.D.",
                                                 "year_start": "1969"})],
        "mixed": [_acand("X", 0, 20, "CA"),
                  _acand("Y", 0, 20, "GB", key={"abbr": "C.D.",
                                                "year_start": "1969"}),
                  _acand("Z", 12, 40, "CA", key={"abbr": "E.F.",
                                                 "year_start": "1970"}),
                  _acand("W", 4, 16, "CA", grade="")],
    }
    for name, rows in scenarios.items():
        base = None
        for seed in range(4):
            rr = [dict(r) for r in rows]
            random.Random(seed).shuffle(rr)
            stats = Counter()
            v = merge.arbitrate_document(rr, stats)
            got = sorted((r["candidate_id"], v[r["candidate_id"]][0],
                          v[r["candidate_id"]][2]) for r in rr)
            if base is None:
                base = got
            else:
                check(got == base,
                      "闭环G：%s 排列 seed=%d 结果不变" % (name, seed))


def test_counterexample_h_same_key_duplication_invariance():
    """闭环反例 H：给一个等价类增加同跨度同键重复解析——counted 语义不变、
    外部候选状态不变，只有类内代表与 alternative_same_key 关系按预期变化。"""
    # B 用弱档（lookup_mode 空 + UNSUPPORTED → 支持档 0）：A 支配 B，A counted，
    # 这样「同键重复加入」的效果才能与 B 的状态隔离观察
    core = [_acand("A", 0, 20, "CA"),
            _acand("B", 12, 32, "UNSUPPORTED", grade="",
                   key={"abbr": "C.D.", "year_start": "1969"})]
    dup = _acand("A2", 0, 20, "CA")              # 同跨度同键同形状同档的重复解析
    dup["candidate_id"] = "A2"
    v1 = merge.arbitrate_document([dict(r) for r in core], Counter())
    v2 = merge.arbitrate_document([dict(r) for r in core] + [dict(dup)], Counter())
    check(v1["A"][0] == "counted" and v2["A"][0] == "counted",
          "闭环H：A 在两次运行中都 counted")
    check(v1["B"][0] == v2["B"][0] and v1["B"][2] == v2["B"][2],
          "闭环H：外部候选 B 的终态与替代对象不变")
    check(v2["A2"][0] == "alternative_same_key" and v2["A2"][2] == "A",
          "闭环H：新增重复解析进类、以 alternative_same_key 指向代表")



def test_d3_partner_self_citation_row():
    """R2 闭环回归（评审定位）：D3 配对者是判决头部自印中立引证
    （self_citation_row）时，仍须作为跨界证据——自引不参与计数竞争，
    但它是真实印刷引证，足以证明「页码被误读成年份」的碎片不是引证。

    失败现象（修复前）：建类前剔除了自引行，cls_of_member 查不到配对者，
    D3 记 unresolved，碎片候选 counted，366 条垃圾边进入 citation_edges。"""
    def cand(cid, s, e, raw, jur, extra=None):
        r = {"candidate_id": cid, "corpus_row_index": "0",
             "source_decision_citation": "SCC_t0", "raw_string": raw,
             "shape_name": "shape_vol_abbr_page",
             "match_start_offset": s, "match_end_offset": e,
             "citation_kind": "reporter", "jurisdiction": jur,
             "jurisdiction_confidence": "estimated", "lookup_mode": "exact",
             "parse_status": "valid", "structural_conflict": "",
             "rejected_reason": "", "self_citation": "",
             "candidate_case_name": "", "source_decision_year": "2020",
             "year_start": "", "vol": "", "abbr": "", "page": "",
             "year_span": "-1:-1", "page_span": "-1:-1"}
        r.update(extra or {})
        return r
    frag = cand("frag", 0, 25, "8377278 Canada Inc., 2019", "UNSUPPORTED", {
        "lookup_mode": "",
        "structural_conflict": "cross_boundary_year_page",
        "conflict_with_candidate": "P",
        "page": "2019", "page_span": "22:26"})
    P = cand("P", 22, 34, "2019 SCC 70", "CA", {
        "shape_name": "shape_neutral_bare",
        "self_citation": "true",
        "year_start": "2019", "year_span": "22:26"})
    stats = Counter()
    v = merge.arbitrate_document([frag, P], stats)
    check(v["P"][0] == "self_citation_row",
          "闭环回归：自引行保持 self_citation_row（不参与计数竞争）")
    check(v["frag"][0] == "cross_boundary_invalid" and v["frag"][2] == "P",
          "闭环回归：自引配对者仍是有效跨界证据，碎片 invalidated（%r %r）"
          % (v["frag"][0], v["frag"][2]))



# ============================================================ R2-1/R2-9
def _grow(rid, merge_key, basis, status="UNDETERMINED", country="", evid="",
          mbasis="", gid="XC-T1"):
    return {"row_key": rid, "merge_key": merge_key, "merged_group_id": gid,
            "identity_basis": basis, "member_origin_status": status,
            "member_origin_country": country, "member_origin_evidence_ids": evid,
            "member_origin_basis": mbasis, "member_origin_conflict_detail": "",
            "case_name_modal": "X v. Y", "distinct_decisions_count": "2",
            "group_foreign_status": "", "group_origin_country": "",
            "group_origin_status": "", "group_origin_basis": "",
            "group_origin_evidence_ids": "", "noncore_origin_evidence": "",
            "foreign_status": "", "origin_country": "", "case_origin": "",
            "origin_basis": "", "origin_evidence_id": "", "deciding_court": "",
            "court": "SCC"}


def test_group_origin_aggregation():
    """R2-1：组级来源地 = 合格成员聚合；启发式不传播；主行置换不变；
    冲突全保留；成员本地冲突升组。"""
    import decide
    # ① 锚成员定国 + 弱成员带异国证据 → 组取锚；弱证据入审计列
    a = _grow("SCC|2009||ukhl||18", "2009||ukhl||18", "anchor",
              "DETERMINED", "GB", "scope:UKHL", "court_scope_rule")
    b = _grow("SCC|2009|3|aller||945", "2009|3|aller||945", "name_year",
              "DETERMINED", "CA", "case_origin:aller", "case_record")
    a["is_primary"], b["is_primary"] = "true", "false"
    decide.aggregate_group_origin([a, b], Counter())
    check(a["group_origin_country"] == "GB" and a["group_foreign_status"] == "FOREIGN",
          "R2-1：组取合格成员（锚）的国别")
    check(b["group_origin_country"] == "GB" and b["foreign_status"] == "FOREIGN",
          "R2-1：组级结果写到每一行")
    check("name_year:CA:case_origin:aller" in b["noncore_origin_evidence"],
          "R2-1：弱成员的异国证据进 noncore 审计列（不丢也不升组）")
    # ② 主行置换不变
    a2 = _grow("SCC|2009||ukhl||18", "2009||ukhl||18", "anchor",
               "DETERMINED", "GB", "scope:UKHL", "court_scope_rule")
    b2 = _grow("SCC|2009|3|aller||945", "2009|3|aller||945", "name_year",
               "DETERMINED", "CA", "case_origin:aller", "case_record")
    a2["is_primary"], b2["is_primary"] = "false", "true"
    decide.aggregate_group_origin([b2, a2], Counter())
    check(a2["group_origin_country"] == "GB" and a2["foreign_status"] == "FOREIGN",
          "R2-1：主行置换不改组结论")
    # ③ 只有弱成员有证据 → 组 UNDETERMINED，证据进审计列
    c = _grow("SCC|1991|1|scr||742", "1991|1|scr||742", "name_year",
              "DETERMINED", "CA", "case_origin:wd", "case_record")
    d = _grow("SCC|1991|63|ccc|2d|399", "1991|63|ccc|2d|399", "cocitation")
    decide.aggregate_group_origin([c, d], Counter())
    check(c["group_origin_status"] == "UNDETERMINED"
          and "name_year:CA:case_origin:wd" in c["noncore_origin_evidence"],
          "R2-1：仅弱路径有证据 → 组 UNDETERMINED（不传播），证据留审计列")
    # ④ 两个合格成员异国（含跨法院行）→ CONFLICT（证据全保留）
    e = _grow("SCC|2009||ukhl||18", "2009||ukhl||18", "anchor",
              "DETERMINED", "GB", "scope:UKHL", "court_scope_rule")
    f = _grow("ONCA|2011||onca||779", "2011||onca||779", "anchor",
              "DETERMINED", "CA", "scope:ONCA", "court_scope_rule")
    decide.aggregate_group_origin([e, f], Counter())
    check(e["group_origin_status"] == "CONFLICT" and f["foreign_status"] == "CONFLICT",
          "R2-1：合格成员异国 → 整组 CONFLICT（跨法院同理）")
    check("scope:UKHL" in e["group_origin_evidence_ids"]
          and "scope:ONCA" in e["group_origin_evidence_ids"],
          "R2-1：冲突组保留全部证据 id")
    # ⑤ 启发式变体（typo）不授权传播
    g = _grow("SCC|2005||scc||79", "2005||scc||79", "anchor")
    h = _grow("SCC|2005||scc||75", "2005||scc||75", "anchor_variant_typo",
              "DETERMINED", "GB", "scope:X", "court_scope_rule")
    decide.aggregate_group_origin([g, h], Counter())
    check(g["group_origin_status"] == "UNDETERMINED"
          and "anchor_variant_typo:GB:scope:X" in g["noncore_origin_evidence"],
          "R2-1：typo 变体是启发式——证据留审计列，不升组")
    # ⑥ 双语变体（已核实的标识映射）合格：证据可传播
    i1 = _grow("SCC|2014||scc||7", "2014||scc||7", "anchor")
    j1 = _grow("SCC|2014||csc||7", "2014||csc||7", "anchor_variant_bilingual",
               "DETERMINED", "CA", "scope:SCC", "court_scope_rule")
    decide.aggregate_group_origin([i1, j1], Counter())
    check(i1["group_foreign_status"] == "DOMESTIC_CA",
          "R2-1：双语变体（bilingual）是显式身份等价——证据可传播")
    # ⑦ 合格成员本地未决冲突 → 组 CONFLICT（不许被单国成员掩盖）
    k1 = _grow("SCC|2009||ukhl||18", "2009||ukhl||18", "anchor",
               "DETERMINED", "GB", "scope:UKHL", "court_scope_rule")
    m1 = _grow("SCC|2009||uksc||23", "2009||uksc||23", "anchor", "CONFLICT",
               "", "case_origin:p|case_origin:q", "case_record")
    decide.aggregate_group_origin([k1, m1], Counter())
    check(k1["group_origin_status"] == "CONFLICT",
          "R2-1：合格成员本地冲突 → 组 CONFLICT（即使另一成员证据单国）")


def test_effective_sources_and_edges():
    """R2-9：有效来源关联与边成员资格——平行形自引不得重现；counted 来源
    数 == dd；仅启发式路径的边不继承组 FOREIGN；自引边留审计文件。"""
    import decide
    import subprocess
    import tempfile
    anchor = _grow("SCC|2009||ukhl||18", "2009||ukhl||18", "anchor",
                   "DETERMINED", "GB", "scope:UKHL", "court_scope_rule")
    aller = _grow("SCC|2009|3|aller||945", "2009|3|aller||945", "name_year")
    did_idx = {"SCC|2009||ukhl||18": {"A", "B"},
               "SCC|2009|3|aller||945": {"A", "C"}}
    # A 是组自身判决（身份根的自引）→ 剔除；B 经锚到达；C 只经 name_year 到达
    eff = decide.build_effective_sources([anchor, aller], {"B", "C"}, {"A"},
                                         did_idx, Counter())
    by_src = {e["source_decision"]: e for e in eff}
    check(by_src["A"]["status"] == "excluded_self"
          and "self-citation" in by_src["A"]["exclusion_reason"],
          "R2-9：组自身判决标 excluded_self（保留在关联里供审计）")
    check(sum(1 for e in eff if e["status"] == "counted") == 2,
          "R2-9：counted 来源数 == dd（2）")
    check(by_src["B"]["identity_status"] == "anchor"
          and by_src["C"]["identity_status"] == "name_year",
          "R2-9：每条来源带其到达路径的最优 identity_basis")
    # 组级结论 + 端到端边构建（临时目录 + 子进程跑 edges.py）
    for r in (anchor, aller):
        r.update({"group_origin_country": "GB", "group_origin_status": "DETERMINED",
                  "group_foreign_status": "FOREIGN", "group_origin_basis":
                  "court_scope_rule", "group_origin_evidence_ids": "scope:UKHL",
                  "noncore_origin_evidence": ""})
    tmp = tempfile.mkdtemp(prefix="test_edges_")
    os.makedirs(os.path.join(tmp, "decide_out"))
    os.makedirs(os.path.join(tmp, "merge_out", "SCC"))
    with open(os.path.join(tmp, "decide_out", "decided.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(anchor.keys()))
        w.writeheader()
        w.writerows([anchor, aller])
    with open(os.path.join(tmp, "decide_out", "effective_sources.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["merged_group_id", "source_decision",
                                          "status", "exclusion_reason",
                                          "identity_status", "via_member_row_keys"])
        w.writeheader()
        w.writerows(eff)
    mentions = [
        {"candidate_id": "c1", "merge_key": "2009||ukhl||18",
         "arbitration_status": "counted", "source_decision_citation": "B",
         "raw_string": "2009 UKHL 18"},
        {"candidate_id": "c2", "merge_key": "2009|3|aller||945",
         "arbitration_status": "counted", "source_decision_citation": "C",
         "raw_string": "[2009] 3 All E.R. 945"},
        {"candidate_id": "c3", "merge_key": "2009|3|aller||945",
         "arbitration_status": "counted", "source_decision_citation": "A",
         "raw_string": "[2009] 3 All E.R. 945"},
    ]
    with open(os.path.join(tmp, "merge_out", "SCC", "mentions_candidates.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(mentions[0].keys()))
        w.writeheader()
        w.writerows(mentions)
    outdir = os.path.join(tmp, "edges")
    p = subprocess.run([sys.executable, os.path.join(PIPE, "edges.py"),
                        "--decided", os.path.join(tmp, "decide_out", "decided.csv"),
                        "--effective", os.path.join(tmp, "decide_out",
                                                    "effective_sources.csv"),
                        "--merge-out", os.path.join(tmp, "merge_out"),
                        "--output", outdir], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    check(p.returncode == 0, "R2-9：edges.py 端到端跑通（%s）" % p.stderr[-300:])
    edges = list(csv.DictReader(open(os.path.join(outdir, "citation_edges.csv"),
                                     encoding="utf-8", newline="")))
    by_src = {e["source_decision"]: e for e in edges}
    check(by_src["B"]["foreign_status"] == "FOREIGN"
          and by_src["B"]["edge_support"] == "supported",
          "R2-1：经锚路径的边继承组 FOREIGN（supported）")
    check(by_src["C"]["foreign_status"] == "UNDETERMINED"
          and by_src["C"]["edge_support"] == "heuristic_only"
          and by_src["C"]["identity_status"] == "name_year_candidate"
          and by_src["C"]["group_origin_country"] == "GB",
          "R2-1：仅启发式路径的边不继承组 FOREIGN（组结论留作上下文）")
    fedges = list(csv.DictReader(open(os.path.join(outdir, "foreign_edges.csv"),
                                      encoding="utf-8", newline="")))
    check([e["source_decision"] for e in fedges] == ["B"],
          "R2-1：foreign 视图只含 supported FOREIGN 边（C 不再混入）")
    tent = list(csv.DictReader(open(os.path.join(outdir, "tentative_edges.csv"),
                                    encoding="utf-8", newline="")))
    check([e["source_decision"] for e in tent] == ["C"],
          "R2-1：启发式候选关系进 tentative 台账")
    selfx = list(csv.DictReader(open(os.path.join(outdir, "self_excluded_edges.csv"),
                                     encoding="utf-8", newline="")))
    check([e["source_decision"] for e in selfx] == ["A"],
          "R2-9：被剔自引进审计文件，不作普通边重现")


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
              test_group_origin_aggregation, test_effective_sources_and_edges,
              test_bilingual_explicit_table_only,
              test_same_citation_requires_single_key_group,
              test_same_citation_single_key_group,
              test_typo_variant_twice_stays_variant,
              test_eligible_bases_shared_between_decide_and_edges,
              test_counterexample_a_win_weak_cannot_break_equal_tie,
              test_counterexample_b_no_cross_redirect,
              test_counterexample_c_d3_partner_unresolved,
              test_counterexample_d_bstep_loser_not_pointing_to_uncounted,
              test_counterexample_e_same_span_undecided_still_competes,
              test_counterexample_g_input_order_invariance_complex,
              test_counterexample_h_same_key_duplication_invariance,
              test_d3_partner_self_citation_row,
              test_new_path_fixture_measurements):
        t()
    print("全部通过：%d 条断言" % len(PASSED))


if __name__ == "__main__":
    main()
