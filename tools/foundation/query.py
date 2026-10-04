"""Search the pipeline results (and the method library) by meaning and by keyword.

    python tools/foundation/query.py "standard of appellate review"          # cases, hybrid search
    python tools/foundation/query.py "上诉审查标准" --min-dd 5               # Chinese works too
    python tools/foundation/query.py "Housen" --mode keyword                  # keyword only
    python tools/foundation/query.py --case XC-G012345                        # one case: who cites it
    python tools/foundation/query.py "同形缩写怎么消歧" --collection methods --layer classification
    python tools/foundation/query.py "standard of review" --collection edges --cited-name Housen --court BCCA --year-from 2015
    python tools/foundation/query.py                                          # interactive prompt

Hybrid = vector neighbours + keyword (FTS trigram) hits, merged by reciprocal rank. Counts and
statistics come from the full tables (use --count), never from the top hits.
"""
import argparse
import math
import struct
import sys
from common import DEFAULT_DB, connect
from embed import embed_texts, load_vec, vec_table
from index_edges import EDGE_DIM
from rewrite import to_english

# Methods: the two best-matching hand-written method cards are always shown in the top k (reserved slots);
# the other slots stay by score, so code and decision-table fragments are not crowded out.
CARD_SLOTS = 2
PRIOR = 0.5    # weight of the authority prior (tuned on acceptance.py: 0 -> 6/15, 0.15 -> 11/15, 0.5 -> 14/15; those questions all seek leading cases, so this favours well-cited cases)


def latest_run(db):
    r = db.execute("SELECT run_id FROM runs WHERE status='ready' ORDER BY imported_at DESC LIMIT 1").fetchone()
    return r[0] if r else None


def fts_query(q):
    terms = [t for t in q.replace('"', ' ').split() if len(t) >= 3]
    return ' OR '.join('"%s"' % t for t in terms) if terms else None


def search(db, q, collection, k, mode, layer=None, english=None):
    """`english`: English rewrite of a Chinese question (see rewrite.py). The vector side searches with
    both the original and the rewrite; the keyword side uses the rewrite (the index is English)."""
    ranks = {}
    variants = [x for x in (q, english) if x]
    if mode in ('hybrid', 'vector'):
        vs, _ = embed_texts(variants)
        for v in vs:
            if v is None:
                continue
            rows = db.execute('SELECT rowid,distance FROM %s WHERE embedding MATCH ? AND k=?' % vec_table(collection),
                              (v, k * 6)).fetchall()
            for i, (rid, _) in enumerate(rows):
                ranks.setdefault(rid, 0.0)
                ranks[rid] += 1.0 / (60 + i)
    if mode in ('hybrid', 'keyword'):
        f = fts_query(english or q)
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
    out.sort(key=lambda x: -x[0])
    if collection == 'methods' and CARD_SLOTS:
        cards = [x for x in out if x[1]['status'] == 'method_card'][:CARD_SLOTS]
        others = [x for x in out if x[1]['status'] != 'method_card']
        keep = cards + others[:max(0, k - len(cards))]
        keep_ids = {x[1]['id'] for x in keep}
        out = sorted(keep, key=lambda x: -x[0]) + [x for x in out if x[1]['id'] not in keep_ids]
    return out


def _has_relations(db):
    return db.execute("SELECT 1 FROM sqlite_master WHERE name='edge_relations'").fetchone() is not None


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
    rel = dict(db.execute("SELECT relation_type,COUNT(*) FROM edge_relations WHERE run_id=? AND resolved_cited_case=? GROUP BY 1",
                          (run, gid)).fetchall()) if _has_relations(db) else {}
    if rel.get('same_case_history'):
        print('    of the %d citing judgments, %d are the same litigation (procedural history), %d other judgments'
              % (g['dd'], rel['same_case_history'], rel.get('other_judgment', 0)))
    if rows:
        print('    cited by (latest %d of %d): ' % (len(rows), g['dd']) + '; '.join(
            '%s %s (%s)' % (r[0], (r[1] or '')[:40], (r[2] or '')[:10]) for r in rows))
    if rec is not None:
        ctx = [l for l in rec['text'].split('\n') if l.startswith('[')]
        if ctx:
            print('    context: ' + ctx[0][:300])
        print('    source: ' + rec['source_locator'])
    print('    trace:  python pipeline/trace_source.py --run-dir data/%s --search "%s"' % (run, (g['name'] or cites[0] if cites else gid)[:40]))


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


def _cited_ids(db, run, a):
    """Group ids selected by --cited / --cited-name, or None when no such filter is given."""
    ids = set()
    if a.cited:
        ids |= set(a.cited.split(','))
    if a.cited_name:
        ids |= {r[0] for r in db.execute('SELECT group_id FROM case_groups WHERE run_id=? AND name LIKE ?',
                                         (run, '%' + a.cited_name + '%'))}
    return ids if (a.cited or a.cited_name) else None


def _edge_filter_sql(a, cited):
    where, args = ['e.run_id=?'], []
    if cited is not None:
        if not cited:
            return None, None
        where.append('e.resolved_cited_case IN (%s)' % ','.join('?' * len(cited)))
        args += sorted(cited)
    if a.court:
        where.append('e.source_decision GLOB ?'); args.append(a.court.upper() + '_*')
    if a.year_from or a.year_to:
        where.append("d.decision_date<>''")
        if a.year_from:
            where.append('substr(d.decision_date,1,4)>=?'); args.append(str(a.year_from))
        if a.year_to:
            where.append('substr(d.decision_date,1,4)<=?'); args.append(str(a.year_to))
    if a.relation:
        where.append('r.relation_type=?'); args.append(a.relation)
    return ' AND '.join(where), args


def search_edges(db, run, q, a, english=None):
    """Citation edges whose passage matches the question, optionally limited to one cited case, court,
    years, or relation type. Narrow filters are applied first (exact), then ranked; broad ones post-filter."""
    cited = _cited_ids(db, run, a)
    where, args = _edge_filter_sql(a, cited)
    if where is None:
        return []
    base = ('FROM edge_passages e LEFT JOIN documents d ON d.run_id=e.run_id AND d.source_id=e.source_decision '
            'LEFT JOIN edge_relations r ON r.run_id=e.run_id AND r.source_decision=e.source_decision '
            'AND r.resolved_cited_case=e.resolved_cited_case WHERE ' + where)
    allowed = None
    filtered = cited is not None or a.court or a.year_from or a.year_to or a.relation
    if filtered:
        allowed = [r[0] for r in db.execute('SELECT e.id ' + base, [run] + args)]
        if not allowed:
            return []
    ranks = {}
    variants = [x for x in (q, english) if x]
    if a.mode in ('hybrid', 'vector'):
        vs, _ = embed_texts(variants, dim=EDGE_DIM)
        for v in vs:
            if v is None:
                continue
            if allowed is not None and len(allowed) <= 30000:
                # exact ranking inside a narrow subset (unit vectors: dot product = cosine)
                q_ = struct.unpack('%df' % EDGE_DIM, v)
                scored = []
                for i in range(0, len(allowed), 900):
                    chunk = allowed[i:i + 900]
                    for rid, emb in db.execute('SELECT rowid,embedding FROM vec_edges WHERE rowid IN (%s)' % ','.join('?' * len(chunk)), chunk):
                        scored.append((sum(x * y for x, y in zip(q_, struct.unpack('%df' % EDGE_DIM, emb))), rid))
                scored.sort(reverse=True)
                rows = [rid for _, rid in scored[:a.k * 6]]
            else:
                rows = [r[0] for r in db.execute('SELECT rowid FROM vec_edges WHERE embedding MATCH ? AND k=?',
                                                 (v, a.k * 60 if allowed is not None else a.k * 6))]
                if allowed is not None:
                    keep = set(allowed)
                    rows = [x for x in rows if x in keep]
            for i, rid in enumerate(rows):
                ranks[rid] = ranks.get(rid, 0.0) + 1.0 / (60 + i)
    if a.mode in ('hybrid', 'keyword'):
        f = fts_query(english or q)
        if f:
            rows = [r[0] for r in db.execute('SELECT rowid FROM edge_fts WHERE edge_fts MATCH ? ORDER BY rank LIMIT ?',
                                             (f, a.k * (60 if allowed is not None else 6)))]
            if allowed is not None:
                keep = set(allowed)
                rows = [x for x in rows if x in keep]
            for i, rid in enumerate(rows):
                ranks[rid] = ranks.get(rid, 0.0) + 1.0 / (60 + i)
    return sorted(ranks.items(), key=lambda x: -x[1])[:a.k]


def show_edges(db, run, hits):
    for n, (rid, _) in enumerate(hits, 1):
        e = db.execute('SELECT * FROM edge_passages WHERE id=?', (rid,)).fetchone()
        src = db.execute('SELECT name,decision_date FROM documents WHERE run_id=? AND source_id=?', (run, e['source_decision'])).fetchone()
        g = db.execute('SELECT name,dd FROM case_groups WHERE run_id=? AND group_id=?', (run, e['resolved_cited_case'])).fetchone()
        cite = db.execute('SELECT canonical_string FROM members WHERE run_id=? AND merged_group_id=? LIMIT 1',
                          (run, e['resolved_cited_case'])).fetchone()
        rel = db.execute('SELECT relation_type FROM edge_relations WHERE run_id=? AND source_decision=? AND resolved_cited_case=?',
                         (run, e['source_decision'], e['resolved_cited_case'])).fetchone() if _has_relations(db) else None
        print('%d. %s %s (%s)' % (n, e['source_decision'], (src[0] if src else '')[:50], (src[1] if src else '')[:10]))
        print('   cites: %s [%s]  %s  DD %d' % ((g['name'] if g else '') or '(no case name)', e['resolved_cited_case'],
                                                  cite[0] if cite else '', g['dd'] if g else 0)
              + ('  <%s>' % rel[0] if rel and rel[0] != 'other_judgment' else ''))
        print('   passage: ' + e['passage'][:420])
    if not hits:
        print('no hits')


def run_query(db, a, q):
    run = a.run or latest_run(db)
    en = to_english(q) if a.collection in ('cases', 'edges') else ''   # method docs are Chinese: no rewrite
    if en:
        print('  (searching also as: %s)' % en)
    if a.collection == 'edges':
        return show_edges(db, run, search_edges(db, run, q, a, en))
    hits = search(db, q, a.collection, a.k, a.mode, a.layer, en)
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
    p.add_argument('--collection', default='cases', choices=['cases', 'methods', 'edges'],
                   help='cases (default), methods, or edges = the passages where one judgment cites another')
    p.add_argument('--mode', default='hybrid', choices=['hybrid', 'vector', 'keyword'])
    p.add_argument('-k', type=int, default=8)
    p.add_argument('--min-dd', type=int)
    p.add_argument('--origin', help='DOMESTIC_CA / FOREIGN / UNDETERMINED')
    p.add_argument('--layer', help='methods only: extraction / classification / merging / adjudication / selection / ...')
    p.add_argument('--case', help='show one case group and its citing decisions')
    p.add_argument('--count', action='store_true', help='exact count over the full table (with --min-dd/--origin/--name)')
    p.add_argument('--name')
    p.add_argument('--cited', help='edges: cited case group id(s), comma separated')
    p.add_argument('--cited-name', help='edges: cited case name contains this text')
    p.add_argument('--court', help='edges: citing court, e.g. BCCA')
    p.add_argument('--year-from', type=int); p.add_argument('--year-to', type=int)
    p.add_argument('--relation', choices=['same_case_history', 'other_judgment'], help='edges: relation type')
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
