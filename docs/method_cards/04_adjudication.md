# Layer 4: adjudication

Current contract: 2026-10-19, adjudication schema 17; implementation: [decide.py](../../pipeline/decide.py), [identity_solve.py](../../pipeline/identity_solve.py) and [identity_parallel.py](../../pipeline/identity_parallel.py). Identity, country evidence and source measurability are separate dimensions.

## Scope, output and DD

The runner performs court-level and cross-court rounds from merge artifacts. `decided.csv` retains member rows and annotates group identity, origin, court, uncertainty and primary-member status. Supporting outputs include `decision_ids.csv`, `effective_sources.csv`, holdout/typo diagnostics, four identity-trace tables and a manifest. Merge inputs are never rewritten.

Final DD is the cardinality of eligible citing-source IDs after group self-citation exclusion. `effective_sources.csv` is authoritative: `counted` links contribute to DD/edges; `excluded_self` and `excluded_source` retain exclusions for audit. `via_member_row_keys` binds each association to its members.

[source_measurement.py](../../pipeline/source_measurement.py) excludes quarantined sources from identity support, own-citation/registry anchors and history/parallel evidence. Raw member rows and source associations are retained. A member supported only by quarantined sources is marked `identity_source_status=excluded_source_only`, retained as an isolated group with DD zero, and cannot bridge eligible groups. Removed own-source anchors remain visible in `quarantined_self_citation_of`.

Source integrity distinguishes missing/incomplete text from a measurable judgment with zero detected citations. Its source table records provider date, native date evidence, conflicts and resolved source year. Native DATE headings can themselves be erroneous or refer to a hearing/amendment: overriding a different provider year requires a valid formal DATE whose year also agrees with the selected metadata neutral year. Otherwise the provider year is retained with an unresolved conflict. Native/provider agreement remains valid when the neutral year differs. The source contract dates the selected written judgment/reasons; it does not reconstruct an earlier oral disposition. A neutral year never supplies a replacement date. See the [source policy](../source_integrity.md) for precedence and limits. G-side calendar consumers remain outside this D implementation's acceptance.

## Identity evidence and guards

Anchors include verified neutral identities and admissible corpus own-citation claims. Complete report keys, document aliases and verified bilingual forms provide additional routes. Name/near-year and co-citation routes remain heuristics. A name match, different page, or one-digit difference alone does not prove either identity or separation.

Co-printed runs provide a distinct, source-bound route even when an individual member lacks a year or name. Every proposal is checked against whole components: held or mixed state, printed-court conflicts, qualified court/report scope, aliases and identifiers, distinct registered roots, year span, reviewed negative pairs and procedural history. Only actual accepted run participants gain `co_printed_run_ids`; heuristic passengers do not inherit the proof. The source threshold defaults to one and is recorded in the manifest.

Fix1 adds three safeguards:

- The parallel route uses the same gate-approved neutral-root map as earlier identity routes. A validated typo cannot reappear as a distinct raw-number root; independently registered judgments remain protected.
- Incompatible observed title contexts for one complete reporter key mark `reporter_identity_conflict` and hold that key out of cross-cluster bridge evidence. The generic guard retains shared-party and ordinary spelling variants; absent or weak name context is not proof of conflict. It does not silently correct the printed reporter citation or assign each ambiguous occurrence to a ruling.
- Printed-run participants with conflicting meaningful title contexts cannot join. Intervening titles already terminate the producer's run. Different reporter pages alone are not a cannot-link.

Exact [pair separations](../../decisions/identity_pair_separations.csv) require native document/text hashes, citation locations and both endpoint keys. The explicit corpus directory binds replay to the supplied corpus without overwriting it. [Reporter possible-court sets](../../decisions/reporter_identity_court_sets.csv) supply negative constraints only; they do not assign a positive court or country.

## Ruling uncertainty, country and court

`ruling_identity_status=uncertain_ruling_identity` flags unanchored same-title adjacent-year components without connected accepted co-printed proof. This I2 mechanism is PARTIAL: it does not split the Bottineau rulings; the known separation remains an expected failing test. W4 residual split estimates and Baker/Dunsmuir before/after review are also PARTIAL, pending the new-run sample. Neither flag changes DD by itself.

Eligible identity bases are `anchor`, `singleton`, `same_citation`, `anchor_variant_bilingual`, `document_alias` and `co_printed_run`. They govern identity-qualified group court propagation and group-only edge propagation. Typo, name/year and other heuristic bases do not acquire that eligibility merely from a group label.

Member country assessment first respects exact case records and applicable sourced scope evidence. Accepted classification jurisdiction can provide country evidence, except where guards such as a matching `verified_mixed` reporter scope block that inference. Mixed publication geography is not a case-origin fact; an exact Canadian case record remains usable. Every member's own country observation participates in group country assessment independently of identity eligibility; contradictions remain conflicts. An edge can use its own member country even when identity is heuristic, while group-only propagation requires eligible support.

`group_deciding_court` combines eligible members' verified neutral, exclusive reporter and printed-designation evidence. Compatible evidence yields `DETERMINED`, contradictions `CONFLICT`, absence `UNSUPPORTED`. There is no majority vote. `probable_same_litigation` remains a retrieval label, separate from judgment identity and DD.

## Residual edge annotations

`reporter_occurrence_status`, `reporter_ambiguous_member_keys` and `reporter_ambiguous_mention_count` expose ambiguous reporter support actually cited by the source. `reviewed_edge_support`, `reviewed_identity_status`, `reviewed_foreign_status`, `reviewed_origin_country`, `reviewed_origin_basis` and `reviewed_origin_evidence_ids` provide a conservative reading of that support. An ambiguous-only occurrence cannot inherit group-only country through the reviewed fields. Canonical edge fields, DD, group assignment, edge keys and mention counts are unchanged; an uncertainty annotation does not reassign the printed citation to a ruling.

The formal-history rules recognize verified docket-prefixed APPEAL headings and front-matter bracketed citations separated from the body by a verified reasons heading. `history_assessment` distinguishes `confirmed_formal_history`, `unassessed_outside_formal_span` and `unassessed_missing_zone_evidence`; it is derived from the same counted zones as `own_case_history` and `zone_profile` and adds no new evidence, only an explicit reading of `false`. `own_case_history=false` does not establish absence of same-case history: history narrated in the reasons remains unassessed. Existing selected-position replay improves from 17/47 to 19/47; this remains below the overall recall gate, even though all 19 sampled formal-block positions are recognized. These code repairs do not establish population or final-edge accuracy; no full run is part of this code-only closeout.

## Verification and limits

Targeted checks: [reporter-context identity](../../pipeline/tests/test_reporter_context_identity.py), [parallel runs](../../pipeline/tests/test_parallel_runs.py), [pair proofs](../../pipeline/tests/test_identity_pairs.py), [identity contracts](../../pipeline/tests/test_identity_contracts.py), [source measurement](../../pipeline/tests/test_source_measurement.py), [source bindings](../../pipeline/tests/test_source_bindings.py), [source dates](../../pipeline/tests/test_source_dates.py), and [mixed reporters](../../pipeline/tests/test_fix1_mixed_reporter.py).

Local native replays separate the four confirmed cross-case reporter collisions and retain positive controls. They are regression evidence, not a general identity-accuracy estimate. Full-run link changes, the independent 150-pair new-merge review and W4 intervals are not established by these code changes and remain pending. See [PROBLEMS](../../PROBLEMS.md) for current status and retained history.
