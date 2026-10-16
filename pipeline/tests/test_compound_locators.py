"""Source-backed compound ILR paragraph locators; ordinary ranges stay literal."""
from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import classify
import extract
import merge
import shapes

SHAPE = 'shape_bracket_compound_locator'


def extracted(text):
    return extract.extract_candidates(text, 'ONCA_fixture', 2000, 0, 'ONCA')[0]


class CompoundLocatorTests(unittest.TestCase):
    def setUp(self):
        self.classifier = classify.Classifier(classify.load_runtime_tables(), Counter())

    def test_native_peet_and_gulf_keep_the_entire_printed_locator(self):
        # Native sources: ONCA_2012onca338 row18460 and ONCA_c34246... row12963.
        for text, page, name, year in (
            ('; Peet v. Ethier, [1988] I.L.R. 1-2261 (Sask. Q.B.), aff’d [1988] I.L.R. 8865 (Sask. C.A.).',
             '1-2261', 'Peet v. Ethier', '1988'),
            ('; Gulf Plastics Ltd. v. Cornhill Insurance Co. Ltd., [1990] I.L.R. 1-2644 (B.C.S.C.) aff’d (1991), 3 C.C.L.I. (2d) 203 (B.C.C.A.).',
             '1-2644', 'Gulf Plastics Ltd. v. Cornhill Insurance Co. Ltd', '1990'),
        ):
            with self.subTest(page=page):
                candidates = extracted(text)
                full = next(row for row in candidates if row['shape_name'] == SHAPE)
                old = next(row for row in candidates if row['shape_name'] == 'shape_bracket' and row['page'] == '1')
                self.assertEqual(full['page'], page)
                self.assertEqual(text[slice(*map(int, full['page_span'].split(':')))], page)
                self.assertTrue(full['raw_string'].startswith(old['raw_string']))
                row = self.classifier.run_row(full)
                self.assertEqual(row['compound_locator_rule_id'], 'ILR_NUMERIC_PARAGRAPH')
                self.assertEqual(row['candidate_case_name'], name)
                self.assertEqual(row['citation_kind'], 'reporter')
                self.assertEqual(row['jurisdiction'], 'UNSUPPORTED')
                self.assertEqual(merge.build_merge_key_v2(row), year + '||ilr||' + page)

    def test_same_year_different_compound_ids_do_not_collapse(self):
        keys = set()
        for page in ('1-2261', '1-2644'):
            row = next(row for row in extracted('; Alpha v. Beta, [1988] I.L.R. ' + page) if row['shape_name'] == SHAPE)
            keys.add(merge.build_merge_key_v2(self.classifier.run_row(row)))
        self.assertEqual(keys, {'1988||ilr||1-2261', '1988||ilr||1-2644'})

    def test_official_printed_paragraph_markers(self):
        for marker in ('', '¶ ', 'para. ', 'Paragraph '):
            with self.subTest(marker=marker):
                rows = [row for row in extracted('; Alpha v. Beta, [1991] I.L.R. ' + marker + '1-2764 at 1517') if row['shape_name'] == SHAPE]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['page'], '1-2764')
                self.assertNotIn('1517', rows[0]['raw_string'])

    def test_unregistered_reporter_ranges_and_ordinary_ilr_ranges_are_unchanged(self):
        for citation in ('[1988] Example Rep. 33-34', '[1988] Example Rep. 1-2261',
                         '[1988] I.L.R. 33-34', '27 I.L.R. 33-34', '[1988] 2 I.L.R. 1-2261'):
            with self.subTest(citation=citation):
                self.assertFalse(any(row['shape_name'] == SHAPE for row in extracted('; Alpha v. Beta, ' + citation)))

    def test_no_letter_i_equivalence_or_partial_compound_extension(self):
        keys = set()
        for locator in ('1-2261', 'I-2261'):
            row = next(row for row in extracted('; Alpha v. Beta, [1988] I.L.R. ' + locator) if row['shape_name'] == SHAPE)
            keys.add(merge.build_merge_key_v2(self.classifier.run_row(row)))
        self.assertEqual(keys, {'1988||ilr||1-2261', '1988||ilr||I-2261'})
        for locator in ('i-2261', 'M-2261', '1-22', '1-226123', '1-2261n', '1-2261-2', '1-2261–2', '1–2261'):
            with self.subTest(locator=locator):
                self.assertFalse(any(row['shape_name'] == SHAPE for row in extracted('; Alpha v. Beta, [1988] I.L.R. ' + locator)))

    def test_previous_candidates_are_preserved(self):
        text = '; Peet v. Ethier, [1988] I.L.R. 1-2261; Gulf Plastics v. Cornhill, [1990] I.L.R. 1-2644.'
        after = {row['candidate_id']: row for row in extracted(text)}
        saved = extract.SHAPES
        try:
            extract.SHAPES = [(name, rx) for name, rx in saved if name != SHAPE]
            before = extracted(text)
        finally:
            extract.SHAPES = saved
        for row in before:
            self.assertEqual(after[row['candidate_id']], row)

    def test_absent_or_mismatched_policy_abstains(self):
        row = next(row for row in extracted('; Alpha v. Beta, [1988] I.L.R. 1-2261') if row['shape_name'] == SHAPE)
        tables = classify.load_runtime_tables()
        tables['reporter_compound_locators'] = []
        result = classify.Classifier(tables, Counter()).run_row(dict(row))
        self.assertEqual(result['compound_locator_rule_id'], '')
        self.assertIn('unverified_compound_locator', result['rejected_reason'])
        row['abbr'] = 'Example Rep.'
        result = self.classifier.run_row(row)
        self.assertEqual(result['compound_locator_rule_id'], '')
        self.assertIn('unverified_compound_locator', result['rejected_reason'])

    def test_policies_are_source_backed_and_single_purpose(self):
        rows = shapes.load_compound_locator_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['locator_regex'], r'1-\d{3,5}')
        self.assertEqual(rows[1]['locator_regex'], r'I-\d{3,5}')
        self.assertTrue(rows[0]['source'].strip() and rows[0]['source_locator'].strip())
        self.assertEqual(rows[0]['verification_status'], 'verified_official_printed_format')
        self.assertNotIn('jurisdiction', rows[0])


if __name__ == '__main__':
    unittest.main()
