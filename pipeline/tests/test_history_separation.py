"""Appeal-history connectors keep two judgments apart (PROBLEMS #142).

Run: python pipeline/tests/test_history_separation.py
"""
import hashlib
import os
import sys
import tempfile
import unittest
import csv
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import decide  # noqa: E402
import merge  # noqa: E402


def mention(cid, start, end, key, pre):
    return {"candidate_id": cid, "source_decision_citation": "ONCA_X", "corpus_row_index": "1",
            "match_start_offset": str(start), "match_end_offset": str(end), "merge_key": key,
            "preceding_text": pre}


def row(key, court="ONCA", name="R. v. Bennett", year="1991", kind="reporter"):
    return {"court": court, "merge_key": key, "case_name_modal": name, "year_printed": year,
            "citation_kind": kind, "jurisdiction": "CA", "canonical_string": key,
            "key_occurrence_count": 1, "occurrence_count": 1, "self_citation_of": "",
            "self_case_name": "", "observed_deciding_court": "", "court_designation_conflict": ""}


def with_test_history_facts(history):
    """Give synthetic solver tests hash-addressed, instance-bound source facts."""
    if not history:
        return {}, None
    fields = ('source_decision_citation', 'corpus_row_index', 'instance', 'side',
              'merge_key', 'candidate_id', 'connector')
    out = {}
    rows = []
    for instance, sides in history.items():
        record = {'before': set(sides['before']), 'after': set(sides['after']), 'records': []}
        for side in ('before', 'after'):
            for index, key in enumerate(sorted(record[side])):
                connector = "aff'd"
                item = {
                    'source_decision_citation': 'TEST_DOC_' + instance,
                    'corpus_row_index': '1', 'instance': instance, 'side': side,
                    'merge_key': key, 'candidate_id': '%s-%s-%d' % (instance, side, index),
                    'connector': connector}
                rows.append(item)
                record['records'].append(item)
        out[instance] = record
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                                     suffix='.csv', delete=False) as source:
        writer = csv.DictWriter(source, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        path = source.name
    with open(path, 'rb') as source:
        digest = hashlib.sha256(source.read()).hexdigest()
    record_no = 2
    for instance in out:
        for item in out[instance]['records']:
            item['connector_sha256'] = hashlib.sha256(item['connector'].encode('utf-8')).hexdigest()
            item['source_locator'] = {
                'artifact': os.path.abspath(path).replace('\\', '/'),
                'resolved_artifact': os.path.abspath(path).replace('\\', '/'),
                'record': record_no, 'sha256': digest,
                'hash_scope': 'logical_csv_bytes'}
            record_no += 1
    return out, path


class HistoryInstanceTests(unittest.TestCase):
    def test_runs_on_both_sides_of_affd(self):
        text = "R. v. Bennett (1991), 3 O.R. (3d) 193, 64 C.C.C. (3d) 449 (C.A.), aff'd [1992] 2 S.C.R. 168"
        a, b, c = text.index("3 O.R."), text.index("64 C.C.C."), text.index("[1992]")
        rows = [mention("a", a, a + len("3 O.R. (3d) 193"), "1991|3|or|3d|193", text[:a][-120:]),
                mention("b", b, b + len("64 C.C.C. (3d) 449"), "|64|ccc|3d|449", text[:b][-120:]),
                mention("c", c, len(text), "1992|2|scr||168", text[:c][-120:])]
        stats = Counter()
        out = merge.history_instances(rows, stats)
        sides = {(r["side"], r["merge_key"]) for r in out}
        self.assertEqual(sides, {("before", "1991|3|or|3d|193"), ("before", "|64|ccc|3d|449"),
                                 ("after", "1992|2|scr||168")})
        self.assertEqual(stats["history_instances"], 1)

    def test_connector_variants(self):
        for gap in (" (Ont.\nC.A. ), at para. 22, leave to appeal to S.C.C.\nrefused ", ", affd. ",
                    ", allowing in part an appeal from ", " (C.A.); aff’d ", ", appeal dismissed "):
            pre = "Horgan (2007), 165 C.R.R. (2d) 332" + gap
            a, b = len("Horgan (2007), "), len(pre)
            rows = [mention("a", a, a + len("165 C.R.R. (2d) 332"), "2007|165|crr|2d|332", pre[:a]),
                    mention("b", b, b + 19, "2008|166|crr|2d|374", pre)]
            self.assertEqual(len(merge.history_instances(rows, Counter())), 2, gap)

    def test_native_pinpoint_forms_and_which_reversed(self):
        examples = (
            ("A v. B, [2002] 1 C.N.L.R. 57 at ¶ 36 (B.C.C.A.), aff'd [2003] 1 S.C.R. 71",
             "[2002] 1 C.N.L.R. 57", "[2003] 1 S.C.R. 71", "aff'd"),
            ("Wills v. Swartz Bros. [1935] S.C.R. 628, which reversed [1934] 3 W.W.R. 441",
             "[1935] S.C.R. 628", "[1934] 3 W.W.R. 441", "which reversed"),
            ("A v. B, 2007 ONCA 546, at paras. 12-13, and 26-27, leave to appeal refused (2008), 397 O.A.C. 397",
             "2007 ONCA 546", "(2008), 397 O.A.C. 397", "leave to appeal refused"),
            ("A v. B, (1998), 38 O.R. (3d) 590 (C.J. (Gen. Div.)) at p. 610; aff'd (1999), 44 O.R. (3d) 545",
             "(1998), 38 O.R. (3d) 590", "(1999), 44 O.R. (3d) 545", "aff'd"),
            ("A v. B, (1996), 28 O.R. (3d) 188 (Gen. Div.), para. 23; aff'd (1997), 97 O.A.C. 241",
             "(1996), 28 O.R. (3d) 188", "(1997), 97 O.A.C. 241", "aff'd"),
            ("A v. B, [2008] O.J. 2526 (S.C.) at paragraphs 34-36, aff'd 2009 ONCA 418",
             "[2008] O.J. 2526", "2009 ONCA 418", "aff'd"),
            ("A v. B, (1998), 131 C.C.C. (3d) 306 (Qc. C.A.), at pp319/20, aff'd (1999), 140 C.C.C. (3d) 225",
             "(1998), 131 C.C.C. (3d) 306", "(1999), 140 C.C.C. (3d) 225", "aff'd"),
            ("A v. B, 2017 BCCA 385 at para. 32, application for leave to appeal to SCC dismissed 2018 CanLII 35648",
             "2017 BCCA 385", "2018 CanLII 35648", "application for leave to appeal to SCC dismissed"),
            ("A v. B, 2017 BCCA 385 at para. 32, applications for leave to appeal to SCC dismissed 2018 CanLII 35648",
             "2017 BCCA 385", "2018 CanLII 35648", "applications for leave to appeal to SCC dismissed"),
            ("A v. B, (1996), 34 C.C.L.I. (2d) 119 (Ont. Ct. J. (Gen. Div.)), varied (1996), 29 O.R. (3d) 720",
             "(1996), 34 C.C.L.I. (2d) 119", "(1996), 29 O.R. (3d) 720", "varied"),
            ("A v. B, (1987), 6 R.F.L. (3d) 1 (Ont. Prov. Ct. (Fam. Div.)), reversed (1988), 21 R.F.L. (3d) 115",
             "(1987), 6 R.F.L. (3d) 1", "(1988), 21 R.F.L. (3d) 115", "reversed"),
            ("A v. B, (1962), 133 C.C.C. 174 (Alta. S.C.(A.D.)), leave to appeal refused [1962] S.C.R. x",
             "(1962), 133 C.C.C. 174", "[1962] S.C.R. x", "leave to appeal refused"),
        )
        for text, left_raw, right_raw, connector in examples:
            left, right = text.index(left_raw), text.index(right_raw)
            rows = [mention("a", left, left + len(left_raw), "left", text[:left][-120:]),
                    mention("b", right, right + len(right_raw), "right", text[:right][-120:])]
            out = merge.history_instances(rows, Counter())
            self.assertEqual({(r["side"], r["merge_key"]) for r in out},
                             {("before", "left"), ("after", "right")}, text)
            self.assertEqual({r["connector"] for r in out}, {connector}, text)

    def test_inserted_comment_and_open_leave_parenthesis_are_not_generic_heads(self):
        examples = (
            ("A v. B, [1974] O.J. No. 1856 (Ont. H.C.), made a pertinent comment at para. 29, rev'd on other grounds (1975), 22 C.C.C. (2d) 19",
             "[1974] O.J. No. 1856", "(1975), 22 C.C.C. (2d) 19"),
            ("A v. B, (1984), 42 C.R. (3d) 376 (leave to appeal to S.C.C. refused (1984), 16 C.C.C. (3d) 30)",
             "(1984), 42 C.R. (3d) 376", "(1984), 16 C.C.C. (3d) 30"),
        )
        for text, left_raw, right_raw in examples:
            left, right = text.index(left_raw), text.index(right_raw, text.index(left_raw) + len(left_raw))
            rows = [mention("a", left, left + len(left_raw), "left", text[:left][-120:]),
                    mention("b", right, right + len(right_raw), "right", text[:right][-120:])]
            self.assertEqual(merge.history_instances(rows, Counter()), [], text)

    def test_plain_parallel_string_has_no_instance(self):
        text = "Housen v. Nikolaisen, 2002 SCC 33, [2002] 2 S.C.R. 235"
        a, b = text.index("2002 SCC"), text.index("[2002]")
        rows = [mention("a", a, a + len("2002 SCC 33"), "2002||scc||33", text[:a]),
                mention("b", b, len(text), "2002|2|scr||235", text[:b])]
        self.assertEqual(merge.history_instances(rows, Counter()), [])

    def test_prose_between_citations_is_not_a_connector(self):
        text = "1 O.R. 1. The trial judge affirmed his view in 2 O.R. 2"
        b = text.index("2 O.R.")
        rows = [mention("a", 0, 8, "|1|or||1", ""), mention("b", b, len(text), "|2|or||2", text[:b])]
        self.assertEqual(merge.history_instances(rows, Counter()), [])


class HistorySplitTests(unittest.TestCase):
    def run_rows(self, history):
        members = [row("1991|3|or|3d|193"), row("|64|ccc|3d|449"),
                   row("1992|2|scr||168", year="1992"), row("|74|ccc|3d|384", year="1992")]
        did = {decide.row_key(m): {"S1", "S2", "S3"} for m in members}
        history, source_path = with_test_history_facts(history)
        try:
            out, _, _ = decide.adjudicate(members, did, {}, {}, "XC", Counter(), False, history=history)
        finally:
            if source_path:
                os.unlink(source_path)
        groups = {}
        for r in out:
            groups.setdefault(r["merged_group_id"], set()).add(r["merge_key"])
        return groups

    def test_unconstrained_multikey_group_preserves_original_reason_and_sequence(self):
        from identity_solve import split_by_history
        members = [row("|1|or||1", kind="neutral"), row("|2|or||2", kind="neutral")]
        did_idx = {decide.row_key(member): {"D1"} for member in members}
        original = (members, "existing_reason", "existing-sequence")
        out = split_by_history([original], {}, did_idx, Counter())
        self.assertEqual(len(out), 1)
        self.assertIs(out[0][0], members)
        self.assertEqual(out[0][1:], ("existing_reason", "existing-sequence"))

    def test_without_instances_name_year_keeps_one_group(self):
        self.assertEqual(len(self.run_rows({})), 1)

    def test_sides_split_and_parallels_follow_their_side(self):
        history = {"i1": {"before": {"1991|3|or|3d|193", "|64|ccc|3d|449"}, "after": {"1992|2|scr||168"}},
                   "i2": {"before": {"|64|ccc|3d|449"}, "after": {"|74|ccc|3d|384"}}}
        groups = list(self.run_rows(history).values())
        self.assertIn({"1991|3|or|3d|193", "|64|ccc|3d|449"}, groups)
        self.assertFalse(any({"1991|3|or|3d|193", "1992|2|scr||168"} <= g for g in groups))
        self.assertFalse(any({"|64|ccc|3d|449", "|74|ccc|3d|384"} <= g for g in groups))

    def test_contradictory_instance_is_ignored(self):
        history = {"i1": {"before": {"1991|3|or|3d|193"}, "after": {"1992|2|scr||168"}},
                   "i2": {"before": {"1991|3|or|3d|193", "1992|2|scr||168"}, "after": {"|74|ccc|3d|384"}}}
        self.assertEqual(len(self.run_rows(history)), 1)

    def test_same_report_union_respects_history(self):
        # The same S.C.R. key cited from two courts must not bridge the two sides.
        members = [row("1991|3|or|3d|193", name="A v. B"), row("1992|2|scr||168", year="1992", name="A v. B"),
                   row("1992|2|scr||168", court="SCC", year="1992", name="")]
        did = {decide.row_key(m): {decide.row_key(m)} for m in members}
        history = {"i1": {"before": {"1991|3|or|3d|193"}, "after": {"1992|2|scr||168"}}}
        history, source_path = with_test_history_facts(history)
        try:
            out, _, _ = decide.adjudicate(members, did, {}, {}, "XC", Counter(), False, history=history)
        finally:
            os.unlink(source_path)
        groups = {}
        for r in out:
            groups.setdefault(r["merged_group_id"], set()).add(r["court"] + "|" + r["merge_key"])
        self.assertFalse(any({"ONCA|1991|3|or|3d|193", "SCC|1992|2|scr||168"} <= g for g in groups.values()))
        self.assertTrue(any({"ONCA|1992|2|scr||168", "SCC|1992|2|scr||168"} <= g for g in groups.values()))


if __name__ == "__main__":
    unittest.main()
