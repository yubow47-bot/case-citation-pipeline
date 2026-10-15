"""Make a tiny offline research fixture. Never uses a production corpus or DB."""
import argparse
import csv
import gzip
import json
import sqlite3
from pathlib import Path

from core import (DOCUMENT_FIELDS, EDGE_FIELDS, STREAM_SCHEMA, canonical,
                  file_hash, optional_arrow)


def write_csv(path, fields, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(records)


def create_fixture(destination, with_parquet=False):
    destination = Path(destination).resolve()
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError("Choose an empty fixture output directory; existing artifacts are never overwritten")
    run = destination / "run_fixture"
    run.mkdir(parents=True, exist_ok=True)
    corpus = destination / "corpus"
    manifest = {"status": "complete", "input_identity_verified_unchanged": True,
                "params": {"courts": ["SCC", "ONCA"], "limit_batches": None, "year_from": None,
                           "corpus_dir": str(corpus)},
                "input_identity": {"fingerprint": "offline-synthetic-fixture-not-a-production-run", "files": {}}}
    groups = [
        ("XC-G000001", 3, "Alpha v Beta", "DOMESTIC_CA", "CA", "DETERMINED"),
        ("XC-G000002", 2, "Gamma v Delta", "FOREIGN", "UK", "DETERMINED"),
        ("XC-G000003", 1, "Conflict case", "CONFLICT", "", "CONFLICT"),
    ]
    selected = []
    for gid, dd, name, status, country, origin_status in groups:
        for index, court in enumerate(("SCC", "ONCA")):
            selected.append({"court": court, "merge_key": gid + "-key", "merged_group_id": gid,
                             "is_primary": "true" if index == 0 else "false", "distinct_decisions_count": str(dd),
                             "case_name_modal": name, "year_printed": "1990", "kept": "true" if dd >= 2 else "false",
                             "group_foreign_status": status, "group_origin_country": country,
                             "group_origin_status": origin_status})
    edges = []
    specs = [("SCC_2000scc1", 0, "supported"), ("SCC_2000scc1", 1, "heuristic_only"),
             ("ONCA_2011onca1", 0, "supported"), ("ONCA_2011onca1", 2, "supported"),
             ("MISSING_1", 1, "supported"), ("SCC_duplicate", 0, "supported")]
    for source, group_index, support in specs:
        gid, dd, name, status, country, origin_status = groups[group_index]
        r = {k: "" for k in EDGE_FIELDS}
        r.update(source_decision=source, resolved_cited_case=gid, foreign_status=status,
                 origin_country=country, group_origin_country=country, group_origin_status=origin_status,
                 group_foreign_status=status, edge_support=support, identity_status="singleton",
                 origin_evidence_ids="fixture-origin" if country else "", mention_count="1",
                 distinct_decisions_count=str(dd), case_name_modal=name)
        if support == "heuristic_only":
            r.update(foreign_status="UNDETERMINED", origin_country="", origin_evidence_ids="", identity_status="name_candidate")
        edges.append(r)
    doc_specs = [("SCC", 0, "SCC_2000scc1", "2000 SCC 1", "2000-01-01"),
                 ("ONCA", 0, "ONCA_2011onca1", "2011 ONCA 1", "2011-02-02"),
                 ("SCC", 1, "SCC_duplicate", "duplicate", "1999-01-01"),
                 ("SCC", 2, "SCC_duplicate", "duplicate", "2001-01-01"),
                 ("SCC", 3, "SCC_2019scc1", "2019 SCC 1", "2019-04-04"),
                 ("SCC", 4, "SCC_invalid", "invalid", "bad-date")]
    documents = [dict(zip(DOCUMENT_FIELDS, (court, str(row), src, cite, "Source " + src, date,
                                          str(corpus / (court + ".parquet")))))
                 for court, row, src, cite, date in doc_specs]
    selected_path = run / "select_out" / "selected.csv.gz"
    edge_path = run / "edges" / "citation_edges.csv.gz"
    document_path = destination / "documents.csv.gz"
    write_csv(selected_path, list(selected[0]), selected)
    write_csv(edge_path, EDGE_FIELDS, edges)
    write_csv(document_path, DOCUMENT_FIELDS, documents)
    quote = "[1990] SCC 10"
    source_text = "判决😀 Alpha mentions " + quote + " in its reasons."
    offset = source_text.index(quote)
    candidate_fields = ("candidate_id", "source_decision_citation", "merge_key", "arbitration_status",
                        "corpus_row_index", "match_start_offset", "match_end_offset", "raw_string")
    candidate = dict(zip(candidate_fields, ("SCC:0:fixture", "SCC_2000scc1", "XC-G000001-key", "counted",
                                            "0", str(offset), str(offset + len(quote)), quote)))
    excluded = {**candidate, "candidate_id": "SCC:0:self", "arbitration_status": "self_citation_row"}
    write_csv(run / "merge_out" / "SCC" / "mentions_candidates.csv.gz", candidate_fields, [excluded, candidate])
    onca_candidate = {**candidate, "candidate_id": "ONCA:0:fixture", "source_decision_citation": "ONCA_2011onca1"}
    write_csv(run / "merge_out" / "ONCA" / "mentions_candidates.csv", candidate_fields, [onca_candidate])
    if with_parquet:
        pq = optional_arrow()
        import pyarrow as pa
        corpus.mkdir(parents=True, exist_ok=True)
        for court in ("SCC", "ONCA"):
            court_docs = [d for d in documents if d["court"] == court]
            table = pa.table({"citation_en": [d["citation"] for d in court_docs],
                              "name_en": [d["name"] for d in court_docs],
                              "document_date_en": [d["decision_date"] for d in court_docs],
                              "unofficial_text_en": [source_text for d in court_docs]})
            path = corpus / (court + ".parquet")
            pq.write_table(table, path, row_group_size=2)
            manifest["input_identity"]["files"]["corpus/" + court + ".parquet"] = file_hash(path)
    (run / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    db_path = destination / "fixture.db"
    if db_path.exists():
        raise ValueError("Fixture DB already exists; choose an empty output directory")
    db = sqlite3.connect(db_path)
    db.executescript(STREAM_SCHEMA)
    db.execute("CREATE TABLE runs(run_id TEXT PRIMARY KEY,source_directory TEXT,input_fingerprint TEXT,manifest_json TEXT,imported_at TEXT,status TEXT)")
    db.execute("CREATE TABLE artifacts(run_id TEXT,relative_path TEXT,sha256 TEXT,row_count INTEGER)")
    db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?)", (run.name, str(run), manifest["input_identity"]["fingerprint"], canonical(manifest), "2026-10-14T00:00:00Z", "ready"))
    for number, row in enumerate(selected, 2):
        db.execute("INSERT INTO members VALUES(?,?,?,?,?)", (run.name, number, row["court"], row["merge_key"], row["merged_group_id"]))
        if row["is_primary"] == "true":
            db.execute("INSERT INTO case_groups VALUES(?,?,?,?,?,?,?,?,?)", (run.name, row["merged_group_id"], int(row["distinct_decisions_count"]),
                row["case_name_modal"], number, row["year_printed"], int(row["kept"] == "true"), row["group_foreign_status"], row["group_origin_country"]))
    db.executemany("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)", [(run.name, *[d[k] for k in DOCUMENT_FIELDS]) for d in documents])
    db.executemany("INSERT INTO citation_edges VALUES(" + ",".join("?" * 18) + ")", [(run.name, i, *[r[k] for k in EDGE_FIELDS]) for i, r in enumerate(edges, 2)])
    for path, relative, count in ((selected_path, "select_out/selected.csv", len(selected)), (edge_path, "edges/citation_edges.csv", len(edges))):
        db.execute("INSERT INTO artifacts VALUES(?,?,?,?)", (run.name, relative, file_hash(path), count))
    db.commit()
    db.close()
    return {"db": str(db_path), "run": str(run), "documents": str(document_path), "corpus": str(corpus),
            "expected": {"citation_edges": 6, "cited_groups": 3, "origin_determined_edges": 4,
                         "origin_unknown_edges": 2, "heuristic_only_edges": 1, "foreign_edges": 1}}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True)
    p.add_argument("--with-parquet", action="store_true")
    a = p.parse_args()
    print(json.dumps(create_fixture(a.output, a.with_parquet), ensure_ascii=False, indent=2))
