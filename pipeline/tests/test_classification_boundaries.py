"""Printed classification boundaries, including native Huard and Sheehy spans.

Run: python pipeline/tests/test_classification_boundaries.py
These tests load the real decision tables and run classification, without a
corpus dependency or any change to a production run.
"""
import csv
from collections import Counter
from pathlib import Path
import sys
import unittest

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))

import classify  # noqa: E402


def classifier(extra_reporters=()):
    return classify.Classifier({
        "neutral_court_codes": classify.load_table("neutral_court_codes.csv"),
        "reporter_jurisdiction": classify.load_table("reporter_jurisdiction.csv") + list(extra_reporters),
        "series_prefix": classify.load_table("series_prefix.csv"),
        "non_citation_words": classify.load_non_citation_words(),
        "non_case_sources": classify.load_non_case_sources(),
        "court_designations": classify.load_court_designations(),
        "court_designation_reporter_scope": classify.load_court_designation_reporter_scope(),
        "reporter_compound_locators": classify.load_compound_locator_rows(),
    }, Counter())


def report(abbr, *, pre="", raw=None, vol="42", page="80"):
    return {"shape_name": "shape_vol_abbr_page", "abbr": abbr, "vol": vol,
            "page": page, "raw_string": raw or f"{vol} {abbr} {page}",
            "preceding_text": pre}


def split(pre):
    row = {"preceding_text": pre, "candidate_case_name": "", "name_rejected_reason": ""}
    classify.split_case_name(row)
    return row


class FederalStatuteBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clf = classifier()

    def test_all_printed_session_years_survive_a_chapter_cut(self):
        for years in ("1970-71-72", "1970–71–72", "1970‑71‑72", "1970-1971-1972", "1992"):
            with self.subTest(years=years):
                row = self.clf.run_row(report("Payment", vol="63", page="47",
                    pre=f"Income Tax Act, S.C. {years}, c. "))
                self.assertIn("federal_statute", row["rejected_reason"])

    def test_revised_statute_alphabetic_chapter_cut_still_rejected(self):
        row = self.clf.run_row(report("Culpable Homicide", vol="46", page="252",
            pre="Criminal Code, R.S.C. 1985, c. C-"))
        self.assertIn("federal_statute", row["rejected_reason"])

    def test_completed_statute_does_not_reject_following_judgment(self):
        for pre in ("Income Tax Act, S.C. 1970-71-72, c. 63; see R. v. Smith, ",
                    "Income Tax Act, S.C. 1970–71–72, c. 63: R. v. Smith, ",
                    "Criminal Code, R.S.C. 1985, c. C-46, R. v. Smith, "):
            with self.subTest(pre=pre):
                row = self.clf.run_row(report("S.C.R.", vol="2", page="368", pre=pre))
                self.assertNotIn("federal_statute", row["rejected_reason"])

    def test_non_session_prose_does_not_satisfy_statute_cut(self):
        row = self.clf.run_row(report("S.C.R.", vol="2", page="368",
            pre="Income Tax Act, S.C. 1970-71-72, concerning c. "))
        self.assertNotIn("federal_statute", row["rejected_reason"])


class LaterCaseNameTests(unittest.TestCase):
    def test_later_party_names_are_preserved_whole(self):
        names = (
            "Commission scolaire régionale de Chambly v. Bergevin",
            "Commission scolaire Marie-Victorin v. Parent",
            "Québec (Procureur général) v. Lambert",
            "Union des employés de commerce, local 503 v. Roy",
            "Hôpital général de Québec Inc. v. Perron",
            "1420041 Ontario Inc. v. 1 King West Inc.",
            "Voyageur (1969) Inc. v. Ally",
            "Voyageur (1969) Holdings v. Ally",
            "Union des employés de commerce, local 503, Division Nord v. Roy",
            "The King v. Sunfield",
            "St. Lawrence Cement Inc. v. Wakeham",
        )
        for name in names:
            for prior in ("R. v. Smith, 2000 SCC 1, and ",
                          "R. v. Smith (1989), 19 M.V.R. (2d) 258 and ",
                          "R. v. Smith, [1990] C.A.I. 438 (C.Q.), and "):
                with self.subTest(name=name, prior=prior):
                    row = split("; " + prior + name + ", ")
                    self.assertEqual(row["candidate_case_name"], name.rstrip("."))
                    self.assertEqual(row["name_rejected_reason"], "")

    def test_native_huard_does_not_borrow_wilson(self):
        # ONCA_c26083, corpus row 16687, candidate offsets 7909/7917..7935.
        for pre in (
            "erred to with approval at the trial level in this province: see R. v. Wilson "
            "(1989), 19 M.V.R. (2d) 258 and R. v. Huard ",
            " with approval at the trial level in this province: see R. v. Wilson "
            "(1989), 19 M.V.R. (2d) 258 and R. v. Huard (1992), ",
        ):
            with self.subTest(pre=pre):
                self.assertEqual(split(pre)["candidate_case_name"], "R. v. Huard")

    def test_native_complete_prior_citation_supplies_missing_outer_separator(self):
        # SCC_2002scc71, corpus row 2817, candidate 60453..60470.
        pre = (" already been decided in Université Laval v. Albert, [1990] C.A.I. 438 "
               "(C.Q.), and Québec (Procureur général) v. Bayle, ")
        self.assertEqual(split(pre)["candidate_case_name"], "Québec (Procureur général) v. Bayle")

    def test_pinpoints_history_and_personal_signals_do_not_pollute_later_name(self):
        for pre, expected in (
            (": R. v. Askov (1990), 59 C.C.C. (3d) 449 at 483-84, and R. v. Morin (1992), ",
             "R. v. Morin"),
            ("; R. v. Shropshire, [1995] 4 S.C.R. 227). As Laskin J.A. explained in R. v. McKnight (1999), ",
             "R. v. McKnight"),
            (": R. v. Friesen, 2020 SCC 9 at para. 26, citing R. v. McKnight ", "R. v. McKnight"),
            ("; R. v. Grover (1990), 56 C.C.C. (3d) 532 (Ont. C.A.), aff'd R. v. Grover, ", "R. v. Grover"),
        ):
            with self.subTest(pre=pre):
                self.assertEqual(split(pre)["candidate_case_name"], expected)

    def test_unproved_later_boundary_never_borrows_first_name(self):
        row = split("; Alpha v. Beta and Gamma v. Delta, ")
        self.assertEqual(row["candidate_case_name"], "")
        self.assertEqual(row["name_rejected_reason"], "multi_v")
        # Direct admission must not strip the last anchor with a citation tail.
        name, reason = classify.admit_candidate("Alpha v. Beta, 2001 TEST 99, Gamma v. Delta")
        self.assertIsNone(name)
        self.assertEqual(reason, "multi_v")

    def test_single_name_and_same_case_parallel_route_remain(self):
        for pre, expected in (
            ("; Québec (Procureur général) v. Lambert, ", "Québec (Procureur général) v. Lambert"),
            ("; Voyageur (1969) Inc. v. Ally, ", "Voyageur (1969) Inc. v. Ally"),
            ("; Housen v. Nikolaisen, 2002 SCC 33; ", "Housen v. Nikolaisen"),
        ):
            self.assertEqual(split(pre)["candidate_case_name"], expected)
        self.assertEqual(split("R. v. Smith, ")["name_rejected_reason"], "no_separator_before_v")

    def test_french_crown_anchor_is_narrow(self):
        for title in ("R. c. Huard", "R.c. Huard"):
            self.assertEqual(split("; " + title + ", ")["candidate_case_name"], title)
            self.assertEqual(split("; R. v. Smith, 2000 SCC 1, and " + title + ", ")
                             ["candidate_case_name"], title)
        for text in ("c. 47", "R.C.S. 486", "Re chapitre c. 47"):
            self.assertFalse(classify.V_RE.search(text), text)

    def test_native_context_regressions_keep_the_later_title_clean(self):
        # Exact native contexts reviewed in the full3 name delta. The names
        # below cover court/database labels, prose, pinpoints and paragraph
        # boundaries, without requiring a case-name whitelist in production.
        for pre, expected in (
            ('; Meyer v. Chou, [1985] B.C.J. No. 1568 (QL) (S.C.) citing Shea v. Miller ',
             'Shea v. Miller'),
            ('; BCGEU v. British Columbia [1988] 2 S.C.R. 214, per Chief Justice Dickson at 243, and R. v. Rahey ',
             'R. v. Rahey'),
            ('; Housen v. Nikolaisen, 2002 SCC 33 at paras. 8, 10, 25 and 36, and Sattva Capital Corp. v. Creston Moly Corp., ',
             'Sattva Capital Corp. v. Creston Moly Corp'),
            ('; R. v. K.(A.) (1999), 45 O.R. (3d) 641 (C.A.), per Charron J., at 678. [29] In R. v. Marquard ',
             'R. v. Marquard'),
            ('; R. v. Mohamad, 2018 ONCA 966, 369 C.C.C. (3d) 211, at paras. 100-104. Hourigan J.A. noted in R. v. Tsega, ',
             'R. v. Tsega'),
            ('; R. c. Gagnon, 2006 CSC 17, [2006] 1 R.C.S. 621, au para. 20 et R. v. R.A., ',
             'R. v. R.A'),
            ('; R. v. White, [1998] 2 S.C.R. 72, 1998 CanLII 789 ["White #1"], and R. v. White, ',
             'R. v. White'),
            ('; Mohave Tribe v. United States, 7 Ind. Cl. Comm. 219, 260-61 (1959), Washoe Tribe v. United States, ',
             'Washoe Tribe v. United States'),
            ('; The Children’s Lawyer v. Penman, 2013 ONSC 1471, aff’d (sub nom. Penman (Litigation guardian of) v. Penman) ',
             'Penman (Litigation guardian of) v. Penman'),
            ('; R. v. Theriault (unreported) and R. v. Johnson & Creanza, ',
             'R. v. Johnson & Creanza'),
            ('; Borowski v. Canada (Attorney General), [1989] 1 S.C.R. 342 at 354, citing The King ex rel. Tolfree v. Clark, ',
             'The King ex rel. Tolfree v. Clark'),
            ('; Culina v. Giuliani, [1972] S.C.R. 343, at pp. 357-58, citing Southern Foundries (1926), Ltd. v. Shirlaw, ',
             'Southern Foundries (1926), Ltd. v. Shirlaw'),
            ('; In Tidesley [sic] v. Harper, 10 Ch. D. pp. 396, 397 [Tildesley v. Harper ',
             'Tildesley v. Harper'),
            ('; Moran v. Pyle was applied by this court in 1990 in G.W.L. Properties Ltd. v. Grace & Co.-Conn., ',
             'G.W.L. Properties Ltd. v. Grace & Co.-Conn'),
            ('; R. v. Joanisse, [1995] O.J. No. 2883 at para. 80 (O.C.A.). In R. v. Dunbar, ',
             'R. v. Dunbar'),
            ('; R. v. Newton, at paras. 11, 13 R. v. Minor, ', 'R. v. Minor'),
            ('; R. v. Lippé, supra, at pp. 142-43 (Lamer C.J.)). Starting with R. v. Lyons, ',
             'R. v. Lyons'),
        ):
            with self.subTest(pre=pre):
                self.assertEqual(split(pre)["candidate_case_name"], expected)


    def test_native_restored_names_exclude_closed_commentary_prefixes(self):
        # Discovery samples: BCCA_2007bcca270, BCCA_2007bcca215,
        # SCC_19921scr901, SCC_2010scc22 and BCCA_1999bcca309.
        for pre, expected in (
            ('rt reiterated this principle in R. v. Daviault, [1994] 3 S.C.R. 63, 93 C.C.C. (3d) 21, Théroux, supra, and R. v. Stone, ',
             'R. v. Stone'),
            ('e v. Jordan, [1981] 1 All E.R. 267 (C.A.) at 281, adopted by Craig J.A. in Smith v. British Columbia (Attorney General) ',
             'Smith v. British Columbia (Attorney General)'),
            (' Saskatchewan v. John East Ironworks, Ltd., [1949] A.C. 134 (P.C.). Finally, in Tomko v. Labour Relations Board (N.S.), ',
             'Tomko v. Labour Relations Board (N.S.)'),
            ('sn. v. Douglas College, [1990] 3 S.C.R. 570, followed in 1991 by Cuddy Chicks Ltd. v. Ontario (Labour Relations Board), ',
             'Cuddy Chicks Ltd. v. Ontario (Labour Relations Board)'),
            ('ardian ad litem) v. Robinson (1993), 75 B.C.L.R. (2d) 273 (B.C.C.A.), and in 1996 by Giles v. Canada (Attorney General) ',
             'Giles v. Canada (Attorney General)'),
        ):
            with self.subTest(pre=pre):
                self.assertEqual(split(pre)['candidate_case_name'], expected)

    def test_native_restored_name_signal_variants(self):
        # Other contexts found by scanning every newly restored name, not just
        # longer names. These are printed closed signals, not name whitelists.
        for pre, expected in (
            ('; Alpha v. Beta, [2000] 1 S.C.R. 1, Norman, Evoy, supra, Henigman, R. v. Ubhi, ', 'R. v. Ubhi'),
            ('; Alpha v. Beta, [2000] 1 S.C.R. 1, Serup supra at 264 Esteban Mgmt. Corp. v. Edelweiss Int. Hldg. Corp., ',
             'Esteban Mgmt. Corp. v. Edelweiss Int. Hldg. Corp'),
            ('; Alpha v. Beta, [2000] 1 S.C.R. 1, Bateman J.A. of the Nova Scotia Court of Appeal, in R. v. Morrisey, ',
             'R. v. Morrisey'),
            ('; Alpha v. Beta, [2000] 1 S.C.R. 1, Dickson C.J. for the majority, and Vézina v. The Queen, ',
             'Vézina v. The Queen'),
            ('; Alpha v. Beta, [2000] 1 S.C.R. 1, Bauman J. in Chang [Chang v. Feng, ', 'Chang v. Feng'),
            ('; Alpha v. Beta, [2000] 1 S.C.R. 1, Tysoe J.A. in Romanchych [Romanchych v. Vallianatos, ',
             'Romanchych v. Vallianatos'),
            ('; Alpha v. Beta, [2000] 1 S.C.R. 1, Similarly, in Mahe v. Alberta, ', 'Mahe v. Alberta'),
            ('; Alpha v. Beta, [2000] 1 S.C.R. 1, Additionally, I note that R. v. Zamiara, ', 'R. v. Zamiara'),
            ('; Alpha v. Beta, [2000] 1 S.C.R. 1, As the Supreme Court notes in Penner v. Niagara (Regional Police Services Board), ',
             'Penner v. Niagara (Regional Police Services Board)'),
            ('ty) v. The Rascal Trucking Ltd., [2000] 1 S.C.R. 342 at p. 358 (Quoting with approval Shell Canada v. Vancouver (City), ',
             'Shell Canada v. Vancouver (City)'),
            ('mmeubles Port Louis Ltée v. Lafontaine (Village), [1991] 1 S.C.R. 326, at p. 364. As Harelkin [v. University of Regina, ',
             'Harelkin [v. University of Regina'),
            ('p. 30. 8 See for example, Rose v. The Queen (1987), 3 M.V.R. (2d) 1 (Ont. Distr. Ct.) 9 At p. 282. 10 e.g. R. v. Penno, ',
             'R. v. Penno'),
        ):
            with self.subTest(pre=pre):
                self.assertEqual(split(pre)['candidate_case_name'], expected)

    def test_nine_court_lead_in_signals_are_not_part_of_the_name(self):
        # PROBLEMS #179: closed citation signals that the nine-court run exported
        # as the first words of a group name.
        for pre, expected in (
            ('; cf. Dalglish v. Jarvie, ', 'Dalglish v. Jarvie'),
            ('; Relying on R. v. Sheppard, ', 'R. v. Sheppard'),
            ('; the case of Goldsoll v. Goldman, ', 'Goldsoll v. Goldman'),
            ('; The decision in Child & Gower Piano Company Ltd. v. Gambrel, ',
             'Child & Gower Piano Company Ltd. v. Gambrel'),
            ('; see, Diligenti v. McAlpine, ', 'Diligenti v. McAlpine'),
            ('; Next, relying on Toronto (City) v. Ontario (Attorney General), ',
             'Toronto (City) v. Ontario (Attorney General)'),
            ('; As in the case of Rogers v. Rogers, ', 'Rogers v. Rogers'),
            ('; quoting from Revenue & Customs v. Cozens, ', 'Revenue & Customs v. Cozens'),
            ('; Applying R. v. Crevier, ', 'R. v. Crevier'),
        ):
            with self.subTest(pre=pre):
                self.assertEqual(split(pre)['candidate_case_name'], expected)
        # A bare Next can open a company name; only `Next,` is a signal.
        self.assertEqual(split('; Next Generation Inc. v. Smith, ')['candidate_case_name'],
                         'Next Generation Inc. v. Smith')

    def test_new_french_crown_route_excludes_explicit_citation_prose(self):
        # ONCA_2020onca106, ONCA_2023onca706, BCCA_2025bcca430.
        for pre, expected in (
            ('; A.G., at para. 52, citing R. c. Lessard, ', 'R. c. Lessard'),
            ('; Gill, the Quebec Court of Appeal held in R. c. Demers-Thibeault, ', 'R. c. Demers-Thibeault'),
            ('; at para. 4. Additional judgments have since touched on the domestic effect of UNDRIP, including R. c. Montour, ',
             'R. c. Montour'),
        ):
            with self.subTest(pre=pre):
                self.assertEqual(split(pre)['candidate_case_name'], expected)

    def test_closed_prefix_rules_preserve_real_names_and_numbered_parties(self):
        for name in (
            'Said v. Butt', 'Held v. Sechelt (District)',
            'Seneca College of Applied Arts & Technology v. Bhaduria',
            'Gomba Holding (UK) Ltd. v. Minories Finance',
            'D. Bacon Holding Ltd v. Naramata Vines Inc',
            '306793 Ontario Ltd. in Trust v. Rimes',
            '1991 Holdings Inc. v. Canada',
            'Union des employés de commerce, local 503 v. Roy',
            'Smith [Litigation Guardian] v. Canada',
        ):
            with self.subTest(name=name):
                self.assertEqual(split('; Alpha v. Beta, [2000] 1 S.C.R. 1, and ' + name + ', ')
                                 ['candidate_case_name'], name.rstrip('.'))


class CourtDesignationAmbiguityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clf = classifier()

    def test_native_ryan_pc_does_not_become_privy_council(self):
        # ONCA_2021onca256, corpus row 22947, Ryan's Provincial Court report.
        for designation in ("PC", "P C"):
            row = report("N.B.R.", vol="211", page="1", pre="; R. v. Ryan, (1999), ")
            row["court_designation_raw"] = designation
            row = self.clf.run_row(row)
            self.assertEqual(row["court_designation_status"], "ambiguous_designation")
            self.assertEqual(row["observed_deciding_court"], "")

    def test_explicit_registered_privy_council_forms_are_preserved(self):
        for designation in ("P.C.", "J.C.P.C."):
            row = report("A.C.", vol="1", page="100")
            row["court_designation_raw"] = designation
            row = self.clf.run_row(row)
            self.assertEqual(row["court_designation_status"], "recognized")
            self.assertEqual(row["observed_deciding_court"], "Judicial Committee of the Privy Council")
        status, court, _ = classify.classify_court_designation("R.C.S.", classify.load_court_designations())
        self.assertEqual((status, court), ("unrecognized", ""))


class NonCaseSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clf = classifier()

    def test_verified_non_case_sources_are_rejected_but_rows_preserved(self):
        for abbr, material in (("Can. Bar Rev.", "periodical"),
                               ("Can. Crim. L.R.", "periodical"),
                               ("J. Soc. Welfare & Fam. L.", "periodical"),
                               ("U.N.T.S.", "treaty_series"), ("L.N.T.S.", "treaty_series"),
                               ("Stat.", "statute"), ("Geo.", "statute")):
            with self.subTest(abbr=abbr):
                row = self.clf.run_row(report(abbr))
                self.assertIn("non_case_" + material, row["rejected_reason"])
                self.assertEqual(row["raw_string"], f"42 {abbr} 80")
                self.assertEqual(row["page"], "80")

    def test_generic_suffixes_share_exact_rows_case_tolerance(self):
        for abbr in ("Nev. L. Rev.", "NEV. L. REV.", "Nev. l. rev.", "Nev.L.Rev.",
                     "Nev. Law Review", "NEV. LAW REVIEW", "Example Bar. Rev."):
            with self.subTest(abbr=abbr):
                self.assertIn("non_case_periodical", self.clf.run_row(report(abbr))["rejected_reason"])

    def test_similar_suffix_is_not_sufficient_evidence(self):
        for abbr in ("NevXL.Rev.", "Nev. L. Rev. Reports", "Nev. L. Review", "L. Rev.",
                     "Nev. Rev. L.", "Example Law Reviewer"):
            with self.subTest(abbr=abbr):
                self.assertNotIn("non_case_", self.clf.run_row(report(abbr))["rejected_reason"])

    def test_registered_reports_and_article_context_remain_cases(self):
        for abbr in ("S.C.R.", "O.R.", "L.J.K.B.", "C.C.C.", "The Reports", "The Times L.R."):
            with self.subTest(abbr=abbr):
                row = self.clf.run_row(report(abbr, pre='Article "Law Review" discusses R. v. Smith; '))
                self.assertNotIn("non_case_", row["rejected_reason"])
        # A quoted title by itself cannot label an unregistered report periodical.
        row = self.clf.run_row(report("Example Rep.", pre='Author, "Article title" (2020), '))
        self.assertNotIn("non_case_", row["rejected_reason"])

    def test_report_registration_wins_over_suffix_rule(self):
        reporter = {"abbreviation": "Example L. Rev.", "normalized_key": "examplelrev",
                    "jurisdiction": "CA", "confidence": "verified", "year_range_start": "",
                    "year_range_end": "", "vol_range_start": "", "vol_range_end": ""}
        clf = classifier([reporter])
        for abbr in ("Example L. Rev.", "EXAMPLE L. REV."):
            self.assertNotIn("non_case_", clf.run_row(report(abbr))["rejected_reason"])

    def test_native_sheehy_article_is_a_periodical_independent_of_quote_context(self):
        # SCC_2026scc16, article quote spans 70022..70061 and 295870..295909.
        pre = ('E. Sheehy and S. B. Boyd, “Penalizing women’s fear: intimate partner violence '
               'and parental alienation in Canadian child custody cases” (2020), ')
        row = self.clf.run_row(report("J. Soc. Welfare & Fam. L.", pre=pre))
        self.assertIn("non_case_periodical", row["rejected_reason"])
        self.assertIn("non_case_periodical", self.clf.run_row(report("J. Soc. Welfare & Fam. L."))["rejected_reason"])

    def test_real_table_has_sources_and_no_registered_exact_collision(self):
        path = PIPE.parent / "decisions/non_case_sources.csv"
        with path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        registered = {classify.nk(r["abbreviation"])
                      for r in classify.load_table("reporter_jurisdiction.csv")}
        self.assertGreater(len(rows), 200)
        for row in rows:
            with self.subTest(form=row["printed_form"]):
                self.assertTrue(row["source"].strip() and row["source_locator"].strip())
                self.assertEqual(row["normalized_key"], classify.nk(row["printed_form"]))
                if row["match_type"] == "exact":
                    self.assertNotIn(row["normalized_key"], registered)


if __name__ == "__main__":
    unittest.main()
