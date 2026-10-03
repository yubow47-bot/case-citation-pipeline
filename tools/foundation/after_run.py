"""After a pipeline run: import -> DD weights -> case profiles -> method records -> vectors -> acceptance.

    python tools/foundation/after_run.py --run data/run_20261002_tables2
    python tools/foundation/after_run.py --pipeline-out data/run_YYYYMMDD_x     # run the pipeline first, then index

The pipeline itself is untouched and never reads anything produced here. Each step is idempotent:
re-running on the same run only embeds texts that are new or changed (vector cache).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from common import ROOT, DEFAULT_DB
import build
import score
import index_cases
import index_methods
import embed


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--run', help='an existing complete run directory')
    g.add_argument('--pipeline-out', help='run pipeline/run_all.py into this new directory first')
    p.add_argument('--db', default=str(DEFAULT_DB))
    p.add_argument('--skip-acceptance', action='store_true')
    a = p.parse_args()

    run_dir = Path(a.run or a.pipeline_out).resolve()
    if a.pipeline_out:
        subprocess.run([sys.executable, str(ROOT/'pipeline'/'run_all.py'), '--out', str(run_dir)], check=True, cwd=ROOT)
    report = {'run': run_dir.name}
    report['import'] = build.build(run_dir, a.db)
    rates = ROOT/'audit'/'findings'/'canlii_crosscheck'/run_dir.name/'t6_bucket_rates.csv'
    if not rates.exists():
        # no calibration for this run yet: reuse the newest one, and say so
        found = sorted((ROOT/'audit'/'findings'/'canlii_crosscheck').glob('*/t6_bucket_rates.csv'))
        rates = found[-1] if found else None
    report['weights'] = score.score(run_dir.name, a.db, rates) if rates else 'skipped: no calibration file'
    report['case_profiles'] = index_cases.build_profiles(run_dir, a.db)
    report['methods'] = index_methods.build(a.db)
    report['vectors'] = embed.index(['cases', 'methods'], a.db)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    if not a.skip_acceptance:
        subprocess.run([sys.executable, str(Path(__file__).with_name('acceptance.py')), '--db', a.db], cwd=ROOT)


if __name__ == '__main__':
    main()
