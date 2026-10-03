# -*- coding: utf-8 -*-
"""残差挖掘：找出"像引证、但抽取层没覆盖"的字符串，归成模板按频率排序。

只读测量，不改管线、不写 decisions/。对每份判决先跑 extract.extract_candidates
（与生产同一函数），再用两个探测器在原文里找未被任何候选覆盖的片段：
  R1 前缀+编号：`AZ-50234567`、`J.E. 2004-1234`、`WT/DS58`、`CUB 12345` 类
  R2 案名后尾巴：`X v. Y, <到分号/右括号/句号为止的 ≤45 字符>`，含数字才算
模板化：数字串→9，空白折叠。R2 只保留前 3 个词，避免长尾稀释。

用法：
  python audit/residual_mining.py --court TCC --court SST --out audit/findings/residual_20261003
"""
import argparse
import collections
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import pyarrow.parquet as pq  # noqa: E402
import extract  # noqa: E402

R1 = re.compile(
    r"(?<![\w/.-])((?:[A-Z][A-Za-z]{0,9}\.?){1,3}[ -]?\d{1,4}[-/]\d{1,8}(?:[-/]\d{1,6})?)(?![\w])"
    r"|(?<![\w/])(WT/DS\d+)")
PARTY = re.compile(
    r"\b[A-Z][\w'’.\-]+ (?:v\.|c\.) [A-Z][\w'’. \-&]{1,60}?,\s*"
    r"([^\n;()]{3,45}?)(?=[;)\n]|\.\s|\s\()")


def template(s, words=None):
    s = re.sub(r"\d+", "9", re.sub(r"\s+", " ", s.strip()))
    if words:
        s = " ".join(s.split(" ")[:words])
    return s


def covered(spans, a, b):
    return any(a < e and s < b for s, e in spans)


def mine(court, corpus_dir, limit):
    r1, r2 = collections.Counter(), collections.Counter()
    ex1, ex2 = {}, {}
    docs = 0
    for batch in pq.ParquetFile(os.path.join(corpus_dir, court + ".parquet")).iter_batches(
            columns=["citation_en", "document_date_en", "unofficial_text_en"]):
        d = batch.to_pydict()
        for cite, date, text in zip(d["citation_en"], d["document_date_en"],
                                    d["unofficial_text_en"]):
            if not text:
                continue
            docs += 1
            if limit and docs > limit:
                return docs, r1, r2, ex1, ex2
            cands = extract.extract_candidates(text, "", extract.decision_year(date),
                                               docs, court)[0]
            spans = [(c["match_start_offset"], c["match_end_offset"]) for c in cands]
            for m in R1.finditer(text):
                if covered(spans, m.start(), m.end()):
                    continue
                t = template(m.group(0))
                r1[t] += 1
                ex1.setdefault(t, text[max(0, m.start() - 40):m.end() + 20].replace("\n", " "))
            for m in PARTY.finditer(text):
                if covered(spans, m.start(1), m.end(1)) or not re.search(r"\d", m.group(1)):
                    continue
                t = template(m.group(1), 3)
                r2[t] += 1
                ex2.setdefault(t, text[max(0, m.start(1) - 40):m.end(1) + 10].replace("\n", " "))
    return docs, r1, r2, ex1, ex2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--court", action="append", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--corpus-dir", default=os.path.join(ROOT, "corpus"))
    ap.add_argument("--limit", type=int, default=0, help="每法院只扫前 N 份（烟雾测试）")
    ap.add_argument("--top", type=int, default=60)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for court in a.court:
        docs, r1, r2, ex1, ex2 = mine(court, a.corpus_dir, a.limit)
        with open(os.path.join(a.out, court + "_residual.csv"), "w", newline="",
                  encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["detector", "template", "count", "example"])
            for det, c, ex in (("R1", r1, ex1), ("R2", r2, ex2)):
                for t, n in c.most_common(a.top * 5):
                    w.writerow([det, t, n, ex[t]])
        print("%s docs=%d R1 distinct=%d total=%d | R2 distinct=%d total=%d" % (
            court, docs, len(r1), sum(r1.values()), len(r2), sum(r2.values())))
        for det, c, ex in (("R1", r1, ex1), ("R2", r2, ex2)):
            print(" ", det)
            for t, n in c.most_common(15):
                print("   %6d  %-28s %s" % (n, t, ex[t][:90]))


if __name__ == "__main__":
    main()
