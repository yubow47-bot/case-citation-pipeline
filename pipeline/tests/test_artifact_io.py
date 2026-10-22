"""Shared artifact I/O: long CSV fields and atomic replacement while Windows scanners hold a file."""
import csv
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'pipeline'))
import artifacts  # noqa: E402


def busy(winerror):
    error = PermissionError(13, 'busy')
    error.winerror = winerror
    return error


class ArtifactIoTests(unittest.TestCase):
    def test_field_longer_than_python_default_is_readable(self):
        long_value = ';'.join('XC-R%06d' % i for i in range(30000))   # about 300 KB
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'members.csv'
            with path.open('w', encoding='utf-8', newline='') as out:
                csv.writer(out).writerows([['co_printed_run_ids'], [long_value]])
            with artifacts.open_csv(path) as source:
                rows = list(csv.DictReader(source))
        self.assertEqual(rows[0]['co_printed_run_ids'], long_value)

    def test_busy_target_is_retried_then_replaced(self):
        real = os.replace
        calls = []

        def flaky(src, dst):
            calls.append(src)
            if len(calls) < 3:
                raise busy(5 if len(calls) == 1 else 32)
            return real(src, dst)

        with tempfile.TemporaryDirectory() as temp:
            src, dst = Path(temp) / 'out.csv.tmp', Path(temp) / 'out.csv'
            src.write_text('new', encoding='utf-8')
            dst.write_text('old', encoding='utf-8')
            with mock.patch.object(artifacts.os, 'replace', flaky), \
                    mock.patch.object(artifacts.time, 'sleep'):
                artifacts.replace_file(src, dst)
            self.assertEqual(dst.read_text(encoding='utf-8'), 'new')
        self.assertEqual(len(calls), 3)

    def test_other_errors_and_exhausted_retries_are_raised(self):
        with mock.patch.object(artifacts.os, 'replace', side_effect=busy(2)), \
                mock.patch.object(artifacts.time, 'sleep'):
            with self.assertRaises(PermissionError):
                artifacts.replace_file('a', 'b')
        always_busy = mock.Mock(side_effect=busy(5))
        with mock.patch.object(artifacts.os, 'replace', always_busy), \
                mock.patch.object(artifacts.time, 'sleep'):
            with self.assertRaises(PermissionError):
                artifacts.replace_file('a', 'b', attempts=4)
        self.assertEqual(always_busy.call_count, 4)


if __name__ == '__main__':
    unittest.main()
