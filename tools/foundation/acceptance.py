"""Fixed real questions for accepting the retrieval layer. A question passes when an expected hit is
in the top K. Re-run after every index rebuild; numbers go into the report, not into any pipeline step.

    python tools/foundation/acceptance.py            # both collections, hybrid
    python tools/foundation/acceptance.py --mode keyword
"""
import argparse
import sys
from common import DEFAULT_DB, connect
from embed import load_vec
from query import search, latest_run

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
    ('S.J. 同形缩写 按卷号区间消歧', ['reporter_jurisdiction', 'classify']),
    ('跨年份 年份写成两段 year_raw', ['extract', 'shapes']),
    ('枢密院 对加拿大上诉 案件来源 与汇编法域不同', ['decide', 'case_origin']),
    ('DD 门槛 只打标记 不删除行 kept', ['select']),
    ('案名多数投票 归并 变体折叠', ['merge']),
    ('中立引证 法院代码 表', ['neutral_court_codes', 'identifier_systems']),
    ('自引 排除 判决自身头部引证', ['decide', 'self']),
    ('CanLII 对照 法院时期分层抽样', ['canlii', 'crosscheck']),
    ('双语中立引证 英法对应', ['bilingual_neutral_codes']),
    ('方括号法院标注 court designation 识别', ['court_designations', 'designation']),
    ('distinct_decisions_count 并集 不是 max', ['merge', 'select', 'distinct']),
    ('抽取层禁止固定缩写表 按结构形状匹配', ['extract', 'shapes', '技术规格']),
]


def run(db, items, collection, k, mode):
    ok = 0
    for q, expect in items:
        hits = search(db, q, collection, k * 3, mode)
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


def main():
    p = argparse.ArgumentParser(); p.add_argument('-k', type=int, default=5)
    p.add_argument('--mode', default='hybrid', choices=['hybrid', 'vector', 'keyword'])
    p.add_argument('--db', default=str(DEFAULT_DB))
    a = p.parse_args()
    db = connect(a.db, readonly=True)
    load_vec(db)
    run(db, CASES, 'cases', a.k, a.mode)
    run(db, METHODS, 'methods', a.k, a.mode)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()
