# -*- coding: utf-8 -*-
"""query.py -- search the experience library. Prints text for a human; there is deliberately
no --json / --csv / output-file option (PROBLEMS #101: results must never feed a program).

    python tools/recall/query.py "year written as two parts was missed" -k 8
    python tools/recall/query.py "BCCA" --keyword
    python tools/recall/query.py "..." --source problems,chat
"""
import argparse
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(ROOT, "data", "recall", "recall.db")
MODEL = "BAAI/bge-m3"


def show(rank, score, row):
    _, source, locator, date, title, text = row
    snippet = " ".join(text.split())[:300]
    print("%2d. [%s] %s  %s  %s" % (rank, score, source, locator, date or ""))
    print("    " + snippet + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=8)
    ap.add_argument("--source", help="comma list, e.g. problems,chat")
    ap.add_argument("--keyword", action="store_true", help="FTS5 keyword search instead of vectors")
    args = ap.parse_args()
    if not os.path.exists(DB_PATH):
        sys.exit("no db at %s -- run tools/recall/build.py first" % DB_PATH)
    import sqlite_vec
    db = sqlite3.connect(DB_PATH)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    srcs = args.source.split(",") if args.source else None
    sel = "c.id, c.source, c.locator, c.date, c.title, c.text"

    if args.keyword:
        if len(args.query) < 3:
            sys.exit("keyword search needs >= 3 characters (trigram index)")
        q = '"%s"' % args.query.replace('"', '""')
        sql = ("SELECT %s FROM fts_chunks f JOIN chunks c ON c.id=f.rowid WHERE fts_chunks MATCH ? "
               "ORDER BY rank LIMIT ?" % sel)
        rows = db.execute(sql, (q, args.k * 5 if srcs else args.k)).fetchall()
        rows = [r for r in rows if not srcs or r[1] in srcs][:args.k]
        for i, r in enumerate(rows, 1):
            show(i, "kw", r)
    else:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        vec = SentenceTransformer(MODEL).encode([args.query], normalize_embeddings=True)[0]
        fetch = args.k * 10 if srcs else args.k
        hits = db.execute("SELECT rowid, distance FROM vec_chunks WHERE embedding MATCH ? AND k=? ORDER BY distance",
                          (np.asarray(vec, dtype="float32").tobytes(), fetch)).fetchall()
        n = 0
        for rowid, dist in hits:
            r = db.execute("SELECT %s FROM chunks c WHERE c.id=?" % sel, (rowid,)).fetchone()
            if r is None or (srcs and r[1] not in srcs):
                continue
            n += 1
            show(n, "%.3f" % (1 - dist), r)
            if n >= args.k:
                break
    if not (args.keyword and rows) and not args.keyword and not hits:
        print("no results")


if __name__ == "__main__":
    main()
