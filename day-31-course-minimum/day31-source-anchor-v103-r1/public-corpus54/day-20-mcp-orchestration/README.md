# Day 20 — Orchestrating multiple MCP servers

Bublik launches three independent stdio MCP servers: `github` (`get_repository_info`), `analysis` (`summarize_repository`, `verify_report`), and `storage` (`save_report`, `read_report`). The registry discovers tools and routes each selected call to the correct server session. The model sees short operation codes such as `FETCH` and `READ` and selects one via strict JSON, for example `{"operation":"READ"}`. The agent maps it to the discovered MCP route and supplies exact validated inputs from prior results. Native Groq `tool_calls` and model-generated report arguments are not required. Real input schemas remain available in the registry and are enforced by the servers.

```text
github.get_repository_info → analysis.summarize_repository
→ storage.save_report → storage.read_report → analysis.verify_report → answer
```

The final verification compares the report read from disk with the original summary. Each pending selection uses strict JSON Schema with an enum of operation codes. If Groq returns HTTP 400 `tool_use_failed`, the agent picks the next guarded step and labels it `agent fallback`. If the model selects a premature step, the agent executes the valid next step and labels it `agent correction`. Neither step can be counted as model selected. The agent forms the final answer from verified MCP results without a sixth model request. Invalid JSON and MCP failures stop the flow; the agent only reports success after `verified=true`.

The user task selects the required subset: `--task info` uses GitHub only, `--task summary` uses GitHub and analysis, and the default `--task report` completes all five calls. The model selects each tool call and the agent enforces the dependencies.

## Local setup and tests

Run from the extracted repository root (Python 3.13 recommended, 3.10+ supported):

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r day-20-mcp-orchestration/requirements.txt
.venv/bin/python day-20-mcp-orchestration/test_day20.py -v
```

On Windows replace `.venv/bin/python` with `.venv\\Scripts\\python`. Tests launch all three real MCP subprocesses, use a fake local GitHub HTTP API, check model-selected tool routing, exact data transfer, five calls in order, file content, invalid calls, and failure handling. No API key is required for tests.

For a live GitHub request using an offline deterministic model stand-in:

```bash
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api --offline
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api --offline --task info
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api --offline --task summary
```

For **real model-selected calls**, set `GROQ_API_KEY` in the environment or root `.env` and omit `--offline`:

```bash
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api
```

This makes Groq and GitHub requests. `GITHUB_TOKEN` is optional for public GitHub repositories. The output file is under `day-20-mcp-orchestration/reports/`, or under `BUBLIK_REPORT_DIR` if set. The scripted offline mode validates real MCP transport and routing but does not establish the reliability of live Groq tool selection; use the second command for that check. See [Russian instructions](README.ru.md) for a requirement-by-requirement checklist.
