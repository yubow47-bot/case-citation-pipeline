# -*- coding: utf-8 -*-
"""preview_prose_trim.py — 案名左侧散文污染的离线预演（审计环，可重放；PROBLEMS #61 / Task 4）

`admit_candidate` 从引证往回找最近的 `;` `:` 换行 当案名起点；近旁没有这几个分隔符时，
候选会把整整一句散文吞进来（`strict liability (presumably on the basis of Rylands v.
Fletcher`）。本工具把拟采用的「左切」规则实现在这里，套在现成的 `candidate_case_name`
上，秒级看出会改哪些名字、会不会误伤合法案名（法语机构名、长机构名）。

用法
    python audit/preview_prose_trim.py                        # 全部改动逐条列出
    python audit/preview_prose_trim.py --dir <classified.csv 目录>
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

from classify import V_RE, _CONNECTOR                          # noqa: E402

PUNCT = "().,&;:'’“”[]"
WORD = re.compile(r"\S+")

# 「切点词表」：**不能**当切点的词 = 会合法出现在当事人名称内部的介词/冠词。
# 它比 classify._CONNECTOR 窄：in/to/by/on/at/with/from 这些**可以**当切点，
# 因为散文里「…said in McIntosh v. Parent」「…decision of the Supreme Court in Sattva
# Capital Corp. v. …」的边界正是这些词；把它们当连接词会让切点落在更早的地方
# （实测会切出「Supreme Court in Sattva Capital Corp.」这种半句）。
_PROSE_CONNECTOR = frozenset("""
of the and a an for de la le les du des et en aux d l
""".split())


def _name_like_tok(tok):
    """token 像不像当事人名称的一部分（含大写 / 不含字母 / 是宽连接词）。"""
    if any(c.isupper() for c in tok):
        return True
    if not any(c.isalpha() for c in tok):
        return True
    return tok.strip(PUNCT).lower() in _CONNECTOR


def _between_ok(text):
    """切点右侧到 v. 之间是不是一段非空的「像案名」词序列。"""
    toks = [m.group(0) for m in WORD.finditer(text)]
    return bool(toks) and all(_name_like_tok(t) for t in toks)


def trim_prose(name, connector=_PROSE_CONNECTOR, drop_bad=True, need=3):
    """返回 (新名字 or None 表示应判无名, 是否触发过)。

    切点：左侧最后一个**小写非名称连接词**，且它到 v. 之间必须是一段非空的
    「像案名」词序列——否则往前退到下一个切点，全都不成立就**不动**。
    这条「between 必须像案名」的闸是关键：法语机构名 `Québec (Procureur général)`、
    `Union des employés de commerce` 的当事人一侧本身含小写词，没有这道闸会被切掉，
    甚至（在 drop 模式下）判成无名。"""
    last = None
    for m in V_RE.finditer(name):
        last = m
    if last is None:
        return name, False
    left = name[:last.start()]
    cuts = []
    for m in WORD.finditer(left):
        w = m.group(0).strip(PUNCT)
        if w and w.islower() and w not in connector:
            cuts.append(m.end())
    if len(cuts) < need:
        return name, False
    cut = None
    for c in reversed(cuts):
        if _between_ok(left[c:]):
            cut = c
            break
    if cut is None:
        return name, False
    rest = name[cut:]
    while True:
        m = re.match(r"[\s,;:.!?&'’“”()\[\]]+", rest)
        if m and m.end():
            rest = rest[m.end():]
            continue
        m = re.match(r"\[\s*\d+\s*\]|\d+\s*[).]|\d+", rest)      # 段落编号/页码残尾
        if m and m.end():
            rest = rest[m.end():]
            continue
        m = re.match(r"([^\W\d_]+)", rest, re.UNICODE)
        if m and m.group(1).lower() in _CONNECTOR and m.group(1).lower() not in ("v", "vs"):
            rest = rest[m.end():]
            continue
        break
    if not rest or not rest[:1].isupper():
        return (None if drop_bad else name), True
    return rest, True


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", default=os.path.join(ROOT, "data", "classify_out"))
    ap.add_argument("--samples", type=int, default=40)
    ap.add_argument("--legit", action="store_true",
                    help="按名字去重列出「触发规则」的全部名字（供人判断哪些是误伤）")
    ap.add_argument("--out")
    a = ap.parse_args()
    changed, dropped, kept = [], [], Counter()
    seen = {}
    for court in ("SCC", "ONCA"):
        with io.open(os.path.join(a.dir, court, "classified.csv"), encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                old = (r.get("candidate_case_name") or "").strip()
                if not old:
                    continue
                new, fired = trim_prose(old)
                if not fired or new == old:
                    continue
                seen.setdefault(old, (new, court, r.get("raw_string")))
                if new:
                    changed.append((court, r.get("raw_string"), old, new))
                else:
                    dropped.append((court, r.get("raw_string"), old))
    print("改动 %d 行（其中改为无名 %d 行）；去重后 %d 个不同名字"
          % (len(changed) + len(dropped), len(dropped), len(seen)))
    if a.legit:
        lines = []
        for old, (new, court, raw) in sorted(seen.items()):
            lines.append("[%s] %-24s\n    旧 %r\n    新 %r" % (court, (raw or "")[:24], old, new or "(改判无名)"))
        text = "\n".join(lines)
        dest = a.out or os.path.join(ROOT, "data", "audit", "trim_all.txt")
        io.open(dest, "w", encoding="utf-8").write(text + "\n")
        print("全部去重改动 -> %s" % dest)
        return
    print("\n== 改为无名（前 %d）==" % a.samples)
    for c, raw, old in dropped[:a.samples]:
        print("   [%s] %-26s %r" % (c, (raw or "")[:26], old))
    print("\n== 改名（前 %d）==" % a.samples)
    for c, raw, old, new in changed[:a.samples]:
        print("   [%s] %-26s\n       旧 %r\n       新 %r" % (c, (raw or "")[:26], old, new))


if __name__ == "__main__":
    sys.exit(main())
