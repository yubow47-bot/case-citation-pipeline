# normalize.py — 共享纯函数
# 见技术规格 6.1-6.3

import re
from typing import Any


def nk(s: str) -> str:
    """去除全部非字母数字字符，转小写。"""
    return re.sub(r"[^A-Za-z0-9]", "", s).lower()


def normalize_code(code: str) -> str:
    """去除句点、空格、连字符，转大写。"""
    return re.sub(r"[.\s\-]", "", code).upper()


def dedup_overlapping(rows: list, shape_order: list) -> list:
    """同一判决内，区间重叠的匹配只保留跨度最长者。
    跨度相同时按 shape_order 取靠前者。"""
    from collections import defaultdict

    by_decision = defaultdict(list)
    for r in rows:
        by_decision[r["source_decision_citation"]].append(r)

    kept = []
    for _, group in by_decision.items():
        group.sort(key=lambda r: (r["match_start_offset"],
                                  -r["match_span"],
                                  shape_order.index(r["shape_name"])))
        accepted = []
        for r in group:
            if any(r["match_start_offset"] < a["match_end_offset"] and
                   a["match_start_offset"] < r["match_end_offset"]
                   for a in accepted):
                continue
            accepted.append(r)
        kept.extend(accepted)
    return kept
