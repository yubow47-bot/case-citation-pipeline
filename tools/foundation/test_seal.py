"""A current checksum cannot re-bless bytes that differ from the run's output seal."""
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from seal import verify_output_seal


class OutputSealTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)
        self.path = self.run/'selected.csv.gz'
        with gzip.open(self.path, 'wb') as target:
            target.write(b'id,value\nx,one\n')
        files = {'selected.csv.gz': hashlib.sha256(self.path.read_bytes()).hexdigest()}
        self.manifest = {'output_identity': {'files': files,
            'fingerprint': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}}

    def test_compressed_consumed_source_is_verified(self):
        self.assertEqual(verify_output_seal(self.run, self.manifest, ['selected.csv'])['status'], 'verified')

    def test_preimport_same_length_tamper_is_rejected(self):
        content = bytearray(self.path.read_bytes())
        content[-1] ^= 1
        self.path.write_bytes(content)
        with self.assertRaisesRegex(ValueError, 'changed'):
            verify_output_seal(self.run, self.manifest)

    def test_missing_required_file_cannot_be_blessed_by_partial_seal(self):
        with self.assertRaisesRegex(ValueError, 'absent'):
            verify_output_seal(self.run, self.manifest, ['unsealed.csv'])

    def test_fingerprint_tamper_is_rejected(self):
        self.manifest['output_identity']['fingerprint'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify_output_seal(self.run, self.manifest)

    def test_historical_unsealed_run_is_explicit(self):
        self.assertEqual(verify_output_seal(self.run, {})['status'], 'historical_unsealed')

    def test_parent_escape_is_rejected(self):
        files = {'../outside.csv': 'a'*64}
        manifest = {'output_identity': {'files': files,
            'fingerprint': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}}
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            verify_output_seal(self.run, manifest)


if __name__ == '__main__':
    unittest.main()
