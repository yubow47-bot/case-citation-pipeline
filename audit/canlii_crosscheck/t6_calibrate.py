"""T6 校准：用 t5_labels.csv 的核实结果，估计「我们的引用边是真实案例引用」的比例，并给 DD 权重候选。

边的正确 = 原文确有这条引用、且指向的是一个案例（不是期刊、条文号、目录、正文数字）。
  real_citation / real_wrong_name / real_comparer_mismatch -> 正确（组名错不影响 DD）
  procedural_history -> 单列：真实提及，但指本案下级/本案报道，不是援引的先例
  not_case / self_citation_leak -> 错误
  unverified -> 不计入
抽样按 层 × 类别（both_strong / both_loose_weak / ours_only）分格，按格内总数加权（Horvitz–Thompson）。
产出：audit/findings/canlii_crosscheck/<RUN>/t6_calibration.md、t6_dd_thresholds.csv
"""
import csv, math, os, sys, collections, random
sys.path.insert(0, os.path.dirname(__file__))
from canlii_client import ROOT

csv.field_size_limit(10 ** 9)
RUN = os.environ.get("CROSSCHECK_RUN", "run_20261002_tables2")
R = os.path.join(ROOT, "data", RUN)
OUT = os.path.join(ROOT, "audit", "findings", "canlii_crosscheck", RUN)
GOOD = {"real_citation", "real_wrong_name", "real_comparer_mismatch"}
BAD = {"not_case", "self_citation_leak"}
KIND = {"EDGE_ours_only": "ours_only", "EDGE_both_strong": "both_strong",
        "EDGE_both_weak": "both_loose_weak", "EDGE_both_loose": "both_loose_weak"}


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, c - h, c + h


def dd_bucket(d):
    return "1" if d <= 1 else "2-4" if d <= 4 else "5-9" if d <= 9 else "10+"


def main():
    labels = [r for r in csv.DictReader(open(os.path.join(OUT, "t5_labels.csv"), encoding="utf-8"))
              if r["kind"] in KIND and r["verdict"] not in ("", "unverified")]
    pairs = list(csv.DictReader(open(os.path.join(OUT, "t2_pairs.csv"), encoding="utf-8")))
    cell_n = collections.Counter()
    for p in pairs:
        c = p["class"]
        k = ("ours_only" if c.startswith("ours_only") else "both_strong" if c == "both_strong"
             else "both_loose_weak" if c in ("both_weak", "both_loose") else None)
        if k:
            cell_n[(p["stratum"], k)] += 1
    cell_s = collections.Counter((r["stratum"], KIND[r["kind"]]) for r in labels)

    # 被引组的 DD：ours_only 的 cited_id 就是组；both_* 用 t2 记的配上组（取最大 DD）
    groups_dd = {}
    for r in csv.DictReader(open(os.path.join(R, "select_out", "selected.csv"), encoding="utf-8")):
        if r["is_primary"] == "true":
            groups_dd[r["merged_group_id"]] = int(r["distinct_decisions_count"])
    pair_by = {(p["source"], p["cited_id"]): p for p in pairs}
    import json
    packet = {x["id"]: x for x in map(json.loads, open(os.path.join(ROOT, "data", "canlii_cache", "crosscheck",
                                                                  "t5_packet.jsonl"), encoding="utf-8"))}

    def target_dd(r):
        it = packet[r["item"]]
        if it["kind"] == "EDGE_ours_only":
            src_pairs = [p for p in pairs if p["source"] == r["source_decision"] and p["class"].startswith("ours_only")]
            # 回查：printed 属于哪个组——用 cited_id
            for p in src_pairs:
                pass
        return None

    # 直接从 t2_pairs 重建：抽样时 picks 的 cited_id 存在 packet 里吗？ours_only 的 cited_id 未存，按印刷引证回查组
    cite2g = collections.defaultdict(set)
    srcs = {r["source_decision"] for r in labels}
    edges = collections.defaultdict(set)
    for e in csv.DictReader(open(os.path.join(R, "edges", "citation_edges.csv"), encoding="utf-8")):
        if e["source_decision"] in srcs:
            edges[e["source_decision"]].add(e["resolved_cited_case"])
    want = set().union(*edges.values())
    for m in csv.DictReader(open(os.path.join(R, "select_out", "selected.csv"), encoding="utf-8")):
        if m["merged_group_id"] in want:
            cite2g[m["canonical_string"]].add(m["merged_group_id"])

    rows = []
    for r in labels:
        it = packet[r["item"]]
        gs = {g for c in it.get("all_citations", []) for g in cite2g.get(c, ()) if g in edges[r["source_decision"]]}
        dd = max((groups_dd.get(g, 0) for g in gs), default=None)
        w = cell_n[(r["stratum"], KIND[r["kind"]])] / cell_s[(r["stratum"], KIND[r["kind"]])]
        rows.append(dict(r, dd=dd, w=w, good=r["verdict"] in GOOD, bad=r["verdict"] in BAD,
                         proc=r["verdict"] == "procedural_history", cell=KIND[r["kind"]]))

    def est(sub):
        W = sum(x["w"] for x in sub)
        if not W:
            return None
        g = sum(x["w"] for x in sub if x["good"]) / W
        b = sum(x["w"] for x in sub if x["bad"]) / W
        pr = sum(x["w"] for x in sub if x["proc"]) / W
        n_eff = W * W / sum(x["w"] ** 2 for x in sub)
        return g, b, pr, len(sub), n_eff

    L = ["# T6 校准：我们的引用边有多少是真实案例引用", "",
         "run：`%s`。核实样本：%d 条我们的边（360 份 CanLII 对照判决内，按 层 × 类别 分层抽样，逐条读原文判定）。" % (RUN, len(rows)),
         "加权：每格按 t2 中该格边总数 / 抽样数加权；置信区间按有效样本量用 Wilson 近似。", "",
         "判定口径：**正确** = 原文确有此引用且指向案例（组名借错不影响 DD，计正确）；**错误** = 不是案例（期刊、条文号、目录、正文数字）或自引漏网；"
         "**程序历史** = 真实提及但指本案下级/本案报道，单列。", ""]

    L += ["## 按类别", "", "| 类别 | 样本 | 正确 | 错误 | 程序历史 |", "|---|---|---|---|---|"]
    for k in ("both_strong", "both_loose_weak", "ours_only"):
        sub = [x for x in rows if x["cell"] == k]
        g, b, pr, n, ne = est(sub)
        L.append("| %s | %d | %.1f%% | %.1f%% | %.1f%% |" % (k, n, 100 * g, 100 * b, 100 * pr))
    g, b, pr, n, ne = est(rows)
    lo, hi = wilson(round(g * ne), round(ne))[1:]
    L += ["", "**全部边（加权）：正确 %.1f%%（约 [%.1f–%.1f]），错误 %.1f%%，程序历史 %.1f%%。**" % (
        100 * g, 100 * lo, 100 * hi, 100 * b, 100 * pr), ""]

    L += ["## 按法院 × 时期", "", "| 层 | 样本 | 正确 | 错误 | 程序历史 |", "|---|---|---|---|---|"]
    for st in sorted({x["stratum"] for x in rows}):
        g, b, pr, n, ne = est([x for x in rows if x["stratum"] == st])
        L.append("| %s | %d | %.1f%% | %.1f%% | %.1f%% |" % (st, n, 100 * g, 100 * b, 100 * pr))

    L += ["", "## 按被引组 DD 分档", "", "| DD 档 | 样本 | 正确 | 错误 | 程序历史 |", "|---|---|---|---|---|"]
    bucket_p = {}
    for bk in ("1", "2-4", "5-9", "10+"):
        sub = [x for x in rows if x["dd"] is not None and dd_bucket(x["dd"]) == bk]
        e = est(sub)
        if e:
            g, b, pr, n, ne = e
            bucket_p[bk] = (g, b, pr, n)
            L.append("| %s | %d | %.1f%% | %.1f%% | %.1f%% |" % (bk, n, 100 * g, 100 * b, 100 * pr))
    with open(os.path.join(OUT, "t6_bucket_rates.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["dd_bucket", "p_real", "p_not_case", "p_procedural", "n_sample"])
        for bk, (g, b, pr, n) in bucket_p.items():
            w.writerow([bk, "%.4f" % g, "%.4f" % b, "%.4f" % pr, n])
    nodd = sum(x["dd"] is None for x in rows)
    L += ["", "未能回查到组 DD 的样本：%d 条（不计入本表）。" % nodd, ""]

    # 错误样本明细
    L += ["## 错误与程序历史明细", "", "| 条目 | 层 | 判定 | DD | 说明 |", "|---|---|---|---|---|"]
    for x in rows:
        if x["bad"] or x["proc"]:
            L.append("| %s | %s | %s | %s | %s |" % (x["item"], x["stratum"], x["verdict"], x["dd"], x["reason"]))

    # 门槛表：全库组按 DD 分布 × 分档正确率
    dist = collections.Counter(dd_bucket(d) for d in groups_dd.values())
    ge = lambda t: [d for d in groups_dd.values() if d >= t]
    T = []
    for t in (1, 2, 3, 5, 10):
        kept = ge(t)
        exp_good = sum(bucket_p.get(dd_bucket(d), (float("nan"),))[0] for d in kept)
        T.append((t, len(kept), exp_good / len(kept) if kept else float("nan")))
    with open(os.path.join(OUT, "t6_dd_thresholds.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["dd_threshold", "groups_kept", "est_share_real_by_bucket"])
        for t, n, s in T:
            w.writerow([t, n, "%.3f" % s])
    L += ["", "## DD 门槛取舍（全库 %d 个案件组）" % len(groups_dd), "",
          "按上面分档正确率（边级，近似当作组级）推算：", "",
          "| 门槛 DD≥ | 保留组数 | 估计其中真实案例比例 |", "|---|---|---|"]
    for t, n, s in T:
        L.append("| %d | %d | %.1f%% |" % (t, n, 100 * s))
    L += ["", "全库组按 DD 档分布：" + "，".join("%s：%d" % (k, dist[k]) for k in ("1", "2-4", "5-9", "10+")), "",
          "局限：样本只来自 360 份对照判决；DD 档样本量小的档（尤其 5+）区间宽；边级正确率近似为组级；"
          "未解决的 102 条 CanLII 侧记录（案名匹配不到）只影响召回估计，不影响本表。"]
    open(os.path.join(OUT, "t6_calibration.md"), "w", encoding="utf-8").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
