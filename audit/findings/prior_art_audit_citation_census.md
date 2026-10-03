# Prior-Art Audit: Auditable Citation Census over Canadian Case Law

Research question audited: does there already exist a **jurisdiction-resolved census of ALL citation
forms (foreign + domestic, neutral + traditional reporter) over a fixed multi-court Canadian corpus
(SCC + ONCA + BCCA)**, with per-row provenance and a quantified undercount ledger?

Interim status: **No such work found.** Details and evidence below. All four buckets (A: Canadian
citation-network studies; B: foreign-citation censuses; C: citation form/typography; D: auditable
extraction with error analysis) are complete, each with an explicit statement of what was NOT found.
All URLs are sources inspected via web search/fetch. Items marked UNVERIFIED could not be confirmed
from the primary source.

---

## 0. The corpus is the A2AJ slice — and A2AJ documents the exact gap

**Confirmed from the project's own artifacts in this workspace.** `data/corpus_manifest.json` records
`"repo": "a2aj/canadian-case-law"` and the downloaded parquet files `corpus/ONCA.parquet` and
`corpus/SCC.parquet` (pulled 2026-08-30, sha256-recorded). `data/audit/counts_v15.json` reports the
local snapshot row counts: **SCC 10,891 rows / 429,822,155 text chars; ONCA 24,089 rows /
365,956,849 chars** (SCC+ONCA = 34,980 rows). BCCA is not in that counts file, so the stated
**49,683-judgment SCC+ONCA+BCCA corpus is an A2AJ three-court target** (BCCA to be added).

A2AJ "Canadian Case Law" HuggingFace dataset row counts (read from the dataset README):

| dataset | court | first–last document | rows |
|---|---|---|---|
| SCC | Supreme Court of Canada | 1877-01-15 – 2026-07-10 | 10,887 |
| ONCA | Ontario Court of Appeal | 1998-06-08 – 2026-07-10 | 23,989 |
| BCCA | British Columbia Court of Appeal | 1999-01-04 – 2026-06-22 | 14,603 |

SCC + ONCA + BCCA = **49,479** in the README snapshot. The project's 49,683 is within ~200 of that
(and the project's own local SCC/ONCA rows already differ from the README by +4 / +100), so the
corpus is **the A2AJ SCC+ONCA+BCCA slice at a slightly different scrape date**. Inference, not a
verified identity — but the provenance chain (manifest → A2AJ repo → A2AJ README) is directly
evidenced.

A2AJ's OWN stated citation-network limitations (verbatim from the dataset card):
- "Extraction is based on **pattern matching of neutral citations only**. Citations using traditional
  reporters (e.g., `[1999] 2 S.C.R. 817`) are **not captured**, so decisions pre-dating neutral
  citations (generally pre-2000) are under-represented in the network."
- "Cited cases are included whether or not they appear in the corpus (e.g., citations to decisions of
  courts we do not cover)" — i.e. **no jurisdiction resolution is performed** on outbound cited cases.
- "Inbound citation data reflects only the corpus."
- "Text extraction artifacts (e.g., OCR or formatting issues) may cause occasional missed or spurious
  citations." — a **qualitative** caveat, with **no quantified error rate**.

A2AJ fields: `cases_cited_en/fr`, `cases_citing_en/fr`, `citing_cases_count`, plus `citation_en`
(neutral) and `citation2_en` (secondary). Code is MIT-licensed. **No published precision/recall and no
error ledger was found in the dataset card or the GitHub repo.**

Sources:
- https://huggingface.co/datasets/a2aj/canadian-case-law
- https://huggingface.co/datasets/a2aj/canadian-case-law/blob/main/README.md
- https://github.com/a2aj-ca/canadian-legal-data

Predecessor: Refugee Law Lab bulk datasets (~185,000 cases; SCC 1877–present ~15,500; FCA 2001–present;
FC 2001–present; TCC 2003–present). https://refugeelab.ca/bulk-data/

---

## 0b. Relationship to this project's own existing gap audit (not prior art, but relevant)

The workspace already contains an internal extraction-layer recall audit, e.g.
`audit/findings/findings_remote.md` and `audit/findings/findings_local.md`, plus
`audit/gap_audit.py` and `data/audit/gap_audit.json`. That internal audit already quantifies one gap
family: `[year] ABBR No. n` (Quicklaw-style, e.g. `[1989] B.C.J. No. 1393`) at **16,124 occurrences /
6,935 decisions** in the SCC+ONCA snapshot, of which strict `[year] X.J. No. n` forms are **10,782**.
`data/audit/counts_v15.json` also carries a whole battery of form-specific occurrence/doc counts
(`scr_dotted_full` 146,175 / `neutral` 49,033 / `or_strict` 29,970 / `ccc_strict` 30,705 /
`dlr_strict` 18,675 / `wwr_strict` 6,126 / `mixedcase_neutral` 4,493, etc.).

**This is the project's own instrument, not external prior art** — but it is worth stating in the
paper that the *approach* (per-form occurrence+document counts as an explicit undercount ledger) has
no external published analogue that I could find. The nearest external analogues are eyecite#304's
hand-validated error taxonomy (43 US opinions) and the EMNLP 2025 UK paper's regex-vs-transformer error
analysis (190 UK judgments). Neither is a multi-court national census, and neither is Canadian.

---

## BUCKET A — Citation-network studies of Canadian courts

### A1. Alschner & St-Hilaire, "Using Network Citation Analysis to Reveal Precedential Archetypes at the Supreme Court of Canada"
- Venue/year: Chapter 3 in *Decoding the Court: Legal Data Insights from the Supreme Court of Canada*,
  eds. Alschner, MacDonnell & Mathen (Routledge, 2024), 15 pp. Open access. DOI 10.4324/9781003279112-5.
- Corpus: **~4,000 SCC decisions, 1983–2021** (post-Charter), full text.
- Source of text: CanLII-derived SCC corpus (book's underlying dataset = metadata on **4,142 SCC
  decisions, 1975–2021**; CanLII licence bars redistribution of full text).
- Extraction: "almost 4,000 decisions" → **>41,000 cross-references** to other SCC cases → trimmed to
  **11,115** constitutional cross-citations → after excluding dissents and negative treatment, **9,295
  cross-references** used. Method: **regex/NLP** on headnote citation-type labels ("Applied",
  "Considered", "Followed", "Referred", "Explained", "Cited", "Adopted"); network analysis in **R +
  igraph**; HITS-style authority scores over yearly network partitions.
- Unit: **case-to-case edge** (citing case → cited case), typed by treatment.
- FOREIGN citations: **No.** Graph is SCC-to-SCC only.
- Jurisdiction of cited case resolved: **N/A** — all nodes are SCC.
- Code/data: chapter is OA; accompanying metadata dataset released; full text not redistributable.
- Its own framing of Neale (see A5): "Thom Neale used network analysis to investigate citations to the
  Supreme Court among all other Canadian citations. While technically advanced and cleverly implemented,
  his analysis focused on the structural and methodological aspects of the network rather than the ebb
  and flow of precedent."
- URLs: https://doi.org/10.4324/9781003279112-5 ;
  https://www.taylorfrancis.com/chapters/oa-edit/10.4324/9781003279112-5/using-network-citation-analysis-reveal-precedential-archetypes-supreme-court-canada-wolfgang-alschner-isabelle-st-hilaire ;
  https://www.routledge.com/Decoding-the-Court-Legal-Data-Insights-from-the-Supreme-Court-of-Canada/Alschner-MacDonnell-Mathen/p/book/9781032245270 ;
  project page https://www.uottawa.ca/faculty-law/common-law/research/centres-research-excellence/legal-tech-lab/decoding-supreme-court-canada

Related chapters in the same volume (relevant, same corpus):
- Ch. 1 "A Bird's-Eye View of the Canadian Supreme Court" (Alschner & MacNeal) — book uses "network
  analysis to create the web of precedents used by the Court", with a full SCC citation network reaching
  back to the 1880s (per the Introduction).
- Ch. 5 "Bilingualism at the Supreme Court of Canada: Quantifying Citations to English, French, and
  Bilingual Doctrinal Sources" (Skolnik & MacNeal) — quantifies the **language of cited doctrinal
  sources**, not citation typography. Closest thing in the volume to a "citation form" study.
- Introduction (OA viewer): https://openresearchlibrary.org/viewer/f7711f3e-00dc-410b-a7ce-5979003b999b

### A2. Neale, "Citation Analysis of Canadian Case Law" (2013)
- Venue/year: *Journal of Open Access to Law* **1**(1), 18 Dec 2013. DOI 10.63567/cm12p629.
- Corpus: **the whole CanLII network of Canadian case law** (all courts/provinces), data supplied by CanLII.
- Method: **statistical/functional analysis + network analysis** (PageRank, in-degree centrality,
  time-series network rankings); Python + NetworkX.
- **CORRECTION — this is more relevant than its abstract suggests.** Per the full text: Neale built his
  own extractor — **594,540 Canadian court opinions**, block quotations detected by headless-Firefox
  paragraph-margin measurement, and a **context-free grammar calibrated to identify 112 different
  strings used in Canadian case-law citations**, handling pinpoint page cites, page ranges, footnote
  cites, subsequent-history cites and **parallel cites**. Result: **1,900,916 citations over 566,992
  nodes; ~40% of nodes resolve directly to CanLII cases; the remaining ~60% are out-of-corpus or
  unofficial reporters (e.g. Criminal Reports).** DOI 10.63567/cm12p629;
  https://ojs.law.cornell.edu/index.php/joal/article/view/20
- **This is the closest existing Canadian precedent for multi-form extraction at national scale** —
  112 citation string forms is a form taxonomy, and the 40%/60% resolution split is an unquantified
  undercount ledger. But **no precision/recall is published**, and the paper is candid:
  "Even if these methods weren't perfectly reliable at determining whether a particular quotation
  originated from an adjacent citation…"; plus an explicit confounding caveat that "the density of
  detected citations per year is determined by at least two unrelated factors. The first is the extent
  of coverage in the collection from which the citations were extracted."
- Unit: **case-to-case edge**.
- Findings: in-degree centrality and PageRank predict CanLII page views; cases typically stop being
  cited in **3–15 years** depending on jurisdiction, except SCC at **~50 years**; ~**19%** of SCC cases
  remain "important"; **<3%** of BCCA/ABCA/ONCA cases remain important; ONCA case "life span" ~6 yrs,
  BCCA ~12 yrs, NWTCA ~16 yrs.
- FOREIGN citations: **No** — Canadian network only.
- Jurisdiction of cited case resolved: cited cases are Canadian court decisions; jurisdiction is
  implicit in CanLII/court metadata, not an analytic output.
- Code/data: notebook and sample data released — https://github.com/twneale/citation-network-analysis ;
  presentation http://twneale.github.io/citation-network-analysis/ ; demo app cite-fight.com.
- Crucial provenance note: Neale did **not** build his own extractor — he used **CanLII's own citation
  data** (i.e., the RefLex citator + CanLII API `citedCases`/`citingCases`). So its recall characteristics
  are RefLex's, not audited in the paper.
- URLs: https://doi.org/10.63567/cm12p629 ;
  https://www.semanticscholar.org/paper/Citation-Analysis-of-Canadian-Case-Law-Neale/7384515485b60aeaf60b4fc100e7ad1c5cba923b ;
  https://www.slaw.ca/2013/09/03/canlii-citation-analysis-available/

### A3. Rehaag / Refugee Law Lab / A2AJ
- **A2AJ (Rehaag, Wallace, McCarten), "A2AJ Canadian Case Law" (2025, updated 2026)** — the bulk corpus
  with the `cases_cited` / `cases_citing` / `citing_cases_count` fields. This is the principal
  *Rehaag-adjacent* citation-network artifact for Canada. See Section 0. **Neutral-citation-only,
  no foreign resolution, no published error rate.**
- **Rehaag, "Claim Types in Canada's Refugee Determination System"** (Refuge: Canada's Journal on
  Refugees, doi 10.25071/1920-7336.41139): 113,000 principal-applicant refugee determinations
  2013–2021 from IRB administrative data via ATI + data-sharing agreement; code in a Code and Data
  Repository. This is **outcome/claim-type** empirics — **not** citation-network analysis. Included here
  to be explicit that Rehaag's flagship quantitative work in this period is not a citation census.
- **Barale et al., "Empowering Refugee Claimants and their Lawyers: Using Machine Learning to Examine
  Decision-Making in Refugee Law"** (arXiv 2308.11531): 59,112 CanLII refugee decisions 1996–2022;
  NER including a `LAW_CASE` label (109 gold annotations for case-law citations) and `LAW` (476) /
  `LAW_REPORT` (18). Relevant as an NLP annotation effort touching Canadian case citations, but
  **not** a citation census and no jurisdiction resolution.
- **No Rehaag/Refugee Law Lab publication was found that performs a jurisdiction-resolved census of
  all citation forms.** Searched: "Rehaag citation network", "Refugee Law Lab citation", "A2AJ
  citation network", "refugee determination precedent citation empirical".

### A4. Bodnar, "A 'Comparative Constitutional Powerhouse' in Action" (2021) — SCC + foreign law
- Author/venue: **Eszter Bodnar**, *UBC Law Review* **54**(2), Article 3 (2021).
- Corpus: **all 1,416 SCC judgments, 2000–2019**; **432 decisions** contained ≥1 reference to
  **foreign (non-international) law** (~30%; range 22.7% in 2011 to 37.5% in 2016, peak >50% in 2007).
- Foreign jurisdictions cited: **62 distinct jurisdictions**, resolved. Most-cited: House of Lords/UKSC,
  Privy Council, SCOTUS, High Court of Australia, Cour de cassation, NZ Supreme Court, South Africa
  Constitutional Court, ECtHR and CJEU (the latter two examined separately as international).
- Method: **MANUAL** — Lexum English search engine, searches on every country name + nationality
  adjective, plus manual scan of every decision's "Cases Cited" and "Statutes and Regulations Cited"
  sections, with manual exclusion of false positives. Unit: **mention/reference**, not typed case-to-case
  edge. Full census of SCC decisions in the window.
- **This is the closest existing thing to a jurisdiction-resolved foreign-citation census for a
  Canadian court** — but: single court (SCC only), foreign-only (no domestic edges), manual, and
  no citation-form/typography dimension.
- URLs: https://commons.allard.ubc.ca/ubclawreview/vol54/iss2/3 ;
  https://commons.allard.ubc.ca/cgi/viewcontent.cgi?article=1007&context=ubclawreview

### A5. Fournier, "Ontario, Listen Up: Citational Practices in the Ontario Court of Appeal"
- Author/venue: **Mireille Fournier** (Laval / Sciences Po), *Canadian Bar Review* vol. 101, no. 3,
  pp. 613–644. SSRN 4973518 (written 2021, posted Nov 2024). DOI 10.2139/ssrn.4973518.
- Corpus/method: counts of decisions by **ONCA, BCCA, ABCA, QCCA** citing sister courts over a **five-year
  window (≈2015–2020 / through 2022)**, percentages computed against each court's total decisions that
  year. Plus a **qualitative deep dive into the 200 longest ONCA decisions of 2021** (≥18 pages) for
  citation of non-Ontario sources.
- Findings: ONCA cites another Canadian appellate court in ~15–16% of its decisions vs ~30% for others;
  BCCA and ABCA cite sister courts 3–4× more often than ONCA; ONCA accounts for ~½ of all US citations by
  provincial courts of appeal; SCC cited ONCA in >50% of its decisions 2015–2020.
- FOREIGN citations: **partially** — the paper asks whether ONCA cites foreign courts and answers
  "not to any significant degree" outside SCC/itself, but **does not enumerate or resolve foreign
  jurisdictions**.
- Jurisdiction of cited case resolved: only as **court of origin at coarse level** (which sister court),
  not per-cited-case jurisdiction with provenance.
- URLs: https://doi.org/10.2139/ssrn.4973518 ; https://sciencespo.hal.science/hal-04357957 ;
  https://cbr.cba.org/index.php/cbr/article/download/4877/4560/5174

### A6. McCormick — the pre-existing Canadian citation-statistics tradition (MANUAL)
- **McCormick, "Judicial Authority and the Provincial Courts of Appeal: A Statistical Investigation of
  Citation Practices"** (1993) 22:2 *Manitoba Law Journal* 286; 1993 CanLIIDocs 136.
  **All 1,402 reported decisions of all ten provincial courts of appeal, calendar year 1987;
  6,213 references to judicial authority.** Authority breakdown includes **U.K. 15.4%**, **U.S. 5.9%**,
  other 13.6%, SCC 26.6%, self 25.6%, other provincial CAs 12.9%. ONCA alone accounted for **half of all
  U.S. citations**. Fully **manual**. Jurisdiction resolved only at court-system level.
  https://www.canlii.org/w/canlii/1993CanLIIDocs136.pdf
- **McCormick, "American Citations and the McLachlin Court: An Empirical Study"** (2009) 47 *Osgoode Hall
  L.J.*; doi 10.60082/2817-5069.1163. **632 SCC decisions, 1 Jan 2000 – 30 Jun 2008; 13,602 citations to
  judicial authority**; foreign citations resolved into English / American (USSC, federal, state) /
  "other countries and supranational tribunals"; includes century-scale trend tables by Chief Justiceship.
  Manual. https://digitalcommons.osgoode.yorku.ca/cgi/viewcontent.cgi?article=1163&context=ohlj
- **McCormick, "The Supreme Court Cites the Supreme Court: Follow-Up Citation on the Supreme Court of
  Canada, 1989–1993"** (1995); doi 10.60082/2817-5069.1643. **All 631 reported SCC decisions 1989–1993;
  4,848 SCC self-references**; decay curve ~15%/yr, half-life just over 4 years. Manual, explicit that
  it is "all reported cases, not a random sample".
- Assessment: McCormick's corpus is **small (single years or ~8 years)**, **manual**, edges are
  **untyped mentions to authority** generally, and foreign jurisdiction is resolved only into broad
  blocks. **No citation-form/typography dimension.**

### A7. Other Canadian citation/network work found
- **Yap & Gammeltoft-Hansen, "Network analysis and comparative migration law: examples from the European
  Court of Human Rights"** (2023) *Int. J. Migration and Border Studies*, doi 10.1504/ijmbs.2023.128598 —
  ECtHR, 3,273 migration cases with 4,613 edges; includes an explicit call to identify "implicit
  citation through repetition of legal arguments without explicit reference." Not Canadian; methodologically
  relevant to "what we undercount."
- **SCC leave-prediction and ML work** (Veel & Glowach, Ch. 6 of *Decoding the Court*; Alarie & Green) —
  institutional, not citation network.
- **CanLII's own infrastructure**: **RefLex citator** and the **CanLII API** (`caseCitator` endpoint
  returns `citedCases` / `citingCases` / `citedLegislations`). This is the de facto production Canadian
  citation graph. https://www.canlii.org/en/info/reflex.html ;
  https://github.com/canlii/API_documentation/blob/master/EN.md

### A8. Rado — the most complete existing jurisdiction-resolved SCC foreign-citation census
- **Klodian Rado, "The Transnational Judicial Dialogue of the Supreme Court of Canada and its Impact"**
  (PhD dissertation, Osgoode Hall Law School, York University, June 2018).
  https://digitalcommons.osgoode.yorku.ca/phd/40
- **All 1,223 SCC judgments, 1 Jan 2000 – 31 Dec 2016** (all four non-domestic source categories:
  foreign case law; foreign constitutions/statutes/regulations; international case law; international
  treaties).
- Method: **fully MANUAL, case-by-case.** Verbatim from the thesis: "all 1,223 decisions had to be
  reviewed on a case-by-case basis to identify all citations of foreign and international courts...
  all **24,509 cases** (19,492 in majority decisions and 5,017 in dissents) cited during the 17-year
  period had to be checked. Then **all non-Canadian cases had to be identified, matched with the
  appropriate jurisdiction** (foreign national court or international), and then divided according to
  their domestic jurisdictions (highest court or lower court)." Similarly 5,647 statutes/regulations
  manually reviewed and matched to jurisdiction.
- 21 justices classified as high-globalist / moderate-globalist / localist; finding of declining
  foreign citation ("slowbalization").
- Journal version: **Rado, "The use of non-domestic legal sources in Supreme Court of Canada judgments:
  Is this the judicial slowbalization of the court?"** (2020) 16(1) *Utrecht Law Review* 57–85,
  doi 10.36633/ulr.584. Related: "The Judicial Diplomacy of the Supreme Court of Canada and its Impact:
  An Empirical Overview", doi 10.29173/alr2606.
- **This is the single most complete existing foreign-citation census for a Canadian court, and it
  resolves cited-case jurisdiction — but it is SCC-only, foreign-only, manual, reports no per-citation
  provenance table, has no domestic edge graph, no citation-form dimension, and no released extraction
  code.** Rado's own methodology note is also an admission of the labour cost that an automated,
  audited pipeline would remove.

### Bucket A — explicit negatives
- **No ONCA-specific or BCCA-specific citation-*network* study (case-to-case graph) was found.** What
  exists for ONCA/BCCA is: per-year citing-court percentages (Fournier 2024), one-year all-CA reference
  counts (McCormick 1993), CanLII-wide rankings (Neale 2013), and A2AJ's neutral-citation graph.
- **No Canadian study found that includes foreign citations inside a case-to-case citation network with
  resolved cited-case jurisdiction.** Foreign-citation work (Bodnar; the Osgoode thesis) is SCC-only,
  manual, and treats foreign references as counts, not as resolved nodes in a graph.
- **No Canadian study found that censuses all citation FORMS** (neutral vs reporter vs parallel) as its
  object of measurement. See Bucket C.

---

## BUCKET B — Empirical censuses of foreign-law / foreign-court citations

### B0. THE TWO MOST IMPORTANT COMPETITIVE HITS (automated + jurisdiction-resolved)

**B0a. ECCN — "The European Constitutional Court Network" (Kirchmair & Lechner).**
- Lando Kirchmair (Salzburg / Bundeswehr Munich) & Lisa Lechner (Innsbruck).
- **FULLY AUTOMATED.** Corpus: decisions of the **CJEU, the ECtHR and 19 national European
  constitutional courts**; "the earliest decisions in our dataset stem from the early 1950s";
  multilingual. Method: web-scraping in R; **direct citation network detected with "thousands of
  regular expressions"**; **indirect/semantic citation network via word embeddings + ML across
  languages**; inferential network analysis.
- **OPEN DATA**: Lechner & Kirchmair, "European Constitutional Court Network Data (OA edition)",
  AUSSDA, **doi 10.11587/AYUJTC**. Project site https://eccn.at/
- Findings: exponential rise in intra-European constitutional-court citations since 2000; vertical
  (ECtHR/CJEU) citations far exceed horizontal; the ECtHR has "constitutional authority" (cited
  regardless of jurisdiction); the German FCC is by far the most-cited national court; few genuine
  pan-European leading cases.
- Book: Kirchmair & Lechner (eds), *Citation Networks of European Constitutional Courts: Asymmetric
  Judicial Dialogues*, Routledge Research in Constitutional Law, 3 Aug 2026, ISBN 9781032723921,
  **doi 10.4324/9781032723914**.
- **Assessment: this is JURISDICTION-RESOLVED BY CONSTRUCTION (every edge is court→court), CENSUS-SCALE,
  and AUTOMATED — the single best existing artefact for the "jurisdiction-resolved census" question.**
  But the unit is citations **between constitutional courts** (+ CJEU/ECtHR); it is **not** general
  court-to-court citation, has **no citation-form/typography dimension**, and has **no Canadian content**.

**B0b. Hoadley et al. 2021, "A Global Community of Courts?" — 1.56M judgments, 26 common-law systems.**
- Hoadley, Bartolo, Chesterman, Faus, Hernandez, Kultys, Moore, Nemsic, Roche, Shangguan, Steer,
  Tylinski, West, *Frontiers in Physics* **9**:665719 (2021), **doi 10.3389/fphy.2021.665719**.
- **FULLY AUTOMATED**: citations identified by **vLex Justis's proprietary rules-based engine**, with
  ambiguous/malformed references resolved and reconciled to unique case entities via a
  **parallel-citation database**. Corpus: **1,559,807 judgments** from senior/appellate courts of
  **26 common-law systems, 1717–2020**; **853,287 unique cited judgments**; complete directed
  case-to-case network; the cross-jurisdictional network separates domestic from foreign citations.
- **BOTH citing and cited country are resolved**: Table 1 gives per-country outward/inward counts
  (e.g. UK 10,928 foreign cases cited; 313,111 UK cases cited by others). Findings: UK most-cited;
  Australia the most prolific user by volume; **US relatively isolationist**; upward trend from the
  1990s; geographic proximity matters.
- **Assessment — flag this as the most important competitive check for the Canadian project.**
  A 26-common-law-system list almost certainly **includes Canada**, so a jurisdiction-resolved
  cross-citation graph over Canadian courts may already exist in the vLex Justis-derived network.
  **UNVERIFIED: whether Canada is one of the 26 systems, and whether SCC/ONCA/BCCA are separately
  resolved.** Limits even if so: a **commercial-database subset of "senior courts"** (not a census of
  every decision), **foreign CASE citations only** (no statutes/scholarship), **no citation-form or
  reporter-vs-neutral dimension**, **proprietary extraction with no published precision/recall**, and
  no per-row provenance.

**B0c. Sargeant, Östling & Magnusson (EMNLP 2025)** — see Bucket D. The **only** located paper that
treats **UK vs non-UK citations as an explicit classification target**: gold corpus of 190 judgments /
45,179 fine-grained annotations for UK and non-UK legislation and case references. A methods paper, not
a census — but it is directly the extraction tool a foreign-citation census would need.

### B1. Confirmation of the three items supplied in the brief
- **Gelter & Siems**, "Citations to Foreign Courts — Illegitimate and Superfluous, or Unavoidable?
  Evidence from Europe", *AJCL* **62**(1) 2014, 35–85, doi 10.5131/ajcl.2013.0012 — **CONFIRMED**.
  **10 European supreme courts, 1,430 cross-citations, 2000–2007.** Method: **manual** reading/
  compilation of "the full text of (almost) all decisions" in civil and criminal law — so effectively
  a census of the accessible reported output for those years. Project hub with data:
  http://cross-citations.blogspot.com/ . Earlier WP: "Networks, Dialogue or One-Way Traffic?…",
  M-EPLI WP 2011/03, SSRN 1722721.
- **D'Andrea, Divissenko, Fanou, Krisztián, Kukavica, Potocka-Sionek & Siems**, "Asymmetric
  cross-citations in private law: An empirical study of 28 supreme courts in the EU", *MJECL* **28**(4)
  2021, 498–534, doi 10.1177/1023263X211014693 — **CONFIRMED**. **28 supreme courts, 2,984
  cross-citations, 2000–2018.** Method: **manual.** **Dataset publicly posted**:
  https://cross-citations.blogspot.com/p/2021-project.html
- **Arcioni & McLeod**, "Cautious But Engaged — An Empirical Study of the Australian High Court's Use of
  Foreign and International Materials in Constitutional Cases", *Int'l J. Legal Information* **42**(3)
  Winter 2014, 437–470, doi 10.1017/S0731126500012178 — **CONFIRMED** as to authorship/venue;
  **counts and corpus size UNVERIFIED** (paywalled; the abstract says only that it "track[s] the
  frequency of citation in constitutional cases").

### B2. Per-court studies that DO resolve the cited jurisdiction

**UK Supreme Court / House of Lords**
- **Hélène Tyrrell, *Human Rights in the UK and the Influence of Foreign Jurisprudence* (Hart 2018)** —
  **TRUE CENSUS: all 533 UKSC cases in its first 8 years (2009–2017); 157 (~29.6%) contain explicit
  citations of foreign domestic jurisprudence.** **Per-jurisdiction breakdown resolved**: Australia 54%,
  US 47%, Canada 45% of the cases citing foreign jurisprudence; plus civil/common/mixed-law breakdown by
  year and per-justice attribution. **MANUAL** + interviews with 10 Justices.
- Frosini, "A Protagonist of Comparative Constitutional Law?…", doi 10.1436/96626 — quantitative analysis
  of UKSC case law 1 Jan 2016 – 11 Apr 2017; counts foreign judgments, foreign statutes, foreign
  scholarship; excludes ECHR/EU/international materials. MANUAL census of that window.
- Stanton, "Comparative law in the House of Lords and Supreme Court" (2013) 42(3) *Common Law World
  Review* 269 — details UNVERIFIED.
- Mak, "Reference to Foreign Law in the Supreme Courts of Britain and the Netherlands" — **interview-based,
  not a citation census.**

**South Africa (Constitutional Court)**
- **Rautenbach**, "South Africa: Teaching an 'Old Dog' New Tricks?… (1995–2010)", in Groppi & Ponthoreau
  (2013) ch. 7, 185–209, doi 10.5040/9781472561312.ch-007 — **CENSUS 1995–2010: foreign precedents cited
  in more than half of ~400 judgments; ~3,000 foreign court decisions cited by 2010** plus hundreds of
  transnational/Privy Council citations; **per-cited-jurisdiction counts**. MANUAL.
- Rautenbach, "The Use of Foreign Precedents by the South African Constitutional Court Judges: Has
  Anything Changed?", in *Judicial Bricolage* (Hart 2025) 191–204 — **CENSUS 2011–2021: ~500 decisions,
  foreign case law cited/discussed in ~a quarter.** MANUAL.
- Seedorf, "Foreign Law and Foreign Legal Culture in the South African Constitutional Court",
  *Constitutional Court Review* (2025), doi 10.2989/CCR.2025.0012 — qualitative/historical, reports the above.

**Germany (Bundesverfassungsgericht)**
- **Martini, *Vergleichende Verfassungsrechtsprechung* (Duncker & Humblot 2018)**, doi
  10.3790/978-3-428-55271-9 — the **first six decades of the BVerfG** analysed quantitatively and
  qualitatively against the official *Entscheidungssammlung*, plus South Africa as contrast. Finding:
  the BVerfG argues comparatively in **~1 in every 20 decisions**; initial surge, decline, rise since
  2000 driven by CJEU/ECtHR citations. MANUAL; corpus = **published decision collection, not the full
  docket**.
- Tischbirek, "Unrequited Love or Secret Passion?…", in the ECCN volume, doi 10.4324/9781032723914-6 —
  uses the **ECCN dataset (AUTOMATED)**. Finding: the GFCC rarely cites other national constitutional
  courts, and cites the CJEU more than the ECtHR (Germany is the only such court).

**Israel (Supreme Court)**
- **Shachar, Harris & Gross, "Citation Practices of Israel's Supreme Court: Quantitative Analysis",
  27 *Mishpatim* 119–217 (1996)** (Hebrew) — 1948–1994; 7,147 SC rulings published in PADI volumes =
  **RANDOM SAMPLE**. **Resolves cited-source jurisdiction**: British 24.4% (1948) → 2.3% (1994);
  US 0% → 5.1%; US overtakes UK 1982–83. MANUAL.
- **Zemer & Pardo, "European Union Law as Foreign Law", 54 *Vand. J. Transnat'l L.* 677 (2021)** —
  **full census of ALL Israeli SC rulings referencing EU-law normative sources, 1948–2016** (Nevo
  database → **74 cases, 153 references**). Manual citation analysis by 2 PIs + RAs. Explicitly contrasts
  itself with Shachar/Harris/Gross (sample) and Navot.
- Navot, "Israel: Creating a Constitution… (1994–2010)", Groppi & Ponthoreau (2013) ch. 5 — based on
  PADI volumes + a digital database; **SAMPLE, not full census**.
- Morag-Levine & Bean, "Foreign Precedents and the Global Canon" (2012) — database of **ALL non-domestic
  cases cited in constitutional decisions of Israel and Hong Kong**, with cited jurisdiction resolved.
- Hirschl, "Judicial Review and the Politics of Comparative Citations" (2018) — case-level counts only
  (e.g. Citizenship Law case: 63 foreign constitutional-case references, 92% in dissent). Not a census.

**New Zealand**
- **Allan, Huscroft & Lynch, "The Citation of Overseas Authority in Rights Litigation in New Zealand:
  How Much Bark? How Much Bite?" (2007) 11 *Otago Law Review* 433** — **CENSUS of all REPORTED High
  Court, Court of Appeal and Supreme Court cases from NZBORA enactment to April 2006 referencing an
  overseas rights-based precedent; 75 SC/CA cases.** **Cited jurisdiction resolved** (Canada > US > UK;
  Germany/India/Ireland rare); also ECtHR, UNHRC. MANUAL.
  https://www.nzlii.org/nz/journals/OtaLawRw/2007/7.html
- Butler, "The Use of Foreign Jurisprudence in New Zealand Courts" (2011) — NZSC and, less so, NZCA over
  six years; corpus size UNVERIFIED.
- **Smyth, "Judicial Citations — an Empirical Study of Citation Practice in the New Zealand Court of
  Appeal" (2000) 31 *VUWLR* 849**, doi 10.26686/vuwlr.v31i4.5929 — **SAMPLE of 300 CA cases 1995–1999**;
  **17.9%** of citations to courts outside NZ/England, with **country breakdown resolved**
  (Australia/Canada/US ≈95% of those; 8 countries total). MANUAL. (Bucket B's sub-audit lists the author
  as UNVERIFIED; my own search retrieved **Russell Smyth** — I regard that as the correct attribution.)

**Ireland**
- Fasone, "The Supreme Court of Ireland and the Use of Foreign Precedents…", Groppi & Ponthoreau (2013)
  ch. 4 — MANUAL. Update: Fasone in *Judicial Bricolage* (2025) ch. 4 — MANUAL.

**India**
- Scotti in Groppi & Ponthoreau (2013) ch. 3; Vergnes in *Judicial Bricolage* (2025) ch. 3 — MANUAL.
- Smith, "Making Itself at Home… The Indian Case", 24 *Berkeley J. Int'l L.* 218 (2006) — **doctrinal
  with some empirical analysis; NOT a census.**
- **No jurisdiction-resolved census of Indian SC foreign citations was located.**

**United States**
- **Zaring, "The Use of Foreign Decisions by Federal Courts: An Empirical Analysis", 3 *J. Empirical
  Legal Studies* 297 (2006)**, doi 10.1111/j.1740-1461.2006.00071.x — 60 years of federal practice citing
  **foreign HIGH COURT** opinions, by citation-count analysis; jurisdiction resolved at foreign-high-court
  level. **Whether every federal decision 1945–2005 was screened is UNVERIFIED.** MANUAL.
- Sperti in Groppi & Ponthoreau (2013) ch. 16; Bizzari & Sperti in *Judicial Bricolage* (2025) ch. 31.
- Simon, "The Supreme Court's Use of Foreign Law in Constitutional Rights Cases" (2013) 1(2)
  *Journal of Law and Courts* 279 — details/method UNVERIFIED.
- Lefler, "A Comparison of Comparison…", 11 *S. Cal. Interdisc. L.J.* 165 (2001) — manual count, 3 courts
  (USSC, SCC, HCA).
- Parrish, "Storm in a Teacup", 2007 *U. Ill. L. Rev.* 637 — doctrinal.

**Australia**
- Spottiswood, "The Use of Foreign Law by the High Court of Australia", 46(2) *Federal Law Review*
  (2018), doi 10.1177/0067205X1804600201 — close analysis of HCA decisions 2015–2016; small-N, not a census.
- **"Patterns of Use: Foreign Cases in High Court Judicial Review Judgments from 1980 to 2018"**,
  doi 10.26180/5e151fc32e00b — **SAMPLE: 246 judicial-review judgments; 99 used foreign cases;
  1,110 foreign cases used.** **Jurisdiction of cited cases resolved** (UK/US dominant). MANUAL.
- Arcioni & Gordon, "An Ongoing Engagement: The Australian High Court and Foreign Case Law", *Judicial
  Bricolage* (2025) ch. 1. Note: Groppi et al. 2025 report Australia is the exception to the post-2011
  decline.

**Canada (beyond the items in Bucket A)**
- **Rado 2020 / Osgoode PhD 2018** — see **A8**. Confirmed as the most granular manual resolution found:
  all 1,223 SCC judgments 2000–2016; **all 24,509 cited cases checked and each non-Canadian case MATCHED
  TO ITS JURISDICTION** (foreign national vs international; highest vs lower court); all 5,647
  statutes/regulations likewise jurisdiction-matched; per-justice breakdown (21 justices; high/moderate
  globalist vs localist). The thesis also documents excluding **UK cases pre-1949 (pre-1933 criminal) as
  non-foreign** and treating the House of Lords + UKSC as one court.
- **Gentili**, "Enhancing Constitutional Self-Understanding Through Comparative Law: An Empirical Study
  of the Use of Foreign Case Law by the Supreme Court of Canada (1982–2013)", SSRN 2672575 / in Andenas &
  Fairgrieve (eds), *Courts and Comparative Law* (OUP 2015) — quantitative + qualitative, 1982–2013.
- **Gentili**, "Canada: Protecting Rights in a 'Worldwide Rights Culture'… (1982–2010)", in Groppi &
  Ponthoreau (2013) ch. 2, 39–68.
- **Bodnár 2021** — see **A4**.
- Brun, "Turbulent Resistance in the Supreme Court of Canada…", *Judicial Bricolage* (2025) ch. 2 — notes
  an increase in 2020–22 after *Québec inc.* (2020). MANUAL.

### B3. Cross-jurisdiction manual projects (multi-court, per-cited-jurisdiction counts)
- **Groppi & Ponthoreau (eds), *The Use of Foreign Precedents by Constitutional Judges* (Hart 2013)** —
  **16 jurisdictions** (Australia, Canada, India, Ireland, Israel, Namibia, South Africa, Austria,
  Germany, Hungary, Japan, Mexico, Romania, Russia, Taiwan, US); ECJ/ECtHR deliberately excluded.
  Quantitative + qualitative with a common questionnaire across reporters. Per the *I-CON* review, each
  report gives "the total number of citations (**and the numbers according to the cited jurisdictions**)",
  the split human-rights vs institutional cases, and majority vs minority — i.e. **cited jurisdiction IS
  resolved at country level. MANUAL.** doi 10.1093/icon/mou010
- **Groppi, Ponthoreau & Spigno (eds), *Judicial Bricolage: The Use of Foreign Precedents by
  Constitutional Judges in the 21st Century* (Hart 2025, ISBN 9781509973996)** — **31 jurisdictions,
  period 2011–2021**, quantitative + qualitative with tables/data. MANUAL.
  https://www.bloomsbury.com/au/judicial-bricolage-9781509974030/
- **Jakab, Dyevre & Itzcovich (eds), *Comparative Constitutional Reasoning* (CUP 2017)**,
  doi 10.1017/9781316084281 — 18 courts incl. ECJ & ECtHR; **40 "leading judgments" per court** coded by
  37 yes/no questions incl. "is there a reference to foreign law in this judgment?". **SAMPLE of canon,
  not a census; cited foreign law jurisdiction NOT resolved.**
- **Siems project follow-ons** (same 28-court dataset as D'Andrea et al.): (i) de Witte, Krisztián,
  Kukavica, Potocka-Sionek, Siems & Yiatrou, "Decoding Judicial Cross-Citations: How Do European Judges
  Engage with Foreign Case Law?", *AJCL* (forthcoming), doi 10.1093/ajcl/avae021, SSRN 4301900;
  (ii) Siems, "A Network Analysis of Judicial Cross-Citations in Europe", *Law & Social Inquiry*,
  doi 10.1017/lsi.2022.22, SSRN 4255083; (iii) Kukavica, *Ljubljana Law Review* 82 (2022) 69–96.
  All **MANUAL** extraction from the shared dataset.
- Law & Chang, "The Limits of Global Judicial Dialogue", 86 *Wash. L. Rev.* 523 (2011) — statistical
  analysis of citations to foreign law in Taiwan Constitutional Court published opinions + interviews;
  "statistical analysis" = **MANUAL coding**; corpus size UNVERIFIED; single court.
- Law, "Judicial Comparativism and Judicial Diplomacy", 163 *U. Pa. L. Rev.* 927 (2015) — Japan, Korea,
  Taiwan, Hong Kong; details UNVERIFIED.

### B4. International courts (ECtHR, CJEU) — note: mostly self-citation, not foreign law
- **Lupu & Voeten, "Precedent in International Courts…", *BJPS* 42(2) (2012)** — **CENSUS: all 7,319
  ECtHR cases decided up to and including 2006; 35,963 citations to prior ECtHR decisions.**
  **AUTOMATED** extraction from HUDOC + network analysis. **Self-citations.**
  https://yonatanlupu.com/LupuVoeten.pdf
- Voeten, "Borrowing and Nonborrowing among International Courts", 39(2) *J. Legal Studies* (2010),
  doi 10.1086/652460 — ECtHR rarely cites other courts in judgments, though individual judges do in
  separate opinions.
- **Esmark, Olsen, Larsen & Byrne, "Adjudicating national contexts…", *German Law Journal* 23(4) (2022)
  465–492, doi 10.1017/glj.2022.29** — **CENSUS: ALL Chamber judgments 1998–2018; 48,791 citations from
  5,399 cases to 20,748 paragraphs**; case-to-paragraph network from HUDOC; **respondent state resolved
  per node**; qualitative step read 2,369 citations manually. **HYBRID.** Self-citations.
- "Context-Aware Citation Networks" (JURIX 2025) — ECHR citation-context datasets: human-annotated
  (115 cases) + AI-annotated (300 judgments, GPT-4o) with complaint and judicial-consideration labels.
  https://livrepository.liverpool.ac.uk/3195643/1/JURIX_2025___ECHR_Annotation_Paper.pdf
- Farahat, "Enhancing Constitutional Justice by Using External References…", *LJIL* 28(2) (2015) 303–322,
  doi 10.1017/S0922156515000096 — scope/method UNVERIFIED.
- **Fjelstul, "The CJEU Database Platform", *Journal of Law and Courts*, doi 10.1017/jlc.2022.14** —
  **supervised, AUTOMATED compilation of the UNIVERSE of CJEU cases/decisions/judges 1952–present**,
  including a citations dataset (one observation per citation per decision; cited document + type).
  Covers case law/treaties/legislation — **NOT foreign national law.**
- "Court of Justice of the EU case citations and full texts" (Maastricht University dataset) — citation
  network + full texts of all CJEU judgments on EUR-Lex up to Dec 2018.
- "Automated Extraction and Representation of Citation Network: A CJEU Case-Study" (2022),
  doi 10.1007/978-3-031-22036-4_10 — regex + EUR-Lex XML pipeline; CJEU self-citations. AUTOMATED.
- Iannone, "Comparative Law in the Practice of the Court of Justice", SSRN 4748352 — **doctrinal.**

### B5. Automated (regex/ML/NLP) extraction — explicit method labelling
- **ECCN** — AUTOMATED, jurisdiction-resolved by construction (see B0a).
- **Hoadley et al. 2021** — AUTOMATED via a proprietary rules-based engine, both endpoints' country
  resolved (see B0b).
- **Sargeant, Östling & Magnusson 2025** — AUTOMATED classifier, UK vs non-UK as an explicit label
  (see B0c and D4/D3).
- **BO-ECLI Parser (2017)**, doi 10.3233/978-1-61499-838-9-113 — open multilingual framework for
  automatic extraction of legal references from EU member-state case law; national extensions for Italy
  and Spain. **Infrastructure, not a census.**
- **"Extracting References from German Legal Texts Using NER" (2022)**, doi 10.3233/faia220472 —
  regex/CRF/BiLSTM/BERT for German law and court-decision citations; best BERT F1 ≈0.98 (law) / 0.96
  (decisions). AUTOMATED; extraction only.
- **A2AJ Canadian Case Law** — automated neutral-citation pattern matching (see Section 0).
- **"From Judgments to Issues" (2026), arXiv 2607.03325** — LLM + Linkoln parser with hallucination
  filtering over ~330,000 Italian tax-court judgments; resolution to URN-NIR/ECLI/CELEX. National, not
  foreign-law. (See D10 for its validation design.)

### Bucket B — explicit negative finding
**Does a jurisdiction-resolved CENSUS of foreign citations exist anywhere? On this evidence: NO — not as
a single artefact covering "foreign law" as such, and none for Canada.**
- **True census + jurisdiction-resolved: only for SINGLE courts, and MANUAL.** Tyrrell 2018 (UKSC, 533
  cases, 2009–17, per-cited-jurisdiction); **Rado 2020 (SCC, 1,223 judgments, 2000–16, per-cited-case
  jurisdiction and court level — the most granular manual resolution found, requiring review of all
  24,509 cited cases)**; Allan/Huscroft/Lynch 2007 (NZ reported rights cases); Shachar/Harris/Gross 1996
  (Israeli SC, but a **sample**); Zemer & Pardo 2021 (Israeli SC, census of **EU-referencing rulings only**).
- **True census + AUTOMATED + jurisdiction-resolved: ECCN and Hoadley et al. 2021.** Neither is framed as
  a census of "foreign-law references": ECCN covers only **constitutional courts' citations to each other
  and to the CJEU/ECtHR**; Hoadley et al. depend on a **commercial corpus** and count **foreign case
  citations only**.
- **Multi-court + jurisdiction-resolved at country level but MANUAL and of varying completeness**:
  Groppi & Ponthoreau 2013 (16 courts) and Groppi/Ponthoreau/Spigno 2025 (31 courts, 2011–2021). **No
  evidence located that these resolve cited-case IDENTITY systematically.**
- **No automated study was found that both (i) detects non-domestic law references specifically and
  (ii) publishes a jurisdiction-resolved census across courts.** Sargeant et al. 2025 supplies the
  classifier for UK/non-UK references but only over 190 judgments.
- **No foreign-citation census of any kind was found for ONCA or BCCA.** Every Canadian foreign-citation
  study located is SCC-only.

**UNVERIFIED in Bucket B**: corpus sizes for Arcioni & McLeod 2014, Frosini, Butler 2011, Law & Chang,
and the exact method/corpus of Simon 2013, Voeten 2010, Farahat 2015. Book-chapter counts for Groppi &
Ponthoreau 2013, *Judicial Bricolage* 2025, Martini 2013/2018 and Tyrrell 2018 rest on abstracts and
reviews, not the chapter texts. **Most consequential open item: whether Canada (and specifically
SCC/ONCA/BCCA) is among Hoadley et al.'s 26 common-law systems.**

---

## BUCKET C — Quantifying citation FORM / typography over time

### C1. Canadian neutral-citation adoption timeline (needed as the ground truth for any form census)
Source: Canadian Citation Committee / Lexum, "A Neutral Citation Standard for Case Law"
https://www.lexum.com/ccc-ccr/neutr/index_en.html (page last updated Feb 2007). First decision bearing
each court's neutral core:

| Court | First month applied | First neutral-cited decision |
|---|---|---|
| **BCCA** | **January 1999** | *R v Giles*, 1999 BCCA 0003 |
| NSCA | September 1999 | *Martini v Wrathall*, 1999 NSCA 105 |
| **SCC** | **January 2000** | *Arsenault-Cameron v PEI*, 2000 SCC 1 |
| FCA / FC | February 2001 | *Bouvidard Ltée v Canada (EI Commission)*, 2001 FCA 1 |
| ABCA (earliest of all) | January 1998 | *R v Siemens*, 1998 ABCA 1 |
| QCCA | January 2005 | *Ghanotakis c Clot & Associés*, 2005 QCCA 1 |
| **ONCA** | **January 2007** | *Atec Marketing Ltd v Heart and Stroke Foundation of Canada*, 2007 ONCA 1 |
| ONSC | January 2010 | *R v Andrew Del Riccio*, 2010 ONSC 1 |

**This is a major design fact for the proposed project**: within the 49,683-judgment SCC/ONCA/BCCA
corpus, the three courts adopted neutral citation **8 years apart (BCCA 1999, SCC 2000, ONCA 2007)**, and
A2AJ's extraction is neutral-citation-only — so the post-1999/2000/2007 window differs by court, and the
pre-2007 ONCA and pre-1999 BCCA text is systematically invisible to the existing graph. The A2AJ README
concedes under-representation but does not quantify it.

### C2. Lexum/CanLII RefLex (2005) — the one place I found citation-form frequency measured over time
- **"Reflex – Bridging Open Access with a Legacy Legal Information System"** (Lexum, ~2005),
  https://lexum.com/wp-content/uploads/2016/10/2005-reflex-lexum.pdf
- States that "Reflex's databases can be used to identify **the frequency of citation of three leading
  Canadian law reports and neutral citation** during CanLII's first five years," with **Figure 1**
  showing growth in neutral-citation use; reports that neutral citation "is catching up to the frequency
  of use of the leading law reports" and "already far surpasses that of the leading law reports, except
  for that of the Supreme Court and the Canadian Criminal Cases series." Neutral citation counted only
  when it appears alone or in first position.
- Method: **regex** detection over "citations of several hundred law reports," plus a citation-compilation
  database and similarity-scored parallel-citation linking, with human editor intervention on low-similarity
  pairs.
- **Limitations for our purposes**: it is a system/methodology paper, not a published empirical census of
  citation forms; the figure covers CanLII's first five years only; it is not per-court
  (SCC/ONCA/BCCA), not per-decision with provenance, and **no precision/recall is reported**. But it
  establishes that the neutral-vs-reporter form question has been *operationalised* in Canada before.
- RefLex also confirms **parallel-citation linking is a core production problem**: "Reflex uses this data
  to find parallel citations associated with a cited decision... RefLex thus 'learns' new citations over
  time." https://www.canlii.org/en/info/reflex.html'
- CanLII citation-format rules for reporters and hierarchies of preferred reporters:
  https://www.legalbluebook.com/bluebook/v21/tables/t2-foreign-jurisdictions/t2-6-canada ;
  https://trulibrarymcgill.wordpress.com/general-form/
- ONCA's own practice direction encourages but does not require parallel citation:
  https://www.ontariocourts.ca/coa/how-to-proceed-court/practice-directions-guidelines/reference-guide-citation/

### C3. Adjacent "citation style over time" work (not form/typography, but measured style drift)
- **Fronk, "The Cost of Judicial Citation: An Empirical Investigation of Citation Practices in the
  Federal Appellate Courts"** (2010) *Journal of Law, Technology & Policy* —
  https://illinoisjltp.com/file/84/Fronk.pdf. 1,200 U.S. Circuit opinions, 1957–2007 in ten-year
  intervals + 688 opinions by two long-serving judges. Measures **string-citation share** (declined from
  >24% in 1957 to 8% in 2007) and depth of engagement, not citation *format*.
- **Cross & Spriggs?, "Citations in the U.S. Supreme Court: An Empirical Study of Their Use and
  Significance"** (2010) *U. Ill. L. Rev.* — citation counts + network centrality (segmentation of the
  citation). https://illinoislawreview.org/wp-content/ilr-content/articles/2010/2/Cross.pdf
- **Martin, "Neutral Citation, Court Web Sites, and Access to Case Law"** (2007, Cornell LSRP) —
  https://scholarship.law.cornell.edu/lsrp_papers/70. **Doctrinal/historical**, describes the ABA 1996
  resolution and its transitional "strongly encourage parallel citations" provision, and documents that
  most neutral-citation adopters *required* parallel citation to print reports. **No measurement.**
- **"Checking Up on Court Citation Standards: How Neutral Citation Improves Public Access to Case Law"**
  (2012) *Legal Reference Services Quarterly*, doi 10.1080/0270319X.2012.741036 — history/rationale
  of neutral citation; **not empirical**.
- **Smyth, "Judicial Citations — An Empirical Study of Citation Practice in the New Zealand Court of
  Appeal"** (2000) 31 *VUWLR* 849, doi 10.26686/vuwlr.v31i4.5929 — **VERIFIED**. Sample of the **300 most
  recent NZCA decisions reported in NZLR as of Dec 1999** (i.e. 1995–1999); **manual** counting of every
  case-law and secondary-authority citation; statutes/regulations excluded. Resolves cited authority to:
  own prior decisions 33%, all NZ courts 46%, English courts 27% (23% excluding Privy Council),
  **courts in countries other than NZ and England 18%**, secondary authorities 8–9%. Also reports
  comparative figures: **High Court of Australia 5.4%** and **Supreme Court of Canada 4.9%** non-domestic.
  - Relevance: **sample, not a census**; pre-dates NZ's 2001–2004 neutral-citation adoption, so it
    cannot speak to citation form.
  - URLs: https://doi.org/10.26686/vuwlr.v31i4.5929 ;
    https://ojs.victoria.ac.nz/vuwlr/article/download/5929/5200/8280

### C4. Mokanov, "Environmentally-Friendly Citations" (2010) — THE closest existing Canadian form measurement
- Ivan Mokanov (then Deputy Director, LexUM), *VoxPopuLII* (Cornell LII blog), 1 March 2010.
  https://blog.law.cornell.edu/voxpop/2010/03/01/environmentally-friendly-citations
- Two datasets drawn from CanLII's **RefLex** citator: **~40,000 citations** (citing cases released 2008;
  cited cases 2006–08) and **~41,000 citations** (citing 2009; cited 2007–09).
- Method: **automated citator link resolution** (not manual, not ML form classification).
- **THE NUMBERS**: dataset 1 — **85%** of hyperlinked citations are, or contain, a neutral citation;
  **68% of all citations** are or contain a neutral citation. Dataset 2 — **91%** hyperlinked;
  **73% of all**. CanLII citation-resolution success rate ~**80%**. All 50 Canadian courts were on the
  neutral standard by 2010.
- **Limits that matter for the proposed project**: only two adjacent time windows (2006–08 and 2007–09);
  **no pre-1999 baseline**; a **blog post**, not peer-reviewed, with no methods appendix; the phrase
  "are or contain" **conflates pure neutral citation with parallel (neutral + reporter) strings**, so it
  cannot separate the two; no per-court breakdown; no code or data released.
- **Verdict: this is the nearest existing precedent for a citation-FORM measurement in Canada, and it is
  a blog post with two adjacent windows.** It leaves the per-court, multi-decade, reporter-disaggregated
  form census unbuilt.

### C5. Clinch, "The Use of Authority: Citation Patterns in the English Courts" (1990) — the only true reporter-title frequency distribution
- Peter Clinch, *Journal of Documentation* **46**(4): 287–317 (1990). doi 10.1108/eb026862.
  Full text viewed via https://vlex.co.uk/vid/the-use-of-authority-846697922
- Corpus: **all issues of 58 different law-report titles published during 1985**; 5,260 versions of
  **2,451 unique cases**; **25,868 citations**, reduced to **11,159** by keeping only the longest version
  of each case. England & Wales. **Manual** extraction and coding.
- Measures: proportion of citations to each of 24 material types; **"the law report titles from which
  cited cases were taken"**; use of unreported cases; **jurisdiction of cited cases**; self-citation;
  ageing of authority; counsel-vs-judgment citation.
- **Limits**: **single year (1985)** — no time series — and it predates neutral citation by 16 years.
  No code/data released.
- **This is the one genuine reporter-series frequency distribution found anywhere.** It is a
  cross-section, not a trend.

### C6. Mowbray & Chung / AustLII, "LawCite" (2016) — authorised-report share over time
- *European Journal of Law and Technology* (2016). http://hdl.handle.net/10453/88504 ;
  https://ejlt.org/index.php/ejlt/article/download/496/699/2477
- Corpus: **LawCite** — citation histories of ~**5 million** cases/articles across **75 countries**;
  **>18,000** valid series and series abbreviations (covering both neutral and printed citations).
  Method: **fully automated** data mining / heuristic citation recognition, no editorial intervention.
- **The number**: of all known citations of NSW Supreme Court decisions, the percentage of cited
  decisions that are in the Court's **authorised reports** declined **100% (1995) → 36% (2005) →
  18% (2013)**. The authors call these "initial statistics… suggestive" and explicitly ask for more research.
- **Careful**: this measures **whether cited cases were reported**, not citation *form* (neutral vs
  reporter) and not reporter-title distribution.
- LawCite itself is public; no study dataset released.

### C7. Warchuk, "Do Pre-1970 Precedents Still Matter?" (2025) — extracts BOTH forms at SCC scale, but publishes no form series
- Paul A. Warchuk, *McGill Law Journal* **70**(4): 651–695 (2025). doi 10.26443/law.v70i4.2615.
- Corpora: **(1) 66,621 outbound SCC citations, 1985–2024** (from the SCC Bulk Decisions Dataset
  "cases cited" headnote section); (2) SCC appeal **factums, Apr 2009 – Dec 2024**; (3)
  **1,427,465 inbound citations to SCC decisions on CanLII, 1876–2024** (CanLII API).
  Datasets deposited on Harvard Dataverse ("Supreme Court Judicial Citations").
- Method: **Python regex** over the "cases cited" section, then **>16,000 citations manually resolved**
  by research assistants; verification against a known-citation list; regression + decay/half-life analysis.
- **Why this matters most for Bucket C**: it extracts **both** citation forms — verbatim,
  "identified by using regular expressions that searched for the pattern `YYYY SCC/CSC NNN` or
  `N S.C.R./R.C.S. NNN`" — and it **uses citation style as a proxy variable** ("Where 80% or more of the
  citations were in the SCC/SCR format, the factum was labelled as English"; CSC/RCS → French),
  validated on 50+50 sampled factums. It also states "Duplicates and **parallel citations were filtered
  out**" (fn 32).
- **But**: citation FORM is **never reported as an outcome**. The raw material for a neutral-vs-SCR time
  series over 1985–2024 exists in this dataset; the paper does not publish that distribution.
- **This is the strongest single piece of evidence that a Canadian neutral-vs-reporter form series is
  buildable and has not been published.**

### C8. Adoption-history primary instruments (no empirical evaluation attached to any of them)
- **Canada**: neutral citation standard approved **June 1999** (CALL resolution 2 June 1999; CJC press
  release 28 June 1999). https://lexum.com/ccc-ccr/neutr/neutr.jur_en.html ;
  https://lexum.com/ccc-ccr/neutr/old/refNeutre_en.html (per-court first-application list — see C1).
  Consolidated standards (CJC / Joint Technology Advisory Committee, 2 April 2009):
  https://cjc-ccm.ca/cmslib/Committee/JTAC/JTAC-Consolidation-of-Standards-2009-04-02-E.pdf
  Proposal history incl. the 1981 CLIC study, 1985 CBA "CDNS" proposal, 1996 CJC Standard and the
  Aug 1997 Montreal Declaration: Felsky, "Case Law Citation in Canada: Proposals for Reform" (1997)
  https://lexum.com/ccc-ccr/docs/felsky.summit97_en.html
- **UK**: **Practice Direction (Judgments: Form and Citation), 11 January 2001**, [2001] 1 WLR 194 —
  http://www.bailii.org/ew/other/EWLC/PD/2001/PD_11_01_2001.html. Para 2.3: "Once the judgment is
  reported, the neutral citation will appear in front of the familiar citation from the law report
  series"; **para 3.1 requires citation from the official ICLR Law Reports where reported** — the rule
  that *manufactures* parallel citation. Extended by PD 14 Jan 2002 to all High Court (London)
  judgments: http://www.bailii.org/ew/other/EWLC/PD/2002/PD_14_01_2002.html ; ICLR explainer
  https://www.iclr.co.uk/knowledge/case-law/neutral-citations/
- **Australia**: HCA medium-neutral citations from **1998** (AustLII style guide
  https://www.austlii.edu.au/techlib/standards/style_guide.html); Federal Court MNC from **1 Jan 1999**,
  FCAFC from **1 Jan 2002**, endorsed by the Council of Chief Justices **1997**
  (https://www.fedcourt.gov.au/digital-law-library/judgments/judgments-faq).
- **NZ**: Supreme Court **2005**, Court of Appeal **2007**, High Court **2012** — practitioner/secondary
  sources only; **no court instrument retrieved — UNVERIFIED**.
- **South Africa**: Juta Judgment Style Guide (2013) §21/§30
  https://juta.co.za/media/filestore/2013/06/Juta_Judgment_Style_Guide_2013.pdf — practitioner guide.
- **Ireland**: OSCOLA Ireland quick reference only. **No adoption instrument and no empirical study found.**
- **EU**: van Opijnen & Ivantchev, "Implementation of ECLI – State of Play", JURIX 2015
  (https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2706768); van Opijnen, Peruginelli, Kefali &
  Palmirani, "On-Line Publication of Court Decisions in the EU" (Feb 2017),
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3088495. Measures **ECLI implementation counts**
  and guideline existence per Member State — **not citation-form shares**.

### C9. US neutral-citation adoption history (verified)
- Martin (2007), "Neutral Citation, Court Web Sites, and Access to Authoritative Case Law",
  https://scholarship.law.cornell.edu/facpub/1178 — Wisconsin 1994 bar report → 1999 rule effective 2000;
  North Dakota 1997; Oklahoma 1997; AALL/ABA 1996 endorsement.
- Borgeson (2012), "Checking Up on Court Citation Standards", 31 *Legal Reference Services Q.* —
  **16 states by 2012**; includes a state-by-state **parallel-citation requirement table** (rules, not
  measured frequency). https://digitalcommons.law.uw.edu/cgi/viewcontent.cgi?article=1110&context=law-lib_borgeson
- DuVivier (2001), "Parallel Citations—Past and Present", 30 *Colorado Lawyer* 25 —
  https://digitalcommons.du.edu/cgi/viewcontent.cgi?article=1390&context=law_facpub — **doctrinal/
  historical**: the 15th ed. Bluebook (1991) dropped parallel citation; state-by-state rules.
  **No measurement of practice frequency.**
- Funk & Mullen (?) [authorship UNVERIFIED], "Making Law Modern: Discovering the Restructuring of Law
  through Legal Citations in American Treatises" — https://legalmodernism.org/docs/Funk-Mullen.Making-Law-Modern.pdf
  — **the only work found that empirically demonstrates diachronic change in citation FORM
  (reporter-abbreviation drift)**: `Barb. R.` vs `Barb.` (>2,000 instances); `Kelly` vs `Ga.`
  (4,185 official vs 2,361 nominate in-period citations). But it is 19th-c. **US treatises**, not court
  output, and the drift appears as a **measurement obstacle** to eyecite ("much less successful at
  finding historically accurate but now obsolete citations").

### Bucket C — explicit negatives (high confidence)

- **A. Neutral-vs-reporter share over time: NOT FOUND**, other than Mokanov's two adjacent 2006–09
  Canadian windows. Specifically searched for and did **not** find: any UK study of post-2001 neutral
  (`[2022] UKSC 25`) vs law-report (`[2023] 2 All ER 303`) share; any Australian (post-1998), NZ
  (post-2005), Irish, South African or US-state equivalent; **any long-run Canadian series (e.g.
  2000–2025) of neutral-citation share.**
- **B. Parallel-citation frequency: NOT FOUND in any jurisdiction.** What exists is only (i) the ABA
  1996 transitional recommendation and state rule tables, (ii) Borgeson/Martin on which states
  require vs permit vs forbid parallel citation, (iii) DuVivier's doctrinal history, (iv) Mokanov's
  "are or contain" figure as an indirect undocumented proxy, (v) Warchuk's statement that "parallel
  citations were filtered out." **No study reports "x% of citations to a case carry both a neutral and
  a reporter cite, from year Y1 to Y2."**
- **C. Reporter-series frequency distribution over time: NOT FOUND over time.** Clinch 1990 is a
  reporter-title frequency distribution for **one year (1985), one jurisdiction**. Nothing reports e.g.
  "share of citations to S.C.R. vs D.L.R. vs W.W.R., 1990–2020", or ICLR Law Reports vs WLR vs All ER
  post-2001.
- **D. Multi-court census of citation forms: NOT FOUND.** No work combines, for a multi-court/multi-year
  corpus, (neutral share) × (reporter-series breakdown) × (time). The structural reason is documented in
  the data-infrastructure literature itself: A2AJ states outright that its citation network matches
  neutral citations only and therefore omits `[1999] 2 S.C.R. 817`-style citations; the EMNLP 2025 UK
  paper shows regex form detection at 35.42% F1 vs 93.3% for a transformer; "Making Law Modern" shows
  historical form drift defeats modern extractors.
- **E. "Typography of citation" as an empirical variable: NONE FOUND.** Searches for
  typography/typeface/italics/small-caps returned only practice handouts (e.g. Georgetown Law's
  Bluebook Bluepages-vs-Whitepages handout) and doctrinal style commentary. Fronk 2010 is the nearest
  neighbour but its variable is **string vs expository** citation, not typography.
- **F. Ireland and South Africa**: no empirical citation-practice study found at all — only style rules.

**Caveat flagged by the deep-dive**: two search results returned implausible forward-dated metadata and
should not be relied on — arXiv 2604.17674 (CNN case-law classification), and the **v2** revision of
arXiv 2505.02763, whose named models do not match its v1. **Cite v1 of 2505.02763** (Dahl & Martinez,
"Bye-bye, Bluebook?", doi 10.48550/arxiv.2505.02763; 866 Bluebook tasks; zero-shot compliance 69–74%,
in-context 77%) — about citation-format *rule-following*, not form prevalence.

**Other longitudinal citation studies found (measured variable ≠ citation form, listed for completeness)**:
Smyth & Nielsen, "The Citation Practices of the High Court of Australia, 1905–2015" (2019) 47 *Federal
Law Review* 655; Smyth, "What Do Trial Judges Cite? Evidence from the NSW District Court" (2018) 41
*UNSWLJ* 211 (3,266 cases 2005–2016, two RAs read every case, 300-case/10% spot check with 298/300 exact);
Smyth (2008) "One Hundred Years of Citation of Authority" 31 *UNSWLJ* (1,018 NSWSC cases, decade
intervals 1905–2005); McCormick (1996) "Judicial Citation, the Supreme Court of Canada, and the Lower
Courts: The Case of Alberta", doi 10.29173/alr1076 (14,678 citations, 1984–1994); Cooney, "What Judges
Cite: A Study of Three Appellate Courts" (2020) 50 *Stetson L. Rev.* 1 (>13,000 citations, USSC +
Virginia + Wisconsin); Detweiler (2020) 39 *Legal Reference Services Q.* 87 (law-review citation share
1945–2018); Klesch et al., "Unleashing Open Access: Law Reporting in an AI Generation" (2025) 37
*Bond Law Review* 57 (NSW: ~2% of available cases reach the authorised reports).

**Form-aware tooling/datasets found (tools, not form studies)**: eyecite (JOSS 6(66):3617) with
`is_parallel_citation` handling; **hkeyecite** (Hong Kong) which explicitly separates neutral citations
(`[2024] HKCFA 1`) from law-report citations (`(2019) 22 HKCFAR 446`); EMNLP 2025 UK benchmark
(CLC-Citation, 190 judgments / 45,179 annotations, access-restricted); **AusLaw Citation Benchmark**
(arXiv 2412.06272 — 55,005 instances / 18,677 unique citations from NSW Caselaw); **SG-LegalCite**
(8,523 Singapore Supreme Court judgments 2000–2025); `a2aj/canadian-case-law`.

**Reader-access caveats from the deep-dive**: Clinch 1990 (Emerald 403; read via abstract + vLex full
text), Smyth & Nielsen 2019 (SAGE bot-blocked; abstract only), NZ VUWLR 2000 (abstract only — and its
author name is **UNVERIFIED**; the sub-audit reports it as "Anderson (?)" while my own search retrieved
it as **Russell Smyth**, doi 10.26686/vuwlr.v31i4.5929, which I regard as the correct attribution),
Cooney 2020 and DuVivier 2001 (partial), Warchuk 2025 (large verbatim extracts rather than the whole PDF).

---

## BUCKET D — Reproducible / auditable citation extraction with published error analysis

### D1. eyecite (Free Law Project / Harvard LIL)
- **Cushman et al., "eyecite: A tool for parsing legal citations"**, *JOSS* 6(66):3617 (2021),
  doi 10.21105/joss.03617. https://github.com/freelawproject/eyecite
- Regex database "built from over 55 million existing citations culled from the collections of the
  Caselaw Access Project and CourtListener, the Cardiff Index to Legal Abbreviations, the Indigo Book
  tables, and the LexisNexis and Westlaw databases." Used in production by CAP and CourtListener.
  Provides extraction, short-form/`supra`/`id.` resolution, annotation, cleaning.
- **CORRECTION / key negative:** the JOSS paper **reports NO evaluation metrics at all** — no precision,
  no recall, no F1, no benchmark table. It offers only "a test suite of real-world citation strings."
  The 55-million figure is a *training-corpus* provenance claim (and appears on the Free Law Project
  marketing page), **not** a measured accuracy. The paper's own declared limitation, verbatim:
  **"eyecite currently only recognizes American legal citations, as it was developed to extract data
  from cases published by courts within the United States. It is unclear how much of its design would
  apply to other bodies of law."**
- The repo's `benchmark.yml` is a **delta and speed regression harness, not a labelled accuracy
  benchmark**: it runs on a CourtListener sample and reports citation-*count* gains/losses vs `main`
  plus timings, with no human gold set anywhere. Its own issue #192 documents that the
  "1 percent random sample" is actually **0.0078%**, that the "10 percent" is **0.076%**, and that the
  GitHub Action **inverts gains and losses**. Issue #212 discusses timing statistics only.
  https://github.com/freelawproject/eyecite/blob/main/.github/workflows/benchmark.yml ;
  https://github.com/freelawproject/eyecite/issues/192 ;
  https://github.com/freelawproject/eyecite/issues/212
- **UNVERIFIED**: JOSS footnote 2 begins "We estimate that eyecite…" but the footnote text is truncated
  in every extraction obtained — do not rely on any number there.

### D2. eyecite issue #304 — the strongest published hand-validated error analysis found
- **freelawproject/eyecite#304, "Citation extraction / resolution gaps surfaced by a hand-reviewed
  case-law citation set"** — https://github.com/freelawproject/eyecite/issues/304
- Reported numbers (raw counts, from the issue body and its follow-up comment):
  - **43 fully-reviewed citing opinions** (SCOTUS, federal, and state); **3,220 case-citation mentions**
    in **1,016 citation groups**.
  - **2,707 mentions (84%) recovered by eyecite; 513 (16%) had to be added by the human reviewer.**
  - **428 non-case-law citations** (statutes 347, Statutes at Large 56, law reviews 12, public laws 9,
    Federal Register 4) came through mixed in with case citations — an explicit precision problem.
  - Recall failure modes: 494 unresolved subsequent references (`id.`/`ibid`, `supra`, bare short names,
    jump cites); 63 missed full citations; 30 parallel/same-case citations split into separate groups.
  - Span over-capture: 8 instances (leading signal or party-name prefix included in the span).
  - Root-cause breakdown of the missed full citations (conservative subset, 35 occurrences): 14 whitespace
    (spaced reporter abbreviation), 10 spelled-out reporter name not registered, 2 reporter absent from
    reporters-db, 1 non-case-law, 5 **OCR/text corruption in the source**, 3 contextual/standalone-parse.
  - Ground-truth markup for all 43 opinions was attached.
- This is directly the model for a "what we undercount" ledger — but it is **US-only**, small (43
  opinions), and about a general-purpose extractor, not a Canadian multi-court census.

### D3. Caselaw Access Project (CAP)
- CAP's `html_with_citations` (eyecite-powered) field and citation metadata are referenced across the
  literature (e.g. LePaRD uses CAP's per-opinion citation metadata to map alternate citation forms to a
  `case_id`). Core-alternative mapping example given in LePaRD: *Marbury v. Madison* as "1 Cranch 137",
  "5 U.S. 137", "2 L. Ed. 60", "SCDB 1803-005", "1803 U.S. LEXIS 352" → `case_id = 12121622`.
  **No standalone CAP citation-extraction validation paper was found**; CAP is used as an *input* to
  other evaluations. UNVERIFIED whether CAP publishes its own accuracy figures.

### D4. Other evaluated legal-citation work found
- **Sargeant, Östling & Magnusson, "Detecting Legal Citations in United Kingdom Court Judgments"**,
  EMNLP 2025, pp. 26810–26836 (ACL). https://aclanthology.org/2025.emnlp-main.1361.pdf —
  **the closest existing analogue to an auditable non-US citation extractor, and it is now VERIFIED
  from the full paper.**
  - Corpus: **Cambridge Law Corpus; 190 court judgments; 45,179 fine-grained annotations**, with labels
    for **UK *and* non-UK** legislation and case references. Paper notes "judgments routinely cite
    foreign or historical authorities."
  - Three paradigms compared on the same gold standard:
    | model | F1 (all labels) | precision | recall |
    |---|---|---|---|
    | Regex (legislation-only) | 12.84% | 93.74% | 6.89% |
    | Regex (under-inclusive) | 29.59% | 97.28% | 17.45% |
    | Regex (over-inclusive, best regex) | **35.42%** | 72.98% | 23.38% |
    | ModernBERT | **93.30%** | 92.73% | 93.88% |
    | LEGAL-BERT | 92.72% | 89.74% | 95.92% |
    | GPT-4.1 (dynamic) | 76.57% | 63.36% | 96.74% |
  - Published **error analysis**: pinpoint and abbreviated legislation references are frequently missed;
    tokeniser limitations; case-law references score higher than statute references.
  - **Key finding for this project**: "Switching from the UK-only to the full label set has a <0.2% F1
    effect on every RegEx pattern, suggesting that the **additional non-UK citation styles lie largely
    outside the pattern coverage**." This is direct, quantified evidence that regex census pipelines
    systematically miss foreign citations — the exact mechanism a "what we undercount" ledger would
    have to measure.
  - Limits: 190 judgments, UK, extractor evaluation — **not** a national multi-court census, and no
    Canadian forms.
- **LePaRD** (ACL 2024 long paper 532) — https://aclanthology.org/2024.acl-long.532.pdf.
  1.7M published U.S. federal opinions from CAP; citation→`case_id` mapping across parallel forms;
  retrieval evaluated by recall@10 (59% best). Not an extraction-error study per se, but it is
  **parallel-form identity resolution at scale** — directly relevant to the "resolve cited case across
  citation forms" problem.
- **LegalCiteBench** (arXiv 2605.10186) — 24K instances from 1,000 CAP U.S. opinions; citation
  precision/recall/F1 for LLM closed-book citation recovery; all models <7/100 on retrieval and
  completion; Misleading Answer Rate >94% for 20 of 21 models. About LLM hallucination, not regex
  extraction, but it publishes citation-level P/R/F1 and an explicit matching rule.
- **"Case law retrieval: accomplishments, problems, methods and evaluations in the past 30 years"**
  (arXiv 2202.07209) — surveys evaluation practice; notes the absence of Cranfield-style public test
  collections and baselines for case-law tasks generally.
- **`646e62/legal-citation-parser`** (GitHub) — Python module extracting metadata from **CanLII**
  citation strings: neutral citations (Canadian), **SCR** citations, CanLII citations; resolves
  jurisdiction (province/territory/federal), court name and court level; plus CanLII API `cited`/`citing`
  wrappers. **No published evaluation.**
  https://github.com/646e62/legal-citation-parser
- **`medelman17/eyecite-ts`** — a TypeScript eyecite port that adds "a blocklist of international
  (non-US) reporter abbreviations" as a false-positive guard. Evidence that general-purpose US-centric
  extractors *actively suppress* non-US citations. https://github.com/medelman17/eyecite-ts

### D5. Warchuk 2025 (McGill L.J.) — THE ONLY Canadian work with quantified extraction error rates
- Paul A. Warchuk (UNB Law), "Do Pre-1970 Precedents Still Matter? An Empirical Analysis of Legal
  Submissions and Court Decisions", **(2025) 70:4 McGill Law Journal 651**, doi 10.26443/law.v70i4.2615.
- Datasets on Harvard Dataverse ("Supreme Court Judicial Citations"): (1) **66,621 outbound citations
  from SCC reasons 1985–2024** (from the SCC publisher-supplied "cases cited" headnote section, via
  regex); (2) SCC appeal **factums 2009–2024**; (3) **1,427,465 CanLII inbound citations to SCC
  decisions 1876–2024** (CanLII `citingCases` API — i.e. CanLII's own unvalidated extraction).
- **Validation protocol and exact numbers**: random survey of **95 factums** (Python `random`, fixed
  seed; 2 not machine-readable). An RA read each factum and compiled citations independently:
  **1,205 citations identified; the database contained 1,187 (98.51%).** Of the 18 missing, six were
  counsel's own citation errors (e.g. "[1979] 2 SCR 790" for "[1979] 2 SCR 709"). The dataset also held
  **6 phantom citations** and **35 appendix-only citations**. Therefore **Type 1 (false-positive) error
  rate 3.34%; Type 2 (false-negative) error rate 1.49% raw / 1% excluding counsel typos.**
- Extraction surface: regex for **`YYYY SCC/CSC NNN`** and **`N S.C.R./R.C.S. NNN` only**; a broader
  regex swept OCR errors into a separate file for manual review; matches verified against the SCC Bulk
  Decisions Dataset citation list so only real cases were kept.
- **Gaps that matter**: SCC citations only — **no provincial reporters, no OR/BCLR/ONCA forms**; the
  validated corpus is **factums (counsel submissions), not judgments** (the judgment side leans on the
  SCC Reports Branch's human-curated list); the CanLII inbound dataset has **no independent validation**;
  the pipeline is **not released as a tool**; the error rates are an appendix-level methodological
  validation, not the paper's object.

### D6. Barale, Rovatsos & Bhuta, ACL Findings 2023 — Canadian, publishes P/R/F1 but only as one NER label
- "Automated Refugee Case Analysis: An NLP Pipeline for Supporting Legal Practitioners", Findings of
  ACL 2023, 2992–3005, doi 10.18653/v1/2023.findings-acl.187.
  https://aclanthology.org/2023.findings-acl.187/ ; code https://github.com/clairebarale/refugee_cases_ner
- Corpus: **59,112 IRB refugee decisions 1996–2022** retrieved from CanLII. spaCy NER, **19 labels**,
  including `LAW`, `LAW_CASE` (prior-case mentions) and `LAW_REPORT`. Three experienced refugee lawyers
  defined labels; gold-standard training annotations.
- **`LAW_CASE` (best)**: RoBERTa-cnn+fts+pt **P 56.25 / R 60.00 / F1 58.06**. CNN baseline
  71.43 / 33.33 / 45.45. LegalBERT 37.50 / 40.00 / 38.71. Paper notes LegalBERT is pre-trained on
  US/European/UK texts and "does not include any refugee cases."
- **Gaps**: `LAW_CASE` is a coarse named-entity tag over prior-case *mentions* — no canonical citation
  parsing, no neutral-citation handling, no coreference resolution, no independent held-out error analysis.

### D7. COLIEE — Canadian case-to-case tasks with gold labels and F1, but references are REDACTED
- **COLIEE 2026 Task 1 (CL-IR)**, Federal Court of Canada: "return 'noticed cases'… In this task, **the
  references are redacted from the query case contents**, because our goal is to measure how accurately
  a machine can capture decision-supporting cases." Training 2,001 labelled queries over 7,708
  candidates; test 400 queries over 1,848 candidates; micro-F1@5.
  https://coliee.org/COLIEE2026/tasks/task1 ; https://coliee.org/COLIEE2026/overview
- **Exact 2026 numbers** (per Team DU, arXiv 2607.11400): Team DU (LightGBM LambdaRank over 34 features
  incl. citation in-degree "authority") **F1 0.3141, rank 11 of 54 submissions / 22 teams**; winner
  NOWJ **F1 0.4220**; post-competition variant 0.3456.
- **COLIEE 2022 Task 1** (same design): best dev **P 0.1073 / R 0.2249 / F1 0.1453**
  (arXiv 2304.08188). Series overview: Rabelo et al., *Review of Socionetwork Strategies* 18(1):27–47 (2024).
- **Why it does not count**: redaction means the task is **retrieval, not extraction** — it cannot report
  extraction precision/recall on citation strings at all.

### D8. Ovcharov — the single strongest precedent for a quantified "what we undercount" ledger
- **Volodymyr Ovcharov, "Citation Grounding Measures the Oracle: Graph Coverage Determines Reported LLM
  Hallucination Rates in Law", arXiv:2606.00898v2** (v1 30 May 2026; v2 8 Aug 2026), 21 pp.
  https://arxiv.org/abs/2606.00898 ; data https://huggingface.co/datasets/overthelex/citation-grounding-eval
- Design: **400 responses (100 Ukrainian legal queries × 4 commercial LLMs) held FIXED**, scored against
  **two snapshots of the same national citation graph** (EDRSR, the Ukrainian State Register of Court
  Decisions), with extractor and metric unchanged.
  - Sparse snapshot (4.7e5 records) → citation grounding **0.791–0.855** (apparently 15–21% hallucinated).
  - Dense snapshot ten weeks later (3.3e8 records / 5.8e7 decisions) → **identical responses score
    0.989–0.999**.
- Attribution: subsampling modelled as uniform record sampling, calibrated on **nothing but record count**,
  reproduces the sparse scores **to within 0.018** — i.e. the metric measures **harvesting coverage, not
  model quality**.
- Separability: bootstrapping over the query sample shows **no pair of systems separable at 95% at any
  oracle size tested** — an uncertainty estimate the author notes was absent from v1.
- Independent adjudication: a separate legislation registry shows **all 54 citations flagged by the sparse
  oracle name real statute articles — a 100% false-positive rate**; of the four flagged by the dense
  oracle, two are confirmed fabrications, one a coverage gap, one unclassifiable (looks like a repealed
  provision). Documents "systematic omission of whole statutory neighbourhoods" and node-hygiene defects.
- **This is the exact methodological shape the proposed Canadian ledger should follow** — hold the
  citations fixed, vary the coverage of the resolution oracle, and report the induced error as an
  omission artefact rather than as a property of the extractor. **But it is Ukrainian statute citations
  in a civil-law system — not case-to-case, not multi-court, not Canadian.**

### D9. Sens — error taxonomy with an explicit OMISSION category
- Diego Sens, "Not Hallucination but Granularity: Error Taxonomy and Quality Audit of LLM-Based Legal
  Information Extraction" (2026 preprint), https://github.com/sensdiego/extraction-quality-audit
- Brazilian courts (STJ, TJPR, TJSP, TRF4), 100 decisions, **1,042 audited items; 96.0% precision, zero
  hallucinations**. A **seven-type taxonomy** explicitly including **OMI (omission — "Concept exists but
  extraction is incomplete")** and **GRA (granularity mismatch — dominant: 31 of 42 errors, 3.0% of
  items)**. LLM-as-judge Cohen's κ 0.23–0.74. Publishes sample IDs, taxonomy, audit files and a stats
  recomputation script (CC BY 4.0) but **not** decision texts or prompts; the recomputation script does
  not run end-to-end without supplementary inputs.
- **A ready-made taxonomy vocabulary for a Canadian undercount ledger** (OMI vs GRA is precisely the
  distinction between "we missed it" and "we captured the wrong span/token").

### D10. Other error-analysed citation work (to show the standard the Canadian side lacks)
- **"The price of automated case law annotation: comparing the cost and performance of GPT-4o and
  student annotators"**, *Artificial Intelligence and Law* (2025), doi 10.1007/s10506-025-09495-1.
  UN human-rights treaty-body decisions. **GPT-4o P 0.94 / R 0.89 / F1 0.92; humans P 0.97 / R 0.98 /
  F1 0.97.** Explicit finding: GPT-4o "struggles with recall in citation extraction, particularly for
  complex legal references"; and prompt-reproducibility failures — "identical prompts yielded different
  citation extractions minutes apart." (Read via abstract + extended passages; **UNVERIFIED** full PDF.)
- **arXiv 2607.03325**, "From Judgments to Issues: Structured Extraction of Legal Reasoning with
  Citation-Hallucination Control" — ~330,000 Italian tax court decisions; extraction + hallucination
  filter via the **Linkoln** parser normalising to URN-NIR / ECLI / CELEX. Validation: 50 judgments,
  two tax-law PhDs (20 double-blind, 30 disjoint halves), inter-annotator agreement, LLM-vs-expert
  agreement, pooled P/R/F1 with **95% CIs via non-parametric cluster bootstrap at judgment level
  (B=10,000)**, Gwet's AC2 instead of Cohen's κ (with justification), and standalone evaluation of the
  hallucination filter (specificity, precision, recall, residual rate by citation type).
  **This is the best available template for the statistical reporting your ledger should carry.**
  UNVERIFIED (arXiv HTML).
- **LEPHANTOMCITE / "Who Checks the Citations?"** (Princeton POLARIS Lab),
  https://princeton-polaris-lab.github.io/legal-hallucination-webpage/Legal_Hallucination.pdf — 1,300
  entries (1,000 excerpts from real appellate briefs 2012–2021 + 300 re-verified); error analysis of
  GPT-5 false negatives/positives: recall 18.2% (incorrect pincites), 82.6% (verbatim misquotes),
  84.0% (content misrepresentation). Documents a **coverage-induced measurement artifact** directly
  relevant to provenance: 129 correct citations return no CourtListener lookup result, and Qwen3.5
  flagged 65.9% of them as hallucinated vs GPT-5 24.0%. UNVERIFIED (preprint/workshop PDF).
- **"Beyond the Haystack: Sensitivity to Context in Reference Recall"** (NLLP 2025),
  https://aclanthology.org/2025.nllp-1.5.pdf — shows NIAH-style long-context benchmarks **overestimate**
  legal reference recall; US opinions post-2024-07-01 (CourtListener, 1.75M decisions); 50 real + 50
  digit-permuted fake citations.
- **CanLegalRAGBench** — Zhao, Taranukhin, Cui, Aikenhead & Shwartz (UBC CS / Vector / Allard Law),
  arXiv 2605.30497, https://github.com/NLP-UBC/CanLegalRAGBench. Canadian, expert-annotated. Retrieval
  macro recall@10 0.406–0.456, nDCG@10 0.449–0.521; **8–29% of generated claims unsupported** by
  retrieved documents. Notable uncertainty finding: automatic retrieval metrics "**unnecessarily penalize
  retrieving relevant documents not in the gold set**" and "**underestimate the absolute performance of
  systems**" — established by expert re-annotation of a stratified 30-query subset that *added* relevant
  documents to the gold set. This is the gold-set-incompleteness problem, stated for Canada. RAG QA,
  not citation-span extraction. UNVERIFIED peer-review venue.

### D11. CAP's operational omission ledger and published caveat
- **courtlistener#5015**, "Run HTML with citations next week", publishes running counts of opinions with
  empty `html_with_citations`: **4,098,731** (2025-06-02) worked down to **49,411** (2025-06-07), then
  155 stragglers — bulk attributed to the Harvard ("U") and RECAP ("G") ingestion pipelines.
  https://github.com/freelawproject/courtlistener/issues/5015
- **Best published CAP uncertainty statement is qualitative and carries no numbers** — Stanford Law / LIL,
  "Tutorial: Citation Analysis via Caselaw Access Project API" (Nov 2025),
  https://law.stanford.edu/wp-content/uploads/2025/11/TutorialCitationAnalysisviaCaselawAccessProjectAPI.pdf
  verbatim: "The Caselaw Access Project structures case text using a combination of OCR tools and human
  review, then extracts citations using the eyecite library… While the Library Innovation Lab takes great
  pains to improve accuracy, **automated digitization tools at scale inevitably introduce errors**.
  Citation extractors also may exclude interesting context such as signals or preceding words." Also:
  "the accuracy of these tools is limited by the accuracy of the underlying dataset." Corpus scale given
  as 5M+ cases and 46M case citations.

### D12. Canadian tooling with ZERO published accuracy evidence
- **646e62/legal-citation-parser** (Daniel Nathan Booy) — https://github.com/646e62/legal_citation_parser,
  PyPI `legal-citation-parser` v0.5.1, created 2024-03-14, 3 stars, 6 open issues, GPLv3. Handles
  **Canadian neutral citations, SCR citations and CanLII citations**; extracts UID (CanLII `caseId`),
  atomic citation, style of cause, citation type, year, decision number, **jurisdiction** (province/
  territory/federal), court name, court level, CanLII URL, URL-verified flag, error field. Example:
  "R v Sutherland, 2022 MBCA 23" → uid `2022mbca23`, court_level "provincial appellate". **No published
  precision/recall, no test set, no benchmark.** Companion repos: `646e62/legal-informatics`,
  `646e62/citation-generator` (McGill Guide formatting). **The closest thing to a Canadian eyecite, and it
  is unbenchmarked.**
- **CanLII citator API** — `GET /v1/caseCitator/en/{databaseId}/{caseId}/{citedCases|citingCases|citedLegislations}`;
  English-only for citator calls. Lexum's production case-to-case graph. **No published accuracy metrics.**
  https://github.com/canlii/API_documentation/blob/master/EN.md
- **Lexum** — subject classification (Longformer, 42-subject taxonomy) and citation-network search ranking
  blog posts; **LexKey** (CEUR-WS Vol-3441 paper12) is CanLII keyword generation, dataset withheld per
  editors' policy. **None of these is citation extraction.**
- **`medelman17/eyecite-ts`** advertises "structured confidence scoring" but is **US-only** (52 US statute
  jurisdictions) and unbenchmarked.

### Bucket D — explicit negatives (high confidence)
- **Auditable citation extraction with published error analysis for CANADIAN citation forms does NOT
  appear to exist.** No work was found publishing precision/recall/F1 for **citation-span extraction or
  case-to-case coreference over Canadian forms** (neutral citations `2020 SCC 5` / `2007 ONCA 1`; SCR,
  FC, OR, BCLR reporters; CanLII IDs) **against a hand-annotated Canadian gold standard**, with an
  accompanying error analysis. There is **no Canadian analogue of Sargeant et al.'s CLC-Citation
  (EMNLP 2025) and no Canadian analogue of eyecite issue #304.**
- The four nearest misses, with their exact gaps:
  1. **Warchuk 2025 (McGill L.J. 70:4:651)** — the only Canadian work with quantified extraction error
     rates (T1 3.34%, T2 1.49%/1%; n=95 factums; 1,205 gold citations; 98.51% coverage). Gaps: SCC only;
     validated on factums not judgments; two regex surface patterns; no provincial reporters; no
     coreference; the CanLII side inherits unvalidated extraction.
  2. **Barale et al. (ACL Findings 2023)** — Canadian, P/R/F1, but `LAW_CASE` is 1 of 19 NER labels over
     refugee decisions; no citation-string canonicalisation, no form handling, no coreference.
  3. **COLIEE 2026 Task 1 / 2022 Task 1** — Canadian, case-to-case, gold labels, published F1, **but
     references are deliberately redacted**, so it is retrieval, not extraction.
  4. **A2AJ Canadian Case Law** — Canadian case-to-case network at scale, openly downloadable, with an
     explicit and candid undercount disclosure. **The undercount is qualitative only** — "approximate",
     neutral-citations-only, pre-2000 under-represented, non-neutral courts null, "no warranties
     regarding completeness or accuracy" — **no measured recall, no gold standard.**
- **A CANADIAN "what we undercount" ledger does not exist.** The strongest existing precedent for the
  *method* is Ovcharov (arXiv 2606.00898), which quantifies how graph coverage alone manufactures
  apparent hallucination rates — but for Ukrainian **statute** citations in a civil-law system, not
  case-to-case, not multi-court. Sens's OMI/GRA taxonomy and the Italian cluster-bootstrap reporting
  template are the other two directly reusable methodological precedents. The CAP/CourtListener and
  eyecite ledgers are **operational coverage counts, not research error analyses**, and every one of them
  is US-only.

---

## Cross-bucket synthesis (evidence only)

| Candidate overlap with the proposed project | What it actually covers | What it lacks |
|---|---|---|
| **A2AJ `cases_cited` graph** (Rehaag/Wallace/McCarten 2025) | SCC+ONCA+BCCA(+many more) full text; automatic outbound/inbound citation lists; **this project's own corpus source** | Neutral-citation regex only; no reporter-form citations; no foreign/cited-case jurisdiction resolution; no precision/recall; no per-row provenance; no per-citation form |
| **Hoadley et al. 2021** (Frontiers in Physics) | **1,559,807 judgments, 26 common-law systems, 1717–2020; both citing and cited country resolved; fully automated** | Proprietary vLex Justis engine (no audited recall); commercial subset of "senior courts" rather than a census; foreign *case* citations only; no citation-form dimension; **whether Canada/SCC/ONCA/BCCA are separately represented is UNVERIFIED** |
| **ECCN** (Kirchmair & Lechner) | **19 European constitutional courts + CJEU + ECtHR, 1950s→present; fully automated (regex + embeddings); OA data; jurisdiction-resolved by construction** | Only inter-constitutional-court + European-court edges; no general court-to-court citation; no citation-form dimension; **no Canadian content** |
| **Alschner & St-Hilaire 2024** | SCC 1983–2021, typed case-to-case edges, authority scores, R/igraph | SCC only; SCC-to-SCC only; no foreign; no citation form; regex on headnote labels only |
| **Neale 2013** | 594,540 Canadian opinions; **own context-free grammar over 112 Canadian citation strings**; 1,900,916 citations / 566,992 nodes; **~40% resolve to CanLII, ~60% out-of-corpus/unofficial reporters**; released notebook | No precision/recall; no foreign resolution; no per-court form breakdown; explicit coverage-confounding caveat; 2013 vintage |
| **Rado 2018/2020** | **All 1,223 SCC judgments 2000–2016; all 24,509 cited cases manually checked and matched to jurisdiction**; 5,647 statutes likewise; per-justice profiles | SCC only; foreign-only; MANUAL; no domestic edge graph; no citation form; no released code |
| **Bodnár 2021** | All 1,416 SCC judgments 2000–2019; 432 with foreign law; 62 foreign jurisdictions resolved | SCC only; foreign-only; hybrid manual; mentions not typed edges; no form |
| **Tyrrell 2018** | **Census: all 533 UKSC cases 2009–2017; 157 (~29.6%) with foreign citations; per-jurisdiction resolved** | UKSC only; manual; no Canadian content; no form |
| **Groppi & Ponthoreau 2013 / *Judicial Bricolage* 2025** | 16 then 31 constitutional courts; per-cited-jurisdiction counts; manual; uniform questionnaire | Manual; country-level only; no cited-case identity resolution; no form; no automation |
| **McCormick 1993/1995/2009** | All 10 provincial CAs 1987 (1,402 dec / 6,213 refs); all SCC 1989–93 (631/4,848); SCC 2000–08 (632/13,602); foreign blocks resolved | Small, dated, manual, untyped, no form |
| **Fournier 2024** | ONCA/BCCA/ABCA/QCCA citing percentages + 200 longest ONCA 2021 decisions | Coarse (court-level citing %); no per-citation records; no foreign resolution; no form |
| **Lexum RefLex 2005 / Mokanov 2010** | Regex detection over hundreds of Canadian reporters; parallel-citation linking; **neutral-cite share 68% then 73% of all citations (2006–08, 2007–09); ~80% resolution rate** | Two adjacent windows; no pre-1999 baseline; "are or contain" conflates pure vs parallel; no per-court series; no error metrics |
| **Warchuk 2025** (McGill L.J.) | 66,621 SCC outbound citations 1985–2024; 1,427,465 CanLII inbound; **both neutral and SCR forms extracted; Type 1 error 3.34%, Type 2 1.49%/1% on 95 factums**; Dataverse deposit | SCC only; validated on **factums not judgments**; two regex surfaces; no provincial reporters; no coreference; **form handled but never reported as an outcome** |
| **Sargeant et al. 2025** (EMNLP) | **UK vs non-UK citations as an explicit gold-labelled target**; 190 judgments / 45,179 annotations; ModernBERT F1 93.3% vs regex 35.42% | Methods/extraction paper, not a census; 190 judgments; no Canadian forms |
| **Ovcharov 2026** (arXiv 2606.00898) | **Quantifies how graph coverage alone manufactures apparent citation error** (0.791–0.855 sparse vs 0.989–0.999 dense, same responses); 100% false-positive rate from the sparse oracle | Ukrainian **statute** citations, civil law; not case-to-case; not multi-court; no Canadian content |
| **eyecite#304** | Hand-validated ground truth, 43 US opinions, 3,220 mentions, 84% recall, six-cause error taxonomy | US only; small; single annotator seeded from the system under test; not a census |

### Direct answer to the audit question

On the evidence reviewed, **a jurisdiction-resolved census of ALL citation forms (foreign + domestic,
neutral + reporter) over a fixed multi-court Canadian corpus, with published per-row provenance and a
quantified undercount ledger, was NOT found to already exist.** The closest existing artifacts are:

1. **A2AJ's neutral-citation-only Canadian graph over essentially the same three-court corpus** — which
   explicitly declines to capture reporter citations, resolve cited-case jurisdiction, or quantify its
   own error (Section 0).
2. **Rado (SCC 2000–2016) and Bodnár (SCC 2000–2019)** — which resolve foreign-cited-case jurisdiction
   but are manual, SCC-only, foreign-only, with no citation-form dimension (A4, A8).
3. **Neale 2013** — which built a 112-form Canadian citation grammar over 594,540 opinions and reported
   a 40%/60% resolution split, but published no precision/recall and no foreign or form census (A2).
4. **Hoadley et al. 2021 and ECCN** — fully automated, jurisdiction-resolved cross-citation censuses, but
   neither is Canadian-multi-court, neither has a citation-form dimension, and neither publishes audited
   extraction error (B0b, B0a).
5. **Mokanov 2010 and Warchuk 2025** — the only two Canadian artifacts that touch citation *form*
   quantitatively, but the first is an unaudited blog post with two adjacent windows and the second
   extracts both forms yet never reports their distribution (C4, C7).

**These components exist separately; no work was found that joins them.** In particular, no source was
found that (a) extracts reporter-form citations at all over a multi-court Canadian corpus, (b) resolves
the jurisdiction of cited foreign cases by automation, (c) publishes per-row provenance, or (d) turns
the acknowledged undercount into a measured, quantified ledger.

### Highest-value follow-ups before any novelty claim

1. **Verify whether Canada is among Hoadley et al.'s 26 common-law systems**, and if so whether
   SCC/ONCA/BCCA are separately resolved — this is the single most consequential open check (B0b).
2. Obtain the **ECCN OA dataset** (doi 10.11587/AYUJTC) and confirm Canada is absent (B0a).
3. Retrieve **Warchuk's Dataverse deposit** to check whether a neutral-vs-SCR series is computable from
   the released data even though unpublished (C7).
4. Read **Clinch 1990** and **Arcioni & McLeod 2014** in full to confirm corpus counts (C5, B1).
5. Check the **`citation2_en`** field population rate in the local A2AJ parquet to see whether a partial
   parallel-citation count is already derivable (C1).
6. **UNVERIFIED** items outstanding: Arcioni & McLeod 2014 corpus size; Frosini and Butler 2011 corpus
   sizes; Law & Chang corpus size; method/corpus of Simon 2013, Voeten 2010, Farahat 2015; chapter-level
   counts for Groppi & Ponthoreau 2013, *Judicial Bricolage* 2025, Martini 2013/2018, Tyrrell 2018;
   NZ neutral-citation adoption instruments; the JOSS footnote-2 estimate; the authorship of
   "Making Law Modern".

### Searches run (indicative)
network citation analysis SCC Routledge; Alschner Canadian citation network; Refugee Law Lab / A2AJ
Canadian case law citation dataset; citation network ONCA BCCA empirical; "Neale" Canadian citation
analysis; Fournier ONCA citational practices; McCormick provincial courts of appeal citation; Bodnár
comparative constitutional powerhouse; non-domestic legal sources SCC; Rado transnational judicial
dialogue; EU 28 supreme courts cross-citations; citations to foreign courts AJCL; foreign law citation
constitutional courts; Groppi Ponthoreau foreign precedents constitutional judges; Judicial Bricolage
2025; ECCN European constitutional court network; Hoadley global community of courts; Tyrrell UKSC
foreign jurisprudence; Israeli Supreme Court citation practices; NZ overseas authority rights litigation;
neutral citation transition empirical; parallel citation practice; reporter series frequency; eyecite
precision recall; eyecite issue 304; Caselaw Access Project citation extraction; citation extraction gold
standard; legal citation parser CanLII GitHub; Lexum RefLex; Mokanov environmentally friendly citations;
Warchuk pre-1970 precedents; "all citation forms" Canadian census; undercount / omission / provenance
ledger; COLIEE 2026 Canadian tasks; CanLegalRAGBench; citation grounding oracle.
