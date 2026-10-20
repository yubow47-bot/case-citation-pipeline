"""Explicit format guards for docket headings and front-matter year citations."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from document_zones import load_markers,locate,position_zone,history_assessment

class ResidualDocumentZoneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.markers,_=load_markers()

    def test_docket_prefixed_appeal_is_formal_history(self):
        text='[33114] APPEAL from an order, 2009 QCCA 235.\nThe judgment of the Court was delivered by\n[1] Reasons.'
        b=locate(text,self.markers['SCC']);p=text.index('2009 QCCA')
        self.assertEqual(position_zone(b,p,p+13),'appeal_block')

    def test_frontmatter_year_does_not_override_explicit_reasons_heading(self):
        text=('On appeal from: Arbitration Board,\n[2011] B.C.C.A.A.A. No. 54.\nCounsel for the Appellants:\nA. Person\n'
              'Reasons for Judgment of the Honourable Judge:\nI. INTRODUCTION\n[1] Reasons.')
        b=locate(text,self.markers['BCCA']);p=text.index('[2011]')
        self.assertEqual(position_zone(b,p,p+26),'appeal_block')
        self.assertEqual(b['reasons_start'],text.index('Reasons for Judgment'))

    def test_later_first_paragraph_still_abstains(self):
        for prefix in ['', 'Reasons for Judgment of the Honourable Judge:\n']:
            b=locate(prefix+'[2] Existing body.\n[1] A footnote.',self.markers['BCCA'])
            self.assertEqual(b['status'],'ambiguous_paragraph_order')

    def test_ordinary_boundary_and_body_precedent_are_preserved(self):
        text='APPEAL from an order, 2009 QCCA 235.\nThe judgment of the Court was delivered by\n[1] Applying 2000 SCC 1.'
        b=locate(text,self.markers['SCC']);p=text.index('2000 SCC')
        self.assertEqual(b['reasons_start'],text.index('The judgment'))
        self.assertEqual(position_zone(b,p,p+10),'reasons')

    def test_unmarked_history_is_unassessed_not_confirmed_absent(self):
        self.assertEqual(history_assessment(['appeal_block']*2), 'confirmed_formal_history')
        for zones in (['reasons'], ['headnote'], ['appeal_block', 'reasons']):
            self.assertEqual(history_assessment(zones), 'unassessed_outside_formal_span')
        for zones in ([], ['unknown'], ['appeal_block', 'unknown']):
            self.assertEqual(history_assessment(zones), 'unassessed_missing_zone_evidence')

if __name__=='__main__':unittest.main()
