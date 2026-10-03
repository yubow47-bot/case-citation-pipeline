"""Housen v. Nikolaisen（2002 SCC 33）逐条证据：两侧可比范围内的全部分歧。

我们独有：主组 XC-G024620 的计数引用方中，能映射到 CanLII id、但 CanLII citingCases 里没有的。
CanLII 独有：CanLII citingCases 中能映射回本语料、但不在主组计数引用方里的。
每条在语料原文里找 Housen 的全部出现（宽松：'Housen' / 'Hausen' / 'Nikolaisen' / 'Nikoleson' / '2002 SCC 33' / 'S.C.R. 235'），
记字符偏移与前后文；另查该判决在我们的哪个组里（主组 / 碎片组 / 自引排除等）。
裁定栏只填机械可判定的；其余写「待人工」。只用缓存，0 次新请求。
"""
import csv, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from canlii_client import ROOT
from t2_compare import nk
import pyarrow.parquet as pq

csv.field_size_limit(10 ** 9)
RUN = os.environ.get("CROSSCHECK_RUN", "run_20261002_tables2")  # 旧 run 已移到 D:\_cases_offload
R = os.path.join(ROOT, "data", RUN)
C = os.path.join(ROOT, "data", "canlii_cache", "crosscheck")
OUT = os.path.join(ROOT, "audit", "findings", "canlii_crosscheck", RUN, "housen_evidence.csv")
DB = {"SCC": "csc-scc", "ONCA": "onca", "BCCA": "bcca"}
MAIN = "XC-G024620"
PAT = re.compile(r"H[ao]u?sen|Nikol[a-z]+|2002\s*SCC\s*33|S\.?\s?C\.?\s?R\.?\s*235|S\.?C\.?J\.?\s*No\.?\s*31", re.I)

tm = {r["court"] + "_" + nk(r["citation_en"]): r for r in
      csv.DictReader(open(os.path.join(C, "t1_map.csv"), encoding="utf-8"))}
inv = {(DB[r["court"]], r["canlii_id"]): k for k, r in tm.items() if r["canlii_id"]}
d = json.load(open(os.path.join(C, "caseCitator_en_csc-scc_2002scc33_citingCases.json"), encoding="utf-8"))["citingCases"]
inc = set()
for c in d:
    cid = c["caseId"]; cid = cid.get("en") or next(iter(cid.values())) if isinstance(cid, dict) else cid
    if (c["databaseId"], cid) in inv:
        inc.add(inv[(c["databaseId"], cid)])

where = {}
for r in csv.DictReader(open(os.path.join(R, "decide_out", "cross_court", "effective_sources.csv"), encoding="utf-8")):
    where.setdefault(r["source_decision"], []).append((r["merged_group_id"], r["status"], r["exclusion_reason"]))
ours = {s for s, L in where.items() if any(g == MAIN and st == "counted" for g, st, _ in L)} - {"SCC_2002scc33"}
mappable = set(inv.values())
ours_only = sorted((ours & mappable) - inc)
canlii_only = sorted(inc - ours)

want = set(ours_only) | set(canlii_only)
texts = {}
for court in DB:
    for b in pq.ParquetFile(os.path.join(ROOT, "corpus", "%s.parquet" % court)).iter_batches(
            columns=["citation_en", "unofficial_text_en"]):
        for r in b.to_pylist():
            k = court + "_" + nk(r["citation_en"])
            if k in want:
                texts[k] = r["unofficial_text_en"] or ""

rows = []
for side, ids in (("ours_only", ours_only), ("canlii_only", canlii_only)):
    for s in ids:
        t = texts.get(s, "")
        hits = [(m.start(), t[max(0, m.start() - 100):m.end() + 120].replace("\n", " ")) for m in PAT.finditer(t)]
        groups = ";".join("%s:%s%s" % (g, st, (":" + ex) if ex else "") for g, st, ex in where.get(s, [])
                          if any(p in (t or "") for p in ("Housen", "Hausen", "Nikol")) and g != "")
        first = hits[0] if hits else (-1, "")
        has_name = bool(re.search(r"H[ao]u?sen|Nikol", t))
        verdict = ("真引用（原文有案名+引证）" if has_name and len(hits) >= 2 else
                   "原文仅见引证无案名，待人工" if hits else "原文中找不到，待人工")
        rows.append([side, s, tm.get(s, {}).get("canlii_id", ""), len(hits), first[0], first[1], verdict,
                     groups[:300] if side == "canlii_only" else ""])

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["side", "source_decision", "canlii_id", "n_hits", "first_offset", "context", "verdict",
                "our_groups_for_source(canlii_only only)"])
    w.writerows(rows)
print("ours_only", len(ours_only), "canlii_only", len(canlii_only))
for r in rows:
    print(r[0], r[1], r[3], r[6], "|", r[5][:170], "|", r[7][:200])
