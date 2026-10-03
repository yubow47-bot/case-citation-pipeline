# -*- coding: utf-8 -*-
"""锚点对账（沿用 corpus_counts.py 的方法）：在原文里直接数"已知格式家族"出现多少次，
再看其中有多少被抽取候选覆盖，差额 = 漏抓。

口径：
  total   = 家族模式的非重叠匹配数
  party   = 其中前 100 字符内出现「X v./c. Y」案名结构者（真被引判决的强信号；
            证据页码、证物号几乎不会出现在案名之后）
  missed  = 其中不与任何候选区间重叠者；missed_party 同理
测量用的正则先过 PATTERN_ASSERTIONS（正反样例），不过不扫描。
只读测量；候选来自与生产同一函数 extract.extract_candidates。

用法：python audit/anchor_reconcile.py --court TCC --court SST --out audit/findings/anchor_20261003
"""
import argparse
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import pyarrow.parquet as pq  # noqa: E402
import extract  # noqa: E402

FAMILIES = {
    "no_serial":    r"\[\d{4}\]\s+(?:[A-Z][A-Za-z.]*\s?){1,4}\s[Nn]o\.\s?\d+",
    "fed_docket":   r"(?<![\w-])(?:A|T)-\d{1,5}-\d{2}(?![\w-])",
    "sst_decision": r"(?<![\w-])(?:AD|GE|GP|ADN)-\d{2}-\d{1,5}(?![\w-])",
    "pssrb_file":   r"\b(?:PSSRB|PSLRB|PSLREB|CLRB|CIRB)\s+Files?\s+Nos?\.?\s?\d+(?:-\d+){1,2}",
    "glued_neutral": r"(?<![\w])\d{4}(?:TCC|FCA|FC|SCC|ONCA|BCCA|SSTAD|SSTGD)\d+(?![\w])",
    "year_range":   r"\[\d{4}-\d{2,4}\]\s+\d*\s*[A-Z][A-Za-z.]+",
    "di_cite":      r"(?<![\w])\d{1,3}\s+di\s+\d{1,4}(?![\w])",
    "cp_pab":       r"(?<![\w])CP\s?\d{4,6}(?![\w])",
    "citt_number":  r"(?<![\w-])(?:AP|PR|NQ|RR|GC|PI|TR|EP)-\d{2,4}-\d{2,4}(?![\w-])",
    "wto_ds":       r"(?<![\w])WT/DS\d+",
    # 噪声对照：不该被抓，用来量"通配会灌进多少垃圾"
    "NOISE_sst_gd": r"(?<![\w-])(?:GD|AD|IS|RA|GT|RGD|GDJ)\s?\d{1,3}-\d{1,4}(?![\w-])",
    "NOISE_exhibit": r"(?:Exhibit|Solicitation No\.?)\s+[A-Z]{1,3}[-\d]+[\w/-]*",
}
PATTERN_ASSERTIONS = {
    "no_serial": (["Sheridan v. M.N.R., [1985] F.C.J. no. 230", "[2000] CIRB no. 99"],
                  ["[1985] 2 S.C.R. 100", "see no. 230"]),
    "fed_docket": (["Walford, A-263-78, 1978", "file T-1334-09)"], ["A-2630-780", "NA-12-34"]),
    "sst_decision": (["Reference number AD-16-785", "GE-16-1958,"], ["GD2-11", "AD-1-2"]),
    "pssrb_file": (["PSSRB File No. 168-02-37 (1973", "PSSRB File Nos. 166-02-28332"], ["File No. 5"]),
    "glued_neutral": (["Yaskiel v. The Queen, 2005TCC640."], ["2005 TCC 640", "12005TCC640"]),
    "year_range": (["[1938-39] C.T.C. 138"], ["[1938] C.T.C. 138"]),
    "di_cite": (["Union des Artistes, 50 di 197;"], ["50 dir 197", "50 di"]),
    "cp_pab": (["Resources Development, CP 20466 (PAB)", "CP20748, 2003"], ["CP 12", "XCP 20466"]),
    "citt_number": (["(CITT), AP-2017-052 (CITT)", "NQ-2000-005"], ["AP-2017", "XAP-2017-052"]),
    "wto_ds": (["WT/DS135/AB/R"], ["WT/DX1"]),
}
PARTY = re.compile(r"(?: v\.? | c\. | and )[A-Z]")


def check_patterns():
    for name, (pos, neg) in PATTERN_ASSERTIONS.items():
        rx = re.compile(FAMILIES[name])
        for s in pos:
            assert rx.search(s), "模式 %s 漏正例 %r" % (name, s)
        for s in neg:
            assert not rx.search(s), "模式 %s 误中反例 %r" % (name, s)


def run(court, corpus_dir, limit):
    rx = {k: re.compile(v) for k, v in FAMILIES.items()}
    st = {k: dict(total=0, party=0, missed=0, missed_party=0, docs=0) for k in FAMILIES}
    ex = {k: [] for k in FAMILIES}
    docs = 0
    for batch in pq.ParquetFile(os.path.join(corpus_dir, court + ".parquet")).iter_batches(
            columns=["citation_en", "document_date_en", "unofficial_text_en"]):
        d = batch.to_pydict()
        for date, text in zip(d["document_date_en"], d["unofficial_text_en"]):
            if not text:
                continue
            docs += 1
            if limit and docs > limit:
                return docs, st, ex
            cands = extract.extract_candidates(text, "", extract.decision_year(date), docs, court)[0]
            spans = [(c["match_start_offset"], c["match_end_offset"]) for c in cands]
            for k, r in rx.items():
                hit = False
                for m in r.finditer(text):
                    hit = True
                    s = st[k]
                    s["total"] += 1
                    party = bool(PARTY.search(text[max(0, m.start() - 100):m.start()]))
                    miss = not any(m.start() < e and a < m.end() for a, e in spans)
                    s["party"] += party
                    s["missed"] += miss
                    s["missed_party"] += miss and party
                    if miss and party and len(ex[k]) < 4:
                        ex[k].append(text[max(0, m.start() - 70):m.end() + 15].replace("\n", " "))
                st[k]["docs"] += hit
    return docs, st, ex


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--court", action="append", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--corpus-dir", default=os.path.join(ROOT, "corpus"))
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    check_patterns()
    os.makedirs(a.out, exist_ok=True)
    allres = {}
    for court in a.court:
        docs, st, ex = run(court, a.corpus_dir, a.limit)
        allres[court] = {"docs": docs, "families": st, "examples": ex}
        print("%s docs=%d" % (court, docs))
        print("  %-14s %8s %8s %8s %8s %6s" % ("family", "total", "party", "missed", "miss_pty", "docs"))
        for k, s in st.items():
            if s["total"]:
                print("  %-14s %8d %8d %8d %8d %6d" % (k, s["total"], s["party"], s["missed"],
                                                       s["missed_party"], s["docs"]))
    with open(os.path.join(a.out, "anchor_reconcile.json"), "w", encoding="utf-8") as f:
        json.dump(allres, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
