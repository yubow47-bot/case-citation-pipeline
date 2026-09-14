# -*- coding: utf-8 -*-
"""R3 收尾核对（只读）：按**组内容签名**比较两轮 dd 与 kept；kept 一律性；
group_only 归因；新增来源地按缩写分布。用法：
    python implementation/_probe_r3_verify.py --before data/run_20260913_r2i \
        --after data/run_20260913_r3c
"""
import argparse
import csv
import json
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(d):
    sig, kept, gid_amb, by_abbr = {}, {}, {}, Counter()
    with open(os.path.join(d, "decide_out", "cross_court", "decided.csv"),
              encoding="utf-8", newline="") as f:
        members = defaultdict(list)
        meta = {}
        for r in csv.DictReader(f):
            g = r["merged_group_id"]
            members[g].append("%s|%s" % (r["court"], r["merge_key"]))
            meta[g] = (int(r["distinct_decisions_count"] or 0),
                       r["group_foreign_status"])
            if (r.get("member_origin_ambiguous_basis") or ""):
                gid_amb[g] = r["member_origin_ambiguous_basis"]
            if (r.get("member_origin_basis") or "") == "exclusive_reporter_scope":
                by_abbr[r["merge_key"].split("|")[2]] += 1
        for g, ms in members.items():
            sig[" ; ".join(sorted(ms))] = (meta[g][0], meta[g][1],
                                           gid_amb.get(g, ""), g)
    with open(os.path.join(d, "select_out", "selected.csv"),
              encoding="utf-8", newline="") as f:
        per = defaultdict(set)
        for r in csv.DictReader(f):
            per[r["merged_group_id"]].add(r["kept"])
        for g, v in per.items():
            kept[g] = ("true" in v, len(v) > 1)
    return sig, kept, by_abbr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    a = ap.parse_args()
    b_dir = a.before if os.path.isabs(a.before) else os.path.join(ROOT, a.before)
    a_dir = a.after if os.path.isabs(a.after) else os.path.join(ROOT, a.after)
    bs, bk, _ = load(b_dir)
    as_, ak, abbr = load(a_dir)
    print("组数：before %d  after %d" % (len(bs), len(as_)))
    print("kept 非均一的组：before %d  after %d"
          % (sum(1 for v in bk.values() if v[1]),
             sum(1 for v in ak.values() if v[1])))
    common = set(bs) & set(as_)
    up = [s for s in common if as_[s][0] > bs[s][0]]
    down = [s for s in common if as_[s][0] < bs[s][0]]
    print("共同签名 %d；dd 升 %d / 降 %d" % (len(common), len(up), len(down)))
    print("  升幅 top5:", sorted((as_[s][0] - bs[s][0], bs[s][0], as_[s][0])
                                for s in up)[-5:])
    print("  降幅 top5:", sorted((bs[s][0] - as_[s][0], bs[s][0], as_[s][0])
                                for s in down)[-5:])
    kg_up = [s for s in common if ak.get(as_[s][3], (False,))[0]
             and not bk.get(bs[s][3], (False,))[0]]
    kg_dn = [s for s in common if bk.get(bs[s][3], (False,))[0]
             and not ak.get(as_[s][3], (False,))[0]]
    print("kept false→true 共同签名 %d；true→false %d" % (len(kg_up), len(kg_dn)))
    only_a, only_b = set(as_) - set(bs), set(bs) - set(as_)
    print("签名只在新 run %d（kept %d）；只在旧 run %d（kept %d）"
          % (len(only_a), sum(1 for s in only_a if ak.get(as_[s][3], (False,))[0]),
             len(only_b), sum(1 for s in only_b if bk.get(bs[s][3], (False,))[0])))
    kept_after = sum(1 for v in ak.values() if v[0])
    kept_before = sum(1 for v in bk.values() if v[0])
    print("kept 组数（按 gid）：before %d  after %d  Δ%+d"
          % (kept_before, kept_after, kept_after - kept_before))
    print("\n新增 exclusive_reporter_scope 成员行按缩写（前 20）：")
    for k, v in abbr.most_common(20):
        print("   %-10s %6d" % (k, v))
    print("   合计 %d" % sum(abbr.values()))


if __name__ == "__main__":
    main()
