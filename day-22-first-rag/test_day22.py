"""Offline Day 22 checks. No Ollama models or Day 21 database are required."""

from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parent
DAY21_DIR = HERE.parent / "day-21-document-indexing"
if str(DAY21_DIR) not in sys.path:
    sys.path.append(str(DAY21_DIR))

from storage import Hit
from evaluation import evaluate_questions, load_questions
from rag_agent import DAY21_DIR as AGENT_DAY21_DIR, Day22RAGAgent


class FakeProvider:
    model = "test-embedding"
    answer_model = "test-answer"

    def __init__(self):
        self.embed_calls = []
        self.answer_prompts = []

    def embed(self, texts):
        self.embed_calls.append(list(texts))
        return [[1.0, 0.0] for _ in texts]

    def answer(self, prompt):
        self.answer_prompts.append(prompt)
        if "Excerpts:" in prompt or "Excerpt [1]:" in prompt:
            return "worker stores snapshots in SQLite [1]."
        return "I do not know the repository-specific worker name."


class FakeKB:
    def __init__(self):
        self.search_calls = []

    def info(self, strategy):
        return {"strategy": strategy, "model": "test-embedding", "dimension": 2}

    def search(self, strategy, query_vector, top_k=5):
        self.search_calls.append((strategy, query_vector, top_k))
        return [
            Hit(
                "chunk-1",
                "day-18-scheduled-mcp/README.md",
                "Worker",
                "worker stores snapshots in SQLite.",
                0.95,
                10,
                12,
            )
        ][:top_k]


class ScriptedAgent:
    """Small fake used to verify report math independently from retrieval."""

    def compare(self, question):
        from rag_agent import AnswerComparison, AnswerResult
        hit = Hit("id", "source.md", "S", "alpha beta", 0.9, 1, 2)
        return AnswerComparison(
            question,
            AnswerResult("no_rag", question, "alpha"),
            AnswerResult("rag", question, "alpha beta", (hit,)),
        )


class Day22Tests(unittest.TestCase):
    def test_no_rag_does_not_touch_retrieval(self):
        provider = FakeProvider()
        kb = FakeKB()
        agent = Day22RAGAgent(kb, provider)
        result = agent.answer_without_rag("Which process stores snapshots?")
        self.assertEqual(result.mode, "no_rag")
        self.assertEqual(result.sources, ())
        self.assertEqual(provider.embed_calls, [])
        self.assertEqual(kb.search_calls, [])
        self.assertEqual(len(provider.answer_prompts), 1)

    def test_rag_is_question_search_context_llm(self):
        provider = FakeProvider()
        kb = FakeKB()
        agent = Day22RAGAgent(kb, provider, top_k=1)
        result = agent.answer_with_rag("Which process stores snapshots?")
        self.assertEqual(result.mode, "rag")
        self.assertEqual(provider.embed_calls, [["Which process stores snapshots?"]])
        self.assertEqual(len(kb.search_calls), 1)
        self.assertEqual(result.sources[0].source, "day-18-scheduled-mcp/README.md")
        self.assertIn("Excerpts:", provider.answer_prompts[-1])
        self.assertIn("Which process stores snapshots?", provider.answer_prompts[-1])
        self.assertIn("worker stores snapshots", provider.answer_prompts[-1])

    def test_compare_uses_both_modes_for_same_question(self):
        provider = FakeProvider()
        kb = FakeKB()
        agent = Day22RAGAgent(kb, provider)
        result = agent.compare("Same question")
        self.assertEqual(result.without_rag.question, "Same question")
        self.assertEqual(result.with_rag.question, "Same question")
        self.assertEqual(len(provider.answer_prompts), 2)
        self.assertEqual(len(provider.embed_calls), 1)

    def test_control_set_has_exactly_ten_complete_questions(self):
        questions = load_questions()
        self.assertEqual(len(questions), 10)
        for item in questions:
            self.assertTrue(item["expectation"])
            self.assertTrue(item["expected_terms"])
            self.assertIsInstance(item["expected_sources"], list)

    def test_evaluation_records_expectation_sources_and_delta(self):
        questions = [
            {
                "question": f"q{i}",
                "expectation": "alpha beta",
                "expected_terms": ["alpha", "beta"],
                "expected_sources": ["source.md"],
            }
            for i in range(10)
        ]
        report = evaluate_questions(ScriptedAgent(), questions)
        self.assertEqual(report["summary"]["questions"], 10)
        self.assertEqual(report["summary"]["no_rag_mean_expected_term_coverage"], 0.5)
        self.assertEqual(report["summary"]["rag_mean_expected_term_coverage"], 1.0)
        self.assertEqual(report["summary"]["rag_expected_source_hit_rate"], 1.0)
        self.assertEqual(report["details"][0]["comparison"]
                         ["term_coverage_delta_rag_minus_no_rag"], 0.5)

    def test_day21_directory_is_the_sibling_index_source(self):
        self.assertEqual(AGENT_DAY21_DIR.name, "day-21-document-indexing")
        self.assertEqual(AGENT_DAY21_DIR.parent, HERE.parent)


if __name__ == "__main__":
    unittest.main()
