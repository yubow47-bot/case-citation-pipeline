"""Local Fix1 comparison adapter; never writes to a run or the G paper project.

The common calendar is 2001-2025 excluding 2011. This is an engineering
comparison, not a paper release or independent accuracy evaluation.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import gzip
from functools import lru_cache
import hashlib
import itertools
import json
from pathlib import Path
import sqlite3
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
csv.field_size_limit(100_000_000)


def rows(path):
    path = Path(path)
    if not path.exists():
        path = Path(str(path) + '.gz')
    with (gzip.open if path.suffix == '.gz' else open)(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        yield from csv.DictReader(stream)


def truth(value):
    return str(value).lower() in ('true', '1')


def write_rows(path, records, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with (gzip.open if path.suffix == '.gz' else open)(path, 'wt', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(records)


def fingerprint(values):
    return hashlib.sha256('\n'.join(sorted(set(values))).encode()).hexdigest()


def in_calendar(year):
    return year is not None and 2001 <= year <= 2025 and year != 2011


def load_dependencies(analysis_root):
    sys.path.insert(0, str(Path(analysis_root) / 'scripts'))
    sys.path.insert(0, str(ROOT / 'pipeline'))
    from citation_years import empty_pool, add_evidence, choose_year, attach_age
    from derive_occurrences import via_row_keys, printed_year_evidence, format_class
    from q2_metrics import vector_similarity
    from court_measurement import court_choice, choose_edge_court, destination, KNOWN
    from identity_evidence import CourtEvidence, _court_nk
    from decide import ELIGIBLE_BASES, CANADIAN_JURISDICTIONS
    return locals()


def prepare(a):
    run, out = Path(a.run_dir).resolve(), Path(a.out).resolve()
    if out == run or run in out.parents:
        raise ValueError('Comparison output must be outside the input run')
    if out.exists() and any(out.iterdir()):
        raise ValueError('Comparison output must be new or empty')
    if out.drive.upper() != 'D:' and not a.allow_fixture_output:
        raise ValueError('This task writes comparison outputs only on D:')
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = run / 'run_manifest.json'
    if not a.allow_fixture_output:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
        if manifest.get('status') != 'complete' or manifest.get('input_identity_verified_unchanged') is not True:
            raise ValueError('A completed run with unchanged verified inputs is required')
    else:
        manifest = {}
    dep = load_dependencies(a.analysis_root)
    db = sqlite3.connect(out / 'comparison.sqlite')
    db.executescript('''
      PRAGMA temp_store=FILE;
      CREATE TABLE docs(sid TEXT PRIMARY KEY,court TEXT,year INTEGER,eligible INTEGER,payload TEXT);
      CREATE TABLE members(gid TEXT,rkey TEXT,payload TEXT,PRIMARY KEY(gid,rkey));
      CREATE INDEX member_keys ON members(rkey);
      CREATE TABLE effective(sid TEXT,rkey TEXT,gid TEXT,PRIMARY KEY(sid,rkey,gid));
      CREATE INDEX effective_groups ON effective(gid);
      CREATE TABLE groups(gid TEXT PRIMARY KEY,signature TEXT,court TEXT,status TEXT,proof TEXT);
      CREATE TABLE edges(sid TEXT,gid TEXT,support TEXT,foreign_status TEXT,mentions INTEGER,history INTEGER,payload TEXT,PRIMARY KEY(sid,gid));
      CREATE TABLE candidates(cid TEXT PRIMARY KEY,sid TEXT,mkey TEXT,rowno INTEGER,start INTEGER,end INTEGER);
      CREATE TABLE occurrences(court TEXT,cid TEXT,sid TEXT,gid TEXT,fmt TEXT,priority INTEGER,year INTEGER,status TEXT,supported INTEGER,PRIMARY KEY(court,cid));
      CREATE INDEX occurrences_local ON occurrences(sid,gid);
      CREATE INDEX occurrences_group ON occurrences(gid,supported);
      CREATE TABLE edge_attributes(sid TEXT,gid TEXT,court_token TEXT,court_status TEXT,destination TEXT,age INTEGER,year_status TEXT,PRIMARY KEY(sid,gid));
    ''')
    prior = {r['source_id']: r for r in rows(a.documents)}
    source_rows = rows(a.source_records) if a.source_records else prior.values()
    for source in source_rows:
        sid = source['source_id']
        old = prior.get(sid, {})
        if a.source_records and sid not in prior:
            raise ValueError('New source missing baseline policy row: ' + sid)
        year_value = source.get('source_decision_year') if a.source_records else source.get('source_year')
        year = int(year_value) if str(year_value or '').isdigit() else None
        measurable = truth(source['source_measurable']) if a.source_records else truth(source.get('edge_assessable'))
        # Preserve reviewed source-scope exclusions, but do not inherit provider-year exclusions.
        eligible = measurable and in_calendar(year) and not truth(old.get('source_policy_excluded'))
        doc = {**old, **source, 'source_year': year, 'eligible': eligible,
               'edge_assessable': measurable, 'run_id': run.name,
               'comparison_calendar': '2001-2025_except_2011'}
        db.execute('INSERT INTO docs VALUES(?,?,?,?,?)', (sid, source['court'], year, int(eligible), json.dumps(doc)))
    del prior, source_rows
    member_fields = None
    for row in rows(run / 'decide_out/cross_court/decided.csv'):
        member_fields = member_fields or list(row)
        db.execute('INSERT INTO members VALUES(?,?,?)', (row['merged_group_id'], row['court'] + '|' + row['merge_key'], json.dumps(row)))
    for row in rows(run / 'decide_out/cross_court/effective_sources.csv'):
        if row['status'] != 'counted':
            continue
        for key in dep['via_row_keys'](row['via_member_row_keys']):
            db.execute('INSERT INTO effective VALUES(?,?,?)', (row['source_decision'], key, row['merged_group_id']))
    history_available = True
    for row in rows(run / 'edges/citation_edges.csv'):
        history_available = history_available and 'own_case_history' in row
        if not db.execute('SELECT 1 FROM docs WHERE sid=?', (row['source_decision'],)).fetchone():
            raise ValueError('Edge source absent from source records')
        if int(row['mention_count']) <= 0:
            raise ValueError('Final edge has no positive mention provenance')
        db.execute('INSERT INTO edges VALUES(?,?,?,?,?,?,?)', (row['source_decision'], row['resolved_cited_case'], row['edge_support'], row['foreign_status'], int(row['mention_count']), int(truth(row.get('own_case_history'))), json.dumps(row)))
    # Group fallback uses identity-qualified members only (F5 contract).
    for (gid,) in db.execute('SELECT DISTINCT gid FROM members ORDER BY gid').fetchall():
        members = [(key, json.loads(payload)) for key, payload in db.execute('SELECT rkey,payload FROM members WHERE gid=?', (gid,))]
        observations = []
        conflict = False
        for key, row in members:
            if row.get('identity_basis') not in dep['ELIGIBLE_BASES']:
                continue
            observations.extend(court_observations(row))
            conflict |= truth(row.get('identity_court_conflict')) or truth(row.get('court_designation_conflict'))
        choice = dep['court_choice'](observations)
        if conflict:
            choice.update(court_token='', court_status='CONFLICT')
        # Stable member facts plus supporting source positions, never an ordinal XC-G ID.
        keys = ['member:' + key for key, _ in members]
        keys += ['source:' + sid + '|' + key for sid, key in db.execute('SELECT sid,rkey FROM effective WHERE gid=? ORDER BY sid,rkey', (gid,))]
        db.execute('INSERT INTO groups VALUES(?,?,?,?,?)', (gid, fingerprint(keys), choice['court_token'], choice['court_status'], json.dumps(choice)))
    db.commit()
    fmt_rules = json.loads(Path(a.format_rules).read_text(encoding='utf-8-sig'))['rules']
    counters = Counter()
    for court in a.courts.split(','):
        db.execute('DELETE FROM candidates')
        for m in rows(run / 'merge_out' / court / 'mentions_candidates.csv'):
            if m['arbitration_status'] == 'counted':
                db.execute('INSERT INTO candidates VALUES(?,?,?,?,?,?)', (m['candidate_id'], m['source_decision_citation'], m['merge_key'], int(m['corpus_row_index']), int(m['match_start_offset']), int(m['match_end_offset'])))
        for c in rows(run / 'classify_out' / court / 'classified.csv'):
            m = db.execute('SELECT sid,mkey,rowno,start,end FROM candidates WHERE cid=?', (c['candidate_id'],)).fetchone()
            if m is None:
                continue
            sid, key, rowno, start, end = m
            if (sid, rowno, start, end) != (c['source_decision_citation'], int(c['corpus_row_index']), int(c['match_start_offset']), int(c['match_end_offset'])):
                raise ValueError('Classified/mention source position mismatch')
            matches = db.execute('SELECT f.gid,e.support FROM effective f JOIN edges e ON e.sid=f.sid AND e.gid=f.gid WHERE f.sid=? AND f.rkey=?', (sid, court + '|' + key)).fetchall()
            if not matches:
                counters['excluded_nonfinal_mentions'] += 1
                continue
            if len(matches) != 1:
                raise ValueError('Ambiguous source-conditioned final member: ' + sid + '|' + key)
            gid, support = matches[0]
            fmt, _ = dep['format_class'](c, fmt_rules)
            year = dep['printed_year_evidence'](c, fmt)
            db.execute('INSERT INTO occurrences VALUES(?,?,?,?,?,?,?,?,?)', (court, c['candidate_id'], sid, gid, fmt, year['year_priority'], year['year_candidate'], year['year_evidence_status'], int(support == 'supported')))
        db.commit()
    gaps = db.execute('SELECT e.sid,e.gid,e.mentions,COUNT(o.cid) FROM edges e LEFT JOIN occurrences o ON o.sid=e.sid AND o.gid=e.gid GROUP BY e.sid,e.gid HAVING e.mentions!=COUNT(o.cid)').fetchall()
    if gaps:
        (out / 'mention_reconciliation_failures.json').write_text(json.dumps(gaps, indent=2), encoding='utf-8')
        raise ValueError('Final occurrence counts do not reconcile: ' + str(len(gaps)))
    courts = dep['CourtEvidence'](ROOT / 'decisions')
    source_tokens = {c: courts.tokens.get(dep['_court_nk'](c), '') for c in a.courts.split(',')}
    geography = {}
    for rule in rows(ROOT / 'decisions/neutral_court_codes.csv'):
        token = courts.tokens.get(dep['_court_nk'](rule['court_code']))
        if token:
            geography.setdefault(token, set()).add(rule['jurisdiction'])
    geography = {t: 'CA' if v <= dep['CANADIAN_JURISDICTIONS'] else 'NON_CA' if not v & dep['CANADIAN_JURISDICTIONS'] else 'UNKNOWN' for t, v in geography.items()}
    @lru_cache(maxsize=2048)
    def group_year_pool(gid):
        return year_pool(db, dep, 'gid=? AND supported=1', (gid,))
    for sid, gid, support, origin, raw in db.execute('SELECT sid,gid,support,foreign_status,payload FROM edges'):
        members = [json.loads(payload) for (payload,) in db.execute('SELECT m.payload FROM effective f JOIN members m ON m.gid=f.gid AND m.rkey=f.rkey WHERE f.sid=? AND f.gid=?', (sid, gid))]
        local = dep['court_choice']([obs for member in members for obs in court_observations(member)])
        if any(truth(m.get('identity_court_conflict')) or truth(m.get('court_designation_conflict')) for m in members):
            local.update(court_token='', court_status='CONFLICT')
        group = json.loads(db.execute('SELECT proof FROM groups WHERE gid=?', (gid,)).fetchone()[0])
        choice = dep['choose_edge_court'](local, group, support == 'supported')
        local_year = year_pool(db, dep, 'sid=? AND gid=?', (sid, gid))
        selected = dep['choose_year'](local_year, group_year_pool(gid), support == 'supported')
        court, year = db.execute('SELECT court,year FROM docs WHERE sid=?', (sid,)).fetchone()
        age = year - selected['chosen_cited_year'] if year is not None and selected['chosen_cited_year'] is not None else None
        dest = dep['destination'](origin, choice, source_tokens.get(court, ''), source_tokens.get('SCC', ''), set(source_tokens.values()), geography)
        db.execute('INSERT INTO edge_attributes VALUES(?,?,?,?,?,?,?)', (sid, gid, choice['court_token'], choice['court_status'], dest, age, selected['year_status']))
    db.commit()
    norm = out / 'normalized'
    write_rows(norm / 'source_member_groups.csv.gz',
               (dict(zip(['source_id','row_key','group_id'], r)) for r in db.execute('SELECT sid,rkey,gid FROM effective')),
               ['source_id','row_key','group_id'])
    write_rows(norm / 'group_signatures.csv',
               (dict(zip(['group_id','stable_signature'], r)) for r in db.execute('SELECT gid,signature FROM groups')),
               ['group_id','stable_signature'])
    write_rows(norm / '04_members.csv.gz', (json.loads(r[0]) for r in db.execute('SELECT payload FROM members ORDER BY gid,rkey')), member_fields or ['court','merge_key','merged_group_id','case_name_modal','year_printed'])
    def normalized_edges():
        for raw, court, year, eligible in db.execute('SELECT e.payload,d.court,d.year,d.eligible FROM edges e JOIN docs d ON d.sid=e.sid'):
            yield {**json.loads(raw), 'source_court': court, 'source_year': year, 'eligible_source': bool(eligible)}
    edge_fields = list(json.loads(db.execute('SELECT payload FROM edges LIMIT 1').fetchone()[0])) if db.execute('SELECT 1 FROM edges LIMIT 1').fetchone() else ['source_decision','resolved_cited_case','foreign_status']
    write_rows(norm / '05_edges.csv.gz', normalized_edges(), edge_fields + ['source_court','source_year','eligible_source'])
    write_rows(norm / 'documents.csv.gz', (json.loads(r[0]) for r in db.execute('SELECT payload FROM docs')), ['source_id','court','source_year','eligible','edge_assessable','source_policy_excluded','source_measurable','quarantine_reason','decision_year_basis','run_id'])
    write_rows(out / 'courts/11_edge_courts.csv.gz', (dict(zip(['source_id','final_group_id','court_token','court_status'], r)) for r in db.execute('SELECT sid,gid,court_token,court_status FROM edge_attributes')), ['source_id','final_group_id','court_token','court_status'])
    write_rows(out / 'courts/court_crosswalk.csv', ({'court_token': token, 'source_court_code': code, 'court_geography': geography.get(token, 'UNKNOWN')} for code, token in source_tokens.items()), ['court_token','source_court_code','court_geography'])
    metrics = summarize(db, dep, a.courts.split(','), history_available)
    (out / 'metrics.json').write_text(json.dumps(metrics, indent=2, allow_nan=False), encoding='utf-8')
    receipt = {'run': str(run), 'out': str(out), 'calendar': '2001-2025 excluding 2011', 'source_contract': 'resolved year/measurability' if a.source_records else 'frozen baseline source policy', 'source_policy_documents': a.documents, 'source_records': a.source_records, 'occurrence_reconciliation_failures': 0, 'counters': dict(counters), 'status': 'LOCAL_ENGINEERING_COMPARISON_NOT_PAPER_RELEASE', 'ordinal_group_ids_compared': False, 'external_files_modified': False, 'history_view_available': history_available, 'run_manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest() if manifest_path.exists() else None, 'run_params': manifest.get('params'), 'seal_validation': 'Use the separate check_run receipt; adapter checks semantic joins and mention reconciliation', 'adapter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out / 'comparison_receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    db.close()
    return receipt


def court_observations(row):
    return [(part.split('=', 1)[0], part.split('=', 1)[1]) for part in row.get('identity_court_evidence', '').split('|') if part.startswith('court:') and '=' in part]


def year_pool(db, dep, where, args):
    pool = dep['empty_pool']()
    for court, cid, priority, year, status in db.execute('SELECT court,cid,priority,year,status FROM occurrences WHERE ' + where, args):
        dep['add_evidence'](pool, dict(court=court, candidate_id=cid, year_priority=priority, year_candidate=year, year_evidence_status=status))
    return pool


def summarize(db, dep, courts, history_available=True):
    result = {'calendar': '2001-2025 excluding 2011', 'O_definition': 'final counted occurrences reconciled to edge mention_count', 'views': {}}
    result['history_view_status'] = 'AVAILABLE' if history_available else 'UNAVAILABLE_IN_FROZEN_EDGE_SCHEMA'
    views = [('all_links', '')] + ([('without_own_case_history', ' AND e.history=0')] if history_available else [])
    for view, history in views:
        metrics, vectors = {}, {}
        for court in courts + ['ALL']:
            filt = '' if court == 'ALL' else ' AND d.court=?'
            params = () if court == 'ALL' else (court,)
            where = 'd.eligible=1' + filt + history
            join = ' FROM edges e JOIN docs d ON d.sid=e.sid'
            N = db.execute('SELECT COUNT(*) FROM docs d WHERE d.eligible=1' + filt, params).fetchone()[0]
            E, O = db.execute('SELECT COUNT(*),COALESCE(SUM(e.mentions),0)' + join + ' WHERE ' + where, params).fetchone()
            counts = Counter(dict(db.execute('SELECT g.signature,COUNT(*)' + join + ' JOIN groups g ON g.gid=e.gid WHERE ' + where + ' GROUP BY g.signature', params)))
            vectors[court] = counts
            ordered = sorted(counts, key=lambda g: (-counts[g], g))
            K = len(ordered)
            degrees = Counter(dict(db.execute('SELECT e.sid,COUNT(*)' + join + ' WHERE ' + where + ' GROUP BY e.sid', params)))
            values = list(degrees.values()) + [0] * (N - len(degrees))
            countries = dict(db.execute('SELECT e.foreign_status,COUNT(*)' + join + ' WHERE ' + where + ' GROUP BY e.foreign_status', params))
            destinations = dict(db.execute('SELECT a.destination,COUNT(*)' + join + ' JOIN edge_attributes a ON a.sid=e.sid AND a.gid=e.gid WHERE ' + where + ' GROUP BY a.destination', params))
            ages = [r[0] for r in db.execute('SELECT a.age' + join + ' JOIN edge_attributes a ON a.sid=e.sid AND a.gid=e.gid WHERE ' + where + ' AND a.age>=0', params)]
            formats = dict(db.execute('SELECT o.fmt,COUNT(*)' + join + ' JOIN occurrences o ON o.sid=e.sid AND o.gid=e.gid WHERE ' + where + ' GROUP BY o.fmt', params))
            if sum(formats.values()) != O:
                raise ValueError('Scoped Q7 O mismatch')
            metrics[court] = {'N': N, 'E': E, 'K': K, 'O': O,
                'Q1_top1pct_share': sum(counts[g] for g in ordered[:(K + 99) // 100]) / E if E else None,
                'Q1_top20': [{'stable_group_signature': g, 'DD': counts[g]} for g in ordered[:20]],
                'Q3_foreign_share_all_edges': countries.get('FOREIGN', 0) / E if E else None,
                'Q3_country_status_counts': countries,
                'Q4_links_per_assessable_source': E / N if N else None,
                'Q4_median_links': statistics.median(values) if values else None,
                'Q5_known_nonnegative_age_median': statistics.median(ages) if ages else None,
                'Q5_known_nonnegative_age_edges': len(ages),
                'Q6_destination_counts': destinations,
                'Q6_destination_shares': {k: v / E for k, v in destinations.items()} if E else {},
                'Q7_neutral_occurrence_share': formats.get('neutral', 0) / O if O else None,
                'Q7_format_counts': formats}
        overlap = {a + '/' + b: dep['vector_similarity'](vectors[a], vectors[b]) for a, b in itertools.combinations(courts, 2)}
        result['views'][view] = {'by_court': metrics, 'Q2_pairwise_top100': overlap}
    return result


def scalar_metrics(value, prefix=""):
    for key, item in value.items():
        name = prefix + key
        if isinstance(item, dict):
            yield from scalar_metrics(item, name + ".")
        elif isinstance(item, (int, float)) or item is None:
            yield name, item


def compare(before, after):
    old, new = (json.loads(Path(p).read_text(encoding='utf-8-sig')) for p in (before, after))
    result = []
    for view, payload in new['views'].items():
        for category in ('by_court', 'Q2_pairwise_top100'):
            for court, row in payload[category].items():
                baseline = dict(scalar_metrics(old.get('views', {}).get(view, {}).get(category, {}).get(court, {})))
                for key, value in scalar_metrics(row):
                    b = baseline.get(key)
                    result.append(dict(view=view, court=court, metric=key if category=='by_court' else 'Q2.'+key,
                                       before=b, after=value, change=value-b if isinstance(value,(int,float)) and isinstance(b,(int,float)) else None))
    return result


def top20_changes(before, after):
    old, new = (json.loads(Path(p).read_text(encoding='utf-8-sig')) for p in (before, after))
    for view, payload in new['views'].items():
        for court, row in payload['by_court'].items():
            prior = old.get('views', {}).get(view, {}).get('by_court', {}).get(court, {}).get('Q1_top20', [])
            a = {r['stable_group_signature']: (n, r['DD']) for n, r in enumerate(prior, 1)}
            b = {r['stable_group_signature']: (n, r['DD']) for n, r in enumerate(row['Q1_top20'], 1)}
            for signature in sorted(a.keys() | b.keys()):
                yield dict(view=view,court=court,stable_group_signature=signature,
                           before_rank=a.get(signature,(None,None))[0],after_rank=b.get(signature,(None,None))[0],
                           before_DD=a.get(signature,(None,None))[1],after_DD=b.get(signature,(None,None))[1])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir', required=True)
    p.add_argument('--documents', required=True, help='Existing reviewed source-policy documents, read-only')
    p.add_argument('--source-records', help='New D source_records.csv; omit only for frozen Run B')
    p.add_argument('--analysis-root', required=True)
    p.add_argument('--format-rules', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--courts', default='SCC,ONCA,BCCA,NSCA,FCA,YKCA,FC,BCSC,NSSC')
    p.add_argument('--before-metrics')
    p.add_argument('--allow-fixture-output', action='store_true', help=argparse.SUPPRESS)
    a = p.parse_args()
    print(json.dumps(prepare(a), ensure_ascii=False))
    if a.before_metrics:
        write_rows(Path(a.out)/'before_after.csv', compare(a.before_metrics, Path(a.out)/'metrics.json'), ['view','court','metric','before','after','change'])
        write_rows(Path(a.out)/'top20_changes.csv', top20_changes(a.before_metrics, Path(a.out)/'metrics.json'), ['view','court','stable_group_signature','before_rank','after_rank','before_DD','after_DD'])


if __name__ == '__main__':
    main()
