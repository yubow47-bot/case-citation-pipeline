# -*- coding: utf-8 -*-
"""traceback.py — 从最终结果回溯原文（阶段 4）

给定运行目录里的候选定位信息（语料行号 + 原文偏移，或 candidate_id），从
**未改动的** corpus parquet 取原文，打印带标记的窗口，并回显该候选的解析、
分类与仲裁状态——「最终表里的一行 → 它在判决原文里的字」的完整通路。

用法
    # 按 candidate_id（mentions_candidates.csv / 台账里的 id）
    python pipeline/traceback.py --run-dir data/run_20260912_stage2 \
        --candidate-id "SCC:701:31220:31241:shape_vol_abbr_page"

    # 按定位四元组
    python pipeline/traceback.py --run-dir data/run_20260912_stage2 \
        --court ONCA --row 8123 --start 4021 --end 4044

    # 按案件名找边/候选再回溯（先粗后细）
    python pipeline/traceback.py --run-dir data/run_20260912_stage2 --search Almrei

窗口 = 原文 [start-160, end+160]，候选跨度以 << … >> 标出。语料只读。
"""
import argparse
import csv
import json
import os
import sys

import pyarrow.parquet as pq

COURTS = tuple(c for c in os.environ.get("PIPELINE_COURTS", "SCC,ONCA,BCCA").split(",") if c)

PIPE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(PIPE)
sys.path.insert(0, PIPE)

COLUMNS = ["unofficial_text_en", "citation_en", "document_date_en"]


def corpus_row(court, row_index):
    pf = pq.ParquetFile(os.path.join(ROOT, "corpus", court + ".parquet"))
    idx = -1
    for batch in pf.iter_batches(batch_size=500, columns=COLUMNS):
        d = batch.to_pydict()
        if row_index - (idx + 1) < len(d["unofficial_text_en"]):
            j = row_index - (idx + 1)
            return (d["citation_en"][j], d["document_date_en"][j],
                    d["unofficial_text_en"][j])
        idx += len(d["unofficial_text_en"])
    raise SystemExit("row %d 超出 %s 语料" % (row_index, court))


def find_candidate(run_dir, court, row, start, end, cand_prefix=None):
    """在候选台账里定位（start/end 为 -1 时按 candidate_id 前缀）。"""
    for court_ in ([court] if court else COURTS):
        path = os.path.join(run_dir, "merge_out", court_, "mentions_candidates.csv")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", newline="") as f:
            for m in csv.DictReader(f):
                if m["corpus_row_index"] != str(row):
                    continue
                if cand_prefix and not m["candidate_id"].startswith(cand_prefix):
                    continue
                if start >= 0 and (m["match_start_offset"] != str(start)
                                   or m["match_end_offset"] != str(end)):
                    continue
                return court_, m
    return None, None


def search_candidates(run_dir, needle):
    """粗搜：mentions 台账里 raw_string / candidate_case_name 含 needle 的前 40 条。"""
    out = []
    for court in COURTS:
        path = os.path.join(run_dir, "merge_out", court, "mentions_candidates.csv")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", newline="") as f:
            for m in csv.DictReader(f):
                if (needle.lower() in m["raw_string"].lower()
                        or needle.lower() in (m.get("candidate_case_name") or "").lower()):
                    out.append((court, m))
                    if len(out) >= 40:
                        return out
    return out


def show(run_dir, court, m):
    row = int(m["corpus_row_index"])
    s, e = int(m["match_start_offset"]), int(m["match_end_offset"])
    cite, date, text = corpus_row(court, row)
    print("== candidate %s (%s)" % (m["candidate_id"], court))
    print("   corpus: %s  row=%d  decision_date=%s" % (cite, row, date))
    print("   raw_string: %r" % m["raw_string"])
    print("   shape=%s  parse_status=%s  arbitration=%s" % (
        m["shape_name"], m.get("parse_status", ""), m["arbitration_status"]))
    if m.get("superseded_by_candidate"):
        print("   superseded_by: %s (%s)" % (m["superseded_by_candidate"],
                                             m.get("arbitration_note", "")))
    if m.get("structural_conflict"):
        print("   structural_conflict: %s (%s)" % (m["structural_conflict"],
                                                   m.get("conflict_note", "")))
    print("   kind=%s  jurisdiction=%s(%s)  merge_key=%s" % (
        m["citation_kind"], m["jurisdiction"], m["jurisdiction_confidence"],
        m["merge_key"]))
    lo, hi = max(0, s - 160), min(len(text), e + 160)
    print("   ---- 原文窗口（<<…>> 为候选跨度；偏移即未改动语料文本的绝对下标）----")
    print("   " + text[lo:s] + "<<" + text[s:e] + ">>" + text[e:hi])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--candidate-id", default="")
    ap.add_argument("--court", default="", choices=("",) + COURTS)
    ap.add_argument("--row", type=int, default=-1)
    ap.add_argument("--start", type=int, default=-1)
    ap.add_argument("--end", type=int, default=-1)
    ap.add_argument("--search", default="")
    a = ap.parse_args()

    if a.search:
        hits = search_candidates(a.run_dir, a.search)
        if not hits:
            raise SystemExit("无命中：%r" % a.search)
        print("粗搜 %d 条（--candidate-id 深查其一）：" % len(hits))
        for court, m in hits[:40]:
            print("  %-4s %-55s  %s" % (court, m["raw_string"][:55],
                                        m["candidate_id"]))
        return
    if a.candidate_id:
        court, _, rest = a.candidate_id.partition(":")
        row = int(rest.split(":")[0])
        c, m = find_candidate(a.run_dir, court, row, -1, -1,
                              cand_prefix=a.candidate_id)
    else:
        c, m = find_candidate(a.run_dir, a.court, a.row, a.start, a.end)
    if m is None:
        raise SystemExit("台账中未找到该候选（run-dir 是否正确？）")
    show(a.run_dir, c, m)


if __name__ == "__main__":
    main()
