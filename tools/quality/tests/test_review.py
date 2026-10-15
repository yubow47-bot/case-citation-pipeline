"""Synthetic defects and design checks for the offline review workflow."""
import gzip
import json
import sqlite3
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools/research'))
from tools.research.fixture import create_fixture, write_csv
from tools.research.core import rows, EDGE_FIELDS, DOCUMENT_FIELDS
from tools.quality import common, identity_queue, sample


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.quality-test-', dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.paths = create_fixture(self.base)
        self.run = Path(self.paths['run'])
        self.selected = self.run / 'select_out/selected.csv.gz'
        self.members = [r for _, r in rows(self.selected)]
        for r in self.members:
            g = r['merged_group_id']
            r['merge_key'] = '1990||scc||10' if g != 'XC-G000003' else '1990||canlii||22'
            r['citation_kind'] = 'neutral' if g != 'XC-G000003' else 'identifier'
            r['identity_basis'] = 'cocitation' if g == 'XC-G000001' else 'name_year' if g == 'XC-G000002' else 'singleton'
            r['identity_court_evidence'] = 'court:csc=neutral_code:scc' if r['court'] == 'SCC' else 'court:onca=printed_court:ONCA'
            r['identity_court_conflict'] = 'false'
        write_csv(self.selected, list(self.members[0]), self.members)
        for court in ('SCC', 'ONCA'):
            path = self.run / 'merge_out' / court / ('mentions_candidates.csv.gz' if court == 'SCC' else 'mentions_candidates.csv')
            records = [r for _, r in rows(path)]
            for r in records:
                r['merge_key'] = '1990||scc||10'
            write_csv(path, list(records[0]), records)
        typo = self.run / 'decide_out/cross_court/typo_over_registered.csv'
        write_csv(typo, ['merge_key', 'folded_into', 'registry_decision_id', 'typo_kind'],
                  [{'merge_key': '1990||scc||11', 'folded_into': '1990||scc||10',
                    'registry_decision_id': 'SCC_real11', 'typo_kind': 'typo_number'}])

    def source(self):
        source = common.open_source(run=self.run, documents=self.paths['documents'])
        self.addCleanup(source.close)
        return source

    def test_queue_finds_independent_identity_defects_from_full_scan(self):
        result = identity_queue.review_queue(self.source(), min_impact_dd=1)
        reasons = result['candidate_counts_by_reason']
        self.assertEqual(result['full_scan_coverage']['members_scanned'], 6)
        self.assertEqual(result['full_scan_coverage']['groups_scanned'], 3)
        self.assertEqual(reasons['complete_neutral_or_identifier_key_in_multiple_groups'], 1)
        self.assertEqual(reasons['conflicting_positive_court_evidence'], 3)
        self.assertEqual(reasons['high_impact_name_year_or_cocitation_identity'], 2)
        self.assertEqual(reasons['registered_real_decision_folded_as_typo'], 1)
        for r in result['records']:
            self.assertEqual(r['record_hash'], common.canonical_hash({k: v for k, v in r.items() if k != 'record_hash'}))

    def test_queue_retention_limit_does_not_change_candidate_denominator(self):
        source = self.source()
        all_records = identity_queue.review_queue(source, limit=500, min_impact_dd=1)
        limited = identity_queue.review_queue(source, limit=1, min_impact_dd=1)
        self.assertEqual(limited['candidates_total'], all_records['candidates_total'])
        self.assertEqual(len(limited['records']), 1)
        self.assertTrue(limited['truncated'])
        self.assertEqual(limited['records'][0]['priority'], 100)

    def test_queue_does_not_use_citing_court_as_deciding_court(self):
        for r in self.members:
            r['identity_court_evidence'] = ''
        write_csv(self.selected, list(self.members[0]), self.members)
        result = identity_queue.review_queue(self.source(), min_impact_dd=1)
        self.assertNotIn('conflicting_positive_court_evidence', result['candidate_counts_by_reason'])
        self.assertEqual(result['full_scan_coverage']['members_without_stored_positive_court_evidence'], 6)

    def test_sampling_covers_all_countable_edges_including_unknowns(self):
        result = sample.stratified_sample(self.source())
        self.assertEqual(result['frame_N'], 6)
        self.assertEqual(sum(c['N_cell'] for c in result['cells']), 6)
        self.assertEqual(result['sample_n'], sum(c['n_cell'] for c in result['cells']))
        self.assertTrue(any(c['stratum']['citing_judgment_era'] == 'unknown' for c in result['cells']))
        self.assertTrue(any(c['stratum']['edge_support'] == 'heuristic_only' for c in result['cells']))
        for c in result['cells']:
            self.assertEqual(c['n_cell'], min(2, c['N_cell']))
            self.assertEqual(c['pi'], c['n_cell'] / c['N_cell'])

    def test_seed_and_source_fold_are_stable(self):
        source = self.source()
        first = sample.stratified_sample(source, seed=123)
        second = sample.stratified_sample(source, seed=123)
        self.assertEqual(first['records'], second['records'])
        folds = {}
        for r in first['records']:
            folds.setdefault(r['edge']['source_decision'], set()).add(r['fold'])
            self.assertEqual(r['record_hash'], common.canonical_hash({k: v for k, v in r.items() if k != 'record_hash'}))
        self.assertTrue(all(len(v) == 1 for v in folds.values()))

    def test_two_per_cell_and_inverse_probability_are_not_top_k(self):
        edge_path = self.run / 'edges/citation_edges.csv.gz'
        edges = [r for _, r in rows(edge_path)]
        documents = [r for _, r in rows(self.paths['documents'])]
        for n in range(12):
            src = f'SCC_extra{n}'
            edges.append({**edges[0], 'source_decision': src})
            documents.append({**documents[0], 'source_id': src, 'corpus_row': str(n + 10)})
        write_csv(edge_path, EDGE_FIELDS, edges)
        write_csv(Path(self.paths['documents']), DOCUMENT_FIELDS, documents)
        result = sample.stratified_sample(self.source(), seed=31415)
        cell = next(c for c in result['cells'] if c['N_cell'] >= 12)
        chosen = [r for r in result['records'] if r['cell_id'] == cell['cell_id']]
        self.assertEqual(len(chosen), 2)
        self.assertEqual(chosen[0]['pi'], 2 / cell['N_cell'])
        self.assertEqual(result['frame_N'], 18)
        self.assertLess(result['sample_n'], result['frame_N'])

    def test_citing_document_date_not_reporter_year_defines_era(self):
        result = sample.stratified_sample(self.source())
        modern = [r for r in result['records'] if r['edge']['source_decision'] == 'SCC_2000scc1']
        self.assertTrue(modern)
        self.assertTrue(all(r['stratum']['citing_judgment_era'] == '2000+' for r in modern))
        self.assertTrue(all('1990' not in r['stratum']['citing_judgment_era'] for r in modern))

    def test_evidence_only_uses_counted_mentions(self):
        result = sample.stratified_sample(self.source())
        r = next(r for r in result['records'] if r['edge']['source_decision'] == 'SCC_2000scc1'
                 and r['edge']['resolved_cited_case'] == 'XC-G000001')
        evidence = r['evidence']
        self.assertEqual(evidence['candidate']['candidate_id'], 'SCC:0:fixture')
        self.assertEqual(evidence['candidate']['arbitration_status'], 'counted')
        self.assertEqual(evidence['span']['start'], len('判决😀 Alpha mentions '))
        self.assertIn('ledger_logical_sha256', evidence['candidate'])

    def test_source_mutation_during_generation_is_rejected(self):
        source = self.source()
        real = sample.locate_evidence
        def changing(*args, **kwargs):
            result = real(*args, **kwargs)
            self.selected.write_bytes(self.selected.read_bytes() + b'changed')
            return result
        with mock.patch.object(sample, 'locate_evidence', side_effect=changing):
            with self.assertRaisesRegex(ValueError, 'Source changed'):
                sample.stratified_sample(source)

    def test_output_budget_and_source_overwrite_fail_closed(self):
        source = self.source()
        with self.assertRaises(ValueError):
            common.write_bounded_json(self.run / 'review.json', {}, source=source)
        with self.assertRaises(ValueError):
            common.write_bounded_json(self.base / 'oversize.json', {'value': 'x' * common.MAX_JSON_BYTES})
        self.assertFalse((self.base / 'oversize.json').exists())

    def test_running_source_cannot_supply_review_frame(self):
        p = self.run / 'run_manifest.json'
        m = json.loads(p.read_text())
        m['status'] = 'running'
        p.write_text(json.dumps(m), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'complete'):
            common.open_source(run=self.run, documents=self.paths['documents'])

    def test_formal_database_mode_is_read_only_and_not_copied(self):
        source = self.source()
        # Persist only this six-edge synthetic in-memory fixture, never a user DB.
        path = self.base / 'small_formal_fixture.db'
        destination = sqlite3.connect(path)
        source.db.backup(destination)
        destination.execute('CREATE TABLE runs(run_id TEXT,source_directory TEXT,input_fingerprint TEXT,manifest_json TEXT,imported_at TEXT,status TEXT)')
        destination.execute('CREATE TABLE artifacts(run_id TEXT,relative_path TEXT,sha256 TEXT,row_count INTEGER)')
        destination.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)', (source.run_id, str(self.run),
            source.manifest['input_identity']['fingerprint'], json.dumps(source.manifest), '2026-10-14', 'ready'))
        for relative in ('select_out/selected.csv', 'edges/citation_edges.csv'):
            destination.execute('INSERT INTO artifacts VALUES(?,?,?,?)',
                                (source.run_id, relative, common.artifact_digest(self.run / relative), 6))
        destination.commit()
        destination.close()
        before = path.read_bytes()
        db_source = common.open_source(db=path)
        self.addCleanup(db_source.close)
        result = sample.stratified_sample(db_source)
        self.assertEqual(result['frame_N'], 6)
        self.assertEqual(path.read_bytes(), before)
        with self.assertRaises(sqlite3.OperationalError):
            db_source.db.execute('DELETE FROM citation_edges')
        self.assertEqual(list(self.base.glob('*formal*.db')), [path])


if __name__ == '__main__':
    unittest.main()
