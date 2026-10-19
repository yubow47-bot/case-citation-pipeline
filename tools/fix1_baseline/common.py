# Locally adapted from the existing engineering-fix baseline; G source remains unchanged.
"""Shared loaders for the engineering-fix baseline measurements.

Every script takes the same three paths so it can be pointed at Run B (baseline)
or at the fixed run (after) without code changes:
  --run-dir      case-citation-pipeline/data/<run_id>   (merge_out/<COURT>/...)
  --norm-dir     analysis/<run_id>/normalized           (04_members, 05_edges)
  --courts-dir   analysis/<run_id>/courts               (11_edge_courts)
  --corpus-dir   case-citation-pipeline/corpus          (<COURT>.parquet)
Outputs are written as JSON/CSV under --out. Nothing here writes into a run.
"""
import argparse, json, os, re
import pandas as pd
import pyarrow.parquet as pq

COURTS = ['SCC', 'ONCA', 'BCCA', 'NSCA', 'FCA', 'YKCA', 'FC', 'BCSC', 'NSSC']
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def args(extra=None):
    p = argparse.ArgumentParser()
    p.add_argument('--reference-root', required=True)
    p.add_argument('--baseline-signatures')
    p.add_argument('--run-id', default='run_20261017_a2aj9_fixed')
    p.add_argument('--run-dir')
    p.add_argument('--norm-dir')
    p.add_argument('--courts-dir')
    p.add_argument('--corpus-dir', default=os.path.join(ROOT, 'case-citation-pipeline', 'corpus'))
    p.add_argument('--out')
    p.add_argument('--courts', default=','.join(COURTS))
    for a, kw in (extra or []):
        p.add_argument(a, **kw)
    a = p.parse_args()
    a.run_dir = a.run_dir or os.path.join(ROOT, 'case-citation-pipeline', 'data', a.run_id)
    a.norm_dir = a.norm_dir or os.path.join(ROOT, 'analysis', a.run_id, 'normalized')
    a.courts_dir = a.courts_dir or os.path.join(ROOT, 'analysis', a.run_id, 'courts')
    a.out = a.out or os.path.join(os.path.dirname(__file__), 'outputs', a.run_id)
    a.courts = a.courts.split(',')
    os.makedirs(a.out, exist_ok=True)
    return a


def common_sources(norm_dir, court=None):
    """Eligible source judgments on the common calendar 2001-2025 excluding 2011."""
    e = pd.read_csv(os.path.join(norm_dir, '05_edges.csv.gz'),
                    usecols=['source_decision', 'resolved_cited_case', 'source_court', 'source_year', 'eligible_source',
                             'foreign_status'], low_memory=False)
    e = e[(e.eligible_source == True) & e.source_year.between(2001, 2025) & (e.source_year != 2011)]
    if court:
        e = e[e.source_court == court]
    return e


def counted_mentions(run_dir, court, cols=('corpus_row_index', 'source_decision_citation', 'match_start_offset',
                                           'match_end_offset', 'merge_key', 'raw_string', 'citation_kind')):
    m = pd.read_csv(os.path.join(run_dir, 'merge_out', court, 'mentions_candidates.csv.gz'),
                    usecols=list(cols) + ['arbitration_status'], low_memory=False)
    return m[m.arbitration_status == 'counted'].drop(columns=['arbitration_status'])


def key_to_group(run_dir, norm_dir, court, members=None):
    """Source-conditioned mapping; ambiguous member keys cannot choose an ordinal winner."""
    km = pd.read_csv(os.path.join(run_dir, 'merge_out', court, 'key_mapping.csv.gz'))
    kmap = dict(zip(km.old_merge_key, km.new_merge_key))
    mapping = pd.read_csv(os.path.join(norm_dir, 'source_member_groups.csv.gz'))
    mapping = mapping[mapping.row_key.str.startswith(court + '|')]
    by_source = {}
    for row in mapping.itertuples():
        pair = (row.source_id, row.row_key.split('|', 1)[1])
        if pair in by_source and by_source[pair] != row.group_id:
            raise ValueError('Ambiguous source-conditioned member: ' + str(pair))
        by_source[pair] = row.group_id
    return lambda key, source: by_source.get((source, kmap.get(key, key)))


def load_members(norm_dir):
    return pd.read_csv(os.path.join(norm_dir, '04_members.csv.gz'),
                       usecols=['merge_key', 'court', 'merged_group_id', 'case_name_modal', 'year_printed'],
                       low_memory=False)


def texts(corpus_dir, court):
    t = pq.read_table(os.path.join(corpus_dir, court + '.parquet'), columns=['unofficial_text_en', 'unofficial_text_fr'])
    en = t.column(0).to_pylist(); fr = t.column(1).to_pylist()
    return [a if a else (b or '') for a, b in zip(en, fr)]


def dump(out, name, obj):
    with open(os.path.join(out, name), 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=float)
    print(name, json.dumps(obj, ensure_ascii=False, default=float)[:1500])
