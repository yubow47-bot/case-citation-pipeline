"""Label every citation edge with a relation type, by identity rather than by wording.

  same_case_history  the cited group also contains a citation printed by the source judgment itself
                     (its citation_en / citation2_en): the source and the cited judgment are two levels of
                     the same litigation (the Supreme Court judgment naming the appeal court below it).
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
from pathlib import Path
from common import ROOT, DEFAULT_DB, connect

csv.field_size_limit(10**9)


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
        have_own = own_file.exists()
        if have_own:
            for r in csv.DictReader(own_file.open(encoding='utf-8', newline='')):
                own[r['merge_key']].add(r['decision_id'])
        keys_of = collections.defaultdict(set)      # group -> merge keys
        for g, mk in db.execute('SELECT DISTINCT merged_group_id,merge_key FROM members WHERE run_id=?', (run_id,)):
            keys_of[g].add(mk)
        counts = collections.Counter()
        rows = []
        for s, g in db.execute('SELECT source_decision,resolved_cited_case FROM citation_edges WHERE run_id=?', (run_id,)):
            if not have_own:
                t = 'unknown'
            else:
                t = 'same_case_history' if any(s in own.get(k, ()) for k in keys_of[g]) else 'other_judgment'
            counts[t] += 1
            rows.append((run_id, s, g, t))
        with db:
            db.execute('DELETE FROM edge_relations WHERE run_id=?', (run_id,))
            db.executemany('INSERT INTO edge_relations VALUES(?,?,?,?)', rows)
        return {'run_id': run_id, 'edges': len(rows), 'by_relation': dict(counts), 'own_citations_file': have_own}
    finally:
        db.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--run', required=True); p.add_argument('--db', default=str(DEFAULT_DB))
    a = p.parse_args()
    print(json.dumps(label(a.run, a.db), ensure_ascii=False, indent=2))
