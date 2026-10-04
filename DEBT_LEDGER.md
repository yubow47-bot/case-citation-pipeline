# Technical debt ledger (DEBT_LEDGER)

**Purpose**: to close the books on the 83 entries of `PROBLEMS.md` and keep only what really needs watching. From now on this is the only page you need to look at.

**Criterion**: **a real impact + no final state (not fixed, not fully measured, and not explicitly accepted as a limitation) = debt.**
By this criterion, **15** of the 83 entries are real debts (§1, covering **32** PROBLEMS numbers in total); the other **51** entries are not debts (classified in §3).

**Evidence-grade convention** (every item in this file carries one):

- ✅ = **measured independently in this session** (from running code / scanning the corpus / querying the data; reproducible)
- 📖 = **recorded in the ledger** (a number from `PROBLEMS.md`, **not** independently re-checked in this session)

> Why this is called out: three times in a row in this session I overstated things (calling the fixed #18 "won't do", calling #14 "harmless",
> and saying #1 "is not extracted at all"), and all three times it was because **I took the ledger as fact**. So anything marked 📖 in this file
> must be re-checked before acting on it. The current state of B1–B21 (the former demo ledger, see below) is 📖 too; this merge only extracted
> the status last mentioned in `implementation/demo_repair_progress.md`, **without re-running code to verify each one**
> — a lower degree of re-checking than for #1–#63, so re-check before acting on those as well.

**Record of merging the two ledgers on 2026-09-15**: B1–B21 in `implementation/demo_repair_progress.md`
(a separate ledger opened for the R2–R4 demo rounds, recording identity-judgement problems in the merge/adjudication layers) were numbered and merged
into `PROBLEMS.md` by the user's decision, becoming **#64–#84**. Reason for the merge: the group-level reshuffle triggered by the fix for #21 (debt 1)
had as its root cause exactly the mechanism already measured in B21 — had the two ledgers stayed separate, links like this would have kept being missed.
`implementation/demo_repair_progress.md` itself is kept as a historical record and not deleted, but it is no longer
an independent tracking ledger; every new problem goes into `PROBLEMS.md`.

---

## 1. The 15 real debts

### A. Debts that make numbers under-count (recall gaps)

#### Debt 2 — #14 case names behind inline footnotes cannot be cut (SCC 1877–1967)

- **What it is**: in that batch of judgments the citations are in `[n]` footnote lines, and the case names are in the body with a marker, as in `Brook v. Hook[11]`.
  The current method of "looking for the case name before the citation" structurally does not work for this material.
- **Impact** (✅ all measured this time):
  - Of the 8,646 groups over the threshold, **576 groups (6.7%) have no case name at all**;
  - **60.4%** of the citation evidence for these nameless groups **comes from the SCC before 1968**; for named groups it is only **5.1%** (a 12-fold difference);
  - **It does not affect dd, the threshold or the ranking**; it affects only the "case name" column and merging by case name.
  - 📖 Ledger: the `v. X[n]` pattern covers 4,373/10,829 SCC judgments.
- **To close it**: first take **one measurement** — "the share of inline markers that can be linked". There are only two outcomes:
  a low share → close it and write it into the limitations; a high share → it becomes a real work item (an inline-marker anchor table in the extraction layer).
- **Note**: this was originally recorded as "registered only in this version, not implemented" and slipped into the "won't do" bucket. It is not "won't do"; it is "not yet measured".

#### Debt 3 — #35 + #32 foreign court codes / neutral codes lack an authoritative source

- **What it is**: CanLII's structure cannot supply foreign neutral codes (BAILII and the like have them); English court codes
  (UKPC/UKHL/EWCA) have no authoritative source either.
- **Impact**: 📖 of the 215,405 rows missed by extraction, **1,042 rows** are likely real court codes; `[year] UKPC n` 43 rows.
  **This is exactly the project's original goal (foreign citations), and the largest known gap that a source could close.**
- **To close it**: assess the feasibility of fetching from BAILII (UK/Ireland), AustLII (Australia/New Zealand) and SAFLII (South Africa)
  **and their licence terms** (licensing must be assessed first, in line with the established position on external sources in spec §5.1).
  **(Revised by decision on 2026-09-15, priority lowered)**: ① **Scope narrowed** — the place of origin does not aim for full coverage:
  the reporter jurisdiction classification (the 196-row main table is verified, see debt 4) + the Privy Council Canadian special case
  (`case_origin.csv`, 203 rows, with the pre-1888 gap stated honestly) is enough; the long tail of foreign neutral codes
  (the 36 entries of debt 6) likewise gets only low-cost spot checks, not full verification. ② **The scope of "licence assessment"
  corrected**: the original wording lumped two kinds together, which was a mistake — (a) **reading public judgment pages, copying printed strings and
  recording the source URL = allowed** (judgments are public documents and printed strings are facts, the same in nature as what debt 6 did this round with
  courts' official websites); (b) **bulk fetching / storing in a database is still not done** — the reason is not copyright but
  the load on the other side's small sites and courtesy of use. Accordingly, "licensing must be assessed first" no longer blocks
  verification of kind (a); BAILII and the like are demoted to one optional source for spot checks.
  **(The same decision also settles #66/B3, the place of origin of cross-jurisdictional courts** — for the Privy Council Canadian special case, the route of
  `case_origin.csv` + `case_origin_manual.csv` with case-by-case verification is enough, so #66 is no longer listed as a debt and
  moves to §3.2.)

### B. Debts that leave determinations on weak ground

#### Debt 4 — #40 all 196 rows of the reporter jurisdiction table unverified ★ best value for effort

- **What it is**: `decisions/reporter_jurisdiction.csv` has 196 rows, **100% `confidence=estimated` and
  100% `verification_level=name_inference`**, and its source column itself says "provisional inference (unverified)".
- **Impact**: 📖 jurisdiction is resolved for 519,149 rows (89.1%), of which **51,024 rows** are foreign
  (GB 43,797 / US 6,676 / NZ 377 / AU 145 / ZA 29), **all inferred from the abbreviation's name**.
  A mitigation is in place: the `jurisdiction_confidence` column is kept, so estimated rows can be filtered out by confidence.
- **To close it**: verify the 196 rows one by one, then raise `confidence` to `confirmed`.
  Of all the real debts this one has **the highest return per hour** — it directly decides whether the "foreign authority citation" research line is usable.
- **Progress (2026-09-15)**: `audit/findings/reporter_jurisdiction_proposal.csv` has completed the proposal:
  166 rows CONFIRMED (📖 weighted coverage 94.0%), CHANGE=0 (not one jurisdiction determination was wrong);
  it awaits a human spot check of 20 rows and approval before going into the table (`implementation/prompt_switch_r21a.md`/`plan_gold_debt_2026-09-15.md`).

#### Debt 5 — #31 the trailing parenthesis of the CanLII pseudo-code + #70/B7 the same-grade tie of DTC-type codes (same family, handled together)

- **What it is**: in forms like `2026 CanLII 88302 (PE IWCAT)` the jurisdiction is printed in a **trailing parenthesis**, and none of the 7 shapes captures trailing parentheses.
  A problem of the same family (B7): codes like `2022 DTC 5064` hit the court-code table and the reporter table exactly **at the same time**; both tables give
  the exact grade → under rule R2-2 it must abstain and may not force a choice by shape order — essentially a dual-identity problem of
  "the same printed code can be found in two tables with different meanings", the same kind of problem as the CanLII trailing parenthesis:
  "the table structure has no room for this information".
- **Impact**: 📖 for 1,678 neutral citations with `token=CanLII` the jurisdiction always falls to `UNSUPPORTED` (the code spans
  14 jurisdictions). 📖 all 4,980 DTC rows abstain on a same-grade tie and count 0 (an honest under-count, not a guess).
- **To close it**: decide three things — (a) whether the extraction layer adds a trailing-parenthesis capture slot (under constraint six, if added it can only be in the extraction layer);
  (b) whether the classification layer should distinguish two kinds of UNSUPPORTED, "a neutral citation whose jurisdiction is unknowable" and "a reporter not found in the table";
  (c) the correct placement of dual-identity codes such as DTC in the two tables — whether decision-table rows need an explicit
  "not a court code / not a reporter" label to break the tie.

#### Debt 6 — #39 a long tail of 36 foreign neutral codes not traced to a source

- **What it is**: 36 foreign neutral codes still have no authoritative source. The list and leads on "where to look" are in
  `audit/findings/neutral_foreign_proposal.md`, all marked [unverified] and not in the table (leaving them empty is the correct behaviour).
- **Impact**: the jurisdiction of these 36 codes cannot be determined.
- **To close it**: verify against the list. This is work of the same family as debts 3 and 4 and can be done together.
  **(Progress and decision on 2026-09-15)**: this round verified 5 entries into the proposal (NZCA/NZSC/NZHC/TASSC/NICA,
  see `audit/findings/neutral_foreign_verified.csv`), with 25 NOT_FOUND (official sites rendered by JS;
  each lists the URLs tried). Under the debt 3 decision, the remaining entries get **only low-cost spot checks** (reading public pages
  and copying printed strings is allowed), not full verification; the reporter jurisdiction classification + the Privy Council special case is enough.

#### Debt 7 — #50 long and short case names of the same judgment do not join

- **What it is**: `Canada (Minister of Citizenship and Immigration) v. X` and its short form are treated as two groups.
- **Impact**: 📖 after the fix this band has **19 entries, could add dd 331**, and looked at one by one **most are false links**. The original direction of the fix has been abandoned.
- **To close it**: shelve it explicitly (write it into the limitations), or redo it in a new direction. Small in size, can be low priority.

#### Debt 10 — #64/B1 + #67/B4: the reporter jurisdiction table structurally cannot produce a place of origin

- **What it is**: `decide.py:183` states explicitly that `reporter_jurisdiction.csv` (the 196 rows of debt 4)
  can only be upgraded to `jurisdiction` (which country's reporter it is printed in) and **never** to a fact about place of origin. The S.C.R. citation of R. v. W.(D.)
  (`1991|1|scr||742`) and US places of origin (the `389 U.S. 347 (1967)` kind) are both stuck here —
  the neutral-code rules structurally do not apply; both problems have the same root cause.
- **Impact**: these keys have `foreign_status=UNDETERMINED`, which is not a defect (constraint four: no evidence, no default),
  but it means the "foreign authority citation" research line can never get a place of origin for reporter-style citations, only the place of printing.
- **To close it**: the only path is a source-verified, date-bounded exclusivity check for S.C.R./C.C.C./D.L.R., U.S. Reports and so on, one by one
  (the `reporter_origin_scope.csv` route, currently 40 rows,
  verified at the statute level), or case-by-case checks in the manual case-level table (`case_origin_manual.csv`). The search-capability
  block of #81/B18 has been lifted (with an Exa key), which fed the building of `reporter_origin_scope.csv`, but the final share of full coverage
  has not been counted, so this debt stays "unresolved".

#### Debt 11 — #68/B5 same-case propagation (co-citation propagation) not implemented

- **What it is**: item 4 of `decide.py` §9.4 allows place-of-origin evidence to propagate over "supported same-case identity relations",
  but this round's minimal closed loop did not build that chain.
- **Impact**: when some members of a group have a known place of origin and others do not, the current conservative rule easily drops the whole group to CONFLICT or
  UNDETERMINED; part of what identity-relation propagation could have resolved stays unresolved.
- **To close it**: the direction is known but not done, and unscheduled. **2026-09-15 review corrected the effort estimate**: `decide.py`'s
  `assign_identity_basis`/`ELIGIBLE_BASES` already separate "which links are trustworthy" (anchor/singleton/
  same_citation/anchor_variant_bilingual) from "which are only heuristic" (name_year/cocitation/typo)
  — that was the hard part needing domain knowledge, and it is done. What remains is propagation over connected components of trustworthy edges,
  a standard graph algorithm that can use the ready-made `networkx.connected_components`, adapting
  the existing "several places of origin means CONFLICT, no guessing" logic of `aggregate_group_origin`.
  The effort is much smaller than first estimated; it is not a separate workstream but one extension inside decide.py.

#### Debt 12 — #69/B6(D9) no independent manually labelled gold validation has ever been done

- **What it is**: since the project began, all accuracy evidence has been self-consistency (regression gates, golden, invariants) or
  recall against upstream ground truth (98.80%, covering only bare neutral citations). **79% (6,873/8,646)** of the groups over the threshold are reporter-style
  citations, and their precision and recall have never been measured independently.
- **Impact**: we do not know whether the final output is right, only that it is "the same as last time" and "violates no encoded rule".
  This must be filled in before a paper or an external audit.
- **To close it**: an execution plan exists in `implementation/plan_gold_debt_2026-09-15.md` §2 (three sub-samples:
  mention-level precision, group-level correctness, a recall lower bound; agreement from double labelling). **The user decided on 2026-09-15 to defer it**
  — the current stage is building the method, not the strictest standard for publishing a paper; debts 4/6/1 come first.

#### Debt 13 — #71/B8 splitting keys on non-ordinal parentheticals; the direction of the downstream count effect is not established

- **What it is**: `10 Cush. (Mass.) 337` and `10 Cush. 337` are split into two base keys, because the current tables cannot distinguish a "new series" parenthetical
  (such as (N.S.), really a new series) from a "court note" parenthetical (such as (Mass.)/(P.C.), only a court/jurisdiction label);
  35 base keys are affected.
- **Impact**: **the direction is undetermined** — it could under-count (one citation split into two groups, each missing the threshold) or over-count
  (different judgments merged by mistake). Making no claim about the direction is the only honest choice for now.
- **To close it**: the unlocking condition = a sourced classification table of notes (distinguishing "series" from "court note" parentheticals),
  which does not exist and would have to be built.

#### Debt 14 — #77/B14 groups blocked by the identity-basis gate: the highest-value direction not yet started

- **What it is**: R3 measured the upper bound of net new groups from co-citation propagation at 113,432, but **only 4,567 groups
  are blocked by the qualifying identity-basis gate**, of which `name_year` (the case name + year heuristic) makes up 97.9%. In other words: the bottleneck is not
  that the co-citation propagation rule is too strict, but that "case name + year" as an identity criterion is itself unreliable and cannot be promoted to a qualifying criterion.
- **Impact**: this is **possibly the best value for effort** in this table — if a more reliable identity criterion can be added (better
  neutral-anchor recognition or case-name extraction), it benefits several problems at once, including debt 2 (case names) and B21 (absorption along the way).
- **To close it**: left to the user's decision; no relaxation implemented. The right direction is a separate "neutral anchor / case-name extraction" workstream,
  not further relaxing the co-citation propagation definition (that road has been measured and works poorly).

#### Debt 15 — #82/B19 vendor/database identifiers not on the existing table route

- **What it is**: Quicklaw identifiers such as `oj` (Ontario Judgments QL), `scca` (S.C.C.A. No.) and `bcj`/`fcj`
  should by nature go through the existing `decisions/identifier_systems.csv` +
  `decisions/court_or_reporter_scope.csv` route (R2F already used that route for
  CanLII/Carswell/DTC/Westlaw), not be mixed into the new `reporter_origin_scope.csv` table.
- **Impact**: these identifiers are currently on neither the right route nor do they have a jurisdiction / place-of-origin conclusion. `scca` (1,189 groups)
  has the highest priority.
- **To close it**: registered as a candidate for the next round; not done this round to avoid going out of scope.

#### Debt 16 — #84/B21 single-anchor clusters absorb judgments of different instances along the way

- **What it is**: when a group has one strong anchor (such as a neutral citation), the other members are absorbed into the same group without adequate checks.
  Measured on the full data: **4,035 groups / 5,249 members absorbed along the way** (1,001 of them from a different year). The proposed tightening of co-citation routing
  was rejected (it would move 4.0% of kept groups, over the 1% red line; its effectiveness on the #75/B12 subset was only 16/98), which triggered the stop
  condition; not implemented.
- **Impact**: this is not an abstract risk — **it actually happened once after the fix for debt 1 (#21) on 2026-09-15**:
  the 2004 ONCA judgment and the 2005 SCC judgment in R. v. Hamilton (two different courts, different judgments) were wrongly
  merged into one group (dd 50→56). The same reshuffle also corrected an existing error of the same kind in r4c
  (the SCC/Privy Council judgments of MNR v. Wright's Canadian Ropes); see
  `audit/findings/r21_group_reshuffle_pairs.md`.
- **To close it**: the discriminator needed is not co-citation but positive evidence of the kind "different year + printed court designation" (such as
  `(P.C.)` next to A.C.) — R4 Stage 2 has already laid down designation capture (`observed_deciding_court`
  recognized per key, 26/26 with zero errors); the unlocking condition = re-propose a narrow rule on that basis, which would be much smaller in scale
  (only absorbed members carrying a designation would be split). **No delivery is delayed for this debt** — its scale (one group per occurrence)
  is too small compared with the measured cost of tightening (4.0% of kept groups) to be worth acting on now.

### C. Debts that make people misread (definitions not written down)

#### Debt 8 — an after-effect of #47: `key_occurrence_count` is not documented

- **What it is**: the two occurrence columns use different definitions, but the column notes in `USAGE.md` §5 **only have
  `occurrence_count`, not `key_occurrence_count`** — and the latter is the one the ledger uses for "conservation".
- **Impact** (✅ measured this time): summed over the whole table,
  `occurrence_count` = **1,092,865** and `key_occurrence_count` = **532,101** (**a 2.05-fold difference**).
  Anyone who sums the former and reconciles it against 532,101 will think the data is wrong.
  Linked to the #60 trap: the denominator of `case_name_agreement` is "rows that voted", so **a single vote can show 1.0**;
  `case_name_support` is the one to look at (USAGE §5 warns about it, but the column name itself does not guard against it).
- **To close it**: add the column note to USAGE. Pure documentation, very cheap, but it blocks the most common misreading.

#### Debt 9 — spec write-back backlog (about 15 entries)

- **What it is**: #37 #38 #42 #48 #49 #52 #54 #55 #56 #57 #58 #59 #60 #61 #62
  all say "**must be reviewed by a human and written into the specification**" — the implementation was changed after measurement, but the specification was not updated.
- **Impact**: **a reader of the specification gets an impression that does not match the code**. This is a debt at the "reproduction/audit" level, **not wrong numbers**.
- **To close it**: ratify once + write back into the specification (or mark them uniformly in the specification as "implementation notes (v1.x)").
  This is the most numerous but **cheapest** kind: no code changes and no new material needed.
- **Progress**: the notes for spec v1.7 (commit `a0647da`) are written, all marked "pending review"; only human ratification is missing.

---

## 2. What the real debts consist of (one line each)

| Type | Count | Which |
|---|---|---|
| Need **production code changes** | **0** | The former debt 1 (#21) was fixed on 2026-09-15 and moved to §3.1 |
| Need **more source material** | 4 | Debt 3 (#35/#32), debt 4 (#40), debt 6 (#39), debt 10 (#64/#67, reporter / place-of-origin exclusivity checks) |
| Need **your decision** | 3 | Debt 5 (#31/#70, including DTC), debt 7 (#50), the DTC part of debt 5(c) |
| Need **one measurement** | 1 | Debt 2 (#14) |
| Need **documentation** | 2 | Debt 8 (column definitions), debt 9 (spec write-back) |
| Need **a new workstream** (high value, unscheduled) | 3 | Debt 11 (#68, same-case propagation), debt 14 (#77, identity basis / name_year unreliable), debt 15 (#82, vendor identifier route) |
| Need **independent validation** (plan exists, deferred) | 1 | Debt 12 (#69, manually labelled gold) |
| Need **rule design** (direction undetermined) | 1 | Debt 13 (#71, splitting keys on non-ordinal parentheticals) |
| **Accepted as known residue, not chased when it occurs** (with quantitative monitoring) | 1 | Debt 16 (#84, B21 single-anchor absorption — the measured cost is too high, not implemented, but its occurrences are monitored) |

**Of the 15 real debts, only 3 (debts 2/4/6) already have a clear next step under way; debts 10/11/14/15
surfaced only after merging the two ledgers this time and had never been scheduled at all; debt 16 is the kind "known to happen, decided not to fix".**

---

## 3. The 51 entries that are not debts

**Exact partition**: 83 = the **32** entries covered by debts (§1; some debts cover several numbers) + **51** non-debt entries (this section).
(PROBLEMS.md numbers run `#1`–`#84`, of which **`#22` never existed**, so the total is 83.)

### 3.1 Fixed / implemented, cleared (24 entries)

`#7 #11 #13 #18 #19 #20 #21 #23 #24 #25 #28 #29 #30 #33 #34 #36 #41 #43 #44 #45 #46 #51 #53 #73`

- **How #21 (formerly debt 1) was closed**: fixed (2026-09-15). An 8th shape was added,
  `shape_paren_year_abbr_page` ((year) abbreviation page), with **fallback semantics** — it takes effect only at positions none of the seven existing shapes
  match (overlap suppression in the extract layer), which removes at the root the cause of the last rollback, "crowding out correct matches";
  all guards were tested on real typesetting (vol tolerates `. , ;` and lowercase connectives, Roman continuations
  accepted in both cases, p./page/slash continuations rejected, page==year rejected), structural predicates with no word list.
  Measured (run_20260915_r21a; the delivery run has been switched, user review passed on 2026-09-15): counted
  gained **635** (A.C. 268, S.C.R. 77, O.J. 24, P. 19, neutral codes, etc.), vanished **0**, identity
  changes **0**; groups over the threshold 8,646→**8,657** (+11: Keech v. Sandford / 2008 SCC 20 /
  2019 ONCA 638, etc.); dd of existing groups rose for 90 and fell for 0; no entries or exits in the top 25. Group-level reshuffle:
  29 keys / 22 pairs, 1 pair newly wrong (merged into #84/B21), 1 pair correcting an old r4c error — see
  `audit/findings/r21_group_reshuffle_pairs.md`. Test `pipeline/tests/test_shape_21.py`
  (76 assertions).
- **How #73 (B10) was closed**: fixed (2026-09-13, commit 8d8b008 + r2e). The compatible-containment rule
  let through long "repeated year" misparses — a new structural relation `year_reread_as_vol` was added (aligned by field SPAN offsets),
  and arbitration marks the whole class of containers `year_reread_as_vol_invalid`; counter-examples a–e failed first and then turned green,
  test_candidates 158→170; red-line disclosure: old-supported lost 61 (cap 60; the 1 over has been attributed).

(Note: the wording of `#7` "resolved", `#18` "fixed by the slot correction", `#44` "changed to two-level voting" and so on **does not contain
the word "fixed"**, yet all have landed — which is exactly why classifying by keyword misses them.)
Regression gate status (✅ all green in this measurement): `run_regression.py --selftest` exit 0,
`test_layers.py` all 120 assertions pass, `test_layers.py --golden` "full golden matches item by item" exit 0
(reminder: `--golden` only proves agreement with the old output and has no independent power over new code; see the note on #21).

### 3.2 Fully measured = known limitations, no action needed (19 entries)

| Number | Limitation | Size |
|---|---|---|
| #10 | The `shape_vol_abbr_page` form prints no year (modern reporter style) | ✅ 35.9% of all groups, 16.9% of groups over the threshold, **10.0% weighted by dd**; 100% of groups missing a year are reporter-type, concentrated in O.R. 3d 474 / C.C.C. 3d 229 / D.L.R. 4d 122 / O.A.C. 82 |
| #3 | Bracketed citations with no volume are disambiguated by year range alone | A `vol_missing` trace is left; does not affect dd/threshold |
| #4 | Residual false positives of `shape_leading_abbr` | 📖 10,850 rows after deduplication (real prefixes 9,806 + comma-less name swallowing 1,044 + EXHIBIT-type) |
| #5 | `table_conflict` | 📖 measured 0 same-grade conflicts once the reporter table was filled |
| #6 | Frequency of `case_origin_conflict` unknown | Meaningful only once the place-of-origin table reaches some size |
| #17 | No left-hand digit guard on the year | 📖 counts with and without the guard are identical (SCC 31,926 = 31,926; ONCA 17,107 = 17,107); 0 instances in the corpus |
| #26 #27 | Two slots deliberately not added | 📖 40 times (all case-name swallowing), 0 times |
| #63 | The extraction layer's 1.2% under-count against upstream ground truth (872 entries) | A safe failure form (a visible, honest refusal); explicitly not unfrozen |
| #65 (B2) | The extreme adjacency structure of D3 without a partner | 📖 a constructed risk scenario; all 1,233 D3 flags in the full corpus have partners and resolve under the rules; no real instance found |
| #66 (B3) | No exclusive rule-layer evidence for the place of origin of cross-jurisdictional courts (UKPC/JCPC) | Covered by the existing approach (the 2026-09-15 decision on debt 3): the case-by-case route of `case_origin.csv` (203 rows) + `case_origin_manual.csv` (32 rows) is enough; no longer listed as a debt |
| #72 (B9) | Case-name voting includes non-counted candidates | 📖 43.7% of all 466,862 voting rows come from non-counted candidates; `case_name_modal` is only a display column, not identity evidence |
| #74 (B11) | Name changes appear under definition C of case-name sensitivity (counted-only voting) | Production keeps definition A unchanged; a phenomenon found by a sensitivity diagnostic, no effect on delivery |
| #75 (B12) | A subset of single-anchor absorption (foreign mixed reporters, different-year absorption) | 📖 93 groups / 98 absorbed members; the proposed rule was effective on only 16/98; a subset of #84/B21, recorded together and not counted as a separate debt |
| #76 (B13) | Year read as volume | 📖 92 mentions measured (the planned definition's 188 could not be reproduced); counted is always 0, so it never becomes a wrong answer |
| #78 (B15) | Size of the M3 abstention bucket | 📖 13,130 families / 142,082 dd; abstains in the conservative direction as planned; recorded as a known residual |
| #79 (B16) | Residual true ambiguity of homographs | 📖 an estimated 294 combinations / 1,911 mentions fall in zones where countries overlap; recorded as residual; should be marked `exclusive_reporter_scope_ambiguous` in future |
| #80 (B17) | Degenerate table rows (`pd`/`nfldpeir` with no range; `lrex`/`lrqb` inconsistent case) | Small; recorded for someone to fix in passing |
| #83 (B20) | Residual isolated groups from zeroing continuous volume numbering and from self-printed year-less forms becoming their own identity anchors | 📖 isolated groups under definition A measured 9,449→16,743 (+7,294 residual); left alone under the "no scope expansion" principle |

### 3.3 Decided not to do / a choice (5 entries)

- **#1 split years**: ✅ corrected — **it is not "not extracted at all"**. Measured: `[1893-94] 1 S.C.R. 1`
  is caught by `shape_vol_abbr_page` as `1 S.C.R. 1` (vol=1, page=1, no year) and goes into the "missing year" class.
  ✅ A scan of the full corpus finds split-year forms only **70 times / in 46 judgments** (SCC 49, ONCA 21).
- **#2**: `[1978] 1 AC 728` and `[1978] AC 728` count as two keys under strict matching (no speculative merging; a choice).
- **#8**: no lower bound on judgment year = no pre-filtering (a choice, not a defect).
- **#9**: the 396 UNCLEAR strings of the old line are not migrated (the old line is abandoned).
- **#12**: `117 U, S. R. 113` and `13 C.B., N.S., 381` ✅ measured and confirmed at zero hits, but only 2 + 13 occurrences;
  relaxing would break case-name cutting; rejected.

### 3.4 Definition and process rules (3 entries)

`#15` (design of diagnostic-script buckets: should be "footnote rows / body prose / Cases Cited blocks" × era),
`#16` (the admission gate for any future new shape or relaxation, a process rule; anchors counted as 6, pending human review),
`#81` (B18, the search-capability block has been lifted — not the closing of the problem itself but a change in a precondition that unlocks other debts;
with an Exa API key configured, `web_search` works again and fed `reporter_origin_scope.csv`, see debt 10).

---

## 4. Corrections made in this session (so the ledger does not mislead again)

| What I said earlier | What is actually so | How it was found |
|---|---|---|
| #18 belongs to "declared won't do" | It **is fixed** ("fixed by the slot correction 2026-09-06") | Reading each entry's text showed the wording lacked the word "fixed", so keyword classification missed it |
| #14 belongs to "nothing to do" | It is **debt 2**, the largest gap in the "case name" column (6.7% of groups over the threshold are nameless, six tenths of their evidence from the SCC before 1968) | Compared link sources using `effective_sources` |
| That batch of #1 citations is "not extracted at all" | The citations **are captured**, just without a year; the impact is even smaller than the ledger says | Tested synthetic strings directly with `shapes.SHAPES` |
| The 62 entries are all of the project's known problems | The demo rounds opened a separate B1–B21 ledger that was never merged | The group-level reshuffle triggered by the #21 fix exposed the link between the two ledgers (2026-09-15) |

**Lesson (and how to use this file)**: the wording of `PROBLEMS.md` cannot be used as a conclusion. **Before acting, re-check.**

---

## 5. How to use this file

1. **`PROBLEMS.md` is the only problem ledger** (it must not itself be read by scripts); this file is its triage.
   Every new problem is first recorded in `PROBLEMS.md` (with `audit/append_problems_entry.py`, which splits and rejoins on
   `\r\n` so CRLF is not broken), then triaged here.
2. When a debt is closed, **move it to §3** and state how it was closed (fixed / fully measured / explicitly shelved).
3. **Suggest doing debt 4 first (verifying the 196-row jurisdiction table)**: the proposal is in place and only needs a human spot check and approval to go into the table.
4. Debts 10/11/14/15 are directions that surfaced after this merge and **none is scheduled yet**; debt 14 may be
   the best value for effort (it would benefit debt 2 and debt 16 at the same time).
5. The pipeline is **recommended for freezing** (`v1.0-frozen`, no more rule changes except bugs) — but this recommendation now needs reassessment:
   before the merge the basis was "of 9 real debts, 8 are not engineering work"; after the merge the real debts rose to 15, of which 3
   (debts 11/14/15) are entirely new, unscheduled directions, so the user needs to reconfirm whether "freeze" means
   "the five-layer architecture no longer changes" or "no known direction is pursued any further".

---

**Related files**: size and directory governance has been carried out (2026-09-15, 46.8 GB → 9.6 GB), see `data/README.md` and `implementation/run_registry.csv` (`CLEANUP_PLAN.md` was the proposal draft before execution and has been deleted; its content is superseded by the former). The original B ledger merged with this one is `implementation/demo_repair_progress.md` (kept as a historical record, no longer an independent tracking ledger).
