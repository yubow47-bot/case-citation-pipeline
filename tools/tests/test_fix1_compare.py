"""Small local fixtures for Fix1 comparison contracts (no corpus/full run)."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('fix1_compare',ROOT/'tools/fix1_compare.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
ANALYSIS=Path(os.environ.get('FIX1_ANALYSIS_ROOT',r'G:\加拿大法庭数据论文\analysis'))


@unittest.skipUnless((ANALYSIS/'scripts/citation_years.py').is_file(),'Existing paper-analysis pure functions not available')
class Fix1CompareTests(unittest.TestCase):
    def build(self, root, rename=False):
        run=root/'run';run.mkdir(parents=True)
        g1,g2=('XC-G900','XC-G800') if rename else ('XC-G001','XC-G002')
        neutral='2010||scc||1';reporter='2015|2|fixture||3';passenger='2015|5|passenger||6'
        members=[dict(court='SCC',merge_key=neutral,merged_group_id=g1,case_name_modal='One',year_printed='2010',identity_basis='same_citation',identity_court_evidence='court:scc=neutral_code:SCC'),
                 dict(court='SCC',merge_key=reporter,merged_group_id=g2,case_name_modal='Two',year_printed='2015',identity_basis='same_citation',identity_court_evidence=''),
                 dict(court='SCC',merge_key=passenger,merged_group_id=g2,case_name_modal='Passenger',year_printed='2015',identity_basis='name_year',identity_court_evidence='court:onca=printed_court:ONCA')]
        module.write_rows(run/'decide_out/cross_court/decided.csv',members,list(members[0]))
        effective=[dict(source_decision=sid,merged_group_id=gid,status='counted',via_member_row_keys='SCC|'+key) for sid,gid,key in [('SCC_one',g1,neutral),('SCC_two',g2,reporter),('SCC_bad',g1,neutral)]]
        module.write_rows(run/'decide_out/cross_court/effective_sources.csv',effective,list(effective[0]))
        edges=[dict(source_decision=e['source_decision'],resolved_cited_case=e['merged_group_id'],edge_support='supported',foreign_status='DOMESTIC_CA',mention_count=1,own_case_history=e['source_decision']=='SCC_one') for e in effective]
        module.write_rows(run/'edges/citation_edges.csv',edges,list(edges[0]))
        mentions=[];classified=[]
        for i,e in enumerate(effective):
            key=e['via_member_row_keys'][4:]
            mentions.append(dict(candidate_id='c'+str(i),corpus_row_index=i,source_decision_citation=e['source_decision'],merge_key=key,match_start_offset=10,match_end_offset=25,arbitration_status='counted'))
            neutral_kind=key==neutral
            classified.append(dict(candidate_id='c'+str(i),corpus_row_index=i,source_decision_citation=e['source_decision'],match_start_offset=10,match_end_offset=25,citation_kind='neutral' if neutral_kind else 'reporter',raw_string='2010 SCC 1' if neutral_kind else '(2015) 2 Fixture 3',abbreviation='SCC' if neutral_kind else 'Fixture',serial_marker='',year_start='2010' if neutral_kind else '2015',year_raw='2010' if neutral_kind else '2015',shape_name='shape_neutral_bare' if neutral_kind else 'shape_year_vol_page'))
        module.write_rows(run/'merge_out/SCC/mentions_candidates.csv',mentions,list(mentions[0]))
        module.write_rows(run/'classify_out/SCC/classified.csv',classified,list(classified[0]))
        docs=[dict(source_id=sid,court='SCC',source_year=2026 if sid=='SCC_one' else 2020,eligible=sid!='SCC_one',edge_assessable=True,source_policy_excluded=False) for sid in ['SCC_one','SCC_two','SCC_bad','SCC_zero']]
        module.write_rows(root/'documents.csv',docs,list(docs[0]))
        sources=[dict(source_id=d['source_id'],court='SCC',source_decision_year=2020,source_measurable=d['source_id']!='SCC_bad',quarantine_reason='wrong_binding' if d['source_id']=='SCC_bad' else '') for d in docs]
        module.write_rows(root/'source_records.csv',sources,list(sources[0]))
        return argparse.Namespace(run_dir=str(run),documents=str(root/'documents.csv'),source_records=str(root/'source_records.csv'),out=str(root/'out'),analysis_root=str(ANALYSIS),format_rules=str(ANALYSIS/'q7_format_overlay.json'),courts='SCC',allow_fixture_output=True)

    def test_resolved_dates_measurability_zero_sources_and_history_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=self.build(Path(tmp));module.prepare(a)
            data=json.loads((Path(a.out)/'metrics.json').read_text())
            all_=data['views']['all_links']['by_court']['ALL']
            filtered=data['views']['without_own_case_history']['by_court']['ALL']
            self.assertEqual((all_['N'],all_['E'],all_['K'],all_['O']),(3,2,2,2))
            self.assertEqual((filtered['N'],filtered['E'],filtered['O']),(3,1,1))
            self.assertEqual(all_['Q7_neutral_occurrence_share'],0.5)
            self.assertEqual(all_['Q5_known_nonnegative_age_median'],7.5)
            self.assertEqual(all_['Q6_destination_counts']['CANADIAN_ORIGIN_COURT_UNKNOWN'],1)

    def test_missing_baseline_history_is_unavailable_not_an_identical_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=self.build(Path(tmp));a.source_records=None
            path=Path(a.run_dir)/'edges/citation_edges.csv'
            edges=list(module.rows(path))
            for edge in edges:edge.pop('own_case_history')
            module.write_rows(path,edges,list(edges[0]))
            module.prepare(a)
            data=json.loads((Path(a.out)/'metrics.json').read_text())
            self.assertEqual(data['history_view_status'],'UNAVAILABLE_IN_FROZEN_EDGE_SCHEMA')
            self.assertNotIn('without_own_case_history',data['views'])

    def test_ordinal_group_renumbering_does_not_change_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=self.build(root/'a');b=self.build(root/'b',True)
            module.prepare(a);module.prepare(b)
            aa=json.loads((Path(a.out)/'metrics.json').read_text());bb=json.loads((Path(b.out)/'metrics.json').read_text())
            self.assertEqual(aa,bb)
            self.assertTrue(all(r['change']==0 for r in module.compare(Path(a.out)/'metrics.json',Path(b.out)/'metrics.json') if r['change'] is not None))


if __name__=='__main__':unittest.main()
