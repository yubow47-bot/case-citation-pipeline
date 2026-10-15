# Case Citation Pipeline

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23149206.svg)](https://doi.org/10.5281/zenodo.23149206)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Corpus: a2aj/canadian-case-law](https://img.shields.io/badge/corpus-a2aj%2Fcanadian--case--law-yellow)](https://huggingface.co/datasets/a2aj/canadian-case-law)

Courts constantly cite earlier cases. This project reads the available judgments of a court, finds the cases they cite, works out which differently written references belong to the same case, and counts how many different judgments cite each one. The aim is to make citation research reproducible: each counted link leads back to a source judgment and a passage in its text.

It has been run on three Canadian courts — the Supreme Court of Canada (SCC), the Court of Appeal for Ontario (ONCA), and the Court of Appeal for British Columbia (BCCA) — using the public [a2aj Canadian case law dataset](https://huggingface.co/datasets/a2aj/canadian-case-law). Historical results have been compared with [CanLII](https://www.canlii.org). Adding another court means checking its citation styles and source coverage as well as changing a setting.

| | |
| --- | --- |
| **The problem** | The same case is written in many different ways: the court's own citation (`2002 SCC 33`), law-report references (`[2002] 2 S.C.R. 235`), database IDs, and old footnote styles. Finding an abbreviation is only the beginning; these references need to be linked before counting. |
| **The approach** | Five steps: find anything shaped like a citation, label it, combine duplicates, decide which citations are the same case, and count. Rejected readings and groups below the cut-off remain available for inspection, and reference rules record their evidence. |
| **What you get** | Citation and case-group tables, counts, and source passages that support research into which cases courts cite and how citation patterns change. Search tools help researchers explore the results and maintainers understand the method. |
| **How accurate** | An audit of an earlier run found that 87.0% of links were real case citations, rising to 98.9–100% for groups cited by at least five judgments. A new model review checks case identity as well as citation detection. Both reviews, their dates, and their limits are explained [below](#how-well-it-works). |

A citation means a judgment **mentions** a case. It does not by itself show approval, following, or reliance. Read [the counting and usage guide](docs/USAGE.md) before quoting any number; this is research data, not legal advice.

## What the final data looks like

The pipeline's output is a list of case groups, each with one key number: **DD**, or **distinct decisions**. DD counts the different source judgments that cite a group. If one judgment mentions the same case twenty times, it adds one to DD and twenty to the mention count.

All groups stay in the tables. The select step applies a working cut-off of **DD ≥ 5**:

| DD | Meaning | In the current snapshot |
| --- | --- | ---: |
| **5 or more** | Kept in the main view; cited by at least five different judgments. | 14,003 groups |
| **Below 5** | Below the cut-off, but still available for inspection. | 216,446 groups |
| **All groups** | Includes groups without a final counted link after exclusions. | 230,449 groups |

A high DD means more different judgments cite the group. It does not prove that all the references were assigned to the right case, or that the citing courts relied on it. A low DD may describe a rarely cited case or an extraction or identity mistake. Five is a working cut-off that has not been formally calibrated. The historical audit found fewer non-case citations in higher-DD groups, but it did not establish identity accuracy.

## Example: one paragraph through two steps

`scripts/demo.py` runs the first two steps (find and label) on a made-up paragraph. It needs no downloaded data and no internet:

```text
[12] The standard of review was settled in Housen v. Nikolaisen, 2002 SCC 33, [2002] 2 S.C.R. 235.
The English rule in Donoghue v. Stevenson, [1932] A.C. 562 (H.L.), was applied. See also R. v. Oakes,
[1986] 1 S.C.R. 103, and section 7 of the Act, R.S.C. 1985, c. C-46.
```

```console
$ python scripts/demo.py
raw_string            shape                 offset   kind       jurisdiction  parse_status         court
2002 SCC 33           neutral_bare          65       neutral    CA            valid                -
2002 SCC 33           vol_abbr_page         65       reporter   UNSUPPORTED   ambiguous_year_vol   -
[2002] 2 S.C.R. 235   bracket               78       reporter   CA            valid                -
2 S.C.R. 235          vol_abbr_page         85       reporter   CA            valid                -
[1932] A.C. 562       bracket               142      reporter   GB            valid                H.L.
[1986] 1 S.C.R. 103   bracket               201      reporter   CA            valid                -
1 S.C.R. 103          vol_abbr_page         208      reporter   CA            valid                -
```

How to read this:

- `shape` is the text pattern that matched; `offset` is the character position where the citation starts.
- `kind`: `neutral` is the court's own case number (like `2002 SCC 33`); `reporter` is a reference to a printed law report (volume, report name, page, like `[2002] 2 S.C.R. 235`).
- `jurisdiction` is the citation classification (`CA` Canada, `GB` United Kingdom). For a reporter citation, this can describe the law report rather than the case's origin; origin is established separately. `UNSUPPORTED` means the classification is unknown.
- `parse_status` says whether the citation reads cleanly (`valid`) or is doubtful.
- The find step keeps every possible reading of the text, so `2002 SCC 33` appears twice: once correctly, as a neutral citation, and once misread as volume 2002 of a law report called `SCC`, which the label step marks as doubtful (`ambiguous_year_vol`). The combine step chooses between overlapping readings later.
- `[2002] 2 S.C.R. 235` and `2 S.C.R. 235` are the same reference matched twice (with and without the year); it is counted once later.
- `(H.L.)` (House of Lords) is recorded as the court that decided the English case.
- The statute reference at the end is correctly *not* picked up as a case citation.

### What the full pipeline makes possible

The two steps above find and label pieces of text. The later steps decide which references belong to the same case and count how many different judgments cite it. This makes a concrete research question possible: **which foreign judgments appear in Canadian courts' reasons, and how does that pattern vary by court and decade?** The source passages then let a researcher investigate what those citations were doing.

The table shows the five most-cited of **460 groups with an established foreign origin** in the 2026-10-15 snapshot. DD is counted across SCC, ONCA, and BCCA:

| Cited by (different judgments) | Case | Citation | Origin |
| ---: | --- | --- | --- |
| 173 | Anns v. Merton London Borough Council | [1978] A.C. 728 | GB (United Kingdom) |
| 108 | Donoghue v. Stevenson | [1932] A.C. 562 | GB (United Kingdom) |
| 52 | Salomon v. Salomon & Co | [1897] A.C. 22 | GB (United Kingdom) |
| 43 | Makin v. Attorney-General for New South Wales | [1894] A.C. 57 | AU (Australia) |
| 41 | Ibrahim v. The King | [1914] A.C. 599 | HK (Hong Kong) |

The [saved ranking and coverage evidence](audit/findings/readme_example_20261015/foreign_cases.json) records the run and query. With the documented run active locally, reproduce it with:

```powershell
python tools/research/research.py ask --intent ranking --origin FOREIGN --top 5 --evidence-limit 0 --language en --output audit/findings/research/foreign_top5.json
```

Origin is distinct from the country of the law report. Makin and Ibrahim were decided in London by the Privy Council, which heard appeals from across the British Empire, but the appeals originated in Australia and Hong Kong. An English report alone therefore cannot establish a British origin. The pipeline assigns origin only when citation evidence or a verified reference rule supports it.

Coverage is still incomplete. Across all cases, origin is known for **58,688 of the 228,102 groups with counted links (25.7%)**. The identified foreign subset contains **460 groups and 1,082 links**. The [coverage report](audit/findings/research_20261015/active_foreign_scope.json) gives the full counts and definitions; groups without a final counted link are outside this comparison.

These are results for the identified subset, not a complete ranking of foreign influence. Unknown origins are not treated as foreign and are not extrapolated. Court-and-decade comparisons must carry their own coverage denominators: a change in known foreign citations may reflect coverage as well as changes in judicial citation practice.

## Pipeline

```mermaid
flowchart LR
    J["Judgments<br/>(a2aj dataset)"]
    E["1 · Find<br/>every piece of text<br/>that looks like a citation"]
    C["2 · Label<br/>what kind of citation,<br/>which country"]
    M["3 · Combine<br/>identical citations"]
    D["4 · Decide<br/>which different citations<br/>are the same case"]
    S["5 · Select<br/>count citing judgments,<br/>apply the cut-off"]
    O["Results<br/>tables + search"]
    T["Reference tables<br/>courts · law reports"]

    J --> E --> C --> M --> D --> S --> O
    T -.-> C

    classDef main fill:#eaf3ff,stroke:#2563eb,stroke-width:2px,color:#142d50;
    classDef support fill:#f8fafc,stroke:#94a3b8,color:#25354a;
    class J,E,C,M,D,S,O main;
    class T support;
```

1. **Find** anything shaped like a citation (year, court code, volume, page). No abbreviation list is needed, so unfamiliar reports are still caught.
2. **Label** each one: what kind of citation, which country, and whether it is only a look-alike or a judgment citing itself.
3. **Combine** identical citations and resolve text that could be read two ways.
4. **Decide** which different citations are the same case — for example a case number and a law-report reference printed side by side — and keep apart different cases with the same name.
5. **Select** by DD (the number of different judgments citing each case). Cases with DD of 5 or more are kept as the main result; groups below 5 are flagged as below the cut-off, not removed.

The steps keep their own outputs and decision evidence, so an unexpected count can be traced back through the grouping and parsing decisions to the text. The [reference tables](decisions/) record the evidence used by the rules. When origin cannot be established, it remains unknown. Earlier and later judgments in the same litigation must be distinguished from multiple references to one judgment.

### Data

The judgments come from the [`a2aj/canadian-case-law`](https://huggingface.co/datasets/a2aj/canadian-case-law) dataset on Hugging Face. This project does not collect them itself. The documented production snapshot is **run_20261015_identity_review**, completed on **2026-10-15**, using English text when available and French text otherwise.

| Court | Source records | Years |
| --- | ---: | --- |
| Supreme Court of Canada (SCC) | 10,891 | 1877–2026 |
| Court of Appeal for Ontario (ONCA) | 24,089 | 1998–2026 |
| Court of Appeal for British Columbia (BCCA) | 14,703 | 1999–2026 |

These total 49,683 source records; **49,674 contain usable text**. The three-court production snapshot does not include trial courts, other appeal courts, federal courts, or tribunals. Separate court experiments do not expand this snapshot's scope. Courts are selected with `PIPELINE_COURTS`, but unfamiliar reports and non-case references still need review before results from a new court can be interpreted.

The first number below is much larger than the others because it includes repeated mentions and duplicate readings of the same text:

| Measure | Count |
| --- | ---: |
| Possible citation matches | 1,472,144 |
| Citation members used in case grouping | 261,029 |
| Case groups | 230,449 |
| Links from a source judgment to a cited group | 490,577 |
| Counted mentions in those links | 705,476 |
| Groups cited by at least five different judgments | 14,003 |

Counts come from the retained [release summary](audit/findings/project_review_20261015/release_summary_final.json). The [mention reconciliation](audit/findings/project_review_20261015/edge_counters.json) explains why an earlier step log has 716,593 mentions: it includes 11,117 later excluded as self-citations. Source records, groups, links, and mentions are different units.

Save the run ID with every research result: group IDs and counts can change between runs. On a configured local installation, `data/active_run.json` selects the active run and database, and `python tools/status.py` reports availability. Large corpus files and generated databases are local inputs and outputs; a source checkout alone does not contain the full results.

## Two search systems on top of the pipeline

The pipeline produces both research results and a record of how each step was built, checked, and fixed. Search is a way to use this work: researchers explore cases and passages, while maintainers find rules, code, and earlier problems before extending the method.

```mermaid
flowchart TB
    subgraph METHODS["Method search · for maintainers"]
        direction TB
        MS["Specification · Audits<br/>History of fixes"]
        MC["Method guides<br/>Steps · Checks · Pitfalls"]
        MI["Search indexes"]
        MQ["Maintenance question<br/>e.g. how to add a court"]
        MV["Search by meaning"]
        MK["Search by keyword"]
        MR["Combined results<br/>with scope and status shown"]
        MA["AI-assisted extension<br/>and repair"]

        MS -->|Summarised and checked by hand| MC
        MC --> MI
        MQ --> MV & MK
        MI -.-> MV & MK
        MV & MK --> MR
        MR --> MA
    end

    subgraph DATA["Data search · for researchers"]
        direction TB
        DS["Pipeline results<br/>Cases · Citation links · Positions"]
        DI["Search indexes"]
        DQ["Research question"]
        DV["Search by meaning"]
        DK["Search by keyword"]
        DT["SQL queries<br/>Exact counts · Filters"]
        DR["Results with evidence"]
        DA["AI-written answer<br/>(planned)"]
        DP["Trace back to the judgment<br/>and the exact passage"]

        DS --> DI
        DS -.-> DT
        DQ --> DV & DK & DT
        DI -.-> DV & DK
        DV & DK & DT --> DR
        DR --> DA
        DA --> DP
    end

    classDef content fill:#eaf3ff,stroke:#2563eb,color:#142d50;
    classDef search fill:#f8fafc,stroke:#94a3b8,color:#25354a;
    classDef result fill:#fff4e8,stroke:#d97706,color:#65320a;
    classDef planned fill:#ffffff,stroke:#d97706,stroke-dasharray:5 4,color:#65320a;
    class MS,MC,DS content;
    class MI,MQ,MV,MK,DI,DQ,DV,DK,DT search;
    class MR,MA,DR,DP result;
    class DA planned;
```

The diagram shows the intended workflow as well as implemented tools. **Keyword search and exact table queries are ready for the documented run. Vector search is unavailable for that run, and AI-written research answers remain planned.** Optional vector code does not mean a usable index has been built. The method guides and audit records also contain model-assisted work; the diagram's hand-checking label should not be read as independent human validation of all material.

### Data search

After a run, the tables can be loaded into a local database. Case profiles bring together names, citations, DD, and sample passages. A researcher can search a case name, inspect the judgments citing it, and return to the source text. Exact counts come from the full tables, not the first few search hits.

```powershell
python tools/status.py
python tools/foundation/query.py "Donoghue" --run run_20261015_identity_review --mode keyword -k 5
python pipeline/trace_source.py --run-dir data/run_20261015_identity_review --search "Donoghue v. Stevenson"
python tools/research/research.py find "Housen" --top 5 --language en --output audit/findings/research/housen.json
python tools/research/research.py ask --intent court_decade --language en --output audit/findings/research/trend.json
python tools/research/research.py ask --intent ranking --top 10 --with-text --language en --output audit/findings/research/top10.json
```

The [research tool](tools/research/README.md) saves query parameters, exact counts, coverage context, and a limited set of source passages. Its `ask` command supports defined question types; it does not generate an answer to an arbitrary legal question. The [retained court-and-decade result](audit/findings/research_20261015/active_court_decade.json) is an example of a reproducible research output.

Optional weighted DD uses experimental citation-quality weights. It does not measure importance, treatment, or identity correctness, and historical weights should not be presented as current-run accuracy. Production DD remains the unweighted count of distinct citing judgments.

### Method search

The code, reference tables, specification, audit reports, and method guides are split into searchable pieces linked to their source files. A maintainer exploring how to add a court can find the guide, the relevant code, and earlier failures. Method search is project-wide; data search should specify the intended run.

```powershell
python tools/foundation/query.py "new court" --collection methods --mode keyword
```

Both indexes can be rebuilt with [`after_run.py`](tools/foundation/after_run.py). The default build is offline and skips vectors; optional embeddings require separate configuration. See the [search setup guide](tools/foundation/README.md).

The [quality tool](tools/quality/README.md) supports sampling and review. The [citation-context experiment](tools/citation_context/README.md) explores short citations and possible treatment words separately. Short-citation recovery and treatment classification remain experimental and do not change production DD or establish judicial reliance.

## How well it works

### Current source-text model review

On 2026-10-15, a model assessed all **270 links** in a fixed sample from `run_20261015_identity_review`. It read source evidence and checked both whether a case was mentioned and whether the link pointed to the right judgment.

| Question | Model decisions | Weighted score among decided records | Share of sample weight decided |
| --- | --- | ---: | ---: |
| Does the source mention a case? | 265 yes, 3 no, 2 unknown | 93.9% | 95.3% |
| Is it a case mention linked to the right judgment? | 118 correct, 18 incorrect, 134 unknown | 90.9% | 77.1% |

Weights account for different chances of selection. Unknowns count as neither correct nor incorrect, so the scores describe only the records the model could decide. In particular, **90.9% is not an accuracy estimate for the whole pipeline**. All 270 records received model assessments; none received manual labels in this review. The recorded model was `gpt-6.1-sol`, with 77 assessments at Max and 193 at Medium reasoning effort. See the [review results, raw rates, and reproducible commands](audit/findings/quality_model_review_20261015/README.md).

### Historical CanLII comparison

These are **historical results for run_20261002_tables2**, the run dated **2026-10-02**. The current model review uses a different method and evidence; the two sets of scores are not directly comparable.

The [T6 audit](audit/findings/canlii_crosscheck/run_20261002_tables2/t6_calibration.md) checked **215 links** by reading source text. The links were sampled within a comparison set of **360 judgments** across three courts and three time periods per court. Results were weighted by the number of links in each sampling category; they are not simple percentages of the sample.

| DD of the cited group | Links checked | Weighted share that were real case citations |
| --- | ---: | ---: |
| 1 | 76 | 75.0% |
| 2–4 | 53 | 81.7% |
| 5–9 | 29 | 98.9% |
| 10 or more | 57 | 100% |
| Overall | 215 | 87.0% |

The overall approximate interval was **75.0%–92.3%**. The remaining weighted shares were 8.2% errors and 4.8% mentions of earlier stages or reports of the same case. The audit counted a real case citation as correct even if its group had the wrong name. It therefore does not establish case-identity accuracy or tell us how a court treated a case. Small samples also limit what the 100% result can tell us about other links.

**How much of CanLII's citation list is matched?** The separate [T2 comparison](audit/findings/canlii_crosscheck/run_20261002_tables2/t2_summary.md) used 40 judgments in each court-and-period sample. For SCC, it matched 97.3% of CanLII-listed citations in 2000–2026, 79.8% in 1950–1999, and 36.4% in 1875–1949. ONCA and BCCA samples ranged from 70.2% to 96.9%. These are coverage figures against CanLII, not a complete measure of missed text citations: different source texts, grouping, exclusions, and CanLII records can all affect the comparison. For example, the oldest SCC sample's 68 CanLII-only cases included five extracted but grouped elsewhere; the automated name check could not locate the other 63 in the source text. That finding does not establish that the source contains no missed citations.

**Do the “cited by” lists agree?** The historical [T3 comparison](audit/findings/canlii_crosscheck/run_20261002_tables2/t3_summary.md) examined 60 sampled cited groups plus Housen. Within comparable citing judgments from the same three courts and corpus, 98.5–99.8% of the pipeline's citing judgments also appeared in CanLII's lists across the three sampled periods. The pipeline found 82.7% of CanLII's citing judgments for pre-1950 cases, 89.2% for 1950–1999 cases, and 99.5% for 2000–2026 cases. Citing judgments that could not be mapped to a CanLII ID were excluded, so those percentages apply to the comparable subset.

The original outputs for `run_20261002_tables2`, `run_20261003_selfcite`, and `run_20261003_v16f` have been retired. Small receipts, manifests, logs, and audit reports remain: [retirement receipt and retained record paths](audit/findings/repository_cleanup_20261015/retired_runs.json). These records describe past runs; they cannot replace the original full outputs.

Automated checks cover extraction, grouping, run integrity, and the research tools; the [verification record](audit/findings/repository_cleanup_20261015/validation.json) records the results. These checks catch software and table errors; source-text reviews address whether a citation was understood correctly. Open problems and remaining work are tracked in [PROBLEMS.md](PROBLEMS.md) and [DEBT_LEDGER.md](DEBT_LEDGER.md).

## Quick start

Use Python 3.11 or later. The download script also needs `bash` (Git Bash or WSL on Windows). Allow several gigabytes for the corpus and generated files; storage needs depend on the courts and runs you keep.

```bash
pip install pyarrow pyyaml
bash scripts/download_corpus.sh list
bash scripts/download_corpus.sh download
python scripts/demo.py
python pipeline/run_all.py --out data/run_smoke --limit-batches 1
python pipeline/run_all.py --out data/run_YYYYMMDD_name
```

The default courts are SCC, ONCA, and BCCA. To select others, set `PIPELINE_COURTS` for both the download and pipeline commands. Support for a new court still needs review of its citation styles and source data.

Check a completed run before using its counts:

```bash
python tools/check_run.py --run data/run_YYYYMMDD_name --output audit/findings/run_check.json
```

This reads CSV or compressed CSV files and checks links, group membership, DD, and exclusions. A passing check means the output tables agree with each other; separate audits are needed to measure extraction and identity accuracy.

To build the local keyword-search database, first install the dependencies in the [search setup guide](tools/foundation/README.md), then run:

```bash
python tools/foundation/after_run.py --run data/run_YYYYMMDD_name
```

The default build is offline and skips vectors. New pipeline runs use compressed output and storage limits by default. [Storage tools](tools/storage.py) can inventory files, compress retained runs, and retire selected runs with receipts.

After changing pipeline code, run the relevant checks:

```bash
python pipeline/tests/run_regression.py --selftest
python pipeline/tests/test_layers.py
python pipeline/tests/test_layers.py --golden
```

The last command needs a completed pipeline run for comparison. The full step order is in the [technical specification](docs/technical_specification.md).

## Roadmap

- Independently review source-text case mentions and case identities on the current run, including unresolved and French-text records.
- Calibrate the DD cut-off and repeat the CanLII comparison on the current run.
- Improve origin coverage before drawing broader conclusions about foreign citation patterns.
- Resolve citation and identity problems recorded in [PROBLEMS.md](PROBLEMS.md) and [DEBT_LEDGER.md](DEBT_LEDGER.md), while keeping procedural relationships separate from judgment identity.
- Evaluate short-citation recovery and treatment classification without silently changing production counts.
- Evaluate optional vector search and research answers with source references.
- Extend court coverage using the [new-court guide](docs/method_cards/00_new_court_playbook.md).

## License

The code is released under the [MIT License](LICENSE). The judgments themselves come from the [a2aj/canadian-case-law](https://huggingface.co/datasets/a2aj/canadian-case-law) dataset and are covered by its own terms, not by this license.
