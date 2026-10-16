"""Real SQLite/corpus/FTS; explicitly synthetic vectors and model metadata."""
from hashlib import sha256
from contextlib import closing
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from bublik_developer.errors import DeveloperError, ErrorCode
from bublik_developer.model_session import ModelSession
from bublik_developer.rag.chunking import chunk_document
from bublik_developer.rag.corpus import ProjectCorpus, SourceSpec
from bublik_developer.rag.embeddings import LocalEmbeddings, normalize
from bublik_developer.rag.index import ProjectIndex, build_index
from bublik_developer.rag.retrieval import (endpoint_heading_matcher, explicit_endpoints,
    fts_query, fuse, has_body, query_terms, search)
from bublik_developer.rag.state import ProjectState
from bublik_developer.workspace import ProjectWorkspace

APP = Path(__file__).resolve().parents[1]


class SyntheticVectors:
    """Test-only controlled unit vectors; never evidence of real bge quality."""
    def __init__(self):
        self.digest = "0" * 64
        self.events = []

    def identity(self):
        return {"name": "bge-m3", "digest": self.digest, "dimension": 1024}

    def embed(self, texts, *, final=True):
        result = []
        for text in texts:
            vector = [0.] * 1024
            vector[0 if "memory" in text.casefold() else 1] = 1.
            result.append(vector)
        return result


class RagFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # macOS temporary paths may pass through /var -> /private/var.
        self.parent = Path(self.temp.name).resolve(strict=True)
        self.root = self.parent / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "README.md").write_text("\n\n# Memory\nMemory history uses FTS5 and SQLite.\n\n# API\nThe API prefix is /api/v1.\n", encoding="utf-8")
        self.workspace = ProjectWorkspace.open(self.root, "fixture")
        self.corpus = ProjectCorpus(self.workspace)
        self.state = ProjectState(self.workspace, self.parent / "state")

    def build(self, dense=False):
        return build_index(self.corpus, self.state, provider=SyntheticVectors() if dense else None)


class CorpusTests(RagFixture):
    def test_exact_initial_blank_lines_crlf_and_raw_digest(self):
        raw = b"\r\n\r\n# Title\r\nA source sentence.\r\n"
        (self.root / "README.md").write_bytes(raw)
        doc = self.corpus.collect().documents[0]
        chunk = chunk_document(doc)[0]
        self.assertEqual(chunk.start_line, 3)
        self.assertEqual(chunk.end_line, 4)
        self.assertEqual(doc.raw_digest, sha256(raw).hexdigest())
        self.assertEqual(doc.text[chunk.start:chunk.end], chunk.text)

    def test_markdown_fence_heading_is_not_a_section(self):
        (self.root / "README.md").write_text("# Actual\n```python\n# Not a heading\nvalue = 1\n```\n# Next\ntext\n")
        chunks = chunk_document(self.corpus.collect().documents[0])
        self.assertEqual([c.section for c in chunks], ["Actual", "Next"])

    def test_lone_cr_line_endings_preserve_source_line_numbers(self):
        (self.root / "README.md").write_bytes(b"\r\r# Title\rExact text.\r")
        doc = self.corpus.collect().documents[0]
        chunk = chunk_document(doc)[0]
        self.assertEqual((chunk.start_line, chunk.end_line), (3, 4))
        self.assertIn("# Title\nExact text.", chunk.text)

    def test_repeated_text_keeps_distinct_spans_and_ids(self):
        (self.root / "README.md").write_text("# First\nsame words\n# Second\nsame words\n")
        chunks = chunk_document(self.corpus.collect().documents[0])
        self.assertNotEqual(chunks[0].chunk_id, chunks[1].chunk_id)
        self.assertNotEqual(chunks[0].start_line, chunks[1].start_line)

    def test_default_addition_and_deletion_change_fingerprint(self):
        old = self.corpus.collect().revision
        (self.root / "README.ru.md").write_text("# Память\nИстория хранится в SQLite.\n")
        new = self.corpus.collect().revision
        self.assertNotEqual(old, new)
        (self.root / "README.ru.md").unlink()
        self.assertEqual(self.corpus.collect().revision, old)

    def test_unselected_code_and_reports_do_not_change_corpus(self):
        before = self.corpus.collect().revision
        (self.root / "worker.py").write_text("something\n")
        (self.root / "reports").mkdir()
        (self.root / "reports/README.md").write_text("evaluation rubric\n")
        self.assertEqual(before, self.corpus.collect().revision)

    def test_explicit_json_yaml_schema_only_and_secret_paths_denied(self):
        (self.root / "schema.json").write_text('{"type":"object"}')
        (self.root / "schema.yaml").write_text("type: object\n")
        selected = ProjectCorpus(self.workspace, [SourceSpec("schema.json", "schema"), SourceSpec("schema.yaml", "schema")])
        self.assertEqual(len(selected.collect().documents), 2)
        for source in (".env", "history.sqlite3", "reports/fixtures.md", "../outside.md"):
            with self.assertRaises(DeveloperError):
                SourceSpec(source)
        with self.assertRaises(DeveloperError):
            SourceSpec("schema.json", "markdown")

    def test_symlink_and_secret_like_document_are_denied(self):
        outside = self.parent / "outside.md"
        outside.write_text("outside")
        (self.root / "README.md").unlink()
        (self.root / "README.md").symlink_to(outside)
        with self.assertRaises(DeveloperError):
            self.corpus.collect()
        (self.root / "README.md").unlink()
        (self.root / "README.md").write_text('api_key = "secret_value_long_enough"')
        with self.assertRaises(DeveloperError):
            self.corpus.collect()


class IndexTests(RagFixture):
    def test_real_fts_verify_and_exact_evidence(self):
        self.build()
        with ProjectIndex.current(self.state, self.corpus) as index:
            self.assertEqual(index.verify()["status"], "verified")
            result = search(index, "Memory SQLite")
            self.assertEqual(result["status"], "retrieved")
            self.assertEqual(result["metrics"]["answer_model_calls"], 0)
            for hit in result["sources"]:
                doc = self.corpus.collect().documents[0]
                self.assertEqual(doc.text[hit["start"]:hit["end"]], hit["quote"])
                self.assertEqual(hit["raw_digest"], doc.raw_digest)
            with self.assertRaises(sqlite3.OperationalError):
                index.db.execute("DELETE FROM documents")

    def test_modified_doc_blocks_current_index_and_keeps_old_version(self):
        self.build()
        old_file, _ = self.state.current()
        (self.root / "README.md").write_text("# Changed\nNew text.\n")
        with self.assertRaises(DeveloperError) as caught:
            ProjectIndex.current(self.state, self.corpus)
        self.assertEqual(caught.exception.code, ErrorCode.INDEX_STALE)
        self.build()
        new_file, _ = self.state.current()
        self.assertNotEqual(old_file, new_file)
        self.assertTrue(old_file.is_file())

    def test_deleted_explicit_source_blocks_index(self):
        self.build()
        (self.root / "README.md").unlink()
        with self.assertRaises(DeveloperError):
            ProjectIndex.current(self.state, self.corpus)

    def test_model_failure_preserves_current_pointer(self):
        self.build()
        before = self.state.current()[1]
        provider = SyntheticVectors()
        with patch.object(provider, "embed", side_effect=DeveloperError(ErrorCode.EMBEDDING_UNAVAILABLE)):
            with self.assertRaises(DeveloperError):
                build_index(self.corpus, self.state, provider=provider)
        self.assertEqual(before, self.state.current()[1])

    def test_state_inside_repo_and_public_permissions_are_denied(self):
        with self.assertRaises(DeveloperError):
            ProjectState(self.workspace, self.root / "state")
        self.state.path.chmod(0o755)
        with self.assertRaises(DeveloperError):
            ProjectState(self.workspace, self.state.path)

    def test_state_symlink_parent_is_denied(self):
        alias = self.parent / "state-alias"
        alias.symlink_to(self.state.path, target_is_directory=True)
        with self.assertRaises(DeveloperError) as caught:
            ProjectState(self.workspace, alias / "nested")
        self.assertEqual(caught.exception.code, ErrorCode.PERMISSION_DENIED)
        self.assertFalse((self.state.path / "nested").exists())

    def test_modified_database_is_detected(self):
        self.build()
        file, _ = self.state.current()
        with closing(sqlite3.connect(file)) as db:
            db.execute("UPDATE chunks SET text='tampered'")
            db.commit()
        with self.assertRaises(DeveloperError) as caught:
            ProjectIndex.current(self.state, self.corpus)
        self.assertEqual(caught.exception.code, ErrorCode.INDEX_UNAVAILABLE)

    def test_other_project_identity_cannot_read_this_index(self):
        self.build()
        other = ProjectWorkspace.open(self.root, "other-project")
        with self.assertRaises(DeveloperError):
            ProjectIndex.current(self.state, ProjectCorpus(other))

    def test_build_lock_is_shared_and_not_unlinked(self):
        with self.state.build_lock():
            with self.assertRaises(DeveloperError) as caught:
                with self.state.build_lock():
                    pass
            self.assertEqual(caught.exception.code, ErrorCode.INDEX_LOCKED)
        self.assertTrue((self.state.path / "build.lock").exists())

    def test_verify_recomputes_spans_even_with_updated_db_checksum(self):
        self.build()
        file, pointer = self.state.current()
        with closing(sqlite3.connect(file)) as db:
            db.execute("UPDATE chunks SET start_line=1000")
            db.commit()
        pointer["sha256"] = sha256(file.read_bytes()).hexdigest()
        self.state.publish(pointer)
        with ProjectIndex.current(self.state, self.corpus) as index:
            with self.assertRaises(DeveloperError):
                index.verify()


class RetrievalTests(RagFixture):
    def test_dense_raw_preserves_question_and_legacy_query_is_explicit(self):
        self.build(dense=True)
        class RecordingVectors(SyntheticVectors):
            def __init__(self):
                super().__init__()
                self.inputs = []
            def embed(self, texts, *, final=True):
                self.inputs.extend(texts)
                return super().embed(texts, final=final)
        question = "Why is Ollama API /ps not an idle witness?"
        from bublik_developer.rag.retrieval import query_terms
        before = self.state.current()[1]
        with ProjectIndex.current(self.state, self.corpus) as index:
            for mode in ("dense", "hybrid"):
                provider = RecordingVectors()
                result = search(index, question, mode=mode, provider=provider, dense_query="raw")
                self.assertEqual(provider.inputs, [question])
                self.assertEqual(result["settings"]["dense_query_policy"], "raw")
                provider = RecordingVectors()
                result = search(index, question, mode=mode, provider=provider, dense_query="vocabulary")
                self.assertEqual(provider.inputs, [question + "\nSearch vocabulary: " + " ".join(query_terms(question))])
                self.assertEqual(result["settings"]["dense_query_policy"], "vocabulary")
            self.assertEqual(index.verify()["status"], "verified")
        self.assertEqual(self.state.current()[1], before)

    def test_invalid_query_policy_and_diagnostics_rejected_before_embedding(self):
        class UnavailableProvider:
            def identity(self):
                self.fail("provider must not be accessed")
        self.build(dense=True)
        with ProjectIndex.current(self.state, self.corpus) as index:
            for values in ({"dense_query": "oracle"}, {"dense_query": []}, {"diagnostics": 1}):
                with self.subTest(values=values), self.assertRaises(DeveloperError) as caught:
                    search(index, "memory", mode="dense", provider=UnavailableProvider(), **values)
                self.assertEqual(caught.exception.code, ErrorCode.INVALID_INPUT)

    def test_diagnostics_show_rejected_scores_without_admitting_them(self):
        self.build(dense=True)
        with ProjectIndex.current(self.state, self.corpus) as index:
            regular = search(index, "memory", mode="dense", provider=SyntheticVectors())
            detailed = search(index, "memory", mode="dense", provider=SyntheticVectors(), diagnostics=True)
            self.assertIsNone(regular["dense_diagnostics"])
            self.assertEqual(regular["sources"], detailed["sources"])
            rows = detailed["dense_diagnostics"]["rows"]
            rejected = [row for row in rows if not row["above_threshold"]]
            self.assertTrue(rejected)
            self.assertTrue(all(not row["in_candidates"] for row in rejected))
            self.assertTrue({row["chunk_id"] for row in rejected}.isdisjoint({row["chunk_id"] for row in detailed["sources"]}))
            self.assertEqual([row["rank"] for row in rows], list(range(1, len(rows) + 1)))

    def test_dense_diagnostics_obey_source_namespace(self):
        (self.root / "other.md").write_text("# Memory\nMemory unrelated owner.\n")
        corpus = ProjectCorpus(self.workspace, [SourceSpec("README.md"), SourceSpec("other.md")])
        build_index(corpus, self.state, provider=SyntheticVectors())
        with ProjectIndex.current(self.state, corpus) as index:
            result = search(index, "memory", mode="dense", provider=SyntheticVectors(), sources=["README.md"], diagnostics=True)
            for row in result["dense_diagnostics"]["rows"]:
                self.assertEqual(index.evidence(row["chunk_id"])["source"], "README.md")

    def test_dense_diagnostics_are_bounded_and_do_not_bypass_candidate_limit(self):
        (self.root / "README.md").write_text("".join(f"# Memory {number}\nMemory fact {number}.\n" for number in range(110)))
        self.build(dense=True)
        with ProjectIndex.current(self.state, self.corpus) as index:
            result = search(index, "memory", mode="dense", provider=SyntheticVectors(), diagnostics=True, candidate_k=1, final_k=1)
            diagnostic = result["dense_diagnostics"]
            self.assertEqual(len(diagnostic["rows"]), 100)
            self.assertEqual(diagnostic["scored_chunks"], 110)
            self.assertTrue(diagnostic["truncated"])
            self.assertEqual(sum(row["in_candidates"] for row in diagnostic["rows"]), 1)
            self.assertEqual(len(result["sources"]), 1)

    def test_fts_query_policy_does_not_change_results_or_load_provider(self):
        self.build()
        with ProjectIndex.current(self.state, self.corpus) as index:
            raw = search(index, "memory", dense_query="raw", provider=object(), diagnostics=True)
            legacy = search(index, "memory", dense_query="vocabulary", provider=object(), diagnostics=True)
            self.assertEqual(raw["sources"], legacy["sources"])
            self.assertIsNone(raw["dense_diagnostics"])
            self.assertIsNone(raw["settings"]["dense_query_policy"])

    def test_paired_calibration_labels_only_annotate_finished_rankings(self):
        sys.path.insert(0, str(APP / "scripts"))
        from compare_project_retrieval import expected_dense_matches, trials
        self.assertEqual(trials("all", "both"), [("fts", "raw"), ("dense", "vocabulary"), ("dense", "raw"),
                                                ("hybrid", "vocabulary"), ("hybrid", "raw")])
        self.build(dense=True)
        with ProjectIndex.current(self.state, self.corpus) as index:
            result = search(index, "memory", mode="dense", provider=SyntheticVectors(), diagnostics=True)
            case = {"sources": ["README.md"], "terms": ["/api/v1"]}
            matches = expected_dense_matches(index, case, result)["matches"]
            self.assertEqual(len(matches), 1)
            self.assertFalse(matches[0]["above_threshold"])
            self.assertFalse(matches[0]["selected"])
            self.assertNotIn("/api/v1", result["sources"][0]["quote"])

    def test_calibration_acceptance_does_not_turn_dense_miss_or_partial_into_pass(self):
        sys.path.insert(0, str(APP / "scripts"))
        from compare_project_retrieval import acceptance
        summary = {key: {"source_hit_at_5": 1., "source_mrr": .9, "negative_no_candidates": 2, "negative_cases": 2}
                   for key in ("fts", "dense/raw", "dense/vocabulary", "hybrid/raw", "hybrid/vocabulary")}
        self.assertEqual(acceptance(summary, True)["status"], "passed")
        self.assertEqual(acceptance(summary, False)["status"], "not_evaluated")
        for key, value in (("source_hit_at_5", .9), ("source_mrr", .85), ("negative_no_candidates", 1)):
            changed = {name: dict(row) for name, row in summary.items()}
            changed["dense/raw"][key] = value
            self.assertEqual(acceptance(changed, True)["status"], "failed")

    def test_mode_defaults_preserve_explicit_policy_and_one_embedding_call(self):
        from bublik_developer.rag.retrieval import resolve_dense_query
        self.assertEqual(resolve_dense_query("dense", "auto"), "vocabulary")
        self.assertEqual(resolve_dense_query("hybrid", "auto"), "raw")
        self.assertEqual(resolve_dense_query("dense", "raw"), "raw")
        self.assertEqual(resolve_dense_query("hybrid", "vocabulary"), "vocabulary")
        class RecordingVectors(SyntheticVectors):
            def __init__(self):
                super().__init__()
                self.inputs = []
            def embed(self, texts, *, final=True):
                self.inputs.extend(texts)
                return super().embed(texts, final=final)
        self.build(dense=True)
        with ProjectIndex.current(self.state, self.corpus) as index:
            for mode, expected in (("dense", "vocabulary"), ("hybrid", "raw")):
                provider = RecordingVectors()
                result = search(index, "memory", mode=mode, provider=provider)
                self.assertEqual(result["settings"]["dense_query_policy"], expected)
                self.assertEqual(result["settings"]["requested_dense_query"], "auto")
                self.assertEqual(len(provider.inputs), 1)
                self.assertEqual("Search vocabulary:" in provider.inputs[0], expected == "vocabulary")

    def test_selected_acceptance_keeps_failed_raw_hypothesis_and_detects_regressions(self):
        sys.path.insert(0, str(APP / "scripts"))
        from compare_project_retrieval import acceptance, selected_acceptance, trials
        self.assertEqual(trials("all", "auto"), [("fts", "raw"), ("dense", "vocabulary"), ("hybrid", "raw")])
        summary = {key: {"source_hit_at_5": 1., "source_mrr": mrr, "negative_no_candidates": 2, "negative_cases": 2}
                   for key, mrr in (("fts", .9), ("dense/raw", .9), ("dense/vocabulary", .95), ("hybrid/raw", .95), ("hybrid/vocabulary", .9))}
        self.assertEqual(acceptance(summary, True)["status"], "failed")
        self.assertEqual(selected_acceptance(summary, True)["status"], "passed")
        self.assertEqual(selected_acceptance(summary, False)["status"], "not_evaluated")
        for group, key, value in (("dense/vocabulary", "source_hit_at_5", .9),
                                  ("dense/vocabulary", "source_mrr", .85),
                                  ("dense/raw", "negative_no_candidates", 1)):
            changed = {name: dict(row) for name, row in summary.items()}
            changed[group][key] = value
            self.assertEqual(selected_acceptance(changed, True)["status"], "failed")

    def test_heading_only_filter_preserves_code_and_schema(self):
        self.assertFalse(has_body("# Memory\n\n  ## Retrieval", "markdown"))
        self.assertFalse(has_body("\n  \n", "markdown"))
        self.assertTrue(has_body("# Memory\nSQLite history.", "markdown"))
        self.assertTrue(has_body("```python\n# Memory\n```", "markdown"))
        self.assertTrue(has_body("# Memory", "schema"))

    def test_heading_only_filtered_before_top_k_without_index_rebuild(self):
        (self.root / "README.md").write_text(
            "# Memory\n\n## Memory\n\n### Memory\n\n#### Storage\nMemory history lives in SQLite.\n")
        self.build(dense=True)
        before = self.state.current()[1]
        with ProjectIndex.current(self.state, self.corpus) as index:
            for mode in ("fts", "dense", "hybrid"):
                with self.subTest(mode=mode):
                    result = search(index, "memory", mode=mode, provider=SyntheticVectors(), candidate_k=1, final_k=1)
                    self.assertEqual(result["status"], "retrieved")
                    self.assertEqual(result["content_filter"]["excluded_heading_only"], 3)
                    hit = result["sources"][0]
                    self.assertIn("SQLite", hit["quote"])
                    self.assertEqual(hit["start_line"], 7)
                    doc = self.corpus.collect().documents[0]
                    self.assertEqual(doc.text[hit["start"]:hit["end"]], hit["quote"])
            self.assertEqual(index.verify()["status"], "verified")
        self.assertEqual(self.state.current()[1], before)

    def test_heading_only_corpus_is_no_evidence_in_every_mode(self):
        (self.root / "README.md").write_text("# Memory\n\n## Memory retrieval\n")
        self.build(dense=True)
        with ProjectIndex.current(self.state, self.corpus) as index:
            for mode in ("fts", "dense", "hybrid"):
                with self.subTest(mode=mode):
                    result = search(index, "memory", mode=mode, provider=SyntheticVectors())
                    self.assertEqual(result["status"], "no_evidence")
                    self.assertEqual(result["candidate_counts"], {"fts": 0, "dense": 0})

    def test_dense_and_hybrid_use_identical_stored_chunks(self):
        self.build(dense=True)
        with ProjectIndex.current(self.state, self.corpus) as index:
            provider = SyntheticVectors()
            for mode in ("fts", "dense", "hybrid"):
                result = search(index, "memory", mode=mode, provider=provider)
                self.assertEqual(result["status"], "retrieved")
                self.assertIn("Memory", result["sources"][0]["section"])
                self.assertFalse(result["semantic_support_verified"])

    def test_rrf_boosts_shared_evidence_without_mixing_raw_scores(self):
        rows = fuse([{"chunk_id": "a", "bm25": -900}, {"chunk_id": "b", "bm25": -1}],
                    [{"chunk_id": "b", "cosine": .51}, {"chunk_id": "c", "cosine": .99}])
        self.assertEqual(rows[0]["chunk_id"], "b")
        self.assertAlmostEqual(rows[0]["rrf"], 1 / 62 + 1 / 61)

    def test_namespace_filters_before_top_k(self):
        (self.root / "other.md").write_text("# Memory\nMemory memory memory memory.\n")
        corpus = ProjectCorpus(self.workspace, [SourceSpec("README.md"), SourceSpec("other.md")])
        build_index(corpus, self.state)
        with ProjectIndex.current(self.state, corpus) as index:
            result = search(index, "memory", candidate_k=1, final_k=1, sources=["README.md"])
            self.assertEqual([row["source"] for row in result["sources"]], ["README.md"])
            with self.assertRaises(DeveloperError):
                search(index, "memory", sources=["private.md"])

    def test_sql_operators_and_unknown_entity_do_not_execute_sql(self):
        self.build()
        with ProjectIndex.current(self.state, self.corpus) as index:
            search(index, '" OR 1; DROP TABLE documents; --')
            self.assertEqual(index.verify()["status"], "verified")
            self.assertEqual(search(index, "zxqv_unknown_transducer_9988")["status"], "no_evidence")

    def test_missing_or_mismatched_dense_model_is_not_silent_fts_fallback(self):
        self.build()
        with ProjectIndex.current(self.state, self.corpus) as index:
            with self.assertRaises(DeveloperError):
                search(index, "memory", mode="hybrid", provider=SyntheticVectors())
        self.build(dense=True)
        with ProjectIndex.current(self.state, self.corpus) as index:
            provider = SyntheticVectors()
            provider.digest = "1" * 64
            with self.assertRaises(DeveloperError):
                search(index, "memory", mode="dense", provider=provider)

    def test_utf8_context_budget_and_settings_are_bounded(self):
        self.build()
        with ProjectIndex.current(self.state, self.corpus) as index:
            result = search(index, "memory", context_bytes=1024)
            self.assertLessEqual(result["metrics"]["context_bytes"], 1024)
            for values in ({"candidate_k": 0}, {"min_cosine": float("nan")}, {"context_bytes": 1}):
                with self.assertRaises(DeveloperError):
                    search(index, "memory", **values)

    def test_fts_cli_needs_no_site_packages_or_model(self):
        command = [sys.executable, "-S", str(APP / "main.py"), "--root", str(self.root), "--state-dir", str(self.state.path),
                   "index", "build", "--mode", "fts"]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["embedding_calls"], 0)


class EndpointTests(RagFixture):
    def endpoint_document(self):
        (self.root / "README.md").write_text(
            "# Generation diagnostics\nAPI service progress генерации завершении request completion "
            "API service progress генерации завершении request completion.\n\n"
            "# Service /service/progress: resident jobs\nThe endpoint reports resident jobs; it does not certify completion.\n")

    def test_literal_endpoints_preserve_case_and_exclude_prose_punctuation_and_urls(self):
        self.assertEqual(explicit_endpoints("Compare `/Service/v2` with /service/progress. Also /Service/v2?"),
                         ["/Service/v2","/service/progress"])
        self.assertEqual(explicit_endpoints("No standalone endpoint https://example.test/service/progress"),[])
        match=endpoint_heading_matcher(["/service/progress"])
        self.assertEqual(match("Endpoint /service/progress: report"),1)
        for heading in ("/service/progress-v2","/service/progress/details","/service/progress.bak","/SERVICE/progress"):
            self.assertEqual(match(heading),0,heading)

    def test_endpoint_heading_wins_before_candidate_limit_in_ru_and_en_without_rebuild(self):
        self.endpoint_document();self.build();before=self.state.current()[1]
        with ProjectIndex.current(self.state,self.corpus) as index:
            for question in ("Что сообщает API /service/progress о завершении генерации?",
                             "What does API /service/progress establish about request completion?"):
                original=index.db.execute("SELECT c.section FROM search JOIN chunks c ON c.chunk_id=search.chunk_id "
                    "WHERE search MATCH ? ORDER BY bm25(search,0,2,3,1),c.chunk_id LIMIT 1",[fts_query(query_terms(question))]).fetchone()
                self.assertEqual(original["section"],"Generation diagnostics")
                result=search(index,question,candidate_k=1,final_k=1,context_bytes=4096)
                self.assertEqual(result["sources"][0]["section"],"Service /service/progress: resident jobs")
                self.assertEqual(result["sources"][0]["ranking"]["endpoint_heading_matches"],1)
                self.assertLessEqual(result["metrics"]["context_bytes"],4096)
                self.assertEqual(result["metrics"]["answer_model_calls"],0)
            self.assertEqual(index.verify()["status"],"verified")
        self.assertEqual(self.state.current()[1],before)

    def test_endpoint_priority_does_not_escape_namespace_or_admit_heading_only_or_prefix(self):
        (self.root / "README.md").write_text("# /service/progress\n\n## /service/progress-v2\nAPI service progress explanation.\n")
        (self.root / "other.md").write_text("# /service/progress\nEndpoint report.\n")
        corpus=ProjectCorpus(self.workspace,[SourceSpec("README.md"),SourceSpec("other.md")]);build_index(corpus,self.state)
        with ProjectIndex.current(self.state,corpus) as index:
            result=search(index,"Explain /service/progress",candidate_k=1,final_k=1,sources=["README.md"])
            self.assertEqual(result["sources"][0]["source"],"README.md")
            self.assertEqual(result["sources"][0]["section"],"/service/progress-v2")
            self.assertEqual(result["sources"][0]["ranking"]["endpoint_heading_matches"],0)
            self.assertEqual(result["content_filter"]["excluded_heading_only"],1)
            with self.assertRaises(DeveloperError):search(index,"/service/progress",sources=["private.md"])

    def test_nonendpoint_query_keeps_bm25_order_and_unknown_endpoint_is_not_an_answer(self):
        self.endpoint_document();self.build()
        with ProjectIndex.current(self.state,self.corpus) as index:
            question="request completion"
            original=[x["chunk_id"] for x in index.db.execute("SELECT c.chunk_id FROM search JOIN chunks c ON c.chunk_id=search.chunk_id "
                "WHERE search MATCH ? ORDER BY bm25(search,0,2,3,1),c.chunk_id",[fts_query(query_terms(question))])]
            result=search(index,question)
            self.assertEqual([x["chunk_id"] for x in result["sources"]],original)
            self.assertEqual(result["settings"]["explicit_endpoints"],[])
            self.assertEqual(search(index,"/zxqv_nebula_882019/unknown_662211")["status"],"no_evidence")
            self.assertFalse(result["semantic_support_verified"])

    def test_hybrid_uses_endpoint_fts_rank_with_rrf_and_dense_keeps_cosine_order(self):
        self.endpoint_document();self.build(dense=True)
        question="What is /service/progress request completion?"
        with ProjectIndex.current(self.state,self.corpus) as index:
            dense=search(index,question,mode="dense",provider=SyntheticVectors(),dense_query="raw")
            self.assertIsNone(dense["settings"]["fts_endpoint_policy"])
            dense_ids=[x["chunk_id"] for x in dense["sources"]]
            self.assertEqual(dense_ids,sorted(dense_ids))  # equal synthetic cosine, stable ID order
            hybrid=search(index,question,mode="hybrid",provider=SyntheticVectors())
            hit=next(x for x in hybrid["sources"] if x["section"]=="Service /service/progress: resident jobs")
            self.assertEqual(hit["ranking"]["ranks"]["fts"],1)
            ranks=hit["ranking"]["ranks"]
            self.assertAlmostEqual(hit["ranking"]["rrf"],sum(1/(60+rank) for rank in ranks.values()))


class SessionTests(RagFixture):
    def session(self):
        self.epoch = "a" * 64
        return ModelSession(self.workspace, state_path=self.parent / "model-state", witness=lambda: self.epoch)

    def confirmed(self):
        session = self.session()
        session.prepare()
        self.epoch = "b" * 64
        session.confirm()
        return session

    @patch("bublik_developer.model_session.check_day30_off", return_value={})
    def test_prepare_requires_a_changed_epoch_before_confirm(self, _):
        session = self.session()
        session.prepare()
        with self.assertRaises(DeveloperError):
            session.confirm()
        self.epoch = "b" * 64
        self.assertTrue(session.confirm()["fresh_epoch"])

    @patch("bublik_developer.model_session.check_day30_off", return_value={})
    def test_lease_cannot_escape_context_or_overlap(self, _):
        session = self.confirmed()
        with session.lease() as lease:
            lease.validate()
            with self.assertRaises(DeveloperError):
                with session.lease():
                    pass
        with self.assertRaises(DeveloperError):
            lease.validate()

    @patch("bublik_developer.model_session.check_day30_off", return_value={})
    def test_dispatch_checkpoint_survives_interrupted_request(self, _):
        session = self.confirmed()
        with session.lease() as lease:
            lease.begin()
            self.assertEqual(session._read()["state"], "uncertain")
        with self.assertRaises(DeveloperError):
            with session.lease():
                pass
        self.epoch = "c" * 64
        session.confirm()
        with session.lease() as lease:
            lease.begin()
            lease.finish()
        self.assertEqual(session._read()["state"], "confirmed")

    @patch("bublik_developer.model_session.check_day30_off", return_value={})
    def test_unexpected_restart_blocks_a_reserved_session(self, _):
        session = self.confirmed()
        self.epoch = "c" * 64
        with self.assertRaises(DeveloperError) as caught:
            with session.lease():
                pass
        self.assertEqual(caught.exception.code, ErrorCode.MODEL_EPOCH_CHANGED)


class EmbeddingTests(unittest.TestCase):
    def lease(self):
        class FakeLease:
            invalidated = False
            def validate(self): pass
            def begin(self): pass
            def finish(self): pass
            def uncertain(self): self.invalidated = True
        return FakeLease()

    def test_normalization_rejects_nonfinite_wrong_dimension_and_zero(self):
        for vector in ([0.] * 1024, [1.] * 5, [float("nan")] * 1024, [True] * 1024, [1e308] * 1024):
            with self.assertRaises(DeveloperError):
                normalize(vector)

    def test_local_embed_contract_and_metrics(self):
        calls = []
        def transport(endpoint, body):
            calls.append((endpoint, body))
            return {"model": "bge-m3:latest", "embeddings": [[2.] + [0.] * 1023], "prompt_eval_count": 2}
        provider = LocalEmbeddings(self.lease(), transport=transport)
        self.assertEqual(provider.embed(["text"])[0][0], 1.)
        self.assertFalse(calls[0][1]["truncate"])
        self.assertEqual(calls[0][1]["keep_alive"], "0s")
        self.assertEqual(provider.events[0]["prompt_eval_count"], 2)

    def test_invalid_or_lost_embedding_response_invalidates_lease(self):
        for value in ({"model": "wrong", "embeddings": []}, {"model": "bge-m3", "embeddings": []}):
            lease = self.lease()
            provider = LocalEmbeddings(lease, transport=lambda endpoint, body, value=value: value)
            with self.assertRaises(DeveloperError):
                provider.embed(["text"])
            self.assertTrue(lease.invalidated)

    def test_cloud_embedding_identity_is_rejected(self):
        lease = self.lease()
        def transport(endpoint, body):
            return {"models": [{"name": "bge-m3:latest", "digest": "0" * 64}]} if endpoint == "/api/tags" else {"remote_host": "remote"}
        with self.assertRaises(DeveloperError):
            LocalEmbeddings(lease, transport=transport).identity()


if __name__ == "__main__":
    unittest.main()
