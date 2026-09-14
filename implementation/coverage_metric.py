# -*- coding: utf-8 -*-
"""Stage 0 覆盖度量（只读仪器，不改管线、不写 decisions/）。

对应计划 §3 的四个测量：
  M1a/M1b  汇编式引证（citation_kind=reporter）的来源地可达上限
           M1a = counted + citation_kind=reporter + L2（分类层）jurisdiction 已解析
           M1b = M1a 再限定「该提及所属成员行的 identity_basis 属合格集」
           并按 (identity_basis × 组当前是否已有确定来源地) 分层，
           报**净新增组级覆盖**（当前 UNDETERMINED 且将首次获得正面证据的组）为头条。
  M2       top 30 汇编缩写的 L2 法域分布（含同形异义标记）
  M3       无年变体族（undated-variant family）规模：同一 (abbr, series, vol, page)
           族内 year 槽位有多于一种取值的族——Stage 3 身份修复的标的与规模
  M4       同形异义汇编在**现有未核实**区间表下的重叠规模（规划用，非生产数字）

口径声明（脚本会把这些口径原样写进 JSON）：
  * 「提及」= merge_out/<court>/mentions_candidates.csv 中 arbitration_status=counted 的行
    （自引、被包含的并存读法、被拒、未决重叠都不计数——与生产计数口径一致）。
  * 「成员行」= decide_out/cross_court/decided.csv 的一行，键 = (court, merge_key)。
  * 合格 identity_basis **从 pipeline/decide.py 直接 import**（ELIGIBLE_BASES），
    不在此处另行硬编码，避免与生产规则漂移。
  * 所有输出都是**只读测量**；M4 明确标注为「未核实区间上的规划估计」。

用法：
  python implementation/coverage_metric.py [--run-dir data/run_..] [--json-out data/...json]
"""

from __future__ import print_function

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

from decide import ELIGIBLE_BASES  # noqa: E402  生产规则唯一事实源
from normalize import nk          # noqa: E402

DECISIONS = os.path.join(ROOT, "decisions")
COURTS = ("SCC", "ONCA")

# 省级法域 → 国别（来源地表按 origin_country 判定；省级只作 subdivision）
CA_PROVINCES = frozenset(("ON", "QC", "BC", "AB", "NS", "NB", "MB", "SK",
                          "NL", "PE", "YT", "NT", "NU"))

# 顶层组状态：组级来源地结论
ST_DETERMINED = "DETERMINED"
ST_CONFLICT = "CONFLICT"
ST_UNDETERMINED = "UNDETERMINED"


def country_of(j):
    j = (j or "").strip()
    if not j or j == "UNSUPPORTED":
        return ""
    return "CA" if j in CA_PROVINCES else j


def key_parts(merge_key):
    """merge_key = year|vol|abbr|series|page（§9.1）。不足 5 段返回 None。"""
    p = merge_key.split("|")
    if len(p) < 5:
        return None
    return p[0], p[1], p[2], p[3], p[4]


def load_rows(path, wanted):
    """（保留给后续阶段复用）按需投影读取 CSV 行。"""
    with open(path, encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        for r in rd:
            yield {k: r.get(k, "") for k in wanted}


# --------------------------------------------------------------------- M1
def measure_m1(run_dir, decided, groups, stats):
    """M1a/M1b + 分层 + 净新增组级覆盖。"""
    per_abbr = Counter()            # 全部 M1a 提及的缩写分布
    strata = Counter()              # (identity_basis, group_status) -> 提及数
    strata_kind = Counter()         # identity_basis -> 提及数（含 gate 之外的）
    strata_groups = defaultdict(set)
    m1a_mentions = 0
    m1a_canadian = 0
    m1a_foreign = 0
    unresolved_mentions = 0
    unresolved_abbr = Counter()
    m1a_rows = set()
    all_counted_reporter_mentions = 0
    m1b_mentions = 0
    m1b_rows = set()
    netnew_groups = set()
    netnew_group_abbrs = defaultdict(set)
    netnew_group_countries = defaultdict(set)
    all_m1a_groups = defaultdict(set)          # gid -> {identity_basis}
    eligible_m1a_groups = set()
    netnew_mentions = Counter()
    netnew_abbr = Counter()
    conflict_risk_groups = set()
    conflict_risk_detail = Counter()
    unknown_member_rows = 0
    per_court = {}

    for court in COURTS:
        path = os.path.join(run_dir, "merge_out", court, "mentions_candidates.csv")
        c = Counter()
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("arbitration_status") != "counted":
                    continue
                if r.get("citation_kind") != "reporter":
                    continue
                all_counted_reporter_mentions += 1
                j = (r.get("jurisdiction") or "").strip()
                if not j or j == "UNSUPPORTED":
                    unresolved_mentions += 1
                    pr = key_parts(r.get("merge_key") or "")
                    unresolved_abbr[pr[2] if pr else ""] += 1
                    continue
                c["m1a"] += 1
                m1a_mentions += 1
                if country_of(j) == "CA":
                    m1a_canadian += 1
                else:
                    m1a_foreign += 1
                mk = r.get("merge_key") or ""
                rk = (court, mk)
                m1a_rows.add(rk)
                ab = key_parts(mk)
                abbr = ab[2] if ab else ""
                per_abbr[abbr] += 1

                mrow = decided.get(rk)
                if mrow is None:
                    unknown_member_rows += 1
                    continue
                ib = mrow["identity_basis"] or "unanchored"
                gst = mrow["group_status"] or ST_UNDETERMINED
                gid = mrow["group_id"]
                strata[(ib, gst)] += 1
                strata_kind[ib] += 1
                strata_groups[(ib, gst)].add(gid)
                all_m1a_groups[gid].add(ib)
                if ib in ELIGIBLE_BASES:
                    m1b_mentions += 1
                    c["m1b"] += 1
                    m1b_rows.add(rk)
                    eligible_m1a_groups.add(gid)
                    if gst == ST_UNDETERMINED:
                        netnew_groups.add(gid)
                        netnew_group_abbrs[gid].add(abbr)
                        netnew_group_countries[gid].add(country_of(j))
                        netnew_mentions[abbr] += 1
                        netnew_abbr[abbr] += 1
                    elif gst == ST_DETERMINED:
                        # 代理冲突风险：该提及按其 L2 法域所属国与组结论国别不一致
                        pc = country_of(j)
                        gc = (mrow["group_country"] or "").strip()
                        if pc and gc and pc != gc:
                            conflict_risk_groups.add(gid)
                            conflict_risk_detail[(gc, pc, abbr)] += 1
        per_court[court] = dict(c)

    stats["M1a_mentions"] = m1a_mentions
    stats["M1a_sensitivity_all_counted_reporter_mentions"] = \
        all_counted_reporter_mentions
    stats["M1a_mentions_canadian_reporter"] = m1a_canadian
    stats["M1a_mentions_foreign_reporter"] = m1a_foreign
    stats["M1a_sensitivity_counted_reporter_unresolved_jurisdiction"] = \
        unresolved_mentions
    stats["M1a_sensitivity_top20_unresolved_abbr"] = unresolved_abbr.most_common(20)
    stats["M1a_member_rows"] = len(m1a_rows)
    stats["M1b_mentions"] = m1b_mentions
    stats["M1b_member_rows"] = len(m1b_rows)
    stats["M1a_member_rows_unknown_in_decided"] = unknown_member_rows
    stats["M1a_abbr_distinct"] = len(per_abbr)
    stats["per_court"] = per_court
    stats["M1a_top40_abbr"] = per_abbr.most_common(40)
    stats["M1_strata_mentions_by_identity_basis"] = dict(
        sorted(strata_kind.items(), key=lambda x: -x[1]))
    stats["M1_strata_mentions_by_ib_and_group_status"] = {
        "%s|%s" % k: v for k, v in
        sorted(strata.items(), key=lambda x: (-x[1], x[0]))}
    stats["M1_strata_groups_by_ib_and_group_status"] = {
        "%s|%s" % k: len(v) for k, v in
        sorted(strata_groups.items(), key=lambda x: -len(x[1]))}
    stats["M1_netnew_undetermined_groups"] = len(netnew_groups)
    stats["M1_netnew_kept_groups_dd_ge_5"] = sum(
        1 for g in netnew_groups if groups.get(g, {}).get("dd", 0) >= 5)
    stats["M1_undetermined_groups_total"] = sum(
        1 for g in groups.values() if g["status"] == ST_UNDETERMINED)
    stats["M1_netnew_abbr_distinct"] = len(netnew_abbr)
    stats["M1_netnew_top40_abbr"] = netnew_abbr.most_common(40)
    gby = Counter()
    for gid, abbrs in netnew_group_abbrs.items():
        for a in abbrs:
            gby[a] += 1
    stats["M1_netnew_groups_by_abbr_top40"] = gby.most_common(40)
    stats["M1a_mentions_by_abbr_full"] = dict(per_abbr)
    stats["M1_netnew_groups_by_abbr_full"] = dict(gby)
    clean = sum(1 for g in netnew_groups
                if len(netnew_group_countries.get(g, ())) == 1)
    stats["M1_netnew_clean_single_country_groups"] = clean
    stats["M1_netnew_multicountry_would_conflict_groups"] = \
        len(netnew_groups) - clean
    dom = {g for g in netnew_groups
           if netnew_group_countries.get(g) == {"CA"}}
    stats["M1_netnew_domestic_ca_groups"] = len(dom)
    stats["M1_netnew_foreign_groups"] = len(netnew_groups) - len(dom)
    stats["M1_netnew_domestic_ca_kept_groups_dd_ge_5"] = sum(
        1 for g in dom if groups.get(g, {}).get("dd", 0) >= 5)
    stats["M1_netnew_foreign_kept_groups_dd_ge_5"] = sum(
        1 for g in (netnew_groups - dom) if groups.get(g, {}).get("dd", 0) >= 5)
    stats["M1_netnew_clean_kept_groups_dd_ge_5"] = sum(
        1 for g in netnew_groups
        if len(netnew_group_countries.get(g, ())) == 1
        and groups.get(g, {}).get("dd", 0) >= 5)

    # 只被不合格 identity_basis 挡住的组（计划 §2 的「阶段 3.5」缺口规模）
    blocked = [g for g in all_m1a_groups
               if g not in eligible_m1a_groups
               and groups.get(g, {}).get("status") == ST_UNDETERMINED]
    blocker_combo = Counter()
    for g in blocked:
        blocker_combo["+".join(sorted(all_m1a_groups[g]))] += 1
    stats["M1_blocked_by_ineligible_basis_groups"] = len(blocked)
    stats["M1_blocked_by_ineligible_basis_combo_top20"] = \
        blocker_combo.most_common(20)
    stats["M1_undetermined_groups_with_m1a_any_basis"] = len(
        [g for g in all_m1a_groups
         if groups.get(g, {}).get("status") == ST_UNDETERMINED])
    stats["M1_determined_groups_with_m1a_any_basis"] = len(
        [g for g in all_m1a_groups
         if groups.get(g, {}).get("status") == ST_DETERMINED])
    stats["M1_conflict_risk_groups_proxy"] = len(conflict_risk_groups)
    stats["M1_conflict_risk_top30"] = [
        {"group_country": a, "mention_country": b, "abbr": c, "mentions": n}
        for (a, b, c), n in conflict_risk_detail.most_common(30)]
    stats["ELIGIBLE_BASES"] = sorted(ELIGIBLE_BASES)
    return netnew_groups


# --------------------------------------------------------------------- M2
def measure_m2(run_dir, homographs, stats):
    dist = defaultdict(Counter)
    tot = Counter()
    for court in COURTS:
        path = os.path.join(run_dir, "merge_out", court, "mentions_candidates.csv")
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("arbitration_status") != "counted":
                    continue
                if r.get("citation_kind") != "reporter":
                    continue
                p = key_parts(r.get("merge_key") or "")
                if not p:
                    continue
                abbr = p[2]
                j = (r.get("jurisdiction") or "").strip() or "(blank)"
                dist[abbr][j] += 1
                tot[abbr] += 1
    out = []
    for abbr, n in tot.most_common(30):
        out.append({
            "abbr": abbr,
            "mentions": n,
            "homograph_rows": homographs.get(abbr, 0),
            "jurisdiction": dict(dist[abbr].most_common()),
        })
    stats["M2_top30"] = out
    stats["M2_population_note"] = (
        "counted + citation_kind=reporter，全部法域（含 UNSUPPORTED/空）——"
        "与 M1a 的差别只在是否要求法域已解析；homograph_rows = "
        "reporter_jurisdiction.csv 里 nk(abbreviation) 相同的行数（>1 即同形异义）")
    return out


# --------------------------------------------------------------------- M3
def measure_m3(run_dir, stats):
    """无年变体族规模：族 = (abbr, series, vol, page)，year 槽位是唯一变量。
    分类：unique_year_merge（恰一个非空年 + 若干空年槽）＝ Stage 3 修复标的；
          multi_year_abstain（≥2 个非空年）＝ 设计规定弃权的反例族。"""
    fam = defaultdict(list)
    per_court_rows = Counter()
    for court in COURTS:
        path = os.path.join(run_dir, "merge_out", court, "merged.csv")
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                p = key_parts(r.get("merge_key") or "")
                if not p:
                    continue
                year, vol, abbr, series, page = p
                fam[(court, nk(abbr), series, vol, page)].append(
                    (year, int(r.get("occurrence_count") or 0),
                     int(r.get("distinct_decisions_count") or 0),
                     r.get("citation_kind") or ""))
                per_court_rows[court] += 1

    agg = {"families_total": 0, "families_single_row": 0,
           "families_multi_row": 0,
           "unique_year_merge_families": 0,
           "unique_year_merge_rows_merged_away": 0,
           "unique_year_merge_occurrence": 0,
           "unique_year_merge_dd": 0,
           "multi_year_abstain_families": 0,
           "multi_year_abstain_with_empty_variant_families": 0,
           "multi_year_abstain_with_empty_variant_occurrence": 0,
           "multi_year_abstain_with_empty_variant_dd": 0,
           "multi_year_abstain_no_empty_variant_families": 0,
           "multi_year_abstain_no_empty_variant_occurrence": 0,
           "multi_year_abstain_no_empty_variant_dd": 0,
           "multi_year_abstain_occurrence": 0,
           "multi_year_abstain_dd": 0,
           "all_empty_year_multi_row_families": 0}
    abbr_unique = Counter()
    abbr_multi = Counter()
    abbr_multi_empty = Counter()
    examples_merge = []
    examples_abstain = []
    examples_odd = []

    for fkey, rows in fam.items():
        agg["families_total"] += 1
        if len(rows) == 1:
            agg["families_single_row"] += 1
            continue
        agg["families_multi_row"] += 1
        years = sorted({y for (y, _, _, _) in rows if y})
        empty = sum(1 for (y, _, _, _) in rows if not y)
        occ = sum(o for (_, o, _, _) in rows)
        dd = sum(d for (_, _, d, _) in rows)
        court, ab, series, vol, page = fkey
        if not years:
            agg["all_empty_year_multi_row_families"] += 1
        elif len(years) == 1 and empty:
            agg["unique_year_merge_families"] += 1
            agg["unique_year_merge_rows_merged_away"] += len(rows) - 1
            agg["unique_year_merge_occurrence"] += occ
            agg["unique_year_merge_dd"] += dd
            abbr_unique[ab] += 1
            if len(examples_merge) < 20:
                examples_merge.append({
                    "court": court, "abbr": ab, "series": series,
                    "vol": vol, "page": page, "year": years[0],
                    "empty_year_rows": empty, "rows": len(rows),
                    "merge_keys": sorted(y for (y, _, _, _) in rows),
                })
        elif len(years) >= 2:
            agg["multi_year_abstain_families"] += 1
            agg["multi_year_abstain_occurrence"] += occ
            agg["multi_year_abstain_dd"] += dd
            abbr_multi[ab] += 1
            if empty:
                agg["multi_year_abstain_with_empty_variant_families"] += 1
                agg["multi_year_abstain_with_empty_variant_occurrence"] += occ
                agg["multi_year_abstain_with_empty_variant_dd"] += dd
                abbr_multi_empty[ab] += 1
            else:
                agg["multi_year_abstain_no_empty_variant_families"] += 1
                agg["multi_year_abstain_no_empty_variant_occurrence"] += occ
                agg["multi_year_abstain_no_empty_variant_dd"] += dd
            if len(examples_abstain) < 20:
                examples_abstain.append({
                    "court": court, "abbr": ab, "series": series,
                    "vol": vol, "page": page, "years": years,
                    "empty_year_rows": empty, "rows": len(rows),
                })
        else:
            # 恰一个非空年、无空年槽 → 全部同键，不可能出现多行；留痕以防万一
            agg.setdefault("unexpected_same_year_multi_row_families", 0)
            agg["unexpected_same_year_multi_row_families"] += 1
            if len(examples_odd) < 20:
                examples_odd.append({
                    "court": court, "abbr": ab, "series": series,
                    "vol": vol, "page": page, "years": years,
                    "rows": len(rows),
                })

    agg["rows_per_court"] = dict(per_court_rows)
    stats["M3"] = agg
    stats["M3_unique_year_top20_abbr"] = abbr_unique.most_common(20)
    stats["M3_multi_year_top20_abbr"] = abbr_multi.most_common(20)
    stats["M3_multi_year_with_empty_variant_top20_abbr"] = \
        abbr_multi_empty.most_common(20)
    stats["M3_examples_unique_year"] = examples_merge
    stats["M3_examples_multi_year_abstain"] = examples_abstain
    stats["M3_examples_unexpected_same_year_multi_row"] = examples_odd
    stats["M3_definition"] = (
        "族=(court, nk(abbr), series, vol, page)；多行族按 year 槽位取值分类。"
        "unique_year_merge = 恰一个非空年 + ≥1 空年槽（Stage 3 目标）；"
        "multi_year_abstain = ≥2 个非空年（设计规定弃权）。")
    return agg


# --------------------------------------------------------------------- M4
def _in_range(v, lo, hi):
    """闭区间；空界=无约束。可比较性由调用方判断。"""
    try:
        iv = int(v)
    except (TypeError, ValueError):
        return False
    if lo != "":
        try:
            if iv < int(lo):
                return False
        except ValueError:
            pass
    if hi != "":
        try:
            if iv > int(hi):
                return False
        except ValueError:
            pass
    return True


def row_matches(vol, year, row):
    """维度式包含：仅当**两侧都有值**时该维度才可判、才可否决；
    任何可比维度否决即不匹配。两个维度都不可比 → 该行无约束（匹配一切）。"""
    vs = (row.get("vol_range_start") or "").strip()
    ve = (row.get("vol_range_end") or "").strip()
    ys = (row.get("year_range_start") or "").strip()
    ye = (row.get("year_range_end") or "").strip()
    if vol != "" and (vs or ve):
        if not _in_range(vol, vs, ve):
            return False
    if year != "" and (ys or ye):
        if not _in_range(year, ys, ye):
            return False
    return True


def load_jurisdiction_rows():
    rows = []
    path = os.path.join(DECISIONS, "reporter_jurisdiction.csv")
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            r = {k: (v or "").strip() for k, v in r.items()}
            rows.append(r)
    return rows


def measure_m4(run_dir, jrows, stats):
    by_abbr = defaultdict(list)
    for r in jrows:
        by_abbr[nk(r["abbreviation"])].append(r)
    homographs = {a: len(v) for a, v in by_abbr.items() if len(v) > 1}

    combos = defaultdict(set)
    combos_m = defaultdict(Counter)      # (vol, year) -> 提及数
    mentions = Counter()
    for court in COURTS:
        path = os.path.join(run_dir, "merge_out", court, "mentions_candidates.csv")
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("arbitration_status") != "counted":
                    continue
                if r.get("citation_kind") != "reporter":
                    continue
                p = key_parts(r.get("merge_key") or "")
                if not p:
                    continue
                year, vol, abbr = p[0], p[1], p[2]
                if abbr in homographs:
                    combos[abbr].add((vol, year))
                    combos_m[abbr][(vol, year)] += 1
                    mentions[abbr] += 1

    out = []
    tot = Counter()
    for abbr, rows in sorted(by_abbr.items()):
        if len(rows) < 2:
            continue
        unconstrained = sum(1 for r in rows
                            if not (r["vol_range_start"] or r["vol_range_end"]
                                    or r["year_range_start"] or r["year_range_end"]))
        c = Counter()
        cm = Counter()
        for (vol, year) in combos.get(abbr, ()):
            hit = [r for r in rows if row_matches(vol, year, r)]
            n = len(hit)
            if n == 0:
                bucket = "combos_out_of_window"
            elif n == 1:
                bucket = "combos_unique"
            else:
                cs = {country_of(r["jurisdiction"]) for r in hit}
                bucket = ("combos_ambiguous_same_country" if len(cs) == 1
                          else "combos_ambiguous_diff_country")
                c["combos_ambiguous"] += 1
            c[bucket] += 1
            cm[bucket.replace("combos_", "mentions_")] += \
                combos_m[abbr][(vol, year)]
            if n >= 2:
                cm["mentions_ambiguous"] += combos_m[abbr][(vol, year)]
        out.append({
            "abbr": abbr,
            "table_rows": len(rows),
            "table_origins": sorted({r["jurisdiction"] for r in rows}),
            "unconstrained_rows": unconstrained,
            "observed_combos": len(combos.get(abbr, ())),
            "observed_mentions": mentions.get(abbr, 0),
            "combos_out_of_window": c["combos_out_of_window"],
            "combos_unique": c["combos_unique"],
            "combos_ambiguous": c["combos_ambiguous"],
            "combos_ambiguous_same_country": c["combos_ambiguous_same_country"],
            "combos_ambiguous_diff_country": c["combos_ambiguous_diff_country"],
            "mentions_out_of_window": cm["mentions_out_of_window"],
            "mentions_unique": cm["mentions_unique"],
            "mentions_ambiguous": cm["mentions_ambiguous"],
            "mentions_ambiguous_same_country":
                cm["mentions_ambiguous_same_country"],
            "mentions_ambiguous_diff_country":
                cm["mentions_ambiguous_diff_country"],
        })
        for k, v in c.items():
            tot[k] += v
        for k, v in cm.items():
            tot[k] += v

    stats["M4_homograph_reporters"] = out
    stats["M4_totals_combos"] = {
        "combos_out_of_window": tot["combos_out_of_window"],
        "combos_unique": tot["combos_unique"],
        "combos_ambiguous": tot["combos_ambiguous"],
        "combos_ambiguous_same_country": tot["combos_ambiguous_same_country"],
        "combos_ambiguous_diff_country": tot["combos_ambiguous_diff_country"],
        "combos_total": (tot["combos_out_of_window"] + tot["combos_unique"]
                         + tot["combos_ambiguous"]),
        "mentions_out_of_window": tot["mentions_out_of_window"],
        "mentions_unique": tot["mentions_unique"],
        "mentions_ambiguous": tot["mentions_ambiguous"],
        "mentions_ambiguous_same_country":
            tot["mentions_ambiguous_same_country"],
        "mentions_ambiguous_diff_country":
            tot["mentions_ambiguous_diff_country"],
        "mentions_total": (tot["mentions_out_of_window"] + tot["mentions_unique"]
                           + tot["mentions_ambiguous"]),
    }
    stats["M4_country_proxy_note"] = (
        "「同国/异国」用 reporter_jurisdiction.csv 的 jurisdiction 作国别代理"
        "（省级 ON/QC/… 归 CA）；代理只用于估计同国重叠的规模，不是生产判定。")
    stats["M4_label"] = (
        "规划估计，**不是生产数字**：区间取自现有 reporter_jurisdiction.csv，"
        "该表 196 行 100% confidence=estimated / verification_level=name_inference（未核实）；"
        "重叠规模只用于校准 Stage 1 研究工作量与预期 UNDETERMINED 残差。")
    return homographs


# --------------------------------------------------------------------- main
def load_decided(run_dir):
    path = os.path.join(run_dir, "decide_out", "cross_court", "decided.csv")
    want = ("court", "merge_key", "identity_basis", "merged_group_id",
            "group_origin_status", "group_origin_country", "group_foreign_status",
            "occurrence_count", "distinct_decisions_count", "citation_kind",
            "jurisdiction")
    out = {}
    groups = {}
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rk = (r["court"], r["merge_key"])
            out[rk] = {
                "identity_basis": r.get("identity_basis") or "",
                "group_id": r.get("merged_group_id") or "",
                "group_status": r.get("group_origin_status") or "",
                "group_country": r.get("group_origin_country") or "",
                "group_foreign": r.get("group_foreign_status") or "",
                "occ": int(r.get("occurrence_count") or 0),
                "dd": int(r.get("distinct_decisions_count") or 0),
            }
            g = groups.setdefault(r.get("merged_group_id") or "", {
                "status": r.get("group_origin_status") or "",
                "country": r.get("group_origin_country") or "",
                "foreign": r.get("group_foreign_status") or "",
                "dd": int(r.get("distinct_decisions_count") or 0)})
            g["dd"] = max(g["dd"], int(r.get("distinct_decisions_count") or 0))
    return out, groups


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", default=os.path.join(
        ROOT, "data", "run_20260913_r2i"))
    ap.add_argument("--json-out", default=os.path.join(
        ROOT, "data", "coverage_out", "stage0_r2i.json"))
    args = ap.parse_args()

    run_dir = args.run_dir
    if not os.path.isabs(run_dir):
        run_dir = os.path.join(ROOT, run_dir)
    stats = {"run_dir": os.path.relpath(run_dir, ROOT).replace("\\", "/")}

    print("loading decided ...", file=sys.stderr)
    decided, groups = load_decided(run_dir)
    stats["groups_total"] = len(groups)
    stats["member_rows_total"] = len(decided)
    stats["groups_by_status"] = dict(Counter(
        g["status"] for g in groups.values()).most_common())
    stats["groups_by_foreign_status"] = dict(Counter(
        g["foreign"] for g in groups.values()).most_common())
    kept = [g for g in groups.values() if g["dd"] >= 5]
    stats["kept_groups_dd_ge_5"] = len(kept)
    stats["kept_groups_by_foreign_status"] = dict(Counter(
        g["foreign"] for g in kept).most_common())

    print("M1 ...", file=sys.stderr)
    measure_m1(run_dir, decided, groups, stats)
    print("M2 ...", file=sys.stderr)
    jrows = load_jurisdiction_rows()
    by_abbr = defaultdict(list)
    for r in jrows:
        by_abbr[nk(r["abbreviation"])].append(r)
    homographs = {a: len(v) for a, v in by_abbr.items() if len(v) > 1}
    stats["reporter_jurisdiction_rows"] = len(jrows)
    stats["reporter_jurisdiction_homograph_abbrs"] = homographs
    measure_m2(run_dir, homographs, stats)
    print("M3 ...", file=sys.stderr)
    measure_m3(run_dir, stats)
    print("M4 ...", file=sys.stderr)
    measure_m4(run_dir, jrows, stats)

    out = args.json_out
    if not os.path.isabs(out):
        out = os.path.join(ROOT, out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1, sort_keys=False)
    print("written:", os.path.relpath(out, ROOT), file=sys.stderr)
    print(json.dumps(_summary(stats), ensure_ascii=False, indent=1))


def _summary(s):
    return {
        "run_dir": s["run_dir"],
        "groups_total": s["groups_total"],
        "groups_by_foreign_status": s["groups_by_foreign_status"],
        "kept_groups_dd_ge_5": s["kept_groups_dd_ge_5"],
        "M1a_mentions": s["M1a_mentions"],
        "M1a_mentions_canadian_reporter": s["M1a_mentions_canadian_reporter"],
        "M1a_mentions_foreign_reporter": s["M1a_mentions_foreign_reporter"],
        "M1a_sensitivity_counted_reporter_unresolved_jurisdiction":
            s["M1a_sensitivity_counted_reporter_unresolved_jurisdiction"],
        "M1a_member_rows": s["M1a_member_rows"],
        "M1b_mentions": s["M1b_mentions"],
        "M1b_member_rows": s["M1b_member_rows"],
        "M1_strata_mentions_by_identity_basis":
            s["M1_strata_mentions_by_identity_basis"],
        "M1_strata_mentions_by_ib_and_group_status":
            s["M1_strata_mentions_by_ib_and_group_status"],
        "M1_netnew_undetermined_groups": s["M1_netnew_undetermined_groups"],
        "M1_netnew_clean_single_country_groups":
            s["M1_netnew_clean_single_country_groups"],
        "M1_netnew_multicountry_would_conflict_groups":
            s["M1_netnew_multicountry_would_conflict_groups"],
        "M1_blocked_by_ineligible_basis_groups":
            s["M1_blocked_by_ineligible_basis_groups"],
        "M1_blocked_by_ineligible_basis_combo_top20":
            s["M1_blocked_by_ineligible_basis_combo_top20"],
        "M1_netnew_domestic_ca_groups": s["M1_netnew_domestic_ca_groups"],
        "M1_netnew_foreign_groups": s["M1_netnew_foreign_groups"],
        "M1_netnew_domestic_ca_kept_groups_dd_ge_5":
            s["M1_netnew_domestic_ca_kept_groups_dd_ge_5"],
        "M1_netnew_foreign_kept_groups_dd_ge_5":
            s["M1_netnew_foreign_kept_groups_dd_ge_5"],
        "M1_netnew_kept_groups_dd_ge_5": s["M1_netnew_kept_groups_dd_ge_5"],
        "M1_undetermined_groups_total": s["M1_undetermined_groups_total"],
        "M1_conflict_risk_groups_proxy": s["M1_conflict_risk_groups_proxy"],
        "ELIGIBLE_BASES": s["ELIGIBLE_BASES"],
        "M3": s["M3"],
        "M4_totals_combos": s["M4_totals_combos"],
    }


if __name__ == "__main__":
    main()
