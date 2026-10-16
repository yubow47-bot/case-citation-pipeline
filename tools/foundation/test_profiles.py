"""Offline fixtures for final-edge evidence in case profiles."""
import csv
import json
import sqlite3
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import common
import index_cases


class ProfileEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root_patch = patch.object(common, 'ROOT', Path(self.temp.name))
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.run = Path(self.temp.name) / 'run_fixture'
        self.mentions = self.run / 'merge_out' / 'SCC' / 'mentions_candidates.csv'
        self.mentions.parent.mkdir(parents=True)
        self.db_path = Path(self.temp.name) / 'fixture.db'
        self.db = common.connect(self.db_path)
        self.addCleanup(self.db.close)
        self.db.executescript(common.SCHEMA)
        self.corpus = Path(self.temp.name)/'SCC.parquet'
        self.corpus.write_bytes(b'fixture corpus snapshot')
        selected = self.run/'select_out'/'selected.csv'
        selected.parent.mkdir(parents=True)
        selected.write_text('fixture\nvalue\n', encoding='utf-8')
        self.db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',
                        ('run_fixture', str(self.run), 'fingerprint', json.dumps({'params': {'courts': ['SCC']},
                            'input_identity': {'files': {'corpus/SCC.parquet': common.digest(self.corpus)}}}),
                         '2026-01-01', 'ready'))
        self.db.execute('INSERT INTO case_groups VALUES(?,?,?,?,?,?,?,?,?)',
                        ('run_fixture', 'g', 2, 'Example case', 2, '2000', 0, 'DOMESTIC_CA', 'CA'))
        self.db.executescript('''
            CREATE TABLE members(run_id TEXT, court TEXT, merge_key TEXT, merged_group_id TEXT, canonical_string TEXT);
            CREATE TABLE citation_edges(run_id TEXT, source_decision TEXT, resolved_cited_case TEXT, edge_support TEXT);
            CREATE TABLE effective_associations(run_id TEXT, source_decision TEXT, merged_group_id TEXT, status TEXT);
        ''')
        self.db.execute('INSERT INTO members VALUES(?,?,?,?,?)', ('run_fixture', 'SCC', 'mk', 'g', '1 S.C.R. 100'))
        self.texts = []
        self.rows = []

    def mention(self, source, text, status, support='supported'):
        row = len(self.texts)
        self.texts.append(text)
        self.rows.append(dict(arbitration_status='counted', merge_key='mk', source_decision_citation=source,
                              corpus_row_index=row, match_start_offset=0, match_end_offset=len(text)))
        self.db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)',
                        ('run_fixture', 'SCC', row, source, '', source, '2020-01-01', str(self.corpus)))
        self.db.execute('INSERT INTO effective_associations VALUES(?,?,?,?)', ('run_fixture', source, 'g', status))
        if status == 'counted':
            self.db.execute('INSERT INTO citation_edges VALUES(?,?,?,?)', ('run_fixture', source, 'g', support))

    def build(self, candidates=2):
        self.db.commit()
        with self.mentions.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(self.rows[0]))
            writer.writeheader()
            writer.writerows(self.rows)
        common.source_record(self.db, 'run_fixture', 'merge_out/SCC/mentions_candidates.csv', self.mentions)
        common.source_record(self.db, 'run_fixture', 'corpus/SCC.parquet', self.corpus)
        self.db.commit()
        parent = types.ModuleType('pyarrow')
        pq = types.ModuleType('pyarrow.parquet')
        parent.parquet = pq
        column = types.SimpleNamespace(to_pylist=lambda: self.texts)
        batch = types.SimpleNamespace(column=lambda _: column)
        pq.ParquetFile = lambda _: types.SimpleNamespace(iter_batches=lambda **kwargs: [batch])
        with patch.dict('sys.modules', {'pyarrow': parent, 'pyarrow.parquet': pq}), \
                patch.object(index_cases, 'CANDIDATES', candidates), \
                patch.object(index_cases, 'spread', lambda source: source):
            report = index_cases.build_profiles(self.run, self.db_path)
        body = self.db.execute("SELECT text FROM text_records WHERE collection='cases'").fetchone()[0]
        return report, body

    def test_excluded_self_cannot_fill_candidate_slots_but_final_heuristic_edge_can(self):
        self.mention('SCC_2000self', 'EXCLUDED SELF CONTEXT', 'excluded_self')
        self.mention('SCC_2001excluded', 'EXCLUDED IDENTITY CONTEXT', 'excluded_duplicate')
        self.mention('SCC_2020heuristic', 'VALID HEURISTIC CONTEXT', 'counted', 'heuristic_only')
        self.mention('SCC_2021supported', 'VALID SUPPORTED CONTEXT', 'counted', 'supported')
        report, body = self.build(candidates=2)
        self.assertNotIn('EXCLUDED SELF CONTEXT', body)
        self.assertNotIn('EXCLUDED IDENTITY CONTEXT', body)
        self.assertIn('VALID HEURISTIC CONTEXT', body)
        self.assertIn('VALID SUPPORTED CONTEXT', body)
        self.assertIn('SCC_2020heuristic', body)
        self.assertIn('edge_support=heuristic_only', body)
        self.assertIn('edge_support=supported', body)
        self.assertEqual(report['candidate_mentions_excluded_by_final_edges'], 2)
        self.assertEqual(report['with_context'], 1)

    def test_profile_has_no_citing_context_when_all_mentions_were_excluded(self):
        self.mention('SCC_2000self', 'EXCLUDED SELF CONTEXT', 'excluded_self')
        report, body = self.build()
        self.assertNotIn('EXCLUDED SELF CONTEXT', body)
        self.assertEqual(report['with_context'], 0)
        self.assertEqual(report['candidate_mentions_excluded_by_final_edges'], 1)


if __name__ == '__main__':
    unittest.main()
