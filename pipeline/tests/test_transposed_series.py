"""Waldick's native 70 O.R. 2(d) 717 must keep its page and series.

The extra shapes preserve all pre-existing candidates. Arbitration must prefer
the complete supported reporter reading without promoting unknown prose tokens.
"""
from collections import Counter
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'pipeline'))
sys.path.insert(0, str(ROOT/'pipeline/tests'))
import classify
import extract
import merge
import shapes
from fixtures import FIXTURES

NEW_SHAPES = {'shape_year_vol_page_transposed_series', 'shape_vol_abbr_page_transposed_series'}
# Verbatim native wording: ONCA_2026onca371, corpus row16983, para29.
WALDICK = ('This court considered that provision in Waldick v. Malcolm (1990), '
           '70 O.R. 2(d) 717 (C.A.) (“Waldick (ONCA)”), at p. 723, aff’d [1991] 2 S.C.R. 456:')


def candidates(text):
    return extract.extract_candidates(text, 'ONCA_fixture', '2026', 0, 'ONCA')[0]


def arbitrate(text):
    classifier = classify.Classifier(classify.load_runtime_tables(), Counter())
    rows = [classifier.run_row(dict(row)) for row in candidates(text)]
    return rows, merge.arbitrate_document(rows, Counter())


class TransposedSeriesTests(unittest.TestCase):
    def test_native_waldick_capture_keeps_full_page_series_raw_and_offsets(self):
        rows = candidates(WALDICK)
        full = next(r for r in rows if r['shape_name'] == 'shape_year_vol_page_transposed_series')
        self.assertEqual((full['year_start'], full['vol'], full['abbr'], full['series'], full['page']),
                         ('1990', '70', 'O.R.', '2d', '717'))
        self.assertEqual(full['raw_string'], '(1990), 70 O.R. 2(d) 717')
        self.assertEqual(WALDICK[full['match_start_offset']:full['match_end_offset']], full['raw_string'])
        start, end = map(int, full['page_span'].split(':'))
        self.assertEqual(WALDICK[start:end], '717')

    def test_complete_supported_reading_counted_and_old_page_two_retained(self):
        rows, verdicts = arbitrate(WALDICK)
        full = [r for r in rows if r['shape_name'] == 'shape_year_vol_page_transposed_series']
        self.assertEqual(len(full), 1)
        self.assertEqual(verdicts[full[0]['candidate_id']][0], 'counted')
        self.assertEqual(merge.build_merge_key_v2(full[0]), '1990|70|or|2d|717')
        old = [r for r in rows if r['page'] == '2' and r['abbr'] == 'O.R.']
        self.assertEqual(len(old), 2)
        self.assertTrue(all(verdicts[r['candidate_id']][0] != 'counted' for r in old))
        counted = [r for r in rows if verdicts[r['candidate_id']][0] == 'counted' and r['abbr'] == 'O.R.']
        self.assertEqual(len(counted), 1)

    def test_yearless_transposed_second_and_third_series_stay_distinct(self):
        keys = []
        for ordinal in ('2', '3'):
            rows, verdicts = arbitrate('Smith v. Jones, 70 O.R. '+ordinal+'(d) 717 (C.A.).')
            counted = [r for r in rows if verdicts[r['candidate_id']][0] == 'counted']
            self.assertEqual(len(counted), 1)
            self.assertEqual(counted[0]['page'], '717')
            keys.append(merge.build_merge_key_v2(counted[0]))
        self.assertEqual(keys, ['|70|or|2d|717', '|70|or|3d|717'])

    def test_page_reinterpretation_requires_exact_source_span_and_suffix(self):
        rows, _ = arbitrate(WALDICK)
        long = next(r for r in rows if r['shape_name'] == 'shape_year_vol_page_transposed_series')
        short = next(r for r in rows if r['shape_name'] == 'shape_vol_abbr_page' and r['page'] == '2')
        self.assertTrue(merge._fields_compatible(short, long))
        altered = copy.deepcopy(long)
        altered['vol_span'] = '0:1'
        self.assertFalse(merge._fields_compatible(short, altered))
        altered = copy.deepcopy(short)
        altered['match_start_offset'] += 1
        self.assertFalse(merge._fields_compatible(altered, long))
        altered = copy.deepcopy(short)
        altered['match_end_offset'] += 1
        self.assertFalse(merge._fields_compatible(altered, long))
        altered = copy.deepcopy(long)
        altered['raw_string'] = altered['raw_string'].replace('(d) 717', '(x) 717')
        self.assertFalse(merge._fields_compatible(short, altered))

    def test_ordinary_parenthesized_series_keeps_its_existing_shape(self):
        text = 'Waldick v. Malcolm (1990), 70 O.R. (2d) 717 (C.A.).'
        rows, verdicts = arbitrate(text)
        self.assertFalse(any(r['shape_name'] in NEW_SHAPES for r in rows))
        full = next(r for r in rows if verdicts[r['candidate_id']][0] == 'counted')
        self.assertEqual(full['shape_name'], 'shape_year_vol_page')
        self.assertEqual(merge.build_merge_key_v2(full), '1990|70|or|2d|717')

    def test_unknown_company_token_does_not_gain_counted_transposed_reading(self):
        rows, verdicts = arbitrate('There were 70 Companies 2(d) 717 units.')
        new = [r for r in rows if r['shape_name'] in NEW_SHAPES]
        self.assertTrue(new)
        self.assertTrue(all(merge.support_grade(r) == 0 for r in new))
        self.assertTrue(all(verdicts[r['candidate_id']][0] != 'counted' for r in new))
        self.assertFalse(any(r['shape_name'] in NEW_SHAPES
                             for r in candidates('The company recorded 70 entries under section 2(d), totaling 717.')))

    def test_only_exact_two_or_three_suffix_parenthesis_form_is_added(self):
        for series in ('(2d)', '2 (d)', '22(d)', '2(D)', '4(d)', '2(d)(C.A.)'):
            with self.subTest(series=series):
                self.assertFalse(any(r['shape_name'] in NEW_SHAPES
                                     for r in candidates('70 O.R. '+series+' 717')))

    def test_old_candidate_records_are_preserved_in_every_fixture(self):
        old_shapes = [(name, rx) for name, rx in extract.SHAPES if name not in NEW_SHAPES]
        for text in [WALDICK, *[fixture['text'] for fixture in FIXTURES]]:
            with patch.object(extract, 'SHAPES', old_shapes):
                before = {row['candidate_id']: row for row in candidates(text)}
            after = {row['candidate_id']: row for row in candidates(text)}
            self.assertTrue(before.keys() <= after.keys())
            self.assertEqual(before, {cid: after[cid] for cid in before})

    def test_capture_normalization_does_not_mutate_input_or_ordinary_series(self):
        original = {'series_transposed': '3(d)', 'series': None, 'page': '717'}
        resolved = shapes.resolve_registered_id(original)
        self.assertIsNone(original['series'])
        self.assertEqual(resolved['series'], '3d')
        self.assertEqual(shapes.resolve_registered_id({'series_paren': '2d'}), {'series_paren': '2d'})


if __name__ == '__main__':
    unittest.main()
