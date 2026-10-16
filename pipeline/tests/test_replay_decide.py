"""Replay provenance, compatibility and failure contracts without large data."""
import contextlib
from collections import Counter
import csv
import errno
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline import replay_decide as replay
from pipeline import run_all


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='replay-fixture-', dir=ROOT / 'implementation')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'data/run_source'
        self.source.mkdir(parents=True)
        self.target = self.root / 'data/run_target'
        (self.root / 'pipeline').mkdir()
        for name in ('extract', 'classify', 'merge', 'shapes', 'normalize', 'artifacts', 'decide', 'registry', 'edges', 'run_all'):
            (self.root / 'pipeline' / (name + '.py')).write_text('# producer ' + name, encoding='utf-8')
        (self.root / 'decisions').mkdir()
        (self.root / 'decisions/table.csv').write_text('token\na\n', encoding='utf-8')
        (self.root / 'decisions/identity_court_facts.csv').write_text('merge_key,canonical_court\na,SCC\n', encoding='utf-8')
        (self.root / 'corpus').mkdir()
        for court in ('SCC', 'ONCA', 'BCCA'):
            (self.root / 'corpus' / (court + '.parquet')).write_bytes(('corpus-' + court).encode())
        self.params = {'batch_size': 13, 'year_from': 1980, 'limit_batches': 1,
                       'courts': ['ONCA', 'SCC'], 'anchor_corpus': ['BCCA'],
                       'corpus_dir': str(self.root / 'corpus'), 'registry_gate': 'registered',
                       'mixed_key_holdout': True, 'compact': True}
        self.write_artifact('extract_out/manifest.json', b'{"original":true}')
        self.write_artifact('extract_out/candidates.csv.gz', gzip.compress(b'raw_string\none\n', mtime=0))
        for court in self.params['courts']:
            self.write_artifact('classify_out/' + court + '/manifest.json', b'{}')
            self.write_artifact('classify_out/' + court + '/classified.csv.gz', gzip.compress(b'id\none\n', mtime=0))
            self.write_artifact('merge_out/' + court + '/manifest.json', b'{}')
            for name in ('merged', 'mentions_candidates', 'decision_ids', 'folded_log'):
                self.write_artifact('merge_out/' + court + '/' + name + '.csv.gz', gzip.compress(b'id\none\n', mtime=0))
        self.seal_source()
        self.addCleanup(setattr, run_all, 'ACTIVE_RUNNER', None)

    def write_artifact(self, relative, raw):
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def seal_source(self):
        files = {p.relative_to(self.source).as_posix(): run_all.sha256_file(p)
                 for p in self.source.rglob('*') if p.is_file() and p.name != 'run_manifest.json'}
        manifest = {'status': 'complete', 'input_identity_verified_unchanged': True,
                    'params': self.params, 'schema_versions': dict(run_all.SCHEMA_VERSIONS),
                    'input_identity': run_all.input_identity(self.root, tuple(self.params['courts']), self.params,
                                                            self.params['corpus_dir']),
                    'output_identity': {'files': files, 'fingerprint': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}}
        (self.source / 'run_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return manifest

    def proof(self):
        return replay.verify_source(self.source, self.root)

    def test_sealed_compatible_source_is_accepted(self):
        proof = self.proof()
        self.assertEqual(proof['manifest']['params']['courts'], ['ONCA', 'SCC'])
        self.assertEqual(len(proof['upstream']), 16)

    def test_parser_table_and_anchor_corpus_changes_refuse_reuse(self):
        for relative in ('pipeline/normalize.py', 'decisions/table.csv', 'corpus/BCCA.parquet'):
            path = self.root / relative
            original = path.read_bytes()
            path.write_bytes(original + b'changed')
            with self.assertRaisesRegex(ValueError, 'inputs changed'):
                self.proof()
            path.write_bytes(original)

    def test_explicit_downstream_changes_are_allowed_but_new_helper_is_not(self):
        (self.root / 'pipeline/decide.py').write_text('# new downstream', encoding='utf-8')
        (self.root / 'pipeline/edges.py').write_text('# new downstream reader', encoding='utf-8')
        (self.root / 'pipeline/coverage_report.py').write_text('# new downstream diagnostic', encoding='utf-8')
        (self.root / 'pipeline/replay_decide.py').write_text('# new downstream', encoding='utf-8')
        self.proof()
        (self.root / 'pipeline/new_parser.py').write_text('# unexpected dependency', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'new_parser'):
            self.proof()

    def test_only_exact_downstream_court_fact_table_may_change(self):
        fact = self.root / 'decisions/identity_court_facts.csv'
        fact.write_text('merge_key,canonical_court\na,SCC\nb,BCCA\n', encoding='utf-8')
        proof = self.proof()
        self.assertNotEqual(proof['manifest']['input_identity']['files']['decisions/identity_court_facts.csv'],
                            run_all.sha256_file(fact))
        separation = self.root / 'decisions/identity_separations.csv'
        separation.write_text('merge_key,excluded_decision_id\nb,target\n', encoding='utf-8')
        self.proof()  # New exact downstream table is also fingerprinted in the new run.
        other = self.root / 'decisions/identity_court_scope.csv'
        other.write_text('Unexpected table change\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'identity_court_scope'):
            self.proof()

    def test_source_tampering_unsealed_files_and_bad_fingerprint_refuse(self):
        path = self.source / 'extract_out/candidates.csv.gz'
        original = path.read_bytes()
        path.write_bytes(original + b'changed')
        with self.assertRaisesRegex(ValueError, 'output seal changed'):
            self.proof()
        path.write_bytes(original)
        extra = self.source / 'unsealed.txt'
        extra.write_text('unexpected', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'exact file set'):
            self.proof()
        extra.unlink()
        manifest = json.loads((self.source / 'run_manifest.json').read_text())
        manifest['output_identity']['fingerprint'] = '0' * 64
        (self.source / 'run_manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'seal fingerprint'):
            self.proof()

    def test_running_or_unverified_source_refuses(self):
        for key, value in (('status', 'running'), ('input_identity_verified_unchanged', False)):
            manifest = self.seal_source()
            manifest[key] = value
            (self.source / 'run_manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'complete'):
                self.proof()

    def test_plaintext_upstream_and_missing_required_stage_refuse(self):
        self.write_artifact('extract_out/extra.csv', b'id\n1\n')
        self.seal_source()
        with self.assertRaisesRegex(ValueError, 'plaintext'):
            self.proof()
        (self.source / 'extract_out/extra.csv').unlink()
        (self.source / 'merge_out/SCC/decision_ids.csv.gz').unlink()
        self.seal_source()
        with self.assertRaisesRegex(ValueError, 'required compressed'):
            self.proof()

    def test_path_escape_and_reparse_tree_are_rejected(self):
        with self.assertRaises(ValueError):
            replay.run_path(self.root / 'data/sub/run_bad', self.root)
        with self.assertRaises(ValueError):
            replay._relative('../escape.csv.gz')
        original = replay._link
        with patch.object(replay, '_link', side_effect=lambda p: p.name == 'candidates.csv.gz' or original(p)):
            with self.assertRaisesRegex(ValueError, 'link/junction'):
                self.proof()

    def test_hardlinks_preserve_upstream_after_source_removal(self):
        proof = self.proof()
        self.target.mkdir()
        old = self.source / 'extract_out/candidates.csv.gz'
        new = self.target / 'extract_out/candidates.csv.gz'
        new.parent.mkdir(parents=True)
        # Probe the OS directly so an unavailable fixture capability is distinct
        # from a regression in reuse_upstream's hardlink implementation.
        try:
            os.link(old, new)
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EPERM, errno.ENOSYS, errno.ENOTSUP, errno.EXDEV) \
                    and getattr(exc, 'winerror', None) not in (1, 50, 1314):
                raise
            self.skipTest('Hardlinks unavailable for fixture paths: ' + str(exc))
        else:
            new.unlink()
        with patch.object(replay, 'ROOT', self.root), patch.object(run_all, 'preflight', return_value={}):
            receipt = replay.reuse_upstream(proof, self.target)
        self.assertTrue(all(r['method'] == 'hardlink_compressed_csv' for r in receipt['files'] if r['path'].endswith('.csv.gz')))
        self.assertEqual(old.stat().st_ino, new.stat().st_ino)
        replay.run_path(self.source, self.root)  # Exact plain temporary scope before recursive removal.
        shutil.rmtree(self.source)
        self.assertEqual(gzip.decompress(new.read_bytes()), b'raw_string\none\n')
        self.assertTrue((self.target / 'reused_upstream_manifest.json').is_file())

    def test_explicit_copy_survives_unavailable_hardlinks(self):
        proof = self.proof()
        with patch.object(replay.os, 'link', side_effect=OSError('unavailable')), \
             patch.object(replay, 'MAX_COPY_BYTES', 0), \
             patch.object(run_all, 'preflight', return_value={'allowed': True}):
            receipt = replay.reuse_upstream(proof, self.target, copy_upstream=True)
        self.assertIn('copy_compressed_csv', {r['method'] for r in receipt['files']})
        replay.verify_source_unchanged(proof, self.target)

    def test_country_only_reassessment_preserves_identity_and_effective_sources(self):
        import decide
        record = dict(merged_group_id='g1', merge_key='1973|3|nfldpeir||418',
            jurisdiction='UNSUPPORTED', citation_kind='reporter', court='SCC',
            distinct_decisions_count='2', identity_basis='unanchored',
            member_origin_status='UNDETERMINED', member_origin_country='',
            member_origin_basis='', member_origin_evidence_ids='', member_origin_conflict_detail='',
            member_origin_subdivision='', member_origin_ambiguous_basis='', member_origin_exclusivity='')
        decide.aggregate_group_origin([record], Counter())
        for label in ('ONCA', 'SCC', 'cross_court'):
            stream = io.StringIO(newline='')
            writer = csv.DictWriter(stream, fieldnames=list(record))
            writer.writeheader(); writer.writerow(record)
            self.write_artifact('decide_out/' + label + '/decided.csv.gz', gzip.compress(stream.getvalue().encode()))
            self.write_artifact('decide_out/' + label + '/manifest.json', b'{"stats":{"groups_out":1}}')
        relative = 'decide_out/cross_court/effective_sources.csv.gz'
        self.write_artifact(relative, gzip.compress(b'source_decision,identity_status\nsource,unanchored\n'))
        self.seal_source()
        proof = self.proof()
        calls = []
        runner = SimpleNamespace(out=str(self.target), courts=('ONCA', 'SCC'),
            manifest={'steps_done': []}, write_manifest=lambda status: None,
            run_step=lambda name, cmd: calls.append(name))
        copied = replay.reassess_countries(proof, runner)
        with (self.target / 'decide_out/cross_court/decided.csv').open(encoding='utf-8', newline='') as f:
            after = next(csv.DictReader(f))
        self.assertEqual(after['member_origin_country'], 'CA')
        self.assertEqual(after['group_origin_country'], 'CA')
        self.assertEqual(after['identity_basis'], 'unanchored')
        self.assertEqual(after['distinct_decisions_count'], '2')
        self.assertEqual((self.target / relative).read_bytes(), (self.source / relative).read_bytes())
        self.assertIn(relative, copied)
        self.assertEqual(calls, ['select', 'edges', 'coverage_report'])

    def test_reused_target_bytes_and_source_manifest_changes_are_detected(self):
        proof = self.proof()
        self.target.mkdir()
        with patch.object(replay, 'ROOT', self.root), patch.object(run_all, 'preflight', return_value={}):
            replay.reuse_upstream(proof, self.target)
        (self.target / 'classify_out/SCC/manifest.json').write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError, 'upstream bytes changed'):
            replay.verify_source_unchanged(proof, self.target)
        (self.source / 'run_manifest.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'manifest changed'):
            replay.verify_source_unchanged(proof)

    def test_peak_budget_includes_reused_bytes_generated_and_scratch(self):
        self.write_artifact('compact_receipt.json', json.dumps({'files': [
            {'path': 'select_out/selected.csv.gz', 'logical_bytes': 900000000},
            {'path': 'extract_out/candidates.csv.gz', 'logical_bytes': 3000000000}]}).encode())
        self.seal_source()
        proof = self.proof()
        self.assertEqual(replay.estimated_peak_bytes(proof), proof['upstream_bytes'] + 1125000000 + 900000000 + 64 * 1024**2)

    def invoke(self, downstream):
        with patch.object(replay, 'ROOT', self.root), patch.object(run_all, 'ROOT', str(self.root)), \
             patch.object(run_all, 'preflight', return_value={'allowed': True}), \
             patch.object(run_all, 'run_downstream', side_effect=downstream), \
             patch.object(run_all, 'dep_versions', return_value={'fixture': 'offline'}), \
             contextlib.redirect_stdout(io.StringIO()):
            return replay.main(['--source-run', str(self.source), '--out', str(self.target)])

    def test_complete_replay_preserves_scope_and_seals_provenance(self):
        seen = []
        def downstream(runner):
            seen.append(runner)
            self.assertEqual(runner.courts, ('ONCA', 'SCC'))
            self.assertEqual(runner.params['year_from'], 1980)
            path = self.target / 'select_out/selected.csv'
            path.parent.mkdir()
            path.write_text('id\nnew\n', encoding='utf-8')
            runner.manifest['steps_done'].append('fixture_downstream')
        with patch.dict(os.environ, {'PIPELINE_COURTS': 'TCC'}):
            self.assertEqual(self.invoke(downstream), 0)
        manifest = json.loads((self.target / 'run_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['status'], 'complete')
        self.assertEqual(manifest['steps_done'], ['fixture_downstream'])
        self.assertEqual(manifest['steps_reused'], ['extract', 'classify_ONCA', 'classify_SCC', 'merge_ONCA', 'merge_SCC'])
        self.assertFalse(manifest['replay']['fresh_upstream_execution'])
        self.assertEqual(manifest['params']['full_scope']['anchor_corpus'], ['BCCA'])
        self.assertIn('reused_upstream_manifest.json', manifest['output_identity']['files'])
        self.assertIn('extract_out/candidates.csv.gz', manifest['output_identity']['files'])
        self.assertIn('select_out/selected.csv.gz', manifest['output_identity']['files'])
        self.assertNotIn('select_out/selected.csv', manifest['output_identity']['files'])
        for relative, sha in manifest['output_identity']['files'].items():
            self.assertEqual(run_all.sha256_file(self.target / relative), sha)

    def test_replay_preserves_explicit_french_fallback_policy(self):
        self.params['text_policy'] = 'en_then_fr'
        self.seal_source()
        def downstream(runner):
            self.assertEqual(runner.params['text_policy'], 'en_then_fr')
            self.assertEqual(runner.params['full_scope']['text_policy'], 'en_then_fr')
        self.assertEqual(self.invoke(downstream), 0)

    def test_downstream_failure_records_failed_target(self):
        with self.assertRaisesRegex(RuntimeError, 'downstream fault'):
            self.invoke(lambda runner: (_ for _ in ()).throw(RuntimeError('downstream fault')))
        manifest = json.loads((self.target / 'run_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['status'], 'failed')
        self.assertIn('downstream fault', manifest['failure_detail'])
        self.assertFalse(manifest['replay']['fresh_upstream_execution'])

    def test_nonempty_target_is_not_modified(self):
        self.target.mkdir()
        (self.target / 'keep').write_text('keep', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'missing or empty'):
            self.invoke(lambda runner: self.fail('Must not execute'))
        self.assertEqual((self.target / 'keep').read_text(), 'keep')

    def test_source_change_during_downstream_refuses_complete(self):
        def downstream(runner):
            (self.source / 'classify_out/SCC/manifest.json').write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError, 'Source artifact changed'):
            self.invoke(downstream)
        manifest = json.loads((self.target / 'run_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['status'], 'failed')
        self.assertNotIn('output_identity', manifest)

    def test_large_link_failure_never_falls_back_to_large_copy(self):
        with patch.object(replay, 'MAX_COPY_BYTES', 20), \
             patch.object(replay.os, 'link', side_effect=PermissionError('sandbox link denied')), \
             self.assertRaisesRegex(ValueError, 'large fallback copy'):
            self.invoke(lambda runner: self.fail('No downstream step may execute'))
        manifest = json.loads((self.target / 'run_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['status'], 'failed')
        self.assertFalse((self.target / 'classify_out/ONCA/classified.csv.gz').exists())

    def test_shared_downstream_has_no_upstream_commands(self):
        runner = type('Recorder', (), {})()
        runner.courts, runner.anchor_courts = ('SCC',), ()
        runner.corpus_dir = str(self.root / 'corpus')
        runner.args = type('Args', (), {'out': str(self.target), 'corpus_dir': runner.corpus_dir,
                                      'registry_gate': 'registered', 'mixed_key_holdout': True})()
        calls = []
        runner.run_step = lambda name, cmd: calls.append((name, cmd))
        run_all.run_downstream(runner)
        self.assertEqual([name for name, _ in calls], ['build_registry', 'decide_SCC', 'decide_cross', 'registry_report', 'select', 'edges', 'coverage_report'])
        self.assertTrue(all(not name.startswith(('extract', 'classify', 'merge')) for name, _ in calls))


if __name__ == '__main__':
    unittest.main()
