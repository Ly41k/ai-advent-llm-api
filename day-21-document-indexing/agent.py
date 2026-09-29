"""A small Bublik agent adapter over the shared knowledge base."""

from dataclasses import dataclass

from retrieval import answer_question, retrieve
from storage import Hit, KnowledgeBase


@dataclass(frozen=True)
class KnowledgeAnswer:
    question: str
    answer: str
    sources: tuple[Hit, ...]


class BublikKnowledgeAgent:
    """Use indexed evidence when answering; later agents can reuse this adapter."""

    def __init__(self, kb: KnowledgeBase, provider, strategy: str = "structural",
                 top_k: int = 5, rerank_model: str | None = None):
        self.kb = kb
        self.provider = provider
        self.strategy = strategy
        self.top_k = top_k
        self.rerank_model = rerank_model

    def ask(self, question: str) -> KnowledgeAnswer:
        sources = tuple(retrieve(self.kb, self.provider, self.strategy,
                                 question, self.top_k, self.rerank_model))
        return KnowledgeAnswer(question, answer_question(self.provider, question,
                                                         list(sources)), sources)
