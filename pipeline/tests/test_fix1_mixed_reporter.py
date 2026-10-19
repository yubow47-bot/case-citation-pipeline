"""Fix1 A1: mixed publications do not establish the appeal's country."""
from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decide


class MixedReporterOriginTests(unittest.TestCase):
    def assess(self, citation, key, year='', jurisdiction='GB'):
        row = dict(merge_key=key, canonical_string=citation,
                   citation_kind='reporter', jurisdiction=jurisdiction,
                   year_printed=year)
        decide.decide_case_origin(row, [citation], decide.load_case_origin(), Counter(),
                                  scope_idx=decide.load_scope(),
                                  reporter_idx=decide.load_reporter_origin())
        return row

    def test_radio_reference_does_not_get_british_origin_from_ac(self):
        row = self.assess('[1932] A.C. 304', '1932||ac||304', '1932')
        self.assertEqual(row['member_origin_status'], 'UNDETERMINED')
        self.assertEqual(row['member_origin_country'], '')
        self.assertEqual(row['member_origin_ambiguous_basis'], 'mixed_reporter_scope')
        self.assertTrue(row['member_origin_evidence_ids'])

    def test_edwards_exact_case_record_remains_canadian(self):
        row = self.assess('[1930] A.C. 124', '1930||ac||124', '1930')
        self.assertEqual((row['member_origin_country'], row['member_origin_basis']),
                         ('CA', 'case_record'))

    def test_absent_year_does_not_remove_mixed_constraint(self):
        row = self.assess('A.C. 304', '||ac||304')
        self.assertEqual(row['member_origin_status'], 'UNDETERMINED')
        self.assertEqual(row['member_origin_ambiguous_basis'], 'mixed_reporter_scope')

    def test_exclusive_reporter_retains_verified_origin(self):
        row = self.assess('[1995] 2 S.C.R. 3', '1995|2|scr||3', '1995', 'CA')
        self.assertEqual((row['member_origin_country'], row['member_origin_basis']),
                         ('CA', 'exclusive_reporter_scope'))

    def test_default_origin_api_also_retains_mixed_constraint(self):
        row = dict(merge_key='1932||ac||304', citation_kind='reporter', jurisdiction='GB')
        decide.decide_case_origin(row, [], {}, Counter())
        self.assertEqual(row['member_origin_status'], 'UNDETERMINED')


if __name__ == '__main__':
    unittest.main()
