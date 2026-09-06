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


def dedup_overlapping(rows: list, shape_order: list) -> tuple:
    """同一判决内，区间重叠的匹配只保留跨度最长者。
    主键跨度降序，起点作次键，形状顺序作末键（规格 §7.4 v1.2 订正后的口径；
    旧版以起点升序为主键，会让起点更早的短匹配先占位挤掉更晚的长匹配）。
    v1.3 起去重不删行（规格 §7.4）：返回 (kept, superseded) 二元组——
    kept 按 (起点, 终点) 升序；superseded 每行带 superseded_by（挤掉它的
    kept 行的 (起点, 终点, 形状名) 三元组），供"某行为何不在结果里"追溯
    （约束五）。occurrence/decisions 计数只读 kept。"""
    from collections import defaultdict

    by_decision = defaultdict(list)
    for r in rows:
        by_decision[r["source_decision_citation"]].append(r)

    kept = []
    superseded = []
    for _, group in by_decision.items():
        group.sort(key=lambda r: (-r["match_span"],
                                  r["match_start_offset"],
                                  shape_order.index(r["shape_name"])))
        accepted = []
        for r in group:
            hit = next((a for a in accepted
                        if r["match_start_offset"] < a["match_end_offset"] and
                        a["match_start_offset"] < r["match_end_offset"]), None)
            if hit is None:
                accepted.append(r)
            else:
                r = dict(r)
                r["superseded_by"] = (hit["match_start_offset"],
                                      hit["match_end_offset"],
                                      hit["shape_name"])
                superseded.append(r)
        kept.extend(accepted)
    kept.sort(key=lambda r: (r["match_start_offset"], r["match_end_offset"]))
    return kept, superseded
