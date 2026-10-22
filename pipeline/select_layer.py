# -*- coding: utf-8 -*-
"""select_layer.py — 选取层（规格 §11）

**一道门槛，判据是 distinct_decisions_count。不删行，只打标记。**

用法
    python pipeline/select_layer.py --input data/decide_out/cross_court/decided.csv \
        --config select_config.yaml --profile default --output data/select_out

输出
    <output>/selected.csv    全量行 + kept 列（产品只读 kept=true，完整表始终留存）
    <output>/dd_profile.csv  dd 分布：各阈值下留下多少组、多少案名（供定标）
    <output>/manifest.json   参数、阈值、配置原文、各项计数（约束九）

为什么用 dd 而不是 occurrence_count（§11.1）
    同一份判决里反复引用同一个案子十次是常见写法，但那只是一位法官的一次法律
    行为。occurrence 会把「一个法官引了十次」和「十个法官各引一次」算成同样重要。
    dd 还天然防 OCR 噪音：噪音串几乎只出现在一份判决里，dd = 1。

门槛必须放在最后一次合并之后（§11.1）
    若放在归并层：某案在 A.C. 下 2 次、在 All E.R. 下 2 次，两组各自不到门槛、
    双双被砍，而它真实引用次数是 4。本层的输入因此必须是裁定层**跨法院轮**的
    输出，不是归并层的输出。

默认保留至少一份判决实际引用的全量组（DD >= 1）。
    DD >= 5 只作为 frequent 可选筛选，不能把低频自动视为非判例。
    dd_profile.csv 继续报告各门槛的覆盖范围；门槛不代表正确率。

不设高频豁免通道（§11.2）
    旧管线有一条 occ>=20 且 dd>=10 且 admitted>=10 且 agreement>=0.25 的并行
    路径，四个参数没有依据来源。裁定层正确完成合并后，真正重要的案子 dd 自然
    达标，豁免路径失去存在理由。
"""
import argparse
import csv
import datetime
import json
import os
from collections import Counter

import yaml

from artifacts import replace_file

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _relpath(p):
    """manifest 里记输入路径。跨盘符时（测试临时目录在 C:、仓库在 D:）relpath 会抛
    ValueError——而 manifest 写在数据文件之后，首版就这样留下有数据、无 manifest 的
    半成品输出（迷你全链首跑抓到）。退回绝对路径。"""
    try:
        return os.path.relpath(p, ROOT).replace("\\", "/")
    except ValueError:
        return os.path.abspath(p).replace("\\", "/")


# A full-data default is a selection policy, not a calibrated precision claim.
THRESHOLD_CALIBRATION = "full_data_default_1_frequency_profiles_are_optional"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--profile", default="default")
    ap.add_argument("--output", required=True)
    a = ap.parse_args()

    with open(a.config, encoding="utf-8") as f:
        raw_cfg = f.read()
    cfg = yaml.safe_load(raw_cfg)
    if a.profile not in cfg:
        raise SystemExit("配置里没有 profile %r，可选：%s"
                         % (a.profile, ", ".join(sorted(cfg))))
    threshold = int(cfg[a.profile]["threshold_dd"])

    with open(a.input, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames) + ["kept"]
        rows = list(reader)

    stats = Counter()
    dd_hist = Counter()
    groups_kept, groups_seen = set(), set()
    for r in rows:
        dd = int(r["distinct_decisions_count"])
        gid = r.get("merged_group_id") or r["merge_key"]
        if gid not in groups_seen:
            groups_seen.add(gid)
            dd_hist[dd] += 1
        keep = dd >= threshold
        r["kept"] = "true" if keep else "false"
        stats["kept" if keep else "dropped"] += 1
        if keep:
            groups_kept.add(gid)
    stats["rows_total"] = len(rows)
    stats["groups_total"] = len(groups_seen)
    stats["groups_kept"] = len(groups_kept)

    # 定标仪器：各候选阈值下还剩多少组。规格 §11.2 要求「按 dd 分布重定」，
    # 数字必须由可重放的仪器产出（约束九），不能靠临时脚本口算。
    profile_rows = []
    total_groups = len(groups_seen)
    for t in (1, 2, 3, 5, 10, 20, 50, 100):
        n = sum(c for dd, c in dd_hist.items() if dd >= t)
        profile_rows.append({"threshold_dd": t, "groups_kept": n,
                             "pct_of_groups": round(n / total_groups * 100, 3)
                             if total_groups else 0.0})

    os.makedirs(a.output, exist_ok=True)
    for name, flds, data in (
            ("selected.csv", fields, rows),
            ("dd_profile.csv", ["threshold_dd", "groups_kept", "pct_of_groups"],
             profile_rows)):
        path = os.path.join(a.output, name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=flds, extrasaction="ignore")
            w.writeheader()
            w.writerows(data)
        replace_file(tmp, path)

    # 不删行（§11.3）：完整表始终留存，任何时候都能回答「某案为什么不在结果里」
    assert stats["kept"] + stats["dropped"] == len(rows), "行数不守恒"

    manifest = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "spec_section": "11",
        "input": _relpath(a.input),
        "profile": a.profile,
        "threshold_dd": threshold,
        "threshold_calibration": THRESHOLD_CALIBRATION,
        "config_verbatim": raw_cfg,
        "stats": dict(sorted(stats.items())),
        "dd_profile": profile_rows,
    }
    with open(os.path.join(a.output, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    print("profile=%s  threshold_dd=%d (%s)"
          % (a.profile, threshold, THRESHOLD_CALIBRATION))
    print("  行 %d：kept %d / dropped %d" % (len(rows), stats["kept"], stats["dropped"]))
    print("  组 %d：kept %d" % (stats["groups_total"], stats["groups_kept"]))
    print("  dd 分布（定标用）：")
    for p in profile_rows:
        print("     dd>=%-4d %7d 组  %6.2f%%"
              % (p["threshold_dd"], p["groups_kept"], p["pct_of_groups"]))


if __name__ == "__main__":
    main()
