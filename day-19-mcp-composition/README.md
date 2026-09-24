# Day 19 — MCP tool composition

One command runs three separate MCP tools over stdio: `search_repository(owner, repo)` fetches public GitHub metadata, `summarize_repository(repository)` converts the exact result into Markdown, and `save_report(summary)` writes the exact summary to disk. `BublikPipelineAgent.run()` verifies discovery, calls tools in order, and stops on error. No Groq key or VPS is needed; the summary is deterministic.

From the repository root (Python 3.13 recommended):

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r day-19-mcp-composition/requirements.txt
.venv/bin/python day-19-mcp-composition/test_day19.py -v
.venv/bin/python day-19-mcp-composition/main.py Ly41k ai-advent-llm-api
```

Tests use a real MCP stdio connection and a local fake GitHub API, so they need no key or GitHub connection. The demo requires access to `api.github.com`; `GITHUB_TOKEN` is optional for public repositories. The output file is `day-19-mcp-composition/reports/Ly41k-ai-advent-llm-api-summary.md` by default. Set `BUBLIK_REPORT_DIR` to change its directory. See [README.ru.md](README.ru.md) for the detailed assignment checklist.
