# Source-text model review: 270 citation links

Completed on 2026-10-15 for `run_20261015_identity_review`. All **270 sampled links** received model assessments using source-text evidence. The actual recorded model was **`gpt-6.1-sol`**: 77 assessments used Max reasoning effort and 193 used Medium after the setting changed. These are model assessments, not manual labels or independent ground truth.

## Results

| Check | Correct / yes | Incorrect / no | Unknown | Raw score among decided records | Weighted score among decided records | Weighted share decided |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Source mentions a judicial case | 265 | 3 | 2 | 265/268 = 98.88% | 93.88% | 95.28% |
| Case mention and correct judgment identity together | 118 | 18 | 134 | 118/136 = 86.76% | 90.90% | 77.11% |

The joint check requires both a real case mention and the correct judgment identity. It fails if either the mention is not a case or the identity is wrong. Otherwise, missing evidence leaves it unknown.

The fixed sample was drawn in groups with different selection chances. Each record's weight is `1/pi`, where `pi` is its chance of selection. The 270 weights sum to **490,577**, the number of links in the sampling frame. The original split remains **212 train and 58 holdout**; the table above combines both.

Unknowns are neither successes nor errors and are excluded from score denominators. The weighted share decided shows how much of the sample's total weight received a yes/no or correct/incorrect decision. In raw record counts, that is 268 of 270 for case mentions and 136 of 270 for the joint check. **The 90.90% score is not full-pipeline or population accuracy.** Model-review completion is 270/270; manual-review count is zero.

The historical [215-link CanLII audit](../canlii_crosscheck/run_20261002_tables2/t6_calibration.md) reported 87.0% for an older run using different evidence and rules. These results are not directly comparable and do not establish an accuracy improvement over that audit. This review does not change production links, DD, or case groups.

## Files and reproduction

- [evaluation.json](evaluation.json): counts, rates, weights, coverage, and fold summaries.
- [reviews.jsonl](reviews.jsonl): individual model assessments and reasons.
- [model_labels.csv](model_labels.csv) and [model_labels.json](model_labels.json): labels used by the evaluation tool.
- [rubric.json](rubric.json): assessment rules.
- [review_manifest.json](review_manifest.json) and [execution_changes.json](execution_changes.json): run identity, model settings, and execution history.
- [Original sample](../quality_20261015/samples.json): fixed selection and sampling weights.

From the repository root, import the existing labels and reproduce the evaluation:

```powershell
python tools/quality/quality.py import-labels --samples audit/findings/quality_20261015/samples.json --labels audit/findings/quality_model_review_20261015/model_labels.csv --output audit/findings/quality_model_review_20261015/model_labels.json
python tools/quality/quality.py evaluate --samples audit/findings/quality_20261015/samples.json --labels audit/findings/quality_model_review_20261015/model_labels.json --output audit/findings/quality_model_review_20261015/evaluation.json
```

These commands process saved labels; they do not call a model or create new assessments. See the [quality tool guide](../../../tools/quality/README.md) for field definitions.
