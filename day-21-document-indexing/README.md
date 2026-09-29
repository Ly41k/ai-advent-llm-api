# Day 21 — Document indexing and a shared knowledge base

This lesson builds a local knowledge base reused by later retrieval lessons. The corpus contains root READMEs, Days 1–20 READMEs, and substantive Python files from Days 16–20. `corpus` prints its exact manifest, source commit plus content fingerprint, and approximate page equivalent (300 Markdown words or 50 code lines per page). It exceeds the 20–30 page minimum.

Both strategies index the **same documents with the same embedding model**. `fixed` uses a 500-unit window and 75-unit overlap. `structural` splits Markdown at headings and Python at top-level definitions, then splits long sections using that same window. The units are whitespace-separated fragments (`\S+`), approximate tokens, **not** the BGE-M3 tokenizer. SQLite stores chunk ID, source, title, section, line range, text, strategy, vector, model, dimension, parameters, and corpus revision. Rebuilding replaces previous chunks.

## Local run

From the extracted repository root with Python 3.13:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python day-21-document-indexing/test_day21.py -v
python day-21-document-indexing/main.py corpus
```

Install and start Ollama, then obtain a multilingual embedding model:

```bash
ollama pull bge-m3
ollama serve
```

If the Ollama app already serves locally, do not start another instance. In a separate terminal:

```bash
source .venv/bin/activate
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py inspect
python day-21-document-indexing/main.py verify
python day-21-document-indexing/main.py search "How are GitHub snapshots scheduled?"
python day-21-document-indexing/main.py compare
```

CPU indexing may take time and prints batch progress. Try `build --batch 8` with limited memory. The database defaults to the ignored `day-21-document-indexing/knowledge.db`. Put global flags `--db PATH`, `--url`, and `--model` **before** the subcommand.

`verify` checks both indexes, chunk metadata, vector dimensions and L2 norms, and whether the corpus still matches the source files. `compare` runs the same 15 labeled questions on both indexes and reports document-level Recall@1, Recall@k, MRR@k, ranks and source paths. This checks finding a source document, not passage-level relevance or answer quality. `inspect` shows index size and average chunk length.

## Optional work for the rest of the week

- The embedding model is the **bi-encoder**. Document vectors are computed once. Both query and document vectors are L2-normalized, so dot product equals cosine similarity. Search also displays `display_01=(cosine+1)/2`; it is a display mapping into `[0,1]`, not a calibrated probability.
- For **cross-encoder** reranking of the top 20 candidates, install `sentence-transformers` and pass `--rerank-model cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` to `search`, `ask`, or `compare`. The first call may download the model. Compare reranking separately from chunking.
- For a local generated answer, run `ollama pull llama3.2` and `python day-21-document-indexing/main.py ask "How does the worker run?"`. `BublikKnowledgeAgent` retrieves from the shared base and returns an answer and its sources. It is a lesson adapter, not yet merged into every prior BublikAgent version.
- `python day-21-document-indexing/main.py review --number 11` prints the answer, supplied context, expected-term diagnostics, and an unfilled human rubric for retrieval relevance, support by context, and correctness against reference. Terms or citations alone do **not** establish correctness.

An exact scan of SQLite vectors is sufficient for the learning corpus; FAISS can be added later without changing ingestion. Rebuild after changing the model, corpus, or parameters. Generated answers need human review. See [Russian instructions](README.ru.md) for the video checklist.
