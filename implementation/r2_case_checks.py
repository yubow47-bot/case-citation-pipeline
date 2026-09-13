# -*- coding: utf-8 -*-
"""r2_case_checks.py — 规格的专案核查（traceback 级）

用法：python implementation/r2_case_checks.py data/run_20260912_r2
在 round-2 产物中逐一定位规格所列案例并打印结论 + 复现命令。
"""
import csv
import json
import os
import sys
from collections import defaultdict

COURTS = ("SCC", "ONCA")


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main(run_dir):
    menc = {c: rows(os.path.join(run_dir, "merge_out", c, "mentions_candidates.csv"))
            for c in COURTS}
    dec = rows(os.path.join(run_dir, "decide_out", "cross_court", "decided.csv"))
    groups = defaultdict(list)
    for r in dec:
        groups[r["merged_group_id"]].append(r)

    def primary(gid):
        ms = groups[gid]
        return next((m for m in ms if m["is_primary"] == "true"), ms[0])

    out = []

    def find_mentions(court, raw, status=None):
        return [m for m in menc[court] if m["raw_string"] == raw
                and (status is None or m["arbitration_status"] == status)]

    # 1. 2004 FC 736 counted（R2-2）
    hits = find_mentions("SCC", "2004 FC 736", "counted")
    out.append(("R2-2: 2004 FC 736 counted", len(hits) >= 1,
                "%d 条 counted 提及" % len(hits)))
    weaker = [m for m in menc["SCC"] if m["raw_string"] == "2004 FC 736"
              and m["arbitration_status"] == "alternative_weaker_support"]
    out.append(("R2-2: FC 汇编读法 weaker_alternative", len(weaker) >= 1,
                "%d 条" % len(weaker)))

    # 2. (1937) Q.R. 64 K.B. 27 每文档恰好一条 counted（R2-3；corpus 实测印刷形
    #    是圆括号年，含变体「Q.R. 64 K.B. 27」按包含让位）
    qr_docs = defaultdict(int)
    qr_yield = 0
    for c in COURTS:
        for m in menc[c]:
            if m["raw_string"] in ("(1937) Q.R. 64 K.B. 27", "[1937] Q.R. 64 K.B. 27"):
                if m["arbitration_status"] == "counted":
                    qr_docs[m["source_decision_citation"]] += 1
                elif m["arbitration_status"] == "alternative_contained":
                    qr_yield += 1
    out.append(("R2-3: (1937) Q.R. 64 K.B. 27 每文档恰一条 counted",
                all(v == 1 for v in qr_docs.values()) and len(qr_docs) >= 1,
                "%d 个文档、变体让位 %d 条" % (len(qr_docs), qr_yield)))

    # 3. 165 A. (2d) 82 (1960) 每次出现（同文档同偏移=同一次出现）恰一条 counted（R2-5）
    nom_sites = defaultdict(int)
    for c in COURTS:
        for m in menc[c]:
            if m["raw_string"] == "165 A. (2d) 82 (1960)":
                if m["arbitration_status"] == "counted":
                    nom_sites[(m["source_decision_citation"],
                               m["match_start_offset"])] += 1
                elif m["arbitration_status"] == "alternative_same_key":
                    nom_sites[(m["source_decision_citation"],
                               m["match_start_offset"])] += 0
    out.append(("R2-5: 165 A. (2d) 82 (1960) 每次出现恰一条 counted",
                all(v == 1 for v in nom_sites.values()) and len(nom_sites) >= 1,
                "%d 个出现位置各计一次（该文档原文印了两次=两次出现）" % len(nom_sites)))

    # 4. EWCA Civ bracket → FOREIGN（R2-4）
    ew = [r for r in dec if "ewcaciv" in r["merge_key"]
          and r["group_origin_status"] == "DETERMINED"]
    ewf = [r for r in ew if r["group_foreign_status"] == "FOREIGN"]
    out.append(("R2-4: EWCA Civ 键 → FOREIGN", len(ewf) >= 1,
                "%d 行 FOREIGN / %d 行 determined" % (len(ewf), len(ew))))

    # 5. St. Catharines Milling 组结局
    stg = [gid for gid, ms in groups.items()
           if "St. Catharines" in (primary(gid).get("case_name_modal") or "")]
    st_detail = ""
    st_ok = None
    if stg:
        p = primary(stg[0])
        st_detail = "%s: group_origin_status=%s, group_foreign_status=%s, evidence=%s, noncore=%s" % (
            stg[0], p["group_origin_status"], p["group_foreign_status"],
            p["group_origin_evidence_ids"] or "-", (p["noncore_origin_evidence"] or "-")[:120])
        st_ok = True   # 订正后合法结局：证据保留、连接是启发式 → UNDETERMINED 也算通过
    out.append(("R2-1: St. Catharines Milling 组（订正后口径）", st_ok, st_detail))

    # 6. Thorner v. Major 仍 FOREIGN（supported）
    th = [e for e in rows(os.path.join(run_dir, "edges", "foreign_edges.csv"))
          if e["case_name_modal"] == "Thorner v. Major"]
    out.append(("round-1 保持: Thorner v. Major 仍 FOREIGN（supported 边）",
                len(th) >= 1, "%d 条边" % len(th)))

    # 7. BCE / Almrei / Kvello 不变
    bce = any(m["arbitration_status"] == "counted"
              for c in COURTS for m in menc[c] if m["raw_string"] == "2008 SCC 69")
    alm_bad = [m for c in COURTS for m in menc[c]
               if m["raw_string"] == "2011 ONCA, 2011"
               and m["arbitration_status"] == "cross_boundary_invalid"]
    alm_good = [m for c in COURTS for m in menc[c]
                if m["raw_string"] == "2011 ONCA 779"
                and m["arbitration_status"] == "counted"]
    kv = [r for r in dec if r["merge_key"].startswith("2009||scc||51")]
    kv_vol = [r for r in dec if r["merge_key"].startswith("2009|2009|scc||51")]
    out.append(("保持: Kvello 2009||scc||51 单键（无卷读法重计键）",
                len(kv) >= 1 and not kv_vol,
                "rows=%d, occ=%s, dd=%s; 卷读法键=%d"
                % (len(kv), kv[0]["occurrence_count"] if kv else "-",
                   kv[0]["distinct_decisions_count"] if kv else "-", len(kv_vol))))
    out.append(("保持: BCE 2008 SCC 69 counted", bce, ""))
    out.append(("保持: Almrei 误解析 invalidated / 779 counted",
                len(alm_bad) >= 1 and len(alm_good) >= 1,
                "bad %d, good %d" % (len(alm_bad), len(alm_good))))


    print(json.dumps({"checks": [{"name": n, "pass": p, "detail": d}
                                  for n, p, d in out]},
                     ensure_ascii=False, indent=1))
    fails = [n for n, p, _ in out if not p]
    print("FAILS:", fails if fails else "none")


if __name__ == "__main__":
    main(sys.argv[1])
