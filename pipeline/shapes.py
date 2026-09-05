# shapes.py — 正则形状定义（v2，七形状）
# 见技术规格 7.1-7.4
#
# v2 相对 v1 的改动（每条改动的实测依据见规格 §7.2 与 pipeline/tests/）：
#   1. 序数分辨式补 d 后缀、补多位数：_SERIES -> _ORD。
#      v1 的 \d(?:st|nd|rd|th)? 漏 d 且只容单位数，规格 §7.1 自举的示例
#      `83 F. (2d) 212` 在 v1 下是 NO MATCH（实测，见 tests/ 基线）。
#   2. 页码后缀显式捕获（page_suffix 组）。v1 的 (?![A-Za-z]) 遇 `12n`
#      不是拒绝而是回溯截断成 page=1；显式捕获后缀消除静默截断。
#   3. _ABBR 段间分隔 [ .&]+（去掉 \s），不跨换行、不跨句点粘连。
#   4. 形状级分隔 _SEP = \s*,?\s+：卷号与缩写之间等位置容忍逗号
#      （19 世纪排版惯例）。注意与 _ABBR 段内分隔集是两回事，后者
#      明确不收逗号（见规格 §7.2，案名吞噬风险）。
#   5. _ABBR 允许 2-3 字母小写段（法语汇编 R. de J. / C. de D.、
#      英文 H. of L.），且小写段之后必须紧跟大写开头的段。
#
# 形状集结构变化：
#   - 序数括注做成可选插槽 _SERP_SLOT，复用于多个形状；
#     shape_series_paren 因此消失，功能被插槽吸收。
#   - 新增 shape_neutral_bare（2019 SCC 65，无括注的中立引用）与
#     shape_vol_abbr_page（93 E.R. 664，无年份的 卷 缩写 页）。
#
# 排序注意：SHAPE_ORDER 的顺序参与去重的末级决胜（跨度相同、起点相同
# 时取靠前者）。shape_neutral_bare 必须排在 shape_vol_abbr_page 之前，
# 否则 `2019 SCC 65` 会被 vol_abbr_page 抢走、token 语义降级为自由缩写。

_ABBR = (
    r"[A-Z][A-Za-z]*"
    r"(?:[ .&]+[A-Z][A-Za-z]*)*"                      # 段间：仅普通空格/句点/&
    r"(?:[ .&]+[a-z]{2,3}[ .&]+[A-Z][A-Za-z]*)?"      # 可选小写段（of/de），后必大写段
    r"\.?"
)
_YEAR = r"(?:1[6-9]|20)\d{2}"
_SEP = r"\s*,?\s+"                                    # 形状级分隔，容忍一个逗号
_ORD = r"\d+(?:st|nd|rd|th|d)"
_SERP = rf"\(\s*{_ORD}\s*\)"
_SERP_SLOT = rf"(?:{_SEP}{_SERP})?"                   # 序数括注插槽，可复用
_SERIES_OPT = rf"(?:{_SEP}(?P<series>{_ORD}))?"       # 裸序数系列（D.L.R. 4th 300）
_PAGE = r"(?P<page>\d+)(?P<page_suffix>n)?(?![A-Za-z0-9])"

SHAPES = [
    ("shape_bracket",
     rf"\[\s*(?P<year>{_YEAR})\s*\]\s*"
     rf"(?:(?P<vol>\d+){_SEP})?"
     rf"(?P<token>{_ABBR})"
     rf"{_SERIES_OPT}"
     rf"{_SERP_SLOT}"
     rf"{_SEP}{_PAGE}"),

    ("shape_vol_page_year",
     rf"(?P<vol>\d+){_SEP}(?P<abbr>{_ABBR})"
     rf"{_SERIES_OPT}"
     rf"{_SERP_SLOT}"
     rf"{_SEP}{_PAGE}"
     rf"\s*\(\s*(?P<year>{_YEAR})\s*\)"),

    ("shape_year_vol_page",
     rf"\(\s*(?P<year>{_YEAR})\s*\)"
     rf"{_SEP}(?P<vol>\d+){_SEP}(?P<abbr>{_ABBR})"
     rf"{_SERIES_OPT}"
     rf"{_SERP_SLOT}"
     rf"{_SEP}{_PAGE}"),

    ("shape_nominate",
     rf"(?P<vol>\d+){_SEP}(?P<abbr>{_ABBR})"
     rf"{_SEP}\([^)]+\){_SEP}{_PAGE}"
     rf"\s*\(\s*(?P<year>{_YEAR})\s*\)"),

    ("shape_neutral_bare",
     rf"(?P<year>{_YEAR})\s+(?P<token>[A-Z]{{2,6}})"
     rf"(?:{_SEP}(?P<series>[A-Z][A-Za-z]*))?"
     rf"{_SEP}{_PAGE}"),

    ("shape_vol_abbr_page",
     rf"(?P<vol>\d+){_SEP}(?P<abbr>{_ABBR})"
     rf"{_SERIES_OPT}"
     rf"{_SERP_SLOT}"
     rf"{_SEP}{_PAGE}"),

    ("shape_leading_abbr",
     rf"(?P<leading_abbr>{_ABBR})"
     rf"{_SEP}(?P<vol>\d+){_SEP}(?P<abbr>{_ABBR})"
     rf"{_SEP}{_PAGE}"),
]

SHAPE_ORDER = [name for name, _ in SHAPES]
