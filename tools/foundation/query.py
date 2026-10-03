"""Search the pipeline results (and the method library) by meaning and by keyword.

    python tools/foundation/query.py "standard of appellate review"          # cases, hybrid search
    python tools/foundation/query.py "上诉审查标准" --min-dd 5               # Chinese works too
    python tools/foundation/query.py "Housen" --mode keyword                  # keyword only
    python tools/foundation/query.py --case XC-G012345                        # one case: who cites it
    python tools/foundation/query.py "同形缩写怎么消歧" --collection methods --layer classification
    python tools/foundation/query.py                                          # interactive prompt

Hybrid = vector neighbours + keyword (FTS trigram) hits, merged by reciprocal rank. Counts and
statistics come from the full tables (use --count), never from the top hits.
"""
import argparse
import math
import sys
from common import DEFAULT_DB, connect
from embed import embed_texts, load_vec, vec_table

PRIOR = 0.5    # weight of the authority prior (tuned on acceptance.py: 0 -> 6/15, 0.15 -> 11/15, 0.5 -> 14/15; those questions all seek leading cases, so this favours well-cited cases)


def latest_run(db):
    r = db.execute("SELECT run_id FROM runs WHERE status='ready' ORDER BY imported_at DESC LIMIT 1").fetchone()
    return r[0] if r else None


def fts_query(q):
    terms = [t for t in q.replace('"', ' ').split() if len(t) >= 3]
    return ' OR '.join('"%s"' % t for t in terms) if terms else None


def search(db, q, collection, k, mode, layer=None):
    ranks = {}
    if mode in ('hybrid', 'vector'):
        v, _ = embed_texts([q])
        if v[0] is not None:
            rows = db.execute('SELECT rowid,distance FROM %s WHERE embedding MATCH ? AND k=?' % vec_table(collection),
                              (v[0], k * 6)).fetchall()
            for i, (rid, _) in enumerate(rows):
                ranks.setdefault(rid, 0.0)
                ranks[rid] += 1.0 / (60 + i)
    if mode in ('hybrid', 'keyword'):
        f = fts_query(q)
        if f:
            rows = db.execute('SELECT rowid FROM text_fts WHERE text_fts MATCH ? ORDER BY rank LIMIT ?', (f, k * 6)).fetchall()
            for i, (rid,) in enumerate(rows):
                ranks.setdefault(rid, 0.0)
                ranks[rid] += 1.0 / (60 + i)
    out = []
    for rid, s in ranks.items():
        r = db.execute('SELECT * FROM text_records WHERE id=?', (rid,)).fetchone()
        if r and r['collection'] == collection and (layer is None or r['layer'] == layer):
            if collection == 'cases' and PRIOR:
                # authority prior: among passages about the same topic, the case courts rely on most
                # should come first; weighted DD (not raw DD) so likely non-case noise gets no boost
                w = db.execute("SELECT weighted_dd FROM scores WHERE run_id=? AND group_id=? AND scoring_version='canlii-t6-v1'",
                               (r['run_id'], r['entity_key'].split('/', 1)[1])).fetchone()
                s += PRIOR * math.log1p(w[0] if w else 0) / 60
            out.append((s, r))
    return sorted(out, key=lambda x: -x[0])


def case_row(db, run, gid):
    g = db.execute('SELECT * FROM case_groups WHERE run_id=? AND group_id=?', (run, gid)).fetchone()
    s = db.execute("SELECT confidence,weighted_dd FROM scores WHERE run_id=? AND group_id=? AND scoring_version='canlii-t6-v1'",
                   (run, gid)).fetchone()
    return g, s


def show_case(db, run, gid, rec=None, citing=5):
    g, s = case_row(db, run, gid)
    if not g:
        print('  (group not in run %s)' % run)
        return
    cites = [r[0] for r in db.execute('SELECT DISTINCT canonical_string FROM members WHERE run_id=? AND merged_group_id=? LIMIT 6',
                                      (run, gid))]
    print('  %s  [%s]' % (g['name'] or '(no case name)', gid))
    print('    citations: ' + '; '.join(cites))
    w = ('  weighted DD %.1f (confidence %.2f, experimental)' % (s['weighted_dd'], s['confidence'])) if s else ''
    print('    DD %d%s  origin %s %s' % (g['dd'], w, g['foreign_status'], g['origin_country']))
    rows = db.execute('''SELECT e.source_decision, d.name, d.decision_date FROM citation_edges e
        LEFT JOIN documents d ON d.run_id=e.run_id AND d.source_id=e.source_decision
        WHERE e.run_id=? AND e.resolved_cited_case=? ORDER BY d.decision_date DESC LIMIT ?''', (run, gid, citing)).fetchall()
    if rows:
        print('    cited by (latest %d of %d): ' % (len(rows), g['dd']) + '; '.join(
            '%s %s (%s)' % (r[0], (r[1] or '')[:40], (r[2] or '')[:10]) for r in rows))
    if rec is not None:
        ctx = [l for l in rec['text'].split('\n') if l.startswith('[')]
        if ctx:
            print('    context: ' + ctx[0][:300])
        print('    source: ' + rec['source_locator'])
    print('    trace:  python pipeline/traceback.py --run-dir data/%s --search "%s"' % (run, (g['name'] or cites[0] if cites else gid)[:40]))


def count(db, run, a):
    where, args = ['g.run_id=?'], [run]
    if a.min_dd:
        where.append('g.dd>=?'); args.append(a.min_dd)
    if a.origin:
        where.append('g.foreign_status=?'); args.append(a.origin)
    if a.name:
        where.append('g.name LIKE ?'); args.append('%' + a.name + '%')
    n = db.execute('SELECT COUNT(*), COALESCE(SUM(g.dd),0) FROM case_groups g WHERE ' + ' AND '.join(where), args).fetchone()
    print('groups: %d   total DD: %d   (exact, full table, run %s)' % (n[0], n[1], run))


def run_query(db, a, q):
    run = a.run or latest_run(db)
    hits = search(db, q, a.collection, a.k, a.mode, a.layer)
    shown = 0
    for s, r in hits:
        if a.collection == 'cases':
            gid = r['entity_key'].split('/', 1)[1]
            if r['run_id'] != run:
                continue
            g, _ = case_row(db, run, gid)
            if not g or g['dd'] < (a.min_dd or 0) or (a.origin and g['foreign_status'] != a.origin):
                continue
            shown += 1
            print('%d.' % shown)
            show_case(db, run, gid, r)
        else:
            shown += 1
            print('%d. [%s | %s] %s' % (shown, r['layer'], r['status'], r['title']))
            print('    ' + ' '.join(r['text'].split())[:500])
            print('    source: ' + r['source_locator'])
        if shown >= a.k:
            break
    if not shown:
        print('no hits')


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('query', nargs='?')
    p.add_argument('--collection', default='cases', choices=['cases', 'methods'])
    p.add_argument('--mode', default='hybrid', choices=['hybrid', 'vector', 'keyword'])
    p.add_argument('-k', type=int, default=8)
    p.add_argument('--min-dd', type=int)
    p.add_argument('--origin', help='DOMESTIC_CA / FOREIGN / UNDETERMINED')
    p.add_argument('--layer', help='methods only: extraction / classification / merging / adjudication / selection / ...')
    p.add_argument('--case', help='show one case group and its citing decisions')
    p.add_argument('--count', action='store_true', help='exact count over the full table (with --min-dd/--origin/--name)')
    p.add_argument('--name')
    p.add_argument('--run')
    p.add_argument('--db', default=str(DEFAULT_DB))
    a = p.parse_args()
    db = connect(a.db, readonly=True)
    load_vec(db)
    run = a.run or latest_run(db)
    if a.count:
        return count(db, run, a)
    if a.case:
        return show_case(db, run, a.case, citing=20)
    if a.query:
        return run_query(db, a, a.query)
    print('Search pipeline results (%s). Empty line to quit.' % run)
    while True:
        try:
            q = input('> ').strip()
        except EOFError:
            break
        if not q:
            break
        run_query(db, a, q)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()
