"""Small real-Parquet policy/field provenance checks, with no network or cache."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
import build
import common
import index_cases
import index_edges


class CorpusLanguageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(common, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.corpus = self.root / 'corpus'
        self.corpus.mkdir()
        self.quote = '2000 SCC 1'
        self.original_quote = self.quote
        self.english = 'An English court cites '+self.quote+' in its reasoning.'
        self.french = 'Le juge français😀 cite '+self.quote+' dans les motifs.'
        records = [
            dict(citation_en='2020 SCC 2', citation_fr='2020 CSC 2', name_en='English source',
                 name_fr='Source bilingue', document_date_en='2020-01-01', document_date_fr='2020-01-02',
                 unofficial_text_en=self.english, unofficial_text_fr='A different French parallel text.'),
            dict(citation_en=None, citation_fr='2021 CSC 3', name_en=None, name_fr='Source français',
                 document_date_en=None, document_date_fr='2021-02-01', unofficial_text_en=None,
                 unofficial_text_fr=self.french),
            dict(citation_en='2022 SCC 4', citation_fr=None, name_en='Metadata without text', name_fr=None,
                 document_date_en='2022-03-01', document_date_fr=None, unofficial_text_en=None, unofficial_text_fr=None),
        ]
        pq.write_table(pa.Table.from_pylist(records), self.corpus / 'SCC.parquet', row_group_size=2)

    def csv(self, run, relative, records):
        path = run / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8', newline='') as out:
            writer = csv.DictWriter(out, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)

    def rewrite_original_quote(self, original):
        self.original_quote = original
        self.english = self.english.replace(self.quote, original)
        self.french = self.french.replace(self.quote, original)
        records = pq.read_table(self.corpus / 'SCC.parquet').to_pylist()
        records[0]['unofficial_text_en'] = self.english
        records[1]['unofficial_text_fr'] = self.french
        pq.write_table(pa.Table.from_pylist(records), self.corpus / 'SCC.parquet', row_group_size=2)

    def run_fixture(self, fallback, bad_raw=False, index=True, end_delta=0):
        run = self.root / ('run_fr' if fallback else 'run_legacy')
        run.mkdir()
        sources = [('SCC_2020scc2', 0, self.english)]
        if fallback:
            sources.append(('SCC_2021csc3', 1, self.french))
        self.csv(run, 'select_out/selected.csv', [dict(court='SCC', merge_key='mk', merged_group_id='g',
            canonical_string=self.quote, is_primary='true', distinct_decisions_count=str(len(sources)),
            case_name_modal='Example case', year_printed='2000', kept='false',
            group_foreign_status='DOMESTIC_CA', group_origin_country='CA')])
        self.csv(run, 'edges/citation_edges.csv', [dict(source_decision=src, resolved_cited_case='g', edge_support='supported')
                                                  for src, _, _ in sources])
        self.csv(run, 'decide_out/cross_court/effective_sources.csv', [dict(source_decision=src, merged_group_id='g', status='counted')
                                                                   for src, _, _ in sources])
        self.csv(run, 'registry/decision_own_citations.csv', [dict(merge_key='own', decision_id='SCC_2020scc2')])
        self.csv(run, 'merge_out/SCC/mentions_candidates.csv', [dict(arbitration_status='counted', merge_key='mk',
            source_decision_citation=src, corpus_row_index=str(row), match_start_offset=str(text.index(self.original_quote)),
            match_end_offset=str(text.index(self.original_quote)+len(self.original_quote)+end_delta),
            raw_string='NOT THE CITATION' if bad_raw and row == 1 else self.quote) for src, row, text in sources])
        (run / 'select_out/manifest.json').write_text(json.dumps({'stats': {'groups_total': 1, 'rows_total': 1}}))
        params = {'courts': ['SCC'], 'corpus_dir': str(self.corpus)}
        if fallback:
            params['text_policy'] = 'en_then_fr'
        manifest = {'status': 'complete', 'input_identity_verified_unchanged': True, 'params': params,
                    'input_identity': {'fingerprint': 'tiny language fixture',
                                       'files': {'corpus/SCC.parquet': common.digest(self.corpus/'SCC.parquet')}}}
        (run/'run_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        db = self.root / (run.name+'.db')
        build.build(run, db)
        if index:
            index_cases.build_profiles(run, db)
            index_edges.build_passages(run, db)
        return run, common.connect(db, readonly=True)

    def test_french_fallback_metadata_and_unicode_evidence_are_one_source(self):
        run, db = self.run_fixture(True)
        self.addCleanup(db.close)
        documents = db.execute('SELECT * FROM documents ORDER BY corpus_row').fetchall()
        self.assertEqual(len(documents), 3)
        self.assertEqual(tuple(documents[1][k] for k in ('source_id', 'citation', 'name', 'decision_date')),
                         ('SCC_2021csc3', '2021 CSC 3', 'Source français', '2021-02-01'))
        self.assertEqual(db.execute('SELECT COUNT(*) FROM citation_edges').fetchone()[0], 2)
        evidence = json.loads(db.execute("SELECT evidence_json FROM edge_passages WHERE source_decision='SCC_2021csc3'").fetchone()[0])
        self.assertEqual(evidence['corpus']['text_field'], 'unofficial_text_fr')
        self.assertEqual(evidence['corpus']['language'], 'fr')
        self.assertEqual(evidence['corpus']['citation_field'], 'citation_fr')
        self.assertEqual(evidence['corpus']['date_field'], 'document_date_fr')
        self.assertEqual(self.french[evidence['match_start']:evidence['match_end']], self.quote)
        profile = json.loads(db.execute("SELECT evidence_json FROM profile_passages WHERE source_decision='SCC_2021csc3'").fetchone()[0])
        self.assertEqual(profile['corpus']['text_field'], 'unofficial_text_fr')
        bilingual = json.loads(db.execute("SELECT evidence_json FROM edge_passages WHERE source_decision='SCC_2020scc2'").fetchone()[0])
        self.assertEqual(bilingual['corpus']['text_field'], 'unofficial_text_en')
        self.assertEqual(db.execute('SELECT COUNT(*) FROM edge_passages').fetchone()[0], 2)

    def test_legacy_manifest_never_reinterprets_french_only_rows(self):
        _, db = self.run_fixture(False)
        self.addCleanup(db.close)
        row = db.execute('SELECT * FROM documents WHERE corpus_row=1').fetchone()
        self.assertEqual((row['source_id'], row['citation'], row['name'], row['decision_date']), ('SCC_', '', '', ''))
        self.assertEqual(db.execute('SELECT COUNT(*) FROM edge_passages').fetchone()[0], 1)
        self.assertNotIn('français', db.execute("SELECT text FROM text_records WHERE collection='cases'").fetchone()[0])
        self.assertEqual(json.loads(db.execute('SELECT evidence_json FROM edge_passages').fetchone()[0])['corpus']['text_field'],
                         'unofficial_text_en')

    def test_raw_span_cannot_be_taken_from_another_language_field(self):
        with self.assertRaisesRegex(ValueError, 'text disagrees'):
            self.run_fixture(True, bad_raw=True)

    def test_cross_line_and_nbsp_fold_only_for_ledger_comparison(self):
        original = '2000\nSCC\u00a01'
        self.rewrite_original_quote(original)
        _, db = self.run_fixture(True)
        self.addCleanup(db.close)
        for table in ('edge_passages', 'profile_passages'):
            evidence_rows = db.execute('SELECT source_decision,evidence_json FROM '+table).fetchall()
            self.assertEqual(len(evidence_rows), 2)
            for row in evidence_rows:
                evidence = json.loads(row['evidence_json'])
                text = self.french if row['source_decision'] == 'SCC_2021csc3' else self.english
                self.assertEqual(text[evidence['match_start']:evidence['match_end']], original)
                self.assertEqual(evidence['match_end']-evidence['match_start'], len(original))
                self.assertGreaterEqual(evidence['window_end'], evidence['match_end'])

    def test_each_index_refuses_non_whitespace_change(self):
        self.rewrite_original_quote('2000 SCC 2')
        run, db = self.run_fixture(True, index=False)
        db.close()
        for indexer in (index_cases.build_profiles, index_edges.build_passages):
            with self.subTest(indexer=indexer.__module__):
                with self.assertRaisesRegex(ValueError, 'text disagrees'):
                    indexer(run, self.root / (run.name+'.db'))

    def test_each_index_refuses_out_of_bounds_span(self):
        run, db = self.run_fixture(True, index=False, end_delta=1000)
        db.close()
        for indexer in (index_cases.build_profiles, index_edges.build_passages):
            with self.subTest(indexer=indexer.__module__):
                with self.assertRaisesRegex(ValueError, 'offset outside'):
                    indexer(run, self.root / (run.name+'.db'))


if __name__ == '__main__':
    unittest.main()
