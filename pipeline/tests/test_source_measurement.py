"""Quarantine removes support and counts while retaining original observations."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from source_measurement import prepare_sources, restore_source_audit, filter_instances


class SourceMeasurementTests(unittest.TestCase):
    def test_mixed_and_excluded_only_members_remain_auditable(self):
        rows = [dict(court='SCC', merge_key='a', self_citation_of='bad|good', merged_group_id='G1'),
                dict(court='SCC', merge_key='b', self_citation_of='bad', merged_group_id='G2')]
        raw = {'SCC|a': {'bad', 'good'}, 'SCC|b': {'bad'}}
        exclusions = {'bad': 'native_citation_mismatch'}
        clean = prepare_sources(rows, raw, exclusions)
        self.assertEqual(clean, {'SCC|a': {'good'}, 'SCC|b': set()})
        self.assertEqual(rows[0]['self_citation_of'], 'good')
        self.assertEqual(rows[1]['identity_source_status'], 'excluded_source_only')
        ids = [{'row_key': 'SCC|a', 'source_decision_citation': 'good'}]
        effective = []
        restore_source_audit(rows, ids, effective, raw, exclusions)
        self.assertEqual(len(ids), 3)
        self.assertEqual(len(effective), 2)
        self.assertTrue(all(r['status'] == 'excluded_source' for r in effective))
        self.assertEqual(raw['SCC|a'], {'bad', 'good'})

    def test_instances_from_quarantined_sources_cannot_support_identity(self):
        instances = {'bad_run': {'records': [{'source_decision_citation': 'bad'}]},
                     'good_run': {'records': [{'source_decision_citation': 'good'}]}}
        self.assertEqual(set(filter_instances(instances, {'bad': 'mismatch'})), {'good_run'})
        self.assertEqual(len(instances), 2)


if __name__ == '__main__':
    unittest.main()
