"""Supplement a completed local comparison with three SCC zone views.

This is a mechanical view of the existing final edges. It is not a history
accuracy estimate and does not invent old-run zone fields or a baseline delta.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics


def summarize_scc(db):
    count = db.execute("SELECT COUNT(*) FROM docs WHERE court='SCC' AND eligible=1").fetchone()[0]
    rows = db.execute("SELECT e.sid,e.gid,e.mentions,e.history,e.payload FROM edges e JOIN docs d ON d.sid=e.sid WHERE d.court='SCC' AND d.eligible=1")
    edges = [(sid, gid, mentions, history, json.loads(payload)) for sid, gid, mentions, history, payload in rows]
    if edges and any('zone_profile' not in r[4] or 'own_case_history' not in r[4] for r in edges):
        return {'status': 'UNAVAILABLE_IN_EDGE_SCHEMA', 'baseline_delta': None, 'views': {}}
    views = {}
    for name, keep in (
        ('all_links', lambda edge: True),
        ('without_own_case_history', lambda edge: not edge[3]),
        ('without_headnote_only', lambda edge: edge[4].get('zone_profile') != 'headnote_only'),
    ):
        chosen = [edge for edge in edges if keep(edge)]
        degrees = Counter(edge[0] for edge in chosen)
        profile = Counter(edge[4].get('zone_profile') or 'unknown' for edge in chosen)
        values = list(degrees.values()) + [0] * (count - len(degrees))
        views[name] = {
            'N': count, 'E': len(chosen), 'K': len({edge[1] for edge in chosen}),
            'O': sum(edge[2] for edge in chosen),
            'mean_links_per_assessable_source': len(chosen) / count if count else None,
            'median_links_including_zero': statistics.median(values) if values else None,
            'sources_with_links': len(degrees),
            'zone_profile_edge_counts': dict(profile),
            'own_case_history_edges': sum(bool(edge[3]) for edge in chosen),
        }
    return {
        'status': 'MECHANICAL_SCC_ZONE_VIEWS',
        'calendar': '2001-2025 excluding 2011',
        'denominator': 'Same measurable SCC sources including zero-edge sources in every view',
        'without_headnote_only_rule': 'Exclude only zone_profile=headnote_only; retain both, reasons_only and unknown',
        'accuracy_caution': 'W2 seed-position recall failed its gate; these counts are not semantic precision or recall',
        'baseline_delta': None,
        'views': views,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison-dir', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    comparison, out = Path(args.comparison_dir).resolve(), Path(args.out).resolve()
    if out.drive.upper() != 'D:':
        raise ValueError('This task writes supplemental comparison outputs only on D:')
    if out.exists():
        raise ValueError('Supplement output must be new')
    receipt_path = comparison / 'comparison_receipt.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8-sig'))
    metrics = json.loads((comparison / 'metrics.json').read_text(encoding='utf-8-sig'))
    db = sqlite3.connect((comparison / 'comparison.sqlite').as_uri() + '?mode=ro', uri=True)
    try:
        result = (summarize_scc(db) if receipt.get('history_view_available') else
                  {'status': 'UNAVAILABLE_IN_EDGE_SCHEMA', 'baseline_delta': None, 'views': {}})
    finally:
        db.close()
    for view in ('all_links', 'without_own_case_history'):
        if view in result['views']:
            prior = metrics['views'][view]['by_court']['SCC']
            assert all(result['views'][view][key] == prior[key] for key in ('N', 'E', 'K', 'O')), view
    result.update(
        comparison_receipt_sha256=hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        run_manifest_sha256=receipt['run_manifest_sha256'],
        run=receipt['run'],
        supplementary_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
