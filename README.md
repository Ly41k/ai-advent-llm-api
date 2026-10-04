**English** | [Русский](README.ru.md)

# AI Advent — from an LLM API request to MCP tools and retrieval-augmented answers

A day-by-day Python project built around the Groq API. The first lessons examine prompts, models, tokens, and context. Later lessons develop **BublikAgent** with SQLite-backed dialogues, explicit memory, personalization, task-state guards, MCP experiments, a shared local knowledge index, a first RAG workflow, query rewrite with relevance filtering, and answers with exact quotations, sources, and abstention. **Cheburator** is the captain of the research spacecraft; **Bublik** is the assistant that grows through the course.

Each `day-XX-...` directory is a self-contained lesson with English and Russian instructions. The repository currently contains **Days 1–24**. Examples from different days demonstrate successive designs; later lessons reuse selected components instead of automatically merging every previous agent version into one application.

## Learning path

| Day | Lesson | What it adds |
|---|---|---|
| [01](day-01-first-api-request/README.md) | First API request | Interactive Groq chat with in-session history |
| [02](day-02-response-control/README.md) | Response control | Structure, length, and explicit answer rules |
| [03](day-03-reasoning-methods/README.md) | Reasoning methods | Four approaches compared on the same task |
| [04](day-04-temperature/README.md) | Temperature | Compare factual consistency, creativity, and variability |
| [05](day-05-model-versions/README.md) | Model comparison | Quality, latency, token use, and estimated cost |
| [06](day-06-first-agent/README.md) | First agent | `BublikAgent`, console interface, and SQLite memory |
| [07](day-07-context-persistence/README.md) | Context persistence | Isolated dialogues recovered after a restart |
| [08](day-08-token-usage/README.md) | Token usage | Estimates, API usage, and approximate request cost |
| [09](day-09-context-compression/README.md) | Compression | Persisted summary plus recent full messages |
| [10](day-10-context-strategies/README.md) | Context strategies | Sliding Window, Sticky Facts, and Branching |
| [11](day-11-memory-layers/README.md) | Memory model | Short-term, task working, and long-term memory |
| [12](day-12-personalization/README.md) | Personalization | User profiles and profile-scoped context |
| [13](day-13-task-state-machine/README.md) | Task state machine | Persistent stage, progress, expected action, and pause |
| [14](day-14-invariants/README.md) | Invariants | Versioned policy and preflight/postflight semantic checks |
| [15](day-15-controlled-transitions/README.md) | Guarded transitions | Plan approval, stage guards, validation, and resume |
| [16](day-16-mcp-connection/README.md) | MCP connection | Local server and client, stdio handshake, tool discovery |
| [17](day-17-first-mcp-tool/README.md) | First MCP tool | GitHub tool invoked through the model's tool-calling loop |
| [18](day-18-scheduled-mcp/README.md) | Scheduled jobs | SQLite schedules, independent worker, stored snapshots, aggregate result |
| [19](day-19-mcp-composition/README.md) | Tool composition | Three MCP calls: fetch → summarize → save Markdown |
| [20](day-20-mcp-orchestration/README.md) | MCP orchestration | Model-selected, verified five-call flow across three servers |
| [21](day-21-document-indexing/README.md) | Document indexing | Shared SQLite knowledge base, two chunking strategies, local embeddings, retrieval comparison |
| [22](day-22-first-rag/README.md) | First RAG request | NO RAG vs RAG, retrieved context, source provenance, and a 10-question evaluation set |
| [23](day-23-reranking-filtering/README.md) | Relevance filtering and query rewrite | Candidate/final top-K, raw cosine threshold, heuristic/LLM rewrite, calibration, and four-mode comparison |
| [24](day-24-citations-grounding/README.md) | Citations and grounding | Exact source passages, validated citations, coverage policies, and abstention with clarification |

## How the pieces fit

- **Days 1–5:** compare API parameters, reasoning prompts, models, and their measured output.
- **Days 6–10:** separate agent logic from the CLI, persist dialogues in SQLite, and manage the context/token budget.
- **Days 11–15:** add memory layers, user profiles, a task state machine, invariant checks, and guarded task transitions. Day 15 requires an approved plan before execution and successful validation before `done`.
- **Day 16:** use the Python MCP SDK to discover `ping` and `add` from a local stdio server.
- **Day 17:** register `get_github_repo(owner, repo)`; the focused `BublikMcpAgent` exposes its schema to the Groq model, executes the model-selected MCP call, and returns the result to the model.
- **Day 18:** an MCP tool stores a periodic GitHub job in SQLite. A separate worker runs due jobs and saves snapshots; another tool returns an aggregate of those snapshots. The worker needs a separate long-running process for unattended operation.
- **Day 19:** `BublikPipelineAgent` deterministically invokes `search_repository`, `summarize_repository`, and `save_report` in order. It passes each complete MCP result to the next call and stops on error. The summary itself does not call an LLM.
- **Day 20:** three stdio MCP servers expose five namespaced tools. The model selects calls, while the agent checks arguments and ordering, reads the saved report back, and verifies it.
- **Day 21:** index README and code with a local embedding model into SQLite; compare fixed and structural chunks on a shared question set. Optional search, reranking, and local answers build on the same knowledge base.
- **Day 22:** reuse the Day 21 index for the first full RAG request. The same generation model answers once without retrieval and once with retrieved chunks, while source provenance and a 10-question control set make the comparison reproducible.

- **Day 23:** reuse the same index and Ollama adapter, expand the search query, filter candidate chunks by an inclusive raw cosine threshold, and cap the final context. Compare `baseline`, `filter`, `rewrite`, and `rewrite_filter`; choose a threshold on calibration questions and inspect a separate evaluation split.

- **Day 24:** select exact passages from the retrieved chunks, validate their citations, audit coverage, and refuse weak context with a clarification request. Strict mode gates publication on model coverage; explicit diagnostic mode preserves audit failures for manual review.

The MCP servers in Days 16–20 communicate with local clients over **stdio**. Days 17–20 also use the public GitHub REST API to fetch live data. Only the scheduled worker in Day 18 needs an always-running process for continuous observation. Days 21–23 run locally with Ollama by default: `bge-m3` provides embeddings and `llama3.2` generates answers. Day 24 uses `bge-m3` and `qwen2.5:14b` by default for extractive answers and coverage auditing.

## Requirements and setup

- Python **3.13** is the project's target version.
- A Groq key is needed for interactive Groq examples, including the model-driven applications in Days 17–18. The Day 16 connection, Day 19 pipeline, Day 20 offline checks, and the local Day 21–24 Ollama flow do not need one.
- Internet access is needed when calling Groq or fetching live public GitHub data. `GITHUB_TOKEN` is optional for public repositories and can help with GitHub API rate limits.
- Days 21–23 use a local Ollama service by default. Pull `bge-m3` for embeddings and `llama3.2` for local answer generation before the live retrieval/RAG demos. The Day 23 exploratory profile uses `qwen2.5:7b` through explicit `--answer-model` flags; the code default remains `llama3.2`. Day 24 uses `qwen2.5:14b` by default; its reviewed live environment is a Mac M1 with 32 GB RAM. Days 21–24 use the Python standard library for the base workflow; an optional cross-encoder needs `sentence-transformers`.

Run from the repository root:

```bash
git clone https://github.com/Ly41k/ai-advent-llm-api.git
cd ai-advent-llm-api
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, activate the environment with `.venv\Scripts\activate`. If `python3.13` is not the name of your Python 3.13 executable, use its local command instead.

The root `requirements.txt` contains the Groq, dotenv, and tokenizer dependencies used in earlier lessons. Install the **specific day's** additional dependencies before running an MCP lesson:

```bash
python -m pip install -r day-19-mcp-composition/requirements.txt
```

Replace `day-19-mcp-composition` with `day-20-mcp-orchestration`, `day-16-mcp-connection`, `day-17-first-mcp-tool`, or `day-18-scheduled-mcp` for those lessons.

For the local retrieval/RAG lessons, install and start Ollama, then pull the default models:

```bash
ollama pull bge-m3
ollama pull llama3.2
# Additional model used in the documented Day 23 live experiments:
ollama pull qwen2.5:7b
# Day 24 default for passage selection and coverage auditing:
ollama pull qwen2.5:14b
```

If the Ollama desktop app is already serving locally, a separate `ollama serve` process is not required.

For Groq programs, copy `.env.example` to a root-level `.env` and set `GROQ_API_KEY` there. The `.env` file is ignored by Git. Keep credentials out of commits and recordings.

## Run the examples

From the root, Days 1–15 each have a `main.py` in their lesson directory. For example:

```bash
python day-01-first-api-request/main.py
python day-15-controlled-transitions/main.py
```

The later lessons have different entry points:

| Day | Command from the repository root | What to expect |
|---|---|---|
| 16 | `python day-16-mcp-connection/client.py` | Discover `ping` and `add`; no key or network |
| 17 | `python day-17-first-mcp-tool/demo.py` | Real GitHub call and deterministic agent demo; no Groq key |
| 17 | `python day-17-first-mcp-tool/main.py` | Interactive Groq-driven MCP tool selection |
| 18 | `python day-18-scheduled-mcp/worker.py` and `python day-18-scheduled-mcp/main.py` in separate terminals | Periodic worker plus interactive Groq agent |
| 19 | `python day-19-mcp-composition/main.py Ly41k ai-advent-llm-api` | One command executes three MCP tools and writes a report |
| 20 | `python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api --offline` | Five calls across three MCP servers; no Groq key |
| 21 | `python day-21-document-indexing/main.py corpus` then `build` | Local Ollama embeddings, two indexes in SQLite, reusable knowledge base |
| 22 | `python day-22-first-rag/main.py compare "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?"` | Same question answered without RAG and with retrieved Day 21 context |
| 22 | `python day-22-first-rag/main.py evaluate` | Run all 10 control questions and write `evaluation_results.json` |
| 23 | `python day-23-reranking-filtering/main.py questions` | Inspect 20 labeled questions: 8 calibration and 12 evaluation |
| 23 | `python day-23-reranking-filtering/main.py compare "How does the Day 18 worker run?" --retrieval-only` | Inspect four retrieval modes with the CLI defaults |
| 24 | `python day-24-citations-grounding/main.py questions` | Inspect 10 positive questions and 2 negative controls |
| 24 | `python day-24-citations-grounding/console_demo.py` | Replay the reviewed run, quotations, source checks, and refusals in the console |
| 24 | `python day-24-citations-grounding/console_demo.py --live` | New local Ollama run; new answers require their own manual review |

For a **Day 18 check without Groq**, use `mcp_cli.py` to create a schedule, run due work once, and read its stored summary:

```bash
python day-18-scheduled-mcp/mcp_cli.py schedule Ly41k ai-advent-llm-api 60
python day-18-scheduled-mcp/worker.py --once
python day-18-scheduled-mcp/mcp_cli.py summary Ly41k ai-advent-llm-api
```

For Day 19, inspect `day-19-mcp-composition/reports/Ly41k-ai-advent-llm-api-summary.md` after the run. Set `BUBLIK_REPORT_DIR` if you need a different output directory. The [Day 18 verification guide](day-18-scheduled-mcp/VERIFY.ru.md) covers worker and VPS checks; [Day 19 instructions](day-19-mcp-composition/README.md) explain the automatic pipeline.

For Day 22, build the Day 21 knowledge base once before a live RAG run if `day-21-document-indexing/knowledge.db` does not exist:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
python day-22-first-rag/main.py questions
python day-22-first-rag/main.py compare \
  "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?"
python day-22-first-rag/main.py evaluate
```

## Day 23: search, filter, rewrite, and answer

All Day 23 global flags go **before** the subcommand. This example explicitly uses the exploratory profile, rather than the CLI defaults:

```bash
python day-23-reranking-filtering/main.py \
  --model bge-m3 --answer-model qwen2.5:7b \
  --strategy fixed --candidate-k 20 --final-k 5 \
  --min-similarity 0.50 --rewrite-method heuristic \
  compare "На 18 дне кто выполняет фоновые джобы по расписанию?" \
  --output day-23-reranking-filtering/reports/check/compare.json
```

Add `--retrieval-only` after the question to inspect retrieval without generating answers. `search` also skips the final answer; `ask --mode rewrite_filter` runs one mode. With `--rewrite-method llm`, a model call for rewrite still occurs even in retrieval-only commands. An empty selected context returns a deterministic refusal without an answer-model call.

For a new index, calibrate first and apply its selected threshold explicitly:

```bash
python day-23-reranking-filtering/main.py \
  --strategy fixed --candidate-k 20 --final-k 5 \
  --rewrite-method heuristic \
  calibrate --thresholds 0.15 0.25 0.35 0.45 0.50 0.55 0.65 \
  --output day-23-reranking-filtering/reports/check/calibrate.json

# Example only: replace 0.55 with selected_threshold from your calibration.
python day-23-reranking-filtering/main.py \
  --answer-model qwen2.5:7b --strategy fixed \
  --candidate-k 20 --final-k 5 --min-similarity 0.55 \
  --rewrite-method heuristic \
  evaluate --split evaluation \
  --output day-23-reranking-filtering/reports/check/evaluate.json
```

`evaluate` writes JSON traces and a Markdown summary for all four modes. The recorded fixed/20/5/0.50 experiment increased labeled source precision from 28.0% to 37.3% and reduced average context from 2007.8 to 1393.3 words, preserving document hits on 10/10 positive questions. This is an exploratory result on an already inspected evaluation set: some generated answers remain wrong, and rewrite did not improve every metric. See [Day 23](day-23-reranking-filtering/README.md) for defaults, metrics, report publication, and limitations.

## Day 24: grounded answers

The current `verbatim-extractive-v14` workflow selects exact source passages and constructs validated `source`, `section`, `chunk_id`, line bounds, and quotations. Its defaults are `bge-m3` / `qwen2.5:14b`, fixed chunks, 20 candidates, 5 final chunks, inclusive cosine `>= 0.50`, and heuristic rewrite. Weak context returns “I don't know” with a clarification request and empty evidence.

`strict` is the default: publication requires positive model coverage as well as valid source evidence. Explicit `diagnostic` mode can publish exact validated passages despite a negative coverage verdict; the verdict stays negative and manual review is required. A source-contract pass does not establish answer completeness.

```bash
python day-24-citations-grounding/test_day24.py -v
python day-24-citations-grounding/test_console_demo.py -v
python day-24-citations-grounding/console_demo.py
```

The last command replays saved real reports with Enter pauses and repeats source/quote checks; it does not call Ollama. For a new live run, first build and verify the Day 21 index in the final checkout, then run:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
python day-24-citations-grounding/console_demo.py --live
```

For a JSON/Markdown evaluation report with the same explicit diagnostic policy:

```bash
python day-24-citations-grounding/main.py --coverage-policy diagnostic \
  evaluate --output day-24-citations-grounding/reports/check/evaluate.json
```

The recorded full v14 run has 10/10 answers with sources and quotations, 53/53 exact quotations, and 2/2 correct negative-control refusals. Model coverage is **7/10**, while subsequent assistant source review confirms meaning and completeness for **10/10**. This is one reviewed diagnostic run, not independent human review or strict-model coverage 10/10. New runs retain `assignment_complete=false` until their own review. See the [Day 24 instructions](day-24-citations-grounding/README.md) and [recorded review](day-24-citations-grounding/reports/live/REVIEW_evaluate_v14.ru.md).

## Tests

Install each lesson's dependencies before its tests. These local tests use fakes or a local HTTP server and do **not** spend Groq tokens or require a live GitHub request:

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
python day-24-citations-grounding/test_console_demo.py -v
```

Day 19 tests assert MCP tool discovery, call order, **exact input/output transfer** at both boundaries, persisted report content, replacement on a second run, and failure handling. The full command-line run is also exercised. The live GitHub run is a separate manual check. Day 20 tests launch three real servers and verify routing, order, input/output transfer, readback, and failure handling; model behavior with Groq needs a separate keyed run. Day 22 offline tests verify that NO RAG does not call retrieval, RAG follows `question → search → context → LLM`, both A/B paths use the same question, and the control set contains exactly 10 complete records.

The Days 21–23 suites contain 7, 6, and 21 tests (34 total in the reviewed version). Day 23 tests cover inclusive thresholding before final-K, shared candidate pools, empty-context refusal without generation, rewrite/fallback, calibration split separation, and the CLI/HTTP/SQLite/report path. A local HTTP fixture verifies the Ollama contract; these tests do not establish real-model answer quality.

Day 24 has 116 core tests and 19 console demonstration tests (135 total). They cover evidence bindings, coverage policies, refusals, errors, and saved-report presentation. These use Ollama stand-ins and do not establish live-model quality.

## Data and limitations

- SQLite data from earlier lessons and Day 18 schedules/snapshots remain local. Day 18's default database is `day-18-scheduled-mcp/schedule.db`; `BUBLIK_DB_PATH` can point both the worker and client to a shared alternative.
- Day 18 prints completed worker results to stdout or the service journal. It does not automatically send a chat message. Its sample systemd unit supports running a worker continuously on a VPS.
- Day 19 writes a Markdown snapshot of current repository metadata to its ignored `reports/` directory. It does not run periodically and does not require a VPS.
- Day 20 saves and rereads a report in its ignored `reports/` directory. It runs on demand; no VPS is needed.
- Days 21–24 share the ignored `day-21-document-indexing/knowledge.db`. The corpus includes root READMEs, lesson READMEs from Days 1–20, and non-test Python files from Days 16–20. Day 21–24 lesson READMEs and reports are excluded; **root README changes still change the corpus**. `verify` compares both the Git HEAD and a content fingerprint, so a new commit can also require a rebuild. Build both strategies in the final checkout before strict verification.
- Day 22 reuses the Day 21 index instead of creating a second knowledge base. `evaluate` writes the ignored `day-22-first-rag/evaluation_results.json` with both answers, retrieved sources, expected-term coverage, and source-hit diagnostics. These diagnostics help comparison but do not replace human review of answer correctness.
- Day 23 uses document-level retrieval labels, not passage-level semantic judgments. `negative_abstention_rate` counts empty contexts, not every verbal refusal by a model; expected-term coverage is not answer accuracy.
- Day 23 `reports/check/` and `reports/video/` are ignored. Keep selected final evidence under `reports/live/` with names such as `evaluate_050.json` and `.md`. The current `*_results.json` / `*_results.md` rules also match nested paths. The reviewed commit contains live verification summaries, provenance, and an assistant review, but not the original live `*_results` files.
- Day 24 ignores new `reports/check/` output and packaging/test logs. Keep the final v14 reports, console replay data, and whitelisted historical regression fixtures. Exact text provenance does not guarantee relevance, completeness, or source truth.
- Generated model answers, available Groq/Ollama models, limits, and cost estimates may change. Check the relevant provider documentation before relying on model names or pricing.

## Resources

- [Groq Console](https://console.groq.com/)
- [Ollama](https://ollama.com/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [GitHub REST API documentation](https://docs.github.com/en/rest)
