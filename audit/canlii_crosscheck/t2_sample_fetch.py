"""T2 取数：法院 × 时期分层抽样（固定种子），老案逐案核实映射，再取 citedCases。

抽样框 = t1_map.csv 中有 canlii_id 的判决。每层目标 N=40。
basis=name_unverified 的判决先调 caseBrowse 元数据核实：decisionDate 年份与本语料一致；
SCC 老案另须 CanLII citation 串里含本语料的 SCR 引证（归一化后相等）。核不上的剔除并计数。
产出：data/canlii_cache/crosscheck/t2_sample.csv（不含 CanLII 内容，只有 id 与层）
"""
import csv, os, random, re, sys, collections
sys.path.insert(0, os.path.dirname(__file__))
from canlii_client import get, calls_made, StopError, ROOT

SEED, N = 20260927, 40
DB = {"SCC": "csc-scc", "ONCA": "onca", "BCCA": "bcca"}
ERAS = {
    "SCC": [(1875, 1949), (1950, 1999), (2000, 2026)],
    "ONCA": [(1998, 2006), (2007, 2015), (2016, 2026)],
    "BCCA": [(1999, 2007), (2008, 2016), (2017, 2026)],
}
C = os.path.join(ROOT, "data", "canlii_cache", "crosscheck")


def nk(s):
    return re.sub(r"[^A-Za-z0-9]", "", s or "").lower()


def main():
    rows = list(csv.DictReader(open(os.path.join(C, "t1_map.csv"), encoding="utf-8")))
    rng = random.Random(SEED)
    out, stats = [], collections.Counter()
    for court, eras in ERAS.items():
        for lo, hi in eras:
            frame = [r for r in rows if r["court"] == court and r["canlii_id"]
                     and r["year"] and lo <= int(r["year"]) <= hi]
            frame.sort(key=lambda r: r["our_id"])
            rng.shuffle(frame)
            stratum = "%s_%d-%d" % (court, lo, hi)
            stats[(stratum, "frame")] = len(frame)
            taken = 0
            for r in frame:
                if taken >= N:
                    break
                if r["basis"] == "name_unverified":
                    m = get("caseBrowse/en/%s/%s/" % (DB[court], r["canlii_id"]))
                    ok = str(m.get("decisionDate", ""))[:4] == r["year"]
                    if ok and court == "SCC" and not r["citation_en"][:1].isdigit():
                        ok = nk(r["citation_en"]) in [nk(p) for p in (m.get("citation") or "").split(",")]
                    if not ok:
                        stats[(stratum, "verify_failed")] += 1
                        continue
                    stats[(stratum, "verified")] += 1
                d = get("caseCitator/en/%s/%s/citedCases" % (DB[court], r["canlii_id"]))
                if d.get("_http") == 404:
                    stats[(stratum, "citator_404")] += 1
                    continue
                out.append(dict(r, stratum=stratum))
                taken += 1
            stats[(stratum, "taken")] = taken
            print(stratum, dict((k[1], v) for k, v in stats.items() if k[0] == stratum),
                  "calls so far", calls_made(), flush=True)
    with open(os.path.join(C, "t2_sample.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader(); w.writerows(out)
    with open(os.path.join(ROOT, "audit", "findings", "canlii_crosscheck", "t2_sampling.csv"),
              "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["stratum", "measure", "n"])
        for k in sorted(stats):
            w.writerow(list(k) + [stats[k]])


if __name__ == "__main__":
    try:
        main()
    except StopError as e:
        print("STOP:", e, "calls:", calls_made())
        sys.exit(2)
