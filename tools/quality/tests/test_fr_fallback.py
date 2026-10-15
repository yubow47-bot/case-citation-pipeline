"""Original-text quality evidence follows the run's explicit language policy."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools/research'))
from tools.research.fixture import create_fixture, write_csv
from tools.research.core import rows, EDGE_FIELDS, DOCUMENT_FIELDS
from tools.quality import common, sample, identity_queue
from pipeline.corpus_fields import POLICY_EN, POLICY_FALLBACK


class FrenchEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.quality-fr-proof-', dir=common.ROOT)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.paths = create_fixture(self.base, with_parquet=True)
        self.run, self.corpus = Path(self.paths['run']), Path(self.paths['corpus'])
        selected = self.run / 'select_out/selected.csv.gz'
        records = [r for _, r in rows(selected)]
        for record in records:
            record.update(citation_kind='neutral', identity_basis='name_year',
                          identity_court_evidence='', identity_court_conflict='false')
        write_csv(selected, list(records[0]), records)

    def configure(self, court, policy=POLICY_FALLBACK, fr_only=False, text_only=False):
        path = self.corpus / (court + '.parquet')
        records = pq.read_table(path).to_pylist()
        old_citation = records[0]['citation_en']
        old_source = court + '_' + ''.join(c.lower() for c in old_citation if c.isascii() and c.isalnum())
        french_text = 'Décision😀 mentionne [1990] SCC 10 dans ses motifs. FR_ONLY_MARKER'
        for record in records:
            record.update(citation_fr='', name_fr='', document_date_fr='', unofficial_text_fr='')
        records[0].update(citation_fr='2012 ONCA 2' if court == 'ONCA' else '2000 CSC 1',
                          name_fr='Décision française', document_date_fr='2012-08-23' if court == 'ONCA' else '2000-01-01',
                          unofficial_text_fr=french_text)
        if fr_only:
            for field in ('citation_en', 'name_en', 'document_date_en', 'unofficial_text_en'):
                records[0][field] = ''
        elif text_only:
            records[0]['unofficial_text_en'] = ''
        pq.write_table(pa.Table.from_pylist(records), path, row_group_size=2)
        manifest_path = self.run / 'run_manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if policy is not None:
            manifest['params']['text_policy'] = policy
        manifest['input_identity']['files']['corpus/' + court + '.parquet'] = common.file_hash(path)
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        # The counted ledger itself is an independently located source span.
        selected_text = french_text if policy == POLICY_FALLBACK and (fr_only or text_only) else records[0]['unofficial_text_en']
        new_source = old_source
        if policy == POLICY_FALLBACK and fr_only:
            new_source = court + '_' + ''.join(c.lower() for c in records[0]['citation_fr'] if c.isascii() and c.isalnum())
        ledger = common.csv_path(self.run / 'merge_out' / court / 'mentions_candidates.csv')
        candidates = [r for _, r in rows(ledger)]
        for candidate in candidates:
            candidate['source_decision_citation'] = new_source
            if selected_text:
                start = selected_text.index(candidate['raw_string'])
                candidate['match_start_offset'] = str(start)
                candidate['match_end_offset'] = str(start + len(candidate['raw_string']))
        write_csv(ledger, list(candidates[0]), candidates)
        edge_path = self.run / 'edges/citation_edges.csv.gz'
        edges = [r for _, r in rows(edge_path)]
        for edge in edges:
            if edge['source_decision'] == old_source:
                edge['source_decision'] = new_source
        write_csv(edge_path, EDGE_FIELDS, edges)
        return new_source, selected_text

    def source(self):
        source = common.open_source(run=self.run)
        self.addCleanup(source.close)
        return source

    def chosen(self, result, source_id):
        return next(r for r in result['records'] if r['edge']['source_decision'] == source_id
                    and r['edge']['resolved_cited_case'] == 'XC-G000001')

    def test_fr_only_metadata_source_and_window_are_verified_in_fr_fields(self):
        source_id, french_text = self.configure('ONCA', fr_only=True)
        source = self.source()
        doc = dict(source.db.execute('SELECT * FROM documents WHERE source_id=?', (source_id,)).fetchone())
        self.assertEqual(doc['citation'], '2012 ONCA 2')
        self.assertEqual(doc['decision_date'], '2012-08-23')
        result = sample.stratified_sample(source, with_text=True)
        record = self.chosen(result, source_id)
        evidence = record['evidence']
        self.assertEqual(evidence['status'], 'original_text_verified')
        self.assertEqual(evidence['field_selection']['verification'], 'original_corpus_fields_verified')
        self.assertEqual(evidence['field_selection']['citation_field'], 'citation_fr')
        self.assertEqual(evidence['field_selection']['name_field'], 'name_fr')
        self.assertEqual(evidence['field_selection']['date_field'], 'document_date_fr')
        self.assertEqual(evidence['field_selection']['text_field'], 'unofficial_text_fr')
        self.assertEqual(evidence['span']['language'], 'fr')
        self.assertIn('Décision😀', evidence['quote_preview'])
        self.assertEqual(evidence['source_text_sha256'], common.hashlib.sha256(french_text.encode()).hexdigest())
        self.assertEqual(record['record_hash'], common.canonical_hash({k: v for k, v in record.items() if k != 'record_hash'}))
        queue = identity_queue.review_queue(source, min_impact_dd=1, with_text=True)
        preview = next(r['evidence_preview'] for r in queue['records'] if r['entity'] == 'XC-G000001')
        self.assertEqual(preview['field_selection']['text_field'], 'unofficial_text_fr')

    def test_bilingual_source_uses_en_id_metadata_and_text_once(self):
        source_id, _ = self.configure('SCC')
        source = self.source()
        self.assertEqual(source_id, 'SCC_2000scc1')
        self.assertEqual(source.db.execute('SELECT COUNT(*) FROM documents WHERE court=? AND corpus_row=0', ('SCC',)).fetchone()[0], 1)
        self.assertEqual(source.db.execute("SELECT COUNT(*) FROM documents WHERE source_id='SCC_2000csc1'").fetchone()[0], 0)
        result = sample.stratified_sample(source, with_text=True)
        evidence = self.chosen(result, source_id)['evidence']
        self.assertEqual(result['frame_N'], 6)
        self.assertEqual(evidence['status'], 'original_text_verified')
        self.assertEqual(evidence['field_selection']['citation_field'], 'citation_en')
        self.assertEqual(evidence['field_selection']['text_field'], 'unofficial_text_en')
        self.assertEqual(evidence['span']['language'], 'en')
        self.assertNotIn('FR_ONLY_MARKER', evidence['quote_preview'])

    def test_fr_text_with_existing_en_citation_keeps_primary_en_source_id(self):
        source_id, _ = self.configure('SCC', text_only=True)
        result = sample.stratified_sample(self.source(), with_text=True)
        evidence = self.chosen(result, source_id)['evidence']
        self.assertEqual(source_id, 'SCC_2000scc1')
        self.assertEqual(evidence['status'], 'original_text_verified')
        self.assertEqual(evidence['field_selection']['citation_field'], 'citation_en')
        self.assertEqual(evidence['field_selection']['text_field'], 'unofficial_text_fr')
        self.assertEqual(evidence['span']['language'], 'fr')

    def test_legacy_missing_policy_never_borrows_available_fr_text(self):
        source_id, _ = self.configure('SCC', policy=None, text_only=True)
        source = self.source()
        document = source.db.execute('SELECT citation FROM documents WHERE source_id=?', (source_id,)).fetchone()
        self.assertEqual(document['citation'], '2000 SCC 1')
        result = sample.stratified_sample(source, with_text=True)
        evidence = self.chosen(result, source_id)['evidence']
        self.assertEqual(evidence['status'], 'source_or_span_text_mismatch')
        self.assertEqual(evidence['field_selection']['text_policy'], POLICY_EN)
        # Empty EN text cannot verify the stored span. A policy declaration is
        # not original field evidence, and available FR text is never borrowed.
        self.assertIsNone(evidence['field_selection']['text_field'])
        self.assertIsNone(evidence['span']['language'])
        self.assertNotIn('FR_ONLY_MARKER', evidence.get('quote_preview', ''))

    def test_wrong_caller_fr_metadata_in_legacy_run_cannot_fake_field_proof(self):
        old_id, _ = self.configure('ONCA', policy=None, fr_only=True)
        claimed_id = 'ONCA_2012onca2'
        edge_path = self.run / 'edges/citation_edges.csv.gz'
        edges = [r for _, r in rows(edge_path)]
        for edge in edges:
            if edge['source_decision'] == old_id:
                edge['source_decision'] = claimed_id
        write_csv(edge_path, EDGE_FIELDS, edges)
        ledger = common.csv_path(self.run / 'merge_out/ONCA/mentions_candidates.csv')
        candidates = [r for _, r in rows(ledger)]
        for candidate in candidates:
            candidate['source_decision_citation'] = claimed_id
        write_csv(ledger, list(candidates[0]), candidates)
        docs_path = Path(self.paths['documents'])
        documents = [r for _, r in rows(docs_path)]
        for document in documents:
            if document['court'] == 'ONCA':
                document.update(source_id=claimed_id, citation='2012 ONCA 2', decision_date='2012-08-23')
        write_csv(docs_path, DOCUMENT_FIELDS, documents)
        source = common.open_source(run=self.run, documents=docs_path)
        self.addCleanup(source.close)
        result = sample.stratified_sample(source, with_text=True)
        evidence = self.chosen(result, claimed_id)['evidence']
        self.assertEqual(evidence['status'], 'source_or_span_text_mismatch')
        self.assertTrue(all(evidence['field_selection'][key] is None for key in
                            ('citation_field', 'name_field', 'date_field', 'text_field', 'language')))
        self.assertNotIn('source_text_sha256', evidence)
        self.assertNotIn('quote_span', evidence)

    def test_without_original_text_does_not_fabricate_a_verified_fr_field(self):
        source_id, _ = self.configure('ONCA', fr_only=True)
        result = sample.stratified_sample(self.source(), with_text=False)
        evidence = self.chosen(result, source_id)['evidence']
        self.assertEqual(evidence['status'], 'candidate_span_located_corpus_not_read')
        self.assertIsNone(evidence['field_selection']['text_field'])
        self.assertIsNone(evidence['span']['language'])
        self.assertNotEqual(evidence['field_selection']['verification'], 'original_corpus_fields_verified')

    def test_contradictory_or_missing_field_proof_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'English-only'):
            common._field_proof({'text_field': 'unofficial_text_fr', 'language': 'fr'}, POLICY_EN)
        with self.assertRaisesRegex(ValueError, 'language disagree'):
            common._field_proof({'text_field': 'unofficial_text_fr', 'language': 'en'}, POLICY_FALLBACK)
        with self.assertRaisesRegex(ValueError, 'lacks field proof'):
            common._field_proof({}, POLICY_FALLBACK, verified=True)

    def span_fixture(self, printed_span, ledger_raw='[1990] SCC 10'):
        source_id, _ = self.configure('SCC')
        path = self.corpus / 'SCC.parquet'
        records = pq.read_table(path).to_pylist()
        prefix = 'Judgment😀 mentions '
        records[0]['unofficial_text_en'] = prefix + printed_span + ' for this point.'
        pq.write_table(pa.Table.from_pylist(records), path, row_group_size=2)
        manifest_path = self.run / 'run_manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['input_identity']['files']['corpus/SCC.parquet'] = common.file_hash(path)
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        ledger = common.csv_path(self.run / 'merge_out/SCC/mentions_candidates.csv')
        candidates = [r for _, r in rows(ledger)]
        for candidate in candidates:
            candidate.update(raw_string=ledger_raw, match_start_offset=str(len(prefix)),
                             match_end_offset=str(len(prefix) + len(printed_span)))
        write_csv(ledger, list(candidates[0]), candidates)
        return source_id

    def test_cross_line_and_nbsp_match_extract_whitespace_contract(self):
        original_span = '[1990]\u00a0 SCC\n\t10'
        source_id = self.span_fixture(original_span)
        result = sample.stratified_sample(self.source(), with_text=True)
        evidence = self.chosen(result, source_id)['evidence']
        self.assertEqual(evidence['status'], 'original_text_verified')
        self.assertEqual(evidence['candidate']['raw_preview'], '[1990] SCC 10')
        self.assertIn(original_span, evidence['quote_preview'])
        self.assertEqual(evidence['span']['end'] - evidence['span']['start'], len(original_span))
        self.assertEqual(evidence['field_selection']['text_field'], 'unofficial_text_en')
        self.assertEqual(evidence['quote_sha256'], common.hashlib.sha256(evidence['quote_preview'].encode()).hexdigest())

    def test_non_whitespace_reference_difference_never_verifies(self):
        source_id = self.span_fixture('[1990] SCC 11')
        result = sample.stratified_sample(self.source(), with_text=True)
        evidence = self.chosen(result, source_id)['evidence']
        self.assertEqual(evidence['status'], 'source_or_span_text_mismatch')
        self.assertIsNone(evidence['field_selection']['text_field'])
        self.assertIsNone(evidence['span']['language'])
        self.assertNotIn('source_text_sha256', evidence)
        self.assertNotIn('quote_span', evidence)


if __name__ == '__main__':
    unittest.main()
