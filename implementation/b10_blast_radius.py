# -*- coding: utf-8 -*-
"""b10_blast_radius.py — B10 修复的爆半径核查（验证项 1/2/6）

用法：python implementation/b10_blast_radius.py <r2e_run_dir> <r2d_c_dir>

1. B10 before/after：容器作废数、配对者去向分解、unresolved 数
   （court-code 中立 vs vendor/CanLII 分列）。
2. 候选台账 diff（candidate_id × status）：每条变化分类为
   (i)  B10 容器 / 配对者 / 配对者同跨度孪生
   (ii) 其他（目标 0）
6. 追溯：2003 SCC 74 与一条 CanLII 样例的 candidate_id。
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

COURTS = ("SCC", "ONCA")


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main(r2e, r2dc):
    m_old, m_new = {}, {}
    cand_new = {}
    for court in COURTS:
        for m in rows(os.path.join(r2dc, "merge_out", court,
                                   "mentions_candidates.csv")):
            m_old[m["candidate_id"]] = m
        for m in rows(os.path.join(r2e, "merge_out", court,
                                   "mentions_candidates.csv")):
            m_new[m["candidate_id"]] = m
        for c in rows(os.path.join(r2e, "extract_out", "candidates.csv")):
            if c.get("structural_conflict"):
                cand_new[c["candidate_id"]] = c

    containers = {cid for cid, c in cand_new.items()
                  if c["structural_conflict"] == "year_reread_as_vol"}
    partners = {c["conflict_with_candidate"] for c in cand_new.values()
                if c["structural_conflict"] == "year_reread_as_vol"}
    # 配对者同跨度孪生：同 (sdc,row,start,end) 的其他候选
    pos_index = defaultdict(list)
    for m in m_new.values():
        pos_index[(m["source_decision_citation"], m["corpus_row_index"],
                   m["match_start_offset"], m["match_end_offset"])].append(
            m["candidate_id"])
    twins = set()
    for p in partners:
        pm = m_new.get(p)
        if not pm:
            continue
        key = (pm["source_decision_citation"], pm["corpus_row_index"],
               pm["match_start_offset"], pm["match_end_offset"])
        twins.update(pos_index.get(key, []))
    related = containers | partners | twins

    # ---- 1. B10 before/after ----
    partner_fate = Counter()
    unresolved = 0
    code_split = Counter()
    for c in cand_new.values():
        if c["structural_conflict"] != "year_reread_as_vol":
            continue
        st = m_new.get(c["candidate_id"], {}).get("arbitration_status", "?")
        if st == "year_reread_as_vol_invalid":
            pm = m_new.get(c["conflict_with_candidate"], {})
            partner_fate[pm.get("arbitration_status") or "<missing>"] += 1
            token = (c.get("token") or c.get("abbr") or "")
            # court-code 中立 vs vendor（CanLII 类）：按配对者的法域判定结果分
            pj = pm.get("jurisdiction") or "UNSUPPORTED"
            code_split["court_code_resolved" if pj not in ("", "UNSUPPORTED")
                       else "vendor_or_unresolved"] += 1
        else:
            unresolved += 1
    item1 = {
        "containers_flagged": len(containers),
        "containers_invalidated": sum(
            1 for c in containers
            if m_new.get(c, {}).get("arbitration_status")
            == "year_reread_as_vol_invalid"),
        "partner_fate": dict(partner_fate),
        "unresolved_containers": unresolved,
        "by_partner_table_outcome": dict(code_split),
    }

    # ---- 2. 台账 diff 分类 ----
    changes = []
    for cid in sorted(set(m_old) & set(m_new)):
        a = m_old[cid]["arbitration_status"]
        b = m_new[cid]["arbitration_status"]
        if a != b:
            cls = ("i_b10_related" if cid in related else "ii_other")
            changes.append({
                "candidate_id": cid, "raw_string": m_new[cid]["raw_string"],
                "shape": m_new[cid]["shape_name"],
                "r2dc_status": a, "r2e_status": b,
                "b10_class": cls,
                "role": ("container" if cid in containers else
                         "partner" if cid in partners else
                         "partner_twin" if cid in twins else "-")})
    cnt = Counter((c["b10_class"], c["r2dc_status"], c["r2e_status"])
                  for c in changes)
    item2 = {
        "total_status_changes": len(changes),
        "class_i_b10_related": sum(1 for c in changes
                                   if c["b10_class"] == "i_b10_related"),
        "class_ii_other": sum(1 for c in changes
                              if c["b10_class"] == "ii_other"),
        "transitions": {("%s -> %s [%s]" % k): v for k, v in cnt.most_common()},
    }
    outdir = os.path.join(r2e, "audit")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "b10_blast_radius.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(changes[0].keys()) if changes
                           else ["candidate_id"])
        w.writeheader()
        w.writerows(changes)

    # ---- 6. 追溯样例 candidate_id ----
    samples = {}
    for m in m_new.values():
        if m["raw_string"] == "2003 SCC 74" and m["arbitration_status"] == "counted":
            samples.setdefault("scc_74_counted", m["candidate_id"])
        if m["raw_string"] == "2001 CanLII 24079" and \
                m["arbitration_status"] == "span_alternative_undecided":
            samples.setdefault("canliii_24079_undecided", m["candidate_id"])
    item6 = samples

    print(json.dumps({"item1_b10": item1, "item2_blast_radius": item2,
                      "item6_traceback_ids": item6},
                     ensure_ascii=False, indent=1))
    with open(os.path.join(outdir, "b10_blast_summary.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump({"item1": item1, "item2": item2, "item6": item6},
                  f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
