**English** | [Русский](README.ru.md)

# AI Advent — from an LLM API request to MCP, grounded RAG and local applications

A day-by-day Python learning project that starts with direct LLM API calls and grows into agents, persistent state, MCP tools, document indexing, retrieval-augmented generation, grounded citations, a persistent RAG chat with task memory, a local Kotlin pre-commit review application, and a private AI chat accessible from computers and phones.

**Cheburator** is the captain of the research spacecraft; **Bublik** is the assistant that evolves through the course. **Revik**, introduced on Day 27, is a separate local code review assistant for Kotlin projects.

The repository currently contains **Days 1–30**. Each `day-XX-...` directory is a self-contained lesson with English and Russian documentation. Later lessons reuse selected components from earlier days instead of merging every historical implementation into one application.

## Learning path

| Day | Lesson | What it adds |
|---|---|---|
| [01](day-01-first-api-request/README.md) | First API request | Interactive Groq chat with in-session history |
| [02](day-02-response-control/README.md) | Response control | Structure, length, and explicit answer rules |
| [03](day-03-reasoning-methods/README.md) | Reasoning methods | Four approaches compared on the same task |
| [04](day-04-temperature/README.md) | Temperature | Factual consistency, creativity, and variability |
| [05](day-05-model-versions/README.md) | Model comparison | Quality, latency, token use, and estimated cost |
| [06](day-06-first-agent/README.md) | First agent | `BublikAgent`, console interface, and SQLite memory |
| [07](day-07-context-persistence/README.md) | Context persistence | Isolated dialogues recovered after restart |
| [08](day-08-token-usage/README.md) | Token usage | Estimates, API usage, and approximate request cost |
| [09](day-09-context-compression/README.md) | Context compression | Persisted summary plus recent full messages |
| [10](day-10-context-strategies/README.md) | Context strategies | Sliding Window, Sticky Facts, and Branching |
| [11](day-11-memory-layers/README.md) | Memory model | Short-term, task working, and long-term memory |
| [12](day-12-personalization/README.md) | Personalization | User profiles and profile-scoped context |
| [13](day-13-task-state-machine/README.md) | Task state machine | Persistent stage, progress, expected action, and pause |
| [14](day-14-invariants/README.md) | Invariants | Versioned policy and semantic preflight/postflight checks |
| [15](day-15-controlled-transitions/README.md) | Guarded transitions | Plan approval, stage guards, validation, and resume |
| [16](day-16-mcp-connection/README.md) | MCP connection | Local stdio server/client, handshake, and tool discovery |
| [17](day-17-first-mcp-tool/README.md) | First MCP tool | GitHub tool invoked through the model tool-calling loop |
| [18](day-18-scheduled-mcp/README.md) | Scheduled jobs | SQLite schedules, independent worker, stored snapshots |
| [19](day-19-mcp-composition/README.md) | Tool composition | Fetch → summarize → save across three MCP tools |
| [20](day-20-mcp-orchestration/README.md) | MCP orchestration | Model-selected five-call flow across three MCP servers |
| [21](day-21-document-indexing/README.md) | Document indexing | Shared SQLite index, two chunking strategies, local embeddings |
| [22](day-22-first-rag/README.md) | First RAG request | NO RAG vs RAG, retrieved context, provenance, evaluation set |
| [23](day-23-reranking-filtering/README.md) | Relevance filtering and query rewrite | Candidate/final top-K, cosine threshold, rewrite, calibration |
| [24](day-24-citations-grounding/README.md) | Citations and grounding | Exact source passages, app-owned citations, coverage validation |
| [25](day-25-rag-chat/README.md) | Persistent RAG chat | SQLite sessions, task memory, fresh retrieval, sources, long-dialogue evaluation |
| [26](day-26-local-llm/README.md) | Local LLM launch | Three Ollama requests, Groq comparison, JSON checks, and local loading evidence |
| [27](day-27-local-llm-integration/README.md) | Local LLM integration — Revik | Staged Kotlin analysis, Detekt commit gate, local explanations, linked reports and reviewer tones |
| [28](day-28-local-rag/README.md) | Local LLM + RAG | Week 6 index, local embedding/search/generation, paired cloud comparison and repeated evaluation |
| [29](day-29-local-llm-optimization/README.md) | Local LLM optimization | Task-specific prompts and limits, Q4/Q5 measurements, resource sampling and frozen V7 evidence selections |
| [30](day-30-private-ai-service/README.md) | Private AI service | FastAPI, local Qwen, SQLite history, Web UI/PWA, LAN/Tailscale HTTPS, queue and limits |

## How the architecture evolves

- **Days 1–5:** explore prompts, model parameters, reasoning styles, token use, latency, and cost.
- **Days 6–10:** separate agent logic from the CLI, persist dialogues in SQLite, and manage context size.
- **Days 11–15:** add explicit memory layers, user profiles, a task state machine, invariants, and guarded task transitions.
- **Days 16–20:** introduce MCP. The project moves from a local stdio handshake to a GitHub tool, scheduled jobs, tool composition, and multi-server orchestration.
- **Day 21:** build a reusable local knowledge base with `bge-m3` embeddings, SQLite storage, metadata, and fixed/structural chunking.
- **Day 22:** connect retrieval to generation and compare the same question with and without RAG.
- **Day 23:** add query rewrite, candidate filtering, calibrated cosine thresholds, and four retrieval modes.
- **Day 24:** make answers evidence-bound. The application publishes exact source passages and validates coverage instead of allowing unconstrained synthesis.
- **Day 25:** wrap the grounded RAG protocol in a persistent local chat. Full history and task memory survive restarts, every ordinary question performs fresh retrieval, and long conversations are evaluated with durable checkpoints and per-turn provenance.
- **Day 26:** a standalone module verifies a downloaded Ollama model and sends three prompts of different difficulty. The same inputs can be sent to Groq; the application validates responses and saves JSON/Markdown reports.
- **Day 27:** integrate local inference into Revik, a practical Kotlin pre-commit CLI. Detekt checks staged code using the project configuration; Qwen explains findings. The hook permits or blocks the commit and produces linked reports. Russian/English and three reviewer tones are configurable.
- **Day 28:** reuse the Week 6 index for fully local RAG, retain an initial paired Groq comparison and evaluate selective local/OpenAI fixes. Live reports record quality, speed, exact stability and manual citation support.
- **Day 29:** optimize local Qwen parameters and task contracts, compare Q4/Q5 and resource measurements, and validate V7 evidence selections on frozen RU/EN procedure questions.
- **Day 30:** local Qwen becomes a private HTTP service. The Mac stores full history, Android/iPhone continue the same chats, and Tailscale Serve provides mobile access. Cookie/CSRF, ownership, idempotency, a durable queue, quotas and launchd are separate from inference; the course baseline used no RAG; later history RAG is optional, with no cloud fallback.

The MCP servers in Days 16–20 communicate with local clients over **stdio**. Days 17–20 can call the public GitHub REST API. Only the Day 18 worker needs a continuously running process for unattended schedules.

Days 21–25 and 28–29 use the shared Day 21 knowledge index. Day 25 does not treat earlier assistant answers or remembered task facts as repository evidence: they help resolve intent, while the current answer is grounded in fresh retrieval.

## Requirements

- Python **3.13** is the project target.
- A Groq key is required only by lessons that explicitly call Groq. Day 28 optionally supports OpenAI with `OPENAI_API_KEY`; local operation needs neither key.
- Internet access is required for Groq, OpenAI and live GitHub API calls.
- Local retrieval/RAG lessons and Days 26–30 use **Ollama**.
- Day 27 additionally needs Git, a compatible JDK and Detekt CLI; its Python module has no extra pip dependencies. Its documented hook workflow targets macOS/Linux.
- Day 30 has its own `requirements.lock` (FastAPI/httpx/Uvicorn/Argon2); its main Mac/phone path uses Tailscale, direct LAN uses Caddy and a trusted local CA. No knowledge index or embedding model is required.
- `GITHUB_TOKEN` is optional for public GitHub repositories and can help with rate limits.

### Local models

| Lessons | Embeddings | Generation |
|---|---|---|
| 21–22 | `bge-m3` | `llama3.2` in the documented base flow |
| 23 | `bge-m3` | `llama3.2` by default; `qwen2.5:7b` in documented experiments |
| 24–25 | `bge-m3` | `qwen2.5:14b` in the current grounded/live profile |
| 26 | Not required | `qwen2.5:7b` default; `qwen2.5:14b` in the verified run |
| 27 | Not required | `qwen2.5:14b` default; configurable downloaded local model |
| 28 | `bge-m3` | `qwen2.5:14b` default; optional Groq/OpenAI comparison |
| 29 | `bge-m3` | `qwen2.5:14b` Q4_K_M selected; Q5_K_M compared on one factual case |
| 30 | Not required | `qwen2.5:14b` Q4_K_M; private-chat-v2, context 8192 / output 1024 |

Pull only the models needed for the lesson you want to run.

## Setup

From the repository root:

```bash
git clone https://github.com/Ly41k/ai-advent-llm-api.git
cd ai-advent-llm-api
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows:

```text
.venv\Scripts\activate
```

MCP lessons have lesson-specific dependencies. For example:

```bash
python -m pip install -r day-20-mcp-orchestration/requirements.txt
```

For local RAG work:

```bash
ollama pull bge-m3
ollama pull llama3.2
ollama pull qwen2.5:7b
ollama pull qwen2.5:14b
```

You do not need all answer models at once; the commands above simply cover the documented profiles through Day 30.

If the Ollama desktop application is already serving the local API, a separate `ollama serve` process is not required.

For Groq programs, copy `.env.example` to `.env`, add `GROQ_API_KEY`, and keep credentials out of commits and recordings.

## Running the lessons

Days 1–15 expose a lesson-level `main.py`. For example:

```bash
python day-01-first-api-request/main.py
python day-15-controlled-transitions/main.py
```

Later lessons use specialized entry points:

| Day | Command from repository root | Result |
|---|---|---|
| 16 | `python day-16-mcp-connection/client.py` | Discover local `ping` and `add` MCP tools |
| 17 | `python day-17-first-mcp-tool/demo.py` | Deterministic GitHub-tool demo |
| 17 | `python day-17-first-mcp-tool/main.py` | Interactive model-driven MCP selection |
| 18 | `python day-18-scheduled-mcp/worker.py` + `python day-18-scheduled-mcp/main.py` | Scheduler/worker plus interactive agent |
| 19 | `python day-19-mcp-composition/main.py Ly41k ai-advent-llm-api` | Three-tool pipeline and Markdown report |
| 20 | `python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api --offline` | Five-call flow across three servers |
| 21 | `python day-21-document-indexing/main.py build` | Build both local document indexes |
| 21 | `python day-21-document-indexing/main.py verify` | Verify index revision and corpus fingerprint |
| 22 | `python day-22-first-rag/main.py evaluate` | Evaluate the first RAG flow |
| 23 | `python day-23-reranking-filtering/main.py questions` | Inspect calibration/evaluation questions |
| 24 | `python day-24-citations-grounding/main.py evaluate --output day-24-citations-grounding/reports/check/evaluate.json` | Grounded answers with exact citations |
| 25 | `python day-25-rag-chat/main.py chat` | Persistent local RAG chat |
| 25 | `python day-25-rag-chat/main.py evaluate --process-per-turn --output day-25-rag-chat/reports/check/live.json` | Durable long-dialogue live evaluation |
| 26 | `python day-26-local-llm/main.py demo --local-model qwen2.5:14b` | Three real local requests |
| 26 | `python day-26-local-llm/main.py compare --local-model qwen2.5:14b` | Identical prompts in Ollama and Groq |
| 27 | `python day-27-local-llm-integration/live_demo.py --detekt-bin /absolute/path/to/detekt` | Two real commits in a disposable repository with local LLM explanations |
| 28 | `python day-28-local-rag/main.py ask "Какой процесс выполняет фоновые задания на Day 18?"` | One local RAG answer with source quotations |
| 29 | `python day-29-local-llm-optimization/experiments/quality_v7/main.py verify day-29-local-llm-optimization/reports/check/quality-transfer-v7.json` | Offline consistency check of saved V7 evidence |
| 30 | `python day-30-private-ai-service/scripts/verify_report.py day-30-private-ai-service/reports/verified/languages-policy-v4-offline-20261011.json` | Verify the current 229/229 offline regression, languages and RAG memory checks; see Day 30 README for server setup |

## Day 21 shared knowledge index

Days 21–25 and 28–29 reuse:

```text
day-21-document-indexing/knowledge.db
```

The indexed corpus rule remains intentionally narrow:

- root `README.md` and `README.ru.md`;
- lesson READMEs from Days 1–20;
- non-test Python files from Days 16–20.

README files from Days 21–30 are not automatically added to that corpus. Days 26–27 and 30 do not use this index.

The index stores document digests and a corpus revision. A change to the **root README files** changes indexed content. After installing these updated root READMEs, rebuild before the next strict verification or Day 24/25/28/29 live run. This does not alter saved historical reports. Day 28 accepts a Git commit alone when the indexed corpus fingerprint is unchanged:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
```

## Day 24 — grounded answers

Day 24 publishes exact source passages rather than freely synthesized factual prose. The application owns citation identity and validates source/section/chunk metadata plus coverage.

Current grounded profile:

```text
fixed
candidate K = 20
final K = 5
raw cosine >= 0.50
heuristic rewrite
bge-m3
qwen2.5:14b
strict coverage
```

Run:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
python day-24-citations-grounding/main.py evaluate \
  --output day-24-citations-grounding/reports/check/evaluate.json
```

Semantic validators are still model components; exact citations and a positive verdict do not replace human source review.

## Day 25 — persistent RAG chat with task memory

Day 25 reuses the Day 24 extractive/grounded protocol and adds:

- isolated SQLite chat sessions in `day-25-rag-chat/chats.db`;
- complete persisted history plus bounded recent model context;
- explicit task memory: goal, constraints, clarifications, terms;
- fresh retrieval on every ordinary user question;
- exact source/citation contracts;
- safe recovery of interrupted turns;
- compare-and-set protection for memory updates;
- atomic JSON report/export writes;
- process ownership for live turns on POSIX systems;
- checkpoint/resume long-dialogue evaluation;
- real embedding/search traces with request/session/turn identity.

Quick start:

```bash
python day-25-rag-chat/test_day25.py -v
python day-25-rag-chat/main.py offline-demo
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
python day-25-rag-chat/main.py chat
```

Final v24 verification recorded in the repository:

- **181 Day 25 tests passed**;
- **169 regression tests from Days 21–24 passed**;
- final live 12+12 run: **24/24 answers passed manual review**;
- **47 exact quotes**;
- **48 embedding calls + 48 search calls**;
- **24 separate question processes/request IDs**;
- two additional negative controls passed with expected `unknown` behavior.

See the [Day 25 README](day-25-rag-chat/README.md), [v24 audit](day-25-rag-chat/AUDIT_V24.ru.md), and [final acceptance](day-25-rag-chat/ACCEPTANCE_V24.ru.md).

## Day 26 — local LLM and cloud comparison

The standalone `day-26-local-llm/` module calls a downloaded model through the Ollama HTTP API. Local mode satisfies the assignment; Groq is an additional cloud comparison.

The three examples cover a short `2 + 2` answer, JSON formatting of a Python calculator result, and five-field extraction with an exact quotation from a Day 18 README excerpt. The application calls the calculator before generation. This lesson does not perform model-selected tool calls, MCP calls, or RAG retrieval.

With Qwen 14B already installed:

```bash
python day-26-local-llm/test_day26.py -v
python day-26-local-llm/main.py doctor --local-model qwen2.5:14b
python day-26-local-llm/main.py demo --local-model qwen2.5:14b \
  --output day-26-local-llm/reports/check/local.json
ollama ps

# Requires GROQ_API_KEY; sends three additional requests to Groq.
python day-26-local-llm/main.py compare --local-model qwen2.5:14b \
  --output day-26-local-llm/reports/check/compare.json
```

The author-supplied `compare-v1.3.json` report dated 2026-10-06 records Python 3.13.3, Ollama 0.34.4, `qwen2.5:14b` Q4_K_M, and Groq `openai/gpt-oss-20b`. **3/3 local** and **3/3 cloud** answers passed validation; the local model was still loaded after generation. The 38 offline tests also passed on Python 3.12.

These results cover three examples with calculator assistance in the middle prompt, not arbitrary-answer reliability. Keep selected live evidence in `reports/live/`; temporary `reports/check/` and `reports/video/` are ignored by Git.

See the [Day 26 README](day-26-local-llm/README.md).

## Day 27 — Revik, a local Kotlin pre-commit review agent

Revik is a standalone Python CLI application for a real KMP development workflow. It reads staged `.kt`/`.kts` blobs, runs Detekt with `detekt/detekt.yml`, requests an explanation from downloaded Qwen through Ollama, and displays findings with file/line links. The Git hook permits or rejects the commit through its exit code.

The configuration and Kotlin inputs come from the Git index, including partially staged changes. A configuration/baseline change checks the entire staged Kotlin tree. A missing configuration or no selected Kotlin files skips the check. Findings and technical errors block the commit; the LLM never overrides Detekt. By default, an unavailable/incomplete local model also blocks the commit.

Revik supports `language=ru|en` and `tone=professional|light_troll|hard_troll`, uses no cloud API keys or fallback, and writes JSON/Markdown/HTML reports to the Git service directory. Analysis is AST-only without type resolution, so keep platform-specific Gradle/CI checks.

From the course repository root:

```bash
python -m unittest discover -s day-27-local-llm-integration/tests -v

# Requires installed Detekt CLI, Ollama and downloaded qwen2.5:14b.
python day-27-local-llm-integration/live_demo.py \
  --detekt-bin /absolute/path/to/detekt \
  --language en --tone professional \
  --output day-27-local-llm-integration/revik-live.json
```

The live demo creates a disposable repository and tries a rejected bad commit and a successful corrected commit. It does not install a hook in the course repository. The [Day 27 README](day-27-local-llm-integration/README.md) includes standalone JAR setup and instructions for copying the lesson into a working project's `tools/revik-agent/`.

**28 integration tests pass** on the current Day 27 code. Their model and Detekt responses are scripted; a separate real Detekt 1.23.8 smoke check covers the demo's bad/clean inputs. Live Qwen explanations require review. See [validation](day-27-local-llm-integration/VALIDATION.md).

Commit Revik's source, examples and template in the course repository. In the working KMP project, the agent directory and `.revik.json` can stay local and ignored. Downloaded JARs and temporary reports are not course source artifacts.

## Day 28 — local LLM + RAG

The [Day 28 module](day-28-local-rag/README.md) reuses the Week 6 / Day 21 index read-only, local bge-m3 embeddings, Day 23 retrieval/filtering and downloaded Qwen through Ollama. `ask` and `evaluate` require no cloud key. `compare` optionally adds Groq or OpenAI. A fresh pair shares the first prompt and retrieved context; with two-stage synthesis, each provider's final evidence/prompt can differ.

Quick local demonstration:

```bash
python day-28-local-rag/main.py doctor
python day-28-local-rag/main.py ask \
  "Какой процесс выполняет фоновые задания на Day 18?" \
  --repeats 1 --max-tokens 512 \
  --output day-28-local-rag/reports/check/video-local.json
python day-28-local-rag/verify_report.py \
  day-28-local-rag/reports/check/video-local.json
```

`doctor` does not generate an answer; zero attempts and `local_rag_verified=false` are expected. A successful local request records answer/source evidence, loading confirmation and `local_rag_verified=true`. Models and index must be prepared before disconnecting internet access. JSON records the local endpoints and generation; the recording/environment must show the actual network disconnection.

Live evidence is committed in [reports/accepted](day-28-local-rag/reports/accepted/):

| Run | Recorded result | Generation median |
|---|---|---:|
| Original V2, 20 cases ×3 per provider | Local: 60/60 valid, heuristic quality 48/60; Groq: 48/60 valid, quality 38/48 | Local 54.53 s / Groq 0.82 s |
| V11, one corrected local isolation case ×3 | Quality/manual review 3/3; exact answer/citation stability 1/1 group; two calls per trial | 43.03 s, both stages |
| V12, three OpenAI cases ×3 | 9/9 valid without API errors; initial quality 5/9 | 2.94 s |
| V16, corrected OpenAI invariant case ×3 | Quality/manual review 3/3; citations identical, wording varies | 2.84 s |
| Published video-local, one custom local question | Valid cited answer; local model loaded; no predefined heuristic rubric | 20.03 s (pipeline 21.40 s) |

The V2 quality scores are historical; validity includes application abstentions. Later selective successes across versions are retained without merging them into a fresh full-suite score. V16 exact answer stability is 0/1 group, while manual review confirms the same mechanisms and citations across three trials. Its cloud-only measurement is not a fresh speed comparison with the two-stage V11 local run.

The reviewed V16 implementation has **71 passing offline tests**. [Local/paired results](day-28-local-rag/FINAL_REPORT.md), [OpenAI baseline](day-28-local-rag/OPENAI_RESULTS.md), [quality fixes](day-28-local-rag/QUALITY_RESULTS_V16.md) and [final focused stability](day-28-local-rag/STABILITY_RESULTS_V16.md) document scope and limitations. Local RAG, cloud comparison and quality/speed/stability evaluation are complete; no full rerun is required for submission.

For an optional cloud run use `compare --cloud-provider openai` with `OPENAI_API_KEY`, or the default Groq provider with `GROQ_API_KEY`. Keys can come from the existing root `.env`; local commands do not load them. The default local mode stays `baseline`; the specialized `phases` mode is only for before/after questions. See the Day 28 README for commands and call counts.

## Day 29 — task-specific local LLM optimization

The [Day 29 module](day-29-local-llm-optimization/README.md) optimizes local Qwen for repository lookups, unsupported-question abstention, and a source-backed check of the Day 18 periodic VPS worker. It reuses the Day 21 index and Day 28 components; no cloud key or fallback is required.

Selected: **Qwen2.5 14B Instruct Q4_K_M**, local bge-m3, temperature=0, output limit=1024, and context=8192, measured on a MacBook Pro M1 / 32 GB. Baseline limits were 2048 / 16384. Prompts and limits changed together; temperature's isolated effect and weight fine-tuning were not part of the measured result.

V3 produces short factual answers. V7 routes supported periodic-procedure questions to four model-selected evidence roles: status, logs, execution, and recurrence. The application validates and renders the procedure from source quotations. Raw selections and displayed answers remain separate; completed failures are cached without hidden retries. The current launcher is `experiments/quality_v7/main.py`, rather than the original top-level experiment launcher.

| Evidence | Recorded result |
|---|---|
| Four factual / abstention questions ×3 | 12/12 semantic-review passes |
| Original V7 periodic procedure ×3 | 3/3 semantic-review passes |
| Frozen new RU/EN procedure formulations ×3 each | 6/6 semantic-review passes; identical responses within each triplet |
| Worker fact: baseline / Q4-V3 / Q5-V3 | Median generation 26.281 / 6.091 / 7.665 s |
| Periodic procedure: V6 / V7 | Median generation 16.572 / 6.077 s, with a changed output contract |
| Q4 / Q5 reported allocation on the worker fact | Maximum Ollama `size_vram` 9.56 / 10.89 GiB |

These are 21 reviewed selected-profile observations on seven questions, including three formulations of one procedure. The assistant's semantic reviews are stored separately from automatic audits. Q4/Q5 parity was tested on one factual question only; no universal reasoning improvement is claimed. V7's 75 output tokens describe selections, not the full procedure. Cache/prefill affects timings; RSS and `size_vram` are not full physical unified-memory usage.

Check committed evidence without Ollama or the original database:

```bash
python day-29-local-llm-optimization/experiments/quality_v7/main.py verify \
  day-29-local-llm-optimization/reports/check/quality-transfer-v7.json
```

`consistent=true` verifies report consistency; the preserved automatic `optimization_verified=false` still requires separate semantic review. Original reports are committed in `reports/check/` despite the directory's ignore rule; new outputs and cache remain local. Documentation changes require an index rebuild before a new live run, but not to verify saved reports.

See [final measurements](day-29-local-llm-optimization/FINAL_REPORT.ru.md), [selected profile](day-29-local-llm-optimization/SELECTED_PROFILE.json), [assignment checklist](day-29-local-llm-optimization/ASSIGNMENT_CHECKLIST.ru.md), and [validation](day-29-local-llm-optimization/VALIDATION.md). The assignment is complete within the stated scope; new generation is optional.

## Day 30 — Bublik Private AI Service

**Current extension: 0.10.3.** Russian/English interface and reply languages
are separate, saved per user and shared across devices. SQLite schema 3 adds
preferences; archive/restore accepts schemas 2/3 without replacing originals.
See [upgrade and language checks](day-30-private-ai-service/LANGUAGES.ru.md).
Current validation: [229/229 offline checks](day-30-private-ai-service/reports/verified/languages-policy-v4-offline-20261011.json)
and [33/33 live HTTPS/Qwen checks on the Mac](day-30-private-ai-service/reports/verified/languages-policy-v4-live-mac-20261011.json).
Four live generations covered Russian/English replies with plain input and a RAG follow-up,
including user instructions asking for the opposite language. The operator also confirmed
language switching through the UI and phone use. This manual check is separate from the
JSON report; these examples do not guarantee the language of every possible answer.

After the course, **0.9.1** adds lexical RAG enabled by default in the Web UI over both sides of saved conversations,
owner-specific SQLite FTS5 caches, role/status-aware source links, original conversation windows and immutable RAG snapshots.
RAG was introduced with schema 2; schema 3 is documented above. No embedding model or
cloud LLM is used. See [history RAG setup and checks](day-30-private-ai-service/RAG_MEMORY.ru.md).
The 0.8.0 live evidence below is historical and does not prove 0.9.1 model quality.

[Day 30](day-30-private-ai-service/README.md) turns local Qwen into a private HTTP
service with multiple conversations, durable SQLite history and a responsive
Web UI. Mac, Android and iPhone can open the same conversation and continue it.
The PWA can be added to the phone's home screen.

The tested host is a **MacBook Pro M1 with 32 GB unified memory**. Ollama runs
Qwen2.5:14b Q4_K_M on localhost; FastAPI handles authentication, API v1, context
budgets, quotas and the durable queue. **No cloud LLM or automatic cloud fallback** is used. The accepted0.8.0 course
runtime used no RAG; the post-course0.9.1 Web UI enables history retrieval by default. Complete saved history is separate from the bounded
recent context sent to the model.

**Tailscale Serve** is the main private HTTPS route on home Wi-Fi and mobile data.
It requires Tailscale on the client, application login and an awake, connected
Mac. Its `.ts.net` URL needs no manually installed local CA. An optional **Caddy**
route provides direct LAN HTTPS; that route requires trusting your own CA.
Ollama and the API remain bound to localhost.

| Recorded evidence for runtime 0.8.0 / private-chat-v2 | Result |
|---|---|
| Real Mac API/Qwen baseline, including 10 sequential and 3 concurrent requests | 259/259 technical checks; 13/13 quality controls |
| Persisted history after API restart | 11/11; seven chats and 32 messages unchanged |
| Current LAN HTTPS / launchd check from the Mac | 6/6 |
| Offline / Chromium / PWA fixtures | 143/143; 26/26; 11/11 |
| Physical phone handoff and daily use | Android handoff 8/8; Mac/Android/iPhone sync and mobile access manually confirmed |

Concurrent API requests are queued; the model runs **one generation at a time**.
Fixture tests do not prove real network or model availability. Quality controls
cover the recorded examples, not arbitrary-answer reliability. Original successful
and failed reports are retained in the [final report](day-30-private-ai-service/FINAL_REPORT.ru.md).

From the root, with an active Python 3.13 virtualenv:

```bash
python -m pip install -r day-30-private-ai-service/requirements.lock
python day-30-private-ai-service/scripts/verify_report.py \
  day-30-private-ai-service/reports/verified/languages-policy-v4-offline-20261011.json
```

This verifies saved evidence against source hashes; it does not start the server.
Follow the [lesson README](day-30-private-ai-service/README.md) and
[Mac runbook](day-30-private-ai-service/RUNBOOK.ru.md) for installation, secure
login, phones, launchd and stopping the service before sleep. The user has recorded
a UI demonstration of cross-device chat; the
[console scenario](day-30-private-ai-service/CONSOLE_VIDEO.ru.md) is optional.

Working-history restore into a separate database was rehearsed on the operator's Mac.
Physical transfer, phone LAN CA setup and an independent audit of the saved tailnet
policy remain separate tasks. See the
[acceptance checklist](day-30-private-ai-service/ACCEPTANCE.ru.md) and
[backlog](day-30-private-ai-service/BACKLOG.ru.md). Rust is not implemented; a
separate API overhead benchmark is deferred until after the course.

Changing these root READMEs changes the Day 21 corpus fingerprint. Rebuild that
index before a new strict RAG live run; Day 30 and saved-report verification do
not use it. Earlier lesson implementations and historical JSON reports are preserved.

After Day 30, a separate [history portability extension](day-30-private-ai-service/MEMORY_PORTABILITY.ru.md)
adds verified backup and restoration into a new database. That first tool did not
change API runtime. The subsequent0.9.1 lexical RAG extension is described above;
semantic retrieval and versioned facts remain future work. The historical69/69
report covers storage only; the original 143/143 model/API fixture report retains its historical scope.

## Tests

The local test suites use fakes, scripted HTTP fixtures, local SQLite, or local MCP servers. They do not call paid cloud APIs unless a command explicitly performs a live model/API run.

```bash
python -m unittest discover -s day-10-context-strategies -p 'test_*.py' -v
python -m unittest discover -s day-11-memory-layers -p 'test_*.py' -v
python -m unittest discover -s day-12-personalization -p 'test_*.py' -v
python -m unittest discover -s day-13-task-state-machine -p 'test_*.py' -v
python -m unittest discover -s day-14-invariants -p 'test_*.py' -v
python -m unittest discover -s day-15-controlled-transitions -p 'test_*.py' -v
python day-16-mcp-connection/test_mcp_connection.py
python day-17-first-mcp-tool/test_day17.py -v
python day-18-scheduled-mcp/test_day18.py -v
python day-19-mcp-composition/test_day19.py -v
python day-20-mcp-orchestration/test_day20.py -v
python day-21-document-indexing/test_day21.py -v
python day-22-first-rag/test_day22.py -v
python day-23-reranking-filtering/test_day23.py -v
python day-24-citations-grounding/test_day24.py -v
python day-25-rag-chat/test_day25.py -v
python day-26-local-llm/test_day26.py -v
python -m unittest discover -s day-27-local-llm-integration/tests -v
python -m unittest discover -s day-28-local-rag -p 'test*28.py'
python day-29-local-llm-optimization/test_day29.py -v
python -m unittest discover -s day-29-local-llm-optimization/experiments/quality_v7 -p test_quality_v7.py -v
python -W error::ResourceWarning day-30-private-ai-service/scripts/check_storage.py
```

## Data and limitations

- Day 27 is a local, bypassable pre-commit check. It analyzes entire changed files without type resolution and does not replace KMP compilation, Android Lint or CI. Reviewer style affects explanations only.
- Generated SQLite databases, temporary reports, model outputs, and provider availability are environment-dependent. Day 28 keeps selected original JSON in `reports/accepted/` and audits in `reports/verified/`; working `reports/check/` and recording `reports/video/` are ignored.
- Day 18 worker output goes to stdout or a service journal; it does not automatically push a message back into a chat.
- Days 21–25 are local RAG experiments, not a hosted multi-user service.
- Day 25 is a local single-user CLI. It does not execute arbitrary user code or call external MCP tools from the chat.
- Stored memory is evidence-bound to user text, but literal provenance alone does not prove that a model interpreted the text correctly.
- Exact quotations prove source provenance, not semantic completeness. Live reports therefore retain an explicit manual-review requirement.
- Model names, provider limits, and pricing can change; check the relevant provider documentation when reproducing older lessons.

## Resources

- [Groq Console](https://console.groq.com/)
- [Ollama](https://ollama.com/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [GitHub REST API documentation](https://docs.github.com/en/rest)
