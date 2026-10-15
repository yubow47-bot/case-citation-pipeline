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
import json
import math
import sqlite3
import sys
from common import DEFAULT_DB, connect, component_status
from embed import embed_texts, load_vec, vec_table, MODEL, DIM
from index_edges import EDGE_DIM
from rewrite import to_english, has_cjk

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


def require_vector(db, run_id, collection):
    state = component_status(db, run_id, 'vectors_' + collection)
    if state != 'ready':
        raise ValueError('Vector search is %s for %s/%s; use --mode keyword or complete the cached index.' %
                         (state, run_id, collection))
    load_vec(db)
    if not db.execute('SELECT 1 FROM sqlite_master WHERE name=?', (vec_table(collection),)).fetchone():
        raise ValueError('Published vector table is missing: ' + collection)
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='vec_meta'").fetchone():
        raise ValueError('Vector model metadata is missing; use --mode keyword.')
    meta = dict(db.execute('SELECT name,value FROM vec_meta'))
    model_key, dim_key, dimension = ('edge_model', 'edge_dim', EDGE_DIM) if collection == 'edges' else ('model', 'dim', DIM)
    if meta.get(model_key) != MODEL or meta.get(dim_key) != str(dimension):
        raise ValueError('Vector model metadata is stale; use --mode keyword.')
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='vector_records'").fetchone():
        raise ValueError('Vector content bindings are missing; rebuild the index or use --mode keyword.')
    if collection != 'edges':
        where, args = ('t.collection=?', [collection])
        if collection != 'methods':
            where += ' AND t.run_id=?'; args.append(run_id)
        stale = db.execute('SELECT COUNT(*) FROM text_records t WHERE ' + where +
            ' AND (NOT EXISTS(SELECT 1 FROM vector_records v WHERE v.collection=t.collection AND v.record_id=t.id '
            'AND v.content_hash=t.content_hash) OR NOT EXISTS(SELECT 1 FROM ' + vec_table(collection) + ' x WHERE x.rowid=t.id))', args).fetchone()[0]
    else:
        stale = db.execute('SELECT COUNT(*) FROM edge_passages e WHERE e.run_id=? AND '
            '(NOT EXISTS(SELECT 1 FROM vector_records v WHERE v.collection=\'edges\' AND v.record_id=e.id) '
            'OR NOT EXISTS(SELECT 1 FROM vec_edges x WHERE x.rowid=e.id))', (run_id,)).fetchone()[0]
    if stale:
        raise ValueError('Vector records are incomplete or stale; use --mode keyword.')


def available_mode(db, run_id, collection, mode):
    if mode != 'hybrid':
        return mode
    try:
        require_vector(db, run_id, collection)
    except (ValueError, ImportError, sqlite3.Error) as exc:
        print('Hybrid search uses keyword mode: %s' % exc, file=sys.stderr)
        return 'keyword'
    return mode


def search(db, q, collection, k, mode, layer=None, english=None,
           run_id=None, min_dd=None, origin=None, allow_network=False):
    """`english`: English rewrite of a Chinese question (see rewrite.py). The vector side searches with
    both the original and the rewrite; the keyword side uses the rewrite (the index is English)."""
    # The eligible set is shared by FTS and KNN. Filtering only after their LIMIT/k
    # lets another run (or collection/layer) consume all candidate slots.
    where, args = ['t.collection=?'], [collection]
    source = 'FROM text_records t'
    fts_source = 'FROM text_fts CROSS JOIN text_records t ON t.id=text_fts.rowid'
    if collection == 'cases':
        run_id = run_id or latest_run(db)
        if run_id is None:
            return []
        group_join = ('case_groups g ON g.run_id=t.run_id '
                      'AND g.group_id=substr(t.entity_key,length(t.run_id)+2)')
        source += ' JOIN ' + group_join
        fts_source += ' CROSS JOIN ' + group_join
        where.append('t.run_id=?'); args.append(run_id)
        if min_dd is not None:
            where.append('g.dd>=?'); args.append(min_dd)
        if origin:
            where.append('g.foreign_status=?'); args.append(origin)
    if layer is not None:
        where.append('t.layer=?'); args.append(layer)
    eligible = 'SELECT t.id ' + source + ' WHERE ' + ' AND '.join(where)
    ranks = {}
    variants = [x for x in (q, english) if x]
    mode = available_mode(db, run_id or latest_run(db), collection, mode)
    if mode in ('hybrid', 'vector'):
        require_vector(db, run_id or latest_run(db), collection)
        vs, stats = embed_texts(variants, allow_network=allow_network)
        if any(v is None for v in vs):
            if mode == 'vector':
                raise ValueError('Query embedding is absent from the offline cache; use --mode keyword.')
            print('Hybrid search uses keyword mode: query embedding is absent from the offline cache.', file=sys.stderr)
            vs = []
        for v in vs:
            if v is None:
                continue
            rows = db.execute('SELECT rowid,distance FROM %s WHERE embedding MATCH ? AND k=? '
                              'AND rowid IN (%s)' % (vec_table(collection), eligible),
                              (v, k * 6, *args)).fetchall()
            for i, (rid, _) in enumerate(rows):
                ranks.setdefault(rid, 0.0)
                ranks[rid] += 1.0 / (60 + i)
    if mode in ('hybrid', 'keyword'):
        f = fts_query(english or q)
        if f:
            # Keep FTS as the outer scan: a large rowid IN list makes FTS probe
            # separately for every eligible record instead of scanning matches.
            rows = db.execute('SELECT text_fts.rowid ' + fts_source +
                              ' WHERE text_fts MATCH ? AND ' + ' AND '.join(where) +
                              ' ORDER BY text_fts.rank LIMIT ?',
                              (f, *args, k * 6)).fetchall()
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
        dates = ["d.run_id=e.run_id", "d.source_id=e.source_decision", "d.decision_date<>''"]
        if a.year_from:
            dates.append('substr(d.decision_date,1,4)>=?'); args.append(str(a.year_from))
        if a.year_to:
            dates.append('substr(d.decision_date,1,4)<=?'); args.append(str(a.year_to))
        where.append('EXISTS(SELECT 1 FROM documents d WHERE ' + ' AND '.join(dates) + ')')
    if a.relation:
        where.append('EXISTS(SELECT 1 FROM edge_relations r WHERE r.run_id=e.run_id '
                     'AND r.source_decision=e.source_decision '
                     'AND r.resolved_cited_case=e.resolved_cited_case AND r.relation_type=?)')
        args.append(a.relation)
    return ' AND '.join(where), args


def search_edges(db, run, q, a, english=None):
    """Citation edges whose passage matches the question, optionally limited to one cited case, court,
    years, or relation type. Run and research filters apply before FTS LIMIT and vector k."""
    if run is None or (a.relation and not _has_relations(db)):
        return []
    cited = _cited_ids(db, run, a)
    where, args = _edge_filter_sql(a, cited)
    if where is None:
        return []
    eligible = 'SELECT e.id FROM edge_passages e WHERE ' + where
    args = [run] + args
    ranks = {}
    variants = [x for x in (q, english) if x]
    mode = available_mode(db, run, 'edges', a.mode)
    if mode in ('hybrid', 'vector'):
        require_vector(db, run, 'edges')
        vs, _ = embed_texts(variants, dim=EDGE_DIM, allow_network=getattr(a, 'allow_network', False))
        if any(v is None for v in vs):
            if mode == 'vector':
                raise ValueError('Edge query embedding is absent from the offline cache; use --mode keyword.')
            print('Hybrid search uses keyword mode: edge query embedding is absent from the offline cache.', file=sys.stderr)
            vs = []
        for v in vs:
            if v is None:
                continue
            rows = [r[0] for r in db.execute('SELECT rowid FROM vec_edges WHERE embedding MATCH ? AND k=? '
                                            'AND rowid IN (%s)' % eligible,
                                            (v, a.k * 6, *args))]
            for i, rid in enumerate(rows):
                ranks[rid] = ranks.get(rid, 0.0) + 1.0 / (60 + i)
    if mode in ('hybrid', 'keyword'):
        f = fts_query(english or q)
        if f:
            rows = [r[0] for r in db.execute('SELECT edge_fts.rowid FROM edge_fts '
                                            'CROSS JOIN edge_passages e ON e.id=edge_fts.rowid '
                                            'WHERE edge_fts MATCH ? AND ' + where +
                                            ' ORDER BY edge_fts.rank LIMIT ?',
                                            (f, *args, a.k * 6))]
            for i, rid in enumerate(rows):
                ranks[rid] = ranks.get(rid, 0.0) + 1.0 / (60 + i)
    return sorted(ranks.items(), key=lambda x: -x[1])[:a.k]


def show_edges(db, run, hits):
    for n, (rid, _) in enumerate(hits, 1):
        e = db.execute('SELECT * FROM edge_passages WHERE id=? AND run_id=?', (rid, run)).fetchone()
        if e is None:
            continue
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
    en = to_english(q, allow_network=getattr(a, 'allow_network', False)) if a.collection in ('cases', 'edges') else ''
    if en:
        print('  (searching also as: %s)' % en)
    elif a.collection in ('cases', 'edges') and has_cjk(q) and not getattr(a, 'allow_network', False):
        print('  离线中文改写缓存未命中；仅搜索原始词，匹配英文判决的范围有限。可提供英文法律术语。')
    if a.collection == 'edges':
        return show_edges(db, run, search_edges(db, run, q, a, en))
    hits = search(db, q, a.collection, a.k, a.mode, a.layer, en,
                  run_id=run, min_dd=a.min_dd, origin=a.origin, allow_network=getattr(a, 'allow_network', False))
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
    p.add_argument('--allow-network', action='store_true', help='explicitly allow query embedding and rewrite API requests')
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
    if a.k < 1:
        p.error('-k must be positive')
    db = connect(a.db, readonly=True)
    run = a.run or latest_run(db)
    if a.collection in ('cases', 'edges') or a.count or a.case:
        record = db.execute('SELECT status,manifest_json,input_fingerprint FROM runs WHERE run_id=?', (run,)).fetchone()
        if not record or record['status'] != 'ready':
            raise ValueError('No published run is available for this query; finish offline acceptance first.')
        courts = json.loads(record['manifest_json']).get('params', {}).get('courts', [])
        print('run %s | courts %s | input %s' % (run, ','.join(courts), record['input_fingerprint']))
    if not (a.count or a.case):
        a.mode = available_mode(db, run, a.collection, a.mode)
    if not (a.count or a.case) and a.mode == 'vector':
        require_vector(db, run, a.collection)
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
