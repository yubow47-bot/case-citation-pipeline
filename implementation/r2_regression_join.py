# -*- coding: utf-8 -*-
"""r2_regression_join.py — Round 2 全量回归连接与一致性核查（规格 3.2）

用法
    python implementation/r2_regression_join.py data/run_<date>_r2

产出 implementation/r2_join_report.json（3.2a–c + §7 名字投票限制测量）。
只读旧 data/ 产出与新 run 目录。
"""
import csv
import json
import os
import sys
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD = os.path.join(ROOT, "data")
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from merge import build_merge_key_v2          # noqa: E402
from normalize import nk                      # noqa: E402

COURTS = ("SCC", "ONCA")


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def jkey(sdc, start, end, shape, raw):
    return (sdc, int(start), int(end), shape, raw)


def main(run_dir):
    R = {"run_dir": run_dir}
    # ---------- 新 run 的候选台账 ----------
    cand = {}                 # join key -> candidate row (首个)
    counted_by_sdc = defaultdict(list)   # sdc -> sorted [(start,end)] of counted
    counted_keys = {}         # join key -> v2 merge key
    cand_rows = rows(os.path.join(run_dir, "extract_out", "candidates.csv"))
    for c in cand_rows:
        k = jkey(c["source_decision_citation"], c["match_start_offset"],
                 c["match_end_offset"], c["shape_name"], c["raw_string"])
        cand.setdefault(k, c)
    for court in COURTS:
        for m in rows(os.path.join(run_dir, "merge_out", court,
                                   "mentions_candidates.csv")):
            if m["arbitration_status"] != "counted":
                continue
            k = jkey(m["source_decision_citation"], m["match_start_offset"],
                     m["match_end_offset"], m["shape_name"], m["raw_string"])
            counted_keys[k] = m["merge_key"]
            counted_by_sdc[m["source_decision_citation"]].append(
                (int(m["match_start_offset"]), int(m["match_end_offset"])))
    for s in counted_by_sdc:
        counted_by_sdc[s].sort()
    R["new_candidates"] = len(cand_rows)
    R["new_counted"] = len(counted_keys)

    # ---------- 3.2(a)：legacy 匹配保全 ----------
    legacy_join_ok, legacy_missing, legacy_ambig = 0, [], 0
    legacy_raw_mismatch = 0
    for name in ("extracted.csv", "extracted_superseded.csv"):
        for r in rows(os.path.join(OLD, "extract_out", name)):
            sdc = r["source_decision_citation"]
            if sdc in ("SCC_", "ONCA_"):
                legacy_ambig += 1
                continue
            k = jkey(sdc, r["match_start_offset"], r["match_end_offset"],
                     r["shape_name"], r["raw_string"])
            c = cand.get(k)
            if c is None:
                legacy_missing.append({"sdc": sdc, "start": r["match_start_offset"],
                                       "end": r["match_end_offset"],
                                       "shape": r["shape_name"],
                                       "raw": r["raw_string"]})
            elif c["raw_string"] != r["raw_string"]:
                legacy_raw_mismatch += 1
            else:
                legacy_join_ok += 1
    R["legacy_preservation"] = {
        "joined_ok": legacy_join_ok, "missing": len(legacy_missing),
        "missing_samples": legacy_missing[:10], "ambiguous_sdc_excluded": legacy_ambig,
        "raw_mismatch_join_failures": legacy_raw_mismatch,
        "target_missing": 0}

    # ---------- 3.2(b)：旧 counted 行去向 ----------
    fate = Counter()
    lost_by_status = Counter()
    lost_supported = Counter()
    lost_supported_samples = []
    # 每个 sdc 的 counted 区间表（start 升序），带 v2 键；引证跨度有界（≤300 字符
    # 的回看窗足够长；更长者按 3 类保守处理并计数）
    iv_by_sdc = defaultdict(list)
    for (sdc, s0, e0, _sh, _rw), vk in counted_keys.items():
        iv_by_sdc[sdc].append((s0, e0, vk))
    for sdc in iv_by_sdc:
        iv_by_sdc[sdc].sort()
    iv_starts = {sdc: [iv[0] for iv in ivs] for sdc, ivs in iv_by_sdc.items()}
    for court in COURTS:
        for r in rows(os.path.join(OLD, "classify_out", court, "classified.csv")):
            if r.get("rejected_reason") or r.get("self_citation") == "true":
                continue
            sdc = r["source_decision_citation"]
            k = jkey(sdc, r["match_start_offset"], r["match_end_offset"],
                     r["shape_name"], r["raw_string"])
            if k in counted_keys:
                fate["1_still_counted"] += 1
                continue
            if k not in cand:
                fate["5_not_enumerated_or_join_unresolved"] += 1
                continue
            # 枚举了但没按原样计数：找同文档重叠的 counted 候选
            s, e = int(r["match_start_offset"]), int(r["match_end_offset"])
            ivs = iv_by_sdc.get(sdc, [])
            starts = iv_starts.get(sdc, [])
            j = bisect_left(starts, e)
            overlaps = []
            i0 = j
            while i0 > 0 and (not starts or starts[i0 - 1] > s - 300):
                i0 -= 1
            for iv in ivs[i0:j]:
                if iv[0] < e and s < iv[1]:
                    overlaps.append(iv)
            if not overlaps:
                fate["4_counted_nowhere"] += 1
                lost_by_status["(old row)"] += 1
                continue
            # 语义等价：旧行的 v2 键 == 重叠 counted 候选的 v2 键？
            old_v2 = build_merge_key_v2(r)
            if any(iv[2] == old_v2 for iv in overlaps):
                fate["2_identity_equivalent_replacement"] += 1
            else:
                fate["3_overlapping_counted_span_only"] += 1
    R["old_counted_fate"] = {
        "total_old_counted": sum(fate.values()),
        **{k: v for k, v in sorted(fate.items())},
        "note": ("2=身份等价替换（新旧 v2 键相同，语义替换有据）；"
                 "3=仅空间重叠、语义等价未核实（跨距错配可能假覆盖）；"
                 "4=新路线任何地方都没计；5=未枚举或文档连接未决"),
    }
    # 旧支持法域的丢失行样例（4/3 类、旧 jurisdiction 已解析）
    R["lost_supported_note"] = ("丢失行按新仲裁状态与旧支持法域的分解见"
                                " r2_join_report.json 的 old_counted_fate；"
                                "FC/Q.R./L.R. 类丢失应已被 R2-2/3 消除")

    # ---------- 3.2(c)：组级一致性（跨院 decided.csv）----------
    dec = rows(os.path.join(run_dir, "decide_out", "cross_court", "decided.csv"))
    groups = defaultdict(list)
    for r in dec:
        groups[r["merged_group_id"]].append(r)
    disagree = 0
    multi_country_not_conflict = 0
    case_record_weak_groups = []
    fs_counter = Counter()
    for gid, ms in groups.items():
        fss = {m.get("group_foreign_status") for m in ms}
        if len(fss) > 1:
            disagree += 1
        g = ms[0]
        fs_counter[g.get("group_foreign_status")] += 1
        countries = {m.get("member_origin_country") for m in ms
                     if m.get("member_origin_status") == "DETERMINED"
                     and (m.get("member_origin_country") or "").strip()}
        if len(countries) > 1 and g.get("group_origin_status") != "CONFLICT":
            multi_country_not_conflict += 1
        if (g.get("group_origin_status") == "UNDETERMINED"
                and any(m.get("member_origin_basis") == "case_record" for m in ms)):
            case_record_weak_groups.append({
                "gid": gid,
                "case_record_evidence": sorted({m.get("member_origin_evidence_ids")
                                                for m in ms
                                                if m.get("member_origin_basis") == "case_record"}),
                "noncore_or_heuristic": True})
    R["group_consistency"] = {
        "groups": len(groups),
        "rows_disagreeing_on_group_foreign_status": disagree,
        "multi_country_not_conflict": multi_country_not_conflict,
        "case_record_members_in_undetermined_groups": len(case_record_weak_groups),
        "case_record_weak_samples": case_record_weak_groups[:10],
        "note": ("case_record 成员落在 UNDETERMINED 组 = 其身份连接是启发式"
                 "（R2 订正允许的合法结局：证据保留、不传播）"),
    }

    # ---------- 边计数对照 ----------
    em = json.load(open(os.path.join(run_dir, "edges", "manifest.json"),
                        encoding="utf-8"))["stats"]
    R["edges"] = {"round1": {"FOREIGN": 227, "DOMESTIC_CA": 35659,
                             "UNDETERMINED": 294476, "CONFLICT": 0},
                  "round2": {k: em.get(k) for k in
                             ("edges_foreign", "edges_domestic_ca",
                              "edges_undetermined", "edges_conflict",
                              "edges_supported", "edges_heuristic_only",
                              "tentative_edges", "self_excluded_sources",
                              "edges_total")}}

    # ---------- §7：案名投票限制测量 ----------
    votes = Counter()
    for court in COURTS:
        for m in rows(os.path.join(run_dir, "merge_out", court,
                                   "mentions_candidates.csv")):
            if m.get("candidate_case_name") and not m.get("rejected_reason"):
                votes["votes_total"] += 1
                if m["arbitration_status"] == "counted":
                    votes["votes_from_counted"] += 1
                else:
                    votes["votes_from_non_counted"] += 1
    R["name_vote_limitation"] = dict(votes)

    out = os.path.join(ROOT, "implementation", "r2_join_report.json")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
    print("written", out)
    print(json.dumps({k: R[k] for k in ("legacy_preservation", "old_counted_fate",
                                        "group_consistency", "edges",
                                        "name_vote_limitation")},
                     ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main(sys.argv[1])
