# -*- coding: utf-8 -*-
"""build.py -- build data/recall/recall.db (the experience library).

    python tools/recall/build.py                  # full rebuild, embeddings reused from cache
    python tools/recall/build.py --source problems,git
    python tools/recall/build.py --no-embed       # chunk + redact + count only; touches no model, no db

This is the recall reader exception for PROBLEMS.md (see #101 and check_isolation.py).
Scoped ledger maintenance tools and synthetic-fixture tests have their own exception;
none of these prose records may become pipeline configuration or semantic evidence.
Everything is redacted before it is hashed, embedded or stored.
"""
import argparse
import hashlib
import os
import re
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sources  # noqa: E402

ROOT = sources.ROOT
DB_PATH = os.path.join(ROOT, "data", "recall", "recall.db")
KEY_FILE = r"C:\api key\canlii.txt"
EMAIL = "yubow47@gmail.com"
MODEL = "BAAI/bge-m3"
DIM = 1024
EMITTED = {"decisions_doc": "decisions"}  # factory key -> chunk source it emits

HEX_LEN_OK = {40, 64}  # git hash / sha256 are not secrets
LONG_TOKEN = re.compile(r"(?<![A-Za-z0-9_\-/.])[A-Za-z0-9]{32,}(?![A-Za-z0-9_\-/.])")


def load_secrets():
    toks = []
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, encoding="utf-8", errors="replace") as f:
            toks = [t for t in re.split(r"\s+", f.read()) if len(t) >= 8]
    return sorted(set(toks), key=len, reverse=True)


def make_redactor():
    secrets = load_secrets()

    def redact(text):
        for s in secrets:
            text = text.replace(s, "[REDACTED_KEY]")
        text = re.sub(r"(api_key=)[^&\s\"')]+", r"\1[REDACTED_KEY]", text)
        text = text.replace(EMAIL, "[EMAIL]")

        def tok(m):
            s = m.group(0)
            if len(s) in HEX_LEN_OK and re.fullmatch(r"[0-9a-fA-F]+", s):
                return s
            return "[REDACTED_TOKEN]"
        return LONG_TOKEN.sub(tok, text)
    return redact


SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY, source TEXT NOT NULL, locator TEXT NOT NULL, date TEXT,
  title TEXT, text TEXT NOT NULL, sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS emb_cache (sha256 TEXT NOT NULL, model TEXT NOT NULL, vec BLOB NOT NULL,
  PRIMARY KEY (sha256, model));
CREATE TABLE IF NOT EXISTS dups (sha256 TEXT NOT NULL, source TEXT NOT NULL, locator TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def open_db():
    import sqlite_vec
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    db.executescript(SCHEMA)
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(embedding float[%d] distance_metric=cosine)" % DIM)
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5(text, content='chunks', content_rowid='id', tokenize='trigram')")
    return db


def load_model():
    import torch
    from sentence_transformers import SentenceTransformer
    device = "cuda" if torch.cuda.is_available() else "cpu"
    m = SentenceTransformer(MODEL, device=device)
    m.max_seq_length = 1024
    return m, device


LEDGER_MARKERS = (
    "<!-- ledger-current:start -->", "<!-- ledger-current:end -->",
    "<!-- ledger-history:start -->", "<!-- ledger-history:end -->",
)
CURRENT_SUMMARY_CHARS = 500


def problem_records(text):
    """Group current and historical table rows by ID; also accept an unmarked ledger.

    Only the numeric row prefix is structural here. Printed code can contain pipes,
    and old records can lack the final table pipe; neither changes the record ID.
    """
    lines = text.splitlines()
    positions = [[i for i, line in enumerate(lines) if line.strip() == marker]
                 for marker in LEDGER_MARKERS]
    marked = any(positions)
    if marked:
        if any(len(found) != 1 for found in positions):
            raise ValueError("Ledger requires each current/history marker exactly once")
        boundaries = [found[0] for found in positions]
        if boundaries != sorted(boundaries):
            raise ValueError("Ledger current/history markers are out of order")
        current_start, current_end, history_start, history_end = boundaries
        sections = (("current", lines[current_start + 1:current_end]),
                    ("history", lines[history_start + 1:history_end]))
    else:
        sections = (("history", lines),)
    records = {}
    for section, section_lines in sections:
        for line in section_lines:
            match = re.match(r"\|\s*(\d+)\s*\|", line)
            if match:
                number = int(match.group(1))
                record = records.setdefault(number, {"current": [], "history": []})
                if line not in record[section]:
                    record[section].append(line)
    for number in sorted(records):
        yield number, records[number], marked


def chunks_from_problem_text(text):
    """One logical entry per ID, with current context repeated on bounded pieces."""
    for number, record, marked in problem_records(text):
        current = "\n".join(record["current"])
        history = "\n".join(record["history"])
        summary = current or (
            "No current index row recorded; do not read historical status as current."
            if marked else "Legacy ledger format; no separate current disposition recorded."
        )
        long_current = len(summary) > CURRENT_SUMMARY_CHARS
        if long_current:
            summary = summary[:CURRENT_SUMMARY_CHARS] + " [continued in current-index detail]"
        context = ("Current index (authoritative when supplied):\n" + summary +
                   "\n\nHISTORICAL RECORD: earlier wording is not current status.")
        sections = []
        if long_current:
            sections.append(("CURRENT INDEX DETAIL", current))
        sections.append(("HISTORICAL RECORD" if marked else "LEGACY HISTORICAL RECORD",
                         history or "No historical row is recorded for this ID."))
        locator = "PROBLEMS.md#%d" % number
        index = 0
        for label, body in sections:
            for chunk in sources._emit_prefixed("problems", locator, "PROBLEMS #%d" % number,
                                                body, context + "\nRecord section: " + label):
                chunk["locator"] = locator if index == 0 else "%s~%d" % (locator, index + 1)
                index += 1
                yield chunk


def chunk_problems():
    """Read only for human recall; current conclusions precede marked historical text."""
    path = os.path.join(ROOT, "PROBLEMS.md")
    with open(path, encoding="utf-8", errors="replace") as f:
        yield from chunks_from_problem_text(f.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", help="comma list of chunk sources to rebuild (default all)")
    ap.add_argument("--no-embed", action="store_true", help="count chunks only; no model, no db")
    args = ap.parse_args()
    wanted = set(args.source.split(",")) if args.source else None

    t0 = time.time()
    redact = make_redactor()
    chat_stats = {}
    chunks = []
    factories = {"problems": chunk_problems}
    factories.update(sources.all_sources(chat_stats))
    for key, factory in factories.items():
        if wanted and EMITTED.get(key, key) not in wanted:
            continue
        for c in factory():
            c["text"] = redact(c["text"])
            c["title"] = redact(c["title"] or "")
            c["sha256"] = hashlib.sha256(c["text"].encode("utf-8")).hexdigest()
            chunks.append(c)

    # identical text (after redaction) is stored once; the first occurrence wins, and since the
    # ledger/audit sources come before chat in `factories`, those beat a chat copy of the same text.
    seen, unique, dups = {}, [], []
    for c in chunks:
        if c["sha256"] in seen:
            dups.append((c["sha256"], c["source"], c["locator"]))
        else:
            seen[c["sha256"]] = c["locator"]
            unique.append(c)
    chunks = unique
    counts = {}
    for c in chunks:
        counts[c["source"]] = counts.get(c["source"], 0) + 1
    print("chunks per source:", counts, "total", len(chunks), "(exact duplicates dropped: %d)" % len(dups))
    if chat_stats:
        print("chat records dropped, by reason:", chat_stats)
    if args.no_embed:
        return

    db = open_db()
    cached = {r[0] for r in db.execute("SELECT sha256 FROM emb_cache WHERE model=?", (MODEL,))}
    todo = sorted({c["sha256"]: c["text"] for c in chunks if c["sha256"] not in cached}.items())
    print("embeddings: reuse %d, compute %d" % (len(cached & {c["sha256"] for c in chunks}), len(todo)))

    if todo:
        import numpy as np
        model, device = load_model()
        print("model", MODEL, "on", device)
        for i in range(0, len(todo), 16):
            batch = todo[i:i + 16]
            vecs = model.encode([t for _, t in batch], batch_size=16, normalize_embeddings=True)
            db.executemany("INSERT OR REPLACE INTO emb_cache VALUES (?,?,?)",
                           [(h, MODEL, np.asarray(v, dtype="float32").tobytes()) for (h, _), v in zip(batch, vecs)])
            db.commit()
            if (i // 16) % 20 == 0:
                print("  embedded %d/%d" % (min(i + 16, len(todo)), len(todo)))

    sources_built = wanted or {c["source"] for c in chunks}
    ph = ",".join("?" * len(sources_built))
    ids = [r[0] for r in db.execute("SELECT id FROM chunks WHERE source IN (%s)" % ph, tuple(sources_built))]
    db.executemany("DELETE FROM vec_chunks WHERE rowid=?", [(i,) for i in ids])
    db.execute("DELETE FROM chunks WHERE source IN (%s)" % ph, tuple(sources_built))
    db.execute("DELETE FROM dups WHERE source IN (%s)" % ph, tuple(sources_built))
    db.executemany("INSERT INTO dups(sha256, source, locator) VALUES (?,?,?)", dups)
    for c in chunks:
        cur = db.execute("INSERT INTO chunks(source,locator,date,title,text,sha256) VALUES (?,?,?,?,?,?)",
                         (c["source"], c["locator"], c["date"], c["title"], c["text"], c["sha256"]))
        vec = db.execute("SELECT vec FROM emb_cache WHERE sha256=? AND model=?", (c["sha256"], MODEL)).fetchone()[0]
        db.execute("INSERT INTO vec_chunks(rowid, embedding) VALUES (?,?)", (cur.lastrowid, vec))
    db.execute("INSERT INTO fts_chunks(fts_chunks) VALUES ('rebuild')")
    total = db.execute("SELECT count(*) FROM chunks").fetchone()[0]
    db.execute("INSERT OR REPLACE INTO meta VALUES ('model', ?)", (MODEL,))
    db.execute("INSERT OR REPLACE INTO meta VALUES ('built_at', ?)", (time.strftime("%Y-%m-%d %H:%M:%S"),))
    db.execute("INSERT OR REPLACE INTO meta VALUES ('total_chunks', ?)", (str(total),))
    db.commit()
    print("done: %d chunks in db, %.0f s, %.1f MB" % (total, time.time() - t0, os.path.getsize(DB_PATH) / 1e6))


if __name__ == "__main__":
    main()
