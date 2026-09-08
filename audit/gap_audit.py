# -*- coding: utf-8 -*-
r"""gap_audit.py — 抽取层缺口审计（审计环工具）

================================ 膜的规则 ================================
本文件属于**审计环**，不属于生产线。

  * 它的产出是**提案**，不是数据：残差聚类供人判断"要不要建第八个形状"，
    不得作为引证行进入任何产出表。
  * **生产线的任何脚本不得读取本工具的输出**（同 PROBLEMS.md 的地位，
    见规格 §4.2）。审计环 → 生产线只允许三样东西过去：确定性形状
    （带正反断言）、PROBLEMS 登记项（带可重放数字）、决策表行
    （带 source / source_locator）。
  * 审计环允许宽网、允许试探性推断；生产线不允许。两边规矩相反，
    混用即失去意义。
==========================================================================

方法
    宽骨架命中 减去 七形状命中（区间重叠）= 残差。
    残差按形态归一（数字→N、罗马数→R）聚类，报每类条数与样例。

    七形状的命中区间**不重跑**，直接读生产产出：
        extracted.csv 并 extracted_superseded.csv = 全部原始命中（规格 7.4）
    因此本工具对照的是生产实际产出的东西，不是另跑一遍的近似。

仪器自检（本工具最重要的一部分）
    宽网若包不住七形状，"残差"这个概念就不成立。故每次运行都计算
    **包住率**：七形状的每一条命中，是否有宽网命中与之区间重叠。

    2026-09-07 实测包住率 **98.81%**（980,795 / 992,641）。
    未包住的 1.19% 主要是：
      - 148 N.Y.S. 2d 284 (1955) 类空格序数（词块不得以数字开头）
      - Edwards 1 July 58 类案名吞噬的垃圾命中（本就非引证）
    **因此残差是下界，低估约 1.2%。引用残差数时必须带这个限定。**

本工具自身的除虫史（三处缺陷全部由自带断言与自检抓出，留档以免重犯）
    1. ABBRISH 曾定义为"以句点结尾"，而 (Mass.) 结尾是右括号
       —— 断言当场拦下；否则会安静给出一个漏掉非序数括注的残差数。
    2. W4 中间词块曾不要求大写首字母，the years 1930 and 1931 被当引证
       —— 占据首轮残差榜首。
    3. 词块字符集曾不含 & 与数字，B. & C.、F.2d、(1 Cranch)
       全部看不见 —— 由包住率 85.9% 暴露，修正后升至 98.81%。

已删除的宽骨架 W5（设计不成立，留档）
    W5 曾为"缩写 + 页码（无卷号）"，目的是发现 Swab. 96 类无卷号
    nominate。实测残差 301,561（48.7%），噪声压倒信号：Art. 12、
    Ltd. 5、No. 3 与 Swab. 96 在结构上不可分辨。
    **结论是方法边界，不是可修的 bug**：无卷号 nominate 无法由结构性
    宽网发现，需要别的发现手段。已登记。

用法
    python audit/gap_audit.py                  # 全量，JSON 到 stdout
    python audit/gap_audit.py --out data/gap_audit.json
    python audit/gap_audit.py --assert-only    # 只跑断言，不扫语料
"""
import argparse
import csv
import json
import os
import re
import sys
from bisect import bisect_left
from collections import defaultdict

import pyarrow.parquet as pq

AUDIT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(AUDIT)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import normalize                                          # noqa: E402

Y = r"(?:1[6-9]|20)\d{2}"
PAGEISH = r"(?:\d{1,5}n?|[ivxlcdm]{1,7})"
# 词块：首字符字母/左括号/&（B. & C.），字符集含数字（F.2d、(1 Cranch)）
WORDISH = r"[A-Za-z(&][A-Za-z0-9.,'’&()\-]*"
# 缩写状词块：**含**句点即可，不要求以句点结尾（(Mass.) 结尾是右括号）
ABBRISH = r"[A-Za-z(&][A-Za-z0-9,'’&()\-]*\.[A-Za-z0-9.,'’&()\-]*"

WIDE = {
    "W1_bracket": re.compile(
        rf"\[\s*{Y}\s*\]\s*(?:\d{{1,4}}\s+)?(?:{WORDISH}\s+){{1,5}}{PAGEISH}"
        rf"(?![A-Za-z0-9])"),
    "W2_paren": re.compile(
        rf"\(\s*{Y}\s*\)\s*,?\s*(?:\d{{1,4}}\s+)?(?:{WORDISH}\s+){{1,5}}{PAGEISH}"
        rf"(?![A-Za-z0-9])"),
    # 卷号 + 词块串（其中至少一个含句点）+ 页码；含句点的要求排除
    # "in 3 of the 5 cases" 类散文
    "W3_vol_abbr_page": re.compile(
        rf"(?<![A-Za-z0-9])\d{{1,4}}\s+(?:{WORDISH}\s+){{0,3}}{ABBRISH}\s+"
        rf"(?:{WORDISH}\s+){{0,2}}{PAGEISH}(?![A-Za-z0-9])"),
    "W4_year_tok_num": re.compile(
        rf"(?<![A-Za-z0-9]){Y}\s+[A-Z][A-Za-z.]{{1,15}}\s+\d{{1,5}}"
        rf"(?![A-Za-z0-9])"),
}

# 正反断言：宽骨架必须命中已登记的真缺口，且不得命中明显非引证。
# 教训同 PROBLEMS #23：测量工具自己必须先被测过。
PATTERN_ASSERTIONS = [
    # 正例：已登记缺口
    ("W1_bracket",       "[1971] S.C.R. x",                  1),  # 单字符罗马页
    ("W1_bracket",       "[2010] J.Q. no 9074",              1),  # 法语 no 编号
    ("W1_bracket",       "[1984] 1 Lloyd's Rep. 555",        1),  # 撇号 reporter
    ("W2_paren",         "(1938) S.C.R. 423",                1),  # 无卷号年份
    ("W2_paren",         "(1874) L.R. 7 E. and I. App. 135", 1),  # 双连接段
    ("W2_paren",         "(1982), 42 C.B.R. (N.S.) 97",      1),  # 非序数括注
    ("W2_paren",         "(1826) 5 B. & C. 125",             1),  # & 词块
    ("W3_vol_abbr_page", "4 Allen (Mass.) 447",              1),
    ("W3_vol_abbr_page", "117 U, S. R. 113",                 1),  # 段内逗号
    ("W3_vol_abbr_page", "15 App. Cas. 210",                 1),
    ("W3_vol_abbr_page", "1 Cr. M. & R. 849",                1),
    ("W3_vol_abbr_page", "600 F.2d 368",                     1),  # 粘连序数
    ("W3_vol_abbr_page", "5 U.S. (1 Cranch) 137",            1),  # 带数字括注
    ("W4_year_tok_num",  "1998 CanLII 13001",                1),
    # 反例：明显非引证
    ("W1_bracket",       "[1971] S.C.R.",                    0),
    ("W2_paren",         "(1938) see below",                 0),
    ("W4_year_tok_num",  "the years 1930 and 1931 together", 0),
    ("W3_vol_abbr_page", "in 3 of the 5 cases considered",   0),
    ("W3_vol_abbr_page", "12 members voted 7 against",       0),
]


def run_assertions():
    bad = []
    for name, sample, want in PATTERN_ASSERTIONS:
        got = len(WIDE[name].findall(sample))
        if (got > 0) != (want > 0):
            bad.append((name, sample, want, got))
    if bad:
        for b in bad:
            print("WIDE-ASSERT FAILED: %s on %r: want %s, got %s" % b,
                  file=sys.stderr)
        sys.exit(1)
    print("宽骨架断言 %d 条全绿" % len(PATTERN_ASSERTIONS), file=sys.stderr)


NORM_D = re.compile(r"\d+")
NORM_R = re.compile(r"(?<![A-Za-z])[ivxlcdm]{1,7}(?![A-Za-z])")


def norm_form(s):
    """形态归一：数字→N，罗马数→R。用于把同构串聚成一类。"""
    return NORM_R.sub("R", NORM_D.sub("N", re.sub(r"\s+", " ", s).strip()))


def load_covered(extracted_dir):
    """读生产产出得到 sdc -> [(start, end, shape_name)]（已排序）。
    kept 并 superseded = 全部原始命中（规格 7.4）。"""
    cov = defaultdict(list)
    for fn in ("extracted.csv", "extracted_superseded.csv"):
        path = os.path.join(extracted_dir, fn)
        if not os.path.exists(path):
            print("缺少生产产出：%s（先跑 pipeline/extract.py）" % path,
                  file=sys.stderr)
            sys.exit(2)
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                cov[r["source_decision_citation"]].append(
                    (int(r["match_start_offset"]),
                     int(r["match_end_offset"]), r["shape_name"]))
    for k in cov:
        cov[k].sort()
    return cov


def overlaps(ivs, starts, s, e):
    """[s,e) 是否与 ivs 中任一区间重叠。ivs 按起点排序，starts 为其起点列表。"""
    j = bisect_left(starts, e) - 1
    guard = 0
    while j >= 0 and guard < 400:
        if ivs[j][0] < e and s < ivs[j][1]:
            return True
        if ivs[j][1] <= s - 200:
            break
        j -= 1
        guard += 1
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="JSON 输出路径（默认 stdout）")
    ap.add_argument("--assert-only", action="store_true",
                    help="只跑断言，不扫语料")
    args = ap.parse_args()

    run_assertions()
    if args.assert_only:
        return

    cov = load_covered(os.path.join(ROOT, "extracted"))
    print("已载入 %d 份判决的命中区间" % len(cov), file=sys.stderr)

    clusters = defaultdict(lambda: {"n": 0, "ex": []})
    per_wide = defaultdict(int)
    per_wide_resid = defaultdict(int)
    shape_hits = shape_cov = 0
    by_shape_total = defaultdict(int)
    by_shape_cov = defaultdict(int)
    uncov_ex = defaultdict(list)

    COLS = ["citation_en", "unofficial_text_en"]
    for court in ("SCC", "ONCA"):
        pf = pq.ParquetFile(os.path.join(ROOT, "corpus", court + ".parquet"))
        for batch in pf.iter_batches(batch_size=500, columns=COLS):
            d = batch.to_pydict()
            for cite, text in zip(d["citation_en"], d["unofficial_text_en"]):
                if not text:
                    continue
                sdc = court + "_" + normalize.nk(cite or "")
                ivs = cov.get(sdc, [])
                starts = [x[0] for x in ivs]
                wide_iv = []
                for wname, rx in WIDE.items():
                    for m in rx.finditer(text):
                        per_wide[wname] += 1
                        wide_iv.append((m.start(), m.end()))
                        if overlaps(ivs, starts, m.start(), m.end()):
                            continue
                        per_wide_resid[wname] += 1
                        c = clusters[(wname, norm_form(m.group(0)))]
                        c["n"] += 1
                        if len(c["ex"]) < 3:
                            a = max(0, m.start() - 30)
                            z = min(len(text), m.end() + 30)
                            c["ex"].append(re.sub(r"\s+", " ", text[a:z]))
                # 仪器自检：宽网是否包住七形状
                wide_iv.sort()
                wstarts = [x[0] for x in wide_iv]
                for s, e, shp in ivs:
                    shape_hits += 1
                    by_shape_total[shp] += 1
                    if overlaps(wide_iv, wstarts, s, e):
                        shape_cov += 1
                        by_shape_cov[shp] += 1
                    elif len(uncov_ex[shp]) < 4:
                        uncov_ex[shp].append(
                            re.sub(r"\s+", " ", text[s:e])[:60])
        print(court, "done", file=sys.stderr)

    out = {
        "_membrane": "审计环产出。提案，非数据。生产线脚本不得读取本文件。",
        "instrument_selfcheck": {
            "七形状命中总数": shape_hits,
            "被宽网包住的": shape_cov,
            "包住率": round(100.0 * shape_cov / shape_hits, 2) if shape_hits else None,
            "说明": "宽网若包不住形状，残差不成立；未包住的部分使残差成为下界",
            "逐形状": {k: {"total": by_shape_total[k], "covered": by_shape_cov[k],
                          "rate": round(100.0 * by_shape_cov[k] / by_shape_total[k], 1)
                                  if by_shape_total[k] else None,
                          "未包住样例": uncov_ex[k]}
                      for k in sorted(by_shape_total)},
        },
        "wide_total": dict(per_wide),
        "wide_residual": dict(per_wide_resid),
        "cluster_count": len(clusters),
        "clusters": sorted(
            [{"wide": k[0], "form": k[1], "n": v["n"], "ex": v["ex"]}
             for k, v in clusters.items()], key=lambda x: -x["n"]),
    }
    js = json.dumps(out, ensure_ascii=False, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(js + "\n")
        print("写入 %s" % args.out, file=sys.stderr)
    else:
        print(js)


if __name__ == "__main__":
    main()
