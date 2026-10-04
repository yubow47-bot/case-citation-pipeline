# shapes.py — 正则形状定义（v2，七形状；v1.3 订正：分隔符按槽位分配）
# See technical specification §7.1-7.4
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
    # v1.5 #29：字符集加撇号（直/弯两种）。Lloyd's Rep. / Queen's L.J. /
    #   O'M. & H. / Grant's Ch. Rep. 此前整条失配（实测漏抓 1,005 条）。
    r"[A-Z][A-Za-z’']*"
    r"(?:[ .&]+(?!No\.)[A-Z][A-Za-z’']*)*"             # 段间：仅普通空格/句点/&；
    #                                                   v1.4 债1：段起点 (?!No\.) 防编号词
    #                                                   被吸进缩写（O.J. No. 3423 的
    #                                                   token 污染）。唯一字面量例外，
    #                                                   门槛见 §7.2 专节/PROBLEMS #23
    r"(?:[ .&]+[a-z]{2,3}[ .&]+[A-Z][A-Za-z]*)?"      # 可选小写段（of/de），后必大写段
    r"\.?"
)
_YEAR = r"(?:1[6-9]|20)\d{2}"
_SEP_COMMA = r"\s*,?\s+"                              # 年份→卷；缩写→系列/括注/页
_SEP_TIGHT = r"\s+"                                   # 前缀→卷；卷→缩写
_ORD = r"\d+(?:st|nd|rd|th|d)"
# 2026-09 demo 修复 D4：括注序数系列必须捕获。此前 _SERP 匹配 (2d)/(3d) 却不捕获，
#   47 D.L.R. (2d) 400 与 47 D.L.R. (3d) 400 得到同一个归并键。只加捕获组、不改匹配
#   集合（加组不改变任何命中的起止与分支选择），但字段集合变了，属 schema 变更（candidates-2.0）。
_SERP = rf"\(\s*(?P<series_paren>{_ORD})\s*\)"
# v1.5 #11：非序数括注（(Mass.)/(N.S.)/(H.L.)/(U.S.)/(Q.B.) 等法院、法域、
#   分辑标注）。**紧口径**：大写开头、不含数字、长度受限——与 §7.2（五）1
#   否决的对象不是同一个东西：那条否的是把 shape_nominate 的 \([^)]+\)（任意
#   非右括号内容）塞进通用插槽、从而丢掉它的尾随年份闸门；本式不含数字、有
#   长度上限，与 _SERP 互斥，且实测零破坏。
#   D4 同批：非序数括注也捕获（paren_note）。(N.S.) 是「新系列」，与无括注的同名汇编
#   不是一本书，不能当序数清掉，也不能丢。
_NONORD = r"\(\s*(?P<paren_note>[A-Z][A-Za-z. ]{0,8})\s*\)"
_SERP_SLOT = rf"(?:{_SEP_COMMA}(?:{_SERP}|{_NONORD}))?"   # 括注插槽（序数或非序数）
# 裸序数系列（D.L.R. 4th 300）+ v1.4 粘连变体（F.2d：序数紧贴缩写句点，零空白）。
# 粘连变体要求序数后缀（st/nd/rd/th/d），OCR 粘连页码（Q.B.D.43，无后缀）仍不收——
# 与 PROBLEMS #12 的区分见规格 §7.2。series_glued 为独立捕获组，extract 时并入 series。
_SERIES_OPT = rf"(?:{_SEP_COMMA}(?P<series>{_ORD})|(?P<series_glued>\d{{1,2}}(?:st|nd|rd|th|d)))?"
# v1.4 封版前审计：编号标记槽提为共享子式——(?!No.) 边界的批准条件是"信息重定位"，
# 重定位需要接收槽；守卫在共享 _ABBR 里而槽只在 bracket = 七分之一兑现，其余六个形状
# 是纯排除。作用域必须一致（PROBLEMS #23 补记）
# v1.5 #28：法语编号体例 no（小写、无句点，Jurisprudence Québec 的
#   [2010] J.Q. no 9074）。这是 _ABBR 字面量例外的**第二个成员**，按 §7.2（六）
#   的闸门：自带槽（serial_marker，已存在）+ 自带 #16 测量（三门全过）+
#   信息重定位证明（no 从 token 移入 serial_marker，零丢弃）——三条齐备。
#   **不加 (?![A-Za-z]) 尾部守卫**：全语料实测该守卫零作用（north/nothing 类
#   已由其后的 _SEP_COMMA + _PAGE 结构性拒绝——"no" 后必须是空白加数字）。
#   加了就是"看着在防什么、实际从不执行"的代码，同 §7.3 对 year_raw.split("-")
#   的告诫；v1.5 自检时按同一标准删除（原带守卫版与本版全语料命中集合逐位相同）。
_SERIAL_SLOT = r"(?:\s+(?P<serial_marker>No\.|no))?"
# R4（D1）：**法院标注**零宽捕获——印刷在完整引证（页码或页码后缀、或已消费的
#   尾部年份括注）之后的圆括号标注，如 "[1932] A.C. 562 (H.L.)"、
#   "42 C.C.C. (3d) 1 (1997) (P.C.)"。与 neutral_bare 的 trailing_paren 同一技术
#   （零宽前瞻捕获，(start,end,shape) 跨度集合逐字节不变）但**独立捕获组、独立字段**，
#   不复用 trailing_paren。
#   边界（D1）：标注与页码之间只允许空白与一个逗号（\s*,?\s*）；内容不含换行/圆括号、
#   长度 1–30。**排除纯序数系列**（(4th)/(2d) 类）——那是下一条引证的系列槽，
#   不属于本引证（负测试钉住）。年份括注**不排除**：捕获后由 classify 判 not_a_court
#   （负测试 "(1932) → not a court" 的对象）。含义只来自 court_designations.csv 的
#   精确匹配（D1：抽取层不解释）。
_CDES = (r"(?:(?=\s*,?\s*\((?!\s*\d+\s*(?:st|nd|rd|th|d)\s*\))"
         r"(?P<court_designation>[^()\n]{1,30})\)))?")
# 页码：数字（可选字母斜杠前缀 D/、脚注后缀 n）或罗马页码（xi/vii，leave to appeal
# 序册页）。罗马子式 {2} 最小长度挡空串与章节标记 c.；交替整体包在 (?:) 内，
# 防止嵌入 _SEP_COMMA+ _PAGE 时 | 在错误层级分裂。
_PAGE = (r"(?:(?:(?P<page_prefix>[A-Z]{1,2}/))?(?P<page>\d+)(?P<page_suffix>n)?(?![A-Za-z0-9])"
         r"|(?P<page_roman>(?=[ivxlcdm]{2})(?:c[md]|d?c{0,3})(?:xc|xl|l?x{0,3})"
         r"(?:ix|iv|v?i{0,3})(?![a-z0-9])"
         # v1.5 #30：单字符罗马页（[1983] 2 S.C.R. v 类序册页）。仅收 i/v/x——
         #   c 是章节标记（R.S.C., c. 11）、d/m 语料内无实例；尾部排句点以剔
         #   v.（versus）。**守卫只加在本分支**：首版把句点排除加到公共尾部，
         #   毁掉了 [1991] 1 S.C.R. xiii. 类 396 条已有正确捕获（门 1 抓出）。
         r"|[ivx](?![A-Za-z0-9.])))")
# #21 兜底形状的中段段式（见 SHAPES 末条的注释）：段 ≤8 字符、段间必有句点、
#   末段可带尾点；段起点 (?!No\.|no) 与七形状的 (?!No\.) 同款（编号词进
#   serial_marker 槽，不进缩写）。
_N21_SEG = r"[A-Z][A-Za-z]{0,7}"

SHAPES = [
    ("shape_bracket",
     rf"\[\s*(?P<year>{_YEAR})\s*\]\s*"
     rf"(?:(?P<vol>\d+){_SEP_TIGHT})?"
     rf"(?P<token>{_ABBR})"
     rf"{_SERIAL_SLOT}"                                # v1.4 债1：编号标记槽（共享子式）
     rf"{_SERIES_OPT}"
     rf"{_SERP_SLOT}"
     rf"{_SEP_COMMA}{_PAGE}"
     rf"{_CDES}"),                                     # R4：法院标注（零宽）

    ("shape_vol_page_year",
     rf"(?P<vol>\d+){_SEP_TIGHT}(?P<abbr>{_ABBR})"
     rf"{_SERIAL_SLOT}"                                # 编号标记槽（共享）
     rf"{_SERIES_OPT}"
     rf"{_SERP_SLOT}"
     rf"{_SEP_COMMA}{_PAGE}"
     rf"\s*\(\s*(?P<year>{_YEAR})\s*\)"
     rf"{_CDES}"),                                     # R4：年份括注已消费→标注取下一个（零宽）

    ("shape_year_vol_page",
     rf"\(\s*(?P<year>{_YEAR})\s*\)"
     rf"{_SEP_COMMA}(?P<vol>\d+){_SEP_TIGHT}(?P<abbr>{_ABBR})"  # v1.4 修3 卷可选已回滚（PROBLEMS #21）
     rf"{_SERIAL_SLOT}"                                # 编号标记槽（共享）
     rf"{_SERIES_OPT}"
     rf"{_SERP_SLOT}"
     rf"{_SEP_COMMA}{_PAGE}"
     rf"{_CDES}"),                                     # R4：法院标注（零宽）

    ("shape_nominate",
     rf"(?P<vol>\d+){_SEP_TIGHT}(?P<abbr>{_ABBR})"
     rf"{_SERIAL_SLOT}"                                # 编号标记槽（共享）
     rf"{_SEP_COMMA}\((?P<paren_note>[^)]+)\){_SEP_COMMA}{_PAGE}"   # D4：括注捕获
     rf"\s*\(\s*(?P<year>{_YEAR})\s*\)"
     rf"{_CDES}"),                                     # R4：年份括注已消费→标注取下一个（零宽）

    ("shape_neutral_bare",
     # v1.4：token 2-12 位（大写开头无空格纯字母段）。上界依据=观测到的最长
     # 标识符+余量：法院代码最长 7 位（FPSLREB/CRTESPF），vendor 最长 11 位
     # （CarswellOnt/Que）。不判断合法性（约束二），归 neutral_court_codes.csv
     rf"(?P<year>{_YEAR})\s+(?P<token>[A-Z][A-Za-z]{{1,11}})"
     rf"(?:{_SEP_COMMA}(?P<series>[A-Z][A-Za-z]*))?"  # token→分辑词：页向，COMMA
     rf"{_SEP_COMMA}{_PAGE}"
     # R2F：尾括注可选零宽前瞻捕获（identifier 引证常尾随法院/数据库括注，
     # 如 "2001 CanLII 24079 (ON CA)"）。零宽 → (start,end,shape) 跨度集合
     # 与旧版逐字节一致（测试 j 钉住）；捕获内容仅供 classify 细分用。
     rf"(?:(?=\s*\((?P<trailing_paren>[^)\n]{{1,25}})\)))?"),

    ("shape_vol_abbr_page",
     rf"(?P<vol>\d+){_SEP_TIGHT}(?P<abbr>{_ABBR})"
     rf"{_SERIAL_SLOT}"                                # 编号标记槽（共享）
     rf"{_SERIES_OPT}"
     rf"{_SERP_SLOT}"
     rf"{_SEP_COMMA}{_PAGE}"
     rf"{_CDES}"),                                     # R4：法院标注（零宽）

    ("shape_leading_abbr",
     rf"(?:\(\s*(?P<year>{_YEAR})\s*\){_SEP_COMMA})?"  # v1.4 改动一：年份前缀槽
     #                                                   （(1866) L.R. 2 Ch. App. 127 类，
     #                                                   年份印在紧邻位置，此前被丢弃）
     rf"(?P<leading_abbr>{_ABBR})"
     rf"{_SEP_TIGHT}(?P<vol>\d+){_SEP_TIGHT}(?P<abbr>{_ABBR})"
     rf"{_SERIAL_SLOT}"                                # 编号标记槽（共享）
     rf"{_SEP_COMMA}{_PAGE}"
     rf"{_CDES}"),                                     # R4：法院标注（零宽）

    # ---------------------------------------------------------------- #21（债 1）
    # 兜底形状：shape_paren_year_abbr_page —— (年) 缩写 页，无卷号圆括号年份
    # （(1924) A.C. 222. / (1892) P. 17. / (1951) O.W.N. 635）。PROBLEMS #21。
    # 兜底语义（#16 规矩 §5.1）：**只允许在七个既有形状都不命中的位置生效**
    # ——重叠抑制在 extract 层做（extract._apply_fallback_semantics），
    # 新候选与既有候选结构上不可能共存，从根上拔掉「新匹配挤掉正确匹配」
    # （上次回滚的病因，见 PROBLEMS #21 回滚记录）。
    # 结构判据（§5.3，无词表；行级结构谓词在 extract 层）：
    #   * 中段各段 ≤8 字符、≤4 段，段间必须有句点、末段可带尾点——Chapter/
    #     Section/Study Paper/Working Paper 无句点或段超长，结构上不中；
    #   * 点分形必须含**单字母段**（S.C.R. 的 S/C/R；Sup. Ct. Rev. / App. Cas. /
    #     Sel. Ca. / Crim. L. Rev.(?) 无单字母段——期刊与旧名义报告人被结构排除）
    #     或整段 2-8 位全大写（SCC/ONCA/QCCS 类中立代码）；
    #   * page == year 拒（(1978), S.M. 1978 类制定法年份位）。
    # vol 守卫（§5.2，全部按真实排版测，禁合成串；上次回滚的教训）：
    #   * 页码后拒绝「缩写词（含 ≤3 字母小写连接词 and/of/the、含逗号续接，
    #     至多 3 词）+ 数字/罗马」——即该数字是卷号不是页码：
    #     (1874), L.R. 9 Ex. 192 / (1868) L.R. 1 H.L., Sc. 348 /
    #     (1874) L.R. 7 E. and I. App. 135 / (1763), R.S.C. 1985, App. II；
    #   * 页码后跟 p./page 续接（(1970), I.C.J. Reports 1971, p. 16）或斜杠
    #     续接（(1994), HCJ 5100/94 流水号）——这串数字不是页码。
    # 罗马续接必须大小写都收（App. II 是大写——首版只写 [ivxlcdm] 被全量
    # 原型当场抓出）。
    ("shape_paren_year_abbr_page",
     rf"\(\s*(?P<year>{_YEAR})\s*\)"
     rf"[\s,]{{0,3}}(?!(?:No\.|no))"
     rf"(?P<abbr>{_N21_SEG}(?:[\s.]*[.][\s.]*(?!No\.|no){_N21_SEG}){{0,3}}[.]?)"
     rf"{_SERIAL_SLOT}"                                # 编号标记槽（共享子式，与七形状同款）
     rf"[\s,]{{0,3}}{_PAGE}"
     rf"(?![ \t,;.]*(?:{_N21_SEG}"
     rf"(?:[ \t,;.]*(?:[a-z'’]{{1,3}}[ \t,;.]*)?{_N21_SEG}){{0,2}}"
     rf"[ \t,;.]*(?:\d{{1,4}}|[IVXLCDMivxlcdm]{{2,}})))"
     rf"(?![ \t,;]*p\.\s*\d)"
     rf"(?![ \t,;]*page\b)"
     rf"(?![ \t,;]*/[ \t]?\d)"),
]

# ------------------------------------------------------------ v1.6 表驱动形状
# 2026-10-03（PROBLEMS #107）：四个边缘法庭（TCC/SST/FPSLREB/CITT）残差挖掘暴露
# 「前缀+编号」型标识（联邦案卷号 A-675-94、CP 20466、PSSRB File No. 168-02-37、
# WT/DS135、魁北克 AZ-…）对七形状不可见，粘连中立引证 2005TCC640 同。两个新形状：
#   shape_registered_id  正则由 decisions/id_prefixes.csv 生成——新增前缀只加行。
#                        第一层「登记即抽」，不判断真引用/页眉/审理去向（后续层的事）。
#                        字段复用：token=规范前缀，page=编号体（连字符归一），无年份。
#   shape_neutral_glued  年份+法院码+序号无空格粘连（2005TCC640），法院码取自
#                        neutral_court_codes.csv，故 2005ABC1 类随机串不会中。
#                        字段与 neutral_bare 同构，下游按 neutral 处理。
# 二者插在兜底形状之前（兜底恒在末位，test_shape_21 钉住）。未登记的
# GD2-11（SST 证据页码）/Exhibit PR-…（证物号）不在表里，故结构上不会被抽到。
import csv as _csv
import os as _os

_DECISIONS = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                           "decisions")
_HYPHENS = "‐‑‒–"


def load_id_prefix_rows():
    path = _os.path.join(_DECISIONS, "id_prefixes.csv")
    if not _os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return [r for r in _csv.DictReader(f) if (r.get("prefix_id") or "").strip()]


ID_PREFIX_ROWS = load_id_prefix_rows()


def _registered_id_regex(rows):
    alts = ["(?P<rid%d>(?P<rtok%d>%s)(?P<rbody%d>%s))"
            % (i, i, r["prefix_regex"], i, r["body_regex"]) for i, r in enumerate(rows)]
    return r"(?<![\w-])(?:" + "|".join(alts) + r")(?![\w-])"


def _glued_neutral_regex():
    path = _os.path.join(_DECISIONS, "neutral_court_codes.csv")
    if not _os.path.exists(path):
        return None
    with open(path, encoding="utf-8", newline="") as f:
        codes = {(r.get("court_code") or "").strip() for r in _csv.DictReader(f)}
    codes = sorted((c for c in codes if c.isalpha() and c.isupper() and len(c) >= 2),
                   key=lambda c: (-len(c), c))
    if not codes:
        return None
    return (rf"(?<![A-Za-z0-9])(?P<year>{_YEAR})(?P<token>{'|'.join(codes)})"
            rf"(?P<page>\d{{1,6}})(?![A-Za-z0-9])")


def resolve_registered_id(groupdict):
    """shape_registered_id 的捕获组归一：把 rtokN/rbodyN 解析为 token/page。
    其他形状原样返回。返回新字典，不改入参。"""
    if "rid0" not in groupdict and not any(k.startswith("rid") for k in groupdict):
        return groupdict
    g = dict(groupdict)
    for i, r in enumerate(ID_PREFIX_ROWS):
        tok = g.get("rtok%d" % i)
        if tok is None:
            continue
        canon = (r.get("canonical_token") or "").replace("{prefix}", tok.upper())
        body = (g.get("rbody%d" % i) or "")
        body = body.replace("�C", "-")
        for h in _HYPHENS:
            body = body.replace(h, "-")
        g["token"] = canon
        g["page"] = body.strip().lstrip("-").strip()
        g["rid_row"] = r["prefix_id"]
        break
    return g


# [1938-39] C.T.C. 138：年份区间括注（15 处，TCC/CITT/FPSLREB）。复制 shape_bracket 的
# 全部后段，只换年份头；year 组只取起始年（与 year_start 恒等 year_raw 的口径一致）。
_BRACKET_HEAD = rf"\[\s*(?P<year>{_YEAR})\s*\]\s*"
_BRACKET_RANGE_HEAD = rf"\[\s*(?P<year>{_YEAR})\s*[-‐-–]\s*(?:{_YEAR}|\d{{2}})\s*\]\s*"
_bracket_rx = dict(SHAPES)["shape_bracket"]
assert _bracket_rx.startswith(_BRACKET_HEAD)
_EXTRA = [("shape_bracket_range", _BRACKET_RANGE_HEAD + _bracket_rx[len(_BRACKET_HEAD):])]
if ID_PREFIX_ROWS:
    _EXTRA.append(("shape_registered_id", _registered_id_regex(ID_PREFIX_ROWS)))
_glued = _glued_neutral_regex()
if _glued:
    _EXTRA.append(("shape_neutral_glued", _glued))
SHAPES = SHAPES[:-1] + _EXTRA + SHAPES[-1:]

SHAPE_ORDER = [name for name, _ in SHAPES]
