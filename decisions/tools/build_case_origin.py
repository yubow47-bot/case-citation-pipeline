# -*- coding: utf-8 -*-
"""build_case_origin.py — 建 decisions/case_origin.csv 的枢密院部分（规格 §5.4，PROBLEMS #59）

问题：[1896] A.C. 348 这类判决登在英国出的汇编上，reporter 法域是 GB，案子却是枢密院
审理的**加拿大上诉案**。不填这张表，研究「外国法影响」的人会把几百件加拿大案子当成英国判例。

来源：CanLII API v1 `caseBrowse/en/ukpc/`——CanLII 收录的枢密院对加拿大上诉的判决库
（库内全部是加拿大来源，#32 记过它的 jurisdiction 字段为 ca）。一次调用取全表，缓存。

为什么要按案名 + 年份去对：CanLII 记录只有标题、判决年份、CanLII 自己的引证，**不给 A.C.
页码**；表的键却必须是印刷引证串（约束七）。所以用「本管线里印着 A.C./App. Cas. 等的组
的案名 + 年份」去对 CanLII 标题。对上即说明这串印刷引证是一件加拿大上诉案。

判据（宁缺毋滥，约束四）：
  · 年份：CanLII 判决年 ∈ [报告年 − 2, 报告年]（A.C. 按出版年编，常晚于判决年）
  · 案名：双方各自比词集（去掉 Ltd./Co./Attorney General/the 等泛词）；两方都要对上，
    允许原被告顺序颠倒（上诉时常对调）；一方去泛词后为空（如 Hodge v. The Queen 的右方），
    须两边都空才算对上
  · 同一印刷串对上多条 CanLII 记录不算歧义——库里全是加拿大来源，来源地都是 CA
不收：没有案名的组（无证据）、House of Lords 汇编（H.L. 不审加拿大上诉）、
      非加拿大来源的枢密院案（Makin v. A-G for New South Wales）——CanLII 库里本就没有，保持 UNDETERMINED

用法
    python decisions/tools/build_case_origin.py --key-file "C:/api key/canlii.txt" --cache-dir <目录>
    python decisions/tools/build_case_origin.py --cache-dir <目录> --offline      # 只用缓存重建
输入：data/select_out/selected.csv（裁定层全部列 + kept）与两院 merge_out/*/folded_log.csv（取每个键的全部印刷写法）
输出：decisions/case_origin.csv（表非空时拒绝覆盖，除非 --replace）、
      audit/findings/case_origin_review.md（逐条对照、疑似漏网、已知案例核对）
"""
import argparse
import csv
import datetime
import json
import os
import re
import sys
import time
import urllib.request
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from normalize import nk  # noqa: E402

LIST_URL = "https://api.canlii.org/v1/caseBrowse/en/ukpc/?offset=%d&resultCount=10000"
SOURCE = "CanLII ukpc（枢密院对加拿大上诉判决库，API v1 caseBrowse）"
FIELDS = ["citation_display", "normalized_key", "case_origin", "deciding_court",
          "source", "source_locator", "added_date"]
# 枢密院判决常见的英国汇编（A.C. 与 App. Cas. 同时刊登上议院判决，靠案名去分）
PC_REPORTER = re.compile(r"^(A\.? ?C\.?|App\.? ?Cas\.?|P\.? ?C\.?|L\.? ?R\.? ?P\.? ?C\.?|"
                         r"Moo\.? ?P\.? ?C\.?(?: ?N\.? ?S\.?)?|All ?E\.? ?R\.?|W\.? ?L\.? ?R\.?|T\.? ?L\.? ?R\.?)$")
STOP = {"the", "of", "for", "and", "et", "al", "ltd", "limited", "co", "company", "inc", "corp",
        "corporation", "cie", "in", "re", "a", "an", "de", "la", "le", "du", "des", "ex", "parte",
        "attorney", "general", "attorneygeneral", "his", "her", "majesty", "king", "queen", "rex",
        "regina", "r", "dominion", "others", "another", "anor", "ors", "province", "city", "town"}
KNOWN_CA = ["Parsons", "Hodge v. The Queen", "Union Colliery", "John Deere", "Snider",
            "Attorney-General for Ontario v. Attorney-General for the Dominion"]
KNOWN_NOT = ["Donoghue", "Anns v. Merton", "Makin", "Hedley Byrne", "Salomon", "Woolmington"]


def parties(name):
    s = name.lower().replace("&", " and ").replace("’", "'")
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    s = re.sub(r"'s\b", "", s)
    halves = re.split(r"\bv\b|\bvs\b", s, maxsplit=1)
    if len(halves) != 2:
        return None
    return tuple(frozenset(t for t in h.split() if t not in STOP and len(t) > 1) for h in halves)


def side_ok(a, b):
    if not a and not b:
        return True
    if not a or not b:
        return False
    return len(a & b) / len(a | b) >= 0.5 or a <= b or b <= a


def same_case(p, q):
    return (side_ok(p[0], q[0]) and side_ok(p[1], q[1])) or (side_ok(p[0], q[1]) and side_ok(p[1], q[0]))


def fetch_all(key, cache_dir, offline):
    path = os.path.join(cache_dir, "ukpc_list.json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    if offline:
        sys.exit("--offline 但缓存里没有 ukpc_list.json")
    out, off = [], 0
    while True:
        url = LIST_URL % off
        with urllib.request.urlopen(url + "&api_key=" + key, timeout=60) as r:
            got = json.loads(r.read().decode("utf-8")).get("cases", [])
        out.extend(got)
        time.sleep(1.0)                       # 用户要求：测试用、别打太猛
        if len(got) < 10000:
            break
        off += 10000
    os.makedirs(cache_dir, exist_ok=True)
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key-file")
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--replace", action="store_true")
    # 选取层产出 = 裁定层全部列 + kept；报告要分过没过门槛
    ap.add_argument("--decided", default=os.path.join(ROOT, "data/select_out/selected.csv"))
    args = ap.parse_args()
    key = ""
    if not args.offline:
        key = os.environ.get("CANLII_API_KEY", "").strip()
        if not key and args.key_file:
            key = next((l.strip() for l in open(args.key_file, encoding="utf-8", errors="replace") if l.strip()), "")
        if not key:
            sys.exit("需要 API key")
    csv.field_size_limit(10 ** 9)

    recs = []
    for c in fetch_all(key, args.cache_dir, args.offline):
        cid = c["caseId"]["en"] if isinstance(c.get("caseId"), dict) else c.get("caseId", "")
        if not cid[:4].isdigit():
            continue
        p = parties(c.get("title", ""))
        if p:
            recs.append({"year": int(cid[:4]), "title": c.get("title", ""), "url": c.get("longUrl", ""),
                         "citation": c.get("citation", ""), "p": p})
    by_year = defaultdict(list)
    for r in recs:
        by_year[r["year"]].append(r)

    raws = defaultdict(set)                   # (court, merge_key) -> 全部印刷写法
    for court in ("SCC", "ONCA"):
        with open(os.path.join(ROOT, "data/merge_out/%s/folded_log.csv" % court), encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                raws[(court, r["merge_key"])].add(r["raw_string"])
    groups = defaultdict(list)
    with open(args.decided, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            groups[r["merged_group_id"]].append(r)

    rows, matched, cand_n = {}, [], 0
    unmatched_ca = []
    CAN = re.compile(r"Canad|Ontario|Quebec|Québec|Montreal|Toronto|British Columbia|Alberta|Manitoba|"
                     r"Saskatchewan|Nova Scotia|New Brunswick|Newfoundland|Dominion|Winnipeg|Vancouver", re.I)
    today = datetime.date.today().isoformat()
    for gid, ms in groups.items():
        gb = [m for m in ms if m["jurisdiction"] == "GB" and PC_REPORTER.match((m["abbreviation"] or "").strip())]
        if not gb:
            continue
        p0 = next(m for m in ms if m["is_primary"] == "true")
        name = p0["case_name_modal"]
        years = {int(m["merge_key"].split("|")[0]) for m in ms if m["merge_key"].split("|")[0].isdigit()}
        cand_n += 1
        pp = parties(name) if name else None
        if not pp or not years:
            continue
        hits = [r for y in years for yy in range(y - 2, y + 1) for r in by_year.get(yy, []) if same_case(pp, r["p"])]
        hits = list({h["url"]: h for h in hits}.values())
        if not hits:
            if CAN.search(name):
                unmatched_ca.append((int(p0["distinct_decisions_count"]), name, sorted(years), p0["canonical_string"]))
            continue
        matched.append((int(p0["distinct_decisions_count"]), p0["kept"], name, sorted(years), hits, [m["canonical_string"] for m in gb]))
        loc = " ; ".join("%s（CanLII 标题「%s」，%d）" % (h["url"], h["title"], h["year"]) for h in hits[:3])
        loc += "｜依据：本管线组案名「%s」与 CanLII 标题双方对上、判决年 ∈ 报告年−2..报告年" % name
        for m in gb:
            for raw in raws.get((m["court"], m["merge_key"]), {m["canonical_string"]}):
                k = nk(raw)
                if k and k not in rows:
                    rows[k] = {"citation_display": raw, "normalized_key": k, "case_origin": "CA",
                               "deciding_court": "JCPC", "source": SOURCE, "source_locator": loc,
                               "added_date": today}

    out = os.path.join(ROOT, "decisions", "case_origin.csv")
    with open(out, encoding="utf-8", newline="") as f:
        existing = [r for r in csv.DictReader(f) if any((v or "").strip() for v in r.values())]
    if existing and not args.replace:
        sys.exit("case_origin.csv 已有 %d 行，拒绝覆盖（加 --replace）" % len(existing))
    with open(out + ".tmp", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\r\n")
        w.writeheader()
        w.writerows(sorted(rows.values(), key=lambda r: r["normalized_key"]))
    os.replace(out + ".tmp", out)

    # ---- 复核报告
    def check(names):
        res = []
        for n in names:
            m = [x for x in matched if n.lower() in x[2].lower()]
            res.append("- `%s`：%s" % (n, "对上（%s）" % "; ".join(h["title"] for h in m[0][4][:2]) if m else "未对上"))
        return res
    rep = ["# case_origin.csv 枢密院部分：逐条对照（PROBLEMS #59）", "",
           "仪器：`decisions/tools/build_case_origin.py`（可重放，`--offline` 只用缓存）。", "",
           "- CanLII ukpc 记录：%d 条（可解析出双方者）" % len(recs),
           "- 本管线候选组（GB 法域、印在枢密院类汇编上）：%d" % cand_n,
           "- 对上：%d 组（其中过门槛 %d）→ 表 %d 行（每种印刷写法一行）" % (
               len(matched), sum(1 for x in matched if x[1] == "true"), len(rows)),
           "- 对上多条 CanLII 记录的组：%d（同名不同年的系列案；库里全是加拿大来源，来源地不受影响）"
           % sum(1 for x in matched if len(x[4]) > 1), "",
           "## 已知案例核对", "", "应对上（加拿大上诉案）：", ""] + check(KNOWN_CA) + [
           "", "不应对上（英国本土 / 其他英联邦上诉）：", ""] + check(KNOWN_NOT) + [
           "", "## 对上的组（按 dd 降序，全列）", "", "| dd | 过门槛 | 本管线案名 | 年份 | CanLII 标题（年） | 印刷写法 |",
           "|---:|---|---|---|---|---|"]
    for d, kept, name, ys, hits, cs in sorted(matched, key=lambda x: -x[0]):
        rep.append("| %d | %s | %s | %s | %s | %s |" % (d, "是" if kept == "true" else "", name.replace("|", "/"),
                   "/".join(map(str, ys)), "; ".join("%s（%d）" % (h["title"].replace("|", "/"), h["year"]) for h in hits[:2]),
                   "; ".join(cs[:2]).replace("|", "/")))
    rep += ["", "## 疑似漏网：案名含加拿大地名却没对上的（按 dd 降序，前 60）", "",
            "多为非加拿大来源的同名案、CanLII 标题写法差得太远、或年份超窗。按约束四不猜，留 UNDETERMINED。", ""]
    for d, name, ys, c in sorted(unmatched_ca, reverse=True)[:60]:
        rep.append("- dd %d `%s` %s — %s" % (d, name, ys, c))
    rp = os.path.join(ROOT, "audit", "findings", "case_origin_review.md")
    open(rp, "w", encoding="utf-8", newline="\n").write("\n".join(rep) + "\n")
    print("\n".join(rep[:20]))
    print("... 报告 ->", rp)


if __name__ == "__main__":
    main()
