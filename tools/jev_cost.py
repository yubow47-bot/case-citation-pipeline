"""jev_cost.py — cold-start Jev cost of a run, from its ledgers and the answer cache.

Sums the cached input tokens of the unique requests a run's ledgers reference,
so a run served mostly from cache still reports what an empty cache would cost.
Output tokens are free. Price is TypeSafe's published $0.042 per million input tokens.
"""
import argparse
import csv
import gzip
import sqlite3
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(1 << 30)
PRICE_PER_MTOK = 0.042


def ledger_rows(run):
    for path in sorted(Path(run).rglob("jev/*.csv*")):
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8", newline="") as f:
            yield from csv.DictReader(f)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run", nargs="+")
    ap.add_argument("--cache", default=str(Path(__file__).resolve().parents[1] / "data" / "jev_cache.sqlite"))
    ap.add_argument("--scale", type=float, default=1.0, help="multiply by this (e.g. full-corpus / sample candidates)")
    args = ap.parse_args()
    db = sqlite3.connect(args.cache)
    tokens = dict(db.execute("SELECT key, input_tokens FROM answers"))
    for run in args.run:
        keys = defaultdict(set)
        for r in ledger_rows(run):
            keys[r["node"]].add(r["cache_key"])
        total = calls = 0
        print(run)
        for node in sorted(keys):
            t = sum(tokens.get(k, 0) for k in keys[node])
            total += t
            calls += len(keys[node])
            print("  %-20s requests %7d  tokens %10d  USD %.3f" % (node, len(keys[node]), t, t / 1e6 * PRICE_PER_MTOK))
        print("  %-20s requests %7d  tokens %10d  USD %.3f  (x%.0f -> USD %.2f)" % (
            "TOTAL", calls, total, total / 1e6 * PRICE_PER_MTOK, args.scale, total / 1e6 * PRICE_PER_MTOK * args.scale))


if __name__ == "__main__":
    main()
