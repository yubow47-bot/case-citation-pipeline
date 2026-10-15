"""Source tracing must bind compressed ledgers and exact original corpus bytes."""
import contextlib
import csv
import gzip
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import trace_source as trace


class TraceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]/'implementation')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.corpus = self.root/'relocated'
        self.corpus.mkdir()
        self.text = 'A source judgment cites 2000 TCC 12. End.'
        self.path = self.corpus/'TCC.parquet'
        pq.write_table(pa.table({'unofficial_text_en': [self.text], 'citation_en': ['2020 TCC 1'],
                                 'document_date_en': ['2020-01-02']}), self.path)
        self.run = self.root/'run_test'
        (self.run/'merge_out/TCC').mkdir(parents=True)
        start = self.text.index('2000')
        self.row = {'candidate_id': 'TCC:0:24:35:neutral_bare', 'corpus_row_index': '0',
                    'match_start_offset': str(start), 'match_end_offset': str(start+11),
                    'raw_string': '2000 TCC 12', 'shape_name': 'neutral_bare',
                    'arbitration_status': 'counted', 'citation_kind': 'neutral',
                    'jurisdiction': 'CA', 'jurisdiction_confidence': 'verified',
                    'merge_key': 'test', 'candidate_case_name': 'Test Case'}
        with gzip.open(self.run/'merge_out/TCC/mentions_candidates.csv.gz', 'wt', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(self.row))
            writer.writeheader()
            writer.writerow(self.row)
        manifest = {'status': 'complete', 'input_identity_verified_unchanged': True,
                    'params': {'courts': ['TCC'], 'corpus_dir': str(self.root/'missing_original')},
                    'input_identity': {'files': {'corpus/TCC.parquet': trace.sha256(self.path)}}}
        (self.run/'run_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')

    def test_new_court_search_reads_gzip_ledger(self):
        hits = trace.search_candidates(self.run, '2000 TCC')
        self.assertEqual([(court, r['candidate_id']) for court, r in hits], [('TCC', self.row['candidate_id'])])

    def test_candidate_id_is_exact_not_prefix(self):
        self.assertEqual(trace.find_candidate(self.run, 'TCC', 0, -1, -1, 'TCC:0:24'), (None, None))
        self.assertEqual(trace.find_candidate(self.run, 'TCC', 0, -1, -1, self.row['candidate_id'])[0], 'TCC')

    def test_relocated_identical_corpus_returns_exact_original_span(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            trace.show(self.run, 'TCC', self.row, self.corpus)
        self.assertIn('<<2000 TCC 12>>', output.getvalue())

    def test_changed_corpus_is_rejected_before_returning_text(self):
        self.path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'does not match'):
            trace.corpus_row('TCC', 0, self.run, self.corpus)

    def test_wrong_offset_is_rejected(self):
        row = dict(self.row, match_start_offset='0', match_end_offset='11')
        with self.assertRaisesRegex(ValueError, 'span does not agree'):
            trace.show(self.run, 'TCC', row, self.corpus)

    def test_negative_corpus_row_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'nonnegative'):
            trace.corpus_row('TCC', -1, self.run, self.corpus)


if __name__ == '__main__':
    unittest.main()
