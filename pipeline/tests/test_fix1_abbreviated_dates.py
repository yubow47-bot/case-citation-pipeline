"""Fix1 F3: real date/amount structures do not become A.P.R. citations."""
from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import classify
import extract
import merge


class AbbreviatedDateTests(unittest.TestCase):
    def replay(self, text):
        rows, _ = extract.extract_candidates(text, 'SCC_fixture', '2020', 0, 'SCC')
        extract.annotate_cross_boundary(rows, text)
        clf = classify.Classifier(classify.load_runtime_tables(), Counter())
        rows = [clf.run_row(row) for row in rows]
        verdicts = merge.arbitrate_document(rows, Counter())
        return rows, [row for row in rows if verdicts[row['candidate_id']][0] == 'counted']

    def test_native_amount_and_april_dates_are_rejected(self):
        # Structures reproduced from SCC_1964scr667 and SCC_1934scr698;
        # source locations and complete originals remain in private audit evidence.
        for text in ('1,000.00\nApr.\n25/58', '905 25\nApr. 19, 1922'):
            with self.subTest(text=text):
                rows, counted = self.replay(text)
                april = [row for row in rows if row['abbreviation'] == 'Apr.']
                self.assertTrue(april)
                self.assertTrue(all('abbreviated_date_form' in row['rejected_reason'] for row in april))
                self.assertFalse([row for row in counted if classify.nk(row['abbreviation']) == 'apr'])

    def test_day_abbreviated_month_year_is_not_a_reporter(self):
        rows, counted = self.replay('The order was made on 28 Apr. 1995.')
        self.assertTrue(any('abbreviated_date_form' in row['rejected_reason'] for row in rows))
        self.assertEqual(counted, [])

    def test_real_reporter_spelling_survives_date_shaped_numbers(self):
        # Native positive: SCC [1992] 1 SCR 984, corpus row 61, offsets 910:924.
        for text in ('271 A.P.R. 339', '28 A.P.R. 1995', '25 APR 19'):
            with self.subTest(text=text):
                _, counted = self.replay(text)
                self.assertTrue([row for row in counted if classify.nk(row['abbreviation']) == 'apr'])

    def test_ambiguous_short_form_without_date_structure_is_not_rejected(self):
        rows, _ = self.replay('25 Apr. 19 is cited.')
        self.assertTrue(rows)
        self.assertFalse(any('abbreviated_date_form' in row['rejected_reason'] for row in rows))

    def test_right_context_is_raw_and_available_on_both_paths(self):
        text = '1,000.00\nApr.\n25/58'
        candidate = next(r for r in extract.extract_candidates(text, 'SCC_fixture', '', 0, 'SCC')[0]
                         if r.get('abbr') == 'Apr.')
        legacy = next(r for r in extract.extract_rows(text, 'SCC_fixture', '')
                      if r.get('abbr') == 'Apr.')
        self.assertEqual(candidate['following_text'], '/58')
        self.assertEqual(legacy['following_text'], '/58')
        self.assertIn('following_text', extract.CAND_SCHEMA)
        self.assertIn('following_text', extract.SCHEMA)


if __name__ == '__main__':
    unittest.main()
