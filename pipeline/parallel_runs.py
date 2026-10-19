"""Printed parallel-run structure and provenance loading; no identity decisions.

The producer sees only classified rows. Positive evidence deliberately uses a
narrower grammar than negative appeal-history evidence: a comma and at most two
row-classified service/court annotations. Pinpoints and prose do not join runs.
"""
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
from artifacts import open_csv, sha256_logical_csv_bytes
from suffix_annotations import parallel_gap

FIELDS = ('source_decision_citation', 'corpus_row_index', 'instance', 'member_index',
          'merge_key', 'candidate_id', 'match_start_offset', 'match_end_offset',
          'raw_string', 'gap_before')
BOUND_FIELDS = ('source_decision_citation', 'corpus_row_index', 'merge_key',
                'match_start_offset', 'match_end_offset', 'raw_string')

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))

def extract_runs(counted, gap_text, stats):
    """Emit complete adjacent counted runs, retaining original spans and keys."""
    out = []
    runs, current = [], []
    for row in counted:
        gap = gap_text(current[-1], row) if current else None
        if current and not parallel_gap(gap, current[-1]):
            runs.append(current); current = []
        current.append(row)
    if current:
        runs.append(current)
    for run in runs:
        if len({r['merge_key'] for r in run}) < 2:
            continue
        first, last = run[0], run[-1]
        iid = 'parallel:' + hashlib.sha256(canonical([
            first['source_decision_citation'], first.get('corpus_row_index', ''),
            first['candidate_id'], last['candidate_id']]).encode()).hexdigest()
        for i, row in enumerate(run):
            item = {k: str(row.get(k, '')) for k in FIELDS}
            item.update(instance=iid, member_index=str(i),
                        gap_before=gap_text(run[i-1], row) if i else '')
            out.append(item)
        stats['parallel_runs'] += 1
        stats['parallel_run_members'] += len(run)
    return out

class ParallelRuns(dict):
    """A load-validated snapshot; mutations are rejected before evidence use."""
    def seal(self, artifacts):
        self.artifacts = artifacts
        self.signature = hashlib.sha256(canonical({'instances':dict(self),'artifacts':self.artifacts}).encode()).hexdigest()
        return self

    def verify(self):
        if hashlib.sha256(canonical({'instances':dict(self),'artifacts':self.artifacts}).encode()).hexdigest() != self.signature:
            raise ValueError('Parallel run evidence changed after validation')
        for path, digest in self.artifacts.items():
            if sha256_logical_csv_bytes(path) != digest:
                raise ValueError('Parallel source artifact changed after validation')


def load_parallel_runs(paths):
    """Bind each run to counted adjacent candidates and classified gap text.

    None denotes an explicit caller-selected legacy path. A supplied file must
    exist, have its complete schema and agree with both upstream ledgers.
    """
    out, artifacts = ParallelRuns(), {}
    for supplied in paths or ():
        path = Path(supplied)
        logical = str(path).replace('\\', '/')
        artifacts[logical] = sha256_logical_csv_bytes(path)
        records, wanted = [], set()
        with open_csv(path) as f:
            reader = csv.DictReader(f, strict=True)
            if not set(FIELDS) <= set(reader.fieldnames or ()):
                raise ValueError('Parallel run schema is incomplete')
            for n, r in enumerate(reader, 2):
                if None in r or any(r.get(k) is None for k in FIELDS):
                    raise ValueError('Malformed parallel run row')
                if any(not r[k] for k in FIELDS if k != 'gap_before'):
                    raise ValueError('Blank parallel run field')
                if not all(r[k].isdigit() for k in ('corpus_row_index', 'member_index', 'match_start_offset', 'match_end_offset')):
                    raise ValueError('Invalid parallel run offsets')
                if int(r['match_end_offset']) <= int(r['match_start_offset']):
                    raise ValueError('Invalid parallel run span')
                r['_source_locator'] = {'artifact': logical, 'record': n,
                    'sha256': artifacts[logical], 'hash_scope': 'logical_csv_bytes'}
                records.append(r); wanted.add(r['candidate_id'])
        mentions_path = path.parent/'mentions_candidates.csv'
        classified_path = path.parents[2]/'classify_out'/path.parent.name/'classified.csv'
        matches, counters = {}, defaultdict(int)
        with open_csv(mentions_path) as f:
            for r in csv.DictReader(f):
                if r['arbitration_status'] != 'counted':
                    continue
                doc = (r['source_decision_citation'], r['corpus_row_index'])
                ordinal = counters[doc]; counters[doc] += 1
                if r['candidate_id'] in wanted:
                    if r['candidate_id'] in matches:
                        raise ValueError('Duplicate parallel candidate ID')
                    matches[r['candidate_id']] = ({k:r[k] for k in BOUND_FIELDS}, ordinal)
        context = {}
        with open_csv(classified_path) as f:
            for r in csv.DictReader(f):
                if r['candidate_id'] in wanted:
                    if r['candidate_id'] in context:
                        raise ValueError('Duplicate classified candidate ID')
                    context[r['candidate_id']] = {k:r.get(k, '') for k in
                        BOUND_FIELDS + ('preceding_text', 'parallel_suffix_annotations_json')}
        for dependency in (mentions_path, classified_path):
            artifacts[str(dependency).replace('\\', '/')] = sha256_logical_csv_bytes(dependency)
        local = defaultdict(list)
        for r in records:
            if r['candidate_id'] not in matches or r['candidate_id'] not in context:
                raise ValueError('Parallel member is not a counted classified candidate')
            m, ordinal = matches[r['candidate_id']]
            for field in ('source_decision_citation', 'corpus_row_index', 'merge_key',
                          'match_start_offset', 'match_end_offset', 'raw_string'):
                if m[field] != r[field]:
                    raise ValueError('Parallel member differs from counted ledger: '+field)
            for field in ('source_decision_citation', 'corpus_row_index', 'match_start_offset', 'match_end_offset', 'raw_string'):
                if context[r['candidate_id']][field] != r[field]:
                    raise ValueError('Parallel member differs from classified ledger: '+field)
            local[r['instance']].append((r, ordinal))
        for iid, items in local.items():
            items.sort(key=lambda x: int(x[0]['member_index']))
            rs = [r for r, _ in items]
            if len(rs)<2 or len({r['merge_key'] for r in rs})<2:
                raise ValueError('Parallel run lacks distinct members')
            if [int(r['member_index']) for r in rs] != list(range(len(rs))):
                raise ValueError('Parallel run member order is incomplete')
            if len({(r['source_decision_citation'],r['corpus_row_index']) for r in rs}) != 1 or rs[0]['gap_before']:
                raise ValueError('Parallel run mixes documents or has a leading gap')
            for i in range(1,len(rs)):
                prev,r = rs[i-1],rs[i]
                n = int(r['match_start_offset'])-int(prev['match_end_offset'])
                pre = context[r['candidate_id']].get('preceding_text') or ''
                gap = pre[-n:] if 0<n<=len(pre) else None
                if items[i][1] != items[i-1][1]+1 or gap != r['gap_before'] or not parallel_gap(gap, context[prev['candidate_id']]):
                    raise ValueError('Parallel gap is not a native adjacent parallel separator')
            expected_iid = 'parallel:' + hashlib.sha256(canonical([rs[0]['source_decision_citation'],
                rs[0]['corpus_row_index'], rs[0]['candidate_id'], rs[-1]['candidate_id']]).encode()).hexdigest()
            if iid != expected_iid:
                raise ValueError('Parallel instance ID is not bound to its source span')
            if iid in out:
                raise ValueError('Duplicate parallel run instance')
            out[iid] = {'keys': sorted({r['merge_key'] for r in rs}),
                        'source': rs[0]['source_decision_citation'], 'records': rs}
    return out.seal(artifacts)
