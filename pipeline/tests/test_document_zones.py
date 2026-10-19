"""Printed boundaries, unknowns and all-occurrence history semantics."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from document_zones import load_markers, locate, position_zone, edge_zones


class ZoneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markers, _ = load_markers()

    def test_scc_contents_title_is_not_body(self):
        text = ('Reasons for Judgment: (paras. 1 to 7)\nCases Cited\n2001 SCC 1\n'
                'APPEAL from a judgment: 2000 ONCA 2.\n'
                'The judgment of the Court was delivered by\n[1] The Court — Reasons.\n')
        b = locate(text, self.markers['SCC'])
        self.assertEqual(b['reasons_start'], text.index('The judgment'))
        self.assertEqual(position_zone(b, text.index('2001 SCC'), text.index('2001 SCC')+10), 'headnote')
        self.assertEqual(position_zone(b, text.index('2000 ONCA'), text.index('2000 ONCA')+11), 'appeal_block')
        self.assertEqual(position_zone(b, text.index('[1]'), len(text)), 'reasons')

    def test_multiline_delivery_precedes_later_opinion(self):
        text = ('APPEAL from a judgment.\nThe judgment of A and B JJ.\nwas delivered by\n'
                '[1] Majority reasons.\nThe reasons of C J. were delivered by\n[83] Separate opinion.')
        self.assertEqual(locate(text, self.markers['SCC'])['reasons_start'], text.index('The judgment'))

    def test_formal_order_and_opinion(self):
        for header in ['English version of the order delivered by',
                       'The following is the opinion of', 'ORDER']:
            text = 'Metadata\n' + header + '\n[1] Reasons.'
            self.assertEqual(locate(text, self.markers['SCC'])['reasons_start'], 9)

    def test_no_markers_or_late_footnote_abstains(self):
        self.assertEqual(locate('Unstructured native text', [])['reasons_start'], -1)
        text = '[2] Existing body.\n[3] More body.\n[1] A footnote.'
        self.assertEqual(locate(text, self.markers['ONCA'])['status'], 'ambiguous_paragraph_order')

    def test_inline_first_paragraph_after_heading(self):
        text = 'On appeal from a conviction.\nA. Overview [1] Reasons.\n[2] Next.'
        b = locate(text, self.markers['ONCA'])
        self.assertEqual(b['reasons_start'], text.index('A. Overview'))

    def test_bcca_summary_is_outside_appeal_field(self):
        text = ('On appeal from: Order in 2001 BCSC 2.\nCounsel for the Appellant:\nA. Name\n'
                'Summary:\n2000 SCC 1 discussed.\nReasons for Judgment of the Honourable Judge:\n[1] Reasons.')
        b = locate(text, self.markers['BCCA'])
        p = text.index('2000 SCC')
        self.assertEqual(position_zone(b, p, p+10), 'headnote')
        p = text.index('2001 BCSC')
        self.assertEqual(position_zone(b, p, p+11), 'appeal_block')

    def test_straddling_boundary_is_unknown(self):
        b = {'reasons_start': 10, 'appeal_spans': [[3, 8]]}
        for start, end in [(2, 5), (7, 9), (9, 11)]:
            self.assertEqual(position_zone(b, start, end), 'unknown')

    def test_history_requires_every_counted_occurrence(self):
        self.assertEqual(edge_zones(['appeal_block']*2), ('true', 'headnote_only'))
        self.assertEqual(edge_zones(['appeal_block', 'headnote']), ('false', 'headnote_only'))
        self.assertEqual(edge_zones(['appeal_block', 'reasons']), ('false', 'both'))
        self.assertEqual(edge_zones(['appeal_block', 'unknown']), ('false', 'unknown'))
        self.assertEqual(edge_zones([]), ('false', 'unknown'))
        self.assertEqual(edge_zones(['reasons']), ('false', 'reasons_only'))


if __name__ == '__main__':
    unittest.main()
