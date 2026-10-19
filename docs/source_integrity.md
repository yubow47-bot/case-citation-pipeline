# Source integrity contract

`pipeline/source_integrity.py` exports one `source_records.csv` row per physical
corpus row, including empty texts and records without extracted citations. Source
IDs and original parquet files are never changed. `source_anomalies.csv` is a
review queue; `summary.json` reconciles dispositions by court. Invoke the command
with repeated `--court`, `--corpus-dir`, `--text-policy`, and `--out`; optional
`--batch-size` and `--limit-batches` match extraction scope.

## Judicial dates (S1)

`provider_date` preserves the selected provider timestamp. A native judicial date
must be printed on its own `DATE:` / `Date:` line as YYYYMMDD, YYYY-MM-DD, or
YYYY/MM/DD (optional parentheses), in a formal header containing a Citation or
Docket label. The web wrapper before `Decision Content` is ignored, and the first
printed paragraph or judgment/order body marker ends the header. Multiple
different dates or invalid dates do not authorize replacement.

`native_decision_date`, `native_date_status`, and `native_date_evidence_json`
retain the resolved native date and its original character spans. `text_sha256`
binds these spans to the exact selected corpus text. `date_conflict_status` is
MATCH, DATE_CONFLICT, YEAR_CONFLICT, or NOT_COMPARABLE. `source_decision_year`
uses the unique valid formal date, otherwise the provider date; the choice is
explicit in `decision_year_basis`. Citation years are never a fallback.

This corrects the reviewed ONCA 2018/238, 2007/621, 2011/777 and FC 2020/474
calendar errors while preserving the 2012 date of NSSC 2011/506 and the 2011
date of FC 2016/18. Extraction uses the same date resolver. Consumers should use
`source_decision_year` instead of reading provider dates again. G-side consumers
are outside this implementation round.
