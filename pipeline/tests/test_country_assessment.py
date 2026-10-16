"""Country assessment must not require a proved same-judgment identity link."""
from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decide
from edges import origin_for_edge


def observation(country="CA", identity="cocitation", basis="classification_jurisdiction"):
    return dict(member_origin_country=country, member_origin_status="DETERMINED",
                member_origin_basis=basis, member_origin_evidence_ids="classification:fixture:" + country,
                identity_basis=identity)


class CountryAssessmentTests(unittest.TestCase):
    def classify(self, jurisdiction, kind="reporter", **extra):
        row = dict(merge_key="2000|10|fixture||20", jurisdiction=jurisdiction,
                   citation_kind=kind, **extra)
        decide.decide_case_origin(row, [], {}, Counter())
        return row

    def test_country_and_province_classifications_are_usable(self):
        for jurisdiction, country in (("CA", "CA"), ("BC", "CA"), ("ON", "CA"),
                                      ("QC", "CA"), ("GB", "GB"), ("US", "US"),
                                      ("AU", "AU"), ("NZ", "NZ")):
            with self.subTest(jurisdiction=jurisdiction):
                row = self.classify(jurisdiction)
                self.assertEqual(row["member_origin_country"], country)
                self.assertEqual(row["member_origin_basis"], "classification_jurisdiction")
                self.assertTrue(row["member_origin_evidence_ids"].startswith("classification:"))

    def test_neutral_and_identifier_need_no_separate_exclusive_rule(self):
        for kind in ("neutral", "identifier"):
            self.assertEqual(self.classify("BC", kind)["member_origin_country"], "CA")

    def test_unknown_ambiguous_noncase_and_rejected_rows_are_not_guessed(self):
        for jurisdiction, kind, extra in (("UNSUPPORTED", "reporter", {}),
                ("XX", "reporter", {}), ("", "neutral", {}),
                ("CA", "ambiguous", {}), ("CA", "statute", {}),
                ("CA", "reporter", {"rejected_reason": "not_a_decision"})):
            self.assertEqual(self.classify(jurisdiction, kind, **extra)["member_origin_status"],
                             "UNDETERMINED")

    def test_case_observation_overrides_reporter_classification(self):
        row = dict(merge_key="1900|1|ac||20", jurisdiction="GB", citation_kind="reporter")
        decide.decide_case_origin(row, ["fixture"], {"fixture": [
            dict(case_origin="CA", normalized_key="fixture")]}, Counter())
        self.assertEqual((row["member_origin_country"], row["member_origin_basis"]),
                         ("CA", "case_record"))

    def test_transnational_court_is_not_a_country_of_origin_rule(self):
        row = dict(merge_key="1900||ukpc||20", jurisdiction="GB", citation_kind="neutral")
        decide.decide_case_origin(row, [], {}, Counter())
        self.assertEqual(row["member_origin_status"], "UNDETERMINED")

    def test_reporter_with_two_canadian_provinces_still_identifies_country(self):
        row = dict(merge_key="1973|3|nfldpeir||418", jurisdiction="UNSUPPORTED",
                   citation_kind="reporter")
        decide.decide_case_origin(row, [], {}, Counter())
        self.assertEqual(row["member_origin_country"], "CA")
        self.assertEqual(row["member_origin_subdivision"], "")
        self.assertEqual(row["member_origin_basis"], "classification_reporter_consensus")

    def test_reporter_with_candidates_in_different_countries_stays_unresolved(self):
        row = dict(merge_key="1818|12|qb||310", jurisdiction="UNSUPPORTED", citation_kind="reporter")
        decide.decide_case_origin(row, [], {}, Counter())
        self.assertEqual(row["member_origin_status"], "UNDETERMINED")

    def test_conflicting_scope_is_not_hidden_by_classification(self):
        row = dict(merge_key="1900|1|qb||20", jurisdiction="GB", citation_kind="reporter")
        rules = [dict(printed_abbreviation="Q.B.", origin_country=c,
                      verification_status="verified_exclusive_publisher") for c in ("GB", "CA")]
        decide.decide_case_origin(row, [], {}, Counter(), reporter_idx={"qb": rules})
        self.assertEqual(row["member_origin_status"], "UNDETERMINED")

    def test_country_survives_each_identity_basis(self):
        for identity in ("anchor", "name_year", "cocitation", "unanchored", "anchor_variant_typo"):
            rows = [observation(identity=identity)]
            decide.aggregate_group_origin(rows, Counter())
            self.assertEqual(rows[0]["group_origin_country"], "CA")
            self.assertEqual(rows[0]["identity_basis"], identity)

    def test_group_conflict_preserves_member_countries(self):
        rows = [observation("CA"), observation("GB")]
        decide.aggregate_group_origin(rows, Counter())
        self.assertEqual(rows[0]["group_origin_status"], "CONFLICT")
        self.assertEqual([r["member_origin_country"] for r in rows], ["CA", "GB"])

    def test_edge_country_is_independent_of_identity_and_group_conflict(self):
        group = dict(group_foreign_status="CONFLICT", group_origin_country="",
                     group_origin_basis="", group_origin_evidence_ids="")
        status, country, basis, ids = origin_for_edge(group, [observation("GB")], False)
        self.assertEqual((status, country), ("FOREIGN", "GB"))
        self.assertTrue(basis.startswith("member:"))
        self.assertTrue(ids)

    def test_group_only_country_requires_identity_link(self):
        group = dict(group_foreign_status="DOMESTIC_CA", group_origin_country="CA",
                     group_origin_basis="court_scope_rule", group_origin_evidence_ids="scope:SCC")
        self.assertEqual(origin_for_edge(group, [], False)[0], "UNDETERMINED")
        self.assertEqual(origin_for_edge(group, [], True)[:2], ("DOMESTIC_CA", "CA"))

    def test_edge_conflict_is_not_resolved_by_voting(self):
        result = origin_for_edge({}, [observation("GB"), observation("CA"), observation("CA")], False)
        self.assertEqual(result[:2], ("CONFLICT", ""))


if __name__ == "__main__":
    unittest.main()
