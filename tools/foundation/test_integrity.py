"""Publication and immutable-evidence regressions; all fixtures are offline and tiny."""
import contextlib
import csv
import gzip
import io
import json
import sqlite3
import subprocess
import struct
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import acceptance
import after_run
import build
import common
import embed
import index_cases
import index_edges
import index_methods
import query
import rewrite


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Capacity checks must measure the tiny fixture, independent of retained production runs.
        self.root_patch = patch.object(common, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.run = self.root/'run_fixture'
        self.run.mkdir()
        self.db_path = self.root/'research.db'
        self.corpus_dir = self.root/'immutable_corpus'
        self.corpus_dir.mkdir()
        self.corpus = self.corpus_dir/'SCC.parquet'
        self.corpus.write_bytes(b'sealed parquet fixture')
        self.text = 'A judgment applies Alpha v Beta, 2000 SCC 1 to the factual question.'
        self.source = 'SCC_2020scc2'
        self.member = dict(court='SCC', merge_key='mk', merged_group_id='g', canonical_string='2000 SCC 1',
            is_primary='true', distinct_decisions_count='1', case_name_modal='Alpha v Beta', year_printed='2000',
            kept='false', group_foreign_status='DOMESTIC_CA', group_origin_country='CA')
        self.csv('select_out/selected.csv', [self.member])
        self.csv('edges/citation_edges.csv', [dict(source_decision=self.source, resolved_cited_case='g', edge_support='supported')])
        self.csv('decide_out/cross_court/effective_sources.csv', [dict(source_decision=self.source, merged_group_id='g', status='counted')])
        self.csv('registry/decision_own_citations.csv', [dict(merge_key='other', decision_id=self.source)])
        self.csv('merge_out/SCC/mentions_candidates.csv', [dict(arbitration_status='counted', merge_key='mk',
            source_decision_citation=self.source, corpus_row_index='0', match_start_offset='19', match_end_offset='42')])
        (self.run/'select_out/manifest.json').write_text(json.dumps({'stats': {'groups_total': 1, 'rows_total': 1}}))
        manifest = {'status': 'complete', 'input_identity_verified_unchanged': True,
                    'params': {'courts': ['SCC'], 'corpus_dir': str(self.corpus_dir)},
                    'input_identity': {'fingerprint': 'fixture', 'files': {'corpus/SCC.parquet': common.digest(self.corpus)}}}
        (self.run/'run_manifest.json').write_text(json.dumps(manifest))
        parent = types.ModuleType('pyarrow')
        pq = types.ModuleType('pyarrow.parquet')
        parent.parquet = pq
        source_row = {'citation_en': '2020 SCC 2', 'name_en': 'Source judgment',
                      'document_date_en': '2020-01-01', 'unofficial_text_en': self.text}
        def batches(**kwargs):
            fields = kwargs['columns']
            data = {k: source_row[k] for k in fields}
            yield types.SimpleNamespace(to_pylist=lambda: [data], column=lambda _: types.SimpleNamespace(to_pylist=lambda: [source_row[fields[0]]]))
        self.seen_paths = []
        def parquet_file(path):
            self.seen_paths.append(str(path))
            return types.SimpleNamespace(iter_batches=batches)
        pq.ParquetFile = parquet_file
        self.modules = patch.dict('sys.modules', {'pyarrow': parent, 'pyarrow.parquet': pq})
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def csv(self, logical, values):
        path = self.run/logical
        path.parent.mkdir(parents=True, exist_ok=True)
        # Every run CSV is gzip, with no uncompressed companion.
        with gzip.open(str(path)+'.gz', 'wt', encoding='utf-8', newline='') as out:
            writer = csv.DictWriter(out, fieldnames=list(values[0]))
            writer.writeheader()
            writer.writerows(values)

    def methods(self, db_path):
        db = common.connect(db_path)
        with db:
            common.upsert_text(db, 'methods', 'fixture', 'all', 'method_card', 'Method fixture',
                               'Alpha keyword method fixture', 'fixture:1')
            common.rebuild_fts(db)
        db.close()
        return {'records': 1}

    def all(self, skip_acceptance=False):
        with patch.object(after_run.index_methods, 'build', side_effect=self.methods), \
             patch.object(after_run, 'method_sources', return_value={}), \
             patch.object(embed, '_key', side_effect=AssertionError('No API key may be read')), \
             patch.object(embed.urllib.request, 'urlopen', side_effect=AssertionError('No network')):
            return after_run.run_all(self.run, self.db_path, vectors='skip', skip_acceptance=skip_acceptance)

    def state(self):
        db = common.connect(self.db_path, readonly=True)
        try:
            run = db.execute('SELECT status FROM runs WHERE run_id=?', (self.run.name,)).fetchone()[0]
            states = {r['component']: r['status'] for r in db.execute('SELECT * FROM run_components')}
            return run, states
        finally:
            db.close()

    def test_gzip_reader_and_content_hash_are_lossless(self):
        path = self.run/'select_out/selected.csv'
        actual = common.resolve_artifact(path)
        logical = gzip.decompress(actual.read_bytes())
        self.assertEqual(common.artifact_digest(path), common.hashlib.sha256(logical).hexdigest())
        self.assertEqual(common.csv_fields(path), list(self.member))
        self.assertEqual(list(common.rows(path)), [self.member])
        self.assertNotEqual(common.digest(actual), common.artifact_digest(path))
        self.assertFalse(path.exists())

    def test_fixture_still_enforces_capacity_against_its_own_root(self):
        report = common.database_preflight(self.db_path)
        self.assertTrue(report['guarded'])
        self.assertEqual(Path(report['root']), self.root)
        self.assertEqual(report['max_project_bytes'], 12 * 1024 ** 3)
        with common.storage_limits(max_project_bytes=1):
            with self.assertRaisesRegex(ValueError, 'project peak exceeds'):
                common.database_preflight(self.db_path)

    def test_import_never_publishes_before_indexes(self):
        report = build.build(self.run, self.db_path)
        self.assertEqual(report['status'], 'building')
        self.assertEqual(self.state(), ('building', {'import': 'ready'}))
        db = common.connect(self.db_path)
        with self.assertRaisesRegex(ValueError, 'Cannot publish'):
            common.publish_run(db, self.run.name)
        db.close()

    def test_complete_offline_keyword_build_publishes_with_missing_vectors(self):
        report = self.all()
        self.assertEqual(report['status'], 'ready')
        self.assertTrue(report['acceptance']['published'])
        run, states = self.state()
        self.assertEqual(states['vectors_cases'], 'missing')
        self.assertEqual(states['vectors_edges'], 'missing')
        self.assertTrue(self.seen_paths)
        self.assertEqual(set(self.seen_paths), {str(self.corpus)})
        db = common.connect(self.db_path, readonly=True)
        try:
            edge = db.execute('SELECT evidence_json FROM edge_passages').fetchone()[0]
            ev = json.loads(edge)
            self.assertEqual(ev['corpus']['logical_path'], 'corpus/SCC.parquet')
            expanded = common.expand_evidence(db, self.run.name, edge)
            self.assertEqual(expanded['corpus']['path'], str(self.corpus))
            self.assertEqual(expanded['corpus']['sha256'], common.digest(self.corpus))
            source = db.execute('SELECT * FROM run_sources WHERE logical_path=?', (ev['mentions']['logical_path'],)).fetchone()
            self.assertEqual(source['sha256'], common.artifact_digest(self.run/'merge_out/SCC/mentions_candidates.csv'))
            self.assertEqual(ev['mention_record'], 2)
            self.assertEqual(ev['corpus_row'], 0)
            self.assertTrue(query.search(db, 'Alpha', 'cases', 2, 'keyword', run_id=self.run.name))
            with self.assertRaisesRegex(ValueError, 'Vector search is missing'):
                query.search(db, 'Alpha', 'cases', 2, 'vector', run_id=self.run.name)
        finally:
            db.close()

    def test_skip_acceptance_leaves_run_unpublished(self):
        report = self.all(skip_acceptance=True)
        self.assertEqual(report['status'], 'building')
        self.assertNotIn('acceptance', self.state()[1])

    def test_changed_corpus_fails_closed_and_keeps_existing_profiles(self):
        self.all()
        self.corpus.write_bytes(b'changed after import')
        with self.assertRaisesRegex(ValueError, 'snapshot mismatch'):
            index_cases.build_profiles(self.run, self.db_path)
        self.assertEqual(self.state()[0], 'building')
        self.assertEqual(self.state()[1]['cases'], 'failed')
        db = common.connect(self.db_path, readonly=True)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM text_records WHERE collection='cases'").fetchone()[0], 1)
        db.close()

    def test_changed_mentions_rejected_after_import(self):
        build.build(self.run, self.db_path)
        self.csv('merge_out/SCC/mentions_candidates.csv', [dict(arbitration_status='counted', merge_key='mk',
            source_decision_citation=self.source, corpus_row_index='0', match_start_offset='1', match_end_offset='2')])
        with self.assertRaisesRegex(ValueError, 'snapshot mismatch'):
            index_edges.build_passages(self.run, self.db_path)
        self.assertEqual(self.state()[1]['edges'], 'failed')

    def test_missing_mentions_prevents_publication(self):
        build.build(self.run, self.db_path)
        (self.run/'merge_out/SCC/mentions_candidates.csv.gz').unlink()
        with self.assertRaises(FileNotFoundError):
            index_cases.build_profiles(self.run, self.db_path)
        self.assertEqual(self.state()[0], 'building')
        self.assertEqual(self.state()[1]['cases'], 'failed')

    def test_source_id_offset_mismatch_cannot_supply_evidence(self):
        self.csv('merge_out/SCC/mentions_candidates.csv', [dict(arbitration_status='counted', merge_key='mk',
            source_decision_citation=self.source, corpus_row_index='7', match_start_offset='1', match_end_offset='2')])
        build.build(self.run, self.db_path)
        with self.assertRaisesRegex(ValueError, 'Mention locator'):
            index_cases.build_profiles(self.run, self.db_path)
        self.assertEqual(self.state()[1]['cases'], 'failed')

    def test_partial_embedding_failure_cannot_publish_vector_component(self):
        self.all()
        with patch.object(embed, 'embed_texts', return_value=([None], {'failed': 1, 'missing': 1})), \
             patch.object(embed, 'load_vec', side_effect=AssertionError('No index may be changed')):
            report = embed.index(['cases'], self.db_path, self.run.name)
        self.assertEqual(report['cases']['status'], 'failed')
        self.assertEqual(report['cases']['vectors_written'], 0)
        self.assertEqual(self.state()[1]['vectors_cases'], 'failed')
        self.assertEqual(self.state()[0], 'building')

    def test_vector_limit_cannot_be_marked_ready(self):
        self.all()
        db = common.connect(self.db_path)
        with db:
            db.execute("INSERT INTO edge_passages(run_id,source_decision,resolved_cited_case,passage) VALUES(?,?,?,?)",
                       (self.run.name, 'second', 'g', 'second passage'))
        db.close()
        with patch.object(index_edges, 'embed_texts', return_value=([b'x'*(512*4)], {'failed': 0})), \
             patch.object(index_edges, 'load_vec', side_effect=AssertionError('No partial index')):
            report = index_edges.embed_passages(self.run.name, self.db_path, limit=1)
        self.assertEqual(report['status'], 'stale')
        self.assertEqual(report['vectors_written'], 0)

    def test_acceptance_missing_passage_is_failed_not_ready(self):
        self.all()
        db = common.connect(self.db_path)
        with db:
            db.execute('DELETE FROM edge_passages')
        db.close()
        with self.assertRaisesRegex(ValueError, 'Incomplete edge evidence'):
            acceptance.accept_run(self.db_path, self.run.name)
        self.assertEqual(self.state()[0], 'building')
        self.assertEqual(self.state()[1]['acceptance'], 'failed')

    def test_benchmark_misses_have_nonzero_exit(self):
        self.all()
        with patch.object(acceptance, 'run', return_value=0), \
             patch('sys.argv', ['acceptance.py', '--suite', 'benchmark', '--db', str(self.db_path)]), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(acceptance.main(), 1)

    def test_offline_missing_embeddings_never_read_key_or_call_api(self):
        with patch.object(embed, '_key', side_effect=AssertionError('Key accessed')), \
             patch.object(embed.urllib.request, 'urlopen', side_effect=AssertionError('Network used')):
            vectors, stats = embed.embed_texts(['new unseen fixture'], cache_path=self.root/'cache.db')
        self.assertEqual(vectors, [None])
        self.assertEqual(stats['missing'], 1)
        self.assertFalse(stats['network_allowed'])

    def test_corrupt_embedding_cache_is_not_reused(self):
        path = self.root/'cache.db'
        cache = sqlite3.connect(path)
        cache.execute('CREATE TABLE emb(h TEXT,model TEXT,dim INTEGER,v BLOB,PRIMARY KEY(h,model,dim))')
        h = common.hashlib.sha256(embed.prepare('fixture').encode()).hexdigest()
        cache.execute('INSERT INTO emb VALUES(?,?,?,?)', (h, embed.MODEL, embed.DIM, b'bad'))
        cache.commit()
        cache.close()
        vectors, stats = embed.embed_texts(['fixture'], cache_path=path)
        self.assertEqual(vectors, [None])
        self.assertEqual(stats['missing'], 1)

    def test_offline_chinese_rewrite_does_not_contact_api(self):
        with patch.object(rewrite, 'CACHE', self.root/'rewrite.db'), \
             patch.object(rewrite.urllib.request, 'urlopen', side_effect=AssertionError('Network used')):
            self.assertEqual(rewrite.to_english('完全全新检索问题'), '')

    def test_long_method_heading_keeps_all_chunks_including_repeated_content(self):
        build.build(self.run, self.db_path)
        docs = self.root/'docs'
        docs.mkdir()
        (docs/'long.md').write_text('# Long heading\n' + ('repeated method content ' * 350), encoding='utf-8')
        expected = list(index_methods.md_chunks(docs/'long.md'))
        self.assertGreater(len(expected), 2)
        with patch.object(index_methods, 'ROOT', self.root), patch.object(index_methods, 'git_head', return_value='fixture'):
            report = index_methods.build(self.db_path)
        db = common.connect(self.db_path, readonly=True)
        actual = db.execute("SELECT COUNT(*) FROM text_records WHERE collection='methods'").fetchone()[0]
        db.close()
        self.assertEqual(actual, len(expected))
        self.assertEqual(report['records'], len(expected))

    def test_pipeline_subprocess_failure_stops_after_run(self):
        with patch('sys.argv', ['after_run.py', '--pipeline-out', str(self.root/'failed_run'),
                                '--db', str(self.db_path)]), \
             patch.object(after_run.subprocess, 'run', side_effect=subprocess.CalledProcessError(2, ['pipeline'])) as child, \
             patch.object(after_run, 'run_all') as downstream:
            with self.assertRaises(subprocess.CalledProcessError):
                after_run.main()
        self.assertTrue(child.call_args.kwargs['check'])
        downstream.assert_not_called()


if __name__ == '__main__':
    unittest.main()
