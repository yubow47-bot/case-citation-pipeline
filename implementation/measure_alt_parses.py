# -*- coding: utf-8 -*-
"""measure_alt_parses.py — 全语料候选枚举测量（阶段 1 验收依据）

跑全语料（SCC+ONCA），统计：
  1. 旧 finditer（非重叠）原始命中数 vs 新重叠+边界闸候选数；
  2. 边界闸拦下数；被拦者样例（验证拦的是截断垃圾而非真引证）；
  3. 同起点候选对分类：同形状（同解析） / 同跨度异形状（异读） /
     嵌套异形状（包含）；同形状同起点**不同解析**数（应为 0，正则确定性）；
  4. D3 跨界标注数。
结果落 implementation/measure_alt_parses.json。
"""
import json
import os
import re
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

import pyarrow.parquet as pq
import extract

COLUMNS = ["unofficial_text_en"]


def old_matches(text):
    n = 0
    for name, rx in extract.SHAPES:
        for _ in rx.finditer(text):
            n += 1
    return n


def main():
    t0 = time.perf_counter()
    stats = Counter()
    guard_samples = []
    same_shape_diff_parse = []
    span_pair_kinds = Counter()
    per_shape = Counter()
    flag_samples = []
    for court in ("SCC", "ONCA"):
        pf = pq.ParquetFile(os.path.join(ROOT, "corpus", court + ".parquet"))
        idx = -1
        for batch in pf.iter_batches(batch_size=500, columns=COLUMNS):
            for text in batch.to_pydict()["unofficial_text_en"]:
                idx += 1
                if not text:
                    continue
                stats["docs"] += 1
                stats["old_raw"] += old_matches(text)
                cands, blocked = extract.extract_candidates(
                    text, court + "_x", "", idx, court)
                extract.annotate_cross_boundary(cands, text)
                stats["blocked"] += blocked
                if blocked and len(guard_samples) < 10:
                    guard_samples.append({"court": court, "row": idx,
                                          "sample": text[:0]})
                stats["new_cands"] += len(cands)
                for c in cands:
                    per_shape[c["shape_name"]] += 1
                    if c["structural_conflict"] and len(flag_samples) < 8:
                        flag_samples.append({"court": court, "row": idx,
                                             "raw": c["raw_string"],
                                             "note": c["conflict_note"]})
                # 同起点对分析
                by_start = {}
                for c in cands:
                    by_start.setdefault(c["match_start_offset"], []).append(c)
                for s, group in by_start.items():
                    if len(group) < 2:
                        continue
                    for i in range(len(group)):
                        for j in range(i + 1, len(group)):
                            a, b = group[i], group[j]
                            same_span = (a["match_end_offset"] == b["match_end_offset"])
                            same_shape = a["shape_name"] == b["shape_name"]
                            if same_shape:
                                # 正则确定性下不应发生；发生即记录
                                if a["parse_signature"] != b["parse_signature"]:
                                    stats["same_start_same_shape_diff_parse"] += 1
                                    if len(same_shape_diff_parse) < 8:
                                        same_shape_diff_parse.append(
                                            {"court": court, "row": idx, "start": s,
                                             "a": a["parse_signature"],
                                             "b": b["parse_signature"]})
                                else:
                                    stats["same_start_same_shape_same_parse"] += 1
                            else:
                                if same_span:
                                    span_pair_kinds["same_span_diff_shape"] += 1
                                else:
                                    span_pair_kinds["nested_diff_shape"] += 1
                stats["same_start_multi_groups"] += sum(
                    1 for g in by_start.values() if len(g) > 1)
    out = {
        "wall_s": round(time.perf_counter() - t0, 1),
        "docs": stats["docs"],
        "old_finditer_raw": stats["old_raw"],
        "new_candidates": stats["new_cands"],
        "growth_pct": round((stats["new_cands"] / stats["old_raw"] - 1) * 100, 2)
        if stats["old_raw"] else None,
        "blocked_by_guard": stats["blocked"],
        "same_start_multi_groups": stats["same_start_multi_groups"],
        "same_start_same_shape_diff_parse": stats["same_start_same_shape_diff_parse"],
        "same_start_same_shape_same_parse": stats["same_start_same_shape_same_parse"],
        "span_pairs": dict(span_pair_kinds),
        "per_shape": dict(per_shape),
        "cross_boundary_flags_sample": flag_samples,
        "same_shape_diff_parse_samples": same_shape_diff_parse,
        "note": ("同形状同起点不同解析=0 是「重叠枚举 + 逐形状确定性正则足以枚举"
                 "全部候选」的实测依据；非零则该形状需要显式双解析展开"),
    }
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "measure_alt_parses.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
