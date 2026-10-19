"""F1/I1: source-printed reporter collisions must not become identity bridges.

Native counterexamples and locators are documented in the 2026-10-19 identity
reports. Fixtures contain citation metadata only, never judgment excerpts.
"""
from collections import Counter
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'pipeline'), str(ROOT/'pipeline/tests')]
from identity_solve import solve_identity
from identity_evidence import EvidenceSnapshot, row_key
from identity_constraints import ConstraintLedger
import test_parallel_runs as parallel_fixture
member = parallel_fixture.member
from parallel_runs import load_parallel_runs


class ReporterContextIdentityTests(unittest.TestCase):
    def solve(self, rows, sources=None, parallels=None):
        sources = sources or {row_key(r): {r['court']+'_source'} for r in rows}
        stats = Counter()
        trace = ConstraintLedger(EvidenceSnapshot(rows, sources, 'TEST', parallels=parallels))
        out, _ = solve_identity(rows, sources, 'TEST', stats,
            registry={}, gate='registered', holdout=[], identity_separations=[],
            trace=trace, history={}, parallels=parallels)
        self.assertEqual(sorted(map(row_key, rows)),
                         sorted(row_key(r) for c in out for r in c[0]))
        return out, stats, trace

    def test_four_native_reporter_collision_contexts_separate(self):
        # Native sources: BCSC_2008bcsc1619; NSCA_2008nsca117;
        # BCSC_2004bcsc72; NSSC_2010nssc26. The shared number is
        # printed in each source, so extraction is deliberately not corrected.
        cases = [
            ('1997||bcj||2543', '1997|99|bcac||22', '1997|99|bcac||134',
             'Robertson v. Canadian Imperial Bank of Commerce', 'Darlington v. Darlington', '1997'),
            ('|101|nsr|2d|243', '1991||nsj||86', '|106|nsr|2d|300',
             'Minkoff v. Poole and Lambert', 'R. v. Nickerson', '1991'),
            ('1993||bcj||1408', '1993||bcj||1049', '1993|50|cpr|3d|76',
             'Goudie v. Goudie', 'Macri v. Miskiewicz', '1993'),
            ('1993||bcj||395', '1993|77|bclr|2d|305', '1993|44|mvr|2d|295',
             'Leung v. Leung', 'R. v. Thimsen', '1993')]
        for collision, first, second, title_a, title_b, year in cases:
            with self.subTest(key=collision):
                rows = [member(collision, year=year, name=title_a, court='BCCA'),
                        member(first, year=year, name=title_a, court='BCCA'),
                        member(collision, year=year, name=title_b, court='BCSC'),
                        member(second, year=year, name=title_b, court='BCSC')]
                out, stats, trace = self.solve(rows)
                self.assertFalse(any({title_a, title_b} <=
                    {r['case_name_modal'] for r in c[0]} for c in out))
                self.assertEqual(stats['reporter_identity_conflicted_keys'], 1)
                self.assertTrue(all(r['reporter_identity_conflict'] == 'true'
                                    for r in rows if r['merge_key'] == collision))
                self.assertTrue(any(r['split_reason'] == 'reporter_context_conflict'
                                    for r in trace.records['solution']))

    def test_genuine_title_variants_and_absent_names_still_join(self):
        for names in [
            ('Hedley Byrne & Co. v. Heller & Partners Ltd',
             'Hedley Byrne & Co Ltd v Heller & Partners Ltd'),
            ('Minkoff v. Poole', 'Minkoff v. Poole and Lambert'),
            ('Robertson v CIBC', 'Robertson v. Canadian Imperial Bank of Commerce'),
            ('R. v. Bottineau', 'R. v. E.B'),
            ('R. v. Smith', 'R v Smyth'),
            ('Alpha v. Beta', '')]:
            with self.subTest(names=names):
                rows = [member('1964||ac||465', year='1964', name=names[0], court='BCCA'),
                        member('1964||ac||465', year='1964', name=names[1], court='BCSC')]
                out, stats, _ = self.solve(rows)
                self.assertEqual(len(out), 1)
                self.assertEqual(stats['reporter_identity_conflicted_keys'], 0)

    def test_conflicted_key_cannot_reenter_through_printed_parallel_run(self):
        fixture = parallel_fixture.ParallelTests(); fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        collision, a, b = '1997||bcj||2543', '1997|99|bcac||22', '1997|99|bcac||134'
        path, _, _ = fixture.fixture((collision, a))
        rows = [member(collision, year='1997', name='Robertson v. CIBC', court='BCCA'),
                member(a, year='1997', name='Robertson v. CIBC', court='BCCA'),
                member(collision, year='1997', name='Darlington v. Darlington', court='BCSC'),
                member(b, year='1997', name='Darlington v. Darlington', court='BCSC')]
        out, stats, _ = self.solve(rows, parallels=load_parallel_runs([path]))
        self.assertEqual(len(out), 2)
        self.assertEqual(stats['parallel_blocked_reporter_context_conflict'], 1)
        self.assertTrue(all(not r['co_printed_run_ids'] for r in rows))


if __name__ == '__main__':
    unittest.main()
