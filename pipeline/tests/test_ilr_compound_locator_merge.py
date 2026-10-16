"""Merge may complete an ILR partial page only from the verified new shape.

The locator is a printed paragraph identifier (for example 1-2261), not a
generic page range. This test keeps the old partial candidate in the ledger and
checks the narrow span-completion edge plus adversarial field changes.
"""
from collections import Counter
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

import classify
import extract
import merge


TEXT = "[1988] I.L.R. 1-2261"


def classified_candidates(text=TEXT):
    tables = {
        name: classify.load_table(name + ".csv")
        for name in ("neutral_court_codes", "reporter_jurisdiction", "series_prefix",
                     "reporter_compound_locators")
    }
    classifier = classify.Classifier(tables, Counter())
    raw, _ = extract.extract_candidates(text, "ONCA_fixture", "2026", 0, "ONCA")
    return [classifier.run_row(dict(row)) for row in raw]


class CompoundLocatorMergeTests(unittest.TestCase):
    def setUp(self):
        self.rows = classified_candidates()
        self.short = next(row for row in self.rows if row["shape_name"] == "shape_bracket")
        self.long = next(row for row in self.rows
                         if row["shape_name"] == "shape_bracket_compound_locator")

    def test_verified_compound_locator_completes_old_page_prefix(self):
        self.assertEqual(self.short["page"], "1")
        self.assertEqual(self.long["page"], "1-2261")
        self.assertEqual(self.long["compound_locator_rule_id"], "ILR_NUMERIC_PARAGRAPH")
        self.assertEqual(self.short["raw_string"], "[1988] I.L.R. 1")
        self.assertEqual(self.long["raw_string"], "[1988] I.L.R. 1-2261")
        self.assertTrue(merge._fields_compatible(self.short, self.long))

        verdicts = merge.arbitrate_document(self.rows, Counter())
        self.assertEqual(verdicts[self.long["candidate_id"]][0], "counted")
        self.assertNotEqual(verdicts[self.short["candidate_id"]][0], "counted")
        # The old candidate remains available in the immutable candidate ledger.
        self.assertEqual(len(self.rows), 2)

    def test_gulf_full_locator_wins_and_preserves_its_short_candidate(self):
        rows = classified_candidates("[1990] I.L.R. 1-2644")
        short = next(row for row in rows if row["shape_name"] == "shape_bracket")
        long = next(row for row in rows
                    if row["shape_name"] == "shape_bracket_compound_locator")
        verdicts = merge.arbitrate_document(rows, Counter())
        self.assertEqual(long["page"], "1-2644")
        self.assertEqual(verdicts[long["candidate_id"]][0], "counted")
        self.assertNotEqual(verdicts[short["candidate_id"]][0], "counted")
        self.assertEqual(len(rows), 2)

    def test_wrong_rule_id_or_locator_form_never_completes(self):
        for field, value in (
            ("compound_locator_rule_id", ""),
            ("compound_locator_rule_id", "UNRELATED_RULE"),
            ("page", "1–2261"),  # only the table-authorized ASCII hyphen
            ("page", "1-22"),
            ("page", "1-123456"),
        ):
            with self.subTest(field=field, value=value):
                altered = copy.deepcopy(self.long)
                altered[field] = value
                self.assertFalse(merge._fields_compatible(self.short, altered))

    def test_unverified_dash_or_locator_bounds_do_not_create_new_shape(self):
        for locator in ("1–2261", "1—2261", "1‑2261", "1-22", "1-123456"):
            with self.subTest(locator=locator):
                rows = classified_candidates("[1988] I.L.R. " + locator)
                self.assertFalse(any(row["shape_name"] == "shape_bracket_compound_locator"
                                     for row in rows))

    def test_wrong_candidate_identity_or_evidence_spans_never_complete(self):
        bad_short = []
        row = copy.deepcopy(self.short)
        row["page"] = "2"
        bad_short.append(row)
        row = copy.deepcopy(self.short)
        row["year_start"] = "1989"
        bad_short.append(row)
        row = copy.deepcopy(self.short)
        row["token"] = "O.R."
        bad_short.append(row)
        row = copy.deepcopy(self.short)
        row["match_start_offset"] += 1
        bad_short.append(row)
        row = copy.deepcopy(self.short)
        row["raw_string"] = row["raw_string"].replace("I.L.R.", "O.R.")
        bad_short.append(row)
        for altered in bad_short:
            with self.subTest(row=altered):
                self.assertFalse(merge._fields_compatible(altered, self.long))

        for field, value in (
            ("page_span", "32:37"),
            ("year_span", "18:22"),
            ("match_end_offset", self.long["match_end_offset"] - 1),
            ("raw_string", self.long["raw_string"].replace("1-2261", "1–2261")),
            ("citation_kind", "ambiguous"),
        ):
            with self.subTest(field=field, value=value):
                altered = copy.deepcopy(self.long)
                altered[field] = value
                self.assertFalse(merge._fields_compatible(self.short, altered))

    def test_wrong_shape_or_extra_reporter_slot_never_completes(self):
        altered = copy.deepcopy(self.long)
        altered["shape_name"] = "shape_bracket"
        self.assertFalse(merge._fields_compatible(self.short, altered))
        altered = copy.deepcopy(self.long)
        altered["vol"] = "2"
        self.assertFalse(merge._fields_compatible(self.short, altered))


if __name__ == "__main__":
    unittest.main()
