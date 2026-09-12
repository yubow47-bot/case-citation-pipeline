# -*- coding: utf-8 -*-
"""edges.py — 引证边输出（阶段 4）

一条边 = (source_decision, resolved_cited_case)：同一份判决对同一案件身份
（跨院裁定后的 merged_group_id）的全部提及折叠成一条边；提及级细节经
(court, merge_key, candidate_id) 与 merge_out/*/mentions_candidates.csv 保持
链接，不丢失。

用法
    python pipeline/edges.py --decided data/run_X/decide_out/cross_court/decided.csv \
        --merge-out data/run_X/merge_out --output data/run_X/edges

输出
    <output>/citation_edges.csv   全部边（国内/外国/未知/冲突都保留）
    <output>/foreign_edges.csv    foreign_status=FOREIGN 的过滤视图（唯一筛选差异）
    <output>/manifest.json        参数与计数（约束九）

边字段：source_decision, resolved_cited_case, origin_country, foreign_status,
identity_status, origin_basis, origin_evidence_id, mention_count, dd, case_name_modal,
mention_detail_key（= court|merge_key，可回连 mentions_candidates.csv 逐候选台账）。

identity_status：unanchored（裁定层无中立锚的拼组）/ anchored（其余）。
select 的 dd 门槛语义与本层无关——本层不设 kept、不过滤国内边（约束六）。
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EDGE_FIELDS = ["source_decision", "resolved_cited_case", "origin_country",
               "foreign_status", "identity_status", "origin_basis",
               "origin_evidence_id", "mention_count", "distinct_decisions_count",
               "case_name_modal", "mention_detail_key"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--decided", required=True,
                    help="decide 跨法院轮 decided.csv")
    ap.add_argument("--merge-out", required=True,
                    help="merge_out 根目录（其下 SCC/ONCA 有 mentions_candidates.csv）")
    ap.add_argument("--output", required=True)
    a = ap.parse_args()

    # (court, merge_key) -> 组级属性（origin 等，取自主行）
    group_attr = {}
    row2group = {}
    groups = {}
    with open(a.decided, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            row2group[(r.get("court") or "", r["merge_key"])] = r["merged_group_id"]
            g = groups.setdefault(r["merged_group_id"], {"foreign_status": "",
                                                         "origin_country": "",
                                                         "identity_status": "anchored",
                                                         "origin_basis": "",
                                                         "origin_evidence_id": "",
                                                         "case_name_modal": "",
                                                         "dd": 0})
            if r.get("is_primary") == "true":
                g["foreign_status"] = r.get("foreign_status") or ""
                g["origin_country"] = r.get("origin_country") or ""
                g["origin_basis"] = r.get("origin_basis") or ""
                g["origin_evidence_id"] = r.get("origin_evidence_id") or ""
                g["case_name_modal"] = r.get("case_name_modal") or ""
                g["dd"] = int(r["distinct_decisions_count"] or 0)
            if "unanchored" in (r.get("split_reason") or ""):
                g["identity_status"] = "unanchored"

    # 逐候选提及 → 边
    edges = defaultdict(list)          # (source_decision, group) -> [mention keys]
    stats = Counter()
    for court in ("SCC", "ONCA"):
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
                    # 院内键若不在跨院产出（不应发生），显式计数不静默
                    stats["mentions_without_group"] += 1
                    continue
                sd = m["source_decision_citation"]
                edges[(sd, gid)].append("%s|%s" % (court, m["merge_key"]))
                stats["mentions_in_edges"] += 1

    os.makedirs(a.output, exist_ok=True)
    all_rows = []
    for (sd, gid), keys in sorted(edges.items()):
        g = groups[gid]
        all_rows.append({
            "source_decision": sd,
            "resolved_cited_case": gid,
            "origin_country": g["origin_country"],
            "foreign_status": g["foreign_status"] or "UNDETERMINED",
            "identity_status": g["identity_status"],
            "origin_basis": g["origin_basis"],
            "origin_evidence_id": g["origin_evidence_id"],
            "mention_count": len(keys),
            "distinct_decisions_count": g["dd"],
            "case_name_modal": g["case_name_modal"],
            "mention_detail_key": ";".join(sorted(set(keys))),
        })
    stats["edges_total"] = len(all_rows)
    fc = Counter(r["foreign_status"] for r in all_rows)
    stats["edges_foreign"] = fc["FOREIGN"]
    stats["edges_domestic_ca"] = fc["DOMESTIC_CA"]
    stats["edges_undetermined"] = fc["UNDETERMINED"]
    stats["edges_conflict"] = fc["CONFLICT"]

    for name, rows in (("citation_edges.csv", all_rows),
                       ("foreign_edges.csv",
                        [r for r in all_rows if r["foreign_status"] == "FOREIGN"])):
        path = os.path.join(a.output, name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=EDGE_FIELDS)
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, path)

    manifest = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "decided_input": a.decided,
        "stats": dict(sorted(stats.items())),
        "note": ("foreign_edges.csv 只是 foreign_status=FOREIGN 的过滤视图；"
                 "select 的 dd 门槛不进本层（约束六）"),
    }
    with open(os.path.join(a.output, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    print("edges: %d (FOREIGN %d / DOMESTIC_CA %d / UNDETERMINED %d / CONFLICT %d)"
          % (stats["edges_total"], stats["edges_foreign"], stats["edges_domestic_ca"],
             stats["edges_undetermined"], stats["edges_conflict"]))
    for k, v in sorted(stats.items()):
        print("   %-28s %d" % (k, v))


if __name__ == "__main__":
    main()
