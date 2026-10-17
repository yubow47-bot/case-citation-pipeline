# -*- coding: utf-8 -*-
"""Identifier identity regressions; no corpus or existing run is changed.

Exact merge keys denote one identifier even across courts. Different keys in one
identifier system denote different documents. Cross-system co-citation still uses
the existing BAR threshold and remains heuristic (never an origin proof).

Run: python pipeline/tests/test_identifier_identity.py
"""
import os
import sys
import unittest
from collections import Counter
from itertools import permutations

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import decide  # noqa: E402


def row(key, court="SCC", kind="identifier", name="X v. Y"):
    return {"court": court, "row_key": court + "|" + key, "merge_key": key,
            "case_name_modal": name, "year": 2011, "citation_kind": kind,
            "jurisdiction": "CA", "canonical_string": key,
            "key_occurrence_count": 1, "self_citation_of": "",
            "self_case_name": "", "is_primary": "false", "split_reason": "",
            "merge_key_dup": ""}


CAN_A = "2011||canlii||111"
CAN_B = "2011||canlii||222"
CAR = "2011||carswellont||11"
ANCHOR_A = "2011||scc||10"
ANCHOR_B = "2011||scc||99"


def groups(parts):
    return {frozenset(m["row_key"] for m in members) for members, _ in parts}


class IdentifierIdentityTests(unittest.TestCase):
    def assert_valid_identifiers(self, parts):
        for members, _ in parts:
            systems = {}
            for m in members:
                system = decide.identifier_system_of(m["merge_key"])
                if system:
                    systems.setdefault(system, set()).add(m["merge_key"])
            self.assertTrue(all(len(keys) == 1 for keys in systems.values()), systems)

    def test_same_key_cross_court_without_anchor(self):
        members = [row(CAN_A), row(CAN_A, court="ONCA")]
        did = {members[0]["row_key"]: {"S1"}, members[1]["row_key"]: {"O1"}}
        parts = decide.split_by_decision(members, did, Counter())
        self.assertEqual(groups(parts), {frozenset(did)})
        basis = decide.assign_identity_basis(parts[0][0], did, None, parts[0][1])
        self.assertEqual(set(basis.values()), {"same_citation"})

    def test_same_key_cross_court_with_single_anchor(self):
        members = [row(CAN_A), row(CAN_A, court="ONCA"),
                   row(ANCHOR_A, kind="neutral")]
        did = {m["row_key"]: {"D1"} for m in members}
        parts = decide.split_by_decision(members, did, Counter())
        self.assertEqual(groups(parts), {frozenset(did)})
        self.assert_valid_identifiers(parts)

    def test_cross_system_single_component_is_returned(self):
        members = [row(CAN_A), row(CAR)]
        did = {m["row_key"]: {"D1", "D2"} for m in members}
        parts = decide.split_by_decision(members, did, Counter())
        self.assertEqual(groups(parts), {frozenset(did)})
        basis = decide.assign_identity_basis(parts[0][0], did, None, parts[0][1])
        self.assertEqual(set(basis.values()), {"cocitation"})

    def test_cross_system_no_cocitation_stays_separate(self):
        members = [row(CAN_A), row(CAR)]
        did = {members[0]["row_key"]: {"D1"}, members[1]["row_key"]: {"D2"}}
        parts = decide.split_by_decision(members, did, Counter())
        self.assertEqual(len(parts), 2)

    def test_cannot_link_survives_cross_system_bridge(self):
        members = [row(CAN_A), row(CAN_B), row(CAR),
                   row("2011|1|scr||3", kind="reporter")]
        did = {m["row_key"]: {"D1"} for m in members[:-1]}
        did[members[-1]["row_key"]] = {"D2"}
        expected = None
        for perm in permutations(members):
            parts = decide.split_by_decision(list(perm), did, Counter())
            self.assert_valid_identifiers(parts)
            actual = groups(parts)
            if expected is None:
                expected = actual
            self.assertEqual(actual, expected)

    def test_multianchor_pending_cannot_link_survives_bridge(self):
        members = [row(ANCHOR_A, kind="neutral"), row(ANCHOR_B, kind="neutral"),
                   row(CAN_A), row(CAN_B), row(CAR)]
        did = {members[0]["row_key"]: {"A"}, members[1]["row_key"]: {"B"}}
        did.update({m["row_key"]: {"D1"} for m in members[2:]})
        expected = None
        for perm in permutations(members):
            parts = decide.split_by_decision(list(perm), did, Counter())
            self.assert_valid_identifiers(parts)
            actual = groups(parts)
            if expected is None:
                expected = actual
            self.assertEqual(actual, expected)

    def test_multianchor_assignment_contributions_require_acceptance(self):
        for later_key, accepted in ((CAN_B, False), (CAR, True)):
            with self.subTest(later_key=later_key):
                members = [row(ANCHOR_A, kind="neutral"),
                           row(ANCHOR_B, kind="neutral"), row(CAN_A), row(later_key)]
                members[-1]["jurisdiction"] = ""
                did = {members[0]["row_key"]: {"A"},
                       members[1]["row_key"]: {"B"},
                       members[2]["row_key"]: {"A"},
                       members[3]["row_key"]: {"A", "new"}}
                stats = Counter()
                parts = decide.split_by_decision(members, did, stats)
                assigned = {members[0]["row_key"], members[2]["row_key"]}
                expected = {frozenset({members[1]["row_key"]})}
                if accepted:
                    assigned.add(members[3]["row_key"])
                else:
                    expected.add(frozenset({members[3]["row_key"]}))
                expected.add(frozenset(assigned))
                self.assertEqual(groups(parts), expected)
                self.assertEqual(stats["units_assigned_by_cocitation"], 1 + accepted)
                self.assertEqual(stats["units_identifier_same_system_blocked"], 1 - accepted)
                for name in ("dd_added_by_assignment",
                             "units_assigned_larger_than_target",
                             "units_assigned_larger_than_target_unknown_jur"):
                    self.assertEqual(stats[name], int(accepted), name)

    def test_adjudication_unions_sources_and_occurrences(self):
        members = [row(CAN_A), row(CAN_A, court="ONCA")]
        did = {members[0]["row_key"]: {"S1", "S2"},
               members[1]["row_key"]: {"O1"}}
        members[0]["key_occurrence_count"] = 2
        out, ids, effective = decide.adjudicate(
            members, did, {}, {}, "XC", Counter(), False)
        self.assertEqual(len({r["merged_group_id"] for r in out}), 1)
        self.assertEqual({r["distinct_decisions_count"] for r in out}, {3})
        self.assertEqual({r["occurrence_count"] for r in out}, {3})
        self.assertEqual({r["identity_status"] for r in effective}, {"same_citation"})
        self.assertEqual({r["source_decision"] for r in effective}, {"S1", "S2", "O1"})
        self.assertEqual(len(ids), 3)

    def test_exact_identifier_precedes_different_or_missing_names(self):
        for names in (("X v. Y", "X versus Y", ""), ("X v. Y", "", ""),
                      ("", "", "")):
            members = [row(CAN_A, court=court, name=name)
                       for court, name in zip(("SCC", "ONCA", "BCCA"), names)]
            did = {m["row_key"]: {m["court"] + "_D1"} for m in members}
            for perm in permutations(members):
                out, _, effective = decide.adjudicate(
                    list(perm), did, {}, {}, "XC", Counter(), False)
                self.assertEqual(len({r["merged_group_id"] for r in out}), 1)
                self.assertEqual({r["distinct_decisions_count"] for r in out}, {3})
                self.assertEqual({r["identity_basis"] for r in out}, {"same_citation"})
                self.assertEqual({r["status"] for r in effective}, {"counted"})
                self.assertEqual({r["source_decision"] for r in effective},
                                 {"SCC_D1", "ONCA_D1", "BCCA_D1"})

    def test_different_identifiers_with_same_name_stay_separate(self):
        members = [row(CAN_A), row(CAN_B, court="ONCA")]
        did = {m["row_key"]: {"D1"} for m in members}
        out, _, _ = decide.adjudicate(members, did, {}, {}, "XC", Counter(), False)
        self.assertEqual(len({r["merged_group_id"] for r in out}), 2)

    def test_same_full_reporter_key_joins_across_courts(self):
        """PROBLEMS #135: one printed report is one citation in every court."""
        members = [row("2011|1|scr||3", kind="reporter", name="X v. Y"),
                   row("2011|1|scr||3", court="ONCA", kind="reporter", name="")]
        out, _, _ = decide.adjudicate(members, {}, {}, {}, "XC", Counter(), False)
        self.assertEqual(len({r["merged_group_id"] for r in out}), 1)

    def test_same_reporter_key_titles_differ_still_joins(self):
        members = [row("1964||ac||465", kind="reporter", name="Hedley Byrne & Co. v. Heller & Partners Ltd"),
                   row("1964||ac||465", court="ONCA", kind="reporter", name="Hedley Byrne & Co Ltd v Heller & Partners Ltd")]
        did = {m["row_key"]: {m["court"] + "_D"} for m in members}
        out, _, _ = decide.adjudicate(members, did, {}, {}, "XC", Counter(), False)
        self.assertEqual(len({r["merged_group_id"] for r in out}), 1)
        self.assertEqual({r["distinct_decisions_count"] for r in out}, {2})

    def test_french_supreme_court_reports_title_joins_english(self):
        """PROBLEMS #139: [1990] 1 R.C.S. 123 is the report [1990] 1 S.C.R. 123."""
        members = [row("1990|1|scr||123", kind="reporter", name="X v. Y"),
                   row("1990|1|rcs||123", court="ONCA", kind="reporter", name="")]
        out, _, _ = decide.adjudicate(members, {}, {}, {}, "XC", Counter(), False)
        self.assertEqual(len({r["merged_group_id"] for r in out}), 1)

    def test_same_reporter_key_never_bridges_two_neutral_numbers(self):
        members = [row("2011||scc||10", kind="neutral", name="X v. Y"),
                   row("2011|1|scr||3", kind="reporter", name="X v. Y"),
                   row("2011||scc||99", court="ONCA", kind="neutral", name="P v. Q"),
                   row("2011|1|scr||3", court="ONCA", kind="reporter", name="P v. Q")]
        did = {m["row_key"]: {m["court"] + "_D" + m["merge_key"]} for m in members}
        out, _, _ = decide.adjudicate(members, did, {}, {}, "XC", Counter(), False)
        groups_of = {}
        for r in out:
            groups_of.setdefault(r["merged_group_id"], set()).add(r["merge_key"])
        self.assertFalse(any({"2011||scc||10", "2011||scc||99"} <= keys for keys in groups_of.values()))

    def test_local_conflict_keeps_evidence_with_determined_member(self):
        determined = {"identity_basis": "anchor", "member_origin_country": "GB",
                      "member_origin_status": "DETERMINED",
                      "member_origin_basis": "court_scope_rule",
                      "member_origin_evidence_ids": "scope:UKHL"}
        conflict = {"identity_basis": "same_citation", "member_origin_country": "",
                    "member_origin_status": "CONFLICT", "member_origin_basis": "case_record",
                    "member_origin_evidence_ids": "case_origin:CA-record|case_origin:GB-record"}
        for perm in permutations((determined, conflict)):
            members = [dict(m) for m in perm]
            decide.aggregate_group_origin(members, Counter())
            for m in members:
                self.assertEqual(m["group_origin_status"], "CONFLICT")
                self.assertEqual(m["group_foreign_status"], "CONFLICT")
                self.assertEqual(set(m["group_origin_evidence_ids"].split("|")),
                                 {"scope:UKHL", "case_origin:CA-record", "case_origin:GB-record"})
                self.assertEqual(set(m["group_origin_basis"].split("+")),
                                 {"court_scope_rule", "case_record"})


if __name__ == "__main__":
    unittest.main()
