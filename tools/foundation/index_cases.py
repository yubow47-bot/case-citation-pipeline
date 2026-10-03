"""Build one searchable profile per case group: name, printed citations, DD/weight, and up to two
passages from citing judgments (the words around the citation). Feeds keyword (FTS) and vector search.

Scope: groups with a case name or DD>=2 (unnamed DD=1 groups carry little meaning and hold most of the
non-case noise found in the CanLII calibration). Exact queries and statistics still use the full tables.
"""
import argparse
import collections
import csv
import json
import os
import re
from pathlib import Path
from common import ROOT, DEFAULT_DB, connect, nk, upsert_text, rebuild_fts

BEFORE, AFTER = 330, 120   # the proposition a case is cited for usually precedes the citation
CANDIDATES = 40            # citing passages looked at per group, spread over all citing judgments
CITE_LIKE = re.compile(r'\d|[;\[\]()]')
CASE_NAME = re.compile(r'\bv\.?\s|\bRe\s')
LIST_HEAD = re.compile(r'Cases Cited|referred to:|considered:|applied:|distinguished:|followed:|Authors Cited|Statutes and Regulations Cited')


def contexts_for(dd):
    return 2 if dd < 5 else 3 if dd < 50 else 4


def prose_score(w):
    """A passage that states what the case decided beats a list of cases.
    Penalise digits/brackets, other case names in the window, and SCC 'Cases Cited' headnote lists."""
    if not w:
        return -9.0
    s = 1 - len(CITE_LIKE.findall(w)) / len(w)
    s -= 0.06 * len(CASE_NAME.findall(w))
    s -= 0.5 * bool(LIST_HEAD.search(w))
    return s


def spread(src):
    """Stable pseudo-random order, so the candidates are not just the oldest SCC judgments in file order."""
    import hashlib
    return hashlib.md5(src.encode()).hexdigest()


def clean(s):
    return ' '.join(s.split())


def build_profiles(run_dir, db_path=DEFAULT_DB):
    import pyarrow.parquet as pq
    run_dir = Path(run_dir).resolve()
    run_id = run_dir.name
    db = connect(db_path)
    try:
        groups = {r['group_id']: r for r in db.execute(
            "SELECT * FROM case_groups WHERE run_id=? AND (name<>'' OR dd>=2)", (run_id,))}
        key2g, cites = {}, collections.defaultdict(set)
        for court, mk, g, cs in db.execute(
                'SELECT court,merge_key,merged_group_id,canonical_string FROM members WHERE run_id=?', (run_id,)):
            if g in groups:
                key2g[(court, mk)] = g
                cites[g].add(cs)
        ckeys = {g: {nk(c) for c in v} for g, v in cites.items()}
        weights = dict(db.execute("SELECT group_id,weighted_dd FROM scores WHERE run_id=? AND scoring_version='canlii-t6-v1'",
                                  (run_id,)))
        names = dict(db.execute('SELECT source_id,name FROM documents WHERE run_id=?', (run_id,)))

        # candidate citing mentions: counted, one per citing judgment; keep the CANDIDATES with the
        # smallest stable hash so they spread across courts and years
        allm = collections.defaultdict(dict)
        courts = json.loads(db.execute('SELECT manifest_json FROM runs WHERE run_id=?', (run_id,)).fetchone()[0])['params']['courts']
        for court in courts:
            with (run_dir/'merge_out'/court/'mentions_candidates.csv').open(encoding='utf-8', newline='') as f:
                for r in csv.DictReader(f):
                    if r['arbitration_status'] != 'counted':
                        continue
                    g = key2g.get((court, r['merge_key']))
                    src = r['source_decision_citation']
                    if not g or src in allm[g]:
                        continue
                    if src.split('_', 1)[-1] in ckeys[g]:   # self-citation leak (PROBLEMS #105): not a citing passage
                        continue
                    allm[g][src] = (court, int(r['corpus_row_index']), src, int(r['match_start_offset']), int(r['match_end_offset']))
        picks = {}
        need = collections.defaultdict(set)
        for g, m in allm.items():
            picks[g] = [m[k] for k in sorted(m, key=spread)[:CANDIDATES]]
            for court, row, *_ in picks[g]:
                need[court].add(row)
        del allm
        windows = {}
        for court in courts:
            texts = {}
            pf = pq.ParquetFile(ROOT/'corpus'/(court+'.parquet'))
            i = 0
            for b in pf.iter_batches(batch_size=500, columns=['unofficial_text_en']):
                for t in b.column(0).to_pylist():
                    if i in need[court]:
                        texts[i] = t or ''
                    i += 1
            for g, ps in picks.items():
                for (c, row, src, a, b) in ps:
                    if c == court:
                        t = texts.get(row, '')
                        windows[(g, src)] = clean(t[max(0, a-BEFORE): b+AFTER])
            del texts

        n = 0
        with db:
            db.execute("DELETE FROM text_records WHERE collection='cases' AND run_id=?", (run_id,))
            for g, r in groups.items():
                ctx = []
                cand = [(prose_score(windows.get((g, p[2]), '')), p[2]) for p in picks.get(g, [])]
                for _, src in sorted(cand, reverse=True)[:contexts_for(r['dd'])]:
                    ctx.append('[%s %s] %s' % (src, names.get(src, ''), windows.get((g, src), '')))
                cs = sorted(cites[g])[:8]
                w = weights.get(g)
                body = '\n'.join([r['name'] or '(no case name)', '; '.join(cs),
                                  'DD %d%s | origin %s %s' % (r['dd'], (' | weighted %.1f' % w) if w is not None else '',
                                                              r['foreign_status'], r['origin_country'])] + ctx)
                upsert_text(db, 'cases', run_id+'/'+g, 'results', 'experimental', r['name'] or (cs[0] if cs else g),
                            body, '%s/select_out/selected.csv:record=%d' % (run_dir, r['primary_row']), run_id)
                n += 1
            rebuild_fts(db)
        return {'run_id': run_id, 'profiles': n, 'with_context': sum(1 for g in groups if picks[g])}
    finally:
        db.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--run', required=True); p.add_argument('--db', default=str(DEFAULT_DB))
    a = p.parse_args()
    print(json.dumps(build_profiles(a.run, a.db), ensure_ascii=False, indent=2))
