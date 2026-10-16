"""Label every citation edge with a relation type, by identity rather than by wording.

  same_case_history  the cited group also contains a citation printed by the source judgment itself
                     (its citation_en / citation2_en): the source and the cited judgment are two levels of
                     the same litigation (the Supreme Court judgment naming the appeal court below it).
  probable_same_litigation
                     the source judgment's own title equals the cited group's title (case-insensitive,
                     punctuation and a final citation year ignored) and the cited group's printed year is
                     0-6 years before the source. A title match is not identity proof: it marks the
                     earlier stages of one proceeding (the judgment under appeal, a prior ruling in the
                     same file) and can include a different case with the same common title (PROBLEMS #140;
                     a 150-edge probe found history wording or a header citation in 128).
  other_judgment     everything else: another judgment named by the source (authority, comparison, ...).

DD counts both: it is the number of distinct source judgments that name the case (decision of
2026-10-03: procedural history is a real relation between judgments). A researcher who wants authority
citations only filters on relation_type. This step does not read the surrounding words: "APPEAL from"
and "Reported at" are not used as evidence. Each source counts once per cited group (one edge per pair).

Needs <run>/registry/decision_own_citations.csv (written by the pipeline's registry step); runs made
before that file existed get relation_type 'unknown'.
"""
import argparse
import collections
import csv
import json
import re
from pathlib import Path
from common import ROOT, DEFAULT_DB, connect, rows, resolve_artifact

csv.field_size_limit(10**9)
HISTORY_WINDOW_YEARS = 6


def title_key(name):
    """Comparable title: lowercase letters and digits, without a final `(YYYY)` citation year."""
    name = re.sub(r'\s*\((?:1[6-9]|20)\d{2}\)$', '', name or '')
    return re.sub(r'[^a-z0-9]', '', name.lower())


def year_of(text):
    m = re.match(r'\s*((?:1[6-9]|20)\d{2})', text or '')
    return int(m.group(1)) if m else None


def relation_of(own_hit, source_title, source_year, cited_title, cited_year):
    """One edge's relation type from identity first, then the dated title match."""
    if own_hit:
        return 'same_case_history'
    if (source_title and source_title == cited_title and source_year is not None
            and cited_year is not None and 0 <= source_year - cited_year <= HISTORY_WINDOW_YEARS):
        return 'probable_same_litigation'
    return 'other_judgment'


def label(run_dir, db_path=DEFAULT_DB):
    run_dir = Path(run_dir).resolve()
    run_id = run_dir.name
    own_file = run_dir/'registry'/'decision_own_citations.csv'
    db = connect(db_path)
    try:
        db.execute('''CREATE TABLE IF NOT EXISTS edge_relations(
            run_id TEXT NOT NULL, source_decision TEXT NOT NULL, resolved_cited_case TEXT NOT NULL,
            relation_type TEXT NOT NULL, PRIMARY KEY(run_id,source_decision,resolved_cited_case))''')
        own = collections.defaultdict(set)          # merge_key -> {decision ids that printed it}
        have_own = own_file.exists() or Path(str(own_file)+'.gz').exists()
        if have_own:
            for r in rows(own_file):
                own[r['merge_key']].add(r['decision_id'])
        keys_of = collections.defaultdict(set)      # group -> merge keys
        for g, mk in db.execute('SELECT DISTINCT merged_group_id,merge_key FROM members WHERE run_id=?', (run_id,)):
            keys_of[g].add(mk)
        sources = {sid: (title_key(name), year_of(date)) for sid, name, date in db.execute(
            'SELECT source_id,name,decision_date FROM documents WHERE run_id=?', (run_id,))}
        groups = {gid: (title_key(name), year_of(year)) for gid, name, year in db.execute(
            'SELECT group_id,name,year_printed FROM case_groups WHERE run_id=?', (run_id,))}
        counts = collections.Counter()
        records = []
        for s, g in db.execute('SELECT source_decision,resolved_cited_case FROM citation_edges WHERE run_id=?', (run_id,)):
            if not have_own:
                t = 'unknown'
            else:
                st, sy = sources.get(s, ('', None))
                gt, gy = groups.get(g, ('', None))
                t = relation_of(any(s in own.get(k, ()) for k in keys_of[g]), st, sy, gt, gy)
            counts[t] += 1
            records.append((run_id, s, g, t))
        with db:
            db.execute('DELETE FROM edge_relations WHERE run_id=?', (run_id,))
            db.executemany('INSERT INTO edge_relations VALUES(?,?,?,?)', records)
        return {'run_id': run_id, 'edges': len(records), 'by_relation': dict(counts), 'own_citations_file': have_own}
    finally:
        db.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--run', required=True); p.add_argument('--db', default=str(DEFAULT_DB))
    a = p.parse_args()
    print(json.dumps(label(a.run, a.db), ensure_ascii=False, indent=2))
