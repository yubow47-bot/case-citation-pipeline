"""T2 对比 + T4 自动初裁（只用缓存，0 次新请求）。

对每个抽样判决 S：
  E = CanLII citedCases(S)          每条带 caseId + 引证串（老案含 SCR 等并列）
  G = 本管线 citation_edges 中 S 的被引组
配对：强 = 归一化引证串或中立 id 相等；弱 = 案名归一化相等且年份差 ≤2（单独计）。
分类：both / canlii_only / ours_only（再分 Canadian vs 结构性境外）。
canlii_only 的自动初裁（只做能机械判定的，其余进人工队列，不猜）：
  C1  原文里找得到该案的引证串，但抽取候选里没有     -> 抽取层真漏（记印刷形式）
  C45 原文里找得到且抽取候选里有，但不在 S 的计数边   -> 下游（归并/裁定/自引/暂定）丢失
  Q   原文里只找得到案名、找不到引证串；或都找不到    -> 人工队列
产出：audit/findings/canlii_crosscheck/t2_summary.md、t2_pairs.csv、t4_human_queue.csv
"""
import csv, json, math, os, re, sys, collections, random
sys.path.insert(0, os.path.dirname(__file__))
from canlii_client import get, ROOT
import pyarrow.parquet as pq

csv.field_size_limit(10 ** 9)
RUN = os.environ.get("CROSSCHECK_RUN", "run_20261002_tables2")  # 旧 run 已移到 D:\_cases_offload
R = os.path.join(ROOT, "data", RUN)
C = os.path.join(ROOT, "data", "canlii_cache", "crosscheck")
OUT = os.path.join(ROOT, "audit", "findings", "canlii_crosscheck", RUN)
DB = {"SCC": "csc-scc", "ONCA": "onca", "BCCA": "bcca"}
CA = {"CA", "ON", "BC", "QC", "AB", "NS", "MB", "SK", "NB", "NL", "YK", "NT", "PE", "NU"}
STOP = {"r", "the", "re", "in", "of", "and", "v", "her", "his", "majesty", "queen", "king",
        "canada", "attorney", "general", "a", "ltd", "inc", "co", "reference"}


def nk(s):
    return re.sub(r"[^A-Za-z0-9]", "", s or "").lower()


def nname(s):
    s = (s or "").lower().replace("&", " and ")
    s = re.sub(r"\bv\.?s?\b", " v ", s)
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", s).split())


def wilson(k, n):
    if n == 0:
        return "—"
    p, z = k / n, 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return "%.1f%% [%.1f–%.1f]" % (100 * p, 100 * (c - h), 100 * (c + h))


def canlii_keys(e):
    cid = e["caseId"]
    cid = (cid.get("en") or next(iter(cid.values()), "")) if isinstance(cid, dict) else cid
    keys = {cid}
    for part in (e.get("citation") or "").split(","):
        part = part.strip()
        if part and "CanLII" not in part:
            keys.add(nk(part))
    return cid, keys


def cite_regex(part):
    toks = re.findall(r"[A-Za-z]+|\d+", part)
    if not toks:
        return None
    pieces = []
    for t in toks:
        pieces.append(r"\.?\s?".join(map(re.escape, t)) if t.isalpha() else re.escape(t))
    return re.compile(r"(?<![0-9A-Za-z])" + r"[\s.,()\[\]]*".join(pieces) + r"(?![0-9])", re.I)


def main():
    sample = list(csv.DictReader(open(os.path.join(C, "t2_sample.csv"), encoding="utf-8")))
    for s in sample:
        s["src"] = s["court"] + "_" + nk(s["citation_en"])
    srcs = {s["src"]: s for s in sample}

    edges = collections.defaultdict(dict)          # src -> gid -> edge row
    side = collections.defaultdict(dict)           # src -> gid -> 'tentative'/'self_excluded:<reason>'
    for r in csv.DictReader(open(os.path.join(R, "edges", "citation_edges.csv"), encoding="utf-8")):
        if r["source_decision"] in srcs:
            edges[r["source_decision"]][r["resolved_cited_case"]] = r
    for fn, tag in (("tentative_edges.csv", "tentative"), ("self_excluded_edges.csv", "self_excluded")):
        for r in csv.DictReader(open(os.path.join(R, "edges", fn), encoding="utf-8")):
            if r["source_decision"] in srcs:
                side[r["source_decision"]][r["resolved_cited_case"]] = tag + ":" + r.get("exclusion_reason", "")
    eff = collections.defaultdict(dict)            # src -> gid -> status/reason (excluded rows)
    for r in csv.DictReader(open(os.path.join(R, "decide_out", "cross_court", "effective_sources.csv"),
                                 encoding="utf-8")):
        if r["source_decision"] in srcs and r["status"] != "counted":
            eff[r["source_decision"]][r["merged_group_id"]] = r["status"] + ":" + r["exclusion_reason"]
    need = {g for d in (edges, side, eff) for m in d.values() for g in m}

    groups = collections.defaultdict(lambda: {"keys": set(), "names": set(), "years": set(), "jur": set(), "kinds": set()})
    for r in csv.DictReader(open(os.path.join(R, "decide_out", "cross_court", "decided.csv"), encoding="utf-8")):
        g = r["merged_group_id"]
        if g not in need:
            continue
        G = groups[g]
        p = r["merge_key"].split("|")
        if r["citation_kind"] == "neutral" and len(p) >= 5:
            G["keys"].add(p[0] + p[2] + p[4])
        G["keys"].add(nk(r["canonical_string"]))
        if r["case_name_modal"]:
            G["names"].add(nname(r["case_name_modal"]))
        if r["year_printed"].isdigit():
            G["years"].add(int(r["year_printed"]))
        G["jur"].add(r["jurisdiction"])
        G["kinds"].add(r["citation_kind"])

    cands = collections.defaultdict(set)           # src -> nk(raw_string) extracted
    for r in csv.DictReader(open(os.path.join(R, "extract_out", "candidates.csv"), encoding="utf-8")):
        if r["source_decision_citation"] in srcs:
            cands[r["source_decision_citation"]].add(nk(r["raw_string"]))

    texts, a2aj = {}, {}
    for court in DB:
        want = {s["citation_en"] for s in sample if s["court"] == court}
        pf = pq.ParquetFile(os.path.join(ROOT, "corpus", "%s.parquet" % court))
        for b in pf.iter_batches(columns=["citation_en", "unofficial_text_en", "cases_cited_en"]):
            for r in b.to_pylist():
                if r["citation_en"] in want:
                    k = court + "_" + nk(r["citation_en"])
                    texts[k] = r["unofficial_text_en"] or ""
                    a2aj[k] = set(nk(x) for x in (r["cases_cited_en"] or []))

    pairs, queue = [], []
    agg = collections.defaultdict(collections.Counter)
    for s in sample:
        src, st = s["src"], s["stratum"]
        E = get("caseCitator/en/%s/%s/citedCases" % (DB[s["court"]], s["canlii_id"])).get("citedCases", [])
        G = edges.get(src, {})
        agg[st]["sources"] += 1
        agg[st]["zero_edge_sources"] += (not G)
        used = set()
        for e in E:
            cid, keys = canlii_keys(e)
            strong = [g for g in G if groups[g]["keys"] & keys]
            weak = []
            if not strong:
                y = int(cid[:4]) if cid[:4].isdigit() else None
                nm = nname(e.get("title"))
                weak = [g for g in G if nm in groups[g]["names"]
                        and (y is None or any(abs(y - gy) <= 2 for gy in groups[g]["years"]))]
            loose = []
            if not strong and not weak:
                y = int(cid[:4]) if cid[:4].isdigit() else None
                ws = [w for w in nname(e.get("title")).split() if w not in STOP and len(w) > 2]
                if ws and y:
                    rx = re.compile(r"\b" + re.escape(ws[0]) + r"\b")
                    loose = [g for g in G if g not in used and any(rx.search(n) for n in groups[g]["names"])
                             and any(0 <= gy - y <= 2 for gy in groups[g]["years"])]
            hit = strong or weak or loose
            used.update(hit)
            agg[st]["canlii_total"] += 1
            agg[st]["a2aj_has"] += bool(keys & a2aj.get(src, set()))
            if hit:
                cls = "both_strong" if strong else ("both_weak" if weak else "both_loose")
                agg[st][cls] += 1
                agg[st]["fragmented"] += len(hit) > 1
                pairs.append([st, src, cid, cls, len(hit), (e.get("title") or "") + " <-> " + " / ".join(sorted(n for g in hit for n in groups[g]["names"]))[:200],
                              ";".join(sorted(hit))])
                continue
            # canlii_only：自动初裁
            text = texts.get(src, "")
            found = None
            for part in (e.get("citation") or "").split(","):
                part = part.strip()
                rx = cite_regex(part)
                if rx and "CanLII" not in part and rx.search(text):
                    found = part
                    break
            if found:
                ext = any(nk(found) in c or c in nk(found) for c in cands.get(src, ()) if len(c) >= 6)
                anyside = [g for g, v in list(side.get(src, {}).items()) + list(eff.get(src, {}).items())
                           if groups[g]["keys"] & keys]
                if not ext:
                    code = "C1_not_extracted"
                elif anyside:
                    code = "C5_excluded:" + (side[src].get(anyside[0]) or eff[src].get(anyside[0]))
                else:
                    code = "C4_extracted_but_elsewhere"
                form = re.sub(r"\d+", "#", found)
            else:
                words = [w for w in nname(e.get("title")).split() if w not in STOP and len(w) > 2]
                name_hit = bool(words) and re.search(r"\b" + re.escape(words[0]) + r"\b", text, re.I)
                code = "Q_first_word_only" if name_hit else "Q_not_found"
                form = ""
            agg[st][code.split(":")[0]] += 1
            agg[st]["canlii_only"] += 1
            pairs.append([st, src, cid, code, 0, form])
            if code.startswith("Q") or code.startswith("C1"):
                queue.append([st, src, cid, e.get("title"), e.get("citation"), code, form])
        for g, r in G.items():
            agg[st]["ours_total"] += 1
            agg[st]["ours_" + r["edge_support"]] += 1
            if g in used:
                agg[st]["ours_matched_" + r["edge_support"]] += 1
                continue
            # 来源地只认生产数据的 foreign_status（案件来源 origin），不用汇编法域 jurisdiction 代替：
            # 外国汇编 ≠ 外国案件（如枢密院对加拿大上诉）。汇编法域只作第二维度记录。
            origin = {"FOREIGN": "foreign", "DOMESTIC_CA": "ca"}.get(r["foreign_status"], "undetermined")
            jur = groups[g]["jur"] - {"", "UNSUPPORTED"}
            pub = "pubnone" if not jur else ("pubca" if jur & CA else "pubforeign")
            cls = "ours_only_origin_" + origin
            agg[st][cls] += 1
            agg[st][cls + "_" + pub] += 1
            cls = cls + "|" + pub
            pairs.append([st, src, g, cls + ":" + r["edge_support"], 0,
                          "|".join(sorted(groups[g]["kinds"]))])

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "t2_pairs.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["stratum", "source", "cited_id", "class", "n_groups", "printed_form", "matched_groups"])
        w.writerows(pairs)
    rng = random.Random(20260927)
    rng.shuffle(queue)
    with open(os.path.join(C, "t4_human_queue_full.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["stratum", "source", "canlii_id", "title", "citation", "code", "form"])
        w.writerows(queue)

    order = sorted(agg, key=lambda k: (["SCC", "ONCA", "BCCA"].index(k.split("_")[0]), k))
    L = ["# T2 边级对比（自动部分）", "",
         "口径：CanLII 覆盖率 = 我们配上的 CanLII 被引案 / CanLII 被引案；"
         "CanLII 对我们的覆盖 = 被 CanLII 配上的我们的边 / 我们的边中「来源地未判定为境外」者"
         "（来源地取生产数据 foreign_status；UNDETERMINED 计入分母，因为它可能是加拿大案）。Wilson 95% CI。", "",
         "未配上的我们的边按来源地：境外（已判定）/ 加拿大（已判定）/ 未判定——未判定者再按汇编法域拆：印在加拿大汇编 / 外国汇编 / 无法域。", "",
         "| 层 | 判决 | 零出边 | CanLII 被引 | 我们配上（强+弱+宽） | 我们对 CanLII 的覆盖 | 我们的边 | 未配上·来源境外 | 未配上·来源加拿大 | 未配上·来源未判定（加汇编/外汇编/无） | CanLII 对我们的覆盖 | A2AJ 也有 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    tot = collections.Counter()
    for st in order:
        a = agg[st]; tot.update(a)
        both = a["both_strong"] + a["both_weak"] + a["both_loose"]
        denom = both + a["ours_only_origin_ca"] + a["ours_only_origin_undetermined"]
        L.append("| %s | %d | %d | %d | %d+%d+%d | %s | %d | %d | %d | %d（%d/%d/%d） | %s | %d |" % (
            st, a["sources"], a["zero_edge_sources"], a["canlii_total"], a["both_strong"], a["both_weak"], a["both_loose"],
            wilson(both, a["canlii_total"]), a["ours_total"], a["ours_only_origin_foreign"], a["ours_only_origin_ca"],
            a["ours_only_origin_undetermined"], a["ours_only_origin_undetermined_pubca"],
            a["ours_only_origin_undetermined_pubforeign"], a["ours_only_origin_undetermined_pubnone"],
            wilson(both, denom), a["a2aj_has"]))
    L += ["", "## CanLII 有、我们没有：自动初裁", "", "| 层 | canlii_only | C1 原文有·未抽到 | C4 抽到·归到别处 | C5 抽到·被规则排除 | Q 仅首个实义词 | Q 原文找不到 |", "|---|---|---|---|---|---|---|"]
    for st in order:
        a = agg[st]
        L.append("| %s | %d | %d | %d | %d | %d | %d |" % (st, a["canlii_only"], a["C1_not_extracted"],
                 a["C4_extracted_but_elsewhere"], a["C5_excluded"], a["Q_first_word_only"], a["Q_not_found"]))
    L += ["", "## 我们的边按 edge_support：被 CanLII 配上的比例", "", "| 层 | supported | heuristic_only |", "|---|---|---|"]
    for st in order:
        a = agg[st]
        L.append("| %s | %s (n=%d) | %s (n=%d) |" % (st, wilson(a["ours_matched_supported"], a["ours_supported"]),
                 a["ours_supported"], wilson(a["ours_matched_heuristic_only"], a["ours_heuristic_only"]), a["ours_heuristic_only"]))
    L += ["", "原始计数：", "", "```", json.dumps({k: dict(v) for k, v in agg.items()}, ensure_ascii=False, indent=0), "```"]
    open(os.path.join(OUT, "t2_summary.md"), "w", encoding="utf-8").write("\n".join(L))
    print("\n".join(L[:40]))


if __name__ == "__main__":
    main()
