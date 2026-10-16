"""Print-evidence channel for non-case periodicals (PROBLEMS #138).

For every abbreviation that fills the reporter slot of a counted reporter
candidate, count how many mentions have a quoted title immediately before the
citation (`... “Title” (1987), 66 Can. Bar Rev. 727`). Case reports are cited
after party names, so their share is ~0 (S.C.R. 0.001, O.R. 0.000, L.J.K.B.
0.000); periodicals print an article title (McGill L.J. 0.957). The output is
evidence for decisions/non_case_sources.csv rows; the pipeline never reads it.

    python audit/non_case_quote_channel.py --run data/run_NAME \
        --output audit/findings/non_case_sources_20261016/quote_channel.csv
"""
import argparse
import re

import pandas as pd

QUOTE_TAIL = re.compile(r'[”"]\s*,?\s*(?:\(\s*(?:1[6-9]|20)\d{2}\s*\)\s*,?\s*)?$')


def nk(s):
    return re.sub(r'[^A-Za-z0-9]', '', s or '').lower()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--run', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--courts', default='SCC,ONCA,BCCA')
    a = ap.parse_args()
    parts = []
    for court in a.courts.split(','):
        x = pd.read_csv(f'{a.run}/classify_out/{court}/classified.csv.gz',
                        usecols=['preceding_text', 'abbreviation', 'citation_kind', 'rejected_reason',
                                 'source_decision_citation'], dtype=str, keep_default_na=False)
        x = x[(x.citation_kind == 'reporter') & (x.rejected_reason == '')]
        parts.append(x.assign(quoted=x.preceding_text.str.contains(QUOTE_TAIL))[
            ['abbreviation', 'quoted', 'source_decision_citation']])
    x = pd.concat(parts)
    x['normalized_key'] = x.abbreviation.map(nk)
    g = x.groupby('normalized_key').agg(
        mentions=('quoted', 'size'), quoted_title_mentions=('quoted', 'sum'),
        printed_form=('abbreviation', lambda s: s.value_counts().index[0]),
        citing_decisions=('source_decision_citation', 'nunique'))
    g['quoted_share'] = (g.quoted_title_mentions / g.mentions).round(3)
    g = g[g.mentions >= 10].sort_values(['quoted_share', 'mentions'], ascending=[False, False])
    g.to_csv(a.output, encoding='utf-8')
    print(len(g), 'abbreviations with >= 10 counted mentions ->', a.output)


if __name__ == '__main__':
    main()
