# Layer 3: merging

## What this layer does

**Cross-row statistics: counting, voting, folding.** It makes no cross-judgment judgements and **loads no file under `decisions/`** (this is the boundary with the classification layer; the merge layer reads only the fields in the rows).

- Input: `classify_out/<court>/classified.csv`.
- Output (one set per court, `merge_out/<court>/`) [verified: directory listing and `merged.csv` header]:
  - `merged.csv`: one row per "key";
  - `mentions_candidates.csv`: the per-candidate **arbitration ledger** (candidate id → arbitration status, what it yielded to, notes), the backbone of tracing;
  - `folded_log.csv`: the folding log (printed variants of counted rows);
  - `decision_ids.csv`: key → the union of ids of the judgments citing it;
  - `key_mapping.csv`, `manifest.json`.
- `merged.csv` columns: `merge_key`, `canonical_string`, `abbreviation`, `citation_kind`, `jurisdiction`, `jurisdiction_confidence`, `case_name_modal`, `occurrence_count`, `distinct_decisions_count`, `case_name_agreement`, `case_name_support`, `variants_count`, `candidates_admitted`, `candidates_rejected`, `self_citation_of`, `self_case_name`, `name_classes`, `observed_deciding_court`, `court_designation_*`, `year_printed`.

## Two jobs

### 1. Overlap arbitration within a judgment (only on the all-candidates route; spec §9 does not describe it, so the code is authoritative) [verified: `merge.py` file header and `arbitrate_document`, `merge.py:351`]

The extraction layer supplies all overlapping candidates. Within one judgment (same `source_decision_citation` + `corpus_row_index`), overlapping candidates go through one round of arbitration that decides which one counts:

- Row-level split first: a `rejected_reason` → `rejected_row`; `self_citation=true` → `self_citation_row`; neither takes part in the contest.
- Same span and same key fold into one equivalence class and count once.
- Attack relations (the winner suppresses the loser): `support_span` (same span, different meaning, strictly stronger table evidence), `same_key` (same key, different spans, the longer wins), `contained` (compatible containment, the longer wins), `dominated` (partial overlap, higher support grade), `conflict_*` (same grade, cannot be decided, mutual), `cross_boundary` (a parse crossing a boundary).
- Final states: **IN** (counted), **OUT** (suppressed), **UNDEC** (a standoff or no evidence; **not counted, abstains**). A pure mutual cycle stays UNDEC; it is never broken by input order or shape order.
- **"Abstain" means a count of 0**, not 0.5 and not a double count. This is the counting version of constraint four.
- Arbitration **never** calls back into the extraction or classification layers.
- Status values (measured on BCCA): `counted`, `alternative_unsupported_reading`, `self_citation_row`, `rejected_row`, `alternative_contained`, `alternative_same_key`, `span_alternative_undecided`, `overlap_undecided`, `cross_boundary_invalid`, `alternative_weaker_support`, `year_reread_as_vol_invalid`, `alternative_dominated_by_support`.

### 2. Keys, counts, votes

- **The merge key** is built from structured fields, not by flattening the whole string: `year|vol|nk(abbreviation)|series|page`. A missing volume leaves an empty slot rather than being omitted (`1978||ac||728` and `1978|1|ac||728` are two keys; whether to match loosely is undecided, #2). `merge_key` is an internal identifier and is not used to join decision tables (constraint seven).
  - A recognized series prefix is merged into the abbreviation slot (`Q.R.` and `L.R.` give different keys, #53).
  - The year slot is zeroed for reporters with "continuous volume numbering" (`volume_system`, stamped by the classification layer).
- **Counts**: `occurrence_count` counts only counted rows (excluding row-level false positives and self-citation rows); `distinct_decisions_count` (DD) is **the cardinality of the union of judgment ids**, not a maximum and not a sum (#46). Judgment ids carry the court prefix, so they are unique across courts by construction.
- **Case-name voting**: two levels — first fold spelling variants by `nk()`, then take the mode; a tie goes to the more recent year (#44). The denominator of `case_name_agreement` is "rows that voted"; rows with no extractable case name cast a blank vote, so with one named row out of 199 it still reports 1.0; hence the additional `case_name_support` (winning votes / max(counted rows, votes)) (#60).
- **Quality columns do not filter**: `case_name_agreement`, `variants_count` and `candidates_admitted/rejected` are only an ordering aid for manual review; **never filter rows on them** (with few candidates agreement tends to 1.0 and is no evidence). Selection belongs to the selection layer, and its criterion is DD.
- **Single-valued fields within a group** (`citation_kind`, `jurisdiction`, etc.) may disagree within one key (`FC` and `F.C.` share a key): take the mode over counted rows, and on a tie the row holding `canonical_string`; the number of disagreeing groups goes into the manifest's `groups_with_internal_disagreement`, never silently (#42). The merge layer does not adjudicate.
- `name_classes`: the distribution of case-name classes printed by the key's counted mentions (e.g. `housen:4|chieu:2`), a purely informational column used by the adjudication layer's mixed-key criterion (#88).

## Four invariants before writing (refuse to write if any fails) [verified: `merge.py` file header]

1. For each key, the sum of `folded_log` counts == `occurrence_count`.
2. DD is a union cardinality.
3. Rows in `mentions_candidates.csv` == input candidate rows (no candidate is deleted, constraint five).
4. For each key, rows in `decision_ids.csv` == `distinct_decisions_count`.

## When adding a court

- **The merge layer is essentially court-agnostic**: parameterized with `--court <code>`, same rules. **Usually no change is needed.**
- Watch what comes down from upstream:
  - Zero-padded numbers form their own key (`1999 BCCA 0010` vs `10`): **#90, still unfixed**; BCCA 319 entries, SCC 520 times, ONCA 27 times. #105 handled only "a judgment citing itself", not "zero-padded forms when citing other cases".
  - Dates taken as citations inflate counts badly (#85): first confirm the classification layer's `date_form` blocks them.
  - If self-citation detection fails (e.g. `citation_en` is not a citation), every judgment's DD is over-counted by one.
- The new court's counting definition must match the SCC/ONCA one: DD is a union; do not compute it some other way.

## Verification

- `python pipeline/tests/test_layers.py`: merge-layer unit assertions and the mini end-to-end chain.
- Conservation check: the sum of `occurrence_count` over groups == total counted rows (#47; the mini chain asserts it).
- When comparing after a full rerun, check both "existing keys grew" and "brand-new keys appeared".

## Known pitfalls

| # | Content | Status |
|---|---|---|
| 2 | Whether forms that omit the volume are the same citation | Strict matching, not merged |
| 42 | Which value to take for single-valued fields within a group | Take the mode, recorded in the manifest |
| 44 | Case-name voting counted raw strings, so punctuation and spaces mattered | Fixed (two-level voting) |
| 46 | Numbers alone were not enough for the adjudication layer to get DD right; summing inflated it by 62–90% | Fixed (`decision_ids.csv`) |
| 47 | In the cross-court round occurrence was inflated 1.59× | Fixed (recomputed with `key_occurrence_count`) |
| 53 | The merge key did not include the series prefix | Fixed |
| 60 | "One vote decides the name": rows with no extractable name do not vote | `case_name_support` added; **a gate on it measured net negative and is not enabled** |
| 72 (B9) | Case-name voting included non-counted candidates (43.7%) | Status [unverified]; go by the PROBLEMS text |
| 76 (B13) | Year read as volume | Measured: 0 counted |
| 90 | Zero-padded numbers form their own key | **Unfixed** |

## Sources

Spec §9; code `pipeline/merge.py` (file header, `arbitrate_document`, `build_merge_key_v2`); PROBLEMS #2, #42, #44, #46, #47, #53, #60, #72, #76, #90.

Verification status: files, columns, arbitration statuses and invariants checked against the code and BCCA measurements (2026-10-03) [verified]; key and voting details [per spec].
