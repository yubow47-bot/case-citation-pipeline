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
from common import (ROOT, DEFAULT_DB, connect, nk, rows, source_snapshot, verify_snapshot,
                    start_component, finish_component, fail_component, fingerprint,
                    policy_from_manifest, selected_corpus_rows, corpus_field_evidence)
from index_cases import clean, prose_score, BEFORE, AFTER
from embed import embed_texts, load_vec

EDGE_DIM = 512
MENTIONS_PER_EDGE = 3


def build_passages(run_dir, db_path=DEFAULT_DB):
    import pyarrow.parquet as pq
    run_dir = Path(run_dir).resolve()
    run_id = run_dir.name
    db = connect(db_path)
    generation = start_component(db, run_id, 'edges')
    try:
        snapshot = source_snapshot(db, run_id, run_dir)
        db.execute('UPDATE run_components SET source_fingerprint=? WHERE run_id=? AND component=?',
                   (fingerprint(snapshot), run_id, 'edges'))
        db.commit()
        document_sources = {(r['court'], r['corpus_row']): r['source_id'] for r in db.execute(
            'SELECT court,corpus_row,source_id FROM documents WHERE run_id=?', (run_id,))}
        key2g = {}
        for court, mk, g in db.execute('SELECT court,merge_key,merged_group_id FROM members WHERE run_id=?', (run_id,)):
            key2g[(court, mk)] = g
        edges = {(s, g) for s, g in db.execute('SELECT source_decision,resolved_cited_case FROM citation_edges WHERE run_id=?', (run_id,))}
        manifest = json.loads(db.execute('SELECT manifest_json FROM runs WHERE run_id=?', (run_id,)).fetchone()[0])
        courts, policy = manifest['params']['courts'], policy_from_manifest(manifest)
        cand = collections.defaultdict(list)       # (source, group) -> [(court,row,start,end)]
        for court in courts:
                for line, r in enumerate(rows(run_dir/'merge_out'/court/'mentions_candidates.csv'), 2):
                    if r['arbitration_status'] != 'counted':
                        continue
                    g = key2g.get((court, r['merge_key']))
                    k = (r['source_decision_citation'], g)
                    if g and k in edges and len(cand[k]) < MENTIONS_PER_EDGE:
                        row = int(r['corpus_row_index'])
                        a, b = int(r['match_start_offset']), int(r['match_end_offset'])
                        if document_sources.get((court, row)) != k[0] or not 0 <= a < b:
                            raise ValueError('Mention locator disagrees with imported judgment: %s:%s' % (court, line))
                        cand[k].append((court, row, a, b, line, r.get('raw_string')))
        need = collections.defaultdict(set)
        for ms in cand.values():
            for court, row, *_ in ms:
                need[court].add(row)
        windows, field_selections = {}, {}
        for court in courts:
            pf = pq.ParquetFile(snapshot['corpus/'+court+'.parquet']['path'])
            for i, selected in selected_corpus_rows(pf, policy):
                if i in need[court]:
                    windows[(court, i)] = selected['text']
                    field_selections[(court, i)] = corpus_field_evidence(selected)
        passages, missing = [], 0
        for (src, g) in sorted(edges):
            best, best_s, evidence = '', -9.0, None
            for court, row, a, b, line, raw in cand.get((src, g), ()):
                t = windows.get((court, row), '')
                if b > len(t):
                    raise ValueError('Mention offset outside corpus text: %s:%s' % (court, line))
                # Match extractor's raw_string contract, retaining original
                # offsets/window rather than normalizing the source text.
                if raw is not None and re.sub(r'\s+', ' ', t[a:b]).strip() != raw:
                    raise ValueError('Mention text disagrees with selected corpus field: %s:%s' % (court, line))
                w = clean(t[max(0, a - BEFORE): b + AFTER])
                s = prose_score(w)
                if w and s > best_s:
                    best, best_s = w, s
                    evidence = {'court': court, 'corpus_row': row, 'match_start': a, 'match_end': b,
                                'window_start': max(0, a-BEFORE), 'window_end': min(len(t), b+AFTER),
                                'corpus': {'logical_path': 'corpus/'+court+'.parquet', **field_selections[(court, row)]},
                                'mentions': {'logical_path': 'merge_out/'+court+'/mentions_candidates.csv'},
                                'mention_record': line}
            if not best:
                missing += 1
                continue
            passages.append((run_id, src, g, best, json.dumps(evidence, ensure_ascii=False, separators=(',', ':'))))
        db.execute('''CREATE TABLE IF NOT EXISTS edge_passages(
            id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, source_decision TEXT NOT NULL,
            resolved_cited_case TEXT NOT NULL, passage TEXT NOT NULL, evidence_json TEXT NOT NULL DEFAULT '{}',
            UNIQUE(run_id,source_decision,resolved_cited_case))''')
        if 'evidence_json' not in [r['name'] for r in db.execute('PRAGMA table_info(edge_passages)')]:
            db.execute("ALTER TABLE edge_passages ADD COLUMN evidence_json TEXT NOT NULL DEFAULT '{}'")
        with db:
            db.execute('DELETE FROM edge_passages WHERE run_id=?', (run_id,))
            db.executemany('INSERT INTO edge_passages(run_id,source_decision,resolved_cited_case,passage,evidence_json) VALUES(?,?,?,?,?)', passages)
            db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS edge_fts USING fts5(passage,content='edge_passages',content_rowid='id',tokenize='trigram')")
            db.execute("INSERT INTO edge_fts(edge_fts) VALUES('rebuild')")
            verify_snapshot(snapshot)
            report = {'run_id': run_id, 'edges': len(edges), 'passages': len(passages),
                      'edges_without_passage': missing, 'source_fingerprint': fingerprint(snapshot), 'text_policy': policy}
            finish_component(db, run_id, 'edges', generation, details=report)
        return report
    except Exception as exc:
        fail_component(db, run_id, 'edges', generation, exc)
        raise
    finally:
        db.close()


def embed_passages(run_id, db_path=DEFAULT_DB, limit=None, allow_network=False):
    db = connect(db_path)
    generation = start_component(db, run_id, 'vectors_edges')
    try:
        if limit is not None and limit < 1:
            raise ValueError('limit must be positive')
        all_recs = db.execute('SELECT id,passage FROM edge_passages WHERE run_id=? ORDER BY id', (run_id,)).fetchall()
        recs = all_recs[:limit] if limit else all_recs
        db.execute('UPDATE run_components SET source_fingerprint=? WHERE run_id=? AND component=?',
                   (fingerprint([(r['id'], r['passage']) for r in all_recs]), run_id, 'vectors_edges'))
        db.commit()
        vecs, stats = embed_texts([r['passage'] for r in recs], dim=EDGE_DIM, allow_network=allow_network)
        missing = sum(v is None for v in vecs)
        if len(recs) != len(all_recs) or missing or len(vecs) != len(recs) or stats.get('failed', 0):
            status = 'failed' if stats.get('failed', 0) else 'missing' if missing == len(recs) else 'stale'
            report = dict(stats, status=status, expected=len(all_recs), vectors_written=0, dim=EDGE_DIM,
                          missing=missing, limited=limit is not None)
            with db:
                finish_component(db, run_id, 'vectors_edges', generation, status, report)
            return report
        try:
            load_vec(db)
        except ImportError:
            report = dict(stats, status='missing', vectors_written=0, reason='sqlite-vec is unavailable')
            with db:
                finish_component(db, run_id, 'vectors_edges', generation, 'missing', report)
            return report
        if any(len(v) != EDGE_DIM*4 for v in vecs):
            raise ValueError('Invalid packed edge vector dimension')
        db.execute('CREATE TABLE IF NOT EXISTS vec_meta(name TEXT PRIMARY KEY, value TEXT NOT NULL)')
        from embed import MODEL
        meta = dict(db.execute('SELECT name,value FROM vec_meta'))
        if meta.get('edge_model') not in (None, MODEL) or meta.get('edge_dim') not in (None, str(EDGE_DIM)):
            db.execute('DROP TABLE IF EXISTS vec_edges')
            db.execute("UPDATE run_components SET status='stale' WHERE component='vectors_edges' AND run_id<>?", (run_id,))
        db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS vec_edges USING vec0(embedding float[%d] distance_metric=cosine)' % EDGE_DIM)
        db.execute('CREATE TABLE IF NOT EXISTS vector_records(collection TEXT,record_id INTEGER,content_hash TEXT,PRIMARY KEY(collection,record_id))')
        n = 0
        with db:
            live = {r['id'] for r in db.execute('SELECT id FROM edge_passages')}
            for (rid,) in db.execute('SELECT rowid FROM vec_edges').fetchall():
                if rid not in live:
                    db.execute('DELETE FROM vec_edges WHERE rowid=?', (rid,))
            for r, v in zip(recs, vecs):
                db.execute('DELETE FROM vec_edges WHERE rowid=?', (r['id'],))
                db.execute('INSERT INTO vec_edges(rowid,embedding) VALUES(?,?)', (r['id'], v))
                from hashlib import sha256
                db.execute('INSERT OR REPLACE INTO vector_records VALUES(?,?,?)',
                           ('edges', r['id'], sha256(r['passage'].encode('utf-8')).hexdigest()))
                n += 1
            db.execute("INSERT OR REPLACE INTO vec_meta VALUES('edge_dim',?)", (str(EDGE_DIM),))
            db.execute("INSERT OR REPLACE INTO vec_meta VALUES('edge_model',?)", (MODEL,))
            report = dict(stats, status='ready', expected=len(all_recs), vectors_written=n, dim=EDGE_DIM)
            finish_component(db, run_id, 'vectors_edges', generation, details=report)
        return report
    except Exception as exc:
        fail_component(db, run_id, 'vectors_edges', generation, exc)
        raise
    finally:
        db.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--run', required=True); p.add_argument('--db', default=str(DEFAULT_DB))
    p.add_argument('--limit', type=int, help='embed only the first N passages (test)')
    p.add_argument('--skip-build', action='store_true')
    p.add_argument('--allow-network', action='store_true')
    a = p.parse_args()
    run_id = Path(a.run).name
    out = {} if a.skip_build else {'passages': build_passages(a.run, a.db)}
    out['vectors'] = embed_passages(run_id, a.db, a.limit, a.allow_network)
    print(json.dumps(out, ensure_ascii=False, indent=2))
