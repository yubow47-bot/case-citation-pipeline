"""Keep unusable source observations auditable without counting their links."""
from collections import defaultdict


def prepare_sources(rows, did_idx, excluded):
    """Mark retained members and remove unusable sources from identity support."""
    filtered = {key: set(ids) - set(excluded) for key, ids in did_idx.items()}
    for row in rows:
        key = row.get('court', '') + '|' + row['merge_key']
        raw = set(did_idx.get(key, ()))
        row['identity_source_status'] = ('excluded_source_only'
            if raw and not filtered.get(key) else 'eligible')
        self_ids = set(filter(None, row.get('self_citation_of', '').split('|')))
        old = set(filter(None, row.get('quarantined_self_citation_of', '').split('|')))
        row['quarantined_self_citation_of'] = '|'.join(sorted(old | (self_ids & set(excluded))))
        row['self_citation_of'] = '|'.join(sorted(self_ids - set(excluded)))
    return filtered


def filter_instances(instances, excluded):
    """Retain the original provenance hashes while selecting admissible instances."""
    if not excluded:
        return instances
    if hasattr(instances, 'verify'):
        instances.verify()
    selected = type(instances)() if hasattr(instances, 'seal') else {}
    for key, instance in instances.items():
        records = instance.get('records', ())
        if not any(r.get('source_decision_citation') in excluded for r in records):
            selected[key] = instance
    return selected.seal(instances.artifacts) if hasattr(selected, 'seal') else selected


def restore_source_audit(rows, out_ids, effective, raw_ids, excluded):
    """Append excluded associations; group DD already uses only admissible sources."""
    by_group = defaultdict(lambda: defaultdict(list))
    seen = {(r['row_key'], r['source_decision_citation']) for r in out_ids}
    for row in rows:
        key = row.get('court', '') + '|' + row['merge_key']
        for source in set(raw_ids.get(key, ())) & set(excluded):
            by_group[row['merged_group_id']][source].append(key)
            if (key, source) not in seen:
                out_ids.append({'row_key': key, 'source_decision_citation': source})
                seen.add((key, source))
    for group, sources in sorted(by_group.items()):
        for source, keys in sorted(sources.items()):
            effective.append({'merged_group_id': group, 'source_decision': source,
                'status': 'excluded_source', 'exclusion_reason': excluded[source],
                'identity_status': 'unmeasurable_source', 'via_member_row_keys': '|'.join(sorted(keys))})
