"""Embed text_records through OpenRouter and store the vectors in research.db (sqlite-vec).

Model: qwen/qwen3-embedding-8b at 1024 dimensions (multilingual: a Chinese question finds English
judgments). Vectors are cached by (text hash, model, dim) in data/foundation/emb_cache.db, so a new
run only pays for new or changed texts. Changing MODEL or DIM rebuilds the vector table; vectors from
different models are never mixed. API-key-looking strings are removed before any text leaves the machine.
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import re
import sqlite3
import struct
import time
import urllib.request
from pathlib import Path
from common import ROOT, DEFAULT_DB, connect

MODEL = 'qwen/qwen3-embedding-8b'
DIM = 1024
BATCH = 64
WORKERS = 6
MAX_CHARS = 2400
KEY_FILE = Path(os.environ.get('OPENROUTER_KEY_FILE', r'C:\api key\openrouter 1.txt'))
CACHE = ROOT/'data'/'foundation'/'emb_cache.db'
SECRET = re.compile(r'sk-[A-Za-z0-9_-]{16,}|api_key=[^&\s]+|Bearer\s+[A-Za-z0-9._-]{16,}')


def _key():
    m = re.search(r'sk-or-[A-Za-z0-9_-]+', KEY_FILE.read_text(encoding='utf-8', errors='ignore'))
    if not m:
        raise SystemExit('No OpenRouter key found in ' + str(KEY_FILE))
    return m.group(0)


def prepare(text):
    return SECRET.sub('[redacted]', text)[:MAX_CHARS]


def _post(texts, key, tries=5):
    body = json.dumps({'model': MODEL, 'input': texts, 'dimensions': DIM}).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request('https://openrouter.ai/api/v1/embeddings', data=body,
                                         headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
            r = json.load(urllib.request.urlopen(req, timeout=120))
            vecs = [d['embedding'] for d in sorted(r['data'], key=lambda d: d['index'])]
            if len(vecs) != len(texts) or any(len(v) != DIM for v in vecs):
                raise ValueError('bad embedding response shape')
            return vecs, r.get('usage', {}).get('cost', 0) or 0
        except Exception as e:  # network errors, 429, 5xx: back off and retry
            if i == tries - 1:
                raise RuntimeError(str(e).replace(key, '[key]'))
            time.sleep(2 ** i * 2)


def _unit(v):
    n = sum(x * x for x in v) ** 0.5 or 1.0
    return struct.pack('%df' % len(v), *(x / n for x in v))


def embed_texts(texts):
    """texts: list of str -> list of packed unit float32 vectors (cached)."""
    cache = sqlite3.connect(CACHE)
    cache.execute('CREATE TABLE IF NOT EXISTS emb(h TEXT, model TEXT, dim INTEGER, v BLOB, PRIMARY KEY(h,model,dim))')
    prepared = [prepare(t) for t in texts]
    hs = [hashlib.sha256(t.encode('utf-8')).hexdigest() for t in prepared]
    have = {}
    for i in range(0, len(hs), 900):
        chunk = hs[i:i + 900]
        q = 'SELECT h,v FROM emb WHERE model=? AND dim=? AND h IN (%s)' % ','.join('?' * len(chunk))
        have.update(cache.execute(q, (MODEL, DIM, *chunk)).fetchall())
    todo = sorted({h: t for h, t in zip(hs, prepared) if h not in have}.items())
    cost, failed = 0.0, 0
    if todo:
        key = _key()
        batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
        done = 0
        with cf.ThreadPoolExecutor(WORKERS) as ex:
            futs = {ex.submit(_post, [t for _, t in b], key): b for b in batches}
            for f in cf.as_completed(futs):
                b = futs[f]
                try:
                    vecs, c = f.result()
                except Exception as e:
                    failed += len(b)
                    print('batch failed:', str(e)[:200])
                    continue
                cost += c
                rows = [(h, MODEL, DIM, _unit(v)) for (h, _), v in zip(b, vecs)]
                cache.executemany('INSERT OR REPLACE INTO emb VALUES(?,?,?,?)', rows)
                cache.commit()
                have.update((h, v) for h, _, _, v in rows)
                done += len(b)
                if done % (BATCH * 50) < BATCH:
                    print('embedded %d/%d new texts, cost so far $%.4f' % (done, len(todo), cost), flush=True)
    cache.close()
    return [have.get(h) for h in hs], {'new': len(todo), 'cached': len(hs) - len(todo), 'failed': failed, 'cost_usd': round(cost, 4)}


def load_vec(db):
    import sqlite_vec
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)


def vec_table(collection):
    if not collection.isidentifier():
        raise ValueError('bad collection name')
    return 'vec_' + collection


def index(collections, db_path=DEFAULT_DB):
    """One vector table per collection (vec_cases, vec_methods), so a small collection is not
    crowded out of the nearest-neighbour list by a large one."""
    db = connect(db_path)
    try:
        load_vec(db)
        db.execute('CREATE TABLE IF NOT EXISTS vec_meta(name TEXT PRIMARY KEY, value TEXT NOT NULL)')
        meta = dict(db.execute('SELECT name,value FROM vec_meta'))
        stale = meta and (meta.get('model') != MODEL or meta.get('dim') != str(DIM))
        out = {}
        for col in collections:
            t = vec_table(col)
            if stale:
                db.execute('DROP TABLE IF EXISTS ' + t)   # never mix vectors from different models
            db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS %s USING vec0(embedding float[%d] distance_metric=cosine)' % (t, DIM))
            recs = db.execute('SELECT id,title,text FROM text_records WHERE collection=?', (col,)).fetchall()
            vecs, stats = embed_texts([r['title'] + '\n' + r['text'] for r in recs])
            n = 0
            with db:
                db.execute('DELETE FROM ' + t)
                for r, v in zip(recs, vecs):
                    if v is not None:
                        db.execute('INSERT INTO %s(rowid,embedding) VALUES(?,?)' % t, (r['id'], v))
                        n += 1
            out[col] = dict(stats, vectors_written=n)
        with db:
            db.execute("INSERT OR REPLACE INTO vec_meta VALUES('model',?),('dim',?)", (MODEL, str(DIM)))
            db.execute('DROP TABLE IF EXISTS vec_text')   # superseded shared table
        return dict(out, model=MODEL, dim=DIM)
    finally:
        db.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--collections', default='cases')
    p.add_argument('--db', default=str(DEFAULT_DB))
    a = p.parse_args()
    print(json.dumps(index(a.collections.split(','), a.db), ensure_ascii=False, indent=2))
