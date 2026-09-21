# Case Citation Network

**English** | [中文](docs/README.zh.md)

A citation-extraction pipeline over Canadian case law. From full-text judgments it structurally extracts **every case citation** — foreign and domestic, neutral and reprinted, database and vendor identifiers alike — and assembles them into an auditable statistical table carrying case name, jurisdiction, case origin, and citation frequency. The purpose is academic research: an auditable census of the cited-case landscape in the history of these courts.

**Corpus — [`a2aj/canadian-case-law`](https://huggingface.co/datasets/a2aj/canadian-case-law).** The source is that dataset on HuggingFace (Parquet), **not** a corpus collected by this project. Three courts as of 2026-09-18 (BCCA added after a validation run on the `exp/bcca-citt` branch — see `implementation/exp_bcca_citt_findings.md` — reached a jurisdiction-resolved rate matching ONCA's):

| Court | Judgments | Year range |
|---|---:|---|
| Supreme Court of Canada (SCC) | 10,891 | 1877–2026 |
| Court of Appeal for Ontario (ONCA) | 24,089 | 1998–2026 |
| Court of Appeal for British Columbia (BCCA) | 14,703 | 1999–2026 |

Provincial superior courts, appellate courts other than ONCA/BCCA, federal courts and tribunals are **not** in the corpus — see §1 of [`USAGE.md`](docs/USAGE.md). The set of courts is configurable (`PIPELINE_COURTS`, see `pipeline/run_all.py --help`); a federal tribunal (CITT) was also validated on the same experiment branch but is not yet in the default scope — its jurisdiction-resolved rate (28.4%) reflects a structurally different institution (tariff-schedule line items and specialist reporters not yet in the decision tables), not a pipeline defect.

**Read [`USAGE.md`](docs/USAGE.md) before reading any number** (Chinese): it states exactly what "cited N times" measures, the difference between `dd` and `occurrence_count`, that the `kept` threshold is an uncalibrated placeholder, that jurisdiction and case origin are two different things, and a complete list of what this table under-counts.

## Five layers

1. **Extract** — structural matching; full output, nothing filtered or judged
2. **Classify** — row-independent: look up jurisdiction, split case-name candidates, flag false positives
3. **Merge** — cross-row statistics: collapse identical strings, fold variants, mode-vote on case names
4. **Decide** — case identity: origin determination, parallel-reporter merging, cross-court merging, splitting homonymous distinct cases
5. **Select** — a single threshold; rows are flagged, never deleted

## Repository layout

```
.
├── .gitignore
├── README.md                       this file
├── PROBLEMS.md                     tracked; a record only, scripts must not read it
├── DEBT_LEDGER.md                  technical-debt ledger
├── select_config.yaml              selection-layer profiles (hashed into run fingerprints, hence kept at root)
├── docs/
│   ├── README.zh.md                Chinese original of this file
│   ├── USAGE.md                    how to read the data — read this first (Chinese)
│   └── 外国引证数据整理抽取管线项目技术规格.md   the single technical spec (Chinese)
├── scripts/
│   └── download_corpus.sh          corpus snapshot downloader (HF enumeration, resume, SHA256; bash/WSL)
├── corpus/                         gitignored, read-only snapshot; download dates and fingerprints in spec §1.3
│   ├── SCC.parquet
│   ├── ONCA.parquet
│   └── BCCA.parquet
├── decisions/                      tracked; the single source of truth
│   ├── README.md
│   ├── reporter_jurisdiction.csv
│   ├── neutral_court_codes.csv
│   ├── series_prefix.csv
│   └── case_origin.csv
├── audit/                          tracked; audit ring — output is proposals, not data (rules in audit/README.md)
│   └── findings/                   triage hand-offs, provenance proposals, exclusion lists
├── pipeline/                       tracked
│   ├── normalize.py
│   ├── shapes.py
│   ├── extract.py
│   ├── classify.py
│   ├── merge.py
│   ├── decide.py
│   ├── select.py
│   ├── coverage_report.py          table-filling priority report (§12.1)
│   └── tests/                      run_regression.py (extract layer), test_layers.py (layers 2–5), golden_layers.json
├── implementation/                 tracked; session reports and probes; run_registry.csv + rebuild_run.py rebuild old runs
├── data/                           gitignored; derived artifacts (what each dir is and retention rules: data/README.md)
│   ├── run_20260915_r21a/          ★ delivery run (from 2026-09-15; #21 / debt 1 fix)
│   ├── run_20260914_r4c/           previous delivery run, kept for comparison
│   ├── run_20260913_r3e/           previous baseline (fully retained)
│   ├── run_2026091x_*/             5 historical runs; only answer-layer or sensitivity artifacts kept (not rebuildable)
│   ├── extract_out … coverage_out  6 directories from the old route (--golden gate and USAGE §8 anchors)
│   ├── audit/                      pre-change snapshots and measurement output
│   └── canlii_cache/               required by build_case_origin.py --offline
    └── README.md
```

## Running

The full order of execution and the exact commands are in the technical spec §12. After changing any layer:

```bash
python pipeline/tests/run_regression.py --selftest
python pipeline/tests/test_layers.py
python pipeline/tests/test_layers.py --golden
```

Additions to, and deviations from, the spec are logged in `PROBLEMS.md` and marked in the spec as "implementation note (v1.6)", pending human review.

## Constraints

See the technical spec for the full list. The core ones:

- A problem must be fixed at the layer that produces it
- The extract layer may not use a fixed abbreviation list
- Jurisdiction determination may not rely on surrounding-text keywords
- Not found means `UNSUPPORTED`
- Never delete a row; only flag it
- Layers are one-directional, and each runs exactly once
- Keys of decision tables must be facts printed in the judgment
- Every row must carry a source
