# -*- coding: utf-8 -*-
"""临时：把 Stage 0 上限按「本轮可写行 / 未写行」拆开，给出实际兑现预测。"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(ROOT, "data", "coverage_out", "stage0_r2i.json"),
                   encoding="utf-8"))
m1a = d["M1a_mentions_by_abbr_full"]
nn = d["M1_netnew_groups_by_abbr_full"]
WRITABLE = {"scr", "canscr", "fc", "fcr"}
MIXED = {"ac", "appcas", "er", "wlr", "kb", "qb", "ch", "chd", "qbd", "aller",
         "crappr", "lrhl", "lrqb", "chapp", "lrpc", "us", "clr", "p", "alr",
         "nzlr", "f", "fsupp"}

tot_nn = sum(nn.values())
w = sum(nn.get(k, 0) for k in WRITABLE)
m = sum(nn.get(k, 0) for k in MIXED)
print("净新增组上限（全部）: %d" % tot_nn)
print("本轮可写行覆盖 (%s): %d (%.1f%%)  提及 %d"
      % (",".join(sorted(WRITABLE)), w, 100.0 * w / tot_nn,
         sum(m1a.get(k, 0) for k in WRITABLE)))
print("已判 mixed/不可写覆盖: %d (%.1f%%)" % (m, 100.0 * m / tot_nn))
print()
print("未写但量级最大的（组 / 提及）:")
rest = [(k, v, m1a.get(k, 0)) for k, v in nn.items()
        if k not in WRITABLE and k not in MIXED and v >= 300]
for k, v, mm in sorted(rest, key=lambda x: -x[1]):
    print("   %-12s %6d 组  %7d 提及" % (k, v, mm))
print("   小计 %d 组" % sum(v for _, v, _ in rest))
print()
print("可写行明细:")
for k in sorted(WRITABLE):
    print("   %-8s %6d 组  %7d 提及" % (k, nn.get(k, 0), m1a.get(k, 0)))
