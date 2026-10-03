"""T5-Q 自动判定：CanLII 有、我们没配上的 Q 类记录（0 次新请求）。

对每条：在来源判决原文里找 CanLII 案名（全部实义词近邻出现），看案名后面紧跟的印刷引证，
或老判决的脚注号 [n] 指向的脚注引证；再看这条引证是否在我们该来源判决的边里。
判定：
  ours_has_edge        原文案名后有引证，且我们有指向含该引证的组的边 -> 实为双方都有，对照器没配上
  ours_missing_edge    原文案名后有引证，我们没有对应的边 -> 我们漏了（召回问题）
  name_only            原文只有案名，附近没有引证串 -> 抽取设计范围外
  header_or_history    只出现在判决头部/上诉来源（本案下级），不是正文引用
  not_in_text          原文找不到案名 -> CanLII 误链或文本差异
结果写回 t5_labels.csv 的 Q 行（只填空白行，不覆盖人工判定）。
"""
import csv, json, os, re, sys, collections
sys.path.insert(0, os.path.dirname(__file__))
from canlii_client import ROOT
from t2_compare import nk, nname, STOP

csv.field_size_limit(10 ** 9)
RUN = os.environ.get("CROSSCHECK_RUN", "run_20261002_tables2")
R = os.path.join(ROOT, "data", RUN)
C = os.path.join(ROOT, "data", "canlii_cache", "crosscheck")
OUT = os.path.join(ROOT, "audit", "findings", "canlii_crosscheck", RUN)
CITE = re.compile(r"[\[(]?\d{4}[\])]?,?\s*(?:\d+\s+)?[A-Z][A-Za-z.&' ]{0,25}?(?:\(\d\w{1,2}\))?\s*\d+|\d+\s+[A-Z][A-Za-z.&' ]{0,25}?(?:\(\d\w{1,2}\))?\s+\d+|\d{4}\s+[A-Z]{2,6}\s+\d+")


def main():
    import pyarrow.parquet as pq
    P = [json.loads(l) for l in open(os.path.join(C, "t5_packet.jsonl"), encoding="utf-8")]
    Q = [p for p in P if p["kind"] == "Q"]
    srcs = {p["source"] for p in Q}
    texts = {}
    for court in ("SCC", "ONCA", "BCCA"):
        for b in pq.ParquetFile(os.path.join(ROOT, "corpus", court + ".parquet")).iter_batches(
                columns=["citation_en", "unofficial_text_en"]):
            for r in b.to_pylist():
                k = court + "_" + nk(r["citation_en"])
                if k in srcs:
                    texts[k] = r["unofficial_text_en"] or ""
    # 每个来源判决：我们的边指向的组 -> 组内全部引证（归一化）
    edges = collections.defaultdict(set)
    for r in csv.DictReader(open(os.path.join(R, "edges", "citation_edges.csv"), encoding="utf-8")):
        if r["source_decision"] in srcs:
            edges[r["source_decision"]].add(r["resolved_cited_case"])
    want = set().union(*edges.values())
    gcites = collections.defaultdict(set)
    for r in csv.DictReader(open(os.path.join(R, "select_out", "selected.csv"), encoding="utf-8")):
        if r["merged_group_id"] in want:
            gcites[r["merged_group_id"]].add(nk(r["canonical_string"]))

    res = {}
    for p in Q:
        text = texts.get(p["source"], "")
        words = [w for w in nname(p["title"]).split() if w not in STOP and len(w) > 2]
        if not words:
            words = [w for w in nname(p["title"]).split() if len(w) > 1][:2]
        ours = set().union(*(gcites[g] for g in edges[p["source"]])) if edges[p["source"]] else set()
        hits = []
        ws = words[:4]
        need = max(1, (len(ws) + 1) // 2)
        for w in ws:
            for m in re.finditer(r"\b" + re.escape(w) + r"\b", text, re.I):
                win = text[max(0, m.start() - 120): m.end() + 120].lower()
                if sum(bool(re.search(r"\b" + re.escape(x) + r"\b", win)) for x in ws) >= need:
                    hits.append(m.start())
        hits = sorted(set(hits))
        if not hits:
            res[p["id"]] = ("not_in_text", "")
            continue
        # 头部 = 本判决自己的标题/元数据块（CanLII 常把本案的同名下级判决列为被引）
        hm = re.search(r"Present:|Heard:|BETWEEN|Coram|Before:|REASONS FOR JUDGMENT", text)
        body_start = hm.start() if hm else 1500
        verdict = None
        own = p["source"].split("_", 1)[1]
        oursx = {nk(re.sub(r"^\d{4}", "", o)) for o in ours}
        for h in [x for x in hits if x >= body_start]:  # 头部（本判决标题/元数据）不算引用
            after = text[h: h + 260]
            # 脚注号：案名后紧跟 [n] 或上标数字
            fn = re.match(r"[^\[\]\n]{0,120}?\[(\d{1,3})\]", after)
            cands = []
            if fn:
                n = fn.group(1)
                for fm in re.finditer(r"\[" + n + r"\]\s*([^\[]{4,160})", text[h + 1:]):
                    cands += [c.group(0) for c in CITE.finditer(fm.group(1))]
                    if cands:
                        break
            cands += [c.group(0) for c in CITE.finditer(after[:220])]
            cands = [c for c in cands if len(nk(c)) >= 6 and own not in nk(c) and "neutralcitation" not in nk(c)]
            if cands:
                # 精确：去掉括号年份差异后归一化相等（子串比较会把本判决头部引证误算成有边）
                got = [c for c in cands if nk(c) in ours or nk(re.sub(r"^[\[(]?\d{4}[\])]?,?\s*", "", c)) in oursx]
                if got:
                    verdict = ("ours_has_edge", got[0])
                    break
                verdict = verdict or ("ours_missing_edge", cands[0])
        if verdict is None:
            if all(h < body_start for h in hits) or re.search(r"On appeal from|APPEAL from|aff.g|rev.g",
                                                              text[max(0, hits[0] - 200): hits[0] + 50]):
                verdict = ("header_or_history", "")
            else:
                verdict = ("name_only", "")
        if verdict[0] in ("ours_missing_edge", "name_only") and all(h < body_start for h in hits):
            verdict = ("header_or_history", verdict[1])
        res[p["id"]] = verdict

    lp = os.path.join(OUT, "t5_labels.csv")
    rows = list(csv.reader(open(lp, encoding="utf-8")))
    for r in rows[1:]:
        if r[1] == "Q" and not r[6] and r[0] in res:
            r[6], r[8] = res[r[0]][0], ("auto; printed=" + res[r[0]][1]).strip()
    with open(lp, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    print(collections.Counter(v[0] for v in res.values()))


if __name__ == "__main__":
    main()
