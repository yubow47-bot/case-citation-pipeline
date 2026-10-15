# Local data

This directory holds generated data and is ignored by Git. Download the case-law corpus separately into `corpus/`; see the project README.

## Current local run

`active_run.json` selects the run, research database and review frames used by the status and research tools. It is local configuration, not a portable release file.

The accepted snapshot on 2026-10-15 is `run_20261015_identity_review`: SCC, ONCA and BCCA; English text with French fallback; 49,674 judgments with text, 230,449 resolved groups, 14,003 groups with DD at least 5, and 490,577 counted edges. Final CSV/SQL data contain 705,476 mentions. These are snapshot counts, not accuracy measurements.

```console
python tools/status.py
python tools/check_run.py --run data/run_20261015_identity_review
```

Check `tools/check_run.py --help` before using a relocated run. The run manifest, input fingerprints and output seal determine its scope. A filename or date does not establish that a run is current.

## Storage

- `run_*/`: retained pipeline runs, with manifests and compressed outputs.
- `foundation/`: local research/search databases and caches.
- `experiments/`: bounded experimental packages and offline reports.
- `run_receipts/`: manifests, logs and deletion receipts for retired outputs.

Do not commit databases, corpus text, generated run tables or API caches. Use the storage tool to preview and explicitly select any cleanup; never delete the active run by guessing from directory names.

## Retired historical outputs

The original outputs for `run_20261003_v16f`, `run_20261002_tables2` and `run_20261003_selfcite` have been retired. Only receipts and selected historical audit results remain. The receipts are not backups of the tables, so an old measurement cannot be replayed from them alone.

[Published retirement receipts](../audit/findings/repository_cleanup_20261015/retired_runs.json) preserve the manifests, hashes and deletion records. Historical CanLII accuracy belongs to its named historical sample; it does not establish current-run precision.

See the [audit retention policy](../audit/findings/README.md), [current release receipt](../audit/findings/project_review_20261015/release_summary_final.json), and [public usage notes](../docs/USAGE.md).

The fixed 270-record main sample now has explicit model reviews, with the local active pointer selecting their labels and evaluation. See the [model review results](../audit/findings/quality_model_review_20261015/README.md). The separate French supplement retains its own review frame.
