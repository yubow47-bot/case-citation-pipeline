"""jev_classify.py — Jev nodes owned by the classification layer (N1, N2, N5, N3).

Runs inside classify.py after every row has its rule result, as a second pass
over the layer's own temporary output. The layer still runs once (constraint 6);
rule values stay in rule_* columns and no row is dropped (constraint 5).
"""
import csv
import json
import os
from collections import Counter, defaultdict

import jev_client as jc
import jev_nodes as jn

RULE_COLUMNS = ["row_status", "row_status_source", "rule_rejected_reason",
                "case_name_source", "rule_candidate_case_name", "rule_name_rejected_reason",
                "suffix_meanings_json"]


def stamp_rule(row):
    """Rule-only values of the model-judgment columns (also the --jev off output)."""
    row["rule_rejected_reason"] = row.get("rejected_reason") or ""
    row["row_status"] = jn.row_status(row.get("rejected_reason"))
    row["row_status_source"] = "rule"
    row["rule_candidate_case_name"] = row.get("candidate_case_name") or ""
    row["rule_name_rejected_reason"] = row.get("name_rejected_reason") or ""
    row["case_name_source"] = "rule" if row.get("candidate_case_name") else ""
    row["suffix_meanings_json"] = ""
    return row


def _suffix_raws(row):
    try:
        items = json.loads(row.get("suffix_annotations_json") or "[]")
    except ValueError:
        return []
    return [str(i.get("raw") or "").strip() for i in items if isinstance(i, dict) and i.get("raw")]


def _texts(corpus, policy, wanted):
    """Yield (row_index, text, text_field) for the wanted corpus rows, one pass."""
    import pyarrow.parquet as pq
    from corpus_fields import projection, select_record
    parquet = pq.ParquetFile(corpus)
    offset = 0
    for batch in parquet.iter_batches(batch_size=128, columns=projection(parquet.schema_arrow.names)):
        for i, native in enumerate(batch.to_pylist(), offset):
            if i in wanted:
                rec = select_record(native, policy)
                yield i, rec["text"] or "", rec.get("text_field") or ""
        offset += batch.num_rows


def _overlap_verdict(cfg, resp):
    """(exclude?, reason, decision, why) for a competitor promoted by a rejection."""
    a = (resp or {}).get("answers") or {}
    ans, noul = a.get("candidate_type"), (a.get("is_case_citation") or {}).get("noul")
    choice = (ans or {}).get("choice")
    if choice == "case_citation" and jc.gate(cfg, "T2", ans, noul=noul)[0] == "adopt":
        return False, "", "reject", "overlap_confirmed_case_citation"
    reason = ("model_judged_not_case:" + choice
              if choice in jn.N1_NOT_CASE and jc.gate(cfg, "T1", ans)[0] == "adopt"
              else "model_overlap_unconfirmed")
    return True, reason, "adopt", ""


def _overlap_rounds(adopt, counted_by_doc, ledgers, responses, args, jev, stats, limit, rounds=4):
    """A rejection must not quietly promote an unvetted overlapping competitor.

    Merge arbitration may have left two overlapping readings undecided; once Jev
    rejects one, the other would win without review (run B3: "15 Stage 1"
    rejected, "14 The Relevant Law. 15" then counted; run B4: "(1997), 113
    L.Q.R. 257" rejected as a journal, its contained "113 L.Q.R. 257" counted).
    Every counted row that overlaps a Jev-rejected span must be a case citation
    at T2 to stay counted, judged from its existing N1 answer when it has one
    and otherwise asked. Anything less is excluded as `model_overlap_unconfirmed`
    (the conservative direction).
    """
    node = "N1_candidate_type"
    cfg = jev.cfg
    checked = set()

    def rejected(cid):
        return adopt.get(cid, {}).get("row_status") == "not_citation"

    def settle(b, resp, ckey, st, qs):
        cid = b["candidate_id"]
        exclude, reason, decision, why = _overlap_verdict(cfg, resp)
        if exclude:
            adopt[cid].update(rejected_reason=reason, row_status="not_citation", row_status_source="jev")
            stats["jev_N1_overlap_excluded"] += 1
        row = jc.ledger_row(node, cid, "L2", "candidate_type", qs, resp, decision, why,
                            ckey, noul_id="is_case_citation", state=st)
        row["question"] = "candidate_type:overlap_check"
        ledgers[node].append(row)
    for _ in range(rounds):
        todo = []
        for idx, rows in counted_by_doc.items():
            spans = [(int(b["match_start_offset"]), int(b["match_end_offset"]))
                     for b in rows if rejected(b["candidate_id"])]
            if not spans:
                continue
            for b in rows:
                cid = b["candidate_id"]
                s, e = int(b["match_start_offset"]), int(b["match_end_offset"])
                if cid in checked or rejected(cid):
                    continue
                if any(s < re_ and rs < e for rs, re_ in spans):
                    todo.append(b)
        if not todo:
            return
        checked |= {b["candidate_id"] for b in todo}
        fresh = []
        for b in todo:
            stored = responses.get(b["candidate_id"])
            # A stored answer without the agreement Noul cannot reach tier T2: ask again.
            if stored is not None and (stored[0] is None or "is_case_citation" in (stored[0].get("answers") or {})):
                resp, ckey, st, qs = stored
                settle(b, resp, ckey, st, qs)
            else:
                fresh.append(b)
        by_doc = defaultdict(list)
        for b in fresh:
            by_doc[int(b["corpus_row_index"])].append(b)
        triples = []
        for idx, text, field in _texts(args.corpus, args.text_policy, set(by_doc)):
            for b in by_doc[idx]:
                if cfg.get("english_only", True) and not jn.is_english(field):
                    adopt[b["candidate_id"]].update(rejected_reason="model_overlap_unconfirmed",
                                                    row_status="not_citation", row_status_source="jev")
                    stats["jev_N1_overlap_french_excluded"] += 1
                    continue
                s, e = int(b["match_start_offset"]), int(b["match_end_offset"])
                triples.append((b, jn.window(text, s, e, 300, 150, limit), jn.n1_question(True)))
        answers = jev.ask_many(node, [(st, qs) for _, st, qs in triples])
        for (b, st, qs), (ckey, resp) in zip(triples, answers):
            responses[b["candidate_id"]] = (resp, ckey, st, qs)
            settle(b, resp, ckey, st, qs)


def postpass(tmp_path, out_path, fieldnames, args, jev, stats, keep_input=False):
    from classify import admit_candidate
    cfg = jev.cfg
    enabled = {n: jev.enabled(n) for n in ("N1_candidate_type", "N2_case_name",
                                           "N5_name_owner", "N3_suffix_meaning")}
    n1cfg = jev.node_cfg("N1_candidate_type")
    audit_rate = float(n1cfg.get("audit_rate", 0.0))
    lexical_audit_rate = float(n1cfg.get("audit_rate_lexical", 0.0))
    readmit = bool(n1cfg.get("readmit", False))

    # pass 1: select items from rule results (selection lives in code and is counted)
    items = defaultdict(list)  # corpus_row_index -> [(node, row_subset)]
    # Same-span twins: one printed span read by two shapes. A "not a citation"
    # judgment is about the span, so it must reach every counted twin; otherwise
    # rejecting one reading promotes the other in merge arbitration.
    span_rows = defaultdict(list)
    counted_by_doc = defaultdict(list)  # corpus row -> counted rows, for overlap competitors
    with open(tmp_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            cid = row["candidate_id"]
            span_rows[(row["corpus_row_index"], row["match_start_offset"], row["match_end_offset"])].append(
                (cid, bool(row.get("rejected_reason"))))
            base = {k: row.get(k, "") for k in (
                "candidate_id", "corpus_row_index", "match_start_offset", "match_end_offset",
                "rejected_reason", "candidate_case_name", "jurisdiction", "parse_status",
                "citation_kind")}
            if not row.get("rejected_reason"):
                counted_by_doc[int(row["corpus_row_index"])].append(base)
            if enabled["N1_candidate_type"]:
                scope = jn.n1_scope(row, audit_rate, readmit, lexical_audit_rate)
                if scope:
                    items[int(row["corpus_row_index"])].append(("N1_candidate_type", dict(base, mode=scope[0], level=scope[1])))
            if enabled["N2_case_name"]:
                s2 = jn.n2_scope(row)
                if s2 == "ask":
                    items[int(row["corpus_row_index"])].append(("N2_case_name", base))
                elif s2:
                    stats["jev_N2_excluded_" + s2] += 1
            if enabled["N5_name_owner"] and not row.get("rejected_reason") \
                    and row.get("candidate_case_name") and row.get("self_citation") != "true":
                items[int(row["corpus_row_index"])].append(("N5_name_owner", base))
            if enabled["N3_suffix_meaning"]:
                raws = _suffix_raws(row)
                if raws:
                    items[int(row["corpus_row_index"])].append(("N3_suffix_meaning", dict(base, suffixes=raws)))

    # pass 2: build states from native text, one corpus pass
    limit = int(cfg.get("state_char_limit", 6000))
    asks = defaultdict(list)  # node -> [(item, state, questions)]
    for idx, text, field in _texts(args.corpus, args.text_policy, set(items)):
        english = jn.is_english(field)
        for node, it in items[idx]:
            if cfg.get("english_only", True) and not english:
                stats["jev_%s_skipped_french" % node[:2]] += 1
                continue
            s, e = int(it["match_start_offset"]), int(it["match_end_offset"])
            if node == "N1_candidate_type":
                asks[node].append((it, jn.window(text, s, e, 300, 150, limit),
                                   jn.n1_question(it["mode"] == "readmit")))
            elif node == "N2_case_name":
                opts = jn.n2_options(text, s)
                if not opts:
                    stats["jev_N2_no_options"] += 1
                    continue
                it = dict(it, options=opts)
                asks[node].append((it, jn.window(text, s, e, 300, 80, limit), jn.n2_question(opts)))
            elif node == "N5_name_owner":
                names = jn.n5_names(text, s)
                if not names:
                    continue  # not a string citation: out of scope
                if it["candidate_case_name"] not in names:
                    names = names + [it["candidate_case_name"]]
                it = dict(it, names=names)
                qs = jn.n5_question(names, it["candidate_case_name"])
                for i, n in enumerate(names, 1):
                    qs["agrees_n%d" % i] = jn.n5_agreement(n)["owner_agrees"]
                asks[node].append((it, jn.window(text, s, e, 400, 80, limit), qs))
            else:
                asks[node].append((it, jn.window(text, s, e, 200, 200, limit),
                                   jn.n3_questions(it["suffixes"])))

    # pass 3: ask, gate, record
    adopt = defaultdict(dict)  # candidate_id -> column updates
    ledgers = defaultdict(list)
    n1_responses = {}  # candidate_id -> (response, cache key, state, questions)
    for node, triples in asks.items():
        triples, dropped = jc.cap(triples, jev.node_cfg(node).get("max_questions_per_run"), node)
        stats["jev_%s_capped" % node[:2]] += dropped
        answers = jev.ask_many(node, [(st, qs) for _, st, qs in triples])
        for (it, st, qs), (ckey, resp) in zip(triples, answers):
            cid = it["candidate_id"]
            if node == "N1_candidate_type":
                n1_responses[cid] = (resp, ckey, st, qs)
                decision, why, choice = jn.n1_decide(cfg, it["mode"], resp)
                if decision == "adopt" and it["mode"] == "readmit" and not (
                        it["parse_status"] in ("", "valid") and it["jurisdiction"] not in ("", "UNSUPPORTED")):
                    decision, why = "reject", "structural_precondition"
                if decision == "adopt":
                    if it["mode"] == "readmit":
                        adopt[cid].update(rejected_reason="", row_status="citation_counted", row_status_source="jev")
                    else:
                        span = (it["corpus_row_index"], it["match_start_offset"], it["match_end_offset"])
                        for twin, rejected in span_rows[span]:
                            if twin == cid or not rejected:
                                adopt[twin].update(rejected_reason="model_judged_not_case:" + choice,
                                                   row_status="not_citation", row_status_source="jev")
                                stats["jev_N1_span_rows_rejected"] += 1
                ledgers[node].append(jc.ledger_row(node, cid, it["level"], "candidate_type", qs, resp,
                                                   decision, why, ckey, noul_id="is_case_citation", state=st))
            elif node == "N2_case_name":
                ans = ((resp or {}).get("answers") or {}).get("case_name")
                decision, why = jc.gate(cfg, "T1", ans, abstain={"no_name_here"})
                if decision == "adopt" and not jc.level_allowed(cfg, "L1"):
                    decision, why = "reject", "level_disabled"
                if decision == "adopt":
                    pick = jn.option_index(ans["choice"], "o", len(it["options"]))
                    chosen = it["options"][pick] if pick is not None else ""
                    cleaned, reject = admit_candidate(chosen, bounded_name=True) if chosen else ("", "unknown_option")
                    if reject or not cleaned:
                        decision, why = "reject", "admit_candidate:" + (reject or "empty")
                    else:
                        adopt[cid].update(candidate_case_name=cleaned, name_rejected_reason="",
                                          case_name_source="jev")
                ledgers[node].append(jc.ledger_row(node, cid, "L1", "case_name", qs, resp, decision, why, ckey,
                                                   state=st))
            elif node == "N5_name_owner":
                ans = ((resp or {}).get("answers") or {}).get("owner")
                choice = (ans or {}).get("choice", "")
                names = it["names"]
                pick = jn.option_index(choice, "n", len(names))
                chosen = names[pick] if pick is not None else ""
                # Compare names as the rule would print them: regex options keep a
                # trailing period or bracket that admit_candidate removes.
                cleaned_choice = admit_candidate(chosen, bounded_name=True)[0] if chosen else ""
                if chosen and cleaned_choice == it["candidate_case_name"]:
                    decision, why, level = "reject", "confirms_rule", "L0"
                else:
                    level = "L2"
                    noul = (((resp or {}).get("answers") or {}).get("agrees_" + choice) or {}).get("noul")
                    decision, why = jc.gate(cfg, "T2", ans, noul=noul, abstain={"none"})
                    if decision == "adopt" and not jc.level_allowed(cfg, "L2"):
                        decision, why = "reject", "level_disabled"
                    if decision == "adopt" and not chosen:
                        decision, why = "reject", "unknown_option"
                    if decision == "adopt":
                        cleaned, reject = admit_candidate(chosen, bounded_name=True)
                        if reject or not cleaned:
                            decision, why = "reject", "admit_candidate:" + (reject or "empty")
                        else:
                            adopt[cid].update(candidate_case_name=cleaned, case_name_source="jev_owner")
                ledgers[node].append(jc.ledger_row(node, cid, level, "owner", qs, resp, decision, why, ckey,
                                                   noul_id=("agrees_" + choice) if pick is not None else None,
                                                   state=st))
            else:
                labels = []
                for i, raw in enumerate(it["suffixes"]):
                    qid = "suffix_%d" % i
                    ans = ((resp or {}).get("answers") or {}).get(qid)
                    choice, p_max, _ = jc.choice_metrics(ans)
                    ok = bool(choice) and p_max >= cfg["gates"]["label_p_max"]
                    labels.append({"raw": raw, "meaning": choice if ok else "unclassified",
                                   "p": round(p_max, 4)})
                    ledgers[node].append(jc.ledger_row(node, cid, "L0", qid, qs, resp,
                                                       "adopt" if ok else "reject",
                                                       "" if ok else "below_label_threshold", ckey, state=st))
                adopt[cid]["suffix_meanings_json"] = json.dumps(labels, ensure_ascii=False)

    if enabled["N1_candidate_type"]:
        _overlap_rounds(adopt, counted_by_doc, ledgers, n1_responses, args, jev, stats, limit)

    # pass 4: stream the rule output to the final file with adopted judgments applied
    with open(tmp_path, encoding="utf-8", newline="") as fin, \
            open(out_path + ".jev", "w", encoding="utf-8", newline="") as fout:
        w = csv.DictWriter(fout, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in csv.DictReader(fin):
            upd = adopt.get(row["candidate_id"])
            if upd:
                row.update(upd)
                for k in upd:
                    stats["jev_applied_" + k] += 1
            w.writerow(row)
    os.replace(out_path + ".jev", out_path)
    if not keep_input:  # tests replay one input under several configurations
        os.remove(tmp_path)

    jev_dir = os.path.join(os.path.dirname(out_path), "jev")
    for node, rows in ledgers.items():
        jc.write_ledger(os.path.join(jev_dir, node + ".csv"), rows)
        c = Counter((r["level"], r["adopted"], r["reason_not_adopted"]) for r in rows)
        for (level, adopted, why), n in c.items():
            stats["jev_%s_%s_%s" % (node[:2], level, "adopted" if adopted == "true" else (why or "rejected"))] += n
    return jev.summary()
