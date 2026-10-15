"""French-only corpus rows are real sources, while bilingual rows count once."""
import csv
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import corpus_fields as fields
import extract
import trace_source as trace


class LanguageFallbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]/'implementation')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.corpus = self.root/'corpus'
        self.corpus.mkdir()
        self.records = [
            {'citation_en':'2020 SCC 1','citation_fr':'2020 CSC 1','name_en':'English Name','name_fr':'Nom français',
             'document_date_en':dt.datetime(2020,1,1),'document_date_fr':dt.datetime(2020,1,1),
             'unofficial_text_en':'Citation: 2002 SCC 33.','unofficial_text_fr':'Citation: 2000 CSC 15.'},
            {'citation_en':None,'citation_fr':'2021 CSC 2','name_en':None,'name_fr':'Nom français seulement',
             'document_date_en':None,'document_date_fr':dt.datetime(2021,2,3),
             'unofficial_text_en':None,'unofficial_text_fr':'Énoncé: 2002 CSC 42.'},
            {'citation_en':'2022 SCC 3','citation_fr':None,'name_en':'Missing Text','name_fr':None,
             'document_date_en':dt.datetime(2022,1,1),'document_date_fr':None,
             'unofficial_text_en':None,'unofficial_text_fr':None}]
        pq.write_table(pa.Table.from_pylist(self.records), self.corpus/'SCC.parquet')

    def candidates(self, out):
        with (out/'SCC/cand_batch_0000.csv').open(encoding='utf-8',newline='') as stream:
            return list(csv.DictReader(stream))

    def test_new_scope_adds_french_only_and_preserves_every_english_candidate(self):
        old, new = self.root/'old',self.root/'new'
        extract.run_corpus('SCC',str(old),batch_size=10,corpus_dir=str(self.corpus))
        stats = extract.run_corpus('SCC',str(new),batch_size=10,corpus_dir=str(self.corpus),text_policy=fields.POLICY_FALLBACK)
        original, current = self.candidates(old),self.candidates(new)
        self.assertEqual(original,[r for r in current if r['corpus_row_index']=='0'])
        added = [r for r in current if r['corpus_row_index']=='1']
        self.assertTrue(added)
        self.assertTrue(all(r['source_decision_citation']=='SCC_2021csc2' and r['source_decision_year']=='2021' for r in added))
        self.assertEqual(stats['docs_by_language'],{'en':1,'fr':1})
        self.assertEqual(stats['docs_without_text'],1)
        self.assertFalse(any(r['corpus_row_index']=='2' for r in current))
        self.assertFalse(any(r['raw_string']=='2000 CSC 15' for r in current))

    def test_policy_cannot_change_under_resumed_or_merged_batches(self):
        out = self.root/'out'
        extract.run_corpus('SCC',str(out),batch_size=10,corpus_dir=str(self.corpus))
        with self.assertRaisesRegex(ValueError,'resume'):
            extract.run_corpus('SCC',str(out),batch_size=10,corpus_dir=str(self.corpus),text_policy=fields.POLICY_FALLBACK)
        with self.assertRaisesRegex(ValueError,'merge'):
            extract.merge(str(out),('SCC',),fields.POLICY_FALLBACK)

    def test_legacy_manifest_keeps_english_only(self):
        self.assertEqual(fields.policy_from_manifest({'params':{}}),fields.POLICY_EN)
        self.assertEqual(fields.select_record(self.records[1])['citation'],'')
        with self.assertRaisesRegex(ValueError,'Unknown'):
            fields.policy_from_manifest({'params':{'text_policy':'both'}})

    def test_french_trace_selects_exact_original_field_and_unicode_span(self):
        run = self.root/'run'
        run.mkdir()
        manifest = {'status':'complete','input_identity_verified_unchanged':True,
                    'params':{'courts':['SCC'],'corpus_dir':str(self.corpus),'text_policy':fields.POLICY_FALLBACK},
                    'input_identity':{'files':{'corpus/SCC.parquet':trace.sha256(self.corpus/'SCC.parquet')}}}
        (run/'run_manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        row = trace.corpus_row('SCC',1,run,with_fields=True)
        self.assertEqual(row['citation'],'2021 CSC 2')
        self.assertEqual(row['text_field'],'unofficial_text_fr')
        start = row['text'].index('2002')
        self.assertEqual(row['text'][start:start+11],'2002 CSC 42')
        manifest['params'].pop('text_policy')
        (run/'run_manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        self.assertEqual(trace.corpus_row('SCC',1,run)[2],'')


if __name__ == '__main__':
    unittest.main()
