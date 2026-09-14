# -*- coding: utf-8 -*-
"""R3 Stage 1 研究目标清单生成器（审计环仪器，只读生产产出，产出是**提案**）。

读：data/coverage_out/stage0_r2i.json（M1a/净新增组按缩写）+ run 的
    merge_out/<court>/mentions_candidates.csv + decisions/reporter_jurisdiction.csv
写：audit/findings/r3_stage1_targets.json + r3_stage1_targets_{canadian,british,other}.md

用途：给 Stage 1 的三个只读研究子代理一份**按语料提及量排序**的目标清单，附
「语料实测的 vol/年区间」（研究者据此知道哪段区间真正要紧）。本文件**不写任何
决策表**——表由人按 findings 手工整理（audit/README.md 的膜规则）。

约束（写进子代理任务书）：每个缩写同时做两件事——(A) 排他性溯源；(B) **反例搜寻**。
逐行必须给 source + source_locator；查不到或争议 → 不写行或写 exclusivity=mixed。
"""

import csv
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "data", "run_20260913_r2i")
STAGE0 = os.path.join(ROOT, "data", "coverage_out", "stage0_r2i.json")
OUTDIR = os.path.join(ROOT, "audit", "findings")

CA_SET = frozenset(("CA", "ON", "QC", "BC", "AB", "NS", "NB", "MB", "SK",
                    "NL", "PE", "YT", "NT", "NU"))
GB_SET = frozenset(("GB",))
COURTS = ("SCC", "ONCA")

TIER1 = 25
TIER2 = 70


def key_parts(mk):
    p = mk.split("|")
    return p if len(p) >= 5 else None


def main():
    stage0 = json.load(open(STAGE0, encoding="utf-8"))
    m1a = stage0["M1a_mentions_by_abbr_full"]
    netnew = stage0["M1_netnew_groups_by_abbr_full"]

    # 现有（未核实）表行
    table = defaultdict(list)
    with open(os.path.join(ROOT, "decisions", "reporter_jurisdiction.csv"),
              encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            table[r["abbreviation"].strip()].append(r)
    # 归一键索引（分类层归一键可能与印刷形不同）
    nk_table = defaultdict(list)
    for a, rows in table.items():
        for r in rows:
            nk_table[(r.get("normalized_key") or a).strip().lower()].append(r)

    counted = Counter()
    jur = defaultdict(Counter)
    combos = defaultdict(Counter)          # abbr -> {(vol,year): n}
    volmin, volmax = {}, {}
    ymin, ymax = {}, {}
    empty_vol = Counter()
    empty_year = Counter()

    for court in COURTS:
        with open(os.path.join(RUN, "merge_out", court,
                               "mentions_candidates.csv"),
                  encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("citation_kind") != "reporter":
                    continue
                if r.get("arbitration_status") != "counted":
                    continue
                p = key_parts(r.get("merge_key") or "")
                if not p:
                    continue
                year, vol, abbr = p[0], p[1], p[2]
                counted[abbr] += 1
                jur[abbr][(r.get("jurisdiction") or "").strip() or "(blank)"] += 1
                combos[abbr][(vol, year)] += 1
                if vol == "":
                    empty_vol[abbr] += 1
                else:
                    v = int(vol) if vol.isdigit() else None
                    if v is not None:
                        volmin[abbr] = min(volmin.get(abbr, v), v)
                        volmax[abbr] = max(volmax.get(abbr, v), v)
                if year == "":
                    empty_year[abbr] += 1
                else:
                    y = int(year) if year.isdigit() else None
                    if y is not None:
                        ymin[abbr] = min(ymin.get(abbr, y), y)
                        ymax[abbr] = max(ymax.get(abbr, y), y)

    ranks = [a for a, _ in counted.most_common()]
    total = sum(counted.values())
    cum = 0
    out = []
    for i, abbr in enumerate(ranks):
        cum += counted[abbr]
        rows = table.get(abbr) or nk_table.get(abbr) or []
        js = jur[abbr]
        jtop = js.most_common(1)[0][0] if js else ""
        if jtop in CA_SET:
            grp = "canadian"
        elif jtop in GB_SET:
            grp = "british"
        else:
            grp = "other"
        out.append({
            "rank": i + 1,
            "abbr": abbr,
            "tier": 1 if i < TIER1 else (2 if i < TIER2 else 3),
            "group": grp,
            "counted_mentions": counted[abbr],
            "m1a_mentions": m1a.get(abbr, 0),
            "netnew_groups": netnew.get(abbr, 0),
            "cum_share_pct": round(100.0 * cum / total, 2),
            "jurisdiction_dist": dict(js.most_common()),
            "table_rows": len(rows),
            "table_jurisdictions": sorted({r["jurisdiction"] for r in rows}),
            "table_vol_range": ((rows[0].get("vol_range_start") or "",
                                 rows[0].get("vol_range_end") or "")
                                if rows else ("", "")),
            "table_year_range": ((rows[0].get("year_range_start") or "",
                                  rows[0].get("year_range_end") or "")
                                 if rows else ("", "")),
            "homograph": len(rows) > 1,
            "observed_combos": len(combos[abbr]),
            "observed_vol_span": [volmin.get(abbr), volmax.get(abbr)],
            "observed_year_span": [ymin.get(abbr), ymax.get(abbr)],
            "mentions_empty_vol": empty_vol[abbr],
            "mentions_empty_year": empty_year[abbr],
            "top_combos": [list(k) + [v] for k, v in combos[abbr].most_common(12)],
        })

    os.makedirs(OUTDIR, exist_ok=True)
    jpath = os.path.join(OUTDIR, "r3_stage1_targets.json")
    full = [t for t in out if t["tier"] <= 2]
    tail = [{"abbr": t["abbr"], "tier": 3, "group": t["group"],
             "counted_mentions": t["counted_mentions"],
             "netnew_groups": t["netnew_groups"],
             "jurisdiction_dist": t["jurisdiction_dist"]} for t in out
            if t["tier"] > 2]
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump({"run": "data/run_20260913_r2i",
                   "generated_by": "audit/stage1_targets.py",
                   "total_counted_reporter_mentions": total,
                   "note": "提案清单，不是决策表；表行须人按 findings 手工整理。"
                           "tier1_2 = 全字段；tier3 = 压缩字段（长尾，多为噪声/"
                           "期刊/非汇编缩写）",
                   "tier1_2": full, "tier3": tail}, f,
                  ensure_ascii=False, indent=1)

    for grp, label in (("canadian", "加拿大/省级"), ("british", "英国"),
                       ("other", "美国及其他")):
        sel = [t for t in out if t["group"] == grp]
        p = os.path.join(OUTDIR, "r3_stage1_targets_%s.md" % grp)
        with open(p, "w", encoding="utf-8") as f:
            f.write("# R3 Stage 1 研究目标清单（%s）\n\n" % label)
            f.write("产出者：`audit/stage1_targets.py`（**审计环——产出是提案，不是"
                    "数据**；`audit/README.md`）。\n")
            f.write("依据 run：`data/run_20260913_r2i`；Stage 0 测量："
                    "`implementation/coverage_metric.py`。\n")
            f.write("全量机器可读：`audit/findings/r3_stage1_targets.json`。\n\n")
            f.write("## 每个缩写都要做两件事\n\n")
            f.write("**A. 排他性溯源**——这个汇编是否只刊登某一来源地的判决？给出**约束级别**：\n")
            f.write("- `exclusive_statute`：有约束力的法律/宪制文本（法条、法院设立"
                    "文件、官方报告规则）**明文规定**其刊登范围。\n")
            f.write("- `exclusive_publisher`：只有出版方自己的编辑方针/说明。"
                    "**必须做 B。**\n")
            f.write("- `mixed`：存在（或无法排除）非该来源地的案件。\n")
            f.write("- `scope_evidence_third_party_only`：**只**找到第三方手册/目录"
                    "（McGill Guide、Bluebook、Cardiff Index、图书馆目录）的范围描述，"
                    "既无法律文本也无出版方自述。**本轮不写行**（P2 只认两档），但必须"
                    "把出处与 B 的结果记下来——供后续决定是否增设第三档时直接可用。\n")
            f.write("- `not_a_reporter`：根本不是判例汇编（法学期刊、二手评论、"
                    "抽取层噪声 token 如 `section`/`no`/`december`）。**不写行。**\n\n")
            f.write("**B. 反例搜寻（必做，`exclusive_publisher` 行强制）**——主动找"
                    "「这个汇编里有没有不属于所声称来源地的案件」。找一个具体反例"
                    "（卷/页 + 案名 + 为什么不属于）或写明查了哪些来源、为什么没找到。"
                    "**注意：不得只看你这一组**——名义上的国内汇编（如 `D.L.R.`）"
                    "也要显式检查是否刊登过非加拿大材料（比较法引用、枢密院案等）。\n\n")
            f.write("**C. 卷/年体系**——`volume_system` ∈ {`year_volume`, "
                    "`continuous`}：卷号每年从 1 重新开始（S.C.R. 式 `[1995] 2 S.C.R. "
                    "3`）＝ `year_volume`；卷号跨年连续（D.L.R. 式 `34 D.L.R. (2d) "
                    "451`）＝ `continuous`。需要 source（引用手册/出版方说明）。\n\n")
            f.write("**D. 窗口**（仅同形异义/需切分的缩写）——独立溯源的 vol 区间与"
                    "年区间（**不得**抄 `decisions/reporter_jurisdiction.csv` 的现有"
                    "估计值）。\n\n")
            f.write("## 硬规矩\n\n")
            f.write("- 每个写入 findings 的事实必须带 `source`（机构/文件类型）与 "
                    "`source_locator`（URL + 条款/页 + 取用日期）。查不到就写"
                    "「无权威出处」，**不要写行**。\n")
            f.write("- 不得读 `PROBLEMS.md` 当证据；不得以语料上下文当法域证据。\n")
            f.write("- **不要改任何 `decisions/` 表、不要改 `pipeline/` 代码**；产出只"
                    "写 `audit/findings/r3_reporter_origin_%s.md`。\n" % grp)
            f.write("- 数字纪律（约束九）：凡是写下的规模/区间，都要能重放或标"
                    "「未核实」。\n\n")
            f.write("## 目标表（按语料 counted 汇编提及量排序，累计份额为全体占比）\n\n")
            f.write("只列 tier 1–2（全局前 %d 名）。tier 3（长尾，多为噪声/期刊/非汇编"
                    "缩写）只在 JSON 里，按需查。\n\n" % TIER2)
            f.write("| # | abbr | counted 提及 | 累计% | 净新增组(M1b) | 分类层法域"
                    " | 表内行 | 语料实测 vol | 语料实测年 | 空卷 | 空年 | 层级 |\n")
            f.write("|---:|---|---:|---:|---:|---|---:|---|---|---:|---:|---:|\n")
            listed = [t for t in sel if t["tier"] <= 2]
            for t in listed:
                f.write("| %d | `%s` | %d | %.2f | %d | %s | %d | %s | %s | %d | %d | %d |\n"
                        % (t["rank"], t["abbr"], t["counted_mentions"],
                           t["cum_share_pct"], t["netnew_groups"],
                           ",".join("%s:%d" % kv for kv in
                                    list(t["jurisdiction_dist"].items())[:4]),
                           t["table_rows"],
                           "%s–%s" % (t["observed_vol_span"][0],
                                      t["observed_vol_span"][1])
                           if t["observed_vol_span"][0] is not None else "-",
                           "%s–%s" % (t["observed_year_span"][0],
                                      t["observed_year_span"][1])
                           if t["observed_year_span"][0] is not None else "-",
                           t["mentions_empty_vol"], t["mentions_empty_year"],
                           t["tier"]))
            f.write("\n本组 tier 3 目标 %d 个（提及合计 %d，净新增组合计 %d），"
                    "见 JSON 的 `tier: 3` 条目。\n"
                    % (len(sel) - len(listed),
                       sum(t["counted_mentions"] for t in sel if t["tier"] > 2),
                       sum(t["netnew_groups"] for t in sel if t["tier"] > 2)))
            f.write("\n## 明细（前 30 名；含语料实测高频 vol/年组合，供窗口校准）\n")
            for t in sel[:30]:
                f.write("\n### `%s`（rank %d, tier %d）\n" % (t["abbr"], t["rank"],
                                                              t["tier"]))
                f.write("- counted 提及 %d；M1a %d；可带来净新增组 %d；累计份额 %.2f%%\n"
                        % (t["counted_mentions"], t["m1a_mentions"],
                           t["netnew_groups"], t["cum_share_pct"]))
                f.write("- 分类层法域分布：%s\n" % ", ".join(
                    "%s=%d" % kv for kv in t["jurisdiction_dist"].items()))
                f.write("- 现有表行：%d（法域 %s；vol 区间 %s；年区间 %s；**未核实**）\n"
                        % (t["table_rows"], ",".join(t["table_jurisdictions"]) or "-",
                           t["table_vol_range"], t["table_year_range"]))
                f.write("- 语料实测：vol %s；年 %s；空卷提及 %d；空年提及 %d；"
                        "不同 (vol,年) 组合 %d\n"
                        % (t["observed_vol_span"], t["observed_year_span"],
                           t["mentions_empty_vol"], t["mentions_empty_year"],
                           t["observed_combos"]))
                if t["top_combos"]:
                    f.write("- 高频组合 (vol,年,提及数)：%s\n" % ", ".join(
                        "(%s,%s,%d)" % tuple(c) for c in t["top_combos"]))
        print("written:", os.path.relpath(p, ROOT))

    print("written:", os.path.relpath(jpath, ROOT))
    print("total counted reporter mentions:", total)
    for grp in ("canadian", "british", "other"):
        sel = [t for t in out if t["group"] == grp]
        t1 = [t for t in sel if t["tier"] == 1]
        print("%-9s targets=%-4d tier1=%-3d mentions=%d netnew_groups=%d"
              % (grp, len(sel), len(t1),
                 sum(t["counted_mentions"] for t in sel),
                 sum(t["netnew_groups"] for t in sel)))


if __name__ == "__main__":
    main()
