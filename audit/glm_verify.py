# -*- coding: utf-8 -*-
"""glm_verify.py — 机器核对 GLM 的打标签结果（审计环，只读，可重放）

模型的输出一律不直接信（约束九）。本脚本只做能机器判定的事：

  C  每条抄出的串：① 在该段原文里找得到吗（找不到 = 抄错或编造，丢弃并计数）；
     ② 找到的位置有没有被抽取层任一 span（kept 或 superseded）盖住。
     没被盖住的 = **疑似漏抽**，写进 C_candidates.csv 交人看（是不是真引证仍须人定）。
  A  每条标签：evidence_quote 在给它的原文里找得到吗；两遍标签一致吗。
     写进 A_review.csv，按「标了毛病 → 引语可核 → dd 高」排序。

结果文件：data/glm_audit/{C,A}/out/batch_NNNN.runK.jsonl（每行一个 JSON）
  C 行：{"id": "C000123", "citations": ["[1985] 2 S.C.R. 486", ...]}
  A 行：{"id": "A0007", "label": "correct|truncated|prose_contaminated|borrowed|wrong|cannot_tell",
         "evidence_quote": "...", "note": "..."}

用法
    python audit/glm_verify.py
"""
import csv
import glob
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv.field_size_limit(10 ** 9)
OUT = os.path.join(ROOT, "data", "glm_audit")
_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "})


def _norm_with_map(s):
    """空白压成单个空格、弯引号/破折号拉直；返回 (归一串, 归一串下标 → 原串下标)。"""
    out, idx, prev_space = [], [], False
    for i, ch in enumerate(s.translate(_QUOTES)):
        if ch.isspace():
            if prev_space:
                continue
            ch, prev_space = " ", True
        else:
            prev_space = False
        out.append(ch)
        idx.append(i)
    return "".join(out), idx


def locate(needle, hay):
    """needle 在 hay 里的所有出现位置（hay 的原始下标）。先精确找，找不到再按归一形找。"""
    needle = needle.strip()
    if not needle:
        return []
    hits = [m.start() for m in re.finditer(re.escape(needle), hay)]
    if hits:
        return [(h, h + len(needle)) for h in hits]
    nn, _ = _norm_with_map(needle)
    nh, mp = _norm_with_map(hay)
    res, p = [], nh.find(nn)
    while p >= 0:
        res.append((mp[p], mp[p + len(nn) - 1] + 1))
        p = nh.find(nn, p + 1)
    return res


def load_items(sub):
    items = {}
    for fn in sorted(glob.glob(os.path.join(OUT, sub, "batch_*.jsonl"))):
        for line in io.open(fn, encoding="utf-8"):
            if line.strip():
                it = json.loads(line)
                items[it["id"]] = it
    return items


def load_results(sub):
    """{id: [结果行, ...]}（每遍一行）；解析不了的行计数但不中断。"""
    res, bad = defaultdict(list), 0
    for fn in sorted(glob.glob(os.path.join(OUT, sub, "out", "*.jsonl"))):
        for line in io.open(fn, encoding="utf-8", errors="replace"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                res[r["id"]].append(r)
            except (ValueError, KeyError, TypeError):
                bad += 1
    return res, bad


def verify_c():
    items = load_items("C")
    res, bad = load_results("C")
    if not res:
        return ["C：还没有结果文件"]
    need = {items[i]["sdc"] for i in res if i in items}
    spans = defaultdict(list)
    for fn in ("extracted.csv", "extracted_superseded.csv"):
        for r in csv.DictReader(io.open(os.path.join(ROOT, "data", "extract_out", fn),
                                        encoding="utf-8", newline="")):
            if r["source_decision_citation"] in need:
                spans[r["source_decision_citation"]].append(
                    (int(r["match_start_offset"]), int(r["match_end_offset"]), fn[:-4]))
    st = Counter()
    cands = {}
    for iid, runs in sorted(res.items()):
        it = items.get(iid)
        if not it:
            st["结果 id 不在批次里"] += 1
            continue
        st["已完成段落"] += 1
        seen = set()
        for run in runs:
            for c in run.get("citations") or []:
                if not isinstance(c, str) or not c.strip() or c.strip() in seen:
                    continue
                c = c.strip()
                seen.add(c)
                st["抄出的串（去重）"] += 1
                locs = locate(c, it["text"])
                if not locs:
                    st["原文里找不到（抄错/编造，丢弃）"] += 1
                    continue
                for s, e in locs:
                    a0, a1 = it["start"] + s, it["start"] + e
                    cover = [src for (x0, x1, src) in spans.get(it["sdc"], ()) if x0 < a1 and a0 < x1]
                    if "extracted" in cover:
                        st["被 kept span 盖住（已抽到）"] += 1
                    elif cover:
                        st["只被 superseded 盖住（去重输掉）"] += 1
                    else:
                        st["**没被任何 span 盖住（疑似漏抽）**"] += 1
                        key = (it["sdc"], a0, a1)
                        if key not in cands:
                            ctx = it["text"][max(0, s - 120):e + 60].replace("\n", " ")
                            cands[key] = {"sdc": it["sdc"], "start": a0, "end": a1, "citation": c,
                                          "context": ctx, "item": iid}
    p = os.path.join(OUT, "C_candidates.csv")
    with io.open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["citation", "sdc", "start", "end", "context", "item"])
        w.writeheader()
        for row in sorted(cands.values(), key=lambda r: (r["sdc"], r["start"])):
            w.writerow(row)
    out = ["## C 找漏抽", "解析失败的结果行：%d" % bad]
    out += ["- %s：%d" % (k, v) for k, v in st.items()]
    out.append("疑似漏抽（去重后）→ %s：%d 条" % (os.path.relpath(p, ROOT), len(cands)))
    return out


LABELS = {"correct", "truncated", "prose_contaminated", "borrowed", "wrong", "cannot_tell"}


def verify_a():
    items = load_items("A")
    res, bad = load_results("A")
    if not res:
        return ["A：还没有结果文件"]
    rows, st = [], Counter()
    for iid, runs in sorted(res.items()):
        it = items.get(iid)
        if not it:
            st["结果 id 不在批次里"] += 1
            continue
        hay = "\n".join(c["text"] for c in it["contexts"]) + "\n" + it["case_name"]
        labels = [r.get("label") if r.get("label") in LABELS else "INVALID" for r in runs]
        quotes_ok = [bool(locate(r.get("evidence_quote") or "", hay)) for r in runs]
        agree = len(set(labels)) == 1
        flagged = any(l not in ("correct", "cannot_tell") for l in labels)
        st["已完成组"] += 1
        st["两遍一致" if agree else "两遍不一致"] += 1
        st["引语全部可核" if all(quotes_ok) else "有引语在原文里找不到"] += 1
        if flagged:
            st["至少一遍标了毛病"] += 1
        rows.append({"id": iid, "group": it["group"], "dd": it["dd"], "case_name": it["case_name"],
                     "labels": "|".join(labels), "agree": agree, "quotes_ok": all(quotes_ok),
                     "notes": " || ".join((r.get("note") or "").replace("\n", " ") for r in runs),
                     "quotes": " || ".join((r.get("evidence_quote") or "").replace("\n", " ") for r in runs)})
    rows.sort(key=lambda r: (not any(l not in ("correct", "cannot_tell") for l in r["labels"].split("|")),
                             not r["quotes_ok"], -r["dd"]))
    p = os.path.join(OUT, "A_review.csv")
    with io.open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["id"])
        w.writeheader()
        w.writerows(rows)
    return ["## A 案名挑错", "解析失败的结果行：%d" % bad] + \
           ["- %s：%d" % (k, v) for k, v in st.items()] + ["人工队列 → %s" % os.path.relpath(p, ROOT)]


def main():
    txt = "\n".join(verify_c() + [""] + verify_a())
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print(txt)
    io.open(os.path.join(OUT, "summary.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    sys.exit(main())
