"""Structural suffix capture and row-local classification of printed labels."""
import json
import re

# No reporter, court or service vocabulary is used by the capture function.
_PREFIX = r'\s*,?\s*(?:at\s+(?:(?:pp?\.?|paras?\.?|paragraphs?)\s+)?\d+(?:\s*[-–]\s*\d+)?\s*)?'
_PAREN = r'\((?P<raw>(?:[^()]|\([^()]{1,30}\)){1,80})\)'
_NEXT = re.compile(_PREFIX + r'(?P<outer>' + _PAREN + r')')


def capture_suffix(text, end):
    tail = text[end:end+240]
    cursor = 0; result = []
    for _ in range(3):
        match = _NEXT.match(tail, cursor)
        if not match:
            break
        if re.fullmatch(r'\s*\d+\s*(?:st|nd|rd|th|d)\s*', match['raw']):
            # An ordinal belongs to a reporter series, not a suffix annotation.
            break
        result.append({'raw': match['raw'], 'start': end+match.start('outer'),
                       'end': end+match.end('outer'), 'raw_start': end+match.start('raw'),
                       'raw_end': end+match.end('raw')})
        cursor = match.end()
    return result


def classify_suffix(row, classify_court, service_labels, normalize):
    """Interpret only the structural annotations supplied on this candidate."""
    annotations = json.loads(row.get('suffix_annotations_json') or '[]')
    allowed = []; observations = []
    for item in annotations:
        raw = item['raw']; key = normalize(raw)
        if key in service_labels:
            allowed.append({**item, 'kind': 'service',
                            'evidence_id': 'citation_service_labels:'+key})
            continue
        status, court, evidence = classify_court(raw)
        observations.append((item, status, court, evidence))
        if status in ('recognized', 'ambiguous_designation'):
            allowed.append({**item, 'kind': 'court', 'evidence_id': evidence})
    row['parallel_suffix_annotations_json'] = json.dumps(allowed, ensure_ascii=False)
    if not annotations:
        return
    recognized = [o for o in observations if o[1] == 'recognized']
    courts = {o[2] for o in recognized}
    if len(courts) > 1:
        row.update(court_designation_status='conflict', observed_deciding_court='',
                   court_designation_evidence_id=';'.join(sorted({o[3] for o in recognized})))
        return
    if recognized:
        item, status, court, evidence = recognized[0]
    elif observations:
        # Keep a genuine unresolved designation instead of a database label.
        item, status, court, evidence = observations[0]
    else:
        item = annotations[0]
        status, court, evidence = 'not_a_court', '', 'citation_service_labels:'+normalize(item['raw'])
    row.update(court_designation_raw=item['raw'],
        court_designation_span='%s:%s' % (item['raw_start'], item['raw_end']),
        court_designation_status=status, observed_deciding_court=court,
        court_designation_evidence_id=evidence)


def parallel_gap(gap, previous):
    """A comma and at most two previously classified short annotations."""
    if gap is None:
        return False
    if re.fullmatch(r'\s*,\s*', gap):
        return True
    if ';' in gap:
        return False
    base = int(previous['match_end_offset'])
    suffixes = json.loads(previous.get('parallel_suffix_annotations_json') or '[]')
    relevant = [a for a in suffixes if base <= a['start'] < a['end'] <= base+len(gap)]
    if not 1 <= len(relevant) <= 2:
        return False
    cursor = 0; remainder = ''
    for item in sorted(relevant, key=lambda a: a['start']):
        left, right = item['start']-base, item['end']-base
        if left < cursor or gap[left:right] != '(' + item['raw'] + ')':
            return False
        if item['kind'] not in ('court', 'service') or not item['evidence_id']:
            return False
        remainder += gap[cursor:left]; cursor = right
    remainder += gap[cursor:]
    return bool(re.fullmatch(r'\s*,\s*', remainder))
