**English** | [Русский](README.ru.md)

# AI Advent — from an LLM API request to an agent with MCP tools

A day-by-day Python project built around the Groq API. The first lessons examine prompts, models, tokens, and context. Later lessons develop **BublikAgent** with SQLite-backed dialogues, explicit memory, personalization, task-state guards, and separate MCP experiments. **Cheburator** is the captain of the research spacecraft; **Bublik** is the assistant that grows through the course.

Each `day-XX-...` directory is a self-contained lesson with English and Russian instructions. The repository currently contains **Days 1–19**. Examples from different days demonstrate successive designs; Day 19 does not replace or automatically merge the earlier agents into one application.

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

## How the pieces fit

- **Days 1–5:** compare API parameters, reasoning prompts, models, and their measured output.
- **Days 6–10:** separate agent logic from the CLI, persist dialogues in SQLite, and manage the context/token budget.
- **Days 11–15:** add memory layers, user profiles, a task state machine, invariant checks, and guarded task transitions. Day 15 requires an approved plan before execution and successful validation before `done`.
- **Day 16:** use the Python MCP SDK to discover `ping` and `add` from a local stdio server.
- **Day 17:** register `get_github_repo(owner, repo)`; the focused `BublikMcpAgent` exposes its schema to the Groq model, executes the model-selected MCP call, and returns the result to the model.
- **Day 18:** an MCP tool stores a periodic GitHub job in SQLite. A separate worker runs due jobs and saves snapshots; another tool returns an aggregate of those snapshots. The worker needs a separate long-running process for unattended operation.
- **Day 19:** `BublikPipelineAgent` deterministically invokes `search_repository`, `summarize_repository`, and `save_report` in order. It passes each complete MCP result to the next call and stops on error. The summary itself does not call an LLM.

The MCP servers in Days 16–19 communicate with local clients over **stdio**. Days 17–19 also use the public GitHub REST API to fetch live data. Only the scheduled worker in Day 18 needs an always-running process for continuous observation; the Day 19 pipeline runs on demand.

## Requirements and setup

- Python **3.13** is the project's target version.
- A Groq key is needed for interactive Groq examples, including the model-driven applications in Days 17–18. The Day 16 connection, Day 19 pipeline, and offline tests do not need one.
- Internet access is needed when calling Groq or fetching live public GitHub data. `GITHUB_TOKEN` is optional for public repositories and can help with GitHub API rate limits.

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

Replace `day-19-mcp-composition` with `day-16-mcp-connection`, `day-17-first-mcp-tool`, or `day-18-scheduled-mcp` for those lessons.

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

For a **Day 18 check without Groq**, use `mcp_cli.py` to create a schedule, run due work once, and read its stored summary:

```bash
python day-18-scheduled-mcp/mcp_cli.py schedule Ly41k ai-advent-llm-api 60
python day-18-scheduled-mcp/worker.py --once
python day-18-scheduled-mcp/mcp_cli.py summary Ly41k ai-advent-llm-api
```

For Day 19, inspect `day-19-mcp-composition/reports/Ly41k-ai-advent-llm-api-summary.md` after the run. Set `BUBLIK_REPORT_DIR` if you need a different output directory. The [Day 18 verification guide](day-18-scheduled-mcp/VERIFY.ru.md) covers worker and VPS checks; [Day 19 instructions](day-19-mcp-composition/README.md) explain the automatic pipeline.

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
```

Day 19 tests assert MCP tool discovery, call order, **exact input/output transfer** at both boundaries, persisted report content, replacement on a second run, and failure handling. The full command-line run is also exercised. The live GitHub run is a separate manual check.

## Data and limitations

- SQLite data from earlier lessons and Day 18 schedules/snapshots remain local. Day 18's default database is `day-18-scheduled-mcp/schedule.db`; `BUBLIK_DB_PATH` can point both the worker and client to a shared alternative.
- Day 18 prints completed worker results to stdout or the service journal. It does not automatically send a chat message. Its sample systemd unit supports running a worker continuously on a VPS.
- Day 19 writes a Markdown snapshot of current repository metadata to its ignored `reports/` directory. It does not run periodically and does not require a VPS.
- Generated model answers, available Groq models, limits, and cost estimates may change. Check [Groq's current documentation](https://console.groq.com/docs) before relying on model names or pricing.

## Resources

- [Groq Console](https://console.groq.com/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [GitHub REST API documentation](https://docs.github.com/en/rest)
