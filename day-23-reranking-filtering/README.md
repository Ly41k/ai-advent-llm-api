# Day 23 — Relevance filtering and query rewrite

User-supplied live Ollama results and limitations are documented in [LIVE_VERIFICATION.md](LIVE_VERIFICATION.md). The exploratory fixed/20/5/0.50 profile preserves labeled document hits while reducing context. It was selected after inspecting evaluation; generation errors remain. Supply the profile through explicit CLI flags; code defaults are unchanged.

Day 23 reuses Day 21's SQLite index and Ollama adapter and extends the Day 22 RAG design. The second retrieval stage is an **inclusive raw cosine similarity filter**, one of the assignment's permitted alternatives to a reranker. No new cross-encoder or Python package is needed.

`original question → optional query rewrite → query embedding → candidate top-K → optional relevance threshold → final top-K → original question + selected excerpts → LLM`

| Mode | Query rewrite | Relevance filter |
|---|---|---|
| `baseline` | No | No |
| `filter` | No | Yes |
| `rewrite` | Yes | No |
| `rewrite_filter` | Yes | Yes |

Defaults: **20 candidates, at most 5 final chunks, cosine >= 0.35**. The threshold is a starting configuration, not a calibrated probability or a universally optimal value. It is applied to `Hit.score`, not Day 21's `(cosine+1)/2` display mapping. Filtering precedes truncation. An empty result produces a deterministic refusal without calling the answer model; rejected chunks are never put back into context.

## Run from the repository root

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python day-21-document-indexing/test_day21.py -v
python day-22-first-rag/test_day22.py -v
python day-23-reranking-filtering/test_day23.py -v

ollama pull bge-m3
ollama pull llama3.2
# Start Ollama if its app/service is not already serving the local API.
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify

python day-23-reranking-filtering/main.py search \
  "На 18 дне кто выполняет фоновые джобы по расписанию?"
python day-23-reranking-filtering/main.py compare \
  "На 18 дне кто выполняет фоновые джобы по расписанию?" \
  --output day-23-reranking-filtering/compare_results.json
```

The shared corpus collector now explicitly restricts lesson READMEs to **Days 1–20**, matching its documented contract; previous code could silently include Days 22–29. Root READMEs and substantive Day 16–20 Python files remain included. Rebuild the index after this change or changes to indexed source documents. Existing `knowledge.db` is not included in the archive; do not replace your local database when copying the source files.

All global flags go **before** the subcommand. Configure retrieval and rewrite independently:

```bash
python day-23-reranking-filtering/main.py \
  --candidate-k 30 --final-k 4 --min-similarity 0.25 \
  search "How does the Day 18 worker run?" --mode filter

python day-23-reranking-filtering/main.py --rewrite-method llm \
  compare "How does the Day 18 worker run?" --retrieval-only
```

`heuristic` is the default: a small general search-vocabulary glossary expands abbreviations and Russian technical words. It keeps the original question, identifiers, day numbers and negation. It does not read reference answers or source labels. `llm` uses the same local generation model to append a search rewrite; invalid empty/overlong output falls back to the original query. The original question always goes to answer generation. LLM rewrite is still a generation call in `--retrieval-only`; use `heuristic` to avoid all generation.

`compare` rewrites once, searches once per distinct query, and shares exact candidate pools between the corresponding filtered/unfiltered modes. Every mode uses the same answer prompt, provider and temperature=0. Day 21's focused-answer retry is intentionally not used here, so it cannot confound the mode comparison.

## Calibrate, then evaluate

The 20 labeled questions reuse the 10 Day 22 controls, add six conversational/rewrite cases, and four out-of-corpus negatives. **8 calibration questions** are used for threshold choice; **12 evaluation questions** are held out. Labels are only read by evaluation, never by retrieval or rewrite.

```bash
python day-23-reranking-filtering/main.py calibrate
```

Read `selected_threshold` from `calibrate_results.json`. Selection first requires preservation of the unfiltered rewrite's calibration source-hit and positive-empty rates, then maximizes balanced positive source-hit/negative abstention. Ties prefer source precision and then a lower threshold. If every proposed threshold loses calibration evidence, the CLI asks for a lower grid (`calibrate --thresholds 0 0.05 0.1 0.15 0.25 0.35`). It never uses evaluation labels to choose the threshold.

Run the full comparison with the selected threshold, substituting the number you actually obtained:

```bash
# Example threshold only: replace 0.25 with your selected_threshold.
python day-23-reranking-filtering/main.py --min-similarity 0.25 evaluate
# Faster retrieval diagnostics, with no answer generation:
python day-23-reranking-filtering/main.py --min-similarity 0.25 evaluate --retrieval-only
```

`evaluate_results.json` records all four modes, original/rewritten queries, settings, index revision, cosine scores, selected sources, complete supplied context, answers, every candidate decision (`selected`, `below_threshold`, `final_k_limit`), metrics and pairwise deltas. `evaluate_results.md` provides a summary table. `--split all` is available for inspection, but mixes calibration and evaluation and is not a held-out estimate.

Metrics: document source-hit rate, labeled source precision, MRR, negative abstention, empty positive rate, context size and answer term coverage. Source labels can omit other valid documents; these are **document-level diagnostics**, not passage relevance or answer correctness. Review each answer and context with the unfilled human rubric (0=wrong/unsupported, 1=partial, 2=good). Fewer chunks alone do not demonstrate better quality. A small calibration set may overfit; held-out degradation must be reported, not hidden.

## Verified example without models

```bash
python day-23-reranking-filtering/offline_demo.py
```

This builds a temporary real SQLite index over the actual repository corpus using an explicitly labeled lexical TF-IDF hash embedder. It calibrates on eight questions and evaluates the remaining twelve. Reports are included under `reports/offline_*`. It does **not** generate/imitate LLM answers or measure `bge-m3`/`llama3.2` quality. Its scores and selected threshold cannot be transferred to another model. The included result illustrates that query rewrite may help while an aggressive filter can reduce held-out recall; inspect both gains and losses.

The automated tests additionally exercise the complete CLI → Ollama HTTP contract → SQLite → context → generation → JSON/Markdown report using a local HTTP fixture. A real Ollama/model quality run still requires your local runtime.

[Russian instructions](README.ru.md) · [Requirement checklist](ASSIGNMENT_CHECKLIST.ru.md) · [Verification](VERIFICATION.ru.md)
