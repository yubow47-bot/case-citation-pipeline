"""Exact multi-run retention and transactional cache retirement fixtures."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tools.quality import cache_cleanup as cleanup


class CacheCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.quality-cache-cleanup-', dir=cleanup.ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.db_path, self.cache_path = self.root / 'formal.db', self.root / 'cache.db'
        self.receipt = self.root / 'receipt.json'
        db = sqlite3.connect(self.db_path)
        db.executescript('''CREATE TABLE runs(run_id TEXT,status TEXT,input_fingerprint TEXT,manifest_json TEXT);
        CREATE TABLE run_components(run_id TEXT,component TEXT,generation INTEGER,status TEXT);
        CREATE TABLE text_records(id INTEGER,run_id TEXT,collection TEXT,title TEXT,text TEXT);
        CREATE TABLE edge_passages(id INTEGER,run_id TEXT,passage TEXT);''')
        for rid in ('current', 'old'):
            db.execute('INSERT INTO runs VALUES(?,?,?,?)', (rid, 'ready', rid + '-input', json.dumps({'params': {}})))
            db.executemany('INSERT INTO run_components VALUES(?,?,?,?)',
                           [(rid, component, 1, 'ready') for component in cleanup.REQUIRED_COMPONENTS])
            # Missing/stale vectors do not remove the value of future offline cache reuse.
            db.execute('INSERT INTO run_components VALUES(?,?,?,?)', (rid, 'vectors_cases', 1, 'missing'))
        db.executemany('INSERT INTO text_records VALUES(?,?,?,?,?)', [
            (1, 'current', 'cases', 'Current', 'body'),
            (2, 'old', 'cases', 'Historical', 'body'),
            (3, 'unbound-shared', 'methods', 'Shared method', 'guide'),
            (4, 'current', 'cases', 'Current invalid', 'body')])
        db.executemany('INSERT INTO edge_passages VALUES(?,?,?)',
                       [(1, 'current', 'current passage'), (2, 'old', 'old passage')])
        db.commit()
        db.close()
        self.contract = cleanup.embedding_contract()
        self.model, self.dim, self.edge_dim = (self.contract[k] for k in ('model', 'text_dim', 'edge_dim'))
        cache = sqlite3.connect(self.cache_path)
        cache.execute('CREATE TABLE emb(h TEXT,model TEXT,dim INTEGER,v BLOB,PRIMARY KEY(h,model,dim))')
        self.insert(cache, 'Current\nbody', self.dim)
        self.insert(cache, 'Historical\nbody', self.dim)
        self.insert(cache, 'Shared method\nguide', self.dim)
        self.insert(cache, 'Current invalid\nbody', self.dim, size=4)
        self.insert(cache, 'current passage', self.edge_dim)
        self.insert(cache, 'old passage', self.edge_dim)
        self.insert(cache, 'user paid query without record ref', self.dim)
        self.insert(cache, 'Current\nbody', self.dim, model='retired-model')
        for n in range(40):
            self.insert(cache, 'retired input ' + str(n), self.dim, size=8000)
        cache.commit()
        cache.close()
        self.source_patch = mock.patch.object(cleanup, 'open_source', side_effect=self.source)
        self.source_patch.start()
        self.addCleanup(self.source_patch.stop)
        self.budget_patch = mock.patch.object(cleanup, 'preflight', return_value={'allowed': True, 'fixture': True})
        self.budget_mock = self.budget_patch.start()
        self.addCleanup(self.budget_patch.stop)

    def source(self, **kwargs):
        db = sqlite3.connect(self.db_path.as_uri() + '?mode=ro', uri=True)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        rid = kwargs['run_id']
        return SimpleNamespace(db=db, run_id=rid, run_dir=self.root / ('run_' + rid), close=db.close)

    def insert(self, cache, text, dim, size=None, model=None):
        h = hashlib.sha256(self.contract['prepare'](text).encode()).hexdigest()
        cache.execute('INSERT INTO emb VALUES(?,?,?,?)',
                      (h, model or self.model, dim, bytes(size if size is not None else dim * 4)))
        return h

    def preview(self):
        return cleanup.preview(self.db_path, self.cache_path, 'current')

    def apply(self, plan):
        return cleanup.apply_plan(self.db_path, self.cache_path, 'current', plan, self.receipt)

    def execute_source(self, sql):
        db = sqlite3.connect(self.db_path)
        db.execute(sql)
        db.commit()
        db.close()

    def test_dry_run_is_byte_identical_and_retains_current_methods_and_ready_history(self):
        before = self.cache_path.read_bytes()
        plan = self.preview()
        self.assertEqual(self.cache_path.read_bytes(), before)
        self.assertEqual(plan['current_rows'], 4)
        self.assertEqual(plan['historical_ready_only_rows'], 2)
        self.assertEqual(plan['referenced_invalid_shape_rows'], 1)
        self.assertEqual(plan['unreferenced_rows'], 42)
        self.assertEqual(plan['retained_rows'], 6)
        self.assertIn('paid query', plan['query_history_tradeoff'])
        self.assertEqual(sorted(p.name for p in self.root.glob('*.db')), ['cache.db', 'formal.db'])

    def test_explicit_apply_keeps_exact_refs_and_shrinks_only_cache_db(self):
        source_before = self.db_path.read_bytes()
        plan = self.preview()
        report = self.apply(plan)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['deleted_rows'], 42)
        self.assertEqual(report['after_counts']['cache_rows'], 6)
        self.assertEqual(report['after_counts']['referenced_invalid_shape_rows'], 1)
        self.assertGreater(report['main_file_length_reduction_bytes'], 0)
        self.assertEqual(self.db_path.read_bytes(), source_before)
        self.assertEqual(json.loads(self.receipt.read_text(encoding='utf-8'))['status'], 'complete')
        self.assertEqual(sorted(p.name for p in self.root.glob('*.db')), ['cache.db', 'formal.db'])
        self.budget_mock.assert_called_once_with(cleanup.ROOT, 2 * plan['cache_state']['main']['bytes'] + 64 * 1024**2,
                                                max_project_bytes=12 * cleanup.GiB)

    def test_db_building_keyword_stale_or_vector_building_refuses(self):
        for sql in ("UPDATE runs SET status='building' WHERE run_id='old'",
                    "UPDATE run_components SET status='stale' WHERE run_id='old' AND component='cases'",
                    "UPDATE run_components SET status='building' WHERE run_id='old' AND component='vectors_cases'"):
            before = self.cache_path.read_bytes()
            self.execute_source(sql)
            with self.assertRaises(ValueError):
                self.preview()
            self.assertEqual(self.cache_path.read_bytes(), before)
            self.execute_source("UPDATE runs SET status='ready';")
            self.execute_source("UPDATE run_components SET status='ready'")

    def test_unbound_nonmethod_input_refuses_unknown_retention(self):
        self.execute_source("INSERT INTO text_records VALUES(9,'unknown','cases','Unknown','body')")
        with self.assertRaisesRegex(ValueError, 'unbound'):
            self.preview()

    def test_formal_input_change_after_preview_refuses_before_delete(self):
        plan = self.preview()
        before = self.cache_path.read_bytes()
        self.execute_source("UPDATE text_records SET text='new input' WHERE id=1")
        with self.assertRaisesRegex(ValueError, 'Inputs changed'):
            self.apply(plan)
        self.assertEqual(self.cache_path.read_bytes(), before)

    def test_same_shape_cache_blob_change_after_preview_is_detected_by_file_sha(self):
        plan = self.preview()
        cache = sqlite3.connect(self.cache_path)
        cache.execute('UPDATE emb SET v=? WHERE model=? AND dim=?', (b'x' * self.dim * 4, self.model, self.dim))
        cache.commit()
        cache.close()
        changed = self.cache_path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Cache changed'):
            self.apply(plan)
        self.assertEqual(self.cache_path.read_bytes(), changed)

    def test_exclusive_lock_never_reads_raw_file_even_above_windows_lock_byte(self):
        """Simulate the denied raw read at 1 GiB without creating a huge fixture."""
        plan = self.preview()
        original_connect, original_file_state = cleanup._connect, cleanup._file_state
        state = {'exclusive': False, 'raw_reads_after_close': 0}
        class LockedConnection:
            def __init__(self, db): self.db = db
            def __getattr__(self, name): return getattr(self.db, name)
            def execute(self, sql, *args):
                result = self.db.execute(sql, *args)
                if sql == 'BEGIN EXCLUSIVE': state['exclusive'] = True
                return result
            def close(self):
                self.db.close()
                state['exclusive'] = False
        def connect(path, readonly=True):
            db = original_connect(path, readonly)
            return db if readonly else LockedConnection(db)
        def file_state(path):
            if Path(path) == self.cache_path:
                if state['exclusive']:
                    raise PermissionError(13, 'Windows lock-byte page raw read denied')
                state['raw_reads_after_close'] += 1
            return original_file_state(path)
        with mock.patch.object(cleanup, '_connect', side_effect=connect), \
             mock.patch.object(cleanup, '_file_state', side_effect=file_state):
            report = self.apply(plan)
        self.assertEqual(report['status'], 'complete')
        self.assertFalse(state['exclusive'])
        self.assertGreaterEqual(state['raw_reads_after_close'], 2)

    def test_same_length_payload_race_after_file_check_is_rejected_under_sql_lock(self):
        plan = self.preview()
        original_connect = cleanup._connect
        target = hashlib.sha256(self.contract['prepare']('retired input 0').encode()).hexdigest()
        def connect(path, readonly=True):
            if not readonly:
                other = sqlite3.connect(self.cache_path)
                old_size = other.execute('SELECT LENGTH(v) FROM emb WHERE h=?', (target,)).fetchone()[0]
                other.execute('UPDATE emb SET v=? WHERE h=?', (b'x' * old_size, target))
                other.commit()
                other.close()
            return original_connect(path, readonly)
        with mock.patch.object(cleanup, '_connect', side_effect=connect), \
             self.assertRaisesRegex(ValueError, 'Cache contents changed'):
            self.apply(plan)
        cache = sqlite3.connect(self.cache_path)
        scan = cleanup._scan_cache(cache, cleanup._retention(self.db_path, 'current'))
        self.assertEqual(cache.execute('SELECT COUNT(*) FROM emb').fetchone()[0], 48)
        self.assertEqual(scan['metadata_sha256'], plan['cache_metadata_sha256'])
        self.assertNotEqual(scan['content_sha256'], plan['cache_content_sha256'])
        self.assertEqual(cache.execute('SELECT v FROM emb WHERE h=?', (target,)).fetchone()[0], b'x' * 8000)
        cache.close()
        self.assertEqual(json.loads(self.receipt.read_text(encoding='utf-8'))['status'], 'aborted_delete_rolled_back')

    def test_vacuum_rowid_renumbering_preserves_logical_payload_fingerprint(self):
        cache = sqlite3.connect(self.cache_path)
        target = hashlib.sha256(self.contract['prepare']('Current\nbody').encode()).hexdigest()
        cache.execute('UPDATE emb SET rowid=10000 WHERE h=? AND model=?', (target, self.model))
        cache.commit()
        cache.close()
        plan = self.preview()
        original_connect = cleanup._connect
        class RenumberingVacuumConnection:
            def __init__(self, db): self.db = db
            def __getattr__(self, name): return getattr(self.db, name)
            def execute(self, sql, *args):
                result = self.db.execute(sql, *args)
                if sql == 'VACUUM':
                    # SQLite versions may preserve these particular rowids.
                    # Exercise the documented allowance to change them while
                    # keeping every actual key and BLOB byte intact.
                    self.db.execute('UPDATE emb SET rowid=-rowid')
                    self.db.commit()
                return result
        def connect(path, readonly=True):
            db = original_connect(path, readonly)
            return db if readonly else RenumberingVacuumConnection(db)
        with mock.patch.object(cleanup, '_connect', side_effect=connect):
            report = self.apply(plan)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['after_retained_payload_sha256'], plan['retained_payload_sha256'])
        self.assertNotEqual(report['after_cache_content_sha256'], plan['retained_cache_content_sha256'])

    def test_sql_payload_reader_uses_bounded_chunks(self):
        cache = sqlite3.connect(self.cache_path)
        self.insert(cache, 'large malformed historical vector', self.dim, size=3 * cleanup.PAYLOAD_BLOCK_BYTES + 7)
        cache.commit()
        reads = []
        class BlobReader:
            def __init__(self, blob): self.blob = blob
            def __len__(self): return len(self.blob)
            def __enter__(self): return self
            def __exit__(self, *args): self.blob.close()
            def read(self, size):
                reads.append(size)
                return self.blob.read(size)
        class Connection:
            def __getattr__(self, name): return getattr(cache, name)
            def blobopen(self, *args, **kwargs):
                return BlobReader(cache.blobopen(*args, **kwargs))
        scan = cleanup._scan_cache(Connection(), {'current': set(), 'all_ready': set()})
        cache.close()
        self.assertEqual(scan['totals']['cache_rows'], 49)
        self.assertTrue(reads)
        self.assertLessEqual(max(reads), 64 * 1024)
        self.assertEqual(len(scan['content_sha256']), 64)

    def test_v1_plan_is_not_reused_after_payload_protocol_upgrade(self):
        plan = self.preview()
        old = {**plan, 'schema': 'embedding_cache_cleanup_plan_v1'}
        old['plan_hash'] = cleanup.canonical_hash({k: v for k, v in old.items() if k != 'plan_hash'})
        before = self.cache_path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'fresh v2'):
            self.apply(old)
        self.assertEqual(self.cache_path.read_bytes(), before)

    def test_input_change_during_delete_rolls_back_all_deleted_rows(self):
        plan = self.preview()
        original = cleanup._verify_retention
        calls = 0
        def verify(db_path, current_run, expected):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.execute_source("UPDATE text_records SET title='changed during delete' WHERE id=1")
            return original(db_path, current_run, expected)
        with mock.patch.object(cleanup, '_verify_retention', side_effect=verify), \
             self.assertRaisesRegex(ValueError, 'Inputs changed'):
            self.apply(plan)
        cache = sqlite3.connect(self.cache_path)
        self.assertEqual(cache.execute('SELECT COUNT(*) FROM emb').fetchone()[0], 48)
        cache.close()
        self.assertEqual(json.loads(self.receipt.read_text(encoding='utf-8'))['status'], 'aborted_delete_rolled_back')

    def test_missing_or_tampered_plan_and_source_output_overwrite_refuse(self):
        plan = self.preview()
        changed = dict(plan, unreferenced_rows=0)
        with self.assertRaisesRegex(ValueError, 'plan hash'):
            self.apply(changed)
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            cleanup.apply_plan(self.db_path, self.cache_path, 'current', plan, self.cache_path)
        with self.assertRaisesRegex(ValueError, 'source run'):
            cleanup.apply_plan(self.db_path, self.cache_path, 'current', plan, self.root / 'run_old/output.json')

    def test_vacuum_failure_reports_committed_delete_without_claiming_rollback(self):
        plan = self.preview()
        original = cleanup._connect
        class FaultConnection:
            def __init__(self, db): self.db = db
            def __getattr__(self, name): return getattr(self.db, name)
            def execute(self, sql, *args):
                if sql == 'VACUUM': raise sqlite3.OperationalError('fixture vacuum failure')
                return self.db.execute(sql, *args)
        def connect(path, readonly=True):
            db = original(path, readonly)
            return db if readonly else FaultConnection(db)
        with mock.patch.object(cleanup, '_connect', side_effect=connect), self.assertRaises(cleanup.CleanupCommittedError):
            self.apply(plan)
        report = json.loads(self.receipt.read_text(encoding='utf-8'))
        self.assertEqual(report['status'], 'delete_committed_vacuum_or_verification_failed')
        self.assertEqual(report['deleted_rows'], 42)
        cache = sqlite3.connect(self.cache_path)
        self.assertEqual(cache.execute('SELECT COUNT(*) FROM emb').fetchone()[0], 6)
        cache.close()

    def test_committed_failure_closes_exclusive_connection_before_physical_sha(self):
        plan = self.preview()
        original_connect, original_file_state = cleanup._connect, cleanup._file_state
        state = {'exclusive': False}
        class LockedFaultConnection:
            def __init__(self, db): self.db = db
            def __getattr__(self, name): return getattr(self.db, name)
            def execute(self, sql, *args):
                if sql == 'VACUUM': raise sqlite3.OperationalError('fixture vacuum failure')
                result = self.db.execute(sql, *args)
                if sql == 'BEGIN EXCLUSIVE': state['exclusive'] = True
                return result
            def close(self):
                self.db.close()
                state['exclusive'] = False
        def connect(path, readonly=True):
            db = original_connect(path, readonly)
            return db if readonly else LockedFaultConnection(db)
        def file_state(path):
            if Path(path) == self.cache_path and state['exclusive']:
                raise PermissionError(13, 'Windows lock-byte page raw read denied')
            return original_file_state(path)
        with mock.patch.object(cleanup, '_connect', side_effect=connect), \
             mock.patch.object(cleanup, '_file_state', side_effect=file_state), \
             self.assertRaises(cleanup.CleanupCommittedError):
            self.apply(plan)
        report = json.loads(self.receipt.read_text(encoding='utf-8'))
        self.assertEqual(report['status'], 'delete_committed_vacuum_or_verification_failed')
        self.assertIn('after_cache_state', report)
        self.assertFalse(state['exclusive'])

    def test_post_close_physical_hash_failure_reports_committed_delete(self):
        plan = self.preview()
        original = cleanup._cache_state
        calls = 0
        def cache_state(path):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise PermissionError(13, 'fixture post-close physical access denied')
            return original(path)
        with mock.patch.object(cleanup, '_cache_state', side_effect=cache_state), \
             self.assertRaises(cleanup.CleanupCommittedError):
            self.apply(plan)
        report = json.loads(self.receipt.read_text(encoding='utf-8'))
        self.assertEqual(report['status'], 'delete_committed_vacuum_or_verification_failed')
        self.assertEqual(report['deleted_rows'], 42)
        self.assertIn('post-close physical access', report['error'])
        self.assertNotIn('after_cache_state', report)


if __name__ == '__main__':
    unittest.main()
