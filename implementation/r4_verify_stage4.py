# -*- coding: utf-8 -*-
"""R4 Stage 4 独立复核：r3e（基线）vs r4c（交付 run）。只读。

检查项（对齐任务书 Stage 4 的 8 项报告要求）：
  1. 身份零变化：组集合、组员签名、dd 与 r3e 完全相同（Stage 1 未实现 → 不应有身份变化）
  2. 来源地变化只来自批次：新增判定组逐组追到 case_origin_manual.csv 的行
  3. FOREIGN 净变化 == 批次派生（不得有标注驱动）
  4. 标注：按法院/键级冲突/支撑量统计
  5. 守恒与清单
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from normalize import nk                                        # noqa: E402

BEFORE = os.path.join(ROOT, "data/run_20260913_r3e")
AFTER = os.path.join(ROOT, "data/run_20260914_r4c")


def load(run):
    p = os.path.join(run, "decide_out", "cross_court", "decided.csv")
    groups = defaultdict(list)
    with open(p, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            groups[r["merged_group_id"]].append(r)
    return groups


def sig(ms):
    return tuple(sorted({(m["court"], m["merge_key"]) for m in ms}))


print("== 1. 身份零变化（r3e vs r4c）==")
a, b = load(BEFORE), load(AFTER)
sa = {sig(v) for v in a.values()}
sb = {sig(v) for v in b.values()}
print("   组数：%d → %d" % (len(a), len(b)))
print("   成员签名集合：仅前 %d；仅后 %d" % (len(sa - sb), len(sb - sa)))
dda = {(sig(v), v[0].get("case_name_modal") or ""):
       v[0]["distinct_decisions_count"] for v in a.values()}
ddb = {(sig(v), v[0].get("case_name_modal") or ""):
       v[0]["distinct_decisions_count"] for v in b.values()}
print("   dd 变化（同签名+同名）：%d" % len(set(dda.items()) ^ set(ddb.items())))

def fstat(ms):
    """按覆盖口径派生 foreign_status：无国家=UNDETERMINED；CA=DOMESTIC_CA；其余=FOREIGN。"""
    c = (ms[0].get("group_origin_country") or "").strip()
    if not c:
        return "UNDETERMINED"
    return "DOMESTIC_CA" if c == "CA" else "FOREIGN"


print("\n== 2/3. 来源地变化只来自批次 ==")
oa = Counter(fstat(v) for v in a.values())
ob = Counter(fstat(v) for v in b.values())
print("   r3e:", dict(oa))
print("   r4c:", dict(ob))
for k in sorted(set(oa) | set(ob)):
    if oa[k] != ob[k]:
        print("   delta %-14s %+d" % (k, ob[k] - oa[k]))

manual = {}
with open(os.path.join(ROOT, "decisions", "case_origin_manual.csv"),
          encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        if (r.get("status") or "").strip() == "verified_research_agent":
            manual[r["normalized_key"]] = r

changed = []
for g, ms in b.items():
    st = fstat(ms)
    if st == "UNDETERMINED":
        continue
    old = a.get(g)
    ost = fstat(old) if old else "(新组)"
    if ost != "UNDETERMINED":
        continue
    hit = None
    for m in ms:
        for s in (m.get("canonical_string") or "", m["merge_key"]):
            k = nk(s)
            if k in manual:
                hit = (k, manual[k])
                break
        if hit:
            break
    changed.append((g, st, hit))
print("   由 UNDETERMINED 变为已定的组：%d" % len(changed))
print("   其中有**人工表行可溯**：%d" % sum(1 for _, _, h in changed if h))
print("   不可溯（必须为 0）：%d" % sum(1 for _, _, h in changed if not h))
print("   国家分布（按人工表行）：",
      dict(Counter(h[1]["origin_country"] for _, _, h in changed if h)))
for g, st, h in changed[:10]:
    if h:
        print("     %s -> %-12s %-26s key=%-14s (%s/%s)" % (
            g, st, h[1]["printed_citation"], h[1]["normalized_key"],
            h[1]["origin_country"], h[1]["origin_subdivision"] or "-"))

fc = [(g, st, h) for g, st, h in changed if st == "FOREIGN"]
print("   FOREIGN 改变组 %d；净变化 %+d；相等？%s"
      % (len(fc), ob["FOREIGN"] - oa["FOREIGN"],
         (ob["FOREIGN"] - oa["FOREIGN"]) == len(fc)))
cc = [(g, st, h) for g, st, h in changed if st == "DOMESTIC_CA"]
print("   DOMESTIC_CA 改变组 %d；净变化 %+d；相等？%s"
      % (len(cc), ob["DOMESTIC_CA"] - oa["DOMESTIC_CA"],
         (ob["DOMESTIC_CA"] - oa["DOMESTIC_CA"]) == len(cc)))

print("\n== 4. 标注统计（r4c merged 层键级）==")
des = Counter()
conf = 0
keys_with = 0
sup = 0
for court in ("SCC", "ONCA"):
    p = os.path.join(AFTER, "merge_out", court, "merged.csv")
    for r in csv.DictReader(open(p, encoding="utf-8", newline="")):
        c = (r.get("observed_deciding_court") or "").strip()
        if c:
            des[c] += 1
            keys_with += 1
        if (r.get("court_designation_conflict") or "") == "true":
            conf += 1
        sup += int(r.get("court_designation_support") or 0)
print("   键级 observed_deciding_court：", dict(des))
print("   带法院的键 %d；键级冲突 %d；支撑提及合计 %d" % (keys_with, conf, sup))

print("\n== 5. 守恒与清单 ==")
for tag, run in (("r3e", BEFORE), ("r4c", AFTER)):
    m = json.load(open(os.path.join(run, "run_manifest.json"),
                       encoding="utf-8"))
    st = m.get("stats", {})
    occ = st.get("occurrence_total") or st.get("occurrence_count") or \
        st.get("mentions_occurrence_total")
    print("   %s: status=%s occurrence_total=%s" % (tag, m.get("status"), occ))
    if tag == "r4c":
        for k in sorted(st):
            if "manual" in k or k.startswith("case_origin_determined"):
                print("      %s=%s" % (k, st[k]))