"""试验（只读）：渠道 3——被引判决自己的记录。

单位 = 一个不同的汇编引证键（一个案子在该汇编里的一处登载），不是提及数。
组（select_out/selected.csv 的 merged_group_id，跨院归并结果）的法院来自两种事实：
  · 组里的锚键是语料判决的自引（registry/decision_registry.csv：键 → SCC/ONCA/BCCA，判决书抬头印的）；
  · 组里有中立引证成员（法院码 → 法域，已核实的 neutral_court_codes.csv）。
组里汇编键按它**怎么进组**分两档，分开报、不混：
  · 硬档：identity_basis ∈ ELIGIBLE_BASES（anchor 等）——键本身就是该身份；
  · 启发档：name_year / cocitation / anchor_variant_typo_* / unanchored——项目规则里不得升成组结论，
    这里只当「待审线索」列出。
组内法域多于一个 → 冲突，整组不计。

注意：归并层的仲裁（哪种读法计数）会用到分类层盖的 jurisdiction 支持分（merge.py support_grade），
所以本渠道不是完全独立于人工表；分组本身不读 reporter_jurisdiction.csv。
"""
import csv, json, os, re, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv.field_size_limit(10 ** 9)
R = os.path.join(ROOT, "data", "run_20260918_scc_onca_bcca")
ELIGIBLE = {"anchor", "singleton", "same_citation", "anchor_variant_bilingual"}
REG_J = {"SCC": "CA", "ONCA": "ON", "BCCA": "BC"}


def nk(s):
    return re.sub(r"[^A-Za-z0-9]", "", s or "").lower()


court_j = {nk(r["court_code"]): r["jurisdiction"] for r in
           csv.DictReader(open(os.path.join(ROOT, "decisions", "neutral_court_codes.csv"), encoding="utf-8"))}
reg = {}
for r in csv.DictReader(open(os.path.join(R, "registry", "decision_registry.csv"), encoding="utf-8")):
    reg.setdefault(r["merge_key"], set()).add(r["source_court"])
table = {}
for r in csv.DictReader(open(os.path.join(ROOT, "decisions", "reporter_jurisdiction.csv"), encoding="utf-8")):
    table.setdefault(r["normalized_key"], set()).add(r["jurisdiction"])

groups = collections.defaultdict(dict)        # gid -> merge_key -> row（同键跨院多行只留一行）
for r in csv.DictReader(open(os.path.join(R, "select_out", "selected.csv"), encoding="utf-8")):
    groups[r["merged_group_id"]].setdefault(r["merge_key"], r)

stats = collections.Counter()
ev = {"hard": collections.defaultdict(collections.Counter), "heur": collections.defaultdict(collections.Counter)}
ev_old = {"hard": collections.defaultdict(collections.Counter), "heur": collections.defaultdict(collections.Counter)}
label = {}
for gid, mem in groups.items():
    if len(mem) < 2 and not any(k in reg for k in mem):
        continue
    js, how = set(), set()
    for k, r in mem.items():
        if k in reg:
            js |= {REG_J[c] for c in reg[k]}; how.add("registry")
        if r["citation_kind"] == "neutral":
            j = court_j.get(nk(r["abbreviation"]))
            if j:
                js.add(j); how.add("neutral")
    if not js:
        continue
    stats["groups_with_court"] += 1
    if len(js) > 1:
        stats["groups_conflict"] += 1
        continue
    j = next(iter(js))
    for k, r in mem.items():
        if r["citation_kind"] != "reporter" or not nk(r["abbreviation"]):
            continue
        a = nk(r["abbreviation"]); label.setdefault(a, r["abbreviation"])
        tier = "hard" if r["identity_basis"] in ELIGIBLE else "heur"
        stats["keys_" + tier] += 1
        ev[tier][a][j] += 1
        y = r["year_printed"] or ""
        if y.isdigit() and int(y) < 1999:
            ev_old[tier][a][j] += 1
            stats["keys_%s_pre1999" % tier] += 1

print(dict(stats))
for tier in ("hard", "heur"):
    print("\n==== %s 档（单位：不同汇编键）" % tier)
    res = collections.Counter()
    print("   all  pre99  abbr             表        分布")
    for a, c in sorted(ev[tier].items(), key=lambda kv: -sum(kv[1].values())):
        n = sum(c.values())
        if n < 10:
            res["lt10"] += 1
            continue
        top, tn = c.most_common(1)[0]
        t = table.get(a)
        agree = (top in t) if (t and tn / n >= 0.9) else (bool(t) and "CA" in t)
        res["ge10"] += 1
        res["in_table" if t else "NOT_in_table"] += 1
        if t:
            res["agree" if agree else "DISAGREE"] += 1
        print("%6d %6d  %-16s %-8s %s %s" % (n, sum(ev_old[tier][a].values()), label[a],
              ",".join(sorted(t)) if t else "—", "" if not t else ("✓" if agree else "✗"),
              ", ".join("%s %d" % x for x in c.most_common(6))))
    print(dict(res))

# 完整分布另存，供 audit/jurisdiction_channels_summary.py 汇总
json.dump({t: {k: dict(v) for k, v in ev[t].items()} for t in ev} | {"label": label},
          open(os.path.join(ROOT, "audit", "findings", "jurisdiction_channels", "ch3_evidence.json"), "w", encoding="utf-8"), ensure_ascii=False)
