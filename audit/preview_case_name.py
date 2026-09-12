# -*- coding: utf-8 -*-
"""preview_case_name.py — 案名切分改动的离线预演（审计环，可重放；不写任何生产线文件）

改 `pipeline/classify.py` 之前，先用现成的 `classified.csv`（它有 preceding_text）把新
规则跑一遍，看**有名行会不会被改名**。全量重跑一次分类层要好几分钟，预演是秒级——
#57 就是这么先预演再落地的。

用法
    python audit/preview_case_name.py                     # 预演 PROBLEMS #58 的标记规则
    python audit/preview_case_name.py --samples 10
"""
import argparse
import csv
import io
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
csv.field_size_limit(10 ** 9)

import classify                                                # noqa: E402
from normalize import nk                                       # noqa: E402

LEAD = " \t\r\n[(«\"'‘“«…."          # 与 classify._ADMIT_LEAD_CHARS 同一集合（含 [ 与 (）

_MARKER_PREFIX_RE = re.compile(r"^(?:Reference\s+re|Re|In\s+re|Ex\s+parte)\s+(?=[A-Z])")
_MARKER_TAIL_RE = re.compile(r"\(Re\)\s*[.,]?\s*$")
_MARKER_ANON_RE = re.compile(r"^(?:Droit\s+de\s+la\s+famille|LSJPA)\s*[—–-]")

# 「X (Re)」形：段尾的 (Re) 只说明案名在这里结束，不说明它从哪里开始——
#   段是「从上一个 ; : 换行 起」，句子跨过那个边界时整段散文都会被吞进来。
#   故从 (Re) 向左逐词走，遇「不像案名的一部分」的词就切在那里。
#   像案名的一部分 = 含大写字母 / 不含字母（数字、&、括号）/ 是连接词。
_CONNECTOR = frozenset("""
of the and a an for in on at by to with from v vs re ex parte de la le du des et en
dite dit inc ltd ltee co corp corporation company limited llc lp plc sa srl gmbh no nos
st ste saint al supra
""".split())
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def _is_boundary(t):
    """纯标点且含句读点（"." / ";"）——那是句子边界，不是案名的一部分。"""
    return (not any(c.isalnum() for c in t)) and any(c in ".;" for c in t)


def _name_like(t):
    """像案名的一部分：含大写字母 / 不含字母（数字、&、[5]）/ 是连接词。"""
    if any(c.isupper() for c in t):
        return True
    if not any(c.isalpha() for c in t):
        return True
    return t.lower().strip("().,&;:'’“”[]") in _CONNECTOR


def _walk_right(seg):
    """标记在段首时：从标记向右走，遇到句子边界或不像案名的词就切在那里。"""
    end = len(seg)
    for m in re.finditer(r"\S+", seg):
        if m.start() == 0:
            continue                     # 标记本身
        t = m.group(0)
        if _is_boundary(t) or not _name_like(t):
            end = m.start()
            break
    return seg[:end].strip()


def _re_span(seg):
    """从段尾 (Re) 向左走，返回案名起点在 seg 里的下标；走不到像样的起点就返回 -1。"""
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


def marker_of(seg):
    if _MARKER_PREFIX_RE.match(seg):
        return "prefix"
    if _MARKER_TAIL_RE.search(seg):
        return "tail_re" if _re_span(seg) >= 0 else ""
    if _MARKER_ANON_RE.match(seg):
        return "anon"
    return ""


def segment(pre):
    sep = max(pre.rfind(";"), pre.rfind(":"), pre.rfind("\n"))
    s = pre[sep + 1:]
    i = 0
    while i < len(s) and (s[i].isspace() or s[i] in LEAD):
        i += 1
    return s[i:]


def new_name(pre, mode):
    """mode='marker_first' 标记优先；'marker_if_no_v' 段内有 v. 就仍走旧路。"""
    seg = segment(pre)
    mk = marker_of(seg)
    if mk and (mode == "marker_first" or not classify.V_RE.search(seg)):
        if mk == "prefix":
            seg = _walk_right(seg)
        elif mk == "tail_re":
            i = _re_span(seg)
            if i > 0:
                seg = seg[i:]
        cand = seg.strip().rstrip(",").strip()
        cleaned, reject = classify.admit_candidate(cand)
        return (cleaned or ""), (reject or ""), mk
    # 旧路
    row = {"preceding_text": pre, "candidate_case_name": ""}
    classify.split_case_name(row)
    return row.get("candidate_case_name") or "", row.get("name_rejected_reason") or "", ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", default="marker_first", choices=["marker_first", "marker_if_no_v"])
    ap.add_argument("--samples", type=int, default=8)
    a = ap.parse_args()

    for mode in ("marker_first", "marker_if_no_v"):
        buckets = Counter()
        ex = {}
        mkstat = Counter()
        for court in ("SCC", "ONCA"):
            p = os.path.join(ROOT, "data", "classify_out", court, "classified.csv")
            with io.open(p, encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    old = (r.get("candidate_case_name") or "").strip()
                    new, rej, mk = new_name(r.get("preceding_text") or "", mode)
                    if old and new and old == new:
                        k = "有名 -> 同名"
                    elif not old and new:
                        k = "无名 -> 有名 (%s)" % (mk or "?")
                        mkstat["gain:" + (mk or "?")] += 1
                    elif old and not new:
                        k = "有名 -> 无名 **"
                    elif old and new != old:
                        k = "有名 -> 不同名 **"
                    else:
                        k = "无名 -> 无名"
                    buckets[k] += 1
                    if k.startswith("有名 ->") and k != "有名 -> 同名":
                        if len(ex.get(k, [])) < a.samples:
                            ex.setdefault(k, []).append((court, r.get("raw_string"), old, new,
                                                         r.get("preceding_text")[-160:]))
        print("\n########## mode=%s ##########" % mode)
        for k, v in buckets.most_common():
            print("  %-24s %7d" % (k, v))
        for k in ("有名 -> 不同名 **", "有名 -> 无名 **"):
            for c, raw, old, new, pre in ex.get(k, []):
                print("   [%s] raw=%r\n        旧=%r\n        新=%r\n        pre=…%r" % (c, raw, old, new, pre))


if __name__ == "__main__":
    sys.exit(main())
