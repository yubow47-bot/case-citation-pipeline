"""Deterministic races and child-lifetime failures; no corpus or network operations."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
sys.path.insert(0, str(ROOT))
import storage
from pipeline import run_all


class ConcurrentInventoryTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'implementation/round3_tmp').mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'implementation/round3_tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original_lstat = Path.lstat

    def test_atomic_file_rename_between_scandir_and_lstat_is_tolerated(self):
        source = self.root/'progress.json.tmp'
        source.write_text('{}', encoding='utf-8')
        stable = self.root/'stable.txt'
        stable.write_bytes(b'12345')
        renamed = False
        def lstat(path, *args, **kwargs):
            nonlocal renamed
            if path == source and not renamed:
                renamed = True
                source.replace(self.root/'progress.json')
            return self.original_lstat(path, *args, **kwargs)
        with patch.object(Path, 'lstat', lstat):
            report = storage.inventory(self.root)
        self.assertTrue(renamed)
        self.assertEqual(report['total_bytes'], 5)
        self.assertEqual(report['concurrent_missing_entries'], 1)
        # The next scan picks up the replacement; inventory does not mutate it.
        self.assertEqual(storage.inventory(self.root)['total_bytes'], 7)

    def test_directory_removed_between_scandir_and_child_lstat_is_tolerated(self):
        transient = self.root/'.quality-label-test-fixture'
        transient.mkdir()
        (transient/'data.txt').write_text('fixture')
        removed = False
        def lstat(path, *args, **kwargs):
            nonlocal removed
            if path == transient and not removed:
                removed = True
                shutil.rmtree(transient)
            return self.original_lstat(path, *args, **kwargs)
        with patch.object(Path, 'lstat', lstat):
            report = storage.inventory(self.root)
        self.assertTrue(removed)
        self.assertEqual(report['concurrent_missing_entries'], 1)

    def test_queued_directory_removed_before_scan_is_tolerated(self):
        transient = self.root/'transient'
        transient.mkdir()
        calls = 0
        def lstat(path, *args, **kwargs):
            nonlocal calls
            if path == transient:
                calls += 1
                if calls == 2:
                    transient.rmdir()
            return self.original_lstat(path, *args, **kwargs)
        with patch.object(Path, 'lstat', lstat):
            report = storage.inventory(self.root)
        self.assertEqual(calls, 2)
        self.assertEqual(report['concurrent_missing_entries'], 1)

    def test_directory_removed_at_scandir_is_tolerated(self):
        transient = self.root/'transient'
        transient.mkdir()
        original_scandir = storage.os.scandir
        def scan(path):
            if Path(path) == transient:
                transient.rmdir()
            return original_scandir(path)
        with patch.object(storage.os, 'scandir', scan):
            self.assertEqual(storage.inventory(self.root)['concurrent_missing_entries'], 1)

    def test_strict_scan_does_not_ignore_a_disappearing_file(self):
        source = self.root/'table.csv'
        source.write_text('id\n1\n')
        def lstat(path, *args, **kwargs):
            if path == source and source.exists():
                source.unlink()
            return self.original_lstat(path, *args, **kwargs)
        with patch.object(Path, 'lstat', lstat), self.assertRaisesRegex(storage.StorageError, 'disappeared during strict scan'):
            list(storage._tree(self.root, reject_links=True))

    def test_strict_scan_does_not_ignore_a_disappearing_directory(self):
        transient = self.root/'transient'
        transient.mkdir()
        calls = 0
        def lstat(path, *args, **kwargs):
            nonlocal calls
            if path == transient:
                calls += 1
                if calls == 2:
                    transient.rmdir()
            return self.original_lstat(path, *args, **kwargs)
        with patch.object(Path, 'lstat', lstat), self.assertRaisesRegex(storage.StorageError, 'disappeared during strict scan'):
            list(storage._tree(self.root, reject_links=True))

    def test_unexpected_permission_errors_still_fail_closed(self):
        source = self.root/'file'
        source.write_text('test')
        def lstat(path, *args, **kwargs):
            if path == source:
                raise PermissionError('access denied')
            return self.original_lstat(path, *args, **kwargs)
        with patch.object(Path, 'lstat', lstat), self.assertRaises(PermissionError):
            storage.inventory(self.root)


class FakeChild:
    def __init__(self, actions):
        self.actions = iter(actions)
        self.returncode = None
        self.terminated = self.killed = self.waited = 0
        self.communicated = []

    def communicate(self, timeout=None):
        self.communicated.append(timeout)
        action = next(self.actions)
        if isinstance(action, BaseException):
            raise action
        code, out, err = action
        self.returncode = code
        return out, err

    def terminate(self):
        self.terminated += 1

    def kill(self):
        self.killed += 1

    def wait(self, timeout=None):
        self.waited += 1
        self.returncode = -9
        return self.returncode


class RunnerCleanupTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'implementation/round3_tmp').mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'implementation/round3_tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runner = object.__new__(run_all.Runner)
        self.runner.out = str(self.root)
        self.runner.args = argparse.Namespace(storage_budget_gb=12)
        self.runner.manifest_path = str(self.root/'run_manifest.json')
        self.runner.manifest = {'status': 'running', 'steps_done': []}
        self.runner.params = {}
        self.runner.start_identity = {'fingerprint': 'fixture', 'files': {}}
        self.runner.identity_verified = None

    def call(self, child, monitor=None):
        with patch.object(run_all.subprocess, 'Popen', return_value=child), \
             patch.object(run_all, 'preflight', side_effect=monitor), \
             patch.object(run_all, 'dep_versions', return_value={'fixture': 'offline'}), \
             contextlib.redirect_stdout(io.StringIO()):
            return self.runner.run_step('fixture', ['-c', 'pass'])

    def failed(self, phase):
        manifest = json.loads((self.root/'run_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['status'], 'failed')
        detail = manifest['step_execution_failure']
        self.assertEqual(detail['phase'], phase)
        self.assertTrue(detail['child_reaped'])
        log = (self.root/'step_fixture.log').read_text(encoding='utf-8')
        self.assertIn(phase, log)
        return detail, log

    def test_unknown_monitor_exception_terminates_and_reaps_with_log(self):
        child = FakeChild([subprocess.TimeoutExpired('fixture', 2), (-15, 'saved stdout', 'saved stderr')])
        with self.assertRaisesRegex(FileNotFoundError, 'vanished'):
            self.call(child, monitor=FileNotFoundError('vanished directory'))
        self.assertEqual(child.terminated, 1)
        self.assertEqual(child.killed, 0)
        detail, log = self.failed('storage_monitor')
        self.assertEqual(detail['exception'], 'FileNotFoundError')
        self.assertIn('saved stdout', log)
        self.assertIn('saved stderr', log)

    def test_storage_limit_keeps_guard_failure_semantics_and_reaps(self):
        limit = storage.StorageLimitError({'projected_peak_bytes': 20, 'max_project_bytes': 10,
                                         'free_after_peak_bytes': 10, 'min_free_bytes': 0})
        child = FakeChild([subprocess.TimeoutExpired('fixture', 2), (-15, '', '')])
        with self.assertRaisesRegex(SystemExit, 'Storage guard stopped'):
            self.call(child, monitor=limit)
        self.assertEqual(child.terminated, 1)
        self.assertEqual(self.runner.manifest['failed_step'], 'storage_budget_fixture')
        self.assertIn('storage_failure', self.runner.manifest)
        self.failed('storage_monitor')

    def test_communicate_unknown_exception_still_terminates_and_reaps(self):
        child = FakeChild([RuntimeError('reader failed'), (-15, 'partial output', '')])
        with self.assertRaisesRegex(RuntimeError, 'reader failed'):
            self.call(child)
        self.assertEqual(child.terminated, 1)
        self.failed('communicate')

    def test_stubborn_child_is_killed_after_terminate_timeout(self):
        child = FakeChild([subprocess.TimeoutExpired('fixture', 2),
                           subprocess.TimeoutExpired('fixture', 10, output=b'partial stdout'), (-9, 'complete stdout', '')])
        with self.assertRaisesRegex(OSError, 'monitor fault'):
            self.call(child, monitor=OSError('monitor fault'))
        self.assertEqual(child.terminated, 1)
        self.assertEqual(child.killed, 1)
        self.assertEqual(child.communicated, [2, 10, 10])
        detail, log = self.failed('storage_monitor')
        self.assertTrue(detail['cleanup_errors'])
        self.assertIn('complete stdout', log)

    def test_repeated_communicate_errors_do_not_prevent_wait_reaping(self):
        child = FakeChild([RuntimeError('initial reader failure'), RuntimeError('terminate read failure'), RuntimeError('kill read failure')])
        with self.assertRaisesRegex(RuntimeError, 'initial reader failure'):
            self.call(child)
        self.assertEqual(child.killed, 1)
        self.assertEqual(child.waited, 1)
        self.assertIsNotNone(child.returncode)
        self.failed('communicate')

    def test_keyboard_interrupt_is_not_allowed_to_orphan_a_child(self):
        child = FakeChild([KeyboardInterrupt('interrupted'), (-15, '', '')])
        with self.assertRaises(KeyboardInterrupt):
            self.call(child)
        self.assertEqual(child.terminated, 1)
        self.failed('communicate')

    def test_spawn_failure_is_logged_and_failed_without_a_child(self):
        with patch.object(run_all.subprocess, 'Popen', side_effect=OSError('spawn refused')), \
             patch.object(run_all, 'dep_versions', return_value={}), \
             contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(OSError, 'spawn refused'):
            self.runner.run_step('fixture', ['-c', 'pass'])
        self.failed('spawn')

    def test_successful_step_stays_running_and_preserves_output(self):
        child = FakeChild([(0, 'successful stdout', '')])
        self.call(child)
        self.assertEqual(child.terminated, 0)
        self.assertEqual(self.runner.manifest['steps_done'], ['fixture'])
        self.assertEqual(self.runner.manifest['status'], 'running')
        self.assertIn('successful stdout', (self.root/'step_fixture.log').read_text(encoding='utf-8'))

    def test_post_step_monitor_error_is_explicitly_failed_after_reaping(self):
        child = FakeChild([(0, 'completed output', '')])
        with self.assertRaisesRegex(OSError, 'post-step fault'):
            self.call(child, monitor=OSError('post-step fault'))
        self.assertEqual(child.terminated, 0)
        self.failed('after_step_storage_monitor')


if __name__ == '__main__':
    unittest.main()
