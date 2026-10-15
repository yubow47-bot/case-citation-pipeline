"""Fixed-seed stratified samples of the complete countable-edge frame."""
from collections import defaultdict
import heapq
from pathlib import Path

try:
    from .common import (canonical_hash, frame_identity, member_rows, edge_rows,
                         document_metadata, brief_edge, locate_evidence, verify_unchanged, csv_path)
except ImportError:
    from common import (canonical_hash, frame_identity, member_rows, edge_rows,
                        document_metadata, brief_edge, locate_evidence, verify_unchanged, csv_path)


def era(year):
    if year is None:
        return 'unknown'
    return '<=1949' if year <= 1949 else '1950-1999' if year <= 1999 else '2000+'


def dd_band(dd):
    if dd < 0:
        raise ValueError('Negative group DD')
    return '0-4' if dd < 5 else '5-19' if dd < 20 else '20-99' if dd < 100 else '100+'


def stratified_sample(source, seed=20261014, per_cell=2, with_text=False, *, _domain=None, fold_seed=None):
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError('seed must be an integer')
    if per_cell != 2:
        raise ValueError('This review protocol samples exactly 2 per nonempty cell (or its full population if N<2)')
    frame_id, identity, snapshot = frame_identity(source)
    parent_frame_id = frame_id
    if _domain is not None:
        frame_id = canonical_hash({'parent_frame_id': frame_id, 'domain': _domain['identity']})
    if fold_seed is None:
        fold_seed = seed
    if not isinstance(fold_seed, int) or isinstance(fold_seed, bool):
        raise ValueError('fold_seed must be an integer')
    group_kinds = defaultdict(set)
    for _, row in member_rows(source):
        kind = row.get('citation_kind') or 'unknown'
        if kind not in ('neutral', 'identifier', 'reporter', 'unknown'):
            kind = 'other'
        group_kinds[row['merged_group_id']].add(kind)
    groups = {r['group_id']: r['dd'] for r in source.db.execute(
        'SELECT group_id,dd FROM case_groups WHERE run_id=?', (source.run_id,))}
    documents = document_metadata(source)
    populations, strata, heaps = defaultdict(int), {}, defaultdict(list)
    frame_N = missing_metadata = parent_frame_N = 0
    for edge in edge_rows(source):
        parent_frame_N += 1
        if _domain is not None and edge['source_decision'] not in _domain['source_ids']:
            continue
        gid = edge['resolved_cited_case']
        dd = groups[gid]
        if int(edge['distinct_decisions_count']) != dd:
            raise ValueError('Edge DD disagrees with its resolved group: ' + gid)
        document = documents.get(edge['source_decision'], {})
        court, year = document.get('court', 'UNKNOWN'), document.get('year')
        if not document or year is None or court == 'UNKNOWN':
            missing_metadata += 1
        kinds = group_kinds[gid]
        kind = next(iter(kinds)) if len(kinds) == 1 else 'mixed' if kinds else 'unknown'
        stratum = {'citing_court': court, 'citing_judgment_era': era(year),
                   'dd_band': dd_band(dd), 'citation_kind': kind, 'edge_support': edge['edge_support']}
        if _domain is not None:
            stratum['selected_text_language'] = _domain['language']
        cell = canonical_hash(stratum)[:24]
        strata[cell] = stratum
        populations[cell] += 1
        frame_N += 1
        rank = int(canonical_hash({'seed': seed, 'frame_id': frame_id,
                                   'source': edge['source_decision'], 'group': gid}), 16)
        key = (edge['source_decision'], gid)
        entry = (-rank, key, edge)
        heap = heaps[cell]
        if len(heap) < per_cell:
            heapq.heappush(heap, entry)
        elif rank < -heap[0][0]:
            heapq.heapreplace(heap, entry)
    records, full_edges = [], []
    try:
        edge_path = str(csv_path(source.run_dir / 'edges/citation_edges.csv'))
    except (ValueError, TypeError):
        edge_path = source.provenance['db_path']
    for cell in sorted(heaps):
        N, n = populations[cell], len(heaps[cell])
        for selection_rank, (_, key, edge) in enumerate(sorted(heaps[cell], key=lambda r: (-r[0], r[1])), 1):
            sample_id = canonical_hash({'frame_id': frame_id, 'seed': seed, 'cell_id': cell,
                                        'source': key[0], 'group': key[1]})
            # A source judgment stays in one fold even if several of its edges
            # land in different strata; this reduces source-context leakage.
            fold_number = int(canonical_hash({'seed': fold_seed, 'source': key[0], 'fold_protocol': 'source-v1'}), 16) % 5
            record = {'sample_id': sample_id, 'run_id': source.run_id, 'frame_id': frame_id,
                      'cell_id': cell, 'stratum': strata[cell], 'N_cell': N, 'n_cell': n,
                      'pi': n / N, 'fold': 'holdout' if fold_number == 0 else 'train',
                      'selection_rank': selection_rank, 'edge': brief_edge(edge),
                      'source_locator': {'logical_path': 'edges/citation_edges.csv', 'path': edge_path,
                                         'record': int(edge['row_number']),
                                         'logical_sha256': identity['artifact_logical_sha256']['edges/citation_edges.csv']},
                      'source_sha256': identity['artifact_logical_sha256']['edges/citation_edges.csv']}
            records.append(record)
            full_edges.append(edge)
    evidence, ledger_hashes = locate_evidence(source, full_edges, with_text=with_text)
    for record in records:
        key = (record['edge']['source_decision'], record['edge']['resolved_cited_case'])
        record['evidence'] = evidence[key]
        record['record_hash'] = canonical_hash(record)
    verify_unchanged(snapshot)
    result = {'schema': 'quality_sample_v1', 'run_id': source.run_id, 'frame_id': frame_id,
            'input_identity': identity, 'source_provenance': {
                'run_directory': str(source.run_dir),
                'corpus_directory': source.manifest['params'].get('corpus_dir'),
                'db_path': source.provenance.get('db_path')},
            'seed': seed, 'per_cell': per_cell, 'frame_N': frame_N, 'sample_n': len(records),
            'frame_definition': 'Every final countable citation_edges pair in this run; no DD/top-k/origin filter',
            'stratum_definition': 'Citing judgment court and validated document date; target group DD and member citation-kind category; edge support',
            'fold_protocol': 'source-v1: stable seed/source judgment hash, 1 of 5 buckets held out',
            'sampling_protocol': 'Uniform seeded hash ordering within every nonempty cell; n=min(2,N), pi=n/N',
            'date_metadata_unknown_edges': missing_metadata,
            'cells': [{'cell_id': cell, 'stratum': strata[cell], 'N_cell': populations[cell],
                       'n_cell': len(heaps[cell]), 'pi': len(heaps[cell]) / populations[cell]}
                      for cell in sorted(populations)],
            'evidence_ledger_sha256': ledger_hashes,
            'label_status': 'No human labels supplied; no new precision/calibration is claimed',
            'limitations': ['A two-record cell has very high sampling uncertainty; no confidence interval is claimed.',
                            'Unknown/conflicting document dates stay in explicit unknown strata.',
                            'Mixed citation-kind groups are a separate category rather than guessed from a top hit.',
                            'Countable edges measure mentions; treatment and correct judgment identity need independent labels.'],
            'records': records}
    if _domain is not None:
        result.update(parent_frame_id=parent_frame_id, parent_frame_N=parent_frame_N,
                      frame_definition=_domain['definition'], language_frame=_domain['identity'],
                      fold_seed=fold_seed,
                      fold_protocol='source-v1 with parent fold_seed; source judgment remains in its original fold',
                      stratum_definition=result['stratum_definition'] + '; original selected text language',
                      limitations=result['limitations'] + [
                          'This supplement describes only its French-selected subpopulation, not the full parent edge population.',
                          'Do not pool its inverse-probability weights with the parent sample without a joint inclusion design.'])
    return result
