"""试验（只读）：不查人工表，只凭「印在一起的并列中立引证」推出每种汇编登的是哪些法院的案子。

证据单元 = 同一判决里印刷上相邻的一串引证（两两之间只有逗号/空白，不含分号——分号通常分隔不同案子）。
串里若有中立引证（法院码 → 法域来自已核实的 neutral_court_codes.csv），串里每个汇编引证就得到一条
「此汇编登过该法院的一个案子」的证据。不使用 merge/decide 的归并结果，避免循环论证。
输出：每种汇编的证据串数、法域分布；与 reporter_jurisdiction.csv（人工按名推断）对照。
"""
import csv, json, os, re, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv.field_size_limit(10 ** 9)
# 2026-10-03：run/法院/输出目录可由环境变量覆盖（边缘四法庭复用同一渠道；默认值不变）
R = os.path.join(ROOT, os.environ.get("CHANNEL_RUN", os.path.join("data", "run_20260918_scc_onca_bcca")))
CHANNEL_COURTS = tuple((os.environ.get("CHANNEL_COURTS") or "SCC,ONCA,BCCA").split(","))
CHANNEL_OUT = os.path.join(ROOT, os.environ.get("CHANNEL_OUT", os.path.join("audit", "findings", "jurisdiction_channels")))
GAP_OK = re.compile(r"^[\s,]*$")


def nk(s):
    return re.sub(r"[^A-Za-z0-9]", "", s or "").lower()


table = {}
for r in csv.DictReader(open(os.path.join(ROOT, "decisions", "reporter_jurisdiction.csv"), encoding="utf-8")):
    table.setdefault(r["normalized_key"], set()).add(r["jurisdiction"])
court_j = {nk(r["court_code"]): r["jurisdiction"] for r in
           csv.DictReader(open(os.path.join(ROOT, "decisions", "neutral_court_codes.csv"), encoding="utf-8"))}

ev = collections.defaultdict(collections.Counter)      # abbr -> jurisdiction -> chains
ev_court = collections.defaultdict(collections.Counter)
abbr_label = {}
stats = collections.Counter()


def flush(rows):
    # 同一处印刷常被抽成重叠的两条候选（「(1995), 128 A.L.R. 540」与其内的「128 A.L.R. 540」）；
    # 被另一候选完全包含的不计，否则证据重复计数、且重叠造成的负间隔会把一串切断。（2026-10-01 订正）
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
            use(chain); chain = [b]
    if chain:
        use(chain)


def use(chain):
    if len(chain) < 2:
        return
    stats["parallel_chains"] += 1
    neut = {nk(r["abbreviation"]) for r in chain if r["citation_kind"] == "neutral"}
    js = {court_j[c] for c in neut if c in court_j}
    if not js:
        return
    stats["chains_with_neutral"] += 1
    seen = set()                                          # 每串每种汇编只计一次（2026-10-01 订正）
    for r in chain:
        if r["citation_kind"] == "neutral":
            continue
        k = nk(r["abbreviation"])
        if not k or k in seen:
            continue
        seen.add(k)
        abbr_label.setdefault(k, r["abbreviation"])
        for j in js:
            ev[k][j] += 1
        for c in neut:
            ev_court[k][c.upper()] += 1


for court in CHANNEL_COURTS:
    cur, rows = None, []
    for r in csv.DictReader(open(os.path.join(R, "classify_out", court, "classified.csv"), encoding="utf-8")):
        if r["rejected_reason"]:
            continue
        if r["source_decision_citation"] != cur:
            flush(rows); cur, rows = r["source_decision_citation"], []
        rows.append(r)
    flush(rows)

print(dict(stats))
N = 10
res = collections.Counter()
lines = []
for k, c in sorted(ev.items(), key=lambda kv: -sum(kv[1].values())):
    n = sum(c.values())
    if n < N:
        res["abbr_lt10"] += 1
        continue
    top, tn = c.most_common(1)[0]
    share = tn / n
    t = table.get(k)
    if share >= 0.9:
        verdict = "single:" + top
        agree = t and top in t
    else:
        verdict = "multi"
        agree = t and "CA" in t          # 表里「CA」= 全国性汇编
    res["abbr_ge10"] += 1
    res["in_table" if t else "NOT_in_table"] += 1
    if t:
        res["agree" if agree else "DISAGREE"] += 1
    lines.append((n, abbr_label[k], verdict, ",".join(sorted(t)) if t else "—", "" if not t else ("✓" if agree else "✗"),
                  ", ".join("%s %d" % x for x in c.most_common(5)),
                  ", ".join("%s %d" % x for x in ev_court[k].most_common(4))))
print(dict(res), "| table rows:", len(table))
for l in lines[:45]:
    print("%6d  %-14s %-10s 表=%-6s %s  | %s | %s" % l)
print("... 不一致的：")
for l in lines:
    if l[4] == "✗":
        print("%6d  %-14s %-10s 表=%-6s | %s | %s" % (l[0], l[1], l[2], l[3], l[5], l[6]))

# 完整分布另存，供 audit/jurisdiction_channels_summary.py 汇总
json.dump({"ev": {k: dict(v) for k, v in ev.items()}, "label": abbr_label},
          open(os.path.join(CHANNEL_OUT, "ch1_evidence.json"), "w", encoding="utf-8"), ensure_ascii=False)
