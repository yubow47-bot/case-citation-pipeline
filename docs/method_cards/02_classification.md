# Layer 2: classification

Current contract: 2026-10-19, classification schema 10. The executable schema inventory is in [run_all.py](../../pipeline/run_all.py).

## Boundary and artifacts

[Classifier.run_row](../../pipeline/classify.py) interprets each extracted candidate independently. It reads sourced decision tables but does not resolve cross-row judgment identity. Input is `extract_out/candidates.csv`; output is `classify_out/<court>/classified.csv` and its manifest. Extraction candidates 2.4 also carry bounded following context and source decision-year information.

Every candidate remains auditable. Citation rejection (`rejected_reason`) and name rejection (`name_rejected_reason`) are separate. Missing or ambiguous table evidence preserves uncertainty rather than inventing a jurisdiction. Exact and normalized lookup modes, parse status, missing-volume flags and year/volume ambiguity remain explicit.

The principal kinds are `reporter`, `neutral`, `identifier` and `ambiguous`. Relevant fields include `abbreviation`, `jurisdiction`, `jurisdiction_confidence`, `lookup_mode`, `volume_system`, `series_prefix`, `candidate_case_name`, `self_citation`, and identifier subdivision fields. Classification jurisdiction describes the recognized citation system; it is not an unconditional finding about the cited judgment's origin.

## Structural context

Extraction supplies bounded `suffix_annotations_json` with original offsets, including labels after pinpoints, line breaks and nested parentheses. Classification interprets these spans through [court_designations.csv](../../decisions/court_designations.csv), [court_designation_reporter_scope.csv](../../decisions/court_designation_reporter_scope.csv) and [citation_service_labels.csv](../../decisions/citation_service_labels.csv). A pure reporter-series ordinal is not a court label. Contradictory recognized courts retain `conflict`; an unresolved label does not acquire a default court. `parallel_suffix_annotations_json` contains only table-classified court/service labels with evidence IDs for the merge-layer gap check.

With `--corpus`, [document_zones.py](../../pipeline/document_zones.py) uses the same native text selection policy as extraction. Its document index records selected text field, text hash, original offsets and [marker-table](../../decisions/document_zone_markers.csv) evidence. Candidates receive `zone` and `document_zone_evidence_id`. Formal headings take priority over paragraph fallback; missing or ambiguous boundaries remain `unknown`. Citation meaning does not determine boundaries. Production supplies corpus and text policy explicitly; direct calls without corpus retain unknown zones.

## Fix1 interpretation guards

The abbreviated-date guard recognizes closed calendar structures using bounded surrounding text. It marks `abbreviated_date_form` without blacklisting the letters APR: genuine A.P.R. reporter volume/page forms remain admissible. The regression retains both known date/amount failures and real-reporter controls.

Reporter windows are individual sourced facts. Fix1 corrects eight affected windows and limits historical A.R. interpretation without deleting the real citation. A publication's place or abbreviation alone does not establish a judgment's court. Decision-year resolution and source-text quarantine are separate source-integrity contracts; a neutral year is not a blanket substitute for the source decision date.

Adjudication can use an accepted classification jurisdiction as member country evidence, subject to its explicit-case, mixed-reporter and jurisdiction guards. This does not upgrade identity support; see [adjudication](04_adjudication.md).

## Verification and limits

Targeted checks: [date forms](../../pipeline/tests/test_fix1_abbreviated_dates.py), [reporter windows](../../pipeline/tests/test_fix1_reporter_windows.py), [suffixes](../../pipeline/tests/test_suffix_annotations.py), [zones](../../pipeline/tests/test_document_zones.py), [candidate contracts](../../pipeline/tests/test_candidates.py), and [layer boundaries](../../pipeline/tests/test_layers.py).

The nine-court document-format inventory supports rule development. It is not an independent boundary-accuracy estimate. Fix1 population changes and independent reviews remain pending until the new run and its review receipts exist.
