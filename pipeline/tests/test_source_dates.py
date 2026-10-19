"""S1: native judicial dates, publication metadata, and citation-year controls."""
import datetime as dt
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from source_integrity import inspect_source, resolve_date, build_source_records, load_source_records


def record(citation, provider, native):
    # Synthetic formal headers reconstruct the date facts of reviewed real rows.
    return {'citation': citation, 'date': dt.datetime.fromisoformat(provider),
            'text': ('Date\n' + provider + '\nNeutral citation\n' + citation +
                     '\nDecision Content\nCITATION: ' + citation + '\nDATE: ' + native +
                     '\nDOCKET: A-1\n[1] The application is dismissed.'),
            'text_field': 'unofficial_text_en'}


class SourceDateTests(unittest.TestCase):
    def test_reviewed_calendar_counterexamples(self):
        for cite, provider, native, year in [
                ('2018 ONCA 238', '2026-10-06', '20180312', '2018'),
                ('2007 ONCA 621', '2011-06-14', '20070913', '2007'),
                ('2011 ONCA 777', '2012-05-01', '20111212', '2011'),
                ('2020 FC 474', '2011-04-02', '20200402', '2020')]:
            with self.subTest(cite=cite):
                result = inspect_source(record(cite, provider, native), cite.split()[1], 0)
                self.assertEqual(result['source_decision_year'], year)
                self.assertEqual(result['date_conflict_status'], 'YEAR_CONFLICT')
                self.assertTrue(result['provider_date'].startswith(provider))

    def test_citation_year_never_replaces_the_judicial_year(self):
        for cite, provider, native, year in [
                ('2011 NSSC 506', '2012-02-22', '(20120222)', '2012'),
                ('2016 FC 18', '2011-08-12', '20110812', '2011')]:
            result = resolve_date(record(cite, provider, native))
            self.assertEqual(result['source_decision_year'], year)
            self.assertEqual(result['date_conflict_status'], 'MATCH')

    def test_body_date_and_unlabelled_web_date_are_not_judicial_evidence(self):
        selected = record('2020 FC 1', '2020-01-01', '20200101')
        selected['text'] = 'Decision Content\n[1] Quoting a different case:\nDATE: 19990101\nDocket: X'
        self.assertEqual(resolve_date(selected)['source_decision_year'], '2020')
        self.assertEqual(resolve_date(selected)['native_date_status'], 'NO_VERIFIED_NATIVE_DATE')
        selected['text'] = 'Citation: 2020 FC 1\nDate\n1999-01-01'
        self.assertEqual(resolve_date(selected)['source_decision_year'], '2020')

    def test_ambiguous_and_invalid_dates_keep_the_provider(self):
        selected = record('2020 FC 1', '2020-01-01', '19990101')
        selected['text'] = selected['text'].replace('DOCKET:', 'Date: 20010101\nDOCKET:')
        self.assertEqual(resolve_date(selected)['native_date_status'], 'AMBIGUOUS_NATIVE_DATES')
        self.assertEqual(resolve_date(selected)['source_decision_year'], '2020')
        selected = record('2020 FC 1', '2020-01-01', '19990230')
        self.assertEqual(resolve_date(selected)['native_date_status'], 'INVALID_NATIVE_DATE')

    def test_extract_and_source_export_share_resolved_year(self):
        import csv
        import pyarrow as pa
        import pyarrow.parquet as pq
        import extract
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / 'implementation') as temp:
            root = Path(temp)
            row = record('2018 ONCA 238', '2026-10-06', '20180312')
            native = {'citation_en': row['citation'], 'document_date_en': row['date'],
                      'unofficial_text_en': row['text'] + '\n2001 SCC 12'}
            pq.write_table(pa.Table.from_pylist([native]), root / 'ONCA.parquet')
            extract.run_corpus('ONCA', str(root / 'extract'), corpus_dir=str(root))
            with (root / 'extract/ONCA/cand_batch_0000.csv').open(encoding='utf-8', newline='') as f:
                candidates = list(csv.DictReader(f))
            self.assertTrue(candidates)
            self.assertTrue(all(r['source_decision_year'] == '2018' for r in candidates))
            summary = build_source_records(['ONCA'], root, 'english_only', root / 'sources')
            self.assertEqual(summary['by_court']['ONCA']['year_changed'], 1)
            exported = load_source_records(root / 'sources')['ONCA_2018onca238']
            self.assertEqual(exported['source_decision_year'], '2018')
            self.assertTrue(exported['source_measurable'])

    def test_obvious_native_year_misprints_remain_unresolved(self):
        for native in ['21070101', '02190101', '22050101']:
            result = resolve_date(record('2017 FC 1', '2017-01-01', native))
            self.assertEqual(result['source_decision_year'], '2017')
            self.assertEqual(result['native_date_status'], 'OUT_OF_RANGE_NATIVE_DATE')
            self.assertEqual(result['date_conflict_status'], 'YEAR_CONFLICT_UNRESOLVED')
            self.assertTrue(result['native_decision_date'])
        result = resolve_date(record('2024 FC 1', '2024-01-01', '20140101'))
        self.assertEqual(result['source_decision_year'], '2024')
        self.assertEqual(result['native_date_status'], 'UNRESOLVED_NATIVE_YEAR_CONFLICT')
        # Reviewed large publication delays have independent citation-year
        # corroboration; the actual adopted date still comes from DATE itself.
        result = resolve_date(record('2018 ONCA 238', '2026-10-06', '20180312'))
        self.assertEqual(result['source_decision_year'], '2018')


if __name__ == '__main__':
    unittest.main()
