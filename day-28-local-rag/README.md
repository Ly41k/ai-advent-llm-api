**English** | [Русский](README.ru.md)

# Day 28 — Local LLM + RAG

Bublik reuses the **Week 6 / Day 21 SQLite index**, embeds the question and retrieves evidence locally, then generates an answer through a downloaded Ollama model. Cloud generation is an optional comparison. Local `ask` and `evaluate` do not require cloud keys or an internet connection after preparation.

The implementation and live evaluation are complete. The repository retains the original paired comparison, selective fixes, local stability evidence and a focused OpenAI quality/stability check. These are separate runs with their own versions and settings; they are not merged into a new full benchmark.

## Pipeline

Question → heuristic query expansion → local bge-m3 embedding → SQLite cosine search → relevance filtering → final top-K and context budget → local Qwen → validated answer and exact source quotations.

Day 28 reuses storage from Day 21, retrieval/filtering from Day 23 and HTTP clients from Day 26. The index is opened read-only. Local HTTP is restricted to loopback; local mode has no cloud fallback. Expected answers and evaluation terms are not passed to generation.

## Quick start

Run from the repository root in the existing Python 3.13 environment:

```bash
python -m pip install -r day-28-local-rag/requirements.txt
ollama pull bge-m3
ollama pull qwen2.5:14b
```

Keep Ollama running through its desktop application or `ollama serve`. Downloads require internet access; subsequent local inference does not. The embedding model must match the index. `--local-model` can select another downloaded local model, but its results need a separate evaluation.

The existing index is `day-21-document-indexing/knowledge.db`. If it is absent or its corpus has changed:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
```

The corpus contains root READMEs, Days 1–20 READMEs and non-test Python from Days 16–20. Day 28's own documentation/questions are outside this corpus. **Replacing the root README files changes indexed content: rebuild before the next live RAG run.** Changing only Day 28 files does not require rebuilding. A Git commit alone, with unchanged corpus content, is accepted by Day 28's digest/fingerprint verification.

Check readiness, then make one request:

```bash
python day-28-local-rag/main.py doctor
python day-28-local-rag/main.py ask \
  "Какой процесс выполняет фоновые задания на Day 18?" \
  --repeats 1 --max-tokens 512 \
  --output day-28-local-rag/reports/check/video-local.json
python day-28-local-rag/verify_report.py \
  day-28-local-rag/reports/check/video-local.json
```

`doctor` checks readiness without answer generation, so its zero attempts and `local_rag_verified=false` are expected. After a successful local answer, the report should contain `status=ok`, `local_model_loaded=true` and `local_rag_verified=true`. The last flag requires successful local preflight, valid RAG generation and loading evidence from Ollama `/api/ps`; it is not a semantic correctness guarantee.

For a disconnected-internet demonstration, prepare models/index first, disconnect internet access and run the single `ask` command. Keep the Ollama service available. A saved JSON records local endpoints and inference evidence, but does not itself attest that Wi-Fi was disabled.

## Answers and evidence

The default `baseline` contract returns up to four `statement`/`quote_id` claims. The application joins the model's statements and resolves exact quotations and source metadata from retrieved chunks. A source passage may support multiple claims, so repeated quotations are allowed here. Unknown IDs, malformed output and incomplete generation are rejected. The original model output remains in `generation.answer` for diagnosis.

Exact quotations establish provenance; they do not prove that every statement is supported or complete. Review the answer alongside its cited passages. A custom `ask` has no predefined heuristic rubric and still needs manual review.

If retrieval yields no usable evidence, the application abstains without calling the answer model. A model abstention with nonempty context must satisfy the refusal contract. Application-only abstentions do not verify local generation.

## Cloud comparison

`compare` explicitly enables cloud generation. The provider is `groq` by default (`GROQ_API_KEY`, model `openai/gpt-oss-20b`). OpenAI uses `OPENAI_API_KEY`, including an existing root `.env`, and defaults to pinned `gpt-4.1-mini-2025-04-14`. Local commands do not load these keys. No OpenAI SDK is required.

Optional paired comparisons:

```bash
python day-28-local-rag/main.py compare --repeats 3 \
  --output day-28-local-rag/reports/check/compare-groq.json
python day-28-local-rag/main.py compare --cloud-provider openai --repeats 3 \
  --output day-28-local-rag/reports/check/compare-openai.json
```

A fresh pair shares retrieval and the exact first prompt; local/cloud order alternates across trials. With `--synthesis`, each model selects evidence separately, so second-stage inputs can differ. Cloud-only/subset runs are separate measurements, not fresh pairs with historical local responses. Cloud comparison sends retrieved passages to the selected provider.

Without a cloud key, ordinary comparison records a skip and continues locally. Setup/API/format/quality failures remain visible. Groq 429 handling has bounded retries and may skip remaining cloud observations after exhaustion while local evaluation continues. `--cloud-rate-retries 0` disables transport retries. There are no hidden generation calls to repair an answer.

## Quality modes and call count

| Mode | Behavior | Answer calls per factual trial |
|---|---|---:|
| `baseline` (default) | Evidence-bound claims; retained local profile | 1 |
| `coverage` | Claims with stronger multipart completeness instructions | 1 |
| `complete` | One complete answer with supporting quotation IDs | 1 |
| `phases` | Required before/after statements with distinct supporting IDs | 1 |
| `baseline` or `coverage` with `--synthesis` | Evidence selection, then synthesis from selected original passages | 2 |

`complete` and `phases` reject `--synthesis`. `phases` is specialized for temporal check questions; do not apply it to the mixed 20-question suite as a universal mode. Empty retrieval requires zero answer calls. A selection-stage abstention needs no synthesis call. Transport retries are counted separately.

## Evaluation and selective retries

The default question set contains 20 RU/EN cases, including four negative controls. A new full evaluation is optional and can take substantial time:

```bash
python day-28-local-rag/main.py evaluate --repeats 3 \
  --output day-28-local-rag/reports/check/local-new.json
```

To retain passing case/provider groups, use an existing baseline and inspect the plan first:

```bash
python day-28-local-rag/main.py evaluate \
  --retry-from day-28-local-rag/reports/accepted/compare-v2.json \
  --repeats 1 --plan-only \
  --output day-28-local-rag/reports/check/local-retry-plan.json
```

Remove `--plan-only` only when intending to run unresolved cases. The plan itself makes no HTTP/embedding/generation calls. Baselines are verified and reassessed under the current rubric without inference; failed or missing groups are rerun, passing groups retained. Baseline files remain unchanged. Retry identity requires compatible questions, models and retrieval settings; a changed corpus/settings can require a separate fresh run. Retry output covers only new observations. A retry from a fully passing probe can do nothing even if `--repeats 3` is requested; use a fresh narrow question set to measure stability instead.

The final focused cloud check has already been completed; no repeat is required for submission. To intentionally reproduce just that question:

```bash
python day-28-local-rag/main.py compare \
  --cloud-provider openai --only-provider cloud --quality-mode phases \
  --questions day-28-local-rag/questions-invariants-only.json \
  --repeats 3 --max-tokens 1000 --cloud-rate-retries 0 \
  --output day-28-local-rag/reports/check/openai-phases-new.json
```

## Recorded results

Live reports use Python 3.13.3, Ollama 0.34.4, local bge-m3 and Qwen 14B. The host is the author's MacBook Pro M1 with 32 GB RAM. The original index records 120 fixed / 594 structural chunks, dimension 1024; rebuilt counts/revisions can differ.

| Run | Scope | Validity / heuristic quality | Generation median | Exact response stability |
|---|---|---|---:|---|
| V2 local | 20 cases ×3, paired with Groq | 60/60 valid; 48/60 quality | 54.53 s | 20/20 eligible groups |
| V2 Groq | Same initial paired set | 48/60 valid; 38/48 quality | 0.82 s | 11/14 eligible groups |
| V11 local synthesis | One corrected isolation question ×3, two calls/trial | 3/3 valid and quality; manual review passed | 43.03 s, both stages | 1/1 group |
| V12 OpenAI baseline | Three cases ×3, cloud only | 9/9 valid; 5/9 quality | 2.94 s | 0/3 groups |
| V16 OpenAI phases | One corrected invariant question ×3, cloud only | 3/3 valid, quality and manual review | 2.84 s | 0/1 group; citations identical |
| Published video-local | One custom local question, one call | 1/1 valid; manual support reviewed, no heuristic rubric | 20.03 s | Not measured |

V2 validity includes nine application abstentions per provider; these are excluded from generation speed. Stability excludes groups with invalid/failed trials, but a repeatedly bad answer can still be exactly stable. Original V2 quality scores remain historical and are not rewritten by later fixes.

V16 wording varies while both phases and supporting citations remain consistent across three manual reviews. Pipeline median is 2.91 s; interpolated generation p95 is 3.25 s over only three observations. The published video-local pipeline takes 21.40 s. Neither is a fresh speed comparison against the V11 two-stage local run. JSON alone does not establish physical internet disconnection.

Successful VPS V13 and isolation V12 results are retained separately; the invariant fix is confirmed in V16. Historical successes across modes/versions are not a fresh combined full-suite score or a guarantee for future answers.

## Reports and verification

| Location | Purpose |
|---|---|
| `reports/check/` | Generated JSON/Markdown, checkpoints and local experiments; ignored |
| `reports/video/` | Local recording artifacts; ignored |
| `reports/accepted/` | Selected original live JSON evidence committed to Git |
| `reports/verified/` | Audits, hashes and recorded implementation checks |

Do not delete existing reports when installing updates. Save new runs under new names. Historical reports describe the corpus/prompts at their run time and are not modified after reindexing.

Verify stored evidence without model calls:

```bash
python day-28-local-rag/verify_report.py \
  day-28-local-rag/reports/accepted/local-stability-v11.json
python day-28-local-rag/verify_report.py \
  day-28-local-rag/reports/accepted/openai-quality-stability-v16.json
python day-28-local-rag/verify_report.py \
  day-28-local-rag/reports/accepted/video-local.json
```

Strict verification checks internal consistency, contracts, exact bindings, recorded metrics and heuristic quality. It is not an authenticity or semantic proof. Historical reports containing quality failures can fail strict acceptance even when internally consistent. Speed excludes application abstentions and failed generations; generation wall includes transport retries/waits. Exact stability compares final text/citations, not semantic equivalence.

Exit codes: `0` accepted run/readiness check, `1` setup/transport/contract/quality failure, `130` interruption. Reports are written atomically with checkpoints after observations.

Offline implementation tests (71 passed on the reviewed V16 code):

```bash
python -m unittest discover -s day-28-local-rag -p 'test*28.py'
```

Default retrieval: fixed strategy, candidate-K 20, final-K 5, raw cosine ≥0.50, heuristic rewrite, context budget 16000 characters. Default local context: 16384 tokens; output cap: 2048; timeout: 180 s. `ask` uses one trial; `evaluate`/`compare` use three. Both providers use temperature 0; this does not guarantee identical wording.

## Detailed results and history

- [Local evaluation and original paired comparison](FINAL_REPORT.md)
- [Initial OpenAI experiment](OPENAI_RESULTS.md)
- [Selective quality results](QUALITY_RESULTS_V16.md)
- [Final focused stability review](STABILITY_RESULTS_V16.md)
- [Recorded phase audit](reports/verified/openai-stability-v16-audit.json)
- [Historical validation checklist (RU)](VALIDATION.ru.md)
- [Two-stage synthesis design (RU)](V11_FIX.ru.md) and [OpenAI setup (RU)](V12_OPENAI.ru.md)
- [Coverage experiment (RU)](V13_QUALITY.ru.md), [complete answer (RU)](V14_ONE_ANSWER.ru.md), [focused answer (RU)](V15_FOCUSED_ANSWER.ru.md), [before/after contract (RU)](V16_PHASE_EVIDENCE.ru.md)

Version notes preserve the state at each experiment, including then-pending live checks. Use the final results above for the current status. The local RAG system satisfies Day 28; cloud failures and wording variability are evaluation findings, not a dependency of local operation.
