"""Reuse the unchanged Day 21 index, storage and Ollama client."""

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DAY21 = ROOT / "day-21-document-indexing"
if not DAY21.is_dir():
    raise ImportError("Extract Day 23 next to day-21-document-indexing in the repository root")
if str(DAY21) not in sys.path:
    sys.path.append(str(DAY21))

from embeddings import Ollama, normalize  # noqa: E402,F401
from retrieval import context_for  # noqa: E402,F401
from storage import Hit, KnowledgeBase  # noqa: E402,F401
