"""Native pair exclusions reject stale, forged and incorrectly bound sources."""
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import identity_pairs as pairs


class PairSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'decisions').mkdir()
        (self.root / 'corpus').mkdir()
        self.path = self.root / 'decisions/identity_pair_separations.csv'
        self.corpus = self.root / 'corpus/ONCA.parquet'
        self.text = ('R. v. McCormack, 2009 CanLII 76382 (Ont. S.C.) ("Delay Decision"). '
                     'The court also distinguishes R. v. McCormack, 2009 CarswellOnt 7019 '
                     '(S.C.) ("Disclosure Decision").')
        pq.write_table(pa.Table.from_pylist([{'citation_en': '2025 ONCA 767',
                                            'unofficial_text_en': self.text}]), self.corpus)
        self.row = dict.fromkeys(pairs.PAIR_FIELDS, '')
        self.row.update(left_merge_key='2009||canlii||76382', right_merge_key='2009||carswellont||7019',
                        relation_type='verified_distinct_decisions',
                        verification_status='verified_corpus_distinct_decisions',
                        source_court='ONCA', source_decision='ONCA_2025onca767',
                        source_corpus='corpus/ONCA.parquet', corpus_sha256=pairs._digest(self.corpus),
                        corpus_row='0', text_field='unofficial_text_en',
                        text_sha256=hashlib.sha256(self.text.encode()).hexdigest(),
                        left_raw='2009 CanLII 76382', right_raw='2009 CarswellOnt 7019',
                        span_start='0', span_end=str(len(self.text)),
                        span_sha256=hashlib.sha256(self.text.encode()).hexdigest(),
                        distinction_quote='"Disclosure Decision"',
                        source_locator='audit/findings/fixture/proof.json#different',
                        reviewer='fixture', reviewed_at='2026-10-16')
        for side in ('left', 'right'):
            start = self.text.index(self.row[side + '_raw'])
            self.row[side + '_start'] = str(start)
            self.row[side + '_end'] = str(start + len(self.row[side + '_raw']))
        pairs._CACHE.clear()

    def write(self, rows=None):
        rows = copy.deepcopy(rows if rows is not None else [self.row])
        for row in rows:
            if not row.get('right_proof_json'):
                row['right_proof_json'] = json.dumps({k: row[k] for k in pairs.PROOF_FIELDS},
                                                     ensure_ascii=False, sort_keys=True, separators=(',', ':'))
            row['evidence_id'] = pairs.evidence_id(row)
        with self.path.open('w', encoding='utf-8', newline='') as out:
            writer = csv.DictWriter(out, fieldnames=pairs.PAIR_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def load(self):
        return pairs.load_pair_separations(self.path, self.root)

    def test_native_binding_and_defensive_cache_copy(self):
        self.write()
        result = self.load()
        self.assertEqual(result[0]['source_detail']['source_decision'], 'ONCA_2025onca767')
        self.assertEqual(result[0]['table_evidence_id'], result[0]['evidence_id'])
        result[0]['left_merge_key'] = 'forged'
        self.assertEqual(self.load()[0]['left_merge_key'], self.row['left_merge_key'])

    def test_rehashed_false_key_is_not_native_evidence(self):
        self.row['right_merge_key'] = '2009||carswellont||7020'
        self.write()
        with self.assertRaisesRegex(ValueError, 'does not print'):
            self.load()

    def test_continuous_reporter_key_uses_production_year_normalization(self):
        printed = '(1975), 22 C.C.C. (2d) 19'
        self.text = self.text.replace(self.row['right_raw'], printed)
        pq.write_table(pa.Table.from_pylist([{'citation_en': '2025 ONCA 767',
                                            'unofficial_text_en': self.text}]), self.corpus)
        text_hash = hashlib.sha256(self.text.encode()).hexdigest()
        start = self.text.index(printed)
        self.row.update(right_merge_key='|22|ccc|2d|19', right_raw=printed,
                        right_start=str(start), right_end=str(start + len(printed)),
                        corpus_sha256=pairs._digest(self.corpus), text_sha256=text_hash,
                        span_end=str(len(self.text)), span_sha256=text_hash)
        self.write()
        self.assertEqual(self.load()[0]['right_merge_key'], '|22|ccc|2d|19')

    def test_rehashed_wrong_document_is_rejected(self):
        self.row['source_decision'] = 'ONCA_2025onca768'
        self.write()
        with self.assertRaisesRegex(ValueError, 'document is misbound'):
            self.load()

    def test_wrong_offset_quote_and_duplicate_pairs_are_rejected(self):
        for field, value, error in [('left_start', '0', 'span is misbound'),
                                    ('distinction_quote', 'not in original text', 'distinction span')]:
            row = copy.deepcopy(self.row)
            row[field] = value
            self.write([row])
            with self.assertRaisesRegex(ValueError, error):
                self.load()
        self.write([self.row, self.row])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.load()

    def test_changed_corpus_is_not_a_cache_hit(self):
        self.write()
        self.load()
        pq.write_table(pa.Table.from_pylist([{'citation_en': '2025 ONCA 767',
                                            'unofficial_text_en': self.text + ' altered'}]), self.corpus)
        with self.assertRaisesRegex(ValueError, 'corpus hash changed'):
            self.load()

    def test_same_size_and_mtime_cannot_hide_changed_corpus(self):
        self.write()
        self.load()
        before = self.corpus.stat()
        contents = bytearray(self.corpus.read_bytes())
        contents[len(contents) // 2] ^= 1
        self.corpus.write_bytes(contents)
        os.utime(self.corpus, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(self.corpus.stat().st_size, before.st_size)
        self.assertEqual(self.corpus.stat().st_mtime_ns, before.st_mtime_ns)
        with self.assertRaisesRegex(ValueError, 'corpus hash changed'):
            self.load()

    def test_explicit_missing_source_and_empty_table(self):
        with self.assertRaises(FileNotFoundError):
            self.load()
        self.write([])
        self.assertEqual(self.load(), [])

    def test_unrelated_scope_needs_no_native_corpus(self):
        self.write()
        self.corpus.unlink()
        self.assertEqual(pairs.load_pair_separations(self.path, self.root, keys={'2000||scc||1'}), [])
        with self.assertRaisesRegex(ValueError, 'corpus is missing'):
            pairs.load_pair_separations(self.path, self.root,
                keys={self.row['left_merge_key'], self.row['right_merge_key']})

    def test_two_source_rulings_are_bound_independently(self):
        other = self.root / 'corpus/SCC.parquet'
        second_text = 'R. v. Marshall, 2005 SCC 43. Reasons for judgment on the appeal.'
        pq.write_table(pa.Table.from_pylist([{'citation_en': '2005 SCC 43',
                                            'unofficial_text_en': second_text}]), other)
        raw = '2005 SCC 43'
        proof = {'source_court': 'SCC', 'source_decision': 'SCC_2005scc43',
                 'source_corpus': 'corpus/SCC.parquet', 'corpus_sha256': pairs._digest(other),
                 'corpus_row': '0', 'text_field': 'unofficial_text_en',
                 'text_sha256': hashlib.sha256(second_text.encode()).hexdigest(),
                 'span_start': '0', 'span_end': str(len(second_text)),
                 'span_sha256': hashlib.sha256(second_text.encode()).hexdigest(),
                 'distinction_quote': 'Reasons for judgment'}
        self.row['right_proof_json'] = json.dumps(proof)
        self.row['right_merge_key'] = '2005||scc||43'
        self.row['right_raw'] = raw
        self.row['right_start'] = str(second_text.index(raw))
        self.row['right_end'] = str(second_text.index(raw) + len(raw))
        self.write()
        self.assertEqual(self.load()[0]['source_detail']['right_source']['source_decision'], 'SCC_2005scc43')
        proof['source_decision'] = 'SCC_2005scc44'
        self.row['right_proof_json'] = json.dumps(proof)
        self.write()
        with self.assertRaisesRegex(ValueError, 'document is misbound'):
            self.load()


if __name__ == '__main__':
    unittest.main()
