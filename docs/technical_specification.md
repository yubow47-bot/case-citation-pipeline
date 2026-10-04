Version 1.8 | v1.0 finalized 2026-08-29; v1.1 revisions: corpus snapshot policy (§1.3), repository path corrected (§1.4/§4); v1.2 revisions: scope widened to all citations (§1.1/§1.2), extraction layer v2 with seven shapes (§7), §7.4 deduplication sort primary key corrected, a regression baseline replaces the A/B plan (§13.1), decision-table priorities (§5/§13.3), PROBLEMS sync (§15); v1.3 revisions: corpus-level counts scripted and fully renumbered; v1.4 revisions: separators assigned per slot (name-swallowing fix, §7.1/§7.2), deduplication without deleting rows into two files (§7.4), page-format family page_prefix/page_roman (§7.3), glued ordinal variant, a dedicated section on the `_ABBR` literal exception (§7.2 (6)), extract.py landed and first full run (§13.1); **v1.5 revisions**: the audit loop and the membrane rules established (§4.3, `audit/`), four gap fixes (French no / reporters with apostrophes / non-ordinal parentheticals / single-character Roman pages, §7.1/§7.2, PROBLEMS #11/#28/#29/#30), admission criteria gain "gate 1, zero breakage" (PROBLEMS #16), §13.1 numbers renumbered (corpus_counts.py/prose_sample.py), §5.1 head corrected (O.R. moved into the head), normalize aligned with §7.4 and folded into the regression equivalence assertions, prose sample construction corrected, separators assigned per slot (91,356 name swallowings eliminated), deduplication without deleting rows (kept/superseded in separate files), §13.1 three-column baseline and prose anchor baseline; v1.4 revisions: the two-agent recall-gap audit landed (findings_local/remote committed to git), seven measurement modes consolidated with positive and negative assertions (stage 0), the --field-audit capture-group check-up instrument (stage 1), fix 1 the glued variant of the ordinal slot (the whole F.2d family, 1,778 times), fix 2 the page-format family (slash/roman, +1,817 rows), fix 3 parenthesized years with no volume (670 times, with a misparse guard), fixes 4/5 recorded as observations, the #16 anchor remeasured twice, fix 3 rolled back after implementation (guard failure + net negative gain, PROBLEMS #21); last round before freezing: the year-prefix slot of leading_abbr (#24, 1,631 times / 745 judgments get a year field), _SERIAL_SLOT shared (#25, consistent scope), two deliberate omissions measured and recorded (#26 lead swallowing 40/40, #27 nominate 0 times) — the slots of the seven shapes settled one by one, regexes frozen; **v1.6 revisions (implementation notes, 2026-09-10)**: implementation notes after layers 2–5 landed (§1.4, §8.2, §9.5, §10.7, §12, §12.1, §13.3); design additions and deviations all point to PROBLEMS #33, #36–#50, pending human review; **v1.7 revisions (spec write-back, 2026-09-15, DEBT_LEDGER debt 9)**: the three implementation notes previously missing were added (§8.4 scope of the `s` field corrected #37, §8.2 missing section on `shape_neutral_bare` added #38, §9.5 values of single-valued fields within a group #42), so that PROBLEMS #37–#63 all have matching implementation notes; §10.2/§5.4 rewritten as the three-tier priority waterfall of case-level origin determination (`case_record`/`court_scope_rule`/`reporter_origin_scope`, three new decision tables from R2–R4); §1.4 adds the measured numbers of the delivery run `data/run_20260914_r4c` (1,013,948 candidate rows, 173,845 adjudicated groups, 8,646 selected groups) and clarifies the route difference from the numbers of the old "deduplicated" extraction route; directory structure (§4) and size governance synchronized with `data/README.md`, `implementation/run_registry.csv`, `implementation/rebuild_run.py` (slimmed from 46.8 GB → 9.6 GB; 13 historical runs can be rebuilt with one command from their registered git commits). Pending human review; **v1.8 revisions (spec write-back, 2026-10-04)**: records all implementation notes after 2026-09-15 up to #113 — the corpus scope was widened by user decision (2026-09-18, commit `49c6328`) from SCC+ONCA to SCC+ONCA+BCCA in the main line, with CITT/TCC/SST/FPSLREB only on the experiment line (§1.3, §12); the PROBLEMS ledger extended to #113 (the B1–B21 debt ledger merged in as #64–#84, ledger repairs added #91–#98, then #99–#105 and #113 added); extraction layer v1.6 table-driven shapes (registered ID / glued neutral citation / bracketed year range, §7.1); new rejection families in the classification layer (the `non_citation_word` table, `versus_as_page`, #99 bracketed-year foreign form, #104 volume signature, §8.4); #88 mixed-key holdout on by default (§10.4, recorded earlier on 2026-09-17); #105 fix for self-citations slipping through and `--own-citations` (§10.7); decision-table verification grades upgraded and S.J. split into rows by volume (§5); repository reorganization and the method-card / experience-library system (§4); current baseline `data/run_20261003_selfcite` (§1.4). Pending human review

---

## 0. What this document is

This document is the project's **only technical specification**. It is self-contained and does not depend on any earlier outline, discussion record or iteration. Reading it should be enough to start implementing directly, without going back to any other material.

Every design decision in it comes with its rationale, including which alternatives were rejected and what exactly was wrong with them. This is deliberate: the first version of this project did not fail because a technical choice was wrong, but because the reasons for the choices were never recorded, so each later round re-argued the same questions and each time picked the cheapest option of the moment rather than the right one.

**Evidence-labelling convention.** Every reference in this document to a specific behaviour, field name or value of the old pipeline has been confirmed by reading the source code or files on disk directly, and is marked [verified]. Every unverified inference is marked [unverified] and must not be used as a basis for implementation. This convention is itself a lesson: in the previous round of design a file path appeared that looked entirely concrete and was in fact made up; since then no specific value that has not been confirmed on disk is accepted.

---

## 1. Background and goals

### 1.1 What it solves

From a full-text corpus of Canadian court judgments, extract **every case citation** the judgments make — foreign and domestic citations alike — and organize them into a structured table with case names, jurisdictions and citation frequencies.

**Scope widened (v1.2).** v1 collected only foreign citations (cases from the UK, US, Australia, New Zealand and other jurisdictions). The basis for widening is not a new feature but **stopping the discarding**: the extraction layer matches only by structural shape (constraint two), so domestic citations (of the `[1953] 2 S.C.R. 140` and `2019 SCC 65` kind) were in its output all along; the old pipeline simply threw them away downstream. Measured (2026-09-05, corpus = SCC+ONCA, counted by occurrence, produced by `pipeline/tests/corpus_counts.py`): `S.C.R.` (family: dotted 146,175 + missing final dot 277 + bare SCR 12,165 + half-dotted forms 15 + typeset with internal spaces 1,732) 160,364 times, `C.C.C.` 30,705 times, `O.R.` 29,970 times, `D.L.R.` 18,675 times, `W.W.R.` 6,126 times — domestic citation forms are the largest share of citations in the corpus, and continuing to discard them means throwing away most of the data. `D:\mcgill` has been explicitly declared unrelated to this repository (see 1.4).

This table still serves first of all Cite Counsel's **landmark-case lookup layer**: when a user enters a well-known case (foreign or domestic), the system returns the verified full citation directly, without LLM generation and without querying an external API. After the scope was widened, the same table is also directly useful for questions like "how many times has a case been cited by Canadian judgments", but that is a by-product of the same data, not a new pipeline stage.

### 1.2 Why this matters for the product

Cite Counsel's product rests on "verification over generation": better to return "unsupported" than a citation that looks plausible but may be wrong. The same principle holds inside this pipeline, and more strictly. The reason is that the pipeline's output becomes the product's source of facts, and any guess made inside the pipeline shows up at the product level as a piece of wrong data treated as verified.

Widening the scope does not change this commitment, only broadens where it applies: the jurisdiction of domestic citations must also come from table lookups (`neutral_court_codes.csv`, `reporter_jurisdiction.csv`), and no inference may be injected inside the pipeline because "it is a domestic case and looks obvious".

### 1.3 Corpus

The source is HuggingFace's `a2aj/canadian-case-law` dataset, downloaded through direct Parquet links (`https://huggingface.co/datasets/a2aj/canadian-case-law/resolve/main/{COURT}/train.parquet`). The relevant columns are `citation_en` (the judgment's own citation), `document_date_en` (judgment date) and `unofficial_text_en` (full text of the judgment) [verified].

**Snapshot policy (v1.1 revision, replacing the first version's "never re-download" clause).** The corpus is managed as "snapshots": the corpus used in each round of work is the copy downloaded when that round began; once in place, the local corpus is read-only, and no part of the pipeline may write, move or delete corpus files. Upstream data may be updated at any time, so **every snapshot must be clearly marked with its download date**, and its byte count and SHA-256 must be measured at download time and entered in the table below; if it is ever re-downloaded for any reason, it must be registered as a new snapshot with a new download date and fingerprint, never reusing the old record, and two rounds of work must never share one unmarked file. The first version's statement "SCC has diverged from upstream, never re-download" referred to the old pipeline's local snapshot of 365,137,478 bytes; that file is no longer in this repository (`D:\citations` does not exist; this repository's `corpus\` holds the new snapshots registered below), so its byte count is of historical interest only, and the current corpus is defined by the measured values below.

Scope of this round: SCC + **every Ontario jurisdiction in the dataset**. Enumerating the HuggingFace dataset directory (29 top-level directories) shows that the dataset's Ontario jurisdiction **is only ONCA (Court of Appeal for Ontario)** — there is no ONSC or other Ontario court; the `OHSTC` in the directory is the federal Occupational Health and Safety Tribunal Canada, not an Ontario body. So this round's corpus = the two files SCC + ONCA.

| Court | File | Download date | Bytes (measured) | SHA-256 (measured) | Status |
|---|---|---|---|---|---|
| SCC (Supreme Court of Canada) | `SCC.parquet` | 2026-08-30 | 365,204,389 | `8e79cd406e302d9586ae2235e3c6c34b2797e2dbf6733872536fd2307ace6da6` | Read-only snapshot |
| ONCA (Court of Appeal for Ontario) | `ONCA.parquet` | 2026-08-30 | 183,138,908 | `58c31f93063c6bcc83cb2014310737932ea4396443e3015213a923528d993775` | Read-only snapshot |
| BCCA (Court of Appeal for British Columbia) | `BCCA.parquet` | 2026-09-17 | 186,876,782 | `b816c3679b40fbf55060d325674af3d8e58650a78123a9ec00d38d3112b29ad3` | Read-only snapshot (bytes and SHA-256 measured on this machine on 2026-10-04; the fingerprint matches the input identity in `data/run_20261003_selfcite/run_manifest.json`; **not yet registered in `data/corpus_manifest.json`, registration pending**) |

The measured values differ from the old snapshots recorded in the first version (SCC 365,137,478 → 365,204,389; ONCA 183,026,061 → 183,138,908), confirming that upstream was updated after the previous snapshot. The machine-readable list of source URLs and fingerprints is in `data\corpus_manifest.json` (gitignored, rebuildable).

**Second scope extension (v1.8, user decision 2026-09-18, commit `49c6328`).** The corpus scope was widened from SCC+ONCA to **SCC+ONCA+BCCA**, with BCCA joining the main line; the court list is controlled by the environment variable `PIPELINE_COURTS`, default `SCC,ONCA,BCCA` (the three defaults in `pipeline/extract.py:66`, `pipeline/run_all.py:33` and `pipeline/trace_source.py:30` agree [verified]), and `run_all.py` also has a `--courts` override. Four more parquet files from the dataset, CITT/TCC/SST/FPSLREB, were downloaded (saved 2026-10-03) **for the experiment line and residual mining only** (the marginal-court definition in `pipeline/shapes.py`; the experiment line measured a CITT jurisdiction resolution rate of only 11.6% and 60.9% of extractions being dates, see `implementation/exp_bcca_citt_findings.md` and PROBLEMS #85); they do not enter the main-line corpus. Main-line judgment counts (measured in `README.md`): SCC 10,891 (1877–2026), ONCA 24,089 (1998–2026), BCCA 14,703 (1999–2026). **Registration gaps (pending)**: neither `BCCA.parquet` nor the four experimental court parquet files are in `data/corpus_manifest.json` (`scripts/download_corpus.sh` enumerates only SCC and directories starting with `ON`), and the BCCA fingerprint currently exists only in the input identity of run manifests; under the snapshot policy these two registration gaps must be closed.

**The corpus is read-only.** No part of the pipeline may write, move or delete corpus files.

### 1.4 Project status

The first version of the pipeline was completed and produced results (a 213-row product candidate table), but its architecture was judged beyond repair and all its output was voided. This project is a complete rebuild from the corpus, inheriting only lessons, not any data, code or judgements.

The rebuild lives in this repository directory `D:\cases data analisis`, fully separate from the Cite Counsel main repository `D:\mcgill`, as an independent git repository. (The first version of the specification wrongly gave `D:\citations`, a path that does not exist; the actual path of this repository is authoritative.)

**Rebuild progress (v1.6 implementation note, 2026-09-11).** All five layers are implemented and have run on the full corpus: extraction 582,408 rows → classification (jurisdiction resolved for 91.0%, 529,851/582,408; 58,457 of these rows are a judgment's own citation printed in its header, flagged and not counted in frequencies) → merging 206,213 keys → adjudication 190,153 groups → selection (**8,610 groups** under the dd≥5 placeholder threshold). Every addition to or deviation from the specification during implementation is registered in PROBLEMS (#33, #36–#63); where the body of the specification was not rewritten, an "implementation note" marks it and points to the matching entry — **all these entries are pending human review**.

**What this round (second batch, 2026-09-11) changed and why**: #59 filled the Privy Council part of `case_origin.csv` (203 rows; Canadian appeals to the Privy Council are no longer treated as English cases; source coverage 1888–1959); #58 case names no longer recognize only v., adding `Reference re`/`Re`/`In re`/`Ex parte`/`(Re)`/Quebec anonymized names (nameless→named 7,660 rows), whereby the Secession Reference combined from dd 13+81 into dd 94; #60 exposed the case-name support `case_name_support`, but **a gate on it measured net negative and is not enabled**; #61 cuts off whole sentences of prose swallowed on the left of case names (named→renamed 17,742 rows, no entries or exits in the top 25 of the ranking); #62 adds the visible flag `same_name_near_year_peers` to groups with the same name and years within ±1 (flagged only, not merged); #63 quantified the extraction layer's recall against upstream ground truth at 98.80%, confirming that the missing 1.2% lost deduplication to glued spans rather than not being extracted; **the extraction layer was not changed**. For how to read the data and what it under-counts, see `USAGE.md`. Regression defences: `pipeline/tests/run_regression.py` (extraction layer) and `pipeline/tests/test_layers.py` (layers 2–5: 119 unit assertions, the mini end-to-end chain, the full golden diff).

**Implementation note (R2–R4, delivery run `data/run_20260914_r4c`, 2026-09-14).** The numbers in the previous paragraph are a one-off snapshot from when v1.6 was finalized (the old "deduplicated" extraction route). Since then the extraction layer added the **all-candidates route** (`candidates.csv`, schema `candidates-2.2`), which became the only downstream input — the old route's `extracted.csv`/`extracted_superseded.csv` were demoted to diagnostic output (the v1.4 frozen definition; `--fixture-check` is still pinned to it, and the 6 old-route directories at the root of `data/` and the `--golden` gate read it too, so do not mix the numbers of the two routes). **Measured numbers of the delivery run**: 1,013,948 candidate rows (span invariant: zero differences when checked entry by entry against upstream ground truth) → classification (jurisdiction resolved for 77.4%, 784,579/1,013,948; because it includes all candidates, this rate is not comparable with the 91.0% above — the denominators differ, as the all-candidates route keeps more noise candidates and self-citation rows; 101,226 self-citation rows flagged and not counted) → merging → adjudication **173,845 groups** (case identity see the three-tier waterfall in §10.2) → selection (dd≥5, **8,646 groups / 17,370 rows**, `rows_total` 189,508). Case-level origin determination added `case_origin_manual.csv` (33 rows), `court_or_reporter_scope.csv` (13 rows) and `reporter_origin_scope.csv` (41 rows); these three tables together with `case_origin.csv` (204 rows) decide `member_origin_status`, see §10.2/§5.4. One correction of a corpus case name: `[1914] A.C. 599` was originally attributed to Boudreau and on verification is actually Ibrahim v. The King (PC/HK). Pending review.

**Implementation note (v1.8, 2026-09-15 → 2026-10-04).** After v1.7 the project went through four main lines of work; measured numbers are those of the current baseline **`data/run_20261003_selfcite`** [verified, read from that run's manifest]: candidates → classification → merging → adjudication **236,809 groups** → selection (`rows_total` 263,817, `kept` 30,494, **13,630 groups at dd≥5**); edges **493,164** (supported 452,700), 1,467,015 mentions scanned. The four lines: ① **ledger governance** — the B1–B21 debt ledger of DEBT_LEDGER was merged into PROBLEMS as #64–#84 (commit `1530ede`), ledger repairs restored the accidentally deleted #22 and added #91–#98 (`51fdc99`), then #99–#105 and #113 were added; the ledger now has 113 consecutively numbered entries; ② **joining lines and experiments** — BCCA joined the main line (§1.3), and the BCCA+CITT experiment line produced six real problems #85–#90 (date look-alike extraction fixed in phase one, mixed-key holdout #88 fixed and on by default, #90 zero-padded numbers pending a fix); ③ **table and verification upgrades** — 101 rows of `reporter_jurisdiction.csv` upgraded to print-evidence verification, 13 pairs of bilingual neutral codes corrected according to printed facts (#103; the full rerun changed only 1 identity: `2005 FCA 348` and `2005 CAF 348` merged into one group), decision tables extended (#94 court designations, #100 S.J. split into rows by volume, #99 FCA the same code for two countries), see §5. ④ **Fix for self-citations slipping through (#105, 2026-10-03)**: zero-padding awareness (`2003 BCCA 0443` ≠ `2003 BCCA 443` had created 281 singleton fake "cases") and claiming parallel citations in the header; the full rerun took edges 493,463→493,164 (all −299 were self-citation edges) and groups 237,091→236,809, with the number of dd≥5 groups unchanged. The supporting systems outside the pipeline (method cards, experience library, CanLII cross-check) are in the v1.8 note of §4. Pending review.

---

## 2. Inviolable constraints

The following nine are design constraints, not suggestions. When any implementation plan conflicts with them, change the plan, not the constraint. Each comes with its history, because a constraint detached from its history gets re-argued as dogma in the next round.

### Constraint one: a problem must be fixed in the layer that produces it

**History.** The old pipeline's extraction regex had a truncation defect (see 16.1). The fix should have been to correct the regex and rerun. What was actually done was to let the regex keep extracting wrongly and maintain an exclusion list of "please ignore these 140" in the aggregation layer. That list became a permanent liability: every corpus update required another full census, and anyone reading the data had to know the list existed. After the same kind of thing had happened three times, the aggregation layer had become the place that paid off upstream's debts, and in the end the whole pipeline was unmaintainable.

**Constraint.** Downstream layers must not keep any list, allow-list, block-list or exception table for working around upstream defects. If upstream has a defect, fix upstream.

### Constraint two: the extraction layer must not use a fixed list of abbreviations

**History.** An earlier extractor matched against a fixed list of reporter abbreviations and as a result systematically missed **all** the American citations in the corpus. The reason was that the list had been compiled from Canadian and British citation habits, and American citation formats were entirely absent from it. What makes this kind of defect frightening is that it is silent: what is missed appears in no statistic, and it is exposed only when someone happens to notice that a well-known American case is not in the results.

**Constraint.** The extraction layer matches only by **structural shape**; it looks up no table and compares against no list. Deciding "what this abbreviation is" is the classification layer's job.

This constraint has a precise boundary: **closed and enumerable** sets such as court codes and series prefixes may use fixed tables, but **the lookup must happen in the classification layer**; the extraction layer still only does structural matching. Reasons in 7.2 (3) and 8.3.

### Constraint three: no keyword signals from surrounding text for jurisdiction

**History.** The old pipeline used six signals (S1 to S6) to infer jurisdiction from the text around a citation; S2 was "if Privy Council or Judicial Committee appears in the window, judge it English". This signal systematically misjudged Canadian cases as English. The reason is that Canadian appeals to the Privy Council were routine until 1949, so the words Privy Council in the window do not at all mean the case is English.

The key is how it failed: **the keyword really was present, and the conclusion was still wrong**. This shows the problem was not choosing the wrong keyword but that the method of "inferring jurisdiction from surrounding text" does not hold at all. A different set of keywords would not make it reliable.

**Constraint.** Jurisdiction can come only from table lookups, or from structural evidence the citation itself carries (volume, year). Surrounding text must not be read to infer jurisdiction.

### Constraint four: with no evidence, mark it unsupported; no default values

**History.** In the old pipeline's abbreviation labels, the jurisdiction of the great majority of entries was produced by graph propagation, default values and model inference, and only a tiny fraction had independent evidence. But the output format treated every label the same, so downstream could not tell which were reliable and which were guesses. The result was a batch of unverified judgements used as facts for an entire round.

**Constraint.** If it cannot be found, it is `UNSUPPORTED`. No default values and no presumption of "what it most likely is", even if a class of citation is consequently missing systematically for a while. Adding an `inferred` label does not change the fact that it is a guess; it only gives the guess a free pass.

False negatives are better than false positives. This is already an established principle at the product level, and it applies inside the pipeline too.

### Constraint five: never delete rows, only flag them

**History.** The old pipeline discarded non-conforming rows directly at several points. The consequence was that it could not answer "why is this case not in the results", a question that will certainly be asked. To be able to answer it, another list recording the excluded content had to be built, so there was yet another list.

**Constraint.** Every row judged non-conforming stays in the output table, with fields marking the reason (`rejected_reason`, `kept`, etc.). The product reads only conforming rows, but the full table is always kept.

### Constraint six: layers are one-directional, and each runs once

**History.** The old pipeline's actual execution order was: selection (v1) → classification (v2) → selection again (v3) → adjudication plus classification (v4). Classification ran twice, selection ran twice, and adjudication was squeezed in between. This interleaving meant every layer had to handle data "already half-processed by the previous round", and the logic quickly got out of control.

**Constraint.** Extraction → classification → merging → adjudication → selection, executed in one direction, each layer once, never going back. A downstream layer may overrule an upstream layer's conclusion (see 10.5) but does not modify the upstream layer's output files.

### Constraint seven: a decision table's key must be a fact printed in the judgment

**History.** The old pipeline's human judgements were keyed on strings generated inside the pipeline. When the extraction regex changed, the literal values of 140 citation strings changed, all 432 human triage judgements lost their match, and an old-to-new mapping table had to be built specially to rescue them.

**Constraint.** A decision table's key must be something that exists objectively outside: the printed abbreviation, the court code, the citation string itself. Group ids, canonical keys and row numbers computed by the pipeline must not be used. That way, however the pipeline changes, the results of manual verification never become invalid.

### Constraint eight: every decision-table row must carry its source

**History.** The most important batch of jurisdiction determinations in the old pipeline was hard-coded string by string in the source code of two Python scripts, about 70 in all, with no source at all; the only explanation was a comment `human-confirmed`. These determinations appeared in no data-audit scope and were nearly missed altogether during clean-up.

**Constraint.** Every row of the four decision tables must have the two columns `source` and `source_locator`. Rows without a source may not enter a table. Determinations must not be written into code.

### Constraint nine: trust no unverified number or quotation

**History.** During design discussions, file paths that looked concrete but were made up appeared, as did citations of statutory provisions that had not been checked against the book.

**Constraint.** Every specific value (frequency, proportion, byte count) must be able to explain how it was produced; every citation of a McGill Guide rule must be verified against scanned pages of the physical book. Anything that does not meet this is marked unverified and must not be used as a basis for implementation.

---

## 3. The five-layer architecture

### 3.1 The dividing criterion

The boundaries between layers are not drawn by "code file" but by **how much data a rule needs to look at**:

| Layer | What one rule needs to look at | So what it can do |
|---|---|---|
| Extraction | A piece of text | Structural matching |
| Classification | One row (the fields the row carries) | Table lookups, disambiguation, cutting case names |
| Merging | Several rows of one group | Counting, voting |
| Adjudication | Several groups after merging | Establishing case identity |
| Selection | The whole table | Keeping or dropping by threshold |

**The key test: if a rule needs to look at other rows, it belongs to merging; if it looks only at its own row, it belongs to classification.**

Cutting along this line leaves a third kind of task: neither per-row judgement nor statistics, but needing to know first "which case is this, actually". Case names exist only after merge voting, so this kind of task cannot be done before merging in any case. The old pipeline had no place for them, so they all leaked out as patches; that was the real mechanism that produced the three lists. They need a layer of their own: the adjudication layer.

### 3.2 Responsibilities of the five layers

```
Corpus (parquet, read-only)
  │
  ├─ 1. Extraction     structural matching, full output, no filtering or judging
  │
  ├─ 2. Classification each row independently: table lookups for jurisdiction, case-name candidates, flag false positives
  │
  ├─ 3. Merging        cross-row statistics: merge identical strings, fold variants, modal case-name voting
  │
  ├─ 4. Adjudication   case identity: origin determination, parallel-reporter merging, cross-court merging, splitting same-name different cases
  │
  └─ 5. Selection      one threshold, no rows deleted, flags only
        │
        └─ Product candidate table
```

### 3.3 The difference between the classification and adjudication layers

These two layers are the easiest to confuse, and it was precisely by mixing them that the old pipeline bred its patches.

**The classification layer judges reporter-level questions**: which jurisdiction the abbreviation `A.C.` belongs to. The answer is the same for every citation using that abbreviation and does not need to know which case it is.

**The adjudication layer judges case-level questions**: where this particular case actually comes from. The reporter jurisdiction of `[1938] A.C. 415` is England, but the case itself may be an appeal from Canada to the Privy Council, with Canada as its place of origin. Making this judgement requires knowing which case it is first.

In fields this shows up as `jurisdiction` (output of the classification layer, the reporter's jurisdiction) and `case_origin` (output of the adjudication layer, the case's real place of origin). The two are **not always equal**, which is the only reason the latter exists.

---

## 4. Directory structure and version control

```
D:\cases data analisis\
├── .gitignore
├── README.md                      English (since 2026-09-19, commit b1b8937)
├── PROBLEMS.md                    In git. A pure record; no script may read it (the only adjudicated exception is in 4.4)
├── select_config.yaml             In git. Threshold profiles of the selection layer (dd 5/2/10)
├── scripts\
│   └── download_corpus.sh         In git. Corpus snapshot download script (HF enumeration, resumable, SHA256 list;
│                                  bash/WSL. Windows schannel TLS is unusable under a restricted token; the WSL route was tested.
│                                  v1.8 note: it enumerates only SCC and directories starting with ON; BCCA and others need manual registration, see §1.3)
│
├── corpus\                        gitignored. Read-only snapshots; download dates and fingerprints registered in §1.3
│   ├── SCC.parquet
│   ├── ONCA.parquet
│   ├── BCCA.parquet               joined the main line 2026-09-18
│   └── CITT/TCC/SST/FPSLREB.parquet  experiment line only, not in the main-line corpus (§1.3)
│
├── docs\                          In git. Published documents (reorganized 2026-09-21, commit 07f6fea)
│   ├── USAGE.md                   how to read the data, what it under-counts
│   ├── method_cards\              9 method cards (00_new_court_playbook … 08_pitfalls_by_layer):
│   │                              per layer, "how it works / what to change for a new court / where people tripped", derived from the specification and PROBLEMS
│   └── technical_specification.md   this document
│
├── decisions\                     In git. The only source of facts; README.md explains each table's key and source
│   ├── README.md
│   ├── reporter_jurisdiction.csv      §5.1  abbreviation→jurisdiction (201 rows; 105 rows verified_print_evidence)
│   ├── neutral_court_codes.csv        §5.2  court codes of neutral citations (327 rows)
│   ├── series_prefix.csv              §5.3  series prefixes (4 rows)
│   ├── case_origin.csv                §5.4  case place of origin, per-case register (203 rows)
│   ├── case_origin_manual.csv         §5.4/§10.2  case place of origin, manual case-by-case verification (33 rows, R4)
│   ├── court_or_reporter_scope.csv    §10.2  exclusive place-of-origin rules for courts/identifiers (13 rows, R2)
│   ├── reporter_origin_scope.csv      §10.2  exclusive place-of-origin rules for reporter series (40 rows, R3)
│   ├── bilingual_neutral_codes.csv    bilingual neutral-code mapping (46 rows; 15 rows verified_explicit_equivalence)
│   ├── court_designations.csv         court designation texts (16 rows; 13 recognized + 3 ambiguous_designation)
│   ├── identifier_systems.csv         identifier systems (16 rows)
│   ├── id_prefixes.csv                registered-number prefixes (15 rows; drive the v1.6 table-driven shape of the extraction layer)
│   ├── non_citation_words.csv         closed table of non-citation words (76 rows; used for rejection in classification step2)
│   └── tools\                    table-building scripts (CanLII API, cache in data/canlii_cache/, replayable with --offline)
│
├── pipeline\                      In git. **The production line**
│   ├── normalize.py               shared pure functions
│   ├── shapes.py                  regex shape definitions (v1.4 seven shapes frozen; v1.6 adds table-driven shapes, see the note in §7.1)
│   ├── extract.py                 § 7; produces candidates.csv (all candidates, the only downstream input) + old-route extracted.csv (diagnostic)
│   ├── classify.py                § 8
│   ├── merge.py                   § 9
│   ├── decide.py                  § 10 (including the §10.2 three-tier origin waterfall, #88 mixed-key holdout, #105 self-citation removal)
│   ├── registry.py                judgment registry and own_citations output (input of the decide layer's --own-citations)
│   ├── select_layer.py            § 11
│   ├── edges.py                   effective source links (produces edges/ alongside decide_out)
│   ├── coverage_report.py         § 12.1 table-filling priority report
│   ├── trace_source.py            traces any row back to the source text by candidate_id (usage in README)
│   ├── run_all.py                 runs all five layers in one call (§12); run_manifest.json records the input fingerprint;
│   │                              --courts / PIPELINE_COURTS control the court list
│   └── tests\                     In git. The production line's acceptance instruments
│       ├── fixtures.py            six fixtures (taken verbatim from the corpus)
│       ├── truth.py               ground-truth table (68 entries, [unverified] as a whole)
│       ├── prose_sample.py        frozen prose anchor sample
│       ├── shapes_v1_frozen.py    frozen v1 copy, for regression comparison only
│       ├── run_regression.py      fixture regression / selftest / field-audit (extraction layer)
│       ├── test_layers.py         layers 2–5: unit assertions + mini end-to-end chain + `--golden` full golden diff
│       ├── test_candidates.py     assertions specific to the all-candidates route (candidates-2.x)
│       ├── test_non_citation_words.py / test_bracketed_foreign_neutral.py
│       │                          assertions specific to the v1.8 rejection families (#99/#104/structural words)
│       ├── golden_layers.json     full golden snapshot
│       └── corpus_counts.py       the only script that produces corpus-level counts
│
├── audit\                         In git. **The audit loop** (rules opposite to the production line, see 4.3)
│   ├── README.md                  explains every audit tool; see that file
│   ├── gap_audit.py               wide-net difference set: finds forms that "look like citations but the seven shapes did not catch"
│   ├── table_coverage.py, disambiguation_audit.py, case_origin_audit.py,
│   │   classify_diff.py, select_content_diff.py, preview_case_name.py,
│   │   case_name_gap_audit.py, preview_prose_trim.py, near_year_peers_audit.py,
│   │   extraction_recall_audit.py, one_vote_audit.py, gate_effect_audit.py,
│   │   decide_no_gate.py, glm_prep.py + glm_verify.py (GLM double check, output into
│   │   data/glm_audit/), append_problems_entry.py              the purpose of each tool is in audit/README.md
│   ├── name_borrow_audit.py + name_borrow_impact.py   dedicated audit of borrowed case names (v1.8)
│   ├── canlii_crosscheck\         CanLII API cross-check (T0–T6: extraction consistency, landmark dd comparison,
│   │                              manually labelled edges, dd-bucket calibration; reports in audit/findings/canlii_crosscheck/)
│   └── findings\                  audit reports (proposals, not data; the production line must not read them)
│
├── tools\                         In git. **Post-pipeline tools** (not in the production line; read no pipeline products outside data)
│   ├── foundation\                results-database import + DD weights (score.py, VERSION=canlii-t6-v1, experimental)
│   │                              + hybrid search (index_cases/index_methods/embed/query/acceptance)
│   ├── recall\                    experience library: chunks PROBLEMS/audits/decision tables/diaries and embeds them into
│   │                              data/recall/recall.db for people to search by meaning (#101 adjudicated exception, see 4.4)
│   └── archive_run.py             run archiver (zip + triple check of file count/bytes/CRC; refuses runs in running state)
│
├── implementation\                Mostly gitignored. Session reports, execution plans (plan_*.md) and one-off probes
│   │                              (`_probe_*.py`, `rN_*.py`); allow-listed files in git include run_registry.csv +
│   │                              run_registry_inputs.json + rebuild_run.py (identity registration and
│   │                              rebuilding of old runs, see data/README.md) and others; the list is in the text of .gitignore
│   └── …
│
└── data\                          gitignored. **The only root for machine output**; can be deleted entirely and rerun;
    │                              directory purposes, retention rules and rebuilding old runs in data/README.md
    ├── run_20261003_selfcite\     ★ delivery run (five layers + edges + run_manifest.json, see §12)
    ├── run_20261002_tables2\      previous baseline
    ├── run_20260914_r4c\          v1.7 delivery run (R4 review depends on it; rebuildable from run_registry)
    ├── extract_out … coverage_out the six output directories of the old route (v1.4 deduplicated route); the `--golden` gate reads here
    ├── audit\                     audit-loop output (kept apart from production output, see 4.3)
    └── canlii_cache\              needed by build_case_origin.py --offline
```

Contents of `.gitignore` (from v1.8 the four core lines are unchanged, with additional entries guarding secrets and local tool directories; only allow-listed files of `implementation/` are in git — `rebuild_run.py`, `run_registry.csv`, `run_registry_inputs.json`, `exp_bcca_citt_findings.md`, `coverage_metric.py`, `r4_verify_stage4.py`, `demo_examples.md`, `diff_report.md` and others; the text of `.gitignore` is authoritative):
```
corpus/
data/
*.parquet
__pycache__/
```

### 4.4 v1.8 note: repository reorganization and post-pipeline tools (from 2026-09-21 `07f6fea`)

**Reorganization for publication.** The README was translated into English (`b1b8937`); `USAGE.md`, this document and the method cards moved into `docs/`, and the download script into `scripts/`; the work diaries and execution plans in `implementation/` (`plan_*.md`, `report_*.md`) are no longer committed, only an allow-list. The boundary of human judgement in git, machine output not (4.1), is unchanged — method cards, like `decisions/`, are human judgement and are committed.

**Method cards (`docs/method_cards/`).** Nine per-layer cards answering "what to change and where people have tripped when adding a new court / a new citation form to this pipeline"; the content cites its sources (specification sections, code locations, PROBLEMS numbers) and is a per-layer summary of the specification, not a replacement — the cards are committed under the same rule as `decisions/`, and changing a layer's rules requires updating the matching card in the same commit. `tools/foundation/index_methods.py` builds an index of card fragments; search with `query.py --collection methods`.

**Experience library and the membrane (PROBLEMS #101, user decision 2026-10-02).** "No script may read PROBLEMS.md" (4.2) gets its first adjudicated exception: `tools/recall/build.py` chunks the ledger and other material and embeds it into `data/recall/recall.db` for people to search by meaning. The exception is conditional on three limits: ① only `build.py` reads the ledger, and it is outside the pipeline; ② `tools/recall/check_isolation.py` ensures the pipeline / `decisions/` / `audit` do not reference the search database; ③ `query.py` outputs only text for people to read. Breaking any limit revokes the exception. This extends the membrane rule of 4.3: the experience library is outside the membrane, and search results are hints for people, not data.

**CanLII cross-check (`audit/canlii_crosscheck/`).** External validation of the pipeline with the CanLII API: T2 extraction consistency on 5,684 pairs, T3 landmark dd comparison, T5 manually labelled edges, T6 dd-bucket calibration — weighted edge accuracy 87.0%, accuracy for dd buckets 1 / 2–4 / 5–9 / 10+ of 75 / 82 / 99 / 100% [verified, `audit/findings/canlii_crosscheck/REPORT.md` and the t6 output]. The T6 results feed the DD weights in `tools/foundation/score.py` (VERSION `canlii-t6-v1`, **experimental, not in the production threshold** — the dd threshold of §11 still uses the original value in `select_config.yaml`).

### 4.1 The core rule of version control

**Human judgement goes into git, machine output does not, and the two are never in the same directory.**

The old pipeline put everything in one gitignored directory, so human judgements had no version history. The direct consequence of having no undo was not daring to edit in place, so a manual backup copy was made before every change, eventually producing five backup directories. The backup directories were not the product of laziness but the inevitable result of having no version control.

The four tables in `decisions/` are the only irreproducible thing in the whole project, less than 100 KB in total, and all go into git. Everything in `data/` can be regenerated from `corpus/` plus `pipeline/` plus `decisions/`, so it does not go into git and can be deleted entirely at any time.

### 4.2 The status of PROBLEMS.md

It records every known, unresolved problem. **No script may read this file.** The restriction is deliberate: the old pipeline's three patch lists all began as "let's just write it down", were later read by some script and became configuration, and later still became irremovable dependencies. This path is blocked from day one.

### 4.3 The production line and the audit loop: the membrane rules

**Where the problem comes from.** The extraction layer has a real irreversibility: whatever the seven shapes do not catch, the classification layer never sees — not "deferred to the next layer" but "lost for good". So a mechanism is needed that keeps discovering things that "look like citations but were not caught". But this mechanism **cannot grow on the production line**: once the decision tables are filled, every false positive of a wide net becomes a piece of wrong data that "looks verified" (the position of 1.2).

**The solution is to split the system into two halves with opposite rules.**

| | Production line (`pipeline/`) | Audit loop (`audit/`) |
|---|---|---|
| What it produces | **Data** (becomes the product's source of facts) | **Proposals** (suggestions for people to read) |
| May it guess | No (constraint four) | Yes |
| Must it be deterministic | Yes | No |
| May it use a wide net | No (constraint two) | It should |
| May it use AI | No | Yes, but the output is still a proposal |
| May it modify upstream in reverse | No (constraint six) | The loop is reverse by nature |

**The test.** Which set of rules a piece of work follows has one test only: **is its output data or a proposal?** AI proposing candidate rows → data → no; AI helping a person group difference-set residuals → proposal → yes. A wide-net difference set going straight into the candidate pool → no; a wide-net difference set prompting an eighth shape → yes.

**Rules for crossing the membrane.** From the audit loop to the production line, only three things may pass:

1. Deterministic shapes (regexes, with positive and negative assertions)
2. `PROBLEMS.md` entries (with replayable numbers)
3. Decision-table rows (with `source` / `source_locator`, constraint eight)

What may not pass: candidate rows, confidence scores, AI-judged spans, anything that "looks right but is unverified".

From the production line to the audit loop, **signals** may pass: output files, wide-net difference sets, counts of field-audit invariant violations, the classification layer's rejection patterns. **Signals go back; data does not.** The classification layer repeatedly rejecting the same pattern is a signal that "a shape is missing"; the right response is to send the signal back to the audit loop, evaluate, build the shape and rerun the full corpus, **not to let the classification layer re-extract on the spot** (that would turn it into a second extractor, and the separation of layers would fail).

**No production script may read the audit loop's output**, the same status as 4.2.

**How the nine constraints divide between the two halves.** Constraints one to six are the production line's rules and largely do not apply to the audit loop; constraints seven and eight guard the membrane (they set the conditions the audit loop's output must meet to become knowledge of the production line); **constraint nine is the audit loop's entire constitution** — the audit loop may guess, but any number that wants to cross the membrane into the specification must be replayable.

**The meaning of "frozen" changes accordingly.** Under the old wording, freezing meant permanent freezing (because a rerun was treated as a disaster). Measured, a full run of `extract.py` takes about 100 seconds and is deterministically replayable, so the precise meaning of frozen is: **frozen until the audit loop gives a reason**. The extraction layer thus has a normal version rhythm: the audit loop finds a gap → write down the criteria → a prototype measures the gain/collateral ratio → if it passes, build the shape → verification matrix → full rerun → new manifest. What is really expensive has never been rerunning; it is a schema change once downstream depends on it.

---

## 5. Decision-table specifications

Four tables, all in `decisions/`, all in git, every row with its source.

**v1.8 note: the table family and verification grades (measured 2026-10-04).** Beyond the four tables originally defined in this section, `decisions/` now has eight more: `case_origin_manual.csv`, `court_or_reporter_scope.csv`, `reporter_origin_scope.csv` (these three are the §10.2 origin-waterfall tables already in the specification since v1.7), plus `bilingual_neutral_codes.csv` (46 rows, bilingual neutral-code mapping; 15 rows `verified_explicit_equivalence`), `court_designations.csv` (16 rows, court designation texts; 13 rows `recognized` + 3 rows `ambiguous_designation`), `identifier_systems.csv` (16 rows), `id_prefixes.csv` (15 rows, input to the extraction layer's table-driven shape, see the note in §7.1) and `non_citation_words.csv` (76 rows, used for rejection in the classification layer, see the note in §8.4). The vocabulary of verification grades has also evolved from this section's original three tiers into row-level values: `reporter_jurisdiction.csv` now has **201 rows** — `verified_print_evidence` 105, `verified_authority` 30, `name_inference` 56, `authority_identity_only` 9, `authority_country_only` 1 [verified, counted row by row]; the `confidence` column is still `estimated` for the whole table (the upgrade of verification grades was not linked to the confidence field; unifying the field semantics awaits human review). Constraint eight is unchanged: new rows must carry `source`/`source_locator`. The main table-level changes from 2026-09-15 → 10-04: 101 reporter rows upgraded from name inference to print-evidence verification (commit `42da55a`), 39 rows re-annotated with sources (`451b2b6`), `S.J.` split by volume into GB/SK rows going through §8.6 range disambiguation (#100), 13 bilingual code pairs corrected according to printed facts (#103), the `F.C.J. No` row and new T.C.J./G.S.T.C./G.T.C. and others added (`f7f3951`, `d5f54e9`).

### 5.1 `reporter_jurisdiction.csv`: abbreviation to jurisdiction

**Purpose.** Answers "which jurisdiction does this reporter abbreviation belong to". This is the classification layer's main source of facts.

**Fields.**
```
abbreviation, normalized_key, jurisdiction,
vol_range_start, vol_range_end, year_range_start, year_range_end,
confidence, verification_level,
source, source_locator, added_date, notes
```

**The key is the composite `(abbreviation, jurisdiction)`, not `abbreviation` alone.** The same abbreviation may appear in several rows, each representing one candidate jurisdiction and its value ranges.

This design has a side benefit: **homographs need no separately maintained list**. An "ambiguous abbreviation" is simply "an abbreviation that appears in more than one row of this table". The table is both data and index, so there is no scenario of "an abbreviation is ambiguous but we did not notice". The old pipeline needed someone to guess first which abbreviations were ambiguous and then handle them; that approach is unnecessary under the new table structure.

**Field notes.**
- `normalized_key`: generated by `nk()` (see 6.1), to absorb differences in writing such as `A.C.` vs `AC`
- `vol_range_*` / `year_range_*`: the volume and year coverage of this reporter in this jurisdiction, the only basis for homograph disambiguation (see 8.4). Left empty when unknown, meaning "this dimension does not take part in disambiguation"
- `confidence`: `confirmed` / `inferred` / `estimated`
- `verification_level`: `guide_explicit` (stated in the book) / `guide_by_context` (inferable from the book) / `external_authority` (external authoritative source) / `name_inference` (inferred from the name)

Distinguishing `confidence` from `verification_level` is necessary: in the old pipeline every label looked equally reliable in the output, while their actual reliability differed enormously, and downstream could not tell them apart.

**Current status.** An empty table with only a header. The source for filling it is unverified: whether the McGill Guide contains a table mapping reporter abbreviations to jurisdictions, which appendix it is in and what it covers are all [unverified], to be confirmed by Hermes against scanned pages of the physical book. If the McGill Guide is not enough, external authoritative sources must be assessed, together with the effect of their licence terms on the project's IP cleanliness. (v1.8 correction: this paragraph records the state at v1.2 and is out of date — the table now has 201 rows, including 9 rows outside the jurisdiction, with the row-level verification distribution in the note above; "the source for filling it is unverified" is still not closed, and checking against the physical McGill book is still a gap.)

**Filling strategy.** Fill in descending order of `distinct_decisions_count`, covering first the twenty or thirty abbreviations with the most citations; the long tail always returns `UNSUPPORTED`. A few high-frequency reporters cover the great majority of citations, so returns diminish quickly once the table reaches some size, and completeness need not be pursued.

**The head of the priority list follows measurement (v1.3 correction).** After the scope was widened to all citations, the head is no longer foreign reporters. Measured (2026-09-05, corpus = SCC+ONCA, counted by occurrence, produced by `pipeline/tests/corpus_counts.py`, with the patterns recorded verbatim in that script, uniformly anchored at both ends): `S.C.R.` (family: dotted 146,175 + missing final dot 277 + bare SCR 12,165 + half-dotted forms 15 + typeset with internal spaces 1,732) 160,364, `C.C.C.` 30,705, `O.R.` 29,970, `D.L.R.` 18,675, `W.W.R.` 6,126. The head is **S.C.R., C.C.C., O.R., D.L.R.** (W.W.R. next; `C.C.C.` and `O.R.` differ by 2.4%, essentially tied for second). Three points to note: first, v1.2 counted `O.R.` at 124 with the pattern `\bO\.R\.\b` and on that basis excluded it from the head — because of the final `\b`, that pattern never matches the real form (`O.R.` followed by a space), and 124 was exactly its count of embedded fragments like `O.R.C.C.` and `O.R.B.D.` and OCR-glued strings, without a single real citation; this lesson has been blocked mechanically by the pattern assertions in corpus_counts.py. Second, Ontario judgments refer to themselves with the neutral code `YYYY ONCA n` (63,571 times / 18,267 judgments) alongside printed `O.R.` citations of other cases (20,024 times); the two coexist and do not exclude each other. Third, this count measures **frequency of textual forms**; `distinct_decisions_count` will exist only after the first full extraction, the two orderings may differ, and the full result will then be authoritative.

### 5.2 `neutral_court_codes.csv`: court codes of neutral citations

**Purpose.** Answers "what is the `UKHL` in `[1868] UKHL 1`".

**Background.** BAILII and other bodies have retroactively assigned neutral citation numbers to historical cases. The McGill Guide states explicitly that such retroactive neutral citations are to be treated like court-assigned neutral citations (that rule has been verified). So these citations are a legitimate citation form and must be extractable and recognizable.

**Fields.**
```
court_code, normalized_key, jurisdiction, source, source_locator, added_date
```

**Nature.** A closed, enumerable set. There are only a few dozen neutral-citation court codes in the whole world, and additions are controlled institutional events (a court is created or reorganized). This is entirely different in nature from the open set of reporter abbreviations.

**Current status (v1.5, 2026-09-09). Table built, 313 rows.**

Source: **CanLII API v1 `caseBrowse`** (an API key provided by the user). Method — first fetch `/v1/caseBrowse/en/` for all 409 case databases (`databaseId` / `jurisdiction` / `name`), then take the `citation` field of 5 cases from each database; for renamed courts, supplementary rounds at 9 points in time via `decisionDateBefore` (2020/2018/2016/2015/2013/2012/2008/2006/2002/2003/1998), plus one round on the French endpoint `/v1/caseBrowse/fr/` covering the main federal and Quebec courts (French codes such as `CSC` and `CAF` appear reliably only on that endpoint). About 500 calls in all, 1 second apart.

**`court_code` is not derived from `databaseId`.** Measured: in **118 of the 409 databases, `databaseId.upper()` does not match the real neutral code** (`csc-scc`→SCC, `fct`→FC, `cci-tcc`→TCC, `onhrt`→HRTO, `cmac-cacm`→CMAC …), so `databaseId` is used only to pick databases, and the code written into the table is always taken from the segment printed in that database's real case citations (`YYYY <CODE> <n>`) — a printed fact, satisfying constraint seven. `source_locator` records for each row the databaseId, the raw value of the jurisdiction field, the court name, a supporting citation string and the endpoint URL, so each row can be replayed.

A side gain: French neutral codes (`TCDP`/`CCI`/`CF`/`NBBR`/`TPFD`, etc.) and historical codes from before renaming (`ABQB`/`ABPC`/`PECA`/`NWTSC`/`NFCA`/`NLTD`/`FCT`, etc.) went into the table too, both by-products of the same fetch.

**The table-building script's three rejection gates (constraint four)**: ① the same `court_code` mapping to different `jurisdiction` values in two databases → no row is written, and it is listed as a conflict for a human to decide (measured 0 cases); ② evidence from `ukpc` is never written (PROBLEMS #32); ③ bodies whose database name points to two or more jurisdictions at once are not written — the jurisdiction is not single-valued, and this table's one-code-one-jurisdiction shape cannot hold it (PROBLEMS #34, instance `NTNUWCAT`). When several databases supply evidence for the same code, prefer evidence where "the normalized database name equals the code", then sort by the number of samples in the database printing that code, descending. Fetch failures are reported explicitly, and with more than 0 failures the table is not written. Single-evidence rows (10 entries) were listed separately for review and checked one by one without error. The `CanLII` pseudo-code is skipped per PROBLEMS #31.

**Measured coverage** (instrument `audit/table_coverage.py`, replayable). Of the 147,242 rows of `shape_neutral_bare`, **142,208 rows (96.58%)** hit exactly. The 5,034 rows that slip through fall into three classes: vendor identifiers 4,494 (the Carswell family, the `CanLII` pseudo-code, `WL`/`DTC`), extraction noise 427 (`April`, `Agreement` and the like), and **113 likely real court codes**.

**The third class is a gap, not "correct behaviour".** The first v1.5 draft described everything that slipped through as "all vendor codes and noise; falling to UNSUPPORTED is correct behaviour" — **that conclusion was wrong** and has been corrected; how is recorded in PROBLEMS #34. Of the remaining 113 rows, `QCTAQ` 31 and `ONSEC` 7 have been found to be structurally unobtainable from CanLII (PROBLEMS #35 B).

**This table does not cover `shape_bracket`.** Of that route's 218,046 rows only 76 hit exactly — because the great majority are printed reporter citations, under the jurisdiction of `reporter_jurisdiction.csv`. But among those that slip through are **1,042 rows of likely real court codes, headed entirely by foreign neutral citations** (`UKHL` 225, `UKSC` 163, `EWHC` 114, `HCA` 91 …), which CanLII cannot supply and another source must be found for — see PROBLEMS #35 A; this is currently the largest known gap that a source could close.

**Known defect, see PROBLEMS #33**: if this table were looked up with the normalized key as in §8.2, reporter abbreviations such as `F.C.` and `C.B.` would collide with it (measured 2,565 rows), while the measured gain of the normalized key on this table is 0 rows.

**Status (v1.2).** After the scope was widened to all citations, this table was promoted from a marginal table to a **main table**: neutral citations (`2019 SCC 65`, `2003 EWCA Civ 1746`, `YYYY ONCA n`) are the largest single class of citation in the corpus (corpus = SCC: the `YYYY SCC n` form measured 31,926 times, covering 1,708 judgments, produced by `pipeline/tests/corpus_counts.py`), and it is the only one of the four tables that is closed and enumerable. The priority order in 13.3 reflects this.

### 5.3 `series_prefix.csv`: series prefixes

**Purpose.** In forms where "the abbreviation comes before the volume", such as `L.R. 3 H.L. 330`, recognizes whether the leading abbreviation is a legitimate series prefix.

**Background.** The English Law Reports family used this "series prefix + volume + division abbreviation + page" structure between 1865 and 1875. The regex structure that extracts these citations (abbreviation number abbreviation number) is extremely loose and matches a great deal of text unrelated to citations, so a table is needed to filter it.

**Fields.**
```
canonical_prefix, normalized_key, source, source_locator, added_date
```

**Current status.** An empty table with only a header. Exactly which legitimate prefixes the Law Reports family has is [unverified] and goes to Hermes for verification together with 5.1.

**Note.** Earlier discussions included filling this table with example rows and giving specific rule numbers and page numbers as the source. Those rule and page numbers were unverified, and example data risks being copied into the real table, so this specification provides no example rows.

### 5.4 `case_origin.csv`: the real place of origin of a case

**Purpose.** Answers "which jurisdiction does this particular case actually come from". Mainly for JCPC (Judicial Committee of the Privy Council) cases: the reporter jurisdiction is England, but the case may come from any Commonwealth jurisdiction — Canada, Australia, New Zealand, Hong Kong and so on.

**Fields.**
```
citation_display, normalized_key, case_origin, deciding_court,
source, source_locator, added_date
```

**The key is the printed citation string itself**, such as `[1938] A.C. 415`. `citation_display` stores exactly what the person filling the table saw, and `normalized_key` is generated by `nk()`.

**Why the printed citation string and not a group id generated by the pipeline.** This is a direct application of constraint seven. The pipeline's internal canonical keys and group ids change as algorithms are adjusted; once they change, every manually verified row in the table loses its match at once, and the manual verification has to be done all over again. The printed citation string is a fact in black and white in the judgment; it does not change however the pipeline changes, and it is exactly what the person filling the table sees and relies on when verifying "where this case was appealed from". Filled once, valid forever.

The keys of the other three tables (abbreviation, court code, series prefix) are printed facts as well; the four tables agree on this.

**Coverage.** Only cases whose place of origin needs a separate determination are included; full coverage is not required. For the great majority of cases the place of origin matches the reporter jurisdiction and needs no separate record.

**Current status.** **204 rows** filled (2026-09-11, PROBLEMS #59), from CanLII API v1 `caseBrowse/en/ukpc/` (the database of Privy Council judgments on Canadian appeals): among this pipeline's groups judged GB and printed in Privy Council-type reporters (A.C./App. Cas./P.C./All E.R./W.L.R./T.L.R.), 211 groups were matched by "the word sets of both parties' names match + judgment year ∈ report year−2..report year". This table does not depend on Hermes, because a case's place of appeal origin is a publicly checkable fact that can be verified against the judgment itself. But the roughly 70 hard-coded determinations of the old pipeline **must not** be used as an input source; they may only be used for a comparison afterwards.

**Implementation note (R2–R4).** Case-level origin determination no longer looks up only this table; see the three-tier priority waterfall in §10.2: this table and the identically structured `decisions/case_origin_manual.csv` (33 rows, manual case-by-case verification, see §10.2) together form the first tier `case_record`; there are also two rule tables (not per-case registers, but registers of exclusive scope by "court/identifier" or "reporter series" as a whole) — `decisions/court_or_reporter_scope.csv` (13 rows, second tier `court_scope_rule`) and `decisions/reporter_origin_scope.csv` (41 rows, third tier `reporter_origin_scope`). The four tables have different fields and differently shaped keys (this table's key is a single printed citation string; the two rule tables' keys are a court code / reporter abbreviation + a date window); do not mix them up when filling them. Pending review.

**Implementation note (v1.6, 2026-09-11).** The coverage boundary of this source is **1888–1959** (643 entries in the database); Canadian Privy Council appeals before 1888 are simply not in the database and always stay `UNDETERMINED` — this is the direction constraint four requires (under-counting), not a missed determination; filling it needs a second source and is an open problem. Lookups still happen at the member-string level per §10.2, so within one merged group "the S.C.R. citation of the Supreme Court judgment" and "the A.C. citation of the Privy Council appeal" get different places of origin. The table-building tool is `decisions/tools/build_case_origin.py` (cache `data/canlii_cache/`, replayable with `--offline`), with the entry-by-entry comparison report `audit/findings/case_origin_review.md`. All pending review.

---

## 6. Shared pure functions (`pipeline/normalize.py`)

Three functions are used in several layers and must be defined in one place; no layer may write its own copy.

### 6.1 `nk()`: the general normalized key

```python
def nk(s: str) -> str:
    """Remove every non-alphanumeric character and lowercase."""
    return re.sub(r"[^A-Za-z0-9]", "", s).lower()
```

Used to normalize abbreviations and citation strings. `A.C.`, `AC` and `A. C.` all normalize to `ac`.

### 6.2 `normalize_code()`: code normalization

```python
def normalize_code(code: str) -> str:
    """Remove periods, spaces and hyphens, and uppercase."""
    return re.sub(r"[.\s\-]", "", code).upper()
```

Used for court codes and series prefixes. `U.K.H.L.`, `U. K. H. L.` and `UKHL` all normalize to `UKHL`.

**Why a normalizing function rather than enumerating variants in the table.** Spelling variants cannot be enumerated; adding a table record for every new form has a very high maintenance cost, and additions cannot be applied retroactively to old data. Normalization is a deterministic pure function: the same input always gives the same output, it can be fully reproduced in an audit, and it adapts automatically to any new variant that appears in future.

### 6.3 `dedup_overlapping()`: interval-overlap deduplication

See 7.4.

---

## 7. The extraction layer

### 7.1 The seven structural shapes

Shared sub-patterns live in `pipeline/shapes.py`; each shape only combines them. Every example and number in this section comes from the regression baseline in `pipeline/tests/` (run 2026-09-05; method in 13.1).

```python
_ABBR = (
    r"[A-Z][A-Za-z]*"
    r"(?:[ .&]+(?!No\.)[A-Z][A-Za-z]*)*"              # between segments + v1.4 debt-1 boundary: a segment
    #                                                   does not start with the numbering word No. (see the dedicated section §7.2)
    r"(?:[ .&]+[a-z]{2,3}[ .&]+[A-Z][A-Za-z]*)?"      # optional lowercase segment (of/de), must be followed by an uppercase segment
    r"\.?"
)
_YEAR = r"(?:1[6-9]|20)\d{2}"
_SEP_COMMA = r"\s*,?\s+"                              # year→volume; abbreviation→series/parenthetical/page
_SEP_TIGHT = r"\s+"                                   # prefix→volume; volume→abbreviation
_ORD = r"\d+(?:st|nd|rd|th|d)"
_SERP = rf"\(\s*{_ORD}\s*\)"
# v1.5 #11: non-ordinal parentheticals ((Mass.)/(N.S.)/(H.L.)/(U.S.) and other court, jurisdiction and division labels).
# **Tight definition**: starts with a capital, no digits, limited length — not the same thing as what 7.2 (5) 1
# rejected (that rejected stuffing nominate's \([^)]+\) into the general slot and thereby losing the trailing-year
# gate); this pattern and _SERP are mutually exclusive (measured: (2d) matches only _SERP, (Mass.) only _NONORD)
_NONORD = r"\(\s*[A-Z][A-Za-z. ]{0,8}\s*\)"
_SERP_SLOT = rf"(?:{_SEP_COMMA}(?:{_SERP}|{_NONORD}))?"   # parenthetical slot (ordinal or non-ordinal)
# v1.4 debt 1 + v1.5 #28: the numbering-marker slot. No. (capitalized with a period) and no (French lowercase without a period,
# the Jurisprudence Québec style [2010] J.Q. no 9074). These are the two members of the _ABBR literal
# exception; threshold in 7.2 (6)
_SERIAL_SLOT = r"(?:\s+(?P<serial_marker>No\.|no))?"
# bare ordinal series + v1.4 glued variant (F.2d: the ordinal right against the abbreviation's period, zero whitespace). The glued variant requires
# an ordinal suffix (st/nd/rd/th/d) — OCR-glued pages like Q.B.D.43 have no suffix and are still not accepted (the distinction from #12)
_SERIES_OPT = rf"(?:{_SEP_COMMA}(?P<series>{_ORD})|(?P<series_glued>\d{{1,2}}(?:st|nd|rd|th|d)))?"
# page: digits (optional letter-slash prefix D/, footnote suffix n) or a Roman-numeral page (xi/vii, leave to
# appeal preliminary pages). The Roman sub-pattern's {2} minimum length blocks the empty string and the section marker c.; the alternation is wrapped as a whole in (?:)
_PAGE = (r"(?:(?:(?P<page_prefix>[A-Z]{1,2}/))?(?P<page>\d+)(?P<page_suffix>n)?(?![A-Za-z0-9])"
         r"|(?P<page_roman>(?=[ivxlcdm]{2})(?:c[md]|d?c{0,3})(?:xc|xl|l?x{0,3})"
         r"(?:ix|iv|v?i{0,3}))(?![a-z0-9]))")
```

(Which separator each slot uses is set out in the "separators assigned per slot" paragraph of this section and in §13.1; `series_glued` is a separate capture group that the extract layer merges into the `series` field.)

**The no-volume variant: implemented, then rolled back (v1.4, PROBLEMS #21).** The volume of `shape_year_vol_page` was once made optional to open up forms like `(1938) S.C.R. 423`, with a misparse guard of "two capitalized words + digits". After implementation the audit found: the guard's trailing negative lookahead excluded the period, so the period of real footnote citations kept it from ever firing; the failed guard let no-volume misparses (`(1874), L.R. 9`) crowd out the correct string (`L.R. 9 Ex. 192`) in deduplication by virtue of starting earlier; 2,231 misparses against a real gain of 670, net negative, rolled back. Two lessons: first, guard/validation regexes must be tested against **real typesetting** (with periods); synthetic strings do not count; second, the interval-overlap criterion of `is_covered` cannot detect "catching an overlapping wrong string" — an **exact tier** (verbatim equality) has been added, kept separate from covered. Recorded and kept: the no-volume form occurs 670 times / in 424 judgments; the unlocking conditions are in PROBLEMS #21.

**Three decisions about `_ABBR`.**

1. It starts with a capital letter, as in the old pipeline [verified]: so ordinals starting with a digit, like `2d` and `4th`, are not swallowed into the abbreviation.
2. The separator between segments is `[ .&]+`, without `\s`. v1's `[\s.&]+` crossed line breaks and full stops, gluing two pieces of text into one "abbreviation".
3. One lowercase segment of 2–3 letters is allowed, and it must be followed immediately by a segment starting with a capital (to avoid swallowing ordinary lowercase English words into the abbreviation). This covers the French reporters `R. de J.` (93 occurrences in this corpus) and `C. de D.` (196), and incidentally `H. of L.` (17) — under v1 not one of these three classes was extracted. Counts are by occurrence (corpus = SCC), produced by `pipeline/tests/corpus_counts.py`.

Deliberately not done: no comma in the **within-segment** separator set of `_ABBR`. `117 U, S. R. 113` (an OCR comma, corpus = SCC, 2 times) and `13 C.B., N.S., 381` (a comma nominate, 13 times) are indeed not extracted; but once a comma enters the within-segment separator set, `Howard, L.R.` in `Howard, L.R., 9 C.P., 308` glues into one abbreviation — **case-name swallowing**. This gap becomes a diagnostic observation item (PROBLEMS.md) and is not solved at the regex level. Note that the shape-level comma tolerance of `_SEP` and the within-segment prohibition of this paragraph are two things at two levels and must not be confused.

**`_PAGE`: page suffixes captured explicitly.** v1 ended with `(?![A-Za-z])`, and on `12n` did not refuse to match but **truncated by backtracking**: `\d+` first swallowed `12`, then after the assertion failed gave back to page=`1`, producing a normal-looking wrong row. v2 captures the suffix explicitly and tightens the assertion to `(?![A-Za-z0-9])` — the digit block closes the backtracking path. Measured (`pipeline/tests/run_regression.py --selftest`): `[1892] 1 Ch. 12n` gives page=`1` under v1 (silent truncation) and page=`12`, `page_suffix`=`n` under v2.

**`_ORD` and the ordinal parenthetical slot `_SERP_SLOT`.** v1's ordinal pattern `\d(?:st|nd|rd|th)?` missed the `d` suffix and allowed only single digits, so `(2d)`, `(3d)` and `(10th)` all failed to match — the self-describing example in v1 spec §7.1, `83 F. (2d) 212`, was NO MATCH under v1 (measured). v2 changed it to `\d+(?:st|nd|rd|th|d)` and made the ordinal parenthetical an optional slot reused across several shapes; `shape_series_paren` therefore **disappeared**, its function absorbed by the slot. The parenthetical form is the mainstream form in the corpus: `(2d)` occurs 13,669 times and `(3d)` 16,994 times (corpus = SCC, by occurrence; for the two corpora SCC+ONCA together, 19,663 and 50,999 times respectively — the ONCA corpus measured covers only 1998–2026, and its high frequency of `(3d)` comes from judgments of that era citing (3d)-era reporters heavily).

Deliberately not done: `_SERP` is not relaxed to "an ordinal or any capitalized parenthetical". The corpus does contain non-ordinal parentheticals like `4 Allen (Mass.) 447` (`(Mass.)` 75 times, `(Q. B.)` 5 times, `(N.S.)` 1,020 times), which v2 does not extract. The known candidate change was rejected for a structural reason: `shape_nominate` has always accepted any non-digit parenthetical with the very loose `\([^)]+\)`, and it can afford to be that loose because it requires a trailing `(year)` — that year is its false-positive gate. Stuffing an equally loose parenthetical into the general slot would let the year-less `shape_vol_abbr_page` inherit nominate's looseness while losing its gate. This gap becomes a diagnostic observation item (PROBLEMS.md).

**Two forms of recurrence that constraint two cannot prevent (lessons of v1.3/v1.4).** Constraint two blocks "checking against a list" but not two other mechanisms that quietly let the same kind of citation go: first, **typesetting assumptions hidden in separators** — v1.4 found that the ordinal slot assumed whitespace between the abbreviation and the ordinal (19th-century typesetting `83 F. 2d 212`), so the whole family of modern American `571 F.2d 1277` was missed; the same victim as the original accident of missing American citations (a fixed list), by a different mechanism; second, **wrong capture-group semantics** — the inter-segment set of `_ABBR` absorbed the numbering word `No.` into the token (the token of `[1989] B.C.J. No. 1393` was `B.C.J. No.`): the row exists, looks normal, and every field is wrong, invisible on both the missed-extraction and the false-positive lists. The countermeasures have been institutionalized: positive and negative example assertions for measurement patterns (`PATTERN_ASSERTIONS`) guard the measurement layer, and the five field invariants of `run_regression.py --field-audit` guard the shape layer; any change to `shapes.py` must run both (PROBLEMS #19/#22).

**Separators assigned per slot (v1.3 correction).** 19th-century typesetting uses commas inside citations, but commas appear only in two kinds of slot: **after the year** (`(1936), 83 F. 2d 212`) and **before the page** (`L.R. 5 H. of L., 86`; `724, at 733` is after the page). Of the three evidence examples given when v2 introduced the single `_SEP`, not one supports a comma in the "prefix→volume" or "volume→abbreviation" slots — and the commas in those two slots are exactly the mechanical source of "case-name swallowing": `R. v. Vu, 2013 SCC 60` was glued by `shape_leading_abbr` into `Vu, 2013 SCC 60`, which with its longer span crowded out the correct `2013 SCC 60` in deduplication. Measured (2026-09-06: of 119,438 `shape_leading_abbr` hits across the two corpora, 91,356 swallowings were carried solely by the comma in the "prefix→volume" slot, 98.8%; see PROBLEMS #18). So the separator was split in two and applied by slot semantics across all seven shapes: `_SEP_COMMA = \s*,?\s+` for year→volume and abbreviation→series/parenthetical/page (towards the page); `_SEP_TIGHT = \s+` for prefix→volume and volume→abbreviation. Measured cost and gain: tightening the volume→abbreviation slot lost 69 rows (reviewed one by one by hand, see PROBLEMS #18); rows of `shape_neutral_bare` after deduplication 52,092 → 142,433 (+90,341 real citations previously crowded out by name swallowing revived with their correct identity); recall on fixtures A–F identical to v2 position by position, and D's known false positive disappeared. `_SEP_TIGHT` keeps cross-line matching (`\s` includes line breaks): footnote citations wrapped across lines really exist, and the evidence for tightening to `[^\S\n]+` is insufficient, so it is left as an observation item. **This is unrelated to the within-segment separator set of `_ABBR`** — the reason the latter accepts no comma (case-name swallowing) is unchanged; after this correction removed the main source of comma swallowing outside segments, what remains of that gap is small.

| Shape | Structure | Capture groups | Matching examples (all measured against the regression baseline) |
|---|---|---|---|
| `shape_bracket` | `[year] (vol) word page` | `year, vol?, token, series?, page, page_suffix?` | `[1978] A.C. 728`, `[1978] 2 All E.R. 492`, `[1868] UKHL 1` |
| `shape_vol_page_year` | `vol word page (year)` | `vol, abbr, serial_marker?, series?, page, page_suffix?, year` | `389 U.S. 347 (1967)`, `211 D.L.R. 4th 300 (2004)` |
| `shape_year_vol_page` | `(year) vol word page` | `year, vol, abbr, serial_marker?, series?, page, page_suffix?` | `(1936), 83 F. 2d 212`, `(1889) 6 R.P.C. 518` |
| `shape_nominate` | `vol word (note) page (year)` | `vol, abbr, serial_marker?, page, page_suffix?, year` | `2 Q.B. (N.S.) 100 (1893)` |
| `shape_neutral_bare` | `year code (division word) number` | `year, token, series?, page, page_suffix?` | `2019 SCC 65`, `2003 EWCA Civ 1746` |
| `shape_vol_abbr_page` | `vol word (ordinal) page` (no year) | `vol, abbr, serial_marker?, series?, page, page_suffix?` | `93 E.R. 664`, `347 U.S. 483`, `34 D.L.R. (2d) 451` |
| `shape_leading_abbr` | `(year)? prefix vol word page` | `year?, leading_abbr, vol, abbr, serial_marker?, page, page_suffix?` | `L.R. 3 H.L. 330`, `L.R. 5 P.C. 179` |

Where the two new shapes fit: `shape_neutral_bare` covers neutral citations without brackets (`2019 SCC 65`); `shape_vol_abbr_page` covers the year-less `vol abbreviation page` (`93 E.R. 664`, `347 U.S. 483`) and the second and later segments of parallel citation strings (measured on fixtures: the last two of `[1966] S.C.R. 238, 47 C.R. 400, 2 C.C.C. 273`). All six v1 shapes required the year in brackets or parentheses, so not one modern neutral citation was extracted.

`shape_vol_abbr_page` and `shape_leading_abbr` have no year component, so rows produced by these two shapes have an empty `year_raw`. As a result they cannot take part in the homograph disambiguation of 8.6 (a missing year returns `UNSUPPORTED`), nor in the year-proximity test of 10.3. This is a known limitation; no speculative filling is done.

**Implementation note (v1.8, extraction layer v1.6: table-driven shapes, from 2026-09-19, commits `7bb4165`/`4c75ff0`).** On top of the frozen seven shapes, `pipeline/shapes.py` adds a section of **table-driven shapes** (the "v1.6 table-driven shapes" section of `shapes.py`), whose distinguishing feature is that the regex is generated from tables in `decisions/` and the criteria live in the table, not the code; the "structural shape" nature of constraint two is unchanged (the tables themselves are still built row by row from printed facts with `source_locator`):

1. **Registered-number prefix shape**: the regex is generated from `decisions/id_prefixes.csv` (15 rows) (`load_id_prefix_rows()` → `_registered_id_regex()`), and a hit is group-normalized by `resolve_registered_id()` (called in two places in `extract.py`) — covering registered-number systems other than CanLII (the same origin as `identifier_systems.csv`). Note that the `verification_status` of all 15 rows of that table is still `unverified_corpus_observed` (10) / `unverified_prior_knowledge` (5), **not yet upgraded to `verified_official_source`**; under constraint nine they must not be quoted as verified facts.
2. **Glued neutral citations**: `_glued_neutral_regex()` covers zero-space forms like `2005TCC640`, with the court code taken from the normalized key of `neutral_court_codes.csv`.
3. **Bracketed year ranges**: `shape_bracket_range` (`_BRACKET_RANGE_HEAD`) covers range years like `[1938-39] C.T.C. 138` — the handling of item 1 in §15, "split-year formats are not supported", is thereby **partly lifted**: the range head can be extracted, the year group still takes a single value, and the range semantics (start and end years) are not expanded.

On version labels: the `shapes_version` string in `extract.py`'s run metadata still says "v1.4 (frozen)" — those words describe the frozen definition of the **old deduplicated diagnostic route**; the shape set of the all-candidates route (candidates) is the v1.4 seven shapes + the v1.6 table-driven shapes, and the numbers of the two cannot be compared (§1.4 already has the same two-route warning). Pending review.

**Tie-breaking order between shapes (SHAPE_ORDER).** The final tie-breaker of deduplication takes whichever shape comes first in definition order (see 7.4). `shape_neutral_bare` must come before `shape_vol_abbr_page`: `2019 SCC 65` is matched by both with exactly the same span (the latter treats the year as a volume), and reversing the order would demote the semantics of such citations to a free abbreviation. The order is fixed in `pipeline/shapes.py`; changing it requires rerunning the 13.1 baseline as well.

### 7.2 Five key design points

**(1) The series group fixes the truncation defect; explicit capture of page suffixes replaces silent truncation.**

Three shapes of the old pipeline defined the page as `(?P<page>\d+)` immediately after the abbreviation [verified]. For a citation like `83 F. 2d 212`, the `2` of `2d` was consumed as the page, the real page `212` was lost, and the extracted string was `83 F. 2`. The same defect affects `211 D.L.R. 4th 300`, so it is not limited to foreign citations.

v1's fix (inserting an optional series group) is kept; but its accompanying page-suffix assertion `(?![A-Za-z])` has a real, measured behaviour: **for footnote-marked pages like `212n` it does not refuse to match but silently truncates** — `\d+` first swallows `12`, then gives back after the assertion fails, finally producing a normal-looking wrong row with page=`1`. Silent truncation is far more dangerous than a missed extraction, because it enters downstream without any trace.

v2's fix is to capture the suffix explicitly and tighten the assertion: `(?P<page>\d+)(?P<page_suffix>n)?(?![A-Za-z0-9])`. `page_suffix` enters the output schema (7.3); the digit block closes the path of "giving back part of the page". Measured (`run_regression.py --selftest`, key `page_suffix_12n`): `[1892] 1 Ch. 12n` gives page=`1` under v1 and page=`12` + `page_suffix`=`n` under v2. The earlier paragraph saying "this fix has an unmeasured side effect" is hereby void — the side effect has been measured: suffixed pages are no longer lost, and the negative controls of the fixture baseline (13.1) show no new false positives.

**(2) The year range is widened uniformly, with no switch.**

The year in every shape is uniformly `(?:1[6-9]|20)\d{2}`, covering 1600 to 2099.

The old pipeline made the year extension an opt-in switch `--widen-years` [verified]; when on, the output directory became `<COURT>_widened`, producing two parallel sets of output directories, and every reconciliation had to declare first which definition it used. The switch existed to protect the stability of an "academic snapshot", and that snapshot corresponded to no paper and no reader; it was an archive with no use. A constraint that did not exist blocked something correct.

The new pipeline has no switch, no parallel directories, and a single year range.

**(3) The bracket shape does not distinguish reporters from court codes.**

`[1978] A.C. 728` (a printed reporter) and `[1868] UKHL 1` (a retroactive neutral citation) are identical in regex structure: both are `[year] capitalized-word number`. The only difference is which table the middle word should finally be looked up in, and that is a lookup question, not a structural one.

If the two had separate shapes, the same text would be matched twice with exactly equal spans, and the deduplication rule could not choose between them. Any special case of "a given shape wins on equal spans" would be a patch.

So they are merged into one shape whose capture group is named `token` (not `abbr`), and the classification layer looks up both tables to decide what it really is. This also enforces constraint two more thoroughly: the extraction stage involves no table at all.

Symmetrically, the leading abbreviation of `shape_leading_abbr` is captured as `leading_abbr`, and again whether it is a legitimate series prefix is not judged at the extraction stage.

**(4) Why neutral citations are a separate shape, and why the two dimensions of the token (case, length) are structural constraints.**

Neutral citations like `2019 SCC 65` have no year in brackets; all six v1 shapes required the year in brackets or parentheses, so not one was extracted. After the project scope was widened to all citations (1.1), this was the largest single gap and needed a shape of its own.

The code restriction was originally `[A-Z]{2,6}`; v1.4 relaxed it to "a space-free, purely alphabetic segment starting with a capital, 2–12 characters" (`[A-Z][A-Za-z]{1,11}`, accepting mixed-case vendor identifiers CanLII/CarswellOnt and 7-character court codes FPSLREB/LNQCTAQ) — still a **structural constraint, not a list** (constraint two): it describes only the shape "starts with a capital, no spaces, 2–12 characters" and does not judge "is this code a legitimate court code" — the latter is established by the classification layer looking up `neutral_court_codes.csv`. The basis for the two dimensions (set in v1.4; neither floats with the prose false-positive curve): **case** — there must be internal capital alternation (`CanLII` matches; the prose word `Things` has no internal capital and `APPENDIX` is all capitals with no lowercase segment, so neither matches, measured); **length** — the upper bound 12 = the longest observed identifier + a margin (the longest court codes are 7 characters, FPSLREB/CRTESPF; the longest vendor identifiers 11, CarswellOnt/Que); the knee of the prose false-positive curve was deliberately not used — the knee is set by the length of month names (December 8 characters, September 9), and cutting at the knee would actively exclude CarswellOnt. This is not wordplay: if common codes (SCC, EWCA …) were written into the regex, every new code or OCR variant would require changing the regex and rerunning full extraction (constraint six), and whatever was excluded would appear in no output, not even producing the signal "the table needs filling" (the same argument as in 8.3).

The cost of the loose structure is taken up by the classification layer: strings of "number capitalized-word number" in prose (such as a year followed by an institution's abbreviation) are matched by this shape, enter the classification layer with full fields, and get `UNSUPPORTED` from the court-code table. This is the same kind of false positive as the comma tolerance of `_SEP`: the extraction layer would rather give more candidates that carry traces than make judgements at extraction that require table lookups (constraint one).

**(5) Deliberately kept gaps (three changes explicitly rejected this round, so the next round does not propose them again).**

1. **`_SERP` is not relaxed to accept non-ordinal parentheticals.** `4 Allen (Mass.) 447`, `28 L. J. (Q. B.) 118` and `2 C.B.R. (N.S.) 121` are not extracted under v2 (corpus counts in 7.1). The candidate change was to relax `_SERP` to "an ordinal or a short parenthetical starting with a capital"; rejected: the loose parenthetical `\([^)]+\)` of `shape_nominate` can afford to be loose because it requires a trailing `(year)` as its false-positive gate; stuffing an equally loose parenthetical into the general slot would let the year-less `shape_vol_abbr_page` inherit nominate's looseness while losing its gate. Becomes a diagnostic observation item (PROBLEMS.md).
2. **No comma in the within-segment separator set of `_ABBR`.** See the `_ABBR` paragraph in 7.1. Of the three failures `U, S. R.`, `C.B., N.S.,` and `H. of L.`, the first two share the single decision "the within-segment separator set contains no comma"; `H. of L.` is already covered incidentally by the lowercase-segment change (measured: `L.R. 5 H. of L., 86` is NO MATCH under v1 and matched whole by `shape_leading_abbr` under v2, see the `--selftest` key `hofl_literal`).
3. **No lookbehind for `shape_leading_abbr`.** A lookbehind `(?<![\w,]\s)` was once added to prevent case-name swallowing and has been withdrawn. Judging whether the leading abbreviation is a legitimate series prefix requires looking up `series_prefix.csv`, which is the classification layer's job (8.3 explains why that filter cannot be tightened into the extraction regex). Adding a lookbehind in the extraction layer is patching in the wrong layer and violates constraint one. Let `shape_leading_abbr` produce its false positives; they stay in the table with `unrecognized_series_prefix`. (v1.3 addendum: the main mechanical source of case-name swallowing was the comma tolerance of the "prefix→volume" slot — tightening that slot removed about 99% of swallowing, and that is a correction of the shape's own internal separator structure, not a lookbehind, and looks up no table; what this item rejects is unchanged. See PROBLEMS #18.)

**(6) The literal exception in `_ABBR`: why there is only one, and what a second one must do to get in (v1.4).** `_ABBR` now contains one word-level exception: at the start of a segment, `(?!No\.)` — the numbering marker `No.` must not be absorbed into the abbreviation (the token of `[2010] O.J. No. 3423` used to be caught as `O.J. No.`, so the classification layer's lookup always failed with no signal at all; 16,124 times / 6,935 judgments, field-audit inv1). Why this does not violate constraint two: constraint two's harm model is "an allow-list makes what is not listed silently disappear", whereas the net effect here is **relocating information** — the token returns to `O.J.` and the numbering word goes into the separate `serial_marker` field; not one character is lost, it just changes field; the harm model is not triggered. The earlier argument of "typographic markers vs domain markers" is abandoned (it is debatable and opens a slippery slope to `Num.`/`nr.`/`n°`). The admission threshold for a second literal exception (all three required): ① it brings its own optional slot that **moves the word into a typed field** (not just excluding it); ② it brings the full set of #16 measurements (anchor + the matching field-audit invariant); ③ it proves the information is relocated rather than discarded. `Num.`/`nr.`/`n°` and the like go through this process one by one, not as a bundle.

**(7) Slot inventory in the last round before freezing (v1.4): two slots filled, two deliberately kept empty, all measured and recorded.** The distribution of shared slots across the seven shapes was audited cell by cell: the absence of `_SERP_SLOT`/`_SERIES_OPT` in leading_abbr is **deliberately kept** — measured, the lead+ordinal form occurs 40 times (lead_serp 28 + lead_series 12), and every one checked was case-name swallowing (the lead position held a party name `AWH Corp.`/`QVC Network Inc.`/`Canada Ltd.`, and the real citation after it was already captured normally by vol_abbr_page); adding the slot would only produce longer swallowing matches that crowd out clean real citations in deduplication — the swallowing bug that v1.3 spent a whole round fixing would revive in a new place, so it is not added. The absence of `_SERIES_OPT` in `shape_nominate` **measured 0 times** — so "measured, it is 0" can be told apart from "never measured". Two slots filled: the year-prefix slot of leading_abbr (#24: 1,631 times / 745 judgments get a year field; the net row increase of +206 belongs to change two — the two numbers answer different questions, each labelled clearly); `_SERIAL_SLOT` shared (#25: the approval condition of `(?!No\.)`, "relocating information", requires a receiving slot in all five shapes, for consistent scope). **Regexes frozen**: the presence or absence of every slot in each of the seven shapes has a number and a reason; see the freeze list in §13.1.

### 7.3 Output fields

```
raw_string, shape_name,
token, leading_abbr, abbr, serial_marker, vol, page, page_prefix, page_roman, page_suffix, series,
year_raw, year_start,
preceding_text, source_decision_citation, source_decision_year,
match_start_offset, match_end_offset, match_span
```

Field notes:

- `raw_string`: `re.sub(r"\s+", " ", match.group(0)).strip()`, only collapsing whitespace, no other change
- `token`: has a value for `shape_bracket` and `shape_neutral_bare`
- `leading_abbr`: has a value only for `shape_leading_abbr`
- `abbr`: has a value for shapes other than the two above
- `page_suffix`: new in v2. The footnote marker `n` right after the page (`12n`). An empty string and absence are two different things: `page` with a value and `page_suffix` empty means "this page has no footnote marker"; no sentinel other than the empty string may be used
- `serial_marker`: new in v1.4 debt 1. The numbering-marker slot of `shape_bracket` (the `No.` of the `X.J. No. n` style). The defect before the fix was that the token absorbed `O.J. No.` — the classification layer's lookup always failed with no signal; the fix = relocating information (a clean token + the marker captured separately), with no information discarded. Six _ABBR shapes have this group (bracket and the five shapes filled in v1.4); `shape_neutral_bare` does not.
- `year` (the conditional year group of leading_abbr): added by change one of v1.4 — the year of the `(year) prefix vol abbreviation page` form (measured after aligning shapes at 1,631 times / 745 judgments) used to be discarded and is now recovered; a missing year is still the norm (the group is empty when there is no prefix), and disambiguation is unchanged under the §8.6 principle "a missing year means UNSUPPORTED".
- `page_prefix` / `page_roman`: new in v1.4. `page_prefix` captures the prefix of letter-slash pages (the `D/` of the C.H.R.R. style, 395 times / 65 judgments); `page_roman` captures Roman-numeral pages (leave to appeal preliminary pages `xi`/`vii`, 1,143 times / 636 judgments). The same principle as `page_suffix`: capture explicitly, never silently convert or truncate
- `series`: the ordinal series group (the `4th` of `211 D.L.R. 4th 300`). From v1.4 it includes the glued variant: the `2d` of `F.2d` is captured by the `series_glued` group and merged into `series` by the extract layer. In `shape_neutral_bare` it carries the division word (the `Civ` of `2003 EWCA Civ 1746`) — reusing an existing field rather than adding one, with the semantics distinguished by `shape_name`. Parenthetical ordinals matched by the `_SERP` slot (the `(2d)` of `47 D.L.R. (2d) 400`) are **not captured** and only take part in the match span: v1's `shape_series_paren` did not capture them either, and this version keeps that; if the classification layer later needs to distinguish `D.L.R. (2d)` from `D.L.R. (3d)`, whether to upgrade it to a capture group will be assessed then (that requires rerunning full extraction, constraint six)
- `preceding_text`: the 120 characters before the start of the match
- `source_decision_citation`: `{COURT}_{citation_en}`, e.g. `SCC_2019scc12`. **It must carry the court prefix**, otherwise when counting distinct judgments as a union across courts, two courts' judgment numbers that happen to share a format would be taken as the same judgment
- `match_end_offset`: needed for deduplication, see 7.4

**About `year_start`.** In this version `year_start` always equals `year_raw`. The year capture group matches only four plain digits; a split-year form like `(1893-94)` captures only `1893`, and the hyphen and second half never enter the capture group.

So **no** processing code of the form `year_raw.split("-")[0]` may be written. Such code looks as if it handles split years but actually never runs, the pattern this project has been burned by again and again in its history: a piece of logic that seems solved but never took effect is far more dangerous than an explicit gap. Split-year formats are currently unsupported and recorded in PROBLEMS.md. The two field names are kept only so that supporting it later does not require changing the downstream schema.

**About how the abbreviation is taken.** The extraction layer must take capture groups from the **original match object** and must not re-parse an already generated string with a regex. The old pipeline took the normalized citation string, searched it again with all the shapes, and took the first result with an `abbr` group [verified]. This second parse can reach a different conclusion from the original match, and no mechanism would detect the disagreement.

### 7.4 Deduplicating repeated hits

The same citation may be matched by different shapes with **different starting points**. For example `(1936), 83 F. 2d 212`: `shape_year_vol_page` matches from `(`, and `shape_vol_abbr_page` may match the same citation from `83`. The two have different starts and overlapping intervals.

If the deduplication rule handled only repeats with "exactly the same start", all such overlaps would pass, one citation would be counted twice, and `occurrence_count` would be systematically inflated.

**The deduplication criterion is interval overlap, not identical start:**

```python
def dedup_overlapping(rows: list, shape_order: list) -> list:
    """Within one judgment, of overlapping matches keep only the longest span.
    On equal spans take the earlier start, then the shape earlier in shape_order.
    Output re-sorted by start, ascending."""
    by_decision = defaultdict(list)
    for r in rows:
        by_decision[r["source_decision_citation"]].append(r)

    kept = []
    for _, group in by_decision.items():
        # primary key span descending, start as secondary key, shape order as final key: the longest match claims its place first
        group.sort(key=lambda r: (-r["match_span"],
                                  r["match_start_offset"],
                                  shape_order.index(r["shape_name"])))
        accepted = []
        for r in group:
            if any(r["match_start_offset"] < a["match_end_offset"] and
                   a["match_start_offset"] < r["match_end_offset"]
                   for a in accepted):
                continue
            accepted.append(r)
        kept.extend(accepted)
    return sorted(kept, key=lambda r: (r["match_start_offset"],
                                       r["match_end_offset"]))
```

**Why the longest span first.** Truncation defects naturally produce shorter wrong matches (`83 F. 2` is shorter than `83 F. 2d 212`); year-less shapes match sub-spans of shapes with a year (measured on fixtures: `34 D.L.R. (2d) 451` is matched whole by `shape_vol_abbr_page` and covered by a longer match in the same string). Using span as the priority criterion itself counters both kinds of defect and is more robust than a fixed priority order of shapes.

**Why the primary key must be the span and not the start (v1.2 correction).** The code block in this section once used start ascending as the primary key, directly contradicting the section's own claim to "keep only the longest span": an earlier **short** match would claim its place first and crowd out a later **long** match as overlapping. Measured demonstration (`run_regression.py --selftest`, key `dedup_ordering_example`): for `See Smith 3 All E.R. 12 (1968)`, start ascending lets `See Smith 3 All E.R. 12` of `shape_leading_abbr` (start 0) claim its place first and crowd out `3 All E.R. 12 (1968)` — the kept row is then judged `unrecognized_series_prefix` at the classification layer because `leading_abbr="See Smith"` is not in `series_prefix.csv` (8.3), and the whole citation is effectively lost. With span descending as the primary key, this failure mode of "early and short crowding out late and long" is removed.

One point that must be recorded honestly (same measurement): for this particular string `See Smith 3 All E.R. 12 (1968)`, span descending **cannot** rescue it — once `See Smith` is glued into the abbreviation, that false-positive match is itself the longest span and wins under both orderings. Span descending fixes the inconsistency between the sort criterion and the stated rule and the "early short over late long" class; case-name swallowing itself is not deduplication's responsibility, and is handled in the classification layer (8.3, constraint one). The deduplication layer does not judge semantics; it only keeps spans.

Deduplication is done within a single judgment, so it can safely be done within a batch, since one judgment is never split across two batches.

**Deduplication does not delete rows (v1.3 correction).** The algorithm above only decides "who enters the count"; it no longer physically discards the losers: `extract.py` outputs two files — `extracted.csv` (kept rows) and `extracted_superseded.csv` (deduplication losers, with `superseded_by` pointing to the row id of the kept row). Occurrence/decision counts read only the former, consistent with every registered number in this section; questions like "why is this case not in the results" (constraint five) read the latter. Putting the losers in a separate file rather than adding a boolean column makes "counts look only at kept" a structural invariant, not dependent on every downstream step remembering to filter — a count that forgets to filter is silently inflated, which is exactly why deduplication existed in the first place. There is no revival mechanism: if a crowded-out row is itself structurally malformed (a swallowing row), downstream simply rejects it, and the fork information is kept in `superseded_by`; after the v1.3 slot correction (see 7.1) removed the main source of swallowing, the losers are few. The implementation of `dedup_overlapping` accordingly returns "two groups, kept and superseded", and the equivalence assertions in `pipeline/tests/` were updated to match.

### 7.5 Reading the corpus

**Use pyarrow's streaming interface with column projection.**

```python
import pyarrow.parquet as pq

COLUMNS = ["citation_en", "document_date_en", "unofficial_text_en"]
pf = pq.ParquetFile(parquet_path)
for batch in pf.iter_batches(batch_size=500, columns=COLUMNS):
    ...
```

pandas' `read_parquet` has no chunking parameter and reads the whole file into memory. The old pipeline's aggregation script used exactly `pd.read_parquet` for full corpus scans [verified], one reason it needed a 900-second hard timeout.

### 7.6 Filtering by judgment year

The old pipeline by default processed only judgments from 1970 on [verified], with no reason given in the code.

**The new pipeline has no default lower bound on years** and processes every judgment in the corpus. If a restriction is needed for performance, it must be passed as an explicit parameter and recorded in the run manifest; it must not become a silent default.

Distinguish two different years: the **judgment year** (when this Canadian judgment was written) and the **citation year** (when the cited foreign case was decided). The former is a filter condition on corpus rows; the latter is a field inside the citation. The old pipeline's 1970 lower bound is the former, and the widening of the year range discussed in 7.2 is the latter; the two are different things and must not be confused.

### 7.7 Loop structure and batching

**The loop order must be text in the outer loop, shapes in the inner loop:**

```python
for record in batch:            # outer: text
    for shape_name, regex in SHAPES:   # inner: shapes
        for m in regex.finditer(text):
            ...
```

The other way round reads the corpus seven times over.

**Batching and resuming:**

- 500 judgments per batch, written to `batch_NNNN.csv`
- After each batch, update `progress.json`, recording only the `last_batch` index
- Atomic writes: write `batch_NNNN.csv.tmp` first, rename when done, so a crash midway leaves no half-written file
- On resume, read `progress.json` and start from `last_batch + 1`; if the target batch file already exists (the file was written last time but progress was not updated), rerun that batch and overwrite it
- When all batches are done, merge into `extracted.csv`

### 7.8 The extraction layer's output is complete

No filtering of any kind, no frequency cut-off, no top-N.

The old pipeline's detailed output kept only the top 2000 citation strings by frequency by default [verified], so the file was not a true complete superset: new entries pushed out old ones. Any reconciliation based on that file had to declare first what parameters were used, or the numbers would not match.

---

## 8. The classification layer

Each row is judged independently. Homograph disambiguation uses the structural evidence the row carries (volume, year) and reads no surrounding text, so it does not violate "look only at this row".

### 8.1 Processing order

```
Step 1  shape-level preprocessing: determine citation_kind and abbreviation
Step 2  reject non-case citations
Step 3  jurisdiction lookup
Step 4  homograph disambiguation (only when Step 3 returns several candidates)
Step 5  case-name candidate cutting and cleaning
```

### 8.2 Step 1: looking up both tables for `shape_bracket`

```python
norm_token = normalize_code(row["token"])
court_hit = lookup_one(norm_token, neutral_court_codes, "normalized_key")
reporter_hits = lookup_all(nk(row["token"]), reporter_jurisdiction, "normalized_key")

if court_hit and not reporter_hits:
    row["citation_kind"] = "neutral"
    row["abbreviation"] = court_hit["court_code"]
    row["jurisdiction"] = court_hit["jurisdiction"]
    row["jurisdiction_confidence"] = "confirmed"
elif reporter_hits and not court_hit:
    row["citation_kind"] = "reporter"
    row["abbreviation"] = row["token"]
    # falls through to Step 3
elif court_hit and reporter_hits:
    row["citation_kind"] = "ambiguous"
    row["jurisdiction"] = "UNSUPPORTED"
    append_reason(row, "table_conflict")
else:
    row["citation_kind"] = "reporter"
    row["abbreviation"] = row["token"]
    row["jurisdiction"] = "UNSUPPORTED"
```

**Why look up both tables rather than set a priority.**

Looking up the court-code table first and stopping on a hit is a design that looks reasonable but is wrong, for two reasons:

First, though the closed table is small, a false hit in it is the most costly. If a real printed reporter citation were judged a neutral citation, the determination would look decisive, and no downstream step could detect the error.

Second, the court-code table can be filled at once, while the reporter table stays empty for a long time. Setting a priority would let the progress of table filling decide the result. The same data would get different conclusions before and after the table is filled, with no flag pointing this out.

When both tables hit, it is flagged `table_conflict` for a human to decide — the same principle as homographs' "several candidates match, so don't guess", with no exception here.

**Pending decision (v1.5, 2026-09-08): whether `normalize_code(row["token"])` in the first line of this section should become an exact match.** Measured after the court-code table landed (PROBLEMS #33): the normalized key's gain on `shape_neutral_bare` is **0 rows** (neutral codes are never printed with periods), while on `shape_bracket` it creates **2,565 rows** of hits that should not exist (`F.C.`→FC 2,496, `C.B.`→Copyright Board of Canada 15, etc.). The mitigation designed in this section is that looking up both tables yields `table_conflict`, but that depends on the reporter table being non-empty, and that table is still empty — during the empty-table period these normalized hits would become "decisive wrong determinations". To be decided together with the numbers when writing classify.py; this version does not alter the algorithm block on its own authority.

**Decided (v1.6, 2026-09-09, approved by a human).** The normalized fallback is neither removed nor kept as is: a **structural gate** is added — the normalized fallback is enabled only when the row has no volume (the structural signature of a neutral citation); a normalized hit **never yields a determination** (it is not a printed fact; it falls to UNSUPPORTED with a `lookup_mode=normalized` trace); when both tables hit at different match grades, the exact side wins, and only the same grade counts as `table_conflict`. The process and measurements are in PROBLEMS #33, #36, #41. The algorithm block above is kept as the original design; the implementation in `pipeline/classify.py` is authoritative.

**Implementation note (v1.6, PROBLEMS #38).** §8.1 lists "shape-level preprocessing" as one step, but only `shape_bracket` (this section) and `shape_leading_abbr` (§8.3) get a section each; `shape_neutral_bare` has none — yet its `token` is exactly the neutral court code, with an exact hit rate of 96.59%, the main user of `neutral_court_codes.csv`. **This implementation extends this section's two-table logic by analogy**: `shape_neutral_bare` goes through the same two-table lookup and `table_conflict` handling as `shape_bracket`, with no priority, for the same reason this section gives — the court-code table can be filled at once while the reporter table stays empty for a long time, and a priority would let the progress of table filling decide the result. This is a gap filled by the implementer, not the text of the specification. Pending review.

### 8.3 Step 1: checking the prefix of `shape_leading_abbr`

```python
norm_prefix = normalize_code(row["leading_abbr"])
if not lookup_one(norm_prefix, series_prefix, "normalized_key"):
    append_reason(row, "unrecognized_series_prefix")
else:
    row["series_prefix"] = row["leading_abbr"]
row["citation_kind"] = "reporter"
row["abbreviation"] = row["abbr"]    # the main abbreviation comes only from the abbr group
```

`leading_abbr` takes no part in the jurisdiction determination. It is a series identifier, not a reporter abbreviation.

**Implementation note (v1.6).** Approved by a human (PROBLEMS #52): a recognized prefix that carries a jurisdiction takes part in homograph disambiguation: the `Q.R.` of `Q.R. 56 K.B. 520` has already printed Quebec on the row. `series_prefix.csv` gains a `jurisdiction` column for this; when the prefix conflicts with the table, the result is UNSUPPORTED, with neither side overriding the other. Pending review.

**`unrecognized_series_prefix` and `UNSUPPORTED` must be kept apart.** The former means "this is most likely not a citation at all" (a false positive caused by the loose structural skeleton); the latter means "this is definitely a citation, but the jurisdiction is unknown". The two mean entirely different things for the selection layer and for product quality; lumping them together would make it impossible to tell "collateral damage from extraction" from "insufficient evidence".

**Why the filter is in the classification layer rather than tightening the extraction regex.** Tightening the extraction structure would mean excluding candidates with a fixed list at the extraction stage, repeating the lesson of missing all American citations: what is excluded appears in no output, not even producing the signal "the table needs filling". In the classification layer, false positives stay in the table with an explicit rejection reason, and once `series_prefix.csv` is extended, a rerun recovers them.

### 8.4 Step 2: rejecting non-case citations

Two rules, as in the old pipeline [verified]:

```python
FED_STATUTE = re.compile(r"(?:^|[\s(\[])(?:R\.S\.C\.|S\.C\.)\s*(?:18|19|20)\d{2}")
CHAPTER = re.compile(r"\bc\.\s*(?:[A-Z]|\d)")
PARTY_INITIALS = re.compile(r"\bR\.\s*v\.\s*[A-Z]\.[A-Z]\.")

if FED_STATUTE.search(s) and CHAPTER.search(s):
    append_reason(row, "federal_statute")
if PARTY_INITIALS.search(s):
    append_reason(row, "party_initials")
```

The first targets federal statutes mistaken for case citations (the structure of `R.S.C. 1985, c. C-46` resembles a case citation). The second targets party names that appear as initials, like `R. v. A.B.`.

Flagged rows **continue on to have their other fields filled and are not discarded** (constraint five). `rejected_reason` can accumulate several values, joined with `|`.

**Implementation note (v1.6, PROBLEMS #37).** The specification does not define which field `s` in the code block refers to. Measured (all 582,408 rows): with `s` as `raw_string` alone, both rules hit 0 times — so a literal implementation would give code that never runs. Applying `PARTY_INITIALS` to the whole `preceding_text` hits 15,999 rows (2.7%), rejecting normal citations that "happen to have `R. v. A.B.` mentioned earlier" and falling into the "systematic under-count of citations" that §8.8 warns about. **This implementation's definition**: `FED_STATUTE` uses `preceding_text + raw_string` (866 rows); `PARTY_INITIALS` uses "the preceding text ends exactly in `R. v.`, and the row's `raw_string` starts with `X.Y.`" (92 rows, SCC 60 + ONCA 32) — that is, the case where the party initials themselves were mis-extracted by the shape layer as something like `leading_abbr`. Pending review.

**Implementation note (v1.6).** A self-citation flag is added as well (the handling decided in PROBLEMS #13, landed in #54): when the row's extracted string `nk(raw_string)` equals the judgment's own citation, `self_citation=true`. It is a real citation and does not go into `rejected_reason`; the merge layer does not count it. Pending review.

**Implementation note (v1.7, PROBLEMS #85: the date form `date_form`).** The structure of a header/agreement date `1 June 2007` is letter for letter the same shape as `shape_vol_abbr_page` ("vol abbreviation page"): the extraction layer splits it into vol=`1` / abbreviation=`June` / page=`2007`, which is the extraction layer's **correct** behaviour (the design of §7.1 is exactly "look only at shape, extract everything"). Judging "this is not a citation" is therefore the classification layer's job, handled exactly like `federal_statute`: **structural criterion → `rejected_reason`; the row is not deleted, only not counted** (constraint five).

It is blocked only when all three criteria hold **at once**, and all three are taken from fields the extraction layer has already split, **without rerunning a regex on the source text** (the caution in §8.4):

```python
MONTH_NAMES = frozenset([...])            # January..December, 12 calendar words
# 1) the abbreviation slot (or leading abbreviation slot) is a full English month name (ignoring case and a trailing comma/period)
# 2) volume 1–31 (day)  3) page a four-digit number 1600–2099 (year)
if date_form_hit(row):
    append_reason(row, "rejected_reason", "date_form")
```

Measured (`run_20260915_r21a`, on the classification layer's real input `candidates.csv`): SCC 832 + ONCA 987 rows hit, **all** with `citation_kind=reporter` / `jurisdiction=UNSUPPORTED` / empty `lookup_mode` — zero table support; on the experiment line (exp/bcca-citt) the same form gave BCCA 43,143 / CITT 26,255 rows. No abbreviation or normalized key in `reporter_jurisdiction.csv` or `neutral_court_codes.csv` has the same shape as a full month name (161 + 327 keys compared one by one with `nk()`, zero hits), so the full-name rule causes no collateral damage to known reporters.

**Effect (same-input A/B measurement, `data/audit/ab85_old` vs `data/run_20260916_85date`)**: a zero-support candidate is still judged `counted` when nothing competes with it (occurrence 1 per row), so this rule **does** remove date mentions from the counts — month keys at the main-line decided layer 1,337 → 212, occurrence 1,856 → 243, dd 1,493 → 212. All 212 remaining keys fall outside the three conditions (volume slot 0/-31/32-99/100+, page slot mostly 1–2 digits), all with dd 1: **month keys among groups kept at dd≥5 = 0**. **Correction of 2026-09-17**: a clean A/B review overturned the sentence "not one occurrence/dd grew" — once rejected rows leave the arbitration pool, another junk candidate competing with them on the same span, previously `overlap_undecided` (undecided), may switch to `counted`; measured 5 rows (all occurrence=1/dd=1/`kept=false`, not in the kept table, no material effect on the final result; see the correction record in PROBLEMS #85). The hole in the original statement: it checked only whether existing keys grew and could not detect brand-new keys switching from uncounted to counted.

**Why this does not violate constraint two.** Constraint two prohibits the **extraction layer** from using a fixed list of abbreviations to decide "accept or not" (the argument in §7.2: what is excluded appears in no output, not even producing the signal "the table needs filling"). Month names are not reporter abbreviations; they are a closed set of 12 calendar words that will never change because of a new reporter; and this rule sits in the classification layer, so blocked rows **stay in the table with a `rejected_reason`**, the same nature as `federal_statute`. It is the same kind of argument as the already approved "recognize closed-set markers only at the start/end of a segment" of §8.7 #58 (a structural / closed-set criterion, not enumeration of a word list).

**Implementation note (v1.8, four new batches of rejection from 2026-09-19 → 10-03, commits `f7f3951`/`d5f54e9`/`fe8c66c`).** After `date_form`, step2 / the two-table lookup gained four more kinds of rejection, all following the same handling pattern — **structural criterion → `rejected_reason`; the row is not deleted, only not counted** (constraint five):

1. **`non_citation_word` (table-driven, `f7f3951`+`d5f54e9`)**: `decisions/non_citation_words.csv` (76 rows, all `verification_status=observed_closed_word`) drives `_non_citation_word()` (`classify.py`), blocking "fake reporter citations whose abbreviation slot holds a structural word / calendar word / case-name fragment" (PROBLEMS #113, fixed). This generalizes the same argument as #85: a closed word list + the classification layer + a trace, not violating constraint two. Dedicated assertions in `pipeline/tests/test_non_citation_words.py`.
2. **`versus_as_page` (`f7f3951`)**: forms where the `v.` of `R. v. X` is misread by the shape layer as the page position; the classification layer rejects them on a structural criterion.
3. **`bracketed_year_foreign_form` (#99, `fe8c66c`)**: `FCA` is the same code for two countries (Canada's Federal Court of Appeal / the Federal Court of Australia). The bracketed-year form `[2003] FCA 50` appears in 17 rows of the corpus, all Australian cases, and is now judged `ambiguous`/UNSUPPORTED; the form without brackets is still judged CA. Dedicated assertions in `test_bracketed_foreign_neutral.py` (3). **Not done**: disambiguation by the parenthetical `(F.C.A.)`, a full rerun to check those 17 rows, merging an AU row into the table, reviewing `HCA` and similar codes.
4. **`court_exact_withheld_by_vol_signature` (#104, `fe8c66c`)**: the neutral code `FC` has the same shape as the printed form of the *Federal Court Reports* — `[1998] 1 FC 549` is a reporter volume-page citation, not a neutral citation. In the two-table lookup (§8.2), if an exact neutral hit carries a volume position and the volume ≠ the year, the neutral hit is given up and it falls to the reporter lookup. About 12 rows on the main line are affected; no full rerun has been done.

Also: the `F.C.J. No` reporter row entered the table (Quicklaw style, CA, `verified_print_evidence`). #104 together with items 3 and 4 handles the family of "homograph misjudgements at the two-table lookup layer", complementing the disambiguation rules of §8.6; both changes affect only hit semantics and add no shape. Pending review.

**Implementation decisions (not settled by the specification; human review required).**

**Three boundaries deliberately not blocked, all measured and recorded (better to miss a block than to add a whitelist of forms).** ① Abbreviated months (`28 Feb. 1995`, `4 Mar. 726`): the same shape as reporter abbreviations (`Mar.` may be March's Reports, and that series is not yet in the table), PROBLEMS #86; ② French months (`22 Janvier 1834`): SCC 54 / ONCA 1 rows, the residual column of PROBLEMS #85; ③ the "year-month-day" form (`1936 April 21`, `2014 January 26`, the year in the volume slot and the day as the page) and the "volume=0 / short page" form (`0 December 13`, `15 January 9`): the residual column of PROBLEMS #85. There is also one **inherent cost**: `Cass. 22 March, 1882` (a Cassation case with its judgment date) has four fields of the same shape as a date and is blocked too — the rule looks only at the structured slots; this is a boundary cost, not a defect.

### 8.5 Step 3: jurisdiction lookup

```python
candidates = lookup_all(row["abbreviation"], reporter_jurisdiction, "abbreviation")
if not candidates:
    candidates = lookup_all(nk(row["abbreviation"]), reporter_jurisdiction, "normalized_key")

if len(candidates) == 1:
    row["jurisdiction"] = candidates[0]["jurisdiction"]
    row["jurisdiction_confidence"] = candidates[0]["confidence"]
    row["lookup_mode"] = "exact" or "normalized"
elif len(candidates) > 1:
    row["jurisdiction"] = disambiguate_by_structure(row, candidates)
    row["jurisdiction_confidence"] = "inferred"
else:
    row["jurisdiction"] = "UNSUPPORTED"
    row["jurisdiction_confidence"] = "unsupported"
```

Exact matching first, the normalized-key match as a fallback. The `lookup_mode` field must record which was used. A normalized match is a fuzzy match and must not be indistinguishable from an exact match in the output.

### 8.6 Step 4, homograph disambiguation: the structural-evidence method

```python
def disambiguate_by_structure(row, candidates):
    """Match the citation's own volume and year against the candidate jurisdictions' value ranges.
    Determine only on a unique match; zero or several matches are always UNSUPPORTED."""
    vol, year = row.get("vol"), row.get("year_start")
    if not vol or not year:
        return "UNSUPPORTED"           # missing structural evidence, don't guess
    vol, year = int(vol), int(year)

    matching = []
    for c in candidates:
        vs = int(c["vol_range_start"] or 0)
        ve = int(c["vol_range_end"] or 99999)
        ys = int(c["year_range_start"] or 0)
        ye = int(c["year_range_end"] or 9999)
        if vs <= vol <= ve and ys <= year <= ye:
            matching.append(c)

    return matching[0]["jurisdiction"] if len(matching) == 1 else "UNSUPPORTED"
```

**Rationale.** For a homograph abbreviation, the volume and year ranges historically covered by its candidate reporters usually do not overlap. Whichever range the citation's own volume and year fall into identifies the reporter. This is a deterministic, reproducible, auditable determination that uses only information internal to the citation.

**Rejected alternatives and their defects:**

*Alternative A: read keywords from surrounding text.* For example, `Canada` in the window means Canada, `Insurance` means an insurance-law reporter. This is the same methodology as the S2 signal that has been shown to fail. S2 failed precisely because the keyword was present and the conclusion wrong; a different set of keywords does not change the unreliability of the method itself. Violates constraint three.

*Alternative B: give a presumed default when there is no signal.* For example, when an abbreviation cannot be resolved, default to the most frequent jurisdiction and only mark the field `inferred_default`. This fills a gap in verification with generation, violating constraint four. Adding a label does not change the fact that it is a guess.

**Supplementary rule.** The volume of `shape_bracket` is optional. If a citation has no volume, disambiguation can rely only on the year range, and year spans are usually much wider than volume spans, so the risk of misjudgement is markedly higher. In this case, even with a unique match, the output must be marked `vol_missing=true` as a trace.

**Implementation note (v1.6).** The code block's "no volume, no determination" contradicts this supplementary rule's "year alone", and the implementation takes neither (PROBLEMS #52): not printing a volume is itself a printed fact — a volume range containing 0 in the table means the series may print no volume, one starting at 1 means the volume is always printed; rows with no volume are compared as vol=0 and marked `vol_missing`; with no year, the year dimension does not take part and only the volume counts. The same jurisdiction may have several range rows; a determination is made when the matching **jurisdiction** is unique. The grade is the weakest among the matching table rows, capped at inferred (the hard-coded inferred of §8.5 would raise table rows that are estimated). A new column `disambiguated_by` records the route of the determination. Pending review.

### 8.7 Step 5: case-name candidate cutting and cleaning

**Why it is in the classification layer.** It is a pure text operation that can be done looking only at the row. The old pipeline mixed it into two highly repetitive aggregation scripts of over four hundred lines each [verified], the main source of duplicated code, which also made the merge layer take on a job that did not belong to it.

**Implementation note (v1.6).** If after v. a semicolon starts another stretch of text beginning with a letter, the row's citation belongs to that stretch and does not borrow the case name where v. sits (`name_belongs_to_later_segment`, PROBLEMS #57); the exception is when what follows the semicolon is the case's appeal history (aff'd / rev'd / var'd / leave to appeal). **Case names without v. have been added** (PROBLEMS #58, 2026-09-11, a supplementary rule to §8.7): closed-set markers are recognized only at the **start/end** of "the segment the row's citation sits in" (from the nearest `;`/`:`/line break before it) — prefixes `Reference re` / `Re` / `In re` / `Ex parte`, the suffix `(Re)`, and the Quebec anonymized names `Droit de la famille — N` / `LSJPA — N`; a marker must be followed immediately by a capitalized word (prose does not make a name); **not enabled when the segment contains v.**, which still goes the v. route above. The marker segment's edges are found with a word-walking test of "contains a capital letter / contains no letters / is a connective", without enumerating case names in a word list. Measured: nameless→named 7,660 rows, named→nameless 0 rows. Pending review.

**Implementation note (v1.6, continued).** When a candidate swallows a whole sentence of prose on its left, the prose is cut off (PROBLEMS #61): it triggers when there are at least 3 lowercase prose words on the left; the cut point is the last such word, and what lies between it and v. must be a word sequence that "looks like a case name", otherwise back off, and if nothing qualifies, leave it unchanged; **stripping connectives between the cut point and the case name is case-sensitive** — lowercase words may always be stripped, while capitalized words are stripped only if they are prepositions/signals that cannot start a case name (In / At / By / See …), and articles and abbreviations (The / La / Le / St. / Saint / Inc. / A / Re) are not stripped (the first version was case-insensitive and stripped the start of case names like `The King v. …` and `St. Lawrence Cement …`); if the result does not look like a case name, or starts with a company suffix, or the cut point is immediately preceded by a French article/preposition, in all three cases it is **returned unchanged** (not judged nameless). The cut-point word list is narrower than §8.7's `_CONNECTOR` — in/to/by/on/at are cut points. Measured: first version named→renamed 17,742 rows, nameless→named 307 rows, named→nameless 0 rows; after the correction, another 406 rows changed relative to the first version, and **named→nameless is still 0**. Pending review.

**Cutting logic** (the actual behaviour of the old pipeline [verified]):

```python
V_RE = re.compile(r"\bv\.?(?=\s)")

pre = row["preceding_text"]
last = None
for m in V_RE.finditer(pre):
    last = m

if last is None:
    append_name_reason(row, "no_v_structure")
    row["candidate_case_name"] = ""
else:
    sep = max(pre.rfind(";", 0, last.start()),
              pre.rfind(":", 0, last.start()),
              pre.rfind("\n", 0, last.start()))
    if sep == -1:
        append_name_reason(row, "no_separator_before_v")
        row["candidate_case_name"] = ""
    else:
        cand = pre[sep + 1:].strip().rstrip(",").strip()
        cleaned, reject = admit_candidate(cand)
        if reject:
            append_name_reason(row, reject)
            row["candidate_case_name"] = ""
        else:
            row["candidate_case_name"] = cleaned
```

Three details that must be implemented exactly:

1. Take the **last** ` v.`, not the first. Several cases may be mentioned in the window; the one nearest the citation is the case this citation belongs to.
2. The candidate fragment runs from the separator to the **end** of `preceding_text`, not up to ` v.`. Because the end of `preceding_text` abuts the citation string, this stretch is exactly the full case name (including both parties). Cutting at ` v.` would lose the respondent side.
3. When no separator is found, **give up the candidate**; do not fall back to taking from position 0. Starting from 0 would make any preceding text in the window part of the case name.

**Cleaning logic** (as in the old pipeline [verified]):

```python
_ADMIT_LEAD_CHARS = set("[(«\"'‘“….")
_ADMIT_VERB_RE = re.compile(
    r"(?:citing|see also|see|per|applied|considered|referred to|"
    r"following|approving|distinguished|overruled|cf)\s+", re.IGNORECASE)
_ADMIT_IN_RE = re.compile(r"in\s+(?!re\s)", re.IGNORECASE)

def admit_candidate(cand):
    s = cand
    while True:                      # strip repeatedly until stable
        before = s
        i = 0
        while i < len(s) and (s[i].isspace() or s[i] in _ADMIT_LEAD_CHARS):
            i += 1
        s = s[i:]
        m = _ADMIT_VERB_RE.match(s)
        if m:
            s = s[m.end():]
        m = _ADMIT_IN_RE.match(s)
        if m:
            s = s[m.end():]
        if s == before:
            break
    s = re.sub(r"[,;:.\s]+$", "", s)

    if len(s) > 120:                              return None, "too_long"
    if re.search(r"\[(?:18|19|20)\d{2}\]", s):    return None, "has_bracketed_year"
    if sum(1 for _ in V_RE.finditer(s)) >= 2:     return None, "multi_v"
    if not s:                                     return None, "empty_after_clean"
    return s, None
```

Note the negative lookahead in `_ADMIT_IN_RE`: it strips an introductory `in ` but keeps `in re` (the latter is part of a case name).

All four rejection reasons are recorded; nothing is discarded silently.

### 8.8 The two kinds of rejection reason must be kept apart

The classification layer produces two kinds of rejection that are entirely different in nature; they are carried by two separate fields and must not be merged into one.

**`rejected_reason` (row level)**: this row is not a valid foreign case citation at all.

| Value | Meaning |
|---|---|
| `federal_statute` | A federal statute, not a case |
| `party_initials` | A false positive caused by party initials |
| `date_form` | A false positive caused by a date having the same shape as "vol abbreviation page" (§8.4 v1.7, PROBLEMS #85) |
| `unrecognized_series_prefix` | The prefix is not in the series table; a structural-skeleton false positive |
| `table_conflict` | Hits both tables; which it belongs to awaits a human decision |

**`name_rejected_reason` (case-name level)**: this row is a valid citation, but no usable case name can be cut from the window.

| Value | Meaning |
|---|---|
| `no_v_structure` | No ` v.` in the window |
| `no_separator_before_v` | No separator found, so the start of the case name cannot be determined |
| `too_long` | Over 120 characters after cleaning |
| `has_bracketed_year` | Still contains a bracketed year after cleaning, so too much was cut |
| `multi_v` | Contains two or more ` v.`, so it cut into another case |
| `empty_after_clean` | Empty after cleaning |

**Why they must be kept apart.** The merge layer's two groups of calculation use different filters: citation counts and distinct-judgment counts must exclude row-level false positives but **must not** exclude rows that merely yield no case name (those citations really exist; this occurrence just appeared in a position unsuitable for cutting a name); case-name voting excludes both kinds. If one field were shared, rows yielding no case name would be excluded from the counts along with the others, and citation counts would be systematically under-counted.

Each field can accumulate several reasons, joined with `|`.

### 8.9 Classification-layer output

All extraction-layer fields, plus:

```
citation_kind, abbreviation, jurisdiction, jurisdiction_confidence,
lookup_mode, vol_missing, series_prefix,
candidate_case_name, rejected_reason, name_rejected_reason
```

---

## 9. The merge layer

Cross-row statistics. **Only counting and voting; no judgements and no table lookups.**

### 9.1 The merge key

```python
def build_merge_key(row) -> str:
    year   = row.get("year_start") or ""
    vol    = row.get("vol") or ""
    abbr   = nk(row.get("abbreviation") or "")
    series = (row.get("series") or "").lower()
    page   = row.get("page") or ""
    return f"{year}|{vol}|{abbr}|{series}|{page}"
```

**Built from structured fields, not by flattening the whole raw string character by character.**

Applying `nk()` to the whole string makes errors in both directions at once: what should merge does not (`[1978] 1 AC 728` and `[1978] AC 728` differ only by an omittable volume, and after normalizing the whole string they are still two keys), and what should not be erased is erased (structural information such as the difference between bracketed and parenthesized years and the positions of commas is all lost).

Built from structured fields, differences in writing (`A.C.` vs `AC`) are absorbed by `nk()`, while structural information stays in its own position.

When the volume is missing, **leave an empty slot rather than omitting the field**, so that `1978||ac||728` and `1978|1|ac||728` remain two different keys. Whether the two should be treated as the same citation (that is, whether to match loosely when the volume is missing) is an undecided design question, recorded in PROBLEMS.md; this version uses strict matching and makes no speculative merges.

**`canonical_string`** takes the most frequent `raw_string` in the group, for display only.

**`merge_key` is the pipeline's internal group identifier and has no role in joining decision tables** (constraint seven). It may change as the merge logic is adjusted. Joining decision tables is done through the printed citation string, see 10.2.

**Implementation note (v1.6).** A recognized series prefix is merged into the abbreviation slot (`|6|lr.qb||1` and `|6|qr.qb||1` belong to England and Quebec respectively, and the prefix-less `|6|qb||1` forms a separate key); otherwise, once a prefix is recognized, two judgments in two reporters would share a key (PROBLEMS #53). Keys of rows without a prefix are unchanged. Pending review.

### 9.2 Counting

```python
# exclude only row-level false positives, not rows that merely yield no case name
counted = [r for r in group if not r["rejected_reason"]]
occurrence_count = len(counted)
distinct_decisions_count = len({r["source_decision_citation"] for r in counted})
```

Rows rejected at row level stay in the table (constraint five); they are just not counted in frequencies.

**Implementation note (v1.6).** Self-citation rows (`self_citation=true`, #54) likewise count towards neither occurrence nor dd but still cast case-name votes; `merged.csv` also gets `self_citation_of` (which judgment's own citation this key is) and `self_case_name` (the case name printed in its header), so the adjudication layer can recognize identity anchors and remove the judgment itself. Pending review.

**`distinct_decisions_count` must be the cardinality of a union.**

The old pipeline's implementation was `e["dd"] = max(e["dd"], dist)` [verified], taking the maximum over variants. This misses judgments that appear in only one of the variants. Another wrong approach is to sum, which double-counts a judgment that cites several variants at once. Only the union is correct.

Judgment ids carry the court prefix, so they are unique by construction when taking the union across courts.

### 9.3 Modal case-name voting

```python
valid = [r for r in group
         if not r["rejected_reason"] and not r["name_rejected_reason"]]
if valid:
    cnt = Counter(r["candidate_case_name"] for r in valid)
    recent = {}
    for r in valid:
        n = r["candidate_case_name"]
        recent[n] = max(recent.get(n, 0), int(r["source_decision_year"] or 0))
    case_name_modal = max(cnt.items(), key=lambda kv: (kv[1], recent[kv[0]]))[0]
    case_name_agreement = round(cnt[case_name_modal] / len(valid), 2)
    variants_count = len(cnt)
else:
    case_name_modal, case_name_agreement, variants_count = "", 0.0, 0
```

The sort key is (number of occurrences, most recent year of occurrence): on a tie, take the more recent form, because the standard form of a case name evolves over time.

**Frequency voting across judgments solves two things at once**: ranking by importance (a case cited by more judgments is more important) and quality checking (low-frequency entries are often OCR errors and cannot form a meaningful mode either).

### 9.4 Quality columns do not filter

`case_name_agreement`, `variants_count`, `candidates_admitted` and `candidates_rejected` are all output as columns; **this layer filters no rows on them**.

The reason is a statistical trap: when the number of candidates is very low, `agreement` mathematically tends to 1.0 (with only 3 candidates, all identical, agreement is 100%); the number looks high but is no evidence at all. The old pipeline used `admitted >= 5` and `agreement >= 0.6` side by side as thresholds; the two conditions point in opposite directions and cancel each other out.

The right approach is to use these two indicators only as an ordering aid for manual review, and leave all keeping or dropping to the selection layer, whose criterion is `distinct_decisions_count`.

### 9.5 Traceability of folding

The merge layer produces two files.

Main table `merged.csv`:
```
merge_key, canonical_string, abbreviation, citation_kind,
jurisdiction, jurisdiction_confidence, case_name_modal,
occurrence_count, distinct_decisions_count,
case_name_agreement, variants_count,
candidates_admitted, candidates_rejected
```

Folding log `folded_log.csv`:
```
merge_key, raw_string, count, distinct_decisions_count
```

**Why the folding record is a separate file rather than an inline column.** One merge key may correspond to dozens of raw variants; storing them inline would make that column bigger than the main table itself. As a separate file the main table stays a manageable size, and it can be joined on `merge_key` when needed.

This file has three uses: the adjudication layer looks up member strings in it (see 10.2), locating folding errors when they are found, and answering "which forms did this key absorb".

**Implementation note (v1.6, PROBLEMS #42).** The merge key of §9.1 uses `nk(abbreviation)`, so `FC` and `F.C.` share a key and go into one group; but the two may get different `citation_kind`/`jurisdiction` values in the classification layer, and the specification does not define whose values `merged.csv` should give these single-valued fields within a group. **This implementation: take the mode over counted rows, and on a tie take the value from the row holding `canonical_string`** — deterministic, using only data within the group, adding no column. Measured, disagreement within groups is small (3 of SCC's 126,366 groups, 29 of ONCA's 79,603 groups), typically `2002 SCC 79` judged CA while `[2002] S.C.C. 79` is judged UNSUPPORTED after the #36 withdrawal. The number of disagreeing groups is reported in the manifest's `groups_with_internal_disagreement` counter, never silently. **The merge layer does not adjudicate** — per the opening statement of §9, "only counting and voting; no judgements", the real handling is the adjudication layer's job (§10). Pending review.

**Implementation note (v1.6).** The merge layer also produces a third file, `decision_ids.csv` (`merge_key, source_decision_citation`): when the adjudication layer merges parallel reporters within a court, it must take the union of judgment ids to get dd right; with numbers alone it could only sum, measured as inflating by 62–90% (PROBLEMS #46); the reason for a separate file is the same as for the folding log. Case-name voting was changed to two-level voting that first folds spelling variants by `nk()` (#44). `case_name_support` was added too (PROBLEMS #60): winning votes / `max(counted rows, votes)` — the denominator of §9.3's `case_name_agreement` is "rows that voted"; rows with no extractable case name cast a blank vote and are not in the denominator, so with only 1 of 199 rows yielding a name it still reports 1.0, and it cannot measure "how many of the judgments citing it stand behind this name". All three pending review.

---

## 10. The adjudication layer

The only layer that needs to "know which case this is first" to make its judgements, so it must come after merging.

### 10.1 Why this layer must exist

The old pipeline had no such layer; its tasks were scattered in two places: partly in the aggregation script and partly hard-coded in two rounds of `apply_origin` scripts, interleaved with selection [verified]. The consequence was the three patch lists. Those tasks cannot be done before merging, and forcing them meant propping them up with manually maintained lists.

With a separate adjudication layer, these tasks have the place they always belonged in and are no longer patches.

### 10.2 Case-level origin determination

**Lookups happen at the member-string level, not the merged-group level.**

```python
member_strings = folded_log[folded_log.merge_key == row.merge_key]["raw_string"]
hits = [h for h in (lookup_one(nk(s), case_origin, "normalized_key")
                    for s in member_strings) if h]

if not hits:
    row["case_origin"] = "UNDETERMINED"
    row["deciding_court"] = ""
elif len({h["case_origin"] for h in hits}) == 1:
    row["case_origin"] = hits[0]["case_origin"]
    row["deciding_court"] = hits[0]["deciding_court"]
else:
    row["case_origin"] = "CONFLICT"
    row["deciding_court"] = ""
    append_reason(row, "case_origin_conflict")
```

This design has three consequences, each intended.

**1. Splitting does not affect lookups.** Each record produced by splitting carries its own share of member strings and is looked up on its own, naturally getting its own place of origin. If the merged group were the key, the records from a split would share one key and return one answer, while the very reason for splitting is that they are different cases that may have different places of origin. A group-keyed scheme fails exactly where it is most needed.

**2. Pipeline changes do not invalidate manual verification.** The key is the printed citation string, unaffected by however the merge logic changes (constraint seven).

**3. `CONFLICT` is a useful signal, not an anomaly.** If two citation strings in the same merged group were found by manual checking to have different places of origin, the merge layer has merged two different cases. This lets the manually filled decision table serve in turn as an independent check on the merge layer: when the machine's result and the human's check disagree, it is exposed actively instead of one being picked silently. A group-keyed scheme looks up each group once and never produces this contradiction, so it lacks this ability.

**When not in the table, it must be marked `UNDETERMINED`; it must not default to the value of `jurisdiction`.** Defaulting to equality is exactly the same error by which the old pipeline systematically mislabelled Canadian JCPC cases as English. The only reason the concept of `case_origin` exists is that it is not always equal to `jurisdiction`. Filling in a value that looks determined makes the fact "this cell has not been judged yet" disappear from the data.

**Implementation note (R2–R4, 2026-09-11 to 09-14).** The algorithm block above is the original design, with a single lookup source (`case_origin.csv`). In implementation, case-level origin determination was extended into a **three-tier priority waterfall**, each tier leaving its own trace:

1. **`case_record` (highest, direct evidence on the member string)** — `case_origin.csv` (204 rows, matched against CanLII's Privy Council database) and `case_origin_manual.csv` (R4 Stage 3, 33 rows, verified case by case by a research agent: a row enters only when four proofs are complete — printed citation ↔ judgment correspondence, deciding court, court/jurisdiction appealed from, and report year ≠ judgment year not conflated — `status=verified_research_agent`) are merged into one index; when the two tables give different countries for the same citation string → a member-local `CONFLICT`, in the conservative direction, with neither picked.
2. **`court_scope_rule` (R2-4)** — `court_or_reporter_scope.csv`: exclusive place-of-origin rules for courts/identifiers, applying only when the row is an **accepted neutral parse** (`citation_kind ∈ {neutral, identifier}`, i.e. the code is confirmed by the court-code table; "a year and no volume" by itself is not proof of the citation kind), the code is in the table with a unique match, and the date falls within the rule's `valid_from`–`valid_to` window. Only rows whose `verification_status` starts with `verified` take part; estimated / name-inference rows may never be upgraded to place-of-origin facts.
3. **`reporter_origin_scope` (R3)** — `reporter_origin_scope.csv`: exclusive reporter-scope rules, applying only when the row has `citation_kind=reporter`; it does its own lookup and does not read the classification layer's `jurisdiction` (constraint four: `jurisdiction` and "exclusive place of origin" are evidence of different strength and must not borrow from each other); a window match disambiguates, and overlap between countries → `UNDETERMINED` with an audit column recorded. Two grades of exclusivity are distinguished: `exclusive_statute` (the scope of publication is set by legal/constitutional text) and `exclusive_publisher` (only the publisher's editorial policy, which must come with a record of searching for counter-examples).

None of the three hits → `UNDETERMINED`; cross-jurisdictional courts such as UKPC/JCPC are in no rule table → `UNDETERMINED` (constraint seven: `FOREIGN` comes only from positive exclusive rules, never from "not in the Canadian exception table"). Each determination landed on a row also carries `member_origin_basis` (which tier it went through), `member_origin_evidence_ids` and `deciding_court`, for audit and traceback row by row. R4 Stage 4 review (`implementation/r4_verify_stage4.py`): identity (group set / signature / dd) unchanged relative to the R3 baseline; the batch added determinations for 33 groups (`DOMESTIC_CA` +17, `FOREIGN` +16), 33/33 traceable to the manual table, 0 untraceable, and the net increase in `FOREIGN` matches the number derived from the batch. Pending review, and §5.4 needs its coverage description updated at the same time.

### 10.3 Merging parallel reporters

The same case is often reported in several reporters. The criteria for the same case:

- `nk(case_name_modal)` equal
- `abs(year_a - year_b) <= 1`

**Years are matched by proximity rather than equality**, because publication years in different reporters often differ by a year.

Identifying a retroactive neutral citation (`[1868] UKHL 1`) with a printed reporter form (`(1868), L.R. 3 H.L. 330`) goes through the same logic and needs no extra mechanism. Case name plus year is the standard way to decide the same case, and it applies equally to merging between reporters and merging between neutral citations and reporters.

Earlier discussions included a scheme of "co-occurrence marking" for neutral citations (judging at the extraction stage whether both forms appear in the same sentence). That scheme has been rejected: it requires defining the boundary of "the same sentence" (how big a window, how to count across paragraphs), a problem created entirely by the design itself. Letting neutral citations be extracted normally as separate rows and doing the identification in the adjudication layer makes the problem disappear structurally.

Merged groups are identified by `merged_group_id`, and `is_primary` marks the row that represents the group (the one with the highest `occurrence_count`).

**Implementation note (v1.6).** A gate on merging by name using case-name support (the `case_name_support` added to §9.3) was tried and **measured net negative; not enabled** (PROBLEMS #60): opening the gate affected only 32 groups, and every one of those 32 was parallel reporters of the same case being split apart (`R. v. Kienapple` 273→256+18, `R. v. Lifchus` 166→99+68, `Suresh` 66→63+12 …), and it added 8 cases of "one printed string landing in two groups" while removing 0. Low support comes from "the case is cited mainly by neutral citation without printing its name", not from a wrong name. The `case_name_support` column is still output for human review. This deviation needs human review.

### 10.4 Splitting same-name different cases

```python
abbrs = {m["abbreviation"] for m in members}
years = [int(m["year_start"]) for m in members if m["year_start"]]
if len(abbrs) == len(members) and years and (max(years) - min(years)) > 1:
    mark_split(members)
```

The typical scenario is several Attorney-General References with the same name: the same name, a wide span of years, printed in different reporters.

**Implementation note (v1.8, PROBLEMS #88: the three-tier folding test for mixed keys).** The typo-folding rule (`typo_number`/`typo_year` of `same_decision_kind`) looked only at how lopsided the numbers were, not at whether the citation itself had evidence of being a real judgment — the only brake was "the key is a citation printed by a corpus judgment for itself" (`own[k]`), but that flag is produced only in the round of the judgment's own court and is blind across courts (the first attribution in PROBLEMS #88/#89). **Review found a deeper problem**: one printed string (such as `2002 SCC 3`) can carry two identities at once — in the ONCA round its 10 counted mentions were mixed: 4 printed `Housen v. Nikolaisen` (a real typo), 2 printed `Chieu v. Canada` (a real citation), 4 nameless. A "registry"-type scheme (restoring the cross-court visibility of `own[k]`) is no solution for such keys — letting all 10 through is wrong (4 right, 2 wrong), and blocking all is wrong too (2 right, 4 wrong).

The approach that actually answers to the evidence is to check mention-level case-name evidence at the moment of folding, in three tiers (`mixed_identity()` in `decide.py`, whose input is the new merge-layer column `name_classes` — a purely informational column of `merged.csv`, the distribution of case-name classes printed by the key's counted mentions, such as `housen:4|chieu:2`):

```python
hit_big = big_name in k_classes       # do the mentions print the folding target's name
hit_other = any(n != big_name for n in k_classes)  # do they print another name
# hit_big and not hit_other  → fold    a pure typo, merge (current behaviour is correct)
# not hit_big                → fold    nameless / no same name, left alone this phase (the territory of mechanism A and #89)
# hit_big and hit_other      → holdout one printed string with two identities, do not merge
```

No count threshold is set — one counter-example counts as a counter-example (better to miss than to be wrong, the principle of "verification over generation"). A held-out key must also do two things, or a new regression appears: ① **suppress its case name** (`name_rejected_reason=mixed_identity`) — not erasing the name would create a rival group with the same name and year as the target; ② **leave the identity-root contest** (removed from this bucket, each forming its own group) — doing ① without ② makes the bucket drop from the "single root, ride along" path into the "multiple roots, co-citation assignment" path, and parallel citations without an anchor in the real group (such as D.L.R. reporter citations) lose their right to ride along and are split into isolated groups. This is exactly the measured regression of the first scheme tried, "block on a registry hit": `211 D.L.R. (4th) 577` dropped from dd=602 to a singleton with dd=21. With ① and ② added, the same parallel citation stays in the group, dd=602→597.

Measured (on the same base as `data/run_20260916_85date`): 4 keys held out on the main line, the Housen group's dd 602→597 (the difference attributable key by key); a clean A/B on one global `candidates.csv` changing only the switch — 0 new keys, 0 vanished keys, counts changed for 28 existing keys, `kept` 17,379→17,377 (2 groups dropped out, 0 new). **On 2026-09-17 the user decided to make it on by default** (`--no-mixed-key-holdout` turns it off to reproduce the old behaviour).

### 10.5 Adjudicating splits of folds

The adjudication layer may overrule the merge layer's folding conclusions and split them apart, but **never edits the merge layer's output files**.

This is the engineering pattern of an immutable log: the merge layer's output is the historical record, and the adjudication layer's output is the current best judgement. This keeps the one-directional flow (constraint six) while giving downstream the ability to correct.

```python
if needs_split(row, folded_rows):
    for i, subset in enumerate(partition_members(folded_rows)):
        new_row = row.copy()
        new_row["merge_key"] = f"{row['merge_key']}#{i}"
        new_row["split_seq"] = i
        new_row["split_flag"] = True
        new_row["canonical_string"] = subset[0]["raw_string"]
```

Recomputing `merge_key` after a split is safe, because it no longer has any role in joining decision tables.

### 10.6 Cross-court merging

**Timing:** after SCC and ONCA have each run extraction, classification, merging and the adjudication layer's internal merging, one more cross-court merge is done, using the same logic as 10.3.

**Implementation note (v1.8).** The "two courts" of the time this section was written is now a parameter: the court list is controlled by `--courts` / the environment variable `PIPELINE_COURTS` (default `SCC,ONCA,BCCA`, see §1.3/§12); a per-court loop produces `merge_out/<COURT>/` and per-court step logs, and the cross-court round reads each court's `decided.csv` and writes `decide_out/cross_court/`. Adding a court needs no change to this section's logic, only corpus and table support.

After merging, `distinct_decisions_count` takes the union of both sides (judgment ids carry the court prefix, so they are unique by construction).

This ability exists only once the two twin scripts are combined into one and parameterized with `--court`. The old pipeline was two completely independent parallel chains and structurally could not merge across courts; the same foreign case cited several times by each of two courts was forever counted as two unrelated entries.

### 10.7 Adjudication-layer output

Merge-layer fields, plus:
```
case_origin, deciding_court, merged_group_id, is_primary,
split_flag, split_seq
```

**Implementation note (v1.6).** Also added: `court`, `key_occurrence_count` (the row's raw mention count at the merge layer, from which the group totals of every round are recomputed, #47) and `split_reason` (a combination of `span` / `decision` / `unanchored`); `decision_ids.csv` carries judgment ids row by row (`row_key = court|merge_key`). In implementation §10.4 was extended into two splits — chains with a year span > 1 are split with a ±1-year window (#48), and windows containing several different judgments are split by neutral citation, with reporter rows assigned by co-citation (#49) — all pending review.

**Implementation note (v1.6, continued).** Besides neutral citations, judgment identity also recognizes "the citation printed in the header of a corpus judgment itself" (#55): reporter anchors merge only on an identical key; the typo rule for neutral anchors must not merge away "another corpus judgment whose header prints the same case name". "Neutral citations" from before a corpus court began printing neutral citations are not identity anchors (#56). A group's dd union removes the identity root's own judgment id (#54). All pending review.

**Implementation note (v1.6, continued).** The cross-court round also adds `same_name_near_year_peers` (PROBLEMS #62): the group ids of **other groups** with the same name (equal after `nk()`) and primary-row years within ≤ 1, joined by semicolons. **Flagged only, not merged** — this band mixes genuinely different same-name judgments (an `R. v. John` every year) with two forms of the same judgment (never co-occurring in the same judgment, the zero-co-citation residue of #55), and the data has no signal to tell them apart. `kept` is decided only at the selection layer, so it is computed for **all** groups. Measured: 8,120 groups have peers (at most 21 peers), and all 225 pairs with both sides over the threshold are flagged. Pending review.

**Implementation note (v1.8, PROBLEMS #105: self-citations slipping through and `--own-citations`, 2026-10-03).** The self-citation removal of #54 compared only normalized strings, and three kinds slipped through in measurement: ① **zero padding** (`2003 BCCA 0443` and `2003 BCCA 443` have different keys, 281 singleton fake "cases"); ② **parallel citations in the header** (`[2003] 1 S.C.R. 39` printed in a judgment's header was claimed by nobody as its own); ③ **citing its own lower-court judgment** (the SCC citing `(1991), 3 O.R. (3d) 193`). **User decision**: ① and ② are typesetting/identification problems and do not count towards dd; ③ is a real procedural-history relation and **counts towards dd**. Implementation: the classification layer's self-citation comparison is now numeric equality (`_unpad`, zero-padding aware); `registry.py` produces `<run>/registry/decision_own_citations.csv` (`own_citation_entries`), which the adjudication layer reads with `--own-citations`, and `own_citation_self_ids()` (`decide.py`) removes the judgment's own ids from the group's dd union (statistics column `self_ids_removed_own_citation`). Full rerun `run_20261003_selfcite`: edges 493,463→493,164 (all −299 were self-citation edges), groups 237,091→236,809, **the number of dd≥5 groups unchanged (13,630)**; 165 pipeline assertions and the extraction regression pass. Direct tests `test_own_citation_rule`/`test_own_citations_loader` (`test_layers.py`). Pending review.

---

## 11. The selection layer

### 11.1 One threshold, on dd

```python
df["kept"] = df["distinct_decisions_count"] >= config["threshold_dd"]
```

**Why `distinct_decisions_count` and not `occurrence_count`.**

Citing the same case ten times in one judgment is very common, but it is still one legal act by one judge. `occurrence_count` is inflated by this, treating "one judge cited it ten times" and "ten judges cited it once each" as equally important.

`distinct_decisions_count` also resists OCR noise by construction: a noise string almost always appears in a single judgment, `dd = 1`.

**The threshold must come after the last merge.** If it were at the merge layer, this would happen: a case has 2 under `A.C.` and 2 under `All E.R.`, both groups miss the threshold and are cut, while its real citation count is 4. Only after the adjudication layer's parallel-reporter and cross-court merging is a case's count complete.

### 11.2 Parameterizing the threshold

A YAML configuration file, not command-line arguments:

```yaml
default:
  threshold_dd: 5
loose:
  threshold_dd: 2
strict:
  threshold_dd: 10
```

Reasons: it is easy to run several comparisons side by side, easy to add parameters later without changing the command-line interface, and the configuration itself can be archived with the output for reproducibility.

**The threshold value is a product decision, not a data decision.** It depends on how many candidates the product wants and where the quality line is drawn, so it is not hard-coded.

**`threshold_dd: 5` currently has no basis (v1.2 correction).** The value was tuned for the "foreign landmark case lookup" scenario; after the scope was widened to all citations it lost its basis in the context of all cases. This version **does not change the value** (resetting it requires full data); until it is reset from the `dd` distribution of the first full run, it is only a placeholder and must not be quoted as a calibrated parameter.

**No high-frequency bypass.** The old pipeline had a parallel path (`occ>=20` and `dd>=10` and `admitted>=10` and `agreement>=0.25`) to fish out important cases missed by the normal path [verified]; its four parameters had no source. Once the adjudication layer merges correctly, the `dd` of genuinely important cases reaches the threshold naturally, and the bypass loses its reason to exist.

### 11.3 No rows deleted

Rows below the threshold stay in the table, only marked `kept=false`. The product reads only `kept=true`; the full table is always kept.

So it can always answer "why is this case not in the results". The old pipeline needed a separate exclusion list to answer that question; here the need is removed by the mechanism.

---

## 12. Execution order

```bash
# extraction (both courts in one run; batches written to disk with automatic resume, see 7.7)
python pipeline/extract.py                    # → data/extract_out/
#   optional: --corpus SCC runs a single corpus; --fixture-check acceptance gate; --merge redoes only the merge
#   note: the extraction output is **one merged file** data/extract_out/extracted.csv, not one per court
#   — every row's source_decision_citation carries the {COURT}_ prefix (see 7.3), so downstream filters
#   on that prefix to process by court; batch files are still stored in per-court directories.

# classification
python pipeline/classify.py --court SCC  --input data/extract_out/extracted.csv --output data/classify_out/SCC
python pipeline/classify.py --court ONCA --input data/extract_out/extracted.csv --output data/classify_out/ONCA

# merging
python pipeline/merge.py    --court SCC  --input data/classify_out/SCC/classified.csv  --output data/merge_out/SCC
python pipeline/merge.py    --court ONCA --input data/classify_out/ONCA/classified.csv --output data/merge_out/ONCA

# adjudication (within each court)
python pipeline/decide.py   --court SCC  --input data/merge_out/SCC/merged.csv  --folded-log data/merge_out/SCC/folded_log.csv  --decision-ids data/merge_out/SCC/decision_ids.csv  --output data/decide_out/SCC
python pipeline/decide.py   --court ONCA --input data/merge_out/ONCA/merged.csv --folded-log data/merge_out/ONCA/folded_log.csv --decision-ids data/merge_out/ONCA/decision_ids.csv --output data/decide_out/ONCA

# adjudication (across courts)
python pipeline/decide.py   --cross-court --inputs data/decide_out/SCC/decided.csv data/decide_out/ONCA/decided.csv --output data/decide_out/cross_court

# selection
python pipeline/select_layer.py   --input data/decide_out/cross_court/decided.csv --config select_config.yaml --profile default --output data/select_out

# coverage report (helps fill tables; can run at any time)
python pipeline/coverage_report.py --kind reporter --classified data/classify_out/SCC/classified.csv data/classify_out/ONCA/classified.csv --out data/coverage_out/reporter.csv
#   --kind neutral / --kind series likewise (the input now reads the classification output; reason in 12.1)

# regression (after changing any layer)
python pipeline/tests/run_regression.py --selftest     # extraction layer
python pipeline/tests/test_layers.py                   # layers 2–5: unit assertions + mini end-to-end chain
python pipeline/tests/test_layers.py --golden          # compare full output with the golden summary; --golden-write only for expected diffs
```

**Implementation note (v1.8, the current state of §12).** The code block above is the manual step-by-step command list as of v1.6, kept to describe each layer's interface. The actual entry point is **`pipeline/run_all.py`**: `--courts` (or the environment variable `PIPELINE_COURTS`, default `SCC,ONCA,BCCA`) drives a per-court loop, writing to `data/run_<date>_<label>/` (`classify_out`/`merge_out` in per-court directories, per-court step logs, `decide_out/cross_court/`, `edges/`), and `run_manifest.json` records the input fingerprint and switches (including `mixed_key_holdout`, on by default since #88). After a run finishes it can be archived with `tools/archive_run.py`: zipped to the archive drive, renamed into place only after the triple check of file count / byte count / `testzip()` CRC, refusing runs in `running` state, and appending to `archive_log.jsonl`. Identity registration of historical runs and rebuilding with one command are in `implementation/run_registry.csv` and `implementation/rebuild_run.py` (usage in `data/README.md`). The current baseline is `data/run_20261003_selfcite` (numbers in §1.4).

### 12.1 Coverage report

Input: the merge-layer output and the current decision tables; output: a list of abbreviations **not yet in the tables**, sorted by `distinct_decisions_count` descending.

Its role is to give table filling a clear priority: you always know "which one to fill next" instead of searching aimlessly. Rerun it after each batch to see how much coverage improved.

A report is produced for each of the three tables that need filling (reporter, neutral court code, series prefix).

**Implementation note (v1.6).** The input now reads the classification layer's `classified.csv` — `merged.csv` has no `leading_abbr` or `shape_name`, so the series and neutral reports cannot be produced from it; dd is taken directly as a union of per-row judgment ids, the same definition as §9.2. The reporter report distinguishes "not in the table" from "in the table but undeterminable" (mostly unresolved homographs, which need ranges added rather than new rows). The head of the series report is mostly structural-skeleton false positives (See, Section, Vol.); ranking high does not mean it should go into the table.

---

## 13. What must be done before implementation

### 13.1 Extraction-layer regression baseline (from v2, replacing the old "full A/B validation" plan)

The old version of this section planned "a full A/B comparison of six shapes against the old five shapes", which was dropped together with the old pipeline in `D:\mcgill`: the source of the old five shapes exists only in an abandoned directory, so a full A/B cannot be done, and a "full comparison" cannot answer "what was missed" — it can only answer "what each side has".

The current method is a **fixture regression baseline**, in `pipeline/tests/`, run after every regex change:

- `fixtures.py`: six fixtures, text taken verbatim from `corpus/SCC.parquet` (snapshot of 2026-08-30), covering three typesetting environments plus two negative controls — A a 19th-century footnote block (1877–1899), B a mid-20th-century footnote block (1930–1940), C a 1960s footnote block of parallel citations (with `D.L.R. (2d)`), D a Cases Cited block from a post-1980 judgment header, E a pure prose reasoning passage (negative control), F a mixed passage of statutes and bibliography (negative control). `run_regression.py --verify` rereads the parquet by row and checks the slices match verbatim.
- `truth.py`: the ground-truth table, with printed citation strings enumerated one by one by a person (68 entries at present). **Marked [unverified] as a whole** — until the ground-truth table has been reviewed by a person, none of the recall numbers below may be stated as verified.
- `run_regression.py`: runs each fixture with v1 (the frozen copy `shapes_v1_frozen.py`) and with v2, producing each one's hit count, a list of misses against the ground truth, and the false positives on the negative controls one by one; `--selftest` pins synthetic cases (the spec §7.1 examples, the `12n` truncation, the deduplication ordering, tie-breaking on equal spans, the `_SEP` comma probe — after the v1.3 slot correction that class of false positive has been removed at the extraction layer, and the probe is kept as a regression sentinel that should print nothing) and asserts that `normalize.dedup_overlapping` matches the deduplication definition exactly and that kept∪superseded = all raw hits (the shipped code does not fork from the test implementation, and deduplication deletes no rows); `--throughput` measures single-core throughput over the full corpus.
- `corpus_counts.py`: the only script that produces corpus-level diagnostic counts (the pattern dictionary records each definition verbatim; PATTERN_ASSERTIONS pins positive and negative examples for every measurement regex — a measurement regex must itself be tested first; the S.C.R. family is broken down by printed form with hard identity assertions). Every corpus-level number quoted in the specification and PROBLEMS must be replayable by it (constraint nine) — the one-off counts of v1.2 and earlier were never saved, and this script and `prose_sample.py` pay off that debt. It also offers `--dedup` (v1/v2 extraction + deduplication over the full corpus, rows per shape) and `--prose-sample` (the anchor baseline on the frozen prose sample, PROBLEMS #16).
- `prose_sample.py`: the frozen prose anchor sample (stratified by era × corpus, seed=20260830; the selected row numbers and character ranges are stored, bound to the SHA-256 of the 2026-08-30 snapshot; the ONCA corpus measured covers only 1998–2026, so the 1877–1967 and 1968–1995 strata have no candidates in ONCA, and 200/300 stratum slots are actually filled). Construction correction (v1.3): footnote lines became a hard boundary — the old version "skipped footnote lines but still extended the window span", and measurement showed 59/200 slices over budget, the largest 37,419 characters, with 94% of hits crowded into footnote-dense slices; the old sample (751,262 characters) was voided; after the correction it is 334,204 characters with every slice within budget. Entries must not be edited by hand; if the corpus changes, the whole sample is voided and redrawn.
- `shapes_v1_frozen.py`: the frozen copy of v1, for regression comparison only, never modified.

**Baseline results of 2026-09-05** (the ground truth is [unverified], so the recall numbers below are [unverified]; the negative-control false positives are [verified], because they do not depend on the ground-truth table):

| Fixture | Ground-truth entries | v1 ground-truth hits / misses / extra false positives | v2 ground-truth hits / misses / extra false positives | v2 misses |
|---|---|---|---|---|
| A 19th-century footnote block | 20 | 1 / 19 / 0 | 18 / 2 / 0 | `24 (U.C.) C.P. 275` (the non-ordinal parenthetical gap), `Swab. 96` (a nominate with no volume, structurally covered by neither v1 nor v2) |
| B mid-century footnote block | 15 | 15 / 0 / 0 | 15 / 0 / 0 | — |
| C 1960s parallel citations | 27 | 13 / 14 / 0 | 27 / 0 / 0 | — |
| D Cases Cited block | 6 | 6 / 0 / 0 | 6 / 0 / 0 | — |
| E prose (negative control) | 0 | 0 / 0 / 0 | 0 / 0 / 0 | — |
| F statutes and bibliography (negative control) | 0 | 0 / 0 / 6 | 0 / 0 / 6 | — |

Column definitions (the "kept/missed" columns of the v1.2 table did not distinguish ground-truth hits from false positives; v1.3 split them into three columns): ground-truth hits = rows after deduplication that overlap the ground truth; misses = ground-truth entries not covered; extra false positives = hits kept after deduplication outside the ground truth. The three columns are mutually exclusive; negative-control rows have empty ground truth, so all hits count as extra false positives. In the v1.2 era, row D for v2 was 6/0/1 (`Unemployment Insurance Act, 1971, S.C. 1970` caught by leading_abbr) — that false positive was removed at the extraction layer by the v1.3 slot correction.

The negative-control false positives explained one by one [verified]: all 6 in F are journal volume-page strings (`(1988), 53 Alb. L. Rev. 95` and 6 kinds in all), matched by `shape_vol_page_year` (with its trailing `(year)`) — they are journal citations, not case citations; v1 and v2 match them alike, which is the expected behaviour of this layer, "by structural shape, no semantic judgement", and the classification layer removes non-case citations (8.4). In the v1.2 era D had 1 more false positive (`Unemployment Insurance Act, 1971, S.C. 1970`: the comma tolerance of `_SEP` let a statute line be matched by `shape_leading_abbr`) — removed at the extraction layer by the v1.3 slot correction (see 7.1), with no need for the classification layer to take it over. **After deduplication**, `shape_vol_abbr_page` has 0 false positives on the two negative controls (its 6 raw hits are all sub-spans of the journal strings in F, covered by the longer `shape_vol_page_year` matches) — v1.2 once used this 0 as the initial value of a relative anchor for the threshold; v1.3 abolished that, and the anchor is now produced by measurement on the frozen prose sample (see PROBLEMS #16).

**Prose anchor baseline** (2026-09-06, `corpus_counts.py --prose-sample`; after the sample construction was corrected and regenerated): on the frozen sample of 334,204 characters (200/300 stratum slots; after footnote lines became a hard boundary every slice falls within budget — the old sample of 751,262 characters was voided because footnote citations had crept in), the current v2 seven shapes after deduplication hit 83 entries (3 of them real citations revived by v1.4 fixes 1/2: `663 P.2d 904`, `[1989] 1 S.C.R. xv`, `[1970] S.C.R. viii`); an agent's first check classified 6 false positives — 4 "number-capitalized word-number" prose structures (`30 For 6`, `12 Article 8`, `20 On February 26`, `6 Subsection 27`), 1 journal string (`(1996), 22 Rutgers Computer & Tech. L. J. 479`) and 1 court-division string (`Ct.App. 1 Dist. 1983`, provisionally pending classification) — and the other 77 are real citations inline in the text [classification pending human review; until then the anchor counts as 6]. Swallowing-type false positives on the frozen sample dropped from 79 on the old sample to 0; the overall false-positive rate is 17.9 per million characters (on the old sample's definition it was 123.8, of which the 79 leading-type entries have been removed by the slot correction).

**Throughput** (single core, `--throughput`, 2026-09-05): the full SCC corpus of 429,822,155 text characters (10,829 judgments) took 68.3 s with the v1 regexes (6.3 MB/s) and 93.9 s with v2 (4.58 MB/s); the denominator is the number of characters of non-empty `unofficial_text_en`, not file bytes; a single-process, single-core pure-Python loop with pyarrow `iter_batches(500)` column projection. v2 raw hits 625,532 (v1.5) (including sub-span overlaps between shapes, before deduplication; historical values: v1.2 shapes 660,766, v1.3 shapes 611,238, v1.4 fix 1 614,488 / fix 2 617,032 / fix 3 briefly 619,530 before rollback, see PROBLEMS #18–#27) against v1's 227,041; the increase comes mainly from the new shapes and hits inside parallel citation strings. **Rows after deduplication** (corrected on 2026-09-07 by checking two instruments digit by digit: the first full run of `extract.py` and `corpus_counts.py --dedup` rerun the same day, every number of the two routes identical digit by digit; deduplication definition = §7.4 span descending + no rows deleted, separate files): SCC v1 227,041→226,656, v2 625,532→374,873; ONCA v1 66,825→66,813, v2 372,933→207,535; both corpora together v1 293,469 rows, **v2 582,408 rows** (after the four gap fixes of v1.5; v1.4 was 578,753, an increase of 3,655 — French no / reporters with apostrophes / non-ordinal parentheticals / single-character Roman pages, see PROBLEMS #11/#28/#29/#30; three-gate acceptance: full kept diff with **0 breakage**, frozen prose sample 83→83 with zero additions, zero regression in the fixture exact tier) (about 42% of v2's 998,465 raw hits are overlaps between shapes, and all 416,057 losers go into `extracted_superseded.csv`, see §7.4; in v1.4 it was 992,641 / 413,888). By shape (after deduplication, v1.5, SCC v2): bracket 168,312, vol_abbr_page 72,200, year_vol_page 65,407, neutral_bare 54,700, leading_abbr 9,827, vol_page_year 4,367, nominate 60; ONCA v2: neutral_bare 92,542, bracket 49,734, year_vol_page 34,937, vol_abbr_page 29,012, leading_abbr 1,070, vol_page_year 238, nominate 2 — each block sums digit by digit to exactly the kept total (the per-shape blocks recorded earlier in this table did not sum correctly, a transcription of an intermediate state before freezing, and have been replaced as a whole). Historical comparison: v1.2 shapes leading_abbr 118,832 / neutral_bare 52,092 (the step-by-step changes are in PROBLEMS #18–#27). **First full extraction** (2026-09-07, `extract.py`, §7.3 schema / §7.4 two files / §7.7 batches with resume): the fixture acceptance gate's exact tier A18/B15/C27/D6 equal fixture by fixture; batches 22+49; manifest (snapshot SHA-256, git HEAD, parameters, row counts) in `extracted/manifest.json`; single-core time SCC 53.7s, ONCA 47.5s (including row construction and writing to disk; machine-dependent, not a throughput baseline).

**Corpus-level diagnostic counts** (snapshot = 2026-08-30, corpus = SCC, produced on 2026-09-05 by `pipeline/tests/corpus_counts.py`, by occurrence): `(2d)` 13,669 times, `(3d)` 16,994, `(N.S.)` 1,020, `(Mass.)` 75, `(Q. B.)` 5, `H. of L.` 17, `R. de J.` 93, `C. de D.` 196, `U, S. R.` 2, `C.B., N.S.` 13 (for the two corpora SCC+ONCA together, in order: 19,663 / 50,999 / 1,183 / 75 / 6 / 17 / 93 / 197 / 2 / 13). Every judgment's header prints its own citation: SCC 10,829/10,829 judgments and ONCA 23,953/23,953 judgments (all judgments with non-empty text in each) hit their own normalized `citation_en` within the first 3,000 characters (definition: `nk(citation_en)` ∈ `nk(first 3,000 characters)`; 2026-09-05, the script is replayable; spot-check sample head=2, full=2 times). Also measured: the years of `document_date_en` in the ONCA corpus cover 1998–2026 (24,089 rows, of which 136 have empty text, and those 136 also have empty dates; the 23,953 rows with text all have dates; SCC has the same structure: 62 rows with empty text and empty dates); the `v. X[n]` pattern (party names ≤4 words) covers 4,373/10,829 SCC judgments and `v. X(n)` (1–3-digit parenthetical) 410 judgments (see PROBLEMS #14).

Rule: any change to `shapes.py` must rerun `run_regression.py` (fixtures + selftest); if negative-control false positives or misses in A–D increase, the change goes back for discussion; if a new observation definition is needed, first register it in PROBLEMS.md, then touch the regex.

### 13.2 Hermes verification (external dependency)

Two things:
1. Whether the 9th and 10th editions of the McGill Guide contain a table mapping reporter abbreviations to jurisdictions; if so, which appendix, start and end pages, number of entries, field structure, whether it covers non-Canadian reporters, and whether it covers 19th-century nominate reporters
2. Which legitimate series prefixes the Law Reports family has

If the McGill Guide does not cover enough, external authoritative sources must be assessed, together with the effect of their licence terms on the project's IP cleanliness. This materially affects the project's long-term ownership and is not a purely technical question.

### 13.3 What can start immediately without being blocked (priorities reordered for the scope extension of 1.1)

1. Build `neutral_court_codes.csv` (court codes are publicly verifiable closed information). After the scope extension it is a **main table**: neutral citations are the largest single class of citation (corpus = SCC: the `YYYY SCC n` form measured at 31,926 occurrences, covering 1,708 judgments, produced by `corpus_counts.py`), and the set is closed and enumerable, so filling one table resolves a whole class of citations. After the v1.3 slot correction, rows of `shape_neutral_bare` after deduplication went 52,092 → 142,433 (two corpora); the first full run after the v1.4 freeze measured 147,277 rows (including the mixed-case CanLII/Carswell tokens relaxed under debt 2) — all these neutral citations await this table's determination, and with the table empty they are all `UNSUPPORTED` (the correct state of §13.4), which further raises this table's unit value.
2. Fill `reporter_jurisdiction.csv`, giving priority to the measured head of 5.1 (`S.C.R.`, `C.C.C.`, `O.R.`, `D.L.R.`, then W.W.R.).
3. Build `case_origin.csv` (the place a judgment was appealed from is a public fact that can be checked against the judgment)
4. The directory skeleton, `.gitignore`, `PROBLEMS.md`, the shared pure functions

**Implementation note (v1.6, 2026-09-10).** 1 is done: 326 rows, including 13 foreign codes each traced to a source and verified, with 36 more pending verification in `audit/findings/neutral_foreign_proposal.md`. 2 has been filled provisionally with 166 rows, **all `estimated / name_inference`; each must be verified before any product ships** (PROBLEMS #40). 3 is still empty. 4 is done.

### 13.4 An empty table is not a fault

Until `reporter_jurisdiction.csv` is filled, in the results of a pipeline run the great majority of rows will have `jurisdiction` `UNSUPPORTED` and the great majority will have `case_origin` `UNDETERMINED`.

**This is the correct state, not a broken pipeline.** It accurately reflects the fact that "we have not verified these yet". The old pipeline looked "well filled" because it filled these gaps with inferences, and a good share of those filled values were wrong.

---

## 14. Migrating from the old pipeline: what moves and what does not

### 14.1 What moves (only two files)

`SCC.parquet` and `ONCA.parquet`, copied to `corpus/`; after verifying the hashes match, the old files are kept for a while.

### 14.2 What does not move

**All derived output.** Extraction output, aggregation output, every generation of candidate table (v1 to v4), ranked tables, context tables, audit tables. All contain the truncation defect, and the new pipeline produces them again with one run.

**All old judgements.** Including the three-tier triage of 432 abbreviations, 38 inferred labels, 10 patch entries, 167 review records, the jurisdiction rulings of the 213-row candidate table, and the roughly 70 determinations hard-coded in the source of two scripts.

This item needs its reason stated, because it looks like wasting finished work. The problem with these judgements is not whether they are right but that they are **unreproducible and unsourced**: no prompt, model version or date was kept, so a rerun would not give the same result; there is no source column, so their basis cannot be traced. Moving them into the new `decisions/` would stamp unverified content as "settled" and then build everything downstream on top of it.

**There is only one permitted use**: an entry-by-entry comparison after the new tables are built. Entries where the two tables agree gain credibility, and entries where they disagree get priority for manual review. This use is safe because the old table produces no values here; it only points out where to look twice. The precondition is that it must be kept in an inert place like `_archive/`, not in `decisions/`. Once it is in there, the next person (including yourself a few months later) will use it as a source of facts.

**All old code.** The **logic** of a few pure functions (`nk`, the `_ABBR` sub-pattern, the cleaning logic of `admit_candidate`) is recorded and explained verbatim in this specification; reimplement it from the specification, with no need to import the old files.

**The exclusion list, variant statistics files, the year switch, parallel directories.** These are products of the problems, not assets.

---

## 15. Known unresolved problems (registered in sync in PROBLEMS.md)

**v1.8 correction: this table is a frozen snapshot from the v1.0–v1.7 period (entries 1–16) and is no longer a synchronized copy.** The live ledger is `PROBLEMS.md` at the repository root (currently 113 consecutively numbered entries: #64–#84 are the B1–B21 debt ledger of DEBT_LEDGER merged in, #85–#90 come from the BCCA/CITT experiment line, #91–#98 are records added during ledger repair, and #99–#105 and #113 are additions and fixes around 2026-10-03/04). The implementation notes corresponding to v1.8 have been written back into the body: #85 (§8.4), #88 (§10.4), #99/#104/#113 (§8.4 note), #105 (§10.7 note); for the other entries, go by the text of PROBLEMS.md. The table below is left unchanged so the judgements at the time the specification was finalized can be traced.

| # | Problem | Current handling |
|---|---|---|
| 1 | Split-year format (`1893-94`) is not supported; the year group takes only four plain digits | Explicitly unsupported; no processing code that never runs |
| 2 | Whether forms that omit the volume should count as the same citation (`[1978] 1 AC 728` and `[1978] AC 728`) | Treated as two keys under strict matching; no speculative merging |
| 3 | `shape_bracket` without a volume is disambiguated by year range alone, with a higher risk of misjudgement | A `vol_missing` trace; no stronger constraint |
| 4 | The false-positive rate of `shape_leading_abbr` has not been measured | Cannot be assessed before `series_prefix.csv` is filled; measured 1 on fixture D (a statute line matched across a comma separator), caught by the classification layer's `federal_statute` |
| 5 | The actual frequency of `table_conflict` (one token hitting both tables) is unknown | To be counted after the first full run |
| 6 | The actual frequency of `case_origin_conflict` is unknown | This indicator also measures merge quality; usable only once `case_origin.csv` reaches some size |
| 7 | Page-suffix footnote markers (`212n`): v1's real behaviour is **silent truncation to page=1** (backtracking gives back part of the page), neither refusing to match nor collateral damage | Resolved: v2 captures `page_suffix` explicitly and closes backtracking with `(?![A-Za-z0-9])` (2026-09-05, `run_regression.py --selftest` measured v1 page=1 → v2 page=12+suffix=n). The row is kept as a record of the behaviour |
| 8 | Whether judgment years need a lower bound, and what it should be | No default lower bound in this version; if needed, it must be passed explicitly and recorded in the run manifest |
| 9 | The nature of the 396 `UNCLEAR` candidate strings in the old pipeline's census is undetermined | Not migrated; re-assessed after the new pipeline re-extracts |
| 10 | `shape_vol_abbr_page` and `shape_leading_abbr` have no year component and cannot take part in homograph disambiguation or the year test for parallel reporters | A known limitation, no speculative filling; the output of these two shapes and how much is affected to be counted after the first full run |
| 11 | Non-ordinal parenthetical gap: parentheticals like `(Mass.)`, `(Q. B.)`, `(N.S.)` are not currently extracted (corpus = SCC, by occurrence, 2026-09-05: `(N.S.)` 1,020, `(Mass.)` 75, `(Q. B.)` 5; the two corpora together 1,183 / 75 / 6) | The candidate change (relaxing `_SERP`) was rejected, reason in 7.2 (5) 1; becomes an observation item of the diagnostic script |
| 12 | The within-segment separator set of `_ABBR` has no comma: forms like `U, S. R.` (corpus = SCC, 2 times) and `C.B., N.S.,` (13 times) are not extracted; `H. of L.` (17 times) is already covered incidentally by the lowercase-segment change (measured, see 7.2 (5) 2) | Relaxing was rejected (case-name swallowing, see 7.1). The diagnostic script should measure the **distribution** of which characters actually occur between capitalized segments in sample citation fragments and how often, not three isolated counts |
| 13 | Every SCC judgment's header block prints the judgment's own citation, which the extraction layer extracts in full, inflating row counts uniformly (measured: 10,829/10,829 judgments hit their own normalized citation within the first 3,000 characters, sample head=2/full=2 times) | Not deleted (constraint five); the classification layer flags `self_citation`: compare the row's `source_decision_citation` with the extracted string, a single-row operation. **Row counts of the first full run are not comparable before self-citations are subtracted**. (2026-09-11) Never implemented before; now landed per PROBLEMS #54 |
| 14 | SCC citations from 1877–1967 are almost all in `[n]` footnote lines, and the case names carry inline markers in the form `Brook v. Hook[11]`; the `preceding_text` case-name cutting of 8.7 is structurally impossible for this material (the 120 characters before the match point are the previous footnote) | The substitute anchor is the inline marker in the body. Measured (2026-09-05): the `v. X[n]` pattern covers 4,357/10,829 judgments, the `v. X(n)` pattern only 434 — the latter is the original book's page-numbered short form for repeated citations, whose page boundaries were lost in digitization, most likely unlinkable. **To be measured: the share of linkable patterns**, whose result decides whether `extract.py` produces a second output file (an inline-marker anchor table); under constraint six, if needed it must be produced together with the first full extraction. Registered only in this version, not implemented |
| 15 | Bucket design of the diagnostic script: it should be three classes × era, two-dimensional. The three classes are "footnote rows / body prose / Cases Cited blocks" | The v1 design considered only the first two; Cases Cited is a third set of typesetting rules in post-1980 judgment headers, different from the other two (fixture D is a sample of it) |
| 16 | Relative anchor for thresholds: the future admission criterion for new shapes or relaxations is — on the same randomly drawn prose control passage, the false-positive rate must not exceed the measured value for `shape_vol_abbr_page` | Initial value (2026-09-05): on the two negative controls (E prose 1,099 characters + F statutes and bibliography 2,324 characters, 3,423 characters in all), 0 false positives after deduplication (the 6 raw hits are all sub-spans of journal volume-page strings, covered by longer matches). Measurement method and limits in 13.1; the sample is only two passages, so the anchor value is tight; it should be remeasured on a larger random prose sample after the first full run |

---

## 16. Appendix A: confirmed defects of the old pipeline

This list exists so that every design point of the new pipeline can be traced to a specific failure rather than an abstract principle.

**Grading of evidence:** the defects themselves (code behaviour, structural problems) were all confirmed by reading the source code directly. The **counts** of defects (how many entries affected, how many rows with empty names) come from the old pipeline's own report files and were not re-checked one by one in this round; they are marked [unverified]. The design does not depend on these values; they only indicate the size of the defects.

### 16.1 Extraction layer

1. **Series identifiers consumed as page numbers.** In three shapes the page component immediately follows abbr, so `83 F. 2d 212` was truncated to `83 F. 2`. A full census on 2026-08-27 confirmed 140 truncated strings, and another 396 candidate strings were judged `UNCLEAR`. This defect is not limited to foreign citations; `211 D.L.R. 4th` is affected as well.
2. **A fixed list of abbreviations systematically missed a whole family of citations.** An earlier version matched against a fixed list, and none of the American citations was captured.
3. **The detail file kept only the top 2000 citation strings by frequency by default**, so it was not a true complete superset, and new entries pushed out old ones. Any reconciliation had to declare the parameter values used first.
4. **Abbreviations obtained by a second parse**: the normalized string was searched again with all shapes, taking the first result with an `abbr` group. This may disagree with the original match, and no mechanism detects the disagreement.
5. **The year extension was an opt-in switch** that, when on, wrote to a parallel directory `<COURT>_widened`, producing two definitions.

### 16.2 Classification layer

6. **Jurisdiction labels were not obtained by table lookup** but by having a model infer them from corpus signals; unreproducible and not verified against any authoritative source.
7. **The S2 signal (the words Privy Council) systematically misjudged Canadian cases as English.** Canadian appeals to the Privy Council were routine until 1949.
8. **The S6 place-name signal was originally missing altogether** (abbreviations that literally contain a place name, such as `U.C.Q.B.` = Upper Canada).
9. **Homographs were not handled at all**: `P.` was mislabelled English, `I.L.R.` mislabelled international.
10. **The most important batch of determinations was hard-coded in script source**: `_apply_origin.py` 19+5 entries, `_apply_origin_v4.py` 23+7+4+4+1 entries, about 70 citation_string-level literals in all, unsourced and outside any data-audit scope.

### 16.3 Merge layer

11. **`dd` took the max rather than the union**, missing judgments that appear in only one variant.
12. **The variant-folding table was derived from SCC corpus statistics and applied unchanged to ONCA**, and that table, itself a product of merging, was used as an input to merging, a circular dependency.
13. **Parallel reporters were not merged**: the same case under `A.C.` and `All E.R.` formed two separate groups.
14. **No cross-court folding rule existed**, and the architecture could not support one.
15. **Case-name quality**: SCC 599 rows with empty names and 141 rows with low agreement; ONCA 164 rows with empty names and 20 rows with low agreement [unverified: the values come from the old pipeline's report files and were not re-checked in this round]. The defect itself (many entries cannot vote a case name) is confirmed by the code.

### 16.4 Selection layer

16. **Two parallel threshold paths**, one of them an unfounded high-frequency bypass.
17. **`admitted>=5` and `agreement>=0.6` side by side as thresholds**; the two conditions point in opposite directions and cancel each other out with small samples.
18. **The threshold came before merging parallel reporters**, so mid-frequency cases spread across several reporters were cut on both sides.
19. **Selection and classification interleaved**: v1 selection, v2 classification, v3 reselection, v4 adjudication plus classification.

### 16.5 Engineering and organization

20. **Two twin aggregation scripts of over four hundred lines each**, differing only in paths, with the first 180 lines identical line by line. Every fix had to be made twice.
21. **Dead code**: the ONCA version had a loop that walked all of `kept` calling `jur_of()` but never used the result, a scar left by the patch that added the exclusion list.
22. **The aggregation script loaded the whole corpus with `pd.read_parquet`**, one reason a 900-second hard timeout was needed.
23. **The whole output directory was outside version control**, with no history at all. This was the common cause of the five backup directories, the three patch lists and the two sets of output directories.
24. **The local SCC.parquet had diverged from upstream.** Local 365,137,478 bytes [verified, read from disk in this round]; remote 365,085,432 bytes [unverified, from historical records]. Whatever the exact remote value, re-downloading would not give the same file, so the local copy was an irreproducible resource. (See §1.3: that snapshot has been replaced by the new snapshot of 2026-08-30 and deleted; this disk read cannot be reproduced, and the byte count is of historical interest only.)

---

## 17. Appendix B: rejected approaches

Recorded so they are not proposed again.

| Approach | Reason rejected |
|---|---|
| Maintaining an exclusion list in the aggregation layer to work around extraction defects | Violates constraint one. The list is a permanent liability that must be redone whenever the corpus changes |
| Narrowing the structure with a fixed list of abbreviations in the extraction layer | Violates constraint two. Shown to silently miss whole families of citations |
| Keyword signals from surrounding text for jurisdiction | Violates constraint three. S2 failed with the keyword present and the conclusion wrong; changing keywords does not help |
| A presumed default for homographs when there is no signal | Violates constraint four. Adding an `inferred` label does not stop it being a guess |
| `case_origin` defaulting to `jurisdiction` when not in the table | Violates constraint four. This is exactly the error that mislabelled Canadian JCPC cases as English |
| Decision tables keyed on canonical keys generated by the pipeline | Violates constraint seven. Once the pipeline changes, all manual verification becomes invalid |
| "Co-occurrence marking" for neutral citations | Requires defining the boundary of "the same sentence", a problem created by the design itself. It disappears once they are extracted as separate rows |
| Court-code table first in the classification layer, stopping on a hit | A false hit in the closed table is the most costly and nothing downstream can detect it; and it lets the progress of table filling decide the result |
| Moving "the top few dozen reviewed entries" of the old tables into the new tables | Unsourced and unreproducible, which amounts to stamping unverified content |
| Two separate scripts, one per court | Structurally unable to merge across courts, and every fix must be made twice |
| A high-frequency bypass in the selection layer | Four unfounded parameters; once the adjudication layer merges correctly, important cases reach the threshold naturally |
| The year extension as an opt-in switch | It protected an archive with no use, at the cost of two definitions |
| Merging the six shapes into one regex with `|` | Python `re` does not allow several branches to use capture groups with the same name |
| Reading in chunks with pandas `read_parquet` | That interface has no chunking parameter |
