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


def dedup_v1(rows, order):
    """规格 §7.4 的旧实现口径：主键起点升序。v1 回归用。"""
    group = sorted(rows, key=lambda r: (r["start"], -r["span"], order.index(r["shape_name"])))
    kept = []
    for r in group:
        if any(r["start"] < a["end"] and a["start"] < r["end"] for a in kept):
            continue
        kept.append(r)
    return sorted(kept, key=lambda r: (r["start"], r["end"]))


def dedup_v2(rows, order):
    """规格 §7.4 的 v2 口径：主键跨度降序、起点次键、形状顺序末键；输出按起点重排。"""
    group = sorted(rows, key=lambda r: (-r["span"], r["start"], order.index(r["shape_name"])))
    kept = []
    for r in group:
        if any(r["start"] < a["end"] and a["start"] < r["end"] for a in kept):
            continue
        kept.append(r)
    return sorted(kept, key=lambda r: (r["start"], r["end"]))


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
    report = {"truth_status": TRUTH["_meta"]["status"], "fixtures": {}, "negative_fp": {}, "q_b_anchor": {}}
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
            for ti in truth_items:
                if not is_covered(ti["span"], kept):
                    missing.append({"span": ti["span"], "what": ti["what"]})
            entry[ver] = {
                "raw_hits": len(raw),
                "kept_hits": len(kept),
                "per_shape_raw": per_shape,
                "kept": [(k["shape_name"], k["start"], k["end"], k["raw"]) for k in kept],
                "missing_vs_truth": missing,
            }
        if kind in NEGATIVE_KINDS:
            for ver in ("v1", "v2"):
                entry[ver]["false_positives"] = entry[ver]["kept"]  # 真值为空：全部命中即误报
        report["fixtures"][fid] = entry

    # Q(b)：shape_vol_abbr_page 在负对照上的误报率（每百万字符）
    neg = [fx for fx in FIXTURES if fx["kind"] in NEGATIVE_KINDS]
    for ver, shapes, order, dedup in (("v1", V1_SHAPES, V1_ORDER, dedup_v1),
                                      ("v2", V2_SHAPES, V2_ORDER, dedup_v2)):
        n_chars = sum(len(fx["text"]) for fx in neg)
        fp = {}
        for r in ("shape_vol_abbr_page",):
            cnt = 0
            for fx in neg:
                kept = dedup(extract(fx["text"], shapes), order)
                cnt += sum(1 for k in kept if k["shape_name"] == r)
            fp[r] = {"count": cnt, "chars": n_chars,
                     "per_million_chars": round(cnt / n_chars * 1e6, 1) if n_chars else None}
        allc = sum(len(e[ver]["kept"]) for e in report["fixtures"].values()
                   if e["kind"] in NEGATIVE_KINDS)
        fp["all_shapes"] = {"count": allc, "chars": n_chars,
                            "per_million_chars": round(allc / n_chars * 1e6, 1) if n_chars else None}
        report["q_b_anchor"][ver] = fp
    print(json.dumps(report, ensure_ascii=False, indent=1))


# ------------------------------------------------------------- throughput
def throughput():
    import pyarrow.parquet as pq
    path = os.path.join(os.path.dirname(PIPE), "corpus", "SCC.parquet")
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
    for batch in pq.ParquetFile(os.path.join(os.path.dirname(PIPE), "corpus", "SCC.parquet")
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--throughput", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
    elif args.throughput:
        throughput()
    elif args.verify:
        verify()
    else:
        fixture_run()
