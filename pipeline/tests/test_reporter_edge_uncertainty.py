"""Source-actual reporter uncertainty; canonical authority remains unchanged.

The two Nickerson source/key pairs reproduce saved native observations (no body
text is included). Their historical edges were name_year candidates. The
supported cases below explicitly exercise controlled eligible-basis states;
they do not claim that the historical sources had supported identities.
"""
import contextlib
import csv
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve()
REPO = next(p for p in HERE.parents if (p / 'pipeline/decide.py').exists())
sys.path.insert(0, str(REPO / 'pipeline'))
spec = importlib.util.spec_from_file_location('reviewed_edges', HERE.parents[1] / 'edges.py')
edges = importlib.util.module_from_spec(spec)
spec.loader.exec_module(edges)

NICKERSON_KEY = '|101|nsr|2d|243'
NICKERSON_SOURCES = ('NSCA_1996nsca207', 'NSCA_1996nsca68')


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def member(key, conflict=False, basis='name_year', country='', source_status='eligible'):
    return dict(court='NSCA', merge_key=key, merged_group_id='XC-G1',
        distinct_decisions_count='1', case_name_modal='fixture target',
        group_foreign_status='DOMESTIC_CA', group_origin_country='CA',
        group_origin_status='DETERMINED', group_origin_basis='group-evidence',
        group_origin_evidence_ids='group-1', noncore_origin_evidence='',
        member_origin_country=country,
        member_origin_status='DETERMINED' if country else 'UNDETERMINED',
        member_origin_basis='member-evidence' if country else '',
        member_origin_evidence_ids='member-1' if country else '',
        identity_basis=basis, reporter_identity_conflict=str(conflict).lower(),
        identity_source_status=source_status)


class ReporterEdgeUncertaintyTests(unittest.TestCase):
    def export(self, members, actual_keys, source=NICKERSON_SOURCES[0], effective='anchor'):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_csv(root / 'decided.csv', members)
            court = members[0]['court']
            write_csv(root / 'effective.csv', [dict(merged_group_id='XC-G1',
                source_decision=source, status='counted', exclusion_reason='',
                identity_status=effective, via_member_row_keys=';'.join(court+'|'+k for k in actual_keys))])
            write_csv(root / 'merge' / court / 'mentions_candidates.csv', [dict(
                arbitration_status='counted', merge_key=k,
                source_decision_citation=source, zone='reasons') for k in actual_keys])
            args = ['edges.py', '--decided', str(root / 'decided.csv'), '--effective',
                    str(root / 'effective.csv'), '--merge-out', str(root / 'merge'),
                    '--output', str(root / 'edges')]
            with patch.object(sys, 'argv', args), contextlib.redirect_stdout(io.StringIO()):
                edges.main()
            with (root / 'edges/citation_edges.csv').open(encoding='utf-8') as inp:
                rows = list(csv.DictReader(inp))
            self.assertEqual(len(rows), 1)
            row = rows[0]
            # Invariant: no group, source, membership, count, canonical support or
            # canonical identity rewrite, even when reviewed confidence changes.
            self.assertEqual(row['source_decision'], source)
            self.assertEqual(row['resolved_cited_case'], 'XC-G1')
            self.assertEqual(row['mention_count'], str(len(actual_keys)))
            self.assertEqual(row['distinct_decisions_count'], '1')
            self.assertEqual(row['mention_detail_key'], ';'.join(sorted(set(court+'|'+k for k in actual_keys))))
            self.assertEqual(row['edge_support'], 'supported' if edges.basis_of(effective) else 'heuristic_only')
            self.assertEqual(row['identity_status'], effective if edges.basis_of(effective) else edges.candidate_label(effective))
            stats = json.loads((root / 'edges/manifest.json').read_text(encoding='utf-8'))['stats']
            return row, stats

    def check_native_nickerson(self, source):
        row, stats = self.export([member(NICKERSON_KEY, True)], [NICKERSON_KEY], source, 'name_year')
        self.assertEqual(row['reporter_occurrence_status'], 'uncertain_only_support')
        self.assertEqual(row['reviewed_identity_status'], 'reporter_occurrence_uncertain')
        self.assertEqual(row['reviewed_edge_support'], 'heuristic_only')
        self.assertEqual(row['reporter_ambiguous_member_keys'], 'NSCA|' + NICKERSON_KEY)
        self.assertEqual(stats['reporter_reviewed_supported_downgraded'], 0)

    def test_native_nickerson_source_1996nsca207(self):
        self.check_native_nickerson(NICKERSON_SOURCES[0])

    def test_native_nickerson_source_1996nsca68(self):
        self.check_native_nickerson(NICKERSON_SOURCES[1])

    def test_controlled_supported_conflict_blocks_only_group_country_fallback(self):
        row, stats = self.export([member(NICKERSON_KEY, True, 'anchor')], [NICKERSON_KEY]*2)
        self.assertEqual((row['edge_support'], row['origin_country']), ('supported', 'CA'))
        self.assertEqual((row['reviewed_edge_support'], row['reviewed_origin_country']), ('heuristic_only', ''))
        self.assertEqual(row['reviewed_foreign_status'], 'UNDETERMINED')
        self.assertEqual(row['reporter_ambiguous_mention_count'], '2')
        self.assertEqual(stats['reporter_reviewed_supported_downgraded'], 1)
        self.assertEqual(stats['reporter_reviewed_country_changed'], 1)

    def test_independent_actual_member_country_is_retained(self):
        row, _ = self.export([member(NICKERSON_KEY, True, 'anchor', 'CA')], [NICKERSON_KEY])
        self.assertEqual(row['reviewed_edge_support'], 'heuristic_only')
        self.assertEqual(row['reviewed_origin_country'], 'CA')
        self.assertEqual(row['reviewed_origin_basis'], 'member:member-evidence')

    def test_unused_clean_group_anchor_cannot_rescue(self):
        row, _ = self.export([member(NICKERSON_KEY, True), member('1991||nsj||86', False, 'anchor')], [NICKERSON_KEY])
        self.assertEqual(row['reviewed_edge_support'], 'heuristic_only')

    def test_authentic_darlington_cooccurrence_with_controlled_eligible_anchor(self):
        # These two keys co-occur in BCSC_2008bcsc1619 (saved native evidence).
        # Historical basis was cocitation; same_citation is a branch-control here.
        reporter, clean = '1997||bcj||2543', '1997|99|bcac||134'
        members = [member(reporter, True), member(clean, False, 'same_citation')]
        for m in members:
            m['court'] = 'BCSC'
        row, stats = self.export(members, [reporter, clean], 'BCSC_2008bcsc1619', 'same_citation')
        self.assertEqual(row['reporter_occurrence_status'], 'ambiguous_member_present')
        self.assertEqual(row['reviewed_edge_support'], 'supported')
        self.assertEqual(row['reviewed_identity_status'], 'same_citation')
        self.assertEqual(row['reviewed_origin_country'], 'CA')
        self.assertEqual(stats['reporter_reviewed_supported_downgraded'], 0)

    def test_actual_ineligible_or_excluded_clean_member_cannot_rescue(self):
        for basis, status in [('cocitation', 'eligible'), ('anchor', 'excluded_source_only')]:
            with self.subTest(basis=basis, status=status):
                clean = '1991||nsj||86'
                row, _ = self.export([member(NICKERSON_KEY, True), member(clean, False, basis, source_status=status)], [NICKERSON_KEY, clean])
                self.assertEqual(row['reviewed_edge_support'], 'heuristic_only')

    def test_nonconflicted_supported_edge_is_unchanged(self):
        row, stats = self.export([member(NICKERSON_KEY, False, 'anchor')], [NICKERSON_KEY])
        self.assertEqual(row['reporter_occurrence_status'], 'none')
        for field in ('edge_support', 'identity_status', 'foreign_status', 'origin_country', 'origin_basis', 'origin_evidence_ids'):
            self.assertEqual(row['reviewed_' + field], row[field])
        self.assertEqual(stats['reporter_reviewed_supported_downgraded'], 0)


if __name__ == '__main__':
    unittest.main()
