# -*- coding: utf-8 -*-
"""neutral_triage.py — 漏网「疑似真法院码」的三判据分诊（审计环）

属于**审计环**（见 audit/README.md）：产出是**提案**（每码一档 + 可重放数字），
不喂任何生产脚本。它做两件事：给 Phase 2 人工溯源排候选清单（A/D 桶），
给 reporter_jurisdiction.csv 移交汇编线索（B/C 桶，量级远超中立码）。

population（口径，钉死）：
  data/extract_out/extracted.csv 中 token 非空的行——即 shape_bracket 与
  shape_neutral_bare 两形状（§8.2 的查表 population，其余五形状 token 槽为空）。
  逐行三道前置闸：token 精确命中 court_code / normalize_code(token) 命中
  normalized_key → 已解决，跳过；classify_miss(token) != "courtish" → 厂商/噪声，
  跳过。按 normalize_code(token) 聚成**家族**（AC 与 A.C./A. C. 同族）。

三判据（全部只看判决书上印出来的字样，不查表、不看上下文——不触约束三）：
  A 印刷优势比  家族「无点写法」行数 ÷「带点写法」行数（shape_bracket 内）。
                「带点」判在**码段**上：EWCA Civ. 的尾点在分庭词，码段 EWCA
                无点 → 按无点计（EWCA Civ 175 = 无尾点 137 + 带尾点 38 合并口径）
  B 卷号率      家族行中 vol 字段非空的比例（shape_bracket 内）。中立引用结构是
                [年] 代码 序号、无卷号；vol 有值即汇编引证
  C 序号量级    page 字段位数分布。**注释列，不参与分档**——AZ 51826418 类八位数
                依此可见，但量级不单独定档（判据 C 的代表 AZ 落 A 桶）

分档规则（顺序即优先级，第一个命中者胜）：
  卷号率 ≥ 0.5      → B_REPORTER    （汇编：[年] 卷 码 页，HKC/KP 靠它先于优势比落桶）
  否则 优势比 ≥ 3    → A_NEUTRAL_CAND（中立码候选，仍混有拼写错与噪声，须 Phase 2 溯源）
  否则 优势比 ≤ 1/3  → C_REPORTER    （汇编：无点者是 OCR 变体，AC 44:14,611 类）
  否则               → D_HUMAN       （1/3 < 优势比 < 3，样本量不足，必须人核）
  家族只在 shape_neutral_bare 出现 → E_BARE_ONLY（#35 乙类加拿大机构自用码，另行登记）

校准门（运行时，源自任务书 Phase 1 验收数字，2026-09-09）：75 个纯大写 courtish
漏网码的分桶必须复现 A / B 14 / C 15 / D（全枚举见 CAL_B/C/D）；锚点
UKHL 225:6、EWCACIV 175:7、EWCACRIM 58:7。跑不出这组数 = 判据实现有偏差，
先对齐再往下走（校准失败时退出码非 0，报告仍打印供对齐）。
**已记录偏差 OJN**：任务书列 D，机械三判据下落 A——其唯一行 [2004] OJN 173
与任务书明载落 A 的 UHKL（1:0、无卷号）统计特征完全同构，D 桶归属系作者
预判其为 `OJ No` 无空格粘连变体（人核判断，无机械判据可复现）。OJN 仍进
Phase 2 溯源清单，工作面不变；据此 A 40 / D 6。
任务书的 AC 46:15,001 在本仪器口径下实测值随报告输出（桶位 C 为准），
差值来源未定（疑含空格变体或旧数据），差异记录于 findings。

用法：
    python audit/neutral_triage.py --assert-only
    python audit/neutral_triage.py
    python audit/neutral_triage.py --json data/neutral_triage.json
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)                                    # 同环兄弟模块，口径复用
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import normalize                                             # noqa: E402
import table_coverage as tc                                  # noqa: E402

EXTRACTED = tc.EXTRACTED

# --- 三判据阈值（任务书 Phase 1）---
VOL_RATE_REPORTER = 0.5      # 卷号率 ≥ 0.5 → B_REPORTER
RATIO_NEUTRAL = 3.0          # 优势比 ≥ 3   → A_NEUTRAL_CAND
RATIO_REPORTER = 1.0 / 3.0   # 优势比 ≤ 1/3 → C_REPORTER

_TRAIL_DOT = re.compile(r"\.+$")
# 分庭词表与 table_coverage._DIVISION 同集（英国 PD 载明的 EWHC/EWCA 分庭缩写闭集）
_DIVISION_TAIL = re.compile(r"\s*(?:Civ|Crim|Ch|QB|Fam|Comm|Admin|Pat|TCC)$")
# 诊断用：Civ/Crim 之外的疑似分庭词（EWHC Ch / EWCA Crim 之类），不改变分类
_DIVISIONISH = re.compile(r"^[A-Z]{2,12}\s+[A-Z][a-z]{1,5}\.?$")


def is_dotted_print(token):
    """带点判定落在码段：去尾点、去分庭词之后是否仍含句点。"""
    s = _TRAIL_DOT.sub("", token)
    s = _DIVISION_TAIL.sub("", s)
    return "." in s


# --- 校准靶（任务书 Phase 1 验收数字：75 纯大写 courtish 漏网码的分桶）---
# 已记录偏差：OJN 任务书原列 D，机械判据下落 A（见模块 docstring），
# 已从 CAL_D 移出、计入 CAL_DEVIATIONS，桶计数随之为 A 40 / D 6。
CAL_B = {"NZLR", "QB", "WWR", "CLRBR", "KB", "KP", "FCR", "FLR", "HKCFAR",
         "TLR", "CNLR", "DLR", "EGLR", "HKC"}
CAL_C = {"AC", "CTC", "SCCA", "SCJ", "BCJ", "OWN", "AJ", "DCR", "FCJ", "ILR",
         "ORBD", "OTC", "PEIJ", "SASR", "STC"}
CAL_D = {"QCA", "EWCA", "NICA", "NIQB", "SASC", "CLLC"}
CAL_DEVIATIONS = {
    "OJN": "任务书列 D（作者预判其为 OJ No 无空格粘连变体）；机械三判据下与 "
           "UHKL 同构（1:0、无卷号）落 A。Phase 2 逐条溯源时按无权威出处处理。",
}
CAL_A_REPS = ["UKHL", "UKSC", "EWHC", "HCA", "UKPC", "NZCA", "ZACC", "UHKL"]
CAL_PURE_TOTAL = 75
CAL_BUCKET_COUNTS = {"A": 40, "B": 14, "C": 15, "D": 6}
CAL_ANCHORS = {"UKHL": (225, 6), "EWCACIV": (175, 7), "EWCACRIM": (58, 7)}


def run_static_assertions():
    bad = []
    # 分类口径与 table_coverage 同源（防两工具漂移）
    for t, want in tc.ASSERTIONS:
        if tc.classify_miss(t) != want:
            bad.append("classify_miss(%r) 应为 %s，实为 %s" % (t, want, tc.classify_miss(t)))
    # 带点判据锚：分庭词尾点不算码段带点
    for t, want in [("EWCA Civ", False), ("EWCA Civ.", False), ("E.W.C.A. Civ.", True),
                    ("E.W.C.A. Crim", True), ("EWHC Ch.", False), ("L.J. Ch.", True),
                    ("S.C.R.", True), ("A.C", True),
                    ("AC", False), ("U.K.H.L.", True)]:
        if is_dotted_print(t) != want:
            bad.append("is_dotted_print(%r) 应为 %s" % (t, want))
    # 归一函数同口径（约束：必须复用 pipeline/normalize.py）
    assert normalize.normalize_code("E.W.C.A. Civ.") == "EWCACIV"
    assert normalize.normalize_code("EWCA Civ") == "EWCACIV"
    assert normalize.normalize_code("A. C.") == "AC"
    # 校准靶自身完整性
    assert len(CAL_B) == 14 and len(CAL_C) == 15 and len(CAL_D) == 6
    assert len(CAL_DEVIATIONS) == 1 and not (CAL_DEVIATIONS.keys() & (CAL_B | CAL_C | CAL_D))
    assert not (CAL_B & CAL_C or CAL_B & CAL_D or CAL_C & CAL_D)
    assert sum(CAL_BUCKET_COUNTS.values()) == CAL_PURE_TOTAL
    print("静态断言：全过" if not bad else "静态断言：%d 条失败" % len(bad), file=sys.stderr)
    for b in bad:
        print("  " + b, file=sys.stderr)
    return not bad


def scan_families():
    codes, keys = tc.load_table()
    csv.field_size_limit(10 ** 8)
    fams = {}
    diag_divisionish = Counter()
    with open(EXTRACTED, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            shape = row["shape_name"]
            if shape not in ("shape_bracket", "shape_neutral_bare"):
                continue
            t = (row.get("token") or "").strip()
            if not t or t in codes:
                continue
            if normalize.normalize_code(t) in keys:
                continue
            if tc.classify_miss(t) != "courtish":
                if shape == "shape_bracket" and _DIVISIONISH.match(t):
                    diag_divisionish[t] += 1
                continue
            k = normalize.normalize_code(t)
            st = fams.setdefault(k, {
                "bracket_variants": Counter(), "bare_variants": Counter(),
                "undotted": 0, "dotted": 0, "vol": 0, "serial_lens": Counter()})
            if shape == "shape_bracket":
                st["bracket_variants"][t] += 1
                if is_dotted_print(t):
                    st["dotted"] += 1
                else:
                    st["undotted"] += 1
                if (row.get("vol") or "").strip():
                    st["vol"] += 1
                page = (row.get("page") or "").strip()
                if page.isdigit():
                    st["serial_lens"][len(page)] += 1
            else:
                st["bare_variants"][t] += 1
    return fams, diag_divisionish


def bucket_of(st):
    total = st["undotted"] + st["dotted"]
    if total == 0:
        return "E_BARE_ONLY"
    if st["vol"] / total >= VOL_RATE_REPORTER:
        return "B_REPORTER"
    ratio = st["undotted"] / st["dotted"] if st["dotted"] else float("inf")
    if ratio >= RATIO_NEUTRAL:
        return "A_NEUTRAL_CAND"
    if ratio <= RATIO_REPORTER:
        return "C_REPORTER"
    return "D_HUMAN"


def ratio_str(st):
    if st["dotted"] == 0:
        return "%d:0" % st["undotted"]
    return "%.2f" % (st["undotted"] / st["dotted"])


def run_calibration(fams):
    errs = []
    pure = sorted(k for k, st in fams.items()
                  if any(tc.COURTISH.match(v) for v in st["bracket_variants"]))
    if len(pure) != CAL_PURE_TOTAL:
        errs.append("纯大写 courtish 漏网码 %d 个，校准靶 %d" % (len(pure), CAL_PURE_TOTAL))
    counts = Counter()
    for k in pure:
        got = bucket_of(fams[k])[0]
        counts[got] += 1
        want = ("B" if k in CAL_B else "C" if k in CAL_C else
                "D" if k in CAL_D else "A")
        if got != want:
            st = fams[k]
            errs.append("%s 期望 %s 实测 %s（无点 %d / 带点 %d / 卷号率 %.2f）"
                        % (k, want, got, st["undotted"], st["dotted"],
                           st["vol"] / max(1, st["undotted"] + st["dotted"])))
    for letter, n in CAL_BUCKET_COUNTS.items():
        if counts[letter] != n:
            errs.append("%s 桶 %d 个，校准靶 %d" % (letter, counts[letter], n))
    for k in CAL_A_REPS:
        if k not in fams or bucket_of(fams[k])[0] != "A":
            errs.append("%s 应在 A 桶（任务书明载）" % k)
    for k, (u, d) in CAL_ANCHORS.items():
        st = fams.get(k)
        got = (st["undotted"], st["dotted"]) if st else (-1, -1)
        if got != (u, d):
            errs.append("锚点 %s 实测 %d:%d，校准靶 %d:%d" % (k, got[0], got[1], u, d))
    if "AC" not in fams or bucket_of(fams["AC"])[0] != "C":
        errs.append("AC 应在 C 桶（任务书明载）")
    return errs, counts, pure


def report(fams, diag):
    buckets = {}
    for k, st in fams.items():
        buckets.setdefault(bucket_of(st)[0], []).append((k, st))
    for v in buckets.values():
        v.sort(key=lambda ks: -(ks[1]["undotted"] + ks[1]["dotted"] + sum(ks[1]["bare_variants"].values())))

    def n_rows(st):
        return st["undotted"] + st["dotted"] + sum(st["bare_variants"].values())

    print("== 分诊汇总 ==")
    print("   家族总数 %d：A %d / B %d / C %d / D %d / E(bare-only) %d"
          % (len(fams), len(buckets.get("A", [])), len(buckets.get("B", [])),
             len(buckets.get("C", [])), len(buckets.get("D", [])),
             len(buckets.get("E", []))))
    print("== A_NEUTRAL_CAND（Phase 2 溯源清单）==")
    print("   %-8s %-14s %6s %5s %5s %6s %7s  %s" %
          ("key", "代表印刷形", "br行", "bare", "无点", "带点", "优势比", "卷号率/序号位"))
    for k, st in buckets.get("A", []):
        rep = st["bracket_variants"].most_common(1)[0][0] if st["bracket_variants"] \
            else st["bare_variants"].most_common(1)[0][0]
        total = st["undotted"] + st["dotted"]
        serial = "序号位" + "/".join("%d×%d" % (l, n) for l, n in sorted(st["serial_lens"].items()))
        print("   %-8s %-14s %6d %5d %5d %5d %7s  %.2f | %s"
              % (k, rep, total, sum(st["bare_variants"].values()),
                 st["undotted"], st["dotted"], ratio_str(st),
                 st["vol"] / total if total else 0.0, serial))
    print("== D_HUMAN（1/3 < 优势比 < 3，须人核）==")
    for k, st in buckets.get("D", []):
        rep = st["bracket_variants"].most_common(1)[0][0] if st["bracket_variants"] \
            else st["bare_variants"].most_common(1)[0][0]
        total = st["undotted"] + st["dotted"]
        print("   %-8s %-14s 无点 %d / 带点 %d / 卷号率 %.2f / bare %d"
              % (k, rep, st["undotted"], st["dotted"],
                 st["vol"] / total if total else 0, sum(st["bare_variants"].values())))
    print("== B_REPORTER 头部（→ reporter_jurisdiction.csv 移交，全量见 --json）==")
    for k, st in buckets.get("B", [])[:25]:
        print("   %-10s %6d 行（卷号率 %.2f）" % (k, n_rows(st), st["vol"] / n_rows(st)))
    print("== C_REPORTER 头部（同上移交）==")
    for k, st in buckets.get("C", [])[:25]:
        print("   %-10s %6d 行" % (k, n_rows(st)))
    print("== E_BARE_ONLY（#35 乙，加拿大机构自用码线索）==")
    for k, st in buckets.get("E", []):
        print("   %-10s bare %d 行" % (k, sum(st["bare_variants"].values())))
    if diag:
        print("== 诊断：Civ/Crim 之外的疑似分庭词（现留噪声档，仅上报）==")
        for t, n in diag.most_common(10):
            print("   %-20s %d" % (t, n))
    ac = fams.get("AC")
    if ac:
        print("== AC 桶位锚 ==   无点 %d / 带点 %d（任务书 46:15,001，口径差异见 findings）"
              % (ac["undotted"], ac["dotted"]))


def json_dump(fams, diag, path):
    out = {"families": {}, "diag_divisionish": dict(diag)}
    for k, st in fams.items():
        total = st["undotted"] + st["dotted"]
        out["families"][k] = {
            "bucket": bucket_of(st),
            "undotted": st["undotted"], "dotted": st["dotted"],
            "vol_rows": st["vol"],
            "vol_rate": round(st["vol"] / total, 4) if total else None,
            "ratio": round(st["undotted"] / st["dotted"], 3) if st["dotted"] else None,
            "bare_rows": sum(st["bare_variants"].values()),
            "bracket_variants": sorted(([n, t] for t, n in st["bracket_variants"].items()),
                                       reverse=True),
            "bare_variants": sorted(([n, t] for t, n in st["bare_variants"].items()),
                                    reverse=True),
            "serial_lens": {str(l): n for l, n in sorted(st["serial_lens"].items())},
        }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n写入 %s" % path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assert-only", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    ok = run_static_assertions()
    if a.assert_only:
        sys.exit(0 if ok else 1)
    assert ok, "静态断言未全过，先修口径再看数字"
    fams, diag = scan_families()
    errs, counts, pure = run_calibration(fams)
    for e in errs:
        print("校准失败：%s" % e, file=sys.stderr)
    print("校准（75 纯大写码）：A %d / B %d / C %d / D %d —— %s"
          % (counts["A"], counts["B"], counts["C"], counts["D"],
             "全过" if not errs else "%d 条失败" % len(errs)), file=sys.stderr)
    report(fams, diag)
    if a.json:
        json_dump(fams, diag, a.json)
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
