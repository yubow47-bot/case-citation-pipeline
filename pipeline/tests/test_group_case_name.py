"""A group's exported name comes from all identity-supported members, not the first row."""
import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'pipeline'))
from edges import group_case_name  # noqa: E402


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def member(key, name, basis, occurrences):
    return dict(court='SCC', merge_key=key, merged_group_id='XC-G1', distinct_decisions_count='1',
                case_name_modal=name, identity_basis=basis, key_occurrence_count=str(occurrences),
                group_foreign_status='DOMESTIC_CA', group_origin_country='CA',
                group_origin_status='DETERMINED', group_origin_basis='neutral',
                group_origin_evidence_ids='group-evidence', member_origin_country='CA',
                member_origin_status='DETERMINED', member_origin_basis='neutral',
                member_origin_evidence_ids='member-evidence')


class GroupCaseNameTests(unittest.TestCase):
    def test_most_cited_name_wins_and_ties_ignore_row_order(self):
        self.assertEqual(group_case_name({'B v. C': 2, 'A v. B': 5}), 'A v. B')
        self.assertEqual(group_case_name({'Zeta v. Y': 3, 'Alpha v. Y': 3}), 'Alpha v. Y')
        self.assertEqual(group_case_name({}), '')
        self.assertEqual(group_case_name(None), '')

    def test_unnamed_first_row_does_not_blank_the_group(self):
        # Dunsmuir shape: the first row is an unnamed reporter key; the named neutral
        # citation and a weakly linked member follow.
        rows = [member('2008|1|scr||190', '', 'co_printed_run', 40),
                member('2008||scc||9', 'Dunsmuir v. New Brunswick', 'anchor', 900),
                member('2008|291|dlr|4th|577', 'Wrong v. Name', 'name_year', 5000)]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root / 'decided.csv', rows)
            write(root / 'effective.csv', [dict(merged_group_id='XC-G1',
                source_decision='SCC_2020scc2', status='counted', exclusion_reason='',
                identity_status='anchor', via_member_row_keys='SCC|2008||scc||9')])
            write(root / 'merge/SCC/mentions_candidates.csv', [dict(
                arbitration_status='counted', merge_key='2008||scc||9',
                source_decision_citation='SCC_2020scc2', zone='reasons')])
            result = subprocess.run([sys.executable, str(ROOT / 'pipeline/edges.py'),
                '--decided', str(root / 'decided.csv'), '--effective', str(root / 'effective.csv'),
                '--merge-out', str(root / 'merge'), '--output', str(root / 'edges')],
                capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            with (root / 'edges/citation_edges.csv').open(encoding='utf-8') as source:
                edges = list(csv.DictReader(source))
        # The name_year member is not identity-supported, so its larger count does not vote.
        self.assertEqual([e['case_name_modal'] for e in edges], ['Dunsmuir v. New Brunswick'])


if __name__ == '__main__':
    unittest.main()
