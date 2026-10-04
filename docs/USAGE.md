# Usage notes: what this data is, what it can answer, and what it cannot

**In one sentence.** This is a table of **every cited case** extracted from the full text of judgments of three Canadian courts (SCC, ONCA, BCCA)
— foreign and domestic citations alike — each with a case name, jurisdiction, place of origin and citation frequency. Its purpose is academic research: an
auditable count of the complete picture of the cases a court has cited over its history. The data comes from three corpora only, **not from all Canadian courts**;
please read every limitation below before using any number.

---

## 1. What "cited N times" measures

It counts only mentions of a precedent **by the judgments in the three corpora**:

| Corpus | Judgments | Judgment years | File |
|---|---:|---|---|
| Supreme Court of Canada (SCC) | 10,891 | **1877–2026** | `corpus/SCC.parquet` |
| Court of Appeal for Ontario (ONCA) | 24,089 | **1998–2026** | `corpus/ONCA.parquet` |
| Court of Appeal for British Columbia (BCCA) | 14,703 | **1999–2026** | `corpus/BCCA.parquet` |

In other words: **citations by other courts (provincial superior courts, courts of appeal other than ONCA/BCCA, the Federal Court, administrative tribunals)
are not included at all**. A case cited 200 times by the Ontario Superior Court and 3 times by the SCC shows 3 in this table.
The year ranges are hard limits too: SCC judgments before 1877, ONCA judgments before 1998 and BCCA judgments before 1999
are not in the corpus, so their citations never appear, however important.

The N in "cited N times" is a **number of judgments** (`distinct_decisions_count`, below), not a number of mentions.

## 2. `dd` (distinct decisions count) and `occurrence_count`

| Column | Meaning | When to use it |
|---|---|---|
| `occurrence_count` | The **number of rows in which this citation form is mentioned** in the corpus | When you want to measure "how often it appears" |
| `distinct_decisions_count` (**dd** for short) | **How many different judgments** cite it (one judgment citing it ten times counts once) | This is what the product threshold uses |

Why dd: citing the same case ten times in one judgment is common, but it is still **one legal act
by one judge**; `occurrence_count` treats "one judge cited it ten times" and "ten judges cited it once each" as equally
important. dd also resists OCR noise by construction: a noise string almost always appears in a single judgment, so dd = 1.

**The dd cut must come after the last merge**: the same case may appear as `A.C.`, `All E.R.`, a neutral citation and other
forms; if the cut were made at the merge layer, two groups with "2 each" would both miss the threshold, while the case's real dd is 4. The dd in this table is
the cardinality of the union **after** merging across reporters and across courts.

## 3. The `kept` threshold is an **uncalibrated placeholder**

The `kept` column in `data/select_out/selected.csv` = `dd >= 5`. **This 5 has no basis.** The code states it explicitly:

```
pipeline/select_layer.py: THRESHOLD_CALIBRATION = "uncalibrated_placeholder_see_spec_11_2"
```

What spec §11.2 says: the value was tuned for the "foreign landmark case lookup" scenario and lost its basis when the scope was widened to all citations;
**until it is reset from the dd distribution of the first full run, it is only a placeholder and must not be quoted as a calibrated parameter**.
`data/select_out/dd_profile.csv` is the calibration instrument (how many groups remain at each candidate threshold); the decision to reset the threshold belongs to
the product side, not the data side.

Rows below the threshold are **not deleted**, only marked `kept=false`; the full table is always kept, so it can always answer
"why is this case not in the results".

## 4. `jurisdiction` and `case_origin` are **two different things**

- **`jurisdiction`** = **which country's law report the citation is printed in**. `[1896] A.C. 348` is printed in the British
  *Appeal Cases*, so `jurisdiction = GB` — **this does not mean the case is British**.
- **`case_origin`** = which jurisdiction **the case itself** comes from. The case above is a Canadian constitutional appeal, so
  `case_origin = CA`, `deciding_court = JCPC`.

To study "the influence of foreign law on Canadian courts", split by `case_origin` (not `jurisdiction`).
**Known coverage gap**: `decisions/case_origin.csv` currently has **203 rows**, taken from CanLII's `ukpc` database
(Canadian appeals heard by the Privy Council), which **only covers 1888–1959**; Canadian Privy Council appeals before 1888
(such as *Citizens Insurance v. Parsons* 1881 and *Hodge v. The Queen* 1883) **have no source to check against**,
so they honestly stay `UNDETERMINED`. Beyond Canadian Privy Council cases, the table covers no other place of origin.
See PROBLEMS #59.

**Also: the jurisdiction table itself is unverified.** `decisions/reporter_jurisdiction.csv` has **196 rows, 100%
`confidence=estimated` and 100% `verification_level=name_inference`** — all inferred from the abbreviation's name,
**not one row checked against an authoritative source** (PROBLEMS #40; Task 7 still has to decide which source to use). The
`jurisdiction` values should therefore be treated as **unverified**; a product that filters on it should keep the ability to filter by `confidence`.

## 5. Columns you need to know

| Column | How to read it |
|---|---|
| `kept` | The `dd >= 5` placeholder threshold, see §3 |
| `is_primary` | The representative row of a group; only one row per `merged_group_id` is `true`. **When counting, deduplicate by group and take the representative row** |
| `case_name_modal` | The modal case name in the group (spelling variants are first folded by normalization, then the most common printed form is taken) |
| `case_name_agreement` | Agreement among voters. **The denominator is "rows that voted"** — rows with no extractable name cast a blank vote and are not in the denominator, so with 1 of 199 rows yielding a name it is still `1.0`. Do not read it as "unanimous" |
| `case_name_support` | Votes for the winning name / `max(counted rows for the key, votes)`. **This is "how many of the judgments citing it stand behind this name"** (PROBLEMS #60); the denominator uses max because self-citation rows still vote but are not counted rows |
| `case_origin` / `deciding_court` | See §4; when not in the table it is `UNDETERMINED`, **not** "equal to jurisdiction" |
| `split_reason` | How this group was split off: `span` (year span) / `decision` (split by judgment using neutral citations) / `unanchored` (no neutral anchor, grouped by co-citation) |
| `same_name_near_year_peers` | Group ids of **other groups** with the same name (equal after normalization) and a year within ±1. **A flag only, not a merge suggestion** (PROBLEMS #62, see §6) |

## 6. Under-count list: each item below means the real citation count is **not lower than** the number in the table

When a number looks low, check this list first instead of concluding "this case is rarely cited".

1. **Two groups with the same name and years within ±1 are not merged** (PROBLEMS #62). Measured (group-level counts): across all groups
   there are 8,329 pairs with the same name and primary-row years within ±1, of which **225 pairs** have both sides over the threshold. They mix two kinds:
   genuinely different judgments (an `R. v. John` every year) and **two forms of the same judgment** (for example *R. v. O'Brien* as
   `(1977), 35 C.C.C. (2d) 209` and `[1978] 1 S.C.R. 591` — the two forms never appear together in any judgment, and nothing in the data
   links them). The `same_name_near_year_peers` column was added for this;
   it also flags genuinely different same-name judgments. A machine cannot tell them apart; **a human has to decide**.
2. **Co-citation units with no neutral anchor** (PROBLEMS #49/#55). Forms that have no neutral citation and zero co-citation with any identity anchor
   can only be grouped with each other and are marked `unanchored`. In the current output, groups over the threshold whose `split_reason` contains `unanchored`
   number **69, with dd totalling 648**. (A narrower count when #55 was recorded gave 56 units, dd totalling 262, of which
   18 had dd ≥5 — the two counts use different definitions; say which one you quote.)
3. **Residual self-citation** (PROBLEMS #54). A judgment's header prints its own citation; the merge layer no longer counts it in dd, but
   `occurrence_count` still includes "self-citation mentions in a parallel form" — when a judgment mentions itself in another reporter's form,
   that mention is still in occurrence; only dd is fully cleaned.
4. **A 1.2% under-count from the extraction layer** (PROBLEMS #63). Against the upstream ground truth shipped with the corpus (74,750 bare neutral citations),
   recall counting only the finally kept spans is **98.80%**. The **872 missed are not unextracted; they lost deduplication to a longer span
   with the case name stuck to it** (`Kvello Estate 2009 SCC 51` displaces `2009 SCC 51`). These **do not become
   wrong answers**: the winning string is always classified `UNSUPPORTED` (some with `unrecognized_series_prefix`),
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
  the group conclusion is aggregated only from qualifying identity bases (anchor / same printed string / bilingual variant / singleton), while evidence from heuristic links
  (name_year / cocitation / typo variants) stays in the noncore_origin_evidence audit column);
  `kept` in `select_out/selected.csv` is still just dd≥5 (semantics unchanged);
  `decide_out/cross_court/effective_sources.csv` is the **only authoritative** "source judgment → case identity"
  link (including the exclusion_reason of removed self-citations).
- **Edges**: one row of `edges/citation_edges.csv` = one (citing judgment, cited case) edge;
  `edges/foreign_edges.csv` holds only FOREIGN edges on **supported paths** (edges reached only through heuristic paths
  are marked edge_support=heuristic_only, foreign_status=UNDETERMINED and go to
  `edges/tentative_edges.csv` — they do not pose as confirmed foreign edges); `edges/self_excluded_edges.csv`
  keeps removed self-citations for audit.
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

## 8. How to confirm the numbers you have are still current

```bash
python pipeline/tests/test_layers.py --golden      # compare the full output with the golden summary, item by item
```

`pipeline/tests/golden_layers.json` stores the counts from each layer's manifest and the top 25 of the ranking — **every
number quoted above shows up here whenever the full chain is rerun**. If `--golden` reports a match, your numbers agree with
those at the time this document was written; if it reports a diff, the data has changed: **use the new numbers from the diff, not the old ones in this document**.

Regression defences: `pipeline/tests/run_regression.py` (extraction layer), `pipeline/tests/test_layers.py`
(layers 2–5: unit assertions, the mini end-to-end chain, the full golden diff).

The output that the numbers in this document refer to: `data/select_out/selected.csv` **206,213 rows / 190,153 groups /
8,610 groups over the threshold** (2026-09-11).
