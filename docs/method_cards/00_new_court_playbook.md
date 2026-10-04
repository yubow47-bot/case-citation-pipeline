# Adding a new court: the overall procedure

## First work out which case you are in

| Situation | Example | Most of the work is in |
|---|---|---|
| Citation forms are basically the same as an existing court's | Another province's court of appeal | Decision tables (court codes, reporter abbreviations, homograph ranges) and checking |
| It has its own identifier system | Tribunal file numbers, `J.E. 2004-1234`, `WT/DS58`, database identifiers | **Add rows to `id_prefixes.csv` (no new regex)**; database identifiers go through the classification layer's `identifier_systems.csv` |
| The judgment header does not print its own citation | CITT's `citation_en` is a file number; self-citations count 0 (experiment line E2) | Self-citation detection, identity anchors in the adjudication layer |
| It has French judgments | Quebec | The bilingual neutral-code table `bilingual_neutral_codes.csv`, the French numbering style `no` |

## Procedure (in order)

**0. Get the corpus** [verified: `pipeline/extract.py:65`]
- The corpus is `corpus/<court code>.parquet`, a read-only snapshot. Columns: `citation_en` (the judgment's own citation), `document_date_en`, `unofficial_text_en`.
- A snapshot must have its download date, byte count and SHA-256 recorded (spec §1.3). Existing snapshots must not be rewritten, moved or deleted.
- The download script is `scripts/download_corpus.sh`; note that it originally targeted the SCC plus the Ontario courts, so run `list` first to check that its target list includes the new court.

**1. Probe the corpus first; do not run straight away**
- Is `citation_en` a real citation? CITT's is a file number, so `source_decision_citation` becomes `CITT_<file number>` and self-citation detection stops working.
- Does the judgment header print its own citation? The SCC and ONCA print it within the first 3,000 characters of every judgment (PROBLEMS #13, measured 100%). Measure the new court yourself; do not assume.
- Are there zero-padded numbers in citations (`2007 BCCA 0443` vs `443`)? BCCA has them, and so do the SCC (520 times) and ONCA (27 times) (PROBLEMS #90, still unfixed; #105 fixed only self-citations).
- Are judgment dates extracted as citations (`1 June 2007`)? Measured 13.8% for BCCA and 60.9% for CITT (#85, fixed in the classification layer).

**2. Run extraction (small smoke test)**
- Choose courts: environment variable `PIPELINE_COURTS=BCCA,CITT` or `run_all.py --court X` (`run_all.py:196`, `extract.py:66`).
- Smoke test: `python pipeline/run_all.py --out data/run_smoke --court NEW --limit-batches 1`.
- Judgment id format `{court}_{nk(citation_en)}` (`extract.py:364`); **it must carry the court prefix**, otherwise the cross-court union treats two courts' numbers that happen to share a format as the same judgment.

**3. Look at the classification output and find the gaps**
- See which rows are `UNSUPPORTED`, `unrecognized_series_prefix`, `date_form`, `table_conflict`, and which bracketed designations are `unrecognized`.
- Coverage: `python audit/table_coverage.py` (likely real court codes that slipped through).
- Did extraction miss anything: `python audit/residual_mining.py --court NEW --out audit/findings/<directory>` (finds strings that "look like citations but are not covered by extraction", grouped by template).
- Do not guess. If nothing can be found, leave it `UNSUPPORTED` and record it.

**4. Find the layer to change from the symptom (change only the layer that produces the problem)**

| Symptom | Layer | What to do |
|---|---|---|
| A citation form is not extracted at all | Extraction | A new shape or a new slot; go through the admission criteria, see `01_extraction.md` |
| Extracted, but the jurisdiction is `UNSUPPORTED` | Classification | Add sourced rows to a decision table, see `06_decision_tables.md` |
| The same abbreviation means different reporters in different countries/eras | Classification | Several rows for the abbreviation, with volume or year ranges (#52, #100, #102) |
| Dates, journals, section numbers taken as citations | Classification | Reject on structural criteria (`rejected_reason`); do not change extraction (#85) |
| Case name cut wrong, pulling in a whole sentence of prose | Classification | §8.7 case-name cleaning (#43, #45, #57, #58, #61) |
| One case split into several groups, or different cases merged into one | Adjudication | Identity criteria (#48, #49, #55, #56, #88) |
| DD inflated or miscounted | Merging or adjudication | Union cardinality, self-citation (#46, #47, #54, #105) |
| Place of origin (foreign case, Privy Council appeal) not resolved | Adjudication | `case_origin*`, scope rule tables (#59, #64–#68) |
| How much to keep, threshold | Selection | `select_config.yaml`, flags only |

**5. Verify (after every change)**, see `07_verification_gates.md`:
`run_regression.py --selftest`, `--field-audit`, `test_layers.py`, `--golden` (only proves the old output did not change, #98), and the full classification diff `audit/classify_diff.py`.

**6. Full run**
- `python pipeline/run_all.py --out data/run_<date>_<name>` (the output directory must not exist or must be empty; only `status=complete` counts as complete).
- After the run, build the results database and search: `python tools/foundation/after_run.py --run data/run_...`.

**7. External check (optional, but recommended)**
- If the new court has a CanLII database, sample-compare with `audit/canlii_crosscheck/`; add the new court's CanLII databaseId to `DB = {"SCC":"csc-scc","ONCA":"onca","BCCA":"bcca"}` in the comparison script.
- Stratify the sample by court and period; early judgments differ more.

## An empty table is not a fault (spec §13.4)

Right after a new court is added, many rows are `jurisdiction=UNSUPPORTED` and `case_origin=UNDETERMINED`. That is the correct state: it says truthfully "not yet verified". The old pipeline looked well filled because it filled gaps with inferences, a good share of which were wrong.

## Rules for working on this line

- Constraint one: do not add lists downstream that work around upstream defects. If upstream has a defect, fix upstream.
- After changing `shapes.py` or a rule, **only a full rerun counts**; samples miss regressions (the classification layer once missed 145 rows in a sample).
- Acceptance checks both "existing keys grew" and "brand-new keys appeared" (experiment line #85 checked only the former and missed a 5-row displacement effect).
- "Counts are right" does not mean "the semantics took effect": after adding a decision table, sample downstream fields to confirm they really got filled (#97: a column-name mismatch meant 32 rows loaded successfully with zero effect).
- The audit loop's output (`audit/`) is a proposal; no production script may read it.

## Sources

Spec §1.3, §2, §3, §4.3, §12, §13.4; PROBLEMS #13, #85, #90, #97, #98, #105; experiment-line record `implementation/exp_bcca_citt_findings.md`; code `pipeline/extract.py`, `pipeline/run_all.py`.

Verification status: commands, file names and parameters checked against the code (2026-10-03) [verified]; the symptom-to-layer table is based on the specification and PROBLEMS [per spec].
