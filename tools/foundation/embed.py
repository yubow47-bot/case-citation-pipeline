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
import math
import os
import re
import sqlite3
import struct
import time
import urllib.request
from pathlib import Path
from common import (ROOT, DEFAULT_DB, connect, fingerprint, start_component,
                    finish_component, fail_component)

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


def _post(texts, key, dim=DIM, tries=5):
    body = json.dumps({'model': MODEL, 'input': texts, 'dimensions': dim}).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request('https://openrouter.ai/api/v1/embeddings', data=body,
                                         headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
            r = json.load(urllib.request.urlopen(req, timeout=120))
            vecs = [d['embedding'] for d in sorted(r['data'], key=lambda d: d['index'])]
            if len(vecs) != len(texts) or any(len(v) != dim for v in vecs):
                raise ValueError('bad embedding response shape')
            if any(not all(isinstance(x, (int, float)) and math.isfinite(x) for x in v) or
                   sum(x*x for x in v) == 0 for v in vecs):
                raise ValueError('bad embedding response values')
            return vecs, r.get('usage', {}).get('cost', 0) or 0
        except Exception as e:  # network errors, 429, 5xx: back off and retry
            if i == tries - 1:
                raise RuntimeError(str(e).replace(key, '[key]'))
            time.sleep(2 ** i * 2)


def _unit(v):
    n = sum(x * x for x in v) ** 0.5 or 1.0
    return struct.pack('%df' % len(v), *(x / n for x in v))


def embed_texts(texts, dim=DIM, allow_network=False, cache_path=None):
    """texts: list of str -> list of packed unit float32 vectors (cached)."""
    cache_file = Path(cache_path or CACHE)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache = sqlite3.connect(cache_file)
    cache.execute('CREATE TABLE IF NOT EXISTS emb(h TEXT, model TEXT, dim INTEGER, v BLOB, PRIMARY KEY(h,model,dim))')
    prepared = [prepare(t) for t in texts]
    hs = [hashlib.sha256(t.encode('utf-8')).hexdigest() for t in prepared]
    have = {}
    for i in range(0, len(hs), 900):
        chunk = hs[i:i + 900]
        q = 'SELECT h,v FROM emb WHERE model=? AND dim=? AND h IN (%s)' % ','.join('?' * len(chunk))
        have.update(cache.execute(q, (MODEL, dim, *chunk)).fetchall())
    have = {h: v for h, v in have.items() if isinstance(v, bytes) and len(v) == dim*4 and
            all(math.isfinite(x) for x in struct.unpack('%df' % dim, v))}
    todo = sorted({h: t for h, t in zip(hs, prepared) if h not in have}.items())
    cost, failed = 0.0, 0
    if todo and allow_network:
        key = _key()
        batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
        done = 0
        with cf.ThreadPoolExecutor(WORKERS) as ex:
            futs = {ex.submit(_post, [t for _, t in b], key, dim): b for b in batches}
            for f in cf.as_completed(futs):
                b = futs[f]
                try:
                    vecs, c = f.result()
                except Exception as e:
                    failed += len(b)
                    print('batch failed:', str(e)[:200])
                    continue
                cost += c
                rows = [(h, MODEL, dim, _unit(v)) for (h, _), v in zip(b, vecs)]
                cache.executemany('INSERT OR REPLACE INTO emb VALUES(?,?,?,?)', rows)
                cache.commit()
                have.update((h, v) for h, _, _, v in rows)
                done += len(b)
                if done % (BATCH * 50) < BATCH:
                    print('embedded %d/%d new texts, cost so far $%.4f' % (done, len(todo), cost), flush=True)
    cache.close()
    return [have.get(h) for h in hs], {'requested': len(hs), 'new': len(todo),
        'cached': sum(h in have for h in hs) if not allow_network else len(hs)-sum(h not in have for h in hs),
        'missing': sum(h not in have for h in hs), 'failed': failed,
        'network_allowed': allow_network, 'cost_usd': round(cost, 4)}


def load_vec(db):
    import sqlite_vec
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)


def vec_table(collection):
    if not collection.isidentifier():
        raise ValueError('bad collection name')
    return 'vec_' + collection


def index(collections, db_path=DEFAULT_DB, run_id=None, allow_network=False):
    """One vector table per collection (vec_cases, vec_methods), so a small collection is not
    crowded out of the nearest-neighbour list by a large one."""
    db = connect(db_path)
    try:
        if run_id is None:
            r = db.execute('SELECT run_id FROM runs ORDER BY imported_at DESC LIMIT 1').fetchone()
            if not r:
                raise ValueError('No imported run')
            run_id = r[0]
        db.execute('CREATE TABLE IF NOT EXISTS vec_meta(name TEXT PRIMARY KEY, value TEXT NOT NULL)')
        meta = dict(db.execute('SELECT name,value FROM vec_meta'))
        stale = meta and (meta.get('model') != MODEL or meta.get('dim') != str(DIM))
        out = {}
        for col in collections:
            recs = db.execute('SELECT id,title,text,content_hash FROM text_records WHERE collection=?' +
                              (' AND run_id=?' if col != 'methods' else ''),
                              (col, run_id) if col != 'methods' else (col,)).fetchall()
            component = 'vectors_' + col
            generation = start_component(db, run_id, component,
                {'model': MODEL, 'dim': DIM, 'records': [(r['id'], r['content_hash']) for r in recs]})
            try:
                vecs, stats = embed_texts([r['title'] + '\n' + r['text'] for r in recs], allow_network=allow_network)
                missing = sum(v is None for v in vecs)
                if missing or len(vecs) != len(recs) or stats.get('failed', 0):
                    status = 'failed' if stats.get('failed', 0) else 'missing' if missing == len(recs) else 'stale'
                    report = dict(stats, status=status, expected=len(recs), vectors_written=0, missing=missing)
                    with db:
                        finish_component(db, run_id, component, generation, status, report)
                    out[col] = report
                    continue
                try:
                    load_vec(db)
                except ImportError:
                    report = dict(stats, status='missing', expected=len(recs), vectors_written=0,
                                  reason='sqlite-vec is unavailable')
                    with db:
                        finish_component(db, run_id, component, generation, 'missing', report)
                    out[col] = report
                    continue
                if any(len(v) != DIM*4 for v in vecs):
                    raise ValueError('Invalid packed vector dimension')
                t = vec_table(col)
                with db:
                    if stale:
                        db.execute('DROP TABLE IF EXISTS ' + t)
                        db.execute("UPDATE run_components SET status='stale' WHERE component=? AND run_id<>?",
                                   (component, run_id))
                    db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS %s USING vec0(embedding float[%d] distance_metric=cosine)' % (t, DIM))
                    db.execute('CREATE TABLE IF NOT EXISTS vector_records(collection TEXT,record_id INTEGER,content_hash TEXT,PRIMARY KEY(collection,record_id))')
                    if col == 'methods':
                        db.execute('DELETE FROM ' + t)
                        db.execute('DELETE FROM vector_records WHERE collection=?', (col,))
                    for r, v in zip(recs, vecs):
                        db.execute('DELETE FROM %s WHERE rowid=?' % t, (r['id'],))
                        db.execute('INSERT INTO %s(rowid,embedding) VALUES(?,?)' % t, (r['id'], v))
                        db.execute('INSERT OR REPLACE INTO vector_records VALUES(?,?,?)', (col, r['id'], r['content_hash']))
                    report = dict(stats, status='ready', expected=len(recs), vectors_written=len(recs))
                    finish_component(db, run_id, component, generation, details=report)
                    db.execute("INSERT OR REPLACE INTO vec_meta VALUES('model',?),('dim',?)", (MODEL, str(DIM)))
                out[col] = report
            except Exception as exc:
                fail_component(db, run_id, component, generation, exc)
                raise
        with db:
            db.execute('DROP TABLE IF EXISTS vec_text')   # superseded shared table
        return dict(out, model=MODEL, dim=DIM)
    finally:
        db.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--collections', default='cases')
    p.add_argument('--db', default=str(DEFAULT_DB))
    p.add_argument('--run', help='run id (defaults to newest imported run)')
    p.add_argument('--allow-network', action='store_true', help='explicitly permit embedding API requests')
    a = p.parse_args()
    print(json.dumps(index(a.collections.split(','), a.db, a.run, a.allow_network), ensure_ascii=False, indent=2))
