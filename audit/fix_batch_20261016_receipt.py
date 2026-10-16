"""Receipt for the 2026-10-16 fix batch (PROBLEMS #133-#143): before/after metrics of two sealed runs.

    python audit/fix_batch_20261016_receipt.py --base data/run_20261016_country_complete \
        --new data/run_20261016_fixes_full3 --metadata-db data/foundation/research.db \
        --output audit/findings/fix_batch_20261016/validation.json

Reads run outputs and explicitly selected corpus metadata; writes only the requested receipt.
The numbers describe the runs; they are not an accuracy estimate.
"""
import argparse
from contextlib import closing
import collections
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/foundation'))
import relations  # noqa: E402

PROV = {'ON', 'BC', 'QC', 'AB', 'MB', 'SK', 'NS', 'NB', 'NL', 'PE'}
HISTORY = re.compile(r"(?:leave to appeal(?: to (?:the )?(?:S\.C\.C\.|SCC|Supreme Court(?: of Canada)?))?"
                     r"(?: (?:refused|dismissed|denied|granted|quashed))?|aff(?:[’']?d|irmed|irming|[’']?g)"
                     r"|rev(?:[’']?d|ersed|ersing|[’']?g)|var(?:[’']?d|ied|ying))(?:\s+(?:on other grounds|in part))?"
                     r"[\s,;:]*\(?\s*$", re.I)


def path(p):
    return p + '.gz' if os.path.exists(p + '.gz') else p


def read(run, rel, cols=None):
    import pandas as pd
    return pd.read_csv(path(f'{run}/{rel}'), dtype=str, keep_default_na=False, usecols=cols)


def history_pairs(run):
    """Fixed probe on the base run's counted mentions: adjacent pairs joined by a connector."""
    pairs = set()
    for court in ('SCC', 'ONCA', 'BCCA'):
        m = read(run, f'merge_out/{court}/mentions_candidates.csv',
                 ['candidate_id', 'source_decision_citation', 'match_start_offset', 'match_end_offset',
                  'merge_key', 'arbitration_status'])
        m = m[m.arbitration_status == 'counted']
        c = read(run, f'classify_out/{court}/classified.csv', ['candidate_id', 'preceding_text'])
        m = m.merge(c, on='candidate_id', how='left')
        m['s'] = m.match_start_offset.astype(int)
        m['e'] = m.match_end_offset.astype(int)
        prev = None
        for r in m.sort_values(['source_decision_citation', 's']).itertuples():
            if (prev is not None and prev.source_decision_citation == r.source_decision_citation
                    and 0 <= r.s - prev.e <= 160 and HISTORY.search(r.preceding_text or '')
                    and prev.merge_key != r.merge_key):
                pairs.add((court, prev.merge_key, r.merge_key))
            prev = r
    return pairs


def metrics(run, pairs, docs):
    d = read(run, 'decide_out/cross_court/decided.csv')
    e = read(run, 'edges/citation_edges.csv', ['source_decision', 'resolved_cited_case', 'foreign_status'])
    missing = set(e.source_decision) - docs.keys()
    if missing:
        raise ValueError('Missing source metadata for %d edge sources: %s' % (len(missing), sorted(missing)[:5]))
    eff = read(run, 'decide_out/cross_court/effective_sources.csv', ['status'])
    p = d[d.is_primary == 'true']
    dd = p.distinct_decisions_count.astype(int)
    pos = p[dd > 0]
    fs = pos.group_foreign_status.value_counts()
    efs = e.foreign_status.value_counts()
    out = {'rows': len(d), 'groups': len(p), 'groups_dd_gt0': int((dd > 0).sum()),
           'groups_dd_ge5': int((dd >= 5).sum()), 'edges': len(e),
           'excluded_self': int((eff.status == 'excluded_self').sum()),
           'country_groups_pct': round(100 * (fs.get('DOMESTIC_CA', 0) + fs.get('FOREIGN', 0)) / len(pos), 2),
           'country_edges_pct': round(100 * (efs.get('DOMESTIC_CA', 0) + efs.get('FOREIGN', 0)) / len(e), 2),
           'undetermined_groups': int(fs.get('UNDETERMINED', 0))}
    k = d.groupby('merge_key').merged_group_id.nunique()
    out['merge_keys_in_multiple_groups'] = int((k > 1).sum())
    oc = d[d.observed_deciding_court != ''].groupby('merged_group_id').observed_deciding_court.nunique()
    out['groups_with_two_printed_courts'] = int((oc > 1).sum())
    pv = d[d.jurisdiction.isin(PROV)].groupby('merged_group_id').jurisdiction.nunique()
    out['groups_with_two_provincial_reporters'] = int((pv > 1).sum())
    gid = dict(zip(d.court + '|' + d.merge_key, d.merged_group_id))
    inside = [x for x in pairs if gid.get(x[0] + '|' + x[1]) and gid.get(x[0] + '|' + x[1]) == gid.get(x[0] + '|' + x[2])]
    out['history_pairs_probe'] = len(pairs)
    out['history_pairs_inside_one_group'] = len(inside)
    named = set(d[d.case_name_modal != ''].merged_group_id)
    empty = p[p.case_name_modal == '']
    out['empty_display_name_with_named_member'] = int(empty.merged_group_id.isin(named).sum())
    out['empty_display_name_dd_ge5'] = int((empty.distinct_decisions_count.astype(int) >= 5).sum())
    lead = r'^(?:and|see,|see, e\.g\.|but see|also,|as noted|and in|and see)\s'
    out['display_names_with_prose_lead_in'] = int(p.case_name_modal.str.contains(lead, case=False, regex=True).sum())
    out['display_names_with_final_year'] = int(p.case_name_modal.str.contains(r'\((?:1[6-9]|20)\d{2}\)$', regex=True).sum())
    groups = {g: (relations.title_key(n), relations.year_of(y))
              for g, n, y in zip(p.merged_group_id, p.case_name_modal, p.year_printed)}
    keys = d.groupby('merged_group_id').merge_key.agg(set).to_dict()
    own = collections.defaultdict(set)
    o = read(run, 'registry/decision_own_citations.csv', ['merge_key', 'decision_id'])
    for key, did in zip(o.merge_key, o.decision_id):
        own[key].add(did)
    labels = collections.Counter()
    for s, g in zip(e.source_decision, e.resolved_cited_case):
        st, sy = docs.get(s, ('', None))
        gt, gy = groups.get(g, ('', None))
        labels[relations.relation_of(any(s in own.get(k, ()) for k in keys.get(g, ())), st, sy, gt, gy)] += 1
    out['relation_labels'] = dict(labels)
    probes = {}
    for key in ('1964||ac||465', '1951||ac||601', '|71|ccc|3d|1', '|135|ccc|3d|41', '1992|2|scr||168',
                '1991|3|or|3d|193', '1994|18|or|3d|385', '1995|2|scr||1130'):
        hit = d[d.merge_key == key]
        probes[key] = sorted({(g, int(p.set_index('merged_group_id').loc[g, 'distinct_decisions_count']),
                               p.set_index('merged_group_id').loc[g, 'case_name_modal']) for g in hit.merged_group_id})
    out['probes'] = probes
    return out


def load_documents(db_path, run_id):
    """Use an explicitly selected immutable metadata generation, never the active pointer."""
    with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        rows = db.execute('SELECT source_id,name,decision_date FROM documents WHERE run_id=? ORDER BY source_id',
                          (run_id,)).fetchall()
    if not rows:
        raise ValueError('No source metadata for run: ' + run_id)
    if len({r[0] for r in rows}) != len(rows) or any(not r[0] for r in rows):
        raise ValueError('Source metadata IDs must be nonempty and unique')
    docs = {sid: (relations.title_key(n), relations.year_of(dt)) for sid, n, dt in rows}
    return docs, {'db': str(Path(db_path).resolve()), 'run_id': run_id, 'documents': len(rows),
                  'metadata_sha256': hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--base', required=True)
    ap.add_argument('--new', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--metadata-db', required=True, help='Explicit read-only metadata DB; independent of production pointer')
    ap.add_argument('--metadata-run', help='Metadata run ID; defaults to the base directory name')
    a = ap.parse_args(argv)
    docs, metadata = load_documents(a.metadata_db, a.metadata_run or Path(a.base).resolve().name)
    pairs = history_pairs(a.base)
    receipt = {'protocol': 'fix-batch-20261016-v2', 'base': a.base, 'new': a.new, 'source_metadata': metadata,
               'base_manifest_status': json.load(open(f'{a.base}/run_manifest.json', encoding='utf-8'))['status'],
               'new_manifest_status': json.load(open(f'{a.new}/run_manifest.json', encoding='utf-8'))['status'],
               'before': metrics(a.base, pairs, docs), 'after': metrics(a.new, pairs, docs),
               'scope': 'Run-level counts and fixed probes. Not an accuracy estimate; no human labels.'}
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).write_text(json.dumps(receipt, ensure_ascii=False, indent=1, default=str) + '\n', encoding='utf-8')
    for k in receipt['before']:
        if k != 'probes':
            print(f"{k:42s} {receipt['before'][k]!s:>14} -> {receipt['after'][k]}")


if __name__ == '__main__':
    main()
