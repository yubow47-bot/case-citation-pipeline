# -*- coding: utf-8 -*-
"""test_shape_21.py — PROBLEMS #21（债 1）兜底形状 shape_paren_year_abbr_page 的回归防线。

用法
    python pipeline/tests/test_shape_21.py

三层断言：
  A. §5.4 的 6 条回归用例（把上次回滚的 bug 变成永久测试；全部走真
     extract_candidates，带句点、带脚注号、带前后散文的**真实排版风格**）；
  B. §6.2 真实原文守卫测试——26 条**逐字取自语料**的段落（2026-09-15 全量
     原型扫描清单与上下文记录，court 标注见各条），覆盖测量的 A（卷号）/
     B（页码）/C（非汇编）三类，断言兜底形状的命中与拒绝逐条符合预期。
     禁合成串作主证据（上次翻车原因，PROBLEMS #21 回滚记录）；
  C. 兜底语义与结构谓词的单元断言（重叠抑制、page==year、单字母段/全大写、
     FALLBACK_SHAPE 名字一致性、双路线行为一致）。

失败即退出码非 0。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.dirname(HERE)
ROOT = os.path.dirname(PIPE)
sys.path.insert(0, PIPE)
sys.path.insert(0, HERE)

import extract                                    # noqa: E402
import shapes                                     # noqa: E402

FB = extract.FALLBACK_SHAPE
FAILED = []
PASSED_N = 0


def check(name, cond, detail=""):
    global PASSED_N
    if cond:
        PASSED_N += 1
    else:
        FAILED.append("%s %s" % (name, detail))


def cands_of(text):
    cands, _ = extract.extract_candidates(text, "SCC_t21", "1990", 1, "SCC")
    return cands


def fb_cands(text):
    return [c for c in cands_of(text) if c["shape_name"] == FB]


def fb_spans(text):
    return [(c["match_start_offset"], c["match_end_offset"]) for c in fb_cands(text)]


def fb_fields(text):
    return [((c["match_start_offset"], c["match_end_offset"]), c.get("year_start"),
             c.get("abbr"), c.get("page"), c.get("serial_marker")) for c in fb_cands(text)]


# ======================================================================
# A. §5.4 六条回归用例
# ======================================================================
# 1. vol 形：新形状不得在此生效；既有解析逐字节保留
t = "(1874), L.R. 9 Ex. 192."
check("A1 新形状不生效", fb_cands(t) == [], repr(fb_fields(t)))
lead = [c for c in cands_of(t) if c["shape_name"] == "shape_leading_abbr"
        and c.get("year_start") == "1874"]
check("A1 既有 leading_abbr(year=1874,vol=9,abbr=Ex.,page=192) 保留",
      [(c["match_start_offset"], c["match_end_offset"], c.get("vol"),
        c.get("abbr"), c.get("page")) for c in lead] == [(0, 22, "9", "Ex.", "192")],
      repr(lead))

# 2. vol 形 + at：同上，且不得被误解析为 page=3
t = "(1868) L.R. 3 Ex. 71, at 74."
check("A2 新形状不生效", fb_cands(t) == [], repr(fb_fields(t)))
lead = [c for c in cands_of(t) if c["shape_name"] == "shape_leading_abbr"
        and c.get("year_start") == "1868"]
check("A2 既有解析 page=71（不是 3）",
      [(c["match_start_offset"], c["match_end_offset"], c.get("page")) for c in lead]
      == [(0, 20, "71")], repr(lead))

# 3. 必须新增：page=222（A.C. 不印卷号），带句点也要命中
t = "(1924) A.C. 222."
check("A3 新增 (1924) A.C. 222", fb_fields(t)
      == [((0, 15), "1924", "A.C.", "222", "")], repr(fb_fields(t)))

# 4. 两条都要命中，且都不越界吞掉对方
t = "(1896) A.C. 359. [20] (1898) A.C. 700."
check("A4 两条分别命中", fb_fields(t)
      == [((0, 15), "1896", "A.C.", "359", ""), ((22, 37), "1898", "A.C.", "700", "")],
      repr(fb_fields(t)))

# 5/6. 必须仍然零命中（非判例）
check("A5 Chapter/Section 零命中", fb_cands("(1926), Chapter 45, and by Section 2") == [])
check("A6 Sup. Ct. Rev. 零命中", fb_cands("(1962), Sup. Ct. Rev. 107.") == [])

# ======================================================================
# B. §6.2 真实原文守卫测试（26 条，逐字取自语料；court 为来源语料）
# ======================================================================
REAL = [
    # ---- B 页码类：必须命中（页码、字段）----
    ("B01", "SCC", "(1892) P. 17.", 1, "P.", "17", ""),
    ("B02", "SCC", "(1900) P. 112.", 1, "P.", "112", ""),
    ("B03", "SCC", "(1924) A.C. 222.", 1, "A.C.", "222", ""),
    ("B04", "SCC", "(1907), A.C. 101, 110.", 1, "A.C.", "101", ""),
    ("B05", "SCC", "(1902) A. C. 220.", 1, "A. C.", "220", ""),
    ("B06", "SCC", "(1923) S.C.R. 414.", 1, "S.C.R.", "414", ""),
    ("B07", "SCC", "(1894) Can. S.C.R. 55.", 1, "Can. S.C.R.", "55", ""),
    ("B08", "SCC", "(1916) W.N. 281.", 1, "W.N.", "281", ""),
    ("B09", "SCC", "(1946) O.R. 837.", 1, "O.R.", "837", ""),
    ("B10", "SCC", "(1951) O.W.N. 635, affirmed on appeal (1953) O.W.N. 197", 2,
     None, None, None),  # 两条都命中（span 见下方专项断言）
    ("B11", "SCC", "(1894) P. 58);", 1, "P.", "58", ""),
    ("B12", "SCC", "(1926) S.C.R. 194", 1, "S.C.R.", "194", ""),
    ("B13", "SCC", "(1942) S.C. 231, at 235.", 1, "S.C.", "231", ""),
    ("B14", "ONCA", "(2008) ONCA 497", 1, "ONCA", "497", ""),
    ("B15", "ONCA", "(2009), ONCA 280, 248 O.A.C. 54", 1, "ONCA", "280", ""),
    ("B16", "ONCA", "(2010) QCCS1052.", 1, "QCCS", "1052", ""),
    ("B17", "ONCA", "(1997), O.J. No 852 (Gen Div.)", 1, "O.J. No", "852", ""),
    ("B18", "ONCA", "(2004) BCJ No. 964 (BCCA)", 1, "BCJ", "964", "No."),
    ("B19", "SCC", "(1948) C.T.C. 195.", 1, "C.T.C.", "195", ""),
    ("B20", "SCC", "(1893) L.R. Probate 5.", 1, "L.R. Probate", "5", ""),
    # ---- A 卷号类：守卫必须拒绝（该数字是卷号，内层由既有形状解析）----
    ("A01", "SCC", "(1874) L.R. 7 E. and I. App. 135.", 0, None, None, None),
    ("A02", "SCC", "(1868) L.R. 1 H.L., Sc. 348, at 350.", 0, None, None, None),
    ("A03", "SCC", "(1937) Q.R. 75 S.C. 123.", 0, None, None, None),
    ("A04", "SCC", "(1886) L.R. 1. H. L. 254.", 0, None, None, None),
    # ---- C 非汇编/非页码：必须零命中 ----
    ("C01", "SCC", "Royal Proclamation (1763), R.S.C. 1985, App. II, No. 1.", 0,
     None, None, None),
    ("C02", "SCC", "(1978), S.M. 1978-79, c. 58", 0, None, None, None),
    ("C03", "ONCA", "(1994), HCJ 5100/94,", 0, None, None, None),
    ("C04", "SCC", "Resolution 276 (1970), I.C.J. Reports 1971, p. 16,", 0,
     None, None, None),
    ("C05", "SCC", "Re Shuker's Estate (1937) All E.R. Volume 3, page 25.", 0,
     None, None, None),
    ("C06", "SCC", "(1926), Chapter 45, and by Section 2", 0, None, None, None),
    ("C07", "SCC", "(1962), Sup. Ct. Rev. 107.", 0, None, None, None),
    ("C08", "SCC", "(1909), Arts 1375", 0, None, None, None),
    ("C09", "SCC", "(1988), Table 4", 0, None, None, None),
]
for tag, court, text, want_n, want_abbr, want_page, want_serial in REAL:
    got = fb_fields(text)
    if want_n == 0:
        check("B/%s 零命中" % tag, got == [], repr(got))
    elif want_abbr is None:                     # 只断条数
        check("B/%s 命中条数=%d" % (tag, want_n), len(got) == want_n, repr(got))
    else:
        check("B/%s 命中" % tag, len(got) == want_n, repr(got))
        if got:
            check("B/%s 字段 abbr=%r page=%r serial=%r" % (tag, want_abbr, want_page, want_serial),
                  got[0][2] == want_abbr and got[0][3] == want_page
                  and got[0][4] == want_serial, repr(got))
# B10 专项：两条 O.W.N. 分别命中（跨度按实际文本核算）
got = fb_fields("(1951) O.W.N. 635, affirmed on appeal (1953) O.W.N. 197")
check("B10 两条 O.W.N. 字段", got == [((0, 17), "1951", "O.W.N.", "635", ""),
                                      ((38, 55), "1953", "O.W.N.", "197", "")],
      repr(got))

# ======================================================================
# C. 兜底语义与结构谓词（单元断言）
# ======================================================================
# C-1 FALLBACK_SHAPE 名字与 shapes.SHAPES 末条一致，且恰在末位
check("C1 兜底形状在 SHAPES 末位且名字一致",
      shapes.SHAPES[-1][0] == FB and len(shapes.SHAPES) == 11,   # v1.6：8 + bracket_range + registered_id + neutral_glued
      "last=%r" % (shapes.SHAPES[-1][0],))

# C-2 兜底形状不碰既有形状已命中的位置：裸中立引用 2011 ONCA 779 由
#     shape_neutral_bare 命中（卷读法 shape_vol_abbr_page 同跨度并存是既有
#     口径，与本次改动无关）；兜底形状在此必须零候选。
t = "…held in R. v. Almrei, 2011 ONCA 779…"
n_neutral = len([c for c in cands_of(t) if c["shape_name"] == "shape_neutral_bare"])
check("C2 裸中立引用不受兜底形状扰动",
      n_neutral >= 1 and fb_cands(t) == [],
      "neutral=%d fb=%r" % (n_neutral, fb_spans(t)))

# C-3 page==year 拒（真实排版：R. v. Big M Drug Mart 的制定法年份位）
check("C3 (1978), S.M. 1978-79 拒", fb_cands("(1978), S.M. 1978-79, c. 58") == [])

# C-4 结构谓词直测（extract._n21_structural_ok）
ok = extract._n21_structural_ok
check("C4 全大写码收", ok("ONCA", "497", "2008") is True)
check("C4 点分单字母段收", ok("S.C.R.", "414", "1923") is True)
check("C4 无单字母段拒（Sup. Ct. Rev.）", ok("Sup. Ct. Rev.", "107", "1962") is False)
check("C4 无句点拒（Chapter）", ok("Chapter", "45", "1926") is False)
check("C4 page==year 拒（S.M.）", ok("S.M.", "1978", "1978") is False)

# C-5 双路线一致：extract_rows（legacy）与 extract_candidates 的兜底抑制结果一致
for text, _tag in [("…Regina v. LaPlante (1958) OWN 80 in which…", "hit"),
                   ("…A.-G. Que. v. Begin (1955) S.C.R. 593 that…", "hit"),
                   ("Royal Proclamation (1763), R.S.C. 1985, App. II, No. 1.", "neg"),
                   ("(1926), Chapter 45, and by Section 2", "neg")]:
    rows = extract.extract_rows(text, "SCC_t21", "1990")
    legacy_fb = [(r["match_start_offset"], r["match_end_offset"])
                 for r in rows if r["shape_name"] == FB]
    check("C5 双路线一致 %r" % text[:24], legacy_fb == fb_spans(text),
          "legacy=%r new=%r" % (legacy_fb, fb_spans(text)))

# C-6 既有形状候选集合不受新形状影响（同文本、去重后逐字节一致）
for text in ["(1874), L.R. 9 Ex. 192.",
             "(1868) L.R. 3 Ex. 71, at 74.",
             "…Kerwin, C.J.C., mentioned in A.-G. Que. v. Begin (1955) S.C.R. 593 that…"]:
    kept, _ = extract.process_text(text, "SCC_t21", "1990")
    old_shapes = [k for k in kept if k["shape_name"] != FB]
    # 重建基线：把兜底形状从 SHAPES 摘掉再跑一遍
    import re as _re
    _saved = extract.SHAPES, extract.SHAPE_ORDER
    extract.SHAPES = [(n, r) for n, r in extract.SHAPES if n != FB]
    extract.SHAPE_ORDER = [n for n, _ in extract.SHAPES]
    kept0, _ = extract.process_text(text, "SCC_t21", "1990")
    extract.SHAPES, extract.SHAPE_ORDER = _saved
    a = [(k["match_start_offset"], k["match_end_offset"], k["shape_name"]) for k in old_shapes]
    b = [(k["match_start_offset"], k["match_end_offset"], k["shape_name"]) for k in kept0]
    check("C6 既有候选不受影响 %r" % text[:24], a == b, "%r vs %r" % (a, b))

# ======================================================================
print("全部通过：%d 条断言" % PASSED_N) if not FAILED else None
for f in FAILED:
    print("FAIL: " + f)
sys.exit(1 if FAILED else 0)
