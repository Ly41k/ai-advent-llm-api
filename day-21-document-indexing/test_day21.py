"""Offline checks with a deterministic embedding fake, no model downloads."""

import math
from pathlib import Path
import tempfile
import unittest

from agent import BublikKnowledgeAgent
from chunking import chunk_documents, fixed_chunks, structural_chunks
from corpus import Document, ROOT, corpus_stats, load_documents
from embeddings import normalize
from evaluation import evaluate_retrieval, load_questions
from retrieval import retrieve
from retrieval import answer_question
from storage import KnowledgeBase


class FakeEmbedder:
    model = "test-embedding"

    def embed(self, texts):
        # Deliberately simple: verifies transport and evaluation, not semantic quality.
        return [normalize([float(t.lower().count("scheduler") + 1),
                           float(t.lower().count("memory") + 1)]) for t in texts]

    def answer(self, prompt):
        return "The scheduler stores data [1]."


class AbstainingModel:
    def __init__(self, second_answer):
        self.calls = 0
        self.second_answer = second_answer

    def answer(self, prompt):
        self.calls += 1
        return "I don't know." if self.calls == 1 else self.second_answer


class Day21Tests(unittest.TestCase):
    def setUp(self):
        self.document = Document("notes.md", "notes.md",
                                 "# Alpha\none two three four five six\n"
                                 "## Beta\nseven eight nine ten eleven twelve", "digest")

    def test_fixed_overlap_and_structural_sections(self):
        fixed = fixed_chunks(self.document, limit=4, overlap=1)
        words = [c.text.split() for c in fixed]
        self.assertEqual(words[0][-1], words[1][0])
        structural = structural_chunks(self.document, limit=7, overlap=1)
        self.assertEqual({c.section for c in structural}, {"Alpha", "Beta"})
        self.assertTrue(all(c.token_count <= 7 for c in structural))
        self.assertTrue(all(c.chunk_id and c.source and c.start_line > 0 for c in structural))

    def test_code_sections(self):
        code = Document("example.py", "example.py",
                        "import sys\n\ndef first():\n    return 1\n\nclass Second:\n    pass\n", "d")
        sections = structural_chunks(code, limit=20, overlap=2)
        self.assertEqual([c.section for c in sections],
                         ["module", "FunctionDef first", "ClassDef Second"])
        self.assertEqual(sections[1].start_line, 3)

    def test_bad_parameters_and_zero_vectors(self):
        with self.assertRaises(ValueError):
            fixed_chunks(self.document, limit=3, overlap=3)
        with self.assertRaises(ValueError):
            normalize([0.0, 0.0])
        with self.assertRaises(ValueError):
            normalize([math.nan])

    def test_answer_retries_once_with_best_evidence(self):
        from storage import Hit
        hit = Hit("id", "day-18/README.md", "Components",
                  "worker.py periodically collects GitHub data.", 0.8, 7, 8)
        model = AbstainingModel("worker.py collects the data [1].")
        self.assertEqual(answer_question(model, "Which process collects data?", [hit]),
                         "worker.py collects the data [1].")
        self.assertEqual(model.calls, 2)
        uncertain = AbstainingModel("I don't know.")
        self.assertEqual(answer_question(uncertain, "Unrelated question?", [hit]),
                         "I don't know.")
        self.assertEqual(uncertain.calls, 2)

    def test_persistence_rebuild_and_search(self):
        provider = FakeEmbedder()
        documents = [Document("one.md", "one.md", "scheduler scheduler", "a"),
                     Document("two.md", "two.md", "memory memory", "b")]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "knowledge.db"
            kb = KnowledgeBase(path)
            for strategy in ("fixed", "structural"):
                chunks = chunk_documents(documents, strategy, 20, 2)
                kb.save(documents, strategy, chunks, provider.embed([c.text for c in chunks]),
                        provider.model, 20, 2, "commit")
            kb.close()
            kb = KnowledgeBase(path)
            self.assertEqual(len(kb.stats()), 2)
            self.assertTrue(all(item["valid"] for item in kb.validate()))
            self.assertEqual(retrieve(kb, provider, "structural", "scheduler")[0].source,
                             "one.md")
            response = BublikKnowledgeAgent(kb, provider).ask("scheduler")
            self.assertEqual(response.sources[0].source, "one.md")
            self.assertIn("[1]", response.answer)
            self.assertGreaterEqual(response.sources[0].score_01, 0)
            result = evaluate_retrieval(kb, provider, "fixed",
                        [{"question": "scheduler", "source": "one.md"}], top_k=1)
            self.assertEqual(result["recall_at_1"], 1.0)
            chunks = chunk_documents(documents, "fixed", 20, 2)
            kb.save(documents, "fixed", chunks, provider.embed([c.text for c in chunks]),
                    provider.model, 20, 2, "commit")
            self.assertEqual(next(s for s in kb.stats() if s["strategy"] == "fixed")["chunks"], 2)
            kb.close()

    def test_project_corpus_and_gold_questions(self):
        docs = load_documents(ROOT)
        stats = corpus_stats(docs)
        self.assertGreaterEqual(stats["estimated_text_pages"] +
                                stats["estimated_code_pages"], 20)
        sources = {d.source for d in docs}
        self.assertTrue(all(q["source"] in sources for q in load_questions()))
        self.assertEqual(len(sources), len(docs))


if __name__ == "__main__":
    unittest.main()
