"""Offline fixtures for hash-bound human/model labels, coverage and weights."""
import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.quality import labels
from tools.quality.common import canonical_hash


class LabelsTests(unittest.TestCase):
    def setUp(self):
        # Redirected Windows AppContainer temp can reject atomic rename;
        # these fixtures use the writable checkout like real review outputs.
        self.temp = tempfile.TemporaryDirectory(prefix='.quality-label-test-',
                                                 dir=Path(__file__).resolve().parents[3])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.samples_path = self.root/'samples.json'
        self.csv_path = self.root/'labels.csv'
        self.output_path = self.root/'labels.json'
        self.raw_dir = self.root/'raw_run'
        self.raw_dir.mkdir()
        records = []
        for sid, cell, N, n, fold in [('a1', 'A', 100, 2, 'train'), ('a2', 'A', 100, 2, 'holdout'),
                                     ('b1', 'B', 2, 2, 'train'), ('b2', 'B', 2, 2, 'holdout')]:
            rec = {'sample_id': sid, 'run_id': 'r', 'frame_id': 'frame', 'cell_id': cell,
                   'N_cell': N, 'n_cell': n, 'pi': n/N, 'fold': fold,
                   'edge': {'source_decision': 'SCC_'+sid, 'resolved_cited_case': 'g'+sid},
                   'source_locator': {'path': str(self.raw_dir/'edges.csv.gz'), 'record': len(records)+2},
                   'source_sha256': 'a'*64}
            rec['record_hash'] = canonical_hash(rec)
            records.append(rec)
        self.samples = {'schema': 'quality_sample_v1', 'run_id': 'r', 'frame_id': 'frame', 'frame_N': 102,
                        'seed': 20261014, 'cells': [{'cell_id': 'A', 'N_cell': 100, 'n_cell': 2},
                                                 {'cell_id': 'B', 'N_cell': 2, 'n_cell': 2}],
                        'source_provenance': {'run_directory': str(self.raw_dir), 'corpus_directory': None, 'db_path': None},
                        'records': records}
        self.save_samples()
        labels.template(self.samples_path, self.csv_path)

    def save_samples(self):
        self.samples_path.write_text(json.dumps(self.samples, ensure_ascii=False), encoding='utf-8')

    def read_csv(self):
        with self.csv_path.open(encoding='utf-8', newline='') as stream:
            return list(csv.DictReader(stream))

    def write_csv(self, rows):
        with self.csv_path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=labels.CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def manual(self, row, **dimensions):
        row.update(dimensions, annotator='Reviewer A', label_method='manual',
                   annotated_at='2026-10-14T12:00:00-04:00', notes='Checked cited text')
        return row

    def model(self, row, **dimensions):
        row.update(dimensions, annotator='gpt-review-fixture', label_method='model',
                   annotated_at='2026-10-15T12:00:00-04:00',
                   notes='Checked original source span and target member citations; fixture evidence a1')
        return row

    def imported(self, rows):
        self.write_csv(rows)
        return labels.import_labels(self.samples_path, self.csv_path, self.output_path)

    def test_template_retains_stable_identity_and_blank_manual_columns(self):
        rows = self.read_csv()
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]['record_hash'], self.samples['records'][0]['record_hash'])
        self.assertTrue(all(row[field] == '' for row in rows for field in labels.MANUAL_FIELDS))

    def test_wholly_unlabelled_rows_are_allowed_without_calibration_claim(self):
        result = self.imported(self.read_csv())
        self.assertEqual(result['labelled_records'], 0)
        evaluation = labels.evaluate(self.samples_path, self.output_path)
        self.assertEqual(evaluation['label_method'], 'unlabelled')
        self.assertFalse(evaluation['population_inference_allowed'])
        self.assertFalse(evaluation['dd_or_weight_updates'])
        self.assertEqual(evaluation['population_calibration_status'], 'not_calibrated')
        self.assertEqual(evaluation['sample_coverage']['joint_edge_validity']['unlabelled_n'], 4)
        self.assertIsNone(evaluation['sample_coverage']['joint_edge_validity']['raw_verified_rate'])
        for fold in evaluation['folds'].values():
            self.assertEqual(fold['sampled_n'], 2)
            self.assertIsNone(fold['dimensions']['case_mention']['raw_verified_rate'])
            self.assertEqual(fold['dimensions']['case_mention']['sample_label_completion'], 0)

    def test_weighted_partial_labels_keep_sample_denominator_and_holdout_separate(self):
        rows = self.read_csv()
        self.manual(rows[0], case_mention='yes', judgment_identity='correct', treatment_role='procedural')
        self.manual(rows[1], case_mention='unverifiable', treatment_role='unknown')
        self.manual(rows[2], case_mention='no')
        self.imported(rows)
        result = labels.evaluate(self.samples_path, self.output_path)
        train = result['folds']['train']['dimensions']
        self.assertAlmostEqual(train['case_mention']['raw_verified_rate'], .5)
        self.assertAlmostEqual(train['case_mention']['weighted_verified_rate'], 50/51)
        self.assertEqual(train['judgment_identity']['sample_label_completion'], .5)
        self.assertEqual(train['judgment_identity']['weighted_verified_rate'], 1)
        holdout = result['folds']['holdout']['dimensions']
        self.assertEqual(holdout['case_mention']['unverifiable_n'], 1)
        self.assertEqual(holdout['case_mention']['unlabelled_n'], 1)
        self.assertIsNone(holdout['case_mention']['weighted_verified_rate'])
        self.assertEqual(holdout['treatment_role']['unknown_n'], 1)
        self.assertNotIn('raw_verified_rate', train['treatment_role'])
        self.assertEqual(train['treatment_role']['interpretation'], 'descriptive_categories_not_precision')
        self.assertFalse(result['all_dimensions_verified'])

    def test_unknown_treatment_and_unverifiable_origin_remain_separate(self):
        rows = self.read_csv()
        self.manual(rows[0], treatment_role='unknown', origin='unverifiable')
        self.imported(rows)
        dims = labels.evaluate(self.samples_path, self.output_path)['folds']['train']['dimensions']
        self.assertEqual(dims['treatment_role']['unknown_n'], 1)
        self.assertEqual(dims['origin']['unverifiable_n'], 1)
        self.assertIsNone(dims['origin']['weighted_verified_rate'])

    def test_partial_dimension_requires_reviewer_provenance(self):
        rows = self.read_csv()
        rows[0]['judgment_identity'] = 'correct'
        with self.assertRaisesRegex(ValueError, 'annotator'):
            self.imported(rows)
        self.assertFalse(self.output_path.exists())

    def test_explicit_model_labels_keep_provenance_and_weighted_partial_coverage(self):
        rows = self.read_csv()
        self.model(rows[0], case_mention='yes', judgment_identity='correct', treatment_role='mentioned')
        self.model(rows[1], case_mention='unverifiable', judgment_identity='unknown')
        self.model(rows[2], case_mention='no', judgment_identity='incorrect')
        document = self.imported(rows)
        self.assertEqual(document['label_method'], 'model')
        self.assertEqual(document['label_counts_by_method'], {'manual': 0, 'model': 3})
        self.assertEqual(document['records'][0]['annotator'], 'gpt-review-fixture')
        report = labels.evaluate(self.samples_path, document)
        self.assertEqual(report['manual_reviewed_n'], 0)
        self.assertEqual(report['model_reviewed_n'], 3)
        train = report['folds']['train']['dimensions']['case_mention']
        self.assertEqual(train['raw_verified_rate'], .5)
        self.assertAlmostEqual(train['weighted_verified_rate'], 50/51)
        holdout = report['by_label_method']['model']['folds']['holdout']['dimensions']['case_mention']
        self.assertEqual(holdout['sampled_n'], 2)
        self.assertEqual(holdout['unverifiable_n'], 1)
        self.assertEqual(holdout['unlabelled_n'], 1)
        self.assertIsNone(holdout['raw_verified_rate'])
        human = report['by_label_method']['manual']['sample_coverage']['dimensions']['case_mention']
        self.assertEqual(human['sampled_n'], 4)
        self.assertEqual(human['labelled_n'], 0)
        self.assertIsNone(human['raw_verified_rate'])
        self.assertFalse(report['population_inference_allowed'])
        self.assertEqual(report['population_calibration_status'], 'not_calibrated')
        self.assertTrue(any('not independent human validation' in text for text in report['warnings']))

    def test_unknown_and_blank_label_methods_are_rejected(self):
        for method in ('', 'automatic', 'human', 'mixed'):
            with self.subTest(method=method):
                rows = self.read_csv()
                self.manual(rows[0], case_mention='yes')
                rows[0]['label_method'] = method
                with self.assertRaisesRegex(ValueError, 'label_method'):
                    self.imported(rows)

    def test_model_labels_require_identity_timestamp_and_rationale(self):
        for field, value, error in [('annotator', '', 'annotator'),
                                    ('annotated_at', 'tomorrow', 'ISO'),
                                    ('notes', '', 'rationale')]:
            with self.subTest(field=field):
                rows = self.read_csv()
                self.model(rows[0], case_mention='yes')
                rows[0][field] = value
                with self.assertRaisesRegex(ValueError, error):
                    self.imported(rows)

    def test_mixed_review_methods_have_separate_rates_and_no_pooled_precision(self):
        rows = self.read_csv()
        self.manual(rows[0], case_mention='yes')
        self.model(rows[2], case_mention='no')
        report = labels.evaluate(self.samples_path, self.imported(rows))
        self.assertEqual(report['label_method'], 'mixed')
        self.assertEqual(report['label_counts_by_method'], {'manual': 1, 'model': 1})
        combined = report['sample_coverage']['dimensions']['case_mention']
        self.assertEqual(combined['verified_n'], 2)
        self.assertEqual(combined['sample_label_completion'], .5)
        self.assertIsNone(combined['raw_verified_rate'])
        self.assertIsNone(combined['weighted_verified_rate'])
        self.assertEqual(combined['rate_scope'], 'mixed_review_methods_no_pooled_rate')
        self.assertIsNone(report['sample_coverage']['joint_edge_validity']['raw_verified_rate'])
        self.assertIsNone(report['sample_coverage']['joint_edge_validity']['sample_correct_fraction_bounds']['lower'])
        self.assertIsNone(report['folds']['train']['dimensions']['case_mention']['raw_verified_rate'])
        human = report['by_label_method']['manual']['sample_coverage']['dimensions']['case_mention']
        model = report['by_label_method']['model']['sample_coverage']['dimensions']['case_mention']
        self.assertEqual(human['raw_verified_rate'], 1)
        self.assertEqual(model['weighted_verified_rate'], 0)
        self.assertEqual(human['sampled_n'], 4)
        self.assertEqual(model['sample_verified_coverage'], .25)

    def test_joint_edge_validity_uses_each_sample_once_and_keeps_unresolved_weight(self):
        rows = self.read_csv()
        self.model(rows[0], case_mention='yes', judgment_identity='correct')
        self.model(rows[1], case_mention='no', judgment_identity='unknown')
        self.model(rows[2], case_mention='yes', judgment_identity='unverifiable')
        self.model(rows[3], case_mention='unknown', judgment_identity='correct')
        report = labels.evaluate(self.samples_path, self.imported(rows))
        joint = report['sample_coverage']['joint_edge_validity']
        self.assertEqual(joint['sampled_n'], 4)
        self.assertEqual(joint['correct_n'], 1)
        self.assertEqual(joint['incorrect_n'], 1)
        self.assertEqual(joint['unknown_n'], 1)
        self.assertEqual(joint['unverifiable_n'], 1)
        self.assertEqual(joint['unresolved_n'], 2)
        self.assertEqual(joint['raw_verified_rate'], .5)
        self.assertEqual(joint['weighted_verified_rate'], .5)
        self.assertEqual(joint['sample_verified_coverage'], .5)
        self.assertAlmostEqual(joint['inverse_pi_verified_coverage'], 100/102)
        self.assertEqual(joint['sample_correct_fraction_bounds'], {'lower': .25, 'upper': .75})
        self.assertAlmostEqual(joint['inverse_pi_correct_fraction_bounds']['lower'], 50/102)
        self.assertAlmostEqual(joint['inverse_pi_correct_fraction_bounds']['upper'], 52/102)
        self.assertEqual(report['folds']['train']['joint_edge_validity']['raw_verified_rate'], 1)
        self.assertEqual(report['folds']['holdout']['joint_edge_validity']['raw_verified_rate'], 0)
        self.assertEqual(report['by_label_method']['model']['sample_coverage']['joint_edge_validity'], joint)

    def test_document_review_method_and_counts_must_match_record_provenance(self):
        rows = self.read_csv()
        self.model(rows[0], case_mention='yes')
        document = self.imported(rows)
        for field, value in [('label_method', 'manual'),
                             ('label_counts_by_method', {'manual': 1, 'model': 0})]:
            with self.subTest(field=field):
                altered = copy.deepcopy(document)
                altered[field] = value
                altered['content_hash'] = canonical_hash({k: v for k, v in altered.items() if k != 'content_hash'})
                with self.assertRaisesRegex(ValueError, 'method'):
                    labels.evaluate(self.samples_path, altered)

    def test_legacy_manual_document_without_method_counts_remains_readable(self):
        rows = self.read_csv()
        self.manual(rows[0], case_mention='yes')
        document = self.imported(rows)
        document.pop('label_counts_by_method')
        document['content_hash'] = canonical_hash({k: v for k, v in document.items() if k != 'content_hash'})
        report = labels.evaluate(self.samples_path, document)
        self.assertEqual(report['label_method'], 'manual')
        self.assertEqual(report['manual_reviewed_n'], 1)
        self.assertEqual(report['model_reviewed_n'], 0)
        self.assertEqual(report['sample_coverage']['dimensions']['case_mention']['raw_verified_rate'], 1)

    def test_model_labels_still_bind_to_original_run_frame_and_record_hash(self):
        for field in ('run_id', 'frame_id', 'record_hash'):
            with self.subTest(field=field):
                rows = self.read_csv()
                self.model(rows[0], case_mention='yes')
                rows[0][field] = 'changed'
                with self.assertRaisesRegex(ValueError, 'identity mismatch'):
                    self.imported(rows)

    def test_bad_timestamp_is_rejected(self):
        rows = self.read_csv()
        self.manual(rows[0], origin='correct')
        rows[0]['annotated_at'] = 'tomorrow'
        with self.assertRaisesRegex(ValueError, 'ISO'):
            self.imported(rows)

    def test_invalid_enum_is_rejected(self):
        rows = self.read_csv()
        self.manual(rows[0], treatment_role='approved')
        with self.assertRaisesRegex(ValueError, 'Invalid treatment_role'):
            self.imported(rows)

    def test_unknown_identity_and_origin_do_not_enter_verified_denominators(self):
        rows = self.read_csv()
        self.manual(rows[0], case_mention='unknown', judgment_identity='unknown', origin='unknown')
        imported = self.imported(rows)
        report = labels.evaluate(self.samples_path, imported)
        for name in ('case_mention', 'judgment_identity', 'origin'):
            dimension = report['sample_coverage']['dimensions'][name]
            self.assertEqual(dimension['unknown_n'], 1)
            self.assertEqual(dimension['verified_n'], 0)
            self.assertIsNone(dimension['weighted_verified_rate'])

    def test_duplicate_and_unexpected_sample_ids_are_rejected(self):
        rows = self.read_csv()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.imported(rows + [rows[0]])
        rows[0]['sample_id'] = 'not_in_frame'
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            self.imported(rows)

    def test_changed_record_hash_in_csv_is_rejected(self):
        rows = self.read_csv()
        rows[0]['record_hash'] = 'b'*64
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            self.imported(rows)

    def test_corrupted_sample_record_is_rejected_before_template(self):
        self.samples['records'][0]['edge']['source_decision'] = 'wrong'
        self.save_samples()
        with self.assertRaisesRegex(ValueError, 'record hash mismatch'):
            labels.template(self.samples_path, self.root/'second.csv')

    def test_changed_sampling_probability_even_with_new_record_hash_is_rejected(self):
        rec = self.samples['records'][0]
        rec['pi'] = 1
        rec['record_hash'] = canonical_hash({k: v for k, v in rec.items() if k != 'record_hash'})
        self.save_samples()
        with self.assertRaisesRegex(ValueError, 'inclusion|Inclusion'):
            labels.template(self.samples_path, self.root/'second.csv')

    def test_imported_label_document_tampering_is_rejected(self):
        rows = self.read_csv()
        self.manual(rows[0], case_mention='yes')
        document = self.imported(rows)
        document['records'][0]['case_mention'] = 'no'
        with self.assertRaisesRegex(ValueError, 'document hash mismatch'):
            labels.evaluate(self.samples_path, document)

    def test_label_record_tampering_remains_detected_if_document_hash_is_resealed(self):
        rows = self.read_csv()
        self.manual(rows[0], case_mention='yes')
        document = self.imported(rows)
        document['records'][0]['case_mention'] = 'no'
        document['content_hash'] = canonical_hash({k: v for k, v in document.items() if k != 'content_hash'})
        with self.assertRaisesRegex(ValueError, 'record hash mismatch'):
            labels.evaluate(self.samples_path, document)

    def test_source_input_and_source_directory_overwrites_are_refused(self):
        before = self.samples_path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            labels.template(self.samples_path, self.samples_path)
        with self.assertRaisesRegex(ValueError, 'outside source'):
            labels.template(self.samples_path, self.raw_dir/'manual.csv')
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            labels.import_labels(self.samples_path, self.csv_path, self.csv_path)
        self.assertEqual(self.samples_path.read_bytes(), before)

    def test_source_evidence_path_overwrite_is_refused_without_directory_metadata(self):
        self.samples.pop('source_provenance')
        self.save_samples()
        with self.assertRaisesRegex(ValueError, 'evidence source'):
            labels.template(self.samples_path, self.raw_dir/'edges.csv.gz')

    def test_csv_byte_budget_rejects_oversize_without_touching_output(self):
        self.csv_path.write_bytes(b'x'*(labels.MAX_CSV_BYTES+1))
        self.output_path.write_text('existing output', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'byte budget'):
            labels.import_labels(self.samples_path, self.csv_path, self.output_path)
        self.assertEqual(self.output_path.read_text(encoding='utf-8'), 'existing output')

    def test_subset_csv_still_uses_all_sample_records_as_coverage_denominator(self):
        rows = self.read_csv()
        self.manual(rows[0], case_mention='yes')
        self.imported(rows[:1])
        detail = labels.evaluate(self.samples_path, self.output_path)['sample_coverage']['dimensions']['case_mention']
        self.assertEqual(detail['sampled_n'], 4)
        self.assertEqual(detail['labelled_n'], 1)
        self.assertEqual(detail['sample_label_completion'], .25)

    def test_expanded_json_budget_failure_preserves_previous_output_atomically(self):
        base = self.samples['records'][0]
        records = []
        for index in range(100):
            rec = copy.deepcopy(base)
            rec.update(sample_id='large%d' % index, cell_id='A', N_cell=100, n_cell=100, pi=1.0)
            rec['record_hash'] = canonical_hash({k: v for k, v in rec.items() if k != 'record_hash'})
            records.append(rec)
        self.samples.update(frame_N=100, cells=[{'cell_id': 'A', 'N_cell': 100, 'n_cell': 100}], records=records)
        self.save_samples()
        labels.template(self.samples_path, self.csv_path)
        rows = self.read_csv()
        for row in rows:
            self.manual(row, case_mention='yes')
            row['notes'] = 'x\n'*7000
        self.write_csv(rows)
        self.assertLess(self.csv_path.stat().st_size, labels.MAX_CSV_BYTES)
        self.output_path.write_text('prior receipt', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'JSON output exceeds'):
            labels.import_labels(self.samples_path, self.csv_path, self.output_path)
        self.assertEqual(self.output_path.read_text(encoding='utf-8'), 'prior receipt')


if __name__ == '__main__':
    unittest.main()
