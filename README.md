**English** | [Русский](README.ru.md)

# AI Advent — from an LLM API request to MCP, grounded RAG and local applications

A day-by-day Python learning project that starts with direct LLM API calls and grows into agents, persistent state, MCP tools, document indexing, retrieval-augmented generation, grounded citations, a persistent RAG chat with task memory, and a local Kotlin pre-commit review application.

**Cheburator** is the captain of the research spacecraft; **Bublik** is the assistant that evolves through the course. **Revik**, introduced on Day 27, is a separate local code review assistant for Kotlin projects.

The repository currently contains **Days 1–27**. Each `day-XX-...` directory is a self-contained lesson with English and Russian documentation. Later lessons reuse selected components from earlier days instead of merging every historical implementation into one application.

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

The MCP servers in Days 16–20 communicate with local clients over **stdio**. Days 17–20 can call the public GitHub REST API. Only the Day 18 worker needs a continuously running process for unattended schedules.

Days 21–25 use the shared Day 21 knowledge index. Day 25 does not treat earlier assistant answers or remembered task facts as repository evidence: they help resolve intent, while the current answer is grounded in fresh retrieval.

## Requirements

- Python **3.13** is the project target.
- A Groq key is required only by lessons that explicitly call Groq.
- Internet access is required for Groq and live GitHub API calls.
- Local retrieval/RAG lessons and Days 26–27 use **Ollama**.
- Day 27 additionally needs Git, a compatible JDK and Detekt CLI; its Python module has no extra pip dependencies. Its documented hook workflow targets macOS/Linux.
- `GITHUB_TOKEN` is optional for public GitHub repositories and can help with rate limits.

### Local models

| Lessons | Embeddings | Generation |
|---|---|---|
| 21–22 | `bge-m3` | `llama3.2` in the documented base flow |
| 23 | `bge-m3` | `llama3.2` by default; `qwen2.5:7b` in documented experiments |
| 24–25 | `bge-m3` | `qwen2.5:14b` in the current grounded/live profile |
| 26 | Not required | `qwen2.5:7b` default; `qwen2.5:14b` in the verified run |
| 27 | Not required | `qwen2.5:14b` default; configurable downloaded local model |

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

You do not need all answer models at once; the commands above simply cover the documented profiles through Day 27.

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

## Day 21 shared knowledge index

Days 21–25 reuse:

```text
day-21-document-indexing/knowledge.db
```

The indexed corpus rule remains intentionally narrow:

- root `README.md` and `README.ru.md`;
- lesson READMEs from Days 1–20;
- non-test Python files from Days 16–20.

README files from Days 21–27 are not automatically added to that corpus. Days 26–27 do not use this index.

The index stores a repository/corpus revision. A new commit or a change to the **root README files** can make an existing index stale. After updating the root README, rebuild before strict verification or a Day 24/25 live run:

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

## Tests

The local test suites use fakes, scripted HTTP fixtures, local SQLite, or local MCP servers. They do not spend Groq tokens unless a command explicitly performs a live model/API run.

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
```

## Data and limitations

- Day 27 is a local, bypassable pre-commit check. It analyzes entire changed files without type resolution and does not replace KMP compilation, Android Lint or CI. Reviewer style affects explanations only.
- Generated SQLite databases, temporary reports, model outputs, and provider availability are environment-dependent.
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

