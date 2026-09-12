# -*- coding: utf-8 -*-
"""case_name_gap_audit.py — 无 v. 案名的缺口测量（审计环，可重放；PROBLEMS #58/#59/Task 2-4）

只读分类层产出，不改任何东西。回答三个问题：

1. 切不出案名的行，**紧邻引证的那一段**（从它前面最近的 `;`/`:`/换行 起）以什么开头？
   按首词分档计数——这是「哪些前缀标记值得进闭集」的实测依据。
2. 候选前缀标记（Reference re / Re / In re / Ex parte / 魁北克匿名名 …）各命中多少行，
   清洗后各自留下什么名字（每档打几个样本供人眼验）。
3. `(Re)` 后缀形、以及「左边当事人一侧带散文信号」的污染形各有多少行。

用法
    python audit/case_name_gap_audit.py                     # 全量分档
    python audit/case_name_gap_audit.py --top 40            # 首词档打前 40 个
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
LEAD = " \t\r\n\"'‘“«…."

# 候选标记（只在段首认）
MARKERS = [
    ("Reference re", re.compile(r"^Reference\s+re\s+(?=[A-Z])")),
    ("Re", re.compile(r"^Re\s+(?=[A-Z])")),
    ("In re", re.compile(r"^In\s+re\s+(?=[A-Z])")),
    ("Ex parte", re.compile(r"^Ex\s+parte\s+(?=[A-Z])")),
    ("Droit de la famille —", re.compile(r"^Droit\s+de\s+la\s+famille\s+[—–-]")),
    ("LSJPA —", re.compile(r"^LSJPA\s+[—–-]")),
]
# 可能的同族匿名名（量一下，别凭印象加）
ANON_PROBE = re.compile(r"^([A-Z][A-Za-z]{1,9})\s*[—–-]\s*\d")
TAIL_RE = re.compile(r"\(Re\)\s*[.,]?\s*$")


def segment(pre):
    """本行引证所在的那一段：从它前面最近的 ; : 换行 起，到 preceding_text 末尾。"""
    sep = max(pre.rfind(";"), pre.rfind(":"), pre.rfind("\n"))
    s = pre[sep + 1:]
    i = 0
    while i < len(s) and (s[i].isspace() or s[i] in LEAD):
        i += 1
    return s[i:]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()

    first_word = Counter()
    marker_hits = Counter()
    marker_rows = {k: [] for k, _ in MARKERS}
    tail_re_rows = []
    anon_probe = Counter()
    anon_samples = {}
    unnamed = Counter()
    named = 0
    total = 0

    for court in ("SCC", "ONCA"):
        path = os.path.join(ROOT, "data", "classify_out", court, "classified.csv")
        if not os.path.exists(path):
            continue
        with io.open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                total += 1
                if (r.get("candidate_case_name") or "").strip():
                    named += 1
                    continue
                unnamed[r.get("name_rejected_reason") or "(空)"] += 1
                seg = segment(r.get("preceding_text") or "")
                if not seg:
                    first_word["(空段)"] += 1
                    continue
                w = re.match(r"[^\s]+", seg)
                first_word[(w.group(0) if w else "?")[:24]] += 1
                for label, rx in MARKERS:
                    if rx.match(seg):
                        marker_hits[label] += 1
                        if len(marker_rows[label]) < 12:
                            marker_rows[label].append((court, r.get("raw_string") or "", seg[:110]))
                        break
                if TAIL_RE.search(seg):
                    if len(tail_re_rows) < 12:
                        tail_re_rows.append((court, r.get("raw_string") or "", seg[:110]))
                m = ANON_PROBE.match(seg)
                if m:
                    anon_probe[m.group(1)] += 1
                    anon_samples.setdefault(m.group(1), (court, r.get("raw_string") or "", seg[:110]))

    print("分类层总行 %d，其中切出案名 %d，无名 %d" % (total, named, total - named))
    print("\n== 无名行的 name_rejected_reason ==")
    for k, v in unnamed.most_common():
        print("  %-34s %7d" % (k, v))
    print("\n== 无名行「引证所在段」首词（前 %d） ==" % a.top)
    for k, v in first_word.most_common(a.top):
        print("  %-34s %7d" % (repr(k), v))
    print("\n== 候选前缀标记命中（段首，须后随大写词） ==")
    for label, _ in MARKERS:
        print("  %-24s %7d" % (label, marker_hits[label]))
        for c, raw, s in marker_rows[label][:4]:
            print("      [%s] %-28s %s" % (c, raw[:26], s))
    print("\n== 段尾 (Re) 形 ==")
    for c, raw, s in tail_re_rows:
        print("      [%s] %-28s %s" % (c, raw[:26], s))
    print("\n== 疑似其他匿名名（大写缩写 + 破折号 + 数字） ==")
    for k, v in anon_probe.most_common(20):
        print("  %-14s %7d   e.g. %s" % (k, v, anon_samples[k][2][:80]))


if __name__ == "__main__":
    sys.exit(main())
