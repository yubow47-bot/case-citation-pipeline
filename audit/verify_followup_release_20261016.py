"""Read-only acceptance assertions for the October 16 follow-up release.

These named regressions and provenance contracts are not a population accuracy
estimate. No expectation or run output is rewritten by this verifier.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/foundation'))
sys.path.insert(0, str(ROOT/'tools'))
sys.path.insert(0, str(ROOT/'audit'))
from seal import verify_output_seal
from compare_runs import Run
from identity_trace_contracts import check_scope

csv.field_size_limit(10**9)
NEW_PAIRS = {
    'McCormack': ('2009||canlii||76382', '2009||carswellont||7019'),
    'Green': ('2015||scc||60', '2014||scca||137'),
    'Hazout': ('2006||csc||42', '2005||scca||412'),
    'Marshall': ('2005||scc||43', '2006||scca||105'),
}
ADDITIONAL_NATIVE_PAIRS = {
    'Golden': ('1881|20|chd||389', '1882|51|ljch||503'),
    'Riddle': ('1978||canlii||3967', '1979|95|dlr|3d|193'),
    'Barclay': ('1988||bcwld||2123', '1989|41|bclr|2d|239'),
    '1193652_BC': ('2021||bcca||176', '2021||canlii||126365'),
    'Air_Canada_PA': ('2021||qcca||873', '2022||canlii||16716'),
    'Pflug': ('1952|3|dlr||681', '1953||own||140'),
    'Dodgson': ('1980|125|dlr|3d|177', '1981|33|or|2d|585'),
    'Johnson': ('1981|34|or|2d|236', '1982|35|or|2d|64'),
    'Pagnan': ('1987|1|aller||81', '1987|3|aller||565'),
    'Hawke': ('1974||oj||1856', '|22|ccc|2d|19'),
    'Tasker': ('2007||canlii||23362', '2008||onca||202'),
    'Leontowicz': ('|58|ar||66', '1985|1|scr||ro:ix'),
    'Burdett': ('1903|6|olr||532', '1904|7|olr||72'),
    'City_Equitable': ('1925||ch||407', '1925||ch||500'),
    'Yaeger': ('1948|2|wwr||135', '1948|2|wwr||958'),
    'David': ('1959||scr||797', '1959||queqb||175'),
    'Veronneau': ('|26|ccc||278', '1916|54|scr||7'),
    'Waldick': ('1990|70|or|2d|717', '1991|2|scr||456'),
}
GRAMMAR_RESIDUAL_PAIRS = {
    'Okanagan': ('2002|1|cnlr||57', '2003||scc||71'),
    'Swartz': ('1935||scr||628', '1934|3|wwr||441'),
    'Cavan_application': ('|139|ccc|3d|449', '1999||sccanos||560'),
    'Vijeykumar': ('1998|38|or|3d|590', '1999|44|or|3d|545'),
    'WV': ('2007||onca||546', '2008|397|oac||397'),
    'Lal': ('|130|ccc|3d|413', '1999|61|crr|2d|376'),
    'Fecht': ('1996|28|or|3d|188', '1997|97|oac||241'),
    'Research_Capital': ('2008||oj||2526', '2009||onca||418'),
    'Cameron': ('2017||bcca||385', '2018||canlii||35648'),
    'Timm': ('|131|ccc|3d|306', '|140|ccc|3d|225'),
    'Macartney': ('1996|34|ccli|2d|119', '1996|29|or|3d|720'),
    'Jackson': ('1998|50|ccli|2d|173', '1999||oj||3468'),
    'MacKenzie': ('1998||oj||5342', '1999||oj||4602'),
    'Schultz': ('|133|ccc||174', '1962||scr||ro:x'),
    'MRA': ('|94|ccc|3d|459', '1994||scca||544'),
    'Martselos': ('1994|3|wwr||73', '1994|3|scr||ro:viii'),
    'CCAS': ('|6|rfl|3d|1', '|21|rfl|3d|115'),
}
ILR_PAIRS = {
    'Peet_ILR': ('1988||ilr||1-2261', '1988||ilr||8865'),
    'Gulf_ILR': ('1990||ilr||1-2644', '1991|3|ccli|2d|203'),
}
RETAINED_PAIRS = {
    'Cavan': ('|139|ccc|3d|449', '2000|1|scr||ro:viii'),
    'Hill': ('1994|18|or|3d|385', '1995|2|scr||1130'),
    'Smith': ('1995|22|or|3d|433', '1995|26|or|3d|94'),
    'Horgan': ('2007|165|crr|2d|332', '2008|166|crr|2d|374'),
    'Domm': ('1996|31|or|3d|540', '1997|2|scr||ro:viii'),
    'Lennards': ('1915||ac||705', '1914|1|kb||419'),
    'Munroe': ('|96|ccc|3d|431', '|102|ccc|3d|383'),
    'Dell': ('1963|37|dlr|2d|101', '1964|42|dlr|2d|326'),
    'Deep': ('2007||canlii||27969', '2008||onca||4'),
    'Comba': ('1938||scr||396', '1938||or||200'),
    'Bennett': ('1991|3|or|3d|193', '1992|2|scr||168'),
}
HUARD = '1992|40|mvr|2d|118'
WILSON = ('1991|121|bcac||111', '|68|ccc|3d|569')
NONCASES = {'Sheehy': '2020|42|jsocwelfarefaml||80',
            'TRIPS': '|1869|unts||299', 'Schiff': '1978|56|canbarrev||674'}
NAMED = {'Hedley_Byrne': ('1964||ac||465', ('hedley', 'heller')),
         'Morin': ('|71|ccc|3d|1', ('morin',)),
         'McKnight': ('|135|ccc|3d|41', ('mcknight',)),
         'Love': ('2023|1|wwr||296', ('love',))}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def physical(path):
    path = Path(path)
    return path if path.is_file() else Path(str(path)+'.gz')


def rows(path):
    path = physical(path)
    with (gzip.open if path.suffix == '.gz' else open)(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        yield from csv.DictReader(stream, strict=True)


def digest(path, logical=False):
    path = physical(path) if logical else Path(path)
    opener = gzip.open if logical and path.suffix == '.gz' else open
    value = hashlib.sha256()
    with opener(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def required_scope_artifacts(manifest):
    courts = manifest.get('params', {}).get('courts')
    require(isinstance(courts, list) and courts and len(set(courts)) == len(courts)
            and all(isinstance(c, str) and re.fullmatch('[A-Z][A-Z0-9]*', c) for c in courts),
            'Missing, duplicate or invalid declared court scopes')
    names = ('manifest.json', 'decided.csv', 'decision_ids.csv', 'effective_sources.csv',
             'identity_evidence.csv', 'identity_constraints.csv', 'identity_conflicts.csv', 'identity_solution.csv')
    return [f'decide_out/{scope}/{name}' for scope in [*courts, 'cross_court'] for name in names]


def verify_generic_traces(run, manifest):
    required = required_scope_artifacts(manifest)
    seal = verify_output_seal(run, manifest, required)
    require(seal['status'] == 'verified', 'Generic trace validation requires an output seal')
    view = Run(run)
    scopes = [*manifest['params']['courts'], 'cross_court']
    results = [check_scope(view, 'decide_out/'+scope) for scope in scopes]
    return {'required_scopes': scopes, 'scopes_verified': len(results), 'scopes': results,
            'required_sealed_artifacts': len(required)}


def assert_native_pair_inventory(facts, expected_pairs=NEW_PAIRS):
    expected = {tuple(sorted(pair)) for pair in expected_pairs.values()}
    actual = {tuple(sorted((fact['left_merge_key'], fact['right_merge_key']))) for fact in facts}
    require(len(facts) == len(expected) and actual == expected,
            'Native pair fact inventory does not exactly cover the required release pairs')
    return actual


def verify_native_pairs(manifest, project_root=ROOT, expected_pairs=NEW_PAIRS):
    project_root = Path(project_root).resolve()
    relative = 'decisions/identity_pair_separations.csv'
    path = project_root/relative
    table_hash = digest(path)
    require(table_hash == manifest['input_identity']['files'].get(relative),
            'Native pair table is not bound to the accepted run input')
    # Runtime validation uses the production extractor/classifier/key builder
    # and verifies both native source citations, full text and distinction spans.
    sys.path.insert(0, str(project_root/'pipeline'))
    from identity_pairs import load_pair_separations
    keys = {key for pair in expected_pairs.values() for key in pair}
    facts = load_pair_separations(path=path, root=project_root, keys=keys)
    assert_native_pair_inventory(facts, expected_pairs)
    for fact in facts:
        for proof in (fact, json.loads(fact['right_proof_json'])):
            require(manifest['input_identity']['files'].get(proof['source_corpus']) == proof['corpus_sha256'],
                    'Native pair corpus is not bound to the accepted run input')
    return {'facts_verified': len(facts), 'table': relative, 'table_sha256': table_hash,
            'endpoint_pairs': sorted([list(pair) for pair in assert_native_pair_inventory(facts, expected_pairs)]),
            'table_evidence_ids': sorted(fact['table_evidence_id'] for fact in facts),
            'scope': 'Native byte/span/printed-key validation; distinction interpretation remains reviewed agent evidence'}


def verify_waldick_candidate_ledger(run):
    expected = {
        'ONCA:16983:11266:11283:shape_year_vol_page': ('1990|70|or||2', False),
        'ONCA:16983:11274:11283:shape_vol_abbr_page': ('|70|or||2', False),
        'ONCA:16983:11266:11290:shape_year_vol_page_transposed_series': ('1990|70|or|2d|717', True),
    }
    actual = {}
    for record in rows(Path(run)/'merge_out/ONCA/mentions_candidates.csv'):
        cid = record['candidate_id']
        if cid in expected:
            require(cid not in actual, 'Duplicate Waldick native candidate in ledger')
            actual[cid] = record
    require(actual.keys() == expected.keys(), 'Waldick complete or retained truncated candidate is absent')
    for cid, (key, counted) in expected.items():
        record = actual[cid]
        require(record['merge_key'] == key and (record['arbitration_status'] == 'counted') == counted,
                'Waldick truncated-page/full-series arbitration contract failed: '+cid)
        require(record['source_decision_citation'] == 'ONCA_2026onca371' and record['corpus_row_index'] == '16983',
                'Waldick candidate is bound to another native source')
    return {'source': 'ONCA_2026onca371', 'corpus_row': 16983, 'candidates_verified': len(actual),
            'corrected_key': '1990|70|or|2d|717', 'retained_truncated_candidates_counted': 0}


def ilr_candidate_expectations():
    sources = (
        (18460, 5296, 5311, '1988', '2261', 'ONCA_2012onca338'),
        (12963, 26351, 26366, '1990', '2644',
         'ONCA_c34246c34251c34253c34282c34289c34290c34293c34316c34336c35599'),
    )
    expected = {}
    for index, start, partial_end, year, locator, source in sources:
        common = {'source_decision_citation': source, 'corpus_row_index': str(index)}
        for full in (False, True):
            end = partial_end+5 if full else partial_end
            shape = 'shape_bracket_compound_locator' if full else 'shape_bracket'
            page = '1-'+locator if full else '1'
            expected[f'ONCA:{index}:{start}:{end}:{shape}'] = dict(common,
                merge_key=year+'||ilr||'+page, counted=full, raw_string='['+year+'] I.L.R. '+page)
    return expected


def verify_ilr_candidate_ledger(run):
    expected = ilr_candidate_expectations()
    actual = {}
    for record in rows(Path(run)/'merge_out/ONCA/mentions_candidates.csv'):
        cid = record['candidate_id']
        if cid in expected:
            require(cid not in actual, 'Duplicate ILR native candidate in ledger')
            actual[cid] = record
    require(actual.keys() == expected.keys(), 'ILR complete or retained partial candidate is absent')
    for cid, wanted in expected.items():
        record = actual[cid]
        require(all(record.get(field) == value for field, value in wanted.items() if field != 'counted'),
                'ILR source, complete locator or literal span changed: '+cid)
        require((record['arbitration_status'] == 'counted') == wanted['counted'],
                'ILR partial-page/full-locator arbitration contract failed: '+cid)
        if wanted['counted']:
            require(record['jurisdiction'] in ('', 'UNSUPPORTED'), 'ILR locator syntax inferred a jurisdiction')
    return {'candidates_verified': len(actual), 'complete_counted': 2, 'retained_partial_candidates_counted': 0,
            'jurisdiction_inferred_from_compound_syntax': False}


def index_run(run):
    by_key, primary, named, counts = defaultdict(set), {}, set(), Counter()
    total = 0
    for row in rows(Path(run)/'decide_out/cross_court/decided.csv'):
        total += 1
        gid = row['merged_group_id']
        by_key[row['merge_key']].add(gid)
        if row['case_name_modal'].strip():
            named.add(gid)
        if row['is_primary'] == 'true':
            counts[gid] += 1
            primary[gid] = {'name': row['case_name_modal'], 'dd': int(row['distinct_decisions_count'])}
        else:
            counts.setdefault(gid, 0)
    return {'by_key': by_key, 'primary': primary, 'named': named, 'primary_counts': counts, 'rows': total}


def distinct_pair(index, left, right):
    a, b = index['by_key'].get(left, set()), index['by_key'].get(right, set())
    require(a and b, 'A required judgment key is absent: '+left+' / '+right)
    require(a.isdisjoint(b), 'Distinct judgments still share groups: '+str(sorted(a & b)))
    return {'left_key': left, 'right_key': right, 'left_groups': sorted(a), 'right_groups': sorted(b)}


def named_key(index, key, tokens, singleton=False):
    gids = index['by_key'].get(key, set())
    require(gids, 'Required named judgment is absent: '+key)
    if singleton:
        require(len(gids) == 1, 'Same report remains fragmented: '+key)
    values = {g: index['primary'][g] for g in gids}
    require(all(all(t in v['name'].lower() for t in tokens) for v in values.values()),
            'Unexpected primary name for '+key+': '+str(values))
    return {'key': key, 'groups': values}


def verify_trace(run, scope, manifest, require_mapping=False, project_root=ROOT):
    """Check factual history-row bindings and bilingual proposal policy proofs."""
    run = Path(run).resolve()
    directory = run/'decide_out'/scope
    history, by_instance, policies = {}, defaultdict(set), {}
    source_cache = {}
    policy_source_cache = {}
    for fact in rows(directory/'identity_evidence.csv'):
        kind = fact['fact_kind']
        if kind not in ('appeal_history_instance', 'policy_record'):
            continue
        expected = 'fact:'+hashlib.sha256(canonical({k: v for k, v in fact.items() if k != 'evidence_id'}).encode()).hexdigest()
        require(fact['evidence_id'] == expected, 'Fact content hash disagrees with its ID')
        value, source = json.loads(fact['value_json']), json.loads(fact['sources_json'])
        if kind == 'policy_record':
            if source.get('artifact') == 'decisions/bilingual_reporter_abbreviations.csv':
                require(source.get('sha256') == manifest['input_identity']['files'].get(source['artifact']),
                        'Reporter mapping policy hash is not bound to the run input snapshot')
                if source['artifact'] not in policy_source_cache:
                    policy_path = Path(project_root)/source['artifact']
                    require(digest(policy_path) == source['sha256'], 'Mapping policy input bytes changed')
                    policy_source_cache[source['artifact']] = dict(enumerate(rows(policy_path), start=2))
                require(policy_source_cache[source['artifact']].get(int(source['record'])) == value,
                        'Mapping policy fact differs from its located input row')
                policies[fact['evidence_id']] = value
            continue
        require(value.get('source_locator') == source and source.get('hash_scope') == 'logical_csv_bytes',
                'History fact lacks the logical CSV source locator')
        logical = Path(source['artifact'])
        if not logical.is_absolute():
            logical = Path(project_root)/logical
        logical = logical.resolve()
        require(run in logical.parents, 'History source points outside the accepted run')
        if logical not in source_cache:
            source_cache[logical] = (digest(logical, logical=True),
                                    dict(enumerate(rows(logical), start=2)))
        actual_hash, source_rows = source_cache[logical]
        require(actual_hash == source.get('sha256'), 'History source logical CSV hash changed')
        original = source_rows.get(int(source['record']))
        require(original is not None, 'History source row is absent')
        for field in ('source_decision_citation', 'corpus_row_index', 'instance', 'side', 'merge_key', 'candidate_id', 'connector'):
            require(original.get(field) == value.get(field), 'History fact is bound to another source row: '+field)
        require(hashlib.sha256(value['connector'].encode()).hexdigest() == value.get('connector_sha256'),
                'History connector hash changed')
        require(value['side'] in ('before', 'after'), 'Unknown history side')
        history[fact['evidence_id']] = value
        by_instance[value['instance']].add(fact['evidence_id'])
    require(history, 'No appeal-history instance facts were emitted')
    history_constraints = mapping_proposals = 0
    for constraint in rows(directory/'identity_constraints.csv'):
        detail = json.loads(constraint['source_detail_json'])
        refs = set(json.loads(constraint['evidence_ids_json']))
        if constraint['rule'] == 'appeal_history_connector':
            history_constraints += 1
            require(constraint['relation'] == 'cannot_link', 'History relation is not a cannot-link')
            bindings = detail.get('history_instances')
            require(bindings, 'History constraint has no instance binding')
            left = {k.split('|', 1)[1] for k in json.loads(constraint['left_members_json'])}
            right = {k.split('|', 1)[1] for k in json.loads(constraint['right_members_json'])}
            for binding in bindings:
                ids = set(binding.get('evidence_ids', ()))
                iid = binding['instance']
                require(ids and ids <= refs and ids == by_instance.get(iid), 'History constraint has incomplete or foreign instance facts')
                before = {history[e]['merge_key'] for e in ids if history[e]['side'] == 'before'}
                after = {history[e]['merge_key'] for e in ids if history[e]['side'] == 'after'}
                require(before and after and before.isdisjoint(after), 'History instance sides are incomplete or overlapping')
                require(before == set(binding['before_merge_keys']) and after == set(binding['after_merge_keys']),
                        'Declared history sides differ from immutable facts')
                require((left & before and right & after) or (left & after and right & before),
                        'History instance does not connect these constraint endpoints')
        for mapping in detail.get('reporter_normalizations', ()):
            if mapping.get('from') != 'rcs' or mapping.get('to') != 'scr':
                continue
            mapping_proposals += 1
            eid = mapping.get('policy_evidence_id')
            policy = policies.get(eid)
            require(eid in refs and policy, 'RCS/SCR proposal lacks its mapping policy fact')
            require(policy.get('normalized_fr') == 'rcs' and policy.get('normalized_en') == 'scr'
                    and policy.get('verification_status') == 'verified_corpus_metadata'
                    and policy.get('source') and policy.get('source_locator'), 'RCS/SCR mapping proof is incomplete')
    require(history_constraints, 'No history cannot-link constraints were emitted')
    if require_mapping:
        require(mapping_proposals, 'No RCS/SCR proposals with policy proof were observed')
    return {'scope': scope, 'history_facts': len(history), 'history_constraints': history_constraints,
            'logical_source_files_verified': len(source_cache), 'rcs_scr_proposals_verified': mapping_proposals}


def validate(run, baseline=None, project_root=ROOT):
    run, project_root = Path(run).resolve(), Path(project_root).resolve()
    checks = []
    def check(name, operation):
        try:
            detail = operation()
            checks.append({'id': name, 'status': 'passed', 'detail': detail})
        except Exception as exc:
            checks.append({'id': name, 'status': 'failed', 'error': type(exc).__name__+': '+str(exc)})
    manifest = json.loads((run/'run_manifest.json').read_text(encoding='utf-8'))
    def inputs():
        require(manifest.get('status') == 'complete' and manifest.get('input_identity_verified_unchanged') is True,
                'Run is not complete and input-verified')
        identity = manifest['input_identity']
        require(re.fullmatch('[0-9a-f]{64}', identity.get('fingerprint', '')) and identity.get('files'), 'Input identity is missing')
        for relative, expected in identity['files'].items():
            path = (project_root/relative).resolve()
            require(project_root in path.parents and digest(path) == expected, 'Recorded input bytes changed: '+relative)
        return {'files_hashed': len(identity['files']), 'fingerprint': identity['fingerprint']}
    check('complete_and_input_bytes', inputs)
    def seal():
        required = required_scope_artifacts(manifest)
        required += ['merge_out/'+court+'/mentions_candidates.csv' for court in manifest['params']['courts']]
        result = verify_output_seal(run, manifest, required)
        require(result['status'] == 'verified', 'Run has no output seal')
        return result
    check('output_seal', seal)
    check('all_declared_identity_traces', lambda: verify_generic_traces(run, manifest))
    check('native_pair_sources_and_inventory', lambda: verify_native_pairs(manifest, project_root))
    check('additional_native_pair_sources_and_inventory',
          lambda: verify_native_pairs(manifest, project_root, ADDITIONAL_NATIVE_PAIRS))
    check('Waldick_native_candidate_ledger', lambda: verify_waldick_candidate_ledger(run))
    check('ILR_native_candidate_ledger', lambda: verify_ilr_candidate_ledger(run))
    index = index_run(run)
    def primary_contract():
        bad = {g: n for g, n in index['primary_counts'].items() if n != 1}
        require(not bad, 'Groups without exactly one primary: '+str(list(bad.items())[:10]))
        unnamed = [g for g in index['named'] if not index['primary'][g]['name'].strip()]
        require(not unnamed, 'Primary is unnamed while a member has a name: '+str(unnamed[:10]))
        return {'rows': index['rows'], 'groups': len(index['primary']), 'bad_primary': 0, 'unnamed_with_named_member': 0}
    check('primary_naming_contract', primary_contract)
    for name, pair in (NEW_PAIRS | ADDITIONAL_NATIVE_PAIRS | GRAMMAR_RESIDUAL_PAIRS | ILR_PAIRS | RETAINED_PAIRS).items():
        check('distinct_'+name, lambda pair=pair: distinct_pair(index, *pair))
    check('Huard_name', lambda: named_key(index, HUARD, ('huard',)))
    for number, key in enumerate(WILSON, 1):
        check('Huard_not_Wilson_'+str(number), lambda key=key: distinct_pair(index, HUARD, key))
    for name, key in NONCASES.items():
        def noncase(key=key):
            gids = index['by_key'].get(key, set())
            require(all(index['primary'][g]['dd'] == 0 for g in gids), 'Nonjudgment still contributes to a positive-DD group: '+key)
            return {'key': key, 'retained_groups': sorted(gids), 'positive_dd_groups': 0}
        check('excluded_'+name, noncase)
    for name, (key, tokens) in NAMED.items():
        check('named_'+name, lambda key=key, tokens=tokens: named_key(index, key, tokens, singleton=True))
    for scope in [*manifest['params']['courts'], 'cross_court']:
        check('provenance_'+scope, lambda scope=scope: verify_trace(run, scope, manifest, scope == 'cross_court', project_root))
    label_path = ROOT/'audit/findings/followup_fixes_20261016/booty_label_adjudication.json'
    booty = {'status': 'disputed_historical_model_label_not_forced_split',
             'groups_375': sorted(index['by_key'].get('2009||bcca||375', ())),
             'groups_376': sorted(index['by_key'].get('2009||bcca||376', ())),
             'supplemental_adjudication': str(label_path), 'adjudication_sha256': digest(label_path)}
    scherer_path = ROOT/'audit/findings/followup_fixes_20261016/residual_history_review.json'
    scherer = {'status': 'contradictory_native_history_abstain_from_forced_split',
               'cr_groups': sorted(index['by_key'].get('1984|42|cr|3d|376', ())),
               'ccc_groups': sorted(index['by_key'].get('|16|ccc|3d|30', ())),
               'adjudication': str(scherer_path), 'adjudication_sha256': digest(scherer_path)}
    return {'protocol': 'followup-release-acceptance-20261016-v1',
            'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'run': str(run),
            'baseline_reference': str(Path(baseline).resolve()) if baseline else None,
            'scope': 'Named regression assertions, input/output bytes and provenance contracts; not semantic accuracy or recall.',
            'status': 'passed' if all(c['status'] == 'passed' for c in checks) else 'failed',
            'assertions_passed': sum(c['status'] == 'passed' for c in checks), 'assertions_total': len(checks),
            'checks': checks, 'booty': booty, 'scherer': scherer}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--run', required=True)
    parser.add_argument('--baseline', default='data/run_20261016_fixes_full3')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    if any(path == output or path in output.parents for path in (Path(args.run).resolve(), Path(args.baseline).resolve())):
        parser.error('Receipt output must be outside the read-only run directories')
    try:
        report = validate(args.run, args.baseline)
    except Exception as exc:
        report = {'protocol': 'followup-release-acceptance-20261016-v1', 'status': 'failed',
                  'run': str(Path(args.run).resolve()), 'fatal_error': type(exc).__name__+': '+str(exc)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('status', 'assertions_passed', 'assertions_total', 'fatal_error') if k in report}, ensure_ascii=False))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
