"""Verify physical output bytes before accepting a sealed pipeline run."""
import hashlib
import json
from pathlib import Path
import re
import stat


def verify_output_seal(run_dir, manifest, required=()):
    run_dir = Path(run_dir).resolve()
    seal = manifest.get('output_identity')
    if seal is None:
        return {'status': 'historical_unsealed', 'files_verified': 0}
    if not isinstance(seal, dict) or not isinstance(seal.get('files'), dict) or not seal['files']:
        raise ValueError('Output seal has no valid artifact list')
    files = seal['files']
    fingerprint = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    if fingerprint != seal.get('fingerprint'):
        raise ValueError('Output seal fingerprint disagrees with its artifact list')
    for relative, expected in files.items():
        path = Path(relative)
        if path.is_absolute() or path.drive or '..' in path.parts or not path.parts or '\\' in relative or ':' in relative:
            raise ValueError('Unsafe path in output seal: ' + relative)
        current = run_dir
        for part in path.parts:
            current = current/part
            metadata = current.lstat()
            if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Output seal artifact traverses a link/junction: ' + relative)
        if not current.is_file() or not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError('Invalid artifact in output seal: ' + relative)
        actual = hashlib.sha256()
        with current.open('rb') as source:
            for chunk in iter(lambda: source.read(1024*1024), b''):
                actual.update(chunk)
        if actual.hexdigest() != expected:
            raise ValueError('Sealed output artifact changed: ' + relative)
    for relative in required:
        actual = relative if (run_dir/relative).is_file() else relative+'.gz'
        if actual not in files:
            raise ValueError('Consumed artifact is absent from output seal: ' + relative)
    return {'status': 'verified', 'files_verified': len(files), 'fingerprint': fingerprint}
