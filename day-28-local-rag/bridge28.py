"""Reuse the Week 6 index/retrieval and Day 26 HTTP clients."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for directory in ('day-23-reranking-filtering', 'day-21-document-indexing', 'day-26-local-llm'):
    sys.path.append(str(ROOT / directory))

from corpus import load_documents, revision  # noqa: E402
from embeddings import normalize  # noqa: E402
from storage import KnowledgeBase  # noqa: E402
from rag23 import Day23RAGAgent, Settings  # noqa: E402
from providers import OllamaProvider, GroqProvider, ProviderError, model_matches, HTTP  # noqa: E402
