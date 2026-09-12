# -*- coding: utf-8 -*-
"""extraction_recall_audit.py — 抽取层召回率与漏抽机制的测量（审计环，可重放；PROBLEMS #63 / Task 8）

对**语料自带的上游真值** `cases_cited_en`（判决页面列出的引用案件，条目是裸中立引用）
量我们抽到了多少，并把漏掉的按机制分档：

    真值对 = (语料判决, 中立引用串)，只取 `cases_cited_en` 里形如 `2009 SCC 51` 的条目
    召回 = 我们抽出的 (source_decision_citation, nk(raw_string)) 覆盖了多少真值对
      · kept only       —— 只算最终保留的 span
      · kept+superseded —— 把去重时被更长 span 顶掉的也算进来
    机制
      · 去重败给更长 span：kept 里没有、superseded 里有（#18 的 no-comma-swallow 残余）
      · 根本没抽到：两边都没有 —— 逐条到该判决原文里搜，判断是不是上游元数据条目
        （判决正文里根本没有这一串）

**与 `audit/gap_audit.py` 的「包住率」不是同一个数**：那个量的是宽网对七形状的覆盖率
（实测 98.81%），这个量的是对上游真值的召回（98.80%）。数字相近纯属巧合，引用时分开写。

用法
    python audit/extraction_recall_audit.py --out data/audit/extraction_recall.txt
"""
import argparse
import csv
import io
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
csv.field_size_limit(10 ** 9)
import pyarrow.parquet as pq                                     # noqa: E402
from normalize import nk                                        # noqa: E402

BARE_NEUT = re.compile(r"^(?:1[6-9]|20)\d{2}\s+[A-Za-z][A-Za-z.]{0,24}(?:\s+[A-Za-z]{1,3})?\s+\d{1,6}$")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "audit", "extraction_recall.txt"))
    ap.add_argument("--samples", type=int, default=30)
    a = ap.parse_args()
    out = []

    def w(s=""):
        out.append(s)

    up, up_entry = set(), {}
    for court in ("SCC", "ONCA"):
        pf = pq.ParquetFile(os.path.join(ROOT, "corpus", court + ".parquet"))
        for batch in pf.iter_batches(batch_size=500, columns=["citation_en", "cases_cited_en"]):
            d = batch.to_pydict()
            for cite, lst in zip(d["citation_en"], d["cases_cited_en"]):
                if not lst:
                    continue
                sdc = court + "_" + nk(cite or "")
                for e in lst:
                    e = (e or "").strip()
                    if BARE_NEUT.match(e):
                        k = (sdc, nk(e))
                        up.add(k)
                        up_entry.setdefault(k, e)
    w("上游裸中立引用真值对：(判决, 引用串) = %d" % len(up))

    kept, allset = set(), set()
    shape_kept, shape_all = {}, {}
    span_kept = defaultdict(list)          # sdc -> [(start, end, shape, raw)]
    span_sup = {}                          # (sdc, nk) -> (start, end, raw)
    for fn, acc, sh in (("extracted.csv", kept, shape_kept),
                        ("extracted.csv", allset, shape_all),
                        ("extracted_superseded.csv", allset, shape_all)):
        p = os.path.join(ROOT, "data", "extract_out", fn)
        for r in csv.DictReader(io.open(p, encoding="utf-8", newline="")):
            k = (r["source_decision_citation"], nk(r["raw_string"] or ""))
            if not k[1]:
                continue
            acc.add(k)
            sh.setdefault(k, r["shape_name"])
            try:
                se = (int(r["match_start_offset"]), int(r["match_end_offset"]))
            except (TypeError, ValueError):
                continue
            if fn == "extracted.csv":
                span_kept[k[0]].append((se[0], se[1], r["shape_name"], r["raw_string"]))
            else:
                span_sup[k] = (se[0], se[1], r["raw_string"])
    cov_kept = sum(1 for k in up if k in kept)
    cov_all = sum(1 for k in up if k in allset)
    w("召回（只算最终保留的 span）：%d/%d = %.2f%%" % (cov_kept, len(up), 100.0 * cov_kept / len(up)))
    w("召回（含去重顶掉的 superseded）：%d/%d = %.2f%%" % (cov_all, len(up), 100.0 * cov_all / len(up)))
    w("")

    miss_kept = [k for k in up if k not in kept]
    dedup_lost = [k for k in miss_kept if k in allset]
    never = [k for k in miss_kept if k not in allset]
    w("kept 档漏掉 %d 对：" % len(miss_kept))
    w("  · **去重时输给重叠的更长 span**（superseded 里有）：%d" % len(dedup_lost))
    w("  · **两边都没有**（疑似根本没抽到）：%d" % len(never))
    w("")

    # 赢家 = 同一判决里与它区间重叠、且被保留的那个 span（用偏移量定位，不看名字）
    win_shape, win_ex = Counter(), []
    no_overlap = 0
    for k in dedup_lost:
        sdc = k[0]
        se = span_sup.get(k)
        if not se:
            no_overlap += 1
            continue
        best = None
        for (s0, s1, shp, raw) in span_kept.get(sdc, ()):
            if s0 < se[1] and se[0] < s1:                 # 区间重叠
                if best is None or (s1 - s0) > (best[1] - best[0]):
                    best = (s0, s1, shp, raw)
        if best is None:
            no_overlap += 1
            continue
        win_shape[best[2]] += 1
        if len(win_ex) < a.samples:
            win_ex.append((up_entry.get(k), best[3], best[2], se[2]))
    w("顶掉它的**赢家** span 是哪种形状（按偏移区间重叠定位，不是它的自身形状）：")
    for s, c in win_shape.most_common():
        w("    %-24s %6d" % (s, c))
    w("    定位不到重叠赢家的：%d" % no_overlap)
    w("")
    w("样例（真值条目 → 留在产出里的赢家串）：")
    for e, wraw, shp, lraw in win_ex:
        w("    %-20s 输给 [%s] %r（输家 %r）" % (e, shp, wraw[:60], lraw[:40]))

    # 从没抽到的：先看是不是被并进了更长的键，再到原文里搜
    raw_all = defaultdict(list)          # sdc -> 全部 raw_string（kept + superseded）
    for fn in ("extracted.csv", "extracted_superseded.csv"):
        for r in csv.DictReader(io.open(os.path.join(ROOT, "data", "extract_out", fn),
                                        encoding="utf-8", newline="")):
            raw_all[r["source_decision_citation"]].append(r["raw_string"] or "")
    docs = {}
    for court in ("SCC", "ONCA"):
        pf = pq.ParquetFile(os.path.join(ROOT, "corpus", court + ".parquet"))
        for batch in pf.iter_batches(batch_size=200, columns=["citation_en", "unofficial_text_en"]):
            d = batch.to_pydict()
            for cite, txt in zip(d["citation_en"], d["unofficial_text_en"]):
                docs[court + "_" + nk(cite or "")] = txt or ""
    w("「两边都没有（按归一键）的 %d 对」逐条核查——先看是不是**被并进了更长的键**"
      "（键不等于裸引用，但那一串确实抽出来了），再看原文：" % len(never))
    glued, intext, absent = [], [], []
    for k in sorted(never):
        sdc, nkcite = k
        entry = up_entry.get(k, "")
        host = next((rw for rw in raw_all.get(sdc, ()) if nkcite in nk(rw)), None)
        if host:
            glued.append((sdc, entry, host))
            w("    [并进更长的键] %-24s %-20s -> %r" % (sdc, entry, host[:70]))
            continue
        txt = docs.get(sdc, "")
        if nkcite and nkcite in nk(txt):
            intext.append((sdc, entry))
            w("    [原文里有、但没抽到] %-24s %-20s" % (sdc, entry))
        else:
            absent.append((sdc, entry))
            w("    [原文里没有] %-24s %-20s" % (sdc, entry))
    w("")
    w("小结：%d 条「两边都没有」里——**并进更长的键** %d 条（抽到了，只是没成为独立的裸引用键）；"
      "**原文里有、没抽到** %d 条（真缺口）；**原文里没有** %d 条（更像上游元数据条目，"
      "判决正文根本没印这一串）" % (len(never), len(glued), len(intext), len(absent)))
    w("")
    w("## 与 gap_audit 的口径区分")
    w("本文件的 98.8% 是**对上游 cases_cited_en 真值的召回**；`audit/gap_audit.py` 的 98.81% 是"
      "**宽网对七形状的包住率**。两个数相近纯属巧合，不得混用。")
    txt = "\n".join(out)
    print(txt)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    io.open(a.out, "w", encoding="utf-8").write(txt + "\n")
    print("\n-> %s" % a.out)


if __name__ == "__main__":
    sys.exit(main())
