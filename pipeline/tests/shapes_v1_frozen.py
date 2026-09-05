# shapes_v1_frozen.py — v1 形状定义的冻结副本，仅供回归对照（pipeline/tests/）
# 来源：git 719a8b4 (v1.1) 的 pipeline/shapes.py，逐字符照抄，不得在本仓库其他
# 任何地方 import。v1 的正式实现只存在于 git 历史；本文件是测试夹具，不是
# 平行实现。改正则时本文件永不修改——它必须永远是 v1 的原样。

_ABBR = r"[A-Z][A-Za-z]*(?:[\s.&]+[A-Z][A-Za-z]*)*\.?"
_YEAR = r"(?:1[6-9]|20)\d{2}"
_SERIES = r"(?:(?P<series>\d+(?:d|st|nd|rd|th))\s+)?"

SHAPES = [
    ("shape_bracket",
     rf"\[\s*(?P<year>{_YEAR})\s*\]\s*(?:(?P<vol>\d+)\s+)?(?P<token>{_ABBR})\s+"
     rf"{_SERIES}(?P<page>\d+)(?![A-Za-z])"),

    ("shape_vol_page_year",
     rf"(?P<vol>\d+)\s+(?P<abbr>{_ABBR})\s+{_SERIES}(?P<page>\d+)(?![A-Za-z])\s*"
     rf"\(\s*(?P<year>{_YEAR})\s*\)"),

    ("shape_year_vol_page",
     rf"\(\s*(?P<year>{_YEAR})\s*\)\s*,?\s*(?P<vol>\d+)\s+(?P<abbr>{_ABBR})\s+"
     rf"{_SERIES}(?P<page>\d+)(?![A-Za-z])"),

    ("shape_nominate",
     rf"(?P<vol>\d+)\s+(?P<abbr>{_ABBR})\s*\([^)]+\)\s+(?P<page>\d+)\s*"
     rf"\(\s*(?P<year>{_YEAR})\s*\)"),

    ("shape_series_paren",
     rf"(?P<vol>\d+)\s+(?P<abbr>{_ABBR})\s*\(\s*\d(?:st|nd|rd|th)?\s*\)\s+"
     rf"(?P<page>\d+)"),

    ("shape_leading_abbr",
     rf"(?P<leading_abbr>{_ABBR})\s+(?P<vol>\d+)\s+(?P<abbr>{_ABBR})\s+"
     rf"(?P<page>\d+)(?![A-Za-z])"),
]

SHAPE_ORDER = [name for name, _ in SHAPES]
