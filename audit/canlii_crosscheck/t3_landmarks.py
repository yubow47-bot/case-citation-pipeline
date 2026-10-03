"""T3：被引组的 dd（本管线）vs CanLII citingCases（限三院、限本语料内的引用方判决）。

被引组取「身份锚是语料内判决」者（decided.csv self_citation_of 非空），按被引判决年代分三层，
每层 dd>=5 随机 20 个（固定种子）+ Housen。CanLII 侧只保留 databaseId∈三院 且 caseId 在
t1_map 中能对回本语料判决的引用方——避免把「语料没收」算成差异。
name_unverified 的被引判决先逐案核实（同 T2 规则）。
"""
import csv, os, random, re, sys, collections, math
sys.path.insert(0, os.path.dirname(__file__))
from canlii_client import get, calls_made, StopError, ROOT
from t2_compare import wilson, nk

csv.field_size_limit(10 ** 9)
RUN = os.environ.get("CROSSCHECK_RUN", "run_20261002_tables2")  # 旧 run 已移到 D:\_cases_offload
R = os.path.join(ROOT, "data", RUN)
C = os.path.join(ROOT, "data", "canlii_cache", "crosscheck")
OUT = os.path.join(ROOT, "audit", "findings", "canlii_crosscheck", RUN)
DB = {"SCC": "csc-scc", "ONCA": "onca", "BCCA": "bcca"}
ERAS = [(1800, 1949), (1950, 1999), (2000, 2026)]


def main():
    tmap = {}
    for r in csv.DictReader(open(os.path.join(C, "t1_map.csv"), encoding="utf-8")):
        tmap[r["court"] + "_" + nk(r["citation_en"])] = r
    canlii2ours = {(DB[r["court"]], r["canlii_id"]): k for k, r in tmap.items() if r["canlii_id"]}
    mappable = set(canlii2ours.values())

    grp = {}
    for r in csv.DictReader(open(os.path.join(R, "decide_out", "cross_court", "decided.csv"), encoding="utf-8")):
        so = r["self_citation_of"]
        if so and so in tmap and tmap[so]["canlii_id"] and r["is_primary"] in ("1", "True", "true", ""):
            g = r["merged_group_id"]
            if g not in grp:
                grp[g] = {"self": so, "dd": int(r["distinct_decisions_count"] or 0),
                          "name": r["case_name_modal"], "year": int(tmap[so]["year"] or 0)}
    rng = random.Random(20260927)
    picks = []
    for lo, hi in ERAS:
        frame = sorted(g for g, v in grp.items() if v["dd"] >= 5 and lo <= v["year"] <= hi)
        rng.shuffle(frame)
        picks += [(g, "%d-%d" % (lo, hi)) for g in frame[:26]]
    # Housen 主组（XC-G024620）的身份锚行 is_primary 不满足上面的筛选，这里显式加入（citingCases 已在 T0 缓存）
    grp.setdefault("XC-G024620", {"self": "SCC_2002scc33", "dd": 1534, "name": "Housen v. Nikolaisen", "year": 2002})
    picks += [("XC-G024620", "Housen")]

    ours = collections.defaultdict(set)
    want = {g for g, _ in picks}
    for r in csv.DictReader(open(os.path.join(R, "decide_out", "cross_court", "effective_sources.csv"), encoding="utf-8")):
        if r["merged_group_id"] in want and r["status"] == "counted":
            ours[r["merged_group_id"]].add(r["source_decision"])

    rows, per_era, done = [], collections.defaultdict(collections.Counter), collections.Counter()
    for g, era in picks:
        if era != "Housen" and done[era] >= 20:
            continue
        v = grp[g]; m = tmap[v["self"]]; db = DB[m["court"]]
        if m["basis"] == "name_unverified":
            meta = get("caseBrowse/en/%s/%s/" % (db, m["canlii_id"]))
            ok = str(meta.get("decisionDate", ""))[:4] == m["year"]
            if ok and m["court"] == "SCC" and not m["citation_en"][:1].isdigit():
                ok = nk(m["citation_en"]) in [nk(p) for p in (meta.get("citation") or "").split(",")]
            if not ok:
                per_era[era]["verify_failed"] += 1
                continue
        d = get("caseCitator/en/%s/%s/citingCases" % (db, m["canlii_id"]))
        if "citingCases" not in d:
            per_era[era]["no_data:" + str(d.get("error") or d.get("_http"))] += 1
            continue
        all3, incorp = 0, set()
        for c in d["citingCases"]:
            cid = c["caseId"]; cid = (cid.get("en") or next(iter(cid.values()), "")) if isinstance(cid, dict) else cid
            if c["databaseId"] in DB.values():
                all3 += 1
                o = canlii2ours.get((c["databaseId"], cid))
                if o:
                    incorp.add(o)
        # 两侧同一比较范围：我们这侧也只保留能映射到 CanLII id 的引用方；映射不上的单列为不可比
        O_all = ours[g] - {v["self"]}
        O = O_all & mappable
        a_unmap = len(O_all - O)
        both = O & incorp
        done[era] += 1
        a = per_era[era]
        a["groups"] += 1; a["ours"] += len(O); a["ours_unmappable"] += a_unmap; a["canlii"] += len(incorp); a["both"] += len(both)
        rows.append([era, g, v["self"], v["name"], v["dd"], len(O_all), a_unmap, len(O), all3, len(incorp), len(both),
                     len(O - incorp), len(incorp - O)])
        print(era, v["name"][:40], "dd", v["dd"], "ours", len(O), "canlii_in_corpus", len(incorp),
              "both", len(both), "calls", calls_made(), flush=True)

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "t3_landmarks.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["era", "group", "cited_decision", "name", "dd", "ours_citing_all", "ours_citing_unmappable", "ours_citing_comparable", "canlii_citing_3courts",
                    "canlii_citing_in_corpus", "both", "ours_only", "canlii_only"])
        w.writerows(rows)
    L = ["# T3 被引组：dd vs CanLII citingCases", "",
         "只比较两边都可能看到的引用方（三院、本语料内）。比例按「引用方判决」计，Wilson 95% CI。", "",
         "| 被引判决年代 | 组数 | 我们的引用方（可比） | CanLII 的引用方 | 共有 | CanLII 的引用方中我们也有 | 我们的引用方中 CanLII 也有 |",
         "|---|---|---|---|---|---|---|"]
    for era in ["1800-1949", "1950-1999", "2000-2026", "Housen"]:
        a = per_era[era]
        L.append("| %s | %d | %d | %d | %d | %s | %s |" % (era, a["groups"], a["ours"], a["canlii"], a["both"],
                 wilson(a["both"], a["canlii"]), wilson(a["both"], a["ours"])))
    L += ["", "我们的引用方中映射不到 CanLII id、不可比较而剔除的：" + str({k: v["ours_unmappable"] for k, v in per_era.items()})]
    L += ["", "其他计数：" + str({k: dict(v) for k, v in per_era.items()})]
    open(os.path.join(OUT, "t3_summary.md"), "w", encoding="utf-8").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    try:
        main()
    except StopError as e:
        print("STOP:", e, "calls:", calls_made()); sys.exit(2)
