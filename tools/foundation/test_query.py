"""Offline retrieval regressions: synthetic runs, no corpus, API calls or live database.

    python -m unittest discover -s tools/foundation -p test_query.py -v

FTS tests require only Python's SQLite. Vector tests also exercise sqlite-vec when installed.
"""
import argparse
import contextlib
import io
import sqlite3
import struct
import unittest
from unittest.mock import patch

import common
import query


def vector(dim, first=1.0, second=0.0):
    return struct.pack('%df' % dim, first, second, *([0.0] * (dim - 2)))


class RetrievalIsolationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript(common.SCHEMA)
        for run, date in [('old', '2025-01-01'), ('new', '2026-01-01')]:
            self.db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',
                            (run, run, 'fingerprint', '{}', date, 'ready'))
            for name in ('cases', 'methods', 'edges', 'vectors_cases', 'vectors_methods', 'vectors_edges'):
                self.db.execute('INSERT INTO run_components VALUES(?,?,?,?,?,?,?)',
                                (run, name, 1, 'ready', 'fixture', '{}', date))
        self.db.executescript('''
            CREATE TABLE edge_passages(id INTEGER PRIMARY KEY, run_id TEXT NOT NULL,
                source_decision TEXT NOT NULL, resolved_cited_case TEXT NOT NULL, passage TEXT NOT NULL);
            CREATE TABLE edge_relations(run_id TEXT NOT NULL, source_decision TEXT NOT NULL,
                resolved_cited_case TEXT NOT NULL, relation_type TEXT NOT NULL);
            CREATE VIRTUAL TABLE edge_fts USING fts5(passage, content='edge_passages',
                content_rowid='id', tokenize='trigram');
        ''')
        self.addCleanup(self.db.close)

    def case(self, run, gid, dd=5, origin='FOREIGN', layer='results', text='alpha'):
        self.db.execute('INSERT INTO case_groups VALUES(?,?,?,?,?,?,?,?,?)',
                        (run, gid, dd, gid, 2, '2000', int(dd >= 5), origin, 'GB'))
        common.upsert_text(self.db, 'cases', run + '/' + gid, layer, 'experimental',
                           gid, text, run + '/selected.csv:record=2', run)
        return self.db.execute('SELECT id FROM text_records WHERE entity_key=?',
                               (run + '/' + gid,)).fetchone()[0]

    def method(self, name, layer='classification'):
        common.upsert_text(self.db, 'methods', name, layer, 'reference', name,
                           'alpha', name + ':1')
        return self.db.execute('SELECT id FROM text_records WHERE entity_key=?', (name,)).fetchone()[0]

    def edge(self, run, src, passage='alpha', date='2025-01-01', relation='other_judgment', gid='g'):
        rid = self.db.execute('INSERT INTO edge_passages(run_id,source_decision,resolved_cited_case,passage) '
                              'VALUES(?,?,?,?)', (run, src, gid, passage)).lastrowid
        self.db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)',
                        (run, src.split('_')[0], rid, src, '', src, date, 'corpus.parquet'))
        self.db.execute('INSERT INTO edge_relations VALUES(?,?,?,?)', (run, src, gid, relation))
        return rid

    def rebuild(self):
        common.rebuild_fts(self.db)
        self.db.execute("INSERT INTO edge_fts(edge_fts) VALUES('rebuild')")

    def args(self, **overrides):
        values = dict(cited=None, cited_name=None, court=None, year_from=None,
                      year_to=None, relation=None, mode='keyword', k=1)
        values.update(overrides)
        return argparse.Namespace(**values)

    def load_vectors(self, table, dim, rows):
        try:
            query.load_vec(self.db)
        except ImportError:
            self.skipTest('sqlite-vec is optional for offline keyword tests')
        self.db.execute('CREATE VIRTUAL TABLE %s USING vec0(embedding float[%d] distance_metric=cosine)' % (table, dim))
        self.db.executemany('INSERT INTO %s(rowid,embedding) VALUES(?,?)' % table, rows)
        self.db.execute('CREATE TABLE IF NOT EXISTS vec_meta(name TEXT PRIMARY KEY,value TEXT)')
        for key, value in [('model', query.MODEL), ('dim', str(query.DIM)), ('edge_model', query.MODEL), ('edge_dim', str(query.EDGE_DIM))]:
            self.db.execute('INSERT OR REPLACE INTO vec_meta VALUES(?,?)', (key, value))
        self.db.execute('CREATE TABLE IF NOT EXISTS vector_records(collection TEXT,record_id INTEGER,content_hash TEXT,PRIMARY KEY(collection,record_id))')
        col = table.removeprefix('vec_')
        for rid, _ in rows:
            if col == 'edges':
                text = self.db.execute('SELECT passage FROM edge_passages WHERE id=?', (rid,)).fetchone()[0]
                sha = common.hashlib.sha256(text.encode()).hexdigest()
            else:
                sha = self.db.execute('SELECT content_hash FROM text_records WHERE id=?', (rid,)).fetchone()[0]
            self.db.execute('INSERT OR REPLACE INTO vector_records VALUES(?,?,?)', (col, rid, sha))

    def test_cases_scope_run_before_keyword_limit(self):
        for i in range(20):
            self.case('old', 'old%d' % i)
        target = self.case('new', 'target')
        self.rebuild()
        hits = query.search(self.db, 'alpha', 'cases', 1, 'keyword', run_id='new')
        self.assertEqual([r['id'] for _, r in hits], [target])
        self.assertTrue(all(r['run_id'] == 'new' for _, r in query.search(self.db, 'alpha', 'cases', 1, 'keyword')))
        old = query.search(self.db, 'alpha', 'cases', 1, 'keyword', run_id='old')
        self.assertTrue(old)
        self.assertTrue(all(r['run_id'] == 'old' for _, r in old))

    def test_cases_filters_before_keyword_limit(self):
        for i in range(20):
            self.case('new', 'small%d' % i, dd=1)
            self.case('new', 'domestic%d' % i, origin='DOMESTIC_CA')
            self.case('new', 'layer%d' % i, layer='other')
        target = self.case('new', 'target')
        self.rebuild()
        hits = query.search(self.db, 'alpha', 'cases', 1, 'keyword', layer='results',
                            run_id='new', min_dd=5, origin='FOREIGN')
        self.assertEqual([r['id'] for _, r in hits], [target])

    def test_hybrid_missing_vectors_falls_back_explicitly_without_api(self):
        target = self.case('new', 'target')
        self.rebuild()
        self.db.execute("UPDATE run_components SET status='missing' WHERE component='vectors_cases' AND run_id='new'")
        messages = io.StringIO()
        with contextlib.redirect_stderr(messages), patch.object(query, 'embed_texts', side_effect=AssertionError('No API/cache embedding call')):
            hits = query.search(self.db, 'alpha', 'cases', 1, 'hybrid', run_id='new')
        self.assertEqual([r['id'] for _, r in hits], [target])
        self.assertIn('keyword mode', messages.getvalue())
        self.assertIn('missing', messages.getvalue())

    def test_chinese_cache_miss_explains_limited_offline_scope(self):
        args = argparse.Namespace(run='new', collection='cases', k=1, mode='keyword', layer=None,
                                  min_dd=None, origin=None, allow_network=False)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.object(query, 'to_english', return_value=''), \
             patch.object(query, 'search', return_value=[]):
            query.run_query(self.db, args, '没有缓存的中文研究问题')
        self.assertIn('离线中文改写缓存未命中', output.getvalue())
        self.assertIn('英文法律术语', output.getvalue())

    def test_methods_scope_collection_and_layer_before_keyword_limit(self):
        for i in range(20):
            self.case('old', 'old%d' % i)
            self.method('unrelated%d' % i, layer='extraction')
        target = self.method('target')
        self.rebuild()
        hits = query.search(self.db, 'alpha', 'methods', 1, 'keyword', layer='classification', run_id='new')
        self.assertEqual([r['id'] for _, r in hits], [target])
        self.assertIsNone(hits[0][1]['run_id'])

    def test_edges_scope_run_before_keyword_limit(self):
        old = [self.edge('old', 'SCC_old%d' % i) for i in range(20)]
        target = self.edge('new', 'SCC_new')
        self.rebuild()
        self.assertEqual(query.search_edges(self.db, 'new', 'alpha', self.args()), [(target, 1 / 60)])
        self.assertIn(query.search_edges(self.db, 'old', 'alpha', self.args())[0][0], old)

    def test_edges_old_run_passage_cannot_be_reported_for_new_run(self):
        old = self.edge('old', 'SCC_shared', passage='alpha old evidence')
        self.edge('new', 'SCC_shared', passage='beta current evidence')
        self.rebuild()
        self.assertEqual(query.search_edges(self.db, 'new', 'alpha', self.args()), [])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            query.show_edges(self.db, 'new', [(old, 1.0)])
        self.assertNotIn('old evidence', output.getvalue())

    def test_edges_research_filters_before_keyword_limit(self):
        for i in range(70):
            self.edge('old', 'BCCA_old%d' % i)
            self.edge('new', 'SCC_wrongcourt%d' % i)
            self.edge('new', 'BCCA_oldyear%d' % i, date='2010-01-01')
            self.edge('new', 'BCCA_history%d' % i, relation='same_case_history')
            self.edge('new', 'BCCA_wrongcase%d' % i, gid='other')
        target = self.edge('new', 'BCCA_target')
        self.rebuild()
        a = self.args(cited='g', court='BCCA', year_from=2020, year_to=2026, relation='other_judgment')
        self.assertEqual([rid for rid, _ in query.search_edges(self.db, 'new', 'alpha', a)], [target])

    def test_edge_keyword_search_does_not_need_relations_table(self):
        target = self.edge('new', 'BCCA_target')
        self.rebuild()
        self.db.execute('DROP TABLE edge_relations')
        self.assertEqual([rid for rid, _ in query.search_edges(self.db, 'new', 'alpha', self.args())], [target])
        self.assertEqual(query.search_edges(self.db, 'new', 'alpha', self.args(relation='other_judgment')), [])

    def test_cases_run_and_filters_before_vector_and_hybrid_k(self):
        rows = []
        for i in range(20):
            rows.append((self.case('old', 'old%d' % i), vector(1024)))
            rows.append((self.case('new', 'small%d' % i, dd=1), vector(1024)))
            rows.append((self.case('new', 'domestic%d' % i, origin='DOMESTIC_CA'), vector(1024)))
        target = self.case('new', 'target')
        rows.append((target, vector(1024, 0.8, 0.6)))
        self.rebuild()
        self.load_vectors('vec_cases', 1024, rows)
        with patch.object(query, 'embed_texts', return_value=([vector(1024)], {})):
            for mode in ('vector', 'hybrid'):
                with self.subTest(mode=mode):
                    hits = query.search(self.db, 'alpha', 'cases', 1, mode, run_id='new', min_dd=5, origin='FOREIGN')
                    self.assertEqual([r['id'] for _, r in hits], [target])

    def test_edges_run_and_filters_before_vector_and_hybrid_k(self):
        rows = []
        for i in range(20):
            rows.append((self.edge('old', 'BCCA_old%d' % i), vector(512)))
            rows.append((self.edge('new', 'SCC_other%d' % i), vector(512)))
        target = self.edge('new', 'BCCA_target')
        rows.append((target, vector(512, 0.8, 0.6)))
        self.rebuild()
        self.load_vectors('vec_edges', 512, rows)
        with patch.object(query, 'embed_texts', return_value=([vector(512)], {})):
            for mode in ('vector', 'hybrid'):
                with self.subTest(mode=mode):
                    a = self.args(mode=mode)
                    ids = [rid for rid, _ in query.search_edges(self.db, 'new', 'alpha', a)]
                    self.assertNotIn(rows[0][0], ids)
                    self.assertTrue(all(self.db.execute('SELECT run_id FROM edge_passages WHERE id=?', (rid,)).fetchone()[0] == 'new'
                                        for rid in ids))
                    a.court = 'BCCA'
                    self.assertEqual([rid for rid, _ in query.search_edges(self.db, 'new', 'alpha', a)], [target])

    def test_method_vectors_keep_project_scope(self):
        target = self.method('target')
        self.load_vectors('vec_methods', 1024, [(target, vector(1024))])
        with patch.object(query, 'embed_texts', return_value=([vector(1024)], {})):
            hits = query.search(self.db, 'alpha', 'methods', 1, 'vector', run_id='new')
        self.assertEqual([r['id'] for _, r in hits], [target])
        self.assertIsNone(hits[0][1]['run_id'])


if __name__ == '__main__':
    unittest.main()
