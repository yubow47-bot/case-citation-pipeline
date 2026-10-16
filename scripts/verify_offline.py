"""Run the offline regression suites with workspace-local temporary files.

Every exit code is checked; logs and a compact JSON receipt are retained.
Use --run and --expect to compare an explicit run with a frozen three-court baseline.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def discover_suites(root=ROOT):
    """Keep script-style regressions in separate interpreters; discover new files automatically."""
    suites = [(p.stem, [p.relative_to(root).as_posix()])
              for p in sorted((root/'pipeline/tests').glob('test_*.py'))]
    if not suites:
        raise ValueError('No pipeline test suites discovered')
    suites.append(('extraction_selftest', ['pipeline/tests/run_regression.py', '--selftest']))
    suites += [(name, ['-m', 'unittest', 'discover', '-s', directory, '-p', 'test_*.py'])
               for name, directory in (
                   ('foundation', 'tools/foundation'), ('tools', 'tools/tests'),
                   ('quality', 'tools/quality/tests'), ('research', 'tools/research'),
                   ('audit_readers', 'audit/canlii_crosscheck'),
                   ('citation_context', 'tools/citation_context'))]
    return suites


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', default='implementation/offline_verification')
    parser.add_argument('--temp-root', default=str(ROOT/'implementation'),
                        help='Writable workspace directory for temporary fixtures')
    parser.add_argument('--golden', action='store_true', help='Requires explicit --run and --expect')
    parser.add_argument('--run', help='Completed run directory for a frozen output comparison')
    parser.add_argument('--expect', help='Reviewed frozen run-golden-v1 JSON')
    args = parser.parse_args(argv)
    if bool(args.run) != bool(args.expect) or (args.golden and not args.run):
        parser.error('Golden comparison requires both --run and --expect')
    output = Path(args.output).absolute()
    output.mkdir(parents=True, exist_ok=True)
    temp_root = Path(args.temp_root).resolve()
    temp_root.mkdir(parents=True, exist_ok=True)
    suites = discover_suites()
    if args.run:
        suites.append(('run_golden', ['scripts/check_run_golden.py', '--run', args.run, '--expect', args.expect]))
    report = {'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'python': sys.version, 'network_allowed': False, 'suites': [],
              'assertions': 0, 'unittest_cases': 0}
    with tempfile.TemporaryDirectory(prefix='verify-', dir=temp_root) as temp:
        env = dict(os.environ, PYTHONIOENCODING='utf-8', TEMP=temp, TMP=temp)
        for name, command in suites:
            started = time.monotonic()
            result = subprocess.run([sys.executable, *command], cwd=ROOT, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    encoding='utf-8', errors='replace')
            log = result.stdout
            assertions = re.search(r'全部通过：\s*(\d+)\s*条断言', log)
            cases = re.search(r'Ran (\d+) tests?', log)
            n_assertions = int(assertions[1]) if assertions else 0
            n_cases = int(cases[1]) if cases else 0
            report['assertions'] += n_assertions
            report['unittest_cases'] += n_cases
            (output/(name+'.log')).write_text(log[-2*1024*1024:], encoding='utf-8')
            item = {'name': name, 'command': command, 'exit_code': result.returncode,
                    'seconds': round(time.monotonic()-started, 3),
                    'assertions': n_assertions, 'unittest_cases': n_cases,
                    'log_truncated': len(log) > 2*1024*1024}
            report['suites'].append(item)
            print(f"{name}: {'PASS' if result.returncode == 0 else 'FAIL'}", flush=True)
            if result.returncode:
                print(log[-2500:], flush=True)
    report['status'] = 'passed' if all(r['exit_code'] == 0 for r in report['suites']) else 'failed'
    (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('status', 'assertions', 'unittest_cases')}, ensure_ascii=False))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
