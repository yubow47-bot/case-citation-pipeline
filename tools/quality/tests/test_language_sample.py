"""Original-field French domains, independent draws and preserved parent folds."""
import json
from pathlib import Path
import unittest
from unittest import mock
import pyarrow as pa
import pyarrow.parquet as pq

from tools.quality import common, language_sample, labels, sample
from tools.quality.tests import test_fr_fallback as fr_fixture


class FrenchSupplementTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fr_fixture.FrenchEvidenceTests('test_fr_only_metadata_source_and_window_are_verified_in_fr_fields')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.base = self.fixture.base
        self.budget = mock.patch.object(language_sample, 'preflight', return_value={'fixture': True})
        self.budget_mock = self.budget.start()
        self.addCleanup(self.budget.stop)

    def parent(self, source, seed=20261014):
        result = sample.stratified_sample(source, seed=seed)
        path = self.base / 'old_quality/samples.json'
        common.write_bounded_json(path, result)
        return path, result

    def supplement(self, source, path, seed=20261015):
        return language_sample.french_supplement(source, path, seed)

    def test_actual_fr_field_and_population_ignore_available_unselected_translation(self):
        french_id, _ = self.fixture.configure('SCC', fr_only=True)
        english_id, _ = self.fixture.configure('ONCA')
        source = self.fixture.source()
        parent_path, parent = self.parent(source)
        before = parent_path.read_bytes()
        result = self.supplement(source, parent_path)
        expected_n = source.db.execute('SELECT COUNT(*) FROM citation_edges WHERE source_decision=?', (french_id,)).fetchone()[0]
        self.assertGreater(expected_n, 0)
        self.assertEqual(result['parent_frame_N'], 6)
        self.assertEqual(result['frame_N'], expected_n)
        self.assertEqual(sum(c['N_cell'] for c in result['cells']), expected_n)
        self.assertNotEqual(result['frame_id'], parent['frame_id'])
        self.assertEqual(result['parent_samples_hash'], common.canonical_hash(parent))
        self.assertEqual(result['parent_frame_id'], parent['frame_id'])
        self.assertEqual(parent_path.read_bytes(), before)
        for record in result['records']:
            self.assertEqual(record['edge']['source_decision'], french_id)
            self.assertNotEqual(record['edge']['source_decision'], english_id)
            self.assertEqual(record['stratum']['selected_text_language'], 'fr')
            self.assertEqual(record['language_membership']['text_field'], 'unofficial_text_fr')
            if record['evidence']['status'] == 'original_text_verified':
                self.assertEqual(record['evidence']['field_selection']['text_field'], 'unofficial_text_fr')
            self.assertEqual(record['pi'], record['n_cell'] / record['N_cell'])
        # The fixture deliberately lacks a counted ledger span for its second
        # target. It remains in the probability sample, without a fake quote.
        self.assertTrue(any(r['evidence']['status'] == 'candidate_not_found' for r in result['records']))
        self.budget_mock.assert_called_once_with(common.ROOT, 8 * 1024**2)

    def test_fr_body_with_en_metadata_keeps_english_primary_id(self):
        french_id, _ = self.fixture.configure('SCC', text_only=True)
        source = self.fixture.source()
        path, _ = self.parent(source)
        result = self.supplement(source, path)
        self.assertEqual(french_id, 'SCC_2000scc1')
        self.assertTrue(result['records'])
        self.assertTrue(all(r['edge']['source_decision'] == french_id for r in result['records']))
        verified = [r for r in result['records'] if r['evidence']['status'] == 'original_text_verified']
        self.assertTrue(verified)
        self.assertTrue(all(r['evidence']['field_selection']['citation_field'] == 'citation_en' for r in verified))

    def test_parent_source_fold_is_inherited_despite_new_selection_seed(self):
        self.fixture.configure('SCC', text_only=True)
        source = self.fixture.source()
        path, parent = self.parent(source, seed=123)
        first = self.supplement(source, path, seed=456)
        second = self.supplement(source, path, seed=456)
        self.assertEqual(first['records'], second['records'])
        self.assertEqual(first['fold_seed'], 123)
        parent_folds = {r['edge']['source_decision']: r['fold'] for r in parent['records']}
        for r in first['records']:
            self.assertEqual(r['fold'], parent_folds[r['edge']['source_decision']])
            self.assertEqual(r['record_hash'], common.canonical_hash({k: v for k, v in r.items() if k != 'record_hash'}))

    def test_legacy_policy_does_not_promote_available_fr_text_into_population(self):
        self.fixture.configure('SCC', policy=None, text_only=True)
        self.fixture.configure('ONCA', policy=None)
        source = self.fixture.source()
        path, _ = self.parent(source)
        result = self.supplement(source, path)
        self.assertEqual(result['frame_N'], 0)
        self.assertEqual(result['sample_n'], 0)
        self.assertEqual(result['language_frame']['eligible_source_ids'], 0)
        self.assertEqual(result['parent_frame_N'], 6)

    def test_corpus_metadata_mismatch_refuses_language_claim(self):
        self.fixture.configure('SCC', text_only=True)
        source = self.fixture.source()
        path, _ = self.parent(source)
        source.db.execute('PRAGMA query_only=OFF')
        source.db.execute("UPDATE documents SET name='caller invented' WHERE court='SCC' AND corpus_row=0")
        source.db.execute('PRAGMA query_only=ON')
        with self.assertRaisesRegex(ValueError, 'original document metadata'):
            self.supplement(source, path)

    def test_mixed_language_duplicate_source_id_is_explicitly_excluded(self):
        self.fixture.configure('SCC', text_only=True)
        path = self.fixture.corpus / 'SCC.parquet'
        originals = pq.read_table(path).to_pylist()
        originals[1].update(citation_en=originals[0]['citation_en'], unofficial_text_en='English primary body')
        pq.write_table(pa.Table.from_pylist(originals), path, row_group_size=2)
        manifest_path = self.fixture.run / 'run_manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['input_identity']['files']['corpus/SCC.parquet'] = common.file_hash(path)
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        source = self.fixture.source()
        eligible, identity, _ = language_sample.original_language_census(source)
        self.assertNotIn('SCC_2000scc1', eligible)
        self.assertEqual(identity['counts']['source_ids/ambiguous_duplicate_rows'], 1)
        parent, _ = self.parent(source)
        result = self.supplement(source, parent)
        self.assertEqual(result['frame_N'], 0)

    def test_changed_corpus_and_memory_budget_refuse(self):
        self.fixture.configure('SCC', text_only=True)
        source = self.fixture.source()
        with self.assertRaisesRegex(ValueError, 'memory budget'):
            language_sample.original_language_census(source, max_source_ids=0)
        corpus = self.fixture.corpus / 'SCC.parquet'
        corpus.write_bytes(corpus.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'recorded input'):
            language_sample.original_language_census(source)

    def test_other_parent_frame_and_invalid_parent_fold_refuse(self):
        self.fixture.configure('SCC', text_only=True)
        source = self.fixture.source()
        path, parent = self.parent(source)
        row = parent['records'][0]
        row['fold'] = 'holdout' if row['fold'] == 'train' else 'train'
        row['record_hash'] = common.canonical_hash({k: v for k, v in row.items() if k != 'record_hash'})
        common.write_bounded_json(path, parent)
        with self.assertRaisesRegex(ValueError, 'source-v1 fold'):
            self.supplement(source, path)
        path, parent = self.parent(source)
        parent['frame_id'] = 'other-frame'
        for row in parent['records']:
            row['frame_id'] = 'other-frame'
            row['record_hash'] = common.canonical_hash({k: v for k, v in row.items() if k != 'record_hash'})
        common.write_bounded_json(path, parent)
        with self.assertRaisesRegex(ValueError, 'same source frame'):
            self.supplement(source, path)

    def test_empty_manual_labels_are_not_calibration_and_old_files_are_unchanged(self):
        self.fixture.configure('SCC', text_only=True)
        source = self.fixture.source()
        path, _ = self.parent(source)
        old_labels = path.parent / 'labels.json'
        old_labels.write_text('{"unique_old_label":"preserve"}', encoding='utf-8')
        before = {p: p.read_bytes() for p in (path, old_labels)}
        result = self.supplement(source, path)
        out = self.base / 'new_quality'
        samples = out / 'samples.json'
        template = out / 'manual_labels.csv'
        imported = out / 'labels.json'
        common.write_bounded_json(samples, result)
        labels.template(samples, template)
        payload = labels.import_labels(samples, template, imported)
        evaluation = labels.evaluate(samples, imported)
        self.assertEqual(payload['labelled_records'], 0)
        self.assertEqual(evaluation['frame_N'], result['frame_N'])
        self.assertEqual(evaluation['population_calibration_status'], 'not_calibrated')
        self.assertFalse(evaluation['population_inference_allowed'])
        self.assertTrue(all(v.get('raw_verified_rate') is None for v in evaluation['sample_coverage']['dimensions'].values()))
        self.assertEqual({p: p.read_bytes() for p in before}, before)


if __name__ == '__main__':
    unittest.main()
