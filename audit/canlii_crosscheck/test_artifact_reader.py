"""No CanLII calls: raw CSV and compressed archive reads are equivalent."""
import csv
import gzip
import tempfile
import unittest
from pathlib import Path
from artifact_reader import rows, resolve_csv


class ArtifactReaderTests(unittest.TestCase):
    def test_gzip_fallback_preserves_fields_unicode_and_multiline_quotes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'selected.csv'
            values = [{'group_id': 'g', 'name': '原文, quoted\nsecond line', 'dd': '5', 'empty': ''}]
            with path.open('w', encoding='utf-8-sig', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(values[0]))
                writer.writeheader()
                writer.writerows(values)
            plain = list(rows(path))
            with gzip.open(str(path)+'.gz', 'wb') as stream:
                stream.write(path.read_bytes())
            path.unlink()
            self.assertEqual(resolve_csv(path), Path(str(path)+'.gz'))
            self.assertEqual(list(rows(path)), plain)
            self.assertEqual(list(rows(str(path)+'.gz')), values)

    def test_existing_plain_file_takes_precedence(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'edges.csv'
            path.write_text('id\nplain\n', encoding='utf-8')
            with gzip.open(str(path)+'.gz', 'wt', encoding='utf-8') as stream:
                stream.write('id\narchive\n')
            self.assertEqual(list(rows(path)), [{'id': 'plain'}])

    def test_missing_plain_and_archive_are_an_error(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):
                list(rows(Path(temp)/'missing.csv'))


if __name__ == '__main__':
    unittest.main()
