"""Fail closed when a retired/default historical audit input is missing."""
import gzip
from pathlib import Path


def classified_paths(directory, courts=('SCC', 'ONCA')):
    paths = {}
    missing = []
    for court in courts:
        plain = Path(directory) / court / 'classified.csv'
        compressed = Path(str(plain) + '.gz')
        if plain.is_file():
            paths[court] = plain
        elif compressed.is_file():
            paths[court] = compressed
        else:
            missing.append(str(plain))
    if missing:
        raise SystemExit('Audit input missing; refusing an empty/partial successful report: '
                         + '; '.join(missing)
                         + '. Root legacy intermediates were retired on 2026-10-14 '
                         '(data/legacy_intermediates_retired.json). Choose an explicit complete run snapshot.')
    return paths


def open_csv(path):
    path = Path(path)
    if path.suffix == '.gz':
        return gzip.open(path, 'rt', encoding='utf-8-sig', newline='')
    return path.open(encoding='utf-8-sig', newline='')
