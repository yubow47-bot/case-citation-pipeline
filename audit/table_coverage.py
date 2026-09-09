# -*- coding: utf-8 -*-
"""table_coverage.py — 决策表对抽取产出的覆盖率与漏网审计

属于**审计环**（见 audit/README.md）：读生产线产出 + 决策表，产出的是**给人看的数字与
提案**，不喂任何生产脚本。信号往回走，数据不往回走。

它存在的理由（约束九）：PROBLEMS #33 / 规格 §5.2 里引用的覆盖率数字必须能重放，
仪器就必须落地。首版把测量脚本留在临时目录、只把数字写进文档——那等于没量
（该失误登记于 PROBLEMS #34）。

三件事：
  1. 精确命中 / 仅归一命中 / 漏网，按 shape 分别报
     —— 「仅归一命中」独立成一档是核心：规格 §8.2 用 normalize_code 作查表键，
        本档就是该设计在本表上的**净收益与净实害**，不能与精确命中混在一起
  2. 漏网 token 按形态分类（厂商标识 / 抽取噪声 / **疑似真法院代码**）
     —— 第三类是静默假阴性，不报出来就会被当成「落 UNSUPPORTED 是正确行为」
  3. 断言自检（--assert-only）：口径本身先被钉死，再报数字

用法：
    python audit/table_coverage.py --assert-only
    python audit/table_coverage.py
    python audit/table_coverage.py --json data/table_coverage.json
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import normalize                                             # noqa: E402

TABLE = os.path.join(ROOT, "decisions", "neutral_court_codes.csv")
EXTRACTED = os.path.join(ROOT, "data", "extract_out", "extracted.csv")

# 漏网形态分类。顺序即优先级，第一个命中者胜。
# 判据只看 token 自身的印刷形，不查任何表 —— 分类是给人读的提案，不是判定。
VENDOR = re.compile(r"^(?:Carswell|CanLII|CanLIIDocs|WL|DTC|LN[A-Z]*|BNA)", re.I)
COURTISH = re.compile(r"^[A-Z]{2,10}$")          # 全大写字母串：中立代码的印刷形
NOISEWORDS = {"TO", "OR", "OJ", "VJ", "SCR", "APPENDIX", "ONTARIO", "OVERVIEW",
              "CRIMINAL", "SPA"}


def classify_miss(token):
    if VENDOR.match(token):
        return "vendor"
    if token.upper() in NOISEWORDS or not COURTISH.match(token):
        return "noise"
    return "courtish"


ASSERTIONS = [
    ("CarswellOnt", "vendor"), ("CanLII", "vendor"), ("WL", "vendor"),
    ("QCTAQ", "courtish"), ("ONLSHP", "courtish"), ("EWCA", "courtish"),
    ("April", "noise"), ("Agreement", "noise"), ("TO", "noise"), ("OJ", "noise"),
    # 全大写但已知是抽取噪声的，必须落 noise 而不是 courtish
    ("APPENDIX", "noise"), ("ONTARIO", "noise"),
]


def run_assertions():
    bad = [(t, want, classify_miss(t)) for t, want in ASSERTIONS
           if classify_miss(t) != want]
    for t, want, got in bad:
        print("断言失败：%r 应为 %s，实为 %s" % (t, want, got), file=sys.stderr)
    # nk 必须与生产线同口径，否则「仅归一命中」这一档测的不是 §8.2 真会做的事
    assert normalize.normalize_code("F.C.") == "FC"
    assert normalize.normalize_code("S.C.C.") == "SCC"
    print("断言 %d 条：%s" % (len(ASSERTIONS), "全过" if not bad else "%d 条失败" % len(bad)),
          file=sys.stderr)
    return not bad


def load_table():
    rows = list(csv.DictReader(open(TABLE, encoding="utf-8")))
    assert rows, "决策表为空"
    assert all(r["source"] and r["source_locator"] and r["added_date"] for r in rows), \
        "约束八：有行缺 source / source_locator / added_date"
    assert all(r["normalized_key"] == normalize.normalize_code(r["court_code"])
               for r in rows), "normalized_key 与 pipeline/normalize.py 不同口径"
    codes = {r["court_code"] for r in rows}
    assert len(codes) == len(rows), "court_code 重复"
    return codes, {r["normalized_key"] for r in rows}


def load_tokens():
    csv.field_size_limit(10 ** 8)
    by_shape = {}
    with open(EXTRACTED, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            t = (row.get("token") or "").strip()
            if t:
                by_shape.setdefault(row["shape_name"], Counter())[t] += 1
    return by_shape


def report(codes, keys, by_shape):
    out = {"table_rows": len(codes), "shapes": {}}
    for shape in sorted(by_shape):
        dist = by_shape[shape]
        total = sum(dist.values())
        exact = norm_only = 0
        norm_detail, misses = [], []
        for t, n in dist.items():
            if t in codes:
                exact += n
            elif normalize.normalize_code(t) in keys:
                norm_only += n
                norm_detail.append((n, t))
            else:
                misses.append((n, t))
        norm_detail.sort(reverse=True)
        misses.sort(reverse=True)
        buckets = Counter()
        for n, t in misses:
            buckets[classify_miss(t)] += n
        s = {
            "rows": total, "variants": len(dist),
            "exact_hit_rows": exact, "exact_hit_pct": round(100.0 * exact / total, 2),
            "normalized_only_rows": norm_only,
            "normalized_only_detail": [[n, t] for n, t in norm_detail[:30]],
            "miss_rows": total - exact - norm_only,
            "miss_by_kind": dict(buckets),
            "miss_courtish": [[n, t] for n, t in misses if classify_miss(t) == "courtish"],
        }
        out["shapes"][shape] = s
        print("\n== %s ==  %d 行 / %d 变体" % (shape, total, len(dist)))
        print("   精确命中      %7d 行 (%.2f%%)" % (exact, s["exact_hit_pct"]))
        print("   仅归一命中    %7d 行   <- §8.2 归一键的净效应（PROBLEMS #33）" % norm_only)
        if norm_detail:
            print("      " + ", ".join("%s(%d)" % (t, n) for n, t in norm_detail[:12]))
        print("   漏网          %7d 行   厂商 %d / 噪声 %d / **疑似真法院码 %d**"
              % (s["miss_rows"], buckets["vendor"], buckets["noise"], buckets["courtish"]))
        if s["miss_courtish"]:
            print("      疑似真码：" + ", ".join("%s(%d)" % (t, n)
                                              for n, t in s["miss_courtish"][:20]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assert-only", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    ok = run_assertions()
    if a.assert_only:
        sys.exit(0 if ok else 1)
    assert ok, "断言未全过，先修口径再看数字"
    codes, keys = load_table()
    out = report(codes, keys, load_tokens())
    if a.json:
        os.makedirs(os.path.dirname(a.json), exist_ok=True)
        json.dump(out, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\n写入 %s" % a.json)


if __name__ == "__main__":
    main()
