"""Compare complete runs in place: full counts, bounded examples, no disk database or CSV copies.

Example: python tools/compare_runs.py --old data/run_OLD --new data/run_NEW --output audit/findings/comparison.json
CSV.gz and plain CSV are read transparently. Local group IDs are never cross-run identities.
Exit 0 requires original candidate preservation, complete merged-to-selected coverage,
and unique selected source membership; it does not certify judgment identity accuracy.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import heapq
import io
import itertools
import json
import os
from pathlib import Path
import tempfile

MAX_REPORT_BYTES = 2 * 1024 * 1024
EXAMPLES = 20
MAX_DOCUMENT_CANDIDATES = 20000
csv.field_size_limit(10**9)
CANDIDATE_FIELDS = ('candidate_id', 'corpus_row_index', 'source_decision_citation', 'raw_string',
                    'match_start_offset', 'match_end_offset', 'match_span', 'parse_signature')
COUNT_FIELDS = ('occurrence_count', 'distinct_decisions_count', 'variants_count',
                'candidates_admitted', 'candidates_rejected')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def preview(value, limit=400):
    value = str(value)
    return value if len(value) <= limit else value[:limit] + '…'


def integer(value, name):
    if not isinstance(value, str) or not value.isdigit():
        raise ValueError('Invalid nonnegative count %s: %r' % (name, value))
    return int(value)


def resolve(path):
    path = Path(path)
    if path.is_file():
        return path
    compressed = Path(str(path)+'.gz')
    if compressed.is_file():
        return compressed
    raise FileNotFoundError(str(path)+' (or .gz)')


class HashReader(io.RawIOBase):
    def __init__(self, source):
        self.source, self.hash, self.bytes = source, hashlib.sha256(), 0

    def readable(self):
        return True

    def readinto(self, target):
        count = self.source.readinto(target)
        if count:
            self.hash.update(memoryview(target)[:count])
            self.bytes += count
        return count


class Run:
    def __init__(self, path):
        self.path = Path(path).resolve()
        manifest = self.path/'run_manifest.json'
        if manifest.stat().st_size > MAX_REPORT_BYTES:
            raise ValueError('Run manifest exceeds the byte budget')
        self.manifest = json.loads(manifest.read_text(encoding='utf-8-sig'))
        if self.manifest.get('status') != 'complete' or self.manifest.get('input_identity_verified_unchanged') is not True:
            raise ValueError('Only complete, input-verified runs may be compared: '+str(self.path))
        self.courts = self.manifest.get('params', {}).get('courts', [])
        if not self.courts or len(set(self.courts)) != len(self.courts):
            raise ValueError('Missing or duplicate run court scope')
        self.artifacts = []
        self.manifest_sha256 = hashlib.sha256(manifest.read_bytes()).hexdigest()

    def rows(self, logical, required=()):
        path = resolve(self.path/logical)
        before = path.stat()
        physical = hashlib.sha256()
        with path.open('rb') as source:
            for chunk in iter(lambda: source.read(1024*1024), b''):
                physical.update(chunk)
        physical_sha = physical.hexdigest()
        seal = self.manifest.get('output_identity', {}).get('files', {})
        relative = path.relative_to(self.path).as_posix()
        if seal and seal.get(relative) != physical_sha:
            raise ValueError('Artifact does not match its completed run output seal: '+relative)
        opener = gzip.open if path.suffix == '.gz' else open
        number = 1
        with opener(path, 'rb') as binary:
            hashed = HashReader(binary)
            with io.TextIOWrapper(io.BufferedReader(hashed), encoding='utf-8-sig', newline='') as text:
                reader = csv.DictReader(text, strict=True)
                fields = reader.fieldnames or []
                if len(fields) != len(set(fields)) or set(required)-set(fields):
                    raise ValueError('Missing/duplicate columns: '+logical)
                for number, row in enumerate(reader, 2):
                    if None in row or any(value is None for value in row.values()):
                        raise ValueError('Malformed CSV record %s:%s' % (logical, number))
                    yield number, row
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('Artifact changed during comparison: '+str(path))
        artifact = {'logical_path': logical, 'physical_path': str(path),
                               'physical_sha256': physical_sha, 'content_sha256': hashed.hash.hexdigest(),
                               'logical_bytes': hashed.bytes, 'stored_bytes': after.st_size,
                               'rows': number-1, 'output_seal_verified': bool(seal)}
        previous = next((value for value in self.artifacts if value['logical_path'] == logical), None)
        if previous and previous != artifact:
            raise ValueError('Artifact changed between comparison passes: '+logical)
        if not previous:
            self.artifacts.append(artifact)

    def summary(self):
        return {'run_id': self.path.name, 'directory': str(self.path), 'courts': self.courts,
                'input_fingerprint': self.manifest.get('input_identity', {}).get('fingerprint'),
                'output_fingerprint': self.manifest.get('output_identity', {}).get('fingerprint'),
                'manifest_sha256': self.manifest_sha256,
                'params': {key: self.manifest.get('params', {}).get(key)
                           for key in ('year_from', 'limit_batches', 'batch_size', 'registry_gate', 'mixed_key_holdout')},
                'artifacts': self.artifacts}

    def verify_manifest(self):
        if hashlib.sha256((self.path/'run_manifest.json').read_bytes()).hexdigest() != self.manifest_sha256:
            raise ValueError('Run manifest changed during comparison: '+str(self.path))


def top(counter, n=EXAMPLES):
    values = sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))
    return {'top': [{'value': preview(key), 'count': count} for key, count in values[:n]],
            'other_count': sum(count for _, count in values[n:]), 'distinct_values': len(values)}


def retain(heap, score, key, value):
    row = (score, key, value)
    if len(heap) < EXAMPLES:
        heapq.heappush(heap, row)
    elif row[:2] > heap[0][:2]:
        heapq.heapreplace(heap, row)


def court_order(old, new):
    """A common order exists when one run only adds/removes courts, without reordering shared ones."""
    nodes = list(dict.fromkeys(old+new))
    edges, incoming = defaultdict(set), Counter()
    for sequence in (old, new):
        for left, right in zip(sequence, sequence[1:]):
            if right not in edges[left]:
                edges[left].add(right)
                incoming[right] += 1
    ordered = []
    while len(ordered) < len(nodes):
        ready = [node for node in nodes if node not in ordered and not incoming[node]]
        if not ready:
            raise ValueError('Shared courts were reordered; ordered candidate comparison is not certifiable')
        node = ready[0]
        ordered.append(node)
        for child in edges[node]:
            incoming[child] -= 1
    return {court: index for index, court in enumerate(ordered)}


def candidate_groups(run, order, metrics):
    digest = hashlib.sha256()
    previous = None
    group_key, group = None, []
    for number, row in run.rows('extract_out/candidates.csv', CANDIDATE_FIELDS):
        parts = row['candidate_id'].split(':', 4)
        if len(parts) != 5 or parts[0] not in run.courts or integer(parts[1], 'candidate_id corpus row') != integer(row['corpus_row_index'], 'corpus_row_index'):
            raise ValueError('Candidate ID/row/scope disagreement')
        key = (order[parts[0]], int(parts[1]))
        if previous is not None and key < previous:
            raise ValueError('Candidate documents are not ordered by court and corpus row')
        previous = key
        signature = tuple(row[field] for field in CANDIDATE_FIELDS)
        digest.update((canonical(signature)+'\n').encode('utf-8'))
        metrics['rows'] += 1
        metrics['by_court'][parts[0]] += 1
        if key != group_key and group:
            yield group_key, group
            group = []
        group_key = key
        group.append((signature, number, row.get('shape_name', parts[4])))
        if len(group) > MAX_DOCUMENT_CANDIDATES:
            raise ValueError('Candidate document exceeds the production 20,000 candidate bound')
    if group:
        yield group_key, group
    metrics['ordered_identity_sha256'] = digest.hexdigest()


def compare_candidates(old, new):
    order = court_order(old.courts, new.courts)
    stats = {side: {'rows': 0, 'by_court': Counter()} for side in ('old', 'new')}
    old_iter, new_iter = iter(candidate_groups(old, order, stats['old'])), iter(candidate_groups(new, order, stats['new']))
    left, right = next(old_iter, None), next(new_iter, None)
    added = lost = changed = non_subsequence = 0
    examples, added_shapes, fields_changed = [], Counter(), Counter()
    duplicates = {'old': 0, 'new': 0}
    def example(kind, old_entry=None, new_entry=None):
        if len(examples) < EXAMPLES:
            examples.append({'kind': kind,
                'old': {'record': old_entry[1], 'identity': {field: preview(value) for field, value in zip(CANDIDATE_FIELDS, old_entry[0])}} if old_entry else None,
                'new': {'record': new_entry[1], 'identity': {field: preview(value) for field, value in zip(CANDIDATE_FIELDS, new_entry[0])}} if new_entry else None})
    while left is not None or right is not None:
        if right is None or (left is not None and left[0] < right[0]):
            old_rows, new_rows = left[1], []
            left = next(old_iter, None)
        elif left is None or right[0] < left[0]:
            old_rows, new_rows = [], right[1]
            right = next(new_iter, None)
        else:
            old_rows, new_rows = left[1], right[1]
            left, right = next(old_iter, None), next(new_iter, None)
        maps = []
        for side, records in (('old', old_rows), ('new', new_rows)):
            by_id = defaultdict(list)
            for entry in records:
                by_id[entry[0][0]].append(entry)
            duplicates[side] += sum(len(entries)-1 for entries in by_id.values())
            maps.append(by_id)
        for cid in sorted(maps[0].keys() | maps[1].keys()):
            for a, b in itertools.zip_longest(maps[0].get(cid, []), maps[1].get(cid, [])):
                if a is None:
                    added += 1
                    added_shapes[b[2]] += 1
                    example('added', new_entry=b)
                elif b is None:
                    lost += 1
                    example('lost', old_entry=a)
                elif a[0] != b[0]:
                    changed += 1
                    fields_changed.update(field for field, av, bv in zip(CANDIDATE_FIELDS, a[0], b[0]) if av != bv)
                    example('same_id_changed', a, b)
        index = 0
        for entry in new_rows:
            if index < len(old_rows) and entry[0] == old_rows[index][0]:
                index += 1
        non_subsequence += index != len(old_rows)
    for side in stats:
        stats[side]['by_court'] = dict(stats[side]['by_court'])
    preserved = lost == changed == non_subsequence == 0
    return {'old': stats['old'], 'new': stats['new'], 'added_rows': added, 'lost_rows': lost,
            'same_id_changed_rows': changed, 'documents_failing_legacy_ordered_subsequence': non_subsequence,
            'ordered_identity_equal': stats['old']['ordered_identity_sha256'] == stats['new']['ordered_identity_sha256'],
            'original_candidates_preserved_in_order': preserved, 'preservation_status': 'passed' if preserved else 'failed',
            'same_document_duplicate_candidate_ids': duplicates, 'changed_fields': dict(fields_changed),
            'added_shapes': top(added_shapes), 'examples': examples,
            'identity_fields': list(CANDIDATE_FIELDS), 'example_limit': EXAMPLES,
            'matching': 'Candidate ID plus occurrence ordinal within one corpus document; every raw row is counted, including duplicate IDs.'}


def merge_counts(row):
    return {field: integer(row[field], field) for field in COUNT_FIELDS if field in row}


def compare_merged(old, new):
    reports, examples = {}, []
    for court in dict.fromkeys(old.courts+new.courts):
        original = {}
        old_sums, new_sums, changed_fields = Counter(), Counter(), Counter()
        old_path = 'merge_out/'+court+'/merged.csv'
        if court in old.courts:
            for number, row in old.rows(old_path, ('merge_key', 'occurrence_count', 'distinct_decisions_count')):
                if row['merge_key'] in original:
                    raise ValueError('Duplicate merged key: '+court+'/'+row['merge_key'])
                counts = merge_counts(row)
                old_sums.update(counts)
                original[row['merge_key']] = (counts, preview(row.get('canonical_string', '')), number, row.get('citation_kind', ''))
        old_n, new_n, changed, added = len(original), 0, 0, 0
        seen, fresh_kinds, lost_kinds = set(), Counter(), Counter()
        if court in new.courts:
            for number, row in new.rows(old_path, ('merge_key', 'occurrence_count', 'distinct_decisions_count')):
                key = row['merge_key']
                if key in seen:
                    raise ValueError('Duplicate merged key: '+court+'/'+key)
                seen.add(key)
                new_n += 1
                counts = merge_counts(row)
                new_sums.update(counts)
                prior = original.pop(key, None)
                if prior is None:
                    added += 1
                    fresh_kinds[row.get('citation_kind', '')] += 1
                    retain(examples, counts['distinct_decisions_count'], (court, key), {'court': court, 'merge_key': preview(key),
                        'kind': 'added_key', 'old': None, 'new': counts, 'new_record': number})
                elif prior[0] != counts:
                    changed += 1
                    changed_fields.update(field for field in prior[0].keys() | counts.keys() if prior[0].get(field) != counts.get(field))
                    retain(examples, abs(counts['distinct_decisions_count']-prior[0]['distinct_decisions_count']), (court, key),
                           {'court': court, 'merge_key': preview(key), 'kind': 'existing_key_counts_changed',
                            'old': prior[0], 'new': counts, 'old_record': prior[2], 'new_record': number})
        for key, prior in original.items():
            lost_kinds[prior[3]] += 1
            retain(examples, prior[0]['distinct_decisions_count'], (court, key), {'court': court, 'merge_key': preview(key),
                'kind': 'lost_key', 'old': prior[0], 'new': None, 'old_record': prior[2]})
        reports[court] = {'old_keys': old_n, 'new_keys': new_n, 'added_keys': added, 'lost_keys': len(original),
                         'existing_keys_counts_changed': changed, 'changed_fields': dict(changed_fields),
                         'old_field_sums': dict(old_sums), 'new_field_sums': dict(new_sums),
                         'added_key_kinds': top(fresh_kinds), 'lost_key_kinds': top(lost_kinds)}
    return {'courts': reports, 'examples': [value for _, _, value in sorted(examples, reverse=True)],
            'example_limit': EXAMPLES, 'count_scope': 'Per-court merged keys before cross-court adjudication, full tables.'}


class Union:
    def __init__(self, n):
        self.parent, self.size = list(range(n)), [1]*n

    def find(self, node):
        while node != self.parent[node]:
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def join(self, left, right):
        left, right = self.find(left), self.find(right)
        if left == right:
            return
        if self.size[left] < self.size[right]:
            left, right = right, left
        self.parent[right] = left
        self.size[left] += self.size[right]


def selected(run, registry):
    groups, by_key = {}, defaultdict(set)
    rows = repeated = 0
    fields = ('court', 'merge_key', 'merged_group_id', 'is_primary', 'distinct_decisions_count',
              'kept', 'group_foreign_status', 'group_origin_country')
    for number, row in run.rows('select_out/selected.csv', fields):
        gid = row['merged_group_id']
        if not gid or row['court'] not in run.courts or not row['merge_key']:
            raise ValueError('Invalid selected group/member identity')
        key = (row['court'], row['merge_key'])
        key_id = registry.setdefault(key, len(registry))
        if row['kept'] not in ('true', 'false') or row['is_primary'] not in ('true', 'false'):
            raise ValueError('Invalid selected boolean')
        summary = (integer(row['distinct_decisions_count'], 'DD'), row['kept'] == 'true', row['group_foreign_status'],
                   row['group_origin_country'], row.get('group_origin_status', ''), row.get('group_origin_basis', ''),
                   row.get('group_origin_evidence_ids', ''))
        group = groups.setdefault(gid, {'members': set(), 'summary': summary, 'primary_records': []})
        if group['summary'] != summary:
            raise ValueError('Selected group metadata disagrees across members: '+gid)
        repeated += key_id in group['members']
        group['members'].add(key_id)
        by_key[key_id].add(gid)
        if row['is_primary'] == 'true':
            group['primary_records'].append(number)
            name = row.get('case_name_modal', '')
            group['name'] = preview(name, 180)
            group['name_hash'] = hashlib.sha256(name.encode('utf-8')).hexdigest()
            group['primary_merge_key'] = preview(row['merge_key'])
            group['split_reason'] = preview(row.get('split_reason', ''))
            group['identity_basis'] = preview(row.get('identity_basis', ''))
            group['observed_deciding_court'] = preview(row.get('group_observed_deciding_court', ''))
        rows += 1
    if any(len(group['primary_records']) != 1 for group in groups.values()):
        raise ValueError('Selected groups require exactly one primary row')
    return groups, by_key, {'rows': rows, 'groups': len(groups), 'stable_member_keys': len(by_key),
                           'dd_sum': sum(group['summary'][0] for group in groups.values()),
                           'kept_groups': sum(group['summary'][1] for group in groups.values()),
                           'repeated_same_group_member_rows': repeated,
                           'member_keys_in_multiple_groups': sum(len(gids)>1 for gids in by_key.values())}


def merged_selected_coverage(run, selected_keys, registry):
    """Direct full input-to-output membership check, independent of DD consistency."""
    matched, input_rows, missing = set(), 0, 0
    examples = []
    for court in run.courts:
        logical = 'merge_out/'+court+'/merged.csv'
        for number, row in run.rows(logical, ('merge_key', 'distinct_decisions_count')):
            input_rows += 1
            key_id = registry.get((court, row['merge_key']))
            if key_id is None or key_id not in selected_keys:
                missing += 1
                retain(examples, integer(row['distinct_decisions_count'], 'merged DD'), (court, row['merge_key']),
                       {'court': court, 'merge_key': preview(row['merge_key']), 'input_record': number,
                        'canonical_string': preview(row.get('canonical_string', '')),
                        'input_dd': integer(row['distinct_decisions_count'], 'merged DD')})
            else:
                matched.add(key_id)
    key_names = list(registry)
    extras = selected_keys.keys()-matched
    return {'merged_input_rows': input_rows, 'selected_stable_keys': len(selected_keys),
            'merged_input_keys_missing_from_selected': missing,
            'selected_keys_without_merged_input': len(extras), 'matched_input_member_keys': len(matched),
            'status': 'passed' if missing == len(extras) == 0 else 'failed',
            'missing_input_examples': [value for _, _, value in sorted(examples, reverse=True)],
            'extra_selected_examples': [{'court': key_names[kid][0], 'merge_key': preview(key_names[kid][1])}
                                        for kid in sorted(extras, key=lambda kid: key_names[kid])[:EXAMPLES]],
            'meaning': 'Every per-court merged input key should survive as selected (court, merge_key) membership. Group merging never excuses silently dropping these source member rows.'}


def compare_selected(old, new):
    registry = {}
    old_groups, old_keys, old_stats = selected(old, registry)
    new_groups, new_keys, new_stats = selected(new, registry)
    coverage = {'old': merged_selected_coverage(old, old_keys, registry),
                'new': merged_selected_coverage(new, new_keys, registry)}
    old_ids, new_ids = list(old_groups), list(new_groups)
    old_index = {gid: index for index, gid in enumerate(old_ids)}
    new_index = {gid: len(old_ids)+index for index, gid in enumerate(new_ids)}
    union = Union(len(old_ids)+len(new_ids))
    for key in old_keys.keys() & new_keys.keys():
        nodes = [old_index[gid] for gid in old_keys[key]] + [new_index[gid] for gid in new_keys[key]]
        for node in nodes[1:]:
            union.join(nodes[0], node)
    components = defaultdict(lambda: [[], []])
    for gid in old_ids:
        components[union.find(old_index[gid])][0].append(gid)
    for gid in new_ids:
        components[union.find(new_index[gid])][1].append(gid)
    kinds = ('new_only', 'old_only', 'one_to_one_same_membership', 'one_to_one_changed_membership', 'split', 'merge', 'many_to_many')
    stats = Counter({kind+'_'+suffix: 0 for kind in kinds for suffix in ('components', 'old_groups', 'new_groups')})
    stats.update({key: 0 for key in ('components_with_dd_sum_change', 'components_with_kept_count_change',
                 'components_with_origin_value_set_change', 'one_to_one_dd_changed', 'one_to_one_kept_changed',
                 'one_to_one_origin_values_changed', 'one_to_one_origin_evidence_changed', 'one_to_one_primary_name_changed',
                 'same_membership_dd_changed', 'same_membership_kept_changed', 'same_membership_origin_values_changed')})
    dd_directions, kept_transitions, origin_transitions = Counter(), Counter(), Counter()
    category_totals = {kind: Counter({field: 0 for field in ('old_groups', 'new_groups', 'group_count_delta',
        'old_kept', 'new_kept', 'kept_count_delta', 'old_dd_sum', 'new_dd_sum', 'dd_sum_delta')}) for kind in kinds}
    examples = []
    key_names = list(registry)
    def group_brief(gid, groups):
        group = groups[gid]
        dd, kept, foreign, country, origin, _, _ = group['summary']
        return {'local_group_id': preview(gid, 100), 'name': group['name'], 'dd': dd, 'kept': kept,
                'foreign_status': preview(foreign, 50), 'origin_country': preview(country, 50),
                'origin_status': preview(origin, 50), 'primary_record': group['primary_records'][0],
                'primary_merge_key': group['primary_merge_key'], 'split_reason': group['split_reason'],
                'primary_identity_basis': group['identity_basis'],
                'observed_deciding_court': group['observed_deciding_court'],
                'member_keys': len(group['members'])}
    for olds, news in components.values():
        a, b = len(olds), len(news)
        old_members = set().union(*(old_groups[gid]['members'] for gid in olds))
        new_members = set().union(*(new_groups[gid]['members'] for gid in news))
        if not a:
            kind = 'new_only'
        elif not b:
            kind = 'old_only'
        elif a == b == 1:
            kind = 'one_to_one_same_membership' if old_members == new_members else 'one_to_one_changed_membership'
        elif a == 1:
            kind = 'split'
        elif b == 1:
            kind = 'merge'
        else:
            kind = 'many_to_many'
        stats[kind+'_components'] += 1
        stats[kind+'_old_groups'] += a
        stats[kind+'_new_groups'] += b
        before_dd = sum(old_groups[gid]['summary'][0] for gid in olds)
        after_dd = sum(new_groups[gid]['summary'][0] for gid in news)
        before_kept = sum(old_groups[gid]['summary'][1] for gid in olds)
        after_kept = sum(new_groups[gid]['summary'][1] for gid in news)
        delta = after_dd-before_dd
        category_totals[kind].update({'old_groups': a, 'new_groups': b, 'group_count_delta': b-a,
            'old_kept': before_kept, 'new_kept': after_kept, 'kept_count_delta': after_kept-before_kept,
            'old_dd_sum': before_dd, 'new_dd_sum': after_dd, 'dd_sum_delta': delta})
        stats['components_with_dd_sum_change'] += delta != 0
        stats['components_with_kept_count_change'] += before_kept != after_kept
        dd_directions['increased' if delta > 0 else 'decreased' if delta < 0 else 'unchanged'] += 1
        origins_a = sorted({group['summary'][2:5] for gid in olds for group in [old_groups[gid]]})
        origins_b = sorted({group['summary'][2:5] for gid in news for group in [new_groups[gid]]})
        origin_changed = origins_a != origins_b
        stats['components_with_origin_value_set_change'] += origin_changed
        metadata_changed = False
        if a == b == 1:
            left, right = old_groups[olds[0]]['summary'], new_groups[news[0]]['summary']
            stats['one_to_one_dd_changed'] += left[0] != right[0]
            stats['one_to_one_kept_changed'] += left[1] != right[1]
            stats['one_to_one_origin_values_changed'] += left[2:5] != right[2:5]
            stats['one_to_one_origin_evidence_changed'] += left[5:] != right[5:]
            name_changed = old_groups[olds[0]]['name_hash'] != new_groups[news[0]]['name_hash']
            stats['one_to_one_primary_name_changed'] += name_changed
            if kind == 'one_to_one_same_membership':
                stats['same_membership_dd_changed'] += left[0] != right[0]
                stats['same_membership_kept_changed'] += left[1] != right[1]
                stats['same_membership_origin_values_changed'] += left[2:5] != right[2:5]
            kept_transitions[str(left[1]).lower()+'→'+str(right[1]).lower()] += 1
            origin_transitions[left[2]+'→'+right[2]] += 1
            metadata_changed = left != right or name_changed
        if kind != 'one_to_one_same_membership' or metadata_changed:
            member_sample = sorted(old_members | new_members, key=lambda kid: key_names[kid])[:EXAMPLES]
            value = {'kind': kind, 'old_group_count': a, 'new_group_count': b, 'old_dd_sum': before_dd,
                     'new_dd_sum': after_dd, 'dd_sum_delta': delta, 'old_kept_count': before_kept,
                     'new_kept_count': after_kept, 'origin_value_set_changed': origin_changed,
                     'old_member_keys': len(old_members), 'new_member_keys': len(new_members),
                     'shared_member_keys': len(old_members & new_members), 'member_preview_limit': EXAMPLES,
                     'member_preview': [{'court': key_names[kid][0], 'merge_key': preview(key_names[kid][1])} for kid in member_sample],
                     'old_groups': [group_brief(gid, old_groups) for gid in sorted(olds)[:EXAMPLES]],
                     'new_groups': [group_brief(gid, new_groups) for gid in sorted(news)[:EXAMPLES]]}
            retain(examples, (abs(delta), abs(b-a), len(old_members | new_members)),
                   (tuple(member_sample), tuple(sorted(olds)), tuple(sorted(news))), value)
    return {'old': old_stats, 'new': new_stats, 'stable_keys_added': len(new_keys.keys()-old_keys.keys()),
            'stable_keys_lost': len(old_keys.keys()-new_keys.keys()), 'stable_keys_shared': len(old_keys.keys() & new_keys.keys()),
            'components': dict(stats), 'component_dd_direction': dict(dd_directions), 'one_to_one_kept_transitions': dict(kept_transitions),
            'category_totals': {kind: dict(value) for kind, value in category_totals.items()},
            'one_to_one_foreign_status_transitions': top(origin_transitions),
            'merged_input_membership_coverage': coverage,
            'examples': [value for _, _, value in sorted(examples, reverse=True)], 'example_limit': EXAMPLES,
            'matching': 'Connected components of old/new groups sharing exact (court, merge_key) membership; local group IDs are never compared across runs.',
            'interpretation': 'Splits/merges are structural membership changes, not proof of correct judgment identity. DD sums count edges and can change when group membership changes.'}


def compare(old_dir, new_dir):
    old, new = Run(old_dir), Run(new_dir)
    if old.path == new.path:
        raise ValueError('Choose two distinct run directories')
    shared_courts = sorted(set(old.courts) & set(new.courts))
    old_inputs = old.manifest.get('input_identity', {}).get('files', {})
    new_inputs = new.manifest.get('input_identity', {}).get('files', {})
    changed_corpus = [court for court in shared_courts if not old_inputs.get('corpus/'+court+'.parquet') or
                      old_inputs.get('corpus/'+court+'.parquet') != new_inputs.get('corpus/'+court+'.parquet')]
    candidates = compare_candidates(old, new)
    merged = compare_merged(old, new)
    identities = compare_selected(old, new)
    old.verify_manifest()
    new.verify_manifest()
    report = {'schema': 'run_comparison_v1', 'status': 'compared', 'candidates': candidates, 'merged': merged,
              'selected_identity': identities, 'old': old.summary(), 'new': new.summary(),
              'input_scope': {'shared_courts': shared_courts, 'changed_or_missing_shared_corpus_hashes': changed_corpus,
                              'same_court_scope': old.courts == new.courts,
                              'old_text_policy': old.manifest.get('params',{}).get('text_policy','english_only'),
                              'new_text_policy': new.manifest.get('params',{}).get('text_policy','english_only')},
              'limits': {'max_report_bytes': MAX_REPORT_BYTES, 'examples_per_section': EXAMPLES,
                         'max_candidates_in_one_document': MAX_DOCUMENT_CANDIDATES,
                         'persistent_databases_created': 0, 'uncompressed_csv_copies_created': 0},
              'warnings': ['Counts cover the complete CSV artifacts. Examples are bounded, not an accuracy sample.',
                           'No new semantic precision, causal attribution or population calibration is established by this comparison.']}
    report['invariants'] = {
        'legacy_candidate_preservation': candidates['original_candidates_preserved_in_order'],
        'merged_to_selected_member_coverage': all(value['status'] == 'passed'
            for value in identities['merged_input_membership_coverage'].values()),
        'selected_unique_source_membership': all(identities[side]['repeated_same_group_member_rows'] == 0 and
            identities[side]['member_keys_in_multiple_groups'] == 0 for side in ('old', 'new'))}
    report['validation_status'] = 'passed' if all(report['invariants'].values()) else 'failed'
    if changed_corpus:
        report['warnings'].append('Shared court corpus snapshots differ; changes cannot be attributed solely to code/identity rules.')
    if report['input_scope']['old_text_policy'] != report['input_scope']['new_text_policy']:
        report['warnings'].append('Text-language processing scopes differ. New source judgments can reflect French-only fallback; count changes are not solely identity-rule effects.')
    if not candidates['original_candidates_preserved_in_order']:
        report['warnings'].append('Original candidate preservation failed; identity/DD changes are confounded by upstream candidate changes.')
    if any(value['status'] != 'passed' for value in identities['merged_input_membership_coverage'].values()):
        report['warnings'].append('Merged-to-selected source membership coverage failed. Do not adopt the new run until missing/extra input member keys are explained or repaired.')
    if not report['invariants']['selected_unique_source_membership']:
        report['warnings'].append('Selected source members are repeated within/across groups. Source membership is not uniquely certified.')
    if any(not artifact['output_seal_verified'] for run in (old, new) for artifact in run.artifacts):
        report['warnings'].append('A historical run has no output seal; current logical/physical hashes are recorded without claiming historical byte certification.')
    encoded = (json.dumps(report, ensure_ascii=False, indent=2)+'\n').encode('utf-8')
    if len(encoded) > MAX_REPORT_BYTES:
        raise ValueError('Comparison report exceeds the 2 MiB output budget')
    return report


def save(path, report):
    path = Path(path).resolve()
    if path.suffix.lower() != '.json':
        raise ValueError('Comparison output must be a JSON artifact')
    for side in ('old', 'new'):
        folder = Path(report[side]['directory']).resolve()
        if path == folder or folder in path.parents:
            raise ValueError('Comparison cannot write into either source run')
    payload = (json.dumps(report, ensure_ascii=False, indent=2)+'\n').encode('utf-8')
    if len(payload) > MAX_REPORT_BYTES:
        raise ValueError('Comparison report exceeds the byte budget')
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old', required=True)
    parser.add_argument('--new', required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    report = compare(args.old, args.new)
    if args.output:
        save(args.output, report)
    # JSON on stdout remains usable under Windows legacy console encodings.
    # The saved UTF-8 artifact keeps original Unicode evidence strings.
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report['validation_status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
