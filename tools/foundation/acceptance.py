"""Fixed real questions for accepting the retrieval layer. A question passes when an expected hit is
in the top K. Re-run after every index rebuild; numbers go into the report, not into any pipeline step.

    python tools/foundation/acceptance.py            # both collections, hybrid
    python tools/foundation/acceptance.py --mode keyword
"""
import argparse
import json
import sys
from pathlib import Path
from common import (DEFAULT_DB, connect, component_status, source_snapshot, verify_snapshot,
                    artifact_digest, start_component, finish_component, fail_component, publish_run,
                    dump, REQUIRED_COMPONENTS)
from embed import load_vec
from query import search, latest_run
from rewrite import to_english

CASES = [
    ('standard of appellate review palpable and overriding error', ['Housen']),
    ('上诉审查标准 明显且压倒性的错误', ['Housen']),
    ('Charter section 1 reasonable limits proportionality test', ['Oakes']),
    ('sentencing Aboriginal offenders systemic background factors', ['Gladue', 'Ipeelee']),
    ('原住民被告量刑 系统性背景因素', ['Gladue', 'Ipeelee']),
    ('reasonableness review of administrative decisions', ['Vavilov', 'Dunsmuir']),
    ('spousal support compensatory model economic disadvantage', ['Moge']),
    ('principled exception to hearsay necessity and reliability', ['Khelawon', 'Khan', 'Smith', 'B. (K.G.)', 'Bradshaw']),
    ('unreasonable delay presumptive ceiling 18 months 30 months', ['Jordan']),
    ('刑事审判不合理拖延 推定上限', ['Jordan']),
    ('reasonable doubt jury instruction', ['Lifchus', 'Starr']),
    ('retroactive child support', ['D.B.S.', 'S. (D.B.)', 'DBS']),
    ('fiduciary duty of the Crown to Indigenous peoples', ['Guerin', 'Haida', 'Wewaykum']),
    ('summary judgment genuine issue requiring a trial proportionality', ['Hryniak']),
    ('标准合同解释 事实矩阵', ['Sattva']),
]
METHODS = [
    ('S.J. 同形缩写 按卷号区间消歧', ['reporter_jurisdiction', 'classify', '02_classification', '08_pitfalls_by_layer']),
    ('跨年份 年份写成两段 year_raw', ['extract', 'shapes']),
    ('枢密院 对加拿大上诉 案件来源 与汇编法域不同', ['decide', 'case_origin']),
    ('DD 门槛 只打标记 不删除行 kept', ['select']),
    ('案名多数投票 归并 变体折叠', ['merge']),
    ('中立引证 法院代码 表', ['neutral_court_codes', 'identifier_systems', '06_decision_tables']),
    ('自引 排除 判决自身头部引证', ['decide', 'self']),
    ('CanLII 对照 法院时期分层抽样', ['canlii', 'crosscheck']),
    ('双语中立引证 英法对应', ['bilingual_neutral_codes']),
    ('方括号法院标注 court designation 识别', ['court_designations', 'designation']),
    ('distinct_decisions_count 并集 不是 max', ['merge', 'select', 'distinct']),
    ('抽取层禁止固定缩写表 按结构形状匹配', ['extract', 'shapes', 'technical_specification']),
]

# Extension scenarios: what someone adding a court / a new regex family would ask. The expected
# answer is the hand-written method card (docs/method_cards), not a raw fragment.
EXTENSION = [
    ('加一个新法院（比如 Alberta 上诉法院）要改哪些地方', ['00_new_court_playbook']),
    ('新法院的中立引证代码怎么登记', ['06_decision_tables', '00_new_court_playbook']),
    ('遇到一个新的汇编缩写，怎么判断它属于哪个法域', ['02_classification', '06_decision_tables']),
    ('新法院的判决案名格式不一样，案名切分要怎么处理', ['02_classification']),
    ('新语料上线前怎么确认抽取没有漏掉引证', ['01_extraction', '07_verification_gates', '00_new_court_playbook']),
    ('法语判决（魁北克）的引证怎么处理', ['00_new_court_playbook', '06_decision_tables']),
    ('新增法域后怎么验证结果没有被破坏', ['07_verification_gates']),
    ('一个缩写同时是英国和加拿大的汇编怎么消歧', ['02_classification', '08_pitfalls_by_layer']),
    ('抽到了新的标识符体系，比如案卷号，怎么处理', ['06_decision_tables', '00_new_court_playbook', '02_classification']),
    ('日期被当成引证了怎么办', ['02_classification', '08_pitfalls_by_layer']),
    ('要加一种新的引证写法的正则，门槛是什么', ['01_extraction']),
    ('判决引用了自己，DD 多算了', ['04_adjudication', '08_pitfalls_by_layer']),
    ('DD 门槛 5 有没有依据', ['05_selection_and_edges']),
    ('零填充的编号 0443 和 443 被当成两个案子', ['03_merging', '08_pitfalls_by_layer', '04_adjudication']),
    ('决策表加了行但是没有生效', ['06_decision_tables', '07_verification_gates']),
    ('同一个案子的一审上诉审终审被并成一组', ['04_adjudication', '08_pitfalls_by_layer']),
]


def run(db, items, collection, k, mode, run_id=None, allow_network=False):
    ok = 0
    for q, expect in items:
        hits = search(db, q, collection, k if collection == 'methods' else k * 3, mode, None,
                      to_english(q, allow_network=allow_network) if collection == 'cases' else '',
                      run_id=run_id, allow_network=allow_network)
        top = []
        for _, r in hits:
            top.append(r['title'] + ' ' + r['source_locator'])
            if len(top) >= k:
                break
        good = any(any(e.lower() in t.lower() for e in expect) for t in top)
        ok += good
        print('%s  %s\n      -> %s' % ('PASS' if good else 'MISS', q, ' | '.join(t.split(' ')[0][:40] for t in top[:3])))
    print('%s: %d/%d within top %d (%s)\n' % (collection, ok, len(items), k, mode))
    return ok


def integrity(db, run_id):
    """Full-table contracts and immutable evidence, independent of question relevance."""
    from build import validate
    run = db.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()
    if not run:
        raise ValueError('Run not found: ' + str(run_id))
    states = {c: component_status(db, run_id, c) for c in REQUIRED_COMPONENTS if c != 'acceptance'}
    if any(s != 'ready' for s in states.values()):
        raise ValueError('Incomplete keyword components: ' + json.dumps(states))
    checks = validate(db, run_id)
    method_detail = db.execute("SELECT details_json FROM run_components WHERE run_id=? AND component='methods'", (run_id,)).fetchone()
    method_detail = json.loads(method_detail[0])
    verify_snapshot(method_detail.get('sources', {}))
    snapshot = source_snapshot(db, run_id, run['source_directory'])
    verify_snapshot(snapshot)
    for src in db.execute('SELECT * FROM run_sources WHERE run_id=?', (run_id,)):
        if artifact_digest(src['actual_path']) != src['sha256']:
            raise ValueError('Imported artifact changed: ' + src['logical_path'])
    expected_profiles = db.execute("SELECT COUNT(*) FROM case_groups WHERE run_id=? AND (name<>'' OR dd>=2)", (run_id,)).fetchone()[0]
    profiles = db.execute("SELECT COUNT(*) FROM text_records WHERE run_id=? AND collection='cases'", (run_id,)).fetchone()[0]
    if profiles != expected_profiles:
        raise ValueError('Incomplete case profiles: %d/%d' % (profiles, expected_profiles))
    edge_count = db.execute('SELECT COUNT(*) FROM citation_edges WHERE run_id=?', (run_id,)).fetchone()[0]
    passages = db.execute("SELECT COUNT(*) FROM edge_passages WHERE run_id=? AND trim(passage)<>''", (run_id,)).fetchone()[0]
    if edge_count != passages:
        raise ValueError('Incomplete edge evidence passages: %d/%d' % (passages, edge_count))
    relations = db.execute('SELECT COUNT(*) FROM edge_relations WHERE run_id=?', (run_id,)).fetchone()[0]
    if relations != edge_count:
        raise ValueError('Incomplete edge relations')
    for table, key in [('edge_passages', 'resolved_cited_case'), ('profile_passages', 'group_id')]:
        bad = db.execute('''SELECT COUNT(*) FROM %s p WHERE run_id=? AND
            (NOT json_valid(evidence_json) OR json_extract(evidence_json,'$.corpus.logical_path') IS NULL
             OR json_extract(evidence_json,'$.mentions.logical_path') IS NULL
             OR NOT EXISTS(SELECT 1 FROM documents d WHERE d.run_id=p.run_id AND d.source_id=p.source_decision
                AND d.court=json_extract(p.evidence_json,'$.court')
                AND d.corpus_row=json_extract(p.evidence_json,'$.corpus_row'))
             OR NOT EXISTS(SELECT 1 FROM citation_edges e WHERE e.run_id=p.run_id AND e.source_decision=p.source_decision
                AND e.resolved_cited_case=p.%s)
             OR NOT EXISTS(SELECT 1 FROM run_sources s WHERE s.run_id=p.run_id
                AND s.logical_path=json_extract(p.evidence_json,'$.corpus.logical_path'))
             OR NOT EXISTS(SELECT 1 FROM run_sources s WHERE s.run_id=p.run_id
                AND s.logical_path=json_extract(p.evidence_json,'$.mentions.logical_path')))
             ''' % (table, key), (run_id,)).fetchone()[0]
        if bad:
            raise ValueError('Untraceable %s evidence: %d' % (table, bad))
    methods = db.execute("SELECT COUNT(*) FROM text_records WHERE collection='methods'").fetchone()[0]
    if not methods:
        raise ValueError('Method keyword collection is empty')
    if methods != method_detail.get('records'):
        raise ValueError('Method chunks were lost or overwritten: %d/%s' % (methods, method_detail.get('records')))
    # rank=1 checks the external-content index against the stored content, not just its internal tree.
    db.execute("INSERT INTO text_fts(text_fts,rank) VALUES('integrity-check',1)")
    db.execute("INSERT INTO edge_fts(edge_fts,rank) VALUES('integrity-check',1)")
    return {'run_id': run_id, 'status': 'passed', 'scope': 'keyword_integrity_not_semantic_accuracy',
            'checks': checks, 'profiles': profiles, 'edge_passages': passages, 'methods': methods,
            'components': states, 'vectors': {c: component_status(db, run_id, 'vectors_'+c)
                                             for c in ('cases', 'methods', 'edges')}}


def accept_run(db_path, run_id, publish=True):
    db = connect(db_path)
    generation = start_component(db, run_id, 'acceptance')
    try:
        with db:
            report = integrity(db, run_id)
            finish_component(db, run_id, 'acceptance', generation, details=report)
            if publish:
                publish_run(db, run_id)
            report['published'] = publish
        return report
    except Exception as exc:
        fail_component(db, run_id, 'acceptance', generation, exc)
        raise
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(); p.add_argument('-k', type=int, default=5)
    p.add_argument('--mode', default='keyword', choices=['hybrid', 'vector', 'keyword'])
    p.add_argument('--db', default=str(DEFAULT_DB))
    p.add_argument('--run')
    p.add_argument('--suite', choices=['integrity', 'benchmark', 'all'], default='all')
    p.add_argument('--publish', action='store_true', help='publish after integrity suite passes')
    p.add_argument('--allow-network', action='store_true')
    p.add_argument('--output')
    a = p.parse_args()
    db = connect(a.db, readonly=True)
    try:
        r = db.execute('SELECT run_id FROM runs ORDER BY imported_at DESC LIMIT 1').fetchone()
        run_id = a.run or (r[0] if r else None)
    finally:
        db.close()
    report = {'run_id': run_id}
    if a.suite in ('integrity', 'all'):
        report['integrity'] = accept_run(a.db, run_id, publish=a.publish and a.suite == 'integrity')
    passed = True
    if a.suite in ('benchmark', 'all'):
        db = connect(a.db, readonly=True)
        try:
            if a.mode in ('hybrid', 'vector'):
                load_vec(db)
            sets = [(CASES, 'cases'), (METHODS, 'methods'), (EXTENSION, 'methods')]
            report['benchmark'] = []
            for items, col in sets:
                count = run(db, items, col, a.k, a.mode, run_id, a.allow_network)
                report['benchmark'].append({'collection': col, 'passed': count, 'total': len(items)})
                passed = passed and count == len(items)
        finally:
            db.close()
        if passed and a.publish:
            report['integrity'] = accept_run(a.db, run_id, publish=True)
    if a.output:
        dump(a.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
