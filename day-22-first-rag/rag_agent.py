"""Day 22: compare direct LLM answers with retrieval-augmented answers."""

from dataclasses import dataclass
from pathlib import Path
import sys


DAY21_DIR = Path(__file__).resolve().parents[1] / "day-21-document-indexing"
if not DAY21_DIR.is_dir():
    raise ImportError(
        "day-21-document-indexing was not found next to day-22-first-rag. "
        "Extract this folder into the ai-advent-llm-api repository root."
    )
if str(DAY21_DIR) not in sys.path:
    sys.path.append(str(DAY21_DIR))

from retrieval import answer_question, retrieve  # noqa: E402
from storage import Hit, KnowledgeBase  # noqa: E402


@dataclass(frozen=True)
class AnswerResult:
    mode: str
    question: str
    answer: str
    sources: tuple[Hit, ...] = ()

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "question": self.question,
            "answer": self.answer,
            "sources": [
                {
                    "chunk_id": hit.chunk_id,
                    "source": hit.source,
                    "section": hit.section,
                    "start_line": hit.start_line,
                    "end_line": hit.end_line,
                    "cosine": round(hit.score, 6),
                }
                for hit in self.sources
            ],
        }


@dataclass(frozen=True)
class AnswerComparison:
    question: str
    without_rag: AnswerResult
    with_rag: AnswerResult

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "without_rag": self.without_rag.to_dict(),
            "with_rag": self.with_rag.to_dict(),
        }


class Day22RAGAgent:
    """One answer model, two modes: direct generation or retrieval + generation."""

    def __init__(self, kb: KnowledgeBase, provider, strategy: str = "structural",
                 top_k: int = 5, rerank_model: str | None = None):
        self.kb = kb
        self.provider = provider
        self.strategy = strategy
        self.top_k = top_k
        self.rerank_model = rerank_model

    def answer_without_rag(self, question: str) -> AnswerResult:
        """Ask the LLM directly. This path intentionally does not query the index."""
        prompt = (
            "Answer the question using only the model's own knowledge. "
            "Do not assume that repository excerpts were supplied. "
            "If you are unsure, say that you do not know. "
            "Answer in the language of the question and keep the answer concise.\n\n"
            f"Question:\n{question}\n\nAnswer:"
        )
        return AnswerResult("no_rag", question, self.provider.answer(prompt))

    def answer_with_rag(self, question: str) -> AnswerResult:
        """Question -> relevant chunks -> question + context -> LLM."""
        hits = tuple(
            retrieve(
                self.kb,
                self.provider,
                self.strategy,
                question,
                self.top_k,
                self.rerank_model,
            )
        )
        answer = answer_question(self.provider, question, list(hits))
        return AnswerResult("rag", question, answer, hits)

    def answer(self, question: str, mode: str = "rag") -> AnswerResult:
        if mode == "rag":
            return self.answer_with_rag(question)
        if mode == "no-rag":
            return self.answer_without_rag(question)
        raise ValueError("mode must be 'rag' or 'no-rag'")

    def compare(self, question: str) -> AnswerComparison:
        """Run the same question through both modes using the same answer model."""
        without_rag = self.answer_without_rag(question)
        with_rag = self.answer_with_rag(question)
        return AnswerComparison(question, without_rag, with_rag)
