"""Write DD weights for one imported run from the CanLII calibration (outside the production pipeline).

confidence  = estimated share of real case citations for the group's DD bucket
              (audit/findings/canlii_crosscheck/<run>/t6_bucket_rates.csv), shrunk with a
              Beta(1,1) prior: (p*n + 1) / (n + 2), so small samples never claim 100%.
weighted_dd = dd * confidence.
Raw DD is never changed; the score is labelled experimental until validated on a held-out sample.
"""
import argparse
import csv
import json
from pathlib import Path
from common import ROOT, DEFAULT_DB, connect

VERSION = 'canlii-t6-v1'


def bucket(d):
    return '1' if d <= 1 else '2-4' if d <= 4 else '5-9' if d <= 9 else '10+'


def score(run_id, db_path=DEFAULT_DB, rates_path=None):
    rates_path = Path(rates_path or ROOT/'audit'/'findings'/'canlii_crosscheck'/run_id/'t6_bucket_rates.csv')
    conf = {}
    for r in csv.DictReader(rates_path.open(encoding='utf-8')):
        p, n = float(r['p_real']), int(r['n_sample'])
        conf[r['dd_bucket']] = (p*n + 1) / (n + 2)
    db = connect(db_path)
    try:
        with db:
            db.execute('DELETE FROM scores WHERE run_id=? AND scoring_version=?', (run_id, VERSION))
            rows = [(run_id, g, VERSION, conf[bucket(d)], d*conf[bucket(d)], 'dd_bucket:'+bucket(d), 'experimental')
                    for g, d in db.execute('SELECT group_id,dd FROM case_groups WHERE run_id=? AND dd>=1', (run_id,))]
            db.executemany('INSERT INTO scores VALUES(?,?,?,?,?,?,?)', rows)
        return {'run_id': run_id, 'version': VERSION, 'scored': len(rows), 'confidence_by_bucket': conf,
                'source': str(rates_path)}
    finally:
        db.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--run', required=True); p.add_argument('--db', default=str(DEFAULT_DB))
    p.add_argument('--rates')
    a = p.parse_args()
    print(json.dumps(score(Path(a.run).name, a.db, a.rates), ensure_ascii=False, indent=2))
