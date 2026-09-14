# -*- coding: utf-8 -*-
"""R3 Stage 4 爆半径仪器（只读）：逐层比较两个 run 目录，给每个变化归因。

用法
    python implementation/r3_blast_radius.py --before data/run_20260913_r2i \
        --after data/run_<new> --out data/coverage_out/r3_blast.json

比较层次（**不假设 merged_group_id 跨版本稳定**——audit/README.md 明说组号会变）：
  1 提及层：candidate_id → arbitration_status（candidate_id 由法院/行/跨度为键，稳定）
  2 成员行层：(court, merge_key) → identity_basis / member_origin_* / 组的**内容签名**
               （= 组内成员 row_key 的排序并集；组号不是键，内容才是）
  3 组层：内容签名 → group_foreign_status（合并/拆分/改判分别计数）
  4 边层：citation_edges.csv 的 foreign_status 分布；foreign_edges.csv、tentative
  5 选取层：selected.csv 的 (court, merge_key) → dd / kept
  6 新增审计量：member_origin_ambiguous_basis = exclusive_reporter_scope_ambiguous
               （行数与**去重组数**，计划 §8.4 要求单独计数）

归因口径（每个变化恰好落一类，允许 0 未解释）：
  reporter_scope      成员来源地变成 exclusive_reporter_scope（新证据生效）
  scope_or_record     成员来源地在 case_record/court_scope_rule 之间变化
  identity            组的成员签名变化（合并/拆分/身份修复）
  arbitration         提及层仲裁状态变化
  other               以上都不是（必须逐条解释，目标是 0）

★方法教训（r3c 身份回归，复核人指出后订正）：本工具的 `select` 段比较 dd/kept 时
**只比「签名未变的组」**——受害的组签名恰恰都变了，于是**恰好被排除在比较之外**，
得出「dd 只升不降」的错误结论。**dd/kept 的验收口径不是本工具**，而是
`implementation/r3_case_dd_diff.py`（按**案名最大组 dd**，并统计「前一轮同组、
后一轮不同组」的成员对）。本工具的 select 段只作辅助读数，不得单独用于验收。

输出：stdout 摘要 + JSON（含变化行的 CSV 清单路径）。
"""

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COURTS = ("SCC", "ONCA")


def read_all(path, fields=None):
    with open(path, encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        for r in rd:
            if fields:
                yield {k: (r.get(k) or "") for k in fields}
            else:
                yield r


def load_members(run_dir):
    """(court, merge_key) → {identity_basis, origin fields, 组内容签名}

    **必须读跨法院轮的最终产出**（`decide_out/cross_court/decided.csv`）——那才是
    最终分组（XC-G…）；读院内轮的 decided.csv 得到的是 SCC-G/ONCA-G 中间分组，
    组数会虚高（实测 182,384 vs 最终 177,136）。"""
    out = {}
    p = os.path.join(run_dir, "decide_out", "cross_court", "decided.csv")
    if not os.path.exists(p):
        raise SystemExit("缺少跨法院轮产出：%s" % p)
    for r in read_all(p):
        out[(r["court"], r["merge_key"])] = {
                "identity_basis": r.get("identity_basis") or "",
                "m_country": r.get("member_origin_country") or "",
                "m_status": r.get("member_origin_status") or "",
                "m_basis": r.get("member_origin_basis") or "",
                "m_amb": r.get("member_origin_ambiguous_basis") or "",
                "m_excl": r.get("member_origin_exclusivity") or "",
                "g_country": r.get("group_origin_country") or "",
                "g_status": r.get("group_origin_status") or "",
                "g_foreign": r.get("group_foreign_status") or "",
                "gid": r.get("merged_group_id") or "",
                "dd": int(r.get("distinct_decisions_count") or 0),
                "occ": int(r.get("occurrence_count") or 0),
            }
    # 组内容签名（跨院：同一 gid 的所有成员 row_key）
    sig = defaultdict(list)
    for (court, mk), v in out.items():
        sig[v["gid"]].append("%s|%s" % (court, mk))
    gsig = {g: " ; ".join(sorted(rows)) for g, rows in sig.items()}
    for k, v in out.items():
        v["gsig"] = gsig.get(v["gid"], "")
    return out


def load_mentions(run_dir):
    out = {}
    for court in COURTS:
        p = os.path.join(run_dir, "merge_out", court, "mentions_candidates.csv")
        if not os.path.exists(p):
            continue
        for r in read_all(p, ("candidate_id", "arbitration_status",
                              "citation_kind")):
            out[r["candidate_id"]] = (r["arbitration_status"], r["citation_kind"])
    return out


def load_groups_by_sig(members):
    """内容签名 → 组级结论（签名相同才算同一个组；组号跨版本会变）。"""
    out = {}
    for v in members.values():
        out[v["gsig"]] = (v["g_foreign"], v["g_status"], v["g_country"])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--out", default=os.path.join(
        ROOT, "data", "coverage_out", "r3_blast.json"))
    a = ap.parse_args()

    def abspath(p):
        return p if os.path.isabs(p) else os.path.join(ROOT, p)
    b_dir, a_dir = abspath(a.before), abspath(a.after)

    res = {"before": os.path.relpath(b_dir, ROOT).replace("\\", "/"),
           "after": os.path.relpath(a_dir, ROOT).replace("\\", "/")}

    # ---------------- 1 提及层 ----------------
    bm, am = load_mentions(b_dir), load_mentions(a_dir)
    only_b = set(bm) - set(am)
    only_a = set(am) - set(bm)
    arb = Counter()
    changed_mentions = []
    for cid in set(bm) & set(am):
        if bm[cid][0] != am[cid][0]:
            arb[(bm[cid][0], am[cid][0])] += 1
            changed_mentions.append({
                "candidate_id": cid, "kind": bm[cid][1],
                "before_status": bm[cid][0], "after_status": am[cid][0]})
    res["mentions"] = {
        "candidates_before": len(bm), "candidates_after": len(am),
        "only_before": len(only_b), "only_after": len(only_a),
        "status_changes": len(changed_mentions),
        "by_transition": {"%s -> %s" % k: v for k, v in
                          sorted(arb.items(), key=lambda x: -x[1])},
        "by_kind": dict(Counter(m["kind"] for m in changed_mentions).most_common()),
    }

    # ---------------- 2/3 成员行层与组层 ----------------
    b, a2 = load_members(b_dir), load_members(a_dir)
    rows_only_b = set(b) - set(a2)
    rows_only_a = set(a2) - set(b)
    cause = Counter()
    origin_changes = []
    identity_changes = []
    group_status_changes = []
    for k in sorted(set(b) & set(a2)):
        bv, av = b[k], a2[k]
        reasons = []
        if bv["gsig"] != av["gsig"]:
            reasons.append("identity")
            identity_changes.append({
                "court": k[0], "merge_key": k[1],
                "before_group": bv["gid"], "after_group": av["gid"],
                "before_group_size": bv["gsig"].count(";") + 1,
                "after_group_size": av["gsig"].count(";") + 1})
        if (bv["m_country"], bv["m_status"], bv["m_basis"]) != \
                (av["m_country"], av["m_status"], av["m_basis"]):
            if av["m_basis"] == "exclusive_reporter_scope":
                reasons.append("reporter_scope")
            elif bv["m_basis"] == "exclusive_reporter_scope":
                reasons.append("reporter_scope_lost")
            else:
                reasons.append("scope_or_record")
            origin_changes.append({
                "court": k[0], "merge_key": k[1],
                "before": "%s/%s/%s" % (bv["m_country"], bv["m_status"],
                                        bv["m_basis"]),
                "after": "%s/%s/%s" % (av["m_country"], av["m_status"],
                                       av["m_basis"]),
                "after_exclusivity": av["m_excl"],
                "after_ambiguous": av["m_amb"]})
        if bv["g_foreign"] != av["g_foreign"]:
            group_status_changes.append({
                "court": k[0], "merge_key": k[1],
                "before": bv["g_foreign"], "after": av["g_foreign"],
                "reasons": "+".join(reasons) or "group_only"})
        if not reasons:
            # 组结论变了但没有单行归因 → 记 group_only/other，供逐条解释
            if bv["g_foreign"] != av["g_foreign"]:
                reasons.append("group_only")
        for r in (reasons or (["unchanged"] if False else [])):
            cause[r] += 1
    gb, ga = load_groups_by_sig(b), load_groups_by_sig(a2)
    res["members"] = {
        "rows_before": len(b), "rows_after": len(a2),
        "rows_only_before": len(rows_only_b),
        "rows_only_after": len(rows_only_a),
        "origin_field_changes": len(origin_changes),
        "identity_signature_changes": len(identity_changes),
        "group_foreign_status_changes": len(group_status_changes),
        "attribution": dict(cause.most_common()),
    }
    res["groups"] = {
        "groups_before": len(gb), "groups_after": len(ga),
        "foreign_status_before": dict(Counter(v[0] for v in gb.values()).most_common()),
        "foreign_status_after": dict(Counter(v[0] for v in ga.values()).most_common()),
        "signatures_only_before": len(set(gb) - set(ga)),
        "signatures_only_after": len(set(ga) - set(gb)),
        "signature_status_changes": sum(
            1 for s in set(gb) & set(ga) if gb[s][0] != ga[s][0]),
    }

    # ---------------- 4 边层 ----------------
    edges = {}
    for tag, d in (("before", b_dir), ("after", a_dir)):
        p = os.path.join(d, "edges", "citation_edges.csv")
        c = Counter()
        if os.path.exists(p):
            for r in read_all(p, ("foreign_status", "edge_support")):
                c[r["foreign_status"]] += 1
                c["support:" + r["edge_support"]] += 1
        edges[tag] = dict(c.most_common())
        fp = os.path.join(d, "edges", "foreign_edges.csv")
        edges[tag + "_foreign_edge_rows"] = (
            sum(1 for _ in read_all(fp)) if os.path.exists(fp) else 0)
    res["edges"] = edges

    # ---------------- 5 选取层 ----------------
    sel = {}
    for tag, d in (("before", b_dir), ("after", a_dir)):
        p = os.path.join(d, "select_out", "selected.csv")
        m = {}
        if os.path.exists(p):
            for r in read_all(p, ("court", "merge_key", "distinct_decisions_count",
                                  "kept")):
                m[(r["court"], r["merge_key"])] = (
                    int(r["distinct_decisions_count"] or 0), r["kept"])
        sel[tag] = m
    kept_changes = [k for k in set(sel["before"]) & set(sel["after"])
                    if sel["before"][k][1] != sel["after"][k][1]]
    dd_changes = [k for k in set(sel["before"]) & set(sel["after"])
                  if sel["before"][k][0] != sel["after"][k][0]]
    res["select"] = {
        "rows_before": len(sel["before"]), "rows_after": len(sel["after"]),
        "kept_true_before": sum(1 for v in sel["before"].values() if v[1] == "true"),
        "kept_true_after": sum(1 for v in sel["after"].values() if v[1] == "true"),
        "kept_changes": len(kept_changes),
        "dd_changes": len(dd_changes),
    }

    # ---------------- 6 新增歧义审计量 ----------------
    amb_rows = [k for k, v in a2.items()
                if v["m_amb"] == "exclusive_reporter_scope_ambiguous"]
    amb_groups = {a2[k]["gsig"] for k in amb_rows}
    res["reporter_scope_ambiguous"] = {
        "member_rows": len(amb_rows),
        "distinct_groups_by_signature": len(amb_groups),
        "note": "计划 §8.4：这批是真正「看不出」的残差，不得折进普通 UNDETERMINED",
    }
    res["reporter_scope_evidence"] = dict(Counter(
        v["m_basis"] for v in a2.values()
        if v["m_basis"] == "exclusive_reporter_scope").most_common())
    res["reporter_scope_rows_determined"] = sum(
        1 for v in a2.values() if v["m_basis"] == "exclusive_reporter_scope")
    res["reporter_scope_exclusivity_split"] = dict(Counter(
        v["m_excl"] for v in a2.values()
        if v["m_basis"] == "exclusive_reporter_scope").most_common())

    # 变化清单（供人工逐条追溯；目标 0 未解释）
    out = abspath(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    csvs = {}
    for name, rows in (("origin_changes", origin_changes),
                       ("identity_changes", identity_changes),
                       ("group_status_changes", group_status_changes),
                       ("mention_status_changes", changed_mentions)):
        p = os.path.join(os.path.dirname(out), "r3_blast_%s.csv" % name)
        if rows:
            with open(p, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
        csvs[name] = os.path.relpath(p, ROOT).replace("\\", "/")
    res["change_lists"] = csvs
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    print("\nwritten:", os.path.relpath(out, ROOT), file=sys.stderr)


if __name__ == "__main__":
    main()
