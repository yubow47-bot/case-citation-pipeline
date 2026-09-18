# -*- coding: utf-8 -*-
"""edges.py — 引证边输出（R2-1/R2-9 订正后的溯源契约）

一条边 = (source_decision, resolved_cited_case=merged_group_id)。
**边成员资格只来自 decide 的 effective_sources.csv**（decide 是唯一权威）：
  * status=counted 的来源 → 普通边；
  * status=excluded_self（组自身判决经身份根剔除）→ **不**作为普通边重现，
    保留在 self_excluded_edges.csv 供审计；
  * 每组 counted 来源数 == 该组 dd（同一口径，写表前断言）。

边级 foreign_status 反映**该边实际走的成员路径**（R2-1 订正）：
  * 路径的最优 identity_basis 属于 ELIGIBLE_BASES（anchor/singleton/
    same_citation/anchor_variant_bilingual）→ supported：组级结论适用，
    foreign_status = 组的 group_foreign_status；
  * 只有启发式路径（name_year / cocitation / unanchored / typo 变体）→
    heuristic_only：**不得**继承组 FOREIGN/DOMESTIC——foreign_status=UNDETERMINED，
    组结论保留在 group_origin_* 列作上下文，候选关系写进 tentative_edges.csv。

用法
    python pipeline/edges.py --decided data/run_X/decide_out/cross_court/decided.csv \
        --effective data/run_X/decide_out/cross_court/effective_sources.csv \
        --merge-out data/run_X/merge_out --output data/run_X/edges
"""
import argparse
import csv
import datetime
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import nk                                      # noqa: E402
from decide import ELIGIBLE_BASES                             # noqa: E402  (R2 闭环 4.4 共享契约)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EDGE_FIELDS = ["source_decision", "resolved_cited_case", "foreign_status",
               "origin_country", "group_origin_country", "group_origin_status",
               "group_foreign_status", "edge_support", "identity_status",
               "origin_basis", "origin_evidence_ids", "noncore_origin_evidence",
               "mention_count", "distinct_decisions_count",
               "case_name_modal", "mention_detail_key"]

TENTATIVE_FIELDS = ["source_decision", "resolved_cited_case", "identity_status",
                    "group_origin_country", "group_foreign_status",
                    "origin_evidence_ids", "mention_count",
                    "case_name_modal"]


def basis_of(identity_status):
    # R2 闭环 4.4：资格集合来自 decide.ELIGIBLE_BASES（同一来源，防止漂移）
    return identity_status in ELIGIBLE_BASES


def candidate_label(identity_status):
    return {"cocitation": "cocitation_candidate", "unanchored": "cocitation_candidate",
            "name_year": "name_year_candidate",
            "anchor_variant_typo": "typo_variant_candidate"}.get(
        identity_status, identity_status)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--decided", required=True)
    ap.add_argument("--effective", required=True,
                    help="decide 跨法院轮 effective_sources.csv（R2-9 唯一成员资格来源）")
    ap.add_argument("--merge-out", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()

    # 组级属性（每行都带组结论，取任一行即可）
    group_attr = {}
    row2group = {}
    with open(a.decided, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            row2group[(r.get("court") or "", r["merge_key"])] = r["merged_group_id"]
            g = group_attr.setdefault(r["merged_group_id"], {
                "group_foreign_status": r.get("group_foreign_status") or "UNDETERMINED",
                "group_origin_country": r.get("group_origin_country") or "",
                "group_origin_status": r.get("group_origin_status") or "UNDETERMINED",
                "group_origin_basis": r.get("group_origin_basis") or "",
                "group_origin_evidence_ids": r.get("group_origin_evidence_ids") or "",
                "noncore_origin_evidence": r.get("noncore_origin_evidence") or "",
                "case_name_modal": r.get("case_name_modal") or "",
                "dd": int(r["distinct_decisions_count"] or 0),
            })
    # 决策组的组级列是逐行一致的——不一致即上游违约，拒绝写表
    bad = 0
    with open(a.decided, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            g = group_attr[r["merged_group_id"]]
            if (r.get("group_foreign_status") or "UNDETERMINED") != g["group_foreign_status"] \
                    or (r.get("group_origin_country") or "") != g["group_origin_country"]:
                bad += 1
    assert bad == 0, "组级 foreign_status/origin_country 逐行不一致（%d 行）——上游违约" % bad

    # 逐候选提及（counted）→ (source, group) 提及数；提及细节经 mention_detail_key 回连
    mention_edges = defaultdict(list)
    stats = Counter()
    for court in sorted(d for d in os.listdir(a.merge_out)
                        if os.path.isdir(os.path.join(a.merge_out, d))):
        path = os.path.join(a.merge_out, court, "mentions_candidates.csv")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", newline="") as f:
            for m in csv.DictReader(f):
                stats["mentions_scanned"] += 1
                if m["arbitration_status"] != "counted":
                    continue
                gid = row2group.get((court, m["merge_key"]))
                if gid is None:
                    stats["mentions_without_group"] += 1
                    continue
                mention_edges[(m["source_decision_citation"], gid)].append(
                    "%s|%s" % (court, m["merge_key"]))
                stats["mentions_in_edges"] += 1

    # 有效来源关联 → 边
    all_rows, tentative, self_excluded = [], [], []
    per_group_counted = Counter()
    with open(a.effective, encoding="utf-8", newline="") as f:
        for e in csv.DictReader(f):
            gid = e["merged_group_id"]
            g = group_attr.get(gid)
            if g is None:
                stats["effective_rows_without_group"] += 1
                continue
            if e["status"] != "counted":
                self_excluded.append({
                    "source_decision": e["source_decision"],
                    "resolved_cited_case": gid,
                    "exclusion_reason": e["exclusion_reason"],
                    "identity_status": e["identity_status"],
                    "mention_count": len(mention_edges.get(
                        (e["source_decision"], gid), [])),
                })
                stats["self_excluded_sources"] += 1
                continue
            per_group_counted[gid] += 1
            supported = basis_of(e["identity_status"])
            mkey = (e["source_decision"], gid)
            row = {
                "source_decision": e["source_decision"],
                "resolved_cited_case": gid,
                "foreign_status": g["group_foreign_status"] if supported
                else "UNDETERMINED",
                "origin_country": g["group_origin_country"] if supported else "",
                "group_origin_country": g["group_origin_country"],
                "group_origin_status": g["group_origin_status"],
                "group_foreign_status": g["group_foreign_status"],
                "edge_support": "supported" if supported else "heuristic_only",
                "identity_status": (e["identity_status"] if supported
                                    else candidate_label(e["identity_status"])),
                "origin_basis": g["group_origin_basis"] if supported else "",
                "origin_evidence_ids": g["group_origin_evidence_ids"] if supported else "",
                "noncore_origin_evidence": g["noncore_origin_evidence"],
                "mention_count": len(mention_edges.get(mkey, [])),
                "distinct_decisions_count": g["dd"],
                "case_name_modal": g["case_name_modal"],
                "mention_detail_key": ";".join(sorted(set(mention_edges.get(mkey, [])))),
            }
            all_rows.append(row)
            if not supported and g["group_origin_status"] == "DETERMINED":
                tentative.append({k: row[k] for k in TENTATIVE_FIELDS})
                stats["tentative_edges"] += 1

    # 不变量：每组 counted 来源数 == dd（同口径）
    bad = [gid for gid, g in group_attr.items()
           if per_group_counted[gid] != g["dd"]]
    assert not bad, "R2-9 违约：%d 个组的 counted 来源数 != dd，如 %r" % (
        len(bad), bad[:5])

    stats["edges_total"] = len(all_rows)
    fc = Counter(r["foreign_status"] for r in all_rows)
    stats["edges_foreign"] = fc["FOREIGN"]
    stats["edges_domestic_ca"] = fc["DOMESTIC_CA"]
    stats["edges_undetermined"] = fc["UNDETERMINED"]
    stats["edges_conflict"] = fc["CONFLICT"]
    sc = Counter(r["edge_support"] for r in all_rows)
    stats["edges_supported"] = sc["supported"]
    stats["edges_heuristic_only"] = sc["heuristic_only"]

    os.makedirs(a.output, exist_ok=True)
    for name, fields, rows in (("citation_edges.csv", EDGE_FIELDS, all_rows),
                               ("foreign_edges.csv", EDGE_FIELDS,
                                [r for r in all_rows if r["foreign_status"] == "FOREIGN"]),
                               ("tentative_edges.csv", TENTATIVE_FIELDS, tentative),
                               ("self_excluded_edges.csv",
                                ["source_decision", "resolved_cited_case",
                                 "exclusion_reason", "identity_status",
                                 "mention_count"], self_excluded)):
        path = os.path.join(a.output, name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, path)

    manifest = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "decided_input": a.decided,
        "effective_input": a.effective,
        "stats": dict(sorted(stats.items())),
        "note": ("边成员资格只来自 decide 的 effective_sources（R2-9）；"
                 "foreign_edges 只含 supported 路径的 FOREIGN 边（R2-1 订正）；"
                 "select 的 dd 门槛不进本层（约束六）"),
    }
    with open(os.path.join(a.output, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    print("edges: %d (FOREIGN %d / DOMESTIC_CA %d / UNDETERMINED %d / CONFLICT %d; "
          "supported %d / heuristic_only %d)"
          % (stats["edges_total"], stats["edges_foreign"], stats["edges_domestic_ca"],
             stats["edges_undetermined"], stats["edges_conflict"],
             stats["edges_supported"], stats["edges_heuristic_only"]))
    for k, v in sorted(stats.items()):
        print("   %-28s %d" % (k, v))


if __name__ == "__main__":
    main()
