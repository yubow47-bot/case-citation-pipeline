"""Count same-row English/French official reporter citation pairs in a corpus file (PROBLEMS #139).

A2AJ prints the English and French citations of one judgment in citation_en /
citation_fr (and citation2_*). For the Supreme Court Reports every pair
`[Y] V SCR P` / `[Y] V RCS P` should agree on year, volume and page.

    python audit/bilingual_reporter_pairs.py --corpus corpus/SCC.parquet \
        --output audit/findings/bilingual_reporter_20261016/scr_rcs_pairs.json
"""
import argparse
import json
import re

import pyarrow.parquet as pq


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    df = pq.read_table(a.corpus, columns=['citation_en', 'citation2_en', 'citation_fr', 'citation2_fr']).to_pandas()
    en = re.compile(r'^\[(\d{4})\]\s*(\d*)\s*SCR\s+(\d+)$')
    fr = re.compile(r'^\[(\d{4})\]\s*(\d*)\s*RCS\s+(\d+)$')
    agree, disagree, examples = 0, [], []
    for row in df.itertuples(index=False):
        for e, f in ((row.citation_en, row.citation_fr), (row.citation2_en, row.citation2_fr)):
            me, mf = en.match(str(e or '')), fr.match(str(f or ''))
            if me and mf:
                if me.groups() == mf.groups():
                    agree += 1
                    if len(examples) < 5:
                        examples.append([e, f])
                else:
                    disagree.append([e, f])
    out = {'corpus': a.corpus, 'rows': len(df), 'same_row_pairs_agreeing': agree,
           'same_row_pairs_disagreeing': len(disagree), 'disagreements': disagree[:50], 'examples': examples}
    with open(a.output, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ('rows', 'same_row_pairs_agreeing', 'same_row_pairs_disagreeing')}))


if __name__ == '__main__':
    main()
