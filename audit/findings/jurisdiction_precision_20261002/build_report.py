"""Create the bounded, source-backed native report from approved review records."""
import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
generated_at = datetime.now(timezone.utc).isoformat()
review = json.loads((HERE / 'final_review.json').read_text(encoding='utf-8'))
checks = json.loads((HERE / 'verification.json').read_text(encoding='utf-8'))
with (HERE / 'no_evidence_targets.csv').open(encoding='utf-8-sig', newline='') as f:
    targets = {r['normalized_key']: r for r in csv.DictReader(f)}

partial_notes = {
    'a': '只确认 Atlantic Reporter 的缩写身份；地域覆盖待核。',
    'br': '确认魁北克汇编身份；法院括注与汇编用法仍需区分。',
    'ltns': '确认 Law Times Reports New Series 身份；地域覆盖待核。',
    'nw': '确认 Northwestern Reporter 身份；地域覆盖待核。',
    'p': '英国 Probate 元数据获准；美国 Pacific 仅身份支持，保留两读。',
    'hl': '仅核到 Law Reports House of Lords；其他含义与法院用法待分。',
    'pc': '确认 Privy Council 汇编身份；法院用法和案件来源需另查。',
}
withheld_notes = {
    'ontlr': 'O.R./OLR 不能替代精确 Ont.L.R. 别名证据。',
    'ontappr': '未取得精确 Ont.App.R. 权威记录。',
    'bcrep': '精确加拿大读法未核；Cardiff 另有英国同形，需逐案消歧。',
    'gr': '裸 Gr. 未取得精确对应 Grant 汇编的证据。',
    'nzlr': '本轮未打开精确 N.Z.L.R. 权威记录。',
    'rl': '精确 R.L. 与 Revue légale 对应待核。',
    'timeslr': 'TLR 不能独自证明 Times L.R. 是同一别名。',
    'nsrep': 'N.S.Rep. 的精确别名与新辑歧义待核。',
    'usr': 'U.S. 的证据未证明精确 U.S.R. 别名。',
    'rdj': '采集标题与原表 Revue de droit judiciaire 不同，拒绝替换。',
    'tt': 'T.T. 的精确含义与汇编角色待核。',
    'mass': '6.1 独立访问官方页面受阻；本轮暂缓完整审批。',
    'nbrep': '6.1 独立读取精确记录失败；不以搜索摘要批准。',
    'ae': '采集标题与原表 Adolphus & Ellis 不同；精确 A.&E. 待核。',
    'car': '采集标题与原表 Criminal Appeal Reports 不同；精确含义待核。',
    'cancrcas': 'CCC 不能独自证明历史 Can.Cr.Cas. 别名。',
    'grant': '裸 Grant 未核实；不采用无关 Russell 汇编替代。',
    'sc': '保留英国/魁北克同形；未逐行取得精确证据。',
}
status_labels = {'approved': '批准元数据', 'partial': '部分支持', 'withheld': '暂缓'}
rows = []
for d in review['abbreviation_decisions']:
    t = targets[d['normalized_key']]
    status = d['status']
    note = '批准列明的汇编身份与表列法域；不证明逐案来源或独占范围。'
    if status == 'partial':
        note = partial_notes[d['normalized_key']]
    elif status == 'withheld':
        note = withheld_notes[d['normalized_key']]
    rows.append({'abbreviation': d['abbreviation'], 'normalized_key': d['normalized_key'],
                 'table_jurisdiction': t['table_jurisdiction'], 'corpus_rows': int(t['corpus_rows']),
                 'decision': status_labels[status], 'approved_scope': note,
                 'sources': ' | '.join(d['source_urls']), 'source_count': len(d['source_urls']),
                 'rank': len(rows) + 1})
rows.sort(key=lambda r: (-r['corpus_rows'], r['rank']))
directions = [
    {'direction': 1, 'subject': '50 个缺证缩写', 'decision': '部分批准',
     'result': '25 批准元数据、7 部分支持、18 暂缓。',
     'boundary': '全部 50 项已审；不将外部目录核验计为新增语料证据或案件来源确认。'},
    {'direction': 2, 'subject': 'Nfld. & P.E.I.R.', 'decision': '部分批准',
     'result': '批准外部标题身份；保留 NL、PE 两行。',
     'boundary': '279 条直接样本分为 NL 227、PE 52；完整地域覆盖和每案所属省未核实。'},
    {'direction': 3, 'subject': 'Que. K.B. / Sask. L.R.', 'decision': '部分批准',
     'result': 'Que. K.B. 的 QC 元数据获准；Sask. L.R. 只核到标题/加拿大层。',
     'boundary': '拒绝用传播的 GB 信号改 QC/SK；9+4 个混合证据尚未逐案追踪，不能全部宣布已解释。'},
    {'direction': 4, 'subject': 'S.J. 同形修复', 'decision': '附条件保留',
     'result': '保留今天已有的 SK/GB 结构分流；批准英国期刊元数据。',
     'boundary': '999 是技术边界；3 个年份误作卷号读法保持 UNSUPPORTED。SK 原核验记录保留，6.1 重访 Emond 受阻。'},
]
# Execute the report's real joined source query; preserve import provenance.
db = sqlite3.connect(HERE / 'evidence.sqlite')
db.row_factory = sqlite3.Row
db.execute('DROP TABLE IF EXISTS six_channel_summary')
db.execute('DROP TABLE IF EXISTS approval_decisions')
db.execute('DROP TABLE IF EXISTS direction_decisions')
with (HERE.parents[0] / 'jurisdiction_channels' / 'summary.csv').open(encoding='utf-8-sig', newline='') as f:
    original_summary = list(csv.DictReader(f))
summary_fields = list(original_summary[0])
db.execute('CREATE TABLE six_channel_summary (' + ','.join('"' + k + '" TEXT' for k in summary_fields) + ')')
db.executemany('INSERT INTO six_channel_summary VALUES (' + ','.join('?' for _ in summary_fields) + ')',
               [[r[k] for k in summary_fields] for r in original_summary])
row_fields = list(rows[0])
db.execute('CREATE TABLE approval_decisions (' + ','.join('"' + k + '" ' + ('INTEGER' if k in ('corpus_rows','source_count','rank') else 'TEXT') for k in row_fields) + ')')
db.executemany('INSERT INTO approval_decisions VALUES (' + ','.join('?' for _ in row_fields) + ')',
               [[r[k] for k in row_fields] for r in rows])
direction_fields = list(directions[0])
db.execute('CREATE TABLE direction_decisions (' + ','.join('"' + k + '" ' + ('INTEGER' if k == 'direction' else 'TEXT') for k in direction_fields) + ')')
db.executemany('INSERT INTO direction_decisions VALUES (' + ','.join('?' for _ in direction_fields) + ')',
               [[r[k] for k in direction_fields] for r in directions])
all_sql = """SELECT s.abbreviation, s.normalized_key, s.table_jurisdiction,
       CAST(s.corpus_rows AS INTEGER) AS corpus_rows,
       a.decision, a.approved_scope, a.sources, a.source_count, a.rank
FROM main.six_channel_summary AS s
JOIN main.approval_decisions AS a ON a.normalized_key = s.normalized_key
WHERE s.status = '无证据'
ORDER BY CAST(s.corpus_rows AS INTEGER) DESC, a.rank ASC"""
top_sql = all_sql + '\nLIMIT 10'
directions_sql = 'SELECT direction, subject, decision, result, boundary FROM main.direction_decisions ORDER BY direction ASC'
queried = [dict(r) for r in db.execute(all_sql)]
assert queried == rows
top_rows = [dict(r) for r in db.execute(top_sql)]
assert top_rows == rows[:10]
assert [dict(r) for r in db.execute(directions_sql)] == directions
db.commit()
db.close()
summary = dict(checks['approval_counts'])
summary['weighted_rows'] = checks['original_registered_weight_by_status']
summary['all_target_registered_rows'] = checks['original_no_evidence_weight_total']
summary['approved_share_of_target_weight'] = summary['weighted_rows']['approved'] / summary['all_target_registered_rows']
summary['changed_metadata_rows'] = checks['changed_metadata_rows']
(HERE / 'analysis_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
with (HERE / 'approval_ledger.csv').open('w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

prefix = 'audit/findings/jurisdiction_precision_20261002/'
sources = [
    {'id': 'baseline', 'label': '六渠道 summary.csv：原登记权重',
     'path': prefix + 'evidence.sqlite',
     'query': {'engine': 'SQLite', 'language': 'sql', 'sql': top_sql,
               'description': '原六渠道summary.csv导入main.six_channel_summary，与逐项审批联接；仅取无证据项目，按登记行数排序取头部十项。',
               'tables_used': ['main.six_channel_summary', 'main.approval_decisions', 'audit/findings/jurisdiction_channels/summary.csv'],
               'filters': ['status = 无证据；原登记语料行数；未重新计数'],
               'metric_definitions': ['corpus_rows = 原表登记语料行数；同归一键只计一次。']}},
    {'id': 'review', 'label': '6.1 medium 四方向独立审批与逐项来源', 'path': prefix + 'final_review.json',
     'query': {'engine': 'SQLite', 'language': 'sql', 'sql': directions_sql,
               'tables_used': ['main.direction_decisions'], 'description': '四方向审阅结论整理为完整表格；原始判断、支持和限制见final_review.json。'}},
    {'id': 'checks', 'label': '表格变更、分类重放与单元验证', 'path': prefix + 'verification.json'},
    {'id': 'special', 'label': 'Luna medium 三个特殊方向资料与来源', 'path': prefix + 'collection_special.json'},
    {'id': 'ledger', 'label': '逐项审批账本：权重、批准范围与来源链接', 'path': prefix + 'approval_ledger.csv',
     'query': {'engine': 'SQLite', 'language': 'sql', 'sql': all_sql,
               'description': '按归一键联接原summary.csv登记权重与6.1逐项判定；全部50项，无抽样。',
               'tables_used': ['main.six_channel_summary', 'main.approval_decisions', prefix + 'final_review.json', 'audit/findings/jurisdiction_channels/summary.csv'],
               'metric_definitions': ['状态数量按50个不同normalized_key计；引用权重为原登记值，不是当前全库计数。']}},
]
seen = set()
for c in review['reviewer_checks']:
    url = c.get('url', '')
    if not url or url in seen:
        continue
    seen.add(url)
    sources.append({'id': 'authority_' + str(len(seen)), 'label': c.get('claim_checked', url), 'href': url,
                    'query': {'description': c.get('result', '')}})

title = '汇编法域四方向审批'
blocks = [
    {'id': 'title', 'type': 'markdown', 'body': '# ' + title},
    {'id': 'summary', 'type': 'markdown', 'body': '## Executive Summary\n\n**四个方向已由 gpt-6.1-sol／medium 审批，资料由三路 gpt-6-luna／medium 收集。** 50 个缺证缩写中，25 个批准汇编元数据、7 个部分支持、18 个暂缓。\n\n**特殊项分别保留不同限制。** 联合汇编保留两省候选；混合项不能据 GB 信号改表；S.J. 保留已有分流，并注明技术边界。\n\n**获准记录已经应用。** 本轮更新 ' + str(checks['changed_metadata_rows']) + ' 行证据元数据。审批是用户授权的代理审核，不能称为人工逐条复核，也不证明具体案件来源。'},
    {'id': 'definitions', 'type': 'markdown', 'body': '## 审批范围与计数口径\n\n“批准元数据”指权威资料支持列明的汇编身份和表列法域；“部分支持”只批准标题、国家层级或某一种用法；“暂缓”表示证据缺口，不等于原表错误。\n\n原“无证据”状态包括不足10条语料证据的项目。本轮50项的登记引用权重合计28,320；这来自旧登记值，未重新抽取全库。获准25项对应21,312，约占本批权重75.3%。该比例只描述本批外部元数据审批覆盖。', 'sourceId': 'ledger'},
    {'id': 'direction_heading', 'type': 'markdown', 'body': '## 四个方向的判断与应用边界\n\n每个方向都完成判断；“部分批准”意味着支持范围写明，尚未证实的部分继续保留。'},
    {'id': 'directions', 'type': 'table', 'tableId': 'direction_decisions'},
    {'id': 'priority', 'type': 'markdown', 'body': '## 缺证缩写的引用权重集中在头部\n\n头部项目补到精确外部来源，对核验覆盖的贡献较大；图中显示的是本轮开始时的登记权重。获准状态、具体支持范围和精确来源可在下方账本核对。', 'sourceId': 'baseline'},
    {'id': 'volume', 'type': 'chart', 'chartId': 'top_targets'},
    {'id': 'ledger_heading', 'type': 'markdown', 'body': '## 50 个缩写的逐项审批\n\n账本完整列出25项批准、7项部分支持、18项暂缓。近似拼写或相关标题不能替代精确别名证据；裸 H.L./P.C. 等还需要区分汇编和法院括注。', 'sourceId': 'review'},
    {'id': 'ledger_table', 'type': 'table', 'tableId': 'all_targets'},
    {'id': 'corrections', 'type': 'markdown', 'body': '## 独立审核纠正了采集中的标题替换\n\nC.B.N.S. 曾被误配为加拿大破产汇编；[JustCite 引证格式表](https://www.justcite.com/kb/search-technology/english-reports-reference-formats/)支持其为英国 Common Bench New Series。R.D.J.、A.&E.、C.A.R. 的采集标题与原表不同，相关替换均未获准。\n\nB.C.Rep. 另有英国汇编同形记录，原加拿大读法尚需具体引证核验；本轮保留待核实。', 'sourceId': 'review'},
    {'id': 'applied', 'type': 'markdown', 'body': '## 证据更新已通过字段与分类核对\n\n表仍为197行。本轮只更新核验标签、来源、定位和说明，保留原语料权重出处。所有分类消费字段，包括 confidence、法域、归一键和区间，逐项保持一致。\n\n' + str(checks['classifier_probes_identical']) + ' 个分类探针的更新前后输出完全相同；124条可运行的单元断言通过。S.J. 的无卷号SK、真实卷号GB、年份误作卷号UNSUPPORTED三种读法均符合现有规则。', 'sourceId': 'checks'},
    {'id': 'next', 'type': 'markdown', 'body': '## 下一步优先处理明确缺口\n\n1. 为暂缓的精确历史别名补到原始记录，优先 Ont.L.R.、Ont.App.R.、B.C.Rep. 等较高权重项目。\n2. 找到混合证据的原始引证串，逐案核对两个汇编的9条与4条信号。\n3. 如需改变 confidence 或生产推断规则，另做适配该变化的分类与全流程验证。'},
    {'id': 'questions', 'type': 'markdown', 'body': '## 仍需解决的问题\n\n联合汇编的权威完整收录范围尚未取得；混合项没有全部逐案追踪；部分法院标记和历史汇编同形未分开；S.J. 的999上限没有历史依据。这些缺口已经写入审批记录。'},
    {'id': 'caveats', 'type': 'markdown', 'body': '## 验证限制与假设\n\n本轮没有重跑生产全流程，也没有把外部元数据核验改记为新增语料证据。完整迷你链在修改前因 select.py 缺少 PyYAML 而失败；124条单元断言和分类重放不能替代全流程验收。\n\nEmond 和部分官方页面在6.1独立重访时受阻，未据搜索摘要进行完整升级；原SK核验记录保留。目录、汇编法域、审理法院与具体案件来源分别记录。', 'sourceId': 'checks'},
]
artifact = {
    'surface': 'report',
    'manifest': {'version': 1, 'surface': 'report', 'title': title, 'description': '2026年10月2日 · Luna 收集／6.1 medium 审批 · 四方向结果及证据应用',
                 'generatedAt': generated_at, 'blocks': blocks, 'sources': sources,
                 'charts': [{'id': 'top_targets', 'title': '缺证缩写头部十项的登记引用量',
                             'subtitle': '补证优先级集中在头部；单位为原登记语料行，未重新计数',
                             'type': 'bar', 'dataset': 'top_targets', 'sourceId': 'baseline',
                             'encodings': {'x': {'field': 'abbreviation', 'type': 'nominal'},
                                           'y': {'field': 'corpus_rows', 'type': 'quantitative', 'format': 'number'},
                                           'tooltip': [{'field': 'table_jurisdiction'}, {'field': 'decision'}, {'field': 'approved_scope'}]},
                             'settings': {'orientation': 'horizontal', 'sort': 'descending', 'showValues': True},
                             'palette': {'kind': 'sequential', 'name': 'blue'},
                             'layout': 'full', 'valueFormat': 'number', 'maxRows': 10}],
                 'tables': [
                     {'id': 'direction_decisions', 'title': '四方向审批结果', 'dataset': 'directions', 'sourceId': 'review',
                      'defaultSort': {'field': 'direction', 'direction': 'asc'}, 'layout': 'full',
                      'columns': [{'field': k, 'label': label} for k, label in [('direction','方向'),('subject','对象'),('decision','结论'),('result','批准结果'),('boundary','限制')]]},
                     {'id': 'all_targets', 'title': '50项逐项审批账本', 'dataset': 'all_targets', 'sourceId': 'ledger',
                      'defaultSort': {'field': 'corpus_rows', 'direction': 'desc'}, 'layout': 'full',
                      'columns': [dict({'field': k, 'label': label}, **({'format': 'number'} if k == 'corpus_rows' else {'type': 'text'})) for k, label in [('abbreviation','缩写'),('table_jurisdiction','原表法域'),('corpus_rows','登记行数'),('decision','审批'),('approved_scope','支持范围／缺口'),('sources','来源链接')]]}
                 ]},
    'snapshot': {'version': 1, 'status': 'ready', 'generatedAt': generated_at,
                 'datasets': {'top_targets': top_rows, 'all_targets': queried, 'directions': directions}},
    'sources': sources,
}
(HERE / 'artifact.json').write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'artifact': str(HERE / 'artifact.json'), 'blocks': len(blocks), 'sources': len(sources), 'rows': len(rows)}, ensure_ascii=False))
