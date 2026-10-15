"""Bound project disk growth and compact disposable run artifacts safely.

Inventory never follows links or Windows junctions. Run deletion is explicit;
small receipts retain provenance rather than keeping another full archive.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import heapq
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile

GiB = 1024 ** 3
MiB = 1024 ** 2
DEFAULT_MAX_PROJECT_BYTES = 12 * GiB
DEFAULT_MIN_FREE_BYTES = 2 * GiB


class StorageError(ValueError):
    """A storage operation cannot safely proceed."""


class StorageLimitError(StorageError):
    def __init__(self, report):
        self.report = report
        reasons = []
        if report['projected_peak_bytes'] > report['max_project_bytes']:
            reasons.append('project peak exceeds the configured project budget')
        if report['free_after_peak_bytes'] < report['min_free_bytes']:
            reasons.append('peak would consume the required free-space reserve')
        super().__init__('; '.join(reasons))


def _link(path, st=None):
    st = st or path.lstat()
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, 'st_file_attributes', 0) & 0x400)


def _directory(path):
    path = Path(os.path.abspath(path))
    if not path.is_dir() or _link(path):
        raise StorageError('Expected a plain directory, not a link/junction: ' + str(path))
    return path


def _tree(root, reject_links=False, diagnostics=None):
    """Inventory tolerates concurrent removals; destructive scans fail closed."""
    def disappeared(path):
        if reject_links:
            raise StorageError('Filesystem entry disappeared during strict scan: ' + str(path))
        if diagnostics is not None:
            diagnostics['concurrent_missing_entries'] = diagnostics.get('concurrent_missing_entries', 0) + 1
            paths = diagnostics.setdefault('concurrent_missing_paths', [])
            if len(paths) < 10:
                paths.append(str(path))

    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            if _link(directory):
                raise StorageError('Directory changed into a link/junction: ' + str(directory))
            with os.scandir(directory) as entries:
                entries = sorted(entries, key=lambda e: e.name)
        except FileNotFoundError:
            disappeared(directory)
            continue
        for entry in entries:
            path = Path(entry.path)
            # On Windows DirEntry.stat can return inode/dev=0; use os.stat/lstat.
            try:
                st = path.lstat()
            except FileNotFoundError:
                disappeared(path)
                continue
            if _link(path, st):
                if reject_links:
                    raise StorageError('Refusing a tree containing a link/junction: ' + str(path))
                yield path, st, True
            elif stat.S_ISDIR(st.st_mode):
                pending.append(path)
            elif stat.S_ISREG(st.st_mode):
                yield path, st, False
            else:
                raise StorageError('Unsupported filesystem entry: ' + str(path))


def inventory(root):
    """Return a bounded inventory; directory sizes overlap only within this report."""
    root = _directory(root)
    children = {}
    largest = []
    total = count = unique = 0
    identities = set()
    links = []
    link_count = 0
    concurrent = {'concurrent_missing_entries': 0, 'concurrent_missing_paths': []}
    for path, st, is_link in _tree(root, diagnostics=concurrent):
        if is_link:
            link_count += 1
            if len(links) < 100:
                links.append(str(path))
            continue
        total += st.st_size
        count += 1
        identity = (st.st_dev, st.st_ino)
        # Treat unavailable file identities as distinct rather than silently
        # claiming that every file is a hard link to the first file.
        if not st.st_ino or identity not in identities:
            unique += st.st_size
            identities.add(identity)
        name = path.relative_to(root).parts[0]
        child = children.setdefault(name, {'name': name, 'bytes': 0, 'file_count': 0})
        child['bytes'] += st.st_size
        child['file_count'] += 1
        row = (st.st_size, str(path))
        if len(largest) < 20:
            heapq.heappush(largest, row)
        elif row > largest[0]:
            heapq.heapreplace(largest, row)
    return dict(concurrent, **{'root': str(root), 'total_bytes': total, 'unique_file_bytes': unique,
            'file_count': count, 'skipped_link_count': link_count, 'skipped_links': links,
            'largest_children': sorted(children.values(), key=lambda c: (-c['bytes'], c['name']))[:30],
            'largest_files': [{'path': p, 'bytes': n} for n, p in sorted(largest, reverse=True)],
            'measurement': 'Logical file lengths; links/junctions excluded; not allocated disk blocks. Concurrent removals are skipped; replacement entries are captured by the next guard scan.'})


def preflight(root, estimated_peak_bytes, max_project_bytes=DEFAULT_MAX_PROJECT_BYTES,
              min_free_bytes=DEFAULT_MIN_FREE_BYTES):
    """Check additional peak bytes against both project budget and free disk reserve."""
    values = [estimated_peak_bytes, max_project_bytes, min_free_bytes]
    if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in values):
        raise StorageError('Storage estimates and limits must be non-negative integer bytes')
    root = _directory(root)
    size = inventory(root)['total_bytes']
    free = shutil.disk_usage(root).free
    report = {'root': str(root), 'project_bytes': size, 'estimated_peak_bytes': estimated_peak_bytes,
              'projected_peak_bytes': size + estimated_peak_bytes, 'max_project_bytes': max_project_bytes,
              'free_bytes': free, 'free_after_peak_bytes': free - estimated_peak_bytes,
              'min_free_bytes': min_free_bytes}
    report['allowed'] = (report['projected_peak_bytes'] <= max_project_bytes
                         and report['free_after_peak_bytes'] >= min_free_bytes)
    if not report['allowed']:
        raise StorageLimitError(report)
    return report


def _manifest(run_dir, allowed):
    path = run_dir / 'run_manifest.json'
    if not path.is_file() or _link(path):
        raise StorageError('Run must have a regular run_manifest.json: ' + str(run_dir))
    try:
        raw = path.read_bytes()
        manifest = json.loads(raw.decode('utf-8-sig'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StorageError('Unreadable run manifest: ' + str(path)) from exc
    if not isinstance(manifest, dict) or manifest.get('status') not in allowed:
        raise StorageError('Unsafe run status: ' + str(manifest.get('status') if isinstance(manifest, dict) else manifest))
    return manifest, hashlib.sha256(raw).hexdigest()


def _content_signature(path, compressed=False):
    digest = hashlib.sha256()
    size = 0
    with (gzip.open(path, 'rb') if compressed else path.open('rb')) as stream:
        for block in iter(lambda: stream.read(MiB), b''):
            digest.update(block)
            size += len(block)
    return size, digest.hexdigest()


def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def compact_run(run_dir, compresslevel=6):
    """Losslessly gzip every plain CSV, verify content, then remove that plain CSV.

    Historical manifests are never rewritten. A separate compact_receipt.json
    records content hashes and storage changes. Complete, failed, and finalizing
    runs may be compacted; running/unknown/corrupt manifests are rejected.
    """
    if not isinstance(compresslevel, int) or not 0 <= compresslevel <= 9:
        raise StorageError('gzip compression level must be an integer from 0 to 9')
    run_dir = _directory(run_dir)
    manifest, manifest_sha = _manifest(run_dir, {'complete', 'failed', 'finalizing'})
    files = list(_tree(run_dir, reject_links=True))
    before = sum(st.st_size for _, st, _ in files)
    converted = []
    for path, st, _ in files:
        if path.suffix.lower() != '.csv':
            continue
        _, current_sha = _manifest(run_dir, {'complete', 'failed', 'finalizing'})
        if current_sha != manifest_sha:
            raise StorageError('Run manifest changed during compaction: ' + str(run_dir))
        if _link(path) or not path.is_file():
            raise StorageError('CSV changed during compaction: ' + str(path))
        target = path.with_name(path.name + '.gz')
        source_signature = _content_signature(path)
        if target.exists():
            if _link(target) or _content_signature(target, compressed=True) != source_signature:
                raise StorageError('Existing gzip conflicts with plain CSV: ' + str(target))
            if _content_signature(path) != source_signature:
                raise StorageError('CSV changed during gzip validation: ' + str(path))
            _, current_sha = _manifest(run_dir, {'complete', 'failed', 'finalizing'})
            if current_sha != manifest_sha:
                raise StorageError('Run manifest changed during compaction: ' + str(run_dir))
            path.unlink()
        else:
            # One-file scratch space bounds the extra storage required by gzip.
            if shutil.disk_usage(run_dir).free < st.st_size + 64 * MiB:
                raise StorageError('Insufficient temporary space to safely gzip: ' + str(path))
            fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.gz.tmp', dir=path.parent)
            temporary = Path(temporary)
            try:
                with os.fdopen(fd, 'wb') as destination:
                    with gzip.GzipFile(filename='', fileobj=destination, mode='wb',
                                       compresslevel=compresslevel, mtime=0) as compressed:
                        with path.open('rb') as source:
                            shutil.copyfileobj(source, compressed, length=MiB)
                    destination.flush()
                    os.fsync(destination.fileno())
                if (_content_signature(temporary, compressed=True) != source_signature
                        or _content_signature(path) != source_signature):
                    raise StorageError('gzip content verification failed: ' + str(path))
                # Recheck manifest before the first destructive step for this CSV.
                _, current_sha = _manifest(run_dir, {'complete', 'failed', 'finalizing'})
                if current_sha != manifest_sha:
                    raise StorageError('Run manifest changed during compaction: ' + str(run_dir))
                os.replace(temporary, target)
                path.unlink()
            finally:
                if temporary.exists():
                    temporary.unlink()
        converted.append({'path': str(target.relative_to(run_dir)),
                          'logical_bytes': source_signature[0], 'sha256': source_signature[1],
                          'compressed_bytes': target.stat().st_size})
    after = sum(st.st_size for _, st, _ in _tree(run_dir, reject_links=True))
    report = {'run': str(run_dir), 'status': manifest['status'], 'manifest_sha256': manifest_sha,
              'before_bytes': before, 'after_bytes_before_receipt': after,
              'saved_bytes': before - after, 'csv_files_compacted': len(converted), 'files': converted,
              'completed_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    # A repeat with no CSV must not erase the first compaction's provenance.
    receipt = run_dir / 'compact_receipt.json'
    if converted or not receipt.exists():
        _atomic_json(receipt, report)
    return report


def _remove_tree(run_dir, data_root):
    """Windows deletions use native PowerShell with literal paths throughout."""
    list(_tree(run_dir, reject_links=True))
    if os.name == 'nt':
        env = dict(os.environ, CITATION_STORAGE_TARGET=str(run_dir), CITATION_STORAGE_DATA=str(data_root))
        code = r"""
$ErrorActionPreference = 'Stop'
$target = [IO.Path]::GetFullPath($env:CITATION_STORAGE_TARGET)
$root = [IO.Path]::GetFullPath($env:CITATION_STORAGE_DATA)
if (-not $target.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Target outside data root' }
$item = Get-Item -LiteralPath $target -Force
if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Unsafe target' }
$pending = [Collections.Generic.Stack[string]]::new()
$pending.Push($target)
while ($pending.Count -gt 0) {
  foreach ($entry in Get-ChildItem -LiteralPath ($pending.Pop()) -Force) {
    if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse point in target' }
    if ($entry.PSIsContainer) { $pending.Push($entry.FullName) }
  }
}
Remove-Item -LiteralPath $target -Recurse -Force
"""
        result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', code],
                                env=env, capture_output=True, text=True)
        if result.returncode:
            raise StorageError('Native deletion failed: ' + result.stderr.strip())
    else:
        shutil.rmtree(run_dir)
    if run_dir.exists():
        raise StorageError('Deletion did not finish: ' + str(run_dir))


def delete_run(root, run_name, receipt_max_bytes=2 * MiB):
    """Delete one explicitly named historical data/run_* with bounded receipts."""
    if not isinstance(run_name, str) or not re.fullmatch(r'run_[A-Za-z0-9][A-Za-z0-9_.-]*', run_name):
        raise StorageError('Explicit run directory name required; paths and wildcards are forbidden')
    if not isinstance(receipt_max_bytes, int) or receipt_max_bytes < 0:
        raise StorageError('Receipt limit must be non-negative integer bytes')
    root = _directory(root)
    data_root = _directory(root / 'data')
    run_dir = _directory(data_root / run_name)
    manifest, manifest_sha = _manifest(run_dir, {'complete', 'failed'})
    files = list(_tree(run_dir, reject_links=True))
    before = sum(st.st_size for _, st, _ in files)
    seen_content, exclusive_content, shared_content = set(), 0, 0
    for _, st, _ in files:
        identity = (st.st_dev, st.st_ino)
        # An unavailable inode cannot establish uniqueness. Count it only in
        # removed logical paths; refuse to claim that its content was released.
        if not st.st_ino or identity in seen_content:
            continue
        seen_content.add(identity)
        if st.st_nlink == 1:
            exclusive_content += st.st_size
        else:
            shared_content += st.st_size
    manifest_path = run_dir / 'run_manifest.json'
    receipt_parent = data_root / 'run_receipts'
    if receipt_parent.exists():
        _directory(receipt_parent)
    else:
        receipt_parent.mkdir()
    receipt_dir = receipt_parent / (run_name + '_deleted')
    if receipt_dir.exists():
        raise StorageError('A deletion receipt already exists; refusing to overwrite: ' + str(receipt_dir))
    saved = 0
    retained = []
    candidates = [(p, s) for p, s, _ in files
                  if p.suffix.lower() in {'.json', '.log', '.txt'} and (p == manifest_path or s.st_size <= 200 * 1024)]
    candidates.sort(key=lambda row: (0 if row[0] == manifest_path else 1 if row[0].name.startswith('step_') else 2,
                                    str(row[0])))
    report = {'run': str(run_dir), 'run_status': manifest['status'], 'manifest_sha256': manifest_sha,
              'before_bytes': before, 'after_bytes': 0, 'receipt_directory': str(receipt_dir),
              'removed_logical_bytes': before, 'released_bytes': exclusive_content,
              'hardlinked_content_bytes_not_counted_as_released': shared_content,
              'receipt_total_bytes': 0, 'net_released_content_bytes_lower_bound': exclusive_content,
              'space_accounting_note': ('removed_logical_bytes counts all deleted paths. released_bytes counts unique '
                  'pre-delete inodes with st_nlink=1 only; multi-link content is excluded even when all links '
                  'might be inside the deleted run. These are content-length lower bounds, not allocated '
                  'disk blocks or measured disk-free changes. Net lower bound subtracts receipt file lengths.'),
              'retained_bytes': saved, 'receipt_limit_bytes': receipt_max_bytes, 'retained_files': retained,
              'action': 'direct_delete_without_archive', 'status': 'prepared',
              'created_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    selected = []
    # Budget the receipt JSON as well as copied payloads. The extra 1 KiB
    # accommodates the final status/space accounting fields after deletion.
    for path, st in candidates:
        relative = path.relative_to(run_dir)
        row = {'path': str(relative), 'bytes': st.st_size, 'sha256': _content_signature(path)[1]}
        proposed = dict(report, retained_bytes=saved + st.st_size,
                        retained_files=retained + [row])
        metadata_size = len((json.dumps(proposed, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        if saved + st.st_size + metadata_size + 1024 > receipt_max_bytes:
            if path == manifest_path:
                raise StorageError('Receipt limit cannot hold the mandatory manifest and receipt metadata')
            continue
        retained.append(row)
        selected.append((path, relative))
        saved += st.st_size
    receipt_dir.mkdir()
    for path, relative in selected:
        destination = receipt_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    report['retained_bytes'] = saved
    report['retained_files'] = retained
    _atomic_json(receipt_dir / 'deletion_receipt.json', report)
    _, current_sha = _manifest(run_dir, {'complete', 'failed'})
    if current_sha != manifest_sha:
        raise StorageError('Run changed while creating deletion receipts')
    current = list(_tree(run_dir, reject_links=True))
    if {(str(p), s.st_size, s.st_mtime_ns, s.st_dev, s.st_ino, s.st_nlink) for p, s, _ in current} != \
            {(str(p), s.st_size, s.st_mtime_ns, s.st_dev, s.st_ino, s.st_nlink) for p, s, _ in files}:
        raise StorageError('Run files changed while creating deletion receipts')
    _remove_tree(run_dir, data_root)
    report['status'] = 'deleted'
    _atomic_json(receipt_dir / 'deletion_receipt.json', report)
    # Persist accounting too. Its few integer widths converge after rewriting;
    # receipts remain within the already-reserved metadata budget.
    for _ in range(4):
        total = inventory(receipt_dir)['total_bytes']
        report['receipt_total_bytes'] = total
        report['net_released_content_bytes_lower_bound'] = exclusive_content - total
        _atomic_json(receipt_dir / 'deletion_receipt.json', report)
        if inventory(receipt_dir)['total_bytes'] == total:
            break
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    inv = sub.add_parser('inventory')
    inv.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    check = sub.add_parser('preflight')
    check.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    check.add_argument('--estimated-peak-bytes', type=int, required=True)
    check.add_argument('--max-project-bytes', type=int, default=DEFAULT_MAX_PROJECT_BYTES)
    check.add_argument('--min-free-bytes', type=int, default=DEFAULT_MIN_FREE_BYTES)
    compact = sub.add_parser('compact')
    compact.add_argument('--run', required=True)
    delete = sub.add_parser('delete-run')
    delete.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    delete.add_argument('--run-name', required=True)
    delete.add_argument('--receipt-max-bytes', type=int, default=2 * MiB)
    args = parser.parse_args(argv)
    try:
        if args.command == 'inventory':
            result = inventory(args.root)
        elif args.command == 'preflight':
            result = preflight(args.root, args.estimated_peak_bytes, args.max_project_bytes, args.min_free_bytes)
        elif args.command == 'compact':
            result = compact_run(args.run)
        else:
            result = delete_run(args.root, args.run_name, args.receipt_max_bytes)
    except (StorageError, OSError, EOFError) as exc:
        print(json.dumps({'error': str(exc), 'report': getattr(exc, 'report', None)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
