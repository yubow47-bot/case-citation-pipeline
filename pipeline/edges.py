# -*- coding: utf-8 -*-
"""edges.py — 引证边输出（R2-1/R2-9 订正后的溯源契约）

一条边 = (source_decision, resolved_cited_case=merged_group_id)。
**边成员资格只来自 decide 的 effective_sources.csv**（decide 是唯一权威）：
  * status=counted 的来源 → 普通边；
  * status=excluded_self（组自身判决经身份根剔除）→ **不**作为普通边重现，
    保留在 self_excluded_edges.csv 供审计；
  * 每组 counted 来源数 == 该组 dd（同一口径，写表前断言）。

国别与身份支持分别记录：
  * 本来源所引成员自己的国别可用于 foreign_status，不要求其身份路径已确证；
  * 缺成员国别时，仅 supported 身份路径可继承组国别；
  * edge_support / identity_status 保留身份置信度，不因国别已知而升级；
  * 国别冲突不投票消除，来源自己的国别也不被组冲突清空。

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
from decide import ELIGIBLE_BASES, MODEL_ELIGIBLE_BASES       # noqa: E402  (R2 闭环 4.4 共享契约)
from artifacts import open_csv, replace_file, resolve

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EDGE_FIELDS = ["source_decision", "resolved_cited_case", "foreign_status",
               "origin_country", "group_origin_country", "group_origin_status",
               "group_foreign_status", "edge_support", "identity_status",
               "origin_basis", "origin_evidence_ids", "noncore_origin_evidence",
               "mention_count", "distinct_decisions_count",
               "case_name_modal", "mention_detail_key", "own_case_history",
               "zone_profile", "history_assessment", "own_case_history_pair", "history_basis",
               "reporter_occurrence_status",
               "reporter_ambiguous_member_keys", "reporter_ambiguous_mention_count",
               "reviewed_edge_support", "reviewed_identity_status",
               "reviewed_foreign_status", "reviewed_origin_country",
               "reviewed_origin_basis", "reviewed_origin_evidence_ids"]

TENTATIVE_FIELDS = ["source_decision", "resolved_cited_case", "identity_status",
                    "group_origin_country", "group_foreign_status",
                    "origin_evidence_ids", "mention_count",
                    "case_name_modal"]


def basis_of(identity_status):
    # R2 闭环 4.4：资格集合来自 decide.ELIGIBLE_BASES（同一来源，防止漂移）
    # method card 09: a Jev-confirmed heuristic member (N6) also supports the edge.
    return identity_status in ELIGIBLE_BASES or identity_status in MODEL_ELIGIBLE_BASES


def group_case_name(candidates):
    """Name a group from all identity-supported members, not from whichever row comes first.

    candidates: Counter {case_name_modal: summed key_occurrence_count}. The most-cited
    name wins; ties break on the name itself so the result does not depend on row order."""
    if not candidates:
        return ""
    return min(candidates.items(), key=lambda kv: (-kv[1], kv[0]))[0]


def candidate_label(identity_status):
    return {"cocitation": "cocitation_candidate", "unanchored": "cocitation_candidate",
            "name_year": "name_year_candidate",
            "anchor_variant_typo": "typo_variant_candidate"}.get(
        identity_status, identity_status)


def origin_for_edge(group, members, identity_supported):
    """A source's own citation can identify its country without proving identity.

    Prefer those member observations over a potentially conflicting group.
    Group-only propagation still needs an identity-supported path.
    """
    known = [m for m in members if m.get("member_origin_status") == "DETERMINED"
             and m.get("member_origin_country")]
    conflict = [m for m in members if m.get("member_origin_status") == "CONFLICT"]
    countries = {m["member_origin_country"] for m in known}
    if known or conflict:
        evidence = sorted({e for m in known + conflict
                           for e in m.get("member_origin_evidence_ids", "").split("|") if e})
        basis = "member:" + "+".join(sorted({m.get("member_origin_basis", "")
                                            for m in known + conflict}))
        if conflict or len(countries) != 1:
            return "CONFLICT", "", basis, "|".join(evidence)
        country = next(iter(countries))
        return ("DOMESTIC_CA" if country == "CA" else "FOREIGN",
                country, basis, "|".join(evidence))
    if identity_supported:
        return (group["group_foreign_status"], group["group_origin_country"],
                group["group_origin_basis"], group["group_origin_evidence_ids"])
    return "UNDETERMINED", "", "", ""



def reporter_occurrence_assessment(observations, supported):
    """Assess only members actually cited by this source; preserve canonical authority.

    A conflicted complete reporter key does not independently support assigning
    this source's occurrence to the group's judgment. Another actual, eligible,
    non-conflicted member can still support the target. No occurrence is moved.
    """
    ambiguous = sorted(m["row_key"] for m in observations
                       if str(m.get("reporter_identity_conflict", "")).lower() == "true")
    if not ambiguous:
        return supported, "none", ambiguous
    clean_support = any(m["row_key"] not in ambiguous
                        and basis_of(m.get("identity_basis", ""))
                        and m.get("identity_source_status") != "excluded_source_only"
                        for m in observations)
    return (supported if clean_support else False,
            "ambiguous_member_present" if clean_support else "uncertain_only_support",
            ambiguous)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--decided", required=True)
    ap.add_argument("--effective", required=True,
                    help="decide 跨法院轮 effective_sources.csv（R2-9 唯一成员资格来源）")
    ap.add_argument("--merge-out", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--registry", default=None, help="Run decision registry (reserved for N4 context)")
    ap.add_argument("--corpus-dir", default=None, help="Native corpus for Jev N4 passages")
    ap.add_argument("--text-policy", default="en_then_fr")
    import jev_client
    jev_client.add_cli(ap)
    a = ap.parse_args()
    jev = jev_client.from_args(a)

    # 组级属性（每行都带组结论，取任一行即可）
    group_attr = {}
    row2group = {}
    member_origin = {}
    # case_name_modal 是成员列不是组列：首行恰好无名时整组无名（Dunsmuir、Vavilov），
    # 故汇总所有身份有依据成员的名字，按出现次数选
    group_names = defaultdict(Counter)
    with open_csv(a.decided) as f:
        for r in csv.DictReader(f):
            name = (r.get("case_name_modal") or "").strip()
            if name and basis_of(r.get("identity_basis") or ""):
                group_names[r["merged_group_id"]][name] += int(r.get("key_occurrence_count") or 0)
            row2group[(r.get("court") or "", r["merge_key"])] = r["merged_group_id"]
            member_origin[(r.get("court") or "") + "|" + r["merge_key"]] = {
                k: r.get(k, "") for k in ("member_origin_country", "member_origin_status",
                                          "member_origin_basis", "member_origin_evidence_ids",
                                          "identity_basis", "reporter_identity_conflict",
                                          "identity_source_status")}
            member_origin[(r.get("court") or "") + "|" + r["merge_key"]]["row_key"] = (
                (r.get("court") or "") + "|" + r["merge_key"])
            g = group_attr.setdefault(r["merged_group_id"], {
                "group_foreign_status": r.get("group_foreign_status") or "UNDETERMINED",
                "group_origin_country": r.get("group_origin_country") or "",
                "group_origin_status": r.get("group_origin_status") or "UNDETERMINED",
                "group_origin_basis": r.get("group_origin_basis") or "",
                "group_origin_evidence_ids": r.get("group_origin_evidence_ids") or "",
                "noncore_origin_evidence": r.get("noncore_origin_evidence") or "",
                "case_name_modal": "",
                "dd": int(r["distinct_decisions_count"] or 0),
                "deciding_court": r.get("group_deciding_court") or "",
                "year": "",
            })
            if r.get("is_primary") == "true":
                g["year"] = r.get("year_printed") or ""
    for gid, g in group_attr.items():
        g["case_name_modal"] = group_case_name(group_names.get(gid))
    # 决策组的组级列是逐行一致的——不一致即上游违约，拒绝写表
    bad = 0
    with open_csv(a.decided) as f:
        for r in csv.DictReader(f):
            g = group_attr[r["merged_group_id"]]
            if (r.get("group_foreign_status") or "UNDETERMINED") != g["group_foreign_status"] \
                    or (r.get("group_origin_country") or "") != g["group_origin_country"]:
                bad += 1
    assert bad == 0, "组级 foreign_status/origin_country 逐行不一致（%d 行）——上游违约" % bad

    # 逐候选提及（counted）→ (source, group) 提及数；提及细节经 mention_detail_key 回连
    from document_zones import edge_zones, history_assessment
    mention_zones = defaultdict(list)
    mention_edges = defaultdict(list)
    first_mention = {}
    stats = Counter()
    for court in sorted({court for court, _ in row2group}):
        # A missing file cannot mean that every member had zero mentions.
        resolve(os.path.join(a.merge_out, court, "mentions_candidates.csv"))
    for court in sorted(d for d in os.listdir(a.merge_out)
                        if os.path.isdir(os.path.join(a.merge_out, d))):
        path = os.path.join(a.merge_out, court, "mentions_candidates.csv")
        try:
            resolve(path)
        except FileNotFoundError:
            raise ValueError("Missing mention provenance: " + path)
        with open_csv(path) as f:
            for m in csv.DictReader(f):
                stats["mentions_scanned"] += 1
                if m["arbitration_status"] != "counted":
                    continue
                gid = row2group.get((court, m["merge_key"]))
                if gid is None:
                    raise ValueError("Counted mention has no decided member: "
                                     + court + "|" + m["merge_key"])
                mention_edges[(m["source_decision_citation"], gid)].append(
                    "%s|%s" % (court, m["merge_key"]))
                mention_zones[(m["source_decision_citation"], gid)].append(m.get("zone") or "unknown")
                if (m.get("corpus_row_index") or "").isdigit():  # legacy fixtures lack offsets
                    first_mention.setdefault((m["source_decision_citation"], gid), (
                        m["source_decision_citation"].split("_", 1)[0], int(m["corpus_row_index"]),
                        int(m["match_start_offset"]), int(m["match_end_offset"])))
                stats["mentions_in_edges"] += 1

    # 有效来源关联 → 边
    all_rows, tentative, self_excluded, source_excluded = [], [], [], []
    per_group_counted = Counter()
    with open_csv(a.effective) as f:
        for e in csv.DictReader(f):
            gid = e["merged_group_id"]
            g = group_attr.get(gid)
            if g is None:
                raise ValueError("Effective source has no decided group: " + gid)
            if e["status"] != "counted":
                if e["status"] not in ("excluded_self", "excluded_source"):
                    raise ValueError("Unknown effective source disposition: " + e["status"])
                excluded_view = source_excluded if e["status"] == "excluded_source" else self_excluded
                excluded_view.append({
                    "source_decision": e["source_decision"],
                    "resolved_cited_case": gid,
                    "exclusion_reason": e["exclusion_reason"],
                    "identity_status": e["identity_status"],
                    "mention_count": len(mention_edges.get(
                        (e["source_decision"], gid), [])),
                })
                stats["source_excluded_sources" if e["status"] == "excluded_source" else "self_excluded_sources"] += 1
                continue
            per_group_counted[gid] += 1
            supported = basis_of(e["identity_status"])
            mkey = (e["source_decision"], gid)
            if not mention_edges.get(mkey):
                raise ValueError("Effective link has no positive mention provenance: "
                                 + repr(mkey))
            observations = [member_origin[k] for k in set(mention_edges.get(mkey, []))
                            if k in member_origin]
            foreign_status, country, origin_basis, origin_ids = origin_for_edge(
                g, observations, supported)
            reviewed_supported, occurrence_status, ambiguous_keys = reporter_occurrence_assessment(
                observations, supported)
            reviewed_foreign, reviewed_country, reviewed_basis, reviewed_ids = origin_for_edge(
                g, observations, reviewed_supported)
            reviewed_identity = ("reporter_occurrence_uncertain"
                if occurrence_status == "uncertain_only_support"
                else e["identity_status"] if reviewed_supported
                else candidate_label(e["identity_status"]))
            stats["reporter_occurrence_" + occurrence_status] += 1
            stats["reporter_reviewed_supported_downgraded"] += int(supported and not reviewed_supported)
            stats["reporter_reviewed_country_changed"] += int(
                (foreign_status, country) != (reviewed_foreign, reviewed_country))
            row = {
                "source_decision": e["source_decision"],
                "resolved_cited_case": gid,
                "foreign_status": foreign_status,
                "origin_country": country,
                "group_origin_country": g["group_origin_country"],
                "group_origin_status": g["group_origin_status"],
                "group_foreign_status": g["group_foreign_status"],
                "edge_support": "supported" if supported else "heuristic_only",
                "identity_status": (e["identity_status"] if supported
                                    else candidate_label(e["identity_status"])),
                "origin_basis": origin_basis,
                "origin_evidence_ids": origin_ids,
                "noncore_origin_evidence": g["noncore_origin_evidence"],
                "mention_count": len(mention_edges.get(mkey, [])),
                "distinct_decisions_count": g["dd"],
                "case_name_modal": g["case_name_modal"],
                "mention_detail_key": ";".join(sorted(set(mention_edges.get(mkey, [])))),
                "reporter_occurrence_status": occurrence_status,
                "reporter_ambiguous_member_keys": ";".join(ambiguous_keys),
                "reporter_ambiguous_mention_count": sum(
                    key in ambiguous_keys for key in mention_edges.get(mkey, [])),
                "reviewed_edge_support": "supported" if reviewed_supported else "heuristic_only",
                "reviewed_identity_status": reviewed_identity,
                "reviewed_foreign_status": reviewed_foreign,
                "reviewed_origin_country": reviewed_country,
                "reviewed_origin_basis": reviewed_basis,
                "reviewed_origin_evidence_ids": reviewed_ids,
            }
            row["own_case_history"], row["zone_profile"] = edge_zones(mention_zones.get(mkey, []))
            row["history_assessment"] = history_assessment(mention_zones.get(mkey, []))
            # The printed appeal block names the cited ruling as this case's history;
            # the relation holds for the pair, not only for the block position.
            zones = mention_zones.get(mkey, [])
            row["history_basis"] = ("formal_all" if zones and all(z == "appeal_block" for z in zones)
                                    else "formal_pair" if "appeal_block" in zones else "none")
            row["own_case_history_pair"] = str(row["history_basis"] != "none").lower()
            all_rows.append(row)
            if not supported and g["group_origin_status"] == "DETERMINED":
                tentative.append({k: row[k] for k in TENTATIVE_FIELDS})
                stats["tentative_edges"] += 1

    # 不变量：每组 counted 来源数 == dd（同口径）
    bad = [gid for gid, g in group_attr.items()
           if per_group_counted[gid] != g["dd"]]
    assert not bad, "R2-9 违约：%d 个组的 counted 来源数 != dd，如 %r" % (
        len(bad), bad[:5])

    jev_summary = None
    if jev.enabled("N4_case_history"):
        if not a.corpus_dir:
            ap.error("Jev N4 needs --corpus-dir")
        import jev_edges
        jev_edges.apply(all_rows, group_attr, first_mention, a.corpus_dir, a.text_policy,
                        jev, stats, a.output)
        jev.close()
        jev_summary = jev.summary()
    for basis, count in Counter(r["history_basis"] for r in all_rows).items():
        stats["edge_history_basis_" + basis] = count

    stats["edges_total"] = len(all_rows)
    fc = Counter(r["foreign_status"] for r in all_rows)
    stats["edges_foreign"] = fc["FOREIGN"]
    stats["edges_domestic_ca"] = fc["DOMESTIC_CA"]
    stats["edges_undetermined"] = fc["UNDETERMINED"]
    stats["edges_conflict"] = fc["CONFLICT"]
    sc = Counter(r["edge_support"] for r in all_rows)
    stats["edges_supported"] = sc["supported"]
    stats["edges_heuristic_only"] = sc["heuristic_only"]

    stats["edges_own_case_history"] = sum(r["own_case_history"] == "true" for r in all_rows)
    for zone, count in Counter(r["zone_profile"] for r in all_rows).items():
        stats["edge_zone_" + zone] = count
    os.makedirs(a.output, exist_ok=True)
    for name, fields, rows in (("citation_edges.csv", EDGE_FIELDS, all_rows),
                               ("foreign_edges.csv", EDGE_FIELDS,
                                [r for r in all_rows if r["foreign_status"] == "FOREIGN"]),
                               ("tentative_edges.csv", TENTATIVE_FIELDS, tentative),
                               ("self_excluded_edges.csv",
                                ["source_decision", "resolved_cited_case",
                                 "exclusion_reason", "identity_status",
                                 "mention_count"], self_excluded),
                               ("source_excluded_edges.csv",
                                ["source_decision", "resolved_cited_case", "exclusion_reason",
                                 "identity_status", "mention_count"], source_excluded)):
        path = os.path.join(a.output, name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        replace_file(tmp, path)

    manifest = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "decided_input": a.decided,
        "effective_input": a.effective,
        "stats": dict(sorted(stats.items())),
        "jev": jev_summary or {"mode": "off"},
        "reporter_occurrence_review": {
            "canonical_fields": "Unchanged effective-source authority; checked by check_run",
            "reviewed_fields": "Source-actual member confidence; conflicted-only support cannot inherit group country",
            "scope": "No reassignment, grouping, DD, membership or mention-count changes",
        },
        "note": ("边成员资格只来自 decide 的 effective_sources（R2-9）；"
                 "国别使用本边成员的来源观察，与 identity support 分开；"
                 "select 的 dd 门槛不进本层（约束六）"),
    }
    with open(os.path.join(a.output, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    if jev_summary:
        with open(os.path.join(a.output, "jev_summary.json"), "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump(jev_summary, f, ensure_ascii=False, indent=1)

    print("edges: %d (FOREIGN %d / DOMESTIC_CA %d / UNDETERMINED %d / CONFLICT %d; "
          "supported %d / heuristic_only %d)"
          % (stats["edges_total"], stats["edges_foreign"], stats["edges_domestic_ca"],
             stats["edges_undetermined"], stats["edges_conflict"],
             stats["edges_supported"], stats["edges_heuristic_only"]))
    for k, v in sorted(stats.items()):
        print("   %-28s %d" % (k, v))


if __name__ == "__main__":
    main()
