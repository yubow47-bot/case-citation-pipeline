# -*- coding: utf-8 -*-
"""r2closure_delta.py — R2 闭环差异核对与审计产物生成（任务三 7.1-7.4）

用法：python implementation/r2closure_delta.py <r2d_run_dir>

区分两种时间范围（不得混算）：
  7.1 历史差异：Round 1（data/run_20260912_final）→ r2c（data/run_20260912_r2c）
      ——解释 round-1 报告的净算术残差 330,362 − 1,366 = 328,996 vs r2c 实际 329,836（+840）
  7.2 本轮差异：r2c → r2d（本轮 grounded 仲裁 + 身份授权修复）
边身份键 = (source_decision, 排序后的 mention_detail_key)（稳定、可复算）。
组身份键 = 成员 row_key（court|merge_key）的 frozenset。
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R1 = os.path.join(ROOT, "data", "run_20260912_final")
R2C = os.path.join(ROOT, "data", "run_20260912_r2c")
COURTS = ("SCC", "ONCA")


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def edge_key(e):
    return (e["source_decision"], ";".join(sorted(
        set(k for k in e["mention_detail_key"].split(";") if k))))


def load_edges(run):
    return {edge_key(e): e for e in rows(os.path.join(run, "edges",
                                                      "citation_edges.csv"))}


def groups_of(run):
    g = defaultdict(list)
    for r in rows(os.path.join(run, "decide_out", "cross_court", "decided.csv")):
        g[r["merged_group_id"]].append(r)
    # 组身份 = 成员 row_key 集（跨 run 稳定）
    by_members = {}
    for gid, ms in g.items():
        key = frozenset("%s|%s" % (m.get("court") or "", m["merge_key"])
                        for m in ms)
        by_members[key] = (gid, ms)
    return g, by_members


def edge_categories(removed, added, new_edges, old_edges, r2c_mentions, r1_mentions):
    """给新增/删除边一个尽力而为的成因类（每边一行，不预设恰好多少条某类）。"""
    r2c_by_source_mentions = defaultdict(set)
    for (src, _k) in new_edges:
        r2c_by_source_mentions[src].update(
            k for k in new_edges[(src, _k)]["mention_detail_key"].split(";") if k)
    r1_by_source_mentions = defaultdict(set)
    for (src, _k) in old_edges:
        r1_by_source_mentions[src].update(
            k for k in old_edges[(src, _k)]["mention_detail_key"].split(";") if k)
    cat = {}
    for (src, mk) in removed:
        mks = set(mk.split(";")) if mk else set()
        if r2c_by_source_mentions.get(src) and not (mks & r2c_by_source_mentions[src]):
            c = "mentions_not_counted_in_r2c"
        elif mks & r2c_by_source_mentions.get(src, set()):
            c = "regrouped_or_rekeyed_in_r2c"
        else:
            c = "unclassified"
        cat[("removed", src, mk)] = c
    for (src, mk) in added:
        mks = set(mk.split(";")) if mk else set()
        if r1_by_source_mentions.get(src) and not (mks & r1_by_source_mentions[src]):
            c = "new_counted_mentions_in_r2c"
        elif mks & r1_by_source_mentions.get(src, set()):
            c = "regrouped_or_rekeyed_in_r2c"
        else:
            c = "unclassified"
        cat[("added", src, mk)] = c
    return cat


def main(r2d):
    outdir = os.path.join(r2d, "audit")
    os.makedirs(outdir, exist_ok=True)
    report = {}

    r1_edges = load_edges(R1)
    r2c_edges = load_edges(R2C)
    r2d_edges = load_edges(r2d)

    # ---------- 7.1 历史：Round1 → r2c ----------
    r1_keys, r2c_keys = set(r1_edges), set(r2c_edges)
    removed_h = r1_keys - r2c_keys
    added_h = r2c_keys - r1_keys
    cat_h = edge_categories(removed_h, added_h, r2c_edges, r1_edges, None, None)
    with open(os.path.join(outdir, "historical_edge_delta_round1_to_r2c.csv"),
              "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["direction", "source_decision", "mention_detail_key",
                    "category", "r1_foreign_status", "r2c_foreign_status"])
        for (src, mk) in sorted(removed_h):
            w.writerow(["removed", src, mk, cat_h[("removed", src, mk)],
                        r1_edges[(src, mk)]["foreign_status"], ""])
        for (src, mk) in sorted(added_h):
            w.writerow(["added", src, mk, cat_h[("added", src, mk)], "",
                        r2c_edges[(src, mk)]["foreign_status"]])
    report["historical"] = {
        "round1_dir": R1, "round1_edges": len(r1_keys),
        "r2c_dir": R2C, "r2c_edges": len(r2c_keys),
        "removed": len(removed_h), "added": len(added_h),
        "equation": "%d - %d + %d = %d (实际 %d)" % (
            len(r1_keys), len(removed_h), len(added_h),
            len(r1_keys) - len(removed_h) + len(added_h), len(r2c_keys)),
        "round1_manifest_edges": 330362,
        "round1_reported_self_excluded": 1366,
        "residual_note": ("round-1 报告的 −1,366 是自引剔除的**净效果假设**；"
                          "实际净变化 = removed+added 的合成，见分类统计"),
        "removed_by_category": dict(Counter(
            cat_h[("removed", s, m)] for s, m in removed_h)),
        "added_by_category": dict(Counter(
            cat_h[("added", s, m)] for s, m in added_h)),
    }

    # ---------- 7.2 本轮：r2c → r2d ----------
    removed_c = r2c_keys - set(r2d_edges)
    added_c = set(r2d_edges) - r2c_keys
    cat_c = edge_categories(removed_c, added_c, r2d_edges, r2c_edges, None, None)
    with open(os.path.join(outdir, "current_edge_delta_r2c_to_r2d.csv"),
              "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["direction", "source_decision", "mention_detail_key",
                    "category", "r2c_foreign_status", "r2d_foreign_status",
                    "r2c_edge_support", "r2d_edge_support"])
        for (src, mk) in sorted(removed_c):
            w.writerow(["removed", src, mk, cat_c[("removed", src, mk)],
                        r2c_edges[(src, mk)]["foreign_status"], "",
                        r2c_edges[(src, mk)].get("edge_support", ""), ""])
        for (src, mk) in sorted(added_c):
            w.writerow(["added", src, mk, cat_c[("added", src, mk)], "",
                        r2d_edges[(src, mk)]["foreign_status"], "",
                        r2d_edges[(src, mk)].get("edge_support", "")])
    fsc = lambda run: Counter(
        e["foreign_status"] for e in load_edges(run).values())
    report["current_edges"] = {
        "r2c_edges": len(r2c_keys), "r2d_edges": len(r2d_edges),
        "removed": len(removed_c), "added": len(added_c),
        "foreign_status_r2c": dict(fsc(R2C)),
        "foreign_status_r2d": dict(fsc(r2d)),
        "removed_by_category": dict(Counter(
            cat_c[("removed", s, m)] for s, m in removed_c)),
        "added_by_category": dict(Counter(
            cat_c[("added", s, m)] for s, m in added_c)),
    }

    # ---------- 组级：身份降级 / 组来源变化 ----------
    _, g2c = groups_of(R2C)
    _, g2d = groups_of(r2d)
    down_rows = []
    origin_changes = []
    matched = 0
    for mkey in sorted(set(g2c) & set(g2d), key=lambda k: sorted(k)[:1]):
        matched += 1
        gid_c, ms_c = g2c[mkey]
        gid_d, ms_d = g2d[mkey]
        p_c = next((m for m in ms_c if m["is_primary"] == "true"), ms_c[0])
        p_d = next((m for m in ms_d if m["is_primary"] == "true"), ms_d[0])
        if p_c.get("identity_basis") == "same_citation" \
                and p_d.get("identity_basis") != "same_citation":
            down_rows.append({"member_keys": ";".join(sorted(mkey)[:5]),
                              "r2c_basis": p_c["identity_basis"],
                              "r2d_basis": p_d["identity_basis"],
                              "r2c_group_origin": p_c["group_origin_status"],
                              "r2d_group_origin": p_d["group_origin_status"]})
        if (p_c["group_origin_status"], p_c["group_origin_country"]) != \
                (p_d["group_origin_status"], p_d["group_origin_country"]):
            origin_changes.append({
                "member_keys": ";".join(sorted(mkey)[:5]),
                "r2c_status": p_c["group_origin_status"],
                "r2c_country": p_c["group_origin_country"],
                "r2d_status": p_d["group_origin_status"],
                "r2d_country": p_d["group_origin_country"],
                "r2c_evidence": p_c["group_origin_evidence_ids"],
                "r2d_evidence": p_d["group_origin_evidence_ids"]})
    with open(os.path.join(outdir, "identity_basis_downgrades.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["member_keys", "r2c_basis",
                                          "r2d_basis", "r2c_group_origin",
                                          "r2d_group_origin"])
        w.writeheader()
        w.writerows(down_rows)
    with open(os.path.join(outdir, "group_origin_changes.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["member_keys", "r2c_status",
                                          "r2c_country", "r2d_status",
                                          "r2d_country", "r2c_evidence",
                                          "r2d_evidence"])
        w.writeheader()
        w.writerows(origin_changes)
    report["groups"] = {
        "r2c_groups": len(g2c), "r2d_groups": len(g2d),
        "member_set_matched": matched,
        "same_citation_primary_downgrades": len(down_rows),
        "group_origin_changes": len(origin_changes)}

    # ---------- 仲裁状态变化（逐 candidate_id）----------
    m2c, m2d = {}, {}
    for court in COURTS:
        for m in rows(os.path.join(R2C, "merge_out", court,
                                   "mentions_candidates.csv")):
            m2c[m["candidate_id"]] = m
        for m in rows(os.path.join(r2d, "merge_out", court,
                                   "mentions_candidates.csv")):
            m2d[m["candidate_id"]] = m
    arb_changes = []
    recycled = []
    for cid in sorted(set(m2c) & set(m2d)):
        a, b = m2c[cid]["arbitration_status"], m2d[cid]["arbitration_status"]
        if a != b:
            arb_changes.append({
                "candidate_id": cid, "court": m2c[cid]["candidate_id"].split(":")[0],
                "raw_string": m2c[cid]["raw_string"],
                "r2c_status": a, "r2d_status": b,
                "r2d_superseded_by": m2d[cid].get("superseded_by_candidate", ""),
                "jurisdiction": m2c[cid].get("jurisdiction", ""),
                "shape": m2c[cid].get("shape_name", "")})
            if a in ("span_alternative_undecided", "overlap_undecided",
                     "alternative_spanning_mismatch") and b == "counted":
                recycled.append(arb_changes[-1])
    with open(os.path.join(outdir, "arbitration_status_changes.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(arb_changes[0].keys())
                           if arb_changes else ["candidate_id"])
        w.writeheader()
        w.writerows(arb_changes)
    with open(os.path.join(outdir, "recycled_weak_candidates.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(arb_changes[0].keys())
                           if arb_changes else ["candidate_id"])
        w.writeheader()
        w.writerows(recycled)
    cc = Counter((c["r2c_status"], c["r2d_status"]) for c in arb_changes)
    report["arbitration"] = {
        "candidates_both_runs": len(set(m2c) & set(m2d)),
        "status_changes": len(arb_changes),
        "transitions": {("%s -> %s" % k): v for k, v in cc.most_common()},
        "recycled_weak_to_counted": len(recycled)}

    # ---------- 外国边变化 ----------
    fe_c = {(e["source_decision"], e["resolved_cited_case"]): e
            for e in rows(os.path.join(R2C, "edges", "foreign_edges.csv"))}
    fe_d = {(e["source_decision"], e["resolved_cited_case"]): e
            for e in rows(os.path.join(r2d, "edges", "foreign_edges.csv"))}
    fe_rows = []
    for k in sorted(set(fe_c) | set(fe_d)):
        a, b = fe_c.get(k), fe_d.get(k)
        if a and b and a["foreign_status"] == b["foreign_status"] \
                and a["origin_country"] == b["origin_country"] \
                and a["edge_support"] == b["edge_support"]:
            continue
        fe_rows.append({
            "source_decision": k[0],
            "r2c": json.dumps({x: (a or {}).get(x) for x in
                               ("foreign_status", "origin_country", "edge_support")},
                              ensure_ascii=False),
            "r2d": json.dumps({x: (b or {}).get(x) for x in
                               ("foreign_status", "origin_country", "edge_support")},
                              ensure_ascii=False),
            "case_name": (a or b or {}).get("case_name_modal", "")})
    with open(os.path.join(outdir, "foreign_edge_changes.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source_decision", "r2c", "r2d",
                                          "case_name"])
        w.writeheader()
        w.writerows(fe_rows)
    report["foreign_edges"] = {"r2c": len(fe_c), "r2d": len(fe_d),
                               "changed_rows": len(fe_rows)}

    # spanning 联合依据变化（以 spanning_mismatch 状态的候选计）
    sp_c = {cid for cid, m in m2c.items()
            if m["arbitration_status"] == "alternative_spanning_mismatch"}
    sp_d = {cid for cid, m in m2d.items()
            if m["arbitration_status"] == "alternative_spanning_mismatch"}
    report["spanning"] = {"r2c_spanning_mismatch": len(sp_c),
                          "r2d_spanning_mismatch": len(sp_d),
                          "exits": len(sp_c - sp_d), "entries": len(sp_d - sp_c)}
    with open(os.path.join(outdir, "spanning_joint_basis_changes.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["direction", "candidate_id", "raw_string"])
        for cid in sorted(sp_c - sp_d):
            w.writerow(["exited_spanning", cid, m2c[cid]["raw_string"]])
        for cid in sorted(sp_d - sp_c):
            w.writerow(["entered_spanning", cid, m2d[cid]["raw_string"]])

    # ---------- 7.3/7.4：43 与 761 的固定与追踪 ----------
    old_counted = []
    for court in COURTS:
        for r in rows(os.path.join(OLD := os.path.join(ROOT, "data"),
                                   "classify_out", court, "classified.csv")):
            if not r.get("rejected_reason") and r.get("self_citation") != "true":
                old_counted.append((court, r))
    def jk(r):
        return (r["source_decision_citation"], r["match_start_offset"],
                r["match_end_offset"], r["shape_name"], r["raw_string"])
    def counted_keys_and_status(run):
        ck, st = set(), {}
        for court in COURTS:
            for m in rows(os.path.join(run, "merge_out", court,
                                       "mentions_candidates.csv")):
                k = (m["source_decision_citation"], m["match_start_offset"],
                     m["match_end_offset"], m["shape_name"], m["raw_string"])
                if m["arbitration_status"] == "counted":
                    ck.add(k)
                st.setdefault(k, []).append(m["arbitration_status"])
        return ck, st
    r2c_ck, r2c_st = counted_keys_and_status(R2C)
    r2d_ck, r2d_st = counted_keys_and_status(r2d)
    from bisect import bisect_left
    ivs_by_sdc = defaultdict(list)
    for (sdc, s0, e0, _sh, _rw) in r2c_ck:
        ivs_by_sdc[sdc].append((int(s0), int(e0)))
    for s_ in ivs_by_sdc:
        ivs_by_sdc[s_].sort()
    starts_by = {s_: [x[0] for x in v] for s_, v in ivs_by_sdc.items()}
    lost43, ov761 = [], []
    for court, r in old_counted:
        k = jk(r)
        if k in r2c_ck:
            continue
        s_, e_ = int(r["match_start_offset"]), int(r["match_end_offset"])
        sdc = r["source_decision_citation"]
        ivs = ivs_by_sdc.get(sdc, [])
        sts = starts_by.get(sdc, [])
        j = bisect_left(sts, e_)
        i0 = j
        while i0 > 0 and sts[i0 - 1] > s_ - 300:
            i0 -= 1
        overlap = any(iv[0] < e_ and s_ < iv[1] for iv in ivs[i0:j])
        base = {
            "court": court,
            "source_decision_citation": sdc,
            "match_start_offset": r["match_start_offset"],
            "match_end_offset": r["match_end_offset"],
            "shape_name": r["shape_name"],
            "raw_string": r["raw_string"],
            "old_jurisdiction": r.get("jurisdiction", ""),
            "old_supported": "yes" if r.get("jurisdiction") not in (
                "", "UNSUPPORTED") else "no",
            "r2c_status": "+".join(sorted(set(r2c_st.get(k, ["<not_enumerated>"])))),
        }
        if not overlap and base["old_supported"] == "yes":
            base["r2d_status"] = "+".join(sorted(set(r2d_st.get(k, ["<not_enumerated>"]))))
            base["r2d_counted"] = "yes" if k in r2d_ck else "no"
            base["human_verified"] = ""
            base["note"] = ""
            lost43.append(base)
        elif overlap:
            base["r2d_status"] = "+".join(sorted(set(r2d_st.get(k, ["<not_enumerated>"]))))
            base["r2d_counted"] = "yes" if k in r2d_ck else "no"
            base["semantic_equivalence"] = "unverified (overlap only)"
            base["note"] = ""
            ov761.append(base)
    for name, data in (("r2c_supported_lost_43.csv", lost43),
                       ("r2c_overlap_only_761.csv", ov761)):
        with open(os.path.join(outdir, name), "w", encoding="utf-8",
                  newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0].keys()) if data
                               else ["court"])
            w.writeheader()
            w.writerows(data)
    report["tracked_sets"] = {
        "supported_lost_frozen": len(lost43),
        "supported_lost_counted_in_r2d": sum(1 for x in lost43
                                             if x["r2d_counted"] == "yes"),
        "overlap_only_frozen": len(ov761),
        "overlap_only_counted_in_r2d": sum(1 for x in ov761
                                           if x["r2d_counted"] == "yes")}

    with open(os.path.join(outdir, "r2d_closure_summary.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1)[:5000])


if __name__ == "__main__":
    main(sys.argv[1])
