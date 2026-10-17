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

[verified: current commands checked against their CLI implementations, 2026-10-16. The earlier command review was on 2026-10-03; the lessons above remain historical evidence, not a claim of manual validation of every later run.]

### Offline regression gate

`python scripts/verify_offline.py --output implementation/verification_NAME` discovers every `pipeline/tests/test_*.py` and executes each in a separate interpreter, then runs the extraction self-test and the foundation, tools, quality, research, audit-reader and citation-context unittest suites. It records each exit code and log in the output directory; any failed suite makes the command fail. Test fixtures use workspace-local temporary directories and isolated storage roots; production storage guards remain enabled. This is the default regression entry point, including the history, court-scope, country and classification suites. The exact assertion count changes as tests are added.

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
| `python pipeline/tests/test_layers.py` | Layer assertions plus the mini end-to-end chain (synthetic data, seconds); also included in `verify_offline.py` |
| `python scripts/check_run_golden.py --run data/run_20261016_fixes_full3 --expect pipeline/tests/golden_runs/fixes_full3.json --output implementation/verification_NAME/golden.json` | Compares an explicit completed run against a separately frozen three-court expectation: per-court counts, cross-court counts and named identity/DD probes |
| `python scripts/verify_offline.py --output implementation/verification_NAME --run data/run_20261016_fixes_full3 --expect pipeline/tests/golden_runs/fixes_full3.json` | Runs all offline suites and that explicit frozen-run comparison together |

The old `test_layers.py --golden` / `--golden-write` interface reads legacy fixed `data/` outputs and `golden_layers.json`; it is retained for historical replay. Use the explicit-run checker for immutable `data/run_*` directories. `fixes_full3.json` characterizes the old full3 run; it is not a human-adjudicated accuracy set and must not be reused as an unchanged expectation for a release intended to change identities or counts. The new checker has no write-baseline option. Any new expectation requires an independently reviewed diff and a new frozen file, while preserving the historical expectation.

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

- `python tools/check_run.py --run data/run_X --output audit/findings/run_X_check.json`: checks selected groups, effective sources, DD, edges and origin-support contracts. Missing output seals are warnings for historical runs; a passing structural report alone is insufficient for release.
- `python audit/verify_followup_release_20261016.py --run data/run_X --output audit/findings/run_X_release.json`: the October 16 release gate asserts the named native-source distinct-judgment pairs, Huard/Wilson, noncases, primary naming, unchanged input bytes, output seals, history instance facts after CSV compression, and RCS/SCR policy proofs. It also runs the general trace contracts for every manifest-declared court plus `cross_court`, requiring all consumed scope artifacts to be sealed. These contracts cover all fact/constraint hashes and references, conflict blockers, solver event sequence, final partitions and source membership. It reports Booty's disputed historical model label without forcing a split. It does not estimate population accuracy or extraction recall.
- The historical `implementation/check_identity_split_trace.py` remains useful for replay, but its CLI discovers existing gzip traces and does not alone prove whole-scope completeness. The release gate explicitly enumerates the manifest scopes; a missing entire court or an existing unsealed trace fails. A history-only check does not cover the rest of the identity ledger.
- Required native evidence includes the source-bound own-citation proofs and the exact-pair distinction facts used by the release. `pipeline/identity_pairs.py::load_pair_separations()` validates corpus/text/span hashes, source documents and printed citation-to-key bindings when loading those facts; `pipeline/tests/test_identity_pairs.py` exercises its positive and negative boundaries. Preserve the source locators and agent-review status. A model label is not human adjudication.
- `python tools/foundation/after_run.py --run data/run_X --db data/foundation/research_candidate_X.db --vectors skip --storage-budget-gb 32`: builds a separate local database, verifies import contracts and immutable source snapshots, builds case/edge/method keyword search, and runs keyword integrity acceptance. The explicit 32 GiB override is an example capacity decision; the production default remains 12 GiB with a 2 GiB free-space reserve. Size the budget from measured project usage and peak demand.
- `after_run.py` is offline by default. `--vectors skip` records vectors as `missing`; `--vectors cached` only reuses local cached embeddings. Weights remain `missing` unless this exact run has calibration. A `ready` keyword database does not claim vector coverage, calibrated relevance, semantic accuracy or canonical publication. `--skip-acceptance` leaves it unpublished/building.
- `python tools/foundation/acceptance.py --db data/foundation/research_candidate_X.db --run run_X --suite integrity --mode keyword --output audit/findings/run_X_keyword_integrity.json`: rechecks full-table keyword integrity and immutable evidence. The separate `--suite benchmark` runs 15 case, 12 method and 16 extension questions; these fixed questions **cannot stand for overall quality**. Rebuild the methods component after documentation changes, before its source snapshot is frozen.
- Prepare reversible local adoption only after the run and candidate database pass their gates: `python scripts/adopt_run.py --run data/run_X --db data/foundation/research_candidate_X.db --receipt implementation/adopt_X.json --storage-budget-gb 32`. Preparation checks run/input/output identity, the candidate's `ready` components and SQLite integrity, preserving the old pointer and planned rollback paths. `python scripts/adopt_run.py --receipt implementation/adopt_X.json --apply` switches the canonical database and active pointer; `--rollback` restores both and can recover interrupted adoption states. Retain the receipt and old database. Adoption checks byte/state integrity; review the semantic release receipts before applying it.

## The order of a full verification

This is an optional full regeneration and release workflow. A request to edit or fix code alone does not initiate a full corpus rerun, candidate database build, or active-data switch. Follow the user's requested scope; stop these operations when the user declines them.


1. Before the change: keep a `classified.csv` snapshot (`classify_diff --snapshot`); note the key counts of the existing run.
2. After the change: run `scripts/verify_offline.py`; additionally run extraction `--field-audit` when shapes change. Require nonzero exits to stop the verification; retained logs without exit codes are not a gate.
3. Small smoke test: `run_all.py --out data/run_smoke --limit-batches 1`.
4. **Full rerun into a new directory** (`run_all.py --out data/run_<date>_<name>`; the directory must not exist or must be empty; only `status=complete` counts as complete, and completion requires the input identity fingerprint to be byte-identical to the one taken at start).
5. Diff against the old run: new keys, vanished keys, changed existing keys, `kept` changes; explain each class. `python tools/compare_runs.py --old data/run_OLD --new data/run_NEW --output audit/findings/run_NEW_comparison.json` checks original-candidate preservation, full merged-to-selected membership and unique selected sources. Its pass does not certify semantic identity accuracy.
6. Run structural, full-scope identity trace, native-evidence and release-specific assertions. Compare an unchanged historical run against its frozen three-court expectation when relevant; do not rewrite old expectations to make a changed release pass. Preserve full diffs and source evidence for changed rules.
7. Build and accept a separate offline keyword database. Freeze method documentation before indexing it. Prepare a reversible adoption receipt, review all release receipts, then apply it and verify the canonical pointer/database agree. Vector generation and calibration require their own explicit coverage/evaluation work.
8. Record it in the current index and history of `PROBLEMS.md` (with `audit/append_problems_entry.py --fragment history.txt --current-fragment current.txt`, which validates synchronized current/history rows and preserves CRLF), stating the numbers and the disposition. Distinguish agent/model checks from human labels and distinguish audit flags from proven errors.
9. Handle old runs under the retention rule: keep the newly delivered run plus the previous baseline; older ones are first registered in `implementation/run_registry.csv`, then compressed for archive or deleted (`data/README.md`). Preserve active rollback evidence while adoption remains reversible; never rewrite sealed run bytes for a new audit.

## Sources

Spec §12, §13.1; PROBLEMS #16, #21, #33, #34, #47, #85, #97, #98; `pipeline/tests/`, `audit/`; `data/README.md`.

Verification status: current commands and defaults checked against the code (2026-10-16) [verified]; the lessons come from the PROBLEMS text [per spec]. Passing receipts describe their stated run, contracts and sample only.
