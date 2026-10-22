# Usage notes: what this data is, what it can answer, and what it cannot

**In one sentence.** This is a table of **observed case-citation candidates and counted mentions** extracted from the full text of judgments of three Canadian courts (SCC, ONCA, BCCA)
— foreign and domestic citations alike — each with a case name, jurisdiction, place of origin and citation frequency. Its purpose is academic research: an
auditable count of the complete picture of the cases a court has cited over its history. The data comes from three corpora only, **not from all Canadian courts**;
please read every limitation below before using any number.

**Historical snapshot note (2026-10-15).** Measurements below come from explicitly named runs and are not a current aggregate. The October 15 `run_20261015_identity_review` recorded three courts, 230,449 groups, 14,003 with DD ≥ 5 and 490,577 edges. The independent `run_20261015_tcc_identity_verify` and historical seven-court run have separate scopes. See the [October 14 release receipt](../audit/findings/project_review_20261014/release_summary_final.json), [October 15 release receipt](../audit/findings/project_review_20261015/release_summary_final.json) and [retirement records](../audit/findings/repository_cleanup_20261015/retired_runs.json). Retired outputs are represented by receipts, not by replayable full results.

The **current documented snapshot** is `run_20261016_country_complete`, described in the [README](../README.md#data) and [country-assessment comparison](../audit/findings/country_assessment_20261016/impact.json). These software changes do not publish a new dataset or change the active pointer. `data/active_run.json` selects the accepted local run; `python tools/status.py` reports availability, and `python tools/check_run.py --run <directory>` checks actual artifacts. A citation edge records a mention, including procedural history where counted; it does not prove agreement or reliance. The old CanLII audit evaluates citation-link categories and does not independently validate every resolved group identity. The fixed main sample has 270 explicit model reviews; [results and unresolved coverage](../audit/findings/quality_model_review_20261015/README.md) are reported separately from the historical CanLII audit. The independent French supplement is not included in those figures.

---

## 1. What "cited N times" measures

It counts only mentions of a precedent **by the judgments in the three corpora**:

| Corpus | Raw corpus rows | Judgment years | File |
|---|---:|---|---|
| Supreme Court of Canada (SCC) | 10,891 | **1877–2026** | `corpus/SCC.parquet` |
| Court of Appeal for Ontario (ONCA) | 24,089 | **1998–2026** | `corpus/ONCA.parquet` |
| Court of Appeal for British Columbia (BCCA) | 14,703 | **1999–2026** | `corpus/BCCA.parquet` |

The three-court corpus has 49,683 rows. A native-field audit corrected an earlier interpretation: 62 SCC and 136 ONCA rows lack English metadata/text but contain real French judgments, rather than empty records. The new `en_then_fr` policy processes the nonempty English text first and uses French only when English is absent; it preserves existing English source IDs and extracts bilingual rows once. There are 49,476 English-text rows, 198 French-only rows, and nine BCCA rows without either text. Historical manifests lacking `text_policy` retain their English-only scope and 49,485 valid English source IDs; the new metadata scope uses native fallbacks. Raw metadata rows, valid source IDs, text-available judgments and actual cited-source counts are distinct denominators. Batch/year restrictions remain explicit. See `audit/findings/project_review_20261014/language_coverage_receipt.json` and the release record.

In other words: **citations by other courts (provincial superior courts, courts of appeal other than ONCA/BCCA, the Federal Court, administrative tribunals)
are not included at all**. A case cited 200 times by the Ontario Superior Court and 3 times by the SCC shows 3 in this table.
The year ranges are hard limits too: SCC judgments before 1877, ONCA judgments before 1998 and BCCA judgments before 1999
are not in the corpus, so their citations never appear, however important.

The N in "cited N times" is a **number of judgments** (`distinct_decisions_count`, below), not a number of mentions.

## 2. `dd` (distinct decisions count) and `occurrence_count`

| Column | Meaning | When to use it |
|---|---|---|
| `occurrence_count` | At merge: counted mentions for that key. At decide/select: the group total, repeated on every member row | Deduplicate by group before summing group totals; final edge mentions also exclude self-citations |
| `key_occurrence_count` | The member row's original merge-layer mention count, retained through adjudication | Sum these member counts when reconstructing a group total; it is neither DD nor the repeated group total |
| `distinct_decisions_count` (**dd** for short) | **How many different judgments** cite it (one judgment citing it ten times counts once) | This is what the product threshold uses |

Why dd: citing the same case ten times in one judgment is common, but it is still **one legal act
by one judge**; `occurrence_count` treats "one judge cited it ten times" and "ten judges cited it once each" as equally
important. dd also resists OCR noise by construction: a noise string almost always appears in a single judgment, so dd = 1.

**The dd cut must come after the last merge**: the same case may appear as `A.C.`, `All E.R.`, a neutral citation and other
forms; if the cut were made at the merge layer, two groups with "2 each" would both miss the threshold, while the case's real dd is 4. The dd in this table is
the cardinality of the union **after** merging across reporters and across courts.

## 3. The `kept` column selects a DD view

New runs use the `default` profile from `select_config.yaml`, which marks `kept=true` when `dd >= 1`. The optional profiles show narrower frequency views:

| Profile | `kept=true` when |
|---|---|
| `default` | DD ≥ 1 |
| `frequent` | DD ≥ 5 |
| `loose` | DD ≥ 2 |
| `strict` | DD ≥ 10 |

These profiles control display filtering. They do not delete groups or represent calibrated accuracy thresholds; a low DD is not a finding that a citation is false. `select_out/dd_profile.csv` reports how many groups meet each listed threshold. Rows below the selected threshold remain in the complete table with `kept=false`. Historical runs retain their recorded profile and parameters, so their older DD ≥ 5 measurements remain attached to those runs.

## 4. `jurisdiction` and `case_origin` are **two different things**

- **`jurisdiction`** = **which country's law report the citation is printed in**. `[1896] A.C. 348` is printed in the British
  *Appeal Cases*, so `jurisdiction = GB` — **this does not mean the case is British**.
- **`case_origin`** = which jurisdiction **the case itself** comes from. The case above is a Canadian constitutional appeal, so
  `case_origin = CA`, `deciding_court = JCPC`.

To study "the influence of foreign law on Canadian courts", split by `case_origin` (not `jurisdiction`).
**Historical manual-table coverage gap**: the recorded `decisions/case_origin.csv` snapshot had **203 rows**, taken from CanLII's `ukpc` database
(Canadian appeals heard by the Privy Council), which **only covers 1888–1959**; Canadian Privy Council appeals before 1888
(such as *Citizens Insurance v. Parsons* 1881 and *Hodge v. The Queen* 1883) **have no source to check against**,
so they stayed `UNDETERMINED` under that table-only assessment. Beyond Canadian Privy Council cases, that snapshot of the table covered no other place of origin.
See PROBLEMS #59. This describes the historical coverage of that manual table only. Current origin assessment also uses verified member-level country evidence, as described in §6b.

The current `decisions/reporter_jurisdiction.csv` has **202 rows** (recounted 2026-10-16): 106 marked `verified_print_evidence`, 30 `verified_authority`, 56 `name_inference`, 9 `authority_identity_only`, and 1 `authority_country_only`. All still carry `confidence=estimated`; confidence and verification status are separate fields. This replaces the historical claim that every entry was unverified. Filters and analyses should retain both fields and the source evidence.

## 5. Columns you need to know

| Column | How to read it |
|---|---|
| `kept` | DD profile filter: `default` ≥ 1, `frequent` ≥ 5, `loose` ≥ 2, `strict` ≥ 10; all rows remain available, see §3 |
| `is_primary` | The representative row of a group; only one row per `merged_group_id` is `true`. **When counting, deduplicate by group and take the representative row** |
| `case_name_modal` | The modal case name in the group (spelling variants are first folded by normalization, then the most common printed form is taken) |
| `case_name_agreement` | Agreement among voters. **The denominator is "rows that voted"** — rows with no extractable name cast a blank vote and are not in the denominator, so with 1 of 199 rows yielding a name it is still `1.0`. Do not read it as "unanimous" |
| `case_name_support` | Votes for the winning name / `max(counted rows for the key, votes)`. **This is "how many of the judgments citing it stand behind this name"** (PROBLEMS #60); the denominator uses max because self-citation rows still vote but are not counted rows |
| `case_origin` / `deciding_court` | See §4; when not in the table it is `UNDETERMINED`, **not** "equal to jurisdiction" |
| `split_reason` | How this group was split off: `span` (year span) / `decision` (split by judgment using neutral citations) / `unanchored` (no neutral anchor, grouped by co-citation) |
| `same_name_near_year_peers` | Group ids of **other groups** with the same name (equal after normalization) and a year within ±1. **A flag only, not a merge suggestion** (PROBLEMS #62, see §6) |

## 6. Historical limitation measurements and current review boundaries

The numerical examples below belong to the historical two-court runs cited by the original problem entries. They have not been remeasured for the current three-court snapshot or later source fixes. These mechanisms can under-count, over-count or misassign links; they do not establish a universal lower bound. Use [the current problem index](../PROBLEMS.md#当前状态索引) before treating an item as unresolved.

1. **Two groups with the same name and years within ±1 are not merged** (PROBLEMS #62). Measured (group-level counts): across all groups
   there are 8,329 pairs with the same name and primary-row years within ±1, of which **225 pairs** have both sides over the threshold. They mix two kinds:
   genuinely different judgments (an `R. v. John` every year) and **two forms of the same judgment** (for example *R. v. O'Brien* as
   `(1977), 35 C.C.C. (2d) 209` and `[1978] 1 S.C.R. 591` — the two forms never appear together in any judgment, and nothing in the data
   links them). The `same_name_near_year_peers` column was added for this;
   it also flags genuinely different same-name judgments. A machine cannot tell them apart; **a human has to decide**.
2. **Co-citation units with no neutral anchor** (PROBLEMS #49/#55). Forms that have no neutral citation and zero co-citation with any identity anchor
   can only be grouped with each other and are marked `unanchored`. In the historical output, groups over the threshold whose `split_reason` contains `unanchored`
   number **69, with dd totalling 648**. (A narrower count when #55 was recorded gave 56 units, dd totalling 262, of which
   18 had dd ≥5 — the two counts use different definitions; say which one you quote.)
3. **Residual self-citation** (PROBLEMS #54). A judgment's header prints its own citation; the merge layer no longer counts it in dd, but
   `occurrence_count` still includes "self-citation mentions in a parallel form" — when a judgment mentions itself in another reporter's form,
   that mention is still in occurrence; only dd is fully cleaned.
4. **Historical 1.2% gap against upstream bare-neutral metadata** (PROBLEMS #63). Against the upstream ground truth shipped with the corpus (74,750 bare neutral citations),
   recall counting only the finally kept spans is **98.80%**. The **872 missed are not unextracted; they lost deduplication to a longer span
   with the case name stuck to it** (`Kvello Estate 2009 SCC 51` displaces `2009 SCC 51`). In that historical review, the examined winning strings were classified `UNSUPPORTED` (some with `unrecognized_series_prefix`),
   a visible, honest refusal. The effect size is about "1.2% of the bare neutral citations".
   **Definition warning (added in the 2026-09 demo repair round)**: 98.80% is **coverage of the upstream automatic neutral-citation pairs (judgment, citation string)**
   — it measures how well extraction plus deduplication covers the metadata entries shipped with the corpus; it is **not** the
   overall recall of foreign citations, still less proof of any semantic accuracy. After this round (candidates-2.0 overlapping enumeration + arbitration)
   the number corresponds to a diagnostic measure of the old deduplication route; for the comparison with the new route see `implementation/diff_report.md`.
5. **Known residue in judgment identity resolution**: merging parallel citations across reporters relies on co-citation (overlap coefficient ≥0.8); the jurisdiction table marks
   national reporters (`D.L.R.`, `C.C.C.`) as CA, so provincial judgments printed in them may be assigned to the Supreme Court
   (PROBLEMS #40). The errors are under-counts or misassignments, not inflation.
6. **Database/vendor identifier citations** (fixed in round R2F; before that the whole class abstained on a tie and counted 0). `YYYY CanLII N`,
   `YYYY CarswellJur N`, `YYYY DTC N`, `YYYY QCTAQ N` and other identifier citations used to count 0 because of a tie between the "year reading" and the
   "volume reading". R2F resolved this with the identifier_systems.csv decision table (16 rows, sourced from official/authoritative
   manuals) + a classify identifier branch + the existing support grading. Measured on r2g (shape_neutral_bare
   definition): CanLII 1,763 → counted 1,760 + rejected 3; CarswellOnt 944 → counted 943 +
   rejected 1; DTC counted under the year reading (table semantics year_is_volume=yes); QCTAQ counted through a newly added court code;
   CanLIIDocs rejected at row level as secondary commentary. Spelling variants (the CarswellNlfd kind) are left empty under the exact-match policy
   — that is policy, not debt.

## 6b. 2026-09 repair round: the candidates-2.0 route (demo)

This round added a second pipeline (extract all candidates → classify each candidate → merge with in-judgment arbitration → decide
→ select → edges) that **coexists** with the old route described in sections 1–6:

- **One full run**: `python pipeline/run_all.py --out <new empty directory>` (the directory must not exist or must be empty;
  a failed directory is kept, so retry with a new one). Outputs: `run_manifest.json` (only status=complete counts as complete;
  complete requires that the "input identity fingerprint" at the end — production code + every decision table + the select config + corpus + parameters —
  is byte-identical to the one taken at start, R2-10), and per-layer logs `step_*.log`.
- **How to read the final table**: `decide_out/cross_court/decided.csv` (the group-level conclusion is written on **every row** in
  group_foreign_status / group_origin_country / group_origin_status /
  group_origin_evidence_ids; member-level observations are in the member_origin_* and identity_basis columns —
  country observations are aggregated independently of identity support, with disagreements retained as conflicts. The `noncore_origin_evidence` audit column retains country evidence attached through heuristic identity links);
  `kept` in `select_out/selected.csv` uses the selected DD profile; new runs default to DD ≥ 1 (see §3);
  `decide_out/cross_court/effective_sources.csv` is the **only authoritative** "source judgment → case identity"
  link (including the exclusion_reason of removed self-citations).
- **Edges**: one row of `edges/citation_edges.csv` = one (citing judgment, cited case) edge. Country of origin and identity support are separate dimensions: a source's own cited members can establish the country even when `edge_support=heuristic_only`; propagation from group-only country evidence requires a supported identity path. Conflicting country evidence remains a conflict.
  `edges/foreign_edges.csv` contains all edges with `foreign_status=FOREIGN`, including heuristic identity links when their own country evidence is sufficient. A FOREIGN edge has an empty `origin_country` only when its basis is a not-domestic rule (`not_domestic_window` or `not_domestic_printed_court`): the cited judgment is proven not Canadian, but its country is unknown. Per-country analyses should drop these rows; domestic-versus-foreign analyses can keep them. Filter `edge_support` separately when a study requires supported identity links. `edges/tentative_edges.csv` retains heuristic links with a determined group country; `edges/self_excluded_edges.csv` keeps removed self-citations for audit.
- **Per-candidate ledger**: `merge_out/{SCC,ONCA,BCCA}/mentions_candidates.csv` — each candidate's arbitration status
  (counted / yielded / abstained / voided across a boundary …) and what it yielded to; this answers "why is this string not in the results";
  `key_mapping.csv` maps old keys → new keys (series / Roman-numeral page splits).
- **Case-name voting definition** (R2 closure §8 sensitivity parameter; the default = unchanged production behaviour):
  `merge.py --name-vote-pool {current,dedup_position,counted_only}`. Measured (run r2d_b):
  dedup_position gives 100% the same result as production; counted_only changes only the case-name column and the group splits
  (modal changes for 5,271), with zero change to dd / threshold / origin / FOREIGN edges. **case_name_modal does take part in
  decide's case clustering; it is not a display-only column.**
- **Trace back to the source text**: `python pipeline/trace_source.py --run-dir <run directory> --search <case name>`,
  then `--candidate-id <id>` for the classification evidence + arbitration status + source-text window (`<<…>>` marks the span).
- For a walk-through of real examples see `implementation/demo_examples.md`; for the old-vs-new diff see
  `implementation/diff_report.md`; for the repair work log see `implementation/demo_repair_progress.md`.

### Coverage diagnostics produced before sealing

New runs automatically generate `coverage/summary.json` and `coverage/{reporter,neutral,series}.csv` after edges and before finalization seals the outputs. The internal step uses `pipeline/coverage_report.py --run-dir <new run directory>`. Complete runs with an `output_identity` are immutable and reject an in-place coverage write.

The summary separates diagnostic candidate rows, exact-span positions keyed by `(court, source_decision_citation, corpus_row_index, match_start_offset, match_end_offset)`, and final relations read from `edges/citation_edges.csv` and deduplicated by `(source_decision, resolved_cited_case)`. Exact spans are not mutually non-overlapping entities. Arbitration states are shown separately; their position sets and candidate-family sets can overlap. The counted-position denominator includes only merge-ledger rows with `arbitration_status=counted`; `UNSUPPORTED` positions and their distinct affected sources are reported separately. This is an earlier stage than final relation membership: later decide/edges processing may exclude self-citations, so final effective links use the relations denominator. Empty sources do not count as judgments. Court and original `shape_name` breakdowns use these same definitions.

Relation counts and affected-source counts separate `edge_support` from `foreign_status` and known/undetermined/conflicting country evidence. Family priority starts with distinct sources affected by counted `UNSUPPORTED` positions, then candidate diagnostics; `table_status` distinguishes `absent` from `in_table_unresolved`. The two per-court JSON columns carry position and affected-source counts. Series-prefix families are explicitly `rejected_diagnostic`, not missed citations. These reports have no denominator for unobserved citations and do not estimate whole-corpus recall.

## 7. Corpus licences (quoted verbatim)

The `upstream_license` column of the three parquet files reads as follows (**different for each court**):

**SCC** (10,891 rows, all the same text):

> See upstream license, including non-commercial use and other restrictions: https://perma.cc/6Z3Z-UPAC. Note: This is an unofficial reproduction of a Supreme Court of Canada decision, without endorsement or affiliation by the Supreme Court of Canada.

**ONCA** (24,089 rows, all the same text):

> See upstream license, including non-commercial use and other restrictions: https://perma.cc/55T7-3UEX. Note: This is an unofficial reproduction of an Ontario Court of Appeal decision, without endorsement or affiliation by the Ontario courts.

**BCCA** (14,703 rows, all the same text, checked 2026-09-18):

> See upstream license, including non-commercial use and other restrictions: https://perma.cc/EA5C-R5DK. Note: This is an unofficial reproduction of a British Columbia Court of Appeal decision, without endorsement or affiliation by the British Columbia courts.

All three state **non-commercial use and other restrictions** explicitly. **Whether any downstream product (including commercial use) is
permitted is the user's decision; this document cannot settle it and is not legal advice**; open the three
`perma.cc` links above and check the licence terms yourself. This project uses the corpus read-only and does not copy or redistribute judgment text;
**the output tables keep only factual data: citation strings, case names and frequencies**.

## 8. Verification and historical measurements

```bash
python scripts/verify_offline.py
```

The default offline checks discover the small regression fixtures automatically, including the original CLI fixture, and are also used by CI. They check software behavior on those fixtures; they do not estimate full-corpus accuracy or regenerate a dataset.

To compare a chosen completed run with a separately reviewed frozen expectation, name both explicitly:

```bash
python scripts/check_run_golden.py --run <completed run directory> --expect <reviewed run-golden-v1 JSON>
```

That comparison characterizes the selected run's counts and identity probes; a match is not a semantic accuracy result. Historical measurements in this document retain their original date and scope.

The output that the numbers in this document refer to: `data/select_out/selected.csv` **206,213 rows / 190,153 groups /
8,610 groups over the threshold** (2026-09-11).
