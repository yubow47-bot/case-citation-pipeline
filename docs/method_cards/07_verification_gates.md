# How to verify nothing broke after a change

## First remember these lessons (each one was learned the hard way)

1. **`--golden` only proves the old output did not change; it does not prove the new rule is right** (PROBLEMS #98). New or changed code needs its own end-to-end test run and a manual look at the diff.
2. **Diffs must be full, not sampled**. A sample in the classification layer once missed a 145-row regression.
3. **Acceptance checks both "existing keys grew" and "brand-new keys appeared"**. Experiment line #85 checked only the former and missed a 5-row displacement effect (once rejected rows left the arbitration pool, the junk candidates competing with them became counted).
4. **"Counts are right" does not mean "the semantics took effect"**. After adding a decision table, sample downstream fields to confirm they really got filled (#97: 32 rows loaded successfully with zero effect).
5. **Guards and validation regexes must be tested against real typesetting** (with periods and footnotes); synthetic strings do not count (the #21 guard failed on real footnote citations).
6. **A/B runs need the same input and the same base**, changing only one switch; otherwise the cause of a difference cannot be told.
7. **Measurement scripts must be saved and replayable**. Writing only the number into a document is as good as not measuring (#34).
8. **Using an instrument that structurally excludes a case to prove the case does not exist is circular** (#33: the token regex of `shape_neutral_bare` admits no periods, so it cannot prove "neutral codes never contain periods").

## Command list

[verified: commands and parameters checked against `run_regression.py:401-404`, the `test_layers.py` file header and `run_all.py`; 2026-10-03]

### Extraction layer

| Command | Purpose |
|---|---|
| `python pipeline/tests/run_regression.py --selftest` | Synthetic cases, deduplication-equivalence assertions, the `12n` truncation, the `_SEP` comma probe (should print nothing) |
| `python pipeline/tests/run_regression.py --field-audit` | Five field invariants (shape layer); mandatory after changing `shapes.py` |
| `python pipeline/tests/run_regression.py --verify` | Rereads the parquet row by row and checks the fixture slices match verbatim |
| `python pipeline/tests/run_regression.py --throughput` | Single-core throughput over the full corpus |
| `python pipeline/extract.py --fixture-check` | Fixture acceptance gate (exact tier, A18/B15/C27/D6) |
| `python pipeline/tests/corpus_counts.py` | The only script that produces corpus-level counts (`--dedup`, `--prose-sample`); every corpus-level number in the specification and PROBLEMS must be replayable by it |

Any change to `shapes.py`: run both the regression and `--field-audit`. If negative-control false positives or fixture misses increase, the change goes back for discussion.

### Layers 2–5

| Command | Purpose |
|---|---|
| `python pipeline/tests/test_layers.py` | Unit assertions (171 now) plus the mini end-to-end chain (synthetic data, seconds) |
| `python pipeline/tests/test_layers.py --golden` | Compares the current output with the golden summary (full diff); **only proves the old output did not change** |
| `python pipeline/tests/test_layers.py --golden-write` | Explicitly rewrites the golden summary; use only after changing rules and reviewing every diff item |

Every assertion is pinned to a real pitfall and names its PROBLEMS number; **read that entry before deleting an assertion**. The mini end-to-end chain skips extraction and classification and feeds a hand-built `classified.csv` to the merge layer, because defects where "every layer looks right on its own and only the combination is wrong" can only be caught end to end (#47).

### The audit loop (`audit/`, produces proposals only; production never reads its output)

| Tool | Use |
|---|---|
| `audit/classify_diff.py` | Full row-by-row diff of `classified.csv` before and after changing `classify.py` (`--snapshot`, `--before/--after`) |
| `audit/table_coverage.py` | Decision-table coverage of the extraction output, likely real court codes that slipped through; `--assert-only` pins the definition first |
| `audit/neutral_triage.py` | Three-criterion triage of "likely real court codes" that slipped through |
| `audit/extraction_recall_audit.py` | Measures extraction recall against the ground truth `cases_cited_en` shipped with the corpus |
| `audit/residual_mining.py` | Finds strings that "look like citations but are not covered by extraction", grouped by template (`--court`, `--out`) |
| `audit/gap_audit.py` | Extraction gap audit; clusters residuals so a human can decide whether a new shape is needed |
| `audit/select_content_diff.py`, `audit/r21_diff.py` | Content diffs of the selection table and of a particular fix |

### External check (CanLII)

- `audit/canlii_crosscheck/`: `t1_catalog.py` (database catalogue), `t2_sample_fetch.py`, `t2_compare.py` (edge-level comparison; point `CROSSCHECK_RUN` at the run), `t3_landmarks.py`, `t5_review_packet.py`, `t5_q_resolve.py`, `t6_calibrate.py`.
- Adding a court: add the new court's CanLII databaseId to `DB = {"SCC":"csc-scc","ONCA":"onca","BCCA":"bcca"}` in `t2_compare.py`; stratify the sample by court × period.
- Limits of the conclusions: the CanLII side is not ground truth either; most "no match" cases are identifiers that do not line up. **The accuracy of the whole database cannot be inferred from it**; it only gives stratified estimates.

### Results database and search

- `python tools/foundation/after_run.py --run data/run_X`: import (8 consistency checks), weights, search text, vectors.
- `python tools/foundation/acceptance.py`: fixed-question acceptance (15 case questions, 12 method questions). The case questions lean towards well-known precedents and **cannot stand for overall quality**.

## The order of a full verification

1. Before the change: keep a `classified.csv` snapshot (`classify_diff --snapshot`); note the key counts of the existing run.
2. After the change: `run_regression.py --selftest`, `--field-audit`, `test_layers.py`.
3. Small smoke test: `run_all.py --out data/run_smoke --limit-batches 1`.
4. **Full rerun into a new directory** (`run_all.py --out data/run_<date>_<name>`; the directory must not exist or must be empty; only `status=complete` counts as complete, and completion requires the input identity fingerprint to be byte-identical to the one taken at start).
5. Diff against the old run: new keys, vanished keys, changed existing keys, `kept` changes; explain each class.
6. `test_layers.py --golden`; only if the diff is expected, `--golden-write`.
7. Record it in `PROBLEMS.md` (with `audit/append_problems_entry.py`, which only appends with CRLF and never rewrites the whole file as LF), stating the numbers and the disposition.
8. Handle old runs under the retention rule: keep the newly delivered run plus the previous baseline; older ones are first registered in `implementation/run_registry.csv`, then compressed for archive or deleted (`data/README.md`).

## Sources

Spec §12, §13.1; PROBLEMS #16, #21, #33, #34, #47, #85, #97, #98; `pipeline/tests/`, `audit/`; `data/README.md`.

Verification status: commands and parameters checked against the code (2026-10-03) [verified]; the lessons come from the PROBLEMS text [per spec].
