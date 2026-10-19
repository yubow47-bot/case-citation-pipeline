"""Positive native structure, negative identity guards, and audit provenance."""
from collections import Counter
import copy
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'pipeline'))
from parallel_runs import FIELDS, extract_runs, load_parallel_runs, ParallelRuns
from merge import _gap_text
from identity_evidence import EvidenceSnapshot, row_key
from identity_constraints import ConstraintLedger
from identity_parallel import merge_parallel_clusters
from identity_solve import assign_identity_basis
from decide import load_history_instances


def member(key,kind='reporter',year='',name='',court='SCC'):
    return {'court':court,'merge_key':key,'citation_kind':kind,'year_printed':year,
            'case_name_modal':name,'canonical_string':key,'jurisdiction':'CA',
            'occurrence_count':'2','self_citation_of':'','self_case_name':'',
            'name_classes':'','co_printed_run_ids':''}

A='2013||onca||661'; B='|304|ccc|3d|133'; C='2013||onca||660'

class ParallelTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'implementation').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'implementation',prefix='parallel-test-')
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)

    def write(self,path,fields,rows):
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

    def fixture(self,keys=(A,B),gap=', ',source='SCC_fixture',directory='run',extra=False):
        rows=[];text=''
        for i,key in enumerate(keys):
            if i:text+=gap
            raw='2013 ONCA 661' if key==A else '304 C.C.C. (3d) 133' if key==B else key
            start=len(text)
            row={'source_decision_citation':source,'corpus_row_index':'0',
                 'candidate_id':source+':'+str(i),'merge_key':key,'raw_string':raw,
                 'match_start_offset':str(start),'match_end_offset':str(start+len(raw)),
                 'preceding_text':text,'arbitration_status':'counted'}
            text+=raw;rows.append(row)
        runs=extract_runs(rows,_gap_text,Counter())
        base=self.base/directory;path=base/'merge_out/SCC/parallel_runs.csv'
        self.write(path,FIELDS,runs)
        self.write(path.parent/'mentions_candidates.csv',rows[0].keys(),rows)
        self.write(base/'classify_out/SCC/classified.csv',rows[0].keys(),rows)
        return path,rows,runs

    def solve(self,rows,parallels,history=None,clusters=None,min_sources=1,inject_pair=False):
        sources={row_key(m):{'SCC_fixture'} for m in rows}
        snap=EvidenceSnapshot(rows,sources,'TEST',history=history,parallels=parallels)
        if inject_pair:
            eid=snap.add('','','','test_negative_fact',{'keys':[A,B]},{'fixture':'test'})
            snap.pair_cannot_links.append({'left_merge_key':A,'right_merge_key':B,
                'relation_type':'different_judgments','evidence_id':eid})
        trace=ConstraintLedger(snap);stats=Counter()
        clusters=clusters or [([m],'','') for m in rows]
        out=merge_parallel_clusters(clusters,parallels,sources,{},None,None,history,
                                    stats,trace,min_sources)
        facts={r['evidence_id'] for r in trace.records['evidence']}
        for r in trace.records['constraints']:
            self.assertTrue(set(json.loads(r['evidence_ids_json'])) <= facts)
        self.assertEqual(sorted(map(row_key,rows)),sorted(row_key(m) for c in out for m in c[0]))
        return out,stats,trace

    def test_structural_positive_and_boundaries(self):
        for gap,expected in [(', ',2),(',\n',2),('; ',0),(', aff\'d ',0),
                             (', R. v. X, ',0),(' (QL), ',0),('',0)]:
            with self.subTest(gap=gap):
                p,rs,out=self.fixture(gap=gap,directory='shape'+str(len(gap))+str(expected))
                self.assertEqual(len(out),expected)

    def test_native_gap_tampering_fails_closed(self):
        p,rows,runs=self.fixture()
        rows[1]['preceding_text']=rows[1]['preceding_text'][:-2]+'; '
        self.write(p.parents[2]/'classify_out/SCC/classified.csv',rows[0].keys(),rows)
        with self.assertRaisesRegex(ValueError,'native adjacent'):load_parallel_runs([p])

    def test_noncounted_member_fails_closed(self):
        p,rows,_=self.fixture();rows[1]['arbitration_status']='rejected_row'
        self.write(p.parent/'mentions_candidates.csv',rows[0].keys(),rows)
        with self.assertRaisesRegex(ValueError,'not a counted'):load_parallel_runs([p])

    def test_loaded_evidence_mutation_rejected(self):
        p,_,_=self.fixture();par=load_parallel_runs([p])
        par[next(iter(par))]['source']='fake'
        with self.assertRaisesRegex(ValueError,'changed after validation'):
            EvidenceSnapshot([member(A,'neutral','2013'),member(B)],{},'TEST',parallels=par)

    def test_missing_year_name_joins_with_audit_basis(self):
        p,_,_=self.fixture();par=load_parallel_runs([p])
        rows=[member(A,'neutral','2013','R. v. Saliba'),member(B)]
        out,stats,trace=self.solve(rows,par)
        self.assertEqual(len(out),1);self.assertEqual(stats['parallel_cluster_unions'],1)
        basis=assign_identity_basis(out[0][0],{row_key(m):{'SCC_fixture'} for m in rows},{},'')
        self.assertEqual(basis[row_key(rows[1])],'co_printed_run')
        self.assertEqual(stats['parallel_single_source_cluster_unions'],1)
        self.assertTrue(any(r['fact_kind']=='co_printed_run' for r in trace.records['evidence']))

    def test_conflicted_run_has_no_partial_union(self):
        p,_,_=self.fixture((A,B,C));par=load_parallel_runs([p])
        out,stats,_=self.solve([member(A,'neutral','2013'),member(B),member(C,'neutral','2013')],par)
        self.assertEqual(len(out),3)
        self.assertEqual(stats['parallel_blocked_different_neutral_numbers'],1)

    def test_transitive_reporter_bridge_cannot_join_real_neutrals(self):
        p,_,_=self.fixture((A,B),directory='first')
        q,_,_=self.fixture((B,C),directory='second',source='SCC_other')
        out,stats,_=self.solve([member(A,'neutral','2013'),member(B),member(C,'neutral','2013')],load_parallel_runs([p,q]))
        self.assertEqual(len(out),2)
        self.assertFalse(any({A,C}<={r['merge_key'] for r in c[0]} for c in out))

    def test_unnamed_year_conflict_blocks(self):
        p,_,_=self.fixture();out,stats,_=self.solve([member(A,'neutral','2013'),member(B,year='2017')],load_parallel_runs([p]))
        self.assertEqual(len(out),2);self.assertEqual(stats['parallel_blocked_printed_year_span'],1)

    def test_positive_court_conflict_blocks(self):
        p,_,_=self.fixture((A,'2013||bcsc||40'))
        out,stats,_=self.solve([member(A,'neutral','2013'),member('2013||bcsc||40','neutral','2013')],load_parallel_runs([p]))
        self.assertEqual(len(out),2);self.assertEqual(stats['parallel_blocked_positive_court_conflict'],1)

    def test_curated_negative_fact_blocks(self):
        p,_,_=self.fixture();out,stats,_=self.solve([member(A,'neutral','2013'),member(B)],load_parallel_runs([p]),inject_pair=True)
        self.assertEqual(len(out),2);self.assertEqual(stats['parallel_blocked_verified_pair_separation'],1)

    def test_history_negative_fact_blocks(self):
        p,_,_=self.fixture();h=p.parent/'history_pairs.csv'
        rows=[{'source_decision_citation':'SCC_history','corpus_row_index':'0','instance':'h',
               'side':side,'merge_key':key,'candidate_id':str(i),'connector':"aff'd"}
              for i,(side,key) in enumerate([('before',A),('after',B)])]
        self.write(h,rows[0].keys(),rows)
        out,stats,_=self.solve([member(A,'neutral','2013'),member(B)],load_parallel_runs([p]),load_history_instances([h]))
        self.assertEqual(len(out),2);self.assertEqual(stats['parallel_blocked_appeal_history_connector'],1)

    def test_support_is_distinct_documents(self):
        p,_,_=self.fixture();out,stats,_=self.solve([member(A,'neutral','2013'),member(B)],load_parallel_runs([p]),min_sources=2)
        self.assertEqual(len(out),2);self.assertEqual(stats['parallel_below_support_threshold'],1)
        q,_,_=self.fixture(directory='second',source='SCC_other')
        out,stats,_=self.solve([member(A,'neutral','2013'),member(B)],load_parallel_runs([p,q]),min_sources=2)
        self.assertEqual(len(out),1);self.assertEqual(stats['parallel_single_source_cluster_unions'],0)

    def test_heuristic_passenger_does_not_gain_positive_basis(self):
        p,_,_=self.fixture();rows=[member(A,'neutral','2013'),member(B),member('|99|ccc|3d|80')]
        out,_,_=self.solve(rows,load_parallel_runs([p]),clusters=[([rows[0],rows[2]],'decision;unanchored',''),([rows[1]],'','')])
        self.assertEqual(len(out),1);self.assertEqual(rows[2]['co_printed_run_ids'],'')
        basis=assign_identity_basis(out[0][0],{row_key(m):{'SCC_fixture'} for m in rows},{},'decision;unanchored')
        self.assertEqual(basis[row_key(rows[2])],'unanchored')

    def test_missing_artifact_is_not_silently_legacy(self):
        with self.assertRaises(FileNotFoundError):load_parallel_runs([self.base/'absent.csv'])
        self.assertEqual(load_parallel_runs(None),{})

if __name__=='__main__':unittest.main()
