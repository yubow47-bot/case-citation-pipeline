# Layer 2: classification

## What this layer does

**Each row is judged independently**, looking only at the fields the row carries: what kind of citation it is, which jurisdiction it belongs to, whether it is a false positive, and what the case name is. Decision-table lookups happen in this layer; the extraction layer does none.

- Input: `extract_out/candidates.csv`.
- Output: `classify_out/<court>/classified.csv` plus `manifest.json`.
- Added after the extraction-layer fields [verified: `classified.csv` header]: `citation_kind`, `abbreviation`, `jurisdiction`, `jurisdiction_confidence`, `lookup_mode`, `vol_missing`, `series_prefix`, `candidate_case_name`, `rejected_reason`, `name_rejected_reason`, `disambiguated_by`, `self_citation`, `parse_status`, `year_vol_ambiguity`, `identifier_subdivision_code`, `jurisdiction_subdivision`, `volume_system`, `court_designation_status`, `observed_deciding_court`, `court_designation_evidence_id`.
- The classification layer has four kinds (`citation_kind`): `reporter` (printed law report), `neutral` (neutral citation), `identifier` (database or vendor identifier, e.g. CanLII, Carswell), `ambiguous` (hits both tables at the same grade).

## Classification layer vs adjudication layer (the easiest to confuse)

- The classification layer judges at the **reporter level**: which jurisdiction `A.C.` belongs to. The answer is the same for every citation using that abbreviation; field `jurisdiction`.
- The adjudication layer judges at the **case level**: where `[1938] A.C. 415` actually comes from (it may be a Canadian appeal to the Privy Council); field `case_origin`.
- The two are not always equal, which is exactly why the adjudication layer exists. **When not in the table, the place of origin must be `UNDETERMINED`; it must not default to the value of `jurisdiction`.**
- The test: if a rule needs to look at other rows, it does not belong in the classification layer.

## Processing order (code: `Classifier.run_row`, `classify.py:958`)

1. **Step 1, shape-level preprocessing** (`step1`): determine `citation_kind` and `abbreviation`.
2. **Step 2, reject non-cases** (`step2`): only sets `rejected_reason`; no rows are deleted.
3. **Step 3, jurisdiction lookup** (`step3`).
4. **Step 4, homograph disambiguation** (when Step 3 returns several candidates).
5. **Step 5, case-name candidate cutting and cleaning**.

### Step 1: look up both tables, exact first

- The `token` of `shape_bracket` and `shape_neutral_bare` is looked up in both `neutral_court_codes.csv` and `reporter_jurisdiction.csv`.
- **No priority between them**: the court-code table can be filled at once while the reporter table stays empty for a long time, so a priority would let the progress of table filling decide the conclusion.
- **Exact > normalized**: if the printed string exactly equals a key in one table, it belongs to that table; a match only after stripping punctuation is a normalized hit.
  - **A normalized hit never yields a determination** (it falls to `ambiguous` + `UNSUPPORTED`, leaves a trace in `lookup_mode=normalized`, counter `neutral_withheld_fuzzy_only`). Reason: it is an inference, not a printed fact (#36).
  - Structural gate: the normalized fallback is enabled only when the row **has no volume** (`[1979] 1 F.C. 103` has a volume, so it is a reporter, not the neutral code `FC`; #33).
  - Both tables hit but at different grades → the exact side wins; only the same grade counts as `table_conflict` (#41).
- `shape_leading_abbr`: `leading_abbr` is looked up in `series_prefix.csv`; not in the table → `unrecognized_series_prefix` (most likely not a citation at all). A recognized prefix that carries a jurisdiction takes part in disambiguation (`Q.R.` → Quebec; #52).
- **`unrecognized_series_prefix` and `UNSUPPORTED` must be kept apart**: the former means "most likely not a citation", the latter "definitely a citation, jurisdiction unknown".
- Identifiers: `CanLII`, `CarswellOnt` and the like go through `identifier_systems.csv`, keyed on the printed token **verbatim** (case-sensitive, no fuzzy matching); only rows whose `verification_status` is `verified_official_source` or `verified_authoritative_manual` drive inference (`ALLOWED_IDENTIFIER_STATUSES`, `classify.py:192`).

### Step 2: rejecting non-case citations (`rejected_reason`, cumulative, joined with `|`)

| Value | Meaning | Notes |
|---|---|---|
| `federal_statute` | A federal statute taken as a citation | Scope: `preceding_text + raw_string` (#37) |
| `party_initials` | Party initials in `R. v. A.B.` extracted by mistake | Strict test: the preceding text ends exactly in `R. v.` and the row starts with `X.Y.` (#37) |
| `docket_not_decision` | v1.6: a file number from `shape_registered_id`, identifying a proceeding rather than a judgment — **kept but not counted**, with no guess at which judgment (constraint four). Note that it differs in nature from the other values: not "not a citation" but "a citation that does not map to a judgment" (the two kinds of rejection in spec §8.8 have no separate field for it yet, #111) | See `id_prefixes.csv` |
| `non_citation_word` | v1.6: the abbreviation slot holds a structural word / calendar word / case-name fragment (`Footnote`, `Section`, `See …`, `On …`, month names, `X`), looked up in `non_citation_words.csv` (whole/first_word/last_word, **case-sensitive**); a registered reporter is never rejected (#113) | Observed counts are in the table |
| `versus_as_page` | v1.6: the page slot is a lowercase Roman `v` and the abbreviation is unregistered — a versus without a period in a case name read as a Roman page (`Villani v Canada`); a pure field test (#113) | 24,532 rows on the margin / 55 rows on the main line |
| `unverified_id_prefix` | v1.6: the table row for a `decision`-type prefix (`AZ-`, `J.E.` …) is not yet verified — kept but not counted; once verified (status `verified_*`) it switches to counted automatically | User decision 2026-10-03 |
| `date_form` | `1 June 2007` has the same shape as "volume abbreviation page" | All three conditions hold: the abbreviation slot is a full English month name, volume 1–31, page 1600–2099 (#85). **The constant `MONTH_NAMES` is in code** (user decision; spec §8.4 v1.7 states the reason: the closed set of calendar words is not a reporter abbreviation) |
| `unrecognized_series_prefix` | Prefix not in the series table | Structural-skeleton false positive |
| `table_conflict` | Hits both tables at the same grade | Awaiting a human decision |

- **`rejected_reason` (row level) and `name_rejected_reason` (case-name level) must stay separate**. Merge-layer counting must exclude the former but not the latter (a row with no extractable case name is a real citation); case-name voting excludes both. Merging them into one field would systematically under-count citations (§8.8).
- `name_rejected_reason` values: `no_v_structure`, `no_separator_before_v`, `too_long` (>120), `has_bracketed_year`, `multi_v`, `empty_after_clean`.
- Dates deliberately not blocked (recorded, unfixed): abbreviated months `28 Feb. 1995` (#86), French months, the "year-month-day" form (#85 residual column); `Apr` collides with `A.P.R.` after normalization (#87).

### Step 3/4: jurisdiction lookup and homograph disambiguation [per spec §8.5/§8.6 plus the implementation correction in #52]

- Match the abbreviation exactly first, then the normalized key; `lookup_mode` records `exact` or `normalized`.
- The same abbreviation appearing in several rows of the table = a homograph (the table is itself the index; no separate list is needed).
- Disambiguation uses only **the structural evidence the row carries** (volume, year) and never reads surrounding text (constraint three):
  - A volume range containing 0 in the table means the series may print no volume; a range starting at 1 means the volume is always printed; rows with no volume take part as vol=0 and are flagged `vol_missing`;
  - With no year, the year dimension does not take part; only the volume counts;
  - A determination is made only when exactly one jurisdiction matches; zero or several matches → `UNSUPPORTED`;
  - The grade is the weakest among the matching table rows, capped at `inferred`;
  - `disambiguated_by` records the route: `series_prefix`/`vol_year`/`novol_year`/`vol_only`.
- `shape_vol_abbr_page` and (part of) `shape_leading_abbr` have no year component and cannot take part in disambiguation; this is a known limitation.

### Step 5: case-name cutting and cleaning (`candidate_case_name`) [per spec §8.7 plus #43/#45/#57/#58/#61]

- Find the **last** ` v.` in `preceding_text`; the start is the nearest `;`, `:` or line break before it; **if no separator is found, give up rather than falling back to position 0**; the candidate runs to the end of `preceding_text` (including the respondent side).
- Cleaning: strip signals, signal verbs such as `citing/see/per/applied`, and an introductory `in ` (keeping `in re`); strip paragraph numbers (#43); cut parallel citations off the tail (#45).
- Case names without ` v.` are recognized only through a closed set of markers at the start or end: `Reference re`, `Re`, `In re`, `Ex parte`, `(Re)`, and the Quebec anonymized name `Droit de la famille — N` (#58).
- When the candidate swallows a whole sentence of prose on the left, it is cut (triggered by ≥3 lowercase prose words; if the result does not look like a case name, the original is returned unchanged rather than judged nameless; #61).
- Self-citation flag: when the row's `nk(raw_string)` equals the judgment's own citation, `self_citation=true`, **compared numerically** (`2003 BCCA 0443` == `2003 BCCA 443`, PROBLEMS #105, `_unpad`). It is a real citation, so it does not go into `rejected_reason`; it is just not counted.

## What to change when adding a court

The classification code usually needs no change; **what changes are the decision tables** (see `06_decision_tables.md`):

1. `neutral_court_codes.csv`: the new court's own neutral code, and the foreign codes its judgments often cite. Only **the string printed in judgments** is accepted (constraint seven). Use `decisions/tools/build_neutral_court_codes.py` (CanLII API, rate-limited to 1 request/second; the key comes from an environment variable or `--key-file` and never goes into the repository).
2. `reporter_jurisdiction.csv`: reporter abbreviations the new court often cites that the table lacks; homographs get range rows.
3. `identifier_systems.csv`: database identifiers in the court's judgments.
4. `court_designations.csv`: court designations in parentheses (`(Ont. C.A.)`); it currently has only 16 rows and the `unrecognized` bucket is large (#94).
5. `bilingual_neutral_codes.csv`: when there are French judgments.
6. Do not fill gaps with defaults. If nothing can be found, leave it `UNSUPPORTED` and record it in PROBLEMS.

If the classification layer "keeps rejecting the same pattern", that is **a signal that a shape is missing**; the right response is to send the signal back to the audit loop, evaluate, build the shape in the extraction layer and rerun the full corpus, **not to let the classification layer re-extract on the spot** (that would turn it into a second extractor).

## Verification

- `python pipeline/tests/test_layers.py` (171 unit assertions plus the mini end-to-end chain); `--golden` only proves the old output did not change (#98).
- Keep a `classified.csv` from before and after any change to `classify.py`, then run `python audit/classify_diff.py --snapshot <directory>` and `--before/--after` for a **full row-by-row diff**; do not sample (a sample once missed a 145-row regression).
- After wiring in a decision table, **sample downstream fields to confirm they really got filled**; loaded row counts alone are not enough (#97).
- Coverage: `python audit/table_coverage.py` (`--assert-only` first self-checks the definition).

## Known pitfalls

| # | Content | Status |
|---|---|---|
| 31 | `CanLII` is a pseudo-code shared by 14 jurisdictions and cannot go into the neutral-code table | Goes through `identifier_systems.csv`; the jurisdiction comes from the trailing parenthesis |
| 32 | CanLII's `jurisdiction` is "which collection it belongs to", not the court's jurisdiction (`ukpc`=`ca`) | Hard-excluded by the table-building script |
| 33/36/41 | False hits through the normalized key (`F.C.`→`FC`) | Fixed (structural gate, no determination from normalization, exact first) |
| 34 | The first round of table building overclaimed "everything left is noise" | Corrected |
| 35 | CanLII cannot supply foreign neutral codes (UKHL, EWHC, HCA …, about 1,042 rows) or institution-internal codes | Another source is needed; licensing must be assessed first |
| 40 | `reporter_jurisdiction.csv` was originally a provisional table, all `estimated` | Some rows upgraded since; see `verification_level` |
| 52 | Homograph abbreviations (K.B./Q.B./S.C./P./C.L.R. …) | Fixed (multiple range rows, prefixes take part) |
| 85 | Dates taken as citations | Phase one fixed; #86 #87 unfixed |
| 93/94 | Designations with nested parentheses not captured; `court_designations` coverage insufficient | Unfixed |
| 95 | The case name shipped with the corpus may be wrong (`[1914] A.C. 599`) | Case-name voting inherits it unchanged |
| 96 | Report year ≠ judgment year (Anns 1977→1978 and 8 cases in all) | The year in the key is the report year |
| 99 | `FCA` is the same code for Canada and Australia | Unfixed (the table has only the Canadian row; all 17 bracketed `[YYYY] FCA N` rows are Australian cases) |
| 100 | `S.J.` Saskatchewan reports vs the British Solicitors' Journal | Fixed (split into two rows by volume) |
| 102 | `A.R.` (Ontario Appeal Reports 1880–1897) judged as AB; the province of `L.C.R.` lost | Unfixed |
| 103 | Errors in the French-code mapping | Table corrected, 13 rows |
| 104 | `[1998] 1 FC 549` is a reporter, not the neutral code `FC` | Unfixed |

## Sources

Spec §5, §8; PROBLEMS #5, #31–#41, #43–#45, #52, #57, #58, #61, #85–#87, #93–#104; code `pipeline/classify.py`; tables in `decisions/`.

Verification status: processing order, fields, function locations, kinds and identifier statuses checked against the code and `classified.csv` (2026-10-03) [verified]; rule details for each step [per spec]; items the specification marks "pending review" were not separately verified.
