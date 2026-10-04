# Pitfalls already hit: an index by layer

How to use it: before you start, find the layer you are about to change and see whether someone has already tripped there. One sentence per entry; for details and numbers, read the matching number in `PROBLEMS.md`.

Statuses are those in the ledger on 2026-10-03. **For entries marked [text], I read only the title; go by the PROBLEMS text for the status**. The full ledger has 106 entries.

## Extraction layer

| # | In one sentence | Status |
|---|---|---|
| 1 | Split years `1893-94` are unsupported; do not write a `split("-")` that never runs | Explicitly unsupported |
| 7 | Page suffix `12n`: the old pattern backtracked to page=1, silently truncating | Fixed |
| 11 | Non-ordinal parentheticals `(Mass.)`, `(N.S.)` not extracted | Fixed in v1.5 (`_NONORD`) |
| 12 | `_ABBR` has no comma, so `U, S. R.` is not extracted; kept deliberately to prevent name swallowing | Deliberately kept |
| 17 | `shape_neutral_bare` year has no left-hand digit guard | Quantified, [text] |
| 18 | Case-name swallowing: the comma in the prefix→volume slot caused 98.8% of the swallowing | Fixed (separators assigned per slot) |
| 19 | `F.2d` with the ordinal glued to the abbreviation had zero hits | Fixed |
| 20 | Page family: `D/2948`, Roman-numeral pages | Fixed |
| 21 | No volume: `(1938) S.C.R. 423` | First rolled back, **reimplemented as the fallback shape `shape_paren_year_abbr_page`** (2026-09-15) |
| 22, 23 | Mixed-case codes `CanLII`/`CarswellOnt`; token pollution in `O.J. No.` | Fixed |
| 24, 25 | Year prefix of leading_abbr; scope of `serial_marker` | Fixed |
| 26, 27 | No ordinal slot for leading_abbr, no series slot for nominate | Deliberately kept (0 genuine / all swallowing) |
| 28–30 | French `no`, reporters with apostrophes, single-character Roman pages | Fixed in v1.5 |
| 63 | Recall 98.80%; the misses lost deduplication to glued spans | Quantified |
| 65 | The extreme structure where a page token directly abuts the year of a following neutral citation | A constructed risk, [text] |
| 98 | F6 deferred page forms, F7 bracketed years in statutes | Low frequency, recorded as observations |

## Classification layer

| # | In one sentence | Status |
|---|---|---|
| 3 | `shape_bracket` without a volume relies on the year alone for disambiguation, with a high risk of error | Rewritten by #52 as "no printed volume is a printed fact" |
| 4 | False-positive rate of `shape_leading_abbr` | Measured (10,850 rows remain after the slot correction) |
| 5 | Actual frequency of `table_conflict` | Measured 0 (after #41) |
| 31 | The `CanLII` pseudo-code spans 14 jurisdictions and does not go into the neutral-code table | Goes through `identifier_systems.csv` |
| 32 | CanLII's `jurisdiction` is collection membership, not the court's jurisdiction | Hard-excluded by the table-building script |
| 33, 36, 41 | False hits through normalized keys (`F.C.`→`FC`); a normalized hit is not a printed fact; exact first | Fixed |
| 34 | The first round of table building overclaimed "everything left is noise" | Corrected |
| 35 | CanLII cannot supply foreign neutral codes (UKHL, EWHC, HCA …) or institution-internal codes | Another source is needed; assess licensing first |
| 37, 38 | The specification did not define the `s` field of §8.4 or give `shape_neutral_bare` its own section | Filled in by the implementation, pending review |
| 39 | A long tail of 36 foreign neutral codes not traced to a source | [text] |
| 40 | `reporter_jurisdiction.csv` was originally a provisional table (all `estimated`) | Partly upgraded since |
| 43–45 | Case names carrying paragraph numbers `[24]`; voting counted raw strings; the tail swallowed parallel citations | Fixed |
| 52 | Homograph disambiguation (K.B./Q.B./S.C./P./C.L.R. …), prefixes take part | Fixed |
| 57, 58, 61 | Case names borrowing another case's name; case names without v.; swallowing whole sentences of prose | Fixed |
| 70 (B7) | Codes of the `DTC` kind hit both tables exactly; a same-grade tie abstains | By design, [text] |
| 71 (B8) | Splitting keys on non-ordinal parentheticals (`10 Cush. (Mass.) 337`) deferred | Deferred, [text] |
| 73 (B10) | Long misparses with a "repeated year" suppress real neutral citations as contained | Recorded, [text] |
| 79 (B16) | Residual true ambiguity of homographs (K.B., Q.B., S.C.) | Measured, [text] |
| 80 (B17) | Degenerate table rows: a row with no range = matches everything | Recorded, [text] |
| 82 (B19) | Database/vendor-style citations (`oj`, `scca`, `bcj`) should go through `identifier_systems` | [text] |
| 85 | Dates `1 June 2007` taken as citations | Phase one fixed (`date_form`) |
| 86, 87 | Abbreviated months `Mar.`/`Apr.` not blocked; `Apr` collides with `A.P.R.` | Unfixed |
| 93, 94 | Parenthetical designations with nested parentheses not captured; `court_designations` has only 16 rows, insufficient coverage | Unfixed |
| 95 | The case name shipped with the corpus may be wrong (`[1914] A.C. 599`) | Case-name voting inherits it |
| 96 | Report year ≠ judgment year (8 cases) | The key holds the report year |
| 99 | `FCA` is the same code for Canada and Australia | Unfixed |
| 100 | `S.J.` Saskatchewan vs British | Fixed (split by volume) |
| 102 | `A.R.` (Ontario Appeal Reports 1880–1897) judged as AB; `L.C.R.` loses its province | Unfixed |
| 103 | One pair in the French-code mapping judged wrongly | Table corrected |
| 104 | `[1998] 1 FC 549` is a reporter, not a neutral code | Unfixed |

## Merge layer

| # | In one sentence | Status |
|---|---|---|
| 2 | Whether forms that omit the volume are the same citation | Strict matching, not merged |
| 42 | Which value to take for single-valued fields within a group | Mode, recorded in the manifest |
| 44 | Two-level folding for case-name voting | Fixed |
| 46, 47 | The adjudication layer needs `decision_ids.csv` to get DD right; occurrence inflated in the cross-court round | Fixed |
| 53 | The merge key must include the series prefix | Fixed |
| 60 | "One vote decides the name"; a gate on `case_name_support` measured net negative | Not enabled |
| 72 (B9) | Case-name voting included non-counted candidates (43.7%) | [text] |
| 76 (B13) | Year read as volume | 0 counted, [text] |
| 90 | **Zero-padded numbers form their own key** (BCCA 319, SCC 520, ONCA 27) | **Unfixed** |

## Adjudication layer

| # | In one sentence | Status |
|---|---|---|
| 48 | Chained merging strung together chimeras spanning decades | Fixed |
| 49 | Blind spot of name+year identity: different judgments with same-named parties merged | Fixed (several criteria) |
| 50 | One judgment with a long and a short case name, so parallel citations do not join | [text] |
| 54 | Self-citation: every judgment adds DD+1 to itself | Fixed |
| 55 | Two different judgments in the corpus merged into one group | Fixed, residue of 56 units |
| 56 | "Neutral citations" before a court began using them taken as identities | Fixed |
| 59 | Privy Council appeals labelled British | Filled (1888–1959) |
| 62 | Groups with the same name and years within ±1 | Flagged only, not merged |
| 64–68 (B1–B5) | Place of origin of reporter citations not inferable; extreme adjacency structure; no exclusive rule-layer evidence for UKPC/JCPC; US place of origin unreachable; same-case propagation not implemented | Recorded, mostly unfixed, [text] |
| 69 (B6) | Linking case names in historical footnotes not done (`preceding_text` is only a 120-character window) | [text] |
| 74–75 (B11–B12) | Sample of name changes under case-name sensitivity; single-anchor clusters absorb judgments of different instances along the way | B12 measured; the proposed rule was rejected |
| 77, 78, 81, 83, 84 (B14, B15, B18, B20, B21) | Groups blocked by the identity gate; size of the abstention bucket; publisher sources unobtainable; residual isolated groups; single-anchor clusters absorb unconditionally | Recorded, [text] |
| 88 | One printed string carrying two identities | Fixed (mixed-key holdout, on by default) |
| 89 | The registry depends on the corpus being present | Unfixed |
| 91 | When the suppressor is undecided, the suppressed real citation abstains too | Unfixed, disclosed |
| 92 | 18 cases of the R4 manual verification batch undecided (budget exhausted) | [text] |
| 97 | Inconsistent decision-table column names: loaded successfully, zero effect | Fixed, methodological reminder |
| 105 | Self-citations slipping through (zero padding, parallel citations in the header) | Fixed (2026-10-03) |
| 106 | Case identity groups by case, so all instances of an old case merge into one group | **Unfixed** |

## Selection layer and edges

| # | In one sentence | Status |
|---|---|---|
| 60 | No gate on `case_name_support` | Decided |
| 106 | The procedural-history flag covers only part | Unfixed |

## Process, tests, tools

| # | In one sentence | Status |
|---|---|---|
| 13 | Every judgment's header prints its own citation, inflating the row count | Fixed (`self_citation` flag, #54) |
| 14 | Inline footnote markers `[n]`; case-name cutting works poorly on 1877–1967 material | [text] |
| 15 | Diagnostic scripts bucket by: footnote rows, body prose, Cases Cited blocks × era | Design requirement |
| 16 | Admission criteria for new shapes (frozen prose sample, zero breakage) | Rule |
| 51 | Recording input paths in the manifest crashed across drive letters | Fixed |
| 98 | `--golden` only proves the old output did not change | Disclosed, acceptance discipline |
| 101 | The experience library reads PROBLEMS.md: the first adjudicated exception, with three limits | Exception granted |

## Sources

The full text of `PROBLEMS.md` (106 entries); spec §15. This table is only an index; for every entry's numbers, evidence and disposition, go by the PROBLEMS text.
