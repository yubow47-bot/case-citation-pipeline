"""Qualified header aliases, ambiguity and transitive cannot-link regressions."""
from collections import Counter
import csv
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from itertools import permutations

import pyarrow as pa
import pyarrow.parquet as pq
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decide
import registry


class DocumentAliasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clf, _, tables = registry.build_classifier()
        cls.codes = registry.court_code_set(tables['neutral_court_codes'])

    def setUp(self):
        scratch = Path(__file__).resolve().parents[2]/'implementation/round3_tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def source(self, a='2002 SCC 42', b='[2002] 2 SCR 559', text=None):
        return {'citation_en': a, 'citation2_en': b, 'unofficial_text_en': text if text is not None else
                'Neutral citation\n'+a+'\nReport\n'+b+'\nDecision Content\nReasons and other cited judgments'}

    def own(self, sources, zipped=False):
        pq.write_table(pa.Table.from_pylist(sources), self.path/'SCC.parquet')
        evidence = []
        _, stats = registry.own_citation_entries(('SCC',), str(self.path), self.clf, self.codes, evidence)
        path = self.path/'own.csv'
        if zipped:
            path = Path(str(path)+'.gz')
        opener = gzip.open if zipped else open
        with opener(path, 'wt', encoding='utf-8', newline='') as out:
            writer = csv.DictWriter(out, fieldnames=registry.OWN_FIELDS)
            writer.writeheader()
            writer.writerows(evidence)
        return decide.load_own_citations(str(self.path/'own.csv')), evidence, stats

    def row(self, key, kind='neutral', court='SCC', name='X v. Y', observed=''):
        return {'merge_key': key, 'citation_kind': kind, 'court': court, 'case_name_modal': name,
                'year_printed': '2002', 'canonical_string': key, 'jurisdiction': 'CA',
                'occurrence_count': 10, 'self_citation_of': '', 'self_case_name': '',
                'observed_deciding_court': observed, 'court_designation_conflict': 'false',
                'member_origin_status': 'DETERMINED', 'member_origin_country': 'CA',
                'member_origin_basis': 'fixture', 'member_origin_evidence_ids': 'fixture:CA'}

    def adjudicate(self, rows, own, ids=None, registered=None):
        if ids is None:
            ids = {decide.row_key(row): {row['merge_key']+'_source'} for row in rows}
        stats = Counter()
        out, _, effective = decide.adjudicate(rows, ids, {}, {}, 'XC', stats, False,
            registry=registered, gate='registered', own_cites=own)
        return out, effective, stats

    def test_explicit_header_alias_joins_weak_cocitation_across_names_and_courts(self):
        own, evidence, _ = self.own([self.source()], zipped=True)
        rows = [self.row('2002||scc||42', name='Bell ExpressVu'),
                self.row('2002|2|scr||559', 'reporter', 'ONCA', 'Bell ExpressVu Partnership'),
                self.row('2002|2|scr||559', 'reporter', 'BCCA', '')]
        ids = {decide.row_key(rows[0]): {'NC_ONLY'}, decide.row_key(rows[1]): {'REPORT_ONLY'},
               decide.row_key(rows[2]): {'THIRD'}}
        out, effective, stats = self.adjudicate(rows, own, ids)
        self.assertEqual(len({row['merged_group_id'] for row in out}), 1)
        self.assertEqual({row['distinct_decisions_count'] for row in out}, {3})
        self.assertEqual({row['identity_basis'] for row in out}, {'document_alias'})
        self.assertEqual({row['identity_status'] for row in effective}, {'document_alias'})
        self.assertEqual({row['group_origin_country'] for row in out}, {'CA'})
        self.assertTrue(all(row['document_alias_evidence_ids'].startswith('own:') for row in out))
        self.assertEqual(stats['document_alias_cluster_unions'], 2)
        self.assertTrue(all(row['identity_qualified'] == 'true' for row in evidence))
        self.assertEqual(decide.BAR, .8)

    def test_dd_unions_sources_and_excludes_own_reporter_alias(self):
        own, _, _ = self.own([self.source()])
        rows = [self.row('2002||scc||42'), self.row('2002|2|scr||559', 'reporter')]
        did = 'SCC_2002scc42'
        ids = {decide.row_key(rows[0]): {'shared','NC_ONLY',did},
               decide.row_key(rows[1]): {'shared','REPORT_ONLY',did}}
        out, effective, _ = self.adjudicate(rows, own, ids)
        self.assertEqual({row['distinct_decisions_count'] for row in out}, {3})
        self.assertEqual([(row['source_decision'],row['status']) for row in effective if row['source_decision'] == did],
                         [(did,'excluded_self')])

    def test_metadata_must_be_one_complete_legal_citation(self):
        for value in ('[2002] 2 SCR 559 appendix', '2002 SCC 42; 2002 SCC 43', 'T-1234-20'):
            self.assertIsNone(registry.one_key(self.clf, 'SCC', value, self.codes, own_alias=True)[0])
        self.assertIsNone(registry.one_key(self.clf, 'SCC', '[2002] 2 SCR 559', self.codes)[0])
        self.assertEqual(registry.one_key(self.clf, 'SCC', '[2002] 2 SCR 559', self.codes, own_alias=True)[0],
                         '2002|2|scr||559')

    def test_unknown_boundary_preserves_self_fact_but_refuses_identity(self):
        own, evidence, stats = self.own([self.source(text='2002 SCC 42\n[2002] 2 SCR 559\nUnrecognized body')])
        self.assertFalse(own.aliases)
        self.assertEqual(own['2002|2|scr||559'], {'SCC_2002scc42'})
        self.assertTrue(all(row['claim_status'] == 'self_only_unknown_header_boundary' for row in evidence))

    def test_body_occurrence_after_boundary_cannot_authorize_alias(self):
        own, evidence, _ = self.own([self.source(text='2002 SCC 42\nDecision Content\n[2002] 2 SCR 559')])
        self.assertFalse(own.aliases)
        self.assertTrue(all(row['identity_qualified'] == 'false' for row in evidence))

    def test_duplicate_source_rows_are_rejected_and_retained_as_diagnostics(self):
        own, evidence, _ = self.own([self.source(), self.source()])
        self.assertFalse(own)
        self.assertFalse(own.aliases)
        self.assertTrue(all(row['claim_status'] == 'rejected_ambiguous_source_or_key' for row in evidence))

    def test_same_key_claimed_by_two_sources_cannot_bridge_judgments(self):
        own, evidence, _ = self.own([self.source(), self.source('2002 SCC 43')])
        self.assertNotIn('2002|2|scr||559', own.aliases)
        self.assertNotIn('2002|2|scr||559', own)
        rows = [self.row('2002||scc||42', name='A'), self.row('2002||scc||43', name='B'),
                self.row('2002|2|scr||559', 'reporter', name='C')]
        out, _, _ = self.adjudicate(rows, own)
        self.assertEqual(len({row['merged_group_id'] for row in out}), 3)

    def test_positive_court_conflict_overrides_alias_claim(self):
        own, _, _ = self.own([self.source()])
        rows = [self.row('2002||scc||42'), self.row('2002|2|scr||559', 'reporter',
                observed='British Columbia Court of Appeal')]
        out, _, stats = self.adjudicate(rows, own)
        self.assertEqual(len({row['merged_group_id'] for row in out}), 2)
        self.assertGreater(stats['document_alias_blocked_positive_court_conflict'], 0)

    def test_distinct_neutral_numbers_are_not_aliases_even_in_one_metadata_row(self):
        own, evidence, _ = self.own([self.source('2002 SCC 42', '2002 SCC 43')])
        self.assertFalse(own)
        self.assertFalse(own.aliases)
        self.assertTrue(all(row['claim_status'] == 'rejected_conflicting_metadata_keys' for row in evidence))
        rows = [self.row('2002||scc||42', name='A'), self.row('2002||scc||43', name='B')]
        out, _, stats = self.adjudicate(rows, own)
        self.assertEqual(len({row['merged_group_id'] for row in out}), 2)

    def test_distinct_vendor_numbers_are_not_aliases_even_in_one_metadata_row(self):
        own, evidence, _ = self.own([self.source('2002 CanLII 111', '2002 CanLII 222')])
        self.assertFalse(own)
        self.assertTrue(all(row['claim_status'] == 'rejected_conflicting_metadata_keys' for row in evidence))
        rows = [self.row('2002||canlii||111', 'identifier', name='A'),
                self.row('2002||canlii||222', 'identifier', name='B')]
        out, _, stats = self.adjudicate(rows, own)
        self.assertEqual(len({row['merged_group_id'] for row in out}), 2)

    def test_existing_heuristic_cluster_is_split_by_different_proven_documents(self):
        own, _, _ = self.own([self.source('2000 SCC 15','[2000] 1 SCR 381'),
                              self.source('2000 SCC 17','[2000] 1 SCR 439')])
        rows = [self.row('2000||scc||15', name='Neutral name variant'),
                self.row('2000|1|scr||381', 'reporter', name='Biniaris'),
                self.row('2000|1|scr||439', 'reporter', name='Biniaris'),
                self.row('|9|unknown||10','reporter', name='Biniaris')]
        for row in rows:
            row['year_printed']='2000'
        ids = {decide.row_key(rows[0]): {'NC_ONLY'}, decide.row_key(rows[1]): {'REPORT_ONLY','SCC_2000scc15'},
               decide.row_key(rows[2]): {'WRONG_DOCUMENT'}, decide.row_key(rows[3]): {'UNCLAIMED'}}
        for perm in permutations(rows):
            out, effective, stats = self.adjudicate(list(perm), own, ids)
            groups = {row['merge_key']:row['merged_group_id'] for row in out}
            self.assertEqual(groups['2000||scc||15'],groups['2000|1|scr||381'])
            self.assertNotEqual(groups['2000|1|scr||381'],groups['2000|1|scr||439'])
            self.assertNotEqual(groups['2000|1|scr||381'],groups['|9|unknown||10'])
            self.assertEqual({row['distinct_decisions_count'] for row in out if row['merged_group_id']==groups['2000||scc||15']},{2})
            self.assertGreater(stats['document_claim_contaminated_clusters_split'],0)
            self.assertGreater(stats['document_claim_unassigned_key_units'],0)

    def test_true_2007_pair_cannot_drag_unknown_2006_and_2008_into_wide_group(self):
        own, _, _ = self.own([self.source('2007 SCC 33','[2007] 2 SCR 793')])
        # These synthetic exact keys have no positive court fact. Real Addison
        # FCR/OR keys now exercise the earlier court guard in a separate test.
        rows = [self.row('2007||scc||33',name='A & B'),self.row('2008|99|or|3d|241','reporter',name='A & B'),
                self.row('2007|2|scr||793','reporter',name='A and B'),self.row('2006|9|fcr||532','reporter',name='A and B')]
        for row in rows:
            row['year_printed']=row['merge_key'].split('|')[0]
        ids={decide.row_key(rows[0]):{'A'},decide.row_key(rows[1]):{'A'},
             decide.row_key(rows[2]):{'REPORT'},decide.row_key(rows[3]):{'LOWER_COURT'}}
        for perm in permutations(rows):
            out,_,stats=self.adjudicate([dict(row) for row in perm],own,ids)
            group={row['merge_key']:row['merged_group_id'] for row in out}
            self.assertEqual(group['2007||scc||33'],group['2007|2|scr||793'])
            self.assertNotEqual(group['2007||scc||33'],group['2006|9|fcr||532'])
            self.assertNotEqual(group['2007||scc||33'],group['2008|99|or|3d|241'])
            self.assertEqual(stats['document_alias_unknown_key_units_held_year_span'],2)
            for gid in set(group.values()):
                years={decide.row_year(row) for row in out if row['merged_group_id']==gid}
                self.assertLessEqual(max(years)-min(years),1)

    def test_cross_court_does_not_guess_a_guarded_same_key_back_into_document(self):
        own,_,_=self.own([self.source('2007 SCC 33','[2007] 2 SCR 793')])
        rows=[self.row('2007||scc||33',name='A & B'),self.row('2008|99|or|3d|241','reporter',name='A & B'),
              self.row('2007|2|scr||793','reporter',name='A and B'),self.row('2006|9|fcr||532','reporter',name='A and B')]
        for row in rows:row['year_printed']=row['merge_key'].split('|')[0]
        ids={decide.row_key(rows[0]):{'A'},decide.row_key(rows[1]):{'A'},
             decide.row_key(rows[2]):{'REPORT'},decide.row_key(rows[3]):{'LOWER'}}
        first,_,_=self.adjudicate(rows,own,ids)
        for row in first:row['case_name_modal']='Now the same name'
        extra=self.row('2006|9|fcr||532','reporter','ONCA','Now the same name')
        extra['year_printed']='2006'
        ids[decide.row_key(extra)]={'SECOND_COURT_LOWER'}
        second,effective,stats=self.adjudicate(first+[extra],own,ids)
        group={row['merge_key']:row['merged_group_id'] for row in second}
        self.assertEqual(group['2007||scc||33'],group['2007|2|scr||793'])
        self.assertNotEqual(group['2007||scc||33'],group['2006|9|fcr||532'])
        lower=[row for row in second if row['merge_key']=='2006|9|fcr||532']
        self.assertEqual(len({row['merged_group_id'] for row in lower}),1)
        self.assertTrue(all(row['document_alias_holdout_evidence_ids'].startswith('own:') for row in lower))
        self.assertEqual(stats['document_alias_inherited_holdout_key_units'],2)

    def test_positive_exact_court_facts_separate_isolated_addison_from_lower_and_other_cases(self):
        own,_,_=self.own([self.source('2007 SCC 33','[2007] 2 SCR 793')])
        rows=[self.row('2007||scc||33',name='A & B'),self.row('2007|2|scr||793','reporter',name='A and B'),
              self.row('2006|4|fcr||532','reporter',name='A and B'),self.row('2008|93|or|3d|241','reporter',name='A & B')]
        for row in rows:row['year_printed']=row['merge_key'].split('|')[0]
        ids={decide.row_key(row):{'shared'} for row in rows}
        # Complete source overlap and matching modal names cannot override
        # exact positive evidence of FCA and ONSC judgments.
        for keys in (('2007||scc||33','2007|2|scr||793','2006|4|fcr||532'),
                     ('2007||scc||33','2007|2|scr||793','2008|93|or|3d|241'),
                     tuple(row['merge_key'] for row in rows)):
            for perm in permutations([row for row in rows if row['merge_key'] in keys]):
                out,_,_=self.adjudicate([dict(row) for row in perm],own,ids)
                group={row['merge_key']:row['merged_group_id'] for row in out}
                self.assertEqual(group['2007||scc||33'],group['2007|2|scr||793'])
                for negative in set(keys)-{'2007||scc||33','2007|2|scr||793'}:
                    self.assertNotEqual(group['2007||scc||33'],group[negative])

    def test_multi_target_holdout_preserves_complete_target_proof_association(self):
        own,_,_=self.own([self.source('2007 SCC 33','[2007] 2 SCR 793'),
                          self.source('2008 SCC 34','[2008] 2 SCR 794')])
        documents={did:{r['evidence_id'] for values in own.evidence.values() for r in values
                       if r['decision_id']==did and r['identity_qualified']=='true'} for did in own.aliases.values()}
        rows=[self.row('2007||scc||33'),self.row('2007|2|scr||793','reporter'),
              self.row('2008||scc||34'),self.row('2008|2|scr||794','reporter')]
        for row in rows:row['year_printed']=row['merge_key'].split('|')[0]
        unknown=self.row('2006|4|fcr||532','reporter')
        unknown['year_printed']='2006'
        unknown['document_alias_holdout_doc_ids']='|'.join(sorted(documents))
        unknown['document_alias_holdout_evidence_ids']='|'.join(sorted(set().union(*documents.values())))
        ids={decide.row_key(row):{row['merge_key']+'_SOURCE'} for row in rows+[unknown]}
        first,_,stats=self.adjudicate(rows+[unknown],own,ids)
        self.assertEqual(stats['document_alias_inherited_holdout_key_units'],1)
        extra=self.row('2006|4|fcr||532','reporter','ONCA')
        extra['year_printed']='2006'
        ids[decide.row_key(extra)]={'ONCA_SOURCE'}
        second,_,stats=self.adjudicate(first+[extra],own,ids)
        held=[row for row in second if row['merge_key']==unknown['merge_key']]
        self.assertEqual(len({row['merged_group_id'] for row in held}),1)
        for row in held:
            self.assertEqual(set(row['document_alias_holdout_doc_ids'].split('|')),set(documents))
            self.assertEqual(set(row['document_alias_holdout_evidence_ids'].split('|')),set().union(*documents.values()))
        group=held[0]['merged_group_id']
        self.assertFalse(any(row['merged_group_id']==group for row in second if row['merge_key'] in own.aliases))

    def test_malformed_or_stale_holdout_proofs_fail_closed(self):
        own,_,_=self.own([self.source()])
        did='SCC_2002scc42'
        proofs={r['evidence_id'] for values in own.evidence.values() for r in values}
        variants=[(did,''),('',next(iter(proofs))),(did,'own:unknown'),(did,next(iter(proofs))),
                  ('SCC_WRONG','|'.join(sorted(proofs)))]
        for targets,evidence in variants:
            row=self.row('2002|2|scr||559','reporter')
            row['document_alias_holdout_doc_ids']=targets
            row['document_alias_holdout_evidence_ids']=evidence
            with self.assertRaisesRegex(ValueError,'holdout.*proofs'):
                self.adjudicate([row],own)

    def test_alias_union_respects_same_target_but_can_restore_another_proven_document(self):
        own,_,_=self.own([self.source('2002 SCC 42','[2002] 2 SCR 559'),
                          self.source('2002 SCC 43','[2002] 2 SCR 560')])
        docs={did:{r['evidence_id'] for values in own.evidence.values() for r in values if r['decision_id']==did}
              for did in own.aliases.values()}
        a,b='SCC_2002scc42','SCC_2002scc43'
        held_a=self.row('2002|2|scr||559','reporter')
        held_a['document_alias_holdout_doc_ids']=a
        held_a['document_alias_holdout_evidence_ids']='|'.join(sorted(docs[a]))
        out,_,stats=self.adjudicate([self.row('2002||scc||42'),held_a],own)
        self.assertEqual(len({r['merged_group_id'] for r in out}),2)
        self.assertGreater(stats['document_alias_blocked_explicit_document_holdout'],0)
        held_b=self.row('2002|2|scr||560','reporter')
        held_b['document_alias_holdout_doc_ids']=a
        held_b['document_alias_holdout_evidence_ids']='|'.join(sorted(docs[a]))
        out,_,_=self.adjudicate([self.row('2002||scc||43'),held_b],own)
        self.assertEqual(len({r['merged_group_id'] for r in out}),1)
        self.assertEqual({r['document_alias_decision_id'] for r in out},{b})

    def test_carlos_true_number_cannot_join_housen_via_reporter_component(self):
        own, _, _ = self.own([self.source('2002 SCC 33', '[2002] 2 SCR 235')])
        rows = [self.row('2002||scc||33', name='Housen'),
                self.row('2002|2|scr||235', 'reporter', name='Housen'),
                self.row('2002||scc||35', name='Housen')]
        ids = {decide.row_key(rows[0]): {'A','B','C','D'}, decide.row_key(rows[1]): {'REPORT_ONLY'},
               decide.row_key(rows[2]): {'Carlos_SOURCE'}}
        registered = {'2002||scc||35': ('SCC_2002scc35','SCC'), '2002||scc||33': ('SCC_2002scc33','SCC')}
        for perm in permutations(rows):
            out, _, _ = self.adjudicate(list(perm), own, ids, registered)
            group = {row['merge_key']:row['merged_group_id'] for row in out}
            self.assertEqual(group['2002||scc||33'],group['2002|2|scr||235'])
            self.assertNotEqual(group['2002||scc||33'],group['2002||scc||35'])

    def test_legacy_four_column_own_facts_do_not_authorize_identity(self):
        path = self.path/'old.csv'
        path.write_text('merge_key,decision_id,source_court,field\n2002||scc||42,SCC_2002scc42,SCC,citation_en\n'
                        '2002|2|scr||559,SCC_2002scc42,SCC,citation2_en\n',encoding='utf-8')
        own = decide.load_own_citations(str(path))
        self.assertFalse(own.aliases)
        out, _, _ = self.adjudicate([self.row('2002||scc||42'),self.row('2002|2|scr||559','reporter')], own)
        self.assertEqual(len({row['merged_group_id'] for row in out}), 2)

    def test_corrupted_qualified_proof_hash_fails_closed(self):
        _, _, _ = self.own([self.source()])
        path = self.path/'own.csv'
        content = path.read_text(encoding='utf-8').replace('qualified_metadata_header', 'qualified_metadata_headeX', 1)
        path.write_text(content,encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            decide.load_own_citations(str(path))

    def test_gzip_registry_and_decision_id_readers(self):
        path = self.path/'registry.csv.gz'
        with gzip.open(path,'wt',encoding='utf-8') as out:
            out.write('merge_key,decision_id,source_court\n2002||scc||35,SCC_2002scc35,SCC\n')
        self.assertIn('2002||scc||35',decide.load_registry(str(self.path/'registry.csv')))
        with gzip.open(self.path/'ids.csv.gz','wt',encoding='utf-8') as out:
            out.write('merge_key,source_decision_citation\na,SOURCE\n')
        self.assertEqual(decide.load_decision_ids(str(self.path/'ids.csv'),court='SCC')['SCC|a'],{'SOURCE'})
        self.assertEqual(decide.read_csv(str(self.path/'ids.csv'))[0]['merge_key'],'a')

    def test_registry_reads_gzip_and_adds_metadata_only_true_neutral(self):
        pq.write_table(pa.Table.from_pylist([self.source('2002 SCC 35','[2002] 2 SCR 411')]),self.path/'SCC.parquet')
        run = self.path/'run'
        folder = run/'merge_out/SCC'
        folder.mkdir(parents=True)
        with gzip.open(folder/'merged.csv.gz','wt',encoding='utf-8') as out:
            out.write('merge_key,citation_kind,self_citation_of\n2002|2|scr||411,reporter,SCC_2002scc35\n')
        manifest = registry.build(str(run),corpus_dir=str(self.path),extracted_courts=('SCC',),verbose=False)
        protected = decide.load_registry(str(run/'registry/decision_registry.csv'))
        self.assertIn('2002||scc||35',protected)
        self.assertNotIn('2002|2|scr||411',protected)
        self.assertEqual(manifest['by_source'],{'corpus_citation':1})


if __name__ == '__main__':
    unittest.main()
