"""Behavior checks for discovery, failure propagation, frozen runs and explicit metadata."""
import contextlib
import csv
import gzip
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load('offline_runner', 'scripts/verify_offline.py')
golden = load('run_golden_checker', 'scripts/check_run_golden.py')
receipt = load('fix_batch_receipt', 'audit/fix_batch_20261016_receipt.py')


class VerificationToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'implementation')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_csv(self, relative, rows):
        path = self.root/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(str(path)+'.gz', 'wt', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def golden_fixture(self):
        (self.root/'run_manifest.json').write_text(json.dumps({'status': 'complete',
            'input_identity_verified_unchanged': True, 'params': {'courts': ['SCC', 'ONCA', 'BCCA']}}))
        row = dict(merged_group_id='g', is_primary='true', distinct_decisions_count='5',
                   merge_key='fixed-key', case_name_modal='Expected name')
        for court in ['SCC', 'ONCA', 'BCCA', 'cross_court']:
            self.write_csv(f'decide_out/{court}/decided.csv', [row])
        self.write_csv('edges/citation_edges.csv', [{'source_decision': str(i)} for i in range(5)])
        expected = {'schema': 'run-golden-v1', 'snapshot': {
            'courts': ['BCCA', 'ONCA', 'SCC'],
            'by_court': {c: {'rows': 1, 'groups': 1} for c in ['BCCA', 'ONCA', 'SCC']},
            'cross_court': {'rows': 1, 'groups': 1, 'groups_dd_positive': 1, 'groups_dd_ge5': 1, 'edges': 5},
            'probes': {'fixed-key': [['Expected name', 5]]}}}
        path = self.root/'frozen.json'
        path.write_text(json.dumps(expected), encoding='utf-8')
        return path, row

    def test_discovers_all_pipeline_scripts_and_extraction_selftest(self):
        directory = self.root/'pipeline/tests'
        directory.mkdir(parents=True)
        for name in ['test_history_separation.py', 'test_country_assessment.py', 'test_new_rule.py']:
            (directory/name).touch()
        suites = dict(runner.discover_suites(self.root))
        for name in ['history_separation', 'country_assessment', 'new_rule']:
            self.assertEqual(suites['test_'+name], ['pipeline/tests/test_'+name+'.py'])
        self.assertEqual(suites['extraction_selftest'], ['pipeline/tests/run_regression.py', '--selftest'])

    def test_runner_preserves_failure_and_runs_remaining_suites(self):
        output = self.root/'logs'
        results = [subprocess.CompletedProcess(['fail'], 7, 'original failure'),
                   subprocess.CompletedProcess(['pass'], 0, 'Ran 2 tests\nOK')]
        with patch.object(runner, 'discover_suites', return_value=[('fail', ['bad.py']), ('pass', ['good.py'])]), \
             patch.object(runner.subprocess, 'run', side_effect=results) as child, \
             contextlib.redirect_stdout(io.StringIO()):
            status = runner.main(['--output', str(output), '--temp-root', str(self.root)])
        report = json.loads((output/'summary.json').read_text())
        self.assertEqual(status, 1)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual([x['exit_code'] for x in report['suites']], [7, 0])
        self.assertEqual(child.call_count, 2)
        self.assertEqual((output/'fail.log').read_text(), 'original failure')

    def test_no_suites_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'No pipeline'):
            runner.discover_suites(self.root)

    def test_golden_uses_frozen_expectation_and_detects_name_regression(self):
        expected, row = self.golden_fixture()
        frozen = expected.read_bytes()
        self.assertEqual(golden.compare(self.root, expected)['status'], 'passed')
        row['case_name_modal'] = 'Wrong neighboring name'
        self.write_csv('decide_out/cross_court/decided.csv', [row])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(golden.main(['--run', str(self.root), '--expect', str(expected)]), 1)
        self.assertEqual(expected.read_bytes(), frozen)

    def test_golden_checks_bcca_and_requires_complete_run(self):
        expected, row = self.golden_fixture()
        self.write_csv('decide_out/BCCA/decided.csv', [row, row])
        self.assertEqual(golden.compare(self.root, expected)['status'], 'failed')
        (self.root/'run_manifest.json').write_text(json.dumps({'status': 'running'}))
        with self.assertRaisesRegex(ValueError, 'complete'):
            golden.compare(self.root, expected)

    def test_receipt_metadata_is_explicit_readonly_and_fails_empty(self):
        path = self.root/'metadata.db'
        with contextlib.closing(sqlite3.connect(path)) as db, db:
            db.execute('CREATE TABLE documents(run_id TEXT, source_id TEXT, name TEXT, decision_date TEXT)')
            db.execute('INSERT INTO documents VALUES(?,?,?,?)', ('independent', 'SCC_source', 'A v B', '2020-01-01'))
        original = path.read_bytes()
        docs, provenance = receipt.load_documents(path, 'independent')
        self.assertEqual(docs, {'SCC_source': ('avb', 2020)})
        self.assertEqual(provenance['run_id'], 'independent')
        self.assertEqual(provenance['documents'], 1)
        self.assertEqual(len(provenance['metadata_sha256']), 64)
        with self.assertRaisesRegex(ValueError, 'No source metadata'):
            receipt.load_documents(path, 'absent-run')
        self.assertEqual(path.read_bytes(), original)
        with self.assertRaises(sqlite3.OperationalError):
            receipt.load_documents(self.root/'absent.db', 'independent')
        self.assertFalse((self.root/'absent.db').exists())


if __name__ == '__main__':
    unittest.main()
