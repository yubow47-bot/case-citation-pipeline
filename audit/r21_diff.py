# -*- coding: utf-8 -*-
"""r21_diff.py — #21 全量重跑差分仪器（PROBLEMS #21 / prompt_21_fix.md §6.3）。

用法
    python audit/r21_diff.py --base data/run_20260914_r4c --new data/run_20260915_r21a

产出（stdout 汇总 + --list-file 逐条清单）：
  1. counted 提及级：新增行数、消失行数（必须 0）、身份变化行数（必须 0）
  2. 组级：组数、过门槛（dd>=5）组数、dd 总和、榜单前 25 的进出与 dd 变化
  3. 新形状（shape_paren_year_abbr_page）counted 行的逐条清单（供人工分类判例/非判例）
匹配口径：counted 行按 (court, corpus_row_index, merge_key, match_start_offset,
match_end_offset) 精确配对——7 形状的原行若缺任何一个配对键即记「消失/身份变化」。
只读两个 run 目录；不改任何文件（--list-file 指定的输出文件除外）。
"""
import argparse
import csv
import json
import os
import sys

csv.field_size_limit(10**9)


def counted_rows(run_dir):
    rows = []
    for court in ("SCC", "ONCA"):
        p = os.path.join(run_dir, "merge_out", court, "mentions_candidates.csv")
        with open(p, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["arbitration_status"] == "counted":
                    r["_court"] = court
                    rows.append(r)
    return rows


def group_key(r):
    return (r["_court"], r["corpus_row_index"], r["merge_key"],
            r["match_start_offset"], r["match_end_offset"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--list-file", default=None,
                    help="新形状 counted 行逐条清单输出路径（CSV）")
    args = ap.parse_args()

    base = counted_rows(args.base)
    new = counted_rows(args.new)
    base_keys = {}
    for r in base:
        base_keys.setdefault(group_key(r), []).append(r["raw_string"])
    new_keys = {}
    for r in new:
        new_keys.setdefault(group_key(r), []).append(r["raw_string"])

    disappeared = [k for k in base_keys if k not in new_keys]
    added = [k for k in new_keys if k not in base_keys]
    identity_changed = [k for k in base_keys if k in new_keys
                        and base_keys[k] != new_keys[k]]

    print("== 1. 提及级 counted 行（%s -> %s）" % (os.path.basename(args.base),
                                                 os.path.basename(args.new)))
    print("   base=%d new=%d  新增=%d  消失=%d  身份变化=%d"
          % (len(base), len(new), len(added), len(disappeared), len(identity_changed)))
    ok = not disappeared and not identity_changed
    print("   破坏 0 / 身份变化 0:", "PASS" if ok else "FAIL")

    # 新形状清单
    fb_rows = [r for r in new if r["shape_name"] == "shape_paren_year_abbr_page"]
    fb_counted = [r for r in fb_rows if r["arbitration_status"] == "counted"]
    print("== 3. 新形状 counted 行: %d（候选 %d）" % (len(fb_counted), len(fb_rows)))
    added_fb = [k for k in added if k[0] in ("SCC", "ONCA")
                and any(r["shape_name"] == "shape_paren_year_abbr_page"
                        for r in new if group_key(r) == k)]
    print("   新增行里属于新形状的: %d；其余新增: %d"
          % (len(added_fb), len(added) - len(added_fb)))
    if args.list_file:
        with open(args.list_file, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["court", "corpus_row_index", "raw_string", "abbr", "page",
                        "year", "merge_key", "arbitration_status",
                        "source_decision_citation"])
            for r in fb_rows:
                w.writerow([r["_court"], r["corpus_row_index"], r["raw_string"],
                            r.get("abbr"), r.get("page"), r.get("year_start"),
                            r["merge_key"], r["arbitration_status"],
                            r["source_decision_citation"]])
        print("   清单 -> %s" % args.list_file)

    # ---- 2. 组级（selected.csv，is_primary 行）----
    def groups(run_dir):
        p = os.path.join(run_dir, "select_out", "selected.csv")
        prim = {}
        kept = 0
        dd_sum = 0
        with open(p, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["is_primary"] != "true":
                    continue
                key = (r["court"], r["canonical_string"])
                dd = int(r["distinct_decisions_count"])
                prim[key] = (dd, r["kept"], r["case_name_modal"],
                             r["group_origin_country"], r["group_foreign_status"])
                if r["kept"] == "true":
                    kept += 1
                    dd_sum += dd
        return prim, kept, dd_sum

    gb, kept_b, ddb = groups(args.base)
    gn, kept_n, ddn = groups(args.new)
    lost_groups = [k for k in gb if k not in gn]
    new_groups = [k for k in gn if k not in gb]
    dd_changed = [(k, gb[k][0], gn[k][0]) for k in gn if k in gb
                  and gb[k][0] != gn[k][0]]
    print("== 2. 组级")
    print("   组: %d -> %d（+新 %d / -消失 %d）" % (len(gb), len(gn), len(new_groups), len(lost_groups)))
    print("   过门槛组: %d -> %d；dd 合计: %d -> %d" % (kept_b, kept_n, ddb, ddn))
    print("   dd 变化的既有组: %d" % len(dd_changed))
    print("   消失组（必须 0）:", "PASS" if not lost_groups else "FAIL")

    lb_b = sorted(((k, v[0]) for k, v in gb.items() if v[1] == "true"),
                  key=lambda kv: -kv[1])[:25]
    lb_n = sorted(((k, v[0]) for k, v in gn.items() if v[1] == "true"),
                  key=lambda kv: -kv[1])[:25]
    print("== 4. 榜单前 25")
    sb, sn = set(k for k, _ in lb_b), set(k for k, _ in lb_n)
    print("   进: %s" % (sorted(sn - sb),))
    print("   出: %s" % (sorted(sb - sn),))
    for k in sorted(sb & sn):
        db_ = dict(lb_b)[k]
        dn_ = dict(lb_n)[k]
        if db_ != dn_:
            print("   dd 变化: %s %d -> %d" % (k[1][:44], db_, dn_))

    print("== 总结:", "ALL PASS（零破坏）" if (ok and not lost_groups) else "存在 FAIL，见上")


if __name__ == "__main__":
    main()
