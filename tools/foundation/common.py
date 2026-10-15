"""Shared local helpers; this toolkit is outside the production pipeline."""
from pathlib import Path
from contextlib import contextmanager
from contextvars import ContextVar
import csv
import datetime
import gzip
import hashlib
import json
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from pipeline.corpus_fields import (POLICY_EN, policy_from_manifest, projection,
                                    select_record)
VENDOR = ROOT / 'data' / 'foundation_runtime'
sys.path.append(str(VENDOR))  # after site-packages: the vendored pyarrow is cp312
DEFAULT_DB = ROOT / 'data' / 'foundation' / 'research.db'
csv.field_size_limit(10**9)
_STORAGE_POLICY = ContextVar('foundation_storage_policy', default=None)
_STORAGE_REPORTS = ContextVar('foundation_storage_reports', default=None)


def selected_corpus_rows(parquet, policy, include_text=True, batch_size=500):
    """Yield row numbers and manifest-bound field selections without retaining texts.

    Historical English-only fixtures/readers may expose only the text column;
    real Parquet inputs always use their actual schema projection.
    """
    schema = getattr(getattr(parquet, 'schema_arrow', None), 'names', None)
    if schema is None:
        columns = ['unofficial_text_en'] if include_text else ['citation_en', 'name_en', 'document_date_en']
    else:
        columns = projection(schema, include_text=include_text)
        if policy == POLICY_EN:
            columns = [field for field in columns if field.endswith('_en')]
    offset = 0
    for batch in parquet.iter_batches(batch_size=batch_size, columns=columns):
        if hasattr(batch, 'to_pylist'):
            records = batch.to_pylist()
        else:
            records = [{'unofficial_text_en': text} for text in batch.column(0).to_pylist()]
        for record in records:
            yield offset, select_record(record, policy)
            offset += 1


def corpus_field_evidence(selected):
    """Compact fields needed to interpret original-text offsets, after reading text."""
    result = {field: selected[field] for field in ('text_field', 'language', 'citation_field')}
    if selected['date_field'] != 'document_date_en':
        result['date_field'] = selected['date_field']
    if selected['name_field'] != 'name_en':
        result['name_field'] = selected['name_field']
    return result


def storage_module():
    """Load the existing no-follow storage policy, without a dependency install."""
    repository = str(Path(__file__).resolve().parents[2])
    if repository not in sys.path:
        sys.path.insert(0, repository)
    from tools import storage
    return storage


def current_storage_policy():
    storage = storage_module()
    return _STORAGE_POLICY.get() or {'max_project_bytes': storage.DEFAULT_MAX_PROJECT_BYTES,
        'min_free_bytes': storage.DEFAULT_MIN_FREE_BYTES, 'journal_margin_bytes': 64 * storage.MiB}


@contextmanager
def storage_limits(max_project_bytes=None, min_free_bytes=None, journal_margin_bytes=None):
    """Explicit scoped limits shared by every project DB connection in after_run."""
    policy = dict(current_storage_policy())
    for key, value in (('max_project_bytes', max_project_bytes), ('min_free_bytes', min_free_bytes),
                       ('journal_margin_bytes', journal_margin_bytes)):
        if value is not None:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError('Storage limits must be nonnegative integer bytes: ' + key)
            policy[key] = value
    token = _STORAGE_POLICY.set(policy)
    try:
        yield policy
    finally:
        _STORAGE_POLICY.reset(token)


@contextmanager
def capture_storage_reports():
    reports = []
    token = _STORAGE_REPORTS.set(reports)
    try:
        yield reports
    finally:
        _STORAGE_REPORTS.reset(token)


def project_database(path):
    return Path(ROOT).resolve() in Path(path).resolve().parents


def database_preflight(path, estimated_peak_bytes=0):
    """No guard on readonly or fixture DBs outside the project; no file content hashes."""
    path = Path(path).resolve()
    if not project_database(path):
        return {'guarded': False, 'reason': 'database_outside_project_root', 'db': str(path)}
    policy = current_storage_policy()
    report = storage_module().preflight(ROOT, estimated_peak_bytes,
        max_project_bytes=policy['max_project_bytes'], min_free_bytes=policy['min_free_bytes'])
    return dict(report, guarded=True, db=str(path), journal_margin_bytes=policy['journal_margin_bytes'])


class StorageCapacityError(sqlite3.OperationalError):
    """The configured storage budget cannot hold a writable SQLite generation."""


class GuardedCursor(sqlite3.Cursor):
    def execute(self, *args, **kwargs):
        try:
            return super().execute(*args, **kwargs)
        except sqlite3.Error as exc:
            self.connection._storage_error(exc)

    def executemany(self, *args, **kwargs):
        try:
            return super().executemany(*args, **kwargs)
        except sqlite3.Error as exc:
            self.connection._storage_error(exc)

    def executescript(self, *args, **kwargs):
        try:
            return super().executescript(*args, **kwargs)
        except sqlite3.Error as exc:
            self.connection._storage_error(exc)


class GuardedConnection(sqlite3.Connection):
    storage_report = None

    def cursor(self, factory=GuardedCursor):
        return super().cursor(factory)

    def _storage_error(self, exc):
        if getattr(exc, 'sqlite_errorcode', None) == sqlite3.SQLITE_FULL and self.storage_report:
            report = self.storage_report
            error = StorageCapacityError('SQLite storage cap reached (SQLITE_FULL): db=%s; max_page_count=%s; '
                'max_db_bytes=%s; project_budget_bytes=%s. Rollback this generation and free obsolete derived artifacts before retrying.' %
                (report['db'], report['max_page_count'], report['max_db_bytes'], report['max_project_bytes']))
            error.sqlite_errorcode = sqlite3.SQLITE_FULL
            error.sqlite_errorname = 'SQLITE_FULL'
            error.storage_report = report
            raise error from exc
        raise exc

    def execute(self, *args, **kwargs):
        try:
            return super().execute(*args, **kwargs)
        except sqlite3.Error as exc:
            self._storage_error(exc)

    def executemany(self, *args, **kwargs):
        try:
            return super().executemany(*args, **kwargs)
        except sqlite3.Error as exc:
            self._storage_error(exc)

    def executescript(self, *args, **kwargs):
        try:
            return super().executescript(*args, **kwargs)
        except sqlite3.Error as exc:
            self._storage_error(exc)

    def commit(self):
        try:
            return super().commit()
        except sqlite3.Error as exc:
            self._storage_error(exc)

    def __exit__(self, exception_type, exception_value, traceback):
        try:
            return super().__exit__(exception_type, exception_value, traceback)
        except sqlite3.Error as exc:
            self._storage_error(exc)


def cap_database(db, path, preflight):
    """Bound main DB growth and reserve the final cap's rollback journal, not just its initial size."""
    mode = db.execute('PRAGMA journal_mode').fetchone()[0].lower()
    if mode == 'wal':
        raise StorageCapacityError('Writable project DB is in WAL mode; checkpoint/close existing writers before a guarded DELETE-journal rebuild: ' + str(path))
    mode = db.execute('PRAGMA journal_mode=DELETE').fetchone()[0].lower()
    if mode != 'delete':
        raise StorageCapacityError('Cannot establish guarded DELETE rollback journaling: ' + str(path))
    db.execute('PRAGMA temp_store=MEMORY')
    page_size = db.execute('PRAGMA page_size').fetchone()[0]
    page_count = db.execute('PRAGMA page_count').fetchone()[0]
    current = max(Path(path).stat().st_size, page_size * page_count)
    headroom = min(preflight['max_project_bytes'] - preflight['project_bytes'],
                   preflight['free_bytes'] - preflight['min_free_bytes'])
    # Additional DB bytes + 125% of final DB cap + fixed journal/header margin <= headroom.
    # This remains conservative even when one connection executes several transactions.
    max_db_bytes = (4 * (headroom + current - preflight['journal_margin_bytes'])) // 9
    pages = max_db_bytes // page_size
    if pages < max(1, page_count):
        error = StorageCapacityError('Insufficient SQLite peak capacity: db=%s; current_db_bytes=%s; headroom_bytes=%s; '
            'journal_margin_bytes=%s. Need space for the database plus its rollback journal within the project budget/free reserve.' %
            (path, current, headroom, preflight['journal_margin_bytes']))
        error.storage_report = dict(preflight, current_db_bytes=current, headroom_bytes=headroom)
        raise error
    actual_pages = db.execute('PRAGMA max_page_count=%d' % pages).fetchone()[0]
    report = dict(preflight, current_db_bytes=current, page_size=page_size,
                  max_page_count=actual_pages, max_db_bytes=actual_pages * page_size,
                  journal_reserve_bytes=(actual_pages * page_size * 5 + 3) // 4 + preflight['journal_margin_bytes'],
                  journal_mode='delete', temp_store='memory',
                  measurement='Project logical-file lengths; links/junctions excluded. SQLite main-file page cap reserves 125% rollback journal plus margin.')
    db.storage_report = report
    return report


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def nk(text):
    return re.sub('[^A-Za-z0-9]', '', text or '').lower()


def resolve_artifact(path):
    """Read compressed artifacts in place; never materialize a second CSV copy."""
    path = Path(path)
    if path.is_file():
        return path
    zipped = Path(str(path) + '.gz')
    if zipped.is_file():
        return zipped
    raise FileNotFoundError(str(path) + ' (or .gz)')


def artifact_open(path, mode='rt'):
    path = resolve_artifact(path)
    if path.suffix == '.gz':
        return gzip.open(path, mode, encoding='utf-8-sig' if 't' in mode else None,
                         newline='' if 't' in mode else None)
    return path.open(mode, encoding='utf-8-sig' if 't' in mode else None,
                     newline='' if 't' in mode else None)


def artifact_digest(path):
    """Hash logical bytes, so lossless CSV compression preserves snapshot identity."""
    h = hashlib.sha256()
    with artifact_open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


content_digest = artifact_digest


def csv_fields(path):
    with artifact_open(path) as f:
        fields = csv.DictReader(f).fieldnames
    if not fields or len(fields) != len(set(fields)) or any(not k for k in fields):
        raise ValueError('Missing or duplicate CSV columns: ' + str(path))
    return fields


def rows(path):
    with artifact_open(path) as f:
        yield from csv.DictReader(f)


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def connect(path=DEFAULT_DB, readonly=False):
    path = Path(path).resolve()
    existed = path.exists()
    guarded = not readonly and project_database(path)
    preflight = database_preflight(path) if guarded else None
    if readonly:
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, factory=GuardedConnection if guarded else sqlite3.Connection)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=10000')
    if guarded:
        try:
            report = cap_database(db, path, preflight)
            captured = _STORAGE_REPORTS.get()
            if captured is not None:
                captured.append(report)
        except Exception:
            db.close()
            if not existed and path.is_file() and path.stat().st_size == 0:
                path.unlink()
            raise
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
CREATE TABLE IF NOT EXISTS run_sources(
 run_id TEXT NOT NULL REFERENCES runs(run_id), logical_path TEXT NOT NULL,
 actual_path TEXT NOT NULL, sha256 TEXT NOT NULL, physical_sha256 TEXT NOT NULL,
 size_bytes INTEGER NOT NULL, compression TEXT NOT NULL,
 PRIMARY KEY(run_id,logical_path));
CREATE TABLE IF NOT EXISTS run_components(
 run_id TEXT NOT NULL REFERENCES runs(run_id), component TEXT NOT NULL,
 generation INTEGER NOT NULL, status TEXT NOT NULL
 CHECK(status IN ('building','ready','failed','missing','stale')),
 source_fingerprint TEXT NOT NULL, details_json TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(run_id,component));
CREATE TABLE IF NOT EXISTS profile_passages(
 run_id TEXT NOT NULL, group_id TEXT NOT NULL, source_decision TEXT NOT NULL,
 evidence_json TEXT NOT NULL,
 PRIMARY KEY(run_id,group_id,source_decision));
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

REQUIRED_COMPONENTS = ('import', 'relations', 'cases', 'edges', 'methods', 'acceptance')


def ensure_state_schema(db):
    """Safe schema extension for pre-generation databases."""
    for statement in SCHEMA.split(';'):
        if any('CREATE TABLE IF NOT EXISTS ' + name + '(' in statement
               for name in ('run_sources', 'run_components', 'profile_passages')):
            db.execute(statement)
    fields = {r[1] for r in db.execute('PRAGMA table_info(run_sources)')}
    for name, kind, default in [('physical_sha256', 'TEXT', "''"), ('size_bytes', 'INTEGER', '0'),
                                ('compression', 'TEXT', "''")]:
        if name not in fields:
            db.execute('ALTER TABLE run_sources ADD COLUMN %s %s NOT NULL DEFAULT %s' % (name, kind, default))


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def source_record(db, run_id, logical_path, path, expected=None):
    actual = resolve_artifact(path).resolve()
    sha = artifact_digest(actual)
    if expected is not None and sha != expected:
        raise ValueError('Source snapshot mismatch: ' + logical_path)
    prior = db.execute('SELECT sha256 FROM run_sources WHERE run_id=? AND logical_path=?',
                       (run_id, logical_path)).fetchone()
    if prior and prior[0] != sha:
        raise ValueError('Source changed since import: ' + logical_path)
    physical_sha = digest(actual) if actual.suffix == '.gz' else sha
    size = actual.stat().st_size
    compression = 'gzip' if actual.suffix == '.gz' else 'none'
    db.execute('INSERT OR REPLACE INTO run_sources(run_id,logical_path,actual_path,sha256,physical_sha256,size_bytes,compression) VALUES(?,?,?,?,?,?,?)',
               (run_id, logical_path, str(actual), sha, physical_sha, size, compression))
    return {'path': str(actual), 'sha256': sha, 'logical_path': logical_path,
            'physical_sha256': physical_sha, 'size_bytes': size, 'compression': compression}


def source_snapshot(db, run_id, run_dir, require_mentions=True):
    """Bind passages to imported corpus paths and immutable mention snapshots."""
    ensure_state_schema(db)
    r = db.execute('SELECT manifest_json,source_directory FROM runs WHERE run_id=?', (run_id,)).fetchone()
    if not r:
        raise ValueError('Run is not imported: ' + run_id)
    if Path(r['source_directory']).resolve() != Path(run_dir).resolve():
        raise ValueError('Run directory differs from imported identity')
    manifest = json.loads(r['manifest_json'])
    out = {}
    for court in manifest['params']['courts']:
        logical = 'corpus/' + court + '.parquet'
        expected = manifest['input_identity']['files'][logical]
        paths = [p[0] for p in db.execute('SELECT DISTINCT corpus_path FROM documents WHERE run_id=? AND court=?',
                                        (run_id, court))]
        recorded = db.execute('SELECT actual_path FROM run_sources WHERE run_id=? AND logical_path=?',
                               (run_id, logical)).fetchone()
        if len(paths) > 1 or (not paths and not recorded):
            raise ValueError('No unique imported corpus path: ' + court)
        corpus_path = paths[0] if paths else recorded[0]
        out[logical] = source_record(db, run_id, logical, corpus_path, expected)
        if require_mentions:
            logical = 'merge_out/' + court + '/mentions_candidates.csv'
            # Import must record this snapshot before downstream evidence generation.
            prior = db.execute('SELECT sha256 FROM run_sources WHERE run_id=? AND logical_path=?',
                                (run_id, logical)).fetchone()
            if not prior:
                raise ValueError('Missing imported mentions snapshot: ' + logical + '; reimport into a new DB')
            out[logical] = source_record(db, run_id, logical, Path(run_dir)/logical, prior[0])
    return out


def verify_snapshot(snapshot):
    for logical, record in snapshot.items():
        if artifact_digest(record['path']) != record['sha256']:
            raise ValueError('Source changed during generation: ' + logical)


def expand_evidence(db, run_id, evidence):
    """Resolve compact passage references for an answer packet without duplicating DB storage."""
    out = json.loads(evidence) if isinstance(evidence, str) else dict(evidence)
    for kind in ('corpus', 'mentions'):
        logical = out.get(kind, {}).get('logical_path')
        if not logical:
            raise ValueError('Evidence source reference is missing: ' + kind)
        source = db.execute('SELECT * FROM run_sources WHERE run_id=? AND logical_path=?', (run_id, logical)).fetchone()
        if not source:
            raise ValueError('Evidence source snapshot is missing: ' + logical)
        out[kind] = dict(source)
        out[kind]['path'] = out[kind]['actual_path']
    return out


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def start_component(db, run_id, component, sources=None):
    ensure_state_schema(db)
    old = db.execute('SELECT generation FROM run_components WHERE run_id=? AND component=?',
                      (run_id, component)).fetchone()
    generation = old[0] + 1 if old else 1
    db.execute("UPDATE runs SET status='building' WHERE run_id=?", (run_id,))
    db.execute("UPDATE run_components SET status='stale',updated_at=? WHERE run_id=? AND component='acceptance'",
               (now(), run_id))
    if component in ('cases', 'edges', 'methods'):
        db.execute("UPDATE run_components SET status='stale',updated_at=? WHERE run_id=? AND component=?",
                   (now(), run_id, 'vectors_' + component))
    db.execute('INSERT OR REPLACE INTO run_components VALUES(?,?,?,?,?,?,?)',
               (run_id, component, generation, 'building', fingerprint(sources or {}), '{}', now()))
    db.commit()
    return generation


def finish_component(db, run_id, component, generation, status='ready', details=None):
    changed = db.execute('UPDATE run_components SET status=?,details_json=?,updated_at=? '
                         'WHERE run_id=? AND component=? AND generation=? AND status=\'building\'',
                         (status, json.dumps(details or {}, ensure_ascii=False), now(), run_id, component, generation)).rowcount
    if changed != 1:
        raise ValueError('Component generation changed during build: ' + component)


def fail_component(db, run_id, component, generation, error):
    db.rollback()
    with db:
        db.execute('UPDATE run_components SET status=\'failed\',details_json=?,updated_at=? '
                   'WHERE run_id=? AND component=? AND generation=?',
                   (json.dumps({'error': str(error)[:2000]}, ensure_ascii=False), now(), run_id, component, generation))
        db.execute("UPDATE runs SET status='building' WHERE run_id=?", (run_id,))


def component_status(db, run_id, component):
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='run_components'").fetchone()
    if not exists:
        return 'legacy_unverified'
    r = db.execute('SELECT status FROM run_components WHERE run_id=? AND component=?', (run_id, component)).fetchone()
    return r[0] if r else 'missing'


def publish_run(db, run_id):
    states = {c: component_status(db, run_id, c) for c in REQUIRED_COMPONENTS}
    if any(s != 'ready' for s in states.values()):
        raise ValueError('Cannot publish incomplete keyword generation: ' + json.dumps(states))
    db.execute("UPDATE runs SET status='ready' WHERE run_id=?", (run_id,))


def upsert_text(db, collection, key, layer, status, title, text, locator, run_id=None):
    sha = hashlib.sha256(text.encode('utf-8')).hexdigest()
    db.execute('''INSERT INTO text_records(run_id,collection,entity_key,layer,status,title,text,source_locator,content_hash)
      VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(collection,entity_key) DO UPDATE SET
      run_id=excluded.run_id,layer=excluded.layer,status=excluded.status,title=excluded.title,
      text=excluded.text,source_locator=excluded.source_locator,content_hash=excluded.content_hash''',
      (run_id,collection,key,layer,status,title,text,locator,sha))


def rebuild_fts(db):
    db.execute("INSERT INTO text_fts(text_fts) VALUES('rebuild')")
