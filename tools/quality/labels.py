"""Bounded human/model review labels and descriptive train/holdout evaluation.

All rates describe the labelled, verifiable subset. No function publishes population accuracy,
updates DD or writes calibration weights. Labels bind to an immutable sample record hash.
"""
from __future__ import annotations

from collections import Counter
import csv
import datetime
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import tempfile

try:
    from .common import canonical_hash, read_bounded_json, write_bounded_json, protected_output, MAX_JSON_BYTES, MAX_CSV_BYTES
except ImportError:
    from common import canonical_hash, read_bounded_json, write_bounded_json, protected_output, MAX_JSON_BYTES, MAX_CSV_BYTES

ENUMS = {
    'case_mention': ('yes', 'no', 'unknown', 'unverifiable'),
    'judgment_identity': ('correct', 'incorrect', 'unknown', 'unverifiable'),
    'treatment_role': ('supportive', 'applied', 'distinguished', 'criticized', 'overruled',
                       'procedural', 'mentioned', 'unknown', 'unverifiable'),
    'origin': ('correct', 'incorrect', 'unknown', 'unverifiable'),
}
LABEL_METHODS = ('manual', 'model')
LABEL_FIELDS = tuple(ENUMS) + ('origin_country', 'annotator', 'label_method', 'notes', 'annotated_at')
# Keep the existing CSV/template API compatible for saved manual review sheets.
MANUAL_FIELDS = LABEL_FIELDS
IDENTITY_FIELDS = ('sample_id', 'record_hash', 'run_id', 'frame_id', 'cell_id', 'fold')
CSV_FIELDS = IDENTITY_FIELDS + ('source_decision', 'resolved_cited_case', 'source_locator', 'source_sha256') + LABEL_FIELDS
MAX_ROWS = 10000
MAX_CELL_TEXT = 16384
SHA256 = re.compile(r'^[0-9a-f]{64}$')


def _text(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > 10**12:
        raise ValueError('Invalid sampling count: ' + name)
    return value


def _load_samples(path):
    samples = read_bounded_json(path)
    if not isinstance(samples, dict) or samples.get('schema') != 'quality_sample_v1':
        raise ValueError('Unsupported sample schema')
    for field in ('run_id', 'frame_id'):
        if not isinstance(samples.get(field), str) or not samples[field]:
            raise ValueError('Missing sample frame identity: ' + field)
    if isinstance(samples.get('seed'), bool) or not isinstance(samples.get('seed'), int):
        raise ValueError('Sampling seed must be an integer')
    frame_n = _integer(samples.get('frame_N'), 'frame_N')
    cells, records = samples.get('cells'), samples.get('records')
    if not isinstance(cells, list) or not isinstance(records, list) or len(records) > MAX_ROWS:
        raise ValueError('Invalid or over-budget sample records/cells')
    cell_map = {}
    for cell in cells:
        if not isinstance(cell, dict) or not isinstance(cell.get('cell_id'), str) or not cell['cell_id'] or cell['cell_id'] in cell_map:
            raise ValueError('Missing or duplicate sample cell identity')
        n, big_n = _integer(cell.get('n_cell'), 'n_cell'), _integer(cell.get('N_cell'), 'N_cell')
        if n > big_n or (n and not big_n):
            raise ValueError('Sample size exceeds its cell frame')
        cell_map[cell['cell_id']] = cell
    if sum(c['N_cell'] for c in cells) != frame_n:
        raise ValueError('Cell population counts do not match frame_N')
    by_id, sampled_counts = {}, Counter()
    for rec in records:
        if not isinstance(rec, dict):
            raise ValueError('Malformed sample record')
        sid, sha = rec.get('sample_id'), rec.get('record_hash')
        if not isinstance(sid, str) or not sid or sid in by_id:
            raise ValueError('Missing or duplicate sample_id')
        if not isinstance(sha, str) or not SHA256.fullmatch(sha) or canonical_hash({k: v for k, v in rec.items() if k != 'record_hash'}) != sha:
            raise ValueError('Sample record hash mismatch: ' + sid)
        if rec.get('run_id') != samples['run_id'] or rec.get('frame_id') != samples['frame_id']:
            raise ValueError('Sample record belongs to another run/frame: ' + sid)
        cell = cell_map.get(rec.get('cell_id'))
        if not cell or rec.get('N_cell') != cell['N_cell'] or rec.get('n_cell') != cell['n_cell'] or cell['n_cell'] < 1:
            raise ValueError('Sample record disagrees with its design cell: ' + sid)
        pi = rec.get('pi')
        if isinstance(pi, bool) or not isinstance(pi, (int, float)) or not math.isfinite(pi) or not 0 < pi <= 1:
            raise ValueError('Invalid inclusion probability: ' + sid)
        if not math.isclose(pi, cell['n_cell']/cell['N_cell'], rel_tol=1e-12, abs_tol=0):
            raise ValueError('Inclusion probability differs from n_cell/N_cell: ' + sid)
        if rec.get('fold') not in ('train', 'holdout') or not isinstance(rec.get('edge'), dict):
            raise ValueError('Invalid sample fold or edge: ' + sid)
        sampled_counts[rec['cell_id']] += 1
        by_id[sid] = rec
    if any(sampled_counts[c['cell_id']] != c['n_cell'] for c in cells):
        raise ValueError('Stored sample records do not match n_cell')
    return samples, by_id


def _protected(path, samples, inputs=()):
    result = protected_output(path, inputs)
    provenance = samples.get('source_provenance', {})
    for key in ('run_directory', 'corpus_directory'):
        directory = provenance.get(key)
        if directory:
            folder = Path(directory).resolve()
            if result == folder or folder in result.parents:
                raise ValueError('Label outputs must be outside source run/corpus directories')
    if provenance.get('db_path') and result == Path(provenance['db_path']).resolve():
        raise ValueError('Label output would overwrite the formal database')
    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ('path', 'actual_path', 'ledger_path', 'corpus_path') and isinstance(child, str) and child:
                    if result == Path(child).resolve():
                        raise ValueError('Label output would overwrite an evidence source')
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(samples.get('records', []))
    return result


def _csv_identity(rec):
    row = {key: _text(rec.get(key, '')) for key in IDENTITY_FIELDS}
    row.update({key: _text(rec['edge'].get(key, '')) for key in ('source_decision', 'resolved_cited_case')})
    row.update(source_locator=_text(rec.get('source_locator', '')), source_sha256=_text(rec.get('source_sha256', '')))
    return row


def _atomic_csv(path, payload):
    if len(payload) > MAX_CSV_BYTES:
        raise ValueError('Label CSV exceeds its 2 MiB byte budget')
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def template(samples_path, out_csv):
    samples, by_id = _load_samples(samples_path)
    output = _protected(out_csv, samples, (samples_path,))
    content = io.StringIO(newline='')
    writer = csv.DictWriter(content, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for rec in samples['records']:
        writer.writerow(dict(_csv_identity(rec), **{key: '' for key in LABEL_FIELDS}))
    _atomic_csv(output, content.getvalue().encode('utf-8'))
    return {'schema': 'quality_label_template_v1', 'run_id': samples['run_id'], 'frame_id': samples['frame_id'],
            'samples_hash': canonical_hash(samples), 'rows': len(by_id), 'path': str(output),
            'label_methods_allowed': list(LABEL_METHODS), 'label_columns': list(LABEL_FIELDS),
            'manual_columns': list(MANUAL_FIELDS)}


def _validate_label(row, rec):
    label = {}
    for key in LABEL_FIELDS:
        value = row.get(key) or ''
        if not isinstance(value, str):
            raise ValueError('Review labels must be text: ' + key)
        label[key] = value.strip()
    for key, value in label.items():
        if len(value) > MAX_CELL_TEXT or '\x00' in value:
            raise ValueError('Label cell is invalid or too large: ' + key)
    for key, values in ENUMS.items():
        if label[key] and label[key] not in values:
            raise ValueError('Invalid %s label: %s' % (key, label[key]))
    if label['origin_country'] and not label['origin']:
        raise ValueError('origin_country requires an origin assessment')
    if not any(label[key] for key in ENUMS):
        return None
    if not label['annotator']:
        raise ValueError('Labels require a named annotator (human name or model identity)')
    if label['label_method'] not in LABEL_METHODS:
        raise ValueError('Labels require label_method=manual or model')
    if label['label_method'] == 'model' and not label['notes']:
        raise ValueError('Model labels require notes with a rationale and evidence references')
    try:
        datetime.datetime.fromisoformat(label['annotated_at'].replace('Z', '+00:00'))
    except (TypeError, ValueError):
        raise ValueError('Labels require ISO annotated_at') from None
    return dict(sample_id=rec['sample_id'], record_hash=rec['record_hash'], **label)


def _method_counts(labels):
    counts = Counter(row['label_method'] for row in labels)
    return {method: counts[method] for method in LABEL_METHODS}


def _method_name(counts):
    present = [method for method, count in counts.items() if count]
    return present[0] if len(present) == 1 else 'mixed' if present else 'manual'


def import_labels(samples_path, labels_csv, out_json):
    samples, by_id = _load_samples(samples_path)
    labels_csv = Path(labels_csv)
    if labels_csv.stat().st_size > MAX_CSV_BYTES:
        raise ValueError('Label CSV input exceeds the byte budget')
    output = _protected(out_json, samples, (samples_path, labels_csv))
    seen, labels, rows_seen = set(), [], 0
    with labels_csv.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)) or set(('sample_id', 'record_hash') + LABEL_FIELDS) - set(fields):
            raise ValueError('Label CSV has missing or duplicate columns')
        for row in reader:
            rows_seen += 1
            if rows_seen > MAX_ROWS or None in row or any(value is None for value in row.values()):
                raise ValueError('Malformed or over-budget label CSV record')
            sid = row['sample_id']
            if sid in seen or sid not in by_id:
                raise ValueError('Duplicate or unexpected sample_id: ' + sid)
            seen.add(sid)
            rec = by_id[sid]
            identity = _csv_identity(rec)
            for key in identity:
                if key in row and row[key] != identity[key]:
                    raise ValueError('Label/sample identity mismatch: %s/%s' % (sid, key))
            label = _validate_label(row, rec)
            if label:
                label['label_hash'] = canonical_hash(label)
                labels.append(label)
    method_counts = _method_counts(labels)
    payload = {'schema': 'quality_labels_v1', 'run_id': samples['run_id'], 'frame_id': samples['frame_id'],
               'samples_hash': canonical_hash(samples), 'source_labels_sha256': hashlib.sha256(labels_csv.read_bytes()).hexdigest(),
               'imported_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'label_method': _method_name(method_counts), 'label_counts_by_method': method_counts,
               'sampled_records': len(by_id), 'csv_rows': rows_seen, 'labelled_records': len(labels), 'records': labels}
    payload['content_hash'] = canonical_hash(payload)
    write_bounded_json(output, payload, inputs=(samples_path, labels_csv))
    return payload


def _load_labels(value, samples, by_id):
    labels = read_bounded_json(value) if isinstance(value, (str, Path)) else value
    if not isinstance(labels, dict) or len(json.dumps(labels, ensure_ascii=False).encode('utf-8')) > MAX_JSON_BYTES:
        raise ValueError('Malformed or over-budget imported labels')
    if labels.get('schema') != 'quality_labels_v1' or labels.get('run_id') != samples['run_id'] or labels.get('frame_id') != samples['frame_id']:
        raise ValueError('Labels refer to another schema/run/frame')
    if labels.get('samples_hash') != canonical_hash(samples):
        raise ValueError('Labels no longer match the sampling frame')
    if canonical_hash({k: v for k, v in labels.items() if k != 'content_hash'}) != labels.get('content_hash'):
        raise ValueError('Imported label document hash mismatch')
    if labels.get('label_method') not in (*LABEL_METHODS, 'mixed') or not isinstance(labels.get('records'), list):
        raise ValueError('Only imported manual/model labels may be evaluated')
    by_label = {}
    for row in labels['records']:
        if not isinstance(row, dict):
            raise ValueError('Malformed imported label record')
        sid = row.get('sample_id')
        if sid in by_label or sid not in by_id or row.get('record_hash') != by_id[sid]['record_hash']:
            raise ValueError('Duplicate, unexpected or changed sample label: ' + str(sid))
        if canonical_hash({k: v for k, v in row.items() if k != 'label_hash'}) != row.get('label_hash'):
            raise ValueError('Imported label record hash mismatch: ' + sid)
        if _validate_label(row, by_id[sid]) is None:
            raise ValueError('Imported label record is wholly unlabelled: ' + sid)
        by_label[sid] = row
    method_counts = _method_counts(by_label.values())
    if labels['label_method'] != _method_name(method_counts):
        raise ValueError('Imported label method disagrees with its records')
    if 'label_counts_by_method' in labels and labels['label_counts_by_method'] != method_counts:
        raise ValueError('Imported label method counts disagree with its records')
    return labels, by_label


def _ratio(num, den):
    return num/den if den else None


def _joint_edge_validity(records, labels, method):
    counts, weights = Counter(), Counter()
    for rec in records:
        row = labels.get(rec['sample_id'], {})
        mention, identity = row.get('case_mention'), row.get('judgment_identity')
        if mention == 'no' or identity == 'incorrect':
            category = 'incorrect'
        elif mention == 'yes' and identity == 'correct':
            category = 'correct'
        elif 'unverifiable' in (mention, identity):
            category = 'unverifiable'
        elif 'unknown' in (mention, identity):
            category = 'unknown'
        else:
            category = 'unlabelled'
        counts[category] += 1
        weights[category] += 1/rec['pi']
    total_n, total_weight = len(records), sum(weights.values())
    verified_n = counts['correct'] + counts['incorrect']
    verified_weight = weights['correct'] + weights['incorrect']
    unresolved_n, unresolved_weight = total_n - verified_n, total_weight - verified_weight
    allowed = method != 'mixed'
    return {
        'rule': 'correct if case_mention=yes AND judgment_identity=correct; incorrect if case_mention=no OR judgment_identity=incorrect; otherwise unresolved',
        'sampled_n': total_n, 'correct_n': counts['correct'], 'incorrect_n': counts['incorrect'],
        'unknown_n': counts['unknown'], 'unverifiable_n': counts['unverifiable'],
        'unlabelled_n': counts['unlabelled'], 'verified_n': verified_n, 'unresolved_n': unresolved_n,
        'categories': {category: {'n': counts[category], 'inverse_pi_weight': weights[category]}
                       for category in ('correct', 'incorrect', 'unknown', 'unverifiable', 'unlabelled')},
        'sample_verified_coverage': _ratio(verified_n, total_n),
        'inverse_pi_verified_coverage': _ratio(verified_weight, total_weight),
        'raw_verified_rate': _ratio(counts['correct'], verified_n) if allowed else None,
        'weighted_verified_rate': _ratio(weights['correct'], verified_weight) if allowed else None,
        'sample_correct_fraction_bounds': {
            'lower': _ratio(counts['correct'], total_n) if allowed else None,
            'upper': _ratio(counts['correct'] + unresolved_n, total_n) if allowed else None},
        'inverse_pi_correct_fraction_bounds': {
            'lower': _ratio(weights['correct'], total_weight) if allowed else None,
            'upper': _ratio(weights['correct'] + unresolved_weight, total_weight) if allowed else None},
        'bounds_scope': 'Unresolved sampled records assigned incorrect/correct; not population bounds or confidence intervals',
        'rate_scope': 'labelled_verifiable_subset_only' if allowed else 'mixed_review_methods_no_pooled_rate'}


def _fold(records, labels):
    total_weight = sum(1/rec['pi'] for rec in records)
    method_counts = _method_counts(labels[rec['sample_id']] for rec in records if rec['sample_id'] in labels)
    method = _method_name(method_counts) if any(method_counts.values()) else 'unlabelled'
    dimensions = {}
    for key, categories in ENUMS.items():
        counts, weights = Counter(), Counter()
        for rec in records:
            value = labels.get(rec['sample_id'], {}).get(key, '')
            if value:
                counts[value] += 1
                weights[value] += 1/rec['pi']
        labelled_n, labelled_weight = sum(counts.values()), sum(weights.values())
        unresolved = {'unverifiable', 'unknown'}
        verified_n = sum(n for category, n in counts.items() if category not in unresolved)
        verified_weight = sum(n for category, n in weights.items() if category not in unresolved)
        detail = {'sampled_n': len(records), 'labelled_n': labelled_n, 'unlabelled_n': len(records)-labelled_n,
                  'unverifiable_n': counts['unverifiable'], 'unknown_n': counts['unknown'], 'verified_n': verified_n,
                  'sample_label_completion': _ratio(labelled_n, len(records)),
                  'sample_verified_coverage': _ratio(verified_n, len(records)),
                  'inverse_pi_label_completion': _ratio(labelled_weight, total_weight),
                  'inverse_pi_verified_coverage': _ratio(verified_weight, total_weight),
                  'categories': {category: {'n': counts[category], 'inverse_pi_weight': weights[category]}
                                 for category in categories}, 'rate_scope': 'labelled_verifiable_subset_only'}
        if key == 'treatment_role':
            detail['interpretation'] = 'descriptive_categories_not_precision'
            detail['labelled_category_shares'] = {category: _ratio(counts[category], labelled_n) for category in categories}
            detail['inverse_pi_labelled_category_shares'] = {category: _ratio(weights[category], labelled_weight) for category in categories}
        else:
            good = 'yes' if key == 'case_mention' else 'correct'
            detail['raw_verified_rate'] = _ratio(counts[good], verified_n) if method != 'mixed' else None
            detail['weighted_verified_rate'] = _ratio(weights[good], verified_weight) if method != 'mixed' else None
            if method == 'mixed':
                detail['rate_scope'] = 'mixed_review_methods_no_pooled_rate'
        dimensions[key] = detail
    reviewed = sum(rec['sample_id'] in labels for rec in records)
    return {'sampled_n': len(records), 'reviewed_rows': reviewed, 'row_label_completion': _ratio(reviewed, len(records)),
            'inverse_pi_sample_weight': total_weight, 'label_method': method,
            'label_counts_by_method': method_counts, 'dimensions': dimensions,
            'joint_edge_validity': _joint_edge_validity(records, labels, method)}


def evaluate(samples_path, labels_json):
    samples, by_id = _load_samples(samples_path)
    label_document, by_label = _load_labels(labels_json, samples, by_id)
    folds = {fold: _fold([rec for rec in samples['records'] if rec['fold'] == fold], by_label)
             for fold in ('train', 'holdout')}
    overall = _fold(samples['records'], by_label)
    by_method = {}
    for method in LABEL_METHODS:
        method_labels = {sid: row for sid, row in by_label.items() if row['label_method'] == method}
        by_method[method] = {
            'label_method': method, 'labelled_n': len(method_labels),
            'sample_coverage': _fold(samples['records'], method_labels),
            'folds': {fold: _fold([rec for rec in samples['records'] if rec['fold'] == fold], method_labels)
                      for fold in ('train', 'holdout')}}
    complete = all(d['verified_n'] == d['sampled_n'] for d in overall['dimensions'].values()) and bool(by_id)
    warnings = ['Rates describe the labelled, verifiable subset and are not population calibration.',
                'Train and holdout are reported separately; treatment roles are descriptive categories.']
    if by_method['model']['labelled_n']:
        warnings.append('Model-reviewed precision is based on model assessments, not independent human validation or ground truth.')
    if overall['label_method'] == 'mixed':
        warnings.append('Mixed human/model correctness rates are suppressed; use by_label_method for separate rates and full-frame coverage.')
    if not complete:
        warnings.append('Incomplete or unresolved labels prevent population accuracy claims; retain the full sampled-frame coverage denominator.')
    if not folds['holdout']['sampled_n']:
        warnings.append('No holdout records were selected; held-out evaluation is unavailable.')
    return {'schema': 'quality_evaluation_v1', 'run_id': samples['run_id'], 'frame_id': samples['frame_id'],
            'samples_hash': canonical_hash(samples), 'labels_hash': label_document['content_hash'],
            'frame_N': samples['frame_N'], 'sampled_n': len(by_id), 'labelled_n': len(by_label),
            'label_method': overall['label_method'], 'label_counts_by_method': overall['label_counts_by_method'],
            'manual_reviewed_n': by_method['manual']['labelled_n'], 'model_reviewed_n': by_method['model']['labelled_n'],
            'by_label_method': by_method,
            'cells': samples['cells'], 'weighting': 'inverse_inclusion_probability_1_over_pi',
            'folds': folds, 'sample_coverage': overall, 'all_dimensions_verified': complete,
            'population_calibration_status': 'not_calibrated', 'population_inference_allowed': False,
            'dd_or_weight_updates': False, 'warnings': warnings}
