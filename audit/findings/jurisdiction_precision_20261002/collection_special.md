# Independent evidence collection: directions 2–4

Date: 2026-10-02. Read-only evidence collection; no existing table, code, corpus, or production run changed. Source material is paraphrased.

## Direction 2: Nfld. & P.E.I.R.

**Proposed decision:** retain two exact province rows, NL and PE, as the series reporting scope. Do not treat those rows as the provenance of every reported case. The publisher-description transcription says the series includes Newfoundland and PEI appellate decisions, selected trial decisions, and SCC decisions originating in either province. Thus an SCC case may appear in this reporter while its originating court is the SCC and its case provenance may be either province.

Internal channel 1 directly finds 279 parallel strings: NL 227 and PE 52, with NLCA 172, NFCA 33, PECA 26, and NLTD 22. This is distribution evidence from reporter parallels, not a case-level origin census. The PEI Law Society Library serials catalogue identifies Maritime Law Book as publisher and lists volumes 1–373 (1971–2016). A publisher-description transcription says the series began in 1970, leaving a one-year bibliographic discrepancy.

Sources: [Maritime Law Book series description as transcribed in the Lawi index](https://books.lawi.ca/how-to-use-our-indexes/); [Law Society of Prince Edward Island library catalogue](https://lawsocietypei.ca/media/files/Law%20Library%20Catalogue%20Print%20Serials%20April%2028%2C%202016.pdf); [CanLII-hosted example document containing both NLCA and PEI decisions cited to the series](https://www.canlii.org/w/canlii/2017CanLIIDocs2.pdf); [Department of Justice Canada court-links directory](https://laws.justice.gc.ca/eng/Court/).

**Gap:** I did not find an official publisher-hosted description. The Law Society catalogue confirms title, publisher, and holdings but not court coverage. Keep the province-scope decision; do not infer case origin from reporter membership.

## Direction 3: Que. K.B. and Sask. L.R.

**Proposed decision:** the mixed CA/GB channel-4 signal is consistent with A.C. parallel propagation from Canadian cases appealed to the Judicial Committee. The source material does not trace every mixed record, so do not call all GB instances explained or claim reporter mismatch.

The ch4 JSON is an aggregate distribution with `hop1`, `hop2`, `hop1_old`, and a normalized-key-to-label map; it contains no raw citation string or case identity. Counts: Que. K.B. is CA 17 / GB 9 at hop 1 and CA 18 / GB 9 at hop 2; Sask. L.R. is CA 12 / GB 4 at both hops. Channel 4 text identifies A.C. as the contributor in all nine Que. K.B. GB chains, while the Sask. L.R. row lists W.W.R., D.L.R., and W.L.R. without per-case propagation traces.

A CanLII-hosted McGill Law Journal article gives a concrete Quebec path: *Hirsch v Protestant Board of School Commissioners* is cited as (Que. K.B. in banc), affirmed by the SCC, and later affirmed at [1928] A.C. 200. The same source describes a Saskatchewan path: *Re Farm Security Act (Sask.)* was affirmed sub nom. *A.-G. Sask. v A.-G. Can.*, [1949] A.C. 110. These corroborate the mechanism that Canadian provincial cases can acquire A.C. citations. The [official JCPC case-search portal](https://jcpc.uk/cases) is the appropriate primary source for tracing the exact source cases once case strings are available.

Sources: [CanLII-hosted McGill Law Journal source with both case histories](https://www.canlii.org/w/canlii/1964CanLIIDocs13.pdf); [official JCPC case search](https://jcpc.uk/cases); [Law Society of England and Wales guide to law-report citations](https://www.lawsociety.org.uk/contact-or-visit-us/law-society-library/research-guides/how-to-find-law-reports).

**Gap:** because the aggregate artifact omits case-level chains, none of the nine/four cases were individually audited here. The A.C. explanation must remain limited to the evidence traced.

## Direction 4: S.J.

**Proposed decision:** preserve two interpretations. Emond's original online guide explicitly lists Quicklaw `SJ = Saskatchewan judgments`, supporting the SK row. The guide uses undotted `SJ`; the dotted corpus form depends on punctuation normalization. For GB, Solicitors' Journal is a numbered serial. A true volume position supports the GB reading; a bare `[year] S.J. No. number` form has no volume. Where extraction has misread the year as the volume, leave it unresolved/unsupported instead of assigning either jurisdiction.

`PROBLEMS.md` item 100 records the existing table fix: 211 no-volume Quicklaw-style rows mapped to SK; 19 true-volume rows remained GB; 3 year-as-volume extraction cases matched neither 1–999 nor 0–0 and became UNSUPPORTED. Channel 1 independently found 81 direct parallel strings, all SK (SKCA 54, SKQB 24, SKPC 2, SKKB 1). The narrower summary file's 167-row count belongs to a different subset.

The [ISSN International Centre record](https://portal.issn.org/resource/ISSN/0038-1047) identifies the British serial and consulted volume 162 (2019); [Penn's serial archive guide](https://onlinebooks.library.upenn.edu/webbin/serial?id=solicitorsjnl) independently records its numbered volumes and title history. These establish that Solicitors' Journal has real volumes, but neither source establishes 999 as a maximum.

**Gap:** GB 1–999 is a deliberately broad upper bound, not a sourced historical endpoint. Current corpus evidence supports numbered-volume usage but does not prove every numbered S.J. means the UK journal.

## Evidence files consulted

- `decisions/reporter_jurisdiction.csv` (read-only)
- `audit/findings/jurisdiction_channels/README.md` and `summary.csv`
- `audit/findings/jurisdiction_channels/ch1_evidence.json` and `ch4_evidence.json`
- `audit/findings/jurisdiction_channels/channel1_parallels_output.txt` and `channel4_reporter_parallels_output.txt`
- `PROBLEMS.md`, item 100
