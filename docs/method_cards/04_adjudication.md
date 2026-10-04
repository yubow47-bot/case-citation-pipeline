# Layer 4: adjudication

## What this layer does

The only judgements that require "knowing which case this is first", which is why it comes after merging. **DD is finally counted here**, and case identity (which printed strings are the same case) is established here too.

- Input: each court's merge-layer output (`merged.csv`, `folded_log.csv`, `decision_ids.csv`).
- First one round within each court (`--court X`), then one round across courts (`--cross-court --inputs ...`).
- Output (`decide_out/<court>/` and `decide_out/cross_court/`) [verified: directory listing and `decided.csv` header]:
  - `decided.csv`: on top of the merge-layer columns, adds `court`, `key_occurrence_count`, `identity_basis`, `member_origin_*`, `merged_group_id`, `is_primary`, `split_flag`/`split_seq`/`split_reason`, `same_name_near_year_peers`, `group_origin_*`, `group_foreign_status`, `foreign_status`, `origin_country`, `case_origin`, etc.;
  - `effective_sources.csv`: **the authoritative group → source-judgment link** (`status=counted` or `excluded_self`); `edges.py` consumes only this;
  - `decision_ids.csv`, `mixed_identity_holdouts.csv`, `typo_over_registered.csv` (trace), `manifest.json`.
- Constraint six: the adjudication layer may **overrule** the merge layer's folding conclusions and split them apart, but **never edits the merge layer's output files**.

## What it is responsible for

### 1. Case identity (which keys are the same case)

- **Identity anchors**: neutral citations, or "the citation printed in the header of a corpus judgment itself" (`self_citation_of`, #55). Reporter anchors merge only on an identical key and do not go through `same_decision()` (which resolves by neutral citation and ignores volume).
- **Same name + year means the same case** (`nk(case_name_modal)` equal and years within ±1, §10.3): parallel reporters are merged. This is **heuristic**.
- **Splitting**:
  - Chained merging strings together chimeras spanning decades (`R. v. Smith` 2001–2023, 93 members, #48) → chains with a year span >1 are split with a ±1-year window;
  - Different judgments with same-named parties must not be merged (#49): only one judgment per court per year; bilingual codes with the same number and year merge; a one-digit number difference counts as a typo only when citation counts differ sharply; co-citation coefficient ≥0.8 before assignment;
  - One printed string shared by two different corpus judgments → split by judgment (#55).
- **The "neutral citation start year" of a corpus court**: "neutral citations" before that year are not identity anchors (`1994 SCC 80` is noise, #56). The criterion needs positive evidence on both sides, both taken from the citations printed in the headers of that court's own judgments.
- **Typo folding** (one-digit number difference, sharply different citation counts) is gated by the three-tier test in `mixed_identity()` (#88, on by default, disable with `--no-mixed-key-holdout`):
  - The mentions print only the folding target's name → merge;
  - No name, or none with the same name → leave alone;
  - Some print the target's name and some print another name → **hold out** (no merge, its case name suppressed, out of the identity-root contest).
  - Missing any one of these reproduces the regression (`211 D.L.R. (4th) 577` dropped from DD 602 to 21).
- **A member's `identity_basis`** [verified: `decide.py:1160`]: `anchor`, `singleton` (6), `same_citation` (5), `anchor_variant_bilingual` (4), `anchor_variant_typo_number/year` (3), `name_year` (2), `cocitation`, `unanchored` (1).
  - **Only the first four (`ELIGIBLE_BASES`) authorize propagating a group-level conclusion**; `name_year`, typo variants, `cocitation` and `unanchored` are heuristic: they stay visible and provisional, and member evidence must not be promoted to a group conclusion.

### 2. How DD is counted

- DD = the cardinality of the **union of judgment ids** over all member keys of the group, **excluding self-citations**.
- Self-citation removal has three layers:
  1. The classification layer flags `self_citation` and the merge layer does not count it (row level);
  2. The adjudication layer removes **the identity root's own judgment id** (#54); for a key merged in as a typo, a judgment that cites the group is still a real citation;
  3. New (#105, 2026-10-03): `decision_own_citations.csv` (keys built from each judgment's own `citation_en`+`citation2_en`) plus `own_citation_self_ids()` (`decide.py:579`): a source judgment that **mentions the group only through keys it prints for itself** → treated as mentioning itself, not counted. If it also mentions the group through another key (e.g. an SCC judgment citing the lower-court judgment it is an appeal from), it is **kept**.
- **The DD definition (user decision 2026-10-03)**: DD = the number of different source judgments that mention the case, **not limited to citing it as precedent**. Procedural-history relations count towards DD and are flagged separately by relation type (`tools/foundation/relations.py`: `same_case_history` / `other_judgment`, flagged by identity, not by wording).
- A source judgment contributes DD to a group only once.

### 3. Case-level place of origin (`case_origin`): a three-tier priority waterfall

Lookups happen at the **member-string level**, not the merged-group level (each record after splitting is looked up on its own). Three tiers:

1. `case_record`: `case_origin.csv` (204 rows, CanLII's Privy Council database) plus `case_origin_manual.csv` (case-by-case manual verification);
2. `court_scope_rule`: `court_or_reporter_scope.csv` (exclusive place-of-origin rules for courts/identifiers), only when the row is an accepted neutral parse and its date falls within the `valid_from`–`valid_to` window;
3. `reporter_origin_scope`: `reporter_origin_scope.csv` (exclusive reporter scope), only when `citation_kind=reporter`; the two grades `exclusive_statute` and `exclusive_publisher` differ.

None of the three hits → **`UNDETERMINED`**. `FOREIGN` can come only from a positive exclusive rule, **never from "not in the Canadian exception table"**. Cross-jurisdictional courts such as UKPC/JCPC are in no rule table, so their place of origin is always `UNDETERMINED` (#66). Two tables giving different countries for the same key → member-level `CONFLICT`, in the conservative direction.

## The registry (note how narrow its use is)

- The global judgment registry `registry/decision_registry.csv`: the citations printed by every known real judgment for itself; it is authorized only for the **typo gate** (spec 2.3). **Do not mix it into `own`** (`own` has three other uses: identity-anchor eligibility, DD self-citation exclusion, the start-year criterion).
- Default `--registry-gate literal`, measured as equivalent to the current behaviour; `--anchor-corpus` is off by default.
- The registry depends on the corpus being present (#89): when a court's corpus is missing, none of its judgments has an anchor, and same-named real judgments fuse into one group. `--anchor-corpus` only builds the registry; it neither extracts nor counts.
- **Ceiling monitor** `registry_report.py`: the original text of foreign courts' judgments is not in the corpus, and adding corpora cannot supply it.

## When adding a court

1. **The new court's judgments must be in the corpus** for the adjudication layer to use the citations printed in their own headers as identity anchors and for DD self-citation removal. If the court's `citation_en` is not a citation (CITT's file numbers), self-citation detection fails and **every judgment's DD is over-counted by one**.
2. **The court's neutral-citation start year** is derived from its own judgments' headers (`neutral_start`, #56). It does not apply when the new court has no early corpus.
3. Foreign and Privy Council cases cited by the new court: the place of origin relies on `case_origin*` and the scope rule tables; with no rule it is `UNDETERMINED`; **do not add defaults**.
4. After adding a court, re-examine: whether **different judgments** with the same name and year get merged (the `R. v. Smith` kind); whether cross-court merging (§10.6) joined the same foreign case cited several times by each of two courts.
5. Zero-padded numbers when citing other cases (#90) still form their own key and may split one case into two groups.

## Verification

- `python pipeline/tests/test_layers.py`: includes the adjudication unit assertions, 6 assertions for `own_citation_self_ids`, the mini end-to-end chain, and identity assertions on real cases such as Housen/MacKay/Oland/Gladue/Imoro/Wewaykum/Beaver.
- Hard invariants: no group contains two different corpus judgments (recomputed with the adjudication layer's own criterion); the sum of occurrence over groups == total counted rows.
- After changing an adjudication rule, **run an A/B on the same input and the same base**, checking new keys, vanished keys, changes to existing keys and changes to `kept` rows (experiment: the #88 fix gave 0 new keys, 0 vanished keys, 28 changed existing keys).
- `--golden` only proves the old output did not change; it does not prove the new rule is right (#98).

## Known pitfalls

| # | Content | Status |
|---|---|---|
| 46 | DD must be a union | Fixed |
| 47 | Occurrence inflated in the cross-court round | Fixed |
| 48 | Chained merging strung together chimeras | Fixed (split with a ±1-year window) |
| 49 | Blind spot of name+year identity: different judgments with same-named parties merged | Fixed (several criteria); residue see #55 |
| 50 | Long and short forms of a case name keep parallel citations from joining | [unverified] |
| 54 | Self-citation: every judgment adds DD+1 to itself | Fixed |
| 55 | Two different judgments in the corpus merged into one group | Fixed; residue of 56 units (DD totalling 262) falls to `unanchored` |
| 56 | "Neutral citations" before a corpus court began using them taken as identities | Fixed |
| 59 | Canadian cases appealed to the Privy Council labelled British | `case_origin` filled (covering 1888–1959) |
| 62 | Groups with the same name and years within ±1 | Flagged only, not merged (`same_name_near_year_peers`) |
| 64–68, 77, 84 (B series) | Place of origin not inferable, same-case propagation not implemented, single-anchor clusters absorb unconditionally, etc. | Recorded, mostly unfixed; status of each [unverified] |
| 75 (B12) | Single-anchor clusters absorb judgments of different instances along the way | Measured; the proposed rule was rejected |
| 88 | One printed string carrying two identities at once | Fixed (mixed-key holdout, on by default) |
| 89 | The registry depends on the corpus being present | Unfixed; the `--anchor-corpus` interface exists |
| 91 | When the suppressor is itself undecided, the suppressed real citation abstains too | Unfixed (a side effect of the rule, disclosed) |
| 97 | Inconsistent decision-table column names gave "loaded successfully, zero effect" | Fixed; the acceptance checklist adds "sample downstream fields to confirm they were filled" |
| 105 | Self-citations slipping through (zero padding, parallel citations in the header) | Fixed (2026-10-03) |
| 106 | Case identity by "case" rather than "judgment", so all instances of an old case merge into one group | **Unfixed**, needs its own design |

## Sources

Spec §10; code `pipeline/decide.py` (`decisions_of`, `same_decision`, `mixed_identity`, `assign_identity_basis`, `own_citation_self_ids`, `build_effective_sources`, `BASIS_RANK`, `ELIGIBLE_BASES`), `pipeline/registry.py`; PROBLEMS #46–#49, #54–#56, #59, #62, #64–#68, #75, #77, #84, #88, #89, #91, #97, #105, #106.

Verification status: output files, columns, identity-basis ranks and `own_citation_self_ids` checked against the code and a run (2026-10-03) [verified]; other rules [per spec]; items the specification marks "pending review" were not separately verified.
