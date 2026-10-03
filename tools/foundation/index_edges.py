"""Index every citation edge by the passage where the source judgment cites the case.

An edge is one row in citation_edges: source judgment -> cited case group (joined by ids). Ids answer
"who cites whom"; they say nothing about WHY. This step stores, per edge, the words around the citation
and makes them searchable by keyword (FTS) and by meaning (vectors), so a researcher can ask
"judgments that cite Housen for the standard of review" and get edges, not just cases.

One passage per edge: among that source's counted mentions of the group, the most sentence-like window
(same scoring as case profiles). Vectors are 512-dim (Matryoshka cut of the same model), cached by text.
Tables: edge_passages(+FTS), vec_edges. Rebuilt per run; vectors of unchanged passages come from cache.
"""
import argparse
import collections
import csv
import json
import re
from pathlib import Path
from common import ROOT, DEFAULT_DB, connect, nk
from index_cases import clean, prose_score, BEFORE, AFTER
from embed import embed_texts, load_vec

EDGE_DIM = 512
MENTIONS_PER_EDGE = 3


def build_passages(run_dir, db_path=DEFAULT_DB):
    import pyarrow.parquet as pq
    run_dir = Path(run_dir).resolve()
    run_id = run_dir.name
    db = connect(db_path)
    try:
        key2g = {}
        for court, mk, g in db.execute('SELECT court,merge_key,merged_group_id FROM members WHERE run_id=?', (run_id,)):
            key2g[(court, mk)] = g
        edges = {(s, g) for s, g in db.execute('SELECT source_decision,resolved_cited_case FROM citation_edges WHERE run_id=?', (run_id,))}
        courts = json.loads(db.execute('SELECT manifest_json FROM runs WHERE run_id=?', (run_id,)).fetchone()[0])['params']['courts']
        cand = collections.defaultdict(list)       # (source, group) -> [(court,row,start,end)]
        for court in courts:
            with (run_dir/'merge_out'/court/'mentions_candidates.csv').open(encoding='utf-8', newline='') as f:
                for r in csv.DictReader(f):
                    if r['arbitration_status'] != 'counted':
                        continue
                    g = key2g.get((court, r['merge_key']))
                    k = (r['source_decision_citation'], g)
                    if g and k in edges and len(cand[k]) < MENTIONS_PER_EDGE:
                        cand[k].append((court, int(r['corpus_row_index']), int(r['match_start_offset']), int(r['match_end_offset'])))
        need = collections.defaultdict(set)
        for ms in cand.values():
            for court, row, *_ in ms:
                need[court].add(row)
        windows = {}
        for court in courts:
            pf = pq.ParquetFile(ROOT/'corpus'/(court+'.parquet'))
            i = 0
            for b in pf.iter_batches(batch_size=500, columns=['unofficial_text_en']):
                for t in b.column(0).to_pylist():
                    if i in need[court]:
                        windows[(court, i)] = t or ''
                    i += 1
        rows, missing = [], 0
        for (src, g) in sorted(edges):
            best, best_s = '', -9.0
            for court, row, a, b in cand.get((src, g), ()):
                t = windows.get((court, row), '')
                w = clean(t[max(0, a - BEFORE): b + AFTER])
                s = prose_score(w)
                if w and s > best_s:
                    best, best_s = w, s
            if not best:
                missing += 1
                continue
            rows.append((run_id, src, g, best))
        db.execute('''CREATE TABLE IF NOT EXISTS edge_passages(
            id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, source_decision TEXT NOT NULL,
            resolved_cited_case TEXT NOT NULL, passage TEXT NOT NULL,
            UNIQUE(run_id,source_decision,resolved_cited_case))''')
        db.execute('DROP TABLE IF EXISTS edge_fts')
        with db:
            db.execute('DELETE FROM edge_passages WHERE run_id=?', (run_id,))
            db.executemany('INSERT INTO edge_passages(run_id,source_decision,resolved_cited_case,passage) VALUES(?,?,?,?)', rows)
            db.execute("CREATE VIRTUAL TABLE edge_fts USING fts5(passage,content='edge_passages',content_rowid='id',tokenize='trigram')")
            db.execute("INSERT INTO edge_fts(edge_fts) VALUES('rebuild')")
        return {'run_id': run_id, 'edges': len(edges), 'passages': len(rows), 'edges_without_passage': missing}
    finally:
        db.close()


def embed_passages(run_id, db_path=DEFAULT_DB, limit=None):
    db = connect(db_path)
    try:
        load_vec(db)
        db.execute('CREATE TABLE IF NOT EXISTS vec_meta(name TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS vec_edges USING vec0(embedding float[%d] distance_metric=cosine)' % EDGE_DIM)
        recs = db.execute('SELECT id,passage FROM edge_passages WHERE run_id=? ORDER BY id' + (' LIMIT %d' % limit if limit else ''),
                          (run_id,)).fetchall()
        vecs, stats = embed_texts([r['passage'] for r in recs], dim=EDGE_DIM)
        n = 0
        with db:
            live = {r['id'] for r in db.execute('SELECT id FROM edge_passages')}
            for (rid,) in db.execute('SELECT rowid FROM vec_edges').fetchall():
                if rid not in live:
                    db.execute('DELETE FROM vec_edges WHERE rowid=?', (rid,))
            for r, v in zip(recs, vecs):
                if v is None:
                    continue
                db.execute('DELETE FROM vec_edges WHERE rowid=?', (r['id'],))
                db.execute('INSERT INTO vec_edges(rowid,embedding) VALUES(?,?)', (r['id'], v))
                n += 1
            db.execute("INSERT OR REPLACE INTO vec_meta VALUES('edge_dim',?)", (str(EDGE_DIM),))
        return dict(stats, vectors_written=n, dim=EDGE_DIM)
    finally:
        db.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--run', required=True); p.add_argument('--db', default=str(DEFAULT_DB))
    p.add_argument('--limit', type=int, help='embed only the first N passages (test)')
    p.add_argument('--skip-build', action='store_true')
    a = p.parse_args()
    run_id = Path(a.run).name
    out = {} if a.skip_build else {'passages': build_passages(a.run, a.db)}
    out['vectors'] = embed_passages(run_id, a.db, a.limit)
    print(json.dumps(out, ensure_ascii=False, indent=2))
