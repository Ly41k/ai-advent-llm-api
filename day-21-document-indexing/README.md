**English** | [Русский](README.ru.md)

# Day 21 — Document indexing and a shared knowledge base

This lesson builds a local knowledge base reused by later retrieval lessons. The corpus contains root `README*.md`, Days 1–20 `README*.md`, and top-level Python files from Days 16–20 except `test_*`. Lesson READMEs from Days 21 onward and generated reports are excluded. Root READMEs still contain the project overview, so this is not a corpus consisting exclusively of Days 1–20 content. `corpus` prints its exact manifest, source commit plus content fingerprint, and approximate page equivalent (300 Markdown words or 50 code lines per page). It exceeds the 20–30 page minimum.

Both strategies index the **same documents with the same embedding model**. `fixed` uses a 500-unit window and 75-unit overlap. `structural` splits Markdown at headings and Python at top-level definitions, then splits long sections using that same window. The units are whitespace-separated fragments (`\S+`), approximate tokens, **not** the BGE-M3 tokenizer. The persisted fields `limit_tokens` and `overlap_tokens` use those same units. SQLite stores chunk ID, source, title, section, line range, text, strategy, vector, model, dimension, parameters, and corpus revision. Rebuilding replaces previous chunks.

## Local run

From the repository root with Python 3.13 (reuse an existing `.venv` if already configured):

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

## CLI arguments and index freshness

Day 21 differs from Days 22–23: connection flags (`--db`, `--url`, `--model`, `--answer-model`) go before the subcommand; `--strategy`, `--top-k`, and `--rerank-model` belong after `search`/`ask`. For example:

```bash
python day-21-document-indexing/main.py --model bge-m3 \
  search "How does the Day 18 worker run?" --strategy fixed --top-k 3
python day-21-document-indexing/main.py --answer-model qwen2.5:7b \
  ask "На 18 дне кто выполняет фоновые задачи?" --strategy fixed
```

Pull `qwen2.5:7b` separately if using the second command. Answer-model changes do not change embedding dimensions or require re-embedding by themselves. Embedding-model changes do.

Revision includes **Git HEAD and the corpus content fingerprint**. Updating the root READMEs changes the indexed corpus; a new Git commit can also change the strict revision even when indexed content is unchanged. Run `build` and `verify` in the final checkout. Updating only a Day 21–23 lesson README without changing HEAD does not change the corpus fingerprint. `knowledge.db` is local and is not supplied by GitHub; chunk counts depend on the current corpus and parameters.

Day 22 uses this index for a NO RAG/RAG comparison. Day 23 uses it for query rewrite, a raw cosine filter, configurable candidate/final K, and four-mode evaluation. Day 23 does not enable the optional Day 21 cross-encoder or focused-answer retry.

An exact scan of SQLite vectors is sufficient for the learning corpus; FAISS can be added later without changing ingestion. Rebuild after changing the model, corpus, or parameters. Generated answers need human review. See [Russian instructions](README.ru.md) for the video checklist.
