"""Real citation typography with fixed citation spans and table-owned meaning."""
from collections import Counter
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from extract import extract_candidates
from classify import Classifier, load_runtime_tables, classify_court_designation
from suffix_annotations import capture_suffix, parallel_gap
from decide import add_court_designation_columns


class SuffixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = load_runtime_tables()

    def classify(self, text, raw):
        rows, _ = extract_candidates(text, 'SCC_fixture', '2020', 0, 'SCC')
        target = next(r for r in rows if r['raw_string'] == raw and r['shape_name'] == 'shape_vol_abbr_page')
        original = (target['match_start_offset'], target['match_end_offset'], target['raw_string'])
        row = Classifier(self.tables, Counter()).run_row(target)
        self.assertEqual(original, (row['match_start_offset'], row['match_end_offset'], row['raw_string']))
        return row

    def test_pinpoint_followed_by_court(self):
        r = self.classify('42 C.C.C. (3d) 1 at 110 (Ont. C.A.)', '42 C.C.C. (3d) 1')
        self.assertEqual(r['observed_deciding_court'], 'Ontario Court of Appeal')

    def test_ordinal_series_is_not_a_suffix_label(self):
        r = self.classify('42 C.C.C. (3d) 1 (4th)', '42 C.C.C. (3d) 1')
        self.assertEqual(r['court_designation_raw'], '')
        self.assertEqual(json.loads(r['suffix_annotations_json']), [])

    def test_newline_and_missing_terminal_period(self):
        r = self.classify('42 C.C.C. (3d) 1 (Ont.\nC.A)', '42 C.C.C. (3d) 1')
        self.assertEqual(r['observed_deciding_court'], 'Ontario Court of Appeal')

    def test_service_label_before_court(self):
        r = self.classify('42 C.C.C. (3d) 1 (QL) (Ont. C.A.)', '42 C.C.C. (3d) 1')
        self.assertEqual(r['observed_deciding_court'], 'Ontario Court of Appeal')
        self.assertEqual([a['kind'] for a in json.loads(r['parallel_suffix_annotations_json'])], ['service', 'court'])

    def test_conflicting_suffixes_do_not_vote(self):
        r = self.classify('42 C.C.C. (3d) 1 (Ont. C.A.) (B.C.C.A.)', '42 C.C.C. (3d) 1')
        self.assertEqual((r['court_designation_status'], r['observed_deciding_court']), ('conflict', ''))

    def test_nested_designation_and_unknown_prose(self):
        r = self.classify('42 C.C.C. (3d) 1 (Ont. Ct. J. (Gen. Div.))', '42 C.C.C. (3d) 1')
        self.assertEqual(r['observed_deciding_court'], 'Ontario Court (General Division)')
        r = self.classify('42 C.C.C. (3d) 1 (a different judgment)', '42 C.C.C. (3d) 1')
        self.assertEqual(r['court_designation_status'], 'unrecognized')
        self.assertFalse(parallel_gap(' (a different judgment), ', r))

    def test_qualified_annotations_only_connect_separator(self):
        r = self.classify('42 C.C.C. (3d) 1 (QL) (Ont. C.A.), 2013 ONCA 661', '42 C.C.C. (3d) 1')
        self.assertTrue(parallel_gap(' (QL) (Ont. C.A.), ', r))
        self.assertFalse(parallel_gap(' (QL) (Ont. C.A.); ', r))
        self.assertFalse(parallel_gap(' (QL) (Ont. C.A.), aff\'d ', r))
        self.assertFalse(parallel_gap(' (QL) (Ont. C.A.), Another v. Case, ', r))
        self.assertFalse(parallel_gap(' (QL) (Ont. C.A.), ', {**r, 'parallel_suffix_annotations_json': '[]'}))

    def test_ambiguous_national_designation_stays_unknown(self):
        table, scope = self.tables['court_designations'], self.tables['court_designation_reporter_scope']
        self.assertEqual(classify_court_designation('C.A.', table, scope, 'C.C.C.')[0], 'ambiguous_designation')
        self.assertEqual(classify_court_designation('C.A.', table, scope, 'B.C.J.')[0], 'ambiguous_designation')
        self.assertEqual(classify_court_designation('F.C.A.', table, scope, 'A.L.R.')[0], 'ambiguous_designation')
        self.assertEqual(classify_court_designation('F.C.A.', table, scope, 'F.C.')[1], 'Federal Court of Appeal')

    def test_group_court_uses_qualified_positive_evidence_and_no_vote(self):
        def row(key, basis, evidence):
            return {'court': 'SCC', 'merge_key': key, 'identity_basis': basis,
                    'identity_court_evidence': evidence}
        rows = [row('a', 'anchor', 'court:onca=neutral_code:onca'),
                row('b', 'co_printed_run', ''), row('c', 'name_year', 'court:bcsc=neutral_code:bcsc')]
        add_court_designation_columns(rows, Counter())
        self.assertEqual({r['group_deciding_court'] for r in rows}, {'court:onca'})
        rows[2]['identity_basis'] = 'co_printed_run'
        add_court_designation_columns(rows, Counter())
        self.assertEqual({r['group_deciding_court_status'] for r in rows}, {'CONFLICT'})
        self.assertTrue(all(not r['group_deciding_court'] for r in rows))


if __name__ == '__main__':
    unittest.main()
