"""jev_decide.py — Jev nodes owned by the cross-court adjudication round (N6, N7).

N6: a member joined only by name/year or co-citation (identity_basis name_year,
cocitation, unanchored) may become `model_confirmed` when Jev, at tier T2 with
an agreeing Noul, says it is the group's judgment. DD is unchanged either way:
decide already counts every member's sources. The upgrade only lets the edge
count as identity-supported. A "different judgment" answer is an L0 mark
(`model_identity_doubt`); no split is made this round.

N7: an `uncertain_ruling_identity` group, split by printed year, and every
same-name near-year peer pair. "Same judgment" removes the uncertainty label
(L1, T1). "Different" is an L0 mark only; groups are never split or merged here.

Group-level country/court aggregation is not recomputed from model_confirmed
members (method card 09).
"""
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

import jev_client as jc
import jev_nodes as jn
from artifacts import open_csv

HEURISTIC_BASES = {"name_year", "cocitation", "unanchored"}
JEV_COLUMNS = ("rule_identity_basis", "model_identity_doubt", "model_ruling_relation",
               "model_peer_relation")


def via_row_keys(value):
    """Split decide's '|'-joined row keys; each is COURT|five-part merge key."""
    parts = (value or "").split("|")
    return ["|".join(parts[i:i + 6]) for i in range(0, len(parts) - 5, 6)]


def stamp_rule(out):
    for r in out:
        r["rule_identity_basis"] = r.get("identity_basis", "")
        r["model_identity_doubt"] = ""
        r["model_ruling_relation"] = ""
        r["model_peer_relation"] = ""


def load_contexts(run_dir, needed, per_key=2):
    """{(court, merge_key): [short native contexts]} from this run's own layer outputs."""
    by_court = defaultdict(set)
    for court, key in needed:
        by_court[court].add(key)
    picked, want = defaultdict(list), {}
    for court, keys in by_court.items():
        path = Path(run_dir) / "merge_out" / court / "mentions_candidates.csv"
        if not (path.exists() or Path(str(path) + ".gz").exists()):
            continue
        with open_csv(path) as f:
            for r in csv_rows(f):
                k = r["merge_key"]
                if r.get("arbitration_status") == "counted" and k in keys \
                        and len(picked[(court, k)]) < per_key:
                    picked[(court, k)].append(r["candidate_id"])
                    want[r["candidate_id"]] = (court, k)
    contexts = defaultdict(list)
    for court in by_court:
        path = Path(run_dir) / "classify_out" / court / "classified.csv"
        if not (path.exists() or Path(str(path) + ".gz").exists()):
            continue
        with open_csv(path) as f:
            for r in csv_rows(f):
                if r["candidate_id"] in want:
                    contexts[want[r["candidate_id"]]].append(
                        (r.get("preceding_text") or "") + jn.MARK_L + (r.get("raw_string") or "")
                        + jn.MARK_R + (r.get("following_text") or ""))
    return contexts


def csv_rows(f):
    import csv
    csv.field_size_limit(1 << 30)
    return csv.DictReader(f)


def _member(r, contexts):
    return {"printed_citation": r.get("canonical_string", ""),
            "case_name_as_cited": r.get("case_name_modal", ""),
            "year_printed": r.get("year_printed", ""),
            "citing_court": r.get("court", ""),
            "court_designation": r.get("observed_deciding_court", ""),
            "contexts": contexts.get((r.get("court", ""), r["merge_key"]), [])}


def _group(rows, titles, own_cites):
    eligible = [m for m in rows if m.get("identity_basis") not in HEURISTIC_BASES]
    primary = next((m for m in rows if m.get("is_primary") == "true"), rows[0])
    native = sorted({titles[d] for m in eligible for d in (own_cites or {}).get(m["merge_key"], ())
                     if titles.get(d)})
    return {"case_name": primary.get("case_name_modal", ""),
            "printed_citations": sorted({m.get("canonical_string", "") for m in eligible})[:8],
            "deciding_court": primary.get("group_deciding_court", ""),
            "year_printed": primary.get("year_printed", ""),
            "native_titles": native}


def apply(out, eff_rows, run_dir, jev, stats, own_cites=None, output=None):
    cfg = jev.cfg
    titles = getattr(own_cites, "titles", {}) or {}
    groups = defaultdict(list)
    for r in out:
        groups[r["merged_group_id"]].append(r)
    ledgers = defaultdict(list)

    n6 = []
    if jev.enabled("N6_identity"):
        for gid, rows in groups.items():
            if not any(m.get("identity_basis") not in HEURISTIC_BASES for m in rows):
                continue  # nothing anchored to confirm against
            for m in rows:
                if m.get("identity_basis") in HEURISTIC_BASES:
                    n6.append((gid, m))
    n7 = []
    if jev.enabled("N7_ruling"):
        for gid, rows in groups.items():
            if any(m.get("ruling_identity_status") == "uncertain_ruling_identity" for m in rows):
                years = Counter(m.get("year_printed") for m in rows if m.get("year_printed"))
                if len(years) >= 2:
                    (ya, _), (yb, _) = years.most_common(2)
                    n7.append(("uncertain", gid, [m for m in rows if m.get("year_printed") == ya],
                               gid, [m for m in rows if m.get("year_printed") == yb]))
        seen = set()
        for gid, rows in groups.items():
            peers = (rows[0].get("same_name_near_year_peers") or "").split(";")
            for other in filter(None, peers):
                pair = tuple(sorted((gid, other)))
                if pair not in seen and other in groups:
                    seen.add(pair)
                    n7.append(("peer", pair[0], groups[pair[0]], pair[1], groups[pair[1]]))

    needed = {(m.get("court", ""), m["merge_key"]) for _, m in n6}
    for item in n7:
        for m in item[2][:3] + item[4][:3]:
            needed.add((m.get("court", ""), m["merge_key"]))
    contexts = load_contexts(run_dir, needed) if needed else {}

    # ---- N6
    if n6:
        n6, dropped = jc.cap(n6, jev.node_cfg("N6_identity").get("max_questions_per_run"), "N6")
        stats["jev_N6_capped"] += dropped
        items = [({"member": _member(m, contexts), "group_judgment": _group(groups[gid], titles, own_cites)},
                  jn.n6_questions()) for gid, m in n6]
        answers = jev.ask_many("N6_identity", items)
        for (gid, m), (state, qs), (ckey, resp) in zip(n6, items, answers):
            a = (resp or {}).get("answers") or {}
            ans, noul = a.get("identity"), (a.get("identity_agrees") or {}).get("noul")
            choice = (ans or {}).get("choice")
            if choice == "same_judgment":
                decision, why = jc.gate(cfg, "T2", ans, noul=noul)
                if decision == "adopt" and not (jc.level_allowed(cfg, "L2") and cfg.get("count_model_confirmed", True)):
                    decision, why = "reject", "level_disabled"
                if decision == "adopt":
                    m["identity_basis"] = "model_confirmed"
            elif choice == "different_judgment":
                decision, why = jc.gate(cfg, "T1", ans)
                if decision == "adopt":
                    m["model_identity_doubt"] = "true"
                    decision, why = "reject", "marked_doubt_only"
            else:
                decision, why = "reject", "abstained" if choice else "no_answer"
            ledgers["N6_identity"].append(jc.ledger_row(
                "N6_identity", gid + "|" + m.get("court", "") + "|" + m["merge_key"],
                "L2", "identity", qs, resp, decision, why, ckey, noul_id="identity_agrees", state=state))
        confirmed = {(m["merged_group_id"], m.get("court", "") + "|" + m["merge_key"])
                     for _, m in n6 if m["identity_basis"] == "model_confirmed"}
        for e in eff_rows:
            if e.get("identity_status") in HEURISTIC_BASES and any(
                    (e["merged_group_id"], k) in confirmed
                    for k in via_row_keys(e.get("via_member_row_keys"))):
                e["identity_status"] = "model_confirmed"
                stats["jev_N6_effective_rows_confirmed"] += 1

    # ---- N7
    if n7:
        n7, dropped = jc.cap(n7, jev.node_cfg("N7_ruling").get("max_questions_per_run"), "N7")
        stats["jev_N7_capped"] += dropped

        def side(rows):
            return {"case_name": rows[0].get("case_name_modal", ""),
                    "citations": sorted({m.get("canonical_string", "") for m in rows})[:8],
                    "court_designations": sorted({m.get("observed_deciding_court", "") for m in rows} - {""}),
                    "sample_passages": [c for m in rows[:3]
                                        for c in contexts.get((m.get("court", ""), m["merge_key"]), [])][:2]}
        items = [({"group_a": side(ra), "group_b": side(rb)}, jn.n7_question())
                 for _, _, ra, _, rb in n7]
        answers = jev.ask_many("N7_ruling", items)
        for (kind, ga, ra, gb, rb), (state, qs), (ckey, resp) in zip(n7, items, answers):
            ans = ((resp or {}).get("answers") or {}).get("same_ruling")
            decision, why = jc.gate(cfg, "T1", ans, abstain={"cannot_tell"})
            choice = (ans or {}).get("choice", "")
            level = "L1" if kind == "uncertain" and choice == "same_judgment" else "L0"
            if decision == "adopt":
                if kind == "uncertain":
                    label = "model_same_ruling" if choice == "same_judgment" else "model_distinct_ruling"
                    for m in groups[ga]:
                        if choice == "same_judgment" and jc.level_allowed(cfg, "L1"):
                            m["ruling_identity_status"] = "model_same_ruling"
                        m["model_ruling_relation"] = label
                else:
                    for g, other in ((ga, gb), (gb, ga)):
                        for m in groups[g]:
                            prev = m.get("model_peer_relation")
                            m["model_peer_relation"] = ";".join(filter(None, [prev, "%s:%s" % (other, choice)]))
                if level == "L0":
                    decision, why = "reject", "marked_only"
            ledgers["N7_ruling"].append(jc.ledger_row(
                "N7_ruling", "%s|%s|%s" % (kind, ga, gb), level, "same_ruling", qs, resp, decision, why, ckey,
                state=state))

    if output:
        for node, rows in ledgers.items():
            jc.write_ledger(os.path.join(output, "jev", node + ".csv"), rows)
            for r in rows:
                stats["jev_%s_%s_%s" % (node[:2], r["level"], "adopted" if r["adopted"] == "true"
                                         else (r["reason_not_adopted"] or "rejected"))] += 1
