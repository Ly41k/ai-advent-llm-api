**English** | [Русский](README.ru.md)

**V16 confirmed across three trials:** 3/3 validity, heuristic quality and manual citation/completeness review. Quotations are identical; wording varies (exact stability: 0/1 group). Generation median: 2.84 s; pipeline median: 2.91 s. [Stability results](STABILITY_RESULTS_V16.md). No further code change or full rerun is needed now. Historical sections below include their state before live reviews.

**Verified V16 quality result:** Preflight and Postflight are explained with separate supporting quotations; strict verification and manual review passed for one trial. Successful VPS V13 and isolation V12 remain retained. [Results and optional focused stability check](QUALITY_RESULTS_V16.md). No new code change is needed; this is not a fresh full benchmark. Historical experiments and their limits remain below.

**V16 before/after evidence probe:** V15 passed heuristics, but request-side semantic checks are still underexplained. [Next probe: two evidence-bound phase explanations in one call (RU)](V16_PHASE_EVIDENCE.ru.md). The phases mode is specialized for temporal check questions. 71 offline tests passed; live V16 quality is pending.

**V15 citation coverage probe:** V14 fixed Preflight/Postflight and passed automated checks, but the final background sentence is not fully supported by selected quotes. [Next probe: one question, one call (RU)](V15_FOCUSED_ANSWER.ru.md). The complete prompt now keeps the answer focused on the question. 69 offline tests passed; live V15 is pending.

**V14 next quality probe:** V13 passed the VPS case (retained), but invariant-phase coverage is still incomplete. Opt-in `--quality-mode complete` writes one complete answer with citations in one call. [Run only unresolved base-03 once (RU)](V14_ONE_ANSWER.ru.md). 69 offline tests passed; live V14 quality is pending.

**V13 selective quality experiment:** opt-in `--quality-mode coverage`. First probe: one call each for the two unresolved OpenAI cases; the passing case stays retained. 67 offline tests passed; live quality improvement is pending. [Commands and review criteria (RU)](V13_QUALITY.ru.md). The default baseline mode preserves previous prompts.

# Day 28 — Local LLM + RAG

**Optional V12 experiment:** OpenAI is now selectable with `--cloud-provider openai`, pinned to `gpt-4.1-mini-2025-04-14`. Groq remains the default; local mode is unchanged. [Setup and small-run instructions](V12_OPENAI.ru.md): three questions × three trials, at most nine OpenAI generation calls and no local generation. 63 offline tests pass. Live OpenAI: 9/9 valid answers, no API errors, 5/9 quality passes, 2.94 s median and 0/3 exactly stable groups. [Results and limitations](OPENAI_RESULTS.md). The historical V11 evaluation remains below.

```bash
python day-28-local-rag/main.py compare --cloud-provider openai --only-provider cloud \
  --questions day-28-local-rag/questions-openai-small.json \
  --repeats 3 --max-tokens 1000 --cloud-rate-retries 0 \
  --output day-28-local-rag/reports/check/openai-small-v12.json
```


Bublik reuses the **Week 6 / Day 21 SQLite index**, performs query embedding and retrieval locally, and generates an answer with a downloaded Ollama model. An optional Groq comparison shares retrieval and the first prompt within a pair. With `--synthesis`, selected evidence and the second prompt can differ.

```text
Question → heuristic rewrite → local bge-m3 → Day 21 SQLite cosine search
         → relevance filter → final K + context budget → local Qwen
         → JSON / exact quote checks → answer + application-owned sources
```

This lesson reuses Day 21 storage, Day 23 retrieval/filtering and Day 26 provider adapters. It offers concise model-generated answers, while Days 24–25 retain their separate extractive coverage/auditor protocol. Exact quotes here verify citation identity; they do not prove every generated claim is supported.

## Assignment coverage

| Requirement | Implementation / evidence |
|---|---|
| Week 6 index | Existing `day-21-document-indexing/knowledge.db`, opened read-only; no alternate corpus or implicit reindex |
| Local retrieval | Loopback-only Ollama embedding API + in-process SQLite cosine search; model/dimension/normalization checks |
| Local generation | Downloaded Ollama model, remote/cloud models rejected, no proxy or redirect, `/api/ps` loading evidence |
| Local vs cloud answers | Explicit `compare`; one retrieval per question/trial, identical prompt SHA-256 for the pair |
| Quality | JSON contract, exact quotation checks, expected answer terms, cited expected sources, positive and negative questions |
| Speed | Retrieval time, generation wall time, pipeline time, model load/token metrics, median and interpolated p95 |
| Stability | Three fresh trials by default, completion/error rates, exact answer/citation identity across fully successful repeated cases |
| Recheck | Offline tests + [validation checklist](VALIDATION.ru.md); live commands below produce separate evidence |

**V11 evaluation: the final local case passed 3/3 with identical answers/citations and a 43.03 s median across two stages. Historical successful groups are retained. Cloud retry hit HTTP 429: 3/4 generated answers passed quality; strict success fails. See the [final report](FINAL_REPORT.md) and [audit](reports/verified/final-audit-v11.json). Earlier version sections are historical.**

## Setup

Run from the repository root, preferably in the existing Python 3.13 virtual environment:

```bash
python -m pip install -r day-28-local-rag/requirements.txt
ollama pull bge-m3
ollama pull qwen2.5:14b
```

Use `--local-model qwen2.5:7b` if desired. Start the Ollama app or `ollama serve`. Downloading models is setup; generation and retrieval then work without internet. No Groq dependency or key is required for `doctor`, `ask` or `evaluate`.

Reuse the existing index. If it is missing or the indexed files changed:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
```

The corpus remains the Week 6 corpus: root READMEs, lesson READMEs from Days 1–20, and non-test Python from Days 16–20. This lesson neither indexes its own question expectations nor converts evaluation fixtures into embeddings. This update changes Day 28 only; root READMEs and indexed sources remain unchanged, so no reindex is needed.

Day 28 checks stored document digests, actual stored document/chunk text, the corpus fingerprint and both index strategies' vectors. A code-only commit with an unchanged corpus is accepted; a corpus change is rejected. The original Day 21 `verify` also checks the full Git revision.

## Run local RAG

Options follow the subcommand:

```bash
python day-28-local-rag/main.py doctor
python day-28-local-rag/main.py ask "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?" --synthesis
python day-28-local-rag/main.py evaluate --repeats 3 \
  --output day-28-local-rag/reports/check/local.json
```

`doctor` checks the index and installed local models; it does not call generation. `ask` and `evaluate` perform real embeddings and generation. V8 returns `claims` (four required nullable slots c1–c4) and `abstained`. Each non-null claim contains `quote_id` and a model-written `statement`. The application joins statements into `answer` and inserts the corresponding exact source quotations and metadata. Raw provider JSON remains under `generation.answer`, including invalid output. Structural bindings do not prove semantic support.

An empty or fully filtered/budget-rejected context returns an application-owned refusal without a generation call. If the model refuses with a nonempty context, it must return the canonical refusal and no citations. If every test refuses, `local_rag_verified` remains false: application refusals are not evidence of local inference.

`local_rag_verified` requires at least one valid model-generated local RAG response, a successful local preflight and matching `/api/ps` model-loading evidence. Full acceptance additionally requires no invalid, incomplete or failed requests and no heuristic quality failures. These flags do not replace semantic review.

## Compare with cloud, when available

Set `GROQ_API_KEY` in the environment or the existing root `.env`:

```bash
python day-28-local-rag/main.py compare --repeats 3 \
  --output day-28-local-rag/reports/check/compare.json
```

The default cloud model is the Day 26 profile, `openai/gpt-oss-20b`; availability is checked before use. Configure `--cloud-model` when needed. Local/cloud receive the same serialized messages and excerpt IDs in each trial. Expected terms and gold sources never enter the prompt. Pair order alternates across trials. Invalid model answers are not retried or repaired; there is no cloud fallback. Cloud HTTP 429 retries are bounded and explicitly logged in V3.

If the cloud key is absent, the report explicitly marks the comparison skipped and still evaluates local RAG. If a configured cloud provider fails preflight or requests, local evaluation continues, failures remain in the report, and the command exits with failure. Sending excerpts to Groq happens only in explicit `compare` mode with an available key.

## Settings

| Flag | Default |
|---|---|
| `--db` | Day 21 `knowledge.db` |
| `--url` | `http://127.0.0.1:11434`; loopback HTTP only |
| `--embedding-model` | `bge-m3`, must match the index |
| `--local-model` | `qwen2.5:14b` |
| `--cloud-model` | `openai/gpt-oss-20b` |
| `--strategy` | `fixed` |
| `--candidate-k` / `--final-k` | `20` / `5` |
| `--min-similarity` | `0.50`, inclusive raw cosine, before final K |
| `--rewrite` | `heuristic`; `none` disables expansion |
| `--max-context-chars` | `16000` excerpt text characters; keeps whole excerpts |
| `--num-ctx` | `16384` Ollama context window |
| `--max-tokens` | `2048` output limit |
| `--timeout` | `180` seconds per HTTP call |
| `--repeats` | `3` for evaluation/comparison; `1` for ask |
| `--questions` | 20 EN/RU questions, including 4 negative controls, copied from Day 23 |

Temperature is zero for both generation providers. Character budget is not a tokenizer-exact input limit; choose a sufficient `num_ctx` for the model and language. Prompt/input token counts and completion reasons are reported. Incomplete generations fail the run. Embedding truncation is disabled explicitly.

## Reports and evaluation

Each command writes JSON and sibling Markdown under `reports/check/` by default. JSON contains settings, run ID, timestamp, source/index revisions, model digests/preflights, retrieval candidates/decisions, actual excerpts/messages, pair prompt hashes, generated/raw answers, citation checks, timings and summaries. Files are replaced atomically and checkpointed after every question/trial. Ctrl-C preserves completed observations and marks the run interrupted. Use --retry-from to start a selective new run for unresolved/missing question/provider pairs.

Quality checks are **heuristics**. Term matches can miss paraphrases or accept misleading wording. Quoting a source exactly does not establish entailment or completeness. Review actual answers next to quotes and expectations. Negative controls detect inappropriate confident answers through the explicit abstention contract.

Timing summaries exclude application-only refusals and unsuccessful generations; failures are counted separately. First trials may include loading. Generation wall time excludes the subsequent `/api/ps` probe. Pipeline time includes query rewrite/embedding/search plus generation. p95 on a small sample is descriptive. Cloud latency includes network; each provider uses its own tokenizer. Raw trials preserve Ollama load duration and generation throughput when available.

Stability requires at least two valid trials for a case and no failed trial for that case. It measures exact answer/citation identity, not semantic equivalence. Fresh retrieval is performed for each trial and its prompt hash is stored, so context changes can be inspected.

Exit code: `0` for accepted runs (or successful doctor), `1` for setup/transport/contract/quality failures, `130` for interruption. Cloud skip alone is not a failure. No automatic index creation or cloud fallback occurs.

## Recheck

```bash
python day-28-local-rag/test_day28.py -v
python day-21-document-indexing/test_day21.py -v
python day-23-reranking-filtering/test_day23.py -v
python day-26-local-llm/test_day26.py -v
```

For live verification, run `doctor`, `evaluate` and optional `compare`, then review their JSON/Markdown reports using [VALIDATION.ru.md](VALIDATION.ru.md). Run `evaluate` with internet disconnected after model setup to demonstrate that local RAG has no internet dependency. It still communicates with the local Ollama server.

Recheck saved reports independently:

```bash
python day-28-local-rag/verify_report.py day-28-local-rag/reports/check/local.json
python day-28-local-rag/verify_report.py day-28-local-rag/reports/check/compare.json
```

## V2 — structured JSON and application-owned quotes

The original live response had a trailing double quote after its JSON and removed the Markdown backticks around `worker.py` in both citations. The original report remains invalid. V2 does not repair or silently accept that output.

Ollama now receives `format` with a JSON schema and an enum of valid quotation IDs. Groq receives `response_format={"type":"json_object"}`; application validation checks schema and selected IDs. These output controls differ and are recorded in the report. The two models still receive identical messages/context per pair; there is one generation call, no hidden repair call.

The application extracts exact quotation lines/sentences from retrieved excerpts, retaining code indentation and punctuation. Model context labels each quotation with an ID, and the model returns only `answer`, `abstained`, `quote_ids`. Unknown, duplicate or empty IDs for a factual answer fail. The application resolves IDs to original source substrings; the model no longer recopies quote text. Citation selection still requires semantic review.

V2 reports have `schema_version=2`, `output_contract=quote_ids_v2` and the quotation catalog. The verifier checks catalog/source consistency and raw selections. It can still parse the original exact-quote contract in older reports; malformed legacy outputs remain rejected. Source files in the Week 6 corpus are unchanged by this update, so an already valid index needs no rebuild.

Provider references: [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs), [Groq JSON object mode](https://console.groq.com/docs/structured-outputs).

## V3 — selective retry

The user V2 run completed 20 questions × 3 trials: local 60/60 valid, 48/60 heuristic passes; cloud 48/60 valid, eight overlong quotation selections and four HTTP 429 errors. Local RAG is live verified. V3 live inference is still pending.

```bash
python day-28-local-rag/main.py compare --retry-from day-28-local-rag/reports/check/compare-v2.json \
  --plan-only --output day-28-local-rag/reports/check/retry-v3.json
python day-28-local-rag/main.py compare --retry-from day-28-local-rag/reports/check/compare-v2.json \
  --repeats 3 --output day-28-local-rag/reports/check/retry-v3.json
python day-28-local-rag/verify_report.py day-28-local-rag/reports/check/retry-v3.json
```

Planning performs no HTTP/inference and never overwrites the baseline. It verifies internal baseline consistency, reassesses valid historical answers against current explicit rubrics, then retries only unresolved question/provider pairs. All three trials are repeated for such a pair; a passing local pair is not invoked because cloud failed. Missing trials in interrupted runs are unresolved. Next use `--retry-from retry-v3.json` and a different output filename to narrow further.

For the submitted V2 report: **9 local and 21 cloud calls**. Historical rubric changes and old/new assessments, baseline run ID and SHA-256 are recorded. Invalid raw outputs are not repaired or accepted retrospectively. Question text, model and retrieval settings must match the baseline. The VPS check rubric now requires systemctl/journalctl; source alternatives include the same day's actual client implementation or other-language README. Dialogue isolation additionally requires an identity term alongside SQLite. Rubrics remain heuristic.

The prompt requests complete mechanisms and direct supporting evidence, preferably 1–4 IDs and never more than 12. GPT-OSS cloud requests use strict JSON Schema with catalog ID enum and maxItems=12; other cloud models use JSON object mode. Application validation remains strict. No silent format fallback is used.

Only cloud generation HTTP 429 is retried, at most twice with waits of 30 and 60 seconds. `--cloud-rate-retries 0` disables retries; `--cloud-retry-delay` sets the initial wait, capped at 60 seconds per wait. Each attempt/error/wait is retained in `transport_attempts`; wall time includes all retries. Other HTTP errors, timeouts and invalid answers are not retried. Account quotas can still prevent completion. After an exhausted HTTP 429, remaining cloud calls are explicitly marked skipped/error for this run while local continues, avoiding repeated waits for every question. Official API support: https://console.groq.com/docs/structured-outputs (checked 2026-10-07).

Schema v3 selective reports use `scope=selective_retry` and explicit `planned_observations`. Their metrics and acceptance describe the new subset only, not a fresh full benchmark. Historical successes remain in the original report. New pairs share exact prompts when both providers are requested; unpaired retries are separate measurements. Cloud-only retries can pass with local_rag_verified=false because local inference was not requested; the baseline provides prior local evidence. Updating Day 28 alone does not change the Week 6 corpus or require reindexing.


## V11 — synthesize from selected evidence

`--synthesis` adds a second call to the same model: the first selects evidence; the second receives only those original quotations and generates a complete answer with supporting IDs. First-stage model statements are not factual input. Final IDs must belong to the selected subcatalog; quality criteria remain unchanged. Without the flag, generation still uses one call. See [V11_FIX.ru.md](V11_FIX.ru.md).

```bash
python day-28-local-rag/main.py evaluate --synthesis --retry-from day-28-local-rag/reports/check/local-probe-v10.json --repeats 1 --output day-28-local-rag/reports/check/local-probe-v11.json
python day-28-local-rag/verify_report.py day-28-local-rag/reports/check/local-probe-v11.json
```

One question/trial, up to two local generate calls. Both phases are saved and included in wall time; attempts counts trials, generation_calls counts logical generate invocations. Cloud HTTP retries may add transport attempts. Paired first prompts match; synthesis contexts may differ with model selections. Live V11 remains pending; stability needs repeated trials after successful diagnosis. Only Day 28 changes; no index rebuild is required. V2–V10 sections describe earlier versions.

## V10 — place the question after the context

V9 omitted the storage name and answered mostly in English to a Russian question. V10 tests input ordering: excerpts appear first in the user JSON, followed by the question. Instructions, output contract, retrieval and quality criteria remain unchanged. This experiment is not yet live-verified. See [V10_FIX.ru.md](V10_FIX.ru.md).

```bash
python day-28-local-rag/main.py evaluate --retry-from day-28-local-rag/reports/check/local-probe-v9.json --repeats 1 --output day-28-local-rag/reports/check/local-probe-v10.json
python day-28-local-rag/verify_report.py day-28-local-rag/reports/check/local-probe-v10.json
```

One local call for the unresolved question. Stability trials follow successful diagnosis; passed questions and cloud are not called. Reports use schema_version=10 and prompt_revision=context_then_question_v10. No index rebuild is required. V2–V9 sections describe earlier versions.

## V9 — concise instructions and a single diagnostic trial

V8 selected SQLite/isolation evidence but omitted the storage name and described a test scenario instead of restoration. V9 replaces the long system prompt with concise Russian instructions while still requiring answers in the question's language. Catalog, contract, retrieval and quality criteria remain unchanged. See [V9_FIX.ru.md](V9_FIX.ru.md).

```bash
python day-28-local-rag/main.py evaluate --retry-from day-28-local-rag/reports/check/local-retry-v8.json --repeats 1 --output day-28-local-rag/reports/check/local-probe-v9.json
python day-28-local-rag/verify_report.py day-28-local-rag/reports/check/local-probe-v9.json
```

One local call for the unresolved question. One trial cannot assess stability; run three trials after a successful answer, using the original failed V8 baseline and a new output filename. Retrying a passed probe retains the pair without generation. Reports use schema_version=9 and prompt_revision=concise_mechanism_ru_v9 with V8 context/citation formats. Live V9 remains pending. Only Day 28 changes; no index rebuild is required. V2–V8 sections describe earlier versions.

## V8 — coherent sections and explicit JSON evidence objects

V7's complete answer bound SQLite storage to a bare database path and restoration to the start of a test scenario. V8 catalogs coherent source sections, splitting large sections at paragraph boundaries while keeping exact substrings. Context uses explicit `quote_id`/`quote` objects instead of marker strings. A section may support several claims when it directly supports each one. Quality criteria remain unchanged and semantic review is still required. See [V8_FIX.ru.md](V8_FIX.ru.md).

```bash
python day-28-local-rag/main.py evaluate --retry-from day-28-local-rag/reports/check/local-retry-v7.json --repeats 3 --output day-28-local-rag/reports/check/local-retry-v8.json
python day-28-local-rag/verify_report.py day-28-local-rag/reports/check/local-retry-v8.json
```

Three local calls for one question, no cloud or repair generation. Live V8 is pending. Reports use schema_version=8, prompt_revision=json_sections_v8, output_contract=evidence_claims_v8, quote_catalog_style=sections_v8 and model_context_style=objects_v8. Historical contracts and results are preserved. Only Day 28 changes; no index rebuild is required. V2–V7 sections describe earlier versions.

## V7 — write each claim with its evidence

V6 again mentioned SQLite without selecting storage evidence. V7 replaces the detached answer/evidence fields with four nullable claim objects, each containing `quote_id` and `statement`. The application assembles only those model-written statements and their exact evidence. Quality criteria remain unchanged; semantic support still needs review. See [V7_FIX.ru.md](V7_FIX.ru.md).

```bash
python day-28-local-rag/main.py evaluate --retry-from day-28-local-rag/reports/check/local-retry-v6.json --repeats 3 --output day-28-local-rag/reports/check/local-retry-v7.json
python day-28-local-rag/verify_report.py day-28-local-rag/reports/check/local-retry-v7.json
```

Three local calls for one question; no additional repair generation. Live V7 is pending. Reports use schema_version=7 and prompt_revision=output_contract=evidence_claims_v7 with the existing passages_v4 catalog. Historical reports retain their own contracts. Only Day 28 changes; no index rebuild is required. V2–V6 sections describe earlier versions.

## V6 — explain persistence and restoration

V5 selected direct SQLite/identifier evidence but omitted storage and history restoration from its answer. V6 requests three explicit mechanisms for persistence questions when documented: durable storage, history restoration and isolation by conversation identifier. Quality criteria remain unchanged. See [V6_FIX.ru.md](V6_FIX.ru.md).

```bash
python day-28-local-rag/main.py evaluate --retry-from day-28-local-rag/reports/check/local-retry-v5.json --repeats 3 --output day-28-local-rag/reports/check/local-retry-v6.json
python day-28-local-rag/verify_report.py day-28-local-rag/reports/check/local-retry-v6.json
```

Three local calls for rewrite-ru-02 only, no cloud. Live V6 remains unverified. Reports use schema_version=6 and prompt_revision=persistence_mechanism_v6 with the existing citation contract. Only Day 28 changes; no index rebuild is required. V2–V5 sections describe earlier versions.

## V5 — select evidence before writing the answer

Live local-retry-v4 passed the generation-guard question in all three trials. The dialogue-isolation answer mentioned SQLite without selecting evidence for it, despite direct storage passages in the retrieved catalog. V5 requests evidence selection first and an answer grounded in those selected passages. Retrieval, citation shape and strict quality criteria stay unchanged; this guidance needs live confirmation. See [V5_FIX.ru.md](V5_FIX.ru.md).

```bash
python day-28-local-rag/main.py evaluate --retry-from day-28-local-rag/reports/check/local-retry-v4.json --repeats 3 --output day-28-local-rag/reports/check/local-retry-v5.json
python day-28-local-rag/verify_report.py day-28-local-rag/reports/check/local-retry-v5.json
```

This plan contains three local calls for rewrite-ru-02 only; passed pairs remain historical and cloud is not called. New reports use schema_version=5 and prompt_revision=evidence_first_v5 with the existing quote_slots_v4/passages_v4 contract. Only Day 28 files change; no index rebuild is required. V2–V4 sections below describe earlier versions.

## V4 — passages, fixed evidence slots, separate provider retries

The live V3 subset had 9/9 valid local results but only 3/9 heuristic passes. base-01 passed all trials and stays frozen. base-03 omitted preflight; rewrite-ru-02 explained the mechanism but chose weak EN evidence. Cloud made four HTTP attempts (one 400, three 429); nineteen remaining observations were marked skipped/error without a request. The exact HTTP 400 cause is unknown from the saved safe diagnostic.

V4 catalogs complete source paragraphs/code blocks instead of sentence/line fragments, dropping standalone Markdown headings/fences. Every retained passage is an exact source substring. The prompt explicitly requests both BEFORE-request and AFTER-response checks when the question asks about checks around generation. The RU dialogue case accepts the corresponding EN README but also requires SQLite and an identity term in selected evidence; this remains a lexical heuristic, not semantic proof.

The schema now uses four required string/null slots: quote_ids={q1: ID|null, q2: ID|null, q3: ID|null, q4: ID|null}. Closed objects/primitives avoid array-size constraints. Ollama and Groq GPT-OSS receive the same schema with ID enums; unknown/duplicate IDs, extra slots, wrong shapes and invalid refusals remain rejected. Groq 400 resolution and V4 model quality still need live validation. No automatic format fallback is introduced.

```bash
python day-28-local-rag/main.py evaluate --retry-from day-28-local-rag/reports/check/retry-v3.json \
  --repeats 3 --output day-28-local-rag/reports/check/local-retry-v4.json
python day-28-local-rag/verify_report.py day-28-local-rag/reports/check/local-retry-v4.json
```

This schedules six local calls and no cloud calls. Later, cloud-only comparison can use compare --only-provider cloud --retry-from the same retry-v3.json, writing to cloud-retry-v4.json. It leaves local uninvolved even if local failures remain in that baseline.

Schema version 4 and quote_slots_v4/passages_v4 record the new representation. Old reports retain their original line catalogs and array contracts; the verifier handles both. Subset metrics never claim a new full benchmark. Only Day 28 changes; no Week 6 reindex is required.
