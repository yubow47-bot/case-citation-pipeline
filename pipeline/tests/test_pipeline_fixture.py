"""One isolated six-document CLI run with frozen source-to-target expectations."""
from collections import Counter
import csv
import datetime as dt
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
COURTS = ('SCC', 'ONCA', 'BCCA')

# Reviewed fixture facts, never generated or updated from the pipeline output.
EXPECTED_SOURCES = {
    '2020||scc||901': {'SCC_2021csc902', 'ONCA_2019onca701', 'ONCA_2022onca702', 'BCCA_2018bcca801'},
    '2019||onca||701': {'SCC_2020scc901', 'SCC_2021csc902', 'BCCA_2023bcca802'},
    '2018||bcca||801': {'ONCA_2019onca701'},
    '1999|2|scr||100': {'SCC_2020scc901'},
    '|53|zzr||88': {'SCC_2020scc901'},
}
EXPECTED_SELF = {
    ('SCC_2020scc901', '2020||scc||901'),
    ('SCC_2021csc902', '2021||csc||902'),
    ('ONCA_2019onca701', '2019||onca||701'),
    ('ONCA_2022onca702', '2022||onca||702'),
    ('BCCA_2018bcca801', '2018||bcca||801'),
    ('BCCA_2023bcca802', '2023||bcca||802'),
}


def record(citation, body, french_citation=None, french_body=None):
    english = citation is not None
    year = int((citation or french_citation).split()[0])
    return {
        'citation_en': citation, 'citation_fr': french_citation,
        'name_en': 'Fixture source' if english else None,
        'name_fr': 'Source synthétique' if french_citation else None,
        'document_date_en': dt.datetime(year, 1, 1) if english else None,
        'document_date_fr': dt.datetime(year, 1, 1) if french_citation else None,
        'unofficial_text_en': ('Neutral citation\n' + citation + '\nReasons for Judgment\n' + body) if english else None,
        'unofficial_text_fr': ('Référence neutre\n' + french_citation + '\nContenu de la décision\n' + french_body)
                             if french_citation else None,
    }


class PipelineFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix='pipeline-fixture-', dir=ROOT/'implementation')
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)/'repo'
        cls.root.mkdir()
        for folder in ('pipeline', 'decisions', 'tools', 'corpus', 'data'):
            (cls.root/folder).mkdir()
        for folder, pattern in (('pipeline', '*.py'), ('decisions', '*.csv')):
            for source in (ROOT/folder).glob(pattern):
                shutil.copyfile(source, cls.root/folder/source.name)
        for name in ('storage.py', 'check_run.py'):
            shutil.copyfile(ROOT/'tools'/name, cls.root/'tools'/name)
        shutil.copyfile(ROOT/'select_config.yaml', cls.root/'select_config.yaml')
        records = {
            'SCC': [
                record('2020 SCC 901',
                    '[1] Meridian v. Horizon, 2019 ONCA 701.\n'
                    '[2] Again Meridian v. Horizon, 2019 ONCA 701.\n'
                    '[3] Beacon v. Dune, [1999] 2 S.C.R. 100.\n'
                    '[4] Footnote 7 Section 69 of the Act. R.S.C. 1985, c. C-46.\n'
                    '[5] Zenith v. Cedar, 53 Z.Z.R. 88.'),
                record(None, '', '2021 CSC 902',
                    '[1] Nous suivons Meridian v. Horizon, 2019 ONCA 701.\n'
                    '[2] Voir Atlas v. Boreal, 2020 SCC 901.'),
            ],
            'ONCA': [
                record('2019 ONCA 701',
                    '[1] Atlas v. Boreal, 2020 SCC 901.\n'
                    '[2] Summit v. Vale, 2018 BCCA 801.'),
                record('2022 ONCA 702', '[1] Atlas v. Boreal, 2020 SCC 901.', '2022 ONCA 702',
                    '[1] Hidden v. French, 2017 SCC 999.'),
            ],
            'BCCA': [
                record('2018 BCCA 801', '[1] Atlas v. Boreal, 2020 SCC 901.'),
                record('2023 BCCA 802',
                    '[1] Meridian v. Horizon, 2019 ONCA 701.\n'
                    '[2] Footnote 7 Section 69 of the Act.'),
            ],
        }
        for court, rows in records.items():
            pq.write_table(pa.Table.from_pylist(rows), cls.root/'corpus'/(court + '.parquet'))
        cls.run_dir = cls.root/'data/run_fixture'
        command = [sys.executable, str(cls.root/'pipeline/run_all.py'), '--out', str(cls.run_dir),
                   '--batch-size', '20', '--limit-batches', '1', '--storage-budget-gb', '1', '--min-free-gb', '0']
        for court in COURTS:
            command += ['--court', court]
        result = subprocess.run(command, cwd=cls.root, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=90,
            env=dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1'))
        if result.returncode:
            raise AssertionError('Tiny CLI pipeline failed:\n' + result.stdout[-3000:] + result.stderr[-3000:])
        cls.decided = cls.rows('decide_out/cross_court/decided.csv')
        cls.primary = {row['merged_group_id']: row['merge_key'] for row in cls.decided if row['is_primary'] == 'true'}

    @classmethod
    def rows(cls, relative):
        with gzip.open(str(cls.run_dir/relative) + '.gz', 'rt', encoding='utf-8-sig', newline='') as stream:
            return list(csv.DictReader(stream))

    def relation_set(self, relative):
        rows = self.rows(relative)
        values = {(row['source_decision'], self.primary[row['resolved_cited_case']]) for row in rows}
        self.assertEqual(len(values), len(rows), 'Each source-to-target relation must appear once')
        return values

    def test_frozen_relations_dd_and_self_exclusion(self):
        expected = {(source, key) for key, sources in EXPECTED_SOURCES.items() for source in sources}
        self.assertEqual(self.relation_set('edges/citation_edges.csv'), expected)
        mentions = [row for court in COURTS for row in self.rows('merge_out/' + court + '/mentions_candidates.csv')]
        # The same header also has a volume-shaped candidate; check its neutral identity here.
        self.assertEqual({(row['source_decision_citation'], row['merge_key']) for row in mentions
                          if row['arbitration_status'] == 'self_citation_row' and row['citation_kind'] == 'neutral'}, EXPECTED_SELF)
        self.assertFalse(expected & EXPECTED_SELF)
        # These printed header citations were already removed by merge, before edges.
        self.assertEqual(self.relation_set('edges/self_excluded_edges.csv'), set())
        primary_rows = {row['merge_key']: row for row in self.decided if row['is_primary'] == 'true'}
        self.assertEqual({key: int(row['distinct_decisions_count']) for key, row in primary_rows.items()},
                         {key: len(sources) for key, sources in EXPECTED_SOURCES.items()})
        kept = {row['merge_key'] for row in self.rows('select_out/selected.csv')
                if row['is_primary'] == 'true' and row['kept'] == 'true'}
        self.assertEqual(kept, set(EXPECTED_SOURCES))

    def test_language_scope_overlap_and_rejected_noise(self):
        candidates = self.rows('extract_out/candidates.csv')
        self.assertEqual({row['source_decision_citation'] for row in candidates}, {source for source, _ in EXPECTED_SELF})
        self.assertFalse(any('2017 SCC 999' in row['raw_string'] for row in candidates))
        classified = [row for court in COURTS for row in self.rows('classify_out/' + court + '/classified.csv')]
        self.assertTrue(any('non_citation_word' in row['rejected_reason'] for row in classified))
        self.assertTrue(any('Z.Z.R.' in row['raw_string'] and row['jurisdiction'] == 'UNSUPPORTED'
                            and not row['rejected_reason'] for row in classified))
        overlap = [row for row in self.rows('merge_out/SCC/mentions_candidates.csv') if row['merge_key'] == '1999|2|scr||100']
        self.assertGreater(len(overlap), 1)
        self.assertEqual(Counter(row['arbitration_status'] for row in overlap)['counted'], 1)

    def test_complete_compacted_run_and_coverage(self):
        manifest = json.loads((self.run_dir/'run_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['status'], 'complete')
        self.assertTrue(manifest['input_identity_verified_unchanged'])
        self.assertEqual(manifest['params']['text_policy'], 'en_then_fr')
        self.assertEqual(manifest['steps_done'][-2:], ['edges', 'coverage_report'])
        self.assertFalse(list(self.run_dir.rglob('*.csv')))
        self.assertIn('coverage/summary.json', manifest['output_identity']['files'])
        summary = json.loads((self.run_dir/'coverage/summary.json').read_text(encoding='utf-8'))
        self.assertEqual({key: summary['counted_positions'][key] for key in
            ('positions', 'distinct_sources', 'unsupported_positions', 'unsupported_distinct_sources')},
            {'positions': 11, 'distinct_sources': 6, 'unsupported_positions': 1, 'unsupported_distinct_sources': 1})
        self.assertEqual({key: summary['relations'][key] for key in ('rows', 'unique_relations', 'distinct_sources')},
                         {'rows': 10, 'unique_relations': 10, 'distinct_sources': 6})


if __name__ == '__main__':
    unittest.main()
