"""Verified reporter envelopes are negative court constraints, not assignments."""
import json
import os
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from identity_constraints import ConstraintLedger, document_union_constraint  # noqa: E402
from identity_courts import CourtEvidence  # noqa: E402
from identity_evidence import EvidenceSnapshot, row_key  # noqa: E402
from identity_solve import partition, split_by_history  # noqa: E402


def reporter(key, name="R. v. Envelope", year="2021"):
    return {"court": "ONCA", "merge_key": key, "case_name_modal": name,
            "year_printed": year, "citation_kind": "reporter", "jurisdiction": "CA",
            "canonical_string": key, "key_occurrence_count": 1, "occurrence_count": 1,
            "self_citation_of": "", "self_case_name": "",
            "observed_deciding_court": "", "court_designation_conflict": ""}


def neutral(key, court="BCCA", name="R. v. Envelope", year="2021"):
    return {"court": court, "merge_key": key, "case_name_modal": name,
            "year_printed": year, "citation_kind": "neutral", "jurisdiction": "CA",
            "canonical_string": key, "key_occurrence_count": 1, "occurrence_count": 1,
            "self_citation_of": "", "self_case_name": "",
            "observed_deciding_court": "", "court_designation_conflict": ""}


class ReporterScopeConstraintTests(unittest.TestCase):
    def setUp(self):
        self.courts = CourtEvidence()

    def run_partition(self, rows):
        did_idx = {row_key(row): {"S1", "S2"} for row in rows}
        trace = ConstraintLedger(EvidenceSnapshot(rows, did_idx, "XC"))
        parts = partition(rows, did_idx, self.courts.evidence, row_key,
                          Counter(), trace=trace)
        return parts, trace

    def test_oac_and_bcac_overlap_at_scc_and_are_not_split(self):
        rows = [reporter("2021|1|oac||55"),
                reporter("2021|2|bcac||77")]
        parts, trace = self.run_partition(rows)
        self.assertEqual(len(parts), 1)
        self.assertFalse(any(item["rule"] == "incompatible_reporter_identity_scope"
                             for item in trace.records["constraints"]))

        facts = [fact for fact in trace.records["evidence"]
                 if fact["fact_kind"] == "reporter_identity_court_envelope"]
        self.assertEqual(len(facts), 2)
        envelopes = [set(json.loads(fact["value_json"])["allowed_courts"])
                     for fact in facts]
        self.assertEqual(envelopes[0] & envelopes[1], {"court:csc"})

    def test_oac_envelope_blocks_an_explicit_bcca_decision_and_traces_policy_fact(self):
        rows = [reporter("2021|1|oac||55"),
                neutral("2021||bcca||241")]
        parts, trace = self.run_partition(rows)
        self.assertEqual(len(parts), 2)
        constraint = next(item for item in trace.records["constraints"]
                          if item["rule"] == "incompatible_reporter_identity_scope")
        detail = json.loads(constraint["source_detail_json"])
        self.assertIn(detail["basis"], {
            "right_positive_court_outside_left_envelope",
            "left_positive_court_outside_right_envelope"})
        self.assertIn("court:bcca", detail["left_positive_courts"] +
                      detail["right_positive_courts"])
        constrained_envelope = (detail["left_allowed_courts"]
                                if detail["basis"] == "right_positive_court_outside_left_envelope"
                                else detail["right_allowed_courts"])
        self.assertNotIn("court:bcca", constrained_envelope)
        refs = set(json.loads(constraint["evidence_ids_json"]))
        scope_facts = [fact for fact in trace.records["evidence"]
                       if fact["evidence_id"] in refs
                       and fact["fact_kind"] == "reporter_identity_court_envelope"]
        self.assertEqual(len(scope_facts), 1)
        value = json.loads(scope_facts[0]["value_json"])
        self.assertIn("policy_evidence_id", value)
        self.assertEqual(value["rule_id"], "RICS-OAC-1986")
        sources = json.loads(scope_facts[0]["sources_json"])
        self.assertEqual(sources["artifact"], "decisions/reporter_identity_court_sets.csv")
        self.assertEqual(sources["policy_evidence_id"], value["policy_evidence_id"])

    def test_history_split_stage_also_keeps_scope_conflicts_apart(self):
        rows = [reporter("2021|1|oac||55"),
                neutral("2021||bcca||241")]
        did_idx = {row_key(row): {"S1", "S2"} for row in rows}
        trace = ConstraintLedger(EvidenceSnapshot(rows, did_idx, "XC"))
        parts = split_by_history([(rows, "", "")], {}, did_idx, Counter(), trace)
        self.assertEqual(len(parts), 2)
        self.assertTrue(any(item["rule"] == "incompatible_reporter_identity_scope"
                            for item in trace.records["constraints"]))

    def test_document_alias_union_guard_rejects_scope_conflict(self):
        rows = [reporter("2021|1|oac||55"),
                neutral("2021||bcca||241")]
        did_idx = {row_key(row): {"S1", "S2"} for row in rows}
        trace = ConstraintLedger(EvidenceSnapshot(rows, did_idx, "XC"))
        blocker = document_union_constraint(
            rows, {}, {}, self.courts,
            {"trace": trace, "phase": "document_alias",
             "left": [rows[0]], "right": [rows[1]]})
        self.assertIsNotNone(blocker)
        self.assertEqual(blocker.rule, "incompatible_reporter_identity_scope")
        constraint = next(item for item in trace.records["constraints"]
                          if item["rule"] == blocker.rule)
        self.assertTrue(json.loads(constraint["evidence_ids_json"]))


class ReporterScopePolicyTests(unittest.TestCase):
    def setUp(self):
        from reporter_identity_scope import load_scope_rules
        self.rules = load_scope_rules()
        self.tokens = CourtEvidence().tokens

    def allowed(self, key, year=''):
        from reporter_identity_scope import allowed_courts
        return allowed_courts(reporter(key, year=year), self.rules, self.tokens)

    def test_oac_trial_and_appeal_envelope_rejects_bc_only(self):
        from reporter_identity_scope import scope_conflict
        a = self.allowed('1996|92|oac||200')
        self.assertTrue(scope_conflict(a, {'court:bcca'}))
        self.assertFalse(scope_conflict(a, {'court:onsc'}))
        self.assertFalse(scope_conflict(a, {'court:onca'}))

    def test_bcac_yukon_and_scc_counterexamples_are_allowed(self):
        a = self.allowed('2008|263|bcac||65')
        self.assertIn(self.tokens['ykca'], a)
        self.assertIn(self.tokens['scc'], a)
        self.assertNotIn(self.tokens['onca'], a)

    def test_two_reporters_share_scc_possibility(self):
        from reporter_identity_scope import scope_conflict
        self.assertFalse(scope_conflict(self.allowed('1994|69|oac||47'), self.allowed('2003|195|bcac||160')))

    def test_unknown_year_or_reporter_never_uses_origin_or_citing_court(self):
        from reporter_identity_scope import allowed_courts, scope_conflict
        for key, year in [('|57|bcac||299',''), ('1985|8|oac||320',''),
                          ('2027|1|oac||1',''), ('1990|1|bcac||1',''),
                          ('1997|1|bclr|3d|1',''), ('1997|1|unknown||1','')]:
            row = reporter(key, year=year)
            row.update(jurisdiction='BC', court='ONCA')
            a = allowed_courts(row, self.rules, self.tokens)
            self.assertFalse(a)
            self.assertFalse(scope_conflict(a, {'court:bcca'}))

    def test_continuous_volume_and_window_bounds(self):
        self.assertTrue(self.allowed('|92|oac||200', '1996'))
        self.assertTrue(self.allowed('1986|1|oac||1'))
        self.assertTrue(self.allowed('1991|1|bcac||1'))
        self.assertTrue(self.allowed('2026|1|bcac||1'))
        self.assertFalse(self.allowed('1996|92|oac||200', 'unknown'))

    def test_missing_alias_does_not_narrow_envelope(self):
        from reporter_identity_scope import allowed_courts
        tokens = dict(self.tokens)
        del tokens['ykca']
        self.assertFalse(allowed_courts(reporter('2008|263|bcac||65', year='2008'), self.rules, tokens))

    def test_nonreporter_and_row_mutation(self):
        from reporter_identity_scope import allowed_courts
        row = reporter('1996|92|oac||200', year='1996')
        original = dict(row)
        self.assertTrue(allowed_courts(row, self.rules, self.tokens))
        self.assertEqual(row, original)
        row['citation_kind'] = 'neutral'
        self.assertFalse(allowed_courts(row, self.rules, self.tokens))

    def test_embedded_provenance_and_scope_field_tampering(self):
        import csv
        from pathlib import Path
        import tempfile
        from reporter_identity_scope import DEFAULT_RULES, load_scope_rules, scope_evidence
        fact, = scope_evidence(reporter('1996|92|oac||200', year='1996'), self.rules, self.tokens)
        self.assertTrue(fact['evidence']['sources'])
        self.assertTrue(fact['evidence']['native_counterexamples'])
        with DEFAULT_RULES.open(encoding='utf-8', newline='') as stream:
            rows = list(csv.DictReader(stream))
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]/'implementation') as temp:
            path = Path(temp)/'tampered.csv'
            for tamper in ['evidence_json', 'allowed_court_codes']:
                changed = [dict(r) for r in rows]
                if tamper == 'evidence_json':
                    changed[0][tamper] = json.dumps({'sources': [], 'court_codes': ['ONCA']})
                else:
                    changed[0][tamper] = 'ONCA'
                with path.open('w', encoding='utf-8', newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(changed[0]))
                    writer.writeheader()
                    writer.writerows(changed)
                with self.assertRaisesRegex(ValueError, 'provenance'):
                    load_scope_rules(path)

    def test_regional_sets_allow_trial_and_federal_appeals(self):
        for key, year, included in [('|142|nbr|2d|327','1993','nbqb'),
                                    ('|109|saskr||8','1992','skpc'),
                                    ('|81|manr|2d|255','1992','fc')]:
            with self.subTest(key=key):
                a = self.allowed(key, year)
                self.assertIn(self.tokens[included], a)
                self.assertIn(self.tokens['scc'], a)
                self.assertNotIn(self.tokens['bcca'], a)

    def test_dated_sources_are_not_extrapolated_to_other_editions(self):
        for key, year in [('|131|manr|2d|61','1998'), ('|280|saskr||128','2006'),
                          ('|500|nbr|2d|1','2011'), ('|31|altalr|3d|227','1995'),
                          ('1997||bcj||2121',''), ('1997||oj||100',''),
                          ('|145|ar||64','1993'), ('|45|nsr|2d|428','1981')]:
            self.assertFalse(self.allowed(key, year))

    def test_alberta_sixth_series_includes_scc_and_both_bench_names(self):
        a = self.allowed('2020|1|altalr|6th|1')
        for code in ['abca','abqb','abkb','abpc','abcj','scc']:
            self.assertIn(self.tokens[code], a)
        self.assertNotIn(self.tokens['onca'], a)


if __name__ == "__main__":
    unittest.main()
