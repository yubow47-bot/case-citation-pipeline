# Replay identity decisions

Use this tool to reuse extraction, classification and merge outputs while rerunning
the identity registry, identity decisions, selection and citation edges.

Run from the project root. Replace `run_NAME` with a completed run; the current
selection is recorded in `data/active_run.json`.

```powershell
python pipeline/replay_decide.py --source-run data/run_NAME --out data/run_REPLAY
```

## Source requirements

The source must be a complete local `data/run_*` directory with verified input
identity and an output SHA-256 seal. The tool checks every retained output and
rejects missing or extra files, paths outside the run, links/junctions, and
uncompressed upstream CSVs. The destination must be new or empty.

Corpus files, upstream code and decision tables must still match the source.
Only the exact downstream inputs listed by the replay tool may change, including
`decisions/identity_court_facts.csv` and `decisions/identity_separations.csv`.
This is not permission to reuse upstream data after arbitrary CSV or helper changes.

Court scope, corpus paths, batch/year limits and language policy come from the
source manifest. Environment variables cannot change that scope. Runs without
`text_policy` retain `english_only`; switching to `en_then_fr` requires fresh
extraction.

## Files and completion

Compressed upstream CSVs use filesystem hard links. Other small metadata files
are copied. If hard links are unavailable, only files of at most 2 MiB may be
copied; a large fallback copy fails. Use a filesystem and execution context that
permit hard links.

The replay records the source manifest, input/output fingerprints, reused steps
and steps actually executed. It retains the upstream files it needs even if the
source directory is later removed. It does not delete that source.

The default storage limits are 12 GiB of logical project files and a 2 GiB free
space reserve. Before completion, the tool rechecks upstream bytes, compresses
new CSVs and seals the retained outputs. Execution or finalization errors mark
the new run `failed`.

These checks establish reproducibility and file integrity. They do not measure
whether the judgment identities are correct.

```powershell
python -m unittest pipeline.tests.test_replay_decide pipeline.tests.test_run_integrity tools.tests.test_storage_monitor -q
```