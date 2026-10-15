# Query citation data

This offline tool computes counts, rankings and court-by-decade tables from the
full citation data, then writes a small answer packet with evidence and provenance.
It uses fixed queries and answer templates. It does not call a model or infer
legal treatment from a citation.

Run from the project root. Examples use `--language en` for English output.

## Find a case and inspect its citations

```powershell
python tools/research/research.py find "Housen" --top 5 --language en --output audit/findings/research/group_lookup.json
python tools/research/research.py ask --db data/foundation/research.db --run-id run_NAME --intent case_citations --group-id XC-G012345 --with-text --language en --output audit/findings/research/case.json
```

Use the selected candidate's `review_arguments` to supply the actual database,
run and group ID. Group IDs apply only to their run.

`find` matches literal recorded case-name fragments across all groups, counts
all matches, then shows the top N by DD and ID. It uses Unicode case folding
while preserving accents; spelling variants and missing aliases are not inferred.
Separate candidates are not automatically treated as the same judgment.
Printed years and group origin are not verified judgment dates or edge origin.

## Counts, trends and rankings

```powershell
python tools/research/research.py stats --evidence-limit 0 --language en --output audit/findings/research/court_decade.json --csv audit/findings/research/court_decade.csv
python tools/research/research.py ask --intent count --court SCC --year-from 2000 --year-to 2020 --origin FOREIGN --language en --output audit/findings/research/count.json
python tools/research/research.py ask --intent ranking --court ONCA --top 10 --language en --output audit/findings/research/ranking.json
```

Supported intents are `count`, `court_decade`, `ranking` and `case_citations`.
A small English/Chinese question grammar is also available, such as
`"count citations"` or `"top 10 most cited cases in ONCA"`. Use explicit
`--intent` and filters for other combinations. Unknown questions return
`unsupported`; `--answer-mode model` is unsupported too. Exit codes are
0 for a supported answer, 1 for data/argument errors and 2 for unsupported requests.

By default, `data/active_run.json` selects the database and run. The tool checks
the pointer, database snapshot and run manifest together; mismatches fail.
If the pointer is absent, it tries `data/foundation/research.db`, requiring
`--run-id` when several ready runs exist. For a historical database, supply
`--db` and `--run-id` explicitly. A relocated source directory may be passed
with `--run-dir` only if its manifest matches the imported snapshot.
SQLite is opened read-only in one snapshot.

## Without an existing database

```powershell
python tools/research/research.py stats --stream-run data/run_NAME --corpus-dir corpus --evidence-limit 0 --language en --output audit/findings/research/stream_stats.json
```

CSV/CSV.gz inputs are streamed into compact in-memory tables without an
uncompressed copy or persistent cache. Memory grows with the number of groups,
edges and documents, so an existing database is preferred. Corpus metadata is
checked against manifest hashes. `--documents metadata.csv.gz` can instead
supply `court,corpus_row,source_id,citation,name,decision_date,corpus_path`;
it is explicitly marked caller-supplied and not independently corpus-verified.

## Interpret the results

- An edge is a source judgment identifier mentioning a cited judgment group.
  It does not establish approval, reliance or treatment; procedural history can
  count. Ranking `filtered_dd` is recomputed within the filters, while
  `global_dd` retains the run's DD. Evidence/top-N limits do not change totals.
- Dates come from valid source judgment dates. Missing, invalid or conflicting
  dates stay unknown; year filters exclude unknown years. Repeated source IDs do
  not multiply edges. Missing document metadata has explicit unknown buckets.
- Document denominators describe corpus metadata, including judgments without
  citations or usable text. They are not counts of processed nonempty judgments,
  especially for batch-limited runs. Origin/DD/group filters change the edge
  numerator, not the document universe.
- Origin coverage uses edges. Only supported edges with determined origin count
  as determined; heuristic-only edges stay unknown even when group origin is
  known. Both FOREIGN/all and FOREIGN/determined are reported. Unknown origin
  cannot be assumed random. Origin-filtered packets retain
  `origin_coverage_context` for the same scope before that filter.
- Contract checks reject inconsistent tables. Passing them does not measure
  semantic accuracy or supply a human precision estimate.

## Evidence and output

Packets record the manifest, input fingerprint, source hashes, fixed SQL and
parameters, results, limitations and a canonical JSON SHA-256. CSV rows include
run/parameter/packet identifiers; use the companion JSON for full context.

`--evidence-limit` is 0–10, default 3. These deterministic previews are not a
random quality sample. By default the tool locates the counted mention and
offsets without reading original text. Only `--with-text` verifies corpus
hashes, source IDs, selected fields and Unicode spans before marking evidence
`original_text_verified`. Missing or mismatched evidence is reported.

Whitespace folding follows extraction rules, but offsets and original text
hashes retain original whitespace. Language policy comes from the manifest:
missing policy means `english_only`; `en_then_fr` prefers English and falls
back to French once per row. EN/FR field labels do not detect language.

JSON/CSV outputs are each capped at 2 MiB, atomically replaced, and cannot
overwrite source data or the active pointer. There are no downloads, database
copies or embedding-cache writes.

```powershell
python -m unittest discover -s tools/research -p "test_*.py" -v
```