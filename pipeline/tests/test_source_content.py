"""S3: recognize incomplete title/signature remnants without removing oral orders."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from source_integrity import inspect_source


class SourceContentTests(unittest.TestCase):
    def inspect(self, text):
        return inspect_source({'citation': '2004 BCSC 937', 'name': 'Example v. Example',
                               'text': text}, 'BCSC', 46634)

    def test_reviewed_remnant_structure_is_not_a_zero_citation_observation(self):
        # Synthetic names reproduce the exact title / signature structure of
        # BCSC row 46634; the private replay also tests the full original text.
        row = self.inspect('2004 BCSC 937 Example v. Example\n"M. Example, J."\n'
                           'The Honourable Madam Justice M. Example\n')
        self.assertFalse(row['source_measurable'])
        self.assertEqual(row['text_integrity_status'], 'INCOMPLETE_HEADER_SIGNATURE')
        self.assertEqual(row['quarantine_reason'], 'INCOMPLETE_TEXT')
        self.assertEqual(row['corpus_row_index'], 46634)

    def test_short_oral_order_with_disposition_remains_measurable(self):
        for text in ['The appeal is dismissed.',
                     'Oral Reasons for Judgment\n[1] THE COURT: Appeal dismissed.',
                     '2004 BCSC 937 Example v. Example\nThe appeal is dismissed.\n"M. Example, J."']:
            row = self.inspect(text)
            self.assertTrue(row['source_measurable'])
            self.assertEqual(row['text_integrity_status'], 'PRESENT_UNVERIFIED')

    def test_title_line_containing_an_operative_sentence_is_not_removed(self):
        row = self.inspect('2004 BCSC 937 Example v. Example. Appeal dismissed.\n"M. Example, J."')
        self.assertTrue(row['source_measurable'])

    def test_unknown_short_text_does_not_become_incomplete_just_from_size(self):
        self.assertTrue(self.inspect('Order granted.')['source_measurable'])
        self.assertTrue(self.inspect('"M. Example, J."')['source_measurable'])


if __name__ == '__main__':
    unittest.main()
