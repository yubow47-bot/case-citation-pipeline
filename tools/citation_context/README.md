# Citation context experiment, version 3

This tool adds source passages, short-citation candidates, case-name mentions, and possible treatment words to existing citation links. It reads the research database selected by `data/active_run.json`, the run's citation records, and the original Parquet text. It saves a separate experiment package and does not change production DD, case identities, links, or human review labels.

A full citation already linked to a counted edge provides the starting point for matching short references. Unlinked full citations can block a later short reference from linking to the wrong case. Unresolved, ambiguous, and blocked references remain in the output. A short citation never creates a new production case or edge.

Run the commands from the repository root using the existing Python environment. No extra package is needed beyond the project's existing `pyarrow` dependency.

## Try a small batch

These commands work in PowerShell. Choose an output directory that does not already exist.

```powershell
# Find source judgments by their recorded name or citation.
python tools/citation_context/context.py sources "2002 SCC 33"
python tools/citation_context/context.py sources "2007 BCCA 234"

# Build an experiment from two source judgments.
python tools/citation_context/context.py build --source "2002 SCC 33" --source "2007 BCCA 234" --output-dir audit/findings/citation_context_try1

# Review short citations that have not been linked safely.
python tools/citation_context/context.py inspect audit/findings/citation_context_try1 --unresolved --limit 20
python tools/citation_context/context.py inspect audit/findings/citation_context_try1 --table observations --limit 20
python tools/citation_context/context.py inspect audit/findings/citation_context_try1 --table edges --limit 20
python tools/citation_context/context.py inspect audit/findings/citation_context_try1 --table documents
```

Open `report.html` from the output directory in a browser. The offline viewer has Chinese interface text and lets you search names, source text, statuses, and target groups. It shows short passages; the JSONL files hold the complete experiment records.

`sources` accepts `--court SCC` and `--limit 20`. Repeat `build --source` to choose exact citations or source IDs. Use `build --group` to select judgments that cite a target group, with optional repeated `--court` filters and a `--limit`.

Without an explicit source list, the tool selects 24 source records by taking turns across courts in corpus order. This is an exploratory batch, not a random sample for estimating accuracy. The limit range is 1–200; it does not truncate explicit `--source` choices. Duplicate corpus rows for a source remain separate.

## Build and repeat a larger batch

```powershell
python tools/citation_context/context.py build --court SCC --court BCCA --limit 6 --output-dir data/experiments/citation_context_try2
python tools/citation_context/context.py cohort --limit 120 --seed 20261015 --output data/experiments/context_cohort.json
python tools/citation_context/context.py build --sources-file data/experiments/context_cohort.json --output-dir data/experiments/context_batch120
```

`cohort --include-package data/experiments/citation_context_try2` includes sources from an earlier package. The selection balances courts, selected English/French text fields, and short-reference forms such as ibid, id, supra, and précité. It also includes documents without those markers. Within each category, a stable hash of the seed and source ID sets the order. This deliberately balanced selection helps find rule gaps; it cannot estimate overall accuracy.

A saved source list is tied to the active run and input fingerprints. It cannot be reused directly with another run. Choose either `--sources-file` or `--source`.

Output must go to a new subdirectory under `audit/findings/` or `data/experiments/`. Existing directories are never overwritten. A package may be at most 96 MiB; reduce the batch size if needed.

## Inspect results

```powershell
python tools/citation_context/context.py inspect data/experiments/context_batch120 --kind ibid --unresolved --summary-only
python tools/citation_context/context.py inspect data/experiments/context_batch120 --kind supra --quoted --limit 20
python tools/citation_context/context.py inspect data/experiments/context_batch120 --table observations --speaker reported_case --limit 20
```

`inspect` reads the saved package without rereading the corpus. Filter with `--table`, `--source`, or `--group`; here `--source` requires a source ID. Repeat `--kind` or `--status` for multiple choices. `--basis` matches an exact resolution basis. `--unresolved` applies only to the mentions table. `--summary-only` counts all matching records regardless of the display limit. `--quoted` uses version 3 quotation metadata, including uncertain quotation boundaries.

| File | Contents |
| --- | --- |
| `manifest.json` | Run ID, input fingerprints, selection method, rule version, hashes, totals, and limits |
| `documents.jsonl` | Source IDs, corpus rows, selected text fields, text hashes, quotation spans, and document counts |
| `mentions.jsonl` | Full citations, short references, case-name mentions, offsets, alias evidence, and matching decisions |
| `observations.jsonl` | Possible treatment words, source evidence, possible targets, and context flags |
| `edges.jsonl` | Document-to-group summaries and existing production-edge information |
| `report.html` | Searchable offline viewer |

## Read the fields carefully

Mention kinds are `full`, `ibid`, `id`, `supra`, `precite`, and `case_name`. Case-name mentions come from known full citations in the same judgment and are counted separately from short-reference markers.

A short reference has a `resolution_status` of `resolved`, `ambiguous`, `unresolved`, or `blocked`. Only `resolved` has a linked target. Check `target_group_id`, `candidate_target_ids`, `antecedent_mention_ids`, `resolution_basis`, and `notes` together. A candidate is not a confirmed link. Existing `identity_status`, `edge_support`, and `counted_edge` evidence is carried forward; a machine match does not increase identity confidence.

A treatment observation marked `suggested` has a possible target supported by local grammar. It still needs human review. `target_mention_ids` holds assigned targets; `candidate_mention_ids` holds possibilities; `context_mention_ids` holds other mentions in the sentence. `attribution_basis` records the rule and text used. The older `mention_ids` field contains local candidates and must not be read as assigned targets.

`context_required` means a signal needs wider interpretation, for example because it is negated, quoted, part of an argument or dissent, or lacks a local citation. `ambiguous` means multiple targets or unresolved references prevent assignment. Reasons remain in `flags`, `negated`, and `assignment_reason`.

`speaker_attribution` and `speaker_evidence` record an explicitly supported speaker; otherwise the speaker is `unknown`. `context_owner_group_id`, `context_owner_mention_ids`, and `context_owner_basis` identify a case whose words are being reported. That source is separate from the case being evaluated. Quoting a case does not by itself show how the current court treats it. Edge fields `reported_source_observation_ids` and `reported_source_signals` preserve these source relationships without adding treatment labels.

The word rules include applied, followed, adopted, distinguished, criticized, overruled, considered, discussed, mentioned, affirmed, reversed, and some French forms. Affirmed and reversed are procedural signals, not automatic judgments about a precedent's authority.

`edges.treatment_suggestions` includes only non-negated substantive suggestions. Context-dependent signals go into `context_required_labels` and `context_required_signals`; procedural signals go into `procedural_labels` and `procedural_signals`. Multiple suggestions remain visible, with `label_conflicts` for possible conflicts. No single label overwrites the other evidence.

`mention_treatments`, `unknown_mention_ids`, and `unknown_mention_count` show which mentions lack assigned signals. `coverage_status` measures rule coverage only: finding no treatment word does not mean neutral treatment. Stable IDs, observation links, and `edge_id` allow tracing between records. The HTML viewer shows at most 50 general signals without local citations per document; JSONL retains all of them.

`production_dd` stays unchanged. Do not add counts from duplicate corpus rows and call the result a new DD.

## Rules and limits

- Offsets are `[start,end)` positions in the original Python Unicode string, not byte positions. Text is not normalized. Display passages include 220 characters before and 240 after a match.
- Basic ibid/id matching allows a citation-like gap of up to 220 characters after the nearest citation cluster or safely resolved short reference. Matching across a quotation boundary needs explicit source evidence; distance alone is not enough.
- Named supra/précité searches earlier full citations in the same document and checks up to 180 characters before the marker for a name. Conflicting names remain ambiguous. Bare supra/précité does not automatically link to the nearest case.
- Aliases may come from a nearby full case name or an explicitly declared short name. Rules can remove balanced parenthetical qualifiers and company suffixes, recording the evidence. They do not guess translations, surnames, or arbitrary first-word aliases.
- Generic Crown names, place names, books, statutes, overlapping citations, and some other non-case references are excluded or blocked. A confirmed book or article cannot seed a case short reference. Production records are retained.
- Citation-list boundaries need evidence. French page references such as `à la p.` and `aux pp. 67 à 70` are supported. Numeric line markers alone may be paragraph numbers, so footnote matches can remain ambiguous.
- Short references and treatment rules share quotation spans. Missing or mismatched quotation marks are cut off at corpus paragraph boundaries and marked uncertain. A reliable match inside a quotation does not establish the current court's attitude.
- English and French patterns both run. A corpus field's language label may not describe all its text.
- Treatment rules use local sentence or clause patterns. Negation checks only the last six words within 75 characters before a signal. The rules cannot fully understand arguments, speakers, or majority and dissenting opinions.
- Explicit descriptions of another court's actions are kept as reported speech. Pronouns and phrases such as “the Court” can remain unclear. Procedural phrases such as `, affirmed [later case citation]` need care about which case was affirmed.
- Statements such as `applying … is not analytically sound` and `Court of Appeal erred in applying …` retain target evidence but require context review.
- Bare case-name matching is experimental. Common names and conservative quotation-title rules can cause missed or mistaken candidates.
- Each package records selected-text SHA-256 values and checks full-citation spans. It does not hash the whole corpus again. Existing uncertainty in production case identity remains.

## Recorded experiments on 2026-10-15

The first expanded batch contained 120 judgments: 54 SCC, 37 ONCA, and 29 BCCA. Twenty-nine used the French text field. Of 578 short-reference markers, 213 were linked, 198 unresolved, 25 ambiguous, and 142 blocked. The batch also had 3,673 case-name candidates, 4,010 word observations, and 2,698 document-to-group summaries. These are rule-output counts, not human-verified accuracy rates. See the retained [summary](../../audit/findings/citation_context_20261015/summary.json) and [source list](../../audit/findings/citation_context_20261015/cohort120.json).

A second pass over the same batch improved quotation boundaries and source attribution. It linked 301 of the same 578 markers: the previous 213 targets stayed unchanged, with 83 additional supra links and five ibid links. The rest were 198 unresolved, 43 blocked, and 36 ambiguous. Most newly linked items previously flagged as quoted reflected corrected quotation boundaries; this does not mean the rules solved that many genuine quoted references.

Of 4,010 observations, 109 recorded an explicit source case. Thirteen of the earlier 14 treatment suggestions were moved to context review, keeping their target evidence. The second pass had three treatment suggestions in total. Production counts and DD for the 2,698 document-to-group summaries stayed unchanged. See the [second-pass summary and changes](../../audit/findings/citation_context_20261015_round2/summary.json). The recorded checks included 104 targeted tests plus package hashes, record references, quotation spans, and report links.

The complete experiment packages are local outputs under `data/experiments/`; they are not included with the summaries. To repeat the saved selection on its matching active run:

```powershell
python tools/citation_context/context.py build --sources-file audit/findings/citation_context_20261015/cohort120.json --output-dir data/experiments/context_replay120
```

## Development

```powershell
python -m unittest discover -s tools/citation_context -p "test_*.py"
```

The module reads SQLite, CSV or gzip records, and Parquet directly. It does not depend on the research interface's helper code. `inspect` can still read older version 1 and version 2 packages.
