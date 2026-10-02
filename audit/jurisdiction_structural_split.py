"""试验（只读）：渠道 5——卷号/年份/印刷结构指纹，把同名缩写拆开。

不直接给法域：把同一缩写的提及按「印刷结构签名 × 年代簇」分格，再用渠道 1/2/4 的证据看各格指向是否不同。
  · 结构签名：是否带 `No.`（Quicklaw 判决号式 [2006] S.J. No. 802）、年份括号（方括号/圆括号/无）、有无辑号 (2d)/(3d)…、有无卷号；
  · 年代簇：该缩写出现过的年份排序后，相邻年份断档 > GAP_YEARS 处切开（W.L.R. 式：Western Law Reporter ≤1916 / Weekly Law Reports ≥1953）。
证据：串里的中立引证（渠道 1）、有出处的法院括注（渠道 2）、与种子汇编并印（渠道 4，只用第 0 跳种子，记国家）。
检出：同一缩写有 ≥2 格各自证据 ≥ MIN_EV 且主导国家不同，或同国主导省不同且各自 ≥90% 单一 → 同形候选。
已知同形（#52/#100）用来检验检出力：K.B.、Q.B.、S.C.、P.、C.L.R.、A.L.R.、W.L.R.、S.J.。
"""
import csv, os, re, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv.field_size_limit(10 ** 9)
R = os.path.join(ROOT, "data", "run_20260918_scc_onca_bcca")
GAP_OK = re.compile(r"^[\s,]*$")
GAP_YEARS, MIN_EV = 15, 8
PROV = {"ON", "BC", "AB", "SK", "MB", "QC", "NS", "NB", "NL", "PE", "YK", "NT", "NU"}
KNOWN = {"kb", "qb", "sc", "p", "clr", "alr", "wlr", "sj"}


def nk(s):
    return re.sub(r"[^A-Za-z0-9]", "", s or "").lower()


def country(j):
    return "CA" if j in PROV else j


court_j = {nk(r["court_code"]): r["jurisdiction"] for r in
           csv.DictReader(open(os.path.join(ROOT, "decisions", "neutral_court_codes.csv"), encoding="utf-8"))}
COURT_J = {"House of Lords": "GB", "High Court of Australia": "AU", "Judicial Committee of the Privy Council": None}
desig = {}
for r in csv.DictReader(open(os.path.join(ROOT, "decisions", "court_designations.csv"), encoding="utf-8")):
    if r["status"] == "recognized":
        desig[r["normalized_key"]] = r["canonical_court"]
for r in csv.DictReader(open(os.path.join(ROOT, "audit", "findings", "court_designations_doj_proposal.csv"),
                             encoding="utf-8")):
    if r["status"] == "recognized":
        desig[r["normalized_key"]] = r["canonical_court"]
        COURT_J[r["canonical_court"]] = r["court_jurisdiction"]
table = {}
for r in csv.DictReader(open(os.path.join(ROOT, "decisions", "reporter_jurisdiction.csv"), encoding="utf-8")):
    table.setdefault(r["normalized_key"], set()).add(r["jurisdiction"])


def signature(r):
    raw = r["raw_string"]
    s = []
    s.append("No" if re.search(r"\bNo\.?\s*\d", raw) else "")
    s.append("[y]" if raw.lstrip().startswith("[") else ("(y)" if raw.lstrip().startswith("(") else "-"))
    s.append("ser" if (r["series"] or r["series_paren"]) else "")
    s.append("vol" if (r["vol"] or "").strip() else "novol")
    return "|".join(x for x in s if x)


mentions = []          # (abbr, sig, year, direct_js frozenset, seed_partners tuple)
label = {}


def use(chain):
    js = set()
    reps = []
    for r in chain:
        if r["citation_kind"] == "neutral":
            j = court_j.get(nk(r["abbreviation"]))
            if j:
                js.add(j)
            continue
        raw = (r["court_designation_raw"] or "").strip()
        if raw:
            c = desig.get(nk(raw))
            if c and COURT_J.get(c):
                js.add(COURT_J[c])
        if r["citation_kind"] == "reporter" and nk(r["abbreviation"]):
            reps.append(r)
    seen = set()
    for r in reps:
        a = nk(r["abbreviation"])
        if a in seen:
            continue
        seen.add(a); label.setdefault(a, r["abbreviation"])
        y = int(r["year_start"]) if (r["year_start"] or "").isdigit() else None
        mentions.append((a, signature(r), y, frozenset(js), tuple(nk(x["abbreviation"]) for x in reps if nk(x["abbreviation"]) != a)))


def flush(rows):
    rows.sort(key=lambda r: (int(r["match_start_offset"]), -int(r["match_end_offset"]),
                             r["citation_kind"] != "neutral"))
    kept, far = [], -1
    for r in rows:
        if int(r["match_end_offset"]) > far:
            kept.append(r); far = int(r["match_end_offset"])
    rows = kept
    chain = [rows[0]] if rows else []
    for a, b in zip(rows, rows[1:]):
        gap = int(b["match_start_offset"]) - int(a["match_end_offset"])
        pre = b["preceding_text"] or ""
        if 0 <= gap <= 4 and GAP_OK.match(pre[len(pre) - gap:] if gap else ""):
            chain.append(b)
        else:
            use(chain); chain = [b]
    if chain:
        use(chain)


for court in ("SCC", "ONCA", "BCCA"):
    cur, rows = None, []
    for r in csv.DictReader(open(os.path.join(R, "classify_out", court, "classified.csv"), encoding="utf-8")):
        if r["rejected_reason"]:
            continue
        if r["source_decision_citation"] != cur:
            flush(rows); cur, rows = r["source_decision_citation"], []
        rows.append(r)
    flush(rows)

# 第 0 跳种子（同 channel 4）：直接证据 ≥20 串且 ≥95% 单一法域/国家
direct = collections.defaultdict(collections.Counter)
for a, sig, y, js, partners in mentions:
    if len(js) == 1:
        direct[a][next(iter(js))] += 1
seed = {}
for a, c in direct.items():
    n = sum(c.values())
    if n < 20:
        continue
    j, m = c.most_common(1)[0]
    if m / n >= 0.95:
        seed[a] = j
        continue
    cc = collections.Counter()
    for k, v in c.items():
        cc[country(k)] += v
    k, m = cc.most_common(1)[0]
    if m / n >= 0.95:
        seed[a] = k

# 年代簇
years = collections.defaultdict(set)
for a, sig, y, js, p in mentions:
    if y and 1500 < y < 2030:
        years[a].add(y)
cuts = {}
for a, ys in years.items():
    ys = sorted(ys)
    cl, start = [], ys[0]
    for u, v in zip(ys, ys[1:]):
        if v - u > GAP_YEARS:
            cl.append((start, u)); start = v
    cl.append((start, ys[-1]))
    cuts[a] = cl


def era(a, y):
    if not y or a not in cuts:
        return "?"
    for s, e in cuts[a]:
        if s <= y <= e:
            return "%d-%d" % (s, e)
    return "?"


cell = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))   # a -> cellkey -> j
cell_n = collections.defaultdict(collections.Counter)
for a, sig, y, js, partners in mentions:
    ck = sig + " @" + era(a, y)
    cell_n[a][ck] += 1
    if len(js) == 1:
        cell[a][ck][next(iter(js))] += 1
    elif not js:
        ps = {seed[p] for p in partners if p in seed}
        if len({country(v) for v in ps}) == 1:
            cell[a][ck]["~" + next(iter(ps))] += 1          # ~ = 经种子汇编并印（渠道 4）得来


def top(c):
    cc = collections.Counter()
    for k, v in c.items():
        cc[country(k.lstrip("~"))] += v
    return cc.most_common(1)[0] if cc else (None, 0)


flagged = []
for a, cells in cell.items():
    rich = {ck: c for ck, c in cells.items() if sum(c.values()) >= MIN_EV}
    if len(rich) < 2:
        continue
    tops = {ck: top(c) for ck, c in rich.items()}
    countries = {t[0] for t in tops.values()}
    split = len(countries) > 1
    if not split:
        # 同国：看各格单一省是否不同
        provs = set()
        for ck, c in rich.items():
            pc = collections.Counter()
            for k, v in c.items():
                pc[k.lstrip("~")] += v
            j, m = pc.most_common(1)[0]
            if m / sum(pc.values()) >= 0.9 and j in PROV:
                provs.add(j)
        split = len(provs) > 1
    if split:
        flagged.append(a)

print("mentions:", len(mentions), "| seeds:", len(seed), "| abbrs with cells:", len(cell))
print("检出同形候选:", len(flagged), "| 已知同形命中:", sorted(KNOWN & set(flagged)),
      "| 已知同形漏检:", sorted(KNOWN - set(flagged)))
for a in sorted(flagged, key=lambda a: -sum(cell_n[a].values())) + sorted(KNOWN - set(flagged)):
    t = table.get(a)
    print("\n%s  （表=%s；提及 %d）%s" % (label.get(a, a), ",".join(sorted(t)) if t else "—", sum(cell_n[a].values()),
                                     "" if a in flagged else "  ← 已知同形，未检出"))
    for ck, n in sorted(cell_n[a].items(), key=lambda kv: -kv[1])[:8]:
        c = cell[a].get(ck, {})
        print("   %-28s 提及 %5d | 证据 %4d | %s" % (ck, n, sum(c.values()) if c else 0,
              ", ".join("%s %d" % x for x in collections.Counter(c).most_common(5)) if c else ""))

# ---- 弱档：结构/年代可分，但证据只在一边（或都没有）——只作待审线索，不作结论 ----
# 条件：该缩写总提及 ≥ 30，且满足其一：
#   (a) 有 ≥2 个年代簇各自提及 ≥ 5（断档 > GAP_YEARS 年）；
#   (b) 「No.」判决号式与卷-页式并存，各自提及 ≥ 5。
print("\n\n==== 弱档：结构/年代可分（待审线索；★不代表是同形，可能只是同一汇编的断档或引法变化）")
weak = []
for a, cn in cell_n.items():
    tot = sum(cn.values())
    if tot < 30 or a in flagged:
        continue
    era_n, no_n, vol_n = collections.Counter(), 0, 0
    for ck, n in cn.items():
        sig, e = ck.split(" @")
        if e != "?":
            era_n[e] += n
        if sig.startswith("No"):
            no_n += n
        else:
            vol_n += n
    eras = [e for e, n in era_n.items() if n >= 5]
    if len(eras) >= 2 or (no_n >= 5 and vol_n >= 5):
        weak.append((tot, a, era_n, no_n, vol_n))
for tot, a, era_n, no_n, vol_n in sorted(weak, reverse=True):
    t = table.get(a)
    ev_era = collections.defaultdict(collections.Counter)
    for ck, c in cell[a].items():
        ev_era[ck.split(" @")[1]].update(c)
    print("%-16s 表=%-7s 提及 %5d | No.式 %d / 其他 %d | %s" % (
        label.get(a, a), ",".join(sorted(t)) if t else "—", tot, no_n, vol_n,
        "  ".join("%s:%d[%s]" % (e, n, ",".join("%s %d" % x for x in ev_era[e].most_common(2)))
                  for e, n in sorted(era_n.items()) if n >= 5)))
print("弱档条数:", len(weak))
