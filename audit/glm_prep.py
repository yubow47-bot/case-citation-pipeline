# -*- coding: utf-8 -*-
"""glm_prep.py — 给外部廉价模型（GLM）打标签准备样本批次（审计环，只读，可重放）

两个任务，产出都在 data/glm_audit/（gitignored）；模型只写 out/ 下的结果文件，
结果一律经 audit/glm_verify.py 机器核对后才进人工队列（约束九：未核实不得作实现依据）。

  C  找漏抽：随机抽判决段落，模型只「原样抄出段内每条案例引证」，不做判断。
     核对脚本确认抄出的串在原文里真有，再与抽取层 span（kept + superseded）比对，
     没被任何 span 盖住的就是**客观的疑似漏抽**。
  A  案名挑错：kept 组按 dd 取前 N 组，每组给投票案名 + 同组印刷写法 + 3 段引用处原文，
     模型判案名有没有毛病，必须附原文逐字引语。只用于找 bug，不产出「准确率」。

用法
    python audit/glm_prep.py                      # 默认 C 取 40000 段、A 取前 200 组
    python audit/glm_prep.py --c-n 5000 --a-n 50  # 小规模试点
"""
import argparse
import csv
import io
import json
import os
import random
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
csv.field_size_limit(10 ** 9)
import pyarrow.parquet as pq                                     # noqa: E402
from normalize import nk                                        # noqa: E402

OUT = os.path.join(ROOT, "data", "glm_audit")
CHUNK_MAX = 2000        # 每段上限（字符）；按空行切段，短段合并到不超过此长度


def load_docs():
    docs = {}
    for court in ("SCC", "ONCA"):
        pf = pq.ParquetFile(os.path.join(ROOT, "corpus", court + ".parquet"))
        for batch in pf.iter_batches(batch_size=200, columns=["citation_en", "unofficial_text_en"]):
            d = batch.to_pydict()
            for cite, txt in zip(d["citation_en"], d["unofficial_text_en"]):
                if txt:
                    docs[court + "_" + nk(cite or "")] = txt
    return docs


_OLD_CHUNK_RE = re.compile(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", re.S)


def _chunks_of_ref(txt):
    """原始逐段正则（慢），仅用于对拍验证 _chunks_of_fast 的等价性。"""
    return [(m.start(), m.end()) for m in _OLD_CHUNK_RE.finditer(txt)]


def chunks_of(txt):
    """按空行切段，短段合并；超长段按 CHUNK_MAX 硬切（切点退到最近的空白）。
    返回 [(start, end)]，是 unofficial_text_en 的 Python 字符下标——与抽取层偏移同一坐标系。

    实现与 _OLD_CHUNK_RE 语义逐字符等价（引证段落的切分坐标系必须与旧版一致）：
    段落 = 从一个 \S 开始，终于「其后紧跟空行起头的 \n 或文末」的 \S。
    快版依据：匹配终点必是某个 \S+ run 的末字符（其后一位是 \n 或 EOF），
    故只需扫描 \S+ run 与空行起点，不必逐字符回溯。"""
    n = len(txt)
    bounds = set()
    for m in re.finditer(r"\n", txt):
        p, q = m.start(), m.start() + 1
        while q < n and txt[q].isspace() and txt[q] != "\n":
            q += 1
        if q < n and txt[q] == "\n":
            bounds.add(p)
    paras, cur = [], None
    for m in re.finditer(r"\S+", txt):
        if cur is None:
            cur = m.start()
        e = m.end()
        if e == n or e in bounds:
            paras.append((cur, e))
            cur = None
    out = []
    cur = None
    for s, e in paras:
        while e - s > CHUNK_MAX:
            cut = txt.rfind(" ", s, s + CHUNK_MAX)
            cut = cut if cut > s else s + CHUNK_MAX
            if cur:
                out.append(cur)
                cur = None
            out.append((s, cut))
            s = cut
        if cur and e - cur[0] <= CHUNK_MAX:
            cur = (cur[0], e)
        else:
            if cur:
                out.append(cur)
            cur = (s, e)
    if cur:
        out.append(cur)
    return out


def write_batches(items, sub, size):
    d = os.path.join(OUT, sub)
    os.makedirs(os.path.join(d, "out"), exist_ok=True)
    n = 0
    for i in range(0, len(items), size):
        n += 1
        with io.open(os.path.join(d, "batch_%04d.jsonl" % n), "w", encoding="utf-8", newline="\n") as f:
            for it in items[i:i + size]:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
    return n


def prep_c(docs, n, size, rng):
    pool = []
    for sdc in sorted(docs):
        for s, e in chunks_of(docs[sdc]):
            if e - s >= 200:                     # 太短的多是页眉页脚，不值一次调用
                pool.append((sdc, s, e))
    rng.shuffle(pool)
    items = [{"id": "C%06d" % i, "sdc": sdc, "start": s, "end": e, "text": docs[sdc][s:e]}
             for i, (sdc, s, e) in enumerate(pool[:n])]
    return len(pool), items, write_batches(items, "C", size)


def prep_a(docs, n, size, rng):
    sel = list(csv.DictReader(io.open(os.path.join(ROOT, "data", "select_out", "selected.csv"),
                                      encoding="utf-8", newline="")))
    kept = [r for r in sel if r["kept"] == "true"]
    members = defaultdict(list)
    for r in kept:
        members[r["merged_group_id"]].append(r)
    prim = sorted((r for r in kept if r["is_primary"] == "true"),
                  key=lambda r: (-int(r["distinct_decisions_count"]), r["merged_group_id"]))[:n]
    want = {r["merged_group_id"] for r in prim}

    rk_gid = {}
    for gid in want:
        for m in members[gid]:
            rk_gid[m["court"] + "|" + m["merge_key"]] = gid
    cited_by = defaultdict(set)
    for court in ("SCC", "ONCA", "cross_court"):
        p = os.path.join(ROOT, "data", "decide_out", court, "decision_ids.csv")
        for r in csv.DictReader(io.open(p, encoding="utf-8", newline="")):
            gid = rk_gid.get(r["row_key"])
            if gid:
                cited_by[gid].add(r["source_decision_citation"])

    nks = {gid: {nk(m["canonical_string"]) for m in members[gid]} for gid in want}
    spans = defaultdict(list)                    # sdc -> [(start, end, nk(raw))]，只收本批要用的判决
    need = set().union(*cited_by.values()) if cited_by else set()
    for r in csv.DictReader(io.open(os.path.join(ROOT, "data", "extract_out", "extracted.csv"),
                                    encoding="utf-8", newline="")):
        if r["source_decision_citation"] in need:
            spans[r["source_decision_citation"]].append(
                (int(r["match_start_offset"]), int(r["match_end_offset"]), nk(r["raw_string"] or "")))

    items = []
    for i, r in enumerate(prim):
        gid = r["merged_group_id"]
        dec = sorted(cited_by.get(gid, ()))
        rng.shuffle(dec)
        ctx = []
        for sdc in dec:
            hit = next(((s, e) for s, e, k in spans.get(sdc, ()) if k in nks[gid]), None)
            if hit and sdc in docs:
                ctx.append({"sdc": sdc, "text": docs[sdc][max(0, hit[0] - 500):hit[1] + 150]})
            if len(ctx) == 3:
                break
        items.append({"id": "A%04d" % i, "group": gid, "dd": int(r["distinct_decisions_count"]),
                      "case_name": r["case_name_modal"],
                      "citations_in_group": sorted({m["canonical_string"] for m in members[gid]}),
                      "contexts": ctx})
    return items, write_batches(items, "A", size)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--c-n", type=int, default=40000)
    ap.add_argument("--a-n", type=int, default=200)
    ap.add_argument("--c-batch", type=int, default=25)
    ap.add_argument("--a-batch", type=int, default=10)
    ap.add_argument("--seed", type=int, default=20260912)
    a = ap.parse_args()
    docs = load_docs()
    pool, citems, cb = prep_c(docs, a.c_n, a.c_batch, random.Random(a.seed))
    aitems, ab = prep_a(docs, a.a_n, a.a_batch, random.Random(a.seed))
    no_ctx = sum(1 for it in aitems if not it["contexts"])
    print("C：段落池 %d，抽 %d 段 → %d 批（data/glm_audit/C/）" % (pool, len(citems), cb))
    print("A：%d 组 → %d 批（data/glm_audit/A/）；无引用处原文的组 %d" % (len(aitems), ab, no_ctx))


if __name__ == "__main__":
    sys.exit(main())
