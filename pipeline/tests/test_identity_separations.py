"""Exact, evidence-bound non-identity facts preserve citations and source sets."""
from collections import Counter
import copy
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'pipeline'))
import decide
import registry

KEY='|65|nsr|2d|54'
DOC='SCC_19852scr486'
CHARTRAND='SCC_19942scr864'
SCR='1985|2|scr||486'
RCS='1985|2|rcs||486'


class IdentitySeparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads((Path(__file__).parent/'fixtures/motorvehicle_identity_20261015.json').read_text(encoding='utf-8'))

    def setUp(self):
        scratch=ROOT/'implementation/round3_tmp'
        scratch.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)
        own_path=self.path/'own.csv'
        with own_path.open('w',encoding='utf-8',newline='') as out:
            writer=csv.DictWriter(out,fieldnames=registry.OWN_FIELDS,extrasaction='ignore')
            writer.writeheader();writer.writerows(self.fixture['own'])
        self.own=decide.load_own_citations(str(own_path))
        self.ids={key:set(values) for key,values in self.fixture['source_ids'].items()}

    def facts(self,rows=None,rebind=False):
        rows=copy.deepcopy([self.fixture['fact']] if rows is None else rows)
        if rebind:
            for row in rows:
                row['evidence_id']='sep:'+hashlib.sha256(json.dumps({k:v for k,v in row.items() if k!='evidence_id'},
                    ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        path=self.path/'facts.csv'
        with path.open('w',encoding='utf-8',newline='') as out:
            writer=csv.DictWriter(out,fieldnames=decide.SEPARATION_FIELDS)
            writer.writeheader();writer.writerows(rows)
        return decide.load_identity_separations(str(path))

    def run_rows(self,rows=None,own=None,facts=None,ids=None):
        stats=Counter()
        output,_,effective=decide.adjudicate(copy.deepcopy(self.fixture['members'] if rows is None else rows),
            self.ids if ids is None else ids,{},{},'FIXTURE',stats,False,
            own_cites=self.own if own is None else own,gate='registered',
            identity_separations=self.facts() if facts is None else facts)
        return output,effective,stats

    @staticmethod
    def group(rows,key):
        return next(r['merged_group_id'] for r in rows if r['merge_key']==key)

    @staticmethod
    def sources(effective,gid):
        return {r['source_decision'] for r in effective if r['merged_group_id']==gid and r['status']=='counted'}

    def copy_own(self):
        result=decide.OwnCitations()
        result.update({key:set(values) for key,values in self.own.items()})
        result.aliases=dict(self.own.aliases)
        result.evidence=copy.deepcopy(self.own.evidence)
        result.diagnostics=copy.deepcopy(self.own.diagnostics)
        return result

    def test_real_old_dd214_new213_removes_only_false_motorvehicle_source(self):
        old,old_eff,_=self.run_rows(facts=[])
        fixed,effective,stats=self.run_rows()
        old_group=self.group(old,SCR)
        group=self.group(fixed,SCR)
        self.assertEqual(self.group(old,KEY),old_group)
        self.assertNotEqual(self.group(fixed,KEY),group)
        self.assertEqual(self.group(fixed,RCS),group)
        self.assertEqual(len(self.sources(old_eff,old_group)),214)
        self.assertEqual(len(self.sources(effective,group)),213)
        self.assertEqual(self.sources(old_eff,old_group)-self.sources(effective,group),{CHARTRAND})
        self.assertFalse(self.sources(effective,group)-self.sources(old_eff,old_group))
        self.assertEqual(self.sources(effective,self.group(fixed,KEY)),{CHARTRAND})
        self.assertEqual(len(fixed),len(old))
        self.assertNotIn(DOC,self.sources(effective,group))
        self.assertEqual(stats['identity_separation_facts_applied'],1)
        held=next(r for r in fixed if r['merge_key']==KEY)
        self.assertEqual(held['identity_separation_evidence_ids'],self.fixture['fact']['evidence_id'])
        self.assertEqual(held['document_alias_holdout_doc_ids'],DOC)
        self.assertEqual(held['document_alias_holdout_evidence_ids'],self.fixture['fact']['target_qualified_evidence_ids'])

    def test_court_to_cross_court_lifecycle_keeps_complete_native_proofs(self):
        court_rows=[]
        for court in ('SCC','ONCA','BCCA'):
            rows=[r for r in self.fixture['members'] if r['court']==court]
            output,_,_=self.run_rows(rows=rows)
            court_rows.extend(output)
        extra=copy.deepcopy(next(r for r in self.fixture['members'] if r['merge_key']==KEY))
        extra['court']='ONCA'
        court_rows.append(extra)
        ids=copy.deepcopy(self.ids)
        ids[decide.row_key(extra)]={'ONCA_NEW_SUPPORT'}
        output,effective,_=self.run_rows(rows=court_rows,ids=ids)
        held=[r for r in output if r['merge_key']==KEY]
        self.assertEqual(len({r['merged_group_id'] for r in held}),1)
        self.assertNotEqual(held[0]['merged_group_id'],self.group(output,SCR))
        self.assertEqual(self.sources(effective,held[0]['merged_group_id']),{CHARTRAND,'ONCA_NEW_SUPPORT'})
        self.assertTrue(all(r['identity_separation_evidence_ids']==self.fixture['fact']['evidence_id'] for r in held))
        self.assertTrue(all(r['document_alias_holdout_evidence_ids']==self.fixture['fact']['target_qualified_evidence_ids'] for r in held))

    def test_negative_claim_allows_alias_to_another_proven_document(self):
        own=self.copy_own()
        other='BCCA_1984bcca100'
        other_key='1984||bcca||100'
        for key in (KEY,other_key):
            proof=copy.deepcopy(self.own.evidence[SCR][0])
            proof.update(merge_key=key,decision_id=other,source_court='BCCA',corpus_row='42',
                         corpus_sha256='a'*64,field='citation_en' if key==other_key else 'citation2_en')
            proof['evidence_id']='own:'+hashlib.sha256(json.dumps({k:str(v) for k,v in proof.items() if k!='evidence_id'},
                ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            own[key]={other};own.aliases[key]=other;own.evidence[key]=[proof]
        new=copy.deepcopy(next(r for r in self.fixture['members'] if r['merge_key']==KEY))
        new.update(merge_key=other_key,court='BCCA',citation_kind='neutral',case_name_modal='Verified other judgment',
                   self_citation_of=other,year_printed='1984')
        rows=self.fixture['members']+[new]
        ids=copy.deepcopy(self.ids);ids[decide.row_key(new)]={'OTHER_SUPPORT'}
        out,effective,_=self.run_rows(rows=rows,own=own,ids=ids)
        self.assertEqual(self.group(out,KEY),self.group(out,other_key))
        self.assertNotEqual(self.group(out,KEY),self.group(out,SCR))
        self.assertEqual(self.sources(effective,self.group(out,KEY)),{CHARTRAND,'OTHER_SUPPORT'})

    def test_native_quote_hash_and_retired_production_fact(self):
        fact=self.facts()[0]
        self.assertEqual(decide.load_identity_separations(),[])
        quote=self.fixture['native_distinct_judgment']['text']
        self.assertEqual(hashlib.sha256(quote.encode()).hexdigest(),fact['span_sha256'])
        self.assertIn('R. v. Johnson (1984)',quote)
        self.assertIn('65 N.S.R. (2d) 54 (C.A.)',quote)
        self.assertEqual(int(fact['span_end'])-int(fact['span_start']),len(quote))
        # The record expresses no unsupported canonical court assertion.
        self.assertNotIn('canonical_court',fact)

    def test_corrupt_or_incomplete_provenance_is_rejected(self):
        bad_values={'corpus_sha256':'bad','span_start':'x','span_end':'0',
                    'source_decision':'ONCA_wrong','text_field':'unknown',
                    'verification_status':'guessed','source_locator':'../outside.json',
                    'target_qualified_evidence_ids':'own:'+'a'*64}
        for field,value in bad_values.items():
            with self.subTest(field=field):
                fact=copy.deepcopy(self.fixture['fact']);fact[field]=value
                with self.assertRaisesRegex(ValueError,'Identity separation'):
                    self.facts([fact],rebind=True)
        fact=copy.deepcopy(self.fixture['fact']);fact['span_sha256']='a'*64
        with self.assertRaisesRegex(ValueError,'corrupt provenance'):
            self.facts([fact])
        with self.assertRaisesRegex(ValueError,'duplicate'):
            self.facts([self.fixture['fact'],self.fixture['fact']])

    def test_stale_missing_or_ambiguous_target_proofs_fail_closed(self):
        for field,value in [('target_qualified_evidence_ids','|'.join(self.fixture['fact']['target_qualified_evidence_ids'].split('|')[:-1])),
                            ('target_decision_id','SCC_UNKNOWN'),('corpus_sha256','a'*64)]:
            with self.subTest(field=field):
                fact=copy.deepcopy(self.fixture['fact']);fact[field]=value
                with self.assertRaisesRegex(ValueError,'current qualified proofs'):
                    self.run_rows(facts=self.facts([fact],rebind=True))
        with self.assertRaisesRegex(ValueError,'current qualified proofs'):
            self.run_rows(own=decide.OwnCitations())
        ambiguous=self.copy_own()
        ambiguous.evidence[SCR][0]['corpus_row']='999'
        with self.assertRaisesRegex(ValueError,'ambiguous current qualified proofs'):
            self.run_rows(own=ambiguous)

    def test_stale_misbound_or_incomplete_inherited_flags_cannot_reactivate(self):
        first,_,_=self.run_rows()
        for change in ('unknown_fact','wrong_key','missing_target_proofs'):
            with self.subTest(change=change):
                rows=copy.deepcopy(first)
                held=next(r for r in rows if r['merge_key']==KEY)
                if change=='unknown_fact':held['identity_separation_evidence_ids']='sep:'+'0'*64
                elif change=='wrong_key':held['merge_key']='|65|nsr|2d|55'
                else:held['document_alias_holdout_evidence_ids']=''
                with self.assertRaisesRegex(ValueError,'(Identity separation|holdout)'):
                    self.run_rows(rows=rows)

    def test_conflicting_positive_alias_or_mixed_source_snapshots_fail_closed(self):
        own=self.copy_own()
        own.aliases[KEY]=DOC
        with self.assertRaisesRegex(ValueError,'conflicts with a current positive document alias'):
            self.run_rows(own=own)
        mixed=self.copy_own()
        stale=copy.deepcopy(self.own.evidence[SCR][0])
        stale.update(corpus_sha256='0'*64,identity_qualified='false')
        mixed.evidence['unrelated_old_source']=[stale]
        with self.assertRaisesRegex(ValueError,'ambiguous current qualified proofs'):
            self.run_rows(own=mixed)


if __name__=='__main__':
    unittest.main()
