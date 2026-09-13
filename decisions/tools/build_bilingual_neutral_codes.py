# -*- coding: utf-8 -*-
"""build_bilingual_neutral_codes.py — 生成 decisions/bilingual_neutral_codes.csv

确定性、离线（不联网）。从 decisions/neutral_court_codes.csv 的 source_locator
解析 databaseId、caseBrowse en/fr 端点与佐证引证，按 (databaseId, jurisdiction)
分组配对；再扫描 decisions/ 下其他本地决策表的说明文字，找「同案双语对应」的
显式证据（同 年份+编号 的两个不同代码成对出现，如 2014 CSC 7 = 2014 SCC 7）。

状态语义（只有 verified_explicit_equivalence 参与身份等价）：
  verified_explicit_equivalence  本地决策资料存在显式同案双语对应证据
  candidate_endpoint_pair        同库、en+fr 端点配对（候选，不自动授权）
  unverified_same_db_en_only     同库但只见 en 端点（如 FC/CF）
  unverified_same_database       同库、配对证据不足
  rejected_renamed_code          同库同语言端点 + 佐证引证年代不相交（改名/时代转换，
                                 如 ABQB/ABKB、SKQB/SKKB、NFCA/NLCA）

用法：python decisions/tools/build_bilingual_neutral_codes.py [--out decisions/bilingual_neutral_codes.csv]
重跑幂等：同样输入产出逐字节相同的输出（行按 code_en,code_fr 稳定排序）。
"""
import argparse
import csv
import datetime
import os
import re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DEC = os.path.dirname(HERE)

ALLOWED_BILINGUAL_STATUSES = {
    "verified_explicit_equivalence",
}

# 同案双语对应证据：同一年 + 同一决定编号 + 两个不同代码
# （形如「2014 CSC 7 = 2014 SCC 7」「[2014] 1 R.C.S. 87」整行说明中出现）
WITNESS_RE = re.compile(
    r"(?<!\d)(20\d{2})\s+([A-Z][A-Za-z]{1,11})\s+(\d{1,5})\s*(?:=|＝|／|/)\s*"
    r"(?:\(?19|20)?\d{0,2}\)?\s*([A-Z][A-Za-z]{1,11})\s+\3(?!\d)")

DB_RE = re.compile(r"databaseId=([a-z0-9\-]+)")
EP_RE = re.compile(r"endpoint=(https://api\.canlii\.org/v1/caseBrowse/(en|fr)/[^\s;]*)")
WITNESS_CITE_RE = re.compile(r"(\d{4})\s+([A-Z][A-Za-z]{1,11})\s+\d+")


def load_rows(name):
    path = os.path.join(DEC, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if any((v or "").strip()
                                                    for v in r.values())]


def parse_codes():
    """按 (databaseId, jurisdiction) 分组；每行记 code / lang(端点语言) /
    佐证引证年代集合。"""
    groups = defaultdict(list)
    for r in load_rows("neutral_court_codes.csv"):
        loc = r.get("source_locator") or ""
        db = DB_RE.search(loc)
        ep = EP_RE.search(loc)
        if not db or not ep:
            continue
        years = {int(y) for y, _c in WITNESS_CITE_RE.findall(loc)}
        groups[(db.group(1), (r.get("jurisdiction") or "").strip())].append({
            "code": (r["court_code"] or "").strip(),
            "lang": ep.group(2),
            "endpoint": ep.group(1),
            "years": years,
        })
    return groups


def explicit_witness_pairs():
    """扫描本地决策表的说明/来源字段，找同案双语对应显式证据。
    返回 {frozenset({code_a_lower, code_b_lower}): 证据描述}。"""
    witnesses = {}
    files = ("court_or_reporter_scope.csv", "neutral_court_codes.csv",
             "series_prefix.csv", "case_origin.csv")
    for name in files:
        for r in load_rows(name):
            for field, text in r.items():
                if not text or len(text) < 10:
                    continue
                for m in WITNESS_RE.finditer(text):
                    a, b = nk_code(m.group(2)), nk_code(m.group(4))
                    if a == b:
                        continue
                    key = frozenset((a, b))
                    ev = ("%s:%s 「%s %s %s = %s %s」同案双语对应（本地决策资料）"
                          % (name, field, m.group(1), m.group(2), m.group(3),
                             m.group(4), m.group(3)))
                    witnesses.setdefault(key, ev)
    return witnesses


def nk_code(code):
    return re.sub(r"[^a-z0-9]", "", (code or "").lower())


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(DEC, "bilingual_neutral_codes.csv"))
    args = ap.parse_args()

    groups = parse_codes()
    witnesses = explicit_witness_pairs()
    known_codes = {(r["court_code"] or "").strip()
                   for r in load_rows("neutral_court_codes.csv")}

    rows = []
    for (db, jur), members in sorted(groups.items()):
        ens = [m for m in members if m["lang"] == "en"]
        frs = [m for m in members if m["lang"] == "fr"]
        # 同库内两两配对（每组通常 ≤2 个代码；多代码时两两组合，确定性排序）
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                pair_codes = sorted([a["code"], b["code"]])
                # 只收两代码都在法院代码表里的对
                if not all(c in known_codes for c in pair_codes):
                    continue
                code_en, code_fr = pair_codes
                pair_key = frozenset((nk_code(code_en), nk_code(code_fr)))
                same_lang = a["lang"] == b["lang"]
                years_overlap = bool(a["years"] & b["years"])
                if pair_key in witnesses:
                    status = "verified_explicit_equivalence"
                    evidence = witnesses[pair_key]
                    note = ("本地显式同案双语证据升级；端点 %s | %s"
                            % (a["endpoint"][:70], b["endpoint"][:70]))
                elif not same_lang:
                    status = "candidate_endpoint_pair"
                    evidence = ("databaseId=%s; jurisdiction=%s; en=%s; fr=%s"
                                % (db, jur, a["code"] if a["lang"] == "en" else b["code"],
                                   b["code"] if b["lang"] == "fr" else a["code"]))
                    note = ("同库 en+fr 端点配对——仅候选；共享 databaseId 不构成身份"
                            "授权；升级须本地显式同案双语证据")
                elif same_lang and not years_overlap:
                    status = "rejected_renamed_code"
                    evidence = ("databaseId=%s; jurisdiction=%s; 同语言端点(%s)；"
                                "佐证引证年代不相交（%s vs %s）——属改名/时代转换代码"
                                % (db, jur, a["lang"],
                                   sorted(a["years"]), sorted(b["years"])))
                    note = "改名/时代转换代码对，不得因同库同年同号当成双语代码"
                elif same_lang:
                    status = "unverified_same_db_en_only" if a["lang"] == "en" \
                        else "unverified_same_database"
                    evidence = ("databaseId=%s; jurisdiction=%s; 同语言端点(%s)；"
                                "佐证引证年代相交(%s)——无法据库/年/号判定"
                                % (db, jur, a["lang"], sorted(a["years"] & b["years"])))
                    note = "同库但无跨语言端点配对，保持未核实"
                else:
                    status = "unverified_same_database"
                    evidence = "databaseId=%s; jurisdiction=%s" % (db, jur)
                    note = "配对证据不足，保持未核实"
                rows.append({
                    "code_en": code_en if nk_code(code_en) == nk_code(pair_codes[0])
                    else code_fr,
                    "code_fr": code_fr,
                    "canlii_database_id": db,
                    "verification_status": status,
                    "evidence": evidence,
                    "note": note,
                    "added_by": "decisions/tools/build_bilingual_neutral_codes.py (deterministic)",
                    "added_date": "2026-09-13",
                })

    # code_en/code_fr 规范：本表不区分真实语言方向，存为无方向的代码对；
    # 列名沿用任务书要求（code_en=字典序较小者），加载方只看无方向对
    rows.sort(key=lambda r: (r["code_en"], r["code_fr"]))
    fields = ["code_en", "code_fr", "canlii_database_id", "verification_status",
              "evidence", "note", "added_by", "added_date"]
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, args.out)
    stat = defaultdict(int)
    for r in rows:
        stat[r["verification_status"]] += 1
    print("written %s  pairs=%d  %s" % (args.out, len(rows), dict(sorted(stat.items()))))


if __name__ == "__main__":
    main()
