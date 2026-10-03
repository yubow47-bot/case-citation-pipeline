"""Shared local helpers; this toolkit is outside the production pipeline."""
from pathlib import Path
import csv
import hashlib
import json
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / 'data' / 'foundation_runtime'
sys.path.append(str(VENDOR))  # after site-packages: the vendored pyarrow is cp312
DEFAULT_DB = ROOT / 'data' / 'foundation' / 'research.db'
csv.field_size_limit(10**9)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def nk(text):
    return re.sub('[^A-Za-z0-9]', '', text or '').lower()


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f)


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def connect(path=DEFAULT_DB, readonly=False):
    path = Path(path).resolve()
    if readonly:
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=10000')
    return db


def identifier(name):
    if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', name):
        raise ValueError('Invalid column name')
    return '"' + name + '"'


SCHEMA = '''
CREATE TABLE IF NOT EXISTS runs(
 run_id TEXT PRIMARY KEY, source_directory TEXT NOT NULL,
 input_fingerprint TEXT NOT NULL, manifest_json TEXT NOT NULL,
 imported_at TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('building','ready')));
CREATE TABLE IF NOT EXISTS artifacts(
 run_id TEXT NOT NULL REFERENCES runs(run_id), relative_path TEXT NOT NULL,
 sha256 TEXT NOT NULL, row_count INTEGER, PRIMARY KEY(run_id,relative_path));
CREATE TABLE IF NOT EXISTS case_groups(
 run_id TEXT NOT NULL REFERENCES runs(run_id), group_id TEXT NOT NULL,
 dd INTEGER NOT NULL CHECK(dd>=0), name TEXT NOT NULL, primary_row INTEGER NOT NULL,
 year_printed TEXT NOT NULL, kept INTEGER NOT NULL CHECK(kept IN (0,1)),
 foreign_status TEXT NOT NULL, origin_country TEXT NOT NULL,
 PRIMARY KEY(run_id,group_id));
CREATE INDEX IF NOT EXISTS groups_dd ON case_groups(run_id,dd);
CREATE INDEX IF NOT EXISTS groups_name ON case_groups(run_id,name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS groups_origin ON case_groups(run_id,foreign_status);
CREATE TABLE IF NOT EXISTS documents(
 run_id TEXT NOT NULL REFERENCES runs(run_id), court TEXT NOT NULL,
 corpus_row INTEGER NOT NULL, source_id TEXT NOT NULL, citation TEXT NOT NULL,
 name TEXT NOT NULL, decision_date TEXT NOT NULL, corpus_path TEXT NOT NULL,
 PRIMARY KEY(run_id,court,corpus_row));
CREATE INDEX IF NOT EXISTS documents_source ON documents(run_id,source_id);
CREATE TABLE IF NOT EXISTS decision_facts(
 run_id TEXT NOT NULL REFERENCES runs(run_id), table_name TEXT NOT NULL,
 row_number INTEGER NOT NULL, row_json TEXT NOT NULL,
 PRIMARY KEY(run_id,table_name,row_number));
CREATE TABLE IF NOT EXISTS text_records(
 id INTEGER PRIMARY KEY, run_id TEXT REFERENCES runs(run_id),
 collection TEXT NOT NULL, entity_key TEXT NOT NULL, layer TEXT NOT NULL,
 status TEXT NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL,
 source_locator TEXT NOT NULL, content_hash TEXT NOT NULL,
 UNIQUE(collection,entity_key));
CREATE INDEX IF NOT EXISTS text_filter ON text_records(collection,layer,status);
CREATE VIRTUAL TABLE IF NOT EXISTS text_fts USING fts5(
 title,text,content='text_records',content_rowid='id',tokenize='trigram');
CREATE TABLE IF NOT EXISTS external_observations(
 id INTEGER PRIMARY KEY, baseline_run TEXT NOT NULL, source_artifact TEXT NOT NULL,
 row_number INTEGER NOT NULL, observation_kind TEXT NOT NULL,
 source_id TEXT, external_id TEXT, row_json TEXT NOT NULL,
 verification_status TEXT NOT NULL DEFAULT 'historical_observation_not_truth',
 UNIQUE(source_artifact,row_number));
CREATE TABLE IF NOT EXISTS review_samples(
 sample_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, group_id TEXT NOT NULL,
 source_id TEXT NOT NULL, stratum TEXT NOT NULL, fold TEXT NOT NULL,
 inclusion_probability REAL NOT NULL CHECK(inclusion_probability>0 AND inclusion_probability<=1),
 selection_rank INTEGER NOT NULL, FOREIGN KEY(run_id,group_id) REFERENCES case_groups(run_id,group_id));
CREATE TABLE IF NOT EXISTS review_labels(
 sample_id TEXT PRIMARY KEY REFERENCES review_samples(sample_id),
 verdict TEXT NOT NULL CHECK(verdict IN ('correct','incorrect','unverifiable')),
 reviewer TEXT NOT NULL, evidence_locator TEXT NOT NULL, notes TEXT NOT NULL,
 reviewed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scores(
 run_id TEXT NOT NULL, group_id TEXT NOT NULL, scoring_version TEXT NOT NULL,
 confidence REAL, weighted_dd REAL, scope TEXT NOT NULL, status TEXT NOT NULL,
 PRIMARY KEY(run_id,group_id,scoring_version),
 FOREIGN KEY(run_id,group_id) REFERENCES case_groups(run_id,group_id));
'''


def upsert_text(db, collection, key, layer, status, title, text, locator, run_id=None):
    sha = hashlib.sha256(text.encode('utf-8')).hexdigest()
    db.execute('''INSERT INTO text_records(run_id,collection,entity_key,layer,status,title,text,source_locator,content_hash)
      VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(collection,entity_key) DO UPDATE SET
      run_id=excluded.run_id,layer=excluded.layer,status=excluded.status,title=excluded.title,
      text=excluded.text,source_locator=excluded.source_locator,content_hash=excluded.content_hash''',
      (run_id,collection,key,layer,status,title,text,locator,sha))


def rebuild_fts(db):
    db.execute("INSERT INTO text_fts(text_fts) VALUES('rebuild')")
