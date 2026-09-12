# -*- coding: utf-8 -*-
"""preview_case_name.py — 案名切分改动的离线预演与核查（审计环，可重放；不写任何生产线文件）

改 `pipeline/classify.py` 之前，先用现成的 `classified.csv`（它有 `preceding_text`）把新
规则跑一遍，看**有名行会不会被改名**。全量重跑一次分类层要好几分钟，预演是秒级——
#57、#58 都是这么先预演再落地的。

五个模式（都是为了「改名字之前先量、改完再逐条看」这一件事，故合在一个文件里）：

    无参数            两种切分模式的整体分档对比（标记优先 / 段内无 v. 才认标记）
    --renames         逐条列出会改名的行（旧名、新名、上文），供人眼验是订正还是误伤
    --mode-diff       逐条列出两种模式结果不同的行
    --scan            扫「新得的名字」里的散文特征（小写非连接词 / 跨句吞并），并打印最长的一批
    --vs-prod         预演实现与生产线实现**逐行比对**：两份实现数字不同必须能解释（#58 的教训）

用法
    python audit/preview_case_name.py --renames --out data/audit/renames.txt
    python audit/preview_case_name.py --scan --distinct --dir data/audit/before_task4
    python audit/preview_case_name.py --vs-prod
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

LEAD = " \t\r\n[(«\"'‘“«…."          # 与 classify._ADMIT_LEAD_CHARS 同一集合（含 [ 与 (）

_MARKER_PREFIX_RE = re.compile(r"^(?:Reference\s+re|Re|In\s+re|Ex\s+parte)\s+(?=[A-Z])")
_MARKER_TAIL_RE = re.compile(r"\(Re\)\s*[.,]?\s*$")
_MARKER_ANON_RE = re.compile(r"^(?:Droit\s+de\s+la\s+famille|LSJPA)\s*[—–-]")

_CONNECTOR = frozenset("""
of the and a an for in on at by to with from v vs re ex parte de la le du des et en
dite dit inc ltd ltee co corp corporation company limited llc lp plc sa srl gmbh no nos
st ste saint al supra
""".split())

# --scan 用的散文信号。软连字符先归一，否则 OCR 断词会被当成小写词
_WORD = re.compile(r"(?<![^\W\d_’'])\b[a-z]{3,}\b", re.UNICODE)
_SENT = re.compile(r"[a-z]{2}\.\s+[A-Z][a-z]{2,}")


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
    """mode='marker_first' 标记优先；'marker_if_no_v' 段内有 v. 就仍走旧路（最终采用）。"""
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
    row = {"preceding_text": pre, "candidate_case_name": ""}
    classify.split_case_name(row)
    return row.get("candidate_case_name") or "", row.get("name_rejected_reason") or "", ""


def _rows(d):
    for court in ("SCC", "ONCA"):
        p = os.path.join(d, court, "classified.csv")
        if not os.path.exists(p):
            continue
        with io.open(p, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                yield court, r


def mode_buckets(a):
    for mode in ("marker_first", "marker_if_no_v"):
        buckets, ex = Counter(), {}
        for court, r in _rows(a.dir):
            old = (r.get("candidate_case_name") or "").strip()
            new, _, mk = new_name(r.get("preceding_text") or "", mode)
            if old and new and old == new:
                k = "有名 -> 同名"
            elif not old and new:
                k = "无名 -> 有名 (%s)" % (mk or "?")
            elif old and not new:
                k = "有名 -> 无名 **"
            elif old and new != old:
                k = "有名 -> 不同名 **"
            else:
                k = "无名 -> 无名"
            buckets[k] += 1
            if k.startswith("有名 ->") and k != "有名 -> 同名" and len(ex.get(k, [])) < a.samples:
                ex.setdefault(k, []).append((court, r.get("raw_string"), old, new,
                                             (r.get("preceding_text") or "")[-160:]))
        print("\n########## mode=%s ##########" % mode)
        for k, v in buckets.most_common():
            print("  %-24s %7d" % (k, v))
        for k in ("有名 -> 不同名 **", "有名 -> 无名 **"):
            for c, raw, old, new, pre in ex.get(k, []):
                print("   [%s] raw=%r\n        旧=%r\n        新=%r\n        pre=…%r" % (c, raw, old, new, pre))


def mode_renames(a):
    out = []
    for court, r in _rows(a.dir):
        old = (r.get("candidate_case_name") or "").strip()
        new, _, mk = new_name(r.get("preceding_text") or "", a.mode)
        if a.scan or (old and new and new != old):
            out.append((court, old, new, mk, r.get("raw_string"),
                        r.get("preceding_text") or "", r.get("source_decision_citation")))
    print("改名 %d 行" % len(out))
    if a.out:
        io.open(a.out, "w", encoding="utf-8").write("\n".join(
            "[%s] %s raw=%r\n    旧 %r\n    新 %r（%s）\n    pre…%r"
            % (c, sdc, raw, o, n, mk, pre[-200:]) for c, o, n, mk, raw, pre, sdc in out) + "\n")
        print("-> %s" % a.out)
    else:
        for c, o, n, mk, raw, pre, sdc in out[:a.samples]:
            print("[%s] %s raw=%r\n    旧 %r\n    新 %r（%s）" % (c, sdc, raw, o, n, mk))


def mode_mode_diff(a):
    n = 0
    for court, r in _rows(a.dir):
        pre = r.get("preceding_text") or ""
        n1, _, m1 = new_name(pre, "marker_if_no_v")
        n2, _, _ = new_name(pre, "marker_first")
        if n1 == n2:
            continue
        n += 1
        if a.out:
            pass
        elif n <= a.samples:
            print("[%s] raw=%r  标记=%s\n    无v才认 %r\n    标记优先 %r"
                  % (court, r.get("raw_string"), m1, n1, n2))
    print("两种模式结果不同的行：%d" % n)


def mode_scan(a):
    lower, sent, longest = [], [], []
    kinds = Counter()
    distinct = {"小写非连接词": Counter(), "跨句": Counter()}
    n = 0
    for court, r in _rows(a.dir):
        old = (r.get("candidate_case_name") or "").strip()
        if old:
            continue
        new, _, mk = new_name(r.get("preceding_text") or "", a.mode)
        if not new:
            continue
        n += 1
        kinds[mk] += 1
        flat = new.replace("\xad", "")
        bad = [w for w in _WORD.findall(flat) if w.islower() and w not in _CONNECTOR]
        if bad:
            lower.append((court, r.get("raw_string"), flat, sorted(set(bad))[:6]))
            distinct["小写非连接词"][flat] += 1
        if _SENT.search(flat):
            sent.append((court, r.get("raw_string"), flat))
            distinct["跨句"][flat] += 1
        if len(new) > 95:
            longest.append((len(new), court, mk, r.get("raw_string"), flat))
    print("新得名字 %d 行（prefix %d / tail_re %d / anon %d）"
          % (n, kinds["prefix"], kinds["tail_re"], kinds["anon"]))
    for key, bucket in (("小写非连接词", lower), ("跨句", sent)):
        print("%s：%d 行 / %d 个不同名字" % (key, len(bucket), len(distinct[key])))
        if a.distinct:
            for nm, c in distinct[key].most_common():
                print("   %4d  %r" % (c, nm))
        else:
            for row in bucket[:a.samples]:
                print("   [%s] %s\n      名=%r\n      词=%s" % row)
    longest.sort(reverse=True)
    print("最长 10 条：")
    for L, c, mk, raw, nm in longest[:10]:
        print("   [长 %d][%s %s] %s\n      %r" % (L, c, mk, raw, nm))


def mode_vs_prod(a):
    n, diff = 0, 0
    for court, r in _rows(a.dir):
        n += 1
        pre = r.get("preceding_text") or ""
        pv, _, _ = new_name(pre, "marker_if_no_v")
        row = {"preceding_text": pre, "candidate_case_name": ""}
        classify.split_case_name(row)
        pr = row.get("candidate_case_name") or ""
        if pv == pr:
            continue
        diff += 1
        if diff <= a.samples:
            print("[%s] %s raw=%r\n    预演=%r\n    生产线=%r"
                  % (court, r.get("source_decision_citation"), r.get("raw_string"), pv, pr))
    print("总行 %d，两份实现不一致 %d 行（不一致必须能解释）" % (n, diff))
    return 1 if diff else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", default=os.path.join(ROOT, "data", "classify_out"),
                    help="读哪一份 classified.csv（比对改动前用改动前的快照目录）")
    ap.add_argument("--mode", default="marker_if_no_v",
                    choices=["marker_first", "marker_if_no_v"])
    ap.add_argument("--samples", type=int, default=8)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--renames", action="store_true")
    g.add_argument("--mode-diff", action="store_true")
    g.add_argument("--scan", action="store_true")
    g.add_argument("--vs-prod", action="store_true")
    ap.add_argument("--distinct", action="store_true", help="--scan：按名字去重打印")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.renames:
        mode_renames(a)
    elif a.mode_diff:
        mode_mode_diff(a)
    elif a.scan:
        mode_scan(a)
    elif a.vs_prod:
        return mode_vs_prod(a)
    else:
        mode_buckets(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
