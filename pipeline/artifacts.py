"""Read retained plain or compressed artifact CSVs without unpacking them."""
import gzip
import hashlib
from pathlib import Path


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


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
