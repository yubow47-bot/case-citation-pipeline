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


def extract_rows(text, sdc, year):
    """单份判决的全部原始命中（文本外循环、形状内循环，§7.7）。
    字段值取自捕获组；无值的组一律空串——空串与缺失是两回事（§7.3），
    不用空串以外的哨兵值。"""
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
    return rows


def process_text(text, sdc, year):
    """抽取 + 去重（不删行）。返回 (kept, superseded)，行含 superseded_by
    （kept 行该键为 None）。"""
    rows = extract_rows(text, sdc, year)
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


def write_batch(path, rows):
    """原子写批次文件：先 .tmp 再 rename（§7.7）。行含 superseded_by 键
    （None=kept）。"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(SCHEMA_SUPER)
        for r in rows:
            w.writerow(["" if r[k] is None else r[k] for k in SCHEMA_SUPER])
    os.replace(tmp, path)


def batch_path(run_dir, idx):
    return os.path.join(run_dir, "batch_%04d.csv" % idx)


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
             "per_shape_kept": {}, "batches": 0}
    pf = pq.ParquetFile(os.path.join(ROOT, "corpus", court + ".parquet"))
    t0 = time.perf_counter()
    idx = -1
    for batch in pf.iter_batches(batch_size=batch_size, columns=COLUMNS):
        idx += 1
        if limit_batches is not None and idx >= limit_batches:
            break
        if idx <= last_done:
            continue
        d = batch.to_pydict()
        rows_out = []
        for cite, date, text in zip(d["citation_en"], d["document_date_en"],
                                    d["unofficial_text_en"]):
            stats["docs_total"] += 1
            if not text:
                continue
            year = decision_year(date)
            if year_from and year and int(year) < year_from:
                continue                                    # §7.6 显式过滤
            stats["docs_extracted"] += 1
            kept, superseded = process_text(
                text, source_decision_citation(court, cite), year)
            stats["raw_rows"] += len(kept) + len(superseded)
            stats["kept_rows"] += len(kept)
            stats["superseded_rows"] += len(superseded)
            for k in kept:
                stats["per_shape_kept"][k["shape_name"]] = \
                    stats["per_shape_kept"].get(k["shape_name"], 0) + 1
            rows_out.extend(kept)
            rows_out.extend(superseded)
        write_batch(batch_path(run_dir, idx), rows_out)
        stats["batches"] = idx + 1
        _atomic_write_json(prog_path, {"last_batch": idx})   # 后写进度（§7.7）
    stats["wall_s"] = round(time.perf_counter() - t0, 1)
    return stats


# --------------------------------------------------------------------- merge
def merge(out_root, courts=COURTS):
    """全部批次 → extracted.csv（kept）+ extracted_superseded.csv（败者）。
    流式逐批读写；按 superseded_by 列拆分。返回计数（供 manifest）。"""
    counts = {"kept_rows": 0, "superseded_rows": 0,
              "per_shape_kept": {}, "batches_merged": 0,
              # 按语料的权威计数：merge 逐个批次文件读过一遍，与本次是否续跑
              # 无关。run 段只记本次处理量（续跑时为 0），故行数以本段为准。
              "by_court": {}}
    kept_path = os.path.join(out_root, "extracted.csv")
    sup_path = os.path.join(out_root, "extracted_superseded.csv")
    tmp_k, tmp_s = kept_path + ".tmp", sup_path + ".tmp"
    with open(tmp_k, "w", encoding="utf-8", newline="") as fk, \
            open(tmp_s, "w", encoding="utf-8", newline="") as fs:
        wk = csv.writer(fk)
        ws = csv.writer(fs)
        wk.writerow(SCHEMA)
        ws.writerow(SCHEMA_SUPER)
        for court in courts:
            run_dir = os.path.join(out_root, court)
            if not os.path.isdir(run_dir):
                continue
            names = sorted(n for n in os.listdir(run_dir)
                           if re.fullmatch(r"batch_\d{4}\.csv", n))
            bc = counts["by_court"].setdefault(
                court, {"raw_rows": 0, "kept_rows": 0, "superseded_rows": 0,
                        "batches": 0})
            bc["batches"] = len(names)
            for n in names:
                counts["batches_merged"] += 1
                with open(os.path.join(run_dir, n), encoding="utf-8",
                          newline="") as f:
                    r = csv.reader(f)
                    header = next(r)
                    col = {name: i for i, name in enumerate(header)}
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
        "shapes_version": "v1.4 (frozen)",
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
        "note": ("计数口径：kept 行只存在于 extracted.csv（§7.4）；"
                 "raw_rows = kept + superseded。occurrence/decisions 统计"
                 "只读 extracted.csv，不得读 extracted_superseded.csv"),
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
