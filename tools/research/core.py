"""Offline, read-only research queries. No API calls, persistent caches or SQL input."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from pipeline.corpus_fields import POLICY_EN, policy_from_manifest, projection, select_record
DEFAULT_DB = ROOT / "data" / "foundation" / "research.db"
VERSION = "research-packet-v2"
csv.field_size_limit(10**9)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def csv_path(path):
    path = Path(path)
    if path.is_file():
        return path
    compressed = Path(str(path) + ".gz")
    if compressed.is_file():
        return compressed
    raise ValueError("Missing artifact: " + str(path))


def rows(path, required=()):
    path = csv_path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, strict=True)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)) or set(required) - set(fields):
            raise ValueError("Invalid/missing CSV columns: " + str(path))
        for number, row in enumerate(reader, 2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"Malformed CSV record {number}: {path}")
            yield number, row


def optional_arrow():
    # Same local runtime as foundation; do not install/download dependencies.
    import sys
    vendor = ROOT / "data" / "foundation_runtime"
    if vendor.is_dir() and str(vendor) not in sys.path:
        sys.path.append(str(vendor))
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ValueError("Parquet access requires installed/local pyarrow; supply --documents instead") from exc
    return pq


def require_manifest(manifest):
    policy_from_manifest(manifest)
    if manifest.get("status") != "complete" or manifest.get("input_identity_verified_unchanged") is not True:
        raise ValueError("Only complete runs with verified unchanged input identity can be researched")
    if not manifest.get("input_identity", {}).get("fingerprint"):
        raise ValueError("Run has no input fingerprint")
    courts = manifest.get("params", {}).get("courts", [])
    if not courts or any(not re.fullmatch(r"[A-Z][A-Z0-9]*", c) for c in courts):
        raise ValueError("Run has no valid court scope")
    seal = manifest.get("output_identity")
    if seal:
        files = seal.get("files", {})
        expected = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        if not files or seal.get("fingerprint") != expected:
            raise ValueError("Run output seal is empty or has an invalid fingerprint")


STREAM_SCHEMA = """
CREATE TABLE case_groups(run_id TEXT,group_id TEXT,dd INTEGER,name TEXT,primary_row INTEGER,
 year_printed TEXT,kept INTEGER,foreign_status TEXT,origin_country TEXT,PRIMARY KEY(run_id,group_id));
CREATE TABLE members(run_id TEXT,row_number INTEGER,court TEXT,merge_key TEXT,merged_group_id TEXT);
CREATE INDEX member_group ON members(run_id,merged_group_id,court);
CREATE TABLE documents(run_id TEXT,court TEXT,corpus_row INTEGER,source_id TEXT,citation TEXT,
 name TEXT,decision_date TEXT,corpus_path TEXT);
CREATE TABLE citation_edges(run_id TEXT,row_number INTEGER,source_decision TEXT,resolved_cited_case TEXT,
 foreign_status TEXT,origin_country TEXT,group_origin_country TEXT,group_origin_status TEXT,
 group_foreign_status TEXT,edge_support TEXT,identity_status TEXT,origin_basis TEXT,
 origin_evidence_ids TEXT,noncore_origin_evidence TEXT,mention_count TEXT,
 distinct_decisions_count TEXT,case_name_modal TEXT,mention_detail_key TEXT,
 PRIMARY KEY(run_id,source_decision,resolved_cited_case));
"""
EDGE_FIELDS = ("source_decision", "resolved_cited_case", "foreign_status", "origin_country",
               "group_origin_country", "group_origin_status", "group_foreign_status", "edge_support",
               "identity_status", "origin_basis", "origin_evidence_ids", "noncore_origin_evidence",
               "mention_count", "distinct_decisions_count", "case_name_modal", "mention_detail_key")
DOCUMENT_FIELDS = ("court", "corpus_row", "source_id", "citation", "name", "decision_date", "corpus_path")


class ResearchSource:
    """SQLite read-only snapshot or compact in-memory projections streamed from CSV/gz."""
    def __init__(self, db, run_id, manifest, run_dir, provenance, mode):
        self.db, self.run_id, self.manifest = db, run_id, manifest
        self.run_dir = Path(run_dir).resolve() if run_dir else None
        self.provenance, self.mode = provenance, mode
        self.provenance['text_policy'] = policy_from_manifest(manifest)
        # SQLite lower() is ASCII-only. This pure connection-local UDF supports
        # native French case matching without changing DB contents or accents.
        self.db.create_function('research_casefold', 1,
            lambda value: str(value).casefold() if value is not None else None,
            deterministic=True)
        self.queries = []

    def close(self):
        self.db.close()

    def execute(self, label, sql, parameters):
        parameters = list(parameters)
        self.queries.append({"label": label, "sql": sql.strip(), "parameters": parameters})
        return [dict(r) for r in self.db.execute(sql, parameters)]

    @classmethod
    def sqlite(cls, path=DEFAULT_DB, run_id=None, run_dir=None):
        path = Path(path).resolve()
        if not path.is_file():
            raise ValueError("Database does not exist: " + str(path))
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA temp_store=MEMORY")
        db.execute("PRAGMA cache_size=-65536")
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("BEGIN")  # All exact results use one database read snapshot.
        try:
            if run_id is None:
                available = db.execute("SELECT run_id FROM runs WHERE status='ready' ORDER BY run_id").fetchall()
                if len(available) != 1:
                    raise ValueError("Choose --run-id explicitly when the database has zero or multiple ready runs")
                run_id = available[0][0]
            record = db.execute("SELECT * FROM runs WHERE run_id=? AND status='ready'", (run_id,)).fetchone()
            if record is None:
                raise ValueError("Run is not ready in this database: " + run_id)
            manifest = json.loads(record["manifest_json"])
            require_manifest(manifest)
            if manifest["input_identity"]["fingerprint"] != record["input_fingerprint"]:
                raise ValueError("Database run fingerprint disagrees with its manifest")
            directory = Path(run_dir or record["source_directory"]).resolve()
            # A moved directory is allowed only with the same recorded run identity.
            if directory.is_dir():
                on_disk = json.loads((directory / "run_manifest.json").read_text(encoding="utf-8-sig"))
                if canonical(on_disk) != canonical(manifest):
                    raise ValueError("Run directory manifest differs from the database snapshot")
            elif run_dir:
                raise ValueError("Explicit --run-dir is missing")
            artifacts = [dict(r) for r in db.execute(
                "SELECT relative_path,sha256,row_count FROM artifacts WHERE run_id=? ORDER BY relative_path", (run_id,))]
            stat = path.stat()
            provenance = {"mode": "sqlite_readonly", "db_path": str(path), "db_bytes": stat.st_size,
                          "db_mtime_ns": stat.st_mtime_ns, "db_file_hash": None,
                          "db_file_hash_note": "Large database is not rehashed or copied; imported artifact hashes and one read snapshot are recorded",
                          "imported_at": record["imported_at"], "imported_artifacts": artifacts}
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            provenance["run_sources"] = [dict(r) for r in db.execute(
                "SELECT * FROM run_sources WHERE run_id=? ORDER BY logical_path", (run_id,))] if "run_sources" in tables else []
            provenance["run_components"] = [dict(r) for r in db.execute(
                "SELECT * FROM run_components WHERE run_id=? ORDER BY component", (run_id,))] if "run_components" in tables else []
            provenance["lifecycle_metadata"] = "recorded" if provenance["run_components"] else "legacy_not_recorded"
            provenance["output_seal_verification"] = "manifest fingerprint verified; database query does not rehash all historical run output files" if manifest.get("output_identity") else "historical_outputs_unsealed"
            source = cls(db, run_id, manifest, directory, provenance, "sqlite_readonly")
            source.validate()
            return source
        except Exception:
            db.close()
            raise

    @classmethod
    def stream(cls, run_dir, corpus_dir=None, documents=None):
        directory = Path(run_dir).resolve()
        raw_manifest = (directory / "run_manifest.json").read_text(encoding="utf-8-sig")
        manifest = json.loads(raw_manifest)
        require_manifest(manifest)
        run_id = directory.name
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA temp_store=MEMORY")
        db.executescript(STREAM_SCHEMA)
        provenance = {"mode": "csv_gzip_stream_to_memory", "run_manifest_file_sha256": file_hash(directory / "run_manifest.json"),
                      "persistent_cache_bytes": 0, "artifacts": [],
                      "document_denominator_scope": "supplied document metadata / recorded corpus; not inferred from printed citations"}
        source = cls(db, run_id, manifest, directory, provenance, "csv_gzip_stream_to_memory")
        try:
            selected = csv_path(directory / "select_out" / "selected.csv")
            batch, member_batch = [], []
            required = ("court", "merge_key", "merged_group_id", "is_primary", "distinct_decisions_count",
                        "case_name_modal", "year_printed", "kept", "group_foreign_status", "group_origin_country")
            for number, r in rows(selected, required):
                if r["is_primary"] not in ("true", "false") or r["kept"] not in ("true", "false"):
                    raise ValueError("Invalid selected boolean")
                member_batch.append((run_id, number, r["court"], r["merge_key"], r["merged_group_id"]))
                if r["is_primary"] == "true":
                    batch.append((run_id, r["merged_group_id"], int(r["distinct_decisions_count"]), r["case_name_modal"],
                                  number, r["year_printed"], int(r["kept"] == "true"), r["group_foreign_status"], r["group_origin_country"]))
                if len(member_batch) >= 1000:
                    db.executemany("INSERT INTO members VALUES(?,?,?,?,?)", member_batch)
                    db.executemany("INSERT INTO case_groups VALUES(?,?,?,?,?,?,?,?,?)", batch)
                    member_batch, batch = [], []
            db.executemany("INSERT INTO members VALUES(?,?,?,?,?)", member_batch)
            db.executemany("INSERT INTO case_groups VALUES(?,?,?,?,?,?,?,?,?)", batch)
            edge_path = csv_path(directory / "edges" / "citation_edges.csv")
            batch = []
            for number, r in rows(edge_path, EDGE_FIELDS):
                batch.append((run_id, number, *[r[k] for k in EDGE_FIELDS]))
                if len(batch) >= 1000:
                    db.executemany("INSERT INTO citation_edges VALUES(" + ",".join("?" * 18) + ")", batch)
                    batch = []
            db.executemany("INSERT INTO citation_edges VALUES(" + ",".join("?" * 18) + ")", batch)
            for path in (selected, edge_path):
                source.record_artifact(path, file_hash(path), "current_file_bytes")
            if documents:
                doc_path = csv_path(documents)
                for _, r in rows(doc_path, DOCUMENT_FIELDS):
                    db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)", (run_id, *[r[k] for k in DOCUMENT_FIELDS]))
                source.record_artifact(doc_path, file_hash(doc_path), "caller_supplied_metadata_unverified_against_corpus")
                provenance["document_metadata_verification"] = "caller_supplied; reproducible hash, not an independently verified corpus snapshot"
            else:
                pq = optional_arrow()
                corpus_dir = Path(corpus_dir or manifest["params"].get("corpus_dir") or ROOT / "corpus")
                for court in manifest["params"]["courts"]:
                    path = corpus_dir / (court + ".parquet")
                    expected = manifest["input_identity"].get("files", {}).get("corpus/" + court + ".parquet")
                    actual = file_hash(path)
                    if not expected or expected != actual:
                        raise ValueError("Corpus snapshot hash missing or different: " + str(path))
                    source.record_artifact(path, actual, "matches_recorded_input_identity")
                    offset = 0
                    pf = pq.ParquetFile(path)
                    policy = policy_from_manifest(manifest)
                    columns = projection(pf.schema_arrow.names, include_text=False)
                    if policy == POLICY_EN:
                        columns = [field for field in columns if field.endswith('_en')]
                    for b in pf.iter_batches(batch_size=500, columns=columns):
                        values = []
                        for i, r in enumerate(b.to_pylist(), offset):
                            selected_record = select_record(r, policy)
                            citation = selected_record['citation']
                            key = re.sub("[^A-Za-z0-9]", "", citation).lower()
                            values.append((run_id, court, i, court + "_" + key, citation,
                                           selected_record['name'], str(selected_record['date'] or ""), str(path.resolve())))
                        db.executemany("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)", values)
                        offset += len(values)
                provenance["document_metadata_verification"] = "corpus hashes match recorded input identity"
            db.commit()
            db.execute("PRAGMA query_only=ON")
            source.validate()
            return source
        except Exception:
            db.close()
            raise

    def record_artifact(self, path, sha, verification):
        path = Path(path).resolve()
        seal = self.manifest.get("output_identity")
        if seal and self.run_dir and self.run_dir in path.parents:
            relative = path.relative_to(self.run_dir).as_posix()
            expected = seal["files"].get(relative)
            if not expected or sha != expected:
                raise ValueError("Streamed artifact is missing/different in the recorded output seal: " + relative)
            verification += "; matches_recorded_output_seal"
        self.provenance.setdefault("artifacts", []).append({"path": str(Path(path).resolve()),
            "bytes": Path(path).stat().st_size, "sha256": sha, "verification": verification})

    def validate(self):
        """Fail closed on structural defects that would inflate joins/counts."""
        tests = {
            "duplicate_edges": "SELECT COUNT(*) n FROM (SELECT source_decision,resolved_cited_case FROM citation_edges WHERE run_id=? GROUP BY 1,2 HAVING COUNT(*)<>1)",
            "missing_groups": "SELECT COUNT(*) n FROM citation_edges e WHERE e.run_id=? AND NOT EXISTS(SELECT 1 FROM case_groups g WHERE g.run_id=e.run_id AND g.group_id=e.resolved_cited_case)",
            "invalid_edge_contract": "SELECT COUNT(*) n FROM citation_edges WHERE run_id=? AND (edge_support NOT IN ('supported','heuristic_only') OR foreign_status NOT IN ('FOREIGN','DOMESTIC_CA','UNDETERMINED','CONFLICT') OR (edge_support='heuristic_only' AND (foreign_status<>'UNDETERMINED' OR origin_country<>'') AND (origin_basis NOT LIKE 'member:%' OR origin_evidence_ids='')) OR (foreign_status='DOMESTIC_CA' AND origin_country='') OR (foreign_status='FOREIGN' AND origin_country='' AND origin_basis NOT LIKE '%not_domestic%') OR (foreign_status='FOREIGN' AND origin_country='CA') OR (foreign_status='DOMESTIC_CA' AND origin_country<>'CA') OR (foreign_status IN ('UNDETERMINED','CONFLICT') AND origin_country<>''))",
            "invalid_mention_count": "SELECT COUNT(*) n FROM citation_edges WHERE run_id=? AND (mention_count='' OR mention_count GLOB '*[^0-9]*')",
        }
        self.validation = {name: self.db.execute(sql, (self.run_id,)).fetchone()[0] for name, sql in tests.items()}
        if any(self.validation.values()):
            raise ValueError("Research input violates counting contracts: " + canonical(self.validation))

    def identity(self):
        return {"run_id": self.run_id, "input_fingerprint": self.manifest["input_identity"]["fingerprint"],
                "manifest_sha256_canonical_json": sha_text(canonical(self.manifest)),
                "manifest": self.manifest, "source_directory": str(self.run_dir) if self.run_dir else None,
                "source": self.provenance, "structural_validation": self.validation}


@dataclass(frozen=True)
class Filters:
    court: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    origin: str | None = None
    min_dd: int = 0
    kept_only: bool = False
    group_id: str | None = None

    def validate(self, source):
        if self.court and self.court not in source.manifest["params"]["courts"]:
            raise ValueError("Court is outside this run: " + self.court)
        if self.origin not in (None, "FOREIGN", "DOMESTIC_CA", "UNDETERMINED", "CONFLICT"):
            raise ValueError("Invalid origin filter")
        if self.min_dd < 0 or any(y is not None and not 1000 <= y <= 9999 for y in (self.year_from, self.year_to)):
            raise ValueError("Invalid year or DD filter")
        if self.year_from and self.year_to and self.year_from > self.year_to:
            raise ValueError("year-from is after year-to")
        if self.group_id and not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", self.group_id):
            raise ValueError("Invalid group ID")


# Document dates, never the cited judgment's reporter/printed year, define time.
# Duplicate source IDs collapse once; conflicting/invalid metadata goes to an unknown bucket.
DOC_CTE = """WITH doc_parts AS (
 SELECT source_id,court,substr(decision_date,1,10) date_token,
 CAST(substr(decision_date,1,4) AS INTEGER) y,CAST(substr(decision_date,6,2) AS INTEGER) m,
 CAST(substr(decision_date,9,2) AS INTEGER) day,
 CASE WHEN trim(citation)<>'' AND trim(source_id)<>'' AND source_id<>court||'_'
 THEN 1 ELSE 0 END valid_source_id,trim(citation)='' empty_citation,trim(decision_date)='' empty_date
 FROM documents WHERE run_id=?
), doc_years AS (
 SELECT source_id,court,valid_source_id,empty_citation,empty_date,
 CASE WHEN date_token GLOB '[1-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
 AND m BETWEEN 1 AND 12 AND day BETWEEN 1 AND CASE
 WHEN m=2 THEN CASE WHEN y%4=0 AND (y%100<>0 OR y%400=0) THEN 29 ELSE 28 END
 WHEN m IN (4,6,9,11) THEN 30 ELSE 31 END THEN y END year
 FROM doc_parts
), d AS (
 SELECT source_id,CASE WHEN COUNT(DISTINCT court)=1 THEN MIN(court) ELSE 'UNKNOWN' END court,
 CASE WHEN COUNT(year)=COUNT(*) AND COUNT(DISTINCT year)=1 THEN MIN(year) END year,
 COUNT(*) corpus_rows,MIN(valid_source_id) valid_source_id,
 SUM(empty_citation) empty_citation_rows,SUM(empty_date) empty_date_rows
 FROM doc_years GROUP BY source_id
)"""


def base_query(source, filters):
    filters.validate(source)
    where, parameters = ["e.run_id=?", "g.dd>=?"], [source.run_id, source.run_id, filters.min_dd]
    for sql, value in (("d.court=?", filters.court), ("d.year>=?", filters.year_from),
                       ("d.year<=?", filters.year_to), ("e.foreign_status=?", filters.origin),
                       ("e.resolved_cited_case=?", filters.group_id)):
        if value is not None:
            where.append(sql)
            parameters.append(value)
    if filters.kept_only:
        where.append("g.kept=1")
    sql = DOC_CTE + """, b AS (
 SELECT e.*,g.name group_name,g.dd global_dd,g.kept,
 COALESCE(d.court,'UNKNOWN') source_court,d.year source_year,
 CASE WHEN d.year IS NOT NULL THEN CAST(d.year/10 AS INTEGER)*10 END decade,
 CASE WHEN e.foreign_status IN ('FOREIGN','DOMESTIC_CA')
 AND e.origin_country<>'' THEN 1 ELSE 0 END origin_known,
 CASE WHEN e.group_origin_status='DETERMINED' AND e.group_origin_country<>'' THEN 1 ELSE 0 END group_origin_known,
 CASE WHEN d.source_id IS NULL THEN 1 ELSE 0 END missing_document_metadata
 FROM citation_edges e NOT INDEXED CROSS JOIN case_groups g ON g.run_id=e.run_id AND g.group_id=e.resolved_cited_case
 LEFT JOIN d ON d.source_id=e.source_decision AND d.valid_source_id=1 WHERE """ + " AND ".join(where) + ")\n"
    return sql, parameters


AGGREGATE = """COUNT(*) citation_edges,COUNT(DISTINCT source_decision) citing_source_ids,
 COUNT(DISTINCT resolved_cited_case) cited_groups,COALESCE(SUM(CAST(mention_count AS INTEGER)),0) printed_mentions,
 COALESCE(SUM(origin_known),0) origin_determined_edges,COALESCE(SUM(1-origin_known),0) origin_unknown_edges,
 COALESCE(SUM(foreign_status='FOREIGN'),0) foreign_edges,
 COALESCE(SUM(foreign_status='DOMESTIC_CA'),0) domestic_edges,
 COALESCE(SUM(foreign_status='CONFLICT'),0) origin_conflict_edges,
 COALESCE(SUM(edge_support='heuristic_only'),0) heuristic_only_edges,
 COUNT(DISTINCT CASE WHEN group_origin_known=1 THEN resolved_cited_case END) group_origin_determined,
 COALESCE(SUM(missing_document_metadata),0) edges_missing_document_metadata,
 COALESCE(SUM(source_year IS NULL),0) edges_unknown_source_year"""


def add_rates(row):
    n = row["citation_edges"]
    row["origin_coverage"] = row["origin_determined_edges"] / n if n else None
    row["origin_unknown_rate"] = row["origin_unknown_edges"] / n if n else None
    row["heuristic_only_rate"] = row["heuristic_only_edges"] / n if n else None
    row["foreign_share_all_edges"] = row["foreign_edges"] / n if n else None
    known = row["origin_determined_edges"]
    row["foreign_share_determined_edges"] = row["foreign_edges"] / known if known else None
    groups = row["cited_groups"]
    row["group_origin_coverage"] = row["group_origin_determined"] / groups if groups else None
    return row


def document_stats(source, filters):
    conditions, parameters = [], [source.run_id]
    for sql, value in (("court=?", filters.court), ("year>=?", filters.year_from), ("year<=?", filters.year_to)):
        if value is not None:
            conditions.append(sql)
            parameters.append(value)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    return source.execute("document_denominators", DOC_CTE + """
 SELECT court source_court,CASE WHEN year IS NOT NULL THEN CAST(year/10 AS INTEGER)*10 END decade,
 SUM(valid_source_id) corpus_source_ids,SUM(corpus_rows) corpus_document_rows,
 COUNT(*) corpus_source_ids_including_placeholders,
 SUM(valid_source_id=1 AND year IS NULL) source_ids_unknown_year,
 SUM(valid_source_id=1 AND corpus_rows>1) duplicate_source_ids,
 SUM(CASE WHEN valid_source_id=0 THEN corpus_rows ELSE 0 END) invalid_source_id_document_rows,
 SUM(empty_citation_rows) empty_citation_document_rows,SUM(empty_date_rows) empty_date_document_rows
 FROM d""" + where + " GROUP BY 1,2 ORDER BY 1,2", parameters)


def exact_result(source, intent, filters, top=10):
    if intent not in ("count", "court_decade", "ranking", "case_citations"):
        raise ValueError("Unsupported query intent")
    if not 1 <= top <= 100:
        raise ValueError("top must be between 1 and 100")
    if intent == "case_citations" and not filters.group_id:
        raise ValueError("case_citations requires an explicit group ID; names can identify multiple judgments")
    base, parameters = base_query(source, filters)
    summary = add_rates(source.execute("full_table_summary", base + "SELECT " + AGGREGATE + " FROM b", parameters)[0])
    # A FOREIGN-only result has 100% known origin by construction. Keep the
    # same court/date/DD/group scope visible before applying that origin filter.
    context_filters = replace(filters, origin=None)
    if filters.origin is None:
        context_summary = dict(summary)
    else:
        context_base, context_parameters = base_query(source, context_filters)
        context_summary = add_rates(source.execute("origin_scope_before_origin_filter",
            context_base + "SELECT " + AGGREGATE + " FROM b", context_parameters)[0])
    origin_context = {"applied_origin_filter": filters.origin,
                      "filters_before_origin_filter": asdict(context_filters),
                      "summary_before_origin_filter": context_summary,
                      "meaning": "Only origin is removed; court/date/DD/kept/group constraints remain. Unknown origin is not foreign and is not extrapolated."}
    doc_rows = document_stats(source, filters)
    metadata_diagnostics = source.execute("full_corpus_metadata_diagnostics", DOC_CTE + """
 SELECT COALESCE(SUM(corpus_rows),0) corpus_document_rows,
 COALESCE(SUM(empty_citation_rows),0) empty_citation_document_rows,
 COALESCE(SUM(empty_date_rows),0) empty_date_document_rows,
 COALESCE(SUM(CASE WHEN valid_source_id=0 THEN corpus_rows ELSE 0 END),0) invalid_source_id_document_rows,
 COALESCE(SUM(valid_source_id),0) valid_corpus_source_ids FROM d""", [source.run_id])[0]
    rows_out = []
    if intent == "court_decade":
        by_edge = source.execute("court_decade_full_table", base + "SELECT source_court,decade," + AGGREGATE +
                                 " FROM b GROUP BY 1,2 ORDER BY 1,2", parameters)
        edges = {(r["source_court"], r["decade"]): add_rates(r) for r in by_edge}
        docs = {(r["source_court"], r["decade"]): r for r in doc_rows}
        for key in sorted(set(edges) | set(docs), key=lambda k: (k[0], k[1] if k[1] is not None else -1)):
            row = edges.get(key)
            if row is None:
                row = {"source_court": key[0], "decade": key[1], **{k: 0 for k in summary if not k.endswith(("rate", "coverage")) and not k.startswith("foreign_share")}}
                add_rates(row)
            row.update(docs.get(key, {"corpus_source_ids": 0, "corpus_document_rows": 0,
                        "corpus_source_ids_including_placeholders": 0, "source_ids_unknown_year": 0,
                        "duplicate_source_ids": 0, "invalid_source_id_document_rows": 0,
                        "empty_citation_document_rows": 0, "empty_date_document_rows": 0}))
            row["citing_source_coverage"] = row["citing_source_ids"] / row["corpus_source_ids"] if row["corpus_source_ids"] else None
            rows_out.append(row)
    elif intent == "ranking":
        rows_out = source.execute("ranking_full_table_then_limit", base + """
 SELECT resolved_cited_case group_id,group_name,global_dd,COUNT(*) filtered_dd,
 SUM(origin_known) origin_determined_edges,SUM(edge_support='heuristic_only') heuristic_only_edges,
 MAX(group_origin_country) group_origin_country,MAX(group_origin_status) group_origin_status,
 MAX(group_foreign_status) group_foreign_status
 FROM b GROUP BY resolved_cited_case,group_name,global_dd
 ORDER BY filtered_dd DESC,group_id LIMIT ?""", [*parameters, top])
    elif intent == "case_citations":
        group = source.execute("explicit_case_identity", "SELECT group_id,name,dd,kept,foreign_status,origin_country FROM case_groups WHERE run_id=? AND group_id=?", [source.run_id, filters.group_id])
        if not group:
            raise ValueError("Group ID is not present in this run: " + filters.group_id)
        rows_out = source.execute("case_citing_sources_preview", base + """
 SELECT source_decision,source_court,source_year,edge_support,identity_status,foreign_status,origin_country,mention_count
 FROM b ORDER BY source_year DESC,source_decision LIMIT ?""", [*parameters, top])
        return {"summary": summary, "rows": rows_out, "case_identity": group,
                "preview_limit": top, "preview_truncated": summary["citation_edges"] > len(rows_out),
                "origin_coverage_context": origin_context,
                "document_denominators": doc_rows, "full_corpus_metadata_diagnostics": metadata_diagnostics}
    return {"summary": summary, "rows": rows_out, "document_denominators": doc_rows,
            "origin_coverage_context": origin_context,
            "full_corpus_metadata_diagnostics": metadata_diagnostics,
            "ranking_limit": top if intent == "ranking" else None}


def make_lookup_packet(source, name_contains, top=10, language="zh"):
    """Discover separate group candidates, never resolve identity by case name."""
    query = name_contains.strip()
    if not query or len(query) > 200:
        raise ValueError("Supply a nonempty case-name fragment of at most 200 characters")
    if not 1 <= top <= 100:
        raise ValueError("top must be between 1 and 100")
    source.queries = []
    # instr treats %, _ and SQL-looking text literally; no wildcard or SQL input.
    where = " FROM case_groups WHERE run_id=? AND instr(research_casefold(name),research_casefold(?))>0"
    parameters = [source.run_id, query]
    count = source.execute("group_name_literal_match_count",
        "SELECT COUNT(*) matching_groups" + where, parameters)[0]["matching_groups"]
    candidates = source.execute("group_name_literal_candidates",
        "SELECT group_id,name,dd global_dd,year_printed,kept,foreign_status group_foreign_status,origin_country group_origin_country" +
        where + " ORDER BY dd DESC,group_id LIMIT ?", [*parameters, top])
    for row in candidates:
        keys = source.execute("candidate_member_keys_preview",
            "SELECT DISTINCT court,merge_key FROM members WHERE run_id=? AND merged_group_id=? ORDER BY court,merge_key LIMIT 6",
            [source.run_id, row["group_id"]])
        row["member_key_preview"] = keys[:5]
        row["member_key_preview_truncated"] = len(keys) > 5
        row['review_arguments'] = (["ask", "--db", source.provenance['db_path'],
            "--run-id", source.run_id, "--intent", "case_citations", "--group-id", row['group_id'],
            "--evidence-limit", "1", "--with-text"] if source.mode == 'sqlite_readonly' else None)
    result = {"matching_groups": count, "rows": candidates, "preview_limit": top,
              "preview_truncated": count > len(candidates),
              "match_mode": "literal substring after Python Unicode str.casefold; accents preserved, no deaccenting or identity inference",
              "casefold_unicode_version": unicodedata.unidata_version}
    if language == "en":
        answer = (f"Run {source.run_id}: {count} case-name candidate groups; showing {len(candidates)}. "
                  "A shared name does not establish the same judgment. " +
                  ("Use a candidate's review_arguments against this exact DB/run; group IDs cannot be reused across active-run changes."
                   if source.mode == 'sqlite_readonly' else
                   "Reuse the same stream/corpus/documents inputs with ask --intent case_citations --group-id ID --with-text; IDs belong to this exact run."))
    else:
        answer = (f"运行 {source.run_id}：案名片段匹配 {count} 个候选身份组，展示 {len(candidates)} 个。"
                  "同名不证明是同一判决；" +
                  ("请选择候选行的 review_arguments，在同一 DB/run 中复核引用，不能把 group_id 直接换到新 active run。"
                   if source.mode == 'sqlite_readonly' else
                   "请沿用相同 stream/corpus/documents 输入，以 ask --intent case_citations --group-id ID --with-text 复核；ID仅属于此运行。"))
    packet = {"schema_version": VERSION, "status": "supported", "question": name_contains,
              "intent": "group_lookup", "question_interpretation": "literal_group_discovery_not_identity_resolution",
              "analysis_tool_identity": {"core.py_sha256": file_hash(Path(__file__)),
                  "research.py_sha256": file_hash(Path(__file__).with_name("research.py"))},
              "parameters": {"name_contains": query, "top": top, "language": language,
                  "text_policy": policy_from_manifest(source.manifest)},
              "run_identity": source.identity(), "query_plan": source.queries, "exact_results": result,
              "review_scope": {"run_id": source.run_id,
                  "input_fingerprint": source.manifest['input_identity']['fingerprint'],
                  "stream_note": "Streamed lookup must reuse the same --stream-run and corpus/documents inputs; no DB command is invented for it." if source.mode != 'sqlite_readonly' else None},
              "answer": answer, "evidence": [], "capabilities": CAPABILITIES,
              "warnings": ["Name lookup searches recorded modal group names, not every alias or original judgment text. Empty names are not searchable. Printed year is not a verified judgment date; group origin is not edge-level origin. Member keys are a bounded structured preview, not original citation quotes."],
              "storage": {"copies_of_corpus_or_database": 0, "persistent_query_cache_bytes": 0}}
    packet["packet_sha256"] = sha_text(canonical(packet))
    return packet


def evidence_edges(source, filters, intent, result, limit):
    if not 0 <= limit <= 10:
        raise ValueError("evidence-limit must be between 0 and 10")
    if not limit:
        return []
    base, parameters = base_query(source, filters)
    if intent == "ranking" and result["rows"]:
        ids = [r["group_id"] for r in result["rows"][:limit]]
        # One source per ranked group, rather than letting one large group consume the sample.
        return source.execute("deterministic_evidence_sample", base + """
 SELECT * FROM b WHERE (resolved_cited_case,source_decision) IN (
 SELECT resolved_cited_case,MIN(source_decision) FROM b WHERE resolved_cited_case IN (""" +
            ",".join("?" for _ in ids) + ") GROUP BY resolved_cited_case) ORDER BY resolved_cited_case", [*parameters, *ids])
    return source.execute("deterministic_evidence_sample", base + "SELECT * FROM b ORDER BY source_decision,resolved_cited_case LIMIT ?", [*parameters, limit])


def evidence_packet(source, edge_rows, with_text=False, corpus_dir=None):
    evidence, desired = [], {}
    policy = policy_from_manifest(source.manifest)
    for edge in edge_rows:
        document_rows = [dict(r) for r in source.db.execute(
            "SELECT court,corpus_row,source_id,citation,name,decision_date,corpus_path FROM documents WHERE run_id=? AND source_id=? ORDER BY court,corpus_row",
            (source.run_id, edge["source_decision"]))]
        item = {"source_decision": edge["source_decision"], "cited_group_id": edge["resolved_cited_case"],
                "edge_support": edge["edge_support"], "identity_status": edge["identity_status"],
                "foreign_status": edge["foreign_status"], "origin_country": edge["origin_country"],
                "origin_evidence_ids": edge["origin_evidence_ids"], "edge_record_sha256": sha_text(canonical(edge)),
                "source_documents": document_rows, "candidate": None, "span": None, "quote": None,
                "quote_sha256": None, "status": "candidate_not_found", "limitations": []}
        item['field_selection'] = {'policy': policy, 'citation_field': None, 'name_field': None,
                                  'date_field': None, 'text_field': None, 'language': None,
                                  'verification': 'not_read_from_original_corpus'}
        evidence.append(item)
        court = edge["source_court"]
        if court == "UNKNOWN":
            item["status"] = "document_metadata_missing_or_conflicting"
            continue
        keys = {r[0] for r in source.db.execute("SELECT merge_key FROM members WHERE run_id=? AND merged_group_id=? AND court=?",
                                               (source.run_id, edge["resolved_cited_case"], court))}
        indexed_locator(source, item, document_rows)
        desired[(court, edge["source_decision"], edge["resolved_cited_case"])] = (item, keys)
    # Stream existing ledgers; do not index or materialize them on disk.
    for court in sorted({k[0] for k in desired}):
        path = source.run_dir / "merge_out" / court / "mentions_candidates.csv" if source.run_dir else None
        if path is None:
            continue
        try:
            actual_path = csv_path(path)
        except ValueError:
            for key, (item, _) in desired.items():
                if key[0] == court:
                    item["status"] = "candidate_ledger_missing"
            continue
        pending = {key: value for key, value in desired.items() if key[0] == court}
        required = ("source_decision_citation", "merge_key", "arbitration_status", "candidate_id",
                    "corpus_row_index", "match_start_offset", "match_end_offset", "raw_string")
        for record, candidate in rows(actual_path, required):
            if candidate["arbitration_status"] != "counted":
                continue
            found = []
            for key, (item, keys) in pending.items():
                if candidate["source_decision_citation"] != key[1] or candidate["merge_key"] not in keys:
                    continue
                indexed = item.get("indexed_evidence_locator")
                if indexed and record != indexed.get("mention_record"):
                    continue
                start, end, corpus_row = [int(candidate[k]) for k in ("match_start_offset", "match_end_offset", "corpus_row_index")]
                if start < 0 or end <= start or corpus_row < 0:
                    raise ValueError("Invalid candidate offsets")
                if indexed and (start, end, corpus_row) != (indexed["match_start"], indexed["match_end"], indexed["corpus_row"]):
                    item["limitations"].append("Indexed evidence and current candidate locator disagree; refusing this evidence record")
                    item["status"] = "indexed_candidate_locator_mismatch"
                    found.append(key)
                    continue
                item["candidate"] = {"candidate_id": candidate["candidate_id"], "merge_key": candidate["merge_key"],
                    "raw_string": candidate["raw_string"], "ledger_path": str(actual_path), "csv_record_number": record,
                    "row_sha256": sha_text(canonical(candidate)), "arbitration_status": "counted"}
                item["span"] = {"court": court, "corpus_row": corpus_row, "start": start, "end": end,
                                "text_field": None, "language": None,
                                "coordinate_system": "zero-based Python Unicode code points, half-open; manifest-policy-selected text field not yet verified"}
                item["quote"] = candidate["raw_string"]
                item["quote_sha256"] = sha_text(candidate["raw_string"])
                item["status"] = "candidate_span_located_corpus_not_read"
                item["limitations"].append("Quote is the counted candidate ledger text; current corpus bytes have not yet been verified")
                found.append(key)
            for key in found:
                pending.pop(key)
            if not pending:
                break
        for key, (item, _) in pending.items():
            item["limitations"].append("No eligible counted candidate was found; no span or source quote is invented")
    if with_text:
        enrich_corpus(source, evidence, corpus_dir)
    return evidence


def indexed_locator(source, item, documents):
    """Use normalized offset provenance from a ready index; old indexes remain explicit."""
    components = {r["component"]: r for r in source.provenance.get("run_components", [])}
    if not components or components.get("edges", {}).get("status") != "ready":
        return
    fields = {r["name"] for r in source.db.execute("PRAGMA table_info(edge_passages)")}
    if "evidence_json" not in fields:
        return
    record = source.db.execute("SELECT passage,evidence_json FROM edge_passages WHERE run_id=? AND source_decision=? AND resolved_cited_case=?",
                               (source.run_id, item["source_decision"], item["cited_group_id"])).fetchone()
    if record is None:
        return
    try:
        locator = json.loads(record["evidence_json"])
        for key in ("corpus_row", "match_start", "match_end", "window_start", "window_end", "mention_record"):
            if not isinstance(locator.get(key), int) or locator[key] < 0:
                return
        if not any(d["court"] == locator.get("court") and int(d["corpus_row"]) == locator["corpus_row"] for d in documents):
            item["limitations"].append("Indexed evidence does not agree with imported source row metadata")
            return
        sources = {r["logical_path"]: r for r in source.provenance.get("run_sources", [])}
        for key in ("corpus", "mentions"):
            logical = locator.get(key, {}).get("logical_path")
            if logical in sources:
                locator[key] = {**locator[key], **sources[logical]}
        item["indexed_evidence_locator"] = locator
        item['field_selection'] = {'policy': policy_from_manifest(source.manifest),
                                  **{k: locator.get('corpus', {}).get(k) for k in
                                     ('citation_field', 'name_field', 'date_field', 'text_field', 'language')},
                                  'verification': 'indexed_claim_not_original_corpus_verified'}
        item["indexed_passage"] = record["passage"]
        item["indexed_passage_sha256"] = sha_text(record["passage"])
        item["indexed_passage_note"] = "Index whitespace-normalized passage; original quote/offset verification is separate"
        item["evidence_generation"] = components["edges"]
    except (TypeError, ValueError, KeyError):
        item["limitations"].append("Indexed provenance cannot be parsed; fallback to eligible ledger candidates")


def enrich_corpus(source, evidence, corpus_dir=None):
    by_court = defaultdict(list)
    policy = policy_from_manifest(source.manifest)
    for item in evidence:
        if item["span"]:
            # Reverification never retains a prior window/field success after a failure.
            item.pop('source_text_sha256', None)
            item.pop('quote_span', None)
            item['quote'] = item['candidate']['raw_string']
            item['quote_sha256'] = sha_text(item['quote'])
            item['field_selection'] = {'policy': policy,
                **{key: None for key in ('citation_field', 'name_field', 'date_field', 'text_field', 'language')},
                'verification': 'not_read_from_original_corpus'}
            item['span'].update(text_field=None, language=None,
                coordinate_system='zero-based Python Unicode code points, half-open; manifest-policy-selected text field not yet verified')
            item['status'] = 'candidate_span_located_corpus_not_read'
            by_court[item["span"]["court"]].append(item)
    for court, items in by_court.items():
        directory = Path(corpus_dir or source.manifest["params"].get("corpus_dir") or ROOT / "corpus")
        path = directory / (court + ".parquet")
        indexed_paths = {i.get("indexed_evidence_locator", {}).get("corpus", {}).get("actual_path") for i in items}
        indexed_paths.discard(None)
        if not corpus_dir and len(indexed_paths) == 1:
            path = Path(next(iter(indexed_paths)))
        expected = source.manifest["input_identity"].get("files", {}).get("corpus/" + court + ".parquet")
        if not path.is_file():
            for item in items:
                item["status"] = "corpus_missing"
            continue
        before = path.stat()
        actual = file_hash(path)
        after = path.stat()
        stable = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
        for item in items:
            item["corpus_verification"] = {"path": str(path.resolve()), "expected_sha256": expected,
                                           "actual_sha256": actual, "matches_run": bool(stable and expected and expected == actual)}
        if not stable or not expected or actual != expected:
            for item in items:
                item["status"] = "corpus_hash_mismatch_or_unrecorded"
                item["limitations"].append("Refused to extract an original-text window from a different/unrecorded corpus")
            continue
        try:
            pq = optional_arrow()
        except ValueError as exc:
            for item in items:
                item["status"] = "text_reader_unavailable"
                item["limitations"].append(str(exc))
            continue
        # Read only necessary row groups and columns, never keep a whole court's texts.
        pf = pq.ParquetFile(path)
        positions, offset = {}, 0
        for index in range(pf.metadata.num_row_groups):
            size = pf.metadata.row_group(index).num_rows
            for item in items:
                row = item["span"]["corpus_row"]
                if offset <= row < offset + size:
                    positions.setdefault(index, []).append((item, row - offset))
            offset += size
        policy = policy_from_manifest(source.manifest)
        columns = projection(pf.schema_arrow.names, include_text=True)
        if policy == POLICY_EN:
            columns = [field for field in columns if field.endswith('_en')]
        for index, targets in positions.items():
            pending = defaultdict(list)
            for item, local_row in targets:
                pending[local_row].append(item)
            offset = 0
            # A corpus can have one large row group; keep only a small batch.
            for batch in pf.iter_batches(batch_size=100, row_groups=[index], columns=columns):
                for local, record in enumerate(batch.to_pylist(), offset):
                    for item in pending.pop(local, []):
                        verify_original_record(source, item, court, record, policy)
                offset += batch.num_rows
                if not pending:
                    break
        finished = path.stat()
        if (finished.st_size, finished.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
            for item in items:
                item["status"] = "corpus_changed_during_verification"
                item["quote"] = item["candidate"]["raw_string"]
                item["quote_sha256"] = sha_text(item["quote"])
                item.pop("source_text_sha256", None)
                item.pop("quote_span", None)
                item['field_selection']['verification'] = 'corpus_changed_not_verified'
                item["corpus_verification"]["matches_run"] = False
                item["limitations"] = ["Corpus changed during verification; discarded original-text window"]
        for item in items:
            if item["status"] == "candidate_span_located_corpus_not_read":
                item["status"] = "corpus_row_out_of_range"


def verify_original_record(source, item, court, record, policy):
    selected = select_record(record, policy)
    text, citation = selected['text'], selected['citation']
    source_id = court + "_" + re.sub("[^A-Za-z0-9]", "", citation).lower()
    start, end = item["span"]["start"], item["span"]["end"]
    # Ledger raw_string folds whitespace only; span/window/hash always refer to
    # the unmodified original text, including line breaks and NBSP characters.
    if (source_id != item["source_decision"] or not 0 <= start < end <= len(text)
            or re.sub(r'\s+', ' ', text[start:end]).strip() != item["candidate"]["raw_string"]):
        item["status"] = "source_or_span_text_mismatch"
        return
    declared = item.get('indexed_evidence_locator', {}).get('corpus', {})
    if any(declared.get(k) and declared[k] != selected[k] for k in
           ('citation_field', 'name_field', 'date_field', 'text_field', 'language')):
        item['status'] = 'indexed_field_selection_mismatch'
        return
    lo, hi = max(0, start - 160), min(len(text), end + 160)
    item["source_text_sha256"] = sha_text(text)
    item['field_selection'] = {'policy': policy,
        **{key: selected[key] for key in ('citation_field', 'name_field', 'date_field', 'text_field', 'language')},
        'verification': 'original_corpus_verified',
        'field_values_sha256': {key: sha_text(str(selected[key] or '')) for key in ('citation', 'name', 'date')},
        'metadata_hash_encoding': "SHA256 UTF-8 str(selected value or '')"}
    item['span'].update(text_field=selected['text_field'], language=selected['language'],
        coordinate_system='zero-based Python Unicode code points, half-open, '+selected['text_field'])
    item["quote"], item["quote_sha256"] = text[lo:hi], sha_text(text[lo:hi])
    item["quote_span"] = {"start": lo, "end": hi, 'text_field': selected['text_field'], 'language': selected['language']}
    item["status"] = "original_text_verified"
    item["limitations"] = []


CAPABILITIES = {
    "answer_mode": "offline_templates",
    "supported_intents": ["count", "court_decade", "ranking", "case_citations", "group_lookup"],
    "unsupported": ["legal advice", "why a judgment followed/distinguished another", "holdings or legal reasoning synthesis",
                    "automatic case-name identity resolution", "unrestricted natural language / arbitrary SQL", "model-generated answers"],
    "counting_meaning": "An edge means a source judgment mentions a cited judgment identity group. It does not mean followed, relied on, agreed with, or binding authority.",
    "coverage_meaning": "Origin coverage uses each edge's country assessment independently of identity confidence. Member country evidence can determine a heuristic identity edge's country; group-only inheritance requires identity support. Determined-only country shares cannot be extrapolated to unknown origins.",
    "date_meaning": "Source judgment date chosen under the recorded corpus text policy; printed citation years are not used as judgment dates.",
    "document_denominator_meaning": "Imported/supplied corpus metadata rows and distinct valid source IDs within court/date filters; empty-citation/empty/COURT_ IDs are excluded from source-ID denominators but retained in raw diagnostics. These are metadata-universe denominators, not counts of nonempty texts processed. Origin/DD/group filters affect the edge numerator only. Legacy absent text_policy is English-only; bilingual sources are never counted twice by a fallback.",
    "sampling_meaning": "Evidence is a deterministic bounded preview, not a random sample or the basis for reported totals.",
    "accuracy": "Structural validation is not semantic citation/identity accuracy; no fresh human calibration is implied.",
}


def offline_answer(source, intent, result, language="zh"):
    s, run = result["summary"], source.run_id
    context = result["origin_coverage_context"]
    before = context["summary_before_origin_filter"]
    if language == "en":
        text = (f"Run {run}: {s['citation_edges']} citation edges, {s['citing_source_ids']} citing source IDs, "
                f"{s['cited_groups']} cited judgment groups. Origin determined for {s['origin_determined_edges']}/{s['citation_edges']} edges; "
                f"{s['origin_unknown_edges']} unknown. Independently, {s['heuristic_only_edges']} edges have heuristic-only identity support.")
        if intent == "ranking":
            text += " Ranked by distinct source judgment IDs in the selected scope: " + "; ".join(
                f"{r['group_id']} ({r['group_name'] or 'unnamed'}): {r['filtered_dd']}" for r in result["rows"]) + "."
        if intent == "court_decade":
            text += f" The complete court/decade table contains {len(result['rows'])} buckets, including unknown dates when unfiltered."
        if intent == "case_citations":
            text += f" Source preview has {len(result['rows'])} rows; truncated={result['preview_truncated']}."
        if context["applied_origin_filter"] is not None:
            text += (f" Before the origin filter, with all other filters unchanged: {before['citation_edges']} edges, "
                     f"{before['origin_unknown_edges']} unknown origin (including conflicts), "
                     f"{before['heuristic_only_edges']} heuristic-only. Foreign is {before['foreign_edges']}/{before['citation_edges']} of all edges "
                     f"and {before['foreign_edges']}/{before['origin_determined_edges']} of origin-determined edges; a zero denominator means undefined. "
                     "Unknown origin is not foreign and cannot be extrapolated as foreign.")
        return text + " Counts show mentions, and do not establish whether a court followed a judgment."
    text = (f"运行 {run}：筛选范围内有 {s['citation_edges']} 条引证边、{s['citing_source_ids']} 个来源判决标识、"
            f"{s['cited_groups']} 个被引判决身份组。来源地已确定 {s['origin_determined_edges']}/{s['citation_edges']} 条；"
            f"未知 {s['origin_unknown_edges']} 条。另按身份支持统计，heuristic_only 为 {s['heuristic_only_edges']} 条。")
    if intent == "ranking":
        text += "按该范围内不同来源判决标识数排名：" + "；".join(
            f"{r['group_id']}（{r['group_name'] or '无案名'}）{r['filtered_dd']}" for r in result["rows"]) + "。"
    if intent == "court_decade":
        text += f"完整法院×年代结果有 {len(result['rows'])} 个分桶；未限制年份时保留未知年份桶。"
    if intent == "case_citations":
        text += f"来源判决预览 {len(result['rows'])} 条，{'已截断' if result['preview_truncated'] else '未截断'}。"
    if context["applied_origin_filter"] is not None:
        text += (f"保持其他筛选条件不变，来源地筛选前有 {before['citation_edges']} 条边，"
                 f"其中来源地未知（含冲突）{before['origin_unknown_edges']} 条、heuristic_only {before['heuristic_only_edges']} 条。"
                 f"外国边/全部边为 {before['foreign_edges']}/{before['citation_edges']}，"
                 f"外国边/来源地已知边为 {before['foreign_edges']}/{before['origin_determined_edges']}；分母为0时比例未定义。"
                 "未知来源地不能当作外国，也不能外推为外国。")
    return text + "这些计数表示原文提及，不证明法院遵循、依赖或认可被引判决。"


def make_packet(source, intent, filters=Filters(), top=10, evidence_limit=3, with_text=False,
                corpus_dir=None, language="zh", question=None, question_mode="explicit_fixed_intent"):
    source.queries = []
    result = exact_result(source, intent, filters, top)
    edge_rows = evidence_edges(source, filters, intent, result, evidence_limit)
    evidence = evidence_packet(source, edge_rows, with_text, corpus_dir)
    warnings = []
    params = source.manifest["params"]
    policy = policy_from_manifest(source.manifest)
    if params.get("limit_batches") is not None or params.get("year_from") is not None:
        warnings.append("Run input processing was limited. Corpus document denominators describe imported metadata and may include judgments not processed by this run.")
    if filters.year_from is not None or filters.year_to is not None:
        warnings.append("Date filters exclude unknown or conflicting source years; see unfiltered court_decade for missing-date counts.")
    if not source.manifest.get("output_identity"):
        warnings.append("Historical run has no sealed output identity; imported artifact hashes/current ledger row hashes do not prove unchanged original run outputs.")
    if result["summary"]["edges_missing_document_metadata"]:
        warnings.append("Some edges have no source document metadata; they remain in the UNKNOWN court/date bucket unless filters exclude them.")
    if sum(r["duplicate_source_ids"] for r in result["document_denominators"]):
        warnings.append("Multiple corpus rows share a source ID; source-ID counts are not independently verified distinct judgment counts. Conflicting source dates are assigned to UNKNOWN.")
    if result["full_corpus_metadata_diagnostics"]["invalid_source_id_document_rows"]:
        warnings.append("Corpus metadata contains empty-citation/invalid/placeholder source IDs. Their rows remain in raw corpus totals and diagnostics, but are excluded from distinct source-ID denominators and document joins to citation edges.")
    if source.provenance.get("lifecycle_metadata") == "legacy_not_recorded":
        warnings.append("Historical database has no recorded component lifecycle or normalized source provenance; this tool cannot certify its search indexes as current.")
    if filters.origin is not None and result['origin_coverage_context']['summary_before_origin_filter']['origin_unknown_edges']:
        warnings.append("Origin-filtered coverage describes the returned subset only. See origin_coverage_context for unknown/heuristic/conflict coverage before the origin filter within the same other constraints; unknown origin is not foreign.")
    packet = {"schema_version": VERSION, "status": "supported", "question": question, "intent": intent,
              "question_interpretation": question_mode,
              "analysis_tool_identity": {"core.py_sha256": file_hash(Path(__file__)),
                  "research.py_sha256": file_hash(Path(__file__).with_name("research.py"))},
              "parameters": {**asdict(filters), "top": top, "evidence_limit": evidence_limit,
                             "with_text": with_text, "language": language, 'text_policy': policy},
              "run_identity": source.identity(), "query_plan": source.queries, "exact_results": result,
              "answer": offline_answer(source, intent, result, language), "evidence": evidence,
              "capabilities": CAPABILITIES, "warnings": warnings,
              "storage": {"copies_of_corpus_or_database": 0, "persistent_query_cache_bytes": 0}}
    packet["packet_sha256"] = sha_text(canonical(packet))
    return packet


def route_question(question, courts):
    """A deliberately small grammar; unknown wording never becomes an inferred legal answer."""
    text = question.strip().rstrip("。?？.").strip()
    if not text or len(text) > 1000:
        return None
    if re.search(r"\b(select|pragma|drop|insert|delete|update|attach)\b", text, re.I):
        return None
    options = {}
    matched_courts = [c for c in courts if re.search(r"(?<![A-Za-z0-9])" + c + r"(?![A-Za-z0-9])", text, re.I)]
    if len(matched_courts) > 1:
        return None
    if matched_courts:
        options["court"] = matched_courts[0]
        text = re.sub(r"(?<![A-Za-z0-9])" + matched_courts[0] + r"(?![A-Za-z0-9])", "", text, flags=re.I)
    interval = re.search(r"(?:from\s+|between\s+)?(\d{4})\s*(?:-|–|到|至|to|and)\s*(\d{4})", text, re.I)
    if interval:
        options["year_from"], options["year_to"] = int(interval[1]), int(interval[2])
        text = text[:interval.start()] + text[interval.end():]
    origins = [(r"foreign|外国|境外", "FOREIGN"), (r"domestic|加拿大国内|国内", "DOMESTIC_CA"),
               (r"unknown origin|来源地未知", "UNDETERMINED"), (r"conflicting origin|来源地冲突", "CONFLICT")]
    for pattern, origin in origins:
        if re.search(pattern, text, re.I):
            if "origin" in options:
                return None
            options["origin"] = origin
            text = re.sub(pattern, "", text, flags=re.I)
    dd = re.search(r"(?:DD\s*(?:>=|≥)\s*|DD至少\s*)(\d+)", text, re.I)
    if dd:
        options["min_dd"] = int(dd[1])
        text = text[:dd.start()] + text[dd.end():]
    gid = re.search(r"\bXC-G\d+(?:-[A-Za-z0-9]+)?\b", text)
    if gid:
        options["group_id"] = gid[0]
        text = text[:gid.start()] + text[gid.end():]
    rank = re.search(r"top\s*(\d+)|前\s*(\d+)\s*(?:个|名)?", text, re.I)
    top = int(rank[1] or rank[2]) if rank else 10
    if rank:
        text = text[:rank.start()] + text[rank.end():]
    # Ignore only these scope connectors, never unknown content words.
    cleaned = re.sub(r"\b(in|during|for|the)\b|的|期间", "", text, flags=re.I)
    cleaned = re.sub(r"[\s,，:：]+", " ", cleaned).strip().lower()
    grammars = {
        "count": {"引证数量", "统计引证数量", "有多少条引证", "count citations", "citation count", "how many citations"},
        "court_decade": {"按法院和年代统计引证", "法院 年代引证统计", "引证趋势", "court decade citation statistics", "citation trend"},
        "ranking": {"引证最多 判决", "引证最多判决", "被引最多 判决", "被引最多判决", "引证排名", "cited cases", "most cited cases", "rank cited cases"},
        "case_citations": {"哪些判决引用", "谁引用", "who cites", "which judgments cite"},
    }
    for intent, phrases in grammars.items():
        if cleaned in phrases and (intent == "case_citations") == bool(gid):
            return intent, Filters(**options), top
    return None


def unsupported_packet(question, reason, identity=None):
    packet = {"schema_version": VERSION, "status": "unsupported", "question": question,
              "reason": reason, "run_identity": identity, "query_plan": [], "exact_results": None,
              "answer": None, "evidence": [], "capabilities": CAPABILITIES}
    packet["packet_sha256"] = sha_text(canonical(packet))
    return packet
