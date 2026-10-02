"""试验（只读）：渠道 4——汇编与汇编印在一起，把已知法域一步步传给未知的（主要为 1999 年以前、无括注的老汇编）。

证据单元与渠道 1、2 相同：印刷上相邻、只隔逗号/空白的一串引证；重叠候选按渠道 1 的办法去重。
种子不读人工表：只用渠道 1（并列中立引证）与渠道 2（有出处的法院括注）在同一批串上直接得到的证据，
  种子条件：证据 ≥ SEED_N 串，且 ≥ SEED_SHARE 指向同一法域（地方汇编）或同一国家（全国性汇编，只传国家）。
传播：串里有种子汇编 S（法域 j）→ 串里其他每种汇编各得一条「与 j 的汇编印在一起」的证据。
  第 1 跳由渠道 1/2 种子出发；第 1 跳达到种子条件的汇编在第 2 跳加入种子；最多 2 跳，证据按跳数分开记。
枢密院括注不给法域（D2）；渠道 2 只用已入库表＋司法部提案（同 jurisdiction_from_designations.py）。

已知风险（如实）：英国汇编常与枢密院上诉案并印，种子 GB 的传播对殖民地上诉案会给错国家；所以输出分布、标跳数，不输出标签。
"""
import csv, json, os, re, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv.field_size_limit(10 ** 9)
R = os.path.join(ROOT, "data", "run_20260918_scc_onca_bcca")
GAP_OK = re.compile(r"^[\s,]*$")
SEED_N, SEED_SHARE = 20, 0.95
PROV = {"ON", "BC", "AB", "SK", "MB", "QC", "NS", "NB", "NL", "PE", "YK", "NT", "NU"}


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

# 先把所有串收下来：(reporters, direct_js, old)
chains = []
label = {}
stats = collections.Counter()


def use(chain):
    reps = []
    js = set()
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
        if r["citation_kind"] == "reporter":
            a = nk(r["abbreviation"])
            if a and a not in reps:
                reps.append(a); label.setdefault(a, r["abbreviation"])
    if not reps:
        return
    yrs = [int(r["year_start"]) for r in chain if (r["year_start"] or "").isdigit()]
    chains.append((tuple(reps), frozenset(js), bool(yrs) and min(yrs) < 1999))


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

multi = [c for c in chains if len(c[0]) >= 2]
stats["chains_with_reporter"] = len(chains)
stats["chains_2plus_reporters"] = len(multi)
stats["chains_2plus_no_direct"] = sum(1 for c in multi if not c[1])
stats["chains_2plus_no_direct_pre1999"] = sum(1 for c in multi if not c[1] and c[2])

# 直接证据（渠道 1+2，单一法域的串才计）
direct = collections.defaultdict(collections.Counter)
for reps, js, old in chains:
    if len(js) == 1:
        j = next(iter(js))
        for a in reps:
            direct[a][j] += 1


def seed_of(c):
    """返回 (level, value)：地方汇编 ('j', 'ON')；全国性 ('country', 'CA')；否则 None。"""
    n = sum(c.values())
    if n < SEED_N:
        return None
    j, m = c.most_common(1)[0]
    if m / n >= SEED_SHARE:
        return ("j", j)
    cc = collections.Counter()
    for k, v in c.items():
        cc[country(k)] += v
    k, m = cc.most_common(1)[0]
    if m / n >= SEED_SHARE:
        return ("country", k)
    return None


seeds = {a: (seed_of(c), 0) for a, c in direct.items() if seed_of(c)}
print(dict(stats))
print("hop-0 seeds (渠道 1/2 直接证据):", len(seeds))

prop = {1: collections.defaultdict(collections.Counter), 2: collections.defaultdict(collections.Counter)}
prop_old = {1: collections.defaultdict(collections.Counter), 2: collections.defaultdict(collections.Counter)}
via = {1: collections.defaultdict(collections.Counter), 2: collections.defaultdict(collections.Counter)}
for hop in (1, 2):
    for reps, js, old in multi:
        ss = [(a, seeds[a][0]) for a in reps if a in seeds]
        if not ss:
            continue
        vals = {v for _, (lvl, v) in ss}
        # 串里种子互相矛盾（如 ON 与 GB）→ 不传
        if len({country(v) for v in vals}) > 1:
            stats["hop%d_conflict_chains" % hop] += 1
            continue
        for t in reps:
            if t in seeds:
                continue
            for a, (lvl, v) in ss:
                prop[hop][t][v] += 1
                via[hop][t][label[a]] += 1
                if old:
                    prop_old[hop][t][v] += 1
                break                                     # 每串每目标只计一次（取第一个种子）
    if hop == 1:
        new = {}
        for t, c in prop[1].items():
            s = seed_of(c)
            if s and t not in seeds:
                new[t] = (s, 1)
        print("hop-1 新种子:", len(new))
        seeds.update(new)

print(dict(stats))
for hop in (1, 2):
    res = collections.Counter()
    print("\n==== 第 %d 跳（第 2 跳的种子＝直接种子＋第 1 跳新种子，目标重复出现属正常；单位：串）" % hop)
    print("   all  pre99  abbr                 直接证据  表        分布 | 经由种子")
    for t, c in sorted(prop[hop].items(), key=lambda kv: -sum(kv[1].values())):
        n = sum(c.values())
        if n < 10:
            res["lt10"] += 1
            continue
        res["ge10"] += 1
        tt = table.get(t)
        cc = collections.Counter()
        for k, v in c.items():
            cc[country(k)] += v
        top, m = cc.most_common(1)[0]
        ok = bool(tt) and (top in {country(x) for x in tt})
        res["in_table" if tt else "NOT_in_table"] += 1
        if tt:
            res["country_agree" if ok else "country_DISAGREE"] += 1
        print("%6d %6d  %-20s %-8d %-8s %s %s | %s" % (
            n, sum(prop_old[hop][t].values()), label[t], sum(direct[t].values()),
            ",".join(sorted(tt)) if tt else "—", "" if not tt else ("✓" if ok else "✗"),
            ", ".join("%s %d" % x for x in c.most_common(5)),
            ", ".join("%s %d" % x for x in via[hop][t].most_common(3))))
    print(dict(res))

# 完整分布另存，供 audit/jurisdiction_channels_summary.py 汇总
json.dump({"hop1": {k: dict(v) for k, v in prop[1].items()}, "hop2": {k: dict(v) for k, v in prop[2].items()}, "hop1_old": {k: dict(v) for k, v in prop_old[1].items()}, "label": label},
          open(os.path.join(ROOT, "audit", "findings", "jurisdiction_channels", "ch4_evidence.json"), "w", encoding="utf-8"), ensure_ascii=False)
