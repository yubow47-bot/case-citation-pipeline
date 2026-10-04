# Layer 1: extraction

## What this layer does

For the full text of every judgment, it finds every fragment that looks like a citation using **structural shapes** (regexes) and outputs all of them, **without filtering, judging or table lookups**. Only things that can be done by looking at the text itself belong here.

- Input: `unofficial_text_en` from `corpus/<court>.parquet` (column projection, streamed with `iter_batches(500)`).
- Output (the only downstream input is the all-candidates route):
  - `extract_out/candidates.csv`: schema `candidates-2.2`; every overlapping hit is kept.
  - `extract_out/extracted.csv` and `extracted_superseded.csv`: the old "deduplicated" route, **demoted to diagnostic output**; the golden check (`--golden`) reads it, so do not mix its numbers with those of the all-candidates route.
- Key fields of a candidate row [verified: `candidates.csv` header]: `candidate_id`, `source_decision_citation` (`{court}_{nk(citation_en)}`), `raw_string`, `shape_name`, `match_start_offset`/`match_end_offset`, `token`/`leading_abbr`/`abbr`, `serial_marker`, `vol`, `page` (`page_prefix`/`page_roman`/`page_suffix`), `series` (`series_paren`/`paren_note`), `year_raw`/`year_start`, `trailing_paren`, `court_designation_raw`, `preceding_text` (the 120 characters before the citation), `structural_conflict`, `parse_signature`.

## Shapes (the code now has eleven, not the seven the specification describes) [verified: `pipeline/shapes.py`, `SHAPE_ORDER`]

Order: `shape_bracket`, `shape_vol_page_year`, `shape_year_vol_page`, `shape_nominate`, `shape_neutral_bare`, `shape_vol_abbr_page`, `shape_leading_abbr`, then the three added in v1.6 (2026-10-03, PROBLEMS #107): **`shape_bracket_range`**, **`shape_registered_id`**, **`shape_neutral_glued`**, and finally (always last) **`shape_paren_year_abbr_page`** (2026-09-15, the fix for debt 1 of PROBLEMS #21, a fallback shape).

| Shape | Structure | Example |
|---|---|---|
| `shape_bracket` | `[year] (vol) word page` | `[1978] A.C. 728`, `[1868] UKHL 1` |
| `shape_vol_page_year` | `vol word page (year)` | `389 U.S. 347 (1967)` |
| `shape_year_vol_page` | `(year) vol word page` | `(1936), 83 F. 2d 212` |
| `shape_nominate` | `vol word (note) page (year)` | `2 Q.B. (N.S.) 100 (1893)` |
| `shape_neutral_bare` | `year code (division word) number` | `2019 SCC 65`, `2003 EWCA Civ 1746` |
| `shape_vol_abbr_page` | `vol word (ordinal) page`, no year | `93 E.R. 664`, `34 D.L.R. (2d) 451` |
| `shape_leading_abbr` | `(year)? prefix vol word page` | `L.R. 3 H.L. 330` |
| `shape_bracket_range` | `[year-year] (vol) word page`, the year taken is the start year | `[1938-39] C.T.C. 138` |
| `shape_registered_id` | **a registered prefix + number**, no year slot; the regex is generated from `decisions/id_prefixes.csv`, token = canonical prefix, page = the number part | `A-675-94`, `CP 20466`, `PSSRB File No. 168-02-37`, `WT/DS135`, `AZ-50234567`, `50 di 197` |
| `shape_neutral_glued` | `year code number` glued with no spaces; the code is taken from `neutral_court_codes.csv` | `2005TCC640` |
| `shape_paren_year_abbr_page` | `(year) abbreviation page`, no volume (fallback, always last) | `(1924) A.C. 222` |

- **`shape_registered_id` is table-driven**: adding a prefix means adding one row to `id_prefixes.csv`, not touching the regex. Layer one "extracts whatever is registered" and does not judge real citation versus running header; `identifies=docket` (a file number that does not map to a single judgment) is flagged `docket_not_decision` by the classification layer and kept but not counted, and the `decision` type is flagged `unverified_id_prefix` and not counted until verified. Evidence page numbers (`GD2-11`), exhibit numbers and tender numbers are not in the table, so structurally they cannot be extracted. The table rows are self-checked in `pipeline/tests/test_registered_id.py`.
- Shared sub-patterns (`_ABBR`, `_YEAR`, `_SEP_COMMA`/`_SEP_TIGHT`, `_ORD`, `_SERP_SLOT`, `_SERIAL_SLOT`, `_PAGE`) live in `shapes.py`.
- The eighth is a **fallback shape**: it may only take effect at positions no other shape matches; overlap suppression happens in `extract._apply_fallback_semantics` (`extract.py:165`), not in deduplication. This targets the reason the previous (v1.4) implementation was rolled back (the guard failed on real typesetting, and misparses suppressed correct matches). Spec §7.1 still says "rolled back"; **the code is authoritative**.
- Shape order is the final tie-breaker for identical spans: `shape_neutral_bare` must come before `shape_vol_abbr_page` (otherwise `2019 SCC 65` is demoted to a free abbreviation). Changing the order requires rerunning the regression baseline as well.

## Design points (know these before touching a regex)

1. **Structure only, no table lookups** (constraint two). The restriction on `token` is "starts with a capital, no spaces, 2–12 characters, with internal capital alternation", a structural constraint, not a list of courts. Deciding "is this code a court code" is the classification layer's job.
2. **There is exactly one literal exception**: the lookahead `(?!No\.)` at the start of the `_ABBR` segment (the numbering word `No.` is not absorbed into the abbreviation but captured by `serial_marker`, relocating the information). A second literal exception must meet three conditions: it brings its own optional slot that moves the word into a typed field, it brings a full set of measurements, and it proves the information is relocated rather than discarded (spec §7.2 (6)).
3. **Separators are assigned per slot**: year→volume and abbreviation→series/note/page use `_SEP_COMMA` (comma tolerated); prefix→volume and volume→abbreviation use `_SEP_TIGHT` (no comma). Putting a comma in the "prefix→volume" slot causes case-name swallowing (`R. v. Vu, 2013 SCC 60` glued into `Vu, 2013 SCC 60`); 98.8% of measured swallowing came from that slot (#18).
4. **Do not put a comma inside the `_ABBR` segment**: `Howard, L.R.` would be glued into one abbreviation (case-name swallowing). `U, S. R.` and `C.B., N.S.,` are therefore not extracted, a deliberately kept gap (#12).
5. **Page suffixes are captured explicitly**: the `n` in `212n` goes into `page_suffix`, and the assertion `(?![A-Za-z0-9])` closes the backtracking path (#7: the old pattern silently truncated to page=1).
6. **The year range is uniformly 1600–2099, with no switch**.
7. **Loop order: text in the outer loop, shapes in the inner loop**; the other way round reads the corpus seven times (now eight).
8. **The deduplication criterion is interval overlap, longest span first**, not identical start; losers are not deleted but go to a diagnostic file. The all-candidates route itself keeps all overlapping candidates, and the merge layer's arbitration decides which one counts.
9. **Fields are always taken from the capture groups of the original match object**; never re-parse an already generated string with a regex.
10. **No default lower bound on years**; to restrict, pass `--year-from` explicitly and record it in the manifest.
11. **`year_start` always equals `year_raw`**. Do not write `year_raw.split("-")[0]` (a split year `1893-94` cannot enter the capture group, so that code would never run, #1).

## When adding a court

- **Usually the extraction layer needs no change.** The seven (eight) general shapes match by structure and hold for courts they have never seen. A new court's citation forms fall into existing shapes; what is missing are the classification tables. **When what cannot be extracted is a "prefix + number" identifier (file numbers, publisher numbers), you do not write a new regex either: add rows to `decisions/id_prefixes.csv`** (after residual mining and anchor reconciliation, see below), then run `test_registered_id.py`.
- **Only touch extraction when "some form cannot be extracted"**. Find gaps with `python audit/residual_mining.py --court <code> --out audit/findings/<directory>` (finds strings that look like citations but are not covered by candidates, grouped by template, e.g. identifier systems such as `AZ-50234567`, `J.E. 2004-1234`, `WT/DS58`, `CUB 12345`).
- Admission criteria for a new shape (PROBLEMS #16 plus spec §4.3):
  1. The audit loop finds a gap; write the criteria down;
  2. A prototype measures the gain-to-collateral ratio;
  3. On the frozen prose sample, false positives are classified by hand one by one, and **no new class of false positive outside the known classes may appear**;
  4. The field invariants of `run_regression.py --field-audit` are not violated;
  5. **Gate 1, zero breakage**: the full kept diff breaks no existing row;
  6. Zero regression in the fixture's exact tier;
  7. Only then build the shape, rerun the full corpus and produce a new manifest.
- "Frozen" means "frozen until the audit loop gives a reason", not frozen forever. Full extraction takes about 100 seconds (SCC+ONCA, one core); what is really expensive is a schema change once downstream depends on it.
- The judgment header's own citation: the SCC and ONCA print it in every judgment; the extraction layer extracts all of them and the classification layer flags them `self_citation` (see `02_classification.md`). **For a new court, first measure whether the header prints its own citation**.

## Verification

- `python pipeline/tests/run_regression.py --selftest` (synthetic cases, deduplication-equivalence assertions)
- `python pipeline/tests/run_regression.py --field-audit` (five field invariants)
- `python pipeline/tests/run_regression.py --verify` (rereads the parquet row by row and checks the fixture slices match verbatim)
- `python pipeline/extract.py --fixture-check` (the fixture acceptance gate, exact tier A18/B15/C27/D6)
- Any change to `shapes.py`: both the regression and `--field-audit` must run; if negative-control false positives or fixture misses increase, the change goes back for discussion.
- Recall: `audit/extraction_recall_audit.py` measures recall against the upstream ground truth `cases_cited_en` shipped with the corpus (SCC/ONCA main line 98.80%; almost all misses lost deduplication to a longer span with the case name glued on, rather than not being extracted, #63).

## Known pitfalls and deliberately kept gaps

| # | Content | Status |
|---|---|---|
| 1 | Split years `1893-94` not supported | Explicitly unsupported |
| 7 | Page suffix `12n` silently truncated to page=1 | Fixed (explicit capture) |
| 12 | No comma inside the `_ABBR` segment: `U, S. R.`, `C.B., N.S.,` not extracted | Deliberately kept, prevents case-name swallowing |
| 17 | `shape_neutral_bare` year has no left-hand digit guard | Quantified; [unverified] whether it was handled |
| 18 | Case-name swallowing (leading_abbr glued into `Vu, 2013 SCC 60`) | Fixed (separators assigned per slot) |
| 19 | `F.2d` with the ordinal glued to the abbreviation had zero hits | Fixed (glued variant `series_glued`) |
| 20 | Page-format family: `D/2948`, Roman-numeral pages | Fixed (`page_prefix`, `page_roman`) |
| 21 | Parenthesized year with no volume `(1938) S.C.R. 423` | First rolled back, **reimplemented as a fallback shape on 2026-09-15** |
| 22/23 | Mixed-case codes `CanLII`/`CarswellOnt`; the token of `O.J. No.` polluted | Fixed (token relaxed; `serial_marker`) |
| 24/25 | Year prefix of leading_abbr; scope of `serial_marker` | Fixed |
| 26/27 | No ordinal slot for leading_abbr, no series slot for nominate | Deliberately kept (measured: all 40 were case-name swallowing, 0 genuine) |
| 28–30 | French `no`, reporters with apostrophes, single-character Roman pages | Fixed in v1.5 |
| 63 | Recall 98.80% | Quantified |
| 98 | F6: deferred page forms; F7: bracketed years in statutes | Low frequency, recorded as observations |
| 31 | Trailing-parenthesis jurisdiction of `CanLII` pseudo-codes (`2026 CanLII 88302 (PE IWCAT)`) | The extraction layer now has a zero-width trailing-parenthesis capture `trailing_paren` (candidates-2.1) |

## Sources

Spec §4.3, §7; PROBLEMS #1, #7, #12, #16–#31, #63, #98; code `pipeline/shapes.py`, `pipeline/extract.py`, tests `pipeline/tests/run_regression.py`.

Verification status: the shape list, fields, commands and the fallback mechanism checked against the code and manifest (2026-10-03) [verified]; design points and the status of pitfalls [per spec].
