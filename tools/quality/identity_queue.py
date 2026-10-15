"""Stream all identity members; retain a bounded, deterministic review queue."""
from collections import Counter
import heapq
import json
from pathlib import Path

try:
    from .common import (MAX_QUEUE_RECORDS, MAX_JSON_BYTES, canonical_hash, frame_identity, member_rows,
                         rows, csv_path, locate_evidence, verify_unchanged, edge_rows)
except ImportError:
    from common import (MAX_QUEUE_RECORDS, MAX_JSON_BYTES, canonical_hash, frame_identity, member_rows,
                        rows, csv_path, locate_evidence, verify_unchanged, edge_rows)


def review_queue(source, limit=500, min_impact_dd=20, with_text=False):
    if not isinstance(limit, int) or not 1 <= limit <= MAX_QUEUE_RECORDS:
        raise ValueError('Identity queue limit must be between 1 and 500')
    if min_impact_dd < 1:
        raise ValueError('min-impact-dd must be positive')
    frame_id, identity, snapshot = frame_identity(source)
    groups, first_keys, conflicts = {}, {}, {}
    coverage = Counter()
    selected_sha = identity['artifact_logical_sha256']['select_out/selected.csv']
    try:
        selected = str(csv_path(source.run_dir / 'select_out/selected.csv'))
    except (ValueError, TypeError):
        selected = source.provenance['db_path']

    def locator(number):
        return {'logical_path': 'select_out/selected.csv', 'path': selected,
                'record': number, 'logical_sha256': selected_sha}

    for number, row in member_rows(source):
        coverage['members_scanned'] += 1
        gid, key = row['merged_group_id'], row['merge_key']
        dd = int(row.get('distinct_decisions_count') or 0)
        group = groups.setdefault(gid, {'dd': dd, 'name': row.get('case_name_modal', '')[:120],
                                        'court_tokens': set(), 'weak_bases': set(), 'examples': [],
                                        'member_court_conflict': False})
        if group['dd'] != dd:
            raise ValueError('A group has contradictory DD values: ' + gid)
        if len(group['examples']) < 2:
            group['examples'].append({'merge_key': key, 'citation_kind': row.get('citation_kind', ''),
                                      'source_court_of_mentions': row['court'],
                                      'row_sha256': canonical_hash(row), 'locator': locator(number)})
        printed = row.get('identity_court_evidence') or ''
        if not printed:
            coverage['members_without_stored_positive_court_evidence'] += 1
        for part in printed.split('|'):
            token, _, basis = part.partition('=')
            if token.startswith('court:') and basis:
                group['court_tokens'].add(token)
        if row.get('identity_court_conflict') == 'true':
            group['member_court_conflict'] = True
        basis = row.get('identity_basis') or ''
        if basis in ('name_year', 'cocitation', 'name_year_candidate', 'cocitation_candidate'):
            group['weak_bases'].add(basis)
        if row.get('citation_kind') not in ('neutral', 'identifier'):
            continue
        coverage['neutral_identifier_members_scanned'] += 1
        previous = first_keys.setdefault(key, (gid, number, row.get('citation_kind'), row['court']))
        if previous[0] != gid:
            conflict = conflicts.setdefault(key, {'groups': {previous[0]}, 'citation_kind': previous[2],
                                                  'first_locator': locator(previous[1]), 'other_examples': []})
            conflict['groups'].add(gid)
            if len(conflict['other_examples']) < 2:
                conflict['other_examples'].append({'group_id': gid, 'locator': locator(number),
                                                   'row_sha256': canonical_hash(row)})

    counts, heap = Counter(), []
    def add(reason, entity, dd, severity, detail, group_ids):
        counts[reason] += 1
        record = {'review_id': canonical_hash({'frame_id': frame_id, 'reason': reason, 'entity': entity}),
                  'run_id': source.run_id, 'frame_id': frame_id, 'reason': reason,
                  'entity': entity, 'impact_dd': dd, 'priority': severity,
                  'group_ids_preview': sorted(group_ids)[:4], 'group_ids_count': len(group_ids),
                  'detail': detail, 'evidence_preview': None,
                  'status': 'requires_manual_review_not_an_automatic_error_label'}
        rank = (severity, dd, record['review_id'])
        entry = (rank, record)
        if len(heap) < limit:
            heapq.heappush(heap, entry)
        elif rank > heap[0][0]:
            heapq.heapreplace(heap, entry)

    for key, data in conflicts.items():
        dd = max(groups[g]['dd'] for g in data['groups'])
        add('complete_neutral_or_identifier_key_in_multiple_groups', key, dd, 100,
            {'citation_kind': data['citation_kind'], 'first_locator': data['first_locator'],
             'other_examples': data['other_examples'],
             'meaning': 'Same printed key has several resolved groups; historical/ambiguous keys need source review'},
            data['groups'])
    for gid, group in groups.items():
        if len(group['court_tokens']) > 1 or group['member_court_conflict']:
            add('conflicting_positive_court_evidence', gid, group['dd'], 95,
                {'court_tokens': sorted(group['court_tokens']), 'member_conflict': group['member_court_conflict'],
                 'examples': group['examples']}, {gid})
        if group['weak_bases'] and group['dd'] >= min_impact_dd:
            add('high_impact_name_year_or_cocitation_identity', gid, group['dd'], 50,
                {'name': group['name'], 'identity_bases': sorted(group['weak_bases']),
                 'examples': group['examples'], 'meaning': 'Heuristic identity needs review; this is not a measured error'}, {gid})

    try:
        typo_path = csv_path(source.run_dir / 'decide_out/cross_court/typo_over_registered.csv')
    except (ValueError, TypeError):
        coverage['registered_typo_artifact_missing'] += 1
    else:
        from tools.foundation.common import artifact_digest
        stat = typo_path.stat()
        snapshot[str(typo_path)] = [stat.st_size, stat.st_mtime_ns]
        typo_sha = artifact_digest(typo_path)
        for number, row in rows(typo_path, ('merge_key', 'folded_into', 'registry_decision_id', 'typo_kind')):
            coverage['registered_fold_rows_scanned'] += 1
            if not row['registry_decision_id'] or not row['typo_kind'].startswith('typo_'):
                continue
            target = first_keys.get(row['folded_into'])
            gids = {target[0]} if target else set()
            dd = groups[target[0]]['dd'] if target else 0
            add('registered_real_decision_folded_as_typo', row['merge_key'] + '->' + row['folded_into'], dd, 99,
                {'row': {k: v[:160] for k, v in row.items()}, 'record': number,
                 'path': str(typo_path), 'logical_sha256': typo_sha, 'row_sha256': canonical_hash(row)}, gids)

    records = [r for _, r in sorted(heap, key=lambda entry: entry[0], reverse=True)]
    # Deterministic first-source examples are previews, never sampling denominators.
    edge_by_group, chosen = {}, {}
    desired_groups = {g for r in records for g in r['group_ids_preview']}
    for edge in edge_rows(source):
        gid = edge['resolved_cited_case']
        if gid not in desired_groups:
            continue
        key = (edge['source_decision'], gid)
        previous = edge_by_group.get(gid)
        if previous is None or key < previous:
            if previous is not None:
                chosen.pop(previous)
            chosen[key] = edge
            edge_by_group[gid] = key
    evidence, ledger_hashes = locate_evidence(source, list(chosen.values()), with_text=with_text)
    for record in records:
        for gid in record['group_ids_preview']:
            if gid in edge_by_group:
                record['evidence_preview'] = evidence[edge_by_group[gid]]
                break
        record['record_hash'] = canonical_hash(record)
    verify_unchanged(snapshot)
    report = {'schema': 'quality_identity_queue_v1', 'run_id': source.run_id, 'frame_id': frame_id,
            'input_identity': identity, 'review_rule_version': 'explicit-identity-review-v1',
            'full_scan_coverage': dict(coverage, groups_scanned=len(groups)),
            'candidate_counts_by_reason': dict(sorted(counts.items())),
            'candidates_total': sum(counts.values()), 'retained_records': len(records),
            'truncated': sum(counts.values()) > len(records), 'limit': limit,
            'min_impact_dd': min_impact_dd, 'evidence_ledger_sha256': ledger_hashes,
            'limitations': ['Queue items are review leads, not human labels or accuracy estimates.',
                            'Positive-court conflicts use stored run evidence; older snapshots may lack these columns.',
                            'Evidence is a bounded first-source preview; use the stratified sample for quality measurement.'],
            'records': records}
    while len((json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8')) > MAX_JSON_BYTES:
        if not report['records']:
            raise ValueError('Queue summary alone exceeds the 2 MiB budget')
        report['records'].pop()
        report['retained_records'] = len(report['records'])
        report['truncated'] = True
        report['truncation_reason'] = '2 MiB JSON output budget'
    return report
