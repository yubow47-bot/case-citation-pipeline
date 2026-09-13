# -*- coding: utf-8 -*-
"""arbitration_spotcheck.py — 任务四：状态变化候选分层抽查（20 条，含原文）

用法：python implementation/arbitration_spotcheck.py <r2d_run_dir> <baseline_dir>
分层：变化类型 × 原压制者终态 × 形状；稀有类型全收，大类型按 candidate_id
排序取前 N（可复现）。原文用 traceback.corpus_row 取未改动语料窗口。
输出：<run>/audit/arbitration_spotcheck_20.csv（judgment 列人工填写）
"""
import csv
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import traceback as tb                        # noqa: E402  (corpus_row)

COURTS = ("SCC", "ONCA")
STRATUM_QUOTA = {
    ("span_alternative_undecided", "alternative_contained"): 5,
    ("counted", "overlap_undecided"): 4,
    ("alternative_contained", "overlap_undecided"): 3,
    ("alternative_unsupported_reading", "alternative_contained"): 2,
    ("alternative_contained", "counted"): 2,
    ("alternative_unsupported_reading", "overlap_undecided"): 1,
    ("alternative_dominated_by_support", "overlap_undecided"): 1,
    ("alternative_spanning_mismatch", "alternative_dominated_by_support"): 1,
    ("alternative_same_key", "overlap_undecided"): 1,
    ("cross_boundary_invalid", "span_alternative_undecided"): 1,
}


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main(r2d, baseline):
    m_base, m_new = {}, {}
    for court in COURTS:
        for m in rows(os.path.join(baseline, "merge_out", court,
                                   "mentions_candidates.csv")):
            m_base[m["candidate_id"]] = m
        for m in rows(os.path.join(r2d, "merge_out", court,
                                   "mentions_candidates.csv")):
            m_new[m["candidate_id"]] = m
    changes = []
    for cid in sorted(set(m_base) & set(m_new)):
        a = m_base[cid]["arbitration_status"]
        b = m_new[cid]["arbitration_status"]
        if a != b:
            changes.append((cid, a, b))
    strata = defaultdict(list)
    for cid, a, b in changes:
        strata[(a, b)].append(cid)
    picked = []
    for key, quota in STRATUM_QUOTA.items():
        pool = sorted(strata.get(key, []))
        picked.extend(pool[:quota])
    out = []
    for cid in picked:
        m = m_new[cid]
        court = cid.split(":")[0]
        row_idx = int(m["corpus_row_index"])
        s, e = int(m["match_start_offset"]), int(m["match_end_offset"])
        try:
            _cite, _date, text = tb.corpus_row(court, row_idx)
            lo, hi = max(0, s - 130), min(len(text), e + 130)
            window = (text[lo:s] + "<<" + text[s:e] + ">>" + text[e:hi])
            window = window.replace("\n", " ")
        except Exception as ex:                      # noqa: BLE001
            window = "<corpus read failed: %s>" % ex
        sup = m.get("superseded_by_candidate") or ""
        sup_status = m_new.get(sup, {}).get("arbitration_status", "") if sup else ""
        out.append({
            "candidate_id": cid,
            "corpus_row_index": m["corpus_row_index"],
            "raw_string": m["raw_string"],
            "shape": m["shape_name"],
            "r2c_status": m_base[cid]["arbitration_status"],
            "r2d_status": m["arbitration_status"],
            "r2d_superseded_by": sup,
            "superseder_r2d_status": sup_status,
            "r2d_note": m.get("arbitration_note", ""),
            "original_text_window": window,
            "engineering_judgment": "",
        })
    path = os.path.join(r2d, "audit", "arbitration_spotcheck_20.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print("written", path, "n=", len(out))
    for o in out:
        print("\n== %s | %s -> %s | raw=%r" % (o["candidate_id"],
                                               o["r2c_status"], o["r2d_status"],
                                               o["raw_string"]))
        print("   sup=%r (%s)  note=%r" % (o["r2d_superseded_by"],
                                           o["superseder_r2d_status"],
                                           o["r2d_note"][:80]))
        print("   text: %s" % o["original_text_window"][:280])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
