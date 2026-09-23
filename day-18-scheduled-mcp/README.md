# Day 18 — Scheduled MCP jobs

[Step-by-step verification (Russian)](VERIFY.ru.md) covers local checks and VPS deployment.

Bublik schedules periodic public GitHub repository observations through MCP. An independent worker polls due jobs, stores snapshots in SQLite and writes an aggregate summary to stdout after each run. The agent can read the persisted summary via MCP and include it in its reply.

## Components

- `schedule_github_summary(owner, repo, interval_minutes)` creates or updates a recurring job (1–10080 minutes), due immediately.
- `worker.py` collects `stars`, `forks`, and `open_issues` using the GitHub REST API, storing snapshots and failures in SQLite. Failures retry on the next interval.
- `get_github_summary(owner, repo, limit)` returns the most recent values and changes since the oldest of the selected samples.
- `list_scheduled_jobs()` shows next run times and errors.
- `main.py` connects the Groq agent to those MCP tools.

The ignored `schedule.db` persists across restarts. All timestamps are UTC. After downtime, an overdue job runs once rather than replaying every missed interval. Run a single worker process. The worker outputs summaries to stdout or the systemd journal; it does not push messages to a chat.

## Offline verification

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r day-18-scheduled-mcp/requirements.txt
.venv/bin/python day-18-scheduled-mcp/test_day18.py -v
```

Tests cover a real MCP stdio session, durable schedules and samples, two scheduled executions, aggregation, recovery after an API error, and agent use of the saved result. Fake GitHub and LLM clients avoid network and API keys.

## Run locally

Start the worker in one terminal:

```bash
.venv/bin/python day-18-scheduled-mcp/worker.py
```

With `GROQ_API_KEY` in the root `.env`, start the agent in another:

```bash
.venv/bin/python day-18-scheduled-mcp/main.py
```

Ask it to monitor `Ly41k/ai-advent-llm-api` every 60 minutes and then request its summary. The first scheduled run occurs within 15 seconds. The agent and worker must share `BUBLIK_DB_PATH` if using a custom path. `worker.py --once` processes currently due jobs and exits.

## VPS

Install dependencies on the VPS, edit `bublik-day18.service.example` with the actual user and paths, copy it to `/etc/systemd/system/bublik-day18.service`, and run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bublik-day18
sudo systemctl status bublik-day18
journalctl -u bublik-day18 -f
```

Create the schedule via `main.py` on that VPS or another MCP client sharing the same database. The worker needs outbound access to `api.github.com`, but does not need a Groq key. `GITHUB_TOKEN` is optional for public repositories. Verify the actual VPS deployment separately with `systemctl` and `journalctl`.

## Assignment checklist

| Requirement | Implementation | Verification |
|---|---|---|
| Periodic MCP tool | `schedule_github_summary` plus worker | MCP integration test |
| Save data | SQLite `jobs`, `snapshots`, `runs` | Restart test |
| Scheduled execution | `next_run`, polling loop, systemd unit | Two executions with controlled time |
| Aggregate result | `get_github_summary` | Latest values, deltas and agent reply test |
| 24/7 operation | Worker supervised by systemd | Verify on the target VPS with systemctl, journalctl, service restart and host reboot |
