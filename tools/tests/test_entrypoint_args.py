"""Entrypoint forwarding and storage guards without a corpus build or child process."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'/'foundation'))
import after_run
from pipeline import run_all


class FoundationArgumentTests(unittest.TestCase):
    def call(self, *options):
        with patch.object(after_run, 'database_preflight') as capacity, \
             patch.object(after_run.subprocess, 'run') as child, \
             patch.object(after_run, 'run_all', return_value={'status': 'fixture'}) as foundation, \
             contextlib.redirect_stdout(io.StringIO()):
            result = after_run.main(['--pipeline-out', str(ROOT/'data/run_argument_fixture'), *options])
        self.assertEqual(result, 0)
        return capacity, child, foundation

    def test_explicit_pipeline_scope_and_storage_reach_child_and_foundation(self):
        corpus = str(ROOT/'implementation/corpus with spaces')
        capacity, child, foundation = self.call('--corpus', corpus, '--court', 'ONCA', '--court', 'BCCA',
            '--storage-budget-gb', '9.5', '--min-free-gb', '0.25', '--estimated-peak-gb', '1.5')
        child.assert_called_once_with([
            sys.executable, str(ROOT/'pipeline/run_all.py'), '--out', str((ROOT/'data/run_argument_fixture').resolve()),
            '--storage-budget-gb', '9.5', '--min-free-gb', '0.25', '--corpus-dir', corpus,
            '--court', 'ONCA', '--court', 'BCCA'], check=True, cwd=ROOT)
        self.assertEqual(capacity.call_args.args[1], int(1.5 * run_all.GiB))
        self.assertEqual(foundation.call_args.args[2], corpus)
        self.assertEqual(foundation.call_args.args[5:],
                         (int(9.5 * run_all.GiB), int(0.25 * run_all.GiB), int(1.5 * run_all.GiB)))

    def test_omitted_courts_leave_pipeline_environment_default(self):
        with patch.dict(os.environ, {'PIPELINE_COURTS': 'ONCA'}):
            _, child, _ = self.call()
        self.assertNotIn('--court', child.call_args.args[0])
        self.assertNotIn('--corpus-dir', child.call_args.args[0])
        self.assertNotIn('env', child.call_args.kwargs)

    def test_relative_corpus_resolves_identically_for_child_and_foundation(self):
        corpus = 'implementation/relative corpus'
        _, child, foundation = self.call('--corpus', corpus)
        command = child.call_args.args[0]
        self.assertEqual(command[command.index('--corpus-dir') + 1], str(Path(corpus).resolve()))
        self.assertEqual(foundation.call_args.args[2], str(Path(corpus).resolve()))


class PipelineArgumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='entrypoint-fixture-', dir=ROOT/'implementation')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for directory in ('pipeline', 'data', 'corpus'):
            (self.root/directory).mkdir()
        for court in ('SCC', 'ONCA', 'BCCA'):
            (self.root/'corpus'/(court + '.parquet')).write_bytes(b'mocked corpus identity')
        self.addCleanup(setattr, run_all, 'ACTIVE_RUNNER', None)

    def test_cli_scope_and_reserve_reach_all_preflight_phases(self):
        def child(*args, **kwargs):
            process = Mock(returncode=0)
            process.communicate.side_effect = [subprocess.TimeoutExpired('fixture', 2), ('', '')]
            return process

        target = self.root/'data/run_fixture'
        argv = ['run_all.py', '--out', str(target), '--corpus-dir', str(self.root/'corpus'),
                '--court', 'BCCA', '--court', 'ONCA', '--min-free-gb', '0.25', '--storage-budget-gb', '8']
        with patch.object(run_all, 'ROOT', str(self.root)), \
             patch('sys.argv', argv), patch.dict(os.environ, {'PIPELINE_COURTS': 'SCC'}), \
             patch.object(run_all.subprocess, 'Popen', side_effect=child) as children, \
             patch.object(run_all, 'preflight', return_value={'allowed': True}) as capacity, \
             patch.object(run_all, 'dep_versions', return_value={'fixture': 'offline'}), \
             patch.object(run_all, 'finalize'), contextlib.redirect_stdout(io.StringIO()):
            run_all.main()
        self.assertEqual(capacity.call_count, 1 + 2 * children.call_count)
        self.assertTrue(all(call.kwargs['min_free_bytes'] == run_all.GiB // 4 for call in capacity.call_args_list))
        manifest = json.loads((target/'run_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['params']['courts'], ['BCCA', 'ONCA'])
        self.assertEqual(manifest['params']['min_free_gb'], 0.25)
        extract = children.call_args_list[0].args[0]
        self.assertEqual(extract[extract.index('--corpus-dir') + 1], str(self.root/'corpus'))
        self.assertEqual([extract[i + 1] for i, value in enumerate(extract) if value == '--corpus'], ['BCCA', 'ONCA'])
        self.assertEqual(manifest['steps_done'][-2:], ['edges', 'coverage_report'])

    def test_invalid_free_space_reserve_fails_before_any_work(self):
        for value in ('-1', 'nan', 'inf'):
            with self.subTest(value=value), patch('sys.argv', ['run_all.py', '--out',
                    str(self.root/'data/run_invalid'), '--min-free-gb', value]), \
                 patch.object(run_all, 'ROOT', str(self.root)), \
                 patch.object(run_all, 'Runner') as runner, patch.object(run_all, 'preflight') as capacity, \
                 contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                run_all.main()
            runner.assert_not_called()
            capacity.assert_not_called()


if __name__ == '__main__':
    unittest.main()
