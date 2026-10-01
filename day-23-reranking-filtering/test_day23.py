"""Offline behavioral and CLI/HTTP/SQLite integration checks; no model downloads."""

from dataclasses import replace
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest

from bridge import HERE, Hit, KnowledgeBase, normalize
from chunking import chunk_documents
from corpus import Document, ROOT, load_documents
from quality import calibrate, evaluate, load_questions, metrics
from query_rewrite import rewrite_query
from rag23 import Day23RAGAgent, EMPTY_ANSWER, MODES, Settings, select_hits


def hit(key, score, text=None):
    return Hit(key, f"{key}.md", "Section", text or f"{key} evidence", score, 1, 2)


class Provider:
    model = "test-embedding"
    answer_model = "test-answer"

    def __init__(self):
        self.queries, self.prompts = [], []
        self.vector = [1.0, 0.0]
        self.response = "worker stores data in SQLite [1]."

    def embed(self, texts):
        self.queries.extend(texts)
        return [self.vector for _ in texts]

    def answer(self, prompt):
        self.prompts.append(prompt)
        return self.response


class KB:
    def __init__(self, hits=None):
        self.hits = hits if hits is not None else [hit("good", .9), hit("noise", .1)]
        self.calls = []
        self.model = "test-embedding"

    def info(self, strategy):
        return {"model": self.model, "dimension": 2, "strategy": strategy, "revision": "fixture"}

    def search(self, strategy, vector, top_k):
        self.calls.append(top_k)
        return self.hits[:top_k]


def question(qid="p", text="worker", answerable=True, split="evaluation"):
    return {"id": qid, "question": text, "expectation": "worker stores SQLite" if answerable else "abstain",
            "expected_terms": ["worker", "SQLite"] if answerable else [],
            "expected_sources": ["good.md"] if answerable else [],
            "answerable": answerable, "split": split}


class Day23Tests(unittest.TestCase):
    def test_threshold_is_inclusive_raw_cosine_before_final_k(self):
        settings = Settings(candidate_k=4, final_k=2, min_similarity=.35)
        selected, eligible, decisions = select_hits(
            [hit("below", .3499), hit("edge", .35), hit("top", .8), hit("third", .36)], settings, True)
        self.assertEqual([h.chunk_id for h in selected], ["top", "third"])
        self.assertEqual(len(eligible), 3)
        self.assertEqual({d["chunk_id"]: d["decision"] for d in decisions},
                         {"top": "selected", "third": "selected", "edge": "final_k_limit",
                          "below": "below_threshold"})
        # display_01 of .1 is .55, but it MUST fail a raw .35 threshold.
        self.assertGreater(hit("noise", .1).score_01, .35)
        self.assertEqual(select_hits([hit("noise", .1)], settings, True)[0], [])

    def test_tied_scores_have_stable_chunk_id_order(self):
        selected, _, _ = select_hits([hit("b", .5), hit("a", .5)], Settings(final_k=1), True)
        self.assertEqual(selected[0].chunk_id, "a")

    def test_reject_invalid_threshold_and_k(self):
        for kwargs in ({"min_similarity": math.nan}, {"min_similarity": math.inf},
                       {"min_similarity": 1.1}, {"final_k": 0}, {"candidate_k": 2, "final_k": 3},
                       {"final_k": 1.5}, {"final_k": True}, {"strategy": "x"},
                       {"rewrite_method": "x"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Settings(**kwargs)
        with self.assertRaises(ValueError):
            select_hits([hit("x", math.nan)], Settings(), True)

    def test_empty_context_never_uses_llm_or_rejected_hits(self):
        provider = Provider()
        result = Day23RAGAgent(KB([hit("noise", .1)]), provider).run("question", "filter")
        self.assertEqual(result.answer, EMPTY_ANSWER)
        self.assertEqual(result.sources, ())
        self.assertEqual(provider.prompts, [])
        self.assertEqual(result.candidates[0]["decision"], "below_threshold")

    def test_compare_four_modes_share_candidate_pools(self):
        provider, kb = Provider(), KB()
        agent = Day23RAGAgent(kb, provider, Settings(final_k=2))
        results = agent.compare("Фоновые джобы на 18 дне")
        self.assertEqual(tuple(results), MODES)
        self.assertEqual(kb.calls, [20, 20])
        self.assertEqual(len(provider.queries), 2)
        self.assertEqual([len(r.sources) for r in results.values()], [2, 1, 2, 1])
        self.assertEqual(results["baseline"].rewrite.method, "none")
        self.assertIn("scheduled jobs", results["rewrite"].rewrite.query)
        self.assertEqual([c["cosine"] for c in results["baseline"].candidates],
                         [c["cosine"] for c in results["filter"].candidates])
        self.assertTrue(all("Question:\nФоновые джобы на 18 дне\n" in p for p in provider.prompts))
        self.assertNotIn("noise evidence", provider.prompts[1])
        self.assertNotIn("Search vocabulary:", provider.prompts[3])

    def test_same_prompt_for_same_context_and_question(self):
        provider = Provider()
        Day23RAGAgent(KB([hit("good", .9)]), provider).compare("question")
        self.assertEqual(len(set(provider.prompts)), 1)
        self.assertEqual(len(provider.queries), 1)

    def test_retrieval_only_skips_generation(self):
        provider = Provider()
        results = Day23RAGAgent(KB(), provider).compare("question", generate=False)
        self.assertEqual(provider.prompts, [])
        self.assertTrue(all(r.answer is None for r in results.values()))

    def test_rewrite_preserves_original_numbers_identifiers_negation(self):
        text = "На Day 16 НЕ удаляй session.list_tools(): инструменты МСП"
        rewritten = rewrite_query(text)
        self.assertTrue(rewritten.query.startswith(text))
        self.assertIn("Model Context Protocol", rewritten.query)
        self.assertEqual(rewritten.original, text)
        self.assertEqual(rewrite_query("unmatched text").query, "unmatched text")
        self.assertEqual(rewrite_query(text, "none").query, text)
        with self.assertRaises(ValueError):
            rewrite_query(" ")
        with self.assertRaises(ValueError):
            rewrite_query(text, "bad")

    def test_llm_rewrite_is_once_and_original_question_is_answered(self):
        provider = Provider()
        provider.response = "MCP tool discovery"
        results = Day23RAGAgent(KB(), provider, Settings(rewrite_method="llm")).compare("Day 16 discovery")
        self.assertEqual(len(provider.prompts), 5)
        self.assertIn("Do not answer it", provider.prompts[0])
        self.assertTrue(results["rewrite"].rewrite.query.startswith("Day 16 discovery"))
        self.assertIn("Question:\nDay 16 discovery\n", provider.prompts[-1])

    def test_invalid_llm_rewrite_falls_back_but_transport_errors_propagate(self):
        provider = Provider()
        for response in ("", "word " * 81):
            provider.response = response
            self.assertEqual(rewrite_query("q", "llm", provider).query, "q")
        def fail(prompt):
            raise RuntimeError("transport unavailable")
        provider.answer = fail
        with self.assertRaisesRegex(RuntimeError, "transport"):
            rewrite_query("q", "llm", provider)

    def test_model_mismatch_fails_before_embedding(self):
        provider, kb = Provider(), KB()
        kb.model = "other"
        with self.assertRaisesRegex(ValueError, "model"):
            Day23RAGAgent(kb, provider).run("question", "baseline")
        self.assertEqual(provider.queries, [])

    def test_invalid_query_vectors_fail(self):
        for vector in ([1], [math.nan, 0], [0, 0], [2, 0]):
            provider = Provider()
            provider.vector = vector
            with self.subTest(vector=vector), self.assertRaises(ValueError):
                Day23RAGAgent(KB(), provider).run("q", "baseline")

    def test_unknown_mode_and_blank_question(self):
        agent = Day23RAGAgent(KB(), Provider())
        with self.assertRaises(ValueError):
            agent.run("q", "wrong")
        with self.assertRaises(ValueError):
            agent.run("", "baseline")

    def test_metrics_and_report_deltas_with_negative_denominators(self):
        kb, provider = KB(), Provider()
        # A negative still retrieves noise, so filtering does not guarantee abstention.
        report = evaluate(Day23RAGAgent(kb, provider, Settings(final_k=2)),
                          [question(), question("n", answerable=False)])
        baseline, filtered = report["summary"]["baseline"], report["summary"]["filter"]
        self.assertEqual(baseline["positive_questions"], 1)
        self.assertEqual(baseline["mean_source_precision"], .5)
        self.assertEqual(filtered["mean_source_precision"], 1)
        self.assertEqual(filtered["negative_abstention_rate"], 0)
        self.assertEqual(report["deltas"]["filter_minus_baseline"]["mean_source_precision"], .5)
        self.assertIsNone(report["details"][0]["modes"]["filter"]["human_review"]["answer_correctness_0_2"])
        self.assertEqual(metrics([], question())["source_hit"], False)
        self.assertIsNone(metrics([], question(answerable=False))["source_hit"])

    def test_calibration_uses_only_calibration_queries_and_caches_grid(self):
        provider, kb = Provider(), KB()
        questions = [question("p", "positive", split="calibration"),
                     question("n", "negative", answerable=False, split="calibration"),
                     question("holdout", "SECRET HOLDOUT", split="evaluation")]
        report = calibrate(Day23RAGAgent(kb, provider), questions, [.2, .5, .95])
        self.assertEqual(report["calibration_ids"], ["p", "n"])
        self.assertEqual(provider.queries, ["positive", "negative"])
        self.assertEqual(provider.prompts, [])
        self.assertEqual(report["selected_threshold"], .2)
        with self.assertRaises(ValueError):
            calibrate(Day23RAGAgent(kb, provider), [questions[0]], [.1])
        with self.assertRaises(ValueError):
            calibrate(Day23RAGAgent(kb, provider), questions, [math.nan])
        with self.assertRaisesRegex(ValueError, "preserves"):
            calibrate(Day23RAGAgent(kb, provider), questions, [.95])
        self.assertFalse(report["sweep"][-1]["eligible_for_selection"])

    def test_control_set_split_and_labels_match_real_corpus(self):
        questions = load_questions()
        self.assertEqual(len(questions), 20)
        self.assertEqual(sum(q["split"] == "calibration" for q in questions), 8)
        self.assertEqual(sum(q["split"] == "evaluation" for q in questions), 12)
        sources = {d.source for d in load_documents(ROOT)}
        self.assertTrue(all(source in sources for q in questions for source in q["expected_sources"]))
        self.assertEqual(sum(not q["answerable"] for q in questions), 4)

    def test_custom_questions_reject_bad_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "questions.json"
            for data in ([], [question(), question()], [dict(question(), expected_sources=[])],
                         [dict(question(), answerable="yes")], [dict(question(), expected_terms="x")]):
                path.write_text(json.dumps(data))
                with self.subTest(data=data), self.assertRaises(ValueError):
                    load_questions(path)

    def test_real_sqlite_top_k_filter_and_original_question_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            kb = KnowledgeBase(Path(temp) / "index.db")
            try:
                documents = [Document("good.md", "good", "worker stores SQLite", "a"),
                             Document("noise.md", "noise", "irrelevant distraction", "b")]
                chunks = chunk_documents(documents, "structural")
                kb.save(documents, "structural", chunks, [[1, 0], normalize([.1, .99])],
                        "test-embedding", 500, 75, "fixture")
                provider = Provider()
                result = Day23RAGAgent(kb, provider, Settings(candidate_k=2, final_k=2)).run("q", "filter")
                self.assertEqual([h.source for h in result.sources], ["good.md"])
                self.assertNotIn("irrelevant distraction", provider.prompts[0])
                self.assertEqual(result.to_dict()["candidate_count"], 2)
            finally:
                kb.close()


class CLIIntegrationTests(unittest.TestCase):
    def test_ollama_http_sqlite_cli_evaluation_and_report(self):
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append((self.path, body))
                payload = {"embeddings": [[1, 0] for _ in body["input"]]} if self.path.endswith("embed") else {
                    "response": "worker stores data in SQLite [1]."}
                encoded = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temp:
                temp = Path(temp)
                db = temp / "index.db"
                kb = KnowledgeBase(db)
                documents = [Document("good.md", "good", "worker stores SQLite", "a"),
                             Document("noise.md", "noise", "irrelevant distraction", "b")]
                chunks = chunk_documents(documents, "structural")
                kb.save(documents, "structural", chunks, [[1, 0], [0, 1]], "test-embedding", 500, 75, "fixture")
                kb.close()
                questions = temp / "questions.json"
                questions.write_text(json.dumps([question()]))
                output = temp / "nested" / "report.json"
                args = [sys.executable, str(HERE / "main.py"), "--db", str(db), "--model", "test-embedding",
                        "--url", f"http://127.0.0.1:{server.server_port}", "--final-k", "2", "evaluate",
                        "--questions", str(questions), "--output", str(output)]
                completed = subprocess.run(args, capture_output=True, text=True, timeout=20)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                report = json.loads(output.read_text())
                self.assertEqual(report["summary"]["filter"]["mean_source_precision"], 1)
                self.assertEqual(report["summary"]["baseline"]["mean_source_precision"], .5)
                self.assertTrue(output.with_suffix(".md").is_file())
                self.assertEqual(sum(path.endswith("generate") for path, body in calls), 4)
                self.assertEqual(sum(path.endswith("embed") for path, body in calls), 1)
                self.assertTrue(all(body["options"]["temperature"] == 0 for path, body in calls
                                    if path.endswith("generate")))
                calls.clear()
                completed = subprocess.run(args + ["--retrieval-only"], capture_output=True, text=True, timeout=20)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertFalse(any(path.endswith("generate") for path, body in calls))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_cli_rejects_missing_index_without_creating_it(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "missing.db"
            completed = subprocess.run([sys.executable, str(HERE / "main.py"), "--db", str(path),
                                        "search", "q"], capture_output=True, text=True, timeout=10)
            self.assertEqual(completed.returncode, 2)
            self.assertFalse(path.exists())

    def test_cli_questions_needs_no_index_or_ollama(self):
        completed = subprocess.run([sys.executable, str(HERE / "main.py"), "questions"],
                                   capture_output=True, text=True, timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(len(json.loads(completed.stdout)), 20)


if __name__ == "__main__":
    unittest.main()
