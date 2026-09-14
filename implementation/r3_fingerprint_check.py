# -*- coding: utf-8 -*-
"""R3 Stage 4：独立指纹复核 + 一致性三元组（只读，不信 run 自述）。

用法
    python implementation/r3_fingerprint_check.py --run data/run_20260913_r3a
    python implementation/r3_consistency.py --run data/run_20260913_r3a

指纹口径**逐字复刻** run_all.input_identity（pipeline/*.py + decisions/*.csv +
select_config.yaml + corpus/*.parquet + params），但由本脚本**自己重算**，不采信
manifest 的 `input_identity_verified_unchanged` 字段。

一致性三元组（沿用 r2 各轮的 0/0/0 口径）：
  1 行来源不一致：同一 merged_group_id 内 group_foreign_status 取值不唯一
  2 多国别非 CONFLICT：组级 origin 国家数 > 1 且 group_origin_status != CONFLICT
  3 同系统多键：同组内同 identifier 系统出现 > 1 个 merge_key
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

COURTS = ("SCC", "ONCA")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def recompute_identity(root, params):
    files = {}
    pipe = os.path.join(root, "pipeline")
    for n in sorted(os.listdir(pipe)):
        if re.fullmatch(r"[a-z_0-9]+\.py", n):
            files["pipeline/" + n] = sha256_file(os.path.join(pipe, n))
    dec = os.path.join(root, "decisions")
    if os.path.isdir(dec):
        for n in sorted(os.listdir(dec)):
            if n.endswith(".csv"):
                files["decisions/" + n] = sha256_file(os.path.join(dec, n))
    cfg = os.path.join(root, "select_config.yaml")
    if os.path.exists(cfg):
        files["select_config.yaml"] = sha256_file(cfg)
    for c in COURTS:
        p = os.path.join(root, "corpus", c + ".parquet")
        if os.path.exists(p):
            files["corpus/" + c + ".parquet"] = sha256_file(p)
    total = hashlib.sha256(
        ("".join("%s:%s\n" % (k, files[k]) for k in sorted(files))
         + "params:" + json.dumps(params or {}, sort_keys=True, default=str)
         + "\n").encode("utf-8")).hexdigest()
    return {"fingerprint": total, "files": files}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    run = a.run if os.path.isabs(a.run) else os.path.join(ROOT, a.run)

    man = json.load(open(os.path.join(run, "run_manifest.json"), encoding="utf-8"))
    start = man.get("input_identity") or {}
    params = (start.get("params") or man.get("params") or {})
    now = recompute_identity(ROOT, params)

    mism = [k for k in sorted(set(start.get("files", {})) | set(now["files"]))
             if start.get("files", {}).get(k) != now["files"].get(k)]
    res = {
        "run": os.path.relpath(run, ROOT).replace("\\", "/"),
        "manifest_status": man.get("status"),
        "manifest_claims_unchanged": man.get("input_identity_verified_unchanged"),
        "files_compared": len(now["files"]),
        "fingerprint_manifest": start.get("fingerprint"),
        "fingerprint_recomputed": now["fingerprint"],
        "fingerprint_match": start.get("fingerprint") == now["fingerprint"],
        "file_mismatches": mism,
        "new_table_in_fingerprint": "decisions/reporter_origin_scope.csv"
                                    in now["files"],
    }

    # ---- 一致性三元组（读跨法院轮最终产出）----
    dec = os.path.join(run, "decide_out", "cross_court", "decided.csv")
    gstat, gcountry, gident = defaultdict(set), defaultdict(set), \
        defaultdict(lambda: defaultdict(set))
    sysname_of = None
    try:
        import decide as _decide
        sysname_of = _decide.identifier_system_of
    except Exception:
        pass
    with open(dec, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            g = r["merged_group_id"]
            gstat[g].add(r.get("group_foreign_status") or "")
            if (r.get("group_origin_status") or "") == "DETERMINED":
                gcountry[g].add((r.get("group_origin_country") or "").strip())
            if r.get("citation_kind") == "identifier" and sysname_of:
                sy = sysname_of(r["merge_key"])
                if sy:
                    gident[g][sy].add(r["merge_key"])
    rows_disagree = [g for g, v in gstat.items() if len(v) > 1]
    multi_not_conflict = [g for g, v in gcountry.items() if len(v - {""}) > 1
                          and not (gstat[g] & {"CONFLICT"})]
    same_system_multi = [(g, sy) for g, per in gident.items()
                         for sy, ks in per.items() if len(ks) > 1]
    res["consistency"] = {
        "rows_disagree_groups": len(rows_disagree),
        "multi_country_not_conflict_groups": len(multi_not_conflict),
        "same_system_multi_key_groups": len(same_system_multi),
        "examples": {"rows_disagree": rows_disagree[:5],
                     "multi_country_not_conflict": multi_not_conflict[:5],
                     "same_system_multi_key": same_system_multi[:5]},
    }
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if a.out:
        out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
        json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False,
                  indent=1)
        print("written:", os.path.relpath(out, ROOT), file=sys.stderr)


if __name__ == "__main__":
    main()
