"""试验（只读）：渠道 6——英法双语版对齐，自动得到汇编缩写与中立码的英↔法等价关系。

语料：corpus/SCC.parquet 中同时有 unofficial_text_en 与 unofficial_text_fr 的判决（同一判决的两种官方语言版本）。
做法：取分类层在英文版抽出的每条汇编引证（有卷号、页码、年份），在同一判决的法文版里找
  「年份 … 卷号 <缩写> 页码」——年份须在卷号前 ≤ 15 字符内出现；
  同一 (年, 卷, 页) 在法文版对出 ≥2 种不同缩写 → 歧义，不计。
中立引证同理：「年 <码> 号」。中立码对照 decisions/bilingual_neutral_codes.csv。
辑号 (2d)/(3d)/(4th)/(2e)/(3e)/(4e) 从两侧剥掉后再比。
不读 reporter_jurisdiction.csv 做推断，只在末尾对照：法文写法若是英文语料里也出现的缩写，看表给它的法域是否与英文写法一致。
"""
import csv, os, re, collections
import pyarrow.parquet as pq
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv.field_size_limit(10 ** 9)
R = os.path.join(ROOT, "data", "run_20260918_scc_onca_bcca")
SER = re.compile(r"\(\s*\d+\s*(?:d|nd|rd|th|e|re)\s*\)", re.I)


def nk(s):
    return re.sub(r"[^A-Za-z0-9]", "", s or "").lower()


def clean(s):
    s = SER.sub("", s)
    return re.sub(r"\s+", " ", s).strip(" ,;")


corpus = pq.read_table(os.path.join(ROOT, "corpus", "SCC.parquet"),
                       columns=["citation_en", "unofficial_text_en", "unofficial_text_fr"]).to_pylist()
table = {}
for r in csv.DictReader(open(os.path.join(ROOT, "decisions", "reporter_jurisdiction.csv"), encoding="utf-8")):
    table.setdefault(r["normalized_key"], set()).add(r["jurisdiction"])
bil = {}                                     # 表是无方向代码对（code_en 只是字典序较小者，见 build_bilingual_neutral_codes.py）
for r in csv.DictReader(open(os.path.join(ROOT, "decisions", "bilingual_neutral_codes.csv"), encoding="utf-8")):
    bil[frozenset((r["code_en"], r["code_fr"]))] = r["verification_status"]

stats = collections.Counter()
pairs = collections.defaultdict(collections.Counter)        # en nk -> fr form
pair_docs = collections.defaultdict(lambda: collections.defaultdict(set))
npairs = collections.defaultdict(collections.Counter)       # neutral en code -> fr code
en_label = {}
checked_rows = 0


def align(doc_idx, items):
    fr = corpus[doc_idx]["unofficial_text_fr"]
    if not fr:
        return
    stats["docs_with_fr"] += 1
    for kind, en_abbr, year, vol, page in items:
        if kind == "reporter":
            pat = re.compile(r"%s.{0,15}?(?<![\d])%s\s+([^\d\n]{1,40}?)\s+%s(?![\d])" % (year, vol, page))
        else:
            pat = re.compile(r"(?<![\d])%s\s+([A-Z]{2,8})\s+%s(?![\d])" % (year, page))
        found = {clean(m.group(1)) for m in pat.finditer(fr)}
        found = {f for f in found if f and len(f) <= 30 and not re.search(r"[;:]", f)}
        stats[kind + "_tried"] += 1
        if len(found) == 1:
            f = found.pop()
            if kind == "reporter":
                pairs[nk(en_abbr)][f] += 1
                pair_docs[nk(en_abbr)][f].add(doc_idx)
            else:
                npairs[en_abbr][f] += 1
            stats[kind + "_aligned"] += 1
        elif len(found) > 1:
            stats[kind + "_ambiguous"] += 1


cur, items = None, []
for r in csv.DictReader(open(os.path.join(R, "classify_out", "SCC", "classified.csv"), encoding="utf-8")):
    if r["rejected_reason"]:
        continue
    idx = int(r["corpus_row_index"])
    if idx != cur:
        if cur is not None:
            align(cur, items)
        cur, items = idx, []
        # 校验 corpus_row_index 与语料行对得上（抽前 200 份判决）
        if checked_rows < 200:
            checked_rows += 1
            c = corpus[idx]["citation_en"] or ""
            if nk(c) not in nk(r["source_decision_citation"]):
                stats["row_index_mismatch"] += 1
    y = (r["year_start"] or "").strip()
    page = (r["page"] or "").strip()
    if not (y.isdigit() and page.isdigit()):
        continue
    if r["citation_kind"] == "reporter" and (r["vol"] or "").strip().isdigit():
        en_label.setdefault(nk(r["abbreviation"]), r["abbreviation"])
        items.append(("reporter", r["abbreviation"], y, r["vol"].strip(), page))
    elif r["citation_kind"] == "neutral":
        items.append(("neutral", r["abbreviation"].strip().upper(), y, "", page))
if cur is not None:
    align(cur, items)

print(dict(stats), "| index check on", checked_rows, "docs")
print("\n==== 汇编缩写 英→法（对齐 ≥5 次；★=法文写法与英文写法去标点后不同）")
print("   n  docs  英文            法文主写法（次数）                          表(英) / 表(法)")
diff_rows = 0
for a, c in sorted(pairs.items(), key=lambda kv: -sum(kv[1].values())):
    n = sum(c.values())
    if n < 5:
        continue
    f, m = c.most_common(1)[0]
    star = "★" if nk(f) != a else " "
    if star == "★":
        diff_rows += 1
    te = ",".join(sorted(table.get(a, []))) or "—"
    tf = ",".join(sorted(table.get(nk(f), []))) or "—"
    flag = ""
    if star == "★" and te != "—" and tf != "—" and te != tf:
        flag = "  ← 英法两种写法在表里法域不同"
    print("%5d %4d %s %-15s %-45s %s / %s%s" % (
        n, len(set().union(*pair_docs[a].values())), star, en_label.get(a, a),
        ", ".join("%s %d" % x for x in c.most_common(3)), te, tf, flag))
print("英法写法不同的缩写:", diff_rows)

print("\n==== 中立码 英→法（对齐 ≥3 次），对照 bilingual_neutral_codes.csv")
for code, c in sorted(npairs.items(), key=lambda kv: -sum(kv[1].values())):
    n = sum(c.values())
    if n < 3:
        continue
    f, m = c.most_common(1)[0]
    status = "同码" if f == code else bil.get(frozenset((code, f)), "（表里没有这一对）")
    print("%5d  %-8s → %-8s %-40s %s" % (n, code, f, status, ", ".join("%s %d" % x for x in c.most_common(3)[1:])))
