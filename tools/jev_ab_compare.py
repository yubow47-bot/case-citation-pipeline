"""jev_ab_compare.py — compare runs A0 (baseline code), A (new code, Jev off), B (Jev on).

Read-only over the run directories; writes report.md and detail CSVs to --out
(default implementation/jev_ab/). A0->A isolates the code-only changes and
A->B isolates Jev. Every classify-level A->B difference must trace to an
adopted Jev ledger row; untraced differences are listed separately.
"""
import argparse
import csv
import gzip
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(1 << 30)
ROOT = Path(__file__).resolve().parents[1]
NODES = ["N8_source_date", "N1_candidate_type", "N2_case_name", "N5_name_owner",
         "N3_suffix_meaning", "N6_identity", "N7_ruling", "N4_case_history"]


def rows(path):
    path = Path(path)
    if not path.exists() and Path(str(path) + ".gz").exists():
        path = Path(str(path) + ".gz")
    if not path.exists():
        return
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def courts(run):
    return sorted(p.name for p in (run / "classify_out").iterdir() if p.is_dir())


def classify_index(run):
    out = {}
    for c in courts(run):
        for r in rows(run / "classify_out" / c / "classified.csv"):
            out[r["candidate_id"]] = r
    return out


def decided(run):
    return list(rows(run / "decide_out" / "cross_court" / "decided.csv"))


def member_dd(dec):
    return {r["court"] + "|" + r["merge_key"]: int(r["distinct_decisions_count"] or 0) for r in dec}


def group_signature(dec):
    """Group id -> frozenset of member row keys (ids are not stable across runs)."""
    g = defaultdict(set)
    for r in dec:
        g[r["merged_group_id"]].add(r["court"] + "|" + r["merge_key"])
    return {gid: frozenset(keys) for gid, keys in g.items()}


def edges(run, sig):
    out = {}
    for e in rows(run / "edges" / "citation_edges.csv"):
        out[(e["source_decision"], sig.get(e["resolved_cited_case"], frozenset()))] = e
    return out


def ledgers(run):
    out = defaultdict(list)
    paths = {str(p).removesuffix(".gz") for p in run.rglob("jev/*.csv*")}
    for path in sorted(paths):
        for r in rows(path):
            out[r["node"]].append(r)
    return out


def summarize(run):
    cls = classify_index(run)
    dec = decided(run)
    sig = group_signature(dec)
    eds = edges(run, sig)
    s = Counter()
    s["candidates"] = len(cls)
    for r in cls.values():
        s["row_status:" + (r.get("row_status") or ("citation_counted" if not r["rejected_reason"] else "rejected"))] += 1
        if not r["rejected_reason"]:
            s["counted_with_name"] += bool(r["candidate_case_name"])
            s["counted_rows"] += 1
        if r.get("case_name_source") and r["case_name_source"] != "rule":
            s["case_name_source:" + r["case_name_source"]] += 1
    s["groups"] = len(sig)
    s["members"] = len(dec)
    s["conflicted_keys"] = len({r["merge_key"] for r in dec if r.get("reporter_identity_conflict") == "true"})
    for r in dec:
        s["identity_basis:" + (r.get("identity_basis") or "")] += 1
        if r.get("ruling_identity_status"):
            s["ruling:" + r["ruling_identity_status"]] += 1
        for col in ("model_identity_doubt", "model_ruling_relation"):
            if r.get(col):
                s[col + ":" + r[col]] += 1
    s["edges"] = len(eds)
    for e in eds.values():
        s["edge_support:" + e["edge_support"]] += 1
        s["history_basis:" + e.get("history_basis", "n/a")] += 1
        s["own_case_history_pair:" + e.get("own_case_history_pair", "n/a")] += 1
    for r in rows(run / "source_integrity" / "source_records.csv"):
        if r.get("model_date_status"):
            s["model_date:" + r["model_date_status"]] += 1
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    return {"stats": s, "cls": cls, "dec": dec, "sig": sig, "edges": eds,
            "status": manifest.get("status"), "jev": manifest.get("jev", {})}


def diff_stats(a, b):
    keys = sorted(set(a["stats"]) | set(b["stats"]))
    return [(k, a["stats"].get(k, 0), b["stats"].get(k, 0)) for k in keys
            if a["stats"].get(k, 0) != b["stats"].get(k, 0)]


def dd_changes(a, b):
    da, db = member_dd(a["dec"]), member_dd(b["dec"])
    names = {r["court"] + "|" + r["merge_key"]: r.get("case_name_modal", "") for r in b["dec"]}
    ch = [(k, da.get(k, 0), db.get(k, 0), names.get(k, "")) for k in set(da) | set(db)
          if da.get(k, 0) != db.get(k, 0)]
    return sorted(ch, key=lambda x: -abs(x[2] - x[1]))


def classify_trace(a, b, led):
    # N3 writes its L0 labels (including "unclassified") whenever it asked.
    adopted = {r["item_key"] for node in ("N1_candidate_type", "N2_case_name", "N5_name_owner", "N3_suffix_meaning")
               for r in led.get(node, []) if r["adopted"] == "true" or node == "N3_suffix_meaning"}
    # A span-level rejection reaches same-span twins that have no ledger row of their own.
    span = lambda cid: cid.rsplit(":", 1)[0]
    adopted_spans = {span(c) for c in adopted}
    cols = ("rejected_reason", "candidate_case_name", "name_rejected_reason", "suffix_meanings_json")
    changed, untraced = 0, []
    for cid, rb in b["cls"].items():
        ra = a["cls"].get(cid)
        if ra is None:
            untraced.append((cid, "missing_in_A"))
            continue
        diff = [c for c in cols if (ra.get(c) or "") != (rb.get(c) or "")]
        if diff:
            changed += 1
            if cid not in adopted and not (diff == ["rejected_reason"] and span(cid) in adopted_spans):
                untraced.append((cid, ",".join(diff)))
    return changed, untraced


def node_section(name, recs, rng):
    lines = ["### %s" % name, ""]
    c = Counter((r["level"], r["adopted"], r["reason_not_adopted"].split(":")[0]) for r in recs)
    lines.append("| level | adopted | reason | n |")
    lines.append("|---|---|---|---|")
    for (lvl, ad, why), n in sorted(c.items(), key=lambda x: -x[1]):
        lines.append("| %s | %s | %s | %d |" % (lvl, ad, why or "-", n))
    hist = Counter(min(9, int(float(r["p_max"] or 0) * 10)) for r in recs)
    lines.append("")
    lines.append("p_max deciles: " + ", ".join("%.1f-%.1f: %d" % (d / 10, (d + 1) / 10, hist[d]) for d in range(10) if hist[d]))
    asked = len(recs)
    adopted = sum(r["adopted"] == "true" for r in recs)
    lines.append("")
    lines.append("asked %d, adopted %d (%.1f%%)" % (asked, adopted, 100 * adopted / asked if asked else 0))
    sample = [r for r in recs if r["adopted"] == "true"]
    sample = rng.sample(sample, min(30, len(sample)))
    if sample:
        lines += ["", "<details><summary>30 random adopted judgments</summary>", ""]
        for r in sample:
            lines.append("- `%s` choice=`%s` p=%s ratio=%s noul=%s  \n  %s" % (
                r["item_key"], r["choice"], r["p_max"], r["ratio"], r["noul"] or "-",
                r["state_excerpt"].replace("\n", " ")[:500]))
        lines += ["", "</details>"]
    review = [r for r in recs if r["reason_not_adopted"].startswith("below_") or "agreement" in r["reason_not_adopted"]]
    lines.append("")
    lines.append("review queue (between floor and tier): %d" % len(review))
    lines.append("")
    return lines, asked, adopted


def alarms(led, cfg):
    out = []
    for node, recs in led.items():
        for lvl in ("L2", "L3"):
            sub = [r for r in recs if r["level"] == lvl]
            if not sub:
                continue
            rate = sum(r["adopted"] == "true" for r in sub) / len(sub)
            limit = cfg["alarms"]["L2_adoption_rate" if lvl == "L2" else "L3_adoption_rate"]
            if rate > limit:
                out.append("%s %s adoption %.1f%% > %.0f%%" % (node, lvl, 100 * rate, 100 * limit))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--a0", required=True)
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", default=None)
    ap.add_argument("--out", default=str(ROOT / "implementation" / "jev_ab"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20261020)
    import yaml
    cfg = yaml.safe_load((ROOT / "jev_config.yaml").read_text(encoding="utf-8"))

    runs = {"A0": summarize(Path(args.a0)), "A": summarize(Path(args.a))}
    if args.b:
        runs["B"] = summarize(Path(args.b))
    lines = ["# Jev A/B comparison", "", "Runs: " + ", ".join(
        "%s=`%s` (%s)" % (k, getattr(args, k.lower()), v["status"]) for k, v in runs.items()), ""]

    lines += ["## Headline numbers", "", "| metric | " + " | ".join(runs) + " |",
              "|---|" + "---|" * len(runs)]
    keys = ["candidates", "counted_rows", "counted_with_name", "groups", "members", "conflicted_keys",
            "edges", "edge_support:supported", "edge_support:heuristic_only",
            "history_basis:formal_all", "history_basis:formal_pair", "history_basis:model", "history_basis:none",
            "identity_basis:model_confirmed", "row_status:not_citation", "row_status:citation_uncounted",
            "row_status:citation_counted"]
    for k in keys:
        lines.append("| %s | %s |" % (k, " | ".join(str(r["stats"].get(k, 0)) for r in runs.values())))
    lines.append("")

    for left, right in (("A0", "A"), ("A", "B")):
        if right not in runs:
            continue
        a, b = runs[left], runs[right]
        lines += ["## %s -> %s" % (left, right), ""]
        lines += ["| stat | %s | %s |" % (left, right), "|---|---|---|"]
        for k, va, vb in diff_stats(a, b):
            lines.append("| %s | %d | %d |" % (k, va, vb))
        dd = dd_changes(a, b)
        with (out / ("dd_changes_%s_%s.csv" % (left, right))).open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["member_row_key", "dd_" + left, "dd_" + right, "case_name"])
            w.writerows(dd)
        lines += ["", "Members whose DD changed: %d (top 30 below; full list in dd_changes_%s_%s.csv)" % (len(dd), left, right), ""]
        for k, x, y, n in dd[:30]:
            lines.append("- `%s` %s: %d -> %d" % (k, n[:60], x, y))
        lines.append("")

    if "B" in runs:
        led = ledgers(Path(args.b))
        lines += ["## Jev nodes (run B)", ""]
        for node in NODES:
            if led.get(node):
                sec, _, _ = node_section(node, led[node], rng)
                lines += sec
        changed, untraced = classify_trace(runs["A"], runs["B"], led)
        lines += ["## Difference tracing (classify A -> B)", "",
                  "Changed classified rows: %d; not traced to an adopted Jev record: %d" % (changed, len(untraced)), ""]
        for cid, why in untraced[:50]:
            lines.append("- `%s`: %s" % (cid, why))
        al = alarms(led, cfg)
        lines += ["", "## Alarms", ""] + (["- " + x for x in al] if al else ["None triggered."])
        jev = runs["B"]["jev"]
        lines += ["", "## Jev usage and throughput", "", "```json", json.dumps(jev, indent=1)[:6000], "```"]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", out / "report.md")


if __name__ == "__main__":
    main()
