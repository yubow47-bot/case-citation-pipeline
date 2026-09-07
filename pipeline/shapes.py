# shapes.py — 正则形状定义（v2，七形状；v1.3 订正：分隔符按槽位分配）
# 见技术规格 7.1-7.4
#
# v1.3 槽位订正（实测：两语料 leading_abbr 119,438 次命中中 91,356 次吞名
# 由"前缀→卷号"槽的逗号独家承载，详见 PROBLEMS #18）：
#   分隔符从单一 _SEP 拆为两个，按槽位语义分配——
#     _SEP_COMMA（\s*,?\s+）：年份→卷、缩写→系列/括注/页。逗号出现在年份
#       之后和页码之前（v2 原始证据：(1936), 83 F. 2d 212 / L.R. 5 H. of L., 86）。
#     _SEP_TIGHT（\s+）：前缀→卷、卷→缩写。系列前缀与卷号紧绑定，其间出现
#       逗号即句子边界而非引证内部（R. v. Vu, 2013 SCC 60 的吞名结构）。
#   槽位语义贯穿全部七个形状：凡"卷号→缩写"槽（五个形状）与"前缀→卷"槽
#   （一个形状）一律 _SEP_TIGHT；凡"年份→卷"与"缩写→页向"槽一律 _SEP_COMMA。
#   实测代价：卷→缩写槽收紧损失 69 行（已逐条人审，见 PROBLEMS #18）；
#   收益：neutral_bare 去重后行数 52,092 → 142,433（+90,341 条真引证复活）。
#
# v2 相对 v1 的改动（每条改动的实测依据见规格 §7.2 与 pipeline/tests/）：
#   1. 序数分辨式补 d 后缀、补多位数：_SERIES -> _ORD。
#      v1 的 \d(?:st|nd|rd|th)? 漏 d 且只容单位数，规格 §7.1 自举的示例
#      `83 F. (2d) 212` 在 v1 下是 NO MATCH（实测，见 tests/ 基线）。
#   2. 页码后缀显式捕获（page_suffix 组）。v1 的 (?![A-Za-z]) 遇 `12n`
#      不是拒绝而是回溯截断成 page=1；显式捕获后缀消除静默截断。
#   3. _ABBR 段间分隔 [ .&]+（去掉 \s），不跨换行、不跨句点粘连。
#   4. 形状级分隔容忍逗号（v1.3 起按槽位分配，见上）。
#   5. _ABBR 允许 2-3 字母小写段（法语汇编 R. de J. / C. de D.、
#      英文 H. of L.），且小写段之后必须紧跟大写开头的段。
#
# 形状集结构变化（v2）：
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
_SEP_COMMA = r"\s*,?\s+"                              # 年份→卷；缩写→系列/括注/页
_SEP_TIGHT = r"\s+"                                   # 前缀→卷；卷→缩写
_ORD = r"\d+(?:st|nd|rd|th|d)"
_SERP = rf"\(\s*{_ORD}\s*\)"
_SERP_SLOT = rf"(?:{_SEP_COMMA}{_SERP})?"             # 序数括注插槽，可复用
# 裸序数系列（D.L.R. 4th 300）+ v1.4 粘连变体（F.2d：序数紧贴缩写句点，零空白）。
# 粘连变体要求序数后缀（st/nd/rd/th/d），OCR 粘连页码（Q.B.D.43，无后缀）仍不收——
# 与 PROBLEMS #12 的区分见规格 §7.2。series_glued 为独立捕获组，extract 时并入 series。
_SERIES_OPT = rf"(?:{_SEP_COMMA}(?P<series>{_ORD})|(?P<series_glued>\d{{1,2}}(?:st|nd|rd|th|d)))?"
# 页码：数字（可选字母斜杠前缀 D/、脚注后缀 n）或罗马页码（xi/vii，leave to appeal
# 序册页）。罗马子式 {2} 最小长度挡空串与章节标记 c.；交替整体包在 (?:) 内，
# 防止嵌入 _SEP_COMMA+ _PAGE 时 | 在错误层级分裂。
_PAGE = (r"(?:(?:(?P<page_prefix>[A-Z]{1,2}/))?(?P<page>\d+)(?P<page_suffix>n)?(?![A-Za-z0-9])"
         r"|(?P<page_roman>(?=[ivxlcdm]{2})(?:c[md]|d?c{0,3})(?:xc|xl|l?x{0,3})"
         r"(?:ix|iv|v?i{0,3}))(?![a-z0-9]))")

SHAPES = [
    ("shape_bracket",
     rf"\[\s*(?P<year>{_YEAR})\s*\]\s*"
     rf"(?:(?P<vol>\d+){_SEP_TIGHT})?"                # 卷→token：TIGHT
     rf"(?P<token>{_ABBR})"
     rf"{_SERIES_OPT}"
     rf"{_SERP_SLOT}"
     rf"{_SEP_COMMA}{_PAGE}"),

    ("shape_vol_page_year",
     rf"(?P<vol>\d+){_SEP_TIGHT}(?P<abbr>{_ABBR})"    # 卷→缩写：TIGHT
     rf"{_SERIES_OPT}"
     rf"{_SERP_SLOT}"
     rf"{_SEP_COMMA}{_PAGE}"
     rf"\s*\(\s*(?P<year>{_YEAR})\s*\)"),

    ("shape_year_vol_page",
     rf"\(\s*(?P<year>{_YEAR})\s*\)"
     rf"{_SEP_COMMA}(?:(?P<vol>\d+){_SEP_TIGHT})?(?P<abbr>{_ABBR})"  # v1.4：卷可选（无卷号变体）
     rf"{_SERIES_OPT}"
     rf"{_SERP_SLOT}"
     rf"{_SEP_COMMA}{_PAGE}"
     # 防误解析守卫：页码后紧跟"两个大写词+数字"（如 Ch. App. 127）说明刚才那个
     # "页码"其实是卷号——有卷号形式 (1866) L.R. 1 Ch. App. 127 不得被解析成
     # abbr=L.R. page=1。句点/逗号/分号续接（正文句子）不触发
     rf"(?!\s+[A-Z][A-Za-z.]*\s+[A-Z][A-Za-z.]*\s+\d{{1,5}}(?![0-9A-Za-z.,;]))"),

    ("shape_nominate",
     rf"(?P<vol>\d+){_SEP_TIGHT}(?P<abbr>{_ABBR})"    # 卷→缩写：TIGHT
     rf"{_SEP_COMMA}\([^)]+\){_SEP_COMMA}{_PAGE}"
     rf"\s*\(\s*(?P<year>{_YEAR})\s*\)"),

    ("shape_neutral_bare",
     rf"(?P<year>{_YEAR})\s+(?P<token>[A-Z]{{2,6}})"
     rf"(?:{_SEP_COMMA}(?P<series>[A-Z][A-Za-z]*))?"  # token→分辑词：页向，COMMA
     rf"{_SEP_COMMA}{_PAGE}"),

    ("shape_vol_abbr_page",
     rf"(?P<vol>\d+){_SEP_TIGHT}(?P<abbr>{_ABBR})"    # 卷→缩写：TIGHT
     rf"{_SERIES_OPT}"
     rf"{_SERP_SLOT}"
     rf"{_SEP_COMMA}{_PAGE}"),

    ("shape_leading_abbr",
     rf"(?P<leading_abbr>{_ABBR})"
     rf"{_SEP_TIGHT}(?P<vol>\d+){_SEP_TIGHT}(?P<abbr>{_ABBR})"  # 前缀→卷、卷→缩写：TIGHT
     rf"{_SEP_COMMA}{_PAGE}"),
]

SHAPE_ORDER = [name for name, _ in SHAPES]
