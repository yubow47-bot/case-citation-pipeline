"""Provenance integrity for history and policy-backed reporter merges."""
import csv
import gzip
import hashlib
import json
import os
import sys
import tempfile
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import decide  # noqa: E402
from identity_constraints import ConstraintLedger  # noqa: E402
from identity_evidence import EvidenceSnapshot  # noqa: E402
import identity_pairs as pair_module  # noqa: E402


HISTORY_FIELDS = ("source_decision_citation", "corpus_row_index", "instance", "side",
                  "merge_key", "candidate_id", "connector")


def write_history(path, instance="inst-1", connector="aff'd"):
    rows = [
        ("ONCA_X", "1", instance, "before", "1991|3|or|3d|193", "cand-before-1", connector),
        ("ONCA_X", "1", instance, "before", "|64|ccc|3d|449", "cand-before-2", connector),
        ("ONCA_X", "1", instance, "after", "1992|2|scr||168", "cand-after-1", connector),
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HISTORY_FIELDS)
        writer.writerows(rows)
    return rows


def row(key, court="ONCA", name="R. v. Bennett", year="1991"):
    return {"court": court, "merge_key": key, "case_name_modal": name, "year_printed": year,
            "citation_kind": "reporter", "jurisdiction": "CA", "canonical_string": key,
            "key_occurrence_count": 1, "occurrence_count": 1, "self_citation_of": "",
            "self_case_name": "", "observed_deciding_court": "",
            "court_designation_conflict": ""}


class HistoryInputTests(unittest.TestCase):
    def test_requires_inputs_and_explicit_legacy_compatibility(self):
        with self.assertRaises(FileNotFoundError):
            decide.load_history_instances([])
        self.assertEqual(decide.load_history_instances([], mode="legacy-none"), {})
        with self.assertRaises(ValueError):
            decide.load_history_instances(["unexpected.csv"], mode="legacy-none")
        with self.assertRaises(FileNotFoundError):
            decide.load_history_instances(["missing-history.csv"])

    def test_history_retains_source_candidate_connector_and_hash_locator(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "history_pairs.csv")
            write_history(path)
            loaded = decide.load_history_instances([path])
            instance = loaded["inst-1"]
            self.assertEqual(instance["before"], {"1991|3|or|3d|193", "|64|ccc|3d|449"})
            self.assertEqual(instance["after"], {"1992|2|scr||168"})
            self.assertEqual(len(instance["records"]), 3)
            record = instance["records"][0]
            self.assertEqual(record["source_decision_citation"], "ONCA_X")
            self.assertEqual(record["corpus_row_index"], "1")
            self.assertEqual(record["candidate_id"], "cand-before-1")
            self.assertEqual(record["connector"], "aff'd")
            self.assertEqual(record["connector_sha256"],
                             hashlib.sha256(b"aff'd").hexdigest())
            self.assertEqual(record["source_locator"]["record"], 2)
            self.assertEqual(record["source_locator"]["hash_scope"], "logical_csv_bytes")
            self.assertEqual(record["source_locator"]["artifact"], path.replace("\\", "/"))
            with open(path, "rb") as source:
                source_bytes = source.read()
            self.assertEqual(record["source_locator"]["sha256"],
                             hashlib.sha256(source_bytes).hexdigest())

    def test_logical_csv_resolves_to_retained_gzip_and_keeps_manifest_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            logical_path = os.path.join(tmp, "history_pairs.csv")
            compressed_path = logical_path + ".gz"
            write_history(logical_path)
            with open(logical_path, "rb") as source:
                content = source.read()
            with gzip.open(compressed_path, "wb") as target:
                target.write(content)
            os.unlink(logical_path)

            loaded = decide.load_history_instances([logical_path])
            locator = loaded["inst-1"]["records"][0]["source_locator"]
            self.assertEqual(locator["artifact"], logical_path.replace("\\", "/"))
            self.assertEqual(locator["resolved_artifact"], compressed_path.replace("\\", "/"))
            with open(compressed_path, "rb") as source:
                compressed_bytes = source.read()
            self.assertEqual(locator["hash_scope"], "logical_csv_bytes")
            self.assertEqual(locator["sha256"], hashlib.sha256(content).hexdigest())
            # Snapshot resolves the logical .csv reference through its retained gzip.
            EvidenceSnapshot([row("1991|3|or|3d|193")], {}, "XC", history=loaded)

    def test_loaded_plain_facts_revalidate_after_plain_artifact_is_compacted_to_gzip(self):
        with tempfile.TemporaryDirectory() as tmp:
            logical_path = os.path.join(tmp, "history_pairs.csv")
            compressed_path = logical_path + ".gz"
            write_history(logical_path)
            loaded = decide.load_history_instances([logical_path])
            locator = loaded["inst-1"]["records"][0]["source_locator"]
            self.assertEqual(locator["hash_scope"], "logical_csv_bytes")
            original_ids = sorted(fact["evidence_id"] for fact in
                                  EvidenceSnapshot([row("1991|3|or|3d|193")], {},
                                                   "XC", history=loaded).records
                                  if fact["fact_kind"] == "appeal_history_instance")
            with open(logical_path, "rb") as source:
                logical_bytes = source.read()
            with gzip.open(compressed_path, "wb") as target:
                target.write(logical_bytes)
            os.unlink(logical_path)

            compacted_snapshot = EvidenceSnapshot(
                [row("1991|3|or|3d|193")], {}, "XC", history=loaded)
            compacted_ids = sorted(fact["evidence_id"] for fact in compacted_snapshot.records
                                   if fact["fact_kind"] == "appeal_history_instance")
            self.assertEqual(compacted_ids, original_ids)
            self.assertEqual(locator["sha256"], hashlib.sha256(logical_bytes).hexdigest())

    def test_missing_or_malformed_expected_history_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "history_pairs.csv")
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write("instance,side,merge_key\ninst-1,before,a\n")
            with self.assertRaises(ValueError):
                decide.load_history_instances([path])
            write_history(path)
            loaded = decide.load_history_instances([path])
            loaded["inst-1"]["records"][0]["instance"] = "another-instance"
            rows = [row("1991|3|or|3d|193")]
            with self.assertRaises(ValueError):
                EvidenceSnapshot(rows, {}, "XC", history=loaded)
            loaded = decide.load_history_instances([path])
            loaded["inst-1"]["records"][0]["candidate_id"] = "candidate-not-in-source-row"
            with self.assertRaisesRegex(ValueError, "different source row"):
                EvidenceSnapshot(rows, {}, "XC", history=loaded)

    def test_snapshot_detects_source_artifact_tampering_after_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "history_pairs.csv")
            write_history(path)
            loaded = decide.load_history_instances([path])
            write_history(path, connector="appeal allowed")
            with self.assertRaisesRegex(ValueError, "changed after it was loaded"):
                EvidenceSnapshot([row("1991|3|or|3d|193")], {}, "XC", history=loaded)

    def test_constraint_binds_split_to_history_facts_and_source_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "history_pairs.csv")
            write_history(path)
            history = decide.load_history_instances([path])
            rows = [row("1991|3|or|3d|193"),
                    row("|64|ccc|3d|449"),
                    row("1992|2|scr||168", year="1992"),
                    row("|74|ccc|3d|384", year="1992")]
            did = {decide.row_key(item): {"S1", "S2", "S3"} for item in rows}
            snapshot = EvidenceSnapshot(rows, did, "XC", history=history)
            trace = ConstraintLedger(snapshot)
            decide.adjudicate(rows, did, {}, {}, "XC", Counter(), False,
                              trace=trace, history=history)
            evidence_by_id = {fact["evidence_id"]: fact for fact in trace.records["evidence"]}
            constraints = [c for c in trace.records["constraints"]
                           if c["rule"] == "appeal_history_connector"]
            self.assertTrue(constraints)
            constraint = constraints[0]
            detail = json.loads(constraint["source_detail_json"])
            refs = set(json.loads(constraint["evidence_ids_json"]))
            bindings = detail["history_instances"]
            self.assertEqual({b["instance"] for b in bindings}, {"inst-1"})
            self.assertTrue(bindings[0]["left_component_keys"])
            self.assertTrue(bindings[0]["right_component_keys"])
            self.assertTrue((set(bindings[0]["left_component_keys"]) |
                             set(bindings[0]["right_component_keys"])) <=
                            (set(bindings[0]["before_merge_keys"]) |
                             set(bindings[0]["after_merge_keys"])))
            history_refs = set(bindings[0]["evidence_ids"])
            self.assertTrue(history_refs)
            self.assertTrue(history_refs <= refs)
            facts = [evidence_by_id[eid] for eid in history_refs]
            self.assertTrue(all(f["fact_kind"] == "appeal_history_instance" for f in facts))
            values = [json.loads(f["value_json"]) for f in facts]
            self.assertEqual({v["candidate_id"] for v in values},
                             {"cand-before-1", "cand-before-2", "cand-after-1"})
            self.assertTrue(all(v["connector"] == "aff'd" for v in values))
            self.assertTrue(all(v["source_decision_citation"] == "ONCA_X" for v in values))
            locators = [json.loads(f["sources_json"]) for f in facts]
            self.assertTrue(all(l["record"] >= 2 and len(l["sha256"]) == 64 for l in locators))


class BilingualReporterTraceTests(unittest.TestCase):
    def test_alias_constraint_cites_exact_mapping_policy_row(self):
        rows = [row("1990|1|scr||123", court="SCC", name="X v. Y", year="1990"),
                row("1990|1|rcs||123", court="ONCA", name="", year="1990")]
        snapshot = EvidenceSnapshot(rows, {}, "XC")
        trace = ConstraintLedger(snapshot)
        decide.adjudicate(rows, {}, {}, {}, "XC", Counter(), False, trace=trace)
        constraint = next(c for c in trace.records["constraints"]
                          if c["rule"] == "exact_full_reporter_key")
        mapping_id = snapshot.bilingual_reporter_fact("rcs", "scr")
        refs = set(json.loads(constraint["evidence_ids_json"]))
        detail = json.loads(constraint["source_detail_json"])
        self.assertIn(mapping_id, refs)
        mappings = detail["reporter_normalizations"]
        self.assertTrue(any(m["from"] == "rcs" and m["to"] == "scr"
                            and m["policy_evidence_id"] == mapping_id for m in mappings))
        fact = next(f for f in trace.records["evidence"] if f["evidence_id"] == mapping_id)
        self.assertEqual(fact["fact_kind"], "policy_record")
        self.assertIn("bilingual_reporter_abbreviations.csv", json.loads(fact["sources_json"])["artifact"])
        policy = json.loads(fact["value_json"])
        self.assertEqual(policy["normalized_fr"], "rcs")
        self.assertEqual(policy["normalized_en"], "scr")

    def test_alias_merge_fails_if_exact_mapping_evidence_is_missing(self):
        rows = [row("1990|1|scr||123", court="SCC", name="X v. Y", year="1990"),
                row("1990|1|rcs||123", court="ONCA", name="", year="1990")]
        snapshot = EvidenceSnapshot(rows, {}, "XC")
        snapshot.bilingual_reporter_facts.pop("rcs")
        trace = ConstraintLedger(snapshot)
        with self.assertRaisesRegex(ValueError, "lacks the exact verified policy fact"):
            decide.adjudicate(rows, {}, {}, {}, "XC", Counter(), False, trace=trace)


class VerifiedPairSeparationTests(unittest.TestCase):
    def test_snapshot_binds_right_source_to_hashed_table_proof(self):
        table_row = dict.fromkeys(pair_module.PAIR_FIELDS, "fixture")
        right_proof = {
            "source_court": "SCC", "source_decision": "SCC_2005scc43",
            "source_corpus": "corpus/SCC.parquet", "corpus_sha256": "a" * 64,
            "corpus_row": "4", "text_field": "unofficial_text_en",
            "text_sha256": "b" * 64, "span_start": "0", "span_end": "90",
            "span_sha256": "c" * 64, "distinction_quote": "different reasons",
        }
        table_row.update(
            left_merge_key="2009||canlii||76382",
            right_merge_key="2005||scc||43",
            relation_type="verified_distinct_decisions",
            source_court="ONCA", source_decision="ONCA_2025onca767",
            source_corpus="corpus/ONCA.parquet", corpus_row="12",
            text_field="unofficial_text_en", span_start="0", span_end="100",
            span_sha256="d" * 64, source_locator="audit/findings/fixture.json#one",
            right_proof_json=json.dumps(right_proof, sort_keys=True),
        )
        table_row["evidence_id"] = pair_module.evidence_id(table_row)
        table_evidence_id = table_row["evidence_id"]
        source_detail = {
            "artifact": "decisions/identity_pair_separations.csv",
            "table_evidence_id": table_evidence_id,
            "source_corpus": table_row["source_corpus"],
            "corpus_row": table_row["corpus_row"],
            "source_decision": table_row["source_decision"],
            "text_field": table_row["text_field"],
            "span_start": table_row["span_start"],
            "span_end": table_row["span_end"],
            "span_sha256": table_row["span_sha256"],
            "right_source": right_proof,
            "source_locator": table_row["source_locator"],
        }
        separation = {
            **table_row, "table_evidence_id": table_evidence_id,
            "source_detail": source_detail,
        }
        snapshot = EvidenceSnapshot(
            [row(table_row["left_merge_key"])], {}, "XC",
            pair_separations=[separation])
        fact = next(record for record in snapshot.records
                    if record["fact_kind"] == "verified_pair_separation")
        self.assertEqual(json.loads(fact["sources_json"])["right_source"], right_proof)

        tampered = {
            **separation,
            "source_detail": {
                **source_detail,
                "right_source": {**right_proof, "source_decision": "SCC_2005scc44"},
            },
        }
        with self.assertRaisesRegex(ValueError, "source detail is misbound"):
            EvidenceSnapshot([row(table_row["left_merge_key"])], {}, "XC",
                             pair_separations=[tampered])


    def keyed_row(self, key, court, kind, name="R. v. Villaroman"):
        result = row(key, court=court, name=name, year="2016")
        result["citation_kind"] = kind
        return result

    def test_exact_reporter_union_uses_current_verified_typo_root(self):
        from identity_solve import merge_same_key_clusters

        reporter_key = "2016|1|scr||1001"
        correct_key = "2016||scc||33"
        typo_key = "2016||scc||333"
        onca_report = self.keyed_row(reporter_key, "ONCA", "reporter", name="")
        scc_report = self.keyed_row(reporter_key, "SCC", "reporter")
        correct = self.keyed_row(correct_key, "SCC", "neutral")
        typo = self.keyed_row(typo_key, "ONCA", "neutral")
        # This field is inherited input metadata; root assignment must be recomputed.
        typo["identity_basis"] = "untrusted_stale_basis"
        members = [onca_report, scc_report, correct, typo]
        did_idx = {
            decide.row_key(correct): {"SCC_2016scc33", "ONCA_2016onca1"},
            decide.row_key(typo): {"ONCA_2016onca2"},
        }
        snapshot = EvidenceSnapshot(members, did_idx, "XC")
        trace = ConstraintLedger(snapshot)

        result = merge_same_key_clusters(
            [([onca_report], "", ""), ([scc_report, correct, typo], "", "")],
            did_idx, Counter(), registry={}, trace=trace)

        self.assertEqual(len(result), 1)
        exact = next(edge for edge in trace.records["constraints"]
                     if edge["phase"] == "same_key_union"
                     and edge["rule"] == "exact_full_reporter_key"
                     and edge["relation"] == "must_link")
        normalizations = json.loads(exact["source_detail_json"])["neutral_root_normalizations"]
        by_key = {item["merge_key"]: item["root_merge_key"] for item in normalizations}
        self.assertEqual(by_key[typo_key], correct_key)
        self.assertTrue(any(edge["phase"] == "variant" and edge["rule"] == "typo_number"
                            and edge["relation"] == "must_link"
                            for edge in trace.records["constraints"]))
        self.assertFalse(any(edge["phase"] == "same_key_union"
                             and edge["rule"] == "different_neutral_numbers"
                             for edge in trace.records["constraints"]))

    def test_forged_typo_basis_does_not_bypass_distinct_neutral_guard(self):
        from identity_solve import merge_same_key_clusters

        reporter_key = "2016|1|scr||1001"
        left_report = self.keyed_row(reporter_key, "ONCA", "reporter", name="")
        right_report = self.keyed_row(reporter_key, "SCC", "reporter")
        left_neutral = self.keyed_row("2016||scc||33", "SCC", "neutral")
        right_neutral = self.keyed_row("2016||scc||34", "ONCA", "neutral")
        right_neutral["identity_basis"] = "anchor_variant_typo_number"
        members = [left_report, right_report, left_neutral, right_neutral]
        did_idx = {
            decide.row_key(left_neutral): {"SCC_2016scc33"},
            decide.row_key(right_neutral): {"ONCA_2016onca34"},
        }
        trace = ConstraintLedger(EvidenceSnapshot(members, did_idx, "XC"))

        result = merge_same_key_clusters(
            [([left_report, left_neutral], "", ""),
             ([right_report, right_neutral], "", "")],
            did_idx, Counter(), registry={}, trace=trace)

        self.assertEqual(len(result), 2)
        self.assertTrue(any(edge["phase"] == "same_key_union"
                            and edge["rule"] == "different_neutral_numbers"
                            and edge["relation"] == "cannot_link"
                            for edge in trace.records["constraints"]))

    def test_registered_document_guard_uses_original_neutral_key(self):
        from identity_constraints import document_union_constraint
        from identity_courts import CourtEvidence

        reporter = self.keyed_row("2016|1|scr||1001", "SCC", "reporter")
        neutral = self.keyed_row("2016||scc||33", "SCC", "neutral")
        blocker = document_union_constraint(
            [reporter, neutral], {reporter["merge_key"]: "DOC-A"},
            {neutral["merge_key"]: ("DOC-B", "SCC")}, CourtEvidence(),
            {"neutral_roots": {neutral["merge_key"]: "different-root"}})
        self.assertIsNotNone(blocker)
        self.assertEqual(blocker.rule, "registered_other_document")

    def native_mccormack(self):
        table = os.path.join(decide.ROOT, "decisions", "identity_pair_separations.csv")
        with open(table, encoding="utf-8-sig", newline="") as source:
            record = next(r for r in csv.DictReader(source)
                          if r["source_decision"] == "ONCA_2025onca767")
        corpus = os.path.join(decide.ROOT, record["source_corpus"])
        if not os.path.isfile(corpus):
            self.skipTest("native source corpus is not present in this checkout")
        facts = decide.load_pair_separations(
            keys={record["left_merge_key"], record["right_merge_key"]})
        return next(item for item in facts
                    if item["source_decision"] == "ONCA_2025onca767")

    def test_native_mccormack_pair_fact_splits_and_is_not_mislabeled_as_history(self):
        separation = self.native_mccormack()
        separations = [separation]
        left, right = separation["left_merge_key"], separation["right_merge_key"]
        rows = [row(left, court="ONCA", name="R. v. McCormack", year="2009"),
                row(right, court="ONCA", name="R. v. McCormack", year="2009")]
        did_idx = {decide.row_key(item): {"ONCA_2025onca767"} for item in rows}
        snapshot = EvidenceSnapshot(rows, did_idx, "ONCA", pair_separations=separations)
        trace = ConstraintLedger(snapshot)
        clusters = [(rows, "same_name_year", "")]
        from identity_solve import split_by_history
        parts = split_by_history(
            clusters, {}, did_idx, Counter(), trace,
            pair_cannot_links=snapshot.pair_cannot_links)
        self.assertEqual(len(parts), 2)
        pair_constraints = [c for c in trace.records["constraints"]
                            if c["rule"] == "verified_pair_separation"]
        self.assertTrue(pair_constraints)
        self.assertFalse(any(c["rule"] == "appeal_history_connector"
                             for c in trace.records["constraints"]))
        pair_fact = next(fact["evidence_id"] for fact in snapshot.records
                         if fact["fact_kind"] == "verified_pair_separation")
        constraint = pair_constraints[0]
        self.assertIn(pair_fact, json.loads(constraint["evidence_ids_json"]))
        detail = json.loads(constraint["source_detail_json"])
        self.assertEqual(detail["relation_type"], "verified_distinct_decisions")
        self.assertEqual({left, right},
                         {detail["left_merge_key"], detail["right_merge_key"]})
        facts = {fact["evidence_id"]: fact for fact in trace.records["evidence"]}
        native_fact = facts[pair_fact]
        self.assertEqual(native_fact["fact_kind"], "verified_pair_separation")
        fact_value = json.loads(native_fact["value_json"])
        self.assertEqual(fact_value["table_evidence_id"], separation["table_evidence_id"])
        self.assertEqual(json.loads(native_fact["sources_json"]), separation["source_detail"])

    def test_native_pair_fact_rejects_tampering_and_wrong_source_binding(self):
        separation = self.native_mccormack()
        left, right = separation["left_merge_key"], separation["right_merge_key"]
        rows = [row(left), row(right)]
        tampered_key = dict(separation, left_merge_key="2009||canlii||99999")
        with self.assertRaisesRegex(ValueError, "changed after native source validation"):
            EvidenceSnapshot(rows, {}, "XC", pair_separations=[tampered_key])
        wrong_source = dict(separation, source_detail=dict(separation["source_detail"],
                                                         source_decision="ONCA_2009onca1"))
        with self.assertRaisesRegex(ValueError, "source detail is misbound"):
            EvidenceSnapshot(rows, {}, "XC", pair_separations=[wrong_source])


if __name__ == "__main__":
    unittest.main()
