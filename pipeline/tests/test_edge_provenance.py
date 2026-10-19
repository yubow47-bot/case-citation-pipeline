"""Every exported effective link must have positive, mapped native mentions."""
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class EdgeProvenanceTests(unittest.TestCase):
    def run_fixture(self, mode):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root / 'decided.csv', [dict(court='SCC', merge_key='2001||scc||1',
                merged_group_id='XC-G1', distinct_decisions_count='1',
                group_foreign_status='DOMESTIC_CA', group_origin_country='CA',
                group_origin_status='DETERMINED', group_origin_basis='neutral',
                group_origin_evidence_ids='group-evidence', member_origin_country='CA',
                member_origin_status='DETERMINED', member_origin_basis='neutral',
                member_origin_evidence_ids='member-evidence')])
            write(root / 'effective.csv', [dict(merged_group_id='XC-G1',
                source_decision='SCC_2020scc2', status='counted', exclusion_reason='',
                identity_status='anchor', via_member_row_keys='SCC|2001||scc||1')])
            (root / 'merge').mkdir()
            if mode == 'missing_file':
                (root / 'merge/SCC').mkdir()
            elif mode != 'missing_directory':
                write(root / 'merge/SCC/mentions_candidates.csv', [dict(
                    arbitration_status='rejected' if mode == 'no_counted' else 'counted',
                    merge_key='2001||scc||999' if mode == 'unmapped' else '2001||scc||1',
                    source_decision_citation='SCC_2020scc2', zone='reasons')])
            result = subprocess.run([sys.executable, str(ROOT/'pipeline/edges.py'),
                '--decided', str(root/'decided.csv'), '--effective', str(root/'effective.csv'),
                '--merge-out', str(root/'merge'), '--output', str(root/'edges')],
                capture_output=True, text=True, encoding='utf-8')
            output = root/'edges/citation_edges.csv'
            rows = []
            if output.exists():
                with output.open(encoding='utf-8') as source:
                    rows = list(csv.DictReader(source))
            return result, rows

    def test_positive_native_link_is_preserved(self):
        result, rows = self.run_fixture('complete')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rows[0]['mention_count'], '1')
        self.assertEqual(rows[0]['mention_detail_key'], 'SCC|2001||scc||1')

    def test_incomplete_provenance_fails_before_export(self):
        for mode in ('missing_directory', 'missing_file', 'unmapped', 'no_counted'):
            with self.subTest(mode=mode):
                result, rows = self.run_fixture(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(rows, [])


if __name__ == '__main__':
    unittest.main()
