"""Stream run CSV artifacts as saved, including gzip archives; no cache or network access."""
import csv
import gzip
from pathlib import Path

csv.field_size_limit(10**9)


def resolve_csv(path):
    path = Path(path)
    if path.is_file():
        return path
    compressed = Path(str(path) + '.gz')
    if compressed.is_file():
        return compressed
    raise FileNotFoundError(str(path) + ' (or .gz)')


def rows(path):
    path = resolve_csv(path)
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        yield from csv.DictReader(stream)
