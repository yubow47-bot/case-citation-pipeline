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
     —— v2（2026-09-09）：补「码+分庭词」（EWCA Civ）与「带点码」（E.W.C.A. Civ.）
        两个识别分支，并单列新形态计数；旧口径（纯大写无空格）把这两类全埋进噪声
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
# v2（2026-09-09，PROBLEMS #35 口径订正的依据）：原判据只认「纯大写、无空格」，
# 两类真代码被静默归进噪声——
#   ① 分庭词被吸进 token：[2007] EWCA Civ 588 → "EWCA Civ"（住在 shape_bracket 的
#      _ABBR 槽，neutral_bare 的 token 槽结构上装不下空格/小写）；
#   ② 中立码被印成带点：[2013] E.W.C.A. Civ. 44 → "E.W.C.A. Civ."。
# 分庭词表取英国 Practice Direction 载明的 EWHC/EWCA 分庭缩写闭集
# （Civ/Crim 为 EWCA；Ch/QB/Fam/Comm/Admin/Pat/TCC 为 EWHC 的历史内联形，
# 语料实证仅 Ch；Phase 2 溯源时对照 PD 原文复核）。Rep./Trans 是汇编/笔录
# 系列词、非分庭词，维持噪声档。
# 带点分支在形态层区分不了 E.W.C.A.（法院码）与 S.C.R.（汇编）——故意如此：
# courtish 是提案桶不是判定，汇编同形串的剔除交给三判据分诊
# （audit/neutral_triage.py：卷号率/印刷优势比），不在这层做。
_DIVISION = r"(?:Civ|Crim|Ch|QB|Fam|Comm|Admin|Pat|TCC)"
CODE_DIVISION = re.compile(r"^[A-Z][A-Za-z]{1,10}\s+" + _DIVISION + r"\.?$")
DOTTED_CODE = re.compile(r"^(?:[A-Z]\.)+[A-Z]\.?(?:\s*" + _DIVISION + r"\.?)?$")


def classify_miss(token):
    if VENDOR.match(token):
        return "vendor"
    if token.upper() in NOISEWORDS:
        return "noise"
    if COURTISH.match(token) or CODE_DIVISION.match(token) or DOTTED_CODE.match(token):
        return "courtish"
    return "noise"


ASSERTIONS = [
    ("CarswellOnt", "vendor"), ("CanLII", "vendor"), ("WL", "vendor"),
    ("QCTAQ", "courtish"), ("ONLSHP", "courtish"), ("EWCA", "courtish"),
    ("April", "noise"), ("Agreement", "noise"), ("TO", "noise"), ("OJ", "noise"),
    # 全大写但已知是抽取噪声的，必须落 noise 而不是 courtish
    ("APPENDIX", "noise"), ("ONTARIO", "noise"),
    # v2 两个新识别分支（码+分庭词 / 带点码）；分庭词含 EWHC 历史内联形（Ch 等）
    ("EWCA Civ", "courtish"), ("EWCA Civ.", "courtish"), ("EWCA Crim", "courtish"),
    ("EWHC Ch", "courtish"), ("EWHC Ch.", "courtish"),
    ("E.W.C.A.", "courtish"), ("E.W.C.A. Civ.", "courtish"), ("E.W.C.A. Crim.", "courtish"),
    ("U.K.H.L.", "courtish"), ("L.J. Ch.", "courtish"),
    # 汇编同形串也进提案桶（S.C.R. 是 Supreme Court Reports）——分诊层剔除，
    # 形态层不查表、不做判定
    ("S.C.R.", "courtish"), ("A.C.", "courtish"),
    # 系列词/笔录词不是分庭词；编号词 No（无点）也不是：
    # [2002] OJ No 463 的 "OJ No" 留在噪声，该吸入属抽取层缺陷（登记 PROBLEMS，不在此修）
    ("OJ No", "noise"), ("No.", "noise"), ("OLRB Rep.", "noise"), ("HCA Trans", "noise"),
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
        courtish = [(n, t) for n, t in misses if classify_miss(t) == "courtish"]
        # v2：两个新识别分支的净新增（非纯大写形态），单列计数——
        # 否则带点汇编（S.C.R. 类，~20 万行）会把纯大写境外码（UKHL 类，1,042 行）
        # 在 top-N 显示里彻底淹没，#35 那个静默假阴性就会换个地方再发生一次
        newform = [(n, t) for n, t in courtish if not COURTISH.match(t)]
        s = {
            "rows": total, "variants": len(dist),
            "exact_hit_rows": exact, "exact_hit_pct": round(100.0 * exact / total, 2),
            "normalized_only_rows": norm_only,
            "normalized_only_detail": [[n, t] for n, t in norm_detail[:30]],
            "miss_rows": total - exact - norm_only,
            "miss_by_kind": dict(buckets),
            "miss_courtish": [[n, t] for n, t in courtish],
            "miss_courtish_newform": {"kinds": len(newform),
                                      "rows": sum(n for n, _ in newform)},
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
        if newform:
            print("      其中新形态（码+分庭词/带点码）%d 种 / %d 行"
                  % (len(newform), sum(n for n, _ in newform))
                  + "  <- 纯大写口径之外、v2 分类补回的部分"
                  + "；头部：" + ", ".join("%s(%d)" % (t, n)
                                           for n, t in sorted(newform, reverse=True)[:12]))
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
