"""汇总（只读）：人工表 reporter_jurisdiction.csv 每个缩写，在渠道 1–4 下的证据状态。

读 audit/findings/jurisdiction_channels/ch{1,2,3,4}_evidence.json（由四个渠道脚本写出），
不读 classified.csv、不改任何表。渠道 3 只用硬档（启发档已知被 #84 跨审级误并污染）；渠道 4 只用第 1 跳。
每个渠道证据 ≥ MIN_N 才算「有证据」。证据先折成国家（省 → CA；枢密院不给国家，单列）。
  支持：主导国家占比 ≥ SHARE 且在表的法域集合（折成国家）里；
  反对：主导国家占比 ≥ SHARE 且不在表里；
  混合：其余。
表是省级的行（ON、BC…），再用渠道 1/2 的直接证据看省：主导省占比 ≥ SHARE 且 ≠ 表 → 省级反对。
输出：summary.csv（每个缩写一行）＋按语料出现量（表 notes 里登记的「N 行」）加权的覆盖率。
"""
import csv, json, os, re, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "audit", "findings", "jurisdiction_channels")
MIN_N, SHARE = 10, 0.8
PROV = {"ON", "BC", "AB", "SK", "MB", "QC", "NS", "NB", "NL", "PE", "YK", "NT", "NU"}


def country(j):
    return "CA" if j in PROV else j


ch = {i: json.load(open(os.path.join(D, "ch%d_evidence.json" % i), encoding="utf-8")) for i in (1, 2, 3, 4)}
court_j = ch[2]["court_j"]
ev = {
    "ch1": ch[1]["ev"],
    "ch2": {a: {(court_j.get(c) or "JCPC"): 0 for c in d} for a, d in ch[2]["ev"].items()},
    "ch3": ch[3]["hard"],
    "ch4": ch[4]["hop1"],
}
for a, d in ch[2]["ev"].items():                    # 渠道 2：法院 → 法域（枢密院单列 JCPC）
    for c, n in d.items():
        ev["ch2"][a][court_j.get(c) or "JCPC"] += n

rows = collections.OrderedDict()
for r in csv.DictReader(open(os.path.join(ROOT, "decisions", "reporter_jurisdiction.csv"), encoding="utf-8")):
    k = r["normalized_key"]
    m = re.search(r"：\s*([\d,]+)\s*行", r["source_locator"] or "")
    rows.setdefault(k, {"abbr": r["abbreviation"], "js": set(), "mentions": 0})
    rows[k]["js"].add(r["jurisdiction"])
    if m:                                           # 同形缩写有多行，行数只登在其中一些行上：取最大
        rows[k]["mentions"] = max(rows[k]["mentions"], int(m.group(1).replace(",", "")))


def judge(dist, tcountries):
    n = sum(v for k, v in dist.items() if k != "JCPC")
    if n < MIN_N:
        return None, n, ""
    cc = collections.Counter()
    for k, v in dist.items():
        if k != "JCPC":
            cc[country(k)] += v
    top, m = cc.most_common(1)[0]
    desc = ", ".join("%s %d" % x for x in cc.most_common(3))
    if dist.get("JCPC"):
        desc += ", 枢密院 %d" % dist["JCPC"]
    if m / n >= SHARE:
        return ("支持" if top in tcountries else "反对"), n, desc
    return "混合", n, desc


out, tally, weighted = [], collections.Counter(), collections.Counter()
for k, r in rows.items():
    tc = {country(j) for j in r["js"]}
    verdicts, descs = {}, []
    for name in ("ch1", "ch2", "ch3", "ch4"):
        v, n, desc = judge(ev[name].get(k, {}), tc)
        if v:
            verdicts[name] = v
            descs.append("%s:%s(%d; %s)" % (name, v, n, desc))
    # 省级：表里是单一省时，用渠道 1+2 直接证据看省
    prov_note = ""
    tp = r["js"] & PROV
    if tp and len(r["js"]) == 1:
        pc = collections.Counter()
        for name in ("ch1", "ch2"):
            for j, v in ev[name].get(k, {}).items():
                if j in PROV:
                    pc[j] += v
        if sum(pc.values()) >= MIN_N:
            j, m = pc.most_common(1)[0]
            if m / sum(pc.values()) >= SHARE and j not in tp:
                prov_note = "省级反对：证据主导 %s %d/%d" % (j, m, sum(pc.values()))
            elif m / sum(pc.values()) >= SHARE:
                prov_note = "省级支持"
    vs = set(verdicts.values())
    if not vs:
        status = "无证据"
    elif "反对" in vs or prov_note.startswith("省级反对"):
        status = "证据反对"
    elif vs == {"支持"}:
        status = "证据支持"
    else:
        status = "混合" if "支持" not in vs else "支持（有混合）"
    tally[status] += 1
    weighted[status] += r["mentions"]
    out.append({"abbreviation": r["abbr"], "normalized_key": k, "table_jurisdiction": ",".join(sorted(r["js"])),
                "corpus_rows": r["mentions"], "status": status, "province_check": prov_note,
                "channels": " | ".join(descs)})

with open(os.path.join(D, "summary.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(sorted(out, key=lambda x: -x["corpus_rows"]))
tot = sum(weighted.values())
print("表内缩写 %d 个；按缩写计：%s" % (len(out), dict(tally)))
print("按语料行数加权（表 notes 登记的行数，合计 %d）：" % tot)
for s, v in weighted.most_common():
    print("  %-10s %8d  %.1f%%" % (s, v, 100 * v / tot if tot else 0))
print("\n证据反对 / 混合 的缩写：")
for x in sorted(out, key=lambda x: -x["corpus_rows"]):
    if x["status"] in ("证据反对", "混合", "支持（有混合）"):
        print("  %-14s 表=%-6s 行 %6d  %-8s %s  %s" % (x["abbreviation"], x["table_jurisdiction"], x["corpus_rows"],
              x["status"], x["province_check"], x["channels"]))
print("\n无证据、语料行数最多的 25 个：")
for x in [x for x in sorted(out, key=lambda x: -x["corpus_rows"]) if x["status"] == "无证据"][:25]:
    print("  %-14s 表=%-6s 行 %6d" % (x["abbreviation"], x["table_jurisdiction"], x["corpus_rows"]))
