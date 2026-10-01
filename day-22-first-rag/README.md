**English** | [Русский](README.ru.md)

# Day 22 — First RAG request

Day 22 reuses [Day 21's SQLite knowledge base](../day-21-document-indexing/README.md) and compares two answer modes:

| Mode | Flow |
|---|---|
| `no-rag` | Original question → LLM |
| `rag` | Question → query embedding → chunk search → question + retrieved context → LLM |

`Day22RAGAgent` keeps the same generation provider/model in both modes. The NO RAG branch never invokes retrieval; the RAG branch uses Day 21's `retrieve()` and `answer_question()`. If that shared answer helper detects a refusal, it retries once with the best excerpt. Thus the same model is used, but a RAG request may make two generation calls. The prompts also differ to express the two modes; this is not an identical-prompt or identical-call-count experiment.

## Setup and shared index

Run from the repository root with Python 3.13 and an active virtual environment. The base workflow needs no extra Python packages or Groq key. Start Ollama and pull the models:

```bash
source .venv/bin/activate
ollama pull bge-m3
ollama pull llama3.2
python day-22-first-rag/test_day22.py -v
```

If `.venv` does not exist, follow the [root setup](../README.md#requirements-and-setup). If Ollama's app already serves the local API, a separate `ollama serve` process is unnecessary.

Build the shared index if absent or stale, then verify:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
```

The index defaults to `day-21-document-indexing/knowledge.db`. Its corpus contains root READMEs, lesson READMEs from Days 1–20, and non-test Python files from Days 16–20. It excludes lesson READMEs from Days 21 onward and reports. Root README edits still change the corpus. Strict `verify` compares both Git HEAD and the content fingerprint; rebuild in the final checkout after relevant edits or a new commit. The RAG CLI does not automatically perform this complete freshness check.

## Run both modes

```bash
python day-22-first-rag/main.py questions

python day-22-first-rag/main.py ask \
  "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?" \
  --mode no-rag

python day-22-first-rag/main.py ask \
  "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?" \
  --mode rag

python day-22-first-rag/main.py compare \
  "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?"
```

`compare` returns `without_rag` and `with_rag` for the same original question. RAG sources include chunk ID, file, section, line range, and raw cosine. NO RAG has no retrieved sources. Unlike Day 23, Day 22 does not export the complete context/text in its report; inspect the cited source lines or Day 21 `review` for detailed evidence review.

For another generation model or index strategy, put global flags **before** the subcommand:

```bash
ollama pull qwen2.5:7b
python day-22-first-rag/main.py \
  --model bge-m3 --answer-model qwen2.5:7b --strategy fixed --top-k 5 \
  compare "На 18 дне кто выполняет фоновые задачи?"
```

Defaults: `--model bge-m3`, `--answer-model llama3.2`, `--strategy structural`, `--top-k 5`, `--url http://127.0.0.1:11434`. `--db` selects a different shared index. Optional `--rerank-model` uses Day 21's cross-encoder and requires `sentence-transformers`.

`questions` works without an index or Ollama. For all other commands, the current CLI requires an existing index/strategy even for `ask --mode no-rag`; the NO RAG agent method itself does not query it. Retrieval rejects an embedding-model mismatch. Changing only `--answer-model` does not require re-embedding.

## Ten-question evaluation

```bash
python day-22-first-rag/main.py evaluate
```

`questions.json` has exactly ten controls. Each records `question`, `expectation`, `expected_terms`, and `expected_sources`. `evaluate` obtains two answers for every question and writes the ignored `evaluation_results.json`.

The report contains both answers, RAG source provenance, matched expected terms, source hits, per-question term-coverage deltas, and aggregate A/B results. It does not record the full index revision or settings, so retain your command and index verification when comparing experiments.

To select a compatible custom set or output path:

```bash
python day-22-first-rag/main.py \
  --answer-model qwen2.5:7b --strategy fixed --top-k 5 \
  evaluate --questions day-22-first-rag/questions.json \
  --output day-22-first-rag/evaluation_qwen_results.json
```

A custom set must also contain exactly ten complete records. Expected-term coverage is a string-matching diagnostic, not semantic correctness. A document hit does not guarantee that the selected passage answers the question. Review answers against the expectations and source content.

## Verification and relation to Day 23

The six local tests require no live model. They verify mode separation, question → search → context → generation, the paired comparison, the ten-question contract, and the evaluation output.

For a video: show `verify`, `test_day22.py -v`, `questions`, one `compare`, then `evaluate` and its `summary`/`details`.

[Day 23](../day-23-reranking-filtering/README.md) adds independent rewrite/filter modes, candidate/final top-K, an inclusive raw cosine threshold, calibration/evaluation splits, and full context traces. It uses one common answer prompt and does not invoke Day 21's focused-answer retry.

[Requirement checklist](ASSIGNMENT_CHECKLIST.ru.md) · [Verification guide](VERIFICATION.ru.md)
