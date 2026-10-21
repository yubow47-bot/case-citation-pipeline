# Layer 3: merging

Current contract: 2026-10-19, merge schema 10; implementation: [merge.py](../../pipeline/merge.py). This layer arbitrates overlapping candidates, constructs member keys and aggregates observations. It loads no decision tables and makes no cross-judgment identity determination.

## Arbitration and keys

Input is `classify_out/<court>/classified.csv`. Within each source/corpus row, rejected and self-citation candidates do not enter the counting contest. Equivalent same-span/same-key readings fold; support, containment, overlap and boundary constraints determine admissible winners. Unresolved alternatives remain uncounted. Arbitration never resolves a tie by input order and never calls back into extraction or classification.

The structured `merge_key` retains year, volume, normalized abbreviation, series and page slots. Missing slots stay missing. Recognized series prefixes and classification's volume system govern normalization; continuous-volume reporters do not require a printed year in their identity key. This internal key is not a replacement for explicit decision-table lookup fields.

`occurrence_count` counts admitted occurrences. `distinct_decisions_count` is a union of source judgment IDs, not a sum or maximum. These are observation counts at this layer: adjudication computes final measurable DD after identity, self-citation and source-integrity exclusions.

Case-name variants, modal name, agreement, support and `name_classes` retain the evidence used downstream. Missing names contribute no named vote. These fields do not filter rows. Modal names also feed guarded identity proposals and conflict checks, so they are not merely display labels.

## Output and provenance

Each court's output contains:

- `merged.csv`: normalized members, counts, names, observed court annotations and printed-year evidence.
- `mentions_candidates.csv`: every candidate's arbitration outcome, source/corpus row, candidate ID, native span, raw citation, counted key, zone and document-zone evidence.
- `folded_log.csv`, `decision_ids.csv` and `key_mapping.csv`: printed variants, raw source associations and key mappings.
- `history_pairs.csv` and `parallel_runs.csv`: distinct source-bound negative and positive identity candidates, plus `manifest.json`.

No source row is deleted because it is a headnote or is later quarantined. Conflicting recognized court labels remain `court_designation_conflict`; majority voting does not remove the conflict. Source-integrity exclusions apply downstream while original observations remain traceable.

## Co-printed runs and history

[parallel_runs.py](../../pipeline/parallel_runs.py) emits adjacent counted candidates in one source, separated by a comma and optionally up to two classified court/service labels. Intervening case names or prose, semicolons, pinpoints and history connectors end a run. The producer uses row fields and classified suffix proofs; it does not establish that the candidates identify one judgment.

Each run member retains source ID, corpus row, instance ID, ordinal, candidate ID, counted key, native offsets, raw text and preceding gap. The adjudication loader independently verifies counted membership, adjacency and suffix proofs, and seals logical CSV hashes of the input ledgers. Logical hashes survive gzip compaction.

History connectors identify distinct rulings within proceedings and remain a separate negative identity input. An apparent printed parallel is accepted only after the whole-component identity guards in [adjudication](04_adjudication.md).

## Model-judged classification inputs

Merge reads the classification layer's final `rejected_reason` and `candidate_case_name`, so a Jev-adopted name (N2/N5) enters the name vote and a Jev-adopted rejection or readmission (N1) changes counting. Merge itself makes no model judgment and loads no Jev artifact. Provenance stays on the classified row (`case_name_source`, `row_status_source`, `rule_*`).

## Verification and limits

Checks: [parallel runs](../../pipeline/tests/test_parallel_runs.py), [candidate/arbitration contracts](../../pipeline/tests/test_candidates.py), [layers](../../pipeline/tests/test_layers.py), and [source measurement](../../pipeline/tests/test_source_measurement.py). Preserving a native run is provenance, not a population precision claim. New-merge review and duplicated-link measurements remain pending for the new Fix1 run.
