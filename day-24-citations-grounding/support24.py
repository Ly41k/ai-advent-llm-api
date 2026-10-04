"""Reuse Days 21 and 23 without changing their behavior or index format."""

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DAY21 = ROOT / "day-21-document-indexing"
DAY23 = ROOT / "day-23-reranking-filtering"
for directory in (DAY23, DAY21):
    if not directory.is_dir():
        raise ImportError(f"Extract Day 24 into the repository root; missing {directory.name}")
    if str(directory) not in sys.path:
        sys.path.append(str(directory))

from bridge import Hit, KnowledgeBase, Ollama  # noqa: E402,F401
from rag23 import Day23RAGAgent, Settings  # noqa: E402,F401
