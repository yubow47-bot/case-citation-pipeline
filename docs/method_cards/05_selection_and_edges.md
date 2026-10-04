# Layer 5: selection, and the edge files

## What the selection layer does

**One threshold, on `distinct_decisions_count` (DD); no rows are deleted, only flagged with `kept`.**

- Input: `decide_out/cross_court/decided.csv`. Configuration: `select_config.yaml`, chosen with `--profile` (`default` threshold 5, `loose` 2, `strict` 10).
- Output (`select_out/`) [verified: directory listing]: `selected.csv` (all rows plus `kept`; the product reads only `kept=true`; the full table is always kept), `dd_profile.csv` (DD distribution), `manifest.json` (the threshold and its text).
- **DD, not `occurrence_count`**: one judge citing ten times in one judgment is a single legal act; DD also resists OCR noise by construction (a noise string almost always appears in a single judgment, DD=1).
- **The threshold must come after the last merge** (after the adjudication layer's parallel-reporter and cross-court merging). Placed earlier, the same case with 2 under `A.C.` and 2 under `All E.R.` would see both groups cut for missing the threshold, while the truth is 4.
- **No high-frequency bypass** (the old pipeline had a parallel path `occ>=20 and dd>=10…` whose four parameters had no basis).
- The threshold value is **a product decision, not a data decision**, so it lives in YAML, not in code.
- No rows are deleted: it can always answer "why is this case not in the results".

## DD≥5 now has a basis (CanLII calibration, 2026-10-03)

- Spec §11.2 says "`threshold_dd: 5` currently has no basis; it is only a placeholder". That sentence is **out of date**.
- Using a CanLII comparison plus manual checks of the source text (215 edges, a sample stratified by court × period), **the share of edges that are real case citations** (`audit/findings/canlii_crosscheck/run_20261002_tables2/t6_calibration.md`):

  | DD band of the cited case | 1 | 2–4 | 5–9 | 10+ |
  |---|---|---|---|---|
  | Share of real citations | 75% | 82% | 99% | 100% |

  Weighted over all edges: 87.0%. The errors are mainly journals, section numbers, tables of contents and numbers in the text extracted as citations, concentrated at DD≤4.
- So about 99% of the groups kept at DD≥5 are real case citations (this shows the data identifies real cases; **it says nothing about a case's importance**).
- The weights `canlii-t6-v1` (weighted DD = DD × that band's reliability) are in the results database, marked `experimental`; **they do not change `kept` or `select_config.yaml`**. Letting them affect selection is a separate change that needs its own decision.
- Sample limits: only 29 edges were checked in the DD 5–9 band and 57 in the 10+ band, and there is no held-out validation sample yet.

## Edge files (`edges/`, `pipeline/edges.py`)

One edge = `(source_decision, resolved_cited_case)`, where the latter is a `merged_group_id`. **Edge membership comes only from `decide`'s `effective_sources.csv`**; decide is the only authority.

[verified: the `edges/` directory and the `citation_edges.csv` header] Files:

| File | Content |
|---|---|
| `citation_edges.csv` | Deduplicated edges, one per source and group pair. Columns include `foreign_status`, `origin_country`, `group_origin_*`, `edge_support`, `identity_status`, `origin_basis`, `mention_count`, `distinct_decisions_count`, `case_name_modal`, `mention_detail_key` |
| `self_excluded_edges.csv` | `excluded_self` sources: kept for audit and **must not reappear as ordinary edges** |
| `tentative_edges.csv` | Provisional relations reachable only through heuristic paths (name_year, cocitation, unanchored, typo) |
| `foreign_edges.csv` | Foreign-related edges |

- Invariant: the number of counted sources per group == that group's DD (same definition, checked by `edge_dd_mismatch`).
- `edge_support`: a path through `ELIGIBLE_BASES` (`anchor`/`singleton`/`same_citation`/`anchor_variant_bilingual`) → `supported`, and the group-level place of origin can be used; only through heuristic paths → `heuristic_only`, which **does not inherit** FOREIGN/DOMESTIC, `foreign_status=UNDETERMINED`.
- **Relation type** (`tools/foundation/relations.py`, not in the pipeline): if the cited group also contains a citation the source judgment prints for itself → `same_case_history` (another instance of the same litigation, e.g. a Supreme Court judgment citing the lower-court judgment it is an appeal from), otherwise `other_judgment`. Decided by identity, **not by wording such as "APPEAL from"**.

## When adding a court

- **The selection layer usually needs no change.** A new court just adds rows; `kept` uses the same DD threshold.
- What must be asked again is **whether the threshold still fits**: a new court's data quality (many date false positives, failed self-citation detection) lowers the real-citation rate in the low DD bands. Look at `dd_profile.csv` first, then sample-calibrate the new court with the `canlii_crosscheck` method; do not simply apply the SCC/ONCA/BCCA 99%.
- **Reliability bands** for edges need the new court's own sample (court × period); early judgments differ a lot.

## Verification

- A full import into the results database runs 8 checks (`tools/foundation/build.py`): one primary row per group; DD, `kept` and source status consistent within a group; no duplicate edges; edges per group equal DD; every edge has a source judgment; effective links and edges match each other; no foreign-key violations.
- `test_layers.py` has selection-layer assertions ("kept only when DD reaches the threshold; no rows deleted").

## Known pitfalls

| # | Content | Status |
|---|---|---|
| 60 | A gate on `case_name_support` measured net negative; not enabled | Decided not to enable |
| 106 | Case identity groups by case, so the trial, appeal and final judgments of an old case merge into one group; the `same_case_history` flag covers only part of it | Unfixed |
| — | Few verification samples in the DD 5–9 and 10+ bands; the weights have no independent validation yet | To do |

## Sources

Spec §11, §11.2 (corrected above); code `pipeline/select_layer.py`, `pipeline/edges.py`, `select_config.yaml`; `audit/findings/canlii_crosscheck/run_20261002_tables2/t6_calibration.md`; PROBLEMS #60, #105, #106.

Verification status: files, threshold configuration and headers checked against an actual run (2026-10-03) [verified]; calibration numbers come from our own verification sample, see the calibration report.
