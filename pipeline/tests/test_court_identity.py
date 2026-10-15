"""Decision-level identity constraints from positive court evidence."""
import sys
from pathlib import Path
from collections import Counter
from itertools import permutations
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decide
from identity_courts import CourtEvidence


def member(key, kind="neutral", observed="", citing="ONCA"):
    return dict(merge_key=key, citation_kind=kind, court=citing, jurisdiction="CA",
                canonical_string=key, case_name_modal="Hamilton v. Hamilton", year_printed="2005",
                observed_deciding_court=observed, court_designation_conflict="false",
                self_citation_of="", self_case_name="", occurrence_count=1, key_occurrence_count=1)


class CourtIdentityTests(unittest.TestCase):
    def cluster(self, rows, ids):
        return decide.cluster_same_case(rows, ids, Counter())

    def test_single_anchor_cannot_absorb_printed_different_court(self):
        rows = [member("2005||scc||23"), member("|10|dlr|4th|12", "reporter", "British Columbia Court of Appeal")]
        ids = {decide.row_key(r): {"S"} for r in rows}
        self.assertEqual(len(self.cluster(rows, ids)), 2)

    def test_same_court_official_reporter_remains_parallel(self):
        rows = [member("2005||scc||23"), member("2005|1|scr||12", "reporter")]
        ids = {decide.row_key(r): {"S"} for r in rows}
        self.assertEqual(len(self.cluster(rows, ids)), 1)

    def test_official_reporter_cannot_attach_to_onca(self):
        rows = [member("2005||onca||23"), member("2005|1|scr||12", "reporter")]
        ids = {decide.row_key(r): {"S"} for r in rows}
        self.assertEqual(len(self.cluster(rows, ids)), 2)

    def test_bilingual_court_aliases_are_not_incompatible(self):
        evidence = CourtEvidence()
        a = evidence.evidence(member("2005||scc||23"))
        b = evidence.evidence(member("2005||csc||23"))
        self.assertEqual(set(a), set(b))

    def test_citing_court_does_not_supply_identity_evidence(self):
        evidence = CourtEvidence()
        self.assertEqual(evidence.evidence(member("|10|dlr|4th|12", "reporter", citing="SCC")), {})

    def test_unknown_reporter_not_split_without_positive_conflict(self):
        rows = [member("2005||scc||23"), member("|10|dlr|4th|12", "reporter")]
        ids = {decide.row_key(r): {"S"} for r in rows}
        self.assertEqual(len(self.cluster(rows, ids)), 1)

    def test_unknown_reporter_tied_between_courts_stays_unassigned(self):
        rows = [member("2005||scc||23"), member("2005||onca||23"), member("|10|dlr|4th|12", "reporter")]
        ids = {decide.row_key(r): {"S"} for r in rows}
        parts = self.cluster(rows, ids)
        self.assertEqual(len(parts), 3)
        self.assertTrue(any("court_unassigned" in reason for _, reason, _ in parts))

    def test_exact_key_conflicting_court_observation_not_torn_apart(self):
        rows = [member("2005||canlii||123", "identifier", "British Columbia Court of Appeal", "SCC"),
                member("2005||canlii||123", "identifier", "Supreme Court of Canada", "ONCA")]
        ids = {decide.row_key(r): {r["court"] + "_S"} for r in rows}
        self.assertEqual(len(self.cluster(rows, ids)), 1)

    def test_partition_order_is_deterministic(self):
        rows = [member("2005||scc||23"), member("2005||onca||23"), member("|10|dlr|4th|12", "reporter")]
        ids = {decide.row_key(r): {"S"} for r in rows}
        expected = None
        for perm in permutations(rows):
            actual = {frozenset(decide.row_key(r) for r in part) for part, _, _ in self.cluster(list(perm), ids)}
            expected = actual if expected is None else expected
            self.assertEqual(actual, expected)

    def test_registered_decision_outranks_wrong_modal_name(self):
        a, b = member("2002||scc||33"), member("2002||scc||3")
        b.update(self_citation_of="SCC_2002scc3", self_case_name="Chieu v. Canada")
        ids = {decide.row_key(a): {"A", "B", "C", "D"}, decide.row_key(b): {"E"}}
        root = decide.decisions_of([a, b], ids, registry={b["merge_key"]: ("SCC_2002scc3", "SCC")}, gate="registered")[0]
        self.assertEqual(len(set(root.values())), 2)

    def test_registered_bilingual_equivalence_still_allowed(self):
        a, b = member("2005||scc||23"), member("2005||csc||23")
        ids = {decide.row_key(a): {"A", "B"}, decide.row_key(b): {"A"}}
        registry = {b["merge_key"]: ("SCC_2005scc23", "SCC")}
        self.assertEqual(len(set(decide.decisions_of([a, b], ids, registry=registry, gate="registered")[0].values())), 1)

    def test_same_neutral_id_survives_different_modal_names(self):
        a = member("2005||scc||23", citing="SCC")
        b = member("2005||scc||23", citing="ONCA")
        b["case_name_modal"] = "Hamilton versus Hamilton"
        ids = {decide.row_key(a): {"A"}, decide.row_key(b): {"B"}}
        self.assertEqual(len(self.cluster([a, b], ids)), 1)

    def test_bilingual_id_survives_english_french_names(self):
        a = member("2005||scc||23")
        b = member("2005||csc||23")
        b["case_name_modal"] = "Hamilton c. Hamilton"
        ids = {decide.row_key(a): {"A"}, decide.row_key(b): {"B"}}
        self.assertEqual(len(self.cluster([a, b], ids)), 1)

    def test_no_cocitation_reporter_not_absorbed_by_single_anchor(self):
        rows = [member("2005||scc||23"), member("2005|1|scr||12", "reporter")]
        ids = {decide.row_key(rows[0]): {"A"}, decide.row_key(rows[1]): {"B", "C"}}
        self.assertEqual(len(self.cluster(rows, ids)), 2)

    def test_atomic_identity_retains_conflicting_printed_court(self):
        a = member("2005||scc||23")
        b = member("2005||scc||23", observed="British Columbia Court of Appeal", citing="SCC")
        ids = {decide.row_key(a): {"A"}, decide.row_key(b): {"B"}}
        parts = self.cluster([a, b], ids)
        self.assertEqual(len(parts), 1)
        self.assertTrue(all(r["identity_court_conflict"] == "true" for r in parts[0][0]))


if __name__ == "__main__":
    unittest.main()
