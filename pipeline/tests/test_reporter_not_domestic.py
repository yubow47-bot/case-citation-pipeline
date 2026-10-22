"""PROBLEMS #181: sourced English Law Reports windows and not-Canadian evidence.

Uses the real decision tables. Homonyms (Quebec K.B./Q.B., the Canadian Western Law
Reporter) and the last Canadian Privy Council appeal are the counterexamples.
"""
from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decide  # noqa: E402
import edges  # noqa: E402


def origin_idx():
    idx = decide.load_case_origin()
    for key, rows in decide.load_case_origin_manual().items():
        idx.setdefault(key, []).extend(rows)
    return idx


class ReporterWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.idx = dict(origin_idx=origin_idx(), scope_idx=decide.load_scope(),
                       reporter_idx=decide.load_reporter_origin(),
                       not_domestic_idx=decide.load_not_domestic_rules())

    def assess(self, citation, key, year='', court='', conflict=''):
        row = dict(merge_key=key, canonical_string=citation, citation_kind='reporter',
                   jurisdiction='GB', year_printed=year, observed_deciding_court=court,
                   court_designation_conflict=conflict)
        decide.decide_case_origin(row, [citation], self.idx['origin_idx'], Counter(),
                                  scope_idx=self.idx['scope_idx'],
                                  reporter_idx=self.idx['reporter_idx'],
                                  not_domestic_idx=self.idx['not_domestic_idx'])
        return row['member_origin_status'], row['member_origin_country'], row['member_origin_basis']

    def test_english_kings_bench_needs_year_and_low_volume(self):
        self.assertEqual(self.assess('[1930] 1 K.B. 129', '1930|1|kb||129', '1930'),
                         ('DETERMINED', 'GB', 'exclusive_reporter_scope'))
        for citation, key, year in (('(1929) 47 K.B. 271', '1929|47|kb||271', '1929'),  # Quebec
                                    ('[1936] K.B. 382', '1936||kb||382', '1936'),        # no volume
                                    ('2 K.B. 724', '|2|kb||724', ''),                    # no year
                                    ('[1945] 1 K.B. 100', '1945|1|kb||100', '1945')):    # Quebec by year
            with self.subTest(citation=citation):
                self.assertEqual(self.assess(citation, key, year)[0], 'UNDETERMINED')

    def test_queens_bench_window_starts_after_quebec_renaming(self):
        self.assertEqual(self.assess('[1980] Q.B. 1', '1980||qb||1', '1980')[:2], ('DETERMINED', 'GB'))
        self.assertEqual(self.assess('[1965] 1 Q.B. 1', '1965|1|qb||1', '1965')[0], 'UNDETERMINED')
        self.assertEqual(self.assess('[1893] 1 Q.B. 1', '1893|1|qb||1', '1893')[0], 'UNDETERMINED')

    def test_second_series_and_chancery(self):
        self.assertEqual(self.assess('(1881), 7 Q.B.D. 244', '1881|7|qbd||244', '1881')[:2], ('DETERMINED', 'GB'))
        self.assertEqual(self.assess('(1876) 3 Ch. D. 1', '1876|3|chd||1', '1876')[:2], ('DETERMINED', 'GB'))
        self.assertEqual(self.assess('[1907] Ch. 406', '1907||ch||406', '1907')[:2], ('DETERMINED', 'GB'))
        self.assertEqual(self.assess('(1877), 7 Ch. 166', '1877|7|ch||166', '1877')[0], 'UNDETERMINED')

    def test_late_appeal_cases_are_not_canadian_without_a_country(self):
        self.assertEqual(self.assess('[1964] A.C. 1001', '1964||ac||1001', '1964'),
                         ('NOT_DOMESTIC', '', 'not_domestic_window'))
        # A case record (Hedley Byrne, House of Lords) still outranks the window.
        self.assertEqual(self.assess('[1964] A.C. 465', '1964||ac||465', '1964')[:2], ('DETERMINED', 'GB'))
        self.assertEqual(self.assess('[1975] 1 All E.R. 504', '1975|1|aller||504', '1975')[0], 'NOT_DOMESTIC')

    def test_last_canadian_privy_council_appeal_stays_canadian(self):
        # Ponoka-Calmar was decided 1959-10-07 and printed in the 1960 volume.
        self.assertEqual(self.assess('[1960] A.C. 18', '1960||ac||18', '1960')[:2], ('DETERMINED', 'CA'))
        self.assertEqual(self.assess('[1960] A.C. 1', '1960||ac||1', '1960')[0], 'UNDETERMINED')

    def test_western_law_reporter_is_never_not_domestic(self):
        self.assertEqual(self.assess('(1907), 7 W.L.R. 284', '1907|7|wlr||284', '1907')[0], 'UNDETERMINED')
        self.assertEqual(self.assess('7 W.L.R. 307', '|7|wlr||307', '')[0], 'UNDETERMINED')
        self.assertEqual(self.assess('7 W.L.R. 307', '|7|wlr||307', '', court='House of Lords')[0],
                         'UNDETERMINED')

    def test_printed_house_of_lords_but_not_privy_council(self):
        self.assertEqual(self.assess('[1932] A.C. 999', '1932||ac||999', '1932', court='House of Lords'),
                         ('NOT_DOMESTIC', '', 'not_domestic_printed_court'))
        self.assertEqual(self.assess('[1932] A.C. 304', '1932||ac||304', '1932',
                                     court='Judicial Committee of the Privy Council')[0], 'UNDETERMINED')
        self.assertEqual(self.assess('[1932] A.C. 304', '1932||ac||304', '1932', court='House of Lords',
                                     conflict='true')[0], 'UNDETERMINED')


class NotDomesticAggregationTests(unittest.TestCase):
    def group(self, *members):
        rows = [dict(identity_basis='anchor', member_origin_status=s, member_origin_country=c,
                     member_origin_basis=b, member_origin_evidence_ids=b + ':x') for s, c, b in members]
        decide.aggregate_group_origin(rows, Counter())
        return rows[0]['group_foreign_status'], rows[0]['group_origin_country'], rows[0]['group_origin_status']

    def test_alone_it_is_foreign_with_unknown_country(self):
        self.assertEqual(self.group(('NOT_DOMESTIC', '', 'not_domestic_window')),
                         ('FOREIGN', '', 'UNDETERMINED'))

    def test_it_agrees_with_a_foreign_country_and_contradicts_canada(self):
        self.assertEqual(self.group(('NOT_DOMESTIC', '', 'not_domestic_window'),
                                    ('DETERMINED', 'GB', 'exclusive_reporter_scope')),
                         ('FOREIGN', 'GB', 'DETERMINED'))
        self.assertEqual(self.group(('NOT_DOMESTIC', '', 'not_domestic_window'),
                                    ('DETERMINED', 'CA', 'exclusive_reporter_scope'))[0], 'CONFLICT')

    def test_edge_uses_the_cited_members_observation(self):
        group = dict(group_foreign_status='CONFLICT', group_origin_country='',
                     group_origin_basis='x', group_origin_evidence_ids='x')
        notdom = dict(member_origin_status='NOT_DOMESTIC', member_origin_country='',
                      member_origin_basis='not_domestic_window', member_origin_evidence_ids='not_domestic:A.C.')
        canada = dict(member_origin_status='DETERMINED', member_origin_country='CA',
                      member_origin_basis='exclusive_reporter_scope', member_origin_evidence_ids='reporter_scope:D.L.R.')
        self.assertEqual(edges.origin_for_edge(group, [notdom], True)[:2], ('FOREIGN', ''))
        self.assertEqual(edges.origin_for_edge(group, [notdom, canada], True)[0], 'CONFLICT')
        self.assertEqual(edges.origin_for_edge(group, [canada], True)[:2], ('DOMESTIC_CA', 'CA'))


if __name__ == '__main__':
    unittest.main()
