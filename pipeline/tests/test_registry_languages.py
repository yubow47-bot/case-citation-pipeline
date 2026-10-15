"""Native-language header proofs and canonical-source boundaries, without network."""
from collections import Counter
import csv
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decide
import registry
from corpus_fields import POLICY_EN, POLICY_FALLBACK


class RegistryLanguageTests(unittest.TestCase):
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

    @staticmethod
    def source(en='2002 SCC 42', en2='[2002] 2 SCR 559',
               fr='2002 CSC 42', fr2='[2002] 2 RCS 559'):
        return {'citation_en': en, 'citation2_en': en2,
                'citation_fr': fr, 'citation2_fr': fr2,
                'unofficial_text_en': ('Neutral citation\n'+en+'\nReport\n'+en2+
                                      '\nDecision Content\nEnglish reasons') if en else '',
                'unofficial_text_fr': ('Référence neutre\n'+fr+'\nRecueil\n'+fr2+
                                      '\nContenu de la décision\nMotifs français') if fr else ''}

    def write(self, records):
        pq.write_table(pa.Table.from_pylist(records), self.path/'SCC.parquet')

    def own(self, records, policy=None):
        self.write(records)
        evidence = []
        kwargs = {'text_policy': policy} if policy is not None else {}
        _, stats = registry.own_citation_entries(('SCC',), str(self.path), self.clf,
                                                self.codes, evidence, **kwargs)
        path = self.path/'own.csv'
        with path.open('w', encoding='utf-8', newline='') as out:
            writer = csv.DictWriter(out, fieldnames=registry.OWN_FIELDS)
            writer.writeheader()
            writer.writerows(evidence)
        return decide.load_own_citations(str(path)), evidence, stats

    def test_default_and_explicit_english_policy_have_identical_scope_and_proofs(self):
        records = [self.source(), self.source('', '', '2003 CSC 3', '[2003] 1 RCS 3')]
        default, evidence, stats = self.own(records)
        explicit, evidence2, stats2 = self.own(records, POLICY_EN)
        self.assertEqual(evidence, evidence2)
        self.assertEqual(stats, stats2)
        self.assertEqual(default.aliases, explicit.aliases)
        self.assertEqual(set(default.aliases), {'2002||scc||42', '2002|2|scr||559'})
        self.assertTrue(all(row['language'] == 'en' for row in evidence))

    def test_french_only_source_has_native_header_and_stable_french_id(self):
        record = self.source('', '', '2002 CSC 42', '[2002] 2 R.C.S. 559')
        own, evidence, _ = self.own([record], POLICY_FALLBACK)
        self.assertEqual(own.aliases, {'2002||csc||42': 'SCC_2002csc42',
                                      '2002|2|rcs||559': 'SCC_2002csc42'})
        for row in evidence:
            self.assertEqual(row['text_field'], 'unofficial_text_fr')
            self.assertEqual(row['source_citation_field'], 'citation_fr')
            self.assertEqual(row['header_boundary'], 'Contenu de la décision')
            self.assertEqual(row['text_sha256'], hashlib.sha256(record['unofficial_text_fr'].encode()).hexdigest())
            self.assertEqual(row['source_citation_sha256'], hashlib.sha256(record['citation_fr'].encode()).hexdigest())
            text = record[row['text_field']]
            raw = text[row['header_start']:row['header_match_end']]
            self.assertEqual(row['header_raw_sha256'], hashlib.sha256(raw.encode()).hexdigest())

    def test_bilingual_native_pairs_share_one_physical_source_with_independent_text_hashes(self):
        own, evidence, _ = self.own([self.source()], POLICY_FALLBACK)
        self.assertEqual(set(own.aliases), {'2002||scc||42', '2002|2|scr||559',
                                           '2002||csc||42', '2002|2|rcs||559'})
        self.assertEqual(set(own.aliases.values()), {'SCC_2002scc42'})
        self.assertEqual(len({row['text_sha256'] for row in evidence}), 2)
        self.assertEqual(len({(row['source_court'], row['corpus_row'], row['corpus_sha256'])
                              for row in evidence}), 1)
        self.assertTrue(all(row['identity_qualified'] == 'true' for row in evidence))

    def test_same_native_key_in_both_languages_is_not_a_second_source(self):
        record = self.source(fr='2002 SCC 42', fr2='[2002] 2 SCR 559')
        own, evidence, _ = self.own([record], POLICY_FALLBACK)
        self.assertEqual(len(own.evidence['2002||scc||42']), 2)
        self.assertEqual(own.aliases['2002||scc||42'], 'SCC_2002scc42')
        self.assertEqual(own.diagnostics['ambiguous_qualified_alias_keys'], 0)

    def test_two_different_keys_can_each_have_one_native_language_proof(self):
        own, evidence, _ = self.own([self.source(en2='', fr='2002 CSC 42', fr2='')], POLICY_FALLBACK)
        self.assertEqual(own.aliases, {'2002||scc||42': 'SCC_2002scc42',
                                      '2002||csc||42': 'SCC_2002scc42'})
        self.assertEqual({row['language'] for row in evidence}, {'en', 'fr'})

    def test_header_evidence_cannot_be_borrowed_from_other_language(self):
        record = self.source(fr='', fr2='')
        record['unofficial_text_fr'] = record['unofficial_text_en']
        record['unofficial_text_en'] = ''
        own, evidence, _ = self.own([record], POLICY_FALLBACK)
        self.assertFalse(own.aliases)
        self.assertEqual({row['claim_status'] for row in evidence}, {'self_only_unknown_header_boundary'})

    def test_missing_french_header_does_not_revoke_proven_english_pair(self):
        record = self.source()
        record['unofficial_text_fr'] = 'Référence neutre\n2002 CSC 42\n[2002] 2 RCS 559\nUnrecognized body'
        own, evidence, _ = self.own([record], POLICY_FALLBACK)
        self.assertEqual(set(own.aliases), {'2002||scc||42', '2002|2|scr||559'})
        self.assertTrue(all(row['identity_qualified'] == 'false' for row in evidence if row['language'] == 'fr'))
        self.assertEqual(own['2002|2|rcs||559'], {'SCC_2002scc42'})

    def test_french_body_citation_after_boundary_is_not_an_own_header_proof(self):
        record = self.source('', '', '2002 CSC 42', '[2002] 2 RCS 559')
        record['unofficial_text_fr'] = '2002 CSC 42\nContenu de la décision\n[2002] 2 RCS 559'
        own, evidence, _ = self.own([record], POLICY_FALLBACK)
        self.assertFalse(own.aliases)
        self.assertTrue(all(row['identity_qualified'] == 'false' for row in evidence))

    def test_conflicting_native_neutral_numbers_reject_both_identity_and_self_exclusion(self):
        own, evidence, _ = self.own([self.source(fr='2002 CSC 43', fr2='')], POLICY_FALLBACK)
        self.assertFalse(own)
        self.assertFalse(own.aliases)
        self.assertEqual({row['claim_status'] for row in evidence}, {'rejected_conflicting_metadata_keys'})
        self.assertEqual({row['claim_detail'] for row in evidence}, {'different_neutral_numbers'})

    def test_duplicate_physical_sources_still_reject_bilingual_claims(self):
        own, evidence, _ = self.own([self.source(), self.source()], POLICY_FALLBACK)
        self.assertFalse(own)
        self.assertEqual({row['claim_status'] for row in evidence}, {'rejected_ambiguous_source_or_key'})

    def test_verified_bilingual_keys_do_not_admit_number_year_or_unverified_code_changes(self):
        self.assertTrue(decide.verified_bilingual_keys('2002||scc||42', '2002||csc||42'))
        for key in ('2002||csc||43', '2003||csc||42', '2002||onca||42',
                    '2002|2|csc||42', '2002||csc|division|42', '2002||csc||42|extra',
                    '2002||csc||42a', '2002 CSC 42'):
            self.assertFalse(decide.verified_bilingual_keys('2002||scc||42', key))
        self.assertIsNone(decide.same_decision_kind('2002||scc||42', '', 1, '2002||csc||42', '', 1))

    def test_holdout_carries_all_native_proofs_even_when_french_keys_are_absent_from_first_court(self):
        record = self.source('2007 SCC 33', '[2007] 2 SCR 793', '2007 CSC 33', '[2007] 2 RCS 793')
        own, evidence, _ = self.own([record], POLICY_FALLBACK)
        def row(key, name, court='ONCA'):
            return {'merge_key': key, 'citation_kind': 'neutral' if key.split('|')[2] in ('scc','csc') else 'reporter',
                    'court': court, 'case_name_modal': name, 'year_printed': key.split('|')[0],
                    'canonical_string': key, 'jurisdiction': 'CA', 'occurrence_count': 10,
                    'self_citation_of': '', 'self_case_name': '', 'observed_deciding_court': '',
                    'court_designation_conflict': 'false', 'member_origin_status': 'DETERMINED',
                    'member_origin_country': 'CA', 'member_origin_basis': 'fixture',
                    'member_origin_evidence_ids': 'fixture:CA'}
        # Synthetic unclaimed keys keep this test about proof lifecycle, rather
        # than the separate sourced positive court facts for actual Addison.
        rows = [row('2007||scc||33','A & B'), row('2008|99|or|3d|241','A & B'),
                row('2007|2|scr||793','A and B'), row('2006|9|fcr||532','A and B')]
        ids = {decide.row_key(rows[0]): {'A'}, decide.row_key(rows[1]): {'A'},
               decide.row_key(rows[2]): {'REPORT'}, decide.row_key(rows[3]): {'LOWER'}}
        first, _, _ = decide.adjudicate(rows, ids, {}, {}, 'ONCA', Counter(), False,
                                        gate='registered', own_cites=own)
        complete_proofs = {r['evidence_id'] for r in evidence if r['identity_qualified'] == 'true'}
        self.assertEqual(len(complete_proofs), 4)
        held = [r for r in first if 'holdout' in r.get('split_reason','') or r['document_alias_holdout_doc_ids']]
        self.assertEqual(len(held), 2)
        for r in held:
            self.assertEqual(set(r['document_alias_holdout_evidence_ids'].split('|')), complete_proofs)
        extra = [row('2007||csc||33','Unrelated name','SCC'), row('2007|2|rcs||793','','SCC')]
        ids.update({decide.row_key(r): {r['merge_key']+'_source'} for r in extra})
        second, _, stats = decide.adjudicate(first+extra, ids, {}, {}, 'XC', Counter(), False,
                                             gate='registered', own_cites=own)
        groups = {r['merge_key']:r['merged_group_id'] for r in second}
        self.assertEqual(len({groups[key] for key in own.aliases}), 1)
        self.assertNotEqual(groups['2007||scc||33'], groups['2006|9|fcr||532'])
        self.assertNotEqual(groups['2007||scc||33'], groups['2008|99|or|3d|241'])

    def test_metadata_only_french_and_bilingual_real_neutrals_are_registered_under_canonical_ids(self):
        self.write([self.source(), self.source('', '', '2003 CSC 3', '[2003] 1 RCS 3')])
        entries, _, _ = registry.corpus_citation_entries(('SCC',), str(self.path), self.clf,
                                                       self.codes, POLICY_FALLBACK)
        self.assertEqual({(key, did) for key, did, _, _ in entries},
                         {('2002||scc||42', 'SCC_2002scc42'), ('2002||csc||42', 'SCC_2002scc42'),
                          ('2003||csc||3', 'SCC_2003csc3')})
        english, _, _ = registry.corpus_citation_entries(('SCC',), str(self.path), self.clf, self.codes)
        self.assertEqual({key for key, _, _, _ in english}, {'2002||scc||42'})

    def test_registry_manifest_and_invalid_policy_fail_before_output_creation(self):
        self.write([self.source('', '', '2002 CSC 42', '[2002] 2 RCS 559')])
        run = self.path/'run'
        folder = run/'merge_out/SCC'
        folder.mkdir(parents=True)
        (folder/'merged.csv').write_text('merge_key,citation_kind,self_citation_of\n', encoding='utf-8')
        manifest = registry.build(str(run), corpus_dir=str(self.path), extracted_courts=('SCC',),
                                  verbose=False, text_policy=POLICY_FALLBACK)
        self.assertEqual(manifest['schema_version'], 3)
        self.assertEqual(manifest['text_policy'], POLICY_FALLBACK)
        self.assertIn('2002||csc||42', decide.load_registry(str(run/'registry/decision_registry.csv')))
        with self.assertRaises(ValueError):
            registry.build(str(self.path/'invalid'), text_policy='guess_language')
        self.assertFalse((self.path/'invalid').exists())


if __name__ == '__main__':
    unittest.main()
