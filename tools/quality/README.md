# Review citation quality

These tools create review queues, probability samples and label evaluations from
a completed run or a ready SQLite snapshot. They stay offline, open source data
read-only and do not change DD or confidence weights.

Run commands from the project root. Replace `data/run_NAME` and `run_NAME` with
the run directory and ID recorded in `data/active_run.json`. Use a separate
output directory for each review package.

## Create review materials

```powershell
python tools/quality/quality.py queue --run data/run_NAME --with-text --output audit/findings/quality/identity_queue.json
python tools/quality/quality.py sample --run data/run_NAME --with-text --output audit/findings/quality/samples.json
python tools/quality/quality.py template --samples audit/findings/quality/samples.json --output audit/findings/quality/manual_labels.csv
```

For an existing database, replace `--run data/run_NAME` with
`--db data/foundation/research.db --run-id run_NAME`. The tool checks the ready
snapshot and available source fingerprints. Missing evidence stays missing.
`--documents` is for caller-supplied fixture metadata, not independent corpus
verification.

The queue scans final members for identity conflicts and high-impact ambiguous
identities. Its default impact threshold is DD >= 20, adjustable with
`--min-impact-dd`. It keeps at most 500 previews within the output limit.
Queue items are review leads, not confirmed errors or a probability sample.

The main sample covers all final countable citation edges. Strata use citing
court, source judgment era, DD bucket, citation kind and edge support. Missing
or conflicting metadata has an explicit unknown bucket. Each nonempty cell
contributes `min(2, N)` edges, with recorded population size, sample size and
inclusion probability `pi`. The default seed is 20261014. Train/holdout folds
are assigned by source judgment, so its edges stay together. Small cells do not
support narrow confidence intervals; a sample may have no holdout.

`--with-text` verifies the original Parquet hash, source ID, selected EN/FR
fields and Unicode offsets before saving bounded context. Without it, a ledger
quote is not verified original text. Whitespace may be folded as the extractor
does; other character differences fail verification. Original offsets and hashes
retain the original text. A verified span does not prove the target identity,
treatment or origin is correct.

## Label and evaluate

Keep the template's identity columns and `record_hash` unchanged. Fill these
dimensions independently:

| Field | Allowed values |
| --- | --- |
| `case_mention` | yes, no, unknown, unverifiable |
| `judgment_identity` | correct, incorrect, unknown, unverifiable |
| `treatment_role` | supportive, applied, distinguished, criticized, overruled, procedural, mentioned, unknown, unverifiable |
| `origin` | correct, incorrect, unknown, unverifiable |

For any labeled dimension, also fill `annotator`, ISO datetime `annotated_at`
and `label_method=manual`. Use `origin_country` for a verified country.
Record uncertainty rather than converting machine output into a human label.

```powershell
python tools/quality/quality.py import-labels --samples audit/findings/quality/samples.json --labels audit/findings/quality/manual_labels.csv --output audit/findings/quality/labels.json
python tools/quality/quality.py evaluate --samples audit/findings/quality/samples.json --labels audit/findings/quality/labels.json --output audit/findings/quality/evaluation.json
```

Import rejects unknown/duplicate IDs, changed record hashes, invalid values and
labels without manual provenance. Evaluation checks sample/label bindings and
reports coverage and rates using `1/pi`, separately for train and holdout.
Blank labels remain in the coverage denominator. Unknown and unverifiable
answers remain separate and are excluded from correctness denominators.
Treatment is reported as categories, not precision.

Rates describe only the labeled, verifiable subset; they cannot establish
population accuracy when labels are missing. With zero human labels, accuracy
is null and status is `not_calibrated`. Older CanLII measurements do not validate
a new run's identities, treatment or origin.

## French supplement

A main sample may contain no edges from French text. Preserve it and generate a
separate package:

```powershell
python tools/quality/quality.py sample-french --db data/foundation/research.db --run-id run_NAME --base-samples audit/findings/quality/samples.json --output audit/findings/quality_fr/samples.json
python tools/quality/quality.py template --samples audit/findings/quality_fr/samples.json --output audit/findings/quality_fr/manual_labels.csv
python tools/quality/quality.py import-labels --samples audit/findings/quality_fr/samples.json --labels audit/findings/quality_fr/manual_labels.csv --output audit/findings/quality_fr/labels.json
python tools/quality/quality.py evaluate --samples audit/findings/quality_fr/samples.json --labels audit/findings/quality_fr/labels.json --output audit/findings/quality_fr/evaluation.json
```

The frame contains final edges whose source rows consistently select nonempty
`unofficial_text_fr` under the run's language policy. A bilingual row that selects
English is excluded. Ambiguous duplicate IDs and missing text are reported.
Language denotes the selected field, not detected language. The supplement
does not measure missed mentions or recall.

It uses the same strata and cell size, with default selection seed 20261015,
source-based folds inherited from the parent and hashes binding it to that
parent sample. Missing mention evidence remains in the frame. Keep its weights
and denominator separate from the main sample. Output must be outside the main
package directory and must not overwrite an existing supplement.

## Cache audit and cleanup

```powershell
python tools/quality/cache_audit.py --db data/foundation/research.db --run-id run_NAME --output audit/findings/quality/embedding_cache_usefulness.json
python tools/quality/cache_cleanup.py --db data/foundation/research.db --run-id run_NAME --output audit/findings/quality/cache_cleanup_plan.json
```

Both commands inspect source data read-only and call no APIs. They compare
actual prepared inputs, model and dimension with cache entries. The audit does
not read vector BLOBs; cleanup planning hashes their contents in bounded chunks.
Cleanup also retains inputs needed by other ready runs and shared methods.
Unreferenced payload bytes are not a guarantee of reclaimable disk space.

After reviewing the plan, explicit deletion uses:

```powershell
python tools/quality/cache_cleanup.py --db data/foundation/research.db --run-id run_NAME --apply --plan audit/findings/quality/cache_cleanup_plan.json --output audit/findings/quality/cache_cleanup_receipt.json
```

Apply requires an unchanged v2 plan, source inputs and cache contents. It checks
space for deletion and VACUUM, then verifies retained content. Removed entries
may include paid query or historical vectors. No cache backup is created.
If deletion commits and VACUUM fails, the tool reports that deletion has already
committed; it cannot claim a full rollback.

Each JSON/CSV is capped at 2 MiB and must stay outside source run/corpus paths.
French sampling also prechecks up to 8 MiB of outputs and bounded census memory;
it fails rather than silently truncating a probability sample.

```powershell
python -m unittest discover -s tools/quality/tests -p "test_*.py" -q
```
