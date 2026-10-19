# Fix1 local comparison

`tools/fix1_compare.py` prepares a D-only engineering comparison. It reads a completed run, existing reviewed Run B source-policy documents, the current D source contract, and existing pure analysis functions. It never changes G, a run directory, a freeze receipt or paper output. Test fixtures are small; no full comparison has been run as part of preparation.

The adapter writes:

- `normalized/04_members.csv.gz`, `05_edges.csv.gz`, `documents.csv.gz`, source-conditioned member mappings and stable signatures;
- `courts/11_edge_courts.csv.gz` and a crosswalk, with identity-qualified group donors;
- `metrics.json`: N/E/K/O and Q1 top-1% / top-20, Q2 top-100 Jaccard and cosine, Q3 all-edge foreign share, Q4 mean/median links, Q5 known nonnegative printed-year age median, Q6 court-destination shares, and Q7 final-occurrence neutral share;
- a receipt and local SQLite working database; `before_after.csv` when `--before-metrics` is supplied.

N includes measurable zero-edge sources. New resolved years and measurability are used, while the existing 16 reviewed source-scope exclusions remain excluded. The calendar is explicitly 2001–2025 excluding 2011. O is the final occurrence total and must equal summed final-edge mention counts. Printed-year priority and Q7 format overlays reuse the existing G pure functions; no modal-year shortcut is used. Q5 remains a report-year approximation. Q1 ties use stable signatures rather than ordinal group IDs, which can change cutoff membership within ties; DD and cutoff tie counts must be interpreted accordingly.

All-link and without-own-history views are separate. Old Run B lacks the new own-history field: its second view is marked unavailable, not silently set equal to all links. The new run supplies both; no old/new delta is claimed where the baseline view is unmeasurable.

Example PowerShell arguments (use a fresh D output directory each time):

```powershell
$paperRoot = 'G:\加拿大法庭数据论文'
$policyDocs = Join-Path $paperRoot 'analysis\run_20261017_a2aj9_fixed\source_policy_v1\normalized\documents.csv.gz'
$analysisRoot = Join-Path $paperRoot 'analysis'
$formatRules = Join-Path $analysisRoot 'q7_format_overlay.json'
$env:PYTHONUTF8 = '1'
python tools/fix1_compare.py --run-dir 'G:\加拿大法庭数据论文\case-citation-pipeline\data\run_20261017_a2aj9_fixed' --documents $policyDocs --analysis-root $analysisRoot --format-rules $formatRules --out 'D:\cases data analisis\implementation\fix1_compare_runB'
python tools/fix1_compare.py --run-dir 'D:\cases data analisis\data\run_20261019_a2aj9_fix1' --source-records 'D:\cases data analisis\data\run_20261019_a2aj9_fix1\source_integrity\source_records.csv' --documents $policyDocs --analysis-root $analysisRoot --format-rules $formatRules --out 'D:\cases data analisis\implementation\fix1_compare_new' --before-metrics 'D:\cases data analisis\implementation\fix1_compare_runB\metrics.json'
```

Confirm the actual `source_records.csv` location from the completed run manifest. Do not manufacture a complete manifest for a partial run. The separate production `check_run` receipt supplies seal validation; the adapter checks its semantic joins and occurrence reconciliation. Adapter receipts retain manifest and script hashes.

The existing b1–b4 scripts are adapted in `tools/fix1_baseline/`: measurement definitions remain, while mappings use `(source ID, member key)` and b4 change detection uses stable signatures. Pass every path explicitly; for b4 also pass `--baseline-signatures`. For each script:

```powershell
python tools/fix1_baseline/b2_parallel_run_splits.py --reference-root $paperRoot --run-dir 'D:\cases data analisis\data\run_20261019_a2aj9_fix1' --norm-dir 'D:\cases data analisis\implementation\fix1_compare_new\normalized' --courts-dir 'D:\cases data analisis\implementation\fix1_compare_new\courts' --corpus-dir 'G:\加拿大法庭数据论文\case-citation-pipeline\corpus' --out 'D:\cases data analisis\implementation\fix1_compare_new\baseline' --baseline-signatures 'D:\cases data analisis\implementation\fix1_compare_runB\normalized\group_signatures.csv' --courts SCC,ONCA,BCCA,NSCA,FCA,YKCA,FC,BCSC,NSSC
```

Use the same arguments for b1, b3 and b4. The original saved Run B b1–b4 values remain historical references; rerunning the local adaptations on Run B provides the source-conditioned-mapping check. Differences from saved diagnostics must be explained. b4 labels are reused from the frozen sample and are not a new independent review. The C3 native-locator difference-reading package remains a separate deliverable.

`top20_changes.csv` compares exact member-and-source signatures. A merge or changed supporting-source set changes that signature: the output records membership-signature changes, not established case entries/exits. Use C3 stable-overlap mappings if case continuity or rank movement is reported.

After a new comparison completes, `python -B tools/fix1_zone_views.py --comparison-dir <D-comparison-directory> --out <new-D-json-path>` supplements SCC with all links, without-own-history and without-headnote-only views. Every view retains the same measurable source denominator, including zero-edge sources. Only `zone_profile=headnote_only` is excluded in the third view; unknown zones remain. The first two N/E/K/O totals must match the main comparison. Old schemas are marked unavailable and no old/new delta is invented. These mechanical counts do not repair or supersede W2's failed seed-position recall gate.
