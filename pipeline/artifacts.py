"""Read retained plain or compressed artifact CSVs without unpacking them, and
replace finished artifacts atomically."""
import csv
import gzip
import hashlib
import os
import time
from pathlib import Path

# Member lists can be long: on the nine-court corpus the Dunsmuir group's
# co_printed_run_ids is about 250 KB, past Python's default 131,072-byte field limit.
# Every pipeline step imports this module, so the limit is raised once here.
csv.field_size_limit(10 ** 9)

# Windows reports a just-written file as busy while Defender or the search indexer
# scans it (seen on exFAT): WinError 5 (access denied) or 32 (sharing violation).
_BUSY_WINERRORS = (5, 32)


def replace_file(src, dst, attempts=6, delay=0.5):
    """os.replace that waits briefly while Windows reports the target busy.

    Any other error, or the last attempt, is raised unchanged."""
    for attempt in range(1, attempts + 1):
        try:
            os.replace(src, dst)
            return
        except OSError as exc:
            if getattr(exc, "winerror", None) not in _BUSY_WINERRORS or attempt == attempts:
                raise
            time.sleep(delay * attempt)


def resolve(path):
    path = Path(path)
    if path.is_file():
        return path
    compressed = Path(str(path) + ".gz")
    if compressed.is_file():
        return compressed
    raise FileNotFoundError(path)


def open_csv(path):
    path = resolve(path)
    return (gzip.open if path.suffix == ".gz" else open)(path, "rt", encoding="utf-8-sig", newline="")


def sha256_logical_csv_bytes(path):
    """Hash the logical CSV bytes, independent of plain/gzip retention."""
    path = resolve(path)
    opener = gzip.open if path.suffix == ".gz" else open
    digest = hashlib.sha256()
    with opener(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
