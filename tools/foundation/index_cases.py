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
from common import (ROOT, DEFAULT_DB, connect, upsert_text, rebuild_fts, rows, source_snapshot,
                    verify_snapshot, start_component, finish_component, fail_component, fingerprint,
                    resolve_artifact, policy_from_manifest, selected_corpus_rows,
                    corpus_field_evidence)

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
    generation = start_component(db, run_id, 'cases')
    try:
        snapshot = source_snapshot(db, run_id, run_dir)
        db.execute('UPDATE run_components SET source_fingerprint=? WHERE run_id=? AND component=?',
                   (fingerprint(snapshot), run_id, 'cases'))
        db.commit()
        groups = {r['group_id']: r for r in db.execute(
            "SELECT * FROM case_groups WHERE run_id=? AND (name<>'' OR dd>=2)", (run_id,))}
        key2g, cites = {}, collections.defaultdict(set)
        for court, mk, g, cs in db.execute(
                'SELECT court,merge_key,merged_group_id,canonical_string FROM members WHERE run_id=?', (run_id,)):
            if g in groups:
                key2g[(court, mk)] = g
                cites[g].add(cs)
        # A merge candidate can be counted here but excluded by adjudication later
        # (including self-citations). Profiles must use the same final edge set as DD.
        final_edges = {(src, g): support for src, g, support in db.execute(
            'SELECT source_decision,resolved_cited_case,edge_support FROM citation_edges WHERE run_id=?', (run_id,))}
        weights = dict(db.execute("SELECT group_id,weighted_dd FROM scores WHERE run_id=? AND scoring_version='canlii-t6-v1'",
                                  (run_id,)))
        names = dict(db.execute('SELECT source_id,name FROM documents WHERE run_id=?', (run_id,)))
        document_sources = {(r['court'], r['corpus_row']): r['source_id'] for r in db.execute(
            'SELECT court,corpus_row,source_id FROM documents WHERE run_id=?', (run_id,))}

        # candidate citing mentions: counted, one per citing judgment; keep the CANDIDATES with the
        # smallest stable hash so they spread across courts and years
        allm = collections.defaultdict(dict)
        excluded = 0
        manifest = json.loads(db.execute('SELECT manifest_json FROM runs WHERE run_id=?', (run_id,)).fetchone()[0])
        courts, policy = manifest['params']['courts'], policy_from_manifest(manifest)
        for court in courts:
                for line, r in enumerate(rows(run_dir/'merge_out'/court/'mentions_candidates.csv'), 2):
                    if r['arbitration_status'] != 'counted':
                        continue
                    g = key2g.get((court, r['merge_key']))
                    src = r['source_decision_citation']
                    if not g:
                        continue
                    if (src, g) not in final_edges:
                        excluded += 1
                        continue
                    if src in allm[g]:
                        continue
                    row = int(r['corpus_row_index'])
                    a, b = int(r['match_start_offset']), int(r['match_end_offset'])
                    if document_sources.get((court, row)) != src or not 0 <= a < b:
                        raise ValueError('Mention locator disagrees with imported judgment: %s:%s' % (court, line))
                    allm[g][src] = (court, row, src, a, b, line, r.get('raw_string'))
        picks = {}
        need = collections.defaultdict(set)
        for g, m in allm.items():
            picks[g] = [m[k] for k in sorted(m, key=spread)[:CANDIDATES]]
            for court, row, *_ in picks[g]:
                need[court].add(row)
        del allm
        windows, window_ends, field_selections = {}, {}, {}
        for court in courts:
            texts = {}
            pf = pq.ParquetFile(snapshot['corpus/'+court+'.parquet']['path'])
            for i, selected in selected_corpus_rows(pf, policy):
                if i in need[court]:
                    texts[i] = selected['text']
                    field_selections[(court, i)] = corpus_field_evidence(selected)
            for g, ps in picks.items():
                for (c, row, src, a, b, line, raw) in ps:
                    if c == court:
                        t = texts.get(row, '')
                        if b > len(t):
                            raise ValueError('Mention offset outside corpus text: %s:%s' % (court, line))
                        # extract.raw_string folds whitespace; its offsets still
                        # address the unmodified original Unicode text.
                        if raw is not None and re.sub(r'\s+', ' ', t[a:b]).strip() != raw:
                            raise ValueError('Mention text disagrees with selected corpus field: %s:%s' % (court, line))
                        windows[(g, src)] = clean(t[max(0, a-BEFORE): b+AFTER])
                        window_ends[(g, src)] = min(len(t), b+AFTER)
            del texts

        n = 0
        with db:
            db.execute("DELETE FROM text_records WHERE collection='cases' AND run_id=?", (run_id,))
            db.execute('DELETE FROM profile_passages WHERE run_id=?', (run_id,))
            for g, r in groups.items():
                ctx = []
                cand = [(prose_score(windows.get((g, p[2]), '')), p[2]) for p in picks.get(g, [])]
                selected = [src for _, src in sorted(cand, reverse=True)[:contexts_for(r['dd'])]]
                for src in selected:
                    ctx.append('[%s %s | edge_support=%s] %s' % (
                        src, names.get(src, ''), final_edges[(src, g)] or 'unclassified', windows.get((g, src), '')))
                    c, row, _, a, b, line, _ = next(p for p in picks[g] if p[2] == src)
                    evidence = {'court': c, 'corpus_row': row, 'match_start': a, 'match_end': b,
                                'window_start': max(0, a-BEFORE), 'window_end': window_ends[(g, src)],
                                'corpus': {'logical_path': 'corpus/'+c+'.parquet', **field_selections[(c, row)]},
                                'mentions': {'logical_path': 'merge_out/'+c+'/mentions_candidates.csv'},
                                'mention_record': line, 'edge_support': final_edges[(src, g)]}
                    db.execute('INSERT INTO profile_passages VALUES(?,?,?,?)',
                               (run_id, g, src, json.dumps(evidence, ensure_ascii=False, separators=(',', ':'))))
                cs = sorted(cites[g])[:8]
                w = weights.get(g)
                body = '\n'.join([r['name'] or '(no case name)', '; '.join(cs),
                                  'DD %d%s | origin %s %s' % (r['dd'], (' | weighted %.1f' % w) if w is not None else '',
                                                              r['foreign_status'], r['origin_country'])] + ctx)
                upsert_text(db, 'cases', run_id+'/'+g, 'results', 'experimental', r['name'] or (cs[0] if cs else g),
                            body, '%s:record=%d' % (resolve_artifact(run_dir/'select_out/selected.csv'), r['primary_row']), run_id)
                n += 1
            rebuild_fts(db)
            verify_snapshot(snapshot)
            report = {'run_id': run_id, 'profiles': n, 'with_context': sum(1 for g in groups if picks.get(g)),
                      'candidate_mentions_excluded_by_final_edges': excluded, 'source_fingerprint': fingerprint(snapshot),
                      'text_policy': policy}
            finish_component(db, run_id, 'cases', generation, details=report)
        return report
    except Exception as exc:
        fail_component(db, run_id, 'cases', generation, exc)
        raise
    finally:
        db.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--run', required=True); p.add_argument('--db', default=str(DEFAULT_DB))
    a = p.parse_args()
    print(json.dumps(build_profiles(a.run, a.db), ensure_ascii=False, indent=2))
