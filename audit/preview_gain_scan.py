# -*- coding: utf-8 -*-
"""preview_gain_scan.py — 预演所得「新名字」的垃圾扫描（审计环，可重放）

标记规则只允许**一个标记段**成为案名；本扫描独立地检验这一点有没有漏：
对每条「无名 -> 有名」的行，检查新名字里有没有**小写非连接词**（散文的特征）、
有没有句读点后接大写（跨句吞并的特征）、以及长度分布。任何一条命中都打印出来。

    python audit/preview_gain_scan.py --mode marker_if_no_v
"""
import argparse
import csv
import io
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
csv.field_size_limit(10 ** 9)
from preview_case_name import new_name, _CONNECTOR, _MARKER_ANON_RE   # noqa: E402

WORD = re.compile(r"(?<![^\W\d_’'])\b[a-z]{3,}\b", re.UNICODE)
SENT = re.compile(r"[a-z]{2}\.\s+[A-Z][a-z]{2,}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", default="marker_if_no_v")
    ap.add_argument("--samples", type=int, default=12)
    ap.add_argument("--distinct", action="store_true",
                    help="按名字去重打印（软连字符先归一），供人逐条眼验")
    ap.add_argument("--dir", default=os.path.join(ROOT, "data", "classify_out"),
                    help="读哪一份 classified.csv（比对改动前用改动前的快照目录）")
    a = ap.parse_args()
    lower, sent, longest = [], [], []
    n = 0
    kinds = Counter()
    distinct = {"小写非连接词": Counter(), "跨句": Counter()}
    sample = {}
    for court in ("SCC", "ONCA"):
        with io.open(os.path.join(a.dir, court, "classified.csv"),
                     encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                old = (r.get("candidate_case_name") or "").strip()
                if old:
                    continue
                new, _, mk = new_name(r.get("preceding_text") or "", a.mode)
                if not new:
                    continue
                n += 1
                kinds[mk] += 1
                flat = new.replace("\xad", "")
                bad = [w for w in WORD.findall(flat)
                       if w.islower() and w not in _CONNECTOR]
                if bad:
                    lower.append((court, r.get("raw_string"), flat, sorted(set(bad))[:6]))
                    distinct["小写非连接词"][flat] += 1
                    sample.setdefault("小写非连接词", (court, r.get("raw_string"), flat))
                if SENT.search(flat):
                    sent.append((court, r.get("raw_string"), flat))
                    distinct["跨句"][flat] += 1
                    sample.setdefault("跨句", (court, r.get("raw_string"), flat))
                if len(new) > 95:
                    longest.append((len(new), court, mk, r.get("raw_string"), flat))
    print("新得名字 %d 行（prefix %d / tail_re %d / anon %d）"
          % (n, kinds["prefix"], kinds["tail_re"], kinds["anon"]))
    for key in ("小写非连接词", "跨句"):
        cnt = distinct[key]
        print("%s：%d 行 / %d 个不同名字" % (key, len([1 for x in (lower if key == "小写非连接词" else sent)]), len(cnt)))
        if a.distinct:
            for nm, c in cnt.most_common():
                print("   %4d  %r" % (c, nm))
        else:
            for row in (lower if key == "小写非连接词" else sent)[:a.samples]:
                print("   [%s] %s\n      名=%r\n      词=%s" % row)
    longest.sort(reverse=True)
    print("最长 10 条：")
    for L, c, mk, raw, nm in longest[:10]:
        print("   [长 %d][%s %s] %s\n      %r" % (L, c, mk, raw, nm))


if __name__ == "__main__":
    sys.exit(main())
