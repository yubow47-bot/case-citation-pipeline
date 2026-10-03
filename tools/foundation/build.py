"""Import a completed run without changing it; all rows and original columns survive."""
import argparse
import collections
import datetime
import json
from pathlib import Path
from common import ROOT, DEFAULT_DB, SCHEMA, connect, digest, dump, identifier, nk, rows, upsert_text, rebuild_fts


def create_csv_table(db, name, path, foreign_keys):
    with path.open(encoding='utf-8-sig', newline='') as f:
        import csv
        fields = csv.DictReader(f).fieldnames
    columns = ','.join(identifier(k) + ' TEXT NOT NULL' for k in fields)
    db.execute(f'CREATE TABLE IF NOT EXISTS {identifier(name)}(run_id TEXT NOT NULL,row_number INTEGER NOT NULL,{columns},PRIMARY KEY(run_id,row_number),{foreign_keys})')
    actual = [r['name'] for r in db.execute(f'PRAGMA table_info({identifier(name)})')][2:]
    if actual != fields:
        raise ValueError('Schema changed; use a new database version: ' + name)
    return fields


def import_csv(db, name, path, run_id, fields):
    query = f'INSERT INTO {identifier(name)} VALUES(' + ','.join('?' for _ in range(len(fields)+2)) + ')'
    batch = []
    total = 0
    for line, row in enumerate(rows(path), 2):
        if None in row or any(row.get(k) is None for k in fields):
            raise ValueError(f'Malformed CSV row: {path.name}:{line}')
        batch.append((run_id,line,*[row[k] for k in fields]))
        total += 1
        if len(batch) == 2000:
            db.executemany(query,batch); batch=[]
    db.executemany(query,batch)
    return total


def validate(db, run_id):
    checks = {}
    checks['bad_primary'] = db.execute('''SELECT COUNT(*) FROM (
      SELECT merged_group_id FROM members WHERE run_id=? GROUP BY merged_group_id
      HAVING SUM(is_primary='true')<>1)''',(run_id,)).fetchone()[0]
    checks['member_disagreement'] = db.execute('''SELECT COUNT(*) FROM members m JOIN case_groups g
      ON g.run_id=m.run_id AND g.group_id=m.merged_group_id WHERE m.run_id=? AND
      (CAST(m.distinct_decisions_count AS INTEGER)<>g.dd OR (m.kept='true')<>g.kept
       OR m.group_foreign_status<>g.foreign_status)''',(run_id,)).fetchone()[0]
    checks['duplicate_edges'] = db.execute('''SELECT COUNT(*) FROM (SELECT source_decision,resolved_cited_case
      FROM citation_edges WHERE run_id=? GROUP BY source_decision,resolved_cited_case HAVING COUNT(*)>1)''',(run_id,)).fetchone()[0]
    checks['edge_dd_mismatch'] = db.execute('''SELECT COUNT(*) FROM case_groups g LEFT JOIN
      (SELECT resolved_cited_case,COUNT(*) n FROM citation_edges WHERE run_id=? GROUP BY resolved_cited_case) e
      ON e.resolved_cited_case=g.group_id WHERE g.run_id=? AND g.dd<>COALESCE(e.n,0)''',(run_id,run_id)).fetchone()[0]
    checks['edges_without_document'] = db.execute('''SELECT COUNT(*) FROM citation_edges e WHERE e.run_id=?
      AND NOT EXISTS(SELECT 1 FROM documents d WHERE d.run_id=e.run_id AND d.source_id=e.source_decision)''',(run_id,)).fetchone()[0]
    checks['effective_edge_mismatch'] = db.execute('''SELECT COUNT(*) FROM effective_associations a
      WHERE a.run_id=? AND a.status='counted' AND NOT EXISTS(SELECT 1 FROM citation_edges e
      WHERE e.run_id=a.run_id AND e.source_decision=a.source_decision AND e.resolved_cited_case=a.merged_group_id)''',(run_id,)).fetchone()[0]
    checks['edge_effective_mismatch'] = db.execute('''SELECT COUNT(*) FROM citation_edges e
      WHERE e.run_id=? AND NOT EXISTS(SELECT 1 FROM effective_associations a WHERE a.run_id=e.run_id
      AND a.source_decision=e.source_decision AND a.merged_group_id=e.resolved_cited_case AND a.status='counted')''',(run_id,)).fetchone()[0]
    checks['foreign_key_violations'] = len(db.execute('PRAGMA foreign_key_check').fetchall())
    if any(checks.values()):
        raise ValueError('Import validation failed: ' + json.dumps(checks))
    return checks


def build(run_dir, db_path, corpus_dir=None):
    run_dir = Path(run_dir).resolve()
    run_id = run_dir.name
    manifest_path = run_dir/'run_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('status') != 'complete' or manifest.get('input_identity_verified_unchanged') is not True:
        raise ValueError('Run must be complete and its input identity verified unchanged')
    files = {'members':'select_out/selected.csv','citation_edges':'edges/citation_edges.csv',
             'effective_associations':'decide_out/cross_court/effective_sources.csv'}
    hashed = {v:digest(run_dir/v) for v in files.values()}
    hashed['run_manifest.json'] = digest(manifest_path)
    tables = {}
    for rel, expected in manifest['input_identity']['files'].items():
        if rel.startswith('decisions/'):
            p = ROOT/rel
            if digest(p) != expected:
                raise ValueError('Decision table does not match this run; obtain its immutable snapshot: '+rel)
            tables[rel] = (p,expected)
    db = connect(db_path)
    db.executescript(SCHEMA)
    try:
        prior = db.execute('SELECT * FROM runs WHERE run_id=?',(run_id,)).fetchone()
        if prior:
            previous = {r['relative_path']:r['sha256'] for r in db.execute('SELECT * FROM artifacts WHERE run_id=?',(run_id,))}
            if prior['status'] != 'ready' or any(previous.get(k)!=v for k,v in hashed.items()):
                raise ValueError('An existing run changed; import under a new run identity')
            return {'run_id':run_id,'already_imported':True,'checks':validate(db,run_id)}
        with db:
            db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',(run_id,str(run_dir),manifest['input_identity']['fingerprint'],
                       json.dumps(manifest,ensure_ascii=False),datetime.datetime.now(datetime.timezone.utc).isoformat(),'building'))
            for i,r in enumerate(rows(run_dir/files['members']),2):
                if r['is_primary']=='true':
                    db.execute('INSERT INTO case_groups VALUES(?,?,?,?,?,?,?,?,?)',(run_id,r['merged_group_id'],
                     int(r['distinct_decisions_count']),r['case_name_modal'],i,r['year_printed'],int(r['kept']=='true'),
                     r['group_foreign_status'],r['group_origin_country']))
            counts = {}
            for name,rel in files.items():
                fk = 'FOREIGN KEY(run_id) REFERENCES runs(run_id)'
                target = 'merged_group_id' if name != 'citation_edges' else 'resolved_cited_case'
                fk += f',FOREIGN KEY(run_id,{target}) REFERENCES case_groups(run_id,group_id)'
                fields = create_csv_table(db,name,run_dir/rel,fk)
                counts[name] = import_csv(db,name,run_dir/rel,run_id,fields)
            db.execute('CREATE INDEX IF NOT EXISTS members_group ON members(run_id,merged_group_id)')
            db.execute('CREATE INDEX IF NOT EXISTS members_key ON members(run_id,merge_key)')
            db.execute('CREATE INDEX IF NOT EXISTS members_citation ON members(run_id,canonical_string)')
            db.execute('CREATE INDEX IF NOT EXISTS edge_target ON citation_edges(run_id,resolved_cited_case)')
            db.execute('CREATE INDEX IF NOT EXISTS edge_source ON citation_edges(run_id,source_decision)')
            db.execute('CREATE INDEX IF NOT EXISTS effective_pair ON effective_associations(run_id,source_decision,merged_group_id,status)')
            import pyarrow.parquet as pq
            corpus_dir = Path(corpus_dir or ROOT/'corpus')
            for court in manifest['params']['courts']:
                path = corpus_dir/(court+'.parquet')
                expected = manifest['input_identity']['files']['corpus/'+court+'.parquet']
                if digest(path) != expected:
                    raise ValueError('Corpus snapshot mismatch: '+court)
                pf = pq.ParquetFile(path)
                offset = 0
                for batch in pf.iter_batches(batch_size=500,columns=['citation_en','name_en','document_date_en']):
                    values=[]
                    for n,r in enumerate(batch.to_pylist(),offset):
                        citation=r['citation_en'] or ''
                        values.append((run_id,court,n,court+'_'+nk(citation),citation,r['name_en'] or '',
                                       str(r['document_date_en'] or ''),str(path)))
                    db.executemany('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)',values)
                    offset += len(values)
                db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(run_id,'corpus/'+court+'.parquet',expected,offset))
            for rel,(path,sha) in tables.items():
                total = 0
                for n,r in enumerate(rows(path),2):
                    db.execute('INSERT INTO decision_facts VALUES(?,?,?,?)',(run_id,path.name,n,json.dumps(r,ensure_ascii=False)))
                    total += 1
                db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(run_id,rel,sha,total))
            # One pass over members instead of one query per group (237k queries was the slow step).
            citations_by_group = collections.defaultdict(set)
            for gid, cs in db.execute('SELECT merged_group_id,canonical_string FROM members WHERE run_id=?',(run_id,)):
                citations_by_group[gid].add(cs)
            for g in db.execute('SELECT * FROM case_groups WHERE run_id=?',(run_id,)).fetchall():
                if not g['name'].strip(): continue
                texts=[g['name']]
                texts.extend(sorted(citations_by_group[g['group_id']]))
                # DD remains a filter/sort field, never an embedding-derived credibility value.
                upsert_text(db,'cases',run_id+'/'+g['group_id'],'results','uncalibrated',g['name'],'\n'.join(texts),
                            str(run_dir/files['members'])+':record='+str(g['primary_row']),run_id)
            for rel,sha in hashed.items():
                if digest(run_dir/rel)!=sha: raise ValueError('Input changed during import: '+rel)
                name = next((k for k,v in files.items() if v==rel),None)
                db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(run_id,rel,sha,counts.get(name)))
            rebuild_fts(db)
            checks = validate(db,run_id)
            expected_stats=json.loads((run_dir/'select_out/manifest.json').read_text(encoding='utf-8'))['stats']
            total=db.execute('SELECT COUNT(*) FROM case_groups WHERE run_id=?',(run_id,)).fetchone()[0]
            if total!=expected_stats['groups_total'] or counts['members']!=expected_stats['rows_total']:
                raise ValueError('Counts differ from the select manifest')
            db.execute("UPDATE runs SET status='ready' WHERE run_id=?",(run_id,))
        report={'run_id':run_id,'db':str(Path(db_path).resolve()),'rows':counts,'groups':total,'checks':checks,
                'case_texts':db.execute("SELECT COUNT(*) FROM text_records WHERE run_id=? AND collection='cases'",(run_id,)).fetchone()[0],
                'semantic_accuracy':'not_assessed','weights':'not_calibrated'}
        dump(Path(db_path).parent/(run_id+'_import.json'),report)
        return report
    finally:
        db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--db',default=str(DEFAULT_DB));p.add_argument('--corpus')
    a=p.parse_args();print(json.dumps(build(a.run,a.db,a.corpus),ensure_ascii=False,indent=2))
