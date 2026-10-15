"""Independent probability supplement for the run's selected French text field."""
from collections import Counter
import hashlib
from pathlib import Path
import re

try:
    from .common import (ROOT, canonical_hash, file_hash, frame_identity, verify_unchanged)
    from .sample import stratified_sample
    from .labels import _load_samples
except ImportError:
    from common import ROOT, canonical_hash, file_hash, frame_identity, verify_unchanged
    from sample import stratified_sample
    from labels import _load_samples

from pipeline.corpus_fields import policy_from_manifest, projection, select_record
from tools.storage import preflight, MiB

MAX_SOURCE_IDS = 250000
MAX_SOURCE_ID_CHARS = 512
ESTIMATED_OUTPUT_PEAK_BYTES = 8 * MiB


def original_language_census(source, max_source_ids=MAX_SOURCE_IDS):
    """Read small Parquet batches; retain only bounded source-ID language bits.

    Language means the selected original column, not an automatic linguistic
    judgment. A source ID with mixed/empty duplicate rows is explicitly outside
    the unambiguous French domain, rather than assigned a guessed language.
    """
    import pyarrow.parquet as pq
    policy = policy_from_manifest(source.manifest)
    directory = Path(source.manifest['params']['corpus_dir'])
    helper_path = ROOT / 'pipeline/corpus_fields.py'
    helper_sha = file_hash(helper_path)
    expected_helper = source.manifest['input_identity'].get('files', {}).get('pipeline/corpus_fields.py')
    if expected_helper is not None and expected_helper != helper_sha:
        raise ValueError('Original language selector differs from the recorded producer')
    states, counts, bindings, snapshot = {}, Counter(), [], {}
    selection_digest = hashlib.sha256()
    for court in sorted(source.manifest['params']['courts']):
        path = (directory / (court + '.parquet')).resolve()
        expected = source.manifest['input_identity'].get('files', {}).get('corpus/' + court + '.parquet')
        before = path.stat()
        actual = file_hash(path)
        if not expected or actual != expected:
            raise ValueError('Language census corpus differs from recorded input: ' + str(path))
        documents = iter(source.db.execute(
            'SELECT * FROM documents WHERE run_id=? AND court=? ORDER BY corpus_row', (source.run_id, court)))
        pf = pq.ParquetFile(path)
        row_number = 0
        for batch in pf.iter_batches(batch_size=8, columns=projection(pf.schema_arrow.names, include_text=True)):
            for original in batch.to_pylist():
                chosen = select_record(original, policy)
                sid = court + '_' + re.sub('[^A-Za-z0-9]', '', chosen['citation']).lower()
                document = next(documents, None)
                if document is None or int(document['corpus_row']) != row_number or \
                        document['source_id'] != sid or document['citation'] != chosen['citation'] or \
                        document['name'] != chosen['name'] or document['decision_date'] != str(chosen['date'] or '') or \
                        Path(document['corpus_path']).resolve() != path:
                    raise ValueError('Language census disagrees with imported original document metadata')
                nonempty = bool(chosen['text'].strip())
                language = chosen['language'] if nonempty else 'empty'
                counts['rows/' + language] += 1
                valid = bool(chosen['citation'].strip()) and sid != court + '_'
                selection_digest.update((canonical_hash([
                    court, row_number, sid, chosen['citation_field'], chosen['text_field'], language, valid]) + '\n').encode())
                if valid:
                    if len(sid) > MAX_SOURCE_ID_CHARS:
                        raise ValueError('Source ID exceeds the bounded language census protocol')
                    if sid not in states and len(states) >= max_source_ids:
                        raise ValueError('Language census source-ID memory budget exceeded')
                    states[sid] = states.get(sid, 0) | {'en': 1, 'fr': 2, 'empty': 4}[language]
                else:
                    counts['invalid_source_rows/' + language] += 1
                row_number += 1
        if next(documents, None) is not None:
            raise ValueError('Imported document rows exceed the original corpus language census')
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or file_hash(path) != expected:
            raise ValueError('Corpus changed during original language census')
        snapshot[str(path)] = [after.st_size, after.st_mtime_ns]
        bindings.append({'court': court, 'path': str(path), 'sha256': actual, 'rows': row_number})
    eligible = {sid for sid, bits in states.items() if bits == 2}
    for bits in states.values():
        counts['source_ids/' + {1: 'en', 2: 'fr', 4: 'empty'}.get(bits, 'ambiguous_duplicate_rows')] += 1
    identity = {
        'protocol': 'original-selected-french-source-v1', 'text_policy': policy,
        'selected_text_field': 'unofficial_text_fr', 'language_meaning': 'Original selected field, not inferred natural-language content',
        'membership_rule': 'Every original row for a valid source ID selects nonempty unofficial_text_fr; mixed/empty duplicate-row IDs are excluded',
        'counts': dict(counts), 'source_selection_sha256': selection_digest.hexdigest(),
        'eligible_source_ids_sha256': canonical_hash(sorted(eligible)), 'eligible_source_ids': len(eligible),
        'corpus_bindings': bindings, 'selector_sha256': helper_sha,
        'language_sampler_sha256': file_hash(Path(__file__)),
        'stratified_sampler_sha256': file_hash(Path(__file__).with_name('sample.py')),
        'memory_limits': {'max_source_ids': max_source_ids, 'max_source_id_chars': MAX_SOURCE_ID_CHARS,
                          'parquet_batch_rows': 8, 'persistent_corpus_or_db_copies': 0}}
    return eligible, identity, snapshot


def french_supplement(source, base_samples_path, seed=20261015):
    """Sample only FR-selected countable edges; retain the parent's source fold."""
    storage = preflight(ROOT, ESTIMATED_OUTPUT_PEAK_BYTES)
    base_path = Path(base_samples_path).resolve()
    before = base_path.stat()
    baseline, _ = _load_samples(base_path)
    base_sha = file_hash(base_path)
    parent_frame, _, _ = frame_identity(source)
    if baseline['run_id'] != source.run_id or baseline['frame_id'] != parent_frame or baseline.get('supplement_id'):
        raise ValueError('French supplement requires the unchanged main sample for the same source frame')
    for record in baseline['records']:
        expected_fold = int(canonical_hash({'seed': baseline['seed'], 'source': record['edge']['source_decision'],
                                            'fold_protocol': 'source-v1'}), 16) % 5
        if record['fold'] != ('holdout' if expected_fold == 0 else 'train'):
            raise ValueError('Parent sample does not follow the source-v1 fold protocol')
    eligible, identity, corpus_snapshot = original_language_census(source)
    result = stratified_sample(source, seed=seed, with_text=True, fold_seed=baseline['seed'], _domain={
        'source_ids': eligible, 'identity': identity, 'language': 'fr',
        'definition': 'Every final countable edge whose valid source ID unambiguously selects nonempty original unofficial_text_fr under the recorded run policy; no DD/top-k/origin filter'})
    if result['parent_frame_N'] != baseline['frame_N']:
        raise ValueError('French supplement parent population differs from the preserved main sample')
    for record in result['records']:
        evidence = record['evidence']
        if evidence['status'] == 'original_text_verified' and (
                evidence['field_selection'].get('text_field') != 'unofficial_text_fr' or
                evidence['field_selection'].get('language') != 'fr'):
            raise ValueError('Original span proof contradicts the selected French population')
        # Population membership comes from the complete original-field census.
        # Missing mention evidence stays in the sample and its denominator; it
        # is never silently replaced with a more easily verifiable edge.
        record['language_membership'] = {
            'text_field': 'unofficial_text_fr', 'language': 'fr',
            'verification': 'original_corpus_selection_census_verified',
            'source_selection_sha256': identity['source_selection_sha256']}
        record['record_hash'] = canonical_hash({k: v for k, v in record.items() if k != 'record_hash'})
    verify_unchanged(corpus_snapshot)
    after = base_path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or file_hash(base_path) != base_sha:
        raise ValueError('Parent sample changed while creating the supplement')
    result.update(supplement_id='selected_french_v1', parent_samples_hash=canonical_hash(baseline),
                  parent_samples_sha256=base_sha, parent_samples_path=str(base_path),
                  parent_fold_seed=baseline['seed'], storage_preflight=storage)
    return result
