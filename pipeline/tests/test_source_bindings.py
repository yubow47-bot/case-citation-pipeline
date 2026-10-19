"""S2: every source is checked; equal texts do not merge independent metadata IDs."""
import datetime as dt
import gzip
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from source_integrity import inspect_source, annotate_duplicate_texts, load_source_records


def source(metadata, native, row=0):
    text = ('Decision Content\nDate: 20200101\nDocket: A-1\nCitation:\n'
            'Example v. Example,\n' + native + '\nBefore: Justice Example\n'
            '[1] The appeal is dismissed. 2002 SCC 15 is cited.')
    return inspect_source({'citation': metadata, 'date': dt.datetime(2020, 1, 1),
                           'text': text, 'text_field': 'unofficial_text_en'},
                          metadata.split()[1], row)


class SourceBindingTests(unittest.TestCase):
    def test_reviewed_wrong_bindings_and_their_correct_controls(self):
        for metadata, own in [('2004 BCCA 21', '2004 BCCA 210'),
                              ('2003 BCCA 354', '2003 BCCA 333'),
                              ('2024 FC 89', '2025 FC 89'),
                              ('2004 BCSC 10', '2004 BCSC 102'),
                              ('2007 BCSC 161', '2007 BCSC 1610')]:
            with self.subTest(metadata=metadata):
                wrong, correct = source(metadata, own), source(own, own, 1)
                self.assertFalse(wrong['source_measurable'])
                self.assertEqual(wrong['quarantine_reason'], 'SOURCE_CITATION_MISMATCH')
                self.assertTrue(correct['source_measurable'])
                self.assertNotEqual(wrong['source_id'], correct['source_id'])
                self.assertEqual(len(annotate_duplicate_texts([wrong, correct])), 1)
                self.assertEqual(wrong['duplicate_text_source_count'], 2)

    def test_nonidentical_wrong_text_is_still_checked(self):
        wrong = source('2004 BCCA 21', '2004 BCCA 210')
        self.assertFalse(wrong['source_measurable'])
        self.assertTrue(wrong['own_citation_checked'])
        self.assertFalse(annotate_duplicate_texts([wrong]))

    def test_bilingual_equivalence_and_zero_padded_numbers(self):
        for metadata, own in [('2020 SCC 1', '2020 CSC 001'),
                              ('2020 FC 1', '2020 CF 1'),
                              ('2020 FCA 1', '2020 CAF 1')]:
            self.assertEqual(source(metadata, own)['own_citation_status'], 'MATCH')

    def test_body_citations_and_unqualified_labels_cannot_quarantine(self):
        for text in ['[1] The following judgment was quoted:\nCitation: 2002 SCC 15\nDate: 20020101',
                     'Citation: 2002 SCC 15.', 'Neutral citation\n2002 SCC 15\nDecision Content\nOrder dismissed.']:
            row = inspect_source({'citation': '2020 SCC 1', 'text': text}, 'SCC', 0)
            self.assertTrue(row['source_measurable'])
            self.assertEqual(row['own_citation_status'], 'NO_VERIFIED_NATIVE_CITATION')

    def test_multiple_different_own_citations_require_review(self):
        row = source('2020 FC 1', '2020 FC 1\n2020 FC 2')
        self.assertEqual(row['own_citation_status'], 'AMBIGUOUS_NATIVE_CITATION')
        self.assertTrue(row['source_measurable'])

    def test_missing_text_is_retained_as_nonmeasurable(self):
        row = inspect_source({'citation': '2020 SCC 1', 'text': ''}, 'SCC', 7)
        self.assertEqual(row['corpus_row_index'], 7)
        self.assertFalse(row['source_measurable'])
        self.assertTrue(row['own_citation_checked'])

    def test_malformed_native_code_is_not_truncated_to_a_false_identity(self):
        row = source('2002 BCCA 402', '2002 BCCA0 402')
        self.assertEqual(row['own_citation_status'], 'MALFORMED_NATIVE_CITATION')
        self.assertTrue(row['source_measurable'])
        self.assertEqual(source('2002 BCCA 402', '2002 BCCA 0402')['own_citation_status'], 'MATCH')

    def test_compressed_finalized_source_contract_loads_by_logical_path(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / 'implementation') as temp:
            root = Path(temp)
            with gzip.open(root / 'source_records.csv.gz', 'wt', encoding='utf-8', newline='') as stream:
                stream.write('source_id,source_measurable,source_decision_year,quarantine_reason\n'
                             'SCC_2020scc1,True,2020,\nSCC_2020scc2,False,2020,SOURCE_CITATION_MISMATCH\n')
            result = load_source_records(root)
            self.assertTrue(result['SCC_2020scc1']['source_measurable'])
            self.assertFalse(result['SCC_2020scc2']['source_measurable'])


if __name__ == '__main__':
    unittest.main()
