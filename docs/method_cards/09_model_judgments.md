# Model judgments (Jev)

Current contract: 2026-10-20; implementation: [jev_client.py](../../pipeline/jev_client.py), [jev_nodes.py](../../pipeline/jev_nodes.py), [jev_classify.py](../../pipeline/jev_classify.py), [jev_decide.py](../../pipeline/jev_decide.py), [jev_edges.py](../../pipeline/jev_edges.py); policy: [jev_config.yaml](../../jev_config.yaml).

Some per-case judgments cannot be written as complete rules: where a case name begins, whether a narrated citation is the case's own lower-court ruling, which name in a string citation owns a report key. The pipeline can hand these to TypeSafe's Jev model, a System One model that chooses among typed options and returns calibrated probabilities. `run_all.py --jev` selects `off` (default, the rule pipeline), `live` or `cache-only`.

## What Jev may be asked

Only questions a careful legal assistant could answer from the supplied state alone: the marked source passage plus structured facts that code extracted. Jev is never asked for facts that need an outside source: reporter jurisdiction, court hierarchy, JCPC origin or court abbreviations. Those remain decision tables with `source` and `source_locator`.

Code generates every option from the source text, the run's rows or the registry; Jev only chooses. Code records offsets. Each question has an abstaining option (`none`, `cannot_tell`, `no_name_here`). An abstention is never adopted and is not evidence against anything. Only English texts are adopted; French-fallback texts are recorded only.

## Levels and direction

| Level | Effect | Examples |
|---|---|---|
| L0 annotate | new column only | suffix meaning, distinct-ruling mark, identity doubt, N1 audit sample |
| L1 fill a gap | where the rule gave no result | case name, corroborated source date, own history, same-ruling |
| L2 override | reverses a rule result | candidate type; name ownership; heuristic identity -> supported |
| L3 grouping | splits or merges groups | not enabled |

Model judgments can be wrong. A wrong positive (a citation, an identity, a "reversed" label) is consumed downstream as verified data; a missed one only loses a row. So conservative moves (exclude, mark, flag) use tier T1, and assertive moves use tier T2.

## Adoption gates

Gates use the selected option's probability `p_max` and its ratio to the runner-up. Jev's own `confidence` depends on the option count and is not used.

- **T1**: `p_max >= 0.80` and `ratio >= 3`, plus the node's structural precondition.
- **T2**: `p_max >= 0.90` and `ratio >= 5`, plus an independently phrased Noul in the same request with `p >= 0.90`, plus the precondition.
- Between `0.60` and the tier: not adopted; listed in the ledger as `below_T1` / `below_T2` / `agreement_check_failed` for review.
- L0 labels below `p_max 0.80` are `unclassified`.

Thresholds were fixed conservatively before any data were seen. They change only after reading A/B samples, and each change is recorded here.

## Nodes

| Node | Layer | Asked when (code) | Adopted as | Level / tier |
|---|---|---|---|---|
| N8 source date | source_integrity | no single verified header date, or provider/native conflict | `model_native_date`, `model_date_status=MODEL_SELECTED_HEADER_DATE` only when its year equals the provider year; otherwise `MODEL_DATE_CONFLICT`; `source_decision_year` never changes | L1 / T1 |
| N1 candidate type | classify | kept rows with UNSUPPORTED jurisdiction; fixed audit samples (0.5% of kept rows, 1% of lexical rejections); reversing a lexical rejection (`readmit`) only when enabled | kept row rejected as `model_judged_not_case:<type>` (T1); readmission of a lexical rejection needs a valid parse, a known reporter or neutral form and T2 (off by default); audits are recorded only | L2 / T1 (T2 when readmit) |
| N2 case name | classify | counted row with no name start found, not a parallel after another citation, not a self-citation header | option from the source text, cleaned by the rule's `admit_candidate`; `case_name_source=jev` | L1 / T1 |
| N5 name owner (off by default) | classify | named row inside a semicolon string citation with two or more `v.` names | changing the rule name needs T2 and the per-name Noul; equal to the rule name is a confirmation only | L2 / T2 |
| N3 suffix meaning (off by default) | classify | printed suffix annotations | `suffix_meanings_json` labels | L0 |
| N6 identity | decide (cross-court) | member joined by name/year, co-citation or unanchored, in a group with an anchored member | `identity_basis=model_confirmed`: the edge counts as identity-supported. DD is unchanged because every member's sources were already counted. Group country/court aggregation does not consume it. "Different judgment" -> `model_identity_doubt` | L2 / T2; doubt L0 |
| N7 ruling | decide (cross-court) | `uncertain_ruling_identity` groups (split by printed year) and same-name near-year peer pairs | same judgment: `ruling_identity_status=model_same_ruling` (L1/T1); different: `model_ruling_relation` / `model_peer_relation` mark only | L1 / L0 |
| N4 own history | edges | pair not confirmed by a printed appeal block; cited court is the citing court or below it in [court_hierarchy.csv](../../decisions/court_hierarchy.csv); cited year not later; the two titles are not disjoint usable adversarial titles | `history_basis=model`, `own_case_history_pair=true`, `history_assessment=model_judged_history` | L1 / T1 |

### Cost

Jev bills input tokens only ($0.042 per million). A request has a fixed overhead of about 300 tokens, each extra small question adds about 40 and the state is counted once per request (measured 2026-10-20 with minimal calls), so cost follows the number of requests. The first complete BCCA+BCSC run used 39,062 requests and 25.9 M tokens ($1.09; about $87 for the nine-court corpus at 80x). Measured on that run:

- N1 `readmit` asked 3,627 questions and reversed none; the unrecognized-prefix audit asked about 3,800 more without producing any change. Readmit is now off and audits are samples.
- N3 writes labels only and N5 changed 34 names after 5,941 questions. Both are off by default.
- N4 asked 7,402 pairs; 5,136 had disjoint party names and 5 of those were adopted. Disjoint-party pairs are no longer asked.

With these changes the same two courts need 13,765 requests and 9.0 M tokens ($0.38; about $30 for nine courts), with identical counts of named rows (38,161), groups (13,808), model-confirmed identities (45) and own-history pairs within 408 vs 406. `tools/jev_cost.py` reports a run's cold-cache cost from its ledgers and the answer cache.

### N1 rejections and merge arbitration

A rejection must not promote an unvetted reading in merge arbitration. Two rules enforce this; both were found in A/B runs on 2026-10-20:

- **Same-span twins.** One printed span is often read by two shapes (e.g. `1980 Chev 4` as neutral and as volume/abbreviation/page). A not-a-citation judgment is about the span, so it applies to every counted twin.
- **Overlapping competitors.** Arbitration may leave two overlapping readings undecided, so that neither is counted. Rejecting one would make the other win (`15 Stage 1` rejected, `14 The Relevant Law. 15` counted; `(1997), 113 L.Q.R. 257` rejected as a journal, contained `113 L.Q.R. 257` counted). Every counted row overlapping a Jev-rejected span stays counted only if Jev confirms a case citation at T2. Its existing N1 answer is used when it has one; otherwise it is asked. Anything less is `model_overlap_unconfirmed`. The check repeats up to four rounds.

### Known side effect of added names

Names restored by N2/N5 let the existing name/near-year rule join scattered parallel citations into their judgment's group. In the 2026-10-20 BCCA+BCSC run, 428 groups only grew. A few members moved out of an anchored group: 4 into a heuristic group and 5 regrouped in other ways. Example: `(2004), 31 B.C.L.R. (4th) 203` (McClelland v. Stewart, 2004 BCCA 458) joined a group anchored on `2004 BCCA 45`, likely a misprint. This is the name/year heuristic's own precision, made visible by better names, not a Jev answer. It belongs to the open same-name identity debts (#48/#106).

Rule values are kept: `rule_rejected_reason`, `rule_candidate_case_name`, `rule_name_rejected_reason`, `rule_identity_basis`, and the unchanged `own_case_history` / `zone_profile`. Every model-derived value has a `*_source` column or its own column. No row is removed.

## Reproducibility and control

- The model is pinned to a versioned ID (`jev-1.13.0`), never an alias. Each answer records the versioned `model` field of its response.
- The cache (`data/jev_cache.sqlite`) is keyed by model, node, spec version, state and questions. `cache-only` replays a live run exactly; a miss is "no answer".
- Each layer writes `jev/<node>.csv` ledgers (choice, probabilities, `p_max`, ratio, Noul, level, adoption, reason, state excerpt) and `jev_summary.json` (calls, cache hits, failures, tokens, latency). The run manifest aggregates them with the cache hash.
- Each node has `enabled` and `max_questions_per_run` (`null`, the release setting, asks every eligible question; a number answers a fixed-seed sample above it). Each level has a switch (`allow_L1`, `allow_L2`). `count_model_confirmed: false` disables N6 support.
- API failures, cache misses and throttling produce "no answer" for that item. They do not fail the layer and do not become a default value.
- The key is read only from `TYPESAFE_API_KEY`.

## Alarms

The A/B report ([tools/jev_ab_compare.py](../../tools/jev_ab_compare.py)) marks a node when L2 adoption exceeds 20% of its questions, when L3 adoption exceeds 50%, or when more than 10% of one rule family is overridden. A marked level stays off in E/G full runs until its samples are read.

Alarm log (2026-10-20, BCCA+BCSC):

- N1 L2 adoption 47.5%: the question set now holds only kept rows with UNSUPPORTED jurisdiction, where junk is common, so a high rate is expected. 40 random exclusions were read: all were table-of-contents entries, amounts, parcel IDs, journal or article citations or a statute. Audit of rows the rules kept: 250 of 280 judged case citations, 30 uncertain, none judged non-citations. Audit of 43 lexical rejections: 42 dates, 1 uncertain, none case citations.
- N6 L2 adoption 31.7% (45 of 142): all 45 were read; each is another report of the same named, anchored judgment (e.g. `[2012] 3 S.C.R. 34` for R. v. Cole, 2012 SCC 53). Cleared for E/G on this evidence; the evidence is one reader's pass over one court pair, not a measured accuracy.

## Not done by model judgment

- Group splitting or merging.
- Country, court or reporter facts.
- Gold standards for evaluation: Jev's published calibration uses frontier-model references, not ground truth.
