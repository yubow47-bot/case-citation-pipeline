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

三道拒收闸（约束四，宁可 UNSUPPORTED 不猜）：
  a) 同一 code 在两库对应不同 jurisdiction → 不写行，列入 conflicts
  b) 证据来自 ukpc 的一律不写 —— CanLII 的 jurisdiction 字段是“馆藏归属”不是“法院法域”，
     枢密院收在 ca 馆藏下（PROBLEMS #32）
  c) 库名同时点到两个以上法域的机构不写 —— 该法域本身就不是单值，本表一 code 一 jurisdiction
     的形状承载不了（PROBLEMS #34）。实例：ntwcat / nuwcat 是同一个跨 NT+NU 的工伤上诉庭
     挂了两次，只因 nuwcat 无案例才没触发闸 a
另：`CanLII` 伪代码跳过（PROBLEMS #31）；孤证行单列供人复核。

**证据择优（PROBLEMS #34）**：同一 code 常有多个库供证，早期版本取 `ev[0]`（缓存插入序），
导致 QCCQ 的证据来自牙科纪律委员会库、NSSC 来自遗嘱认证库——法域没错但证据链成色差。
现按「库名归一后等于代码」优先，其次按该库内印此码的样本数降序。

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
    "2012-01-01": {"nlsctd": "NLTD", "nbpc": "NBPC", "onsec": "ONSEC"},
    "2002-01-01": {"nlca": "NFCA"},
    # 第二轮补采（2026-09-09）：语料漏网清单里逐个反查出的真码，见 PROBLEMS #34。
    # 这些码在最近 5 条样本里看不见——法院/庭改了名，或最近判决恰好全是同库的另一个庭。
    "2020-01-01": {"nlsctd": "NLSCTD", "nsuarb": "NSUARB"},
    "2016-01-01": {"pslreb": "PSLREB", "qcbdrvm": "QCBDR"},
    "2015-01-01": {"qctaq": "QCTAQ", "qcbdrvm": "", "nbpc": ""},
    "2013-01-01": {"onlst": "ONLSHP / ONLSAP  听证庭/上诉庭改名前"},
    "2008-01-01": {"qctaq": "", "qcbdrvm": ""},
    "2006-01-01": {"pescad": "PESCAD", "pesctd": "PESCTD"},
}

# 法语中立代码走 /fr/ 端点（CSC、CAF 等在英文端点里只偶然露面）。仅覆盖联邦与魁北克主要法院。
FRENCH = ["csc-scc", "fca", "fct", "cci-tcc", "cmac-cacm", "chrt", "tatc",
          "qcca", "qccs", "qccq", "qccm", "qctat", "qctaq"]


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
    """返回 (dbs, evidence, failures)。

    evidence: code -> jurisdiction(大写) -> [(db, citation, pass_label, 该库内此码样本数)]
    failures: [(pass_label, db, 错误)]  —— **必须往上报**。早期版本把失败写进缓存后
    静默跳过，最终报告只字不提，等于「抓失败」与「该库无此码」不可区分（PROBLEMS #34）。
    """
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

    # (缓存名, 语言, decisionDateBefore, 目标库)
    passes = [("recent", "en", None, list(dbs))]
    passes += [(b, "en", b, list(t)) for b, t in LEGACY.items()]
    passes.append(("fr", "fr", None, list(FRENCH)))

    evidence = defaultdict(lambda: defaultdict(list))
    failures = []
    for label, lang, before, targets in passes:
        cpath = os.path.join(cache_dir, "cases_%s.json" % label)
        cache = json.load(open(cpath, encoding="utf-8")) if os.path.exists(cpath) else {}
        todo = [d for d in targets if d not in cache and d in dbs]
        if todo and offline:
            print("  [%s] --offline，跳过 %d 个未缓存库" % (label, len(todo)), file=sys.stderr)
            todo = []
        for i, db in enumerate(todo):
            url = "%s%s/?offset=0&resultCount=5" % (BASE.replace("/en/", "/%s/" % lang), db)
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
                print("  [%s] %d/%d" % (label, i + 1, len(todo)), file=sys.stderr)
            time.sleep(1.0)
        json.dump(cache, open(cpath, "w", encoding="utf-8"), ensure_ascii=False)

        for db, cases in cache.items():
            if isinstance(cases, dict):
                failures.append((label, db, cases.get("_error")))
                continue
            if not cases:
                continue
            seen = defaultdict(list)
            for c in cases:
                m = RX_CODE.search(c.get("citation") or "")
                if m:
                    seen[m.group(1)].append(c["citation"])
            for code, cites in seen.items():
                evidence[code][dbs[db]["jurisdiction"].upper()].append(
                    (db, cites[0], label, len(cites)))
    return dbs, evidence, failures


# 库名同时点到两个以上法域 → 该机构的法域不是单值（闸 c）
_JUR_WORDS = {"on": r"ontario", "qc": r"quebec|québec", "ab": r"alberta",
              "bc": r"british columbia", "sk": r"saskatchewan", "mb": r"manitoba",
              "ns": r"nova scotia", "nb": r"new brunswick", "nl": r"newfoundland",
              "pe": r"prince edward", "nt": r"northwest", "nu": r"nunavut",
              "yk": r"yukon"}


def jurisdictions_in_name(name):
    return {k for k, pat in _JUR_WORDS.items() if re.search(pat, name, re.I)}


def build(dbs, evidence, added_date):
    rows, conflicts, skipped, singleton = [], [], [], []
    for code in sorted(evidence, key=str.upper):
        jurs = evidence[code]
        if code == "CanLII":
            skipped.append((code, "CanLII 伪代码：法域在尾括注里，本表无法承载（PROBLEMS #31）"))
            continue
        if any(db == "ukpc" for ev in jurs.values() for (db, *_) in ev):
            skipped.append((code, "证据来自 ukpc：CanLII jurisdiction 是馆藏归属非法院法域"
                                  "（PROBLEMS #32）"))
            continue
        if len(jurs) > 1:
            conflicts.append((code, {j: ev[0][0] for j, ev in jurs.items()}))
            continue
        (jur, ev), = jurs.items()

        # 闸 c：机构本身跨法域，本表形状承载不了（PROBLEMS #34）
        multi = [db for (db, *_) in ev if len(jurisdictions_in_name(dbs[db]["name"])) > 1]
        if multi:
            skipped.append((code, "库名点到多个法域（%s），法域非单值，本表承载不了"
                                  "（PROBLEMS #34）" % dbs[multi[0]]["name"]))
            continue

        # 证据择优：库名归一后等于代码者优先，其次按该库内印此码的样本数降序
        ev = sorted(ev, key=lambda e: (nk(e[0]) != code.upper(), -e[3]))
        db, cite, label, n_hits = ev[0]
        if len(ev) == 1 and n_hits == 1:
            singleton.append((code, jur, db, cite))
        d = dbs[db]
        lang = "fr" if label == "fr" else "en"
        loc = ('databaseId=%s; jurisdiction="%s"; name="%s"; 佐证引证="%s"（该库样本 %d 条印此码）; '
               'endpoint=%s%s/?offset=0&resultCount=5%s'
               % (db, d["jurisdiction"], d["name"], cite, n_hits,
                  BASE.replace("/en/", "/%s/" % lang), db,
                  "&decisionDateBefore=" + label if label not in ("recent", "fr") else ""))
        rows.append([code, nk(code), jur, SOURCE, loc, added_date])
    return rows, conflicts, skipped, singleton


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--key-file")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--allow-failures", action="store_true",
                    help="已知抓取失败时仍写表（默认拒绝）")
    ap.add_argument("--allow-drop", action="store_true",
                    help="现表中有本次产出不含的码时仍覆写（默认拒绝，防抹掉人工溯源写入的行）")
    ap.add_argument("--added-date", default=time.strftime("%Y-%m-%d"))
    a = ap.parse_args()

    key = "" if a.offline else get_key(a)
    dbs, evidence, failures = harvest(key, a.cache_dir, a.offline)
    rows, conflicts, skipped, singleton = build(dbs, evidence, a.added_date)

    # 抓取失败必须显式亮出来：失败与「该库无此码」在证据上不可区分，静默跳过等于制造假阴性
    if failures:
        print("!!! 抓取失败 %d 例，表可能缺码，不写表 !!!" % len(failures), file=sys.stderr)
        for label, db, err in failures:
            print("    [%s] %-12s %s" % (label, db, err), file=sys.stderr)
        if not a.allow_failures:
            sys.exit("传 --allow-failures 可在已知失败的情况下强行写表")
    assert not conflicts, "存在法域冲突，需人裁后再写表：%r" % conflicts
    assert len({r[0] for r in rows}) == len(rows), "court_code 重复"
    assert all(r[1] == nk(r[0]) for r in rows), "normalized_key 与 nk() 不一致"
    assert all(all(r) for r in rows), "有行字段为空（约束八）"

    # 防覆写闸：本脚本 open(OUT,"w") 是**整表覆写**，只吐 CanLII 能供出的码。
    # 表里还有人工逐条溯源写入的行（境外中立码 UKHL/HCA/ZACC… 之流，CanLII
    # 结构上供不出，见 PROBLEMS #35 甲），重跑一次就会被静默抹掉——决策表是
    # 本项目唯一不可再生的资产，静默丢人工判断是最贵的一种失败。
    # 与上面的抓取失败闸同款：亮出来、拒绝写、要显式放行。
    if os.path.exists(OUT):
        new_codes = {r[0] for r in rows}
        dropped = []
        with open(OUT, encoding="utf-8", newline="") as f:
            for old in csv.DictReader(f):
                if old["court_code"] and old["court_code"] not in new_codes:
                    dropped.append((old["court_code"], old["jurisdiction"],
                                    old["source"]))
        if dropped:
            print("!!! 本次重跑会丢掉现表中的 %d 行，不写表 !!!" % len(dropped),
                  file=sys.stderr)
            for code, juris, src in dropped:
                print("    %-12s %-3s  source=%s" % (code, juris, src),
                      file=sys.stderr)
            if not a.allow_drop:
                sys.exit("这些码本次抓取没有产出。若确属应当删除，传 --allow-drop；"
                         "若是人工溯源写入的行，先把它们并进本脚本的产出再跑。")

    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["court_code", "normalized_key", "jurisdiction",
                    "source", "source_locator", "added_date"])
        w.writerows(rows)
    print("写入 %d 行 -> %s" % (len(rows), OUT), file=sys.stderr)
    print("冲突 %d / 跳过 %d / 孤证 %d / 抓取失败 %d"
          % (len(conflicts), len(skipped), len(singleton), len(failures)),
          file=sys.stderr)
    for c, why in skipped:
        print("  跳过 %-10s %s" % (c, why), file=sys.stderr)
    for c, j, db, cite in singleton:
        print("  孤证 %-12s %-3s %-12s %s" % (c, j, db, cite), file=sys.stderr)


if __name__ == "__main__":
    main()
