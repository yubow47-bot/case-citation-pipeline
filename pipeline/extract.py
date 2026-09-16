# -*- coding: utf-8 -*-
"""extract.py — 抽取层（v2，七形状；v1.4 封版 schema）

结构匹配，全量输出，不筛不判（规格 §7.8）。schema 见规格 §7.3（封版于 v1.4，
按约束六，各层只跑一次——schema 先冻结、后写本文件）。

用法
    python pipeline/extract.py                     # 两语料全量：分批 + 合并
    python pipeline/extract.py --corpus SCC        # 单语料（可重复给出）
    python pipeline/extract.py --merge             # 只做合并（从既有批次文件）
    python pipeline/extract.py --fixture-check     # 验收门：夹具 exact 档对照 §13.1
    python pipeline/extract.py --limit-batches 1   # 烟雾测试（显式参数，入 manifest）

输出结构（--out，默认 <root>/data/extract_out/，规格 §4 的机器产物根）
    <out>/SCC/batch_NNNN.csv        每批 500 份判决的全部行（§7.7）
    <out>/SCC/progress.json         只记 last_batch（§7.7）
    <out>/ONCA/...
    <out>/extracted.csv             kept 行，列=§7.3 schema（计数只读本文件）
    <out>/extracted_superseded.csv  去重败者，额外列 superseded_by（§7.4）
    <out>/manifest.json             参数、语料指纹、行数、形状分布（约束九）

约定
    * 批次文件含全部行（kept 与败者），superseded_by 列区分：空=kept。
      合并步骤按该列拆成两个文件——"计数只看 kept"由此成为结构不变量（§7.4）。
    * superseded_by 格式 "起点:终点:形状名"，指向同判决内挤掉本行的 kept 行；
      kept 行由 (source_decision_citation, match_start_offset,
      match_end_offset, shape_name) 唯一标识。
    * 去重用 normalize.dedup_overlapping（出货共享函数；与测试口径的逐字
      一致性由 run_regression --selftest 的 normalize_equivalence 断言钉住）。
    * 语料只读：pyarrow iter_batches + 列投影（§7.5），禁用 pd.read_parquet。
    * 判决年份默认不设下限（§7.6）；--year-from 为显式参数，用时入 manifest。
    * 字段一律取自原始 match 对象的捕获组，不得对 raw_string 二次正则解析
      （§7.3"关于缩写的取值方式"）。
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time

import pyarrow.parquet as pq

PIPE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(PIPE)
sys.path.insert(0, PIPE)

import normalize                                    # noqa: E402
import shapes                                       # noqa: E402

SHAPES = [(name, re.compile(rx)) for name, rx in shapes.SHAPES]
SHAPE_ORDER = list(shapes.SHAPE_ORDER)
# #21 兜底形状（PROBLEMS #21）：只在七个既有形状都不命中的位置生效。
# 抑制在生成处做（_suppress_overlapping_fallback）——新候选与既有候选结构上
# 不可能共存，dedup/仲裁的重叠规则碰不到它，「新匹配挤掉正确匹配」从根上
# 不可能发生（不变量 K 的证明依赖这一点，见 implementation/r21_fix_report.md）。
# 该常量必须与 shapes.SHAPES 里兜底形状的名字一致（test_shape_21 钉住）。
FALLBACK_SHAPE = "shape_paren_year_abbr_page"


def _suppress_overlapping_fallback(cands):
    """#21 §5.1 兜底语义：与任何非兜底候选（区间相交）重叠的兜底候选，生成处
    抑制（不留痕迹——它们从未成为候选，与 scan_overlapping 的 run 闸同性质）。
    返回 (kept_cands, suppressed_count)。"""
    out = []
    dropped = 0
    others = [(c["match_start_offset"], c["match_end_offset"])
              for c in cands if c["shape_name"] != FALLBACK_SHAPE]
    for c in cands:
        if c["shape_name"] == FALLBACK_SHAPE:
            s, e = c["match_start_offset"], c["match_end_offset"]
            if any(s < oe and os_ < e for os_, oe in others):
                dropped += 1
                continue
        out.append(c)
    return out, dropped

COLUMNS = ["citation_en", "document_date_en", "unofficial_text_en"]   # §7.5
COURTS = ("SCC", "ONCA")

# 规格 §7.3 输出字段（封版顺序）
SCHEMA = [
    "raw_string", "shape_name",
    "token", "leading_abbr", "abbr", "serial_marker", "vol", "page",
    "page_prefix", "page_roman", "page_suffix", "series",
    "year_raw", "year_start",
    "preceding_text", "source_decision_citation", "source_decision_year",
    "match_start_offset", "match_end_offset", "match_span",
]
SCHEMA_SUPER = SCHEMA + ["superseded_by"]

# ---------------------------------------------------------------- candidates
# candidates-2.0：全候选路线（D1/D2/D3 修复）的正式下游输入。旧 kept/superseded
# 仍是 §7.3 v1.4 封版口径，降为历史诊断产物——**不再决定 classify 看见什么**（约束十：
# 本版不再声称沿用未改动的 v1.4 schema）。
CAND_SCHEMA = [
    "candidate_id", "corpus_row_index",
    "source_decision_citation", "source_decision_year",
    "raw_string", "shape_name",
    "match_start_offset", "match_end_offset", "match_span",
    # 解析字段（与 SCHEMA 同名同义；series_paren/paren_note 为 D4 新捕获组）
    "token", "leading_abbr", "abbr", "serial_marker", "vol", "page",
    "page_prefix", "page_roman", "page_suffix", "series",
    "series_paren", "paren_note", "year_raw", "year_start",
    # 仲裁所需的字段跨度（原文绝对偏移；组缺失为 -1）
    "year_span", "page_span", "vol_span", "abbr_span",
    # R2F：neutral_bare 尾括注（零宽前瞻捕获；identifier 细分用，可空）
    "trailing_paren",
    # R4（D1）：法院标注零宽前瞻捕获（reporter 形状；可空）——原文原样，不解释；
    #   含义由 classify 对 decisions/court_designations.csv 精确匹配得出
    "court_designation_raw",
    "court_designation_span",
    # 同一段落两种读法的区分签名
    "parse_signature",
    "preceding_text",
    # D3 跨界解析标注（extract 有判决内跨候选视野，classify 只读本行标注）
    "structural_conflict", "conflict_with_candidate", "conflict_note",
]

_CAND_FIELD_GROUPS = ["token", "leading_abbr", "abbr", "serial_marker", "vol",
                      "page", "page_prefix", "page_roman", "page_suffix",
                      "series", "series_paren", "paren_note", "year"]
_SPAN_GROUPS = {"year": "year_span", "page": "page_span", "vol": "vol_span",
                "abbr": "abbr_span"}


def scan_overlapping(rx, text):
    """重叠枚举（D2）：下一个匹配从本次 match.start()+1 起重找，不再 match.end()。

    边界闸（R2-6 订正为 **run 级**口径）：仅当新匹配的起点落在**同形状更早发射
    起点**所在的同一连续字母数字 run 内时才拒绝——即 run 内的首个匹配位置照旧
    放行（与旧 finditer 的 run 级行为一致：`R1500 A.C. 400` 里的 1500、
    `Court of Appeal[1997] R.J.Q. 2907`、`1[1961] S.C.R. 614` 这类印刷相邻的真
    匹配不再被吞），而同一 run 里同一形状的第二个及以后的起点（`123 A.C. 4` 里
    截出的 `23 A.C. 4`、`3 A.C. 4`）照拒。
    返回 (matches, rejected_count)。"""
    out = []
    rejected = 0
    pos = 0
    n = len(text)
    emitted = []                       # 本形状已接受起点（升序）
    while pos <= n:
        m = rx.search(text, pos)
        if not m:
            break
        s = m.start()
        if s > 0 and text[s - 1].isalnum():
            rs = s - 1                 # 含 s-1 的最长字母数字 run 的起点
            while rs > 0 and text[rs - 1].isalnum():
                rs -= 1
            if emitted and emitted[-1] >= rs:   # 同形状更早起点已在同一 run 内
                rejected += 1
                pos = s + 1
                continue
        out.append(m)
        emitted.append(s)
        pos = s + 1
    return out, rejected


# ---- #21 兜底形状的行级结构谓词（§5.3，无词表；判据见 shapes.py 末条注释）----
_N21_SINGLE_SEG = re.compile(r"(?:^|[\s.])[A-Z](?=[\s.]|$)")
_N21_ALLCAPS = re.compile(r"^[A-Z]{2,8}$")


def _n21_structural_ok(mid, page, year):
    if _N21_ALLCAPS.match(mid):          # SCC/ONCA/QCCS 类全大写中立代码
        return True
    if "." not in mid:                   # Chapter/Section/Study Paper 无句点
        return False
    if not _N21_SINGLE_SEG.search(mid):  # Sup. Ct. Rev./App. Cas./Sel. Ca. 无单字母段
        return False
    if page == year:                     # (1978), S.M. 1978 制定法年份位
        return False
    return True


def parse_signature(shape_name, groupdict):
    """同跨度不同解析的区分签名：解析字段的「名=值」序列（仅非空字段，固定顺序）。
    同形状同起点在 Python 正则下是确定性单匹配，签名差异只来自不同形状或
    不同捕获组分工——这正是仲裁要的「同段异读」。"""
    parts = ["shape=" + shape_name]
    parts += ["%s=%s" % (f, (groupdict.get(f) or "").strip())
              for f in _CAND_FIELD_GROUPS if (groupdict.get(f) or "").strip()]
    return "|".join(parts)


def extract_candidates(text, sdc, year, row_index, court, stats=None):
    """单份判决的全候选（candidates-2.1：2.0 + 尾括注零宽捕获）。七个形状全部重叠扫描；字段值仍一律取
    自原始 match 的捕获组（§7.3「不得对 raw_string 二次正则解析」不变）；
    偏移量指向**未改动的**语料原文。
    #21：第八形状（兜底）扫描后经 _suppress_overlapping_fallback 抑制——
    与任何既有形状候选重叠者不进入候选集（兜底语义，见 FALLBACK_SHAPE 注）。
    返回 (cands, blocked_by_guard)。stats 给出时累加
    stats["candidates_suppressed_by_fallback_overlap"]。"""
    cands = []
    blocked = 0
    for name, rx in SHAPES:
        matches, bl = scan_overlapping(rx, text)
        blocked += bl
        # 各形状的捕获组集合不同（bracket/neutral 用 token，无 abbr）；
        # 缺组记 -1，不得向 regex 要不存在的组
        span_cols = {col: (grp, grp in rx.groupindex)
                     for grp, col in _SPAN_GROUPS.items()}
        for m in matches:
            g = m.groupdict()
            start, end = m.start(), m.end()
            spans = {}
            for col, (grp, has) in span_cols.items():
                gs, ge = m.span(grp) if has else (-1, -1)
                spans[col] = "%d:%d" % (gs, ge) if gs >= 0 else "-1:-1"
            cands.append({
                "candidate_id": "%s:%d:%d:%d:%s" % (court, row_index, start, end, name),
                "corpus_row_index": row_index,
                "source_decision_citation": sdc,
                "source_decision_year": year,
                "raw_string": re.sub(r"\s+", " ", m.group(0)).strip(),
                "shape_name": name,
                "match_start_offset": start,
                "match_end_offset": end,
                "match_span": end - start,
                "token": g.get("token") or "",
                "leading_abbr": g.get("leading_abbr") or "",
                "abbr": g.get("abbr") or "",
                "serial_marker": g.get("serial_marker") or "",
                "vol": g.get("vol") or "",
                "page": g.get("page") or "",
                "page_prefix": g.get("page_prefix") or "",
                "page_roman": g.get("page_roman") or "",
                "page_suffix": g.get("page_suffix") or "",
                "series": g.get("series") or g.get("series_glued") or "",
                "series_paren": g.get("series_paren") or "",
                "paren_note": g.get("paren_note") or "",
                "year_raw": g.get("year") or "",
                "year_start": g.get("year") or "",
                "year_span": spans["year_span"],
                "page_span": spans["page_span"],
                "vol_span": spans["vol_span"],
                "abbr_span": spans["abbr_span"],
                "trailing_paren": g.get("trailing_paren") or "",
                # R4（D1）：法院标注（零宽前瞻捕获；reporter 形状）。span =
                # 标注原文的绝对偏移（捕获组真实位置，含前瞻内）；未捕获为 -1:-1
                "court_designation_raw": g.get("court_designation") or "",
                "court_designation_span": "%d:%d" % m.span("court_designation")
                                          if "court_designation" in rx.groupindex
                                          and m.group("court_designation") is not None
                                          else "-1:-1",
                "parse_signature": parse_signature(name, g),
                "preceding_text": text[max(0, start - 120):start],
                "structural_conflict": "",
                "conflict_with_candidate": "",
                "conflict_note": "",
            })
    # ---- #21 兜底形状：行级结构谓词 + 兜底语义（重叠抑制）----
    # 见 FALLBACK_SHAPE 注。抑制掉的兜底匹配**不产生候选行**（与 run 闸同性质，
    # 生成处不存在即不存在）；计数分开记（结构性拒 / 重叠抑制），不与 run 闸混数。
    fb = [c for c in cands if c["shape_name"] == FALLBACK_SHAPE]
    if fb:
        drop_ids = set()
        n_struct = n_overlap = 0
        others = [(c["match_start_offset"], c["match_end_offset"])
                  for c in cands if c["shape_name"] != FALLBACK_SHAPE]
        for c in fb:
            if not _n21_structural_ok((c.get("abbr") or "").strip(),
                                      (c.get("page") or "").strip(),
                                      (c.get("year_start") or "").strip()):
                drop_ids.add(c["candidate_id"])
                n_struct += 1
                continue
            s, e = c["match_start_offset"], c["match_end_offset"]
            if any(s < oe and os_ < e for os_, oe in others):
                drop_ids.add(c["candidate_id"])
                n_overlap += 1
        if drop_ids:
            cands = [c for c in cands if c["candidate_id"] not in drop_ids]
            if stats is not None:
                stats["fallback_suppressed_structural"] = \
                    stats.get("fallback_suppressed_structural", 0) + n_struct
                stats["fallback_suppressed_overlap"] = \
                    stats.get("fallback_suppressed_overlap", 0) + n_overlap
    return cands, blocked


_YEAR_RE = re.compile(r"^(?:1[6-9]|20)\d{2}$")


def _span_of(cand, col):
    s, e = (cand[col] or "-1:-1").split(":")
    return int(s), int(e)


def annotate_cross_boundary(cands, text):
    """D3：跨界解析标注。关系判定需要**判决内多候选视野**，故在 extract 算好、
    逐候选带出，classify 只读自己行的标注（不比候选）。

    关系：候选 a 的 page 形如 4 位年份，且 a.page_span == b.year_span，b 是从
    该年份起的**独立完整 neutral 候选**，a.start < b.start < a.end < b.end。
    典型形「Y1 CODE1 [,] Y2 CODE2 SERIAL2」——a 把 Y2 误当自己的 serial/page，
    b 从 Y2 起。这是「疑似跨界解析」旗，**不是**一刀切拒绝一切 4 位序号：旗是
    「关系」本身，无 b 配对即无旗（真 4 位页码不受伤）；有旗而配对者无效/
    缺席时，候选保留、交仲裁记 unresolved。"""
    neutrals = [c for c in cands if c["shape_name"] == "shape_neutral_bare"]
    if not neutrals:
        return
    for a in cands:
        if not (a["page"] and _YEAR_RE.match(a["page"])):
            continue
        ps, pe = _span_of(a, "page_span")
        if ps < 0:
            continue
        for b in neutrals:
            bs, be = _span_of(b, "year_span")
            if bs != ps or be != pe:
                continue
            if not (a["match_start_offset"] < b["match_start_offset"]
                    < a["match_end_offset"] < b["match_end_offset"]):
                continue
            a["structural_conflict"] = "cross_boundary_year_page"
            a["conflict_with_candidate"] = b["candidate_id"]
            # code 与 serial 之间的非标准分隔符记录（标准为单空格；此处常见逗号）
            sep = text[be:a["match_end_offset"]]
            a["conflict_note"] = "page=%s read as year by %s; separator=%r" % (
                a["page"], b["shape_name"], sep)
            b["conflict_note"] = (b["conflict_note"] +
                                  (";" if b["conflict_note"] else "") +
                                  "partner of cross_boundary candidate %s" % a["candidate_id"])
            break

    # ---- B10：year_reread_as_vol（容器把真中立引证的年份读进卷槽）----
    # 关系（全部按字段 SPAN 偏移对齐，不做纯值比较）：
    #   a 有 year 与 vol 字段；a.vol 形如年份；存在 shape_neutral_bare 候选 b
    #   使 b.year_span == a.vol_span（同一段印刷数字）且 b.end <= a.end（包含）。
    # 仲裁消费：容器整类判 year_reread_as_vol_invalid，superseded_by=配对者；
    # 被包含的配对者与其同跨度卷读法走既有仲裁，不加强制计数规则。
    for a in cands:
        if a.get("structural_conflict"):
            continue                          # D3 关系优先，一候选一旗
        vol = (a.get("vol") or "").strip()
        if not (a.get("year_raw") or "").strip() or not _YEAR_RE.match(vol):
            continue
        vs, ve = _span_of(a, "vol_span")
        if vs < 0:
            continue
        for b in neutrals:
            bs, be = _span_of(b, "year_span")
            if (bs, be) != (vs, ve):
                continue
            if b["match_end_offset"] > a["match_end_offset"]:
                continue
            a["structural_conflict"] = "year_reread_as_vol"
            a["conflict_with_candidate"] = b["candidate_id"]
            a["conflict_note"] = ("vol %s rereads the year of neutral %s; "
                                  "container key is malformed" % (vol, b["raw_string"]))
            b["conflict_note"] = (b["conflict_note"] +
                                  (";" if b["conflict_note"] else "") +
                                  "partner of year_reread_as_vol container %s"
                                  % a["candidate_id"])
            break


# ---------------------------------------------------------------- extraction
def source_decision_citation(court, citation_en):
    """{法院}_{nk(citation_en)}，如 SCC_2019scc12（§7.3：必须带法院前缀）。"""
    return court + "_" + normalize.nk(citation_en or "")


def decision_year(document_date_en):
    """判决年份（§7.6：判决年份 ≠ 引证年份）。document_date_en 列类型为
    timestamp（两语料 schema 已核实）或 NULL；NULL 得空串，不得推断。
    刻意不设字符串解析分支——那是在本语料上永不执行的代码（§7.3
    "关于 year_start"的同款教训）。"""
    if isinstance(document_date_en, datetime.datetime):
        return str(document_date_en.year)
    return ""


def extract_rows(text, sdc, year, stats=None):
    """单份判决的全部原始命中（文本外循环、形状内循环，§7.7）。
    字段值取自捕获组；无值的组一律空串——空串与缺失是两回事（§7.3），
    不用空串以外的哨兵值。#21 兜底形状的行级结构谓词与重叠抑制在本函数内
    做（与 candidates 路线同一判据，两路线行为一致）。"""
    rows = []
    for name, rx in SHAPES:
        for m in rx.finditer(text):
            g = m.groupdict()
            rows.append({
                "raw_string": re.sub(r"\s+", " ", m.group(0)).strip(),
                "shape_name": name,
                "token": g.get("token") or "",
                "leading_abbr": g.get("leading_abbr") or "",
                "abbr": g.get("abbr") or "",
                "serial_marker": g.get("serial_marker") or "",
                "vol": g.get("vol") or "",
                "page": g.get("page") or "",
                "page_prefix": g.get("page_prefix") or "",
                "page_roman": g.get("page_roman") or "",
                "page_suffix": g.get("page_suffix") or "",
                # 粘连变体并入 series（§7.3）；neutral_bare 的 series 承载分辑词
                "series": g.get("series") or g.get("series_glued") or "",
                "year_raw": g.get("year") or "",
                # 本版恒等于 year_raw（§7.3"关于 year_start"）；
                # 不得编写 year_raw.split("-") 之类的永不执行代码
                "year_start": g.get("year") or "",
                "preceding_text": text[max(0, m.start() - 120):m.start()],
                "source_decision_citation": sdc,
                "source_decision_year": year,
                "match_start_offset": m.start(),
                "match_end_offset": m.end(),
                "match_span": m.end() - m.start(),
            })
    # ---- #21 兜底形状：行级结构谓词 + 兜底语义（与 extract_candidates 同判据）----
    fb = [r for r in rows if r["shape_name"] == FALLBACK_SHAPE]
    if fb:
        keep = []
        n_struct = n_overlap = 0
        others = [(r["match_start_offset"], r["match_end_offset"])
                  for r in rows if r["shape_name"] != FALLBACK_SHAPE]
        for r in fb:
            if not _n21_structural_ok((r.get("abbr") or "").strip(),
                                      (r.get("page") or "").strip(),
                                      (r.get("year_start") or "").strip()):
                n_struct += 1
                continue
            s, e = r["match_start_offset"], r["match_end_offset"]
            if any(s < oe and os_ < e for os_, oe in others):
                n_overlap += 1
                continue
            keep.append(r)
        if len(keep) != len(fb):
            rows = [r for r in rows if r["shape_name"] != FALLBACK_SHAPE] + keep
            if stats is not None:
                stats["fallback_suppressed_structural"] = \
                    stats.get("fallback_suppressed_structural", 0) + n_struct
                stats["fallback_suppressed_overlap"] = \
                    stats.get("fallback_suppressed_overlap", 0) + n_overlap
    return rows


def process_text(text, sdc, year, stats=None):
    """抽取 + 去重（不删行）。返回 (kept, superseded)，行含 superseded_by
    （kept 行该键为 None）。"""
    rows = extract_rows(text, sdc, year, stats=stats)
    kept, superseded = normalize.dedup_overlapping(rows, SHAPE_ORDER)
    for r in superseded:
        r["superseded_by"] = "%d:%d:%s" % r["superseded_by"]
    for r in kept:
        r["superseded_by"] = None
    return kept, superseded


# ------------------------------------------------------------------ batch IO
def _atomic_write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def write_batch(path, rows, schema=None):
    """原子写批次文件：先 .tmp 再 rename（§7.7）。行含 superseded_by 键
    （None=kept）。candidates 批次走 schema=CAND_SCHEMA。"""
    schema = schema or SCHEMA_SUPER
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(schema)
        for r in rows:
            w.writerow(["" if r[k] is None else r[k] for k in schema])
    os.replace(tmp, path)


def batch_path(run_dir, idx):
    return os.path.join(run_dir, "batch_%04d.csv" % idx)


def cand_batch_path(run_dir, idx):
    return os.path.join(run_dir, "cand_batch_%04d.csv" % idx)


# 候选爆炸上限（R2 §7）：单份判决候选数超过此值 **fail closed**——运行直接失败，
# 不截断、不降级；complete 与「发生过截断」不能并存。
CAND_LIMIT = 20000


def run_corpus(court, out_root, batch_size=500, year_from=None,
               limit_batches=None):
    """单语料分批抽取（§7.7）。续跑：读 progress.json 从 last_batch+1 开始；
    目标批次文件已存在则覆盖重跑（上次写了文件未更新进度的情形）。"""
    run_dir = os.path.join(out_root, court)
    os.makedirs(run_dir, exist_ok=True)
    prog_path = os.path.join(run_dir, "progress.json")
    last_done = -1
    if os.path.exists(prog_path):
        with open(prog_path, encoding="utf-8") as f:
            last_done = json.load(f).get("last_batch", -1)

    stats = {"court": court, "docs_total": 0, "docs_extracted": 0,
             "raw_rows": 0, "kept_rows": 0, "superseded_rows": 0,
             "candidates": 0, "candidates_flagged_cross_boundary": 0,
             "candidates_blocked_by_boundary_guard": 0,
             "per_shape_kept": {}, "batches": 0}
    pf = pq.ParquetFile(os.path.join(ROOT, "corpus", court + ".parquet"))
    t0 = time.perf_counter()
    idx = -1
    doc_index = -1
    for batch in pf.iter_batches(batch_size=batch_size, columns=COLUMNS):
        idx += 1
        if limit_batches is not None and idx >= limit_batches:
            break
        if idx <= last_done:
            # 续跑时同步推进语料行号（候选的 corpus_row_index 是语料行号）
            doc_index += len(batch)
            continue
        d = batch.to_pydict()
        rows_out = []
        cands_out = []
        for cite, date, text in zip(d["citation_en"], d["document_date_en"],
                                    d["unofficial_text_en"]):
            doc_index += 1
            stats["docs_total"] += 1
            if not text:
                continue
            year = decision_year(date)
            if year_from and year and int(year) < year_from:
                continue                                    # §7.6 显式过滤
            stats["docs_extracted"] += 1
            kept, superseded = process_text(
                text, source_decision_citation(court, cite), year, stats=stats)
            stats["raw_rows"] += len(kept) + len(superseded)
            stats["kept_rows"] += len(kept)
            stats["superseded_rows"] += len(superseded)
            for k in kept:
                stats["per_shape_kept"][k["shape_name"]] = \
                    stats["per_shape_kept"].get(k["shape_name"], 0) + 1
            rows_out.extend(kept)
            rows_out.extend(superseded)
            # 全候选路线（candidates-2.0）：重叠枚举 + D3 标注
            sdc = source_decision_citation(court, cite)
            cands, bl = extract_candidates(text, sdc, year, doc_index, court,
                                           stats=stats)
            annotate_cross_boundary(cands, text)
            stats["candidates_blocked_by_boundary_guard"] += bl
            if len(cands) > CAND_LIMIT:
                # R2（§7）：候选爆炸**fail closed**——不再截断续跑，直接失败。
                # 一个标着 complete 的 run 与「发生过截断」不能并存。
                raise RuntimeError(
                    "candidate explosion: %s row %d produced %d candidates "
                    "(limit %d); run fails closed, no truncation is performed"
                    % (sdc, doc_index, len(cands), CAND_LIMIT))
            stats["candidates"] += len(cands)
            stats["candidates_flagged_cross_boundary"] += sum(
                1 for c in cands if c["structural_conflict"])
            cands_out.extend(cands)
        write_batch(batch_path(run_dir, idx), rows_out)
        write_batch(cand_batch_path(run_dir, idx), cands_out, schema=CAND_SCHEMA)
        stats["batches"] = idx + 1
        _atomic_write_json(prog_path, {"last_batch": idx})   # 后写进度（§7.7）
    stats["wall_s"] = round(time.perf_counter() - t0, 1)
    return stats


# --------------------------------------------------------------------- merge
def merge(out_root, courts=COURTS):
    """全部批次 → extracted.csv（kept）+ extracted_superseded.csv（败者）
    + candidates.csv（candidates-2.0 全候选，两语料合流）。
    流式逐批读写；kept/superseded 按 superseded_by 列拆分。返回计数（供 manifest）。"""
    counts = {"kept_rows": 0, "superseded_rows": 0, "candidates": 0,
              "candidates_flagged_cross_boundary": 0,
              "per_shape_kept": {}, "batches_merged": 0,
              # 按语料的权威计数：merge 逐个批次文件读过一遍，与本次是否续跑
              # 无关。run 段只记本次处理量（续跑时为 0），故行数以本段为准。
              "by_court": {}}
    kept_path = os.path.join(out_root, "extracted.csv")
    sup_path = os.path.join(out_root, "extracted_superseded.csv")
    cand_path = os.path.join(out_root, "candidates.csv")
    tmp_k, tmp_s, tmp_c = kept_path + ".tmp", sup_path + ".tmp", cand_path + ".tmp"
    with open(tmp_k, "w", encoding="utf-8", newline="") as fk, \
            open(tmp_s, "w", encoding="utf-8", newline="") as fs, \
            open(tmp_c, "w", encoding="utf-8", newline="") as fc:
        wk = csv.writer(fk)
        ws = csv.writer(fs)
        wc = csv.writer(fc)
        wk.writerow(SCHEMA)
        ws.writerow(SCHEMA_SUPER)
        wc.writerow(CAND_SCHEMA)
        for court in courts:
            run_dir = os.path.join(out_root, court)
            if not os.path.isdir(run_dir):
                continue
            names = sorted(n for n in os.listdir(run_dir)
                           if re.fullmatch(r"batch_\d{4}\.csv", n))
            bc = counts["by_court"].setdefault(
                court, {"raw_rows": 0, "kept_rows": 0, "superseded_rows": 0,
                        "candidates": 0, "batches": 0})
            bc["batches"] = len(names)
            for n in names:
                counts["batches_merged"] += 1
                with open(os.path.join(run_dir, n), encoding="utf-8",
                          newline="") as f:
                    r = csv.reader(f)
                    header = next(r)
                    col = {name: i for i, name in enumerate(header)}
                    # 同批次的候选文件：cand_batch_%04d.csv 与 batch_%04d.csv 一一对应
                    with open(cand_batch_path(run_dir, int(n[6:10])),
                              encoding="utf-8", newline="") as fcand:
                        rc = csv.reader(fcand)
                        next(rc)
                        for row in rc:
                            wc.writerow(row)
                            counts["candidates"] += 1
                            bc["candidates"] += 1
                    for row in r:
                        if row[col["superseded_by"]]:
                            ws.writerow(row)
                            counts["superseded_rows"] += 1
                            bc["superseded_rows"] += 1
                            bc["raw_rows"] += 1
                        else:
                            wk.writerow(row[:col["superseded_by"]] +
                                        row[col["superseded_by"] + 1:])
                            counts["per_shape_kept"][row[col["shape_name"]]] = \
                                counts["per_shape_kept"].get(
                                    row[col["shape_name"]], 0) + 1
                            counts["kept_rows"] += 1
                            bc["kept_rows"] += 1
                            bc["raw_rows"] += 1
    os.replace(tmp_k, kept_path)
    os.replace(tmp_s, sup_path)
    os.replace(tmp_c, cand_path)
    return counts


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=ROOT, capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except Exception:
        return ""


def write_manifest(out_root, run_stats, merge_counts, args):
    manifest = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "git_head": git_head(),
        "shapes_version": "v1.4 (frozen) + D4 capture groups (series_paren/paren_note) "
                          "+ R4 court_designation zero-width capture (reporter shapes) "
                          "+ #21 fallback shape_paren_year_abbr_page (fallback-only: "
                          "structural predicate + overlap suppression at generation; "
                          "guards tested on real typography, see r21_fix_report)",
        "candidates_schema": "candidates-2.2 (candidates-2.1 + court_designation "
                             "zero-width lookahead capture on reporter shapes; "
                             "legacy kept/superseded retained as diagnostic only)",
        "params": {"batch_size": args.batch_size,
                   "year_from": args.year_from,
                   "limit_batches": args.limit_batches,
                   "courts": args.corpus},
        "corpus": {c: {"sha256": sha256_file(
            os.path.join(ROOT, "corpus", c + ".parquet"))} for c in args.corpus},
        # run = **本次运行**处理的量；续跑时已完成批次被跳过，此段为 0
        # 属正常。权威行数见 merge.by_court（merge 逐批读过全部文件）。
        "run_this_invocation": run_stats,
        "merge": merge_counts,
        "note": ("计数口径：candidates.csv 是 classify 的正式输入（全候选）；"
                 "extracted.csv/extracted_superseded.csv 是 v1.4 旧去重路线的"
                 "历史诊断产物，不再决定下游可见集合"),
    }
    _atomic_write_json(os.path.join(out_root, "manifest.json"), manifest)
    return manifest


# ------------------------------------------------------------- fixture check
def fixture_check():
    """验收门：出货抽取路径（extract_rows + normalize.dedup_overlapping）
    对六段夹具的 exact 档必须逐段等于 §13.1 基线
    （A 18 / B 15 / C 27 / D 6 / E 0 / F 0）；失败 exit 1。
    本模式只读 tests/ 的冻结夹具与真值表，不改任何文件。"""
    sys.path.insert(0, os.path.join(PIPE, "tests"))
    from fixtures import FIXTURES
    from truth import TRUTH

    EXPECT = {"A_1877_1899_footnotes": 18, "B_1930_1940_footnotes": 15,
              "C_1960s_parallel_cites": 27, "D_cases_cited_block": 6,
              "E_prose_negative": 0, "F_statute_biblio_negative": 0}
    out = {}
    ok = True
    for fx in FIXTURES:
        fid = fx["id"]
        kept, superseded = process_text(
            fx["text"],
            source_decision_citation("SCC", fx["citation_en"]), "")
        exact = sum(1 for ti in TRUTH["fixtures"].get(fid, {}).get("items", [])
                    if any(k["raw_string"] == ti["what"] for k in kept))
        out[fid] = {"exact_hits": exact, "expect": EXPECT[fid],
                    "kept": len(kept), "superseded": len(superseded)}
        ok = ok and exact == EXPECT[fid]
    out["pass"] = ok
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if not ok:
        sys.exit(1)


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", action="append", choices=COURTS,
                    default=None, help="默认两语料都跑")
    ap.add_argument("--out",
                    default=os.path.join(ROOT, "data", "extract_out"))
    ap.add_argument("--batch-size", type=int, default=500)
    ap.add_argument("--year-from", type=int, default=None,
                    help="显式判决年份下限（§7.6：默认不设）")
    ap.add_argument("--limit-batches", type=int, default=None,
                    help="只跑每语料前 N 批（烟雾测试用）")
    ap.add_argument("--merge", action="store_true", help="只做合并")
    ap.add_argument("--fixture-check", action="store_true")
    args = ap.parse_args()
    args.corpus = args.corpus or list(COURTS)

    if args.fixture_check:
        fixture_check()
        return

    os.makedirs(args.out, exist_ok=True)
    if not args.merge:
        run_stats = [run_corpus(c, args.out, args.batch_size, args.year_from,
                                args.limit_batches) for c in args.corpus]
    else:
        run_stats = []
    merge_counts = merge(args.out, args.corpus)
    manifest = write_manifest(args.out, run_stats, merge_counts, args)
    print(json.dumps({"run": run_stats, "merge": merge_counts,
                      "manifest": os.path.join(args.out, "manifest.json")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
