# Tooling and model sessions / Инструменты и модельная сессия

## Read-only Git tools

Day 31 exposes git_current_branch, git_status, git_diff and project_list_files
through a local FastMCP stdio server. Tool inputs and outputs are validated.
Only the Git role's scoped client can call the Git tools. Project paths are
relative to the configured repository root. Traversal and symlinks are rejected.

git_diff returns metadata by default. Text content requires one to four explicit
allowed paths. Untracked file content is not read. Sensitive names and private
databases are excluded; detected secret-like patches are blocked.

The controlled command runner disables hooks, external diff, textconv, fsmonitor
and configured clean/smudge/process filters. It does not execute arbitrary Bash.
Application capabilities do not constitute an OS sandbox for hostile Python code.

## Explicit writes and approval

The Git tools do not commit, push, edit or delete project files. An explicit
index build writes derived app state outside the project, using private permissions.
Future write tools must bind human approval to concrete validated action arguments
and a project revision. No dangerous executor is added solely for an approval demo.

## Stopping other model clients

Day 30 must be stopped before Day 31 embedding/inference operations. The doctor
checks known processes, launchd and loopback ports. Service inactivity alone is
not proof that an earlier Ollama request ended.

## Ollama /api/ps: loaded models and request state

`GET /api/ps` reports models currently loaded into memory. The returned model
list describes model residency; it is not a completion record for inference
requests. A loaded model does not establish whether a generation has finished
or whether Ollama is idle. Do not use `/api/ps` as an idle witness after a lost
HTTP response or interrupted request.

`/api/ps` показывает загруженные модели, а не подтверждение завершения запроса.
Список моделей не доказывает, что генерация закончилась и Ollama свободна.

Endpoint documentation: https://docs.ollama.com/api/ps . The model-residency
description comes from the API contract; the idle-witness restriction is the
Day 31 policy implemented in model_session.py.

## Fresh process epochs and exclusive model session

День 31 использует prepare/confirm модельной сессии. Оператор перезапускает
Ollama; приложение подтверждает новый OS process epoch и отсутствие старого
отдельного runner. Межпроцессный cooperative lease разрешает одну model operation.
Перед dispatch сохраняется uncertain state; потеря ответа или crash требуют
проверяемого восстановления. Другие приложения не должны использовать эту сессию.

There is one Qwen model, not one copy per agent. Git and retrieval jobs may run
concurrently, while model calls remain serialized. bge-m3 is unloaded after a
final embedding batch/query using keep_alive=0s. No cloud fallback is performed.

## Read-only project answer pipeline

The /help question and ask commands choose Git, documentation, independent
fan-out or a changed-files documentation chain. Chain source association uses
exact relative path mentions, never basename alone, and examines at most four
changed paths. This association does not prove that a document explains all
functionality of a changed file. Missing associations are reported explicitly.

Qwen2.5:14b Q4_K_M generates claims from scoped excerpts through /api/chat with
a closed JSON schema. A Documentation task cannot see the caller's Git facts
or private history. Main has a separate context and can select only checked
claim/fact IDs. The same request permits eight capability calls and a 300-second
deadline. Each model worker has a 180-second timeout. Lost responses retain
uncertain inference state; no retry, cloud fallback or model restart is automatic.

The final verifier checks fresh source digests/spans and reobserves Git after
generation. Exact citations and identifier checks are distinct from semantic
answer correctness. Writes and arbitrary shell commands remain unavailable.

Sources: day-31-developer-assistant/bublik_developer/policy.py;
day-31-developer-assistant/bublik_developer/preflight.py;
day-31-developer-assistant/bublik_developer/model_session.py.
