# Build and search a results database

These tools sit outside the production pipeline. They import a completed run
into SQLite and build keyword indexes, citation passages and optional cached
vectors. Derived tables can be rebuilt from the run and corpus snapshots.
Retain human labels, calibration evidence and paid embedding caches before
replacing a database.

Run from the project root. Replace `data/run_NAME` and `run_NAME` with the
directory and ID recorded in `data/active_run.json`, or choose another run
explicitly.

## Build

```powershell
python tools/foundation/after_run.py --run data/run_NAME --db data/foundation/research_new.db --vectors skip
```

The default build is offline. It does not create uncompressed companions for
CSV.gz inputs. To reuse existing vectors without API requests, use
`--vectors cached`. Incomplete cached vectors do not become a ready component.

| Script | Purpose |
| --- | --- |
| `build.py` | Import groups, members, edges, decision tables and document metadata; capture source snapshots |
| `relations.py` | Label identity-based same-case history versus other judgments |
| `score.py` | Optional experimental DD-bucket confidence weights |
| `index_cases.py` | Case profiles and a keyword index |
| `index_edges.py` | One passage per final citation edge, with evidence locators |
| `index_methods.py` | Searchable project methods and method cards |
| `embed.py` | Optional vectors bound to content, model and dimension |
| `acceptance.py` | Full-table integrity checks and a separate relevance benchmark |

A run becomes `ready` only when import, relations, cases, edges, methods and
integrity acceptance are ready for matching inputs. Failed components retain
their generation and error; the run stays incomplete. `--skip-acceptance`
leaves it `building`. Older imports without immutable mention snapshots need
a fresh database.

`run_sources` records paths, logical and compressed hashes, sizes and compression.
Logical CSV hashes survive lossless gzip compression. `run_components` records
generation, status and source fingerprint. Passages store compact references
joined to those source records. Builders verify the imported corpus and mention
snapshots rather than substituting current workspace files.

```powershell
python tools/foundation/acceptance.py --db data/foundation/research_new.db --run run_NAME --suite integrity --publish
python tools/foundation/acceptance.py --db data/foundation/research_new.db --run run_NAME --suite benchmark --mode keyword
```

Integrity checks establish stored contracts and keyword evidence coverage.
They do not prove every judgment identity is correct. The separate relevance
benchmark fails when an expected hit is absent.

## Search

```powershell
python tools/foundation/query.py "standard of appellate review" --db data/foundation/research_new.db --run run_NAME --mode keyword
python tools/foundation/query.py --case XC-G012345 --db data/foundation/research_new.db --run run_NAME
python tools/foundation/query.py --count --min-dd 5 --origin FOREIGN --db data/foundation/research_new.db --run run_NAME
python tools/foundation/query.py "identifier systems" --collection methods --db data/foundation/research_new.db --mode keyword
python tools/foundation/query.py "palpable and overriding error" --collection edges --cited-name Housen --court BCCA --year-from 2020 --db data/foundation/research_new.db --run run_NAME --mode keyword
```

Use a group ID from the selected run. Always pass `--run` when the run matters:
this search command otherwise selects the newest imported ready run; it does
not follow the active-run pointer. Method search is project-wide and reserves
two result slots for method cards.

Default hybrid search stays offline, combining ready vector and keyword ranks.
Missing, stale or failed vectors, or an uncached query embedding, cause an
explicit keyword fallback. `--mode vector` requires ready vectors.
Only `--allow-network` permits new query embeddings or query rewrites.
Configure any API key through `OPENROUTER_KEY_FILE`; keep the key file outside
the repository.

Case/edge filters apply before candidate limits. Their passages come from the
selected run's final edges, excluding rejected mentions and self-citations.
Retained heuristic edges remain eligible and show their support status.
Top hits are not a statistical denominator: use `--count`, full-table SQL or
the [research tool](../research/README.md) for counts.

## Language, weights and accuracy

Manifest `params.text_policy` fixes field selection. Missing policy means
`english_only`; `en_then_fr` chooses nonempty English text, then French,
once per row. Metadata fields follow the same preference; a nonempty English
primary citation still determines the source ID. Document metadata includes
rows without usable text.

Passage offsets refer to the selected original field, not a translation.
Recorded EN/FR fields and hashes are provenance claims until original-corpus
verification checks them. Rebuilding cannot change an old run's language scope.

Raw DD is never changed. Optional `canlii-t6-v1` weights estimate real case
mentions within DD buckets using the run's CanLII calibration:
`weighted_dd = dd * confidence`. They remain experimental and say nothing
about importance, treatment or identity correctness. The build does not borrow
calibration from another run. Zero human labels do not provide current-run
precision; verified text spans and integrity checks do not replace human review.
Use the [quality tools](../quality/README.md) for that review.

## Storage limits

Project database writes enforce 12 GiB of logical project files and a 2 GiB
free space reserve. Inventory ignores links/junctions. SQLite page caps include
rollback-journal headroom; writes to an existing WAL database are rejected until
writers are closed and an explicit checkpoint/rebuild is performed.

The build prechecks an additional 3 GiB peak estimate, checks again between
stages and records the limits. This estimate does not guarantee every dataset
fits. Explicit overrides are available:

```powershell
python tools/foundation/after_run.py --run data/run_NAME --db data/foundation/research_new.db --vectors skip --storage-budget-gb 12 --min-free-gb 2 --estimated-peak-gb 3
```

The units are GiB. Capacity failures roll back the affected transaction and do
not mark incomplete components ready. Keep source evidence and calibration
records when removing obsolete derived artifacts. Read-only inspection remains
available even when the write budget is exhausted.

```powershell
python -m unittest discover -s tools/foundation -p "test_*.py" -v
```