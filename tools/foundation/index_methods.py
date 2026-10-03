"""Index the project's methods by layer, so that adding a jurisdiction or a court starts from what
already works (and what already failed) instead of from scratch.

Sources (all committed files; PROBLEMS.md is NOT read here - its history stays in tools/recall, see #101):
  pipeline/*.py        every module/function/class with its docstring and code  -> status in_effect
  decisions/README.md  + one record per decision table (header, row count, sample rows) -> status table
  docs/*.md            chunks by heading                                         -> status reference
  implementation/*.md  plans and their outcomes, chunks by heading               -> status plan
  audit/**/*.md        experiment reports and findings                            -> status experiment
Layer: by file for code and tables; by keyword vote for prose (unknown when no layer wins).
Each record keeps file:line and the git commit it was indexed at.
"""
import argparse
import ast
import csv
import json
import re
import subprocess
from pathlib import Path
from common import ROOT, DEFAULT_DB, connect, upsert_text, rebuild_fts

CODE_LAYER = {'extract': 'extraction', 'shapes': 'extraction', 'normalize': 'extraction',
              'classify': 'classification', 'merge': 'merging', 'decide': 'adjudication',
              'registry': 'adjudication', 'registry_report': 'adjudication', 'select': 'selection',
              'edges': 'edges', 'run_all': 'orchestration', 'traceback': 'orchestration',
              'coverage_report': 'orchestration'}
TABLE_LAYER = {'reporter_jurisdiction': 'classification', 'court_designations': 'classification',
               'identifier_systems': 'classification', 'neutral_court_codes': 'classification',
               'series_prefix': 'classification', 'bilingual_neutral_codes': 'classification',
               'case_origin': 'adjudication', 'case_origin_manual': 'adjudication',
               'reporter_origin_scope': 'adjudication', 'court_or_reporter_scope': 'adjudication'}
KEYWORDS = {
    'extraction': ['抽取', 'extract', 'regex', '正则', 'shape', '形状', 'span', '捕获'],
    'classification': ['分类', 'classif', '法域', 'jurisdiction', '缩写', 'abbreviation', 'reporter', '汇编', '同形'],
    'merging': ['归并', 'merge', 'merging', '折叠', 'fold', '案名多数', 'variant'],
    'adjudication': ['裁定', 'adjudicat', 'decide', 'case_origin', '来源', 'origin', '枢密院', 'identity', '身份'],
    'selection': ['选择层', 'select', '门槛', 'threshold', 'kept', 'distinct_decisions', ' DD', 'dd≥'],
}
CARD_LAYER = {'README': 'all', '00_new_court_playbook': 'all', '01_extraction': 'extraction',
              '02_classification': 'classification', '03_merging': 'merging', '04_adjudication': 'adjudication',
              '05_selection_and_edges': 'selection', '06_decision_tables': 'decision_tables',
              '07_verification_gates': 'verification', '08_pitfalls_by_layer': 'pitfalls'}
MAX = 1800


def git_head():
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, text=True).strip()
    except Exception:
        return 'unknown'


def vote_layer(text):
    t = text.lower()
    score = {k: sum(t.count(w.lower()) for w in ws) for k, ws in KEYWORDS.items()}
    best = max(score, key=score.get)
    ranked = sorted(score.values(), reverse=True)
    return best if ranked[0] >= 2 and ranked[0] > ranked[1] else 'unknown'


def md_chunks(path):
    text = path.read_text(encoding='utf-8', errors='ignore')
    lines = text.split('\n')
    heads = [i for i, l in enumerate(lines) if re.match(r'#{1,4} ', l)] or [0]
    if heads[0] != 0:
        heads = [0] + heads
    for a, b in zip(heads, heads[1:] + [len(lines)]):
        body = '\n'.join(lines[a:b]).strip()
        title = lines[a].lstrip('# ').strip() if lines[a].startswith('#') else path.stem
        for k in range(0, len(body), MAX):
            part = body[k:k + MAX]
            if len(part.strip()) > 80:
                yield title, part, a + 1


def code_chunks(path):
    src = path.read_text(encoding='utf-8')
    lines = src.split('\n')
    tree = ast.parse(src)
    doc = ast.get_docstring(tree)
    if doc:
        yield path.stem + ' (module)', doc[:MAX * 2], 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            body = '\n'.join(lines[node.lineno - 1: node.end_lineno])
            d = ast.get_docstring(node) or ''
            text = (d + '\n---\n' if d else '') + body
            if len(text.strip()) > 120:
                yield '%s.%s' % (path.stem, node.name), text[:MAX], node.lineno


def table_records(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    if not rows:
        return
    head, data = rows[0], rows[1:]
    sample = '\n'.join(', '.join(r)[:200] for r in data[:12])
    yield path.stem, 'Decision table %s: %d rows. Columns: %s\nSample rows:\n%s' % (
        path.name, len(data), ', '.join(head), sample), 1


def build(db_path=DEFAULT_DB):
    head = git_head()
    recs = []
    for p in sorted((ROOT / 'pipeline').glob('*.py')):
        for title, text, line in code_chunks(p):
            recs.append((title, text, CODE_LAYER.get(p.stem, 'unknown'), 'in_effect', p, line))
    for p in sorted((ROOT / 'decisions').glob('*.csv')):
        for title, text, line in table_records(p):
            recs.append((title, text, TABLE_LAYER.get(p.stem, 'unknown'), 'table', p, line))
    sources = [(ROOT / 'decisions' / 'README.md', 'table')] + \
              [(p, 'reference') for p in sorted((ROOT / 'docs').glob('*.md'))] + \
              [(p, 'plan') for p in sorted((ROOT / 'implementation').glob('*.md'))] + \
              [(p, 'experiment') for p in sorted((ROOT / 'audit').rglob('*.md'))]
    for p, status in sources:
        if not p.exists() or p.name == 'PROBLEMS.md':
            continue
        for title, text, line in md_chunks(p):
            recs.append(('%s — %s' % (p.stem, title), text, vote_layer(text), status, p, line))
    # Method cards (docs/method_cards): hand-written, one per layer; the layer comes from the card, not a keyword vote
    for p in sorted((ROOT / 'docs' / 'method_cards').glob('*.md')):
        h1 = next((l.lstrip('# ').strip() for l in p.read_text(encoding='utf-8').splitlines() if l.startswith('# ')), p.stem)
        for title, text, line in md_chunks(p):
            # every chunk carries the card's own subject, so a section like "流程（按顺序）" still says what it is about
            # README is the card index (routing table), not an answer: it must not take a reserved card slot
            recs.append(('method_card:%s（%s）— %s' % (p.stem, h1, title), text, CARD_LAYER.get(p.stem, 'unknown'),
                         'reference' if p.stem == 'README' else 'method_card', p, line))
    db = connect(db_path)
    try:
        with db:
            db.execute("DELETE FROM text_records WHERE collection='methods'")
            for title, text, layer, status, p, line in recs:
                rel = p.relative_to(ROOT).as_posix()
                upsert_text(db, 'methods', '%s:%d:%s' % (rel, line, title[:60]), layer, status, title,
                            text, '%s:%d @ %s' % (rel, line, head))
            rebuild_fts(db)
        by = {}
        for _, _, layer, status, _, _ in recs:
            by.setdefault(layer, 0)
            by[layer] += 1
        return {'records': len(recs), 'by_layer': by, 'commit': head}
    finally:
        db.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--db', default=str(DEFAULT_DB))
    a = p.parse_args()
    print(json.dumps(build(a.db), ensure_ascii=False, indent=2))
