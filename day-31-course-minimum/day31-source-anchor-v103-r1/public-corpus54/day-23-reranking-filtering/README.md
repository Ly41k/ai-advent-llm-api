**English** | [Русский](README.ru.md)

# Day 23 — Relevance filtering and query rewrite

Day 23 extends [Day 22's RAG](../day-22-first-rag/README.md) using [Day 21's shared SQLite index](../day-21-document-indexing/README.md). The second stage is an **inclusive raw cosine similarity filter**, an allowed alternative to a reranker. No cross-encoder or additional Python package is required.

Original question → optional search-query rewrite → embedding → candidate top-K → optional cosine filter → final top-K → original question + selected context → LLM.

| Mode | Rewrite | Filter |
|---|---|---|
| `baseline` | No | No |
| `filter` | No | Yes |
| `rewrite` | Yes | No |
| `rewrite_filter` | Yes | Yes |

`baseline` is still a RAG mode: it retrieves context, but does not rewrite or filter. It is not Day 22's NO RAG mode.

## Settings and selection rules

| Global flag | Code default | Meaning |
|---|---|---|
| `--model` | `bge-m3` | Query embedding model; must match the index |
| `--answer-model` | `llama3.2` | Generation and optional LLM-rewrite model |
| `--strategy` | `structural` | `fixed` or `structural` index |
| `--candidate-k` | `20` | Maximum candidates from search |
| `--final-k` | `5` | Maximum chunks supplied as context |
| `--min-similarity` | `0.35` | Inclusive raw cosine cutoff |
| `--rewrite-method` | `heuristic` | `heuristic` or `llm` |
| `--db` | Day 21 `knowledge.db` | Shared local index |
| `--url` | `http://127.0.0.1:11434` | Ollama service |

Require integers `candidate_k >= final_k >= 1` and a finite threshold in `[-1, 1]`. Filtering uses `Hit.score`, not Day 21's `(cosine+1)/2` display mapping. Similarity is not a probability of relevance or answer correctness.

Candidates are ordered by cosine, with chunk ID breaking ties. Filtered modes keep scores **greater than or equal to** the threshold, then take at most final-K. Fewer than final-K may survive. Rejected candidates are never restored. Empty selected context yields a constant refusal, empty sources/context, and no answer-generation call. `abstained` measures empty retrieval, not every verbal refusal by the model.

## Setup

Use Python 3.13 and an active environment from the repository root. See [root setup](../README.md#requirements-and-setup) if `.venv` does not exist. The base workflow uses only Python's standard library and local Ollama; no Groq key is needed.

```bash
source .venv/bin/activate
ollama pull bge-m3
ollama pull llama3.2
# Model used in the documented exploratory live profile:
ollama pull qwen2.5:7b
python day-23-reranking-filtering/test_day23.py -v
```

Start Ollama if its app/service is not already serving. Build the shared index when absent or stale:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
```

The collector includes root READMEs, lesson READMEs from Days 1–20, and non-test Python files from Days 16–20. Day 21–23 lesson READMEs and reports are excluded, but root README updates change the corpus. Strict revision also includes Git HEAD; build and verify in the final checkout. Day 23 checks model/dimension/vector compatibility, but does not automatically check the entire source revision on every query. Index files and models are not stored in Git.

## Inspect the complete flow

Global flags go **before** the subcommand. This example explicitly sets the historical exploratory fixed/20/5/0.50/Qwen profile, not the defaults:

```bash
python day-23-reranking-filtering/main.py \
  --model bge-m3 --answer-model qwen2.5:7b \
  --strategy fixed --candidate-k 20 --final-k 5 \
  --min-similarity 0.50 --rewrite-method heuristic \
  compare "На 18 дне кто выполняет фоновые джобы по расписанию?" \
  --retrieval-only \
  --output day-23-reranking-filtering/reports/check/compare_20_5.json
```

Remove `--retrieval-only` to generate four answers. Inspect `rewrite`, `settings`, `candidate_count`, `eligible_count`, `selected_count`, `candidates`, `sources`, `context`, and `answer`. Without filtering, `eligible_count` means all retrieved candidates. Every candidate has a decision: `selected`, `below_threshold`, or `final_k_limit`. Selected sources contain text and provenance; candidate diagnostics contain raw `cosine`.

The paired modes share exact candidates: baseline/filter use the original query, rewrite/rewrite_filter use the expanded query. `compare` rewrites once and searches once per distinct query. All four modes use the same answer prompt/provider and temperature=0. They answer the original question. Day 21's focused-answer retry and optional cross-encoder are not used.

For a single mode or a different K:

```bash
python day-23-reranking-filtering/main.py \
  --answer-model qwen2.5:7b --strategy fixed \
  --candidate-k 12 --final-k 3 --min-similarity 0.50 \
  ask "На 18 дне кто выполняет фоновые джобы по расписанию?" \
  --mode rewrite_filter
```

`search` has the same question/mode interface and skips the final answer. To demonstrate all candidates being rejected, use `--min-similarity 1.0` on this question; inspect `selected_count: 0`, `abstained: true`, `sources: []`, and `context: ""`. This is a diagnostic cutoff, not a suggested working threshold. Use `--strategy structural` to check the other index.

## Query rewrite

`heuristic` appends a small general search-vocabulary glossary while retaining the original question, day numbers, identifiers, and negation. It never reads expected answers or source labels. No matching vocabulary means the query is unchanged.

`llm` uses the selected answer model to append a search formulation:

```bash
python day-23-reranking-filtering/main.py \
  --answer-model qwen2.5:7b --strategy fixed \
  --candidate-k 20 --final-k 5 --min-similarity 0.50 \
  --rewrite-method llm \
  search "На 18 дне кто выполняет фоновые джобы по расписанию?" \
  --mode rewrite_filter \
  --output day-23-reranking-filtering/reports/check/llm_rewrite.json
```

Check `method: llm` and `reason: llm_expansion`. Empty/overlong output falls back to the original query with `invalid_output_fallback`; transport/model errors propagate. Retaining the original query does not guarantee that the added model text preserves intent, so inspect it. `--retrieval-only` and `search` skip final answers, but **LLM rewrite still calls a model**. Use `heuristic` to avoid generation calls altogether.

## Calibrate, then evaluate

`questions.json` has 20 labels: 10 Day 22 controls, six conversational questions, and four out-of-corpus negatives. Eight questions are calibration (six positive/two negative); twelve are evaluation (ten positive/two negative). Labels are used by the evaluation/calibration helpers, not retrieval or rewrite.

```bash
python day-23-reranking-filtering/main.py \
  --strategy fixed --candidate-k 20 --final-k 5 \
  --rewrite-method heuristic \
  calibrate --thresholds 0.15 0.25 0.35 0.45 0.50 0.55 0.65 \
  --output day-23-reranking-filtering/reports/check/calibrate.json
```

Read `selected_threshold`; `settings.min_similarity` is the initial setting, not the selected value. Full grid results are in the file's `sweep`, omitted from the console summary. Calibration caches candidates and generates no answers. With LLM rewrite, query-rewrite calls still occur.

Selection preserves unfiltered rewrite's source-hit and positive-empty rates on calibration, then maximizes the balanced positive-source-hit/negative-empty-context score for `rewrite_filter`. Ties prefer source precision, then the lower threshold. This selection targets the combined mode, not every mode independently. If no proposed threshold preserves evidence, extend the grid downward. Evaluation labels are not used for threshold selection.

```bash
# Replace 0.55 with selected_threshold from your own calibration.
python day-23-reranking-filtering/main.py \
  --answer-model qwen2.5:7b --strategy fixed \
  --candidate-k 20 --final-k 5 --min-similarity 0.55 \
  --rewrite-method heuristic \
  evaluate --split evaluation \
  --output day-23-reranking-filtering/reports/check/evaluate.json
```

This runs 12 questions × four modes. JSON contains settings, index revision/model, queries, every candidate decision, selected text, full context, answers, diagnostics, deltas, and unfilled `human_review` fields. A `.md` summary is written alongside. Add `--retrieval-only` to omit answers. `--split all` mixes calibration/evaluation and is not a held-out estimate. Calibrate separately after changing the embedding model, corpus, strategy, K, or rewrite method.

Metrics use labeled **source documents**: source hit, source precision, MRR, empty negatives/positives, context size, and expected-term coverage. Labels may omit valid documents. `negative_abstention_rate` means empty context, not semantic refusal; term coverage is not answer accuracy. Review passage relevance, support, correctness, and citations manually.

## Recorded live results and report publication

The [live verification summary](LIVE_VERIFICATION.md) and [detailed Russian review](LIVE_VERIFICATION.ru.md) describe user-run Ollama experiments from September 30–October 1, 2026. They concern an earlier index revision (`7e5cc6d6...@350a65b38804aaa6`); counts and scores need not match a rebuild after root README changes.

Historical fixed/20/5/0.50, `bge-m3` + `qwen2.5:7b`, heuristic rewrite, 12 evaluation questions:

| Metric | baseline | filter | rewrite | rewrite_filter |
|---|---:|---:|---:|---:|
| Document hits on 10 positive questions | 10/10 | 10/10 | 10/10 | 10/10 |
| Mean labeled source precision | 28.0% | 30.3% | 30.0% | 37.3% |
| MRR | 0.791667 | 0.791667 | 0.766667 | 0.766667 |
| Empty positive contexts | 0/10 | 0/10 | 0/10 | 0/10 |
| Empty negative contexts | 0/2 | 1/2 | 0/2 | 1/2 |
| Mean context words, all 12 questions | 2007.8 | 1592.8 | 1851.8 | 1393.3 |

Combined vs baseline: source precision +9.3 percentage points and context −30.6%, with document hits preserved. Rewrite lowered MRR and term coverage; generation errors remained, including VPS instructions and Day 20 report verification. A document hit is not a correct answer. Calibration selected 0.55, but that cutoff lost some positive contexts on evaluation. **0.50 was explored after inspecting evaluation**, so this is not a fresh independent holdout confirmation or a universally optimal threshold.

Publication caveat for commit `05d23cd9`: `reports/live/` contains [provenance](reports/live/PROVENANCE.json) and [assistant review](reports/live/assistant_review_050.json), but the original live `*_results.json`/`.md` files referenced by the older summary are absent. Provenance hashes and an assistant review are not substitutes for the raw traces or independent human review. Some statements in the older verification documents describe an archive/earlier verification stage, rather than this Git checkout.

Keep intermediate runs under ignored `reports/check/` and `reports/video/`. To publish final evidence, use names such as `reports/live/calibrate.json`, `reports/live/evaluate_050.json`, and `.md`; the current `*_results.json`/`*_results.md` ignore rules apply inside subdirectories too. Check `git status` before committing. Reproduction commands above generate new reports, not the historical bytes.

## Offline demonstration and tests

```bash
python day-23-reranking-filtering/offline_demo.py
python day-21-document-indexing/test_day21.py -v
python day-22-first-rag/test_day22.py -v
python day-23-reranking-filtering/test_day23.py -v
```

`offline_demo.py` creates a temporary real SQLite index over the current corpus with a lexical TF-IDF hash embedder, calibrates, and writes `reports/offline_*`. It does not generate or imitate LLM answers and does not measure `bge-m3`/Qwen quality. Its threshold cannot be transferred to Ollama embeddings; rerunning it can change tracked example reports.

The reviewed version has 7 + 6 + 21 = 34 tests. Day 23 covers inclusive raw cosine before final-K, shared candidate pools, empty-context refusal without generation, stable ties, rewrite/fallback, calibration separation, and CLI → local Ollama HTTP fixture → SQLite → context → JSON/Markdown. These verify functionality, not real-model quality.

For a video: verify the index → compare retrieval in four modes → change 20/5 to 12/3 → show answers and source evidence → LLM rewrite → empty-context case → calibration/evaluation reports → structural index → tests.

[Assignment checklist](ASSIGNMENT_CHECKLIST.ru.md) · [Technical verification](VERIFICATION.ru.md)
