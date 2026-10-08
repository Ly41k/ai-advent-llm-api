This Markdown view was generated from the unchanged original JSON. Scoped manual review is in ../../review/manual-review.json.

# Day 29 — local LLM optimization / V1

State: completed; series: v1; split: calibration

Reused rows retain their original timestamps and measurements. Heuristic quality requires manual review.
Warmups and one-token input probes are accounted separately. Application refusals are excluded from generation speed.

| Profile | Quality / present | Valid / planned | Reused | Median seconds | Decode tokens/s | Max sampled RSS GiB |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 3/3 | 3/3 | 3 | 26.28 | 10.67 | 0.11 |
| focused-v3-q4 | 3/3 | 3/3 | 0 | 6.09 | 11.47 | 0.08 |

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

Status: ok; reused: False

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

Status: ok; reused: False

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

Status: ok; reused: False

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
