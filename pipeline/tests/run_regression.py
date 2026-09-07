# -*- coding: utf-8 -*-
"""run_regression.py — 抽取层 v1/v2 回归基线（pipeline/tests/）

用法：
    python pipeline/tests/run_regression.py                # 夹具回归（六段）
    python pipeline/tests/run_regression.py --selftest     # 合成单元检查（规格示例、截断、去重）
    python pipeline/tests/run_regression.py --throughput   # 全语料单核吞吐（v1 与 v2 各一遍）

读取语料遵守规格 §7.5：pyarrow iter_batches + 列投影，禁用 pd.read_parquet。
夹具文本与真值表见 fixtures.py / truth.py；真值整体标注【待核实】，
本脚本输出的是"对未复核真值的召回"，不等于已核实的召回率。
"""
import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.dirname(HERE)
ROOT = os.path.dirname(PIPE)
sys.path.insert(0, PIPE)

import shapes as v2mod                    # noqa: E402  (现行 v2)
import shapes_v1_frozen as v1mod          # noqa: E402  (v1 冻结副本，仅对照)

V1_SHAPES = [(n, re.compile(rx)) for n, rx in v1mod.SHAPES]
V2_SHAPES = [(n, re.compile(rx)) for n, rx in v2mod.SHAPES]
V1_ORDER = list(v1mod.SHAPE_ORDER)
V2_ORDER = list(v2mod.SHAPE_ORDER)

NEGATIVE_KINDS = {"prose", "statute_biblio"}


def extract(text, shapes):
    rows = []
    for name, rx in shapes:
        for m in rx.finditer(text):
            rows.append({
                "shape_name": name,
                "start": m.start(), "end": m.end(),
                "span": m.end() - m.start(),
                "raw": re.sub(r"\s+", " ", m.group(0)).strip(),
                "groups": {k: v for k, v in m.groupdict().items() if v is not None},
            })
    return rows


def _dedup(rows, key):
    kept = []
    for r in sorted(rows, key=key):
        if not any(r["start"] < a["end"] and a["start"] < r["end"] for a in kept):
            kept.append(r)
    return sorted(kept, key=lambda r: (r["start"], r["end"]))


def dedup_v1(rows, order):
    """规格 §7.4 的旧实现口径：主键起点升序。钉住旧规格行为，v1 回归用。"""
    return _dedup(rows,
                  lambda r: (r["start"], -r["span"], order.index(r["shape_name"])))


def dedup_v2(rows, order):
    """规格 §7.4 的 v2 口径（v1.2 订正后）：主键跨度降序、起点次键、形状顺序末键；
    输出按起点重排。"""
    return _dedup(rows,
                  lambda r: (-r["span"], r["start"], order.index(r["shape_name"])))


def is_covered(truth_span, kept):
    ts, te = truth_span
    return any(m["start"] < te and ts < m["end"] for m in kept)


# ---------------------------------------------------------------- selftest
def selftest():
    out = {}
    spec_examples = ["[1978] A.C. 728", "[1978] 2 All E.R. 492", "[1868] UKHL 1",
                     "389 U.S. 347 (1967)", "211 D.L.R. 4th 300 (2004)",
                     "(1936), 83 F. 2d 212", "2 Q.B. (N.S.) 100 (1893)",
                     "83 F. (2d) 212", "L.R. 3 H.L. 330"]
    table = {}
    for ex in spec_examples:
        h1 = [r["shape_name"] for r in dedup_v1(extract(ex, V1_SHAPES), V1_ORDER)]
        h2 = [r["shape_name"] for r in dedup_v2(extract(ex, V2_SHAPES), V2_ORDER)]
        table[ex] = {"v1": h1, "v2": h2}
    out["spec_examples"] = table

    # (2) 截断缺陷：12n 的 page 捕获
    t = "[1892] 1 Ch. 12n"
    r1 = extract(t, V1_SHAPES)
    r2 = extract(t, V2_SHAPES)
    out["page_suffix_12n"] = {
        "v1_bracket_page": next((r["groups"].get("page") for r in r1 if r["shape_name"] == "shape_bracket"), None),
        "v1_page_suffix": next((r["groups"].get("page_suffix") for r in r1 if r["shape_name"] == "shape_bracket"), None),
        "v2_bracket_page": next((r["groups"].get("page") for r in r2 if r["shape_name"] == "shape_bracket"), None),
        "v2_page_suffix": next((r["groups"].get("page_suffix") for r in r2 if r["shape_name"] == "shape_bracket"), None),
    }

    # (a) 合成部分：缩写内小写连接词
    t = "L.R. 5 H. of L., 86"
    out["hofl_literal"] = {
        "v1": [r["raw"] for r in dedup_v1(extract(t, V1_SHAPES), V1_ORDER)],
        "v2": [(r["raw"], r["shape_name"]) for r in dedup_v2(extract(t, V2_SHAPES), V2_ORDER)],
    }

    # 去重排序：起点更早的短匹配是否挤掉更长匹配（规格 §7.4 示例，合成文本）
    t = "See Smith 3 All E.R. 12 (1968)"
    r1 = extract(t, V1_SHAPES)
    r2 = extract(t, V2_SHAPES)
    out["dedup_ordering_example"] = {
        "text": t,
        "v1_raw": [(r["shape_name"], r["raw"]) for r in r1],
        "v1_kept": [r["raw"] for r in dedup_v1(r1, V1_ORDER)],
        "v2_raw": [(r["shape_name"], r["raw"]) for r in r2],
        "v2_kept": [r["raw"] for r in dedup_v2(r2, V2_ORDER)],
    }

    # 同跨度决胜：2019 SCC 65 应由 shape_neutral_bare 胜出
    t = "2019 SCC 65"
    r2 = extract(t, V2_SHAPES)
    kept = dedup_v2(r2, V2_ORDER)
    out["neutral_tiebreak"] = {"raw": [(r["shape_name"], r["raw"]) for r in r2],
                               "kept": [(r["shape_name"], r["raw"]) for r in kept]}

    # _SEP 逗号容忍的已知误报类（合成探针）：夹具负对照未覆盖此结构，
    # 用固定探针把该误报类钉在基线里，防止将来无声回归。
    probes = ["section 3, Article 12 of the treaty", "in 2019, Things 5 happened"]
    out["sep_comma_fp_probes"] = {
        p: [(r["shape_name"], r["raw"]) for r in dedup_v2(extract(p, V2_SHAPES), V2_ORDER)]
        for p in probes}

    # v1.4 粘连序数探针：现代美式 F.2d/P.2d 写法（序数紧贴缩写句点）由
    # series_glued 变体承接；老式带空格写法（83 F. 2d 212）走原 series 槽。
    out["series_glued_probes"] = {
        p: [(r["shape_name"], r["raw"], r["groups"].get("series"),
             r["groups"].get("series_glued"))
            for r in dedup_v2(extract(p, V2_SHAPES), V2_ORDER)]
        for p in ["571 F.2d 1277 (1978)", "936 P.2d 1011 (1997)", "83 F. 2d 212",
                  "211 D.L.R. 4th 300 (2004)", "15 App. Cas. 210-219"]}

    # v1.4 页码格式探针：斜杠前缀（C.H.R.R. 体例）与罗马页码（leave to appeal
    # 序册页）由 _PAGE 的 page_prefix / page_roman 显式捕获，不静默截断。
    out["page_format_probes"] = {
        p: [(r["shape_name"], r["raw"], r["groups"].get("page"),
             r["groups"].get("page_prefix"), r["groups"].get("page_roman"))
            for r in dedup_v2(extract(p, V2_SHAPES), V2_ORDER)]
        for p in ["6 C.H.R.R. D/2948", "6 C.H.R.R. 2948",
                  "[1997] 2 S.C.R. xi", "[1982] 1 S.C.R. vii",
                  "[1927] R.S.C., c. 29"]}

    # v1.4 债2 探针：neutral_bare token 放宽至 2-12 位（混合大小写 vendor 与
    # 7 位法院代码），year 语义恢复；全大写短代码路径不受影响。
    out["neutral_token_probes"] = {
        p: [(r["shape_name"], r["raw"], r["groups"].get("year"), r["groups"].get("token"))
            for r in dedup_v2(extract(p, V2_SHAPES), V2_ORDER)]
        for p in ["1998 CanLII 13001", "2010 CarswellOnt 5877", "2024 FPSLREB 58",
                  "2013 LNQCTAQ 3", "2019 SCC 65", "2003 EWCA Civ 1746"]}

    # v1.4 债1 探针：编号标记槽——token 不再吸 "No."，编号词进独立
    # serial_marker 组；无编号体例与普通 token 路径不受影响。
    out["serial_marker_probes"] = {
        p: [(r["shape_name"], r["raw"], r["groups"].get("token"),
             r["groups"].get("serial_marker"), r["groups"].get("page"))
            for r in dedup_v2(extract(p, V2_SHAPES), V2_ORDER)]
        for p in ["[2010] O.J. No. 3423", "[1989] B.C.J. No. 1393",
                  "[1952] C.T.S. No. 14", "[1990] 2 F.C. 609",
                  "[1978] A.C. 728", "[1978] 2 All E.R. 492"]}

    # 出货代码等价性：normalize.dedup_overlapping 必须与 dedup_v2 同口径
    # （规格 §7.4 v1.2 订正后两处应逐字一致；一旦分叉，此处红——
    #   本项保证回归真正跑到出货的共享函数，而不只是测试内的本地实现。
    #   v1.3 起 normalize 返回 (kept, superseded)，等价性只对 kept 断言，
    #   并顺带校验 superseded 与 kept 的并集 = 全部原始命中（不删行）。）
    import normalize as nzmod
    eq_texts = ["See Smith 3 All E.R. 12 (1968)",
                "(1936), 83 F. 2d 212",
                "[1966] S.C.R. 238, 47 C.R. 400, 2 C.C.C. 273"]
    eq = {}
    for t in eq_texts:
        rows = extract(t, V2_SHAPES)
        reg = sorted((r["start"], r["end"], r["shape_name"])
                     for r in dedup_v2(rows, V2_ORDER))
        nz_rows = [{"source_decision_citation": "T",
                    "match_start_offset": r["start"], "match_end_offset": r["end"],
                    "match_span": r["span"], "shape_name": r["shape_name"]}
                   for r in rows]
        nz_kept, nz_sup = nzmod.dedup_overlapping(nz_rows, V2_ORDER)
        nz = sorted((r["match_start_offset"], r["match_end_offset"], r["shape_name"])
                    for r in nz_kept)
        union = sorted((r["match_start_offset"], r["match_end_offset"], r["shape_name"])
                       for r in list(nz_kept) + list(nz_sup))
        eq[t] = {"identical": reg == nz, "kept": [list(x) for x in reg],
                 "no_row_lost": union == sorted((r["start"], r["end"], r["shape_name"])
                                                for r in rows)}
    out["normalize_equivalence"] = eq
    if not all(v["identical"] and v["no_row_lost"] for v in eq.values()):
        print(json.dumps(out, ensure_ascii=False, indent=1))
        sys.exit(1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


# ------------------------------------------------------------ fixture run
def fixture_run():
    from fixtures import FIXTURES
    from truth import TRUTH

    truth = TRUTH["fixtures"]
    report = {"truth_status": TRUTH["_meta"]["status"], "fixtures": {},
              "negative_fixture_fp": {}}
    for fx in FIXTURES:
        text, fid, kind = fx["text"], fx["id"], fx["kind"]
        truth_items = truth.get(fid, {}).get("items", [])
        entry = {"kind": kind, "chars": len(text), "source": fx["citation_en"]}
        for ver, shapes, order, dedup in (("v1", V1_SHAPES, V1_ORDER, dedup_v1),
                                          ("v2", V2_SHAPES, V2_ORDER, dedup_v2)):
            raw = extract(text, shapes)
            kept = dedup(raw, order)
            per_shape = {}
            for r in raw:
                per_shape[r["shape_name"]] = per_shape.get(r["shape_name"], 0) + 1
            missing = []
            exact_hits = 0
            covered_not_exact = []
            for ti in truth_items:
                if not is_covered(ti["span"], kept):
                    missing.append({"span": ti["span"], "what": ti["what"]})
                    continue
                # exact 档（v1.4）：区间重叠判据发现不了"抓到一个重叠的错串"——
                # 修 3 的 (1874), L.R. 9 误解析挤掉 L.R. 9 Ex. 192 由此暴露
                if any(k["raw"] == ti["what"] for k in kept):
                    exact_hits += 1
                else:
                    covered_not_exact.append({
                        "what": ti["what"],
                        "overlapping_kept": [k["raw"] for k in kept
                                             if k["start"] < ti["span"][1]
                                             and ti["span"][0] < k["end"]]})
            entry[ver] = {
                "raw_hits": len(raw),
                "kept_hits": len(kept),
                "per_shape_raw": per_shape,
                "kept": [(k["shape_name"], k["start"], k["end"], k["raw"]) for k in kept],
                "missing_vs_truth": missing,
                "exact_hits": exact_hits,
                "covered_not_exact": covered_not_exact,
            }
        if kind in NEGATIVE_KINDS:
            # 负对照真值为空：kept 即误报清单（§13.1 三列表的「额外误报」列），
            # 不再向输出复制一份 false_positives 键
            pass
        report["fixtures"][fid] = entry

    # 负对照（E/F）误报统计：夹具回归的回归哨兵，供 §13.1 负对照表使用。
    # 注意：这不是 PROBLEMS #16 的阈值锚——#16 锚在冻结散文样本上，
    # 由 corpus_counts.py --prose-sample 产出（v1.2 的夹具锚已废止）。
    neg_chars = sum(len(fx["text"]) for fx in FIXTURES if fx["kind"] in NEGATIVE_KINDS)
    for ver in ("v1", "v2"):
        kept = [k for e in report["fixtures"].values() if e["kind"] in NEGATIVE_KINDS
                for k in e[ver]["kept"]]
        fp = {"note": "负对照回归统计，非 #16 锚（锚见 corpus_counts.py --prose-sample）"}
        for name in ("shape_vol_abbr_page", "all_shapes"):
            cnt = sum(1 for k in kept if name == "all_shapes" or k[0] == name)
            fp[name] = {"count": cnt, "chars": neg_chars,
                        "per_million_chars": round(cnt / neg_chars * 1e6, 1) if neg_chars else None}
        report["negative_fixture_fp"][ver] = fp
    print(json.dumps(report, ensure_ascii=False, indent=1))


# ------------------------------------------------------------- throughput
def throughput():
    import pyarrow.parquet as pq
    path = os.path.join(ROOT, "corpus", "SCC.parquet")
    COLUMNS = ["citation_en", "document_date_en", "unofficial_text_en"]
    pf = pq.ParquetFile(path)
    acc = {"v1": {"t": 0.0, "n": 0, "hits": 0}, "v2": {"t": 0.0, "n": 0, "hits": 0}}
    total_chars = 0
    docs = 0
    t_all = time.perf_counter()
    for batch in pf.iter_batches(batch_size=500, columns=COLUMNS):
        d = batch.to_pydict()
        for text in d["unofficial_text_en"]:
            if not text:
                continue
            docs += 1
            total_chars += len(text)
            for ver, shapes in (("v1", V1_SHAPES), ("v2", V2_SHAPES)):
                t0 = time.perf_counter()
                n = 0
                for name, rx in shapes:
                    for _ in rx.finditer(text):
                        n += 1
                acc[ver]["t"] += time.perf_counter() - t0
                acc[ver]["n"] += n
    wall = time.perf_counter() - t_all
    out = {"docs": docs, "text_chars": total_chars, "wall_s": round(wall, 1)}
    for ver in ("v1", "v2"):
        t = acc[ver]["t"]
        out[ver] = {"regex_time_s": round(t, 1), "raw_hits": acc[ver]["n"],
                    "MB_text_per_s": round(total_chars / 1e6 / t, 2) if t else None,
                    "method": "pyarrow iter_batches(500) 列投影; 每判决对每形状 finditer；"
                              "MB/s 以非空 unofficial_text_en 字符数（非文件字节）为分母；"
                              "单进程单核，纯 Python 循环"}
    print(json.dumps(out, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- verify
def verify():
    """夹具溯源复核：按 row 重新读取 parquet，text[corpus_start:corpus_end]
    应与 fixtures.py 内嵌 text 逐字一致。只读打开语料。"""
    import pyarrow.parquet as pq
    from fixtures import FIXTURES
    rows = {fx["row"]: fx for fx in FIXTURES}
    COLUMNS = ["citation_en", "document_date_en", "unofficial_text_en"]
    got = {}
    i = -1
    for batch in pq.ParquetFile(os.path.join(ROOT, "corpus", "SCC.parquet")
                                ).iter_batches(batch_size=500, columns=COLUMNS):
        d = batch.to_pydict()
        for cite, date, text in zip(d["citation_en"], d["document_date_en"], d["unofficial_text_en"]):
            i += 1
            if i in rows:
                got[i] = (cite, text)
        if len(got) == len(rows):
            break
    out = []
    for row, fx in sorted(rows.items()):
        cite, text = got[row]
        ok_slice = text[fx["corpus_start"]:fx["corpus_end"]] == fx["text"]
        ok_cite = cite == fx["citation_en"]
        out.append({"id": fx["id"], "row": row, "slice_identical": ok_slice, "citation_identical": ok_cite})
    print(json.dumps({"verify": out}, ensure_ascii=False, indent=1))


# ------------------------------------------------------------- field-audit
def field_audit_mode():
    """捕获组体检（v1.4 新仪器）：对全语料七形状 raw 命中断言字段不变量。
    宽骨架差集只能发现漏抓；本模式专测"抓到了但字段是错的"（R1/R2/R5 族）。
    五条不变量（违反按形状分类计数 + 样例）：
      1  token/abbr/leading_abbr 含编号词 No./no.
      2  token/abbr/leading_abbr 整值为单字母+句点（章节标记 c. 类）
      3  page 之后紧跟 -数字（连字符页码/区间被静默截断）
      4  page 之后紧跟 /
      5  vol 为年份形状而该命中无 year 组（年份被当卷号）
    此后 shapes.py 任何改动与夹具回归同级必跑。"""
    import pyarrow.parquet as pq

    YEAR_RE = re.compile(r"^(?:1[6-9]|20)\d{2}$")
    NO_WORD = re.compile(r"\bNo\.|\bno\.")
    # 章节标记是小写 c.（R.S.C., c. 29）；单字母大写 reporter（P./D./F.）是合法缩写，
    # v1.4 首跑曾用 [A-Za-z] 双大小写误标它们——本不变量只查小写。
    SINGLE_DOT = re.compile(r"^[a-z]\.$")
    FIELDS = ("token", "abbr", "leading_abbr")
    counts = {f"inv{i}": {} for i in (1, 2, 3, 4, 5)}
    examples = {f"inv{i}": [] for i in (1, 2, 3, 4, 5)}

    def record(inv, shape, court, row, hit, why):
        counts[inv][shape] = counts[inv].get(shape, 0) + 1
        if len(examples[inv]) < 8:
            examples[inv].append({"court": court, "row": row, "shape": shape,
                                  "why": why, "raw": hit["raw"][:70]})

    for court in ("SCC", "ONCA"):
        i = -1
        for b in pq.ParquetFile(
                os.path.join(ROOT, "corpus", court + ".parquet")
        ).iter_batches(batch_size=500, columns=["unofficial_text_en"]):
            for t in b.to_pydict()["unofficial_text_en"]:
                i += 1
                if not t:
                    continue
                for h in extract(t, V2_SHAPES):
                    g = h["groups"]
                    shape = h["shape_name"].replace("shape_", "")
                    for f in FIELDS:
                        v = g.get(f)
                        if not v:
                            continue
                        if NO_WORD.search(v):
                            record("inv1", shape, court, i, h, f"{f}={v!r} 含编号词")
                        if SINGLE_DOT.match(v):
                            record("inv2", shape, court, i, h, f"{f}={v!r} 单字母+句点")
                    end = h["end"]
                    nxt2 = t[end:end + 2]
                    if len(nxt2) == 2 and nxt2[0] == "-" and nxt2[1].isdigit():
                        record("inv3", shape, court, i, h, f"page 后连字符：{t[end:end + 8]!r}")
                    if t[end:end + 1] == "/":
                        record("inv4", shape, court, i, h, "page 后斜杠")
                    vol = g.get("vol")
                    if vol and YEAR_RE.match(vol) and "year" not in g:
                        record("inv5", shape, court, i, h, f"vol={vol} 为年份形状且无 year 组")
    out = {"method": "七形状 raw 命中字段不变量体检（全语料）",
           "violations": counts, "examples": examples}
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--throughput", action="store_true")
    g.add_argument("--verify", action="store_true")
    g.add_argument("--field-audit", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
    elif args.throughput:
        throughput()
    elif args.verify:
        verify()
    elif args.field_audit:
        field_audit_mode()
    else:
        fixture_run()
