# Changes

## Unreleased

- Fixed group names in edges: a group is named from all identity-supported members, so cases such as Dunsmuir and Vavilov are no longer exported unnamed.
- Long CSV fields no longer stop the nine-court registry report; atomic file replacement retries briefly when Windows scanners hold a file.
- Jev nodes have no per-run question caps. The pinned model is `typesafe/jev-1.14`; the endpoint is no longer in the repository and is read from `JEV_API_URL`.
- Case names lose closed citation signals (`cf.`, `see,`, `relying on`, `the decision in`); table-of-contents headings and docket, lot and count numbers are no longer read as reporters.
- Sourced English Law Reports windows (K.B., Q.B., Ch., Q.B.D., Ch. D.) and U.S. Reports windows give a country where homonyms allow it.
- Appeal Cases, All England and Weekly Law Reports from the 1961 volume, and a printed House of Lords label, now prove a case is not Canadian; such links are FOREIGN with an empty country.
- Added provincial court labels (Alberta, Manitoba and New Brunswick Queen's Bench, Newfoundland Court of Appeal, Quebec Superior Court, Ontario Superior Court of Justice).

Output schemas are unchanged apart from two new `reporter_origin_scope.csv` columns. Runs from earlier versions differ in names, country and court columns.

## v1.2.0 — 2026-10-20

- Added optional model-assisted judgments with TypeSafe Jev (`--jev`, off by default) for per-case calls that rules cannot write completely: where a case name begins, whether a span is a citation, whether a cited ruling is part of the same litigation, heuristic identity, near-year rulings and header dates. Rule results are kept, model-judged values are marked, and answers are cached so a run can be replayed without the API.
- Added a source-integrity stage: native date headers, source-text bindings, and quarantine of sources whose text conflicts with their own citation.
- Strengthened case identity: guarded parallel-citation unions, reporter-key collision holds with an exemption for joint judgments, reporter date windows, and uncertainty marks for neighbouring-year rulings.
- Added document zones and pair-level own-case history; citation links now require a counted mention.
- Separated "not a citation" from "a citation that is not counted"; abbreviated dates no longer become reporter links.
- Added a sourced court-hierarchy table citing the statute behind each appeal route.
- Rewrote the README as a short introduction; method card 09 documents model judgments.

This is a software source release. Output schemas changed (classify 11, decide 18, edges 7, source integrity 2), so runs made by earlier versions are not comparable column for column. No new full-corpus run is part of this release.

## v1.1.2 — 2026-10-16

- Refactored identity evidence, constraints, and solving; strengthened proof-bound separation, reporter court envelopes, and appeal-history and same-key guards.
- Separated case-origin assessment from identity confidence gates.
- Fixed French nested and later-name boundaries, compound ILR locators, and complete spans for transposed report series.
- Corrected entrypoint arguments and coverage before sealing; added replay checks, automatic offline test discovery, a six-document CLI fixture, and reversible adoption and golden checks.
- Synchronized maintenance validation and the issue ledger, updated snapshot and paper-dataset guides, retained cleanup receipts, and kept exploratory citation-context tools local.
- Counted assignment contributions only after an assignment is accepted.

This is a software source release. The active run remains `run_20261016_country_complete`; later source fixes are not yet represented in a newly completed full-corpus run.

## v1.1.1 — 2026-10-15

- Restored the README's methodology, worked citation example, and foreign-case research example. Updated the example using the current run and published the query evidence.
- Clarified current capabilities and historical measurements while retaining both original workflow diagrams.

## v1.1.0 — 2026-10-15

- Added an experimental tool for short citations, including ibid., supra, and quoted names. It records possible treatment words and their source context alongside citation links. It does not change production counts.
- Improved case identity rules using court and source-document evidence, and included French text when English text is absent.
- Added checks for completed runs, sealed outputs, replay from retained data, and storage budgets.
- Improved the local research database, keyword search, and reproducible research queries.
- Added evidence packets and explicit model-review labels. Published model assessments of 270 sampled links, with unknowns and decision coverage reported separately. These are not manual labels or a full-pipeline accuracy estimate.
- Rewrote the public guides, documented the current data snapshot, and retained small records for retired runs. Corpus files and generated research databases remain separate from the source release.

This version follows `v1.0.0`; the earlier tag is preserved.
