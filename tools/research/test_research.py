"""Offline contract tests; temporary tiny fixtures are deleted after every test."""
import contextlib
import csv
import gzip
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from core import (Filters, ResearchSource, canonical, make_packet, route_question,
                  sha_text, enrich_corpus, make_lookup_packet)
from fixture import create_fixture, write_csv
from research import bounded_write, main, result_csv, open_source, parser


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = create_fixture(self.root)

    def source(self):
        source = ResearchSource.sqlite(self.fixture["db"])
        self.addCleanup(source.close)
        return source

    def packet(self, intent="count", **kwargs):
        return make_packet(self.source(), intent, evidence_limit=0, **kwargs)

    def test_exact_totals_and_unknown_heuristic_origin(self):
        packet = self.packet()
        summary = packet["exact_results"]["summary"]
        for key, expected in self.fixture["expected"].items():
            self.assertEqual(summary[key], expected, key)
        self.assertEqual(summary["citing_source_ids"], 4)
        self.assertEqual(summary["edges_unknown_source_year"], 2)
        self.assertEqual(summary["edges_missing_document_metadata"], 1)
        self.assertAlmostEqual(summary["origin_coverage"], 4 / 6)
        self.assertAlmostEqual(summary["foreign_share_all_edges"], 1 / 6)
        self.assertAlmostEqual(summary["foreign_share_determined_edges"], 1 / 4)

    def test_zero_edges_and_unknown_metadata_remain_in_stats(self):
        packet = self.packet("court_decade")
        matrix = {(r["source_court"], r["decade"]): r for r in packet["exact_results"]["rows"]}
        self.assertEqual(matrix[("SCC", 2010)]["corpus_source_ids"], 1)
        self.assertEqual(matrix[("SCC", 2010)]["citation_edges"], 0)
        self.assertIsNone(matrix[("SCC", 2010)]["origin_coverage"])
        self.assertEqual(matrix[("SCC", None)]["corpus_document_rows"], 3)
        self.assertEqual(matrix[("SCC", None)]["duplicate_source_ids"], 1)
        self.assertEqual(matrix[("SCC", None)]["citation_edges"], 1)
        self.assertEqual(matrix[("UNKNOWN", None)]["citation_edges"], 1)

    def test_empty_citation_placeholders_do_not_become_judgment_ids(self):
        db = sqlite3.connect(self.fixture["db"])
        db.executemany("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)",
                       [("run_fixture", "SCC", row, "SCC_", "", "", "", "missing.parquet") for row in (10, 11)])
        db.commit()
        db.close()
        packet = self.packet("court_decade")
        diagnostics = packet["exact_results"]["full_corpus_metadata_diagnostics"]
        self.assertEqual(diagnostics["corpus_document_rows"], 8)
        self.assertEqual(diagnostics["valid_corpus_source_ids"], 5)
        self.assertEqual(diagnostics["invalid_source_id_document_rows"], 2)
        self.assertEqual(diagnostics["empty_citation_document_rows"], 2)
        self.assertEqual(diagnostics["empty_date_document_rows"], 2)
        matrix = {(r["source_court"], r["decade"]): r for r in packet["exact_results"]["rows"]}
        self.assertEqual(matrix[("SCC", None)]["corpus_document_rows"], 5)
        self.assertEqual(matrix[("SCC", None)]["corpus_source_ids"], 2)
        self.assertEqual(matrix[("SCC", None)]["corpus_source_ids_including_placeholders"], 3)
        self.assertEqual(matrix[("SCC", None)]["duplicate_source_ids"], 1)
        self.assertEqual(packet["exact_results"]["summary"]["citation_edges"], 6)

    def test_date_court_dd_filters_precede_aggregation(self):
        packet = self.packet(filters=Filters(court="SCC", year_from=2000, year_to=2009, min_dd=2))
        self.assertEqual(packet["exact_results"]["summary"]["citation_edges"], 2)
        packet = self.packet(filters=Filters(origin="FOREIGN"))
        self.assertEqual(packet["exact_results"]["summary"]["citation_edges"], 1)
        self.assertEqual(packet["exact_results"]["summary"]["heuristic_only_edges"], 0)
        self.assertEqual(sum(d["corpus_document_rows"] for d in packet["exact_results"]["document_denominators"]), 6)

    def test_invalid_calendar_dates_are_not_a_known_year(self):
        db = sqlite3.connect(self.fixture["db"])
        db.execute("UPDATE documents SET decision_date='2001-02-29' WHERE source_id='SCC_2000scc1'")
        db.commit()
        db.close()
        packet = self.packet()
        self.assertEqual(packet["exact_results"]["summary"]["edges_unknown_source_year"], 4)

    def test_ranking_uses_scoped_dd_and_global_dd_is_separate(self):
        packet = self.packet("ranking", filters=Filters(court="SCC", year_from=2000, year_to=2009), top=1)
        row = packet["exact_results"]["rows"][0]
        self.assertEqual(row["filtered_dd"], 1)
        self.assertEqual(row["global_dd"], 3)
        self.assertEqual(packet["exact_results"]["summary"]["cited_groups"], 2)

    def test_case_preview_cannot_change_full_count(self):
        packet = self.packet("case_citations", filters=Filters(group_id="XC-G000001"), top=1)
        self.assertEqual(packet["exact_results"]["summary"]["citation_edges"], 3)
        self.assertEqual(len(packet["exact_results"]["rows"]), 1)
        self.assertTrue(packet["exact_results"]["preview_truncated"])

    def test_packet_digest_and_queries_are_auditable(self):
        packet = self.packet()
        digest = packet.pop("packet_sha256")
        self.assertEqual(digest, sha_text(canonical(packet)))
        self.assertTrue(packet["query_plan"])
        self.assertTrue(all(q["parameters"][0] == "run_fixture" for q in packet["query_plan"]))
        self.assertIn("input_identity", packet["run_identity"]["manifest"])
        self.assertIn("does not mean followed", packet["capabilities"]["counting_meaning"])

    def test_streaming_gzip_matches_sqlite_without_persistent_cache(self):
        source = ResearchSource.stream(self.fixture["run"], documents=self.fixture["documents"])
        self.addCleanup(source.close)
        actual = make_packet(source, "court_decade", evidence_limit=0)
        expected = self.packet("court_decade")
        self.assertEqual(actual["exact_results"], expected["exact_results"])
        self.assertEqual(actual["storage"]["persistent_query_cache_bytes"], 0)
        self.assertEqual(actual["run_identity"]["source"]["document_metadata_verification"].split(";")[0], "caller_supplied")

    def test_streaming_verifies_sealed_physical_artifacts(self):
        run = Path(self.fixture["run"])
        manifest_path = run / "run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = {relative: hashlib.sha256((run / relative).read_bytes()).hexdigest()
                 for relative in ("select_out/selected.csv.gz", "edges/citation_edges.csv.gz")}
        manifest["output_identity"] = {"files": files,
            "fingerprint": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        source = ResearchSource.stream(run, documents=self.fixture["documents"])
        source.close()
        selected = run / "select_out" / "selected.csv.gz"
        with gzip.open(selected, "rt", encoding="utf-8") as f:
            text = f.read().replace("Alpha v Beta", "Changed title")
        with gzip.open(selected, "wt", encoding="utf-8") as f:
            f.write(text)
        with self.assertRaisesRegex(ValueError, "output seal"):
            ResearchSource.stream(run, documents=self.fixture["documents"])

    def test_evidence_uses_counted_candidates_and_unicode_spans(self):
        packet = make_packet(self.source(), "case_citations", Filters(group_id="XC-G000001", court="SCC", year_from=2000), evidence_limit=1)
        item = packet["evidence"][0]
        self.assertEqual(item["candidate"]["candidate_id"], "SCC:0:fixture")
        self.assertEqual(item["candidate"]["csv_record_number"], 3)
        self.assertEqual(item["span"]["start"], len("判决😀 Alpha mentions "))
        self.assertEqual(item["quote_sha256"], sha_text("[1990] SCC 10"))
        self.assertEqual(item["status"], "candidate_span_located_corpus_not_read")
        self.assertIsNone(packet["exact_results"].get("semantic_accuracy"))

    def test_missing_evidence_is_explicit(self):
        packet = make_packet(self.source(), "count", Filters(origin="FOREIGN"), evidence_limit=1)
        item = packet["evidence"][0]
        self.assertEqual(item["status"], "document_metadata_missing_or_conflicting")
        self.assertIsNone(item["span"])
        self.assertIsNone(item["quote"])

    def test_normalized_ready_index_provenance_is_expanded(self):
        source = self.source()
        first = make_packet(source, "case_citations", Filters(group_id="XC-G000001", court="SCC", year_from=2000), evidence_limit=1)["evidence"][0]
        source.close()
        db = sqlite3.connect(self.fixture["db"])
        db.execute("CREATE TABLE run_sources(run_id TEXT,logical_path TEXT,actual_path TEXT,sha256 TEXT,physical_sha256 TEXT,size_bytes INTEGER,compression TEXT)")
        logical = "merge_out/SCC/mentions_candidates.csv"
        db.execute("INSERT INTO run_sources VALUES(?,?,?,?,?,?,?)", ("run_fixture", logical, first["candidate"]["ledger_path"], "logicalhash", "physicalhash", 200, "gzip"))
        db.execute("CREATE TABLE run_components(run_id TEXT,component TEXT,generation INTEGER,status TEXT,source_fingerprint TEXT,details_json TEXT,updated_at TEXT)")
        db.execute("INSERT INTO run_components VALUES(?,?,?,?,?,?,?)", ("run_fixture", "edges", 2, "ready", "sources-v2", "{}", "2026-10-14"))
        db.execute("CREATE TABLE edge_passages(run_id TEXT,source_decision TEXT,resolved_cited_case TEXT,passage TEXT,evidence_json TEXT)")
        start, end = first["span"]["start"], first["span"]["end"]
        locator = {"court": "SCC", "corpus_row": 0, "match_start": start, "match_end": end,
                   "window_start": 0, "window_end": end, "mention_record": 3,
                   "corpus": {"logical_path": "corpus/SCC.parquet"}, "mentions": {"logical_path": logical}}
        db.execute("INSERT INTO edge_passages VALUES(?,?,?,?,?)", ("run_fixture", "SCC_2000scc1", "XC-G000001", "normalized passage", json.dumps(locator)))
        db.commit()
        db.close()
        packet = make_packet(self.source(), "case_citations", Filters(group_id="XC-G000001", court="SCC", year_from=2000), evidence_limit=1)
        item = packet["evidence"][0]
        self.assertEqual(item["indexed_evidence_locator"]["mentions"]["sha256"], "logicalhash")
        self.assertEqual(item["evidence_generation"]["generation"], 2)
        self.assertEqual(item["indexed_passage_sha256"], sha_text("normalized passage"))
        self.assertEqual(item["status"], "candidate_span_located_corpus_not_read")

    def test_output_cannot_overwrite_input_run(self):
        target = str(Path(self.fixture["run"]) / "run_manifest.json")
        with contextlib.redirect_stderr(io.StringIO()) as out:
            status = main(["stats", "--db", self.fixture["db"], "--evidence-limit", "0", "--output", target])
        self.assertEqual(status, 1)
        self.assertIn("source run", out.getvalue())

    def test_questions_route_only_supported_templates(self):
        courts = ["SCC", "ONCA"]
        expected = route_question("SCC 2000-2020 外国引证数量", courts)
        self.assertEqual(expected[0], "count")
        self.assertEqual(expected[1], Filters(court="SCC", year_from=2000, year_to=2020, origin="FOREIGN"))
        self.assertEqual(route_question("引证最多的前10个判决", courts)[0], "ranking")
        self.assertEqual(route_question("top 5 most cited cases in SCC", courts)[2], 5)
        self.assertEqual(route_question("哪些判决引用 XC-G000001", courts)[0], "case_citations")
        for question in ("SELECT * FROM citation_edges", "why did SCC follow Housen?", "前5个判决有什么法律意义", "SCC ONCA citation count", "哪些判决引用 Housen"):
            self.assertIsNone(route_question(question, courts), question)

    def test_multiple_ready_runs_need_explicit_selection(self):
        db = sqlite3.connect(self.fixture["db"])
        db.execute("INSERT INTO runs SELECT 'other',source_directory,input_fingerprint,manifest_json,imported_at,status FROM runs")
        db.commit()
        db.close()
        with self.assertRaisesRegex(ValueError, "explicitly"):
            ResearchSource.sqlite(self.fixture["db"])
        source = ResearchSource.sqlite(self.fixture["db"], "run_fixture")
        source.close()

    def test_read_only_database_and_snapshot_manifest(self):
        source = self.source()
        with self.assertRaises(sqlite3.OperationalError):
            source.db.execute("DELETE FROM citation_edges")
        path = Path(self.fixture["run"]) / "run_manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["params"]["courts"].append("BCCA")
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "differs"):
            ResearchSource.sqlite(self.fixture["db"])

    def test_unknown_case_and_bad_filters_fail_clearly(self):
        source = self.source()
        with self.assertRaisesRegex(ValueError, "outside this run"):
            make_packet(source, "count", Filters(court="FCA"), evidence_limit=0)
        with self.assertRaisesRegex(ValueError, "requires an explicit"):
            make_packet(source, "case_citations", evidence_limit=0)
        with self.assertRaisesRegex(ValueError, "not present"):
            make_packet(source, "case_citations", Filters(group_id="XC-G999999"), evidence_limit=0)

    def test_invalid_edge_cannot_be_answered(self):
        db = sqlite3.connect(self.fixture["db"])
        db.execute("UPDATE citation_edges SET foreign_status='FOREIGN',origin_country='UK' WHERE edge_support='heuristic_only'")
        db.commit()
        db.close()
        with self.assertRaisesRegex(ValueError, "counting contracts"):
            ResearchSource.sqlite(self.fixture["db"])

    def test_member_country_counts_without_upgrading_identity_support(self):
        db = sqlite3.connect(self.fixture["db"])
        db.execute("UPDATE citation_edges SET foreign_status='DOMESTIC_CA',origin_country='CA',"
                   "origin_basis='member:classification_jurisdiction',origin_evidence_ids='classification:fixture:CA' "
                   "WHERE edge_support='heuristic_only'")
        db.commit()
        db.close()
        source = self.source()
        self.addCleanup(source.close)
        packet = make_packet(source, "count", Filters(), evidence_limit=0)
        summary = packet['exact_results']['summary']
        self.assertEqual(summary['origin_determined_edges'], 5)
        self.assertEqual(summary['heuristic_only_edges'], 1)

    def test_output_budget_csv_identity_and_unsupported_cli(self):
        packet = self.packet()
        text = result_csv(packet)
        self.assertIn("run_fixture", text)
        self.assertIn("packet_sha256", text)
        path = self.root / "report.json"
        bounded_write(path, "small")
        with self.assertRaisesRegex(ValueError, "2 MiB"):
            bounded_write(path, "x" * (2 * 1024 * 1024 + 1))
        self.assertEqual(path.read_text(), "small")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            status = main(["ask", "why did the court follow this case?", "--db", self.fixture["db"]])
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(out.getvalue())["status"], "unsupported")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            status = main(["ask", "citation count", "--answer-mode", "model"])
        self.assertEqual(status, 2)
        self.assertIsNone(json.loads(out.getvalue())["answer"])

    def test_question_cli_filter_conflicts_fail(self):
        with contextlib.redirect_stderr(io.StringIO()) as out:
            status = main(["ask", "SCC citation count", "--db", self.fixture["db"], "--court", "ONCA"])
        self.assertEqual(status, 1)
        self.assertIn("disagree", out.getvalue())

    def test_foreign_subset_retains_unknown_origin_context_and_csv_denominators(self):
        packet = self.packet(filters=Filters(origin='FOREIGN'))
        self.assertEqual(packet['exact_results']['summary']['origin_coverage'], 1)
        context = packet['exact_results']['origin_coverage_context']
        before = context['summary_before_origin_filter']
        self.assertEqual((before['citation_edges'], before['origin_unknown_edges'], before['heuristic_only_edges']), (6, 2, 1))
        self.assertAlmostEqual(before['foreign_share_all_edges'], 1/6)
        self.assertAlmostEqual(before['foreign_share_determined_edges'], 1/4)
        self.assertIn('来源地筛选前有 6 条边', packet['answer'])
        self.assertTrue(any('returned subset only' in warning for warning in packet['warnings']))
        row = next(csv.DictReader(io.StringIO(result_csv(packet))))
        self.assertEqual(json.loads(row['origin_coverage_context_json']), context)

    def test_origin_context_removes_only_origin_and_preserves_empty_denominators(self):
        filters = Filters(court='SCC', year_from=2000, year_to=2009, min_dd=2,
                          kept_only=True, group_id='XC-G000002', origin='FOREIGN')
        packet = self.packet(filters=filters)
        self.assertEqual(packet['exact_results']['summary']['citation_edges'], 0)
        context = packet['exact_results']['origin_coverage_context']
        self.assertEqual(context['summary_before_origin_filter']['citation_edges'], 1)
        self.assertEqual(context['summary_before_origin_filter']['heuristic_only_edges'], 1)
        self.assertIsNone(context['summary_before_origin_filter']['foreign_share_determined_edges'])
        self.assertEqual(context['filters_before_origin_filter'],
                         {'court':'SCC','year_from':2000,'year_to':2009,'origin':None,'min_dd':2,'kept_only':True,'group_id':'XC-G000002'})

    def test_lookup_keeps_same_name_groups_separate_and_limit_is_only_preview(self):
        db = sqlite3.connect(self.fixture['db'])
        db.execute("UPDATE case_groups SET name='Alpha v Beta' WHERE group_id='XC-G000002'")
        db.commit();db.close()
        packet = make_lookup_packet(self.source(), 'alpha', top=1)
        self.assertEqual(packet['exact_results']['matching_groups'], 2)
        self.assertEqual(len(packet['exact_results']['rows']), 1)
        self.assertTrue(packet['exact_results']['preview_truncated'])
        self.assertEqual(packet['exact_results']['rows'][0]['group_id'], 'XC-G000001')
        self.assertTrue(packet['exact_results']['rows'][0]['member_key_preview'])
        review = packet['exact_results']['rows'][0]['review_arguments']
        self.assertEqual(review[review.index('--run-id')+1], 'run_fixture')
        self.assertEqual(review[review.index('--db')+1], self.fixture['db'])
        self.assertFalse(packet['evidence'])
        digest = packet.pop('packet_sha256')
        self.assertEqual(digest, sha_text(canonical(packet)))

    def test_lookup_treats_wildcards_and_sql_text_literally(self):
        db = sqlite3.connect(self.fixture['db'])
        db.execute("UPDATE case_groups SET name='A%_B literal' WHERE group_id='XC-G000002'")
        db.commit();db.close()
        for query, expected in (('%_', 1), ("' OR 1=1 --", 0), ('not present', 0)):
            packet = make_lookup_packet(self.source(), query)
            self.assertEqual(packet['exact_results']['matching_groups'], expected)
            if expected == 0:
                row = next(csv.DictReader(io.StringIO(result_csv(packet))))
                self.assertEqual(row['matching_groups'], '0')
                self.assertNotIn('group_id', row)
        with self.assertRaisesRegex(ValueError, 'nonempty'):
            make_lookup_packet(self.source(), '  ')

    def test_lookup_unicode_casefold_preserves_accents_chinese_and_literal_symbols(self):
        db = sqlite3.connect(self.fixture['db'])
        db.execute("UPDATE case_groups SET name='R. c. Séguin – 李某' WHERE group_id='XC-G000001'")
        db.execute("UPDATE case_groups SET name='ÉTUDE 100%_C' WHERE group_id='XC-G000002'")
        db.commit();db.close()
        before = Path(self.fixture['db']).stat().st_mtime_ns
        source = self.source()
        for query, expected in (('SÉGUIN',1),('séguin',1),('李某',1),('étude',1),('%_',1),('Seguin',0)):
            with self.subTest(query=query):
                packet = make_lookup_packet(source, query)
                self.assertEqual(packet['exact_results']['matching_groups'], expected)
                self.assertTrue(packet['exact_results']['casefold_unicode_version'])
        self.assertEqual(Path(self.fixture['db']).stat().st_mtime_ns, before)

    def pointer(self, **changes):
        path = self.root / 'data/active_run.json'
        path.parent.mkdir(exist_ok=True)
        value = {'run_id':'run_fixture', 'run_directory':'run_fixture', 'db_path':'fixture.db',
                 'input_fingerprint':'offline-synthetic-fixture-not-a-production-run'}
        value.update(changes)
        path.write_text(json.dumps(value), encoding='utf-8')
        return path

    def test_default_selection_follows_verified_pointer_with_multiple_ready_runs(self):
        self.pointer()
        db = sqlite3.connect(self.fixture['db'])
        db.execute("INSERT INTO runs SELECT 'other',source_directory,input_fingerprint,manifest_json,imported_at,status FROM runs")
        db.commit();db.close()
        args = parser().parse_args(['ask','citation count','--evidence-limit','0'])
        with patch('research.ROOT', self.root):
            source = open_source(args)
        self.addCleanup(source.close)
        self.assertEqual(source.run_id, 'run_fixture')
        self.assertEqual(source.provenance['selection']['mode'], 'active_pointer')
        self.assertTrue(source.provenance['selection']['source_directory_verified'])

    def test_bad_pointer_identity_or_json_never_falls_back(self):
        args = parser().parse_args(['ask','citation count','--evidence-limit','0'])
        for changes in ({'input_fingerprint':'wrong'}, {'run_directory':'missing'}, {'run_id':'absent'}):
            self.pointer(**changes)
            with patch('research.ROOT', self.root), self.assertRaises(ValueError):
                open_source(args)
        path = self.pointer();path.write_text('{broken', encoding='utf-8')
        with patch('research.ROOT', self.root), self.assertRaisesRegex(ValueError, 'no fallback'):
            open_source(args)

    def test_explicit_database_ignores_invalid_default_pointer(self):
        path = self.pointer();path.write_text('{broken', encoding='utf-8')
        args = parser().parse_args(['find','Alpha','--db',self.fixture['db']])
        with patch('research.ROOT', self.root):
            source = open_source(args)
        self.addCleanup(source.close)
        self.assertEqual(source.provenance['selection']['mode'], 'explicit_db')

    def test_absent_pointer_preserves_single_run_default_without_database_copy(self):
        target = self.root/'data/foundation/research.db'
        target.parent.mkdir(parents=True)
        Path(self.fixture['db']).rename(target)
        with patch('research.ROOT', self.root):
            source = open_source(parser().parse_args(['ask','citation count']))
        self.addCleanup(source.close)
        self.assertEqual(source.run_id, 'run_fixture')
        self.assertEqual(source.provenance['selection']['mode'], 'default_foundation_db')
        self.assertEqual(source.provenance['selection']['pointer_status'], 'missing')

    def test_pointer_size_and_same_manifest_wrong_directory_fail_closed(self):
        args = parser().parse_args(['ask','citation count'])
        path = self.pointer();path.write_bytes(b'x'*(64*1024+1))
        with patch('research.ROOT', self.root), patch('research.ResearchSource.sqlite') as opened:
            with self.assertRaisesRegex(ValueError, '64 KiB'):
                open_source(args)
            opened.assert_not_called()
        alternate = self.root/'other-run-location';alternate.mkdir()
        (alternate/'run_manifest.json').write_bytes((Path(self.fixture['run'])/'run_manifest.json').read_bytes())
        self.pointer(run_directory='other-run-location')
        with patch('research.ROOT', self.root), self.assertRaisesRegex(ValueError, 'source directory'):
            open_source(args)

    def test_stream_lookup_has_no_invented_database_review_command(self):
        source = ResearchSource.stream(self.fixture['run'], documents=self.fixture['documents'])
        self.addCleanup(source.close)
        packet = make_lookup_packet(source, 'Alpha')
        self.assertEqual(packet['exact_results']['matching_groups'], 1)
        self.assertIsNone(packet['exact_results']['rows'][0]['review_arguments'])
        self.assertIn('same --stream-run', packet['review_scope']['stream_note'])

    def test_pointer_output_and_conflicting_run_override_are_rejected(self):
        path = self.pointer();before = path.read_bytes()
        args = parser().parse_args(['ask','citation count','--run-id','other'])
        with patch('research.ROOT', self.root), self.assertRaisesRegex(ValueError, 'disagrees'):
            open_source(args)
        with patch('research.ROOT', self.root), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            status = main(['find','Alpha','--output',str(path)])
        self.assertEqual(status, 1)
        self.assertIn('active run pointer', err.getvalue())
        self.assertEqual(path.read_bytes(), before)

    def test_find_cli_round_trip_provides_group_for_evidence_query(self):
        self.pointer()
        with patch('research.ROOT', self.root), contextlib.redirect_stdout(io.StringIO()) as out:
            status = main(['find','Alpha','--top','1'])
        self.assertEqual(status, 0)
        found = json.loads(out.getvalue());review = found['exact_results']['rows'][0]['review_arguments']
        # A changed/invalid current pointer cannot silently reinterpret an old ID.
        self.pointer(run_id='new-unavailable-run')
        with patch('research.ROOT', self.root), contextlib.redirect_stdout(io.StringIO()) as out:
            status = main(review)
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(out.getvalue())['exact_results']['summary']['citation_edges'], 3)


class ParquetEvidenceTests(unittest.TestCase):
    def setUp(self):
        try:
            import pyarrow
        except ImportError:
            self.skipTest("optional pyarrow not installed")
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        self.fixture = create_fixture(self.temp.name, with_parquet=True)

    def test_original_text_hash_and_half_open_unicode_span(self):
        source = ResearchSource.sqlite(self.fixture["db"])
        self.addCleanup(source.close)
        packet = make_packet(source, "case_citations", Filters(group_id="XC-G000001", court="SCC", year_from=2000), evidence_limit=1, with_text=True)
        item = packet["evidence"][0]
        self.assertEqual(item["status"], "original_text_verified")
        self.assertTrue(item["corpus_verification"]["matches_run"])
        self.assertEqual(item["source_text_sha256"], sha_text(item["quote"]))
        self.assertIn("判决😀", item["quote"])

    def test_corpus_hash_mismatch_refuses_original_window(self):
        corpus_path = Path(self.fixture["corpus"]) / "SCC.parquet"
        with corpus_path.open("ab") as f:
            f.write(b"changed")
        source = ResearchSource.sqlite(self.fixture["db"])
        self.addCleanup(source.close)
        packet = make_packet(source, "case_citations", Filters(group_id="XC-G000001", court="SCC", year_from=2000), evidence_limit=1, with_text=True)
        item = packet["evidence"][0]
        self.assertEqual(item["status"], "corpus_hash_mismatch_or_unrecorded")
        self.assertNotIn("source_text_sha256", item)

    def original_span_fixture(self, original, end_delta=0):
        import pyarrow as pa
        import pyarrow.parquet as pq
        corpus = Path(self.fixture['corpus']) / 'SCC.parquet'
        records = pq.read_table(corpus).to_pylist()
        raw = '[1990] SCC 10'
        records[0]['unofficial_text_en'] = records[0]['unofficial_text_en'].replace(raw, original)
        text = records[0]['unofficial_text_en']
        pq.write_table(pa.Table.from_pylist(records), corpus, row_group_size=2)
        path = Path(self.fixture['run']) / 'merge_out/SCC/mentions_candidates.csv.gz'
        with gzip.open(path, 'rt', encoding='utf-8', newline='') as handle:
            reader = csv.DictReader(handle)
            fields, mentions = reader.fieldnames, list(reader)
        for mention in mentions:
            mention['match_start_offset'] = str(text.index(original))
            mention['match_end_offset'] = str(text.index(original)+len(original)+end_delta)
        write_csv(path, fields, mentions)
        manifest_path = Path(self.fixture['run']) / 'run_manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['input_identity']['files']['corpus/SCC.parquet'] = hashlib.sha256(corpus.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        source = ResearchSource.stream(self.fixture['run'])
        self.addCleanup(source.close)
        return source, text

    def test_cross_line_and_nbsp_match_preserves_original_window_span_hash(self):
        original = '[1990]\r\nSCC\u00a010'
        source, text = self.original_span_fixture(original)
        item = make_packet(source, 'case_citations', Filters(group_id='XC-G000001', court='SCC', year_from=2000),
                           evidence_limit=1, with_text=True)['evidence'][0]
        self.assertEqual(item['status'], 'original_text_verified')
        self.assertEqual(item['candidate']['raw_string'], '[1990] SCC 10')
        self.assertEqual(text[item['span']['start']:item['span']['end']], original)
        self.assertEqual(item['span']['end']-item['span']['start'], len(original))
        self.assertIn(original, item['quote'])
        self.assertEqual(item['source_text_sha256'], sha_text(text))
        self.assertEqual(item['quote_sha256'], sha_text(text[item['quote_span']['start']:item['quote_span']['end']]))

    def test_non_whitespace_change_cannot_be_verified(self):
        source, _ = self.original_span_fixture('[1990]\nSCC\u00a011')
        item = make_packet(source, 'case_citations', Filters(group_id='XC-G000001', court='SCC', year_from=2000),
                           evidence_limit=1, with_text=True)['evidence'][0]
        self.assertEqual(item['status'], 'source_or_span_text_mismatch')
        self.assertNotIn('source_text_sha256', item)
        self.assertNotIn('quote_span', item)
        self.assertIsNone(item['field_selection']['text_field'])

    def test_out_of_bounds_original_span_cannot_be_verified(self):
        source, _ = self.original_span_fixture('[1990] SCC 10', end_delta=1000)
        item = make_packet(source, 'case_citations', Filters(group_id='XC-G000001', court='SCC', year_from=2000),
                           evidence_limit=1, with_text=True)['evidence'][0]
        self.assertEqual(item['status'], 'source_or_span_text_mismatch')
        self.assertNotIn('source_text_sha256', item)
        self.assertNotIn('quote_span', item)

    def language_fixture(self, policy, french_only=False):
        import csv
        import pyarrow as pa
        import pyarrow.parquet as pq
        corpus = Path(self.fixture['corpus']) / 'SCC.parquet'
        data = pq.read_table(corpus).to_pylist()
        data[0].update(citation_fr='2000 CSC 1', name_fr='Source français',
                       document_date_fr='2001-03-01', unofficial_text_fr=data[0]['unofficial_text_en'])
        if french_only:
            for key in ('citation_en', 'name_en', 'document_date_en', 'unofficial_text_en'):
                data[0][key] = None
            for relative in ('edges/citation_edges.csv.gz', 'merge_out/SCC/mentions_candidates.csv.gz'):
                path = Path(self.fixture['run']) / relative
                with gzip.open(path, 'rt', encoding='utf-8', newline='') as handle:
                    reader = csv.DictReader(handle)
                    fields, records = reader.fieldnames, list(reader)
                for record in records:
                    for field in ('source_decision', 'source_decision_citation'):
                        if record.get(field) == 'SCC_2000scc1':
                            record[field] = 'SCC_2000csc1'
                write_csv(path, fields, records)
        pq.write_table(pa.Table.from_pylist(data), corpus, row_group_size=2)
        manifest_path = Path(self.fixture['run']) / 'run_manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if policy is None:
            manifest['params'].pop('text_policy', None)
        else:
            manifest['params']['text_policy'] = policy
        manifest['input_identity']['files']['corpus/SCC.parquet'] = hashlib.sha256(corpus.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        source = ResearchSource.stream(self.fixture['run'])
        self.addCleanup(source.close)
        return source

    def test_french_fallback_stream_metadata_and_original_field_hashes(self):
        source = self.language_fixture('en_then_fr', french_only=True)
        doc = source.db.execute("SELECT * FROM documents WHERE source_id='SCC_2000csc1'").fetchone()
        self.assertEqual((doc['citation'], doc['name'], doc['decision_date']),
                         ('2000 CSC 1', 'Source français', '2001-03-01'))
        packet = make_packet(source, 'case_citations', Filters(group_id='XC-G000001', court='SCC', year_from=2001),
                             evidence_limit=1, with_text=True)
        item = packet['evidence'][0]
        self.assertEqual(item['status'], 'original_text_verified')
        self.assertEqual(item['span']['text_field'], 'unofficial_text_fr')
        self.assertEqual(item['span']['language'], 'fr')
        self.assertEqual(item['field_selection']['date_field'], 'document_date_fr')
        self.assertEqual(item['field_selection']['citation_field'], 'citation_fr')
        self.assertEqual(item['field_selection']['name_field'], 'name_fr')
        self.assertEqual(item['field_selection']['field_values_sha256']['name'], sha_text('Source français'))
        self.assertEqual(item['field_selection']['verification'], 'original_corpus_verified')
        self.assertEqual(packet['parameters']['text_policy'], 'en_then_fr')

    def test_legacy_manifest_does_not_reinterpret_french_only_source(self):
        source = self.language_fixture(None, french_only=True)
        doc = source.db.execute('SELECT * FROM documents WHERE court=? AND corpus_row=0', ('SCC',)).fetchone()
        self.assertEqual((doc['source_id'], doc['citation'], doc['decision_date']), ('SCC_', '', ''))
        packet = make_packet(source, 'count', evidence_limit=6, with_text=True)
        french = [item for item in packet['evidence'] if item['source_decision'] == 'SCC_2000csc1']
        self.assertTrue(french)
        self.assertTrue(all(item['status'] == 'document_metadata_missing_or_conflicting' for item in french))
        self.assertEqual(packet['parameters']['text_policy'], 'english_only')

    def test_bilingual_prefers_english_and_refuses_conflicting_index_field_claim(self):
        source = self.language_fixture('en_then_fr')
        packet = make_packet(source, 'case_citations', Filters(group_id='XC-G000001', court='SCC', year_from=2000),
                             evidence_limit=1, with_text=True)
        item = packet['evidence'][0]
        self.assertEqual(item['field_selection']['text_field'], 'unofficial_text_en')
        self.assertEqual(item['field_selection']['date_field'], 'document_date_en')
        self.assertEqual(packet['exact_results']['summary']['citation_edges'], 1)
        self.assertEqual(make_packet(source, 'count', evidence_limit=0)['exact_results']['summary']['citation_edges'], 6)
        item['indexed_evidence_locator'] = {'corpus': {'text_field': 'unofficial_text_fr'}}
        item['status'] = 'candidate_span_located_corpus_not_read'
        item.pop('source_text_sha256', None)
        enrich_corpus(source, [item])
        self.assertEqual(item['status'], 'indexed_field_selection_mismatch')
        self.assertNotIn('source_text_sha256', item)


if __name__ == "__main__":
    unittest.main()
