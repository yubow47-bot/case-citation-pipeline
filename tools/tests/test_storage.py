"""Storage-budget and data-loss regression checks, using disposable fixtures."""
import contextlib
import errno
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        # Windows' redirected AppContainer temp can allow writes yet reject
        # atomic rename. Use the writable checkout, matching real run storage.
        self.temporary = tempfile.TemporaryDirectory(prefix='.storage-test-',
                                                       dir=Path(__file__).resolve().parents[2])
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'data').mkdir()
        self.run = self.root / 'data/run_fixture'
        self.run.mkdir()
        self.manifest('complete')

    def manifest(self, status):
        path = self.run / 'run_manifest.json'
        path.write_text(json.dumps({'status': status, 'input_identity': {'fingerprint': 'fixture'}}), encoding='utf-8')
        return path.read_bytes()

    def csv(self, data=b'name,number\n' + b'Example,123\n' * 4000):
        path = self.run / 'nested/table.csv'
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        return path

    def test_inventory_excludes_reparse_subtree(self):
        outside = self.root / 'linked'
        outside.mkdir()
        (outside / 'large.bin').write_bytes(b'x' * 10000)
        plain = self.root / 'normal.txt'
        plain.write_bytes(b'hello')
        real_link = storage._link
        with mock.patch.object(storage, '_link', side_effect=lambda p, s=None: p == outside or real_link(p, s)):
            result = storage.inventory(self.root)
        self.assertEqual(result['total_bytes'], 5 + (self.run / 'run_manifest.json').stat().st_size)
        self.assertEqual(result['skipped_link_count'], 1)
        self.assertEqual(result['skipped_links'], [str(outside)])

    def test_windows_reparse_attribute_is_a_link(self):
        self.assertTrue(storage._link(self.root, SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)))

    def test_inventory_does_not_deduplicate_unavailable_inodes(self):
        self.csv()
        result = storage.inventory(self.root)
        self.assertEqual(result['unique_file_bytes'], result['total_bytes'])

    def test_preflight_accepts_exact_budget_and_reserve(self):
        with mock.patch.object(storage, 'inventory', return_value={'total_bytes': 100}), \
                mock.patch.object(storage.shutil, 'disk_usage', return_value=SimpleNamespace(free=220)):
            result = storage.preflight(self.root, 20, max_project_bytes=120, min_free_bytes=200)
        self.assertTrue(result['allowed'])
        self.assertEqual(result['projected_peak_bytes'], 120)

    def test_preflight_rejects_project_peak(self):
        with mock.patch.object(storage, 'inventory', return_value={'total_bytes': 100}), \
                mock.patch.object(storage.shutil, 'disk_usage', return_value=SimpleNamespace(free=1000)):
            with self.assertRaises(storage.StorageLimitError) as raised:
                storage.preflight(self.root, 20, max_project_bytes=119, min_free_bytes=200)
        self.assertFalse(raised.exception.report['allowed'])

    def test_preflight_rejects_insufficient_disk_reserve(self):
        with mock.patch.object(storage, 'inventory', return_value={'total_bytes': 100}), \
                mock.patch.object(storage.shutil, 'disk_usage', return_value=SimpleNamespace(free=219)):
            with self.assertRaises(storage.StorageLimitError):
                storage.preflight(self.root, 20, max_project_bytes=120, min_free_bytes=200)

    def test_preflight_rejects_negative_and_noninteger_estimates(self):
        for estimate in (-1, 0.5, True):
            with self.subTest(estimate=estimate), self.assertRaises(storage.StorageError):
                storage.preflight(self.root, estimate)

    def test_compaction_preserves_logical_bytes_and_manifest(self):
        manifest_before = (self.run / 'run_manifest.json').read_bytes()
        path = self.csv()
        content = path.read_bytes()
        result = storage.compact_run(self.run)
        target = path.with_name(path.name + '.gz')
        self.assertFalse(path.exists())
        self.assertEqual(gzip.decompress(target.read_bytes()), content)
        self.assertEqual((self.run / 'run_manifest.json').read_bytes(), manifest_before)
        self.assertEqual(result['files'][0]['sha256'], hashlib.sha256(content).hexdigest())
        self.assertGreater(result['saved_bytes'], 0)
        self.assertTrue((self.run / 'compact_receipt.json').is_file())

    def test_compaction_is_deterministic_and_repeat_keeps_receipt(self):
        path = self.csv()
        content = path.read_bytes()
        storage.compact_run(self.run)
        target = path.with_name(path.name + '.gz')
        compressed = target.read_bytes()
        receipt = (self.run / 'compact_receipt.json').read_bytes()
        repeated = storage.compact_run(self.run)
        self.assertEqual(repeated['csv_files_compacted'], 0)
        self.assertEqual((self.run / 'compact_receipt.json').read_bytes(), receipt)
        target.unlink()
        path.write_bytes(content)
        storage.compact_run(self.run)
        self.assertEqual(target.read_bytes(), compressed)

    def test_compaction_allows_finalizing_and_failed(self):
        for status in ('finalizing', 'failed'):
            with self.subTest(status=status):
                self.manifest(status)
                path = self.csv()
                storage.compact_run(self.run)
                self.assertFalse(path.exists())

    def test_compaction_refuses_running_unknown_and_corrupt_manifest(self):
        path = self.csv()
        for status in ('running', 'paused', None):
            with self.subTest(status=status):
                self.manifest(status)
                with self.assertRaises(storage.StorageError):
                    storage.compact_run(self.run)
                self.assertTrue(path.exists())
        (self.run / 'run_manifest.json').write_text('invalid', encoding='utf-8')
        with self.assertRaises(storage.StorageError):
            storage.compact_run(self.run)
        self.assertTrue(path.exists())

    def test_existing_conflicting_gzip_never_deletes_plaintext(self):
        path = self.csv()
        target = path.with_name(path.name + '.gz')
        target.write_bytes(gzip.compress(b'different data'))
        with self.assertRaises(storage.StorageError):
            storage.compact_run(self.run)
        self.assertTrue(path.exists())
        self.assertEqual(gzip.decompress(target.read_bytes()), b'different data')

    def test_existing_identical_gzip_removes_redundant_plaintext(self):
        path = self.csv()
        target = path.with_name(path.name + '.gz')
        content = path.read_bytes()
        target.write_bytes(gzip.compress(content))
        result = storage.compact_run(self.run)
        self.assertFalse(path.exists())
        self.assertEqual(gzip.decompress(target.read_bytes()), content)
        self.assertEqual(result['csv_files_compacted'], 1)

    def test_failed_gzip_verification_preserves_plaintext_and_cleans_temp(self):
        path = self.csv()
        real_signature = storage._content_signature
        with mock.patch.object(storage, '_content_signature',
                               side_effect=lambda p, compressed=False: (0, 'bad') if compressed else real_signature(p)):
            with self.assertRaises(storage.StorageError):
                storage.compact_run(self.run)
        self.assertTrue(path.exists())
        self.assertEqual(list(path.parent.glob('*.tmp')), [])
        self.assertFalse(path.with_name(path.name + '.gz').exists())

    def test_changed_source_during_compression_is_not_deleted(self):
        path = self.csv()
        real_signature = storage._content_signature
        calls = 0
        def signature(p, compressed=False):
            nonlocal calls
            if p == path and not compressed:
                calls += 1
                if calls == 2:
                    path.write_bytes(b'changed while gzip was running')
            return real_signature(p, compressed)
        with mock.patch.object(storage, '_content_signature', side_effect=signature):
            with self.assertRaises(storage.StorageError):
                storage.compact_run(self.run)
        self.assertEqual(path.read_bytes(), b'changed while gzip was running')
        self.assertFalse(path.with_name(path.name + '.gz').exists())

    def test_compaction_refuses_reparse_subtree(self):
        path = self.csv()
        real_link = storage._link
        with mock.patch.object(storage, '_link', side_effect=lambda p, s=None: p == path.parent or real_link(p, s)):
            with self.assertRaises(storage.StorageError):
                storage.compact_run(self.run)
        self.assertTrue(path.exists())

    def test_compaction_refuses_insufficient_scratch_space(self):
        path = self.csv()
        with mock.patch.object(storage.shutil, 'disk_usage', return_value=SimpleNamespace(free=1)):
            with self.assertRaises(storage.StorageError):
                storage.compact_run(self.run)
        self.assertTrue(path.exists())

    def test_delete_requires_explicit_name_and_rejects_traversal(self):
        for name in ('../run_fixture', 'run_fixture/../other', 'run_*', '.', 'run_', 'run_x\\nested'):
            with self.subTest(name=name), self.assertRaises(storage.StorageError):
                storage.delete_run(self.root, name)
        self.assertTrue(self.run.is_dir())

    def test_delete_refuses_running_finalizing_and_unknown(self):
        for status in ('running', 'finalizing', 'unknown'):
            self.manifest(status)
            with self.subTest(status=status), self.assertRaises(storage.StorageError):
                storage.delete_run(self.root, self.run.name)
        self.assertTrue(self.run.is_dir())

    def test_delete_refuses_nested_reparse_points(self):
        path = self.csv()
        real_link = storage._link
        with mock.patch.object(storage, '_link', side_effect=lambda p, s=None: p == path.parent or real_link(p, s)):
            with self.assertRaises(storage.StorageError):
                storage.delete_run(self.root, self.run.name)
        self.assertTrue(path.exists())

    def test_delete_preserves_mandatory_receipt_with_total_size_cap(self):
        self.manifest('failed')
        before_manifest = (self.run / 'run_manifest.json').read_bytes()
        self.csv()
        (self.run / 'step_failed.log').write_bytes(b'failure detail' * 1000)
        for n in range(20):
            (self.run / f'summary_{n}.json').write_text('{}', encoding='utf-8')
        result = storage.delete_run(self.root, self.run.name, receipt_max_bytes=3000)
        receipt = Path(result['receipt_directory'])
        self.assertFalse(self.run.exists())
        self.assertEqual((receipt / 'run_manifest.json').read_bytes(), before_manifest)
        self.assertLessEqual(storage.inventory(receipt)['total_bytes'], 3000)
        self.assertEqual(json.loads((receipt / 'deletion_receipt.json').read_text())['status'], 'deleted')
        self.assertGreater(result['released_bytes'], 0)
        self.assertEqual(list(self.root.rglob('*.zip')), [])

    def test_too_small_receipt_limit_never_deletes_run(self):
        with self.assertRaises(storage.StorageError):
            storage.delete_run(self.root, self.run.name, receipt_max_bytes=1)
        self.assertTrue(self.run.is_dir())

    def test_external_hardlink_content_is_retained_and_not_claimed_released(self):
        path = self.csv()
        path.write_bytes(b'cached content' * 1000)
        retained = self.root / 'retained_content.csv'
        try:
            os.link(path, retained)
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EPERM, errno.ENOSYS, errno.ENOTSUP, errno.EXDEV) \
                    and getattr(exc, 'winerror', None) not in (1, 50, 1314):
                raise
            self.skipTest('Hardlinks unavailable for fixture paths: ' + str(exc))
        manifest_bytes = (self.run / 'run_manifest.json').stat().st_size
        before = storage.inventory(self.run)['total_bytes']
        result = storage.delete_run(self.root, self.run.name)
        self.assertEqual(retained.read_bytes(), b'cached content' * 1000)
        self.assertEqual(result['removed_logical_bytes'], before)
        self.assertEqual(result['released_bytes'], manifest_bytes)
        self.assertEqual(result['hardlinked_content_bytes_not_counted_as_released'], 14000)
        self.assertEqual(result['net_released_content_bytes_lower_bound'], manifest_bytes - result['receipt_total_bytes'])
        receipt = Path(result['receipt_directory']) / 'deletion_receipt.json'
        self.assertEqual(json.loads(receipt.read_text())['released_bytes'], manifest_bytes)
        self.assertIn('not allocated', result['space_accounting_note'])

    def test_multi_link_content_with_all_links_inside_run_stays_lower_bound(self):
        path = self.csv()
        path.write_bytes(b'within run content')
        try:
            os.link(path, self.run / 'second.csv')
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EPERM, errno.ENOSYS, errno.ENOTSUP, errno.EXDEV) \
                    and getattr(exc, 'winerror', None) not in (1, 50, 1314):
                raise
            self.skipTest('Hardlinks unavailable for fixture paths: ' + str(exc))
        manifest_bytes = (self.run / 'run_manifest.json').stat().st_size
        result = storage.delete_run(self.root, self.run.name)
        self.assertEqual(result['removed_logical_bytes'], manifest_bytes + 2 * len(b'within run content'))
        self.assertEqual(result['released_bytes'], manifest_bytes)
        self.assertEqual(result['hardlinked_content_bytes_not_counted_as_released'], len(b'within run content'))

    def test_changed_run_while_copying_receipts_never_deletes_run(self):
        path = self.csv()
        real_copy = storage.shutil.copyfile
        def changing_copy(source, destination):
            value = real_copy(source, destination)
            path.write_bytes(path.read_bytes() + b'changed')
            return value
        with mock.patch.object(storage.shutil, 'copyfile', side_effect=changing_copy):
            with self.assertRaises(storage.StorageError):
                storage.delete_run(self.root, self.run.name)
        self.assertTrue(path.exists())

    def test_cli_reports_budget_failure_as_nonzero_json(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = storage.main(['preflight', '--root', str(self.root), '--estimated-peak-bytes', '1',
                                   '--max-project-bytes', '0', '--min-free-bytes', '0'])
        self.assertEqual(result, 2)
        self.assertFalse(json.loads(output.getvalue())['report']['allowed'])


if __name__ == '__main__':
    unittest.main()
