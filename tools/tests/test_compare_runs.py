"""Structural A/B comparisons, including reorder/loss/split cases; tiny offline fixtures."""
import copy
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import io

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import compare_runs as compare


class CompareRunsTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[2]/'implementation/round3_tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.old, self.new = self.root/'old', self.root/'new'
        for run in (self.old, self.new):
            run.mkdir()
            self.manifest(run)
        self.candidates = [self.candidate(10), self.candidate(30)]
        members = [self.member('a', 'OLD-1', 5, True)]
        for run in (self.old, self.new):
            self.write(run, 'extract_out/candidates.csv', self.candidates)
            self.write(run, 'merge_out/SCC/merged.csv', [self.merged('a', 5, 5)])
            self.write(run, 'select_out/selected.csv', members)

    def manifest(self, run, status='complete', corpus_hash='a'*64):
        value = {'status': status, 'input_identity_verified_unchanged': True,
                 'params': {'courts': ['SCC']},
                 'input_identity': {'fingerprint': run.name, 'files': {'corpus/SCC.parquet': corpus_hash}}}
        (run/'run_manifest.json').write_text(json.dumps(value), encoding='utf-8')

    def candidate(self, start, row=0):
        return {'candidate_id': f'SCC:{row}:{start}:{start+10}:shape', 'corpus_row_index': str(row),
                'source_decision_citation': 'SCC_2020scc1', 'raw_string': f'2000 SCC {start}',
                'match_start_offset': str(start), 'match_end_offset': str(start+10),
                'match_span': f'{start}:{start+10}', 'parse_signature': f'shape|page={start}', 'shape_name': 'shape'}

    def member(self, key, gid, dd, kept, country='CA', primary=True):
        return {'court': 'SCC', 'merge_key': key, 'merged_group_id': gid, 'is_primary': str(primary).lower(),
                'distinct_decisions_count': str(dd), 'kept': str(kept).lower(),
                'group_foreign_status': 'DOMESTIC_CA' if country == 'CA' else 'FOREIGN' if country else 'UNDETERMINED',
                'group_origin_country': country, 'group_origin_status': 'DETERMINED' if country else 'UNDETERMINED',
                'group_origin_basis': 'fixture', 'group_origin_evidence_ids': '', 'case_name_modal': key}

    def merged(self, key, occurrence, dd):
        return {'merge_key': key, 'occurrence_count': str(occurrence), 'distinct_decisions_count': str(dd),
                'citation_kind': 'neutral', 'canonical_string': key}

    def write(self, run, logical, records):
        path = run/logical
        path.parent.mkdir(parents=True, exist_ok=True)
        zipped = run == self.new
        actual = Path(str(path)+'.gz') if zipped else path
        opener = gzip.open if zipped else open
        with opener(actual, 'wt', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)

    def test_same_raw_rows_plain_vs_gzip_preserve_identity_and_membership(self):
        report = compare.compare(self.old, self.new)
        candidates = report['candidates']
        self.assertTrue(candidates['original_candidates_preserved_in_order'])
        self.assertTrue(candidates['ordered_identity_equal'])
        self.assertEqual((candidates['lost_rows'], candidates['same_id_changed_rows'], candidates['added_rows']), (0, 0, 0))
        self.assertEqual(report['selected_identity']['components']['one_to_one_same_membership_components'], 1)
        old_art = report['old']['artifacts'][0]
        new_art = report['new']['artifacts'][0]
        self.assertEqual(old_art['content_sha256'], new_art['content_sha256'])
        self.assertNotEqual(old_art['physical_sha256'], new_art['physical_sha256'])
        self.assertFalse((self.new/'extract_out/candidates.csv').exists())

    def test_local_group_id_renumbering_is_not_an_identity_change(self):
        self.write(self.new, 'select_out/selected.csv', [self.member('a', 'COMPLETELY-DIFFERENT-ID', 5, True)])
        report = compare.compare(self.old, self.new)['selected_identity']
        self.assertEqual(report['components']['one_to_one_same_membership_components'], 1)
        self.assertEqual(report['components']['split_components'], 0)
        self.assertEqual(report['examples'], [])

    def test_every_merged_input_member_is_accounted_for_in_selected(self):
        report = compare.compare(self.old, self.new)
        for side in ('old', 'new'):
            result = report['selected_identity']['merged_input_membership_coverage'][side]
            self.assertEqual(result['status'], 'passed')
            self.assertEqual(result['merged_input_keys_missing_from_selected'], 0)
            self.assertEqual(result['selected_keys_without_merged_input'], 0)

    def test_internal_group_consistency_cannot_hide_dropped_input_member(self):
        self.write(self.new, 'merge_out/SCC/merged.csv', [self.merged('a', 5, 5), self.merged('dropped', 9, 9)])
        report = compare.compare(self.old, self.new)
        result = report['selected_identity']['merged_input_membership_coverage']['new']
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['merged_input_keys_missing_from_selected'], 1)
        self.assertEqual(result['missing_input_examples'][0]['merge_key'], 'dropped')
        self.assertTrue(any('source membership coverage failed' in warning for warning in report['warnings']))

    def test_selected_extra_member_is_not_accepted_as_input_coverage(self):
        self.write(self.new, 'select_out/selected.csv', [self.member('a', 'A', 5, True), self.member('invented', 'B', 2, False)])
        result = compare.compare(self.old, self.new)['selected_identity']['merged_input_membership_coverage']['new']
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['selected_keys_without_merged_input'], 1)
        self.assertEqual(result['extra_selected_examples'][0]['merge_key'], 'invented')

    def test_candidate_addition_within_a_document_does_not_fake_loss(self):
        self.write(self.new, 'extract_out/candidates.csv', [self.candidates[0], self.candidate(20), self.candidates[1]])
        result = compare.compare(self.old, self.new)['candidates']
        self.assertEqual(result['added_rows'], 1)
        self.assertEqual(result['lost_rows'], 0)
        self.assertTrue(result['original_candidates_preserved_in_order'])
        self.assertFalse(result['ordered_identity_equal'])

    def test_same_candidate_id_changed_parse_is_counted_and_not_certified(self):
        rows = copy.deepcopy(self.candidates)
        rows[0]['parse_signature'] = 'changed parse'
        self.write(self.new, 'extract_out/candidates.csv', rows)
        result = compare.compare(self.old, self.new)['candidates']
        self.assertEqual(result['same_id_changed_rows'], 1)
        self.assertEqual(result['changed_fields'], {'parse_signature': 1})
        self.assertFalse(result['original_candidates_preserved_in_order'])

    def test_removed_candidate_and_changed_offset_are_detected(self):
        row = copy.deepcopy(self.candidates[0])
        row['match_start_offset'] = '11'
        self.write(self.new, 'extract_out/candidates.csv', [row])
        result = compare.compare(self.old, self.new)['candidates']
        self.assertEqual(result['lost_rows'], 1)
        self.assertEqual(result['same_id_changed_rows'], 1)
        self.assertIn('match_start_offset', result['changed_fields'])

    def test_same_document_candidate_reorder_is_not_certified_as_preserved(self):
        self.write(self.new, 'extract_out/candidates.csv', list(reversed(self.candidates)))
        result = compare.compare(self.old, self.new)['candidates']
        self.assertEqual(result['lost_rows'], 0)
        self.assertEqual(result['same_id_changed_rows'], 0)
        self.assertEqual(result['documents_failing_legacy_ordered_subsequence'], 1)

    def test_duplicate_candidate_rows_are_counted_without_dictionary_loss(self):
        for run in (self.old, self.new):
            self.write(run, 'extract_out/candidates.csv', [self.candidates[0], self.candidates[0]])
        result = compare.compare(self.old, self.new)['candidates']
        self.assertEqual(result['old']['rows'], 2)
        self.assertEqual(result['same_document_duplicate_candidate_ids'], {'old': 1, 'new': 1})
        self.assertTrue(result['original_candidates_preserved_in_order'])

    def test_merged_count_addition_loss_and_existing_change_use_full_tables(self):
        self.write(self.old, 'merge_out/SCC/merged.csv', [self.merged('a', 5, 5), self.merged('lost', 3, 2)])
        self.write(self.new, 'merge_out/SCC/merged.csv', [self.merged('a', 7, 6), self.merged('fresh', 4, 4)])
        result = compare.compare(self.old, self.new)['merged']['courts']['SCC']
        self.assertEqual((result['added_keys'], result['lost_keys'], result['existing_keys_counts_changed']), (1, 1, 1))
        self.assertEqual(result['old_field_sums']['occurrence_count'], 8)
        self.assertEqual(result['new_field_sums']['occurrence_count'], 11)

    def test_case_name_support_is_a_ratio_not_a_count(self):
        for run in (self.old, self.new):
            row = self.merged('a', 5, 5)
            row['case_name_support'] = '0.0'
            self.write(run, 'merge_out/SCC/merged.csv', [row])
        result = compare.compare(self.old, self.new)['merged']['courts']['SCC']
        self.assertEqual(result['existing_keys_counts_changed'], 0)
        self.assertNotIn('case_name_support', result['old_field_sums'])

    def test_split_merge_dd_kept_origin_changes_are_membership_based(self):
        self.write(self.old, 'select_out/selected.csv', [self.member('a', 'AB', 10, True), self.member('b', 'AB', 10, True, primary=False),
            self.member('c', 'C', 6, True, country=''), self.member('d', 'D', 5, True), self.member('e', 'E', 6, True)])
        self.write(self.new, 'select_out/selected.csv', [self.member('a', 'A', 7, True), self.member('b', 'B', 4, False, country='US'),
            self.member('c', 'C2', 4, False, country='CA'), self.member('d', 'DE', 8, True), self.member('e', 'DE', 8, True, primary=False)])
        result = compare.compare(self.old, self.new)['selected_identity']
        self.assertEqual(result['components']['split_components'], 1)
        self.assertEqual(result['components']['merge_components'], 1)
        self.assertEqual(result['components']['one_to_one_dd_changed'], 1)
        self.assertEqual(result['components']['one_to_one_kept_changed'], 1)
        self.assertEqual(result['components']['one_to_one_origin_values_changed'], 1)
        self.assertEqual(result['old']['dd_sum'], 27)
        self.assertEqual(result['new']['dd_sum'], 23)
        self.assertEqual(result['stable_keys_shared'], 5)
        self.assertEqual(result['category_totals']['split']['group_count_delta'], 1)
        self.assertEqual(result['category_totals']['merge']['kept_count_delta'], -1)
        self.assertEqual(sum(item['kept_count_delta'] for item in result['category_totals'].values()),
                         result['new']['kept_groups']-result['old']['kept_groups'])

    def test_many_to_many_changes_are_not_mislabeled_simple_splits(self):
        self.write(self.old, 'select_out/selected.csv', [self.member('a', 'AB', 5, True), self.member('b', 'AB', 5, True, primary=False), self.member('c', 'C', 1, False)])
        self.write(self.new, 'select_out/selected.csv', [self.member('a', 'A', 2, False), self.member('b', 'BC', 4, False), self.member('c', 'BC', 4, False, primary=False)])
        result = compare.compare(self.old, self.new)['selected_identity']['components']
        self.assertEqual(result['many_to_many_components'], 1)
        self.assertEqual(result['split_components'], 0)
        self.assertEqual(result['merge_components'], 0)

    def test_multiplicity_of_same_stable_key_is_reported_without_heap_tie_crash(self):
        self.write(self.old, 'select_out/selected.csv', [self.member('same', 'OLD-A', 1, False), self.member('same', 'OLD-B', 1, False)])
        self.write(self.new, 'select_out/selected.csv', [self.member('different', 'NEW', 1, False)])
        report = compare.compare(self.old, self.new)
        result = report['selected_identity']
        self.assertEqual(result['old']['member_keys_in_multiple_groups'], 1)
        self.assertEqual(result['components']['old_only_old_groups'], 2)
        self.assertEqual(report['validation_status'], 'failed')
        self.assertFalse(report['invariants']['selected_unique_source_membership'])

    def test_top_examples_are_bounded_but_totals_include_every_changed_group(self):
        old, new = [], []
        for index in range(45):
            old.append(self.member('key%03d' % index, 'old%d' % index, 5, True))
            new.append(self.member('key%03d' % index, 'new%d' % index, 6+index, True))
        self.write(self.old, 'select_out/selected.csv', old)
        self.write(self.new, 'select_out/selected.csv', new)
        report = compare.compare(self.old, self.new)
        result = report['selected_identity']
        self.assertEqual(result['components']['one_to_one_dd_changed'], 45)
        self.assertEqual(len(result['examples']), 20)
        self.assertLess(len(json.dumps(report, ensure_ascii=False).encode('utf-8')), compare.MAX_REPORT_BYTES)
        self.assertEqual(result['examples'][0]['dd_sum_delta'], 45)

    def test_partial_run_is_rejected_before_any_comparison(self):
        self.manifest(self.new, status='running')
        with self.assertRaisesRegex(ValueError, 'complete'):
            compare.compare(self.old, self.new)

    def test_input_corpus_change_prevents_causal_identity_only_claim(self):
        self.manifest(self.new, corpus_hash='b'*64)
        report = compare.compare(self.old, self.new)
        self.assertEqual(report['input_scope']['changed_or_missing_shared_corpus_hashes'], ['SCC'])
        self.assertTrue(any('solely' in warning for warning in report['warnings']))

    def test_bad_output_seal_is_rejected(self):
        path = self.new/'run_manifest.json'
        manifest = json.loads(path.read_text())
        manifest['output_identity'] = {'files': {'extract_out/candidates.csv.gz': 'bad'}}
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'output seal'):
            compare.compare(self.old, self.new)

    def test_missing_selected_primary_and_member_disagreement_fail_closed(self):
        self.write(self.new, 'select_out/selected.csv', [self.member('a', 'G', 5, True), self.member('b', 'G', 6, True, primary=False)])
        with self.assertRaisesRegex(ValueError, 'disagrees'):
            compare.compare(self.old, self.new)
        self.write(self.new, 'select_out/selected.csv', [self.member('a', 'G', 5, True, primary=False)])
        with self.assertRaisesRegex(ValueError, 'primary'):
            compare.compare(self.old, self.new)

    def test_output_budget_and_source_overwrite_are_refused(self):
        report = compare.compare(self.old, self.new)
        with self.assertRaisesRegex(ValueError, 'source run'):
            compare.save(self.old/'comparison.json', report)
        target = self.root/'comparison.json'
        target.write_text('retained output')
        report['oversize'] = 'x'*(compare.MAX_REPORT_BYTES+1)
        with self.assertRaisesRegex(ValueError, 'byte budget'):
            compare.save(target, report)
        self.assertEqual(target.read_text(), 'retained output')

    def test_cli_prints_escaped_unicode_for_legacy_windows_console(self):
        extra = self.candidate(50)
        extra['raw_string'] = 'printed nonbreaking\u2011hyphen'
        self.write(self.new, 'extract_out/candidates.csv', self.candidates+[extra])
        captured = io.StringIO()
        with patch.object(sys, 'argv', ['compare_runs', '--old', str(self.old), '--new', str(self.new)]), \
             patch.object(sys, 'stdout', captured):
            self.assertEqual(compare.main(), 0)
        captured.getvalue().encode('ascii', errors='strict')
        result = json.loads(captured.getvalue())
        self.assertIn('\u2011', result['candidates']['examples'][0]['new']['identity']['raw_string'])


if __name__ == '__main__':
    unittest.main()
