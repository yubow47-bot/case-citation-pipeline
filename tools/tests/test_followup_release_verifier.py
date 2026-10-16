"""Tiny artifact regressions for the follow-up release acceptance gates."""
import csv
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('followup_release_verifier', ROOT/'audit/verify_followup_release_20261016.py')
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class FollowupReleaseVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'implementation')
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.run = self.project/'data/run_fixture'
        self.trace = self.run/'decide_out/cross_court'
        self.before, self.after = '2001||scc||1', '2002||scc||2'
        self.history_path = self.run/'merge_out/SCC/history_pairs.csv'
        raw = [dict(source_decision_citation='SCC_2020scc1', corpus_row_index='0',
                    instance='i1', side=side, merge_key=key, candidate_id='candidate-'+side, connector="aff'd")
               for side, key in [('before', self.before), ('after', self.after)]]
        self.write(self.history_path, raw)
        logical_hash = verify.digest(self.history_path)
        self.facts = []
        for number, row in enumerate(raw, 2):
            source = {'artifact': str(self.history_path), 'resolved_artifact': str(self.history_path),
                      'record': number, 'sha256': logical_hash, 'hash_scope': 'logical_csv_bytes'}
            value = dict(row, connector_sha256=hashlib.sha256(row['connector'].encode()).hexdigest(), source_locator=source)
            self.facts.append(self.fact('appeal_history_instance', value, source, row['merge_key']))
        with gzip.open(str(self.history_path)+'.gz', 'wb') as stream:
            stream.write(self.history_path.read_bytes())
        self.history_path.unlink()
        policy = {'normalized_fr': 'rcs', 'normalized_en': 'scr', 'verification_status': 'verified_corpus_metadata',
                  'source': 'native metadata', 'source_locator': 'fixture proof'}
        policy_path = self.project/'decisions/bilingual_reporter_abbreviations.csv'
        self.write(policy_path, [policy])
        policy_hash = verify.digest(policy_path)
        self.manifest = {'input_identity': {'files': {'decisions/bilingual_reporter_abbreviations.csv': policy_hash}}}
        self.policy = self.fact('policy_record', policy, {'artifact': 'decisions/bilingual_reporter_abbreviations.csv',
                                                       'record': 2, 'sha256': policy_hash})
        ids = [f['evidence_id'] for f in self.facts]
        self.facts.append(self.policy)
        self.constraints = [self.constraint('appeal_history_connector', ids, {'history_instances': [
            {'instance': 'i1', 'before_merge_keys': [self.before], 'after_merge_keys': [self.after], 'evidence_ids': ids}]}),
            self.constraint('exact_full_reporter_key', [self.policy['evidence_id']], {'reporter_normalizations': [
                {'from': 'rcs', 'to': 'scr', 'row_key': 'SCC|1995|2|rcs||1130', 'policy_evidence_id': self.policy['evidence_id']} ]})]
        self.save_trace()

    @staticmethod
    def write(path, records):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)

    @staticmethod
    def fact(kind, value, source, key=''):
        payload = {'scope': 'XC', 'court': '', 'row_key': '', 'merge_key': key, 'fact_kind': kind,
                   'value_json': verify.canonical(value), 'sources_json': verify.canonical(source)}
        return dict(evidence_id='fact:'+hashlib.sha256(verify.canonical(payload).encode()).hexdigest(), **payload)

    def constraint(self, rule, refs, detail):
        return {'rule': rule, 'relation': 'cannot_link' if rule == 'appeal_history_connector' else 'must_link',
                'left_members_json': json.dumps(['SCC|'+self.before]), 'right_members_json': json.dumps(['SCC|'+self.after]),
                'evidence_ids_json': json.dumps(refs), 'source_detail_json': json.dumps(detail)}

    def save_trace(self):
        self.write(self.trace/'identity_evidence.csv', self.facts)
        self.write(self.trace/'identity_constraints.csv', self.constraints)

    def check(self):
        return verify.verify_trace(self.run, 'cross_court', self.manifest, True, self.project)

    def test_compact_history_and_policy_mapping_are_verified(self):
        result = self.check()
        self.assertFalse(self.history_path.exists())
        self.assertEqual(result['history_facts'], 2)
        self.assertEqual(result['history_constraints'], 1)
        self.assertEqual(result['logical_source_files_verified'], 1)
        self.assertEqual(result['rcs_scr_proposals_verified'], 1)

    def test_missing_or_shared_pair_keys_fail_closed(self):
        index = {'by_key': {'a': {'g1'}, 'b': {'g1'}}}
        with self.assertRaisesRegex(ValueError, 'absent'):
            verify.distinct_pair(index, 'a', 'missing')
        with self.assertRaisesRegex(ValueError, 'share groups'):
            verify.distinct_pair(index, 'a', 'b')
        index['by_key']['b'] = {'g2'}
        self.assertEqual(verify.distinct_pair(index, 'a', 'b')['right_groups'], ['g2'])

    def test_native_inventory_requires_all_four_exact_pairs_without_duplicates(self):
        facts = [{'left_merge_key': left, 'right_merge_key': right} for left, right in verify.NEW_PAIRS.values()]
        self.assertEqual(len(verify.assert_native_pair_inventory(facts)), 4)
        with self.assertRaisesRegex(ValueError, 'required release pairs'):
            verify.assert_native_pair_inventory(facts[:-1])
        with self.assertRaisesRegex(ValueError, 'required release pairs'):
            verify.assert_native_pair_inventory(facts+[facts[0]])
        facts[0] = dict(facts[0], right_merge_key='forged')
        with self.assertRaisesRegex(ValueError, 'required release pairs'):
            verify.assert_native_pair_inventory(facts)

    def test_additional_native_inventory_has_independent_frozen_eighteen_pairs(self):
        facts = [{'left_merge_key': left, 'right_merge_key': right}
                 for left, right in verify.ADDITIONAL_NATIVE_PAIRS.values()]
        self.assertEqual(len(verify.assert_native_pair_inventory(facts, verify.ADDITIONAL_NATIVE_PAIRS)), 18)
        self.assertIn('Waldick', verify.ADDITIONAL_NATIVE_PAIRS)
        self.assertEqual(len(verify.GRAMMAR_RESIDUAL_PAIRS), 17)
        with self.assertRaisesRegex(ValueError, 'required release pairs'):
            verify.assert_native_pair_inventory(facts[:-1], verify.ADDITIONAL_NATIVE_PAIRS)

    def test_waldick_retained_partial_candidate_cannot_be_counted_or_missing(self):
        path = self.run/'merge_out/ONCA/mentions_candidates.csv'
        records = [
            {'candidate_id': 'ONCA:16983:11266:11283:shape_year_vol_page', 'merge_key': '1990|70|or||2',
             'arbitration_status': 'alternative_contained', 'source_decision_citation': 'ONCA_2026onca371', 'corpus_row_index': '16983'},
            {'candidate_id': 'ONCA:16983:11274:11283:shape_vol_abbr_page', 'merge_key': '|70|or||2',
             'arbitration_status': 'alternative_contained', 'source_decision_citation': 'ONCA_2026onca371', 'corpus_row_index': '16983'},
            {'candidate_id': 'ONCA:16983:11266:11290:shape_year_vol_page_transposed_series', 'merge_key': '1990|70|or|2d|717',
             'arbitration_status': 'counted', 'source_decision_citation': 'ONCA_2026onca371', 'corpus_row_index': '16983'},
        ]
        self.write(path, records)
        self.assertEqual(verify.verify_waldick_candidate_ledger(self.run)['candidates_verified'], 3)
        records[0]['arbitration_status'] = 'counted'
        self.write(path, records)
        with self.assertRaisesRegex(ValueError, 'arbitration contract failed'):
            verify.verify_waldick_candidate_ledger(self.run)
        self.write(path, records[1:])
        with self.assertRaisesRegex(ValueError, 'candidate is absent'):
            verify.verify_waldick_candidate_ledger(self.run)

    def test_ilr_full_literal_locators_are_counted_and_partial_prefixes_retained(self):
        path = self.run/'merge_out/ONCA/mentions_candidates.csv'
        records = []
        for cid, wanted in verify.ilr_candidate_expectations().items():
            record = {k: v for k, v in wanted.items() if k != 'counted'}
            records.append(dict(record, candidate_id=cid, jurisdiction='UNSUPPORTED',
                arbitration_status='counted' if wanted['counted'] else 'alternative_contained'))
        self.write(path, records)
        self.assertEqual(verify.verify_ilr_candidate_ledger(self.run)['complete_counted'], 2)
        records[0]['arbitration_status'] = 'counted'
        self.write(path, records)
        with self.assertRaisesRegex(ValueError, 'arbitration contract failed'):
            verify.verify_ilr_candidate_ledger(self.run)
        records[0]['arbitration_status'] = 'alternative_contained'
        records[1]['merge_key'] = '1988||ilr||1'
        self.write(path, records)
        with self.assertRaisesRegex(ValueError, 'literal span changed'):
            verify.verify_ilr_candidate_ledger(self.run)

    def test_ilr_complete_syntax_does_not_award_canadian_jurisdiction(self):
        path = self.run/'merge_out/ONCA/mentions_candidates.csv'
        records = []
        for cid, wanted in verify.ilr_candidate_expectations().items():
            record = {k: v for k, v in wanted.items() if k != 'counted'}
            records.append(dict(record, candidate_id=cid, jurisdiction='CA',
                arbitration_status='counted' if wanted['counted'] else 'alternative_contained'))
        self.write(path, records)
        with self.assertRaisesRegex(ValueError, 'inferred a jurisdiction'):
            verify.verify_ilr_candidate_ledger(self.run)

    def test_changed_compressed_history_bytes_are_rejected(self):
        with gzip.open(str(self.history_path)+'.gz', 'ab') as stream:
            stream.write(b'\n')
        with self.assertRaisesRegex(ValueError, 'logical CSV hash changed'):
            self.check()

    def test_history_constraint_requires_instance_facts(self):
        detail = json.loads(self.constraints[0]['source_detail_json'])
        detail['history_instances'][0]['evidence_ids'] = []
        self.constraints[0]['source_detail_json'] = json.dumps(detail)
        self.save_trace()
        with self.assertRaisesRegex(ValueError, 'instance facts'):
            self.check()

    def test_history_constraint_cannot_reference_unrelated_endpoints(self):
        self.constraints[0]['left_members_json'] = json.dumps(['SCC|unrelated'])
        self.save_trace()
        with self.assertRaisesRegex(ValueError, 'endpoints'):
            self.check()

    def test_mapping_requires_the_exact_policy_fact_in_its_references(self):
        self.constraints[1]['evidence_ids_json'] = '[]'
        self.save_trace()
        with self.assertRaisesRegex(ValueError, 'mapping policy fact'):
            self.check()

    def test_policy_fact_must_match_located_input_row(self):
        value = json.loads(self.policy['value_json'])
        value['source_locator'] = 'unrelated proof'
        self.facts[-1] = self.fact('policy_record', value, json.loads(self.policy['sources_json']))
        self.save_trace()
        with self.assertRaisesRegex(ValueError, 'located input row'):
            self.check()


class CompleteTraceScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'implementation')
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)/'run_trace'
        self.manifest = {'status': 'complete', 'input_identity_verified_unchanged': True,
                         'params': {'courts': ['SCC']}}
        key = 'SCC|2001||scc||1'
        for scope, label in [('SCC', 'SCC'), ('cross_court', 'XC')]:
            directory = self.run/'decide_out'/scope
            directory.mkdir(parents=True)
            observation = {'scope': label, 'court': 'SCC', 'row_key': key,
                           'merge_key': '2001||scc||1', 'fact_kind': 'row_observation',
                           'value_json': verify.canonical({'self_citation_of': ''}),
                           'sources_json': verify.canonical({'input_row_key': key, 'source_decision_ids': ['SOURCE']})}
            fact = dict(evidence_id='fact:'+hashlib.sha256(verify.canonical(observation).encode()).hexdigest(), **observation)
            self.table(directory/'identity_evidence.csv', list(fact), [fact])
            self.table(directory/'identity_constraints.csv', ['constraint_id', 'relation', 'evidence_ids_json'], [])
            self.table(directory/'identity_conflicts.csv', ['attempted_constraint_id', 'blocking_constraint_ids_json'], [])
            events = [{'sequence': str(i), 'phase': phase, 'context_id': '', 'members_json': json.dumps([key]),
                       'outcome': outcome, 'group_id': gid, 'split_reason': '', 'constraint_ids_json': '[]'}
                      for i, phase, outcome, gid in [(1, 'final_identity_partition', 'partitioned', ''),
                                                     (2, 'assigned_group_id', 'assigned', 'g1')]]
            self.table(directory/'identity_solution.csv', list(events[0]), events)
            self.table(directory/'decided.csv', ['court', 'merge_key', 'merged_group_id'],
                       [{'court': 'SCC', 'merge_key': '2001||scc||1', 'merged_group_id': 'g1'}])
            self.table(directory/'decision_ids.csv', ['row_key', 'source_decision_citation'],
                       [{'row_key': key, 'source_decision_citation': 'SOURCE'}])
            self.table(directory/'effective_sources.csv', ['merged_group_id'], [])
            counts = {'evidence': 1, 'constraints': 0, 'conflicts': 0, 'solution': 2}
            (directory/'manifest.json').write_text(json.dumps({'mode': 'cross_court' if label == 'XC' else 'in_court',
                'label': label, 'identity_trace': {'protocol': 'scoped-identity-constraints-v1', 'counts': counts}}), encoding='utf-8')
        self.reseal()

    @staticmethod
    def table(path, fields, records):
        with path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)

    def reseal(self, omitted=()):
        files = {path.relative_to(self.run).as_posix(): verify.digest(path)
                 for path in self.run.rglob('*') if path.is_file() and path.name != 'run_manifest.json'
                 and path.relative_to(self.run).as_posix() not in omitted}
        self.manifest['output_identity'] = {'files': files,
            'fingerprint': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}
        (self.run/'run_manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def test_all_declared_courts_and_cross_court_are_checked(self):
        report = verify.verify_generic_traces(self.run, self.manifest)
        self.assertEqual(report['scopes_verified'], 2)
        self.assertEqual(report['required_scopes'], ['SCC', 'cross_court'])
        self.assertEqual(report['required_sealed_artifacts'], 16)

    def test_missing_whole_declared_court_cannot_pass(self):
        directory = self.run/'decide_out/SCC'
        for path in directory.iterdir():
            path.unlink()
        directory.rmdir()
        self.reseal()
        with self.assertRaisesRegex(ValueError, 'absent from output seal'):
            verify.verify_generic_traces(self.run, self.manifest)

    def test_existing_but_unsealed_trace_cannot_pass(self):
        trace = 'decide_out/SCC/identity_solution.csv'
        self.assertTrue((self.run/trace).is_file())
        self.reseal(omitted=[trace])
        with self.assertRaisesRegex(ValueError, 'absent from output seal'):
            verify.verify_generic_traces(self.run, self.manifest)

    def test_corrupt_nonhistory_fact_is_rejected(self):
        path = self.run/'decide_out/SCC/identity_evidence.csv'
        records = list(verify.rows(path))
        records[0]['value_json'] = '{}'
        self.table(path, list(records[0]), records)
        self.reseal()
        with self.assertRaisesRegex(ValueError, 'corrupt scoped evidence ID'):
            verify.verify_generic_traces(self.run, self.manifest)


if __name__ == '__main__':
    unittest.main()
