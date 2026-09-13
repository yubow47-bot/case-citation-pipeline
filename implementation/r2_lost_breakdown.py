# -*- coding: utf-8 -*-
"""r2_lost_breakdown.py — 3.2(b)「counted nowhere」桶的分解与样例

按：旧行是否带已解析法域、旧形状、新路线同键候选的仲裁状态分解；给样例。
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD = os.path.join(ROOT, "data")
COURTS = ("SCC", "ONCA")


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main(run_dir):
    status_by_key = {}
    counted_keys = set()
    for court in COURTS:
        for m in rows(os.path.join(run_dir, "merge_out", court,
                                   "mentions_candidates.csv")):
            k = (m["source_decision_citation"], m["match_start_offset"],
                 m["match_end_offset"], m["shape_name"], m["raw_string"])
            status_by_key.setdefault(k, []).append(m["arbitration_status"])
            if m["arbitration_status"] == "counted":
                counted_keys.add(k)
    counted_ivs = defaultdict(list)
    for (sdc, s0, e0, _sh, _rw) in counted_keys:
        counted_ivs[sdc].append((int(s0), int(e0)))
    for s in counted_ivs:
        counted_ivs[s].sort()
    iv_starts = {s: [x[0] for x in v] for s, v in counted_ivs.items()}

    lost = []
    for court in COURTS:
        for r in rows(os.path.join(OLD, "classify_out", court, "classified.csv")):
            if r.get("rejected_reason") or r.get("self_citation") == "true":
                continue
            sdc = r["source_decision_citation"]
            k = (sdc, r["match_start_offset"], r["match_end_offset"],
                 r["shape_name"], r["raw_string"])
            if k in counted_keys:
                continue
            s, e = int(r["match_start_offset"]), int(r["match_end_offset"])
            ivs = counted_ivs.get(sdc, [])
            starts = iv_starts.get(sdc, [])
            j = bisect_left(starts, e) if starts else 0
            i0 = j
            while i0 > 0 and starts[i0 - 1] > s - 300:
                i0 -= 1
            overlap = any(iv[0] < e and s < iv[1] for iv in ivs[i0:j])
            if overlap:
                continue                     # 3 类，不在本分解内
            lost.append((k, r))

    by_jur = Counter()
    by_shape = Counter()
    by_new_status = Counter()
    supported_samples = []
    for k, r in lost:
        supported = r.get("jurisdiction") not in ("", "UNSUPPORTED")
        by_jur["supported" if supported else "unsupported"] += 1
        by_shape[r["shape_name"]] += 1
        sts = status_by_key.get(k, ["<not_enumerated>"])
        st = "+".join(sorted(set(sts)))
        by_new_status[st] += 1
        if supported and len(supported_samples) < 15:
            supported_samples.append({
                "sdc": k[0], "raw": k[4], "shape": k[3],
                "old_jur": r.get("jurisdiction"),
                "new_status": st,
                "sdc_row_hint": k[0]})

    out = {"total_lost_nowhere": len(lost), "by_old_jurisdiction": dict(by_jur),
           "by_old_shape": dict(by_shape.most_common()),
           "by_new_arbitration_status": dict(by_new_status.most_common(12)),
           "supported_samples": supported_samples}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "r2_lost_breakdown.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1)[:3500])
    print("written", path)


from bisect import bisect_left

if __name__ == "__main__":
    main(sys.argv[1])
