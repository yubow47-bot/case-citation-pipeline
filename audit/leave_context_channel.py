"""Print-evidence channel for SCC leave reporters (PROBLEMS #141).

Share of counted mentions of a reporter-slot abbreviation whose preceding 160
characters carry leave-to-appeal wording (leave to appeal / leave refused /
leave denied / appeal quashed / autorisation d'appel). Evidence for
decisions/identity_court_scope.csv rows; the pipeline never reads it.

    python audit/leave_context_channel.py --run data/run_NAME --abbreviation S.C.C.A. \
        --output audit/findings/leave_context_20261016/scca.json
"""
import argparse
import json
import re

import pandas as pd

LEAVE = re.compile(r"leave to app|leave (?:refused|denied|dismissed|granted)|appeal quashed|autorisation d.appel|"
                   r"application for leave|Supreme Court of Canada", re.I)


def nk(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--run', required=True)
    ap.add_argument('--abbreviation', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    key, total, hits, kinds, misses = nk(a.abbreviation), 0, 0, {}, []
    for court in ('SCC', 'ONCA', 'BCCA'):
        x = pd.read_csv(f'{a.run}/classify_out/{court}/classified.csv.gz',
                        usecols=['preceding_text', 'rejected_reason', 'abbreviation', 'citation_kind', 'raw_string'],
                        dtype=str, keep_default_na=False)
        x = x[(x.rejected_reason == '') & (x.abbreviation.map(nk) == key)]
        h = x.preceding_text.str[-160:].str.contains(LEAVE)
        total += len(x)
        hits += int(h.sum())
        for k, n in x.citation_kind.value_counts().items():
            kinds[k] = kinds.get(k, 0) + int(n)
        misses += [p[-100:] for p in x[~h].preceding_text.head(20)]
    out = {'run': a.run, 'abbreviation': a.abbreviation, 'counted_mentions': total,
           'with_leave_context': hits, 'share': round(hits / total, 4) if total else None,
           'citation_kinds': kinds, 'sample_without_context': misses[:40]}
    with open(a.output, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ('counted_mentions', 'with_leave_context', 'share', 'citation_kinds')}))


if __name__ == '__main__':
    main()
