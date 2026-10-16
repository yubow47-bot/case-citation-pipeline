"""Native Lising/Pires appeal-history regression, captured from sealed inputs.

The court fact separates judgments. It does not turn a lower-court reporter
into a new alias for either of the two BCCA neutral citations.
"""
from collections import Counter
import copy
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'pipeline'))
import decide
import identity_courts
import registry

LOWER = '2004|193|bcac||42'
UPPER_NC = '2005||scc||66'
UPPER_SCR = '2005|3|scr||343'
LOWER_NC = '2004||bcca||33'
BAIL_NC = '2004||bcca||91'
UPPER_SELF = 'SCC_2005scc66'


class LisingIdentityReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((Path(__file__).parent/'fixtures/lising_identity_20261015.json').read_text(encoding='utf-8'))

    def setUp(self):
        scratch=ROOT/'implementation/round3_tmp'
        scratch.mkdir(parents=True,exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name)/'own.csv'
        with path.open('w',encoding='utf-8',newline='') as out:
            writer=csv.DictWriter(out,fieldnames=registry.OWN_FIELDS,extrasaction='ignore')
            writer.writeheader()
            writer.writerows(self.fixture['own'])
        self.own = decide.load_own_citations(str(path))
        self.ids = {key:set(values) for key,values in self.fixture['source_ids'].items()}

    def run_rows(self, *, legacy=False, all_controls=False, reverse=False):
        rows = copy.deepcopy(self.fixture['members'])
        if not all_controls:
            rows = [r for r in rows if r['merge_key'] not in (LOWER_NC,BAIL_NC)]
        if reverse:
            rows.reverse()
        original = identity_courts.CourtEvidence
        def without_new_fact():
            evidence = original()
            evidence.exact.pop(LOWER,None)
            return evidence
        stats = Counter()
        if legacy:
            with patch.object(identity_courts,'CourtEvidence',side_effect=without_new_fact):
                out,_,effective = decide.adjudicate(rows,self.ids,{},{},'FIXTURE',stats,False,
                                                   own_cites=self.own,gate='registered')
        else:
            out,_,effective = decide.adjudicate(rows,self.ids,{},{},'FIXTURE',stats,False,
                                               own_cites=self.own,gate='registered')
        return out,effective,stats

    @staticmethod
    def group(out,court,key):
        return next(row['merged_group_id'] for row in out if row['court']==court and row['merge_key']==key)

    @staticmethod
    def sources(effective,gid):
        return {r['source_decision'] for r in effective if r['merged_group_id']==gid and r['status']=='counted'}

    def test_real_subset_reproduces_old_false_merge_and_new_separation(self):
        old,old_effective,_ = self.run_rows(legacy=True)
        fixed,effective,stats = self.run_rows()
        old_upper=self.group(old,'SCC',UPPER_NC)
        self.assertEqual(self.group(old,'BCCA',LOWER),old_upper)
        upper=self.group(fixed,'SCC',UPPER_NC)
        self.assertNotEqual(self.group(fixed,'BCCA',LOWER),upper)
        self.assertNotEqual(self.group(fixed,'SCC',LOWER),upper)
        self.assertEqual(self.group(fixed,'BCCA',UPPER_SCR),upper)
        # The wrong member contributes an already present source. A DD-only
        # regression would therefore miss this identity error.
        self.assertEqual(self.sources(effective,upper),self.sources(old_effective,old_upper))
        self.assertEqual(len(self.sources(effective,upper)),85)
        self.assertNotIn(UPPER_SELF,self.sources(effective,upper))
        # PROBLEMS #135: the same printed report cited from two courts is one
        # component. The SCC appeal's reference to its lower judgment is a true
        # non-self citation and stays counted there, apart from the appeal.
        self.assertEqual(self.group(fixed,'BCCA',LOWER),self.group(fixed,'SCC',LOWER))
        self.assertEqual(self.sources(effective,self.group(fixed,'BCCA',LOWER)),
                         {'BCCA_2005bcca639',UPPER_SELF})
        self.assertEqual(len(fixed),len(old))
        self.assertGreater(stats['identity_clusters_split_by_court'],0)

    def test_bcca_appeal_and_bail_controls_stay_distinct_and_preserve_sources(self):
        out,effective,_ = self.run_rows(all_controls=True)
        nc=self.group(out,'BCCA',LOWER_NC)
        bail=self.group(out,'BCCA',BAIL_NC)
        upper=self.group(out,'SCC',UPPER_NC)
        self.assertEqual(len({nc,bail,upper}),3)
        self.assertEqual({r['merged_group_id'] for r in out if r['merge_key']==LOWER_NC},{nc})
        for key,gid in ((LOWER_NC,nc),(BAIL_NC,bail)):
            original=set().union(*(values for member,values in self.ids.items() if member.endswith('|'+key)))
            own_self=set().union(*(set((r.get('self_citation_of') or '').split('|')) for r in out if r['merge_key']==key))
            self.assertEqual(self.sources(effective,gid),original-own_self)
        self.assertNotIn(LOWER,self.own.aliases)
        self.assertEqual(len(out),len(self.fixture['members']))

    def test_court_fact_is_exact_and_native_proof_hash_matches(self):
        evidence=identity_courts.CourtEvidence()
        facts=evidence.exact[LOWER]
        self.assertEqual(len(facts),1)
        self.assertEqual(facts[0],self.fixture['fact'])
        proof=self.fixture['native_procedural_history']
        self.assertEqual(int(facts[0]['span_end'])-int(facts[0]['span_start']),len(proof['text']))
        self.assertEqual(hashlib.sha256(proof['text'].encode()).hexdigest(),facts[0]['span_sha256'])
        self.assertIn('British Columbia Court of Appeal',proof['text'])
        self.assertIn('2004 BCCA 33',proof['text'])
        self.assertIn('193 B.C.A.C. 42',proof['text'])
        row={'merge_key':LOWER,'citation_kind':'reporter','year_printed':'2004'}
        self.assertEqual(set(evidence.evidence(row)),{'court:bcca'})
        self.assertEqual(evidence.evidence(dict(row,merge_key='2004|193|bcac||43')), {})
        self.assertIn('2006|4|fcr||532',evidence.exact)
        self.assertIn('2008|93|or|3d|241',evidence.exact)

    def test_order_does_not_change_membership_or_sources(self):
        first,first_eff,_=self.run_rows(all_controls=True)
        reverse,reverse_eff,_=self.run_rows(all_controls=True,reverse=True)
        def signature(out,effective):
            groups={}
            for row in out:
                groups.setdefault(row['merged_group_id'],set()).add(decide.row_key(row))
            return {frozenset(rows):frozenset(self.sources(effective,gid)) for gid,rows in groups.items()}
        self.assertEqual(signature(first,first_eff),signature(reverse,reverse_eff))


if __name__=='__main__':
    unittest.main()
