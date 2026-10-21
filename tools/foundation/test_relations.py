"""Relation labels for citation edges (PROBLEMS #140).

Run: python -m unittest tools/foundation/test_relations.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import relations  # noqa: E402


class RelationTests(unittest.TestCase):
    def label(self, own, source, source_year, cited, cited_year):
        return relations.relation_of(own, relations.title_key(source), source_year,
                                     relations.title_key(cited), cited_year)

    def test_own_citation_identity_wins(self):
        self.assertEqual(self.label(True, 'A v. B', 2000, 'C v. D', 1950), 'same_case_history')

    def test_same_title_within_window_is_probable_history(self):
        self.assertEqual(self.label(False, 'R. v. Bennett', 1992, 'R. v. Bennett (1991)', 1991),
                         'probable_same_litigation')
        self.assertEqual(self.label(False, 'Booty v. Hutton', 2009, 'Booty v. Hutton', 2009),
                         'probable_same_litigation')

    def test_outside_window_or_later_or_untitled_is_other(self):
        self.assertEqual(self.label(False, 'R. v. Smith', 2010, 'R. v. Smith', 1990), 'other_judgment')
        self.assertEqual(self.label(False, 'R. v. Smith', 2010, 'R. v. Smith', 2012), 'other_judgment')
        self.assertEqual(self.label(False, '', 2010, '', 2010), 'other_judgment')
        self.assertEqual(self.label(False, 'R. v. Smith', None, 'R. v. Smith', 2009), 'other_judgment')

    def test_pair_level_history_basis(self):
        def rel(basis, own=False):
            return relations.relation_of(own, '', None, '', None, basis)
        self.assertEqual(rel('formal_all'), 'same_case_history')
        self.assertEqual(rel('formal_pair'), 'same_case_history')
        self.assertEqual(rel('model'), 'same_case_history_model')
        self.assertEqual(rel('none'), 'other_judgment')
        self.assertEqual(rel(''), 'other_judgment')
        # Printed identity outranks a model judgment.
        self.assertEqual(rel('model', own=True), 'same_case_history')

    def test_jev_banner_only_for_model_runs(self):
        import query
        off = {'params': {'jev': 'off'}}
        live = {'params': {'jev': 'live'}, 'jev': {'layers': {'edges': {'model': 'jev-1.13.0'}}}}
        self.assertEqual(query.jev_banner(off), '')
        self.assertEqual(query.jev_banner({'params': {}}), '')
        self.assertIn('jev-1.13.0', query.jev_banner(live))

    def test_inner_year_is_part_of_the_title(self):
        self.assertNotEqual(relations.title_key('Voyageur (1969) Inc. v. X'), relations.title_key('Voyageur Inc. v. X'))
        self.assertEqual(relations.year_of('2004-05-01 00:00:00+00:00'), 2004)


if __name__ == '__main__':
    unittest.main()
