# recall -- the project experience library

Semantic search over this project's own history: the problem ledger, audit reports,
decision tables, work diary, git log, and the author's AI-assisted working sessions.
It answers one question for a human: *"have we run into something like this before,
and what did we decide?"*

It is a retrieval aid, not part of the pipeline. Nothing here feeds any decision.

## Build

```bash
pip install sentence-transformers      # sqlite-vec, torch, numpy are also required
python tools/recall/build.py           # full rebuild; unchanged text reuses cached embeddings
python tools/recall/build.py --source problems,git
python tools/recall/build.py --no-embed   # count chunks / drop reasons only, no model, no db
```

- Embeddings: `BAAI/bge-m3` (multilingual, 1024-d), run locally.
- Store: one SQLite file, `data/recall/recall.db` (sqlite-vec for vectors, FTS5 trigram for keywords).
  `data/` is gitignored; delete the file any time and rebuild.
- Everything is redacted (API keys, e-mail address, long opaque tokens) **before** it is
  hashed, embedded or stored. `audit_secrets.py` re-checks the finished database.

## Query

```bash
python tools/recall/query.py "a year printed as two parts was missed" -k 8
python tools/recall/query.py "BCCA" --keyword
python tools/recall/query.py "court code used by two countries" --source problems,chat
```

Each hit shows source, a locator (file and line, ledger number, commit hash, session
id) and the first 300 characters. Follow the locator to the original; the original is
what counts, the snippet is only a pointer.

## Three limits (PROBLEMS #101)

The ledger carries the rule "no script may read `PROBLEMS.md`", because earlier
pipeline patch lists began as notes and became load-bearing configuration. This tool
is the first ruled exception, under three conditions:

1. Only `build.py` reads `PROBLEMS.md`, and it lives outside the pipeline.
2. `check_isolation.py` fails if `pipeline/`, `decisions/`, `audit/` or `implementation/`
   reference the library, or if any other code reads `PROBLEMS.md`.
3. `query.py` prints text for people only. It has no `--json`, `--csv` or output-file
   option **on purpose**: results must never become input to a program.

Breaking any of the three ends the exception.

## Checks

```bash
python tools/recall/check_isolation.py   # exit 0 = limits hold
python tools/recall/audit_secrets.py     # exit 0 = no key/e-mail in the database
```

"Similar in meaning" is not "same case". Never use a hit as evidence of jurisdiction,
identity or existence of a citation; those come only from what is printed on the judgment.
