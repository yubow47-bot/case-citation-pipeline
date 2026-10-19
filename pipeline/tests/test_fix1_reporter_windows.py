"""Fix1 F2: reporter rules obey their documented chronology."""
from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import classify
import decide
import extract
import merge


class ReporterWindowTests(unittest.TestCase):
    def setUp(self):
        self.tables = classify.load_runtime_tables()

    def classified(self, text):
        candidates, _ = extract.extract_candidates(text, 'SCC_fixture', '2020', 0, 'SCC')
        clf = classify.Classifier(self.tables, Counter())
        return [clf.run_row(dict(row)) for row in candidates]

    def test_eight_attached_start_dates_reject_before_and_accept_after(self):
        starts = {'ccc': 1898, 'wwr': 1911, 'ar': 1976, 'altalr': 1908,
                  'manr': 1979, 'saskr': 1979, 'nbr': 1969, 'nr': 1974}
        rules = decide.load_reporter_origin()
        for key, start in starts.items():
            with self.subTest(reporter=key):
                rule = rules[key][0]
                self.assertEqual(rule['year_range_start'], str(start))
                self.assertEqual(rule['year_range_end'], '')
                self.assertFalse(decide._reporter_window_ok('10', str(start - 10), rule))
                self.assertTrue(decide._reporter_window_ok('10', str(start + 10), rule))

    def test_native_historical_ar_keeps_year_and_not_alberta(self):
        rows = self.classified('(1885) 11 A.R. 178')
        row = next(r for r in rows if r['shape_name'] == 'shape_year_vol_page')
        self.assertEqual(row['citation_kind'], 'reporter')
        self.assertEqual(row['rejected_reason'], '')
        self.assertEqual(row['jurisdiction'], 'UNSUPPORTED')
        self.assertEqual(row['volume_system'], '')
        merge.apply_reporter_identity_fixes({('SCC_fixture', 0): [row]}, Counter())
        self.assertTrue(merge.build_merge_key_v2(row).startswith('1885|11|ar|'))
        row['merge_key'] = merge.build_merge_key_v2(row)
        decide.decide_case_origin(row, ['(1885) 11 A.R. 178'], {}, Counter(),
                                  reporter_idx=decide.load_reporter_origin())
        self.assertEqual(row['member_origin_subdivision'], '')

    def test_modern_alberta_report_retains_jurisdiction_and_continuous_key(self):
        rows = self.classified('(1994) 157 A.R. 241')
        row = next(r for r in rows if r['shape_name'] == 'shape_year_vol_page')
        self.assertEqual(row['jurisdiction'], 'AB')
        self.assertEqual(row['volume_system'], 'continuous')
        merge.apply_reporter_identity_fixes({('SCC_fixture', 0): [row]}, Counter())
        self.assertTrue(merge.build_merge_key_v2(row).startswith('|157|ar|'))
        self.assertEqual(row['year_printed'], '1994')


if __name__ == '__main__':
    unittest.main()
