# -*- coding: utf-8 -*-
"""disambiguation_audit.py — PROBLEMS #52：同形异义消歧「实际对不对」的三道验证

属**审计环**（见 audit/README.md）：读分类层与裁定层产出、决策表，产出数字与提案，
不喂任何生产脚本。

一、前缀的法域有没有印刷证据
    每个系列前缀后面跟的是哪些缩写族、年份跨度——L.R. 后面若全是英国 Law Reports
    的分辑，Q.R. 后面若全是魁北克的法院分辑，前缀的法域就由印出来的结构支撑。

二、区间规则拿「前缀标注」检验（留出法）
    带前缀的行，前缀已经把答案印出来了。把前缀遮住、只用卷号/年份区间去判，
    再与前缀给的答案比：一致 / 不一致 / 判不出。不一致的数就是区间规则的错误率。

三、同组旁证
    一件案子常被几本汇编同时收录。裁定层把它们合成一组后，组里别的汇编的法域
    是独立证据：被区间或前缀判成英国的行，同组的旁证应当是英国汇编；判成魁北克
    的，旁证应当是加拿大/魁北克汇编。只取表里**单一法域**的族当旁证。

用法
    python audit/disambiguation_audit.py      # 读 data/classify_out/、data/decide_out/cross_court/
"""
import csv
import io
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import classify                                               # noqa: E402
from normalize import nk, normalize_code                      # noqa: E402

OUT = os.path.join(ROOT, "audit", "findings", "disambiguation_report.md")
CANADIAN = {"CA", "QC", "ON", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE", "YK", "NT", "NU"}


def compatible(judged, companion):
    if judged == companion:
        return True
    return judged in CANADIAN and companion in CANADIAN and "CA" in (judged, companion)


def main():
    csv.field_size_limit(10 ** 9)
    table = classify.load_table("reporter_jurisdiction.csv")
    by_nk = defaultdict(list)
    for r in table:
        by_nk[nk(r["abbreviation"])].append(r)
    single = {k: rs[0]["jurisdiction"] for k, rs in by_nk.items()
              if len({r["jurisdiction"] for r in rs}) == 1}
    prefixes = {normalize_code(r["canonical_prefix"]): r.get("jurisdiction", "")
                for r in classify.load_table("series_prefix.csv")}

    comp = defaultdict(Counter)
    years = defaultdict(list)
    hold = Counter()
    hold_ex = []
    rows_by_key = {}
    for court in ("SCC", "ONCA"):
        with open(os.path.join(ROOT, "data", "classify_out", court, "classified.csv"),
                  encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                k = nk(r["abbreviation"] or "")
                pf = normalize_code(r["leading_abbr"] or "") if r["leading_abbr"] else ""
                if pf in prefixes:
                    comp[pf][k] += 1
                    if r["year_start"].isdigit():
                        years[pf].append(int(r["year_start"]))
                    cands = by_nk.get(k, [])
                    if len({c["jurisdiction"] for c in cands}) > 1:
                        got = classify.disambiguate_by_structure(r, cands)
                        want = prefixes[pf]
                        tag = "判不出" if got == "UNSUPPORTED" else ("一致" if got == want else "不一致")
                        hold[(k, tag)] += 1
                        if tag == "不一致" and len(hold_ex) < 10:
                            hold_ex.append((r["raw_string"], want, got))

    # 三、同组旁证：读裁定层跨院产出
    groups = defaultdict(list)
    with open(os.path.join(ROOT, "data", "decide_out", "cross_court", "decided.csv"),
              encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            groups[r["merged_group_id"]].append(r)
    # 裁定层的行是归并键级，不带 disambiguated_by；回分类层按 (法院, 归并键) 取消歧方式
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import merge                                              # noqa: E402
    how = {}
    for court in ("SCC", "ONCA"):
        with open(os.path.join(ROOT, "data", "classify_out", court, "classified.csv"),
                  encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r["disambiguated_by"] and not r["rejected_reason"]:
                    how[(court, merge.build_merge_key(r))] = (r["disambiguated_by"], r["jurisdiction"],
                                                               nk(r["abbreviation"] or ""))
    side = Counter()
    side_ex = []
    for ms in groups.values():
        for m in ms:
            h = how.get((m["court"], m["merge_key"]))
            if not h:
                continue
            method, judged, fam = h
            others = {single[nk(o["abbreviation"] or "")] for o in ms
                      if o is not m and nk(o["abbreviation"] or "") in single
                      and o["jurisdiction"] not in ("", "UNSUPPORTED")}
            if not others:
                side[(fam, method, "无旁证")] += 1
            elif all(compatible(judged, o) for o in others):
                side[(fam, method, "旁证一致")] += 1
            else:
                side[(fam, method, "旁证冲突")] += 1
                if len(side_ex) < 12:
                    side_ex.append((m["canonical_string"], judged, sorted(others),
                                    " / ".join(o["canonical_string"] for o in ms[:4])))

    o = io.StringIO()
    w = o.write
    w("# PROBLEMS #52：同形异义消歧的三道验证\n\n仪器：`audit/disambiguation_audit.py`（可重放）。\n\n")
    w("## 一、前缀后随的缩写族（前缀法域的印刷证据）\n\n| 前缀 | 表内法域 | 后随族（前 10） | 年份 |\n|---|---|---|---|\n")
    for pf in sorted(comp):
        ys = years[pf]
        w("| %s | %s | %s | %s |\n" % (pf, prefixes[pf], ", ".join("%s %d" % kv for kv in comp[pf].most_common(10)),
                                       ("%d–%d" % (min(ys), max(ys))) if ys else "-"))
    w("\n## 二、区间规则 vs 前缀标注（遮住前缀、只用卷号/年份判）\n\n| 族 | 一致 | 不一致 | 判不出 |\n|---|---:|---:|---:|\n")
    for fam in sorted({k for k, _ in hold}):
        w("| %s | %d | %d | %d |\n" % (fam, hold[(fam, "一致")], hold[(fam, "不一致")], hold[(fam, "判不出")]))
    tot_ok = sum(v for (k, t), v in hold.items() if t == "一致")
    tot_bad = sum(v for (k, t), v in hold.items() if t == "不一致")
    w("\n合计：一致 %d、不一致 %d（**区间判出者中的错误率 %.2f%%**）。\n" % (
        tot_ok, tot_bad, 100.0 * tot_bad / (tot_ok + tot_bad) if tot_ok + tot_bad else 0))
    if hold_ex:
        w("\n不一致的例：\n\n")
        for raw, want, got in hold_ex:
            w("- `%s`：前缀说 %s，区间判 %s\n" % (raw, want, got))
    w("\n## 三、同组旁证（组里其他汇编中，表内只有单一法域者）\n\n| 族 | 消歧方式 | 旁证一致 | 旁证冲突 | 无旁证 |\n|---|---|---:|---:|---:|\n")
    for fam, method in sorted({(f, m) for f, m, _ in side}):
        w("| %s | %s | %d | %d | %d |\n" % (fam, method, side[(fam, method, "旁证一致")],
                                           side[(fam, method, "旁证冲突")], side[(fam, method, "无旁证")]))
    if side_ex:
        w("\n旁证冲突的例：\n\n")
        for raw, judged, others, members in side_ex:
            w("- `%s` 判 %s，旁证 %s；组内：%s\n" % (raw, judged, ",".join(others), members))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(o.getvalue())
    print(o.getvalue())


if __name__ == "__main__":
    main()
