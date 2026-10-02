"""试验（只读）：渠道 2——凭引证后印着的法院括注 (Ont. C.A.)、(H.L.) 推出每种汇编登的是哪些法院的案子。

证据单元 = 与 jurisdiction_from_parallels.py 相同的「印在一起的并列引证串」。括注印在串尾，说的是整个案子，
所以串里若有一条括注被识别为某法院，串里每个汇编引证都得到一条「此汇编登过该法院的一个案子」的证据。
串内出现两个不同法院 → 冲突，整串不计。

括注含义只来自有出处的表：decisions/court_designations.csv（已入库 8 行）
＋ audit/findings/court_designations_doj_proposal.csv（加拿大司法部缩写表，提案未入库）。
精确匹配（nk 归一），不按名字猜；ambiguous_designation 行（裸 C.A.、S.C.）不给法院。
不使用 merge/decide 的归并结果，不读 reporter_jurisdiction.csv 做推断（只在末尾做对照）。

输出：每种汇编的证据串数、法院分布，按 1999 年前后分开（渠道 1 的中立引证只覆盖 1999 年以后）；
与人工表、渠道 1 的结论对照。
"""
import csv, json, os, re, sys, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv.field_size_limit(10 ** 9)
R = os.path.join(ROOT, "data", "run_20260918_scc_onca_bcca")
GAP_OK = re.compile(r"^[\s,]*$")
USE_PROPOSAL = "--no-proposal" not in sys.argv


def nk(s):
    return re.sub(r"[^A-Za-z0-9]", "", s or "").lower()


# 法院 → 用于对照人工表的法域。枢密院审各殖民地上诉，法院≠来源地（D2），不给法域。
COURT_J = {"House of Lords": "GB", "High Court of Australia": "AU",
           "Judicial Committee of the Privy Council": None}
desig = {}
for r in csv.DictReader(open(os.path.join(ROOT, "decisions", "court_designations.csv"), encoding="utf-8")):
    if r["status"] == "recognized":
        desig[r["normalized_key"]] = r["canonical_court"]
if USE_PROPOSAL:
    for r in csv.DictReader(open(os.path.join(ROOT, "audit", "findings", "court_designations_doj_proposal.csv"),
                                 encoding="utf-8")):
        if r["status"] == "recognized":
            desig[r["normalized_key"]] = r["canonical_court"]
            COURT_J[r["canonical_court"]] = r["court_jurisdiction"]

table = {}
for r in csv.DictReader(open(os.path.join(ROOT, "decisions", "reporter_jurisdiction.csv"), encoding="utf-8")):
    table.setdefault(r["normalized_key"], set()).add(r["jurisdiction"])

ev = collections.defaultdict(collections.Counter)        # abbr -> court -> chains
ev_old = collections.defaultdict(collections.Counter)    # 同上，只计串内最早年份 < 1999
ev_src = collections.defaultdict(set)                    # abbr -> 引用方法院（证据来自几家）
abbr_label = {}
printed = collections.defaultdict(collections.Counter)   # 识别键 -> 印刷形（核查 nk 同键的不同写法）
stats = collections.Counter()


def use(chain, src):
    courts = set()
    for r in chain:
        raw = (r["court_designation_raw"] or "").strip()
        if not raw:
            continue
        stats["designations_seen"] += 1
        c = desig.get(nk(raw))
        if c:
            courts.add(c)
            printed[nk(raw)][raw] += 1
    if not courts:
        return
    stats["chains_with_court"] += 1
    if len(courts) > 1:
        stats["chains_conflict"] += 1
        return
    c = next(iter(courts))
    yrs = [int(r["year_start"]) for r in chain if (r["year_start"] or "").isdigit()]
    old = bool(yrs) and min(yrs) < 1999
    stats["chains_used_pre1999" if old else "chains_used_1999plus_or_noyear"] += 1
    seen = set()                                          # 每串每种汇编只计一次
    for r in chain:
        if r["citation_kind"] == "neutral":
            continue
        k = nk(r["abbreviation"])
        if not k or k in seen:
            continue
        seen.add(k)
        abbr_label.setdefault(k, r["abbreviation"])
        ev[k][c] += 1
        ev_src[k].add(src)
        if old:
            ev_old[k][c] += 1


def flush(rows, src):
    # 同一处印刷常被抽成重叠的两条候选（「(1995), 128 A.L.R. 540」与其内的「128 A.L.R. 540」）；
    # 被另一候选完全包含的不计，否则证据重复计数、且重叠造成的负间隔会把一串切断。
    # 中立引证「2023 ONCA 812」还会被抽成同一跨度的「卷-缩写-页」汇编候选（二选一在归并层才做）；
    # 同跨度时优先保留中立那条，否则串里的中立引证会被它的影子挤掉。
    rows.sort(key=lambda r: (int(r["match_start_offset"]), -int(r["match_end_offset"]),
                             r["citation_kind"] != "neutral"))
    kept, far = [], -1
    for r in rows:
        if int(r["match_end_offset"]) > far:
            kept.append(r); far = int(r["match_end_offset"])
        else:
            stats["contained_dropped"] += 1
    rows = kept
    chain = [rows[0]] if rows else []
    for a, b in zip(rows, rows[1:]):
        gap = int(b["match_start_offset"]) - int(a["match_end_offset"])
        pre = b["preceding_text"] or ""
        if 0 <= gap <= 4 and GAP_OK.match(pre[len(pre) - gap:] if gap else ""):
            chain.append(b)
        else:
            use(chain, src); chain = [b]
    if chain:
        use(chain, src)


for court in ("SCC", "ONCA", "BCCA"):
    cur, rows = None, []
    for r in csv.DictReader(open(os.path.join(R, "classify_out", court, "classified.csv"), encoding="utf-8")):
        if r["rejected_reason"]:
            continue
        if r["source_decision_citation"] != cur:
            flush(rows, court); cur, rows = r["source_decision_citation"], []
        rows.append(r)
    flush(rows, court)

print("proposal rows used:", USE_PROPOSAL, "| recognized keys:", len(desig))
print(dict(stats))
print("印刷形核查（识别键 → 前几种写法）：")
for k, c in sorted(printed.items(), key=lambda kv: -sum(kv[1].values())):
    print("  %-8s %-40s %s" % (k, desig[k], ", ".join("%s %d" % x for x in c.most_common(6))))

N = 10


def short(c):
    return {"Supreme Court of Canada": "SCC", "Ontario Court of Appeal": "ONCA",
            "British Columbia Court of Appeal": "BCCA", "British Columbia Supreme Court": "BCSC",
            "Federal Court of Appeal": "FCA", "Tax Court of Canada": "TCC", "Exchequer Court": "ExC",
            "House of Lords": "HL", "Judicial Committee of the Privy Council": "JCPC",
            "High Court of Australia": "HCA"}.get(c, c)


res = collections.Counter()
rows_out = []
for k, c in sorted(ev.items(), key=lambda kv: -sum(kv[1].values())):
    n = sum(c.values())
    if n < N:
        res["abbr_lt10"] += 1
        continue
    res["abbr_ge10"] += 1
    nold = sum(ev_old[k].values())
    if nold >= N:
        res["abbr_ge10_pre1999"] += 1
    js = collections.Counter()
    for court, m in c.items():
        js[COURT_J.get(court) or "—"] += m
    jtop, jn = js.most_common(1)[0]
    t = table.get(k)
    if jtop != "—" and jn / n >= 0.9:
        verdict = "single:" + jtop
        agree = bool(t) and jtop in t
    else:
        verdict = "multi"
        agree = bool(t) and "CA" in t
    res["in_table" if t else "NOT_in_table"] += 1
    if t:
        res["agree" if agree else "DISAGREE"] += 1
    rows_out.append((n, nold, abbr_label[k], verdict, ",".join(sorted(t)) if t else "—",
                     "" if not t else ("✓" if agree else "✗"),
                     ", ".join("%s %d" % (short(a), b) for a, b in c.most_common(5)),
                     "/".join(sorted(ev_src[k]))))
print(dict(res), "| table rows:", len(table))
print("   all  pre99  abbr           verdict     表       | 法院分布 | 引用方")
for l in rows_out[:60]:
    print("%6d %6d  %-14s %-11s 表=%-6s %s | %s | %s" % l)
print("... 不一致的：")
for l in rows_out:
    if l[5] == "✗":
        print("%6d %6d  %-14s %-11s 表=%-6s | %s | %s" % (l[0], l[1], l[2], l[3], l[4], l[6], l[7]))
print("... 人工表里没有、证据 >=10 的：")
for l in rows_out:
    if l[4] == "—":
        print("%6d %6d  %-14s %-11s | %s | %s" % (l[0], l[1], l[2], l[3], l[6], l[7]))

# 完整分布另存，供 audit/jurisdiction_channels_summary.py 汇总
json.dump({"ev": {k: dict(v) for k, v in ev.items()}, "ev_old": {k: dict(v) for k, v in ev_old.items()}, "court_j": COURT_J, "label": abbr_label},
          open(os.path.join(ROOT, "audit", "findings", "jurisdiction_channels", "ch2_evidence.json"), "w", encoding="utf-8"), ensure_ascii=False)
