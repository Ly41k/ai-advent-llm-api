"""Adapters to the unchanged retrieval and citation modules from Days 21–24."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for name in ("day-24-citations-grounding", "day-23-reranking-filtering", "day-21-document-indexing"):
    directory = ROOT / name
    if not directory.is_dir():
        raise ImportError(f"Install Day 25 in the repository root; missing {name}")
    sys.path.append(str(directory))

from support24 import KnowledgeBase, Settings, Day23RAGAgent  # noqa: E402,F401
from grounded_agent import StructuredOllama, refusal  # noqa: E402,F401
from strict_agent import StrictRAGAgent  # noqa: E402,F401
from evidence import EvidenceError  # noqa: E402,F401
from coverage_proofs import strict_requirements  # noqa: E402,F401
from corpus import revision  # noqa: E402,F401
