# -*- coding: utf-8 -*-
"""临时（修正版）：按**组内容签名**（不是 (court,merge_key)——同一键可被按判决拆成多组）
比较两轮的 dd 与 kept，并给出升降规模。"""
import csv
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "data", "run_20260913_r3a")
B = os.path.join(ROOT, "data", "run_20260913_r2i")


def load(d):
    """→ sig -> (dd, foreign_status, ambiguous, gid)"""
    gid_members, gid_dd, gid_st, gid_amb = {}, {}, {}, {}
    with open(os.path.join(d, "decide_out", "cross_court", "decided.csv"),
              encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            g = r["merged_group_id"]
            gid_members.setdefault(g, []).append("%s|%s" % (r["court"],
                                                            r["merge_key"]))
            gid_dd[g] = int(r["distinct_decisions_count"] or 0)
            gid_st[g] = r["group_foreign_status"]
            if (r.get("member_origin_ambiguous_basis") or ""):
                gid_amb[g] = r["member_origin_ambiguous_basis"]
    sig = {}
    for g, ms in gid_members.items():
        sig[" ; ".join(sorted(ms))] = (gid_dd[g], gid_st[g], gid_amb.get(g, ""), g)
    kept = {}
    with open(os.path.join(d, "select_out", "selected.csv"),
              encoding="utf-8", newline="") as f:
        per = defaultdict(set)
        for r in csv.DictReader(f):
            per[r["merged_group_id"]].add(r["kept"])
        for g, v in per.items():
            kept[g] = (("true" in v), len(v) > 1)
    return sig, kept


bs, bk = load(B)
as_, ak = load(A)
print("组数：before %d  after %d" % (len(bs), len(as_)))
print("kept 非均一的组：before %d  after %d"
      % (sum(1 for v in bk.values() if v[1]), sum(1 for v in ak.values() if v[1])))

common = set(bs) & set(as_)
up = [s for s in common if as_[s][0] > bs[s][0]]
down = [s for s in common if as_[s][0] < bs[s][0]]
print("\n共同签名 %d；dd 升 %d / 降 %d" % (len(common), len(up), len(down)))
print("dd 升幅 top5：", sorted((as_[s][0] - bs[s][0], bs[s][0], as_[s][0])
                              for s in up)[-5:])
print("dd 降幅 top5：", sorted((bs[s][0] - as_[s][0], bs[s][0], as_[s][0])
                              for s in down)[-5:])
for s in sorted(down, key=lambda s: as_[s][0] - bs[s][0])[:2]:
    print("   降样例 before dd=%d after dd=%d members=%s"
          % (bs[s][0], as_[s][0], s[:200]))

kg_up = [s for s in common if ak.get(as_[s][3], (False,))[0]
         and not bk.get(bs[s][3], (False,))[0]]
kg_down = [s for s in common if bk.get(bs[s][3], (False,))[0]
           and not ak.get(as_[s][3], (False,))[0]]
print("\nkept 由 false→true 的共同签名 %d；true→false %d" % (len(kg_up),
                                                             len(kg_down)))
only_a = set(as_) - set(bs)
only_b = set(bs) - set(as_)
print("签名只在新 run %d（其中 kept=%d）；只在旧 run %d（其中 kept=%d）"
      % (len(only_a), sum(1 for s in only_a if ak.get(as_[s][3], (False,))[0]),
         len(only_b), sum(1 for s in only_b if bk.get(bs[s][3], (False,))[0])))
print("新签名 kept 样例：")
n = 0
for s in only_a:
    if ak.get(as_[s][3], (False,))[0]:
        print("   dd=%d  %s" % (as_[s][0], s[:170]))
        n += 1
        if n >= 6:
            break
print("旧签名 kept 样例（被合并掉的高门槛组）：")
n = 0
for s in only_b:
    if bk.get(bs[s][3], (False,))[0]:
        print("   dd=%d  %s" % (bs[s][0], s[:170]))
        n += 1
        if n >= 6:
            break
