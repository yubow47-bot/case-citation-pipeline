# Inspect project status

Run from the project root:

```powershell
python tools/status.py --output audit/findings/project_status.json
python tools/status.py --db data/foundation/research.db
python tools/status.py --verify-run data/run_NAME --output audit/findings/project_status.json
```

The default report reads file sizes, directory metadata, small manifests and
database status records. It does not decompress citation tables, read judgment
text or recalculate large corpus/database/cache hashes. Recorded hashes are
identified as recorded, not newly verified.

`--verify-run` explicitly performs the more expensive core-output and output-seal
check for one plain local run. Links and junctions cannot redirect it to another
copy. This still does not measure citation or identity accuracy.

## Selecting a run

By default, the report uses `data/active_run.json`. Paths may be relative to the
project root:

```json
{
  "run_id": "run_NAME",
  "run_directory": "data/run_NAME",
  "db_path": "data/foundation/research.db",
  "input_fingerprint": "recorded-input-sha",
  "quality": {
    "samples": "audit/findings/quality/samples.json",
    "labels": "audit/findings/quality/labels.json",
    "evaluation": "audit/findings/quality/evaluation.json"
  }
}
```

`quality` is optional. Add independent review packages as a `supplements` list
inside it, with unique `id`, `samples`, `labels` and `evaluation` fields.
At most eight supplements are supported. Their frames, denominators and weights
remain separate.

An explicit `--db` takes priority. If the pointer is absent, the default database
is `data/foundation/research.db`; multiple runs are listed without guessing a
current run. Pointer/run/fingerprint mismatches are reported.

## Reading the report

Pipeline completion, database readiness and component readiness are separate.
Keyword readiness requires matching ready generations for import, relations,
cases, edges, methods and acceptance. A ready run row alone is insufficient.
Missing, stale or failed vectors are reported separately.

The report shows court scope, corpus inputs, date/batch limits and language
policy. Older manifests without a policy mean `english_only`. With
`en_then_fr`, English text is preferred and French is used when English is
empty; a bilingual row is used once. Document metadata counts can include rows
without usable text and are not a count of processed nonempty judgments.

Review counts and small JSON hash bindings identify missing, mismatched or
unbound packages. They do not recheck original evidence or label correctness.
Zero human labels provide no accuracy estimate. Historical experimental weights
do not establish calibration for the selected run.

Storage inventory does not follow links/junctions. It shows a 12 GiB logical
file budget and a 2 GiB free space reserve; logical lengths differ from allocated
disk space. The report does not clean, rebuild or download anything.

JSON output is limited to 2 MiB and atomically replaces the chosen report.
Source runs, corpus files, the database and the active pointer cannot be output
targets. A successful report exits 0 even when `status=attention`; input/output
errors or explicit run-verification failures exit 1.

```powershell
python -m unittest discover -s tools/tests -p "test_status.py" -v
```