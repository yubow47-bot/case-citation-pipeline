"""T1：取 csc-scc / onca / bcca 全名录，并把本语料每份判决映射到 CanLII caseId。

映射规则（按可靠度，逐条记 basis）：
  neutral  : citation_en 形如 'YYYY COURT N' -> caseId 'yyyycourtN'，须在名录中存在
  reporter : citation_en 是汇编引证（SCC 的 '[1935] SCR 238'），与名录 citation 串里的同一汇编引证精确相等
  name     : 案名归一化后与名录 title 唯一相等（日期待逐案核实，basis 标 name_unverified）
  none     : 以上皆无
"""
import csv, json, os, re, sys, collections
sys.path.insert(0, os.path.dirname(__file__))
from canlii_client import get, calls_made, ROOT
import pyarrow.parquet as pq

DB = {"SCC": "csc-scc", "ONCA": "onca", "BCCA": "bcca"}
OUT = os.path.join(ROOT, "audit", "findings", "canlii_crosscheck")
os.makedirs(OUT, exist_ok=True)


def catalog(db):
    cases, off = [], 0
    while True:
        d = get("caseBrowse/en/%s/?offset=%d&resultCount=10000" % (db, off))
        page = d.get("cases", [])
        cases += page
        if len(page) < 10000:
            return cases
        off += 10000


def nname(s):
    s = (s or "").lower().replace("&", " and ")
    s = re.sub(r"\bv\.?s?\b", " v ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return " ".join(s.split())


def nrep(s):
    return re.sub(r"[\s.]+", "", s or "").upper()


def main():
    rows, summary = [], collections.Counter()
    for court, db in DB.items():
        cat = catalog(db)
        ids = {}
        rep_idx, name_idx = collections.defaultdict(set), collections.defaultdict(set)
        for c in cat:
            cid = (c["caseId"].get("en") or next(iter(c["caseId"].values()))) if isinstance(c["caseId"], dict) else c["caseId"]
            ids[cid] = c
            for part in (c.get("citation") or "").split(","):
                part = part.strip()
                if "CanLII" not in part and part:
                    rep_idx[nrep(part)].add(cid)
            name_idx[nname(c.get("title"))].add(cid)
        pf = pq.ParquetFile(os.path.join(ROOT, "corpus", "%s.parquet" % court))
        for b in pf.iter_batches(columns=["citation_en", "name_en", "document_date_en"]):
            for r in b.to_pylist():
                cit = (r["citation_en"] or "").strip()
                y = r["document_date_en"].year if r["document_date_en"] else None
                m = re.match(r"^(\d{4}) %s (\d+)$" % court, cit)
                cid, basis = "", "none"
                if m:
                    k = "%s%s%d" % (m.group(1), court.lower(), int(m.group(2)))
                    if k in ids:
                        cid, basis = k, "neutral"
                    else:
                        basis = "neutral_absent"
                if not cid and nrep(cit) in rep_idx and len(rep_idx[nrep(cit)]) == 1:
                    cid, basis = next(iter(rep_idx[nrep(cit)])), "reporter"
                if not cid:
                    hits = name_idx.get(nname(r["name_en"]), set())
                    if y:
                        hits = {h for h in hits if h[:4].isdigit() and abs(int(h[:4]) - y) <= 1}
                    if len(hits) == 1:
                        cid, basis = next(iter(hits)), "name_unverified"
                    elif len(hits) > 1:
                        basis = "name_ambiguous"
                rows.append({"court": court, "our_id": court + "_" + cit, "year": y or "",
                             "citation_en": cit, "canlii_id": cid, "basis": basis})
                summary[(court, (y // 10 * 10) if y else 0, basis)] += 1
        summary[(court, "catalog_size", "")] = len(cat)
    with open(os.path.join(ROOT, "data", "canlii_cache", "crosscheck", "t1_map.csv"), "w",
              newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    with open(os.path.join(OUT, "t1_coverage.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["court", "decade", "basis", "n"])
        for k in sorted(summary, key=str):
            w.writerow(list(k) + [summary[k]])
    print("calls this run:", calls_made())


if __name__ == "__main__":
    main()
