# Verification report: the 7 open problems (2026-09-11)

Instrument: ad-hoc replayable scripts in `data/verify_*.py` (gitignored, machine
products) against `data/select_out/selected.csv` (206,213 rows), `data/classify_out/*/classified.csv`,
`data/extract_out/extracted{,_superseded}.csv`, `corpus/*.parquet`, and the ukpc
cache left by the previous session. All numbers below were re-measured, not copied
from the task description.

Legend: **VERIFIED** = reproduced as described; **REFINED** = real but with a
corrected mechanism or number; **BLOCKED** = cannot proceed as planned.

---

## P1 — Canadian PC appeals labeled "UK" — VERIFIED, fix is BLOCKED on four findings

**Phenomenon confirmed.** `[1896] A.C. 348` = `Attorney-General for Ontario v.
Attorney-General for the Dominion`, jurisdiction=GB, case_origin=UNDETERMINED,
deciding_court empty, dd=66, kept. Top of the same list: Citizens Insurance v.
Parsons (dd=59), Hodge v. The Queen (dd=58), Union Colliery (dd=49), John Deere
(dd=48), Snider (dd=41) — all GB.

**Scale re-measured (current run, group-primary counting):** 5,668 groups carry a
GB member on a PC-type reporter (A.C./App. Cas./P.C./All E.R./W.L.R./T.L.R./…),
617 kept, ~131 kept groups have a Canada place token in the name. The task text's
5,825/619 is the same magnitude; the gap is enumeration edge (likely the H.L.
family), not substance.

**Four findings that block the planned fix:**

1. **The cached ukpc list spans only 1888–1959 and holds just 643 records** —
   2 records pre-1900 (St. Catherine's Milling 1888; the 1896 A.-G. case). There
   are **zero** records titled "Citizens…/Hodge/Colliery". So *Citizens Insurance
   v. Parsons* (1881) and *Hodge v. The Queen* (1883) **cannot match — the library
   simply does not contain them.** The stated acceptance list ("Parsons, Hodge,
   John Deere, Snider should all match") will fail for Parsons and Hodge for
   source-coverage reasons, not matcher reasons. Of 603 kept PC-flagged groups,
   only **406** have a report year inside 1888–1959 at all. Realistic yield of
   this source is low hundreds of rows, not "several hundred groups" of matches.
2. **The flagship case is present in the cache but the matcher rejects it.**
   `parties("…for the Dominion")` → `({ontario}, {})` because *dominion* is in
   STOP; the CanLII title "Attorney-General for the Dominion of Canada v. …" →
   `({canada}, {ontario})`. The one-side-empty rule (`side_ok`: both empty or both
   non-empty) then kills the crossed match. Fix: normalize `Dominion → Canada`
   before tokenizing (historically exact for these titles), or allow one-side
   empty when the non-empty side matches the other record's corresponding side.
   Prefer the former; it is narrower.
3. **The only copy of `ukpc_list.json` lives in a volatile Claude scratchpad**
   (`<session temp dir>\ukpc_cache\`), while
   `data/canlii_cache/` is empty. Copy it into the repo's cache dir before
   anything else; `--offline` rebuilds die without it.
4. **Ledger hygiene:** `build_case_origin.py` cites "PROBLEMS #59", which does
   not exist yet (ledger ends at #58), and `decisions/README.md`'s tools table
   does not list the new script. `case_origin.csv` is header-only (92 bytes) —
   the consumer (`pipeline/decide.py:124` `load_case_origin`) correctly falls
   back to UNDETERMINED, so nothing downstream is broken, just empty.

**Recommended sequence:** copy the cache → fix the Dominion/CAN normalization →
adjust the acceptance list to in-cache positives (Snider, John Deere, St.
Catherine's Milling, the 1896 A.-G. case) and keep Parsons/Hodge as
expected-unmatched (they stay UNDETERMINED — the safe, undercount direction) →
run `--offline` → write the review report → register the real PROBLEMS entry
(coverage limitation 1888–1959 + residual) → rerun decide+select. Pre-1888 JCPC
coverage would need a second source (BAILII et al., license check first — same
stance as #35).

## P2 — No-"v." case names (#58) — VERIFIED, plan endorsed with one concrete acceptance test

`[1985] 1 S.C.R. 721` (Manitoba Language Rights): name empty, dd=67, kept — the
top unnamed kept row. 744 kept rows have no name. First-word buckets behind the
gap (rows rejected by #57's `name_belongs_to_later_segment`, current run):
`Re` 1,306 · `Reference` 941 · `In` 307 · `Rizzo…(Re)` 198 · `Droit de la
famille` 128 · `Ex` 73 — the claimed bucket shape, with drift from post-#57
reruns.

**Location:** `pipeline/classify.py:194-235` (`split_case_name`): `V_RE` is the
only structural anchor; `no_v_structure` rejects 143,937 SCC + 19,914 ONCA rows.

**Second-order damage confirmed, worse than described:** the Secession
Reference `[1998] 2 S.C.R. 217` exists as **two kept groups** — dd=13 (unnamed)
and dd=81 whose name is **"Air Canada v. British Columbia"** with
`case_name_agreement=1.0`. Traced to the vote: 199 classified rows, 198 rejected
(no_v_structure 118 / belongs_to_later_segment 79 / …), **1 admitted** — a
judgment that prints "Air Canada v. British Columbia, [1989] 1 S.C.R. 1161;
[1998] 2 S.C.R. 217" (semicolon + bracket start = parallel cite, so the name
attaches "legitimately" per #57's rule). One fluke voter, agreement 1.0 because
empties don't vote; and the two groups don't merge, splitting true dd 94 into
81+13. Fixing #58 should merge them under "Reference re Secession of Quebec" —
**use exactly this as an acceptance test.**

**Fix refinement:** gate on a closed marker set at segment start — `Reference
re`, `Re`, `In re`, `Ex parte`; suffix `(Re)`; plus the Quebec anonymized
patterns `Droit de la famille —`, `LSJPA —` (128+ rows measured; the plan didn't
list them). Prose leads (`see also` 46, `referred to:` 84) start with
non-markers and are additionally stripped by the existing `_ADMIT_VERB_RE`.
Acceptance: frozen prose sample zero new false names; **no currently-named row
changes its name** (names may only be gained); regression suite green;
Secession groups merge.

## P3 — Sentence-contaminated names — VERIFIED (count is rule-dependent)

Confirmed examples exactly as described: `'strict liability (presumably on the
basis of Rylands v. Fletcher'` (dd=8), `'negligence, nuisance, and the rule in
Rylands v. Fletcher'` (dd=23). My looser heuristic (≥12 words OR ≥3-word
lowercase run OR verb keywords) flags 481 kept rows — it also catches legitimate
long institutional names (*Thomson Newspapers Ltd. v. Canada (Director of
Investigation and Research…)*, dd=100, real). The claimed 342 used a tighter
rule; order of magnitude and mechanism confirmed.

**Location:** `pipeline/classify.py:221-229` — the separator scan accepts only
`; : \n`; when the nearest one is a sentence boundary (comma/period), the
candidate swallows the clause.

**Fix refinement (differs from "walk backward from v., stop at lowercase"):**
walk-backward-stop-at-lowercase breaks legitimate French names (*Commission
scolaire régionale v. …* — lowercase words inside the party). The cleaner rule
that separates the two cases: **strip the maximal leading lowercase run
(non-connector words, with embedded connectors/punctuation) from the left
party.** Contamination always *starts* lowercase ("strict liability…",
"negligence, nuisance…"); French party names *start* capitalized
("Commission…"). Examples: both Rylands cases reduce to `Rylands v. Fletcher`;
French names are untouched by construction. Guard: if stripping empties the
left party, reject the name instead. Then re-run `admit_candidate` checks.

## P4 — Same-name near-year pairs — VERIFIED EXACTLY (196)

Group-primary counting on kept groups (nk(name) equal, |Δyear| ≤ 1) reproduces
**196 pairs**. The claimed examples are all in the list: *R. v. John* 2016
ONCA 615 / 2017 ONCA 622 / [2017] S.C.C.A. No. 101 / 2018 ONCA 702 (genuinely
different judgments — correctly separate); *R. v. O'Brien* (1977), 35 C.C.C.
(2d) 209 vs [1978] 1 S.C.R. 591 (same decision, parallel cites unmerged —
exactly the #55 zero-co-citation residual). Counting caveat for the doc: row-level
counting gives 841 pairs / 223 group-pairs; the 196 figure is the primary-row
group口径 — state the口径 wherever the number is quoted.

**Fix as planned:** add a peer-reference column (e.g.
`same_name_near_year_peers` = semicolon-joined group ids) in the decide-layer
cross-court pass, flowing into `selected.csv`. Acceptance: all 196 pairs
flagged; every count column byte-identical on rerun. Low risk; do it.

## P5 — No usage notes — VERIFIED

No usage/interpretation document exists (`README.md` is architecture-only; no
LICENSE). Coverage measured for the doc: **SCC 10,891 decisions, 1877–2026;
ONCA 24,089 decisions, 1998–2026**. The parquet `upstream_license` column is
uniform per court and reads "…including non-commercial use and other
restrictions: https://perma.cc/6Z3Z-UPAC (SCC) / https://perma.cc/55T7-3UEX
(ONCA); unofficial reproduction…". `select.py:60` already carries
`THRESHOLD_CALIBRATION = "uncalibrated_placeholder_see_spec_11_2"` — cite it.
Write USAGE.md with the six planned bullets plus: undercount inventory (P4
pairs; #55's 56 unanchored units / dd 262 / 18 over threshold; occurrence
includes parallel-write self-mentions per #54 residual), and the license text
with both perma.cc links. Commercial use is Cite Counsel's call — we can only
point at the links.

## P6 — Jurisdiction table unverified — VERIFIED

`decisions/reporter_jurisdiction.csv`: 196 rows, **100% confidence=estimated,
100% verification_level=name_inference** (mix: GB 60, CA 47, QC 39, ON 13, US
12, …). The upgrade columns (`confidence`, `verification_level`, `source`,
`source_locator`) already exist, so verification is a fill-in operation, no
schema change. Prioritize by `data/coverage_out/reporter.csv` ranking, and put
the same-abbreviation multi-jurisdiction families (K.B./Q.B./S.C./P./C.L.R./
A.L.R./W.L.R.) at the front — they are where name-inference is most dangerous
and they also carry the #52 corpus-derived volume/year ranges that need the
same verification. Keep #40's guard: products must remain able to filter on
`confidence`.

## P7 — ~1% layer-1 misses — VERIFIED numbers, mechanism CORRECTED

Ground truth rebuilt from the parquet's `cases_cited_en` (bare-neutral-shaped
entries): **74,750** (decision, citation) pairs (claim: 74,754 — same
instrument). Recall of our extraction, kept spans only: **73,851/74,750 =
98.80%** — the claimed 98.8% reproduces exactly.

**But the dominant mechanism is not "never extracted".** Of 899 kept-level
misses, **872 were extracted and then lost deduplication** to a name-glued
longer span (winner shapes: vol_abbr_page 566, leading_abbr 278,
year_vol_page 28). Miazga verified in corpus (ONCA 2010 ONCA 118: "See also
Miazga v. Kvello Estate 2009 SCC 51 at para. 47"): `2009 SCC 51` was captured
by neutral_bare and **superseded by** leading_abbr "Kvello Estate 2009 SCC 51".
Winners are frequently junk keys ("6274013 Canada Limited, 2012") while the
true neutral citation is demoted. This is the known #18 no-comma-swallow
residual (1,044 rows), now precisely quantified against upstream truth. Only
**27** pairs were never extracted at all — and those look like upstream
metadata entries not printed in the judgment text (tribunal codes QCTAQ,
ONLSHP, ONSLAP…); spot-check 3–5 in the raw text before counting them as ours
to fix.

**Conflation warning:** this upstream recall 98.80% is a different number from
`audit/gap_audit.py`'s containment rate 98.81% (wide-net coverage of the seven
shapes). Coincidentally similar; label them distinctly in any document.

**Recommendation:** do not unfreeze layer 1 speculatively. Today's behavior is
the *safe* failure mode: glued rows land `unrecognized_series_prefix` /
UNSUPPORTED (1,123 such rows contain a YYYY-CODE-N shape), effect is dd
undercount ~1.2% of bare-neutral volume, nothing silently mis-jurisdictioned.
If it is ever worth fixing, the candidate is a dedup-arbitration rule with a
structural signature (neutral_bare span fully inside a leading_abbr/
vol_abbr_page span whose vol == the neutral's year and abbr == its token →
prefer the neutral), prototyped offline against the three #16 gates
(zero-destruction full diff, prose anchor 83/6, fixtures exact). Otherwise
register the 872 as a known residual with this measurement.

---

## Order of work

Endorse 1 → 2 → 3 → 4 → 5 → 6 → 7, with amendments: P1 needs the cache moved,
the Dominion normalization, and a revised acceptance list before it can run; P2
and P3 both edit `split_case_name`/`admit_candidate` — land them as separate
commits, each with a full line-diff; P7's first step is the 27-item spot check,
not a regex change.
