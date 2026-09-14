# -*- coding: utf-8 -*-
"""Stage 0 仪器：印刷在完整引证之后的「法院标注」出现频率（只读，可重放）。

测量对象：r3e 产出中，counted 且 citation_kind=reporter 且缩写属于**封闭的
「外国混合汇编」集合**的每一条提及；在其候选**结束偏移**处、对**未改动语料原文**
做零宽正则匹配，抓取紧随其后的一个圆括号标注。

本仪器固化并随 JSON 写出的口径（definitions）：
  * counted citation —— merge_out/<court>/mentions_candidates.csv 中
    arbitration_status == "counted" 且 citation_kind == "reporter" 且
    merge_key 缩写槽 ∈ MIXED（封闭集合，24 个，见下）。
  * foreign mixed reporter —— 上述 MIXED 集合（ac appcas aller wlr kb qb ch chd qbd er
    lr.hl lr.qb lr.ch chapp lr.pc us clr nzlr alr sct led f f2d f3d）。
  * distinct citation —— 不同 merge_key 的个数（键，不是提及）。
  * designation —— 正则 \\s*,?\\s*\\(([^()\\n]{1,30})\\) 以 .match(text, end_offset)
    锚定在候选结束偏移处（中间只允许空白与一个逗号）；语料列 = unofficial_text_en。
  * bucket —— 对标注原文去空格/去点并大写后：
      startswith "HL"            → HL
      startswith "PC"/"JCPC"     → PC
      ∈ {CA, ENGCA, EWCA}        → CA_like
      （复核人变体：另计 startswith "ENGCA"）→ CA_like_startswith
      恰为 4 位年份              → year_only
      其他                       → other
      空标注                     → none
  * keys with both —— 同时带有 HL 与 PC 标注的不同 merge_key 数。

输出：data/coverage_out/court_designation_metric_<tag>.json（口径内嵌）
      data/coverage_out/court_designation_metric_<tag>_detail.csv（每条提及一行）

用法：python implementation/court_designation_metric.py [--run-dir data/run_20260913_r3e]
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

import pyarrow.parquet as pq

csv.field_size_limit(10 ** 8)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COURTS = ("SCC", "ONCA")

# 封闭的「外国混合汇编」集合（D 阶段队列与 Stage 2 语义都以此为界，不临时增删）
MIXED = {"ac", "appcas", "aller", "wlr", "kb", "qb", "ch", "chd", "qbd", "er",
         "lr.hl", "lr.qb", "lr.ch", "chapp", "lr.pc", "us", "clr", "nzlr",
         "alr", "sct", "led", "f", "f2d", "f3d"}

# 候选结束偏移处的标注（零宽锚定；中间只允许空白与一个逗号）
PAREN = re.compile(r"\s*,?\s*\(([^()\n]{1,30})\)")
# 盲区测量：同样锚定、只要求「有一个 (」——用于数出**正则抓不到**的括号标注
# （典型：嵌套括号，如 "(H.L. (Sc.))"，或超长标注 >30 字符）
PAREN_ANY = re.compile(r"\s*,?\s*\(")

DEFINITIONS = {
    "counted_citation":
        "mentions_candidates.csv 行：arbitration_status=counted 且 citation_kind=reporter "
        "且 merge_key 缩写槽 ∈ MIXED",
    "foreign_mixed_reporter": sorted(MIXED),
    "distinct_citation": "不同 merge_key 的个数",
    "designation_regex": PAREN.pattern,
    "designation_anchor": "候选结束偏移（.match(text, end)），语料列 unofficial_text_en",
    "bucket_rules": [
        "t = 去空格/去点并大写后的标注原文",
        "t 以 HL 开头 → HL",
        "t 以 PC 或 JCPC 开头 → PC",
        "t ∈ {CA, ENGCA, EWCA} → CA_like（另计变体：t 以 ENGCA 开头）",
        "标注原文恰为 4 位年份 → year_only",
        "其他非空 → other",
        "空 → none",
    ],
    "keys_with_both": "同时带有 HL 与 PC 标注的不同 merge_key 数",
}


def bucket_of(tag):
    if not tag:
        return "none"
    if re.fullmatch(r"(?:18|19|20)\d{2}", tag):
        return "year_only"
    t = re.sub(r"[\s.]", "", tag).upper()
    if t.startswith("HL"):
        return "HL"
    if t.startswith("PC") or t.startswith("JCPC"):
        return "PC"
    if t in ("CA", "ENGCA", "EWCA"):
        return "CA_like"
    if t.startswith("ENGCA"):
        return "CA_like_startswith"
    return "other"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", default=os.path.join(ROOT, "data",
                                                      "run_20260913_r3e"))
    ap.add_argument("--tag", default=None)
    a = ap.parse_args()
    run = a.run_dir if os.path.isabs(a.run_dir) else os.path.join(ROOT, a.run_dir)
    tag = a.tag or os.path.basename(os.path.normpath(run))

    # 1) 收集需要原文的 (court, row) 与提及清单
    need = defaultdict(set)
    mentions = []
    for court in COURTS:
        p = os.path.join(run, "merge_out", court, "mentions_candidates.csv")
        with open(p, encoding="utf-8", newline="") as f:
            for m in csv.DictReader(f):
                if m.get("arbitration_status") != "counted":
                    continue
                if m.get("citation_kind") != "reporter":
                    continue
                parts = (m.get("merge_key") or "").split("|")
                if len(parts) < 5 or parts[2] not in MIXED:
                    continue
                c, row, s, e, _ = (m.get("candidate_id") or "").split(":", 4)
                if c != court:
                    continue
                row, e = int(row), int(e)
                need[court].add(row)
                mentions.append({"court": court, "row": row, "end": e,
                                 "abbr": parts[2], "merge_key": m["merge_key"],
                                 "candidate_id": m["candidate_id"],
                                 "source_decision_citation":
                                     m.get("source_decision_citation") or ""})

    # 2) 流式取语料原文（列投影；只留需要的行）
    texts = {}
    for court in COURTS:
        rows = need.get(court) or set()
        if not rows:
            continue
        pf = pq.ParquetFile(os.path.join(ROOT, "corpus", court + ".parquet"))
        base = 0
        for batch in pf.iter_batches(batch_size=500,
                                     columns=["unofficial_text_en"]):
            col = batch.column(0).to_pylist()
            hit = rows & set(range(base, base + len(col)))
            for i in hit:
                texts[(court, i)] = col[i - base] or ""
            base += len(col)
            rows -= hit
            if not rows:
                break

    # 3) 逐提及抓标注并分桶
    detail = []
    buckets = Counter()
    keys_by_bucket = defaultdict(set)
    per_abbr = defaultdict(Counter)
    raw_forms = Counter()
    us_with_designation = 0
    us_mentions = 0
    blind = Counter()
    blind_examples = []
    for m in mentions:
        text = texts.get((m["court"], m["row"]), "")
        mt = PAREN.match(text, m["end"])
        raw = mt.group(1).strip() if mt else ""
        if not raw and PAREN_ANY.match(text, m["end"]):
            # 有 "(" 但主正则抓不到：嵌套括号 / 超长标注
            snippet = text[m["end"]:m["end"] + 60].replace("\n", " ")
            blind[snippet.strip()[:50]] += 1
            if len(blind_examples) < 10:
                blind_examples.append({"candidate_id": m["candidate_id"],
                                       "merge_key": m["merge_key"],
                                       "snippet": snippet})
        b = bucket_of(raw)
        buckets[b] += 1
        keys_by_bucket[b].add(m["merge_key"])
        per_abbr[m["abbr"]][b] += 1
        if raw:
            raw_forms[raw] += 1
        if m["abbr"] == "us":
            us_mentions += 1
            if raw:
                us_with_designation += 1
        detail.append(dict(m, raw_designation=raw, bucket=b))
    both = keys_by_bucket["HL"] & keys_by_bucket["PC"]
    ca_like_total = (buckets["CA_like"] + buckets["CA_like_startswith"])

    stats = {
        "run_dir": os.path.relpath(run, ROOT).replace("\\", "/"),
        "definitions": DEFINITIONS,
        "total_counted_mixed_mentions": len(mentions),
        "buckets_mentions": dict(buckets.most_common()),
        "buckets_distinct_keys": {k: len(v) for k, v in
                                  sorted(keys_by_bucket.items())},
        "HL_mentions": buckets["HL"],
        "HL_distinct_keys": len(keys_by_bucket["HL"]),
        "PC_mentions": buckets["PC"],
        "PC_distinct_keys": len(keys_by_bucket["PC"]),
        "keys_with_both_HL_and_PC": len(both),
        "CA_like_mentions": ca_like_total,
        "CA_like_mentions_strict": buckets["CA_like"],
        "CA_like_mentions_startswith": buckets["CA_like_startswith"],
        "year_only_mentions": buckets["year_only"],
        "other_mentions": buckets["other"],
        "none_mentions": buckets["none"],
        "us_mentions": us_mentions,
        "us_mentions_with_designation": us_with_designation,
        "regex_blind_parentheticals": sum(blind.values()),
        "regex_blind_examples": blind_examples,
        "per_abbr_buckets": {k: dict(v.most_common())
                             for k, v in sorted(per_abbr.items())},
        "top_raw_designations": raw_forms.most_common(40),
        "regex_blind_snippets": blind.most_common(10),
    }
    out_json = os.path.join(ROOT, "data", "coverage_out",
                            "court_designation_metric_%s.json" % tag)
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    out_csv = os.path.join(ROOT, "data", "coverage_out",
                           "court_designation_metric_%s_detail.csv" % tag)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["candidate_id", "court", "merge_key",
                                          "abbr", "raw_designation", "bucket",
                                          "source_decision_citation"],
                           extrasaction="ignore")
        w.writeheader()
        for r in sorted(detail, key=lambda x: x["candidate_id"]):
            w.writerow(r)
    print(json.dumps({k: v for k, v in stats.items()
                      if k not in ("definitions", "per_abbr_buckets",
                                   "top_raw_designations")},
                     ensure_ascii=False, indent=1))
    print("written:", os.path.relpath(out_json, ROOT))
    print("written:", os.path.relpath(out_csv, ROOT))


if __name__ == "__main__":
    main()
