"""Scoped evidence, phase-local constraints, and legacy solver boundary contracts."""
import ast
from collections import Counter
import copy
import csv
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import FrozenInstanceError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'pipeline'))
import decide
from identity_evidence import EvidenceSnapshot
from identity_constraints import ConstraintLedger, atomic_link, name_year_link
import identity_solve
import identity_constraints as constraints


def row(key, court='SCC', name='X v. Y', kind='identifier'):
    return {'court': court, 'merge_key': key, 'case_name_modal': name,
            'citation_kind': kind, 'year_printed': '2011', 'jurisdiction': 'CA',
            'canonical_string': key, 'occurrence_count': '3',
            'self_citation_of': '', 'self_case_name': '', 'name_classes': ''}


class IdentityContractTests(unittest.TestCase):
    def ledger(self, rows, sources=None, **kwargs):
        sources = sources or {decide.row_key(r): {'SOURCE'} for r in rows}
        return ConstraintLedger(EvidenceSnapshot(rows, sources, 'FIXTURE', **kwargs))

    def assert_references(self, ledger):
        facts = {r['evidence_id']: r for r in ledger.records['evidence']}
        edges = {r['constraint_id']: r for r in ledger.records['constraints']}
        for edge in edges.values():
            self.assertIn(edge['relation'], ('must_link', 'cannot_link'))
            refs = json.loads(edge['evidence_ids_json'])
            self.assertTrue(refs)
            self.assertTrue(set(refs) <= facts.keys())
        for conflict in ledger.records['conflicts']:
            if conflict['attempted_constraint_id']:
                self.assertEqual(edges[conflict['attempted_constraint_id']]['relation'], 'must_link')
            blockers = json.loads(conflict['blocking_constraint_ids_json'])
            self.assertTrue(blockers)
            self.assertTrue(all(edges[e]['relation'] == 'cannot_link' for e in blockers))

    def test_snapshot_preserves_scoped_original_values_and_complete_sources(self):
        rows = [row('2011||canlii||111'), row('2011||canlii||111', 'ONCA', name='Other')]
        sources = {decide.row_key(rows[0]): {'A', 'B'}, decide.row_key(rows[1]): {'C'}}
        rows[0]['identity_court_conflict'] = 'true'
        rows[0]['identity_court_evidence'] = 'court:csc=neutral_code:scc'
        snapshot = EvidenceSnapshot(rows, sources, 'SCOPE')
        rows[0]['case_name_modal'] = ''
        observations = [r for r in snapshot.records if r['fact_kind'] == 'row_observation']
        self.assertEqual(len(observations), 2)
        inherited = next(r for r in observations if r['court'] == 'SCC')
        self.assertEqual(json.loads(inherited['value_json'])['identity_court_conflict'], 'true')
        self.assertEqual(json.loads(inherited['value_json'])['identity_court_evidence'], 'court:csc=neutral_code:scc')
        self.assertEqual({r['scope'] for r in observations}, {'SCOPE'})
        actual = {r['court']: (json.loads(r['value_json'])['case_name_modal'],
                              json.loads(r['sources_json'])['source_decision_ids']) for r in observations}
        self.assertEqual(actual, {'SCC': ('X v. Y', ['A', 'B']), 'ONCA': ('Other', ['C'])})
        self.assertNotEqual(observations[0]['evidence_id'], observations[1]['evidence_id'])
        row_refs = snapshot.by_row[decide.row_key(rows[0])]
        self.assertFalse(row_refs & snapshot.by_row[decide.row_key(rows[1])])

    def test_resolved_court_facts_cite_applicable_policy(self):
        rows = [row('2011||scc||10', kind='neutral')]
        ledger = self.ledger(rows)
        facts = {r['evidence_id']: r for r in ledger.records['evidence']}
        court = next(r for r in facts.values() if r['fact_kind'] == 'court_observation')
        self.assertEqual(json.loads(court['value_json']), {'court:csc': ['neutral_code:scc']})
        policies = json.loads(court['sources_json'])['policy_evidence_ids']
        self.assertTrue(policies)
        self.assertTrue(all(facts[e]['fact_kind'] == 'policy_record' for e in policies))

    def test_unresolved_support_does_not_invent_negative_fact(self):
        rows = [row('2011||canlii||111'), row('2011||carswellont||11')]
        sources = {decide.row_key(rows[0]): {'A'}, decide.row_key(rows[1]): {'B'}}
        ledger = self.ledger(rows, sources)
        parts = identity_solve.split_by_decision(rows, sources, Counter(), trace=ledger)
        self.assertEqual(len(parts), 2)
        self.assertTrue(any(r['outcome'] == 'unresolved' for r in ledger.records['solution']))
        self.assertFalse(any(r['relation'] == 'cannot_link' for r in ledger.records['constraints']))
        self.assert_references(ledger)

    def test_identifier_bridge_is_blocked_by_evidence_bound_edge(self):
        rows = [row('2011||canlii||111'), row('2011||canlii||222'),
                row('2011||carswellont||11')]
        sources = {decide.row_key(r): {'A'} for r in rows}
        ledger = self.ledger(rows, sources)
        parts = identity_solve.split_by_decision(rows, sources, Counter(), trace=ledger)
        for members, _ in parts:
            self.assertLessEqual(len({r['merge_key'] for r in members if 'canlii' in r['merge_key']}), 1)
        self.assertTrue(ledger.records['conflicts'])
        self.assert_references(ledger)
        blocked = next(r for r in ledger.records['constraints'] if r['relation'] == 'cannot_link')
        facts = {r['evidence_id']: r for r in ledger.records['evidence']}
        self.assertTrue(any(facts[e]['fact_kind'] == 'policy_record'
                            for e in json.loads(blocked['evidence_ids_json'])))

    def test_mixed_title_holdout_retains_original_observation(self):
        rows = [row('2011||scc||10', kind='neutral'), row('2011||scc||11', kind='neutral')]
        rows[1]['name_classes'] = 'xvy:1|other:1'
        sources = {decide.row_key(rows[0]): {'A', 'B', 'C'}, decide.row_key(rows[1]): {'A'}}
        ledger = self.ledger(rows, sources)
        held = []
        output, _, _ = decide.adjudicate(rows, sources, {}, {}, 'FIXTURE', Counter(), False,
                                         holdout=held, identity_separations=[], trace=ledger)
        self.assertTrue(held)
        self.assertEqual(next(r for r in output if r['merge_key'].endswith('||11'))['case_name_modal'], '')
        original = next(r for r in ledger.records['evidence'] if r['fact_kind'] == 'row_observation'
                        and r['merge_key'].endswith('||11'))
        self.assertEqual(json.loads(original['value_json'])['case_name_modal'], 'X v. Y')
        self.assertTrue(any(c['reason'] == 'mixed_title_holdout' for c in ledger.records['conflicts']))
        self.assert_references(ledger)

    def test_gzip_artifacts_and_only_recorded_constraints(self):
        rows = [row('2011||canlii||111')]
        snapshot = EvidenceSnapshot(rows, {}, 'FIXTURE')
        with tempfile.TemporaryDirectory(dir=ROOT / 'implementation') as temp:
            ledger = ConstraintLedger(snapshot, temp)
            proposal = atomic_link(rows, ledger)
            self.assertTrue(proposal.recorded)
            self.assertIsNone(name_year_link([row('2011||canlii||111', name='')], ledger))
            receipt = ledger.close()
            for name, relative in receipt['artifacts'].items():
                path = Path(temp) / relative
                self.assertEqual(path.suffix, '.gz')
                with gzip.open(path, 'rt', encoding='utf-8', newline='') as source:
                    self.assertEqual(len(list(csv.DictReader(source))), receipt['counts'][name])
            self.assertFalse(list(Path(temp).glob('*.csv')))
        self.assertFalse(atomic_link(rows).recorded)

    def test_atomic_projection_preserves_missing_metadata_without_joining_unknown_units(self):
        rows = [row('2011||canlii||111'), row('2011||canlii||111', 'ONCA', name='')]
        rows[1]['year_printed'] = ''
        rows[1]['merge_key'] = '2011||canlii||111'
        unit = tuple(sorted(decide.row_key(r) for r in rows))
        projections = {decide.row_key(r): ('xvy', 2011, unit) for r in rows}
        ledger = self.ledger(rows)
        admission = constraints.name_year_link(rows, ledger, projections)
        self.assertIsNotNone(admission)
        self.assertEqual(set(admission.members), set(unit))
        with self.assertRaises(FrozenInstanceError):
            admission.rule = 'changed'
        unrelated = row('2011||carswellont||11', name='')
        self.assertIsNone(constraints.name_year_link(rows + [unrelated], ledger, projections))
        self.assert_references(ledger)

    def test_atomic_neutral_equivalence_retains_verified_transitive_path(self):
        rows = [row('2011||aaa||10', kind='neutral'), row('2011||ccc||10', kind='neutral')]
        verified = frozenset((frozenset(('aaa', 'bbb')), frozenset(('bbb', 'ccc'))))
        with patch.object(constraints, 'load_bilingual', return_value=verified):
            self.assertIsNotNone(constraints.atomic_link(rows))
            self.assertFalse(constraints.verified_bilingual_keys(rows[0]['merge_key'], rows[1]['merge_key']))
        self.assertIsNone(constraints.atomic_link(rows))

    def test_unrelated_neutrals_emit_no_variant_equivalence(self):
        rows = [row('2011||scc||10', kind='neutral'), row('2011||scc||99', kind='neutral')]
        sources = {decide.row_key(r): {'SOURCE'} for r in rows}
        ledger = self.ledger(rows, sources)
        roots = identity_solve.decisions_of(rows, sources, trace=ledger)[0]
        self.assertEqual(set(roots.values()), {r['merge_key'] for r in rows})
        self.assertFalse(ledger.records['constraints'])

    def test_standalone_positive_court_exclusions_are_conflicts(self):
        rows = [row('2011||scc||10', kind='neutral'), row('2011||bcca||10', kind='neutral')]
        ledger = self.ledger(rows)
        blockers = constraints.court_partition_constraints({'court:csc': rows[:1], 'court:bcca': rows[1:]}, ledger)
        self.assertEqual(len(blockers), 1)
        self.assertEqual(blockers[0].relation, 'cannot_link')
        self.assertEqual(ledger.records['conflicts'][0]['attempted_constraint_id'], '')
        self.assert_references(ledger)

    def test_reviewed_holdout_has_negative_relation_without_positive_alias_attempt(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures/motorvehicle_identity_20261015.json').read_text(encoding='utf-8'))
        import registry
        with tempfile.TemporaryDirectory(dir=ROOT / 'implementation') as temp:
            path = Path(temp) / 'own.csv'
            with path.open('w', encoding='utf-8', newline='') as target:
                writer = csv.DictWriter(target, fieldnames=registry.OWN_FIELDS, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(fixture['own'])
            own = decide.load_own_citations(str(path))
        rows = copy.deepcopy(fixture['members'])
        sources = {key: set(values) for key, values in fixture['source_ids'].items()}
        ledger = self.ledger(rows, sources, own_cites=own, separations=[fixture['fact']])
        decide.adjudicate(rows, sources, {}, {}, 'FIXTURE', Counter(), False,
                          own_cites=own, identity_separations=[fixture['fact']], trace=ledger)
        holds = [r for r in ledger.records['constraints'] if r['phase'] == 'document_holdout']
        self.assertTrue(holds)
        self.assertTrue(all(r['relation'] == 'cannot_link' for r in holds))
        self.assert_references(ledger)

    def test_alias_root_annotation_witness_can_reach_an_unannotated_root(self):
        rows = [row('2011||scc||10', kind='neutral'), row('2011||scc||11', kind='neutral'),
                row('2011|1|scr||1', kind='reporter')]
        for member in rows[1:]:
            member['document_alias_decision_id'] = 'SCC_DOCUMENT'
            member['document_alias_evidence_ids'] = 'own:fixture'
        rows[2]['self_citation_of'] = 'SCC_DOCUMENT'
        sources = {decide.row_key(rows[0]): {'A', 'B', 'C'},
                   decide.row_key(rows[1]): {'A'}, decide.row_key(rows[2]): {'A', 'B'}}
        root, _, _, _, kinds = identity_solve.decisions_of(rows, sources)
        self.assertEqual(set(root.values()), {rows[0]['merge_key']})
        self.assertEqual(kinds[rows[2]['merge_key']], 'document_alias')

    def test_single_anchor_proposals_bind_target_before_and_after_ride_exists(self):
        anchor = row('2011||scc||10', kind='neutral')
        reporters = [row('2011|1|scr||1', kind='reporter'),
                     row('2011|2|dlr||2', kind='reporter')]
        rows = reporters + [anchor]
        sources = {decide.row_key(member): {'A'} for member in rows}
        self.assertLess(decide.row_key(reporters[1]), decide.row_key(anchor))
        ledger = self.ledger(rows, sources)
        parts = identity_solve.split_by_decision(rows, sources, Counter(), trace=ledger)
        self.assertEqual(len(parts), 1)
        edges = [edge for edge in ledger.records['constraints']
                 if edge['phase'] == 'single_anchor' and edge['relation'] == 'must_link']
        self.assertEqual(len(edges), 2)
        anchor_fact = next(fact for fact in ledger.records['evidence']
                           if fact['row_key'] == decide.row_key(anchor) and fact['fact_kind'] == 'row_observation')
        for edge in edges:
            with self.subTest(left=edge['left_members_json']):
                self.assertEqual(json.loads(edge['right_members_json']), [decide.row_key(anchor)])
                self.assertIn(anchor_fact['evidence_id'], json.loads(edge['evidence_ids_json']))
                self.assertEqual(json.loads(edge['source_detail_json'])['right_sources'], ['A'])
        self.assert_references(ledger)

    def test_single_anchor_endpoint_facts_include_self_printed_support(self):
        anchor = row('2011||scc||10', kind='neutral')
        anchor['self_citation_of'] = 'SCC_2011scc10'
        reporter = row('2011|1|scr||1', kind='reporter')
        rows = [reporter, anchor]
        sources = {decide.row_key(reporter): {'SCC_2011scc10'}, decide.row_key(anchor): {'A'}}
        ledger = self.ledger(rows, sources)
        parts = identity_solve.split_by_decision(rows, sources, Counter(), trace=ledger)
        self.assertEqual(len(parts), 1)
        edge = next(edge for edge in ledger.records['constraints'] if edge['phase'] == 'single_anchor')
        self.assertEqual(json.loads(edge['right_members_json']), [decide.row_key(anchor)])
        self.assertEqual(set(json.loads(edge['source_detail_json'])['right_sources']), {'A', 'SCC_2011scc10'})
        anchor_fact = next(fact for fact in ledger.records['evidence']
                           if fact['row_key'] == decide.row_key(anchor) and fact['fact_kind'] == 'row_observation')
        self.assertIn(anchor_fact['evidence_id'], json.loads(edge['evidence_ids_json']))
        self.assertEqual(json.loads(anchor_fact['value_json'])['self_citation_of'], 'SCC_2011scc10')
        self.assert_references(ledger)

    def test_holdout_references_target_proofs_even_when_proof_keys_have_no_scope_rows(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures/motorvehicle_identity_20261015.json').read_text(encoding='utf-8'))
        import registry
        with tempfile.TemporaryDirectory(dir=ROOT / 'implementation') as temp:
            path = Path(temp) / 'own.csv'
            with path.open('w', encoding='utf-8', newline='') as target:
                writer = csv.DictWriter(target, fieldnames=registry.OWN_FIELDS, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(fixture['own'])
            own = decide.load_own_citations(str(path))
        fact = fixture['fact']
        did = fact['target_decision_id']
        proofs = set(fact['target_qualified_evidence_ids'].split('|'))
        held = copy.deepcopy(next(member for member in fixture['members'] if member['merge_key'] == fact['merge_key']))
        target = copy.deepcopy(next(member for member in fixture['members'] if member['merge_key'] == '1985|2|scr||486'))
        held['document_alias_holdout_doc_ids'] = did
        held['document_alias_holdout_evidence_ids'] = '|'.join(sorted(proofs))
        rows = [held, target]
        self.assertFalse(any(member['merge_key'] == '1985|2|rcs||486' for member in rows))
        ledger = self.ledger(rows, own_cites=own)
        edge = constraints.document_holdout_constraints([held], [target], did, proofs, ledger)
        record = next(record for record in ledger.records['constraints'] if record['constraint_id'] == edge.constraint_id)
        refs = set(json.loads(record['evidence_ids_json']))
        facts = {record['evidence_id']: record for record in ledger.records['evidence']}
        referenced_native = {json.loads(facts[eid]['value_json'])['evidence_id']
                             for eid in refs if facts[eid]['fact_kind'] == 'own_citation_proof'
                             and json.loads(facts[eid]['value_json'])['decision_id'] == did}
        self.assertEqual(referenced_native, proofs)
        self.assertTrue(set(ledger.snapshot.native_proof_facts(did, proofs)) <= refs)
        with self.assertRaises(ValueError):
            ledger.snapshot.native_proof_facts('SCC_OTHER_DOCUMENT', proofs)
        with self.assertRaises(ValueError):
            constraints.document_holdout_constraints([held], [target], did,
                proofs | {'own:' + '0' * 64}, ledger)
        with self.assertRaises(ValueError):
            ledger.snapshot.native_proof_facts(did, {'own:' + '0' * 64})
        self.assert_references(ledger)

    def test_mixed_holdout_recompute_records_new_driving_variant_after_reset(self):
        rows = [row(f'2011||scc||{number}', kind='neutral') for number in (10, 11, 21, 22)]
        sources = {}
        for member, count in zip(rows, (100, 40, 15, 5)):
            member['occurrence_count'] = str(count)
            member['name_classes'] = 'xvy:1|other:1' if member['merge_key'].endswith('||11') else 'xvy:1'
            sources[decide.row_key(member)] = {f'SOURCE_{index:03d}' for index in range(count)}
        plain_rows, traced_rows = copy.deepcopy(rows), copy.deepcopy(rows)
        plain_held, traced_held, plain_stats, traced_stats = [], [], Counter(), Counter()
        plain = identity_solve.split_by_decision(plain_rows, sources, plain_stats, holdout=plain_held)
        ledger = self.ledger(traced_rows, sources)
        traced = identity_solve.split_by_decision(traced_rows, sources, traced_stats,
                                                 holdout=traced_held, trace=ledger)
        self.assertEqual(plain, traced)
        self.assertEqual(plain_held, traced_held)
        self.assertEqual(plain_stats, traced_stats)
        self.assertEqual([([member['merge_key'] for member in members], reason) for members, reason in traced],
                         [(['2011||scc||10'], 'decision'),
                          (['2011||scc||21', '2011||scc||22'], 'decision'),
                          (['2011||scc||11'], 'mixed_identity')])
        edge = next(edge for edge in ledger.records['constraints']
                    if edge['phase'] == 'variant' and edge['relation'] == 'must_link'
                    and json.loads(edge['left_members_json']) == ['SCC|2011||scc||22']
                    and json.loads(edge['right_members_json']) == ['SCC|2011||scc||21'])
        reset = next(event for event in ledger.records['solution']
                     if event['phase'] == 'root_recompute_after_holdout')
        accepted = next(event for event in ledger.records['solution']
                        if event['phase'] == 'variant' and event['outcome'] == 'accepted'
                        and edge['constraint_id'] in json.loads(event['constraint_ids_json']))
        self.assertEqual(reset['outcome'], 'reset')
        self.assertEqual(reset['split_reason'], 'mixed_identity_holdout')
        self.assertLess(reset['sequence'], accepted['sequence'])
        self.assertEqual(set(json.loads(reset['members_json'])),
                         {'SCC|2011||scc||10', 'SCC|2011||scc||21', 'SCC|2011||scc||22'})
        row_facts = {record['row_key']: record['evidence_id'] for record in ledger.records['evidence']
                     if record['fact_kind'] == 'row_observation'}
        self.assertTrue({row_facts['SCC|2011||scc||21'], row_facts['SCC|2011||scc||22']} <=
                        set(json.loads(edge['evidence_ids_json'])))
        self.assert_references(ledger)

    def test_identity_execution_has_one_owner(self):
        self.assertIs(decide.decisions_of, identity_solve.decisions_of)
        self.assertIs(decide.cluster_same_case, identity_solve.cluster_same_case)
        self.assertIs(decide.merge_document_alias_clusters, identity_solve.merge_document_alias_clusters)
        for name in ('identity_evidence.py', 'identity_constraints.py'):
            tree = ast.parse((ROOT / 'pipeline' / name).read_text(encoding='utf-8-sig'))
            definitions = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
            self.assertFalse({'decisions_of', 'split_by_decision', 'cluster_same_case', 'partition'} & definitions)
        tree = ast.parse((ROOT / 'pipeline' / 'identity_solve.py').read_text(encoding='utf-8-sig'))
        definitions = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        self.assertFalse({'decide_case_origin', 'build_effective_sources', 'adjudicate'} & definitions)


if __name__ == '__main__':
    unittest.main()

