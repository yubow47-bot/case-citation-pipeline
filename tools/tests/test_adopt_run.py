"""Local adoption retains old bytes and restores DB/pointer together on rollback."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import adopt_run as adopt


class AdoptionTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / 'implementation'
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='adopt-fixture-', dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'data/foundation').mkdir(parents=True)
        (self.root / 'audit').mkdir()
        self.run = self.root / 'data/run_new'
        self.run.mkdir()
        self.receipt = self.root / 'audit/adoption.json'
        self.candidate = self.root / 'data/foundation/candidate.db'
        self.target = self.root / 'data/foundation/research.db'
        self.old = {'run_id': 'run_old', 'input_fingerprint': 'old',
                    'run_directory': 'data/run_old', 'db_path': 'data/foundation/research.db'}
        self.manifest = {'status': 'complete', 'input_identity': {'fingerprint': 'new'}}
        adopt.atomic(self.root / 'data/active_run.json', self.old)
        for path, run, fp, manifest in [(self.target, 'run_old', 'old', {}),
                                        (self.candidate, 'run_new', 'new', self.manifest)]:
            db = sqlite3.connect(path)
            db.executescript('CREATE TABLE runs(run_id TEXT,status TEXT,input_fingerprint TEXT,manifest_json TEXT);'
                             'CREATE TABLE run_components(run_id TEXT,component TEXT,status TEXT);'
                             'CREATE TABLE review_notes(note TEXT);')
            db.execute('INSERT INTO runs VALUES(?,?,?,?)', (run, 'ready', fp, json.dumps(manifest)))
            db.executemany('INSERT INTO run_components VALUES(?,?,?)', [(run, c, 'ready') for c in adopt.REQUIRED])
            db.execute('INSERT INTO review_notes VALUES(?)', ('unique ' + run,))
            db.commit()
            db.close()
        self.verify = patch.object(adopt, 'verify_run', return_value=self.manifest)
        self.verify.start()
        self.addCleanup(self.verify.stop)

    def prepare(self):
        return adopt.prepare(self.root, self.run, self.candidate, self.receipt)

    def test_adopt_and_rollback_preserve_exact_database_and_pointer(self):
        old_hash, new_hash = adopt.digest(self.target), adopt.digest(self.candidate)
        plan = self.prepare()
        self.assertEqual(adopt.digest(self.target), old_hash)
        result = adopt.apply(self.root, self.receipt)
        self.assertEqual(result['status'], 'applied')
        self.assertEqual(adopt.digest(self.target), new_hash)
        self.assertEqual(adopt.digest(Path(plan['backup'])), old_hash)
        self.assertEqual(json.loads((self.root / 'data/active_run.json').read_text())['run_id'], 'run_new')
        db = adopt.reader(plan['backup'])
        self.assertEqual(db.execute('SELECT note FROM review_notes').fetchone()[0], 'unique run_old')
        db.close()
        adopt.rollback(self.root, self.receipt)
        self.assertEqual(adopt.digest(self.target), old_hash)
        self.assertEqual(adopt.digest(self.candidate), new_hash)
        self.assertEqual(json.loads((self.root / 'data/active_run.json').read_text()), self.old)

    def test_changed_pointer_prevents_mutation(self):
        self.prepare()
        adopt.atomic(self.root / 'data/active_run.json', dict(self.old, run_id='someone_else'))
        with self.assertRaisesRegex(ValueError, 'inputs changed'):
            adopt.apply(self.root, self.receipt)
        self.assertTrue(self.candidate.is_file())
        self.assertFalse(Path(json.loads(self.receipt.read_text())['backup']).exists())

    def test_missing_required_component_is_rejected(self):
        db = sqlite3.connect(self.candidate)
        db.execute("DELETE FROM run_components WHERE component='acceptance'")
        db.commit()
        db.close()
        with self.assertRaisesRegex(ValueError, 'components are incomplete'):
            self.prepare()
        self.assertFalse(self.receipt.exists())

    def test_interruption_between_database_and_pointer_is_recoverable(self):
        self.prepare()
        result = adopt.apply(self.root, self.receipt)
        adopt.atomic(self.root / 'data/active_run.json', self.old)
        result['status'] = 'applying'
        adopt.atomic(self.receipt, result)
        self.assertEqual(adopt.rollback(self.root, self.receipt)['status'], 'rolled_back')
        self.assertEqual(json.loads((self.root / 'data/active_run.json').read_text()), self.old)

    def test_interruption_between_rollback_renames_can_be_retried(self):
        self.prepare()
        result = adopt.apply(self.root, self.receipt)
        real_replace = os.replace
        def fail_old_restore(source, target):
            if Path(source) == Path(result['backup']) and Path(target) == self.target:
                raise OSError('injected interruption restoring old database')
            return real_replace(source, target)
        with patch.object(adopt.os, 'replace', side_effect=fail_old_restore):
            with self.assertRaisesRegex(OSError, 'injected interruption'):
                adopt.rollback(self.root, self.receipt)
        self.assertFalse(self.target.exists())
        self.assertTrue(self.candidate.is_file())
        self.assertEqual(adopt.rollback(self.root, self.receipt)['status'], 'rolled_back')
        self.assertEqual(json.loads((self.root / 'data/active_run.json').read_text()), self.old)
        self.assertEqual(adopt.rollback(self.root, self.receipt)['status'], 'rolled_back')

    def test_failed_initial_database_rename_can_be_aborted(self):
        self.prepare()
        real_replace = os.replace
        def fail_new_database(source, target):
            if Path(source) == self.candidate and Path(target) == self.target:
                raise OSError('injected adoption rename failure')
            return real_replace(source, target)
        with patch.object(adopt.os, 'replace', side_effect=fail_new_database):
            with self.assertRaisesRegex(OSError, 'adoption rename failure'):
                adopt.apply(self.root, self.receipt)
        self.assertEqual(adopt.rollback(self.root, self.receipt)['status'], 'rolled_back')
        self.assertEqual(json.loads((self.root / 'data/active_run.json').read_text()), self.old)

    def test_failed_pointer_write_retains_pending_evidence_and_recovers(self):
        self.prepare()
        real_replace = os.replace
        pointer_path = self.root / 'data/active_run.json'
        def fail_pointer(source, target):
            if Path(target) == pointer_path:
                raise OSError('injected pointer write failure')
            return real_replace(source, target)
        with patch.object(adopt.os, 'replace', side_effect=fail_pointer):
            with self.assertRaisesRegex(OSError, 'pointer write failure'):
                adopt.apply(self.root, self.receipt)
        self.assertTrue(pointer_path.with_name(pointer_path.name + '.pending').exists())
        self.assertEqual(adopt.rollback(self.root, self.receipt)['status'], 'rolled_back')
        self.assertTrue(list(pointer_path.parent.glob('*.pending.recovered.*')))

    def test_outside_project_target_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'inside the literal project'):
            adopt.contained(self.root, self.root.parent / 'outside.db')


if __name__ == '__main__':
    unittest.main()
