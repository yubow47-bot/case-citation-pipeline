"""Small, offline HTML viewer for experimental citation-context artifacts.

Corpus strings are escaped before insertion. JavaScript contains no input data,
uses textContent for search, and never evaluates source text or inserts HTML.
Snippets are bounded for display; original offsets refer to the source artifact.
"""
from __future__ import annotations

from collections import defaultdict
from html import escape
import hashlib
import json


_LABELS = {
    "applied": "适用", "followed": "遵循", "adopted": "采纳",
    "distinguished": "区分", "criticized": "批评", "overruled": "推翻先例",
    "considered": "考虑", "discussed": "讨论", "mentioned": "提及",
    "affirmed": "维持（程序）", "reversed": "撤销（程序）",
}
_STATUSES = {"suggested": "词语建议", "context_required": "需结合语境复核",
             "ambiguous": "有歧义", "resolved": "已链接（机器）",
             "unresolved": "未解析", "blocked": "被阻断", "full": "完整引文", "short": "短引文", "case_name": "案名提及"}
_METRICS = {"document_rows": "文档行", "source_judgments": "来源判决",
            "full_linked_mentions": "已链接完整引文", "full_unlinked_barriers": "未链接完整引文",
            "short_references": "短引文", "observations": "词语信号",
            "short_resolved": "短引已链接（机器）", "case_name_resolved": "案名已链接（机器）",
            "case_name_mentions": "案名提及", "edges_with_suggestions": "带处理建议的边",
            "quoted_short_references": "引号范围内短引", "quoted_short_resolved": "引号内已链接（机器）",
            "observations_with_context_owner": "有明确引述来源的观察",
            "edges_with_procedural_signals": "带程序信号的边",
            "document_target_edges": "文档目标组", "new_production_edges": "新增生产边"}
_SPEAKERS = {"current_court": "本院的明确表述", "party": "当事人主张", "reported_court": "转述法院",
             "reported_judge": "转述法官", "reported_actor": "转述其他发言者", "reported_case": "转述案例", "unknown": "归属未明"}


def _plain(value):
    if value is None:
        return "—"
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return str(value)


def _h(value):
    return escape(_plain(value), quote=True)


def _snippet(value, limit=1000):
    value = _plain(value)
    return _h(value[:limit]) + (" … [显示已截短]" if len(value) > limit else "")


def _items(values, limit=800):
    if not values:
        return "—"
    if isinstance(values, str):
        return _snippet(values, limit)
    return _snippet(" · ".join(_plain(value) for value in values), limit)


def _status(value):
    return _h(_STATUSES.get(value, value))


def _mention_anchor(mention_id):
    return "mention-" + hashlib.sha256(_plain(mention_id).encode("utf-8")).hexdigest()[:20]


def _antecedents(values):
    if not values:
        return "—"
    return " · ".join('<a href="#' + _mention_anchor(value) + '">' + _h(value) + '</a>' for value in values)


def _observation_links(values):
    return " · ".join('<a href="#' + _h(value) + '">' + _h(value) + '</a>' for value in values) if values else "—"


def _edge_link(record):
    target = _h(record.get("target_group_id"))
    return '<a href="#' + _h(record["edge_id"]) + '">' + target + '</a>' if record.get("edge_id") else target


def _scope_view(scope):
    if not scope:
        return "未检测到引号范围"
    state = "边界存疑" if scope.get("uncertain") else "闭合引号"
    return state + " " + _h(scope.get("start")) + "–" + _h(scope.get("end")) + " · " + _h(scope.get("boundary_reason"))


def _speaker_view(observation):
    label = _SPEAKERS.get(observation.get("speaker_attribution"), observation.get("speaker_attribution", "归属未明"))
    evidence = observation.get("speaker_evidence", [])
    excerpts = " · ".join(_snippet(e.get("raw"), 200) + " [" + _h(e.get("start")) + "–" + _h(e.get("end")) + "]" for e in evidence)
    return _h(label) + ("<br>" + excerpts if excerpts else "")


def _owner_view(observation):
    target = observation.get("context_owner_group_id")
    if not target:
        candidates = observation.get("context_owner_candidate_target_ids")
        return "未确定" + ("；来源候选：" + _items(candidates) + "<br>来源提及：" + _antecedents(observation.get("context_owner_mention_ids")) if candidates else "")
    edge = observation.get("context_owner_edge_id")
    label = '<a href="#' + _h(edge) + '">' + _h(target) + '</a>' if edge else _h(target)
    return label + "<br>来源提及：" + _antecedents(observation.get("context_owner_mention_ids"))


def _label(value):
    return _h(_LABELS.get(value, value)) + " <small>" + _h(value) + "</small>"


def _labels(values):
    return " / ".join(_label(value) for value in values) if values else "—"


def _evidence(observation):
    evidence = _plain(observation.get("evidence_text", ""))
    base = observation.get("evidence_start", 0)
    signal_start, signal_end = observation.get("signal_start"), observation.get("signal_end")
    relative = signal_start - base if isinstance(signal_start, int) and isinstance(base, int) else 0
    length = signal_end - signal_start if isinstance(signal_start, int) and isinstance(signal_end, int) else 0
    left = max(0, relative - 500) if len(evidence) > 1500 else 0
    right = min(len(evidence), left + 1500)
    if 0 <= relative < relative + length <= len(evidence) and left <= relative < right:
        end = min(relative + length, right)
        result = _h(evidence[left:relative]) + "<mark>" + _h(evidence[relative:end]) + "</mark>" + _h(evidence[end:right])
    else:
        result = _h(evidence[left:right])
    return ("[前文截短] … " if left else "") + result + (" … [后文截短]" if right < len(evidence) else "")


def _mention_rows(mentions):
    if not mentions:
        return '<p class="empty">该文档未输出引文提及记录。</p>'
    rows = []
    for mention in mentions:
        context = mention.get("context") or {}
        if not isinstance(context, dict):
            context = {"text": context}
        rows.append('<tr id="' + _mention_anchor(mention.get("mention_id")) + '"><td>' + _status(mention.get("kind")) + "<br><small>" + _h(mention.get("mention_id")) + "</small></td>"
                    "<td><b>" + _snippet(mention.get("raw"), 300) + "</b><br><small>原文偏移 " + _h(mention.get("start")) + "–" + _h(mention.get("end")) + "</small></td>"
                    "<td>" + _status(mention.get("resolution_status")) + "<br><small>身份：" + _h(mention.get("identity_status")) + "<br>解析依据：" + _h(mention.get("resolution_basis")) + "<br>具体定位：" + _snippet(mention.get("pinpoint"), 200) + "<br>备注：" + _items(mention.get("notes"), 500) + "</small></td>"
                    "<td class=mono>" + _edge_link(mention) + "<br><small>先行提及：" + _antecedents(mention.get("antecedent_mention_ids")) + "<br>候选目标：" + _items(mention.get("candidate_target_ids")) + "<br>已指派词语信号：" + _observation_links(mention.get("assigned_observation_ids")) + "<br>引述来源关系：" + _observation_links(mention.get("source_context_observation_ids")) + "</small></td>"
                    "<td><div class=excerpt>" + _snippet(context.get("text", ""), 900) + "</div><small>窗口偏移 " + _h(context.get("start")) + "–" + _h(context.get("end")) + "<br>" + _scope_view(mention.get("quotation_scope")) + "</small></td></tr>")
    return '<div class=table-wrap><table><thead><tr><th>类型 / ID</th><th>原文提及</th><th>解析状态</th><th>目标组 / 先行提及</th><th>上下文窗口</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"


def _observation_rows(observations):
    if not observations:
        return '<p class="empty">未检出本规则集中的词语信号；不表示不存在引用处理。</p>'
    rows = []
    for observation in observations:
        rows.append('<tr id="' + _h(observation.get("observation_id")) + '"><td>' + _label(observation.get("label")) + "<br><small>" + _h(observation.get("observation_id")) + "</small></td>"
                    "<td>" + _status(observation.get("status")) + "<br><small>" + _h(observation.get("assignment_reason")) + "<br>发言归属：" + _speaker_view(observation) + "<br>方向依据：" + _snippet(observation.get("attribution_basis"), 500) + "</small></td>"
                    "<td class=mono>被评价目标：" + _edge_link(observation) + "<br><small>引述来源：" + _owner_view(observation) + "<br>候选目标：" + _items(observation.get("candidate_target_ids")) + "<br>实际指派提及：" + _antecedents(observation.get("target_mention_ids")) + "<br>同句语境提及：" + _antecedents(observation.get("context_mention_ids")) + "</small></td>"
                    "<td><div class=excerpt>" + _evidence(observation) + "</div><small>证据偏移 " + _h(observation.get("evidence_start")) + "–" + _h(observation.get("evidence_end")) + "；信号偏移 " + _h(observation.get("signal_start")) + "–" + _h(observation.get("signal_end")) + "</small></td>"
                    "<td><small>" + _items(observation.get("flags")) + "<br>" + _scope_view(observation.get("quote_scope")) + "</small></td></tr>")
    return '<div class=table-wrap><table><thead><tr><th>词语标签</th><th>建议状态</th><th>目标 / 候选</th><th>原文证据（高亮词语）</th><th>语境提示</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"


def _edge_rows(edges, observations):
    if not edges:
        return '<p class="empty">没有可汇总的已链接目标组；未解析提及仍显示在上表。</p>'
    observations_by_id = {o.get("observation_id"): o for o in observations}
    rows = []
    for edge in edges:
        assigned = [observations_by_id[oid] for oid in edge.get("observation_ids", []) if oid in observations_by_id]
        # Derive the headline from evidence status as well, so older artifact
        # summaries cannot headline an explicitly negated/quoted lexical cue.
        direct = sorted({o["label"] for o in assigned if o.get("status") == "suggested" and not o.get("negated") and "negated" not in o.get("flags", []) and o["label"] not in ("affirmed", "reversed")})
        procedural = sorted({o["label"] for o in assigned if o["label"] in ("affirmed", "reversed")})
        contextual = sorted({o["label"] for o in assigned if o.get("status") != "suggested" or o.get("negated") or "negated" in o.get("flags", [])})
        rows.append('<tr id="' + _h(edge.get("edge_id", "")) + '"><td><b>' + _snippet(edge.get("name"), 220) + "</b><br><span class=mono>" + _h(edge.get("target_group_id")) + "</span><br><small>生产边标记：" + ("是" if edge.get("counted_edge") is True else "否 / 未提供") + "</small></td>"
                    "<td>完整 " + _h(edge.get("full_mention_count", 0)) + " / 短引 " + _h(edge.get("short_mention_count", 0)) + " / 案名 " + _h(edge.get("case_name_mention_count", 0)) + "<br><small>" + _antecedents(edge.get("mention_ids")) + "</small></td>"
                    "<td>" + _labels(direct) + "<br><small>以上仍为词语建议</small><br>需语境复核：" + _labels(contextual) + "<br>程序信号：" + _labels(procedural) + "<br><small>证据：" + _observation_links(edge.get("observation_ids")) + "<br>冲突：" + _snippet(edge.get("label_conflicts", []), 800) + "</small></td>"
                    "<td>" + _h(edge.get("coverage_status")) + "<br><small>无已指派信号的提及：" + _items(edge.get("uncovered_mention_ids")) + "<br>歧义观察：" + _items(edge.get("ambiguous_observation_ids")) + "<br>作为引述来源（不计为本案处理）：" + _observation_links(edge.get("reported_source_observation_ids")) + "</small></td>"
                    "<td><small>" + _items(edge.get("flags")) + "</small></td></tr>")
    return '<div class=table-wrap><table><thead><tr><th>目标组</th><th>提及数</th><th>混合词语建议</th><th>词语覆盖 / 未知项</th><th>提示</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"


_STYLE = """
:root{font:14px/1.6 system-ui,'Microsoft YaHei',sans-serif;color:#192b40;background:#f3f5f8}*{box-sizing:border-box}body{margin:0}header,main{max-width:1500px;margin:auto;padding:24px}h1{font-size:26px;margin:0 0 8px}h2{font-size:18px;margin:24px 0 8px}p{margin:8px 0}.notice{border-left:5px solid #c48014;background:#fff5df;padding:12px 16px;border-radius:5px}.muted,small{color:#536477}small{font-size:12px;overflow-wrap:anywhere}.toolbar{position:sticky;top:0;z-index:2;background:#192b40;color:white;padding:12px 24px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}.toolbar input,.toolbar select,.toolbar button{font:inherit;padding:8px;border:1px solid #b9c4d2;border-radius:5px;max-width:100%}.toolbar input{flex:1;min-width:200px}.toolbar select{max-width:340px}.toolbar button{cursor:pointer;background:#e6eef8;color:#192b40}.doc{background:white;border:1px solid #d9e0e9;border-radius:8px;margin:14px 0}.doc>summary{padding:16px;cursor:pointer;font-size:16px}.doc>summary small{display:block;margin-left:18px}.doc-body{padding:0 16px 20px}.meta{display:flex;gap:12px;flex-wrap:wrap;overflow-wrap:anywhere}.meta span{background:#edf2f7;padding:3px 8px;border-radius:4px}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;vertical-align:top;padding:10px;border:1px solid #dfe5ec;overflow-wrap:anywhere}th{background:#edf2f7;white-space:nowrap}td{min-width:120px}td:has(.excerpt){min-width:300px;width:38%}.excerpt{white-space:pre-wrap;max-height:270px;overflow:auto}.mono{font-family:Consolas,monospace;font-size:12px}.empty{color:#627186;padding:10px 0}mark{background:#ffe58a;color:#14243b;padding:1px 2px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eaf0f6;padding:14px}details[hidden]{display:none}.summary-grid{display:flex;gap:10px;flex-wrap:wrap}.metric{background:white;border:1px solid #d9e0e9;border-radius:6px;padding:8px 14px}.metric b{display:block;font-size:22px}.foot{color:#536477;font-size:12px;margin-top:25px}@media(max-width:700px){header,main{padding:16px}.toolbar{padding:10px 16px}h1{font-size:22px}.doc-body{padding:0 10px 15px}}
"""
_SCRIPT = """
(()=>{'use strict';const query=document.getElementById('query');const source=document.getElementById('source');const docs=Array.from(document.querySelectorAll('.doc'));const index=docs.map(d=>(d.textContent||'').toLocaleLowerCase());const update=()=>{const term=query.value.trim().toLocaleLowerCase();let count=0;docs.forEach((d,i)=>{const visible=(!source.value||d.dataset.source===source.value)&&(!term||index[i].includes(term));d.hidden=!visible;if(visible)count++;});document.getElementById('visible').textContent=String(count)+' / '+String(docs.length)+' 个文档';};query.addEventListener('input',update);source.addEventListener('change',update);document.getElementById('expand').addEventListener('click',()=>docs.forEach(d=>{if(!d.hidden)d.open=true;}));document.getElementById('collapse').addEventListener('click',()=>docs.forEach(d=>{if(!d.hidden)d.open=false;}));update();})();
(()=>{const reveal=()=>{const target=document.getElementById(location.hash.slice(1));if(!target)return;for(let el=target;el;el=el.parentElement){if(el.tagName==='DETAILS')el.open=true;if(el.classList.contains('doc'))el.hidden=false;}target.scrollIntoView({block:'center'});};window.addEventListener('hashchange',reveal);reveal();})();
"""


def render_report(manifest: dict, documents: list[dict], mentions: list[dict],
                  observations: list[dict], edges: list[dict]) -> str:
    """Render a self-contained Chinese-facing review report with escaped text."""
    grouped = []
    for records in (mentions, observations, edges):
        group = defaultdict(list)
        for record in records:
            group[_plain(record.get("document_id"))].append(record)
        grouped.append(group)
    document_list = list(documents)
    seen = {_plain(d.get("document_id")) for d in document_list}
    for document_id in sorted(set().union(*(set(group) for group in grouped)) - seen):
        document_list.append({"document_id": document_id, "source_id": "未提供来源", "name": "记录文档元数据缺失"})
    sources = sorted({_plain(d.get("source_id")) for d in document_list})
    options = '<option value="">全部来源</option>' + "".join('<option value="' + _h(source) + '">' + _snippet(source, 150) + '</option>' for source in sources)
    numeric = manifest.get("summary") or {}
    if not isinstance(numeric, dict):
        numeric = {}
    metrics = "".join('<div class="metric"><b>' + _h(value) + '</b><span>' + _h(_METRICS.get(key, key)) + '</span></div>' for key, value in numeric.items() if isinstance(value, (int, float)) and not isinstance(value, bool))
    blocks = []
    for index, document in enumerate(document_list):
        did = _plain(document.get("document_id"))
        doc_mentions, doc_observations, doc_edges = [group.get(did, []) for group in grouped]
        generic = [o for o in doc_observations if not o.get("mention_ids") and not o.get("candidate_target_ids") and not o.get("target_group_id") and not o.get("context_owner_mention_ids")]
        linked_observations = [o for o in doc_observations if o not in generic]
        primary_signals = _observation_rows(linked_observations) if linked_observations else '<p class="empty">没有带局部引文的词语信号；通用信号见下方折叠区。</p>' if generic else _observation_rows([])
        generic_signals = '<details><summary>未链接的通用词语信号（' + str(len(generic)) + '，展开查看）</summary><p class="muted">这些词语附近没有可指派的局部引文。页面最多展示前 50 条，全部记录保存在 observations.jsonl。</p>' + _observation_rows(generic[:50]) + '</details>' if generic else ''
        title = document.get("citation") or document.get("name") or document.get("source_id") or did
        meta = "".join("<span>" + label + "：" + _snippet(document.get(key), 200) + "</span>" for key, label in (("source_id", "来源"), ("court", "法院"), ("corpus_row", "语料行"), ("text_field", "文本字段")))
        blocks.append('<details class="doc" id="doc-' + str(index) + '" data-source="' + _h(document.get("source_id")) + '"><summary>' + _snippet(title, 300) + '<small>' + str(len(doc_mentions)) + ' 个提及 · ' + str(len(doc_observations)) + ' 个词语信号 · ' + str(len(doc_edges)) + ' 个目标组</small></summary><div class="doc-body"><div class="meta">' + meta + '</div><p><b>案名：' + _snippet(document.get("name"), 400) + '</b><br><small>文档：' + _h(did) + '<br>文本 SHA-256：' + _h(document.get("text_sha256")) + '</small></p><h2>引文提及与短引解析</h2>' + _mention_rows(doc_mentions) + '<h2>词语信号与证据</h2>' + primary_signals + generic_signals + '<h2>目标组汇总</h2>' + _edge_rows(doc_edges, doc_observations) + '</div></details>')
    configuration = manifest.get("configuration", manifest.get("config", {}))
    provenance = '<details><summary>查看运行配置</summary><pre>' + _snippet(configuration, 15000) + '</pre></details>' if configuration else ''
    return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>引文上下文实验报告</title><style>' + _STYLE + '</style></head><body><header><h1>引文上下文实验报告</h1><div class="notice"><strong>实验性机器建议，待复核</strong><p>词语信号与局部链接仅供人工检查。否定、当事人主张、引用和异议意见可能改变含义；本报告不作已核实的法律处理结论。</p></div><p class="muted">来源运行 ID：<span class="mono">' + _h(manifest.get("run_id", manifest.get("source_run_id"))) + '</span></p><div class="summary-grid">' + metrics + '</div><p class="muted">仅展示本次输入和规则输出，不代表全部引文已覆盖。偏移按原文 Unicode 字符计算，显示窗口可能截短。</p>' + provenance + '</header><div class="toolbar"><label for="source">来源</label><select id="source">' + options + '</select><input id="query" type="search" aria-label="搜索报告中的文档内容" placeholder="搜索案名、原文、状态、目标组…"><button id="expand" type="button">展开当前结果</button><button id="collapse" type="button">收起当前结果</button><span id="visible" aria-live="polite"></span></div><main>' + ("".join(blocks) or '<p class="empty">本次没有文档记录。</p>') + '<p class="foot">离线报告 · 无外部资源 · 原始记录以对应 JSONL 文件为准。生产边标记仅转述输入，词语覆盖不代表处理标签已确认。</p></main><script>' + _SCRIPT + '</script></body></html>')
