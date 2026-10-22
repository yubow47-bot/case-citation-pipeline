# Decision tables and evidence boundaries

Current contract: 2026-10-19. Files under [decisions/](../../decisions/README.md) contain explicit facts and evidence scope; production reads them offline. Generic parsing, identity guards, arbitration and source-measurement behavior belong in code. Neither a method card nor the problem ledger supplies production configuration.

## Table families

| Purpose | Tables |
| --- | --- |
| Citation systems and parsing scope | `neutral_court_codes.csv`, `reporter_jurisdiction.csv`, `series_prefix.csv`, `identifier_systems.csv`, `id_prefixes.csv`, `non_citation_words.csv`, `non_case_sources.csv`, `reporter_compound_locators.csv` |
| Verified aliases | `bilingual_neutral_codes.csv`, `bilingual_reporter_abbreviations.csv` |
| Printed courts and services | `court_designations.csv`, `court_designation_codes.csv`, `court_designation_reporter_scope.csv`, `citation_service_labels.csv` |
| Country and origin scope | `case_origin.csv`, `case_origin_manual.csv`, `court_or_reporter_scope.csv`, `reporter_origin_scope.csv` |
| Identity facts and negative constraints | `identity_court_facts.csv`, `identity_court_scope.csv`, `identity_separations.csv`, `identity_pair_separations.csv`, `reporter_identity_court_sets.csv` |
| Native document/source structure | `document_zone_markers.csv`, `source_integrity_policy.csv` |

The manifest's input fingerprint, not a frozen row-count claim in prose, identifies the exact table set used by a run.

## Evidence quality and scope

Rows must carry the source and locator required by their contract, with supported date/volume/series boundaries and honest verification status. Homographs may have several scoped rows. Ambiguous or contradictory matches retain uncertainty; an estimated fact cannot become verified through repeated use.

Exact case-origin facts, exclusive publication scope and mixed publication scope have different effects. A matching `verified_mixed` row is an active constraint against country inference from publication geography; it never supplies positive origin. Exact case evidence remains higher priority. A `verified_not_domestic` row (`not_domestic_window` or `not_domestic_printed_court` with `qualifying_printed_courts`) proves only that a judgment is not Canadian and never supplies a country. `window_requires` (`year`, `volume` or `year+volume`) makes a missing printed dimension fall outside the window; it is used where a homonym (Quebec K.B./Q.B., the Western Law Reporter) can only be excluded by year or volume. Exclusive and not-domestic rows leave `volume_system` empty unless the volume system itself is sourced, so classification keys are unaffected. Reporter possible-court sets are conservative identity constraints only. A provincial reporter label does not by itself exclude SCC or federal judgments.

Fix1 corrects the CCC, WWR, AR, AltaLR, ManR, SaskR, NBR and NR origin windows individually from their attached evidence. Historical A.R. remains a real reporter citation; unsupported modern geographic or volume-regime interpretation is constrained. No global exchange of start/end fields or inferred historical fact is permitted.

Native-bound identity exclusions require both endpoints, document and text hashes, raw citation offsets and constructed keys to match the declared corpus. The loader checks source bytes on replay and supports an explicit corpus directory. A stale or altered proof must fail, including when artifacts are gzip-compacted. Such reviewed negative facts do not authorize a general name-based identity exception.

Source-integrity policy distinguishes usable text, missing/incomplete sources and binding conflicts. Original source IDs remain auditable; a wrong source/text binding is quarantined rather than silently merged into its apparent canonical peer. Date evidence has a separate conflict-resolution contract. Formal labels alone do not establish independent date accuracy, and the initial Fix1 date-change queue remains under review.

## Change discipline and validation

A table edit must identify the changed factual scope and retain positive and negative controls. Run the relevant table/interpretation tests and inspect downstream changes under a fresh input fingerprint. Existing outputs do not gain the new facts merely because the working tree changed. Code changes should address generic mechanisms rather than hardcode named case exceptions.

Relevant tests: [reporter windows](../../pipeline/tests/test_fix1_reporter_windows.py), [mixed origin](../../pipeline/tests/test_fix1_mixed_reporter.py), [not-domestic windows](../../pipeline/tests/test_reporter_not_domestic.py), [court identity](../../pipeline/tests/test_court_identity.py), [pair sources](../../pipeline/tests/test_identity_pairs.py), [source bindings](../../pipeline/tests/test_source_bindings.py), and [layers](../../pipeline/tests/test_layers.py). Source verification and agent review are distinct from independent accuracy labels. Fix1 local regressions do not constitute full nine-court acceptance; dynamic changes and independent samples are still required.
