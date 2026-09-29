# Day 22 — First RAG Request

Day 22 reuses `day-21-document-indexing/knowledge.db` and exposes two explicit answer modes:

- **NO RAG:** question → LLM;
- **RAG:** question → query embedding → relevant chunk search → question + retrieved context → LLM.

Both paths use the same generation model (`llama3.2` by default) for a fair A/B comparison. The RAG path reuses Day 21's validated retrieval/index contract and returns provenance for every retrieved chunk.

## Run

From the repository root:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python day-22-first-rag/test_day22.py -v

# Build Day 21 once if knowledge.db does not exist yet.
ollama pull bge-m3
ollama pull llama3.2
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify

python day-22-first-rag/main.py questions
python day-22-first-rag/main.py compare \
  "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?"
python day-22-first-rag/main.py evaluate
```

`evaluate` runs exactly ten control questions. Every item records an expected answer description, expected terms, and expected source files. The report stores both answers, RAG sources, expected-term coverage, source-hit diagnostics, and aggregate A/B deltas in `evaluation_results.json`.

Expected-term coverage is a reproducible diagnostic, not a semantic judge; review the generated answers as well.
