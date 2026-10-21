"""jev_edges.py — N4: is the cited judgment part of the citing case's own history?

Only pairs not already confirmed by a printed appeal block are asked, and only
when code proves the structural precondition: the cited court is the citing
court or a lower court in decisions/court_hierarchy.csv, and the cited year is
not later than the citing year. Adoption marks history (L1, conservative):
own_case_history_pair=true, history_basis=model. Nothing else changes.
"""
import os
import re
from collections import defaultdict

import jev_client as jc
import jev_nodes as jn

YEAR = re.compile(r"_(1[89]\d\d|20\d\d)")


def source_year(source_decision):
    m = YEAR.search(source_decision or "")
    return int(m.group(1)) if m else None


def apply(rows, group_attr, first_mention, corpus_dir, text_policy, jev, stats, output):
    cfg = jev.cfg
    hierarchy = jn.load_court_hierarchy()
    canon = jn.court_canonicalizer()
    from decide import load_native_titles
    from identity_solve import conflicting_case_context
    titles = load_native_titles(corpus_dir, {r["source_decision"] for r in rows
                                             if r["history_basis"] == "none"})
    asks = []
    for row in rows:
        if row["history_basis"] != "none":
            continue
        g = group_attr[row["resolved_cited_case"]]
        citing = canon(row["source_decision"].split("_", 1)[0])
        cited = canon((g.get("deciding_court") or "").replace("court:", ""))
        cited_year = g.get("year")
        ok, why = jn.history_eligible(citing, cited, source_year(row["source_decision"]),
                                      int(cited_year) if (cited_year or "").isdigit() else None,
                                      hierarchy)
        if not ok:
            stats["jev_N4_excluded_" + why] += 1
            continue
        # The same litigation keeps its parties. When both titles are usable
        # adversarial titles with disjoint party words (spelling and shortened-name
        # variants allowed), the cited ruling cannot be this case's own history.
        # BCCA+BCSC: 5,136 of 7,402 questions had disjoint parties and 5 were adopted.
        if conflicting_case_context({"case_name_modal": titles.get(row["source_decision"], "")},
                                    {"case_name_modal": g.get("case_name_modal", "")}):
            stats["jev_N4_excluded_party_names_disjoint"] += 1
            continue
        mention = first_mention.get((row["source_decision"], row["resolved_cited_case"]))
        if mention is None:
            stats["jev_N4_excluded_no_mention"] += 1
            continue
        asks.append((row, g, mention))
    asks, dropped = jc.cap(asks, jev.node_cfg("N4_case_history").get("max_questions_per_run"), "N4")
    stats["jev_N4_capped"] += dropped

    # one corpus pass per citing court for the needed source rows
    from jev_classify import _texts
    by_court = defaultdict(set)
    for _, _, (court, idx, _, _) in asks:
        by_court[court].add(idx)
    texts = {}
    for court, wanted in by_court.items():
        path = os.path.join(corpus_dir, court + ".parquet")
        for idx, text, field in _texts(path, text_policy, wanted):
            texts[(court, idx)] = (text, field)

    limit = int(cfg.get("state_char_limit", 6000))
    items, kept = [], []
    for row, g, (court, idx, s, e) in asks:
        text, field = texts.get((court, idx), ("", ""))
        if not text:
            stats["jev_N4_excluded_no_text"] += 1
            continue
        if cfg.get("english_only", True) and not jn.is_english(field):
            stats["jev_N4_skipped_french"] += 1
            continue
        state = {"citing_decision": {"id": row["source_decision"]},
                 "cited_decision": {"court": g.get("deciding_court", "").replace("court:", "").upper(),
                                    "year_printed": g.get("year", ""),
                                    "case_name_if_known": g.get("case_name_modal", "")},
                 "text": jn.window(text, s, e, 400, 200, limit)}
        items.append((state, jn.n4_questions()))
        kept.append(row)
    answers = jev.ask_many("N4_case_history", items)
    ledger = []
    for row, (state, qs), (ckey, resp) in zip(kept, items, answers):
        ans = ((resp or {}).get("answers") or {}).get("relation")
        choice = (ans or {}).get("choice")
        if choice == "under_appeal_or_earlier_in_this_case":
            decision, why = jc.gate(cfg, "T1", ans)
            if decision == "adopt" and not jc.level_allowed(cfg, "L1"):
                decision, why = "reject", "level_disabled"
        else:
            decision, why = "reject", ("not_own_history:" + choice) if choice else "no_answer"
        if decision == "adopt":
            row["history_basis"] = "model"
            row["own_case_history_pair"] = "true"
            row["history_assessment"] = "model_judged_history"
        ledger.append(jc.ledger_row("N4_case_history", row["source_decision"] + "|" + row["resolved_cited_case"],
                                    "L1", "relation", qs, resp, decision, why, ckey,
                                    noul_id="explicitly_stated", state=state))
    jc.write_ledger(os.path.join(output, "jev", "N4_case_history.csv"), ledger)
    for r in ledger:
        stats["jev_N4_L1_" + ("adopted" if r["adopted"] == "true" else (r["reason_not_adopted"].split(":")[0] or "rejected"))] += 1
