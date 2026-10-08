"""Read-only reuse of Day 28; no cloud client is instantiated by Day 29."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DAY28 = ROOT / 'day-28-local-rag'
sys.path.insert(0, str(DAY28))
from rag28 import (ExistingIndex, LocalEmbeddings, StructuredHTTP, prepare, parse_answer,
                   quality, percentile)  # noqa: E402
from bridge28 import Settings, OllamaProvider, ProviderError, model_matches  # noqa: E402

