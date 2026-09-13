# -*- coding: utf-8 -*-
"""r2f_verify.py — identifier 轮验证（任务书第 5 节项 1-5、8）

用法：python implementation/r2f_verify.py <r2f_run_dir> <r2e_run_dir>
"""
import csv
import json
import os
import sys
from bisect import bisect_left
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import merge as _m                      # noqa: E402
import decide as _d                     # noqa: E402
from normalize import nk                # noqa: E402

COURTS = ("SCC", "ONCA")


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def jk(m):
    return (m["source_decision_citation"], m["match_start_offset"],
            m["match_end_offset"], m["shape_name"], m["raw_string"])


def token_of(m):
    p = m["merge_key"].split("|")
    return p[2] if len(p) > 2 else ""


def main(r2f, r2e):
    R = {}
    # ---------- 候选台账 ----------
    men_e, men_f = {}, {}
    cand_e, cand_f = {}, {}
    for court in COURTS:
        for m in rows(os.path.join(r2e, "merge_out", court,
                                   "mentions_candidates.csv")):
            men_e[jk(m)] = m
        for m in rows(os.path.join(r2f, "merge_out", court,
                                   "mentions_candidates.csv")):
            men_f[jk(m)] = m
    for court in COURTS:
        for c in rows(os.path.join(r2e, "extract_out", "candidates.csv")):
            cand_e[(court, c["corpus_row_index"], c["match_start_offset"],
                    c["match_end_offset"], c["shape_name"])] = c
        for c in rows(os.path.join(r2f, "extract_out", "candidates.csv")):
            cand_f[(court, c["corpus_row_index"], c["match_start_offset"],
                    c["match_end_offset"], c["shape_name"])] = c

    # ---------- 3. 跨度集合恒等（全语料）----------
    set_e = set(cand_e)
    set_f = set(cand_f)
    R["span_set_identity"] = {
        "r2e_spans": len(set_e), "r2f_spans": len(set_f),
        "differences": len(set_e ^ set_f), "target": 0,
        "note": "键 = (court, corpus_row_index, start, end, shape)",
    }

    # ---------- 1. 每 token 状态 before → after ----------
    ident_tokens = set(_d.load_identifier_systems())
    per_tok = defaultdict(Counter)
    for k, m in men_f.items():
        tok = token_of(m).lower()
        if tok in ident_tokens:
            per_tok[tok][m["arbitration_status"]] += 1
    for k, m in men_e.items():
        tok = token_of(m).lower()
        if tok in ident_tokens:
            per_tok[tok]["r2e_" + m["arbitration_status"]] += 1
    R["per_token_r2f"] = {t: dict(c.most_common()) for t, c in
                          sorted(per_tok.items(), key=lambda kv: -sum(kv[1].values()))}

    # ---------- 2. 爆半径 ----------
    containers = {cid for cid, c in
                  ((c["candidate_id"], c) for c in
                   (r for courts_rows in [] for r in courts_rows))}  # 占位，下行重算
    containers = set()
    partners = set()
    for court in COURTS:
        for c in rows(os.path.join(r2f, "extract_out", "candidates.csv")):
            if c.get("structural_conflict") == "year_reread_as_vol":
                containers.add(c["candidate_id"])
                partners.add(c["conflict_with_candidate"])
    twins = set()
    pos_index = defaultdict(list)
    for court in COURTS:
        for m in rows(os.path.join(r2f, "merge_out", court,
                                   "mentions_candidates.csv")):
            pos_index[(m["source_decision_citation"], m["corpus_row_index"],
                       m["match_start_offset"], m["match_end_offset"])].append(
                m["candidate_id"])
    for p in partners:
        pm = men_f.get(p)
        if not pm:
            continue
        key = (pm["source_decision_citation"], pm["corpus_row_index"],
               pm["match_start_offset"], pm["match_end_offset"])
        twins.update(pos_index.get(key, []))
    related = containers | partners | twins
    # R2F 订正（评审口径）：identifier 系统候选本体同样是 class (i)
    ident_tokens_all = set()
    for r in rows(os.path.join(ROOT, "decisions", "identifier_systems.csv")):
        if (r.get("verification_status") or "").strip().startswith("verified"):
            ident_tokens_all.add(nk(r.get("printed_token") or ""))
    ident_cands = {m["candidate_id"] for m in
                   (men_f[k] for k in men_f)
                   if token_of(m).lower() in ident_tokens_all}
    related = related | ident_cands
    changes = []
    for k in sorted(set(men_e) & set(men_f)):
        a, b = men_e[k]["arbitration_status"], men_f[k]["arbitration_status"]
        if a != b:
            cid = men_f[k]["candidate_id"]
            changes.append({
                "candidate_id": cid,
                "raw_string": men_f[k]["raw_string"],
                "shape": men_f[k]["shape_name"],
                "r2e_status": a, "r2f_status": b,
                "b10_role": ("container" if cid in containers else
                             "partner" if cid in partners else
                             "partner_twin" if cid in twins else "-"),
                "identifier_class": ("i_identifier" if cid in related
                                     else "ii_other")})
    cnt = Counter((c["identifier_class"], c["r2e_status"], c["r2f_status"])
                  for c in changes)
    R["blast_radius"] = {
        "total_changes": len(changes),
        "class_i_identifier_related": sum(1 for c in changes
                                          if c["identifier_class"]
                                          == "i_identifier"),
        "class_ii_other": sum(1 for c in changes
                              if c["identifier_class"] == "ii_other"),
        "class_ii_note": ("(ii) 目标 0；非零条目逐行见 r2f_status_changes.csv，"
                          "须为非 identifier 邻接变化"),
        "transitions": {("%s: %s -> %s" % k): v for k, v in cnt.most_common()},
    }
    os.makedirs(os.path.join(r2f, "audit"), exist_ok=True)
    with open(os.path.join(r2f, "audit", "r2f_status_changes.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(changes[0].keys()) if changes
                           else ["candidate_id"])
        w.writeheader()
        w.writerows(changes)

    # ---------- 4. 旧 counted 行去向 + token 分解 ----------
    old_counted = []
    for court in COURTS:
        for r in rows(os.path.join(ROOT, "data", "classify_out", court,
                                   "classified.csv")):
            if not r.get("rejected_reason") and r.get("self_citation") != "true":
                old_counted.append((court, r))
    ck_e, st_e = {}, {}
    ck_f, st_f = {}, {}
    for court in COURTS:
        for m in rows(os.path.join(r2e, "merge_out", court,
                                   "mentions_candidates.csv")):
            ck_e.setdefault(jk(m), set()).add(m["arbitration_status"])
        for m in rows(os.path.join(r2f, "merge_out", court,
                                   "mentions_candidates.csv")):
            ck_f.setdefault(jk(m), set()).add(m["arbitration_status"])
    ce = {k for k, v in ck_e.items() if "counted" in v}
    cf = {k for k, v in ck_f.items() if "counted" in v}
    fate = Counter()
    lost_by_tok = Counter()
    lost_supported = 0
    ivs = defaultdict(list)
    for k in cf:
        sdc, s0, e0 = k[0], int(k[1]), int(k[2])
        ivs[sdc].append((s0, e0))
    for s_ in ivs:
        ivs[s_].sort()
    starts_by = {s_: [x[0] for x in v] for s_, v in ivs.items()}
    for court, r in old_counted:
        k = jk(r)
        if k in cf:
            fate["1_still_counted"] += 1
            continue
        s_, e_ = int(r["match_start_offset"]), int(r["match_end_offset"])
        sdc = r["source_decision_citation"]
        iv = ivs.get(sdc, [])
        sts = starts_by.get(sdc, [])
        j = bisect_left(sts, e_)
        i0 = j
        while i0 > 0 and sts[i0 - 1] > s_ - 300:
            i0 -= 1
        overlap = any(iv2[0] < e_ and s_ < iv2[1] for iv2 in iv[i0:j])
        if overlap:
            fate["3_overlapping_counted_span_only"] += 1
        else:
            tok = token_of({"merge_key": _m.build_merge_key_v2(r)}).lower()
            fate["4_counted_nowhere"] += 1
            lost_by_tok[tok or "<none>"] += 1
            if r.get("jurisdiction") not in ("", "UNSUPPORTED"):
                lost_supported += 1
    R["old_counted_fate"] = {
        "total": sum(fate.values()),
        "fate": dict(fate), "lost_by_token_top": dict(
            lost_by_tok.most_common(12)),
        "lost_supported_total": lost_supported,
        "r2d_c_reference": {"still": 512044, "overlap": 780, "lost": 5656,
                            "not_enumerated": 0, "lost_supported": 61},
    }

    # ---------- 5/6/7. 组与来源 ----------
    def groups_of(run):
        g = defaultdict(list)
        for r in rows(os.path.join(run, "decide_out", "cross_court",
                                   "decided.csv")):
            g[r["merged_group_id"]].append(r)
        out = {}
        for gid, ms in g.items():
            key = frozenset("%s|%s" % (m.get("court") or "", m["merge_key"])
                            for m in ms)
            p = next((m for m in ms if m["is_primary"] == "true"), ms[0])
            out[key] = {"gid": gid, "dd": int(p["distinct_decisions_count"] or 0),
                        "origin": (p.get("group_origin_status"),
                                   p.get("group_origin_country"))}
        return out

    ge, gf = groups_of(r2e), groups_of(r2f)
    gained_dom = [k for k in set(ge) & set(gf)
                  if ge[k]["origin"][1] != "CA" and gf[k]["origin"][1] == "CA"]
    origin_changed = [k for k in set(ge) & set(gf)
                      if ge[k]["origin"] != gf[k]["origin"]]
    # identifier 组（r2f 新分组的主体）——直接数其 DOMESTIC_CA
    ident_dom, ident_groups = [], []
    for k, v in gf.items():
        gid, ms = None, None
    g_all = defaultdict(list)
    for r in rows(os.path.join(r2f, "decide_out", "cross_court", "decided.csv")):
        g_all[r["merged_group_id"]].append(r)
    for gid, ms in g_all.items():
        ident_keys = [m for m in ms if m.get("citation_kind") == "identifier"]
        if not ident_keys:
            continue
        p = next((m for m in ms if m["is_primary"] == "true"), ms[0])
        ident_groups.append(gid)
        if p.get("group_origin_status") == "DETERMINED" \
                and p.get("group_origin_country") == "CA":
            ident_dom.append({"gid": gid,
                              "evidence": p.get("group_origin_evidence_ids"),
                              "basis": p.get("group_origin_basis"),
                              "keys": ";".join(sorted(
                                  {m["merge_key"] for m in ms})[:3])})
    R["groups"] = {
        "r2e_groups": len(ge), "r2f_groups": len(gf),
        "matched": len(set(ge) & set(gf)),
        "gained_DOMESTIC_CA_matched_only": len(gained_dom),
        "origin_changed_total": len(origin_changed),
        "identifier_groups_r2f": len(ident_groups),
        "identifier_groups_DOMESTIC_CA": len(ident_dom),
        "identifier_dom_samples": ident_dom[:10],
        "gained_dom_samples": [{"keys": ";".join(sorted(k)[:3]),
                                "evidence": gf[k].get("gid")}
                               for k in sorted(gained_dom)[:10]],
    }

    # 同组双 identifier 断言（复核 decide.main 的断言）
    ident_sys = _d.load_identifier_systems()
    viol = 0
    for key, ms in ((None, None),):
        pass
    g2 = defaultdict(list)
    for r in rows(os.path.join(r2f, "decide_out", "cross_court", "decided.csv")):
        g2[r["merged_group_id"]].append(r)
    for gid, ms in g2.items():
        per_sys = defaultdict(set)
        for m in ms:
            if m.get("citation_kind") == "identifier":
                sy = ident_sys.get(token_of(m))
                if sy:
                    per_sys[sy].add(m["merge_key"])
        if any(len(v) > 1 for v in per_sys.values()):
            viol += 1
    R["same_system_assertion"] = {"groups_violating": viol, "target": 0}

    # ---------- 8. 一致性 ----------
    legacy_missing = 0
    cand_by_jk = set()
    for court in COURTS:
        for c in rows(os.path.join(r2f, "extract_out", "candidates.csv")):
            cand_by_jk.add((c["source_decision_citation"],
                            c["match_start_offset"], c["match_end_offset"],
                            c["shape_name"], c["raw_string"]))
    for name in ("extracted.csv", "extracted_superseded.csv"):
        for r in rows(os.path.join(ROOT, "data", "extract_out", name)):
            sdc = r["source_decision_citation"]
            if sdc in ("SCC_", "ONCA_"):
                continue
            k = (sdc, r["match_start_offset"], r["match_end_offset"],
                 r["shape_name"], r["raw_string"])
            if k not in cand_by_jk:
                legacy_missing += 1
    inconsist = 0
    multi = 0
    for gid, ms in g2.items():
        fss = {m.get("group_foreign_status") for m in ms}
        if len(fss) > 1:
            inconsist += 1
        countries = {m.get("member_origin_country") for m in ms
                     if m.get("member_origin_status") == "DETERMINED"
                     and (m.get("member_origin_country") or "").strip()}
        if len(countries) > 1 and ms[0].get("group_origin_status") != "CONFLICT":
            multi += 1
    R["consistency"] = {"legacy_missing": legacy_missing,
                        "rows_inconsistent_origin": inconsist,
                        "multi_country_not_conflict": multi}

    # ---------- 7. kept ----------
    sm = json.load(open(os.path.join(r2f, "select_out", "manifest.json"),
                        encoding="utf-8"))["stats"]
    R["kept"] = {"r2f_kept_groups": sm["groups_kept"],
                 "r2d_c_kept_groups": 8582}

    # ---------- 6. 边 ----------
    def edges_fsc(run):
        ec = Counter(e["foreign_status"] for e in
                     rows(os.path.join(run, "edges", "citation_edges.csv")))
        return dict(ec)
    R["edges"] = {"r2e": edges_fsc(r2e), "r2f": edges_fsc(r2f)}

    out = os.path.join(r2f, "audit", "r2f_verify_summary.json")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
    print("written", out)
    print(json.dumps(R, ensure_ascii=False, indent=1)[:5200])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
