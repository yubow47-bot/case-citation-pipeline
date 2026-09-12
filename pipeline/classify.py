# -*- coding: utf-8 -*-
"""classify.py — 分类层（规格 §8）

逐行独立判定：确定 citation_kind 与 abbreviation、剔除非案例引证、查表定法域、
同形异义消歧、切分案名候选。**不读其他行，不做跨行统计**（那是归并层）。

用法
    python pipeline/classify.py --court SCC  --input data/extract_out/extracted.csv --output data/classify_out/SCC
    python pipeline/classify.py --court ONCA --input data/extract_out/extracted.csv --output data/classify_out/ONCA

输出
    <output>/classified.csv   抽取层全部字段 + §8.9 的十个新列
    <output>/manifest.json    参数、决策表行数、各档计数（约束九：数字须可重放）

不删行（约束五）：任何拒绝都只写 rejected_reason / name_rejected_reason 两个
字段之一，行本身照常输出并填满其余字段。

实现决定（规格未写明或留待裁决，均已实测）。下列三处之外，#41 同档才算冲突、
#43 段落编号残尾、#45 平行引证尾巴三处的说明就近写在代码注释里：
  1. §8.2 首行 normalize_code 的裁决（PROBLEMS #33）——加结构闸：仅当本行
     无卷号（中立引用的结构签名）时才启用归一键退路；有卷号一律只精确匹配。
     实测：挡掉 2,382 行带卷号的汇编误命中（F.C. 2,358 等），保住无卷号的
     带点真中立引用。归一命中一律记 lookup_mode=normalized，按 §8.5 的原则
     不与精确命中混同。
  2. §8.4 两条正则的作用域，规格只写 s 未定义。实测：只看 raw_string 时
     两条规则命中数均为 0（死代码，正是 §7.3 警告的模式）。故 FED_STATUTE
     作用于 preceding_text + raw_string；PARTY_INITIALS 采精确口径——
     要求前文正好以 R. v. 结尾**且**本行 raw 以 X.Y. 起头（实测 92 行）。
     宽口径「前文任意位置出现 R. v. A.B.」命中 15,999 行，会把大量真引证
     误杀，正踩 §8.8 警告的「引用次数被系统性低估」。
  3. §8 无 shape_neutral_bare 的专节。其 token 结构上即裸代码，按 §8.2 的
     两表并查逻辑类推处理（两表都命中→table_conflict 交人裁），理由与 §8.2
     所述相同：中立码表可立即填满而 reporter 表长期为空，设优先级等于让
     填表进度决定判定结果。此处为**补充规格的实现决定**，须人复核。
  4. §8.3 修订（PROBLEMS #52，经人批准「实际正确就消歧」）：认得的系列前缀若带
     法域，参与同形异义消歧——Q.R. 56 K.B. 520 的 Q.R. 已印明是魁北克的系列。
  5. §8.6 修订（#52）：无卷号的行按「不印卷号」这一印刷事实参与区间比对并标
     vol_missing（原代码块一律不判，补充规则只凭年份——都丢了信息）；同一法域可有
     多段区间（Q.B. 英国有四个互不相接的系列）。消歧结果的成色不高于表行本身。
  6. §8.7 修订（PROBLEMS #58）：原式只以 v. 为案名的唯一结构锚，`Re X`、`Reference
     re X`、`In re X`、`Ex parte X`、`X (Re)`、魁北克匿名名（`Droit de la famille — N`、
     `LSJPA — N`）一律切不出。补一条**只在段首/段尾认闭集标记**的规则（见下方常量），
     且只在「本行引证所在那一段内没有 v.」时启用。标记是结构，不是词表枚举案名——
     约束二禁的是抽取层用固定缩写清单决定收不收，此处是清洗层的结构判据。须人复核。
  7. §8.7 修订（PROBLEMS #61）：候选把左侧整句散文吞进来时切掉散文（`_trim_prose_left`，
     见下方常量与注记）。**切不动就原样退回，不判无名**——这是对「切完不像案名就丢弃」
     那一版的收紧，理由是实测丢弃档会丢掉真案名（`Union des employés de commerce,
     local 503 v. Roy`）。须人复核。
"""
import argparse
import csv
import datetime
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import nk, normalize_code                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _relpath(p):
    """manifest 里记输入路径。跨盘符时（测试临时目录在 C:、仓库在 D:）relpath 会抛
    ValueError——而 manifest 写在数据文件之后，首版就这样留下有数据、无 manifest 的
    半成品输出（迷你全链首跑抓到）。退回绝对路径。"""
    try:
        return os.path.relpath(p, ROOT).replace("\\", "/")
    except ValueError:
        return os.path.abspath(p).replace("\\", "/")


DECISIONS = os.path.join(ROOT, "decisions")

NEW_COLUMNS = ["citation_kind", "abbreviation", "jurisdiction",
               "jurisdiction_confidence", "lookup_mode", "vol_missing",
               "series_prefix", "candidate_case_name",
               "rejected_reason", "name_rejected_reason", "disambiguated_by",
               "self_citation"]

# ---------------------------------------------------------------- §8.4 Step 2
FED_STATUTE = re.compile(r"(?:^|[\s(\[])(?:R\.S\.C\.|S\.C\.)\s*(?:18|19|20)\d{2}")
CHAPTER = re.compile(r"\bc\.\s*(?:[A-Z]|\d)")
PARTY_TAIL = re.compile(r"\bR\.\s*v\.\s*$")        # 前文正好以 R. v. 结尾
PARTY_HEAD = re.compile(r"^[A-Z]\.\s*[A-Z]\.")     # 本行 raw 以缩写型姓名起头

# ---------------------------------------------------------------- §8.7 Step 5
V_RE = re.compile(r"\bv\.?(?=\s)")
_ADMIT_LEAD_CHARS = set("[(«\"'‘“….")
_ADMIT_VERB_RE = re.compile(
    r"(?:citing|see also|see|per|applied|considered|referred to|"
    r"following|approving|distinguished|overruled|cf)\s+", re.IGNORECASE)
_ADMIT_IN_RE = re.compile(r"in\s+(?!re\s)", re.IGNORECASE)
# PROBLEMS #57：分号后以这些词起头，是**同一案子**的上诉沿革（R. v. Grover (1990), 56 C.C.C.
#   (3d) 532 (Ont. C.A.); aff'd [1991] 3 S.C.R. 387），本行引证仍属分号前的案名。词表取自
#   全量实测：分号后以字母起头的 3,408 行里，表示本案沿革的只有 aff'd/affirmed（73）与
#   leave to appeal（17）两类，rev'd/var'd 同属一类一并收；其余全是另一件案子（Re …、
#   Reference re …、In re …、Ex parte …）。与 _ADMIT_VERB_RE 同是 §8.7 的案名清洗词表
_HISTORY_RE = re.compile(
    r"(?:aff(?:[’']?d|irmed|irming|[’']?g)|rev(?:[’']?d|ersed|ersing|[’']?g)"
    r"|var(?:[’']?d|ied|ying)|leave\s+to\s+appeal)\b", re.IGNORECASE)
# PROBLEMS #43：判决书段落体例是 [24] The trial judge…，切分起点落在编号中间时
#   会留下 24] 的残尾。原清洗只剥前导的 [ ( 等字符、不剥数字，于是 24] R. v. Smith
#   原样留下。**只收「数字 + 右方括号」这一形**：没有案名以此开头，零误伤；裸数字
#   开头（3 Grand Trunk Ry. Co.）不收——那会把 3M Canada 剥成 M Canada。
#   实测：命中 19,372 条，全部净改善，剥空 0 条，误伤 0 条（离线预演 + 全量复跑）
_ADMIT_PARA_RE = re.compile(r"\d+\s*\]")
# PROBLEMS #45：案名尾巴吞平行引证（Housen v. Nikolaisen, 2002 SCC 33）。
#   后果在裁定层放大：§10.3 按 nk(案名) 判同案，尾巴不同就判不出同案，同一个
#   案子裂成两组（实测 R. v. Lacasse 387dd 与 376dd 两组、Housen 546 与 480）。
#   判据必须能分辨**两种年份**：引证里的年份 vs 公司名里的年份——加拿大公司常以
#   成立年份命名（Voyageur (1969) Inc.、Rapatax (1987) Inc.）。分辨法：年份之后
#   必须紧跟**引证形态**（卷号数字，或「大写代码 + 序号」的中立引用），跟着
#   Inc./Ltd. 之类的不算。年份本身要求词边界，否则编号公司 1420041 里的 2004
#   会被当成年份（首版就栽在这里，把 1420041 Ontario Inc. v. … 剥成了 14）。
_YEARISH = (r"(?:\(\s*(?:18|19|20)\d{2}\s*\)|\[\s*(?:18|19|20)\d{2}\s*\]"
            r"|(?<!\d)(?:18|19|20)\d{2}(?!\d))")
_ADMIT_CITE_TAIL_RE = re.compile(
    r"(?:[,;]\s*|\s+)" + _YEARISH +
    r"(?:,?\s+\d|,?\s+[A-Z][A-Za-z.]{0,9}\.?\s+\d).*$", re.DOTALL)  # 案名可含换行；无 DOTALL 时 .*$ 跨不过换行，漏剥 227 条（自检发现）

# 形状 → 主缩写取自哪个字段（规格 §7.3）
TOKEN_SHAPES = {"shape_bracket", "shape_neutral_bare"}


# ------------------------------------------------------------------- 决策表 IO
def load_table(name):
    """读一张决策表。空表（只有表头）返回空列表——空表不是故障（§13.4）。"""
    path = os.path.join(DECISIONS, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f)
                if any((v or "").strip() for v in r.values())]


def build_index(rows, field):
    idx = {}
    for r in rows:
        k = (r.get(field) or "").strip()
        if k:
            idx.setdefault(k, []).append(r)
    return idx


def lookup_all(key, idx):
    return idx.get((key or "").strip(), [])


def lookup_one(key, idx):
    """唯一命中才返回；同键多行属建表缺陷，不猜。"""
    hits = lookup_all(key, idx)
    return hits[0] if len(hits) == 1 else None


def append_reason(row, field, reason):
    cur = row.get(field) or ""
    row[field] = (cur + "|" + reason) if cur else reason


# --------------------------------------------------------------- §8.7 案名清洗
# PROBLEMS #58：没有 v. 的案名。只在**本行引证所在那一段的段首**认一个闭集标记：
#   Reference re X / Re X / In re X / Ex parte X  —— 名称从标记起；
#   X (Re)                                        —— 后缀形；
#   魁北克匿名案名 Droit de la famille — NNNN / LSJPA — NNNN。
#   标记后须紧跟大写词：「Re the question whether…」这类散文不成名。
#   这是 §8.7 的**补充规则**（原文只以 v. 为唯一结构锚），须人复核。
_MARKER_PREFIX_RE = re.compile(r"^(?:Reference\s+re|Re|In\s+re|Ex\s+parte)\s+(?=[A-Z])")
_MARKER_TAIL_RE = re.compile(r"\(Re\)\s*[.,]?\s*$")
_MARKER_ANON_RE = re.compile(r"^(?:Droit\s+de\s+la\s+famille|LSJPA)\s*[—–-]")
# 走词用的连接词表。**它不决定「是不是案名」**，只决定「这个词能不能继续算案名的一部分」：
#   表太小 ⇒ 提前切断，名字变短（安全方向）；表太大 ⇒ 把散文词吞进来（危险方向）。
_CONNECTOR = frozenset("""
of the and a an for in on at by to with from v vs re ex parte de la dit dite
du des et en le les l ltee inc ltd co corp corporation company limited llc lp
plc srl gmbh no nos st ste saint al supra
""".split())


def _is_boundary(tok):
    """纯标点且含句读点（. ;）——那是句子边界，不是案名的一部分。"""
    return (not any(c.isalnum() for c in tok)) and any(c in ".;" for c in tok)


def _name_like(tok):
    """像案名的一部分：含大写字母 / 不含字母（数字、&、[5]）/ 是连接词。"""
    if any(c.isupper() for c in tok):
        return True
    if not any(c.isalpha() for c in tok):
        return True
    return tok.lower().strip("().,&;:'’“”[]") in _CONNECTOR


def _walk_right(seg):
    """标记在段首：从标记向右走，遇到句子边界或不像案名的词就切在那里。
    防的是「Re X, which is referred to by…」这种标记后面接着散文的情形。"""
    end = len(seg)
    for m in re.finditer(r"\S+", seg):
        if m.start() == 0:
            continue                                  # 标记本身
        t = m.group(0)
        if _is_boundary(t) or not _name_like(t):
            end = m.start()
            break
    return seg[:end].strip()


def _re_span(seg):
    """「X (Re)」形：从段尾 (Re) 向左走，返回案名起点下标；走不到像样的起点返回 -1。
    段是「从上一个 ; : 换行 起」，句子跨过那个边界时整段散文都会被吞进来
    （实测不加此闸时 2,750 行里大半是「…relying on several cases including Nortel
    Networks Corp. (Re)」这类整句），故必须从右往左收。"""
    toks = list(re.finditer(r"\S+", seg))
    if not toks:
        return -1
    start = 0
    for m in reversed(toks):
        t = m.group(0)
        if _name_like(t) and not _is_boundary(t):
            start = m.start()
            continue
        break
    name = seg[start:].strip()
    c = name[:1]
    return start if (c.isupper() or c == "(" or c.isdigit()) else -1


def _marker_of(seg):
    if _MARKER_PREFIX_RE.match(seg):
        return "prefix"
    if _MARKER_TAIL_RE.search(seg):
        return "tail_re" if _re_span(seg) >= 0 else ""
    if _MARKER_ANON_RE.match(seg):
        return "anon"
    return ""


# ------------------------------------------------------- §8.7 左侧散文污染（#61）
# 案名候选是从「引证前面最近的分隔符」切到引证；近旁没有 ; : 换行 时，候选会把整句
# 散文吞进来——`strict liability (presumably on the basis of Rylands v. Fletcher`（dd 8）、
# `negligence, nuisance, and the rule in Rylands v. Fletcher`（dd 23）。
# 判据分两步，都被实测逼出来：
#   ① **切点词表**只收「会合法出现在当事人名称内部」的词（of/the/and/de/la/…）。
#      in/to/by/on/at 这些**是**切点：散文的边界恰好是 `…said in McIntosh v. Parent`、
#      `…decision of the Supreme Court in Sattva Capital Corp. v. …`；把它们当连接词，
#      切点会落在更早处、切出「Supreme Court in Sattva Capital Corp.」这种半句（实测）。
#   ② 切点须满足**它到 v. 之间是一段非空的「像案名」词序列**，否则往前退到下一个切点，
#      全不成立就不动。这道闸是关键：法语机构名 `Québec (Procureur général)`、
#      `Union des employés de commerce` 的当事人一侧本身含小写词，没有它会切掉真名
#      （实测首版 25,049 行被改，含大量误伤）。
# 切完若剩下的不以大写开头，**原样退回**而不是判无名：`Union des employés de commerce,
# local 503 v. Roy` 这类真名切点落在数字上，丢弃它比留着脏名字更糟（实测丢弃档会丢掉
# 「Union des employés de commerce」等真案名；这是对 §8.7 补充规则的一处收紧）。
_PROSE_CONNECTOR = frozenset("""
of the and a an for de la le les du des et en aux d l
""".split())
# 大写开头时可以剥掉的词：**只收不可能出现在案名开头的介词/引导词**。
# 冠词（The / La / Le / A）、缩写（St. / Saint / Inc. / Co.）、Re 一律不在内——
# 它们都是真案名的合法开头（见 _trim_prose_left 里的实测例子）
_CAP_STRIP = frozenset("""
in at by on to with from of for and or per see also cf
""".split())
# 公司后缀：**没有任何案名以它开头**，切完落在这上面说明切点落进了真名内部。
# 实测（本轮 260 条改动里 11 条）：`1196303 Inc. v. Glen Grove Suites Inc` 被切成
# `Inc. v. Glen Grove Suites Inc`、`Hôpital général de la région de l'amiante Inc. v. Perron`
# 被切成 `Inc. v. Perron`。注意**不收 corporation**：`Corporation of Quebec v. Howe`、
# `Corporation de St-Joseph de Beauce v. Le ...` 是真的案名开头。
_CORP_SUFFIX = frozenset("""
inc ltd co corp ltee limited gmbh llc lp plc srl sa kft
""".split())
# 法语冠词/介词。**切点前紧邻的词若落在这里，就不切**：`Moulin de préparation de bois
# en transit de St-Romuald v. …`、`Comité de citoyens et d'action municipale de St-Césaire
# Inc. v. …` 的真名是靠这些词串起来的，切在它们后面就是把真名截断。本语料的散文是英文，
# 英文散文的切点前紧邻词是 in/of/from/See/the，不会命中这一档（实测：253 条改动里恰好
# 只有这 3 条命中，收掉它零代价）。
_FR_CONNECTOR = frozenset("de du des d aux la le les".split())
_PROSE_TAIL_STRIP_RE = re.compile(r"[\s,;:.!?&'’“”()\[\]]+")


def _between_is_name_like(text):
    """切点右侧到 v. 之间是不是一段非空的「像案名」词序列。"""
    toks = [m.group(0) for m in re.finditer(r"\S+", text)]
    return bool(toks) and all(_name_like(t) for t in toks)


def _trim_prose_left(s):
    """左侧当事人一侧是散文时切掉散文，返回 (新串, 是否触发)。切不动就原样返回。"""
    last = None
    for m in V_RE.finditer(s):
        last = m
    if last is None:
        return s, False
    left = s[:last.start()]
    cuts = []
    for m in re.finditer(r"\S+", left):
        w = m.group(0).strip("().,&;:'’“”[]")
        if w and w.islower() and w not in _PROSE_CONNECTOR:
            cuts.append(m.end())
    if len(cuts) < 3:
        return s, False                   # 触发闸：左侧至少 3 个小写散文词
    cut = None
    for c in reversed(cuts):
        if _between_is_name_like(left[c:]):
            cut = c
            break
    if cut is None:
        return s, False
    rest = s[cut:]
    last_skip = ""
    while True:
        m = _PROSE_TAIL_STRIP_RE.match(rest)
        if m and m.end():
            rest = rest[m.end():]
            continue
        m = re.match(r"\[\s*\d+\s*\]|\d+\s*[).]|\d+", rest)      # 段落编号 / 页码残尾
        if m and m.end():
            rest = rest[m.end():]
            continue
        m = re.match(r"([^\W\d_]+)", rest, re.UNICODE)
        if m:
            tok = m.group(1)
            low = tok.lower()
            # 剥头的判据**分大小写**（PROBLEMS #61 同日订正）：
            #   · 小写词：连接词一律可剥——案名不会以小写词开头，剥过头也会被末尾的
            #     「须以大写开头」闸拦下、原样退回
            #   · **大写词：只剥不可能出现在案名开头的介词/引导词**（In / At / By / See…）。
            #     冠词与缩写一律不剥：`The King v. Sunfield`、`St. Lawrence Cement Inc. v.
            #     Wakeham`、`La Française IC 2 v. Wires`、`A.E. LePage Ltd. v. Kamex` 都是
            #     真案名开头。原先不分大小写地拿 _CONNECTOR 比对，把这些开头一起剥了
            if low in ("v", "vs"):
                pass
            elif tok[:1].islower():
                if low in _CONNECTOR:
                    rest = rest[m.end():]
                    last_skip = low
                    continue
            elif low in _CAP_STRIP:
                rest = rest[m.end():]
                last_skip = low
                continue
        break
    if last_skip in _FR_CONNECTOR:
        return s, False                   # 切点前紧邻法语冠词/介词：多半在真法语机构名内部
    if not rest or not rest[:1].isupper():
        return s, False                   # 切不到像样的起点：原样退回，不判无名
    _f = re.match(r"([^\W\d_]+)", rest, re.UNICODE)
    if _f and _f.group(1).lower() in _CORP_SUFFIX:
        return s, False                   # 起点是公司后缀：切点落进真名内部了，原样退回
    return rest, True


def admit_candidate(cand):
    s = cand
    while True:
        before = s
        i = 0
        while i < len(s) and (s[i].isspace() or s[i] in _ADMIT_LEAD_CHARS):
            i += 1
        s = s[i:]
        m = _ADMIT_PARA_RE.match(s)         # PROBLEMS #43：剥判决书段落编号残尾
        if m:
            s = s[m.end():]
        m = _ADMIT_VERB_RE.match(s)
        if m:
            s = s[m.end():]
        m = _ADMIT_IN_RE.match(s)
        if m:
            s = s[m.end():]
        if s == before:
            break
    # PROBLEMS #45：剥尾部吞进来的平行引证。安全闸——剥完不得把定义案名的「v.」剥掉，
    # 且须仍含字母（Unicode），否则视为判据打偏，原样退回。首版的闸是「>= 6 字符且含
    # 3 个连续 ASCII 字母」，把缩写姓名（R. v. R.E.M.）、两字姓（R. v. Vu）、带重音的
    # 姓（R. v. Côté）全挡在门外、尾巴原样留着——#50 审计实测它是异名碎片的最大来源
    _t = _ADMIT_CITE_TAIL_RE.sub("", s).strip().rstrip(",;").strip()
    if re.search(r"[^\W\d_]", _t) and (V_RE.search(_t) or not V_RE.search(s)):
        s = _t
    s = re.sub(r"[,;:.\s]+$", "", s)

    # PROBLEMS #61：左侧吞进来的整句散文（近旁没有 ; : 换行 时）。放在剥尾之后、
    # 长度等闸之前——切短了可能正好把一条 too_long 救回来
    s, _fired = _trim_prose_left(s)

    if len(s) > 120:
        return None, "too_long"
    if re.search(r"\[(?:18|19|20)\d{2}\]", s):
        return None, "has_bracketed_year"
    if sum(1 for _ in V_RE.finditer(s)) >= 2:
        return None, "multi_v"
    if not s:
        return None, "empty_after_clean"
    return s, None


def _cite_segment(pre):
    """本行引证**所在的那一段**：它前面最近的 ; : 换行 起，剥掉前导字符。
    PROBLEMS #58 的标记只在段首/段尾认；段内有 v. 时不走标记路。独立成函数是为了
    测试能直接钉住「这段到底有没有 v.」——上一版那条测试的输入里其实没有 v.，
    断言恒真、等于没测（同日订正）。"""
    sep = max(pre.rfind(";"), pre.rfind(":"), pre.rfind("\n"))
    s = pre[sep + 1:]
    i = 0
    while i < len(s) and (s[i].isspace() or s[i] in _ADMIT_LEAD_CHARS):
        i += 1
    return s[i:]


def split_case_name(row):
    """§8.7：取**最后一个** v.；候选取到 preceding_text 末尾（不截到 v.）；
    找不到分隔符即放弃（不退化为从位置 0 取）。

    PROBLEMS #58 补充：先看本行引证**所在的那一段**（它前面最近的 ; : 换行 起）。
    段首是闭集标记、段尾是 (Re)、或是魁北克匿名名，那一段就是案名——不走「取最后一个
    v.」那条路。**只在段内没有 v. 时才走这条**：段内有 v. 就有名字锚，旧路照旧处理
    （否则「…in Rizzo v. Rizzo Shoes Ltd. (Re)」这类段会被整段当案名，实测 46 行）。"""
    pre = row.get("preceding_text") or ""

    seg = _cite_segment(pre)
    if not V_RE.search(seg):
        marker = _marker_of(seg)
        if marker:
            if marker == "prefix":
                seg = _walk_right(seg)
            elif marker == "tail_re":
                _s = _re_span(seg)
                if _s > 0:
                    seg = seg[_s:]
            cleaned, reject = admit_candidate(seg.strip().rstrip(",").strip())
            if reject:
                append_reason(row, "name_rejected_reason", reject)
                row["candidate_case_name"] = ""
            else:
                row["candidate_case_name"] = cleaned
            return

    last = None
    for m in V_RE.finditer(pre):
        last = m

    if last is None:
        append_reason(row, "name_rejected_reason", "no_v_structure")
        row["candidate_case_name"] = ""
        return

    # PROBLEMS #57：v. 之后若隔着分号又起了一段以字母开头的文字——`R. v. Big M Drug Mart
    # Ltd., [1985] 1 S.C.R. 295; Re B.C. Motor Vehicle Act, [本行]`——本行引证属于那一段
    # （Re B.C. Motor Vehicle Act），不属于 v. 所在的案名。那一段没有 v.，就是没有可切的
    # 案名，不能借前一个案子的名字。#45 的剥尾以前会把「; Re B.C. Motor Vehicle Act」连同
    # 前一个引证一起剥掉，让借来的名字通过。分号后紧接引证（`2002 SCC 33; [本行]`，以 [ ( 或
    # 数字起头）是平行引证，不受影响。判据是结构（分号后那段以字母起头），不是词表
    after = pre[last.end():]
    if ";" in after:
        seg = after[after.rfind(";") + 1:].lstrip(" \t\r\n\"'‘“«")
        if seg[:1].isalpha() and not _HISTORY_RE.match(seg):
            append_reason(row, "name_rejected_reason", "name_belongs_to_later_segment")
            row["candidate_case_name"] = ""
            return

    sep = max(pre.rfind(";", 0, last.start()),
              pre.rfind(":", 0, last.start()),
              pre.rfind("\n", 0, last.start()))
    if sep == -1:
        append_reason(row, "name_rejected_reason", "no_separator_before_v")
        row["candidate_case_name"] = ""
        return

    cand = pre[sep + 1:].strip().rstrip(",").strip()
    cleaned, reject = admit_candidate(cand)
    if reject:
        append_reason(row, "name_rejected_reason", reject)
        row["candidate_case_name"] = ""
    else:
        row["candidate_case_name"] = cleaned


# ---------------------------------------------------------------- §8.6 Step 4
def disambiguate_by_structure(row, candidates):
    """只用本行自带的卷号与年份，与候选法域的取值区间比对（§8.6）。

    - 同一法域可有多段区间（多行），命中的法域唯一才判定；多个法域吻合就不猜
    - 无年份：无证据，UNSUPPORTED
    - 无卷号：本行印的就是「[年] 缩写 页」，不印卷号本身是印刷事实（约束七）。
      表里卷号区间含 0 的行表示「该系列可不印卷号」，区间留空表示卷号不参与；
      区间从 1 起的系列恒印卷号，不接无卷号的行（PROBLEMS #52）。调用方标 vol_missing
    - 无年份：年份维度不参与，只凭卷号——「45 K.B. 198」英国 K.B. 每年至多 4 卷，
      45 只能是魁北克。卷号与年份都没有，才是无证据
    """
    vol_s = (row.get("vol") or "").strip()
    year_s = (row.get("year_start") or "").strip()
    if not vol_s and not year_s:
        return "UNSUPPORTED"
    try:
        year = int(year_s) if year_s else None
        vol = int(vol_s) if vol_s else 0
    except ValueError:
        return "UNSUPPORTED"

    hit = set()
    for c in candidates:
        try:
            vs = int(c.get("vol_range_start") or 0)
            ve = int(c.get("vol_range_end") or 99999)
            ys = int(c.get("year_range_start") or 0)
            ye = int(c.get("year_range_end") or 9999)
        except ValueError:
            continue
        if (year is None or ys <= year <= ye) and vs <= vol <= ve:
            hit.add(c.get("jurisdiction") or "")
    return hit.pop() if len(hit) == 1 and "" not in hit else "UNSUPPORTED"


_CONF_RANK = {"confirmed": 3, "inferred": 2, "estimated": 1}


def _weaker(rows, cap):
    """取表行成色的最弱者，再与上限 cap 取弱。消歧不能让一个 estimated 的表行变成
    inferred——把猜的说成推的，是约束四所禁的「给猜测发许可证」换了个方向。"""
    vals = [(r.get("confidence") or "") for r in rows] + ([cap] if cap else [])
    known = [v for v in vals if v in _CONF_RANK]
    return min(known, key=_CONF_RANK.get) if known else (vals[0] if vals else "")


# --------------------------------------------------------------------- 主流程
class Classifier(object):
    def __init__(self, tables, stats):
        self.court_exact = build_index(tables["neutral_court_codes"], "court_code")
        self.court_norm = build_index(tables["neutral_court_codes"], "normalized_key")
        self.rep_exact = build_index(tables["reporter_jurisdiction"], "abbreviation")
        self.rep_norm = build_index(tables["reporter_jurisdiction"], "normalized_key")
        self.prefix_norm = build_index(tables["series_prefix"], "normalized_key")
        self.stats = stats

    def _court_lookup(self, printed_token, has_vol):
        """中立码表查询。PROBLEMS #33 的结构闸在此：有卷号即印刷汇编的结构
        签名，不启用归一键退路。"""
        hit = lookup_one(printed_token, self.court_exact)
        if hit:
            return hit, "exact"
        if has_vol:
            # 只统计「闸门真的挡下了一次归一命中」，不统计「闸门被应用」——
            # 后者含大量本来就不会命中的行，会把闸门的功劳夸大两个数量级
            if lookup_one(normalize_code(printed_token), self.court_norm):
                self.stats["court_false_hit_blocked_by_vol_gate"] += 1
            return None, ""
        hit = lookup_one(normalize_code(printed_token), self.court_norm)
        if hit:
            self.stats["court_hit_via_normalized"] += 1
            return hit, "normalized"
        return None, ""

    def _two_table(self, row, printed_token):
        """§8.2 两表并查：都命中即 table_conflict 交人裁，不设优先级。"""
        has_vol = bool((row.get("vol") or "").strip())
        court_hit, court_mode = self._court_lookup(printed_token, has_vol)

        reporter_hits = lookup_all(printed_token, self.rep_exact)
        rep_mode = "exact" if reporter_hits else ""
        if not reporter_hits:
            reporter_hits = lookup_all(nk(printed_token), self.rep_norm)
            rep_mode = "normalized" if reporter_hits else ""

        # 两表都命中，但**匹配成色不同档**时，精确的一方胜出——印刷串精确等于
        # 哪张表的键，就归哪张。这不是给冲突开优先级（§8.2 禁的是那个），而是
        # 认定「同档才算冲突」：FC 精确等于中立码、只在去标点后才碰到 reporter
        # 的 F.C.，两者不是同一个印刷事实。与 #33 的裁决同源（精确 > 模糊），
        # 方向相反：那次挡的是归一查法院表造假命中，这次挡的是归一查汇编表造假冲突。
        if court_hit and reporter_hits and court_mode != rep_mode:
            if court_mode == "exact":
                reporter_hits = []          # 中立码胜出，按下方 neutral 分支定案
            else:
                court_hit = None            # 汇编胜出，落 Step 3 查法域
            self.stats["conflict_resolved_by_match_grade"] += 1

        if court_hit and not reporter_hits:
            if court_mode == "normalized":
                # 归一命中不是印刷事实：判决上印的是 F.C.，与代码 FC 只是「去
                # 标点后同形」，这是一次推断。按约束四不给判定——给它打
                # confirmed 等于拿模糊匹配当确证，正是「inferred 标签只是给猜测
                # 发许可证」所禁。lookup_mode 已留痕，表填好后可回溯重判。
                row["citation_kind"] = "ambiguous"
                row["abbreviation"] = printed_token
                row["jurisdiction"] = "UNSUPPORTED"
                row["jurisdiction_confidence"] = "unsupported"
                row["lookup_mode"] = "normalized"
                self.stats["neutral_withheld_fuzzy_only"] += 1
                return True
            row["citation_kind"] = "neutral"
            row["abbreviation"] = court_hit["court_code"]
            row["jurisdiction"] = court_hit["jurisdiction"]
            row["jurisdiction_confidence"] = "confirmed"
            row["lookup_mode"] = court_mode
            return True                      # 已定案，不进 Step 3
        if court_hit and reporter_hits:
            row["citation_kind"] = "ambiguous"
            row["abbreviation"] = printed_token
            row["jurisdiction"] = "UNSUPPORTED"
            row["jurisdiction_confidence"] = "unsupported"
            append_reason(row, "rejected_reason", "table_conflict")
            return True
        row["citation_kind"] = "reporter"
        row["abbreviation"] = printed_token
        return False                         # 落入 Step 3

    def step1(self, row):
        shape = row["shape_name"]
        if shape == "shape_leading_abbr":
            # §8.3：前缀校验，主缩写只取 abbr。PROBLEMS #52 修订：认得的前缀若带法域，
            # 交 Step 3 做同形异义消歧（原文「leading_abbr 不参与法域判定」）
            norm_prefix = normalize_code(row.get("leading_abbr") or "")
            hit = lookup_one(norm_prefix, self.prefix_norm)
            if not hit:
                append_reason(row, "rejected_reason", "unrecognized_series_prefix")
            else:
                row["series_prefix"] = row.get("leading_abbr") or ""
                row["_prefix_jur"] = (hit.get("jurisdiction") or "").strip()
            row["citation_kind"] = "reporter"
            row["abbreviation"] = row.get("abbr") or ""
            return False
        if shape in TOKEN_SHAPES:
            return self._two_table(row, row.get("token") or "")
        row["citation_kind"] = "reporter"
        row["abbreviation"] = row.get("abbr") or ""
        return False

    def step2(self, row):
        """§8.4：剔除非案例引证。被标记的行继续填其余字段，不丢弃（约束五）。"""
        raw = row.get("raw_string") or ""
        pre = row.get("preceding_text") or ""
        window = pre + " " + raw
        if FED_STATUTE.search(window) and CHAPTER.search(window):
            append_reason(row, "rejected_reason", "federal_statute")
        if PARTY_TAIL.search(pre) and PARTY_HEAD.match(raw):
            append_reason(row, "rejected_reason", "party_initials")

    def step3(self, row):
        """§8.5：法域查表。精确优先、归一键作退路，lookup_mode 必须留痕。"""
        abbr = row.get("abbreviation") or ""
        mode = "exact"
        candidates = lookup_all(abbr, self.rep_exact)
        if not candidates:
            candidates = lookup_all(nk(abbr), self.rep_norm)
            mode = "normalized" if candidates else "exact"
        if not candidates:
            row["jurisdiction"] = "UNSUPPORTED"
            row["jurisdiction_confidence"] = "unsupported"
            return
        row["lookup_mode"] = mode
        juris = {c.get("jurisdiction") or "" for c in candidates}

        pj = row.get("_prefix_jur") or ""
        if pj:
            # PROBLEMS #52：系列前缀是印在本行上的事实。前缀与表冲突时不下判定——
            # 说明抽取或表有一处错，不拿任何一方硬压另一方
            hit = [c for c in candidates if c.get("jurisdiction") == pj]
            if not hit:
                row["jurisdiction"] = "UNSUPPORTED"
                row["jurisdiction_confidence"] = "unsupported"
                self.stats["prefix_contradicts_table"] += 1
                return
            row["jurisdiction"] = pj
            row["jurisdiction_confidence"] = _weaker(hit, "inferred" if len(juris) > 1 else None)
            if len(juris) > 1:
                row["disambiguated_by"] = "series_prefix"
                self.stats["disambiguated_by_series_prefix"] += 1
            return

        if len(juris) == 1:
            row["jurisdiction"] = next(iter(juris)) or "UNSUPPORTED"
            row["jurisdiction_confidence"] = _weaker(candidates, None)
            return

        has_vol = bool((row.get("vol") or "").strip())
        if not has_vol:
            # §8.6 补充规则：无卷号时消歧只能靠年份，误判风险显著更高，须留痕
            row["vol_missing"] = "true"
        j = disambiguate_by_structure(row, candidates)
        row["jurisdiction"] = j
        if j == "UNSUPPORTED":
            row["jurisdiction_confidence"] = "unsupported"
        else:
            row["jurisdiction_confidence"] = _weaker(
                [c for c in candidates if c.get("jurisdiction") == j], "inferred")
            has_year = bool((row.get("year_start") or "").strip())
            row["disambiguated_by"] = ("novol_year" if not has_vol
                                       else "vol_year" if has_year else "vol_only")
            self.stats["disambiguated_by_" + row["disambiguated_by"]] += 1

    def run_row(self, row):
        for c in NEW_COLUMNS:
            row.setdefault(c, "")
        settled = self.step1(row)
        self.step2(row)
        if not settled:
            self.step3(row)
        split_case_name(row)
        row.pop("_prefix_jur", None)
        # PROBLEMS #13/#54：判决头部必印自身引证，抽取层照单全收。本行抽出串 == 本判决
        # 自身引证（source_decision_citation 即「法院_nk(citation_en)」）即自引。它是真
        # 引证，故不进 rejected_reason（§8.3 要求「不是引证」与其他含义分开），只打标记；
        # 计数时由归并层排除。平行汇编、双语代码等头部其他写法单行认不出，交裁定层
        own = (row.get("source_decision_citation") or "").split("_", 1)[-1]
        if own and nk(row.get("raw_string") or "") == own:
            row["self_citation"] = "true"
            self.stats["self_citation"] += 1

        self.stats["kind_" + (row["citation_kind"] or "none")] += 1
        for r in (row.get("rejected_reason") or "").split("|"):
            if r:
                self.stats["rejected_" + r] += 1
        for r in (row.get("name_rejected_reason") or "").split("|"):
            if r:
                self.stats["name_rejected_" + r] += 1
        if row["jurisdiction"] == "UNSUPPORTED":
            self.stats["jurisdiction_unsupported"] += 1
        elif row["jurisdiction"]:
            self.stats["jurisdiction_resolved"] += 1
        if row["candidate_case_name"]:
            self.stats["case_name_split"] += 1
        return row


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--court", required=True,
                    help="法院前缀，按 source_decision_citation 的 {COURT}_ 过滤（§7.3）")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    stats = Counter()
    tables = {n: load_table(n + ".csv") for n in
              ("neutral_court_codes", "reporter_jurisdiction",
               "series_prefix", "case_origin")}
    clf = Classifier(tables, stats)

    os.makedirs(args.output, exist_ok=True)
    out_path = os.path.join(args.output, "classified.csv")
    tmp = out_path + ".tmp"
    prefix = args.court + "_"

    with open(args.input, encoding="utf-8", newline="") as fin:
        reader = csv.DictReader(fin)
        fieldnames = list(reader.fieldnames) + NEW_COLUMNS
        with open(tmp, "w", encoding="utf-8", newline="") as fout:
            w = csv.DictWriter(fout, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for row in reader:
                stats["input_rows"] += 1
                if not (row.get("source_decision_citation") or "").startswith(prefix):
                    continue
                stats["court_rows"] += 1
                w.writerow(clf.run_row(row))
    os.replace(tmp, out_path)

    manifest = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "court": args.court,
        "input": _relpath(args.input),
        "spec_section": "8",
        "decision_table_rows": {k: len(v) for k, v in tables.items()},
        "stats": dict(sorted(stats.items())),
    }
    with open(os.path.join(args.output, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    print("court=%s  input %d rows -> court %d rows -> %s"
          % (args.court, stats["input_rows"], stats["court_rows"], out_path))
    for k, v in sorted(stats.items()):
        print("   %-34s %d" % (k, v))


if __name__ == "__main__":
    main()
