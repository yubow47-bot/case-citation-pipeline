# Free Law Project Toolchain — Evidence-Backed Capability Audit

**Purpose:** determine whether a Canadian legal-citation-extraction pipeline would duplicate
existing public work in (a) `reporters-db`, (b) `eyecite`, (c) the CourtListener citation graph.

**Date of evidence gathering:** session date per environment (CourtListener/FLP pages fetched live).

## Verification method and its limits (read this before the table)

Verified by direct retrieval in this session of: GitHub REST API metadata/contents endpoints,
`raw.githubusercontent.com` file fetches, FLP wiki pages, and **anonymous GET against the live
CourtListener REST API v4** (`/courts/`, `/opinions-cited/` docs). Every quote below is verbatim
from the cited URL.

**Hard limitation:** the shell in this session has **no network egress** (pip/curl/Invoke-WebRequest
all fail), and web fetch truncates a single document at roughly 100 KB. `reporters_db/data/reporters.json`
is **907,920 bytes**, so the whole file could not be read or grepped. Observable regions were:

* `reporters.json` head: keys `"A."` → `"Bibb"` (JSON is code-point-sorted — see the
  `test_json_format` guarantee below — so this window is contiguous and complete).
* `reporters.csv` head `A.` → `B.R.`, plus tail `D.S.D.` → `F. Cas.` (the C block and the first part
  of the D block were dropped by truncation).

Consequently the **individual presence/absence of `S.C.R.`, `D.L.R.`, `C.C.C.`, `O.R.`, `W.W.R.`
could not be directly verified** and is carried into the UNVERIFIED list. `A.C.` *could* be verified
absent (see Q1). No local copy of the package exists on this machine (filesystem search performed).

## URL correction

The task cites `https://github.com/freelawproject/reporters_db`. That URL returns **HTTP 404**
(verified via `https://api.github.com/repos/freelawproject/reporters_db` → `{"message":"Not Found"}`).
The canonical repository is **https://github.com/freelawproject/reporters-db** (hyphen).

---

## Q1 — reporters_db

### 1a. Which jurisdictions? Does it include Canadian reporters?

**answer: United States only, by design — no Canadian reporter coverage was found.** One reporter of
Canadian content exists in the data but carries **no jurisdiction mapping**.

* https://free.law/projects/reporters-db/ —
  > "Our Reporters Database is a Python library or JSON file that provides structured information about nearly every American legal reporter."
  > "In the Reporters Database, you will find information about nearly 1,000 different reporters dating from 1754 to today."
* https://raw.githubusercontent.com/freelawproject/reporters-db/main/README.rst — data sourcing is
  entirely US:
  > "1. The original data came from parsing the citation fields for millions of cases in CourtListener.
  > 2. A second huge push came from parsing metadata obtained from two major legal publishers, and by parsing the citation fields of Havard's Case.law database.
  > 3. An audit was performed and additional fields were added by using regular expressions to find number-word-number strings in the entire Harvard Case.law database."
* https://raw.githubusercontent.com/freelawproject/reporters-db/main/tests.py — the schema is
  **test-enforced** to a closed, US-scoped vocabulary. There is no `foreign`, `canada` or `uk` type,
  so no reporter can be *classified* as non-US:
  > `VALID_CITE_TYPES = (`
  > `    "federal",`
  > `    "neutral",`
  > `    "scotus_early",`
  > `    "specialty",`
  > `    "specialty_west",`
  > `    "specialty_lexis",`
  > `    "state",`
  > `    "state_regional",`
  > `)`
  > `def test_all_reporters_have_valid_cite_type(self):`
  > `    """Do all reporters have valid cite_type values?"""`
* Observed data (sample of 665 jurisdiction strings in the `A.`→`Bibb` window; and the
  `A.`→`B.R.` CSV window): **every non-empty `mlz_jurisdiction` value is `us`-prefixed. Zero
  non-`us` country prefixes.** Extraction of `"([a-z]{2})[;:]"` over the fetched window returned
  `us` ×665 and nothing else.
* `A.C.` (Appeal Cases) is **definitively absent**. `reporters.json` is guaranteed code-point sorted:
  > `def test_json_format(self):`
  > `    """Does format of json file match json.dumps(json.loads(), sort_keys=True)?"""`
  and the observed adjacency is `"A."` → `"A.D."` → `"A.E.C."`. Since `"A." < "A.C." < "A.D."`,
  an `A.C.` key would have to sit between them; it does not.
* The single non-US-jurisdiction reporter observed: **`"Dominion Tax Cas. (CCH)"` / `"Dominion Tax Cases"`**,
  `cite_type: "specialty"`, **`mlz_jurisdictions` empty** (raw
  `https://raw.githubusercontent.com/freelawproject/reporters-db/main/reporters_db/data/reporters.csv`).
  That series is Canadian — https://www.wolterskluwer.com/en-ca/solutions/cch-answerconnect:
  > "**Comprehensive coverage of tax cases:** Dominion Tax Cases covers all Canadian tax cases from 1920 onwards."
  and https://ocul-uwo.primo.exlibrisgroup.com/discovery/fulldisplay/alma991012386679705163/01OCUL_UWO:UWO_DEFAULT
  gives subject: "Taxation -- Canada". So reporters_db can *incidentally* contain a Canadian reporter,
  stored as an unlabelled `specialty` with no jurisdiction.
* Scope for foreign reporters is an **open** question, not a settled feature:
  https://github.com/freelawproject/reporters-db/issues/267 — title **"Define scope for foreign
  reporters"**, state `"open"`, created `2026-06-19`. (Its body contains an analysis block explicitly
  labelled `"From Claude:"`; treat that prose as unverified commentary, but the issue's existence and
  open state are first-party.)
* Issue-tracker search: `repo:freelawproject/reporters-db canada` → `"total_count":0`;
  `repo:freelawproject/eyecite canada` → `"total_count":0`; `org:freelawproject canada` → 8 hits,
  none about Canadian case law (a WeWork Canada docket, an AWS grant, Canadian PII regexes).

`S.C.R.` / `D.L.R.` / `O.R.` / `W.W.R.` / `C.C.C.` → **UNVERIFIED** (see list at end).

### 1b. Does it map each reporter abbreviation to a jurisdiction? Data structure?

**answer: yes — via a per-reporter `mlz_jurisdiction` list — but there is no `jurisdictions.json`,
the mapping is US-only, third-party-maintained, and may be empty.**

Repository data files (verified via `https://api.github.com/repos/freelawproject/reporters-db/contents/reporters_db/data`):
`case_name_abbreviations.json` (5,943 B), `journals.json` (265,208 B), `laws.json` (211,528 B),
`regexes.json` (4,658 B), `reporters.csv` (305,328 B), `reporters.json` (907,920 B),
`state_abbreviations.json` (1,231 B). **There is no `jurisdictions.json`** — a direct fetch of that
path returned 404.

Structure, verbatim from README.rst:
> ```
> "$citation": [
>     {
>         "cite_type": "state|federal|neutral|specialty|specialty_west|specialty_lexis|state_regional|scotus_early",
>         "editions": {
>             "$citation": {
>                 "end": null,
>                 "regexes": [],
>                 "start": "1750-01-01T00:00:00"
>             },
>             "$citation 2d": { "end": null, "regexes": [], "start": "1750-01-01T00:00:00" }
>         },
>         "examples": [],
>         "mlz_jurisdiction": [],
>         "name": "",
>         "variations": {},
>         "notes": "",
>         "href": "",
>         "publisher": ""
>     }
> ],
> ```
On the jurisdiction field:
> "``mlz_jurisdiction`` corresponds to the work that is being done for Multi-Lingual Zotero. This field is maintained by Frank Bennett and may sometimes be missing values."

Concrete example entry (from `reporters.json`, verbatim data):
```json
"A.": [
    {
        "cite_type": "state_regional",
        "editions": {
            "A.":   { "end": "1938-12-31T00:00:00", "start": "1885-01-01T00:00:00" },
            "A.2d": { "end": "2010-12-31T00:00:00", "start": "1938-01-01T00:00:00" },
            "A.3d": { "end": null,                  "start": "2010-01-01T00:00:00" }
        },
        "mlz_jurisdiction": [
            "us:ct;supreme.court",
            "us:dc;court.appeals",
            "us:de;supreme.court",
            "... 25 more us:... values ..."
        ],
        "name": "Atlantic Reporter",
        "variations": {
            "A .2d": "A.2d", "A,2d": "A.2d", "A. 2d": "A.2d", "A. 3d": "A.3d",
            "A.2d.": "A.2d", "A.3d.": "A.3d", "A.R.": "A.", "A.Rep.": "A.",
            "A2d": "A.2d", "At.": "A.", "At. Rep.": "A.", "Atl.": "A.",
            "Atl. Rep.": "A.", "Atl.2d": "A.2d", "Atl.R.": "A."
        }
    }
]
```
Note the encoding: `"us:ct;supreme.court"` = country `us`, state/region `ct`, court `supreme.court`;
`"us;federal"` and `"us;supreme.court"` have no state segment. **Nothing in the observed window maps
outside the United States.**

### 1c. Multiple / parallel abbreviations for the same reporter, and name variants?

**answer: yes — extensively.** README.rst:
> "1. Each Reporter key maps to a list of reporters that that key can represent. In some cases (especially in early reporters), the key is ambiguous, referring to more than one possible reporter."
> "3. The ``variations`` key consists of data from local rules, found through organic usage in our corpus and from the `Cardiff Index to Legal Abbreviations <http://www.legalabbrevs.cardiff.ac.uk/>`__."
> "- ``EDITIONS`` — A simple dict to map the abbreviations for each reporter edition to the canonical reporter. For example, ``A.2d`` maps to ``A.``."
> "- ``NAMES_TO_EDITIONS`` — A simple dict to map the name of a reporter back to its canonilcal abbreviations. For example, ``Atlantic Reporter`` maps to ``['A.', 'A.2d']``."
> "- ``VARIATIONS_ONLY`` — This contains a dict mapping a canonical reporter abbreviation to a list of possible variations it could represent."

Also derived helpers `SPECIAL_FORMATS` (from `reporters_db/__init__.py`). Observed in data: `"A."`
carries 15 variations; the `reporters.csv` contains **two separate `Ark.` rows** (one `cite_type`
`neutral`, one `state`) and two `Dall.` rows (`scotus_early`, `state`) — concrete proof that one key
maps to a list of distinct reporters.

**Important:** this is *abbreviation ambiguity*, **not** "parallel citations" in the Canadian/US sense
(same judgment published in several reporters). The latter is handled elsewhere in CourtListener (see Q3).

### 1d. Neutral citation formats per court (e.g. "2013 SCC 60", "2013 ONCA 123")?

**answer: partial — US neutral formats only, with no evidence of Canadian court codes.**

* A neutral `cite_type` exists and is used. Observed entries: `"AZ"` → `"cite_type": "neutral"`,
  `"name": "Arizona Neutral Citation"`, `mlz_jurisdiction: ["us:az;supreme.court"]`; `"AWCC"` →
  `"Arkansas Neutral Citation (Workers Compensation Commission)"`; plus neutral rows for `Ark.`,
  `Ark. App.` in `reporters.csv`. README notes only US states:
  > "Mississippi supports neutral citations, but does so in their own format, as specified in `this rule <...>`."
* The generic neutral pattern is US-shaped, from
  https://raw.githubusercontent.com/freelawproject/reporters-db/main/reporters_db/data/regexes.json:
  > `"format_neutral": {`
  > `    "": "$volume_year-$reporter-$page",`
  > `    "#": "Format neutral cite, like '2000-Ohio-123'",`
  > `    "3_4": "$volume_year-$reporter-$page_3_4",`
  > `    "3_4#": "Format neutral cite where the page must be 3 or 4 digits, like '2000-NMSC-123'"`
  > `},`
  Note the hyphenated `year-COURT-number` shape and the absence of a dash-less generic variant; the
  request to add one is still open — https://github.com/freelawproject/reporters-db/issues/184
  (title "Rename format_neutral to ohio_neutral, and Louisiana to louisiana_neutral, and Add New neutral
  Format", state `"open"`, body: "I'd like to rename that as Ohio Natural and make Format Neutral to be a pattern without dashes.").
* A Canadian neutral citation is `year COURT number` with **no** hyphens and a Canadian court code
  (https://www.lexum.com/ccc-ccr/neutr/neutr.jur_en.html:
  > "The core of the citation (containing the year of the decision, a court or tribunal identifier and an ordinal number attributed to the decision)" … "a court of appeal decision could be cited as follows: Smith v. Leblanc, 1998 BCCA 21."
  … and for bilingual identifiers: "the Supreme Court of Canada will be identified by the identifier codes, 'CSC' and 'SCC'").
  Whether keys `SCC`/`ONCA`/`CSC` exist in `reporters.json` is **UNVERIFIED** (full-file grep not
  possible). No Canadian neutral-court code was observed in the fetched windows, and the `cite_type`
  vocabulary has no Canadian member.

### 1e. Roughly how many reporters and how many jurisdictions?

* Reporters: **1,167** — README.rst:
  > "As of version 3.2.32, this data contains information about 1,167 reporters and 2,102 name variations."
  FLP's own page says "nearly 1,000 different reporters dating from 1754 to today" (older figure).
* Name variations: **2,102** (same quote).
* Number of *jurisdictions*: **not stated anywhere I could find — UNVERIFIED.** No `jurisdictions.json`
  and no documented jurisdiction count. All observed values are `us…` (country `us`, plus US
  state/territory/tribal/federal subdivisions), so the effective jurisdiction space is the United
  States plus US territories and tribal courts.
* Related files with unverified counts: `laws.json` (211,528 B) and `journals.json` (265,208 B).

### 1f. License? Redistributable?

**yes, redistributable.** GitHub repo metadata for `freelawproject/reporters-db`:
> `"license":{"key":"bsd-2-clause","name":"BSD 2-Clause \"Simplified\" License","spdx_id":"BSD-2-Clause"}`

README.rst:
> "This repository is available under the permissive BSD license, making it easy and safe to incorporate in your own libraries."

---

## Q2 — eyecite

### 2a. Which citation classes does it extract?

**yes to all of the classes asked about, via distinct dataclasses** (`eyecite/models.py`,
https://raw.githubusercontent.com/freelawproject/eyecite/main/eyecite/models.py):

| Class | Docstring (verbatim, abbreviated) |
|---|---|
| `FullCaseCitation` | "Convenience class which represents a standard, fully named citation, i.e., the kind of citation that marks the first time a document is cited." |
| `ShortCaseCitation` | "short form citation, i.e., the kind of citation made after a full citation has already appeared … `Adarand, 515 U.S., at 241`" |
| `SupraCitation` | "a 'supra' citation, i.e., a citation to something that is above in the document." |
| `IdCitation` | "an 'id' or 'ibid' citation … `"... foo bar," id., at 240`" |
| `ReferenceCitation` | "A reference citation is a citation that refers to a full case citation by name and pincite alone. Future versions hopefully with drop the pincite requirement. Examples: Roe at 240" |
| `FullLawCitation` | "Citation to a source from `reporters_db/laws.json`." |
| `FullJournalCitation` | "Citation to a source from `reporters_db/journals.json`." |
| `UnknownCitation` | "a recognized citation should theoretically be parsed as a CaseCitation, FullLawCitation, or a FullJournalCitation. If it's something else, this class serves as a naive catch-all." |

README.rst lists the same as: "full case … reference … short case … statutory … law journal … supra … id."
Reference citations additionally require the two-step path `extract_reference_citations()` after
resolving a short case name ("This feature requires an external database or heuristic method to
resolve the short case name before extracting reference citations a second time.").

### 2b. Parallel citations? Resolution to a canonical resource (`resolve_citations`)?

**partial on parallel citations; yes on `resolve_citations`, but only within the document's own text.**

Parallel citations — `FullCaseCitation.is_parallel_citation(preceding)` exists, but it only detects
that two citations share one citation string and copies metadata down:
> `def is_parallel_citation(self, preceding: CaseCitation):`
> `    """Check if preceding citation is parallel"`
> `    ...`
> `    if self.full_span_start == preceding.full_span_start:`
> `        # if parallel get plaintiff/defendant data from`
> `        # the earlier citation, since it won't be on the`
> `        # parallel one.`
It does **not** map a set of parallel reporters onto a canonical case. CourtListener's own doc states
the limitation: https://wiki.free.law/c/courtlistener/help/api/rest/v4/citations —
> "Opinions are often published in more than one book or online resource. Therefore, many opinions have more than one citation to them. These are called "parallel citations." We do not have every parallel citation for every decision. This can impact the accuracy of the graph."
The crosswalk is a separate bulk artefact: https://wiki.free.law/c/courtlistener/help/api/bulk-data/citation-crosswalk-for-parallel-citations —
> "To crosswalk these citations, simply group by the last column, and you'll have all the citations we know for a given case."

`resolve_citations` — yes, it exists (`eyecite/resolve.py`) and maps "full," "short form," "supra,"
"id," and reference citations to a common `Resource` (README.rst). But it is deliberately thin and
purely textual (`resolve.py`):
> "By default, eyecite uses an extremely thin "resource" object that simply serves as a conceptual way to group citations with the same references together."
> "Importantly, eyecite performs these resolutions using only its immanent knowledge about each citation's textual representation."
> "If a citation cannot be definitively resolved to a resource, it is dropped and not resolved."
Plus heuristics such as `MAX_OPINION_PAGE_COUNT = 150` and `_has_invalid_pin_cite()`. External/DB
resolution is opt-in via the injectable `resolve_full_citation=` / `resolve_shortcase_citation=` /
`resolve_supra_citation=` / `resolve_id_citation=` callables.

### 2c. Self-citation exclusion (a document citing itself)?

**no — and it is a documented, open, high-exposure defect in the production pipeline.**
https://github.com/freelawproject/courtlistener/issues/6169 (title "Citation data error", label
`data-quality`, state `"open"`):
> "## Citing opinion listed as its own authority"
> "- **Description:** I assume this is not by design, as we probably don't want the citing opinion itself to be one of its own authorities. These are also listed in authorities but not actually cited."
> "- **Possible Fix:** Compare cluster id between authorities and current citing opinion, remove any authorities that have the same cluster id as the current citing opinion."
> "- **Exposure:** Large. Of 182 randomly sampled opinions, 75 of them (listed below) had this issue, which is ~40% of the opinions"

Nothing in `eyecite/models.py` or `eyecite/resolve.py` implements self-citation exclusion.

### 2d. French / non-English text? 19th-century typography?

**no French/non-English support; partial on 19th-century material (vocabulary yes, typography only generic).**

Non-English:
* Scope statement, README.rst: "eyecite recognizes a wide variety of citations commonly appearing in **American** legal decisions".
* No language/locale parameter exists — `get_citations()` is documented with exactly
  `plain_text`, `remove_ambiguous`, `tokenizer`, `markup_text`, `clean_steps`.
* The **data layer cannot even store accented reporter abbreviations** — `tests.py`:
  > `def check_ascii(self, obj):`
  > `    """Check that all strings in obj match a list of expected ascii characters."""`
  > `    allowed_chars = r"[ 0-9a-zA-Z.,\-'&(){}\[\]\\$§_?<>+*|:/’]"`
  applied to "``reporter_abbv``", edition keys and `variations`. There is no `é`, `à`, `ç`, `É`. So
  French-language reporter/court abbreviations are structurally unrepresentable (note `§` and the
  typographic apostrophe `’` *are* permitted).

19th-century typography — partial:
* Vocabulary coverage is real: README "dating from 1754 to today"; observed early reporters include
  `"Dall."` (start `1754-01-01`) , `"Dall."` (Pennsylvania, start `1754-01-01`), `"Day"` (1802),
  `"Des."` (1784), `"Add."` (1791), and nominative-only forms via `"$volume_nominative"`.
* Punctuation/spacing variation is captured in `variations` (e.g. `"A .2d"`, `"A,2d"`, `"A. 2d"`,
  `"Atl.R."`) and in the allowed-character set (`§`, `’`) — observed real variants such as
  `"F. App’x"` alongside `"F. App'x"`.
* But `eyecite/clean.py` ships only five cleaners, and only one targets scan artefacts:
  > `cleaners_lookup` = `html`, `inline_whitespace`, `all_whitespace`, `underscores`, `xml`
  > `def underscores(text: str): """Remove strings of two or more underscores that are common in text extracted from PDFs."""`
  There is **no** long-s (ſ) normalisation, no ligature handling, no archaic-abbreviation expansion.
  The documented escape hatch is a user-supplied callable — README.rst:
  > "Custom function: any function taking a string and returning a string."
  and README.rst notes "test_FindTest.py includes a simplified example of using a custom tokenizer that uses modified regular expressions to extract citations with OCR errors."
* OCR on historical text measurably corrupts results in production —
  https://github.com/freelawproject/courtlistener/issues/6169:
  > "[97396 cited Mount Pleasant v. Beckwith] … there is an OCR error with the citation, it should be 100 U. S. 520 based on the PDF. Second, because of the wrong citation, the citation link takes us to a different opinion"

### 2e. Any published accuracy / precision / recall evaluation?

**no gold-standard precision/recall evaluation found. The in-repo "accuracy" benchmark is a
branch-to-branch diff, not a measured accuracy figure.**
`benchmark/benchmark.py`, https://raw.githubusercontent.com/freelawproject/eyecite/main/benchmark/benchmark.py:
> "``base`` is the baseline branch (main / original); ``pr`` is the
> updated branch. A *gain* is a citation the PR finds that the base
> did not; a *loss* is one the base found that the PR no longer does."
README.rst:
> "When a pull request is generated for changes to eyecite, a github workflow will automatically trigger. The workflow, benchmark.yml will test improvements in accuracy and speed against the current main branch."
It runs over CourtListener's own bulk CSV (`row["xml_harvard"] or row["html_lawbox"] or
row["html_columbia"] or row["html_anon_2020"] or row["html"]`) and reports counts of added/removed
citation strings — i.e. **relative recall deltas against the previous version of itself**, with no
labelled ground truth and no precision measurement. A JOSS paper exists
(Cushman, Dahl & Lissner, *eyecite: A tool for parsing legal citations*, JOSS 6(66):3617,
https://doi.org/10.21105/joss.03617) but its full text was **not retrievable** in this session
(`web_fetch` returned `unsupported content type "application/pdf"`), so any accuracy figures it may
contain are UNVERIFIED.
License: BSD — README.rst: "This repository is available under the permissive BSD license, making it
easy and safe to incorporate in your own libraries."

---

## Q3 — CourtListener citation graph

### 3a. What exactly is in the graph? Is the unit an opinion-to-opinion edge? Does `depth` count mentions?

**Unit = opinion-to-opinion edge. `depth` = number of times the cited opinion is referenced in the
citing opinion.**
https://wiki.free.law/c/courtlistener/help/api/rest/v4/citations —
> "This endpoint provides an interface into the citation graph that CourtListener provides between opinions in our case law database."
> "The `depth` field indicates how many times the cited opinion is referenced by the citing opinion. In the example above opinion `10008139` references _Obergefell_ (`2812209`) four times. This may indicate that _Obergefell_ is an important authority for `10008139`."
Edge payload (`OPTIONS` filter list and example response, same page): only `id`, `citing_opinion`,
`cited_opinion`, `depth` (plus `resource_uri`). There is **no jurisdiction, reporter or origin field
on an edge.**

Bulk table, https://wiki.free.law/c/courtlistener/help/api/bulk-data/bulk-legal-data —
> "**Citations Map** — This is a narrow table that indicates which opinion cited which and how deeply."
> `COPY public.search_opinionscited (id, depth, cited_opinion_id, citing_opinion_id) FROM ...`

A second, different bulk artefact carries citation strings: `citations-$DATE.csv.bz`, described at
https://wiki.free.law/c/courtlistener/help/api/bulk-data/citation-crosswalk-for-parallel-citations —
> "This is a CSV that has one row for each citation in our system. The columns are for the volume, reporter abbreviation, page, and decision ID."

### 3b. Geographic coverage — US-only? Canadian cases or citations to non-US courts?

**US-only. Canada is not represented at all; the only non-US courts modelled are three English ones.**

* Coverage statement, https://wiki.free.law/c/courtlistener/help/data-coverage/case-law —
  > "CourtListener has one of the most comprehensive collections of American case law on the Internet."
  > "Our database encompasses more than 99.9% of all precedential legal case law published in the United States"
  > "Our hope is that when our work is done, it will never need to be done again — All American jurisprudence will be available to all, forever."
* Live API check — **verified firsthand, anonymous GET**:
  `https://www.courtlistener.com/api/rest/v4/courts/?jurisdiction=I` →
  `{"count":3, ...}` and the three results are:
  * `kingsbench` — `"full_name":"Court of King's Bench"`, `"jurisdiction":"I"`, `"in_use":true`, `"has_opinion_scraper":false`, `"start_date":"1200-01-01"`, `"end_date":"1873-12-31"`
  * `houseoflordsuk` — `"full_name":"House of Lords (UK)"`, `"jurisdiction":"I"`, `"in_use":false`, `"has_opinion_scraper":false`
  * `highctjchuk` — `"full_name":"High Court of Justice, Chancery Division"`, `"jurisdiction":"I"`, `"in_use":false`, `"has_opinion_scraper":false`
* No Canadian jurisdiction code exists — `https://www.courtlistener.com/api/rest/v4/courts/?jurisdiction=CA` →
  > `{"jurisdiction":["Select a valid choice. CA is not one of the available choices."]}`
* Because an edge requires **both** endpoints to be CourtListener opinion rows
  (`citing_opinion` / `cited_opinion` are foreign keys to `/api/rest/v4/opinions/…`), a citation *to*
  a Canadian or other foreign case **cannot appear as an edge at all**. Such citations either are not
  recognised, or are recognised but unresolvable — see Q4.
* No FLP issue discusses Canadian case-law coverage (org-wide issue search for `canada`: 8 hits, all
  unrelated).

### 3c. Bulk export frequency and license?

**Quarterly, PostgreSQL `COPY TO` CSV, public-domain dedication.**
https://wiki.free.law/c/courtlistener/help/api/rest/v4/citations —
> "The citation graph is exported quarterly as part of our bulk data system."
https://wiki.free.law/c/courtlistener/help/api/bulk-data/bulk-legal-data —
> "**Generation Schedule** … bulk data files are regenerated quarterly on the last day of March, June, September, and December beginning at 3AM PST."
> "Files are generated using the [PostgreSQL `COPY TO` command] … CSV output format, in the UTF-8 encoding, with a header row on the top."
> "**Copyright** — Our bulk data files are free of known copyright restrictions." (CC Public Domain Mark 1.0)
> "Important: Files are snapshots, not deltas, meaning each file contains everything in our database at the time of generation."
Scale (two figures from two pages, slightly different snapshots):
> "To date, we have gathered 18,127,590 citations" (citation-crosswalk page)
> "Use this API to look up citations in CourtListener's database of 18,127,355 citations." (citation-lookup page)

### 3d. Documented limitations about parallel citations or coverage?

* Parallel citations — quoted in Q2b above ("We do not have every parallel citation for every
  decision. This can impact the accuracy of the graph."), and:
  > "It is difficult to collect all these citations, and nearly impossible to figure out which ones refer to the same decisions." (citation-crosswalk page)
* Lookup API limits, https://wiki.free.law/c/courtlistener/help/api/rest/v4/citation-lookup —
  > "This API will not attempt to match citations without volume numbers or page numbers (e.g. 22 U.S. \_\_\_)."
  > "This API does not look up statutes, law journals, id, or supra citations. If you wish to match such citations, please use Eyecite directly."
  > "The API will look up at most 250 citations in any single request." / "throttled to 60 valid citations per minute" / "64,000 characters at a time"
* Known data-quality defects, https://github.com/freelawproject/courtlistener/issues/6169 —
  > "- **Exposure:** Large. Of 182 randomly sampled opinions, 75 of them (listed below) had this issue, which is ~40% of the opinions"  (self-authority entries)
  > "- **Exposure:** Medium. There aren't that many, but this is also not a small list from 182 randomly sampled opinions (If this sample is of any indication of the population, this tells us ~10% of the opinions has at least 1 wrong citation links)"  (wrong citation links)
  > "- **Exposure:** Minimal, only the handful of cases listed below from 182 randomly sampled opinions"  (listed-but-not-cited; wrong citation)
* Ambiguity is a first-class outcome, not an error: status `300 (Multiple Choices)` with example
  `1 H. 150` → `"normalized_citations": ["1 Handy 150","1 Haw. 150","1 Hill 150"]` — three US reporters
  for one abbreviation, resolved only against the US corpus.

---

## Q4 (decisive) — Does any component resolve the JURISDICTION / ORIGIN of the CITED case?

**No. None of the three components outputs the jurisdiction, country or legal origin of a cited case,
and none distinguishes foreign from domestic citations. All three only recognise/link citations that
resolve inside the US-scoped FLP corpus.**

Evidence, component by component:

1. **`reporters_db` has jurisdiction data, but it is US-only, unmapped for foreign entries, and it is
   not about the *cited* case's origin so much as the reporter's issuing courts.** The only
   jurisdiction-ish field is `mlz_jurisdiction`, described as third-party maintained and possibly
   absent (README.rst), US-only in every observed value (665/665 `us`-prefixed), empty for the one
   Canadian reporter found (`Dominion Tax Cas. (CCH)`), and structurally incapable of a foreign label
   because `VALID_CITE_TYPES` has no non-US member and is test-enforced (`tests.py`).

2. **`eyecite` discards jurisdiction entirely.** Its `Reporter` dataclass (`eyecite/models.py`)
   carries no jurisdiction field at all:
   > `class Reporter:`
   > `    """Class for top-level reporters in `reporters_db`, like "S.W." """`
   > `    short_name: str`
   > `    name: str`
   > `    cite_type: str`
   > `    source: str  # one of "reporters", "laws", "journals"`
   > `    is_scotus: bool = False`
   `mlz_jurisdiction` never reaches the caller. The **only** reporter-derived court inference in
   eyecite is a boolean SCOTUS test:
   > `def guess_court(self):`
   > `    """Set court based on reporter."""`
   > `    if not self.metadata.court and any(e.reporter.is_scotus for e in self.all_editions):`
   > `        self.metadata.court = "scotus"`
   (`is_scotus` is set when `cite_type == "federal" and "supreme" in name` or `"scotus" in cite_type`.)
   So eyecite can say "US Supreme Court" and nothing else about origin; it cannot say "this is a UK
   House of Lords case".

3. **CourtListener resolves citations only inside its own database, and expresses failure as
   not-found/invalid rather than as a foreign-origin label.**
   https://wiki.free.law/c/courtlistener/help/api/rest/v4/citation-lookup —
   > "`200 (OK)` — We found a citation, it was valid, and we were able to look it up in CourtListener."
   > "`404 (Not Found)` — We found a citation, it was valid, but we were unable to look it up in CourtListener."
   > "`400 (Bad Request)` — We found something that looks like a citation, but the reporter in the citation wasn't in our system (e.g., "33 Umbrella 422" looks like a citation, but is not valid)."
   > "`300 (Multiple Choices)` — We found a valid citation, it was valid, but it matched more than one item in CourtListener."
   The response payload is `citation`, `normalized_citations`, `start_index`, `end_index`, `status`,
   `error_message`, `clusters` — **there is no jurisdiction or country field**. A non-US citation is
   therefore either (a) not recognised as a citation, or (b) reported as status 400
   ("the reporter … wasn't in our system") / 404 — never as "a UK case" or "an Australian case".
   Ambiguous abbreviations resolve only to US candidates (`1 H. 150` → Handy Ohio / Haw. / Hill N.Y.).
   And the graph itself can only hold edges between CourtListener opinions (Q3b), with only three
   non-US courts modelled and two of them unused.

**Practical consequence for a Canadian pipeline:** the duplication question splits cleanly —
FLP provides no Canadian reporter vocabulary, no Canadian neutral-citation court codes, no
French-language handling, and no mechanism to label or separate foreign citations from domestic ones.
Any Canadian pipeline must supply its own reporter/jurisdiction/court-code tables, its own
foreign-vs-domestic discrimination, and French/Quebec handling. What is genuinely reusable (and
already built) is the *generic citation-extraction machinery*: eyecite's tokenizer/regex/annotate/
resolve architecture (BSD) and the reporters_db schema pattern (BSD), plus the public-domain
CourtListener bulk citation data — but only as US-corpus scaffolding, and only if the pipeline can
represent non-US jurisdictions, which reporters_db's schema cannot.

---

## Capability table

| # | Capability | Yes/No/Partial | Evidence URL | Verbatim quote |
|---|---|---|---|---|
| 1 | reporters_db includes Canadian reporters | **No** | https://free.law/projects/reporters-db/ | "structured information about nearly every American legal reporter" |
| 2 | reporters_db covers non-US jurisdictions at all | **No** | https://raw.githubusercontent.com/freelawproject/reporters-db/main/tests.py | `VALID_CITE_TYPES = ("federal","neutral","scotus_early","specialty","specialty_west","specialty_lexis","state","state_regional")` — no foreign type |
| 3 | reporters_db maps each reporter to a jurisdiction | **Yes (US-only)** | https://raw.githubusercontent.com/freelawproject/reporters-db/main/README.rst | "``mlz_jurisdiction`` corresponds to the work that is being done for Multi-Lingual Zotero. This field is maintained by Frank Bennett and may sometimes be missing values." |
| 4 | reporters_db has a separate jurisdictions file/count | **No** | https://api.github.com/repos/freelawproject/reporters-db/contents/reporters_db/data | data dir lists only `case_name_abbreviations.json, journals.json, laws.json, regexes.json, reporters.csv, reporters.json, state_abbreviations.json` (no `jurisdictions.json`) |
| 5 | Multiple/parallel abbreviations + name variants per reporter | **Yes** | https://raw.githubusercontent.com/freelawproject/reporters-db/main/README.rst | "Each Reporter key maps to a list of reporters that that key can represent." / "``NAMES_TO_EDITIONS`` … For example, ``Atlantic Reporter`` maps to ``['A.', 'A.2d']``." |
| 6 | Neutral citation formats supported | **Partial (US only)** | https://raw.githubusercontent.com/freelawproject/reporters-db/main/reporters_db/data/regexes.json | `"format_neutral": {"": "$volume_year-$reporter-$page", "#": "Format neutral cite, like '2000-Ohio-123'"}` |
| 7 | Neutral citation formats for Canadian courts (SCC/ONCA) | **No / UNVERIFIED** | https://github.com/freelawproject/reporters-db/issues/184 | "I'd like to rename that as Ohio Natural and make Format Neutral to be a pattern without dashes." (open) |
| 8 | Reporter count known | **Yes — 1,167** | https://raw.githubusercontent.com/freelawproject/reporters-db/main/README.rst | "As of version 3.2.32, this data contains information about 1,167 reporters and 2,102 name variations." |
| 9 | Jurisdiction count known | **No** | — | none published (no `jurisdictions.json`, no count in README) |
| 10 | reporters_db license / redistributable | **Yes — BSD-2-Clause** | https://api.github.com/repos/freelawproject/reporters-db | `"license":{"key":"bsd-2-clause","spdx_id":"BSD-2-Clause"}` |
| 11 | eyecite extracts full case citations | **Yes** | https://raw.githubusercontent.com/freelawproject/eyecite/main/eyecite/models.py | `class FullCaseCitation(CaseCitation, FullCitation):` "represents a standard, fully named citation" |
| 12 | eyecite extracts statute/law citations | **Yes** | https://raw.githubusercontent.com/freelawproject/eyecite/main/eyecite/models.py | `class FullLawCitation(FullCitation): """Citation to a source from reporters_db/laws.json."""` |
| 13 | eyecite extracts journal citations | **Yes** | https://raw.githubusercontent.com/freelawproject/eyecite/main/eyecite/models.py | `class FullJournalCitation(FullCitation): """Citation to a source from reporters_db/journals.json."""` |
| 14 | eyecite extracts `id.` / `supra` | **Yes** | https://raw.githubusercontent.com/freelawproject/eyecite/main/eyecite/models.py | `class IdCitation(CitationBase): """…an 'id' or 'ibid' citation…"""` ; `class SupraCitation(CitationBase):` |
| 15 | eyecite extracts short-form case citations | **Yes** | https://raw.githubusercontent.com/freelawproject/eyecite/main/eyecite/models.py | `class ShortCaseCitation(CaseCitation):` "short form citation … `Adarand, 515 U.S., at 241`" |
| 16 | eyecite extracts reference citations ("Foo at 552") | **Yes (two-step)** | https://raw.githubusercontent.com/freelawproject/eyecite/main/eyecite/models.py | "A reference citation is a citation that refers to a full case citation by name and pincite alone. Future versions hopefully with drop the pincite requirement. Examples: Roe at 240" |
| 17 | eyecite detects parallel citations | **Partial** | https://raw.githubusercontent.com/freelawproject/eyecite/main/eyecite/models.py | `def is_parallel_citation(self, preceding): """Check if preceding citation is parallel"""` (merges names when `full_span_start` matches; no canonical mapping) |
| 18 | eyecite resolves citations to a canonical resource | **Yes, text-internal only** | https://raw.githubusercontent.com/freelawproject/eyecite/main/eyecite/resolve.py | "eyecite performs these resolutions using only its immanent knowledge about each citation's textual representation." |
| 19 | eyecite self-citation exclusion | **No** | https://github.com/freelawproject/courtlistener/issues/6169 | "Of 182 randomly sampled opinions, 75 of them … had this issue, which is ~40% of the opinions" (open issue, proposed fix not implemented) |
| 20 | eyecite handles French / non-English text | **No** | https://raw.githubusercontent.com/freelawproject/reporters-db/main/tests.py | `allowed_chars = r"[ 0-9a-zA-Z.,\-'&(){}\[\]\\$§_?<>+*|:/’]"` — accented Latin characters not representable |
| 21 | eyecite handles 19th-century material | **Partial** | https://raw.githubusercontent.com/freelawproject/eyecite/main/eyecite/clean.py | only `html`, `inline_whitespace`, `all_whitespace`, `underscores`, `xml`; "Remove strings of two or more underscores that are common in text extracted from PDFs" |
| 22 | Published accuracy/precision/recall evaluation | **No (in-repo benchmark is a diff)** | https://raw.githubusercontent.com/freelawproject/eyecite/main/benchmark/benchmark.py | "A *gain* is a citation the PR finds that the base did not; a *loss* is one the base found that the PR no longer does." |
| 23 | eyecite license | **Yes — BSD** | https://raw.githubusercontent.com/freelawproject/eyecite/main/README.rst | "This repository is available under the permissive BSD license, and safe to incorporate in your own libraries." |
| 24 | Graph unit is opinion-to-opinion edge | **Yes** | https://wiki.free.law/c/courtlistener/help/api/rest/v4/citations | "an interface into the citation graph that CourtListener provides between opinions in our case law database" |
| 25 | `depth` counts mentions within the citing opinion | **Yes** | https://wiki.free.law/c/courtlistener/help/api/rest/v4/citations | "The `depth` field indicates how many times the cited opinion is referenced by the citing opinion." |
| 26 | Graph is US-only | **Yes** | https://wiki.free.law/c/courtlistener/help/data-coverage/case-law | "Our database encompasses more than 99.9% of all precedential legal case law published in the United States" |
| 27 | Graph includes Canadian cases | **No** | https://www.courtlistener.com/api/rest/v4/courts/?jurisdiction=CA | `{"jurisdiction":["Select a valid choice. CA is not one of the available choices."]}` |
| 28 | Non-US (foreign) courts modelled | **Partial — 3 English, 2 unused** | https://www.courtlistener.com/api/rest/v4/courts/?jurisdiction=I | `{"count":3,…}` → `kingsbench` (`"in_use":true`), `houseoflordsuk` (`"in_use":false`), `highctjchuk` (`"in_use":false`) |
| 29 | Citations to non-US courts appear as graph edges | **No** | https://www.courtlistener.com/api/rest/v4/citation-lookup/ (docs) | edges need `citing_opinion`/`cited_opinion` opinion rows; unknown reporters are rejected: "the reporter in the citation wasn't in our system" |
| 30 | Bulk export of the graph | **Yes — quarterly** | https://wiki.free.law/c/courtlistener/help/api/rest/v4/citations | "The citation graph is exported quarterly as part of our bulk data system." |
| 31 | Bulk data license | **Yes — public domain** | https://wiki.free.law/c/courtlistener/help/api/bulk-data/bulk-legal-data | "Our bulk data files are free of known copyright restrictions." (CC Public Domain Mark 1.0) |
| 32 | Documented parallel-citation limitation | **Yes** | https://wiki.free.law/c/courtlistener/help/api/rest/v4/citations | "We do not have every parallel citation for every decision. This can impact the accuracy of the graph." |
| 33 | **Resolves jurisdiction/origin of the CITED case** | **No** | https://raw.githubusercontent.com/freelawproject/eyecite/main/eyecite/models.py | `class Reporter:` has only `short_name, name, cite_type, source, is_scotus` — `mlz_jurisdiction` is dropped |
| 34 | **Distinguishes foreign vs domestic citations** | **No** | https://wiki.free.law/c/courtlistener/help/api/rest/v4/citation-lookup | "`404 (Not Found)` — We found a citation, it was valid, but we were unable to look it up in CourtListener." (failure, not a foreign label) |
| 35 | Only reporter-derived court inference in eyecite | **SCOTUS only** | https://raw.githubusercontent.com/freelawproject/eyecite/main/eyecite/models.py | `def guess_court(self): """Set court based on reporter.""" … self.metadata.court = "scotus"` |

---

## What they definitively do NOT do

1. **No Canadian reporter vocabulary.** reporters_db is US-scoped by design; the `cite_type`
   vocabulary is a closed 8-value, test-enforced set with no foreign member, and every observed
   jurisdiction value is `us`-prefixed.
2. **No Canadian neutral-citation court codes.** Neutral support exists, but the pattern and all
   observed examples are US (`2000-Ohio-123`, `2000-NMSC-123`); no `SCC`/`ONCA`/`CSC` code was
   observed, and adding dash-less neutral patterns is still an open issue.
3. **No jurisdiction/origin output for a cited case — from any component.** eyecite's `Reporter`
   model drops `mlz_jurisdiction`; the only court it can infer is SCOTUS. CourtListener's citation
   APIs return no jurisdiction/country field.
4. **No foreign-vs-domestic discrimination.** Non-US citations are not labelled foreign — they are
   rejected as "not in our system" (status 400), left unresolved (status 404), or, where an
   abbreviation collides with a US reporter, silently resolved to a US case (the documented
   `300 Multiple Choices` path, e.g. `1 H. 150` → three US reporters).
5. **No linkage to any case outside CourtListener's US corpus.** An edge requires both endpoints to
   be CourtListener opinions; only three non-US courts exist (all English, two with `in_use:false`),
   and Canada has no jurisdiction code at all.
6. **No French-language handling.** No language parameter, no accented characters permitted in
   reporter data, no multilingual cleaners.
7. **No 19th-century typography normalisation** (no long-s, ligatures, or archaic-abbreviation
   expansion) — only generic whitespace/underscore cleaning plus a custom-callable hook.
8. **No self-citation exclusion.** Measured at ~40% of a 182-opinion sample; the fix is proposed but
   the issue is open.
9. **No published precision/recall evaluation.** The in-repo benchmark counts citation strings gained
   and lost between two branches of eyecite on CourtListener's own bulk data.

---

## UNVERIFIED

1. **Whether `S.C.R.`, `D.L.R.`, `C.C.C.`, `O.R.` or `W.W.R.` appear anywhere in
   `reporters_db/data/reporters.json`.** The 907,920-byte file could not be downloaded or grepped in
   this environment (no shell network; ~100 KB web-fetch cap). Observable windows were `"A."`→`"Bibb"`
   (JSON) and `A.`→`B.R.` + `D.S.D.`→`F. Cas.` (CSV): this verifies `A.C.` absent, and shows
   `Dominion Tax Cas. (CCH)` present with no jurisdiction, but the C block and the start of the D block
   (where `D.L.R.` would sort, before `D.S.D.`) were truncated. Strong circumstantial evidence says
   absent (US-only sources, closed US `cite_type` vocabulary, no `canada` issue in either repo), but
   **absence of these five specific abbreviations was not directly observed.**
2. **Whether `SCC`/`CSC`/`ONCA`/`QCCA` exist as keys or variation strings.** Same limitation.
3. **The exact number of jurisdictions in reporters_db.** No count is published and no
   `jurisdictions.json` exists.
4. **Counts for `laws.json` and `journals.json`** (file sizes verified; entry counts not).
5. **Whether the JOSS 2021 eyecite paper reports precision/recall figures.** The paper exists
   (10.21105/joss.03617) but the PDF was not retrievable (`unsupported content type "application/pdf"`),
   and the review thread contains no paper body text.
6. **Whether eyecite populates `metadata.court` from a citation's own parenthetical** (e.g.
   `(4th Cir. 1982)` → a US circuit code) via `courts_db`. Not verified in this session — only the
   SCOTUS path in `guess_court()` was read directly. This would still be US-only and is a property of
   the *citing* citation's stated court, not the cited case's origin.
7. **The claim that CourtListener holds "241 clusters" of King's Bench opinions.** This number appears
   inside the body of reporters-db issue #267 in a block explicitly labelled `"From Claude:"`
   (AI-generated text in a user-authored issue) and was not verified against the API.
8. **Whether any text outside `reporters_db`, `eyecite` and FLP bulk data already provides Canadian
   reporter/neutral-citation tables** (e.g. CanLII, the Canadian Citation Committee standard, McGill
   Guide Appendix B-3). The Canadian neutral-citation standard itself was verified as a public
   standard (lexum.com/ccc-ccr), but no open machine-readable Canadian reporter table was evaluated;
   this was outside the requested scope.
