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

The full-corpus check and C3 source reading also found misprinted native dates,
including one-year errors, hearing dates, and dates of amended judgments. A native
year before 1800 or more than one year after both the provider year and the
registered metadata neutral-citation year is OUT_OF_RANGE_NATIVE_DATE.

When the formal native DATE and provider years differ, the native year may replace
the provider only if it agrees with the unique selected metadata neutral-citation year.
Otherwise the result is UNRESOLVED_NATIVE_YEAR_CONFLICT, retaining the provider
year and `decision_year_basis=PROVIDER_UNRESOLVED_NATIVE_DATE`. Native date/span
evidence remains available. This does not replace dates with citation years: a
real, unique valid formal DATE is always required, and agreement between native
and provider dates remains valid even when the citation year differs (NSSC
2011/506 and FC 2016/18 are controls).

This round dates the selected written judgment/reasons rather than reconstructing
the earliest oral disposition. For example, NSSC 2002/27 records an oral decision
in 2001 and written release in 2002; its formal written-source DATE is 2002.
Amendment dates conflicting with original metadata stay unresolved under the
corroboration gate. The rule does not certify all accepted dates as error-free.

Bounds and the corroboration rule are loaded from
`decisions/source_integrity_policy.csv`, with source locators and rationale; the
summary records its SHA-256. The previous five-year discrepancy threshold was
insufficient and was replaced after the C3 sample exposed small native-date errors.

## Source-to-text bindings (S2)

Every physical source row receives `own_citation_checked=True`. A printed
`Citation:` / `CITATION:` / `Référence:` block inside the judicial header, with
a separate Date or Docket label, supplies own-citation evidence. Only registered
neutral codes and accepted `bilingual_neutral_codes.csv` equivalences are used.
Leading zeros in the numerical decision identifier do not create a conflict.
An unlabelled web metadata field or a citation in the judgment body is insufficient.

One unambiguous native citation conflicting with one unambiguous metadata citation
sets `own_citation_status=MISMATCH`, `source_measurable=False`, and
`quarantine_reason=SOURCE_CITATION_MISMATCH`. Missing, ambiguous, and uncomparable
headers remain explicit review states; absence of a verified header is not proof
of a wrong binding. `native_citation_evidence_json` provides original spans.
The mismatch check is independent of duplicate-text detection and therefore also
catches incorrectly attached texts that differ from other corpus records.

Exact nonempty selected-text SHA-256 groups are compared across all source IDs.
`duplicate_text_source_count` and `duplicate_text_sources` retain their membership,
and `duplicate_text_groups.json` lists every group. Equality alone never merges
metadata IDs or quarantines a source. `own_citation_mismatches.csv` lists every
mismatch, including cases with no duplicate. `citation_provider_year_conflict`
retains the original year-screening queue, which is not itself proof of an error.
Malformed number boundaries such as `2002 BCCA0 402` are explicitly marked
MALFORMED_NATIVE_CITATION; they cannot authorize a mismatch with decision zero.

Consumers load the source-ID mapping with `load_source_records(path_or_directory)`;
it converts `source_measurable` to a Python boolean and rejects conflicting
dispositions for repeated source IDs. Quarantined rows and extracted candidates
remain available for inspection, but these sources cannot count as measured
observations or supply positive global identity evidence. No raw row is deleted.
The loader accepts retained `.csv` or `.csv.gz` artifacts through the shared
artifact reader, including a logical CSV path after final run compaction.

## Incomplete content (S3)

`text_integrity_status=INCOMPLETE_HEADER_SIGNATURE` requires all nonblank native
content lines to be accounted for as an exact metadata title/citation or a
printed judicial signature, with both roles present. This identifies the
reviewed 2004 BCSC 937 remnant. Its `source_measurable` is False and its quarantine
reason is INCOMPLETE_TEXT. Original line spans are retained in
`text_integrity_evidence_json`.

Any remaining text, including a brief operative disposition, prevents this
classification. Short oral rulings therefore remain measurable. No minimum word
count or absence of numbered paragraphs is a reason to exclude a source.
PRESENT_UNVERIFIED means that this narrow incompleteness mechanism did not fire;
it is not certification that the original judgment is complete.
