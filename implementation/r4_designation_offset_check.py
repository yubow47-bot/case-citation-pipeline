# -*- coding: utf-8 -*-
"""R4 Stage 4 抽检：标注偏移可在**未改动语料原文**回溯（只读）。

从 r4c 的 candidates.csv 取若干带标注的候选，按 court_designation_span 回读原文，
确认 span 内的文字 == court_designation_raw（D1：抽取层只抓原文、不解释）。
"""
import csv
import os
import sys

import pyarrow.parquet as pq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "data/run_20260914_r4c")
csv.field_size_limit(10 ** 8)

want = 6
need = {}
picked = []
with open(os.path.join(RUN, "extract_out", "candidates.csv"),
          encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        if not (r.get("court_designation_raw") or ""):
            continue
        court, row, s, e, _ = r["candidate_id"].split(":", 4)
        need.setdefault(court, set()).add(int(row))
        picked.append((court, int(row), r["court_designation_span"],
                       r["court_designation_raw"], r["shape_name"], r["raw_string"]))
        if len(picked) >= want * 40:
            break

texts = {}
for court, rows in need.items():
    pf = pq.ParquetFile(os.path.join(ROOT, "corpus", court + ".parquet"))
    base = 0
    for batch in pf.iter_batches(batch_size=500, columns=["unofficial_text_en"]):
        col = batch.column(0).to_pylist()
        hit = rows & set(range(base, base + len(col)))
        for i in hit:
            texts[(court, i)] = col[i - base] or ""
        base += len(col)
        rows -= hit
        if not rows:
            break

ok = bad = 0
seen = 0
for court, row, span, raw, shape, rs in picked:
    if span in ("-1:-1", ""):
        continue
    s, e = span.split(":")
    s, e = int(s), int(e)
    txt = texts.get((court, row), "")
    got = txt[s:e]
    seen += 1
    if got == raw:
        ok += 1
        if ok <= 4:
            print("OK  %-5s %-22s span=%s 原文=%r  raw=%r" % (court, shape, span, got, raw))
    else:
        bad += 1
        if bad <= 4:
            print("BAD %-5s %-22s span=%s 原文=%r  raw=%r" % (court, shape, span, got, raw))
    if seen >= 400:
        break
print("抽查 %d 条：偏移回读与 raw 一致 %d / 不一致 %d" % (seen, ok, bad))