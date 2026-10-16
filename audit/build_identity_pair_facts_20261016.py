"""Build reviewed pair exclusions from immutable native citation/decision spans.

This is an evidence receipt builder, not a mining or identity inference rule.
The judgment explicitly calls these the Delay Decision and Disclosure Decision.
"""
from pathlib import Path
import csv
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
from identity_pairs import PAIR_FIELDS, PROOF_FIELDS, evidence_id, _digest, _native_row, load_pair_separations


def build():
    corpus = ROOT / 'corpus/ONCA.parquet'
    native = _native_row(corpus, 13405, ['citation_en', 'unofficial_text_en'])
    if native['citation_en'] != '2025 ONCA 767':
        raise ValueError('Unexpected native source; refusing to rebuild reviewed facts')
    text = native['unofficial_text_en']
    quote = 'R. v. McCormack, 2009 CarswellOnt 7019 (S.C.) (“Disclosure Decision”)'
    if quote not in text or '2009 CanLII 76382 (Ont. S.C.) (“Delay Decision”)' not in text:
        raise ValueError('Native source no longer expressly distinguishes these decisions')
    start, end = 12600, 16150
    row = {
        'left_merge_key': '2009||canlii||76382',
        'right_merge_key': '2009||carswellont||7019',
        'relation_type': 'verified_distinct_decisions',
        'verification_status': 'verified_corpus_distinct_decisions',
        'source_court': 'ONCA', 'source_decision': 'ONCA_2025onca767',
        'source_corpus': 'corpus/ONCA.parquet', 'corpus_sha256': _digest(corpus),
        'corpus_row': '13405', 'text_field': 'unofficial_text_en',
        'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
        'left_start': '12769', 'left_end': '12786', 'left_raw': '2009 CanLII 76382',
        'right_start': '15773', 'right_end': '15794', 'right_raw': '2009 CarswellOnt 7019',
        'span_start': str(start), 'span_end': str(end),
        'span_sha256': hashlib.sha256(text[start:end].encode('utf-8')).hexdigest(),
        'distinction_quote': quote,
        'source_locator': 'audit/findings/followup_fixes_20261016/identity_pair_sources.json#McCormack',
        'reviewer': 'Codex agent review (user-authorized; not human review)',
        'reviewed_at': '2026-10-16',
    }
    row['right_proof_json'] = json.dumps({k: row[k] for k in PROOF_FIELDS}, ensure_ascii=False,
                                        sort_keys=True, separators=(',', ':'))
    row['evidence_id'] = evidence_id(row)
    rows = [row]
    sources = {'McCormack': {'proof': row, 'source_span': text[start:end],
               'reason': 'The source calls the two rulings Delay Decision and Disclosure Decision.'}}

    def native_proof(court, index, field, raw, quote=None):
        source = ROOT / ('corpus/' + court + '.parquet')
        locale = field.rsplit('_', 1)[1]
        native = _native_row(source, index, ['citation_' + locale, field])
        text = native[field]
        a = text.index(raw)
        begin, finish = max(0, a - 350), min(len(text), a + len(raw) + 650)
        excerpt = text[begin:finish]
        if quote is not None and quote not in excerpt:
            raise ValueError('Reviewed distinction quote is absent from the native context')
        from extract import source_decision_citation
        proof = {'source_court': court,
                 'source_decision': source_decision_citation(court, native['citation_' + locale]),
                 'source_corpus': 'corpus/' + court + '.parquet', 'corpus_sha256': _digest(source),
                 'corpus_row': str(index), 'text_field': field,
                 'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                 'span_start': str(begin), 'span_end': str(finish),
                 'span_sha256': hashlib.sha256(excerpt.encode('utf-8')).hexdigest(),
                 'distinction_quote': quote or raw}
        return proof, a, a + len(raw), excerpt

    def admit(name, left_key, right_key, left, right, reason):
        lp, ls, le, lt = left
        rp, rs, re, rt = right
        item = {**lp, 'left_merge_key': left_key, 'right_merge_key': right_key,
                'relation_type': 'verified_distinct_decisions',
                'verification_status': 'verified_corpus_distinct_decisions',
                'left_start': str(ls), 'left_end': str(le), 'left_raw': lt[ls-int(lp['span_start']):le-int(lp['span_start'])],
                'right_start': str(rs), 'right_end': str(re), 'right_raw': rt[rs-int(rp['span_start']):re-int(rp['span_start'])],
                'right_proof_json': json.dumps(rp, ensure_ascii=False, sort_keys=True, separators=(',', ':')),
                'source_locator': 'audit/findings/followup_fixes_20261016/identity_pair_sources.json#' + name,
                'reviewer': 'Codex agent review (user-authorized; not human review)', 'reviewed_at': '2026-10-16'}
        item['evidence_id'] = evidence_id(item)
        rows.append(item)
        sources[name] = {'proof': item, 'left_source_span': lt, 'right_source_span': rt, 'reason': reason}

    # The source expressly dates the application ruling in 2014 and the SCC
    # judgment in 2015. Both citations occur in this same source document.
    admit('Green', '2015||scc||60', '2014||scca||137',
          native_proof('ONCA', 893, 'unofficial_text_en', '2015 SCC 60', '(“Green (SCC)”)'),
          native_proof('ONCA', 893, 'unofficial_text_en', '[2014] S.C.C.A. No. 137',
                       'application for leave to intervene in that appeal was dismissed on December 17, 2014'),
          'Native paras.2 and 34-35 distinguish the 2014 application disposition from the 2015 SCC judgment; common litigation does not make them one ruling.')
    admit('Hazout', '2006||csc||42', '2005||scca||412',
          native_proof('ONCA', 10393, 'unofficial_text_fr', '2006 CSC 42', 'pourvoi de plein droit annulé'),
          native_proof('ONCA', 10393, 'unofficial_text_fr', '[2005] S.C.C.A. No. 412',
                       'autorisations de pourvoi refusées'),
          'The native French passage separately reports the appeal-as-of-right disposition and refused applications, with different years and citations.')
    import pyarrow.parquet as pq
    citations = pq.read_table(ROOT / 'corpus/SCC.parquet', columns=['citation_en']).column(0).to_pylist()
    marshall = citations.index('2005 SCC 43')
    admit('Marshall', '2005||scc||43', '2006||scca||105',
          native_proof('SCC', marshall, 'unofficial_text_en', '2005 SCC 43'),
          native_proof('ONCA', 10242, 'unofficial_text_en', '[2006] S.C.C.A. No. 105',
                       'R. v. Marshall (2005), 77 O.R. (3d) 81'),
          'The 2005 SCC Marshall judgment has its own numbered native header. The 2006 refusal is expressly the application following the distinct Ontario alibi judgment 77 OR(3d)81, not another report of that SCC judgment.')
    # These reviewed instances contain explicit appeal/leave wording, but an
    # intervening alias, judge attribution, editorial bracket or narrative is
    # outside the deliberately closed parallel-citation gap grammar. Do not
    # broaden that grammar to arbitrary prose or turn a warning into a fact.
    # Scherer's conflicting source and the malformed I.L.R. fragments are
    # deliberately absent. Source offsets, keys and hashes are rechecked below.
    reviewed = {
        ('1881|20|chd||389', '1882|51|ljch||503'): 'Golden',
        ('1978||canlii||3967', '1979|95|dlr|3d|193'): 'Riddle',
        ('1988||bcwld||2123', '1989|41|bclr|2d|239'): 'Barclay',
        ('2021||bcca||176', '2021||canlii||126365'): '1193652_BC',
        ('2021||qcca||873', '2022||canlii||16716'): 'Air_Canada_PA',
        ('1952|3|dlr||681', '1953||own||140'): 'Pflug',
        ('1980|125|dlr|3d|177', '1981|33|or|2d|585'): 'Dodgson',
        ('1981|34|or|2d|236', '1982|35|or|2d|64'): 'Johnson',
        ('1987|1|aller||81', '1987|3|aller||565'): 'Pagnan',
        ('1974||oj||1856', '|22|ccc|2d|19'): 'Hawke',
        ('2007||canlii||23362', '2008||onca||202'): 'Tasker',
        ('|58|ar||66', '1985|1|scr||ro:ix'): 'Leontowicz',
        ('1903|6|olr||532', '1904|7|olr||72'): 'Burdett',
        ('1925||ch||407', '1925||ch||500'): 'City_Equitable',
        ('1948|2|wwr||135', '1948|2|wwr||958'): 'Yaeger',
        ('1959||scr||797', '1959||queqb||175'): 'David',
        ('|26|ccc||278', '1916|54|scr||7'): 'Veronneau',
        ('1990|70|or||2', '1991|2|scr||456'): 'Waldick',
    }
    materials = json.loads((ROOT/'audit/findings/followup_fixes_20261016/residual_history_materials.json').read_text(encoding='utf-8'))
    selected = {(case['left'], case['right']): case for case in materials['pairs']
                if (case['left'], case['right']) in reviewed}
    if set(selected) != set(reviewed):
        raise ValueError('Reviewed residual identity evidence is incomplete')
    for keys, name in reviewed.items():
        case = selected[keys]
        hit = case['occurrences'][0]
        court, index, field = case['court'], hit['corpus_row'], hit['text_field']
        source = ROOT/('corpus/'+court+'.parquet')
        locale = field.rsplit('_', 1)[1]
        record = _native_row(source, index, ['citation_'+locale, field])
        text = record[field]
        if hashlib.sha256(text.encode()).hexdigest() != hit['text_sha256']:
            raise ValueError('Reviewed residual source text changed')
        from extract import source_decision_citation
        if source_decision_citation(court, record['citation_'+locale]) != hit['source_decision']:
            raise ValueError('Reviewed residual source document changed')
        if name == 'Waldick':
            # The old probe exposed a truncated page-2 reading. Bind the fact
            # to the newly extracted complete 70 O.R. 2(d) 717 citation instead.
            from extract import extract_candidates
            from classify import Classifier, load_runtime_tables
            from merge import build_merge_key_v2, apply_reporter_identity_fixes
            from collections import Counter
            classifier = Classifier(load_runtime_tables(), Counter())
            candidates, _ = extract_candidates(text, hit['source_decision'], '', index, court)
            classified = [classifier.run_row(dict(c)) for c in candidates]
            apply_reporter_identity_fixes({hit['source_decision']: classified}, Counter())
            expected = '1990|70|or|2d|717'
            complete = [c for c in classified if int(c['match_start_offset']) == hit['left_start']
                        and build_merge_key_v2(c) == expected]
            if len(complete) != 1:
                raise ValueError('Waldick complete native citation is not uniquely extracted')
            hit = dict(hit, left_end=int(complete[0]['match_end_offset']))
            hit['left_raw'] = text[hit['left_start']:hit['left_end']]
            keys = (expected, keys[1])
        start, end = hit['span_start'], hit['span_end']
        excerpt = text[start:end]
        if hashlib.sha256(excerpt.encode()).hexdigest() != hit['span_sha256']:
            raise ValueError('Reviewed residual source span changed')
        proof = dict(source_court=court, source_decision=hit['source_decision'],
            source_corpus='corpus/'+court+'.parquet', corpus_sha256=_digest(source),
            corpus_row=str(index), text_field=field, text_sha256=hit['text_sha256'],
            span_start=str(start), span_end=str(end), span_sha256=hit['span_sha256'],
            distinction_quote=hit['actual_gap'].strip())
        bound = []
        for side in ('left', 'right'):
            a, b = hit[side+'_start'], hit[side+'_end']
            if text[a:b] != hit[side+'_raw']:
                raise ValueError('Reviewed residual citation span changed')
            bound.append((proof, a, b, excerpt))
        admit(name, *keys, *bound,
            'Native source expressly prints an appeal/leave relation between these two rulings. '
            'The intervening text exceeds the closed automatic gap grammar; this exact '
            'reviewed exclusion creates no positive identity, court or origin assignment.')
    path = ROOT / 'decisions/identity_pair_separations.csv'
    with path.open('w', encoding='utf-8', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=PAIR_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    proof_path = ROOT / 'audit/findings/followup_fixes_20261016/identity_pair_sources.json'
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof = {'protocol': 'native-distinct-rulings-v1', **sources}
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    verified = load_pair_separations()
    print(json.dumps({'facts': len(verified), 'table': str(path), 'native_validation': 'passed'}))


if __name__ == '__main__':
    build()
