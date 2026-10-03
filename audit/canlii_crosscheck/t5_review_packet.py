"""T5 核实包：为校准抽样，并把每条待核记录的原文上下文拉出来（只读缓存与 run，0 次新请求）。

两类记录：
  Q     CanLII 有、我们没配上、自动初裁定不了的全部 318 条 -> 看原文判断：我们漏了 / 只有案名无引证 / CanLII 误链
  EDGE  我们的边（分层抽样）-> 看原文判断：引用是否真实存在、被引身份（组名/引证）是否认对
抽样：每层 ours_only 12 + both_weak/loose 8 + both_strong 4，固定种子。
产出：data/canlii_cache/crosscheck/t5_packet.jsonl（含原文片段，gitignore）
      audit/findings/canlii_crosscheck/<RUN>/t5_labels.csv（标签模板；键 = 来源判决 + 印刷引证/CanLII id，不用 group_id 作键）
"""
import csv, json, os, re, sys, random, collections
sys.path.insert(0, os.path.dirname(__file__))
from canlii_client import ROOT
from t2_compare import nk, nname, cite_regex, STOP, DB
import pyarrow.parquet as pq

csv.field_size_limit(10 ** 9)
RUN = os.environ.get("CROSSCHECK_RUN", "run_20261002_tables2")
R = os.path.join(ROOT, "data", RUN)
C = os.path.join(ROOT, "data", "canlii_cache", "crosscheck")
OUT = os.path.join(ROOT, "audit", "findings", "canlii_crosscheck", RUN)
PER = {"ours_only": 12, "both_loose_weak": 8, "both_strong": 4}
W = 260


def snippets(text, rx_list, k=2):
    out, seen = [], []
    for rx in rx_list:
        for m in rx.finditer(text):
            if any(abs(m.start() - s) < W for s in seen):
                continue
            seen.append(m.start())
            a, b = max(0, m.start() - W), min(len(text), m.end() + W)
            out.append(" ".join(text[a:b].split()))
            if len(out) >= k:
                return out
    return out


def main():
    pairs = list(csv.DictReader(open(os.path.join(OUT, "t2_pairs.csv"), encoding="utf-8")))
    queue = list(csv.DictReader(open(os.path.join(C, "t4_human_queue_full.csv"), encoding="utf-8")))
    rng = random.Random(20261003)
    by = collections.defaultdict(list)
    for p in pairs:
        c = p["class"]
        kind = ("ours_only" if c.startswith("ours_only") else "both_strong" if c == "both_strong"
                else "both_loose_weak" if c in ("both_weak", "both_loose") else None)
        if kind:
            by[(p["stratum"], kind)].append(p)
    picks = []
    for (st, kind), lst in sorted(by.items()):
        lst = sorted(lst, key=lambda p: (p["source"], p["cited_id"]))
        rng.shuffle(lst)
        picks += [dict(p, kind=kind, n_in_cell=len(lst)) for p in lst[:PER[kind]]]
    # both_* 行的 cited_id 是 CanLII id；需要我们这边配上的组——从配对说明里拿组名，组本身按名回查
    need_src = {p["source"] for p in picks} | {q["source"] for q in queue}
    gids = {p["cited_id"] for p in picks if p["kind"] == "ours_only"}

    edges = collections.defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(R, "edges", "citation_edges.csv"), encoding="utf-8")):
        if r["source_decision"] in need_src:
            edges[r["source_decision"]][r["resolved_cited_case"]] = r
    grp = collections.defaultdict(lambda: {"cites": set(), "names": set()})
    want = {g for s in need_src for g in edges[s]} | {g for p in picks for g in (p.get("matched_groups") or "").split(";") if g}
    for r in csv.DictReader(open(os.path.join(R, "select_out", "selected.csv"), encoding="utf-8")):
        g = r["merged_group_id"]
        if g in want:
            grp[g]["cites"].add(r["canonical_string"])
            if r["case_name_modal"]:
                grp[g]["names"].add(r["case_name_modal"])

    texts = {}
    for court in DB:
        pf = pq.ParquetFile(os.path.join(ROOT, "corpus", court + ".parquet"))
        for b in pf.iter_batches(columns=["citation_en", "unofficial_text_en"]):
            for r in b.to_pylist():
                k = court + "_" + nk(r["citation_en"])
                if k in need_src:
                    texts[k] = r["unofficial_text_en"] or ""

    canlii = {}
    for q in queue:
        canlii[(q["source"], q["canlii_id"])] = q

    packet, labels = [], []
    n = 0
    for q in queue:
        n += 1
        words = [w for w in nname(q["title"]).split() if w not in STOP and len(w) > 2]
        rxs = [re.compile(r"\b" + re.escape(w) + r"\b", re.I) for w in words[:3]]
        item = {"id": "Q%03d" % n, "kind": "Q", "stratum": q["stratum"], "source": q["source"],
                "canlii_id": q["canlii_id"], "title": q["title"], "canlii_citation": q["citation"],
                "auto": q["code"], "snippets": snippets(texts.get(q["source"], ""), rxs, 3)}
        packet.append(item)
        labels.append([item["id"], "Q", q["stratum"], q["source"], q["canlii_id"], q["title"], "", "", ""])
    for p in picks:
        n += 1
        src = p["source"]
        if p["kind"] == "ours_only":
            g = p["cited_id"]
            info = grp[g]
            cites = sorted(info["cites"])
            rxs = [x for x in (cite_regex(c) for c in cites) if x]
            item = {"id": "E%03d" % n, "kind": "EDGE_ours_only", "stratum": p["stratum"], "source": src,
                    "printed": cites[0] if cites else "", "all_citations": cites[:6], "group_names": sorted(info["names"])[:3],
                    "class": p["class"], "n_in_cell": p["n_in_cell"],
                    "snippets": snippets(texts.get(src, ""), rxs, 2)}
        else:
            # printed_form 列存的是 "CanLII 标题 <-> 我们的组名"
            left, _, right = p["printed_form"].partition(" <-> ")
            names = [x.strip() for x in right.split(" / ") if x.strip()]
            cand = [g for g in p["matched_groups"].split(";") if g]
            cites = sorted({c for g in cand for c in grp[g]["cites"]})
            rxs = [x for x in (cite_regex(c) for c in cites) if x]
            item = {"id": "E%03d" % n, "kind": "EDGE_" + p["class"], "stratum": p["stratum"], "source": src,
                    "canlii_id": p["cited_id"], "canlii_title": left, "printed": cites[0] if cites else "",
                    "all_citations": cites[:6], "group_names": names[:3], "n_in_cell": p["n_in_cell"],
                    "snippets": snippets(texts.get(src, ""), rxs, 2)}
        packet.append(item)
        labels.append([item["id"], item["kind"], item["stratum"], src, item.get("printed") or item.get("canlii_id"),
                       " / ".join(item["group_names"]), "", "", ""])

    with open(os.path.join(C, "t5_packet.jsonl"), "w", encoding="utf-8") as f:
        for it in packet:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    os.makedirs(OUT, exist_ok=True)
    lp = os.path.join(OUT, "t5_labels.csv")
    if os.path.exists(lp):
        print("labels exist, not overwritten:", lp)
    else:
        with open(lp, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["item", "kind", "stratum", "source_decision", "printed_or_canlii_id", "name", "verdict", "reason", "note"])
            w.writerows(labels)
    print(collections.Counter(it["kind"] for it in packet), "no_snippet:", sum(not it["snippets"] for it in packet))


if __name__ == "__main__":
    main()
