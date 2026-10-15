"""Cache reuse decisions honor run, model/dimension, and actual input text."""
import hashlib
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tools.quality import cache_audit


class CacheAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.quality-cache-test-', dir=cache_audit.ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.executescript('CREATE TABLE text_records(id INTEGER,run_id TEXT,collection TEXT,title TEXT,text TEXT);'
                              'CREATE TABLE edge_passages(id INTEGER,run_id TEXT,passage TEXT);')
        self.db.executemany('INSERT INTO text_records VALUES(?,?,?,?,?)', [
            (1, 'current', 'cases', 'Current', 'body'),
            (2, 'old', 'cases', 'Historical', 'old body'),
            (3, 'old', 'methods', 'Shared method', 'guide'),
            (4, 'current', 'cases', 'Shape invalid', 'body')])
        self.db.executemany('INSERT INTO edge_passages VALUES(?,?,?)',
                            [(1, 'current', 'current edge passage'), (2, 'old', 'old edge passage')])
        self.contract = cache_audit.embedding_contract()
        self.cache_path = self.root / 'fixture_cache.db'
        cache = sqlite3.connect(self.cache_path)
        cache.execute('CREATE TABLE emb(h TEXT,model TEXT,dim INTEGER,v BLOB,PRIMARY KEY(h,model,dim))')
        model, dim, edge_dim = self.contract['model'], self.contract['text_dim'], self.contract['edge_dim']
        def insert(text, size_dim, size=None, use_model=model):
            h = hashlib.sha256(self.contract['prepare'](text).encode()).hexdigest()
            cache.execute('INSERT INTO emb VALUES(?,?,?,?)', (h, use_model, size_dim,
                           bytes(size if size is not None else size_dim * 4)))
        insert('Current\nbody', dim)
        insert('Historical\nold body', dim)
        insert('Shared method\nguide', dim)
        insert('Shape invalid\nbody', dim, size=4)
        insert('Current\nbody', dim, use_model='historical-other-model')
        insert('current edge passage', edge_dim)
        insert('title\ncurrent edge passage', edge_dim)
        insert('old edge passage', edge_dim)
        cache.commit()
        cache.close()
        self.source = SimpleNamespace(db=self.db, run_id='current', run_dir=self.root / 'run_current',
            manifest={'input_identity': {'fingerprint': 'synthetic-current'}, 'params': {}}, close=lambda: None)

    def audit(self):
        with mock.patch.object(cache_audit, 'open_source', return_value=self.source):
            return cache_audit.audit_cache(self.root / 'formal_not_copied.db', self.cache_path, 'current')

    def test_other_run_cases_and_edges_do_not_count_as_current_hits(self):
        result = self.audit()
        self.assertEqual(result['embedding_input_counts']['text_records/cases'], 2)
        self.assertEqual(result['embedding_input_counts']['text_records/methods'], 1)
        self.assertEqual(result['embedding_input_counts']['edge_passages'], 1)
        self.assertEqual(result['matched_current_payload_bytes'], self.contract['text_dim'] * 8 + self.contract['edge_dim'] * 4)
        self.assertEqual(result['unreferenced_payload_bytes'], self.contract['text_dim'] * 8 + self.contract['edge_dim'] * 8)

    def test_edges_use_passage_alone_at_actual_edge_dimension(self):
        result = self.audit()
        edge = next(r for r in result['model_dimensions']
                    if r['model'] == self.contract['model'] and r['dim'] == self.contract['edge_dim'])
        self.assertEqual(edge['current_unique_input_hashes'], 1)
        self.assertEqual(edge['matched_current_rows'], 1)
        self.assertEqual(edge['unreferenced_rows'], 2)

    def test_shape_invalid_current_reference_is_not_called_unreferenced_history(self):
        result = self.audit()
        cases = next(r for r in result['model_dimensions']
                     if r['model'] == self.contract['model'] and r['dim'] == self.contract['text_dim'])
        self.assertEqual(cases['referenced_current_invalid_shape_rows'], 1)
        self.assertEqual(cases['referenced_current_invalid_shape_bytes'], 4)
        self.assertEqual(cases['current_cache_misses'], 1)
        self.assertEqual(cases['unreferenced_rows'], 1)

    def test_audit_leaves_cache_bytes_identical_and_creates_no_db_copy(self):
        before = self.cache_path.read_bytes()
        self.audit()
        self.assertEqual(self.cache_path.read_bytes(), before)
        self.assertEqual(list(self.root.glob('*.db')), [self.cache_path])


if __name__ == '__main__':
    unittest.main()
