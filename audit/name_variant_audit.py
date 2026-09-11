# -*- coding: utf-8 -*-
"""name_variant_audit.py — PROBLEMS #50 量化：同一判决因案名写法不同而没合到一起

属**审计环**（见 audit/README.md）：读裁定层跨院产出，产出**提案与数字**，不喂任何
生产脚本。

背景：§10.3 以 nk(案名) 判同案。同一判决常以长短两种案名被引（Canada (Minister of
Citizenship and Immigration) v. Vavilov 与 Vavilov），折叠后是两个不同的键，§10.3
连候选都不是——于是它的汇编引证单独成组，在产品里成了一个重复条目，本体少算。

判据（与裁定层 #49 给汇编行找归属的判据同一口径，好让两处数字可比）
  F = 没有中立引用的组，且 dd >= 5（进产品的量级）
  A = 含中立引用的组
  F 连到 A，当且仅当：共引重合系数（共引判决数 / 两边较小者）>= 0.8、两组年份
  最近相差 <= 1、法域相容（F 的已知法域须包含于 A 的法域），且 A 是唯一共引最多者

**读法：这是上界。** 共引分不开「平行引证」与「审级历史」——一审总与上诉审一起被引
（PROBLEMS #49 的 Pearson v. Boliden，共引覆盖 100%）。所以按 F 的汇编类型分档：
S.C.R. 只刊最高法院判决，「S.C.R. 连到最高法院锚」最可信；省级汇编连到上诉法院锚，
可能其实是一审判决。

用法
    python audit/name_variant_audit.py            # 读 data/decide_out/cross_court/
"""
import csv
import io
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import decide                                                 # noqa: E402
from normalize import nk                                      # noqa: E402

BAR = 0.8
MIN_DD = 5
OUT = os.path.join(ROOT, "audit", "findings", "name_variant_report.md")


def load():
    D = os.path.join(ROOT, "data", "decide_out", "cross_court")
    ids_by_row = decide.load_decision_ids(os.path.join(D, "decision_ids.csv"))
    groups = defaultdict(list)
    with open(os.path.join(D, "decided.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            groups[r["merged_group_id"]].append(r)
    info = {}
    for gid, ms in groups.items():
        ids = set()
        for m in ms:
            ids |= ids_by_row.get(decide.row_key(m), set())
        neu = [m for m in ms if m["citation_kind"] == "neutral"]
        p = next((m for m in ms if m["is_primary"] == "true"), ms[0])
        info[gid] = {
            "ids": ids,
            "years": {decide.year_of(m["merge_key"]) for m in ms} - {None},
            "anchored": bool(neu),
            "jur": {m["jurisdiction"] for m in (neu or ms)
                    if m["jurisdiction"] not in ("", "UNSUPPORTED")},
            "name": nk(p["case_name_modal"] or ""),
            "label": p["case_name_modal"] or "",
            "abbrs": {nk(m["abbreviation"] or "") for m in ms},
            "strings": sorted({m["canonical_string"] for m in ms}),
            "courts": {m["merge_key"].split("|")[2] for m in neu},
        }
    return info


def kind_of(f, a):
    if f["abbrs"] & {"scr", "canscr"}:
        return "S.C.R.->最高法院锚" if a["courts"] & {"scc", "csc"} else "S.C.R.->非最高法院锚"
    if f["jur"] and f["jur"] <= {"CA"}:
        return "全国性/联邦汇编"
    if f["jur"]:
        return "省级汇编（可能是一审/审级历史）"
    return "法域未知"


def main():
    csv.field_size_limit(10 ** 9)
    info = load()
    inv = defaultdict(list)
    for gid, x in info.items():
        if x["anchored"]:
            for d in x["ids"]:
                inv[d].append(gid)

    st, links = Counter(), []
    for fid, f in info.items():
        if f["anchored"] or len(f["ids"]) < MIN_DD:
            continue
        st["F 候选（无中立引用且 dd>=5）"] += 1
        cnt = Counter()
        for d in f["ids"]:
            for a in inv[d]:
                cnt[a] += 1
        cands = []
        for a, ov in cnt.items():
            x = info[a]
            if ov < BAR * min(len(f["ids"]), len(x["ids"])):
                continue
            if not f["years"] or not x["years"] or \
                    min(abs(y1 - y2) for y1 in f["years"] for y2 in x["years"]) > 1:
                continue
            if f["jur"] and x["jur"] and not f["jur"] <= x["jur"]:
                continue
            cands.append((ov, a))
        if not cands:
            st["无可连的锚"] += 1
            continue
        cands.sort(reverse=True)
        if len(cands) > 1 and cands[0][0] == cands[1][0]:
            st["并列，不连"] += 1
            continue
        ov, a = cands[0]
        x = info[a]
        cat = ("同名（#49 残余）" if f["name"] == x["name"] else "异名（#50）") + " | " + kind_of(f, x)
        added = len(f["ids"] - x["ids"])
        st[cat] += 1
        st[cat + " —— 可补给锚的 dd"] += added
        links.append((len(f["ids"]), cat, f, x, added))

    o = io.StringIO()
    w = o.write
    w("# PROBLEMS #50 量化：同一判决因案名写法不同而没合到一起\n\n")
    w("仪器：`audit/name_variant_audit.py`（可重放）。数据：`data/decide_out/cross_court/`。\n\n")
    w("判据与读法见仪器文件头。**全部数字是上界**：共引分不开平行引证与审级历史，"
      "只有「S.C.R.->最高法院锚」一档可信度高。\n\n## 计数\n\n| 项 | 数 |\n|---|---:|\n")
    for k in sorted(st):
        w("| %s | %d |\n" % (k, st[k]))
    w("\n## 连接明细（按 F 的 dd 降序，前 30）\n\n| F dd | 档 | F 案名 | F 成员串 | → 锚案名 | 锚成员串 | 可补 dd |\n"
      "|---:|---|---|---|---|---|---:|\n")
    for dd, cat, f, x, added in sorted(links, key=lambda t: -t[0])[:30]:
        w("| %d | %s | %s | %s | %s | %s | %d |\n" % (
            dd, cat, f["label"][:40], " / ".join(f["strings"][:3])[:60],
            x["label"][:40], " / ".join(x["strings"][:3])[:60], added))
    w("\n## Vavilov（#50 登记时【待核实】的 dd 41 组）\n\n")
    vav = sorted(((len(x["ids"]), gid, x) for gid, x in info.items()
                  if "vavilov" in x["label"].lower()), key=lambda t: -t[0])
    for dd, gid, x in vav[:6]:
        link = next((("→ " + y["label"][:50], cat) for _, cat, f, y, _ in links if f is x), ("未连", ""))
        w("- dd %d，%s，成员：%s；%s %s\n" % (dd, "有中立锚" if x["anchored"] else "无中立锚",
                                          " / ".join(x["strings"][:4]), link[0], link[1]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(o.getvalue())
    print(o.getvalue())


if __name__ == "__main__":
    main()
