This Markdown view was generated from the unchanged original JSON. Scoped manual review is in ../../review/manual-review.json.

# Day 29 — local LLM optimization / V1

State: completed; series: v1; split: all

Reused rows retain their original timestamps and measurements. Heuristic quality requires manual review.
Warmups and one-token input probes are accounted separately. Application refusals are excluded from generation speed.

| Profile | Quality / present | Valid / planned | Reused | Median seconds | Decode tokens/s | Max sampled RSS GiB |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 15/15 | 15/15 | 3 | 26.67 | 11.20 | 0.11 |
| focused-v3-q4 | 12/15 | 15/15 | 3 | 6.09 | 11.51 | 0.08 |

RSS is a sampled sum, not unique physical memory; do not add it to VRAM on Apple Silicon.
Detailed raw outputs, prompts, sources, context checks, process samples and attempt history are in the JSON.

## baseline / base-07 / 1

Status: ok; reused: True

Bublik schedules periodic public GitHub repository observations through MCP. An independent worker polls due jobs, stores snapshots in SQLite and writes an aggregate summary to stdout after each run.
The `worker.py` collects `stars`, `forks`, and `open_issues` using the GitHub REST API, storing snapshots and failures in SQLite.
Install dependencies on the VPS, edit `bublik-day18.service.example` with the actual user and paths, copy it to `/etc/systemd/system/bublik-day18.service`, and run: `sudo systemctl daemon-reload`, `sudo systemctl enable --now bublik-day18`, `sudo systemctl status bublik-day18`, `journalctl -u bublik-day18 -f`
The worker needs outbound access to `api.github.com`, but does not need a Groq key. `GITHUB_TOKEN` is optional for public repositories.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-18-scheduled-mcp/README.md / README.md

# Day 18 — Scheduled MCP jobs

[Step-by-step verification (Russian)](VERIFY.ru.md) covers local checks and VPS deployment.

Bublik schedules periodic public GitHub repository observations through MCP. An independent worker polls due jobs, stores snapshots in SQLite and writes an aggregate summary to stdout after each run. The agent can read the persisted summary via MCP and include it in its reply.

Source: day-18-scheduled-mcp/README.md / README.md

## Components

- `schedule_github_summary(owner, repo, interval_minutes)` creates or updates a recurring job (1–10080 minutes), due immediately.
- `worker.py` collects `stars`, `forks`, and `open_issues` using the GitHub REST API, storing snapshots and failures in SQLite. Failures retry on the next interval.
- `get_github_summary(owner, repo, limit)` returns the most recent values and changes since the oldest of the selected samples.
- `list_scheduled_jobs()` shows next run times and errors.
- `main.py` connects the Groq agent to those MCP tools.

The ignored `schedule.db` persists across restarts. All timestamps are UTC. After downtime, an overdue job runs once rather than replaying every missed interval. Run a single worker process. The worker outputs summaries to stdout or the systemd journal; it does not push messages to a chat.

Source: day-18-scheduled-mcp/README.md / README.md

## VPS

Install dependencies on the VPS, edit `bublik-day18.service.example` with the actual user and paths, copy it to `/etc/systemd/system/bublik-day18.service`, and run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bublik-day18
sudo systemctl status bublik-day18
journalctl -u bublik-day18 -f
```

Create the schedule via `main.py` on that VPS or another MCP client sharing the same database. The worker needs outbound access to `api.github.com`, but does not need a Groq key. `GITHUB_TOKEN` is optional for public repositories. Verify the actual VPS deployment separately with `systemctl` and `journalctl`.

Source: day-18-scheduled-mcp/README.md / README.md

## Assignment checklist

| Requirement | Implementation | Verification |
|---|---|---|
| Periodic MCP tool | `schedule_github_summary` plus worker | MCP integration test |
| Save data | SQLite `jobs`, `snapshots`, `runs` | Restart test |
| Scheduled execution | `next_run`, polling loop, systemd unit | Two executions with controlled time |
| Aggregate result | `get_github_summary` | Latest values, deltas and agent reply test |
| 24/7 operation | Worker supervised by systemd | Verify on the target VPS with systemctl, journalctl, service restart and host reboot |

## baseline / base-07 / 2

Status: ok; reused: True

Bublik schedules periodic public GitHub repository observations through MCP. An independent worker polls due jobs, stores snapshots in SQLite and writes an aggregate summary to stdout after each run.
The `worker.py` collects `stars`, `forks`, and `open_issues` using the GitHub REST API, storing snapshots and failures in SQLite.
Install dependencies on the VPS, edit `bublik-day18.service.example` with the actual user and paths, copy it to `/etc/systemd/system/bublik-day18.service`, and run: `sudo systemctl daemon-reload`, `sudo systemctl enable --now bublik-day18`, `sudo systemctl status bublik-day18`, `journalctl -u bublik-day18 -f`
The worker needs outbound access to `api.github.com`, but does not need a Groq key. `GITHUB_TOKEN` is optional for public repositories.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-18-scheduled-mcp/README.md / README.md

# Day 18 — Scheduled MCP jobs

[Step-by-step verification (Russian)](VERIFY.ru.md) covers local checks and VPS deployment.

Bublik schedules periodic public GitHub repository observations through MCP. An independent worker polls due jobs, stores snapshots in SQLite and writes an aggregate summary to stdout after each run. The agent can read the persisted summary via MCP and include it in its reply.

Source: day-18-scheduled-mcp/README.md / README.md

## Components

- `schedule_github_summary(owner, repo, interval_minutes)` creates or updates a recurring job (1–10080 minutes), due immediately.
- `worker.py` collects `stars`, `forks`, and `open_issues` using the GitHub REST API, storing snapshots and failures in SQLite. Failures retry on the next interval.
- `get_github_summary(owner, repo, limit)` returns the most recent values and changes since the oldest of the selected samples.
- `list_scheduled_jobs()` shows next run times and errors.
- `main.py` connects the Groq agent to those MCP tools.

The ignored `schedule.db` persists across restarts. All timestamps are UTC. After downtime, an overdue job runs once rather than replaying every missed interval. Run a single worker process. The worker outputs summaries to stdout or the systemd journal; it does not push messages to a chat.

Source: day-18-scheduled-mcp/README.md / README.md

## VPS

Install dependencies on the VPS, edit `bublik-day18.service.example` with the actual user and paths, copy it to `/etc/systemd/system/bublik-day18.service`, and run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bublik-day18
sudo systemctl status bublik-day18
journalctl -u bublik-day18 -f
```

Create the schedule via `main.py` on that VPS or another MCP client sharing the same database. The worker needs outbound access to `api.github.com`, but does not need a Groq key. `GITHUB_TOKEN` is optional for public repositories. Verify the actual VPS deployment separately with `systemctl` and `journalctl`.

Source: day-18-scheduled-mcp/README.md / README.md

## Assignment checklist

| Requirement | Implementation | Verification |
|---|---|---|
| Periodic MCP tool | `schedule_github_summary` plus worker | MCP integration test |
| Save data | SQLite `jobs`, `snapshots`, `runs` | Restart test |
| Scheduled execution | `next_run`, polling loop, systemd unit | Two executions with controlled time |
| Aggregate result | `get_github_summary` | Latest values, deltas and agent reply test |
| 24/7 operation | Worker supervised by systemd | Verify on the target VPS with systemctl, journalctl, service restart and host reboot |

## baseline / base-07 / 3

Status: ok; reused: True

Bublik schedules periodic public GitHub repository observations through MCP. An independent worker polls due jobs, stores snapshots in SQLite and writes an aggregate summary to stdout after each run.
The `worker.py` collects `stars`, `forks`, and `open_issues` using the GitHub REST API, storing snapshots and failures in SQLite.
Install dependencies on the VPS, edit `bublik-day18.service.example` with the actual user and paths, copy it to `/etc/systemd/system/bublik-day18.service`, and run: `sudo systemctl daemon-reload`, `sudo systemctl enable --now bublik-day18`, `sudo systemctl status bublik-day18`, `journalctl -u bublik-day18 -f`
The worker needs outbound access to `api.github.com`, but does not need a Groq key. `GITHUB_TOKEN` is optional for public repositories.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-18-scheduled-mcp/README.md / README.md

# Day 18 — Scheduled MCP jobs

[Step-by-step verification (Russian)](VERIFY.ru.md) covers local checks and VPS deployment.

Bublik schedules periodic public GitHub repository observations through MCP. An independent worker polls due jobs, stores snapshots in SQLite and writes an aggregate summary to stdout after each run. The agent can read the persisted summary via MCP and include it in its reply.

Source: day-18-scheduled-mcp/README.md / README.md

## Components

- `schedule_github_summary(owner, repo, interval_minutes)` creates or updates a recurring job (1–10080 minutes), due immediately.
- `worker.py` collects `stars`, `forks`, and `open_issues` using the GitHub REST API, storing snapshots and failures in SQLite. Failures retry on the next interval.
- `get_github_summary(owner, repo, limit)` returns the most recent values and changes since the oldest of the selected samples.
- `list_scheduled_jobs()` shows next run times and errors.
- `main.py` connects the Groq agent to those MCP tools.

The ignored `schedule.db` persists across restarts. All timestamps are UTC. After downtime, an overdue job runs once rather than replaying every missed interval. Run a single worker process. The worker outputs summaries to stdout or the systemd journal; it does not push messages to a chat.

Source: day-18-scheduled-mcp/README.md / README.md

## VPS

Install dependencies on the VPS, edit `bublik-day18.service.example` with the actual user and paths, copy it to `/etc/systemd/system/bublik-day18.service`, and run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bublik-day18
sudo systemctl status bublik-day18
journalctl -u bublik-day18 -f
```

Create the schedule via `main.py` on that VPS or another MCP client sharing the same database. The worker needs outbound access to `api.github.com`, but does not need a Groq key. `GITHUB_TOKEN` is optional for public repositories. Verify the actual VPS deployment separately with `systemctl` and `journalctl`.

Source: day-18-scheduled-mcp/README.md / README.md

## Assignment checklist

| Requirement | Implementation | Verification |
|---|---|---|
| Periodic MCP tool | `schedule_github_summary` plus worker | MCP integration test |
| Save data | SQLite `jobs`, `snapshots`, `runs` | Restart test |
| Scheduled execution | `next_run`, polling loop, systemd unit | Two executions with controlled time |
| Aggregate result | `get_github_summary` | Latest values, deltas and agent reply test |
| 24/7 operation | Worker supervised by systemd | Verify on the target VPS with systemctl, journalctl, service restart and host reboot |

## focused-v3-q4 / base-07 / 1

Status: ok; reused: True

worker.py collects `stars`, `forks`, and `open_issues` using the GitHub REST API, storing snapshots and failures in SQLite.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-18-scheduled-mcp/README.md / README.md

## Components

- `schedule_github_summary(owner, repo, interval_minutes)` creates or updates a recurring job (1–10080 minutes), due immediately.
- `worker.py` collects `stars`, `forks`, and `open_issues` using the GitHub REST API, storing snapshots and failures in SQLite. Failures retry on the next interval.
- `get_github_summary(owner, repo, limit)` returns the most recent values and changes since the oldest of the selected samples.
- `list_scheduled_jobs()` shows next run times and errors.
- `main.py` connects the Groq agent to those MCP tools.

The ignored `schedule.db` persists across restarts. All timestamps are UTC. After downtime, an overdue job runs once rather than replaying every missed interval. Run a single worker process. The worker outputs summaries to stdout or the systemd journal; it does not push messages to a chat.

## focused-v3-q4 / base-07 / 2

Status: ok; reused: True

worker.py collects `stars`, `forks`, and `open_issues` using the GitHub REST API, storing snapshots and failures in SQLite.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-18-scheduled-mcp/README.md / README.md

## Components

- `schedule_github_summary(owner, repo, interval_minutes)` creates or updates a recurring job (1–10080 minutes), due immediately.
- `worker.py` collects `stars`, `forks`, and `open_issues` using the GitHub REST API, storing snapshots and failures in SQLite. Failures retry on the next interval.
- `get_github_summary(owner, repo, limit)` returns the most recent values and changes since the oldest of the selected samples.
- `list_scheduled_jobs()` shows next run times and errors.
- `main.py` connects the Groq agent to those MCP tools.

The ignored `schedule.db` persists across restarts. All timestamps are UTC. After downtime, an overdue job runs once rather than replaying every missed interval. Run a single worker process. The worker outputs summaries to stdout or the systemd journal; it does not push messages to a chat.

## focused-v3-q4 / base-07 / 3

Status: ok; reused: True

worker.py collects `stars`, `forks`, and `open_issues` using the GitHub REST API, storing snapshots and failures in SQLite.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-18-scheduled-mcp/README.md / README.md

## Components

- `schedule_github_summary(owner, repo, interval_minutes)` creates or updates a recurring job (1–10080 minutes), due immediately.
- `worker.py` collects `stars`, `forks`, and `open_issues` using the GitHub REST API, storing snapshots and failures in SQLite. Failures retry on the next interval.
- `get_github_summary(owner, repo, limit)` returns the most recent values and changes since the oldest of the selected samples.
- `list_scheduled_jobs()` shows next run times and errors.
- `main.py` connects the Groq agent to those MCP tools.

The ignored `schedule.db` persists across restarts. All timestamps are UTC. After downtime, an overdue job runs once rather than replaying every missed interval. Run a single worker process. The worker outputs summaries to stdout or the systemd journal; it does not push messages to a chat.

## baseline / base-06 / 1

Status: ok; reused: False

The first GitHub MCP tool Bublik calls on Day 17 is `get_github_repo`.
The first GitHub MCP tool Bublik calls on Day 17 is `get_github_repo`.
In the agent.py file, the first GitHub MCP tool Bublik calls on Day 17 is `get_github_repo`.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-17-first-mcp-tool/README.md / README.md

## Flow

1. `server.py` registers `get_github_repo` with `@mcp.tool()`.
2. Type annotations and the docstring publish the input JSON Schema and tool
   description through MCP.
3. The agent requests the MCP tool list and gives those schemas to the model.
4. The model requests `get_github_repo(owner, repo)`.
5. The agent calls the tool through `ClientSession.call_tool()`.
6. The MCP server requests repository data from GitHub REST API.
7. The result is returned to the model and used in its final answer.

The tool returns repository name, owner, description, stars, forks, open issue
count, default branch, and URL.

Source: day-17-first-mcp-tool/README.ru.md / README.ru.md

## Как работает решение

1. `server.py` регистрирует `get_github_repo` через `@mcp.tool()`.
2. Аннотации типов и docstring формируют описание инструмента и JSON Schema
   входных параметров.
3. Агент получает список MCP-инструментов и передаёт их схемы модели.
4. Модель запрашивает `get_github_repo(owner, repo)`.
5. Агент выполняет инструмент через `ClientSession.call_tool()`.
6. MCP-сервер запрашивает данные репозитория через GitHub REST API.
7. Результат возвращается модели и используется в финальном ответе.

Инструмент возвращает название и владельца репозитория, описание, stars,
forks, количество открытых issues, основную ветку и URL.

Source: day-17-first-mcp-tool/agent.py / agent.py

"""Bublik agent with an MCP tool-calling loop."""

import json
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession


MODEL_NAME = "openai/gpt-oss-20b"
SYSTEM_PROMPT = (
    "You are Bublik, an AI assistant. Use the GitHub MCP tool whenever the "
    "user asks about a repository. Base the answer on the tool result."
)


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    arguments: dict[str, Any]
    result: str


@dataclass(frozen=True)
class AgentResult:
    answer: str
    tool_calls: tuple[ToolCallRecord, ...]


class BublikMcpAgent:
    """Give MCP schemas to an LLM and execute the tool calls it requests."""

    def __init__(self, llm_client: Any, mcp_session: ClientSession) -> None:
        self._llm_client = llm_client
        self._mcp_session = mcp_session

    async def process(self, user_input: str) -> AgentResult:
        prepared = user_input.strip()
        if not prepared:
            raise ValueError("User input cannot be empty")

        tools_result = await self._mcp_session.list_tools()
        llm_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
            for tool in tools_result.tools
        ]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prepared},
        ]
        call_records: list[ToolCallRecord] = []

        for _ in range(3):
            response = self._llm_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=llm_tools,
                tool_choice="auto",
                temperature=0.1,
                max_completion_tokens=600,
            )
            message = response.choices[0].message
            requested_calls = message.tool_calls or []
            if not requested_calls:
                answer = (message.content or "").strip()
                if not answer:
                    raise RuntimeError("The model returned an empty answer")
                return AgentResult(answer, tuple(call_records))

## baseline / base-08 / 1

Status: ok; reused: False

The Day 19 MCP tool composition involves three separate MCP tools: `search_repository(owner, repo)` fetches public GitHub metadata, `summarize_repository(repository)` converts the exact result into Markdown, and `save_report(summary)` writes the exact summary to disk.
The `search_repository(owner, repo)` tool gets public GitHub repository data and passes this result to `summarize_repository(repository)`.
The `save_report(summary)` tool saves the exact markdown supplied by `summarize_repository` to a local file.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-19-mcp-composition/README.md / README.md

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

Source: day-19-mcp-composition/server.py / server.py

"""Three independent MCP tools: fetch, summarize, persist."""

import os
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from github_api import get_repository, validate_name


mcp = FastMCP("Bublik Day 19 Composition")


@mcp.tool()
def search_repository(owner: str, repo: str) -> dict:
    """Get public GitHub repository data. Pass this result to summarize_repository."""
    return get_repository(owner, repo)


@mcp.tool()
def summarize_repository(repository: dict) -> dict:
    """Turn search_repository data into a report. Pass this result to save_report."""
    name = repository["full_name"]
    owner, separator, repo = name.partition("/")
    if not separator or "/" in repo:
        raise ValueError("Invalid repository full_name")
    validate_name(owner, "owner")
    validate_name(repo, "repo")
    if not isinstance(repository["description"], str):
        raise ValueError("Invalid description")
    for key in ("stars", "forks", "open_issues"):
        if type(repository[key]) is not int or repository[key] < 0:
            raise ValueError(f"Invalid {key}")
    branch = validate_name(repository["default_branch"], "branch")
    url = repository["url"]
    if url != f"https://github.com/{name}":
        raise ValueError("Invalid repository URL")
    lines = [
        f"# Repository summary: {name}",
        "",
        f"- URL: {url}",
        f"- Description: {repository['description'].replace(chr(10), ' ').replace(chr(13), ' ')}",
        f"- Default branch: {branch}",
        f"- Stars: {repository['stars']}",
        f"- Forks: {repository['forks']}",
        f"- Open issues: {repository['open_issues']}",
        "",
    ]
    return {"full_name": name, "markdown": "\n".join(lines)}

Source: day-19-mcp-composition/server.py / server.py

@mcp.tool()
def save_report(summary: dict) -> dict:
    """Save the exact markdown supplied by summarize_repository to a local file."""
    name = summary["full_name"]
    owner, separator, repo = name.partition("/")
    if not separator or "/" in repo:
        raise ValueError("Invalid repository full_name")
    validate_name(owner, "owner")
    validate_name(repo, "repo")
    markdown = summary["markdown"]
    if not isinstance(markdown, str) or not markdown.startswith(f"# Repository summary: {name}\n"):
        raise ValueError("Invalid summary markdown")
    output_dir = Path(os.getenv("BUBLIK_REPORT_DIR", str(Path(__file__).parent / "reports")))
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{owner}-{repo}-summary.md"
    # Write fully before replacing the report so an interrupted run cannot truncate it.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=output_dir, prefix=".report-", delete=False) as file:
            temporary = Path(file.name)
            file.write(markdown)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"full_name": name, "path": str(target.resolve()), "bytes_written": len(markdown.encode("utf-8"))}


if __name__ == "__main__":
    mcp.run(transport="stdio")

## baseline / base-10 / 1

Status: ok; reused: False

На VPS установите зависимости, отредактируйте bublik-day18.service.example с фактическими пользователями и путями, скопируйте его в /etc/systemd/system/bublik-day18.service и запустите команды для загрузки и проверки службы.
Проверьте работу службы на VPS с помощью systemctl и journalctl, а также выполните перезапуск и перезагрузку хоста для проверки устойчивости.
Проверьте, что worker выполняется 24/7, используя systemctl, journalctl, перезапуск и перезагрузку хоста на целевом VPS.
Создайте расписание через main.py на VPS или используя MCP-сервер с тем же BUBLIK_DB_PATH, затем проверьте работу worker с помощью journalctl и запросов через агент.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-18-scheduled-mcp/README.md / README.md

## VPS

Install dependencies on the VPS, edit `bublik-day18.service.example` with the actual user and paths, copy it to `/etc/systemd/system/bublik-day18.service`, and run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bublik-day18
sudo systemctl status bublik-day18
journalctl -u bublik-day18 -f
```

Create the schedule via `main.py` on that VPS or another MCP client sharing the same database. The worker needs outbound access to `api.github.com`, but does not need a Groq key. `GITHUB_TOKEN` is optional for public repositories. Verify the actual VPS deployment separately with `systemctl` and `journalctl`.

Source: day-18-scheduled-mcp/README.md / README.md

## VPS

Install dependencies on the VPS, edit `bublik-day18.service.example` with the actual user and paths, copy it to `/etc/systemd/system/bublik-day18.service`, and run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bublik-day18
sudo systemctl status bublik-day18
journalctl -u bublik-day18 -f
```

Create the schedule via `main.py` on that VPS or another MCP client sharing the same database. The worker needs outbound access to `api.github.com`, but does not need a Groq key. `GITHUB_TOKEN` is optional for public repositories. Verify the actual VPS deployment separately with `systemctl` and `journalctl`.

Source: day-18-scheduled-mcp/README.md / README.md

## Assignment checklist

| Requirement | Implementation | Verification |
|---|---|---|
| Periodic MCP tool | `schedule_github_summary` plus worker | MCP integration test |
| Save data | SQLite `jobs`, `snapshots`, `runs` | Restart test |
| Scheduled execution | `next_run`, polling loop, systemd unit | Two executions with controlled time |
| Aggregate result | `get_github_summary` | Latest values, deltas and agent reply test |
| 24/7 operation | Worker supervised by systemd | Verify on the target VPS with systemctl, journalctl, service restart and host reboot |

Source: day-18-scheduled-mcp/README.ru.md / README.ru.md

## VPS (systemd)

На VPS после клонирования проекта и установки зависимостей адаптируйте `bublik-day18.service.example`: замените `YOUR_LINUX_USER` и пути на фактические, скопируйте файл в `/etc/systemd/system/bublik-day18.service`. Затем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bublik-day18
sudo systemctl status bublik-day18
journalctl -u bublik-day18 -f
```

Создайте расписание через `main.py` на том же VPS (или вызвав его MCP-сервер с тем же `BUBLIK_DB_PATH`). Для worker не требуется Groq key: нужен доступ к `api.github.com`; `GITHUB_TOKEN` для публичных репозиториев необязателен, но помогает с лимитами. Установите переменную окружения для обоих процессов, если база находится в другом месте. Проверяйте `journalctl` и запрашивайте свежую сводку через агента. Установить сервис на конкретном VPS можно только при наличии доступа к нему.

## baseline / negative-03 / 1

Status: ok; reused: False

I do not know from these excerpts.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

## focused-v3-q4 / base-06 / 1

Status: ok; reused: False

The first GitHub MCP tool Bublik calls on Day 17 is `get_github_repo`.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-17-first-mcp-tool/README.md / README.md

## Flow

1. `server.py` registers `get_github_repo` with `@mcp.tool()`.
2. Type annotations and the docstring publish the input JSON Schema and tool
   description through MCP.
3. The agent requests the MCP tool list and gives those schemas to the model.
4. The model requests `get_github_repo(owner, repo)`.
5. The agent calls the tool through `ClientSession.call_tool()`.
6. The MCP server requests repository data from GitHub REST API.
7. The result is returned to the model and used in its final answer.

The tool returns repository name, owner, description, stars, forks, open issue
count, default branch, and URL.

## focused-v3-q4 / base-08 / 1

Status: ok; reused: False

The three MCP tools are `search_repository`, `summarize_repository`, and `save_report`.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-19-mcp-composition/README.md / README.md

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

## focused-v3-q4 / base-10 / 1

Status: ok; reused: False

Проверяйте `journalctl` и запрашивайте свежую сводку через агента.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-18-scheduled-mcp/README.ru.md / README.ru.md

## VPS (systemd)

На VPS после клонирования проекта и установки зависимостей адаптируйте `bublik-day18.service.example`: замените `YOUR_LINUX_USER` и пути на фактические, скопируйте файл в `/etc/systemd/system/bublik-day18.service`. Затем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bublik-day18
sudo systemctl status bublik-day18
journalctl -u bublik-day18 -f
```

Создайте расписание через `main.py` на том же VPS (или вызвав его MCP-сервер с тем же `BUBLIK_DB_PATH`). Для worker не требуется Groq key: нужен доступ к `api.github.com`; `GITHUB_TOKEN` для публичных репозиториев необязателен, но помогает с лимитами. Установите переменную окружения для обоих процессов, если база находится в другом месте. Проверяйте `journalctl` и запрашивайте свежую сводку через агента. Установить сервис на конкретном VPS можно только при наличии доступа к нему.

## focused-v3-q4 / negative-03 / 1

Status: ok; reused: False

I do not know from these excerpts.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

## focused-v3-q4 / base-06 / 2

Status: ok; reused: False

The first GitHub MCP tool Bublik calls on Day 17 is `get_github_repo`.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-17-first-mcp-tool/README.md / README.md

## Flow

1. `server.py` registers `get_github_repo` with `@mcp.tool()`.
2. Type annotations and the docstring publish the input JSON Schema and tool
   description through MCP.
3. The agent requests the MCP tool list and gives those schemas to the model.
4. The model requests `get_github_repo(owner, repo)`.
5. The agent calls the tool through `ClientSession.call_tool()`.
6. The MCP server requests repository data from GitHub REST API.
7. The result is returned to the model and used in its final answer.

The tool returns repository name, owner, description, stars, forks, open issue
count, default branch, and URL.

## focused-v3-q4 / base-08 / 2

Status: ok; reused: False

The three MCP tools are `search_repository`, `summarize_repository`, and `save_report`.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-19-mcp-composition/README.md / README.md

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

## focused-v3-q4 / base-10 / 2

Status: ok; reused: False

Проверяйте `journalctl` и запрашивайте свежую сводку через агента.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-18-scheduled-mcp/README.ru.md / README.ru.md

## VPS (systemd)

На VPS после клонирования проекта и установки зависимостей адаптируйте `bublik-day18.service.example`: замените `YOUR_LINUX_USER` и пути на фактические, скопируйте файл в `/etc/systemd/system/bublik-day18.service`. Затем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bublik-day18
sudo systemctl status bublik-day18
journalctl -u bublik-day18 -f
```

Создайте расписание через `main.py` на том же VPS (или вызвав его MCP-сервер с тем же `BUBLIK_DB_PATH`). Для worker не требуется Groq key: нужен доступ к `api.github.com`; `GITHUB_TOKEN` для публичных репозиториев необязателен, но помогает с лимитами. Установите переменную окружения для обоих процессов, если база находится в другом месте. Проверяйте `journalctl` и запрашивайте свежую сводку через агента. Установить сервис на конкретном VPS можно только при наличии доступа к нему.

## focused-v3-q4 / negative-03 / 2

Status: ok; reused: False

I do not know from these excerpts.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

## baseline / base-06 / 2

Status: ok; reused: False

The first GitHub MCP tool Bublik calls on Day 17 is `get_github_repo`.
The first GitHub MCP tool Bublik calls on Day 17 is `get_github_repo`.
In the agent.py file, the first GitHub MCP tool Bublik calls on Day 17 is `get_github_repo`.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-17-first-mcp-tool/README.md / README.md

## Flow

1. `server.py` registers `get_github_repo` with `@mcp.tool()`.
2. Type annotations and the docstring publish the input JSON Schema and tool
   description through MCP.
3. The agent requests the MCP tool list and gives those schemas to the model.
4. The model requests `get_github_repo(owner, repo)`.
5. The agent calls the tool through `ClientSession.call_tool()`.
6. The MCP server requests repository data from GitHub REST API.
7. The result is returned to the model and used in its final answer.

The tool returns repository name, owner, description, stars, forks, open issue
count, default branch, and URL.

Source: day-17-first-mcp-tool/README.ru.md / README.ru.md

## Как работает решение

1. `server.py` регистрирует `get_github_repo` через `@mcp.tool()`.
2. Аннотации типов и docstring формируют описание инструмента и JSON Schema
   входных параметров.
3. Агент получает список MCP-инструментов и передаёт их схемы модели.
4. Модель запрашивает `get_github_repo(owner, repo)`.
5. Агент выполняет инструмент через `ClientSession.call_tool()`.
6. MCP-сервер запрашивает данные репозитория через GitHub REST API.
7. Результат возвращается модели и используется в финальном ответе.

Инструмент возвращает название и владельца репозитория, описание, stars,
forks, количество открытых issues, основную ветку и URL.

Source: day-17-first-mcp-tool/agent.py / agent.py

"""Bublik agent with an MCP tool-calling loop."""

import json
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession


MODEL_NAME = "openai/gpt-oss-20b"
SYSTEM_PROMPT = (
    "You are Bublik, an AI assistant. Use the GitHub MCP tool whenever the "
    "user asks about a repository. Base the answer on the tool result."
)


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    arguments: dict[str, Any]
    result: str


@dataclass(frozen=True)
class AgentResult:
    answer: str
    tool_calls: tuple[ToolCallRecord, ...]


class BublikMcpAgent:
    """Give MCP schemas to an LLM and execute the tool calls it requests."""

    def __init__(self, llm_client: Any, mcp_session: ClientSession) -> None:
        self._llm_client = llm_client
        self._mcp_session = mcp_session

    async def process(self, user_input: str) -> AgentResult:
        prepared = user_input.strip()
        if not prepared:
            raise ValueError("User input cannot be empty")

        tools_result = await self._mcp_session.list_tools()
        llm_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
            for tool in tools_result.tools
        ]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prepared},
        ]
        call_records: list[ToolCallRecord] = []

        for _ in range(3):
            response = self._llm_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=llm_tools,
                tool_choice="auto",
                temperature=0.1,
                max_completion_tokens=600,
            )
            message = response.choices[0].message
            requested_calls = message.tool_calls or []
            if not requested_calls:
                answer = (message.content or "").strip()
                if not answer:
                    raise RuntimeError("The model returned an empty answer")
                return AgentResult(answer, tuple(call_records))

## baseline / base-08 / 2

Status: ok; reused: False

The Day 19 MCP tool composition involves three separate MCP tools: `search_repository(owner, repo)` fetches public GitHub metadata, `summarize_repository(repository)` converts the exact result into Markdown, and `save_report(summary)` writes the exact summary to disk.
The `search_repository(owner, repo)` tool gets public GitHub repository data and passes this result to `summarize_repository(repository)`.
The `save_report(summary)` tool saves the exact markdown supplied by `summarize_repository` to a local file.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-19-mcp-composition/README.md / README.md

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

Source: day-19-mcp-composition/server.py / server.py

"""Three independent MCP tools: fetch, summarize, persist."""

import os
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from github_api import get_repository, validate_name


mcp = FastMCP("Bublik Day 19 Composition")


@mcp.tool()
def search_repository(owner: str, repo: str) -> dict:
    """Get public GitHub repository data. Pass this result to summarize_repository."""
    return get_repository(owner, repo)


@mcp.tool()
def summarize_repository(repository: dict) -> dict:
    """Turn search_repository data into a report. Pass this result to save_report."""
    name = repository["full_name"]
    owner, separator, repo = name.partition("/")
    if not separator or "/" in repo:
        raise ValueError("Invalid repository full_name")
    validate_name(owner, "owner")
    validate_name(repo, "repo")
    if not isinstance(repository["description"], str):
        raise ValueError("Invalid description")
    for key in ("stars", "forks", "open_issues"):
        if type(repository[key]) is not int or repository[key] < 0:
            raise ValueError(f"Invalid {key}")
    branch = validate_name(repository["default_branch"], "branch")
    url = repository["url"]
    if url != f"https://github.com/{name}":
        raise ValueError("Invalid repository URL")
    lines = [
        f"# Repository summary: {name}",
        "",
        f"- URL: {url}",
        f"- Description: {repository['description'].replace(chr(10), ' ').replace(chr(13), ' ')}",
        f"- Default branch: {branch}",
        f"- Stars: {repository['stars']}",
        f"- Forks: {repository['forks']}",
        f"- Open issues: {repository['open_issues']}",
        "",
    ]
    return {"full_name": name, "markdown": "\n".join(lines)}

Source: day-19-mcp-composition/server.py / server.py

@mcp.tool()
def save_report(summary: dict) -> dict:
    """Save the exact markdown supplied by summarize_repository to a local file."""
    name = summary["full_name"]
    owner, separator, repo = name.partition("/")
    if not separator or "/" in repo:
        raise ValueError("Invalid repository full_name")
    validate_name(owner, "owner")
    validate_name(repo, "repo")
    markdown = summary["markdown"]
    if not isinstance(markdown, str) or not markdown.startswith(f"# Repository summary: {name}\n"):
        raise ValueError("Invalid summary markdown")
    output_dir = Path(os.getenv("BUBLIK_REPORT_DIR", str(Path(__file__).parent / "reports")))
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{owner}-{repo}-summary.md"
    # Write fully before replacing the report so an interrupted run cannot truncate it.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=output_dir, prefix=".report-", delete=False) as file:
            temporary = Path(file.name)
            file.write(markdown)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"full_name": name, "path": str(target.resolve()), "bytes_written": len(markdown.encode("utf-8"))}


if __name__ == "__main__":
    mcp.run(transport="stdio")

## baseline / base-10 / 2

Status: ok; reused: False

На VPS установите зависимости, отредактируйте bublik-day18.service.example с фактическими пользователями и путями, скопируйте его в /etc/systemd/system/bublik-day18.service и запустите команды для загрузки и проверки службы.
Проверьте работу службы на VPS с помощью systemctl и journalctl, а также выполните перезапуск и перезагрузку хоста для проверки устойчивости.
Проверьте, что worker выполняется 24/7, используя systemctl, journalctl, перезапуск и перезагрузку хоста на целевом VPS.
Создайте расписание через main.py на VPS или используя MCP-сервер с тем же BUBLIK_DB_PATH, затем проверьте работу worker с помощью journalctl и запросов через агент.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-18-scheduled-mcp/README.md / README.md

## VPS

Install dependencies on the VPS, edit `bublik-day18.service.example` with the actual user and paths, copy it to `/etc/systemd/system/bublik-day18.service`, and run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bublik-day18
sudo systemctl status bublik-day18
journalctl -u bublik-day18 -f
```

Create the schedule via `main.py` on that VPS or another MCP client sharing the same database. The worker needs outbound access to `api.github.com`, but does not need a Groq key. `GITHUB_TOKEN` is optional for public repositories. Verify the actual VPS deployment separately with `systemctl` and `journalctl`.

Source: day-18-scheduled-mcp/README.md / README.md

## VPS

Install dependencies on the VPS, edit `bublik-day18.service.example` with the actual user and paths, copy it to `/etc/systemd/system/bublik-day18.service`, and run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bublik-day18
sudo systemctl status bublik-day18
journalctl -u bublik-day18 -f
```

Create the schedule via `main.py` on that VPS or another MCP client sharing the same database. The worker needs outbound access to `api.github.com`, but does not need a Groq key. `GITHUB_TOKEN` is optional for public repositories. Verify the actual VPS deployment separately with `systemctl` and `journalctl`.

Source: day-18-scheduled-mcp/README.md / README.md

## Assignment checklist

| Requirement | Implementation | Verification |
|---|---|---|
| Periodic MCP tool | `schedule_github_summary` plus worker | MCP integration test |
| Save data | SQLite `jobs`, `snapshots`, `runs` | Restart test |
| Scheduled execution | `next_run`, polling loop, systemd unit | Two executions with controlled time |
| Aggregate result | `get_github_summary` | Latest values, deltas and agent reply test |
| 24/7 operation | Worker supervised by systemd | Verify on the target VPS with systemctl, journalctl, service restart and host reboot |

Source: day-18-scheduled-mcp/README.ru.md / README.ru.md

## VPS (systemd)

На VPS после клонирования проекта и установки зависимостей адаптируйте `bublik-day18.service.example`: замените `YOUR_LINUX_USER` и пути на фактические, скопируйте файл в `/etc/systemd/system/bublik-day18.service`. Затем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bublik-day18
sudo systemctl status bublik-day18
journalctl -u bublik-day18 -f
```

Создайте расписание через `main.py` на том же VPS (или вызвав его MCP-сервер с тем же `BUBLIK_DB_PATH`). Для worker не требуется Groq key: нужен доступ к `api.github.com`; `GITHUB_TOKEN` для публичных репозиториев необязателен, но помогает с лимитами. Установите переменную окружения для обоих процессов, если база находится в другом месте. Проверяйте `journalctl` и запрашивайте свежую сводку через агента. Установить сервис на конкретном VPS можно только при наличии доступа к нему.

## baseline / negative-03 / 2

Status: ok; reused: False

I do not know from these excerpts.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

## baseline / base-06 / 3

Status: ok; reused: False

The first GitHub MCP tool Bublik calls on Day 17 is `get_github_repo`.
The first GitHub MCP tool Bublik calls on Day 17 is `get_github_repo`.
In the agent.py file, the first GitHub MCP tool Bublik calls on Day 17 is `get_github_repo`.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-17-first-mcp-tool/README.md / README.md

## Flow

1. `server.py` registers `get_github_repo` with `@mcp.tool()`.
2. Type annotations and the docstring publish the input JSON Schema and tool
   description through MCP.
3. The agent requests the MCP tool list and gives those schemas to the model.
4. The model requests `get_github_repo(owner, repo)`.
5. The agent calls the tool through `ClientSession.call_tool()`.
6. The MCP server requests repository data from GitHub REST API.
7. The result is returned to the model and used in its final answer.

The tool returns repository name, owner, description, stars, forks, open issue
count, default branch, and URL.

Source: day-17-first-mcp-tool/README.ru.md / README.ru.md

## Как работает решение

1. `server.py` регистрирует `get_github_repo` через `@mcp.tool()`.
2. Аннотации типов и docstring формируют описание инструмента и JSON Schema
   входных параметров.
3. Агент получает список MCP-инструментов и передаёт их схемы модели.
4. Модель запрашивает `get_github_repo(owner, repo)`.
5. Агент выполняет инструмент через `ClientSession.call_tool()`.
6. MCP-сервер запрашивает данные репозитория через GitHub REST API.
7. Результат возвращается модели и используется в финальном ответе.

Инструмент возвращает название и владельца репозитория, описание, stars,
forks, количество открытых issues, основную ветку и URL.

Source: day-17-first-mcp-tool/agent.py / agent.py

"""Bublik agent with an MCP tool-calling loop."""

import json
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession


MODEL_NAME = "openai/gpt-oss-20b"
SYSTEM_PROMPT = (
    "You are Bublik, an AI assistant. Use the GitHub MCP tool whenever the "
    "user asks about a repository. Base the answer on the tool result."
)


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    arguments: dict[str, Any]
    result: str


@dataclass(frozen=True)
class AgentResult:
    answer: str
    tool_calls: tuple[ToolCallRecord, ...]


class BublikMcpAgent:
    """Give MCP schemas to an LLM and execute the tool calls it requests."""

    def __init__(self, llm_client: Any, mcp_session: ClientSession) -> None:
        self._llm_client = llm_client
        self._mcp_session = mcp_session

    async def process(self, user_input: str) -> AgentResult:
        prepared = user_input.strip()
        if not prepared:
            raise ValueError("User input cannot be empty")

        tools_result = await self._mcp_session.list_tools()
        llm_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
            for tool in tools_result.tools
        ]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prepared},
        ]
        call_records: list[ToolCallRecord] = []

        for _ in range(3):
            response = self._llm_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=llm_tools,
                tool_choice="auto",
                temperature=0.1,
                max_completion_tokens=600,
            )
            message = response.choices[0].message
            requested_calls = message.tool_calls or []
            if not requested_calls:
                answer = (message.content or "").strip()
                if not answer:
                    raise RuntimeError("The model returned an empty answer")
                return AgentResult(answer, tuple(call_records))

## baseline / base-08 / 3

Status: ok; reused: False

The Day 19 MCP tool composition involves three separate MCP tools: `search_repository(owner, repo)` fetches public GitHub metadata, `summarize_repository(repository)` converts the exact result into Markdown, and `save_report(summary)` writes the exact summary to disk.
The `search_repository(owner, repo)` tool gets public GitHub repository data and passes this result to `summarize_repository(repository)`.
The `save_report(summary)` tool saves the exact markdown supplied by `summarize_repository` to a local file.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-19-mcp-composition/README.md / README.md

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

Source: day-19-mcp-composition/server.py / server.py

"""Three independent MCP tools: fetch, summarize, persist."""

import os
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from github_api import get_repository, validate_name


mcp = FastMCP("Bublik Day 19 Composition")


@mcp.tool()
def search_repository(owner: str, repo: str) -> dict:
    """Get public GitHub repository data. Pass this result to summarize_repository."""
    return get_repository(owner, repo)


@mcp.tool()
def summarize_repository(repository: dict) -> dict:
    """Turn search_repository data into a report. Pass this result to save_report."""
    name = repository["full_name"]
    owner, separator, repo = name.partition("/")
    if not separator or "/" in repo:
        raise ValueError("Invalid repository full_name")
    validate_name(owner, "owner")
    validate_name(repo, "repo")
    if not isinstance(repository["description"], str):
        raise ValueError("Invalid description")
    for key in ("stars", "forks", "open_issues"):
        if type(repository[key]) is not int or repository[key] < 0:
            raise ValueError(f"Invalid {key}")
    branch = validate_name(repository["default_branch"], "branch")
    url = repository["url"]
    if url != f"https://github.com/{name}":
        raise ValueError("Invalid repository URL")
    lines = [
        f"# Repository summary: {name}",
        "",
        f"- URL: {url}",
        f"- Description: {repository['description'].replace(chr(10), ' ').replace(chr(13), ' ')}",
        f"- Default branch: {branch}",
        f"- Stars: {repository['stars']}",
        f"- Forks: {repository['forks']}",
        f"- Open issues: {repository['open_issues']}",
        "",
    ]
    return {"full_name": name, "markdown": "\n".join(lines)}

Source: day-19-mcp-composition/server.py / server.py

@mcp.tool()
def save_report(summary: dict) -> dict:
    """Save the exact markdown supplied by summarize_repository to a local file."""
    name = summary["full_name"]
    owner, separator, repo = name.partition("/")
    if not separator or "/" in repo:
        raise ValueError("Invalid repository full_name")
    validate_name(owner, "owner")
    validate_name(repo, "repo")
    markdown = summary["markdown"]
    if not isinstance(markdown, str) or not markdown.startswith(f"# Repository summary: {name}\n"):
        raise ValueError("Invalid summary markdown")
    output_dir = Path(os.getenv("BUBLIK_REPORT_DIR", str(Path(__file__).parent / "reports")))
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{owner}-{repo}-summary.md"
    # Write fully before replacing the report so an interrupted run cannot truncate it.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=output_dir, prefix=".report-", delete=False) as file:
            temporary = Path(file.name)
            file.write(markdown)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"full_name": name, "path": str(target.resolve()), "bytes_written": len(markdown.encode("utf-8"))}


if __name__ == "__main__":
    mcp.run(transport="stdio")

## baseline / base-10 / 3

Status: ok; reused: False

На VPS установите зависимости, отредактируйте bublik-day18.service.example с фактическими пользователями и путями, скопируйте его в /etc/systemd/system/bublik-day18.service и запустите команды для загрузки и проверки службы.
Проверьте работу службы на VPS с помощью systemctl и journalctl, а также проверьте её восстановление после перезапуска и перезагрузки хоста.
Создайте расписание через main.py на VPS или вызовите его MCP-сервер с тем же BUBLIK_DB_PATH. Проверьте работу worker без Groq API ключа, используя доступ к api.github.com.
Проверьте, что служба работает 24/7, используя systemctl, journalctl, перезапуск и перезагрузку хоста для проверки восстановления после простоя.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-18-scheduled-mcp/README.md / README.md

## VPS

Install dependencies on the VPS, edit `bublik-day18.service.example` with the actual user and paths, copy it to `/etc/systemd/system/bublik-day18.service`, and run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bublik-day18
sudo systemctl status bublik-day18
journalctl -u bublik-day18 -f
```

Create the schedule via `main.py` on that VPS or another MCP client sharing the same database. The worker needs outbound access to `api.github.com`, but does not need a Groq key. `GITHUB_TOKEN` is optional for public repositories. Verify the actual VPS deployment separately with `systemctl` and `journalctl`.

Source: day-18-scheduled-mcp/README.md / README.md

## VPS

Install dependencies on the VPS, edit `bublik-day18.service.example` with the actual user and paths, copy it to `/etc/systemd/system/bublik-day18.service`, and run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bublik-day18
sudo systemctl status bublik-day18
journalctl -u bublik-day18 -f
```

Create the schedule via `main.py` on that VPS or another MCP client sharing the same database. The worker needs outbound access to `api.github.com`, but does not need a Groq key. `GITHUB_TOKEN` is optional for public repositories. Verify the actual VPS deployment separately with `systemctl` and `journalctl`.

Source: day-18-scheduled-mcp/README.ru.md / README.ru.md

## VPS (systemd)

На VPS после клонирования проекта и установки зависимостей адаптируйте `bublik-day18.service.example`: замените `YOUR_LINUX_USER` и пути на фактические, скопируйте файл в `/etc/systemd/system/bublik-day18.service`. Затем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bublik-day18
sudo systemctl status bublik-day18
journalctl -u bublik-day18 -f
```

Создайте расписание через `main.py` на том же VPS (или вызвав его MCP-сервер с тем же `BUBLIK_DB_PATH`). Для worker не требуется Groq key: нужен доступ к `api.github.com`; `GITHUB_TOKEN` для публичных репозиториев необязателен, но помогает с лимитами. Установите переменную окружения для обоих процессов, если база находится в другом месте. Проверяйте `journalctl` и запрашивайте свежую сводку через агента. Установить сервис на конкретном VPS можно только при наличии доступа к нему.

Source: day-18-scheduled-mcp/README.ru.md / README.ru.md

## Проверка пунктов задания

| Пункт | Реализация | Проверка |
|---|---|---|
| MCP-инструмент с периодическим выполнением | `schedule_github_summary` + `worker.py` | `McpTests`, `SchedulerTests` |
| Данные сохраняются | `jobs`, `snapshots`, `runs` в SQLite | восстановление после создания нового `Scheduler` |
| Выполняется по расписанию | `next_run`, периодический цикл, `Restart=always` в systemd | повторный сбор при сдвиге часов, отсутствие преждевременного повтора |
| Возвращает агрегированный результат | `get_github_summary`: latest, change, samples | проверка двух снимков и ответа агента |
| Работает

## baseline / negative-03 / 3

Status: ok; reused: False

I do not know from these excerpts.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

## focused-v3-q4 / base-06 / 3

Status: ok; reused: False

The first GitHub MCP tool Bublik calls on Day 17 is `get_github_repo`.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-17-first-mcp-tool/README.md / README.md

## Flow

1. `server.py` registers `get_github_repo` with `@mcp.tool()`.
2. Type annotations and the docstring publish the input JSON Schema and tool
   description through MCP.
3. The agent requests the MCP tool list and gives those schemas to the model.
4. The model requests `get_github_repo(owner, repo)`.
5. The agent calls the tool through `ClientSession.call_tool()`.
6. The MCP server requests repository data from GitHub REST API.
7. The result is returned to the model and used in its final answer.

The tool returns repository name, owner, description, stars, forks, open issue
count, default branch, and URL.

## focused-v3-q4 / base-08 / 3

Status: ok; reused: False

The three MCP tools are `search_repository`, `summarize_repository`, and `save_report`.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-19-mcp-composition/README.md / README.md

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

## focused-v3-q4 / base-10 / 3

Status: ok; reused: False

Проверяйте `journalctl` и запрашивайте свежую сводку через агента.

Human review: support □ completeness □ exact names/conditions □ correct refusal □

Source: day-18-scheduled-mcp/README.ru.md / README.ru.md

## VPS (systemd)

На VPS после клонирования проекта и установки зависимостей адаптируйте `bublik-day18.service.example`: замените `YOUR_LINUX_USER` и пути на фактические, скопируйте файл в `/etc/systemd/system/bublik-day18.service`. Затем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bublik-day18
sudo systemctl status bublik-day18
journalctl -u bublik-day18 -f
```

Создайте расписание через `main.py` на том же VPS (или вызвав его MCP-сервер с тем же `BUBLIK_DB_PATH`). Для worker не требуется Groq key: нужен доступ к `api.github.com`; `GITHUB_TOKEN` для публичных репозиториев необязателен, но помогает с лимитами. Установите переменную окружения для обоих процессов, если база находится в другом месте. Проверяйте `journalctl` и запрашивайте свежую сводку через агента. Установить сервис на конкретном VPS можно только при наличии доступа к нему.

## focused-v3-q4 / negative-03 / 3

Status: ok; reused: False

I do not know from these excerpts.

Human review: support □ completeness □ exact names/conditions □ correct refusal □
