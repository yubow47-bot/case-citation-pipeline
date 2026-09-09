# -*- coding: utf-8 -*-
"""build_neutral_court_codes.py — 由 CanLII API 生成 decisions/neutral_court_codes.csv

**这不是生产线脚本。** 它产出的是决策表行（膜允许穿过的三样东西之一，见 audit/README.md），
不是管线数据。管线只读 decisions/*.csv，从不调用本脚本，也不联网。
本脚本只在人决定重建/扩充表时手动运行。

来源：CanLII API v1 `caseBrowse`
  阶段 1  GET /v1/caseBrowse/en/                 → 全部案例库（databaseId / jurisdiction / name）
  阶段 2  GET /v1/caseBrowse/en/{db}/            → 每库 5 条案例的 citation 字段
  阶段 3  同上 + &decisionDateBefore=...          → 改过名的法院取历史码

**court_code 取自 citation 串里印刷的那一段，不是 databaseId 推的**（约束七）。
实测 409 库中 118 个 databaseId.upper() 与真实代码不符（csc-scc→SCC、fct→FC…）。

两道拒收闸（约束四，宁可 UNSUPPORTED 不猜）：
  a) 同一 code 在两库对应不同 jurisdiction → 不写行，列入 conflicts
  b) 证据来自 ukpc 的一律不写 —— CanLII 的 jurisdiction 字段是“馆藏归属”不是“法院法域”，
     枢密院收在 ca 馆藏下（PROBLEMS #32）
另：`CanLII` 伪代码跳过（PROBLEMS #31）；孤证行单列供人复核。

API key：环境变量 CANLII_API_KEY，或 --key-file 指向的文件首行。key 不进仓库、不进输出。
限速：每次调用间隔 1.0s（用户明确要求“不要用太猛”）。缓存写 --cache-dir，重跑只补缺口。

用法：
    set CANLII_API_KEY=...
    python decisions/tools/build_neutral_court_codes.py --cache-dir <目录>
    python decisions/tools/build_neutral_court_codes.py --cache-dir <目录> --offline   # 只重建表
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "decisions", "neutral_court_codes.csv")
SOURCE = "CanLII API v1 caseBrowse"
BASE = "https://api.canlii.org/v1/caseBrowse/en/"

# 中立引用的印刷形：`YYYY <CODE> <n>`
RX_CODE = re.compile(r"\b(?:1[6-9]|20)\d{2}\s+([A-Za-z][A-Za-z0-9]*)\s+\d+")


def nk(code):
    """与 pipeline/normalize.py 的 normalize_code 同口径（去点/空格/连字符，转大写）。"""
    return re.sub(r"[.\s\-]", "", code).upper()


# 改过名的法院：库 → 该库在旧年份能佐证的历史码（注释仅供人读，不进表）
LEGACY = {
    "2018-01-01": {
        "abkb": "ABQB  Queen's Bench -> King's Bench (2022)",
        "abcj": "ABPC  Provincial Court -> Court of Justice (2023)",
        "skkb": "SKQB", "mbkb": "MBQB", "nbkb": "NBQB",
        "nlca": "NFCA", "nlsctd": "NLTD / NLSC",
        "ntsc": "NWTSC", "ntca": "NWTCA", "nttc": "NWTTC",
        "pescad": "PECA", "pesctd": "PESC",
        "onlst": "ONLSTH / ONLSHP / ONLSTA / ONLSAP",
        "bcsec": "BCSECCOM", "sct-trp": "SCTC",
        "pslreb": "PSLRB", "pssrb": "PSSRB",
        "yksc": "YKSC", "ykca": "YKCA",
    },
    "1998-01-01": {"nlca": "", "nlsctd": "", "ntsc": "", "pescad": "", "abcj": ""},
    # 定向探针：上面两个时点落在改名区间之外的三个码
    "2003-01-01": {"fct": "FCT  Federal Court Trial Division (1998-2003)"},
    "2012-01-01": {"nlsctd": "NLTD"},
    "2002-01-01": {"nlca": "NFCA"},
}


def get_key(args):
    k = os.environ.get("CANLII_API_KEY")
    if k:
        return k.strip()
    if args.key_file and os.path.exists(args.key_file):
        for line in open(args.key_file, encoding="utf-8", errors="replace"):
            if line.strip():
                return line.strip()
    sys.exit("需要 API key：设 CANLII_API_KEY 环境变量，或传 --key-file")


def fetch(url, key):
    sep = "&" if "?" in url else "?"
    with urllib.request.urlopen(url + sep + "api_key=" + key, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def harvest(key, cache_dir, offline):
    """返回 (dbs, evidence)。evidence: code -> jurisdiction(大写) -> [(db, citation, before)]"""
    os.makedirs(cache_dir, exist_ok=True)
    dbpath = os.path.join(cache_dir, "databases.json")
    if not os.path.exists(dbpath):
        if offline:
            sys.exit("--offline 但无 databases.json 缓存")
        json.dump(fetch(BASE, key), open(dbpath, "w", encoding="utf-8"),
                  ensure_ascii=False)
    dbs = {d["databaseId"]: d
           for d in json.load(open(dbpath, encoding="utf-8"))["caseDatabases"]}
    print("案例库 %d" % len(dbs), file=sys.stderr)

    passes = [(None, list(dbs))] + [(b, list(t)) for b, t in LEGACY.items()]
    evidence = defaultdict(lambda: defaultdict(list))
    for before, targets in passes:
        cpath = os.path.join(cache_dir, "cases_%s.json" % (before or "recent"))
        cache = json.load(open(cpath, encoding="utf-8")) if os.path.exists(cpath) else {}
        todo = [d for d in targets if d not in cache and d in dbs]
        if todo and offline:
            print("  [%s] --offline，跳过 %d 个未缓存库" % (before or "recent", len(todo)),
                  file=sys.stderr)
            todo = []
        for i, db in enumerate(todo):
            url = "%s%s/?offset=0&resultCount=5" % (BASE, db)
            if before:
                url += "&decisionDateBefore=" + before
            for attempt in range(2):
                try:
                    cache[db] = fetch(url, key).get("cases", [])
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 429 and attempt == 0:
                        time.sleep(20)
                        continue
                    cache[db] = {"_error": "HTTP %s" % e.code}
                    break
                except Exception as e:                       # noqa: BLE001
                    if attempt == 0:
                        time.sleep(5)
                        continue
                    cache[db] = {"_error": type(e).__name__}
                    break
            if (i + 1) % 20 == 0:
                json.dump(cache, open(cpath, "w", encoding="utf-8"), ensure_ascii=False)
                print("  [%s] %d/%d" % (before or "recent", i + 1, len(todo)),
                      file=sys.stderr)
            time.sleep(1.0)
        json.dump(cache, open(cpath, "w", encoding="utf-8"), ensure_ascii=False)

        for db, cases in cache.items():
            if isinstance(cases, dict) or not cases:
                continue
            for c in cases:
                m = RX_CODE.search(c.get("citation") or "")
                if m:
                    evidence[m.group(1)][dbs[db]["jurisdiction"].upper()].append(
                        (db, c["citation"], before))
    return dbs, evidence


def build(dbs, evidence, added_date):
    rows, conflicts, skipped, singleton = [], [], [], []
    for code in sorted(evidence, key=str.upper):
        jurs = evidence[code]
        if code == "CanLII":
            skipped.append((code, "CanLII 伪代码：法域在尾括注里，本表无法承载（PROBLEMS #31）"))
            continue
        if any(db == "ukpc" for ev in jurs.values() for (db, _, _) in ev):
            skipped.append((code, "证据来自 ukpc：CanLII jurisdiction 是馆藏归属非法院法域"
                                  "（PROBLEMS #32）"))
            continue
        if len(jurs) > 1:
            conflicts.append((code, {j: ev[0][0] for j, ev in jurs.items()}))
            continue
        (jur, ev), = jurs.items()
        db, cite, before = ev[0]
        if len(ev) == 1:
            singleton.append((code, jur, db, cite))
        d = dbs[db]
        loc = ('databaseId=%s; jurisdiction="%s"; name="%s"; 佐证引证="%s"; '
               'endpoint=%s%s/?offset=0&resultCount=5%s'
               % (db, d["jurisdiction"], d["name"], cite, BASE, db,
                  "&decisionDateBefore=" + before if before else ""))
        rows.append([code, nk(code), jur, SOURCE, loc, added_date])
    return rows, conflicts, skipped, singleton


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--key-file")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--added-date", default=time.strftime("%Y-%m-%d"))
    a = ap.parse_args()

    key = "" if a.offline else get_key(a)
    dbs, evidence = harvest(key, a.cache_dir, a.offline)
    rows, conflicts, skipped, singleton = build(dbs, evidence, a.added_date)

    assert not conflicts, "存在法域冲突，需人裁后再写表：%r" % conflicts
    assert len({r[0] for r in rows}) == len(rows), "court_code 重复"
    assert all(r[1] == nk(r[0]) for r in rows), "normalized_key 与 nk() 不一致"
    assert all(all(r) for r in rows), "有行字段为空（约束八）"

    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["court_code", "normalized_key", "jurisdiction",
                    "source", "source_locator", "added_date"])
        w.writerows(rows)
    print("写入 %d 行 -> %s" % (len(rows), OUT), file=sys.stderr)
    print("冲突 %d / 跳过 %d / 孤证 %d" % (len(conflicts), len(skipped), len(singleton)),
          file=sys.stderr)
    for c, why in skipped:
        print("  跳过 %-10s %s" % (c, why), file=sys.stderr)
    for c, j, db, cite in singleton:
        print("  孤证 %-12s %-3s %-12s %s" % (c, j, db, cite), file=sys.stderr)


if __name__ == "__main__":
    main()
