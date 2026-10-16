"""Adopt an accepted local run with preserved database/pointer rollback evidence.

The default command validates and prepares a receipt. --apply switches the
canonical database and active pointer; --rollback restores both from that receipt.
No historical database is deleted or copied into an unbounded archive.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ('import', 'relations', 'cases', 'edges', 'methods', 'acceptance')


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def atomic(path, value, recover=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.pending')
    if temporary.exists():
        if not recover:
            raise ValueError('An unfinished atomic write exists: ' + str(temporary))
        if temporary.is_symlink() or getattr(temporary.lstat(), 'st_file_attributes', 0) & 0x400:
            raise ValueError('Unfinished atomic write is a link/junction')
        # Explicit recovery retains the interrupted small write as evidence.
        # Ordinary writers never steal another writer's pending file.
        retained = temporary.with_name(temporary.name + '.recovered.' + str(time.time_ns()))
        os.replace(temporary, retained)
    with temporary.open('xb') as stream:
        stream.write((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def contained(root, path):
    root, path = Path(root).resolve(), Path(path).absolute()
    if path.resolve() != path or root not in path.parents:
        raise ValueError('Publication path must remain inside the literal project: ' + str(path))
    for component in (path, *path.parents):
        if component == root:
            break
        if component.is_symlink() or (component.exists() and
                getattr(component.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('Publication paths must not traverse links or junctions')
    return path


def reader(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)


def verify_run(root, run):
    sys.path.insert(0, str(root / 'pipeline'))
    sys.path.insert(0, str(root / 'tools/foundation'))
    import run_all
    from seal import verify_output_seal
    manifest = json.loads((run / 'run_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('status') != 'complete' or manifest.get('input_identity_verified_unchanged') is not True:
        raise ValueError('Adoption requires a complete input-verified run')
    if verify_output_seal(run, manifest).get('status') != 'verified':
        raise ValueError('Adoption requires a sealed output snapshot')
    for relative, expected in manifest['input_identity']['files'].items():
        path = root / relative
        if not path.is_file() or digest(path) != expected:
            raise ValueError('Run input changed since acceptance: ' + relative)
    return manifest


def prepare(root, run, candidate, receipt, max_project_bytes=12 * 1024**3):
    root = Path(root).resolve()
    run, candidate, receipt = (contained(root, p) for p in (run, candidate, receipt))
    pointer_path = root / 'data/active_run.json'
    target = contained(root, root / 'data/foundation/research.db')
    if not re.fullmatch(r'run_[A-Za-z0-9_.-]+', run.name) or run.parent != root / 'data':
        raise ValueError('Expected a direct data/run_* directory')
    if candidate == target:
        raise ValueError('The candidate must be a separate accepted database')
    if receipt.exists():
        raise ValueError('A publication receipt already exists; refusing to overwrite it')
    for db in (target, candidate):
        for suffix in ('-wal', '-shm', '-journal'):
            sidecar = Path(str(db) + suffix)
            if sidecar.exists() and sidecar.stat().st_size:
                raise ValueError('Database has an active SQLite sidecar: ' + str(sidecar))
    old_pointer = json.loads(pointer_path.read_text(encoding='utf-8'))
    if old_pointer.get('db_path') != target.relative_to(root).as_posix():
        raise ValueError('Existing pointer does not name the canonical database')
    manifest = verify_run(root, run)
    fingerprint = manifest['input_identity']['fingerprint']
    db = reader(candidate)
    try:
        row = db.execute('SELECT status,input_fingerprint,manifest_json FROM runs WHERE run_id=?', (run.name,)).fetchone()
        if not row or row[0] != 'ready' or row[1] != fingerprint or json.loads(row[2]) != manifest:
            raise ValueError('Candidate database does not match the accepted run')
        states = dict(db.execute('SELECT component,status FROM run_components WHERE run_id=?', (run.name,)))
        if any(states.get(name) != 'ready' for name in REQUIRED):
            raise ValueError('Required candidate components are incomplete')
        if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('Candidate database integrity failed')
    finally:
        db.close()
    db = reader(target)
    try:
        old = db.execute('SELECT status,input_fingerprint FROM runs WHERE run_id=?', (old_pointer['run_id'],)).fetchone()
        if old != ('ready', old_pointer['input_fingerprint']):
            raise ValueError('Current database disagrees with the active pointer')
    finally:
        db.close()
    backup = contained(root, target.with_name('research_before_' + run.name + '.db'))
    pointer_backup = contained(root, root / ('data/active_before_' + run.name + '.json'))
    if backup.exists() or pointer_backup.exists():
        raise ValueError('Rollback targets already exist')
    sys.path.insert(0, str(ROOT))
    from tools.storage import preflight
    capacity = preflight(root, target.stat().st_size + 1024 * 1024,
                         max_project_bytes=max_project_bytes)
    pointer = dict(old_pointer, run_id=run.name, run_directory=run.relative_to(root).as_posix(),
                   db_path=target.relative_to(root).as_posix(), input_fingerprint=fingerprint,
                   previous_active_pointer=pointer_backup.relative_to(root).as_posix())
    value = {'protocol': 'reversible-local-adoption-v1', 'status': 'prepared',
             'created_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'run': str(run),
             'candidate': str(candidate), 'target': str(target), 'backup': str(backup),
             'pointer_backup': str(pointer_backup), 'old_pointer': old_pointer, 'new_pointer': pointer,
             'old_database_sha256': digest(target), 'new_database_sha256': digest(candidate),
             'storage_budget': capacity,
             'required_components': states,
             'historical_quality_scope': 'Any retained historical_quality describes its original run, not new-run accuracy.'}
    atomic(receipt, value)
    return value


def apply(root, receipt):
    root = Path(root).resolve()
    receipt = contained(root, receipt)
    value = json.loads(receipt.read_text(encoding='utf-8'))
    if value['status'] != 'prepared':
        raise ValueError('Only a prepared adoption can be applied')
    manifest = verify_run(root, contained(root, value['run']))
    if manifest['input_identity']['fingerprint'] != value['new_pointer']['input_fingerprint']:
        raise ValueError('Prepared run fingerprint changed')
    candidate, target, backup, pointer_backup = (contained(root, value[name]) for name in
                                               ('candidate', 'target', 'backup', 'pointer_backup'))
    pointer_path = root / 'data/active_run.json'
    if (json.loads(pointer_path.read_text(encoding='utf-8')) != value['old_pointer']
            or digest(target) != value['old_database_sha256']
            or digest(candidate) != value['new_database_sha256']):
        raise ValueError('Publication inputs changed after preparation')
    from tools.storage import preflight
    preflight(root, target.stat().st_size + 1024 * 1024,
              max_project_bytes=value['storage_budget']['max_project_bytes'])
    # Keep all old annotations. Windows sandbox/volumes may disallow hard links;
    # a bounded, budgeted copy is then checked before any active file is touched.
    try:
        os.link(target, backup)
        value['backup_method'] = 'hardlink'
    except OSError:
        if backup.exists():
            raise ValueError('Rollback backup appeared during publication')
        shutil.copyfile(target, backup)
        value['backup_method'] = 'verified_copy'
    if digest(backup) != value['old_database_sha256']:
        raise ValueError('Rollback backup hash disagrees with the current database')
    atomic(pointer_backup, value['old_pointer'])
    value['status'] = 'applying'
    atomic(receipt, value)
    os.replace(candidate, target)
    try:
        atomic(pointer_path, value['new_pointer'])
    except BaseException:
        os.replace(target, candidate)
        os.replace(backup, target)
        raise
    value['status'] = 'applied'
    atomic(receipt, value)
    return value


def rollback(root, receipt):
    root = Path(root).resolve()
    receipt = contained(root, receipt)
    value = json.loads(receipt.read_text(encoding='utf-8'))
    if value['status'] not in ('prepared', 'applied', 'applying', 'rolling_back', 'rolled_back'):
        raise ValueError('Unknown adoption state; refusing rollback')
    candidate, target, backup = (contained(root, value[name]) for name in ('candidate', 'target', 'backup'))
    pointer_path = root / 'data/active_run.json'
    current_pointer = json.loads(pointer_path.read_text(encoding='utf-8'))
    if current_pointer not in (value['new_pointer'], value['old_pointer']):
        raise ValueError('Rollback inputs no longer match the adoption receipt')
    old_hash, new_hash = value['old_database_sha256'], value['new_database_sha256']
    target_hash = digest(target) if target.is_file() else None
    candidate_hash = digest(candidate) if candidate.is_file() else None
    backup_hash = digest(backup) if backup.is_file() else None
    if target_hash not in (None, old_hash, new_hash) or candidate_hash not in (None, new_hash):
        raise ValueError('Rollback database bytes changed outside this adoption')
    # Distinguish each interrupted physical state rather than assuming that the
    # previous attempt reached both renames. Every completed step is retryable.
    if target_hash == new_hash and (candidate_hash is not None or backup_hash != old_hash):
        raise ValueError('Rollback cannot safely recover the old/new databases')
    if target_hash is None and not (candidate_hash == new_hash and backup_hash == old_hash):
        raise ValueError('Rollback is missing a recoverable database')
    if target_hash == old_hash and candidate_hash != new_hash:
        raise ValueError('Rollback candidate generation is missing')
    value['status'] = 'rolling_back'
    atomic(receipt, value, recover=True)
    if target_hash == new_hash:
        os.replace(target, candidate)
        target_hash = None
    if target_hash is None:
        os.replace(backup, target)
    atomic(pointer_path, value['old_pointer'], recover=True)
    value['status'] = 'rolled_back'
    atomic(receipt, value, recover=True)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--run')
    parser.add_argument('--db')
    parser.add_argument('--receipt', required=True)
    parser.add_argument('--storage-budget-gb', type=float, default=12)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--rollback', action='store_true')
    args = parser.parse_args(argv)
    if args.rollback:
        result = rollback(ROOT, args.receipt)
    elif args.apply and Path(args.receipt).is_file():
        result = apply(ROOT, args.receipt)
    else:
        if not args.run or not args.db:
            parser.error('--run and --db are required to prepare an adoption')
        result = prepare(ROOT, args.run, args.db, args.receipt,
                         int(args.storage_budget_gb * 1024**3))
        if args.apply:
            result = apply(ROOT, args.receipt)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
