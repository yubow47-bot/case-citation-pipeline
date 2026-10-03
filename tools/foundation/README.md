# tools/foundation — results database, DD weights, search

Everything here sits **outside** the production pipeline. The pipeline never reads it; deleting
`data/foundation/` loses nothing that cannot be rebuilt.

## One command after a pipeline run

```bash
python tools/foundation/after_run.py --run data/run_20261002_tables2
python tools/foundation/after_run.py --pipeline-out data/run_YYYYMMDD_x   # run the pipeline, then index
```

Steps (each can also be run on its own):

| step | script | what it does |
|---|---|---|
| import | `build.py` | copies the run's groups, members, edges and decision tables into `data/foundation/research.db`; 8 consistency checks; ~70 s |
| weights | `score.py` | writes `confidence` and `weighted_dd = dd × confidence` per group from the CanLII calibration (`audit/findings/canlii_crosscheck/<run>/t6_bucket_rates.csv`); version `canlii-t6-v1`, status `experimental` |
| case profiles | `index_cases.py` | one text per group (name or DD≥2): name, printed citations, DD/weight, two passages from citing judgments; keyword index (FTS trigram) |
| methods | `index_methods.py` | per-layer records from `pipeline/*.py`, `decisions/`, `docs/`, `implementation/`, `audit/**/*.md` (PROBLEMS.md stays in `tools/recall`, see PROBLEMS #101) |
| vectors | `embed.py` | OpenRouter `qwen/qwen3-embedding-8b`, 1024 dims, one sqlite-vec table per collection; cached by text hash, so a new run only pays for changed texts |
| acceptance | `acceptance.py` | fixed real questions; reports how many find the expected case / method in the top 5 |

## Searching

```bash
python tools/foundation/query.py "standard of appellate review"
python tools/foundation/query.py "上诉审查标准" --min-dd 5
python tools/foundation/query.py --case XC-G012345                 # who cites this case
python tools/foundation/query.py --count --min-dd 5 --origin FOREIGN   # exact numbers, full table
python tools/foundation/query.py "同形缩写怎么消歧" --collection methods --layer classification
python tools/foundation/query.py                                   # interactive prompt
```

Search ranks by meaning and keyword together (reciprocal-rank fusion). Counts and statistics must
come from `--count` or SQL on the full tables, never from the top hits.

## What the weights mean

`confidence` is the estimated share of real case citations among edges whose cited group falls in
the same DD bucket (1 / 2–4 / 5–9 / 10+), measured on 215 hand-checked edges from 360 CanLII-compared
judgments, shrunk toward 50 % for small samples. It says whether the data identified a real cited
case; it says nothing about how important the case is. Raw DD is never changed.

## Keys and secrets

The OpenRouter key is read from `C:\api key\openrouter 1.txt` (override with `OPENROUTER_KEY_FILE`)
and never written anywhere. Strings that look like API keys are removed from text before it is sent.
