"""Compatibility imports for positive court evidence and identity partitioning."""
from pathlib import Path
from identity_evidence import CourtEvidence, _court_nk as nk, DECISIONS as _DECISIONS

DECISIONS = Path(_DECISIONS)


def partition(members, did_idx, evidence, row_key, stats, bar=0.8):
    from identity_solve import partition as solve_partition
    return solve_partition(members, did_idx, evidence, row_key, stats, bar)
