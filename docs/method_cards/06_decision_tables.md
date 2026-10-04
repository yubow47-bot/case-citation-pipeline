# Decision tables: what to know before adding rows

## General rules

- Directory `decisions/`, **all committed to git**; the only irreproducible thing in the project. `data/` can be deleted wholesale and rebuilt; these tables cannot.
- **Every row must have `source` and `source_locator`** (constraint eight). Rows without a source must not enter a table; determinations must not be written into code.
- **Keys must be facts printed in the judgment** (printed abbreviation, court code, the citation string itself), never keys, group ids or row numbers computed by the pipeline (constraint seven). That way, however the pipeline changes, the results of manual verification never become invalid.
- The pipeline **only reads** `decisions/*.csv`; it does not call the table-building scripts in `decisions/tools/` and does not go online. The building scripts are run by hand when a person decides to rebuild or extend a table (the key comes from an environment variable or `--key-file` and never goes into the repository; rate limit 1 request/second).
- An empty table is not a fault (spec §13.4). Prioritize filling by the coverage reports `audit/table_coverage.py` and `pipeline/coverage_report.py`, in descending DD order; the long tail stays `UNSUPPORTED`.
- **Loaded is not the same as in effect**: a misspelled column name or a status value outside the allow-list makes rows be silently ignored. After wiring in a table, sample downstream fields to confirm they really got filled (PROBLEMS #97).

## The ten tables: who reads them, what the key is, whether a new court needs changes

[verified: row counts and status distributions from `decisions/*.csv` (2026-10-03); readers from `classify.py:1043`, `decide.py:142-462`]

| Table | Rows | Read by | Key (printed fact) | When adding a court |
|---|---|---|---|---|
| `neutral_court_codes.csv` | 327 | Classification, registry | `court_code` (the segment printed in judgments, e.g. `ONCA`) | **Must add** the new court's own code and the foreign codes it often cites |
| `reporter_jurisdiction.csv` | 197 | Classification | `abbreviation` + `jurisdiction` (composite key) + volume/year ranges | Reporters the new court often cites that the table lacks; homograph abbreviations get range rows |
| `series_prefix.csv` | 4 | Classification | `canonical_prefix` (`L.R.`, `Q.R.`) | Rarely |
| `identifier_systems.csv` | 16 | Classification, adjudication | `printed_token` (**verbatim, case-sensitive**) | Database/vendor identifiers in the court's judgments |
| `id_prefixes.csv` | 15 | **Extraction** (generates the regex of `shape_registered_id`), classification | `prefix_id`; reverse lookup by `canonical_token` | File numbers (docket) and publisher judgment numbers (decision); for "prefix + number" identifiers in a new court, just add rows. All statuses are `unverified_*`: until verified the jurisdiction is UNSUPPORTED and the decision type is not counted |
| `non_citation_words.csv` | 39 | Classification (step2) | `word` + `match_type` (case-sensitive) | Fake reporters whose abbreviation slot holds a structural word / calendar word / case-name fragment; add rows when a new court shows new noise words; the building script asserts zero hits on already-resolved rows |
| `court_designations.csv` | 16 | Classification | `printed_designation` (court designation in parentheses) | Parenthetical designations common in the new court (`(Ont. C.A.)`); coverage is currently insufficient (#94) |
| `bilingual_neutral_codes.csv` | 46 | Adjudication | `code_en` ↔ `code_fr` | When there are French judgments |
| `case_origin.csv` | 203 | Classification (loading), adjudication | `citation_display` (printed citation string) | Privy Council-type appeals; source is CanLII's `ukpc` database, covering 1888–1959 |
| `case_origin_manual.csv` | 32 | Adjudication | `printed_citation` | Places of origin verified manually case by case |
| `court_or_reporter_scope.csv` | 12 | Adjudication | `printed_key` + date window | Exclusive place-of-origin rules for courts/identifiers |
| `reporter_origin_scope.csv` | 40 | Classification (`volume_system`), adjudication | `printed_abbreviation` + date window | Exclusive reporter-scope rules |

## Each table's "trust grade": which rows actually drive determinations

| Table | Column | Values (current distribution) | Which take part in determinations |
|---|---|---|---|
| `reporter_jurisdiction.csv` | `confidence` | `estimated` 197 rows (**all**) | Can only be upgraded to `jurisdiction`, **never to a fact about place of origin** (constraint nine) |
| Same | `verification_level` | `verified_print_evidence` 101, `name_inference` 56, `verified_authority` 30, `authority_identity_only` 9, `authority_country_only` 1 | The pipeline **does not read** this column; it only records how hard the evidence is |
| `identifier_systems.csv` | `verification_status` | `verified_authoritative_manual` 13, `verified_official_source` 3 | Only these two drive inference (`ALLOWED_IDENTIFIER_STATUSES`) |
| `court_or_reporter_scope.csv` | `verification_status` | `verified_scope_rule` 12 | Only rows starting with `verified` take part |
| `reporter_origin_scope.csv` | `verification_status` | `verified_mixed` 22, `verified_exclusive_publisher` 13, `verified_exclusive_statute` 5 | Only `verified_exclusive_statute` and `verified_exclusive_publisher` take part; `verified_mixed` is **record only** and never produces a place of origin |
| `case_origin_manual.csv` | `status` | `verified_research_agent` 32 | Only this one value |
| `bilingual_neutral_codes.csv` | `verification_status` | `rejected_renamed_code` 27, `verified_explicit_equivalence` 15, others 4 | Only `verified_explicit_equivalence` takes part in identity equivalence (`ALLOWED_BILINGUAL_STATUSES`, `decide.py:450`); candidate endpoint pairings are not authorized automatically |
| `court_designations.csv` | `status` | `recognized` 13, `ambiguous_designation` 3 | Exact match (looked up after nk normalization) |

## How to add a row (procedure)

1. First find **a source that can be checked against the judgment itself or authoritative material**: the CanLII API, the McGill Guide, the Department of Justice abbreviation list, AGLC, etc. **The roughly 70 hard-coded determinations of the old pipeline must not be used as input**; they may only be used for a comparison afterwards.
2. Fill in `source` (who says so) and `source_locator` (page, URL, endpoint; each row independently re-checkable). The CanLII table-building tools put a replayable endpoint URL in `source_locator`.
3. Fill in the matching `verification_*` or `confidence` value, **without overstating it**: if not verified, write `name_inference`/`estimated`; those never drive a place of origin.
4. Homograph abbreviations: write several rows for the same abbreviation, one candidate jurisdiction per row, with `vol_range_*` and `year_range_*` (a range containing 0 means the volume may be omitted; one starting at 1 means the volume is always printed). Ranges need evidence (measured print structure in the corpus, or publication history), not guesswork.
5. After adding:
   - Rerun classification and do a **full diff** (`audit/classify_diff.py`) to see whether the changed rows are the expected ones;
   - Sample downstream fields to confirm they were filled;
   - Run `test_layers.py`.
6. After changing a table, **every run that depends on it must be rerun** (the input identity fingerprint includes the decision tables).

## Table-building tools (`decisions/tools/`, not part of the production line)

| Script | What it does |
|---|---|
| `build_neutral_court_codes.py` | Builds the neutral-code table from CanLII `caseBrowse`; `--offline` rebuilds from the cache only |
| `build_case_origin.py` | Fetches the `ukpc` database to build Privy Council places of origin; `--offline`, `--key-file` |
| `build_bilingual_neutral_codes.py` | Bilingual code mapping |
| `build_identifier_systems_csv.py` | Identifier-system table |
| `build_non_citation_words_csv.py` | Rejection-word table (observed counts recomputed on the spot, with a zero-collateral assertion) |
| `build_id_prefixes_csv.py` | Prefix-identifier table (file numbers / publisher numbers); `source_locator` holds the observed source, not the issuer's official source |

Key points (from the three rejection gates in `build_neutral_court_codes.py`, constraint four):
- `court_code` is **not** derived from `databaseId` (118 of 409 databases do not match, e.g. `csc-scc`→`SCC`); it is always taken from the segment printed in real case citations from that database.
- The same code mapping to different jurisdictions in two databases → not written, left for a human; evidence from `ukpc` is not written (#32); a database name pointing to two or more jurisdictions at once is not written (#34).
- CanLII's `jurisdiction` field is "which collection it belongs to", not the court's own jurisdiction (#32).
- CanLII assigns the pseudo-code `CanLII` to bodies without a neutral code, spanning 14 jurisdictions; it **does not go into the neutral-code table** (#31).

## Known pitfalls

| # | Content |
|---|---|
| 31–35 | Defects of the first round of table building: the CanLII pseudo-code, the collection semantics of `ukpc`, false hits through normalized keys, the overclaim "everything left is noise", foreign codes CanLII cannot supply (about 1,042 rows; another source is needed and licensing must be assessed first) |
| 40 | The 166 early rows of `reporter_jurisdiction.csv` were all `estimated`/`name_inference`; each must be verified before any product ships |
| 97 | A column-name mismatch (`origin_country` vs `case_origin`) meant 32 rows loaded successfully with zero effect |
| 99 | `FCA` is the same code for Canada and Australia (the table has only the Canadian row; bracketed `[YYYY] FCA N` is Australian) |
| 100 | `S.J.`: split into two rows by volume (with a volume, British; without, Saskatchewan Quicklaw) |
| 102 | `A.R.` (Ontario Appeal Reports 1880–1897) and `L.C.R.` (Quebec) lack range rows |
| 103 | Errors in the bilingual code mapping; the table was corrected as the user instructed |
| 104 | `FC` has the same shape as the bracketed printed form of the Federal Court Reports |

## Sources

Spec §2 (constraints seven and eight), §5; `decisions/README.md`; code `pipeline/classify.py` (`load_table`, `load_identifier_systems`, `load_court_designations`, `load_volume_systems`), `pipeline/decide.py`; PROBLEMS #31–#35, #40, #97, #99–#104.

Verification status: row counts, status distributions and readers checked against the actual files and code (2026-10-03) [verified].
