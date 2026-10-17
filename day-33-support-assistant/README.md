# Day 33 — AI Support Assistant: PASS

A separate local support assistant for **Bublik Private AI Service (Day 30)**,
using synthetic JSON CRM through real MCP stdio and FAQ/document RAG.
**Course Minimum accepted on 2026-10-17:** Mac offline **25/25**, fresh Groq
attempt-03 **HTTP 200 / full E2E PASS**, saved-answer semantic review **PASS**.
[Русский](README.ru.md) · [Final report](FINAL_REPORT.md) ·
[Accepted JSON](reports/accepted.json) · [Terminal video](CONSOLE_VIDEO.ru.md).

## Architecture and scope

Question → MCP `get_ticket` → MCP `get_user` using only the ticket's user ID →
SQLite FTS5/BM25 top-3 → Groq JSON plan → evidence validation → final answer.
The MCP SDK uses a real stdio subprocess, initialization, discovery and tool calls.
The design follows Day 20 ClientSession/FastMCP and Day 32 bounded FTS5 patterns;
no earlier runtime is imported, and no Day 30 database is opened.

Seven Russian FAQ items plus seven exact English excerpts form 14 chunks.
Day 30 README.md and API.md are read-only sources checked against file SHA-256
and exact quotations; README.ru.md was also reviewed when preparing the FAQ.
Links point to original sections at base `c654e24610bdabed15747088f9e1691ed36d0b17`.
A changed source fails closed. No embeddings, reranker or shared knowledge.db.

The model selects an assessment, exact document/context facts and action IDs.
Action text comes from a bounded application catalogue. Model `document_facts`
remain unchanged; `application_evidence` separately binds selected actions to
retrieved passages, marked `assigned_by: application`. No arbitrary model prose is
published. This is deliberately narrower than unrestricted support diagnosis.

The real accepted T-101 call used `openai/gpt-oss-120b` through curl: **1370 input /
233 completion tokens**, reasoning low, temperature 0, output cap 1800, one POST,
no retries/fallback. The input had DOC-ERRORS / FAQ-AUTH / DOC-AUTH; the final answer
cites DOC-ERRORS and FAQ-AUTH. Billing is unknown; list-price estimate $0.0003453.
Attempt-01 HTTP 403 and attempt-02 evidence rejection remain recorded in the final
report. Offline replay was kept separate from the later fresh live PASS.

## Install and verify retained evidence

From the repository root, use Python 3.12+ with SQLite FTS5 (tested Mac 3.13.3).
Keep a separate environment from the working Day 30 service:

```bash
python3.13 -m venv "$HOME/.venvs/bublik-day33"
source "$HOME/.venvs/bublik-day33/bin/activate"
python -m pip install -r day-33-support-assistant/requirements.txt
python day-33-support-assistant/verify_delivery.py
python -W error::ResourceWarning -m unittest discover -s day-33-support-assistant/tests -v
```

Dependency installation needs network. Verification and all 25 tests perform no
real provider generation; tests do use real local MCP subprocesses. The verifier
rechecks 19 retained runtime/support hashes, saved context, RAG sources, exact
quotes and reconstructed answer. It is not a new live or semantic acceptance.
The initial `offline-linux.json` is historical 22-test evidence, not current 25-test
acceptance. Current Mac evidence is bound by SHA in the accepted report.

## CLI and local HTTP demonstration

These commands use **offline_mock**, with zero real generation calls:

```bash
python day-33-support-assistant/main.py answer \
  --question 'Почему не работает авторизация?'
python day-33-support-assistant/main.py answer \
  --ticket T-101 --question 'Почему не работает авторизация?'
python day-33-support-assistant/main.py prepare \
  --ticket T-101 --question 'Почему не работает авторизация?'
python day-33-support-assistant/main.py serve --port 8033
```

`prepare` performs real MCP + RAG, without provider POST. The HTTP server binds
only 127.0.0.1 and always uses mock. In a second terminal:

```bash
curl --fail-with-body --max-time 10 http://127.0.0.1:8033/health
curl --fail-with-body --max-time 30 http://127.0.0.1:8033/support/answer \
  -H 'Content-Type: application/json' \
  --data '{"ticket_id":"T-101","question":"Почему не работает авторизация?"}'
```

Stop the server with Ctrl+C. Health is process liveness, not MCP/model readiness.
The real Groq path is the explicit acceptance CLI, not the mock HTTP endpoint.
Historical live/retry/final runners preserve exclusive attempt markers; they are
not recording commands or permission for new calls. Their frozen README hashes
precede final documentation and intentionally differ now. Do not delete markers,
rewrite original receipts or run another generation for the video. The legacy
`main.py live` uses urllib; curl was the accepted transport. A future unified
adapter/live HTTP is post-course work, not a reason to repeat this acceptance.

## Required scenarios and safeguards

| Case | Verified behavior |
|---|---|
| T-101 | Explicit expired session; MCP facts plus sources and sign-in advice; real Groq PASS |
| T-102 | Another user, iPhone, disconnected Tailscale; different actions; offline PASS |
| T-103 | Only HTTP 401 known; exact cause remains undetermined; offline PASS |
| T-104 | Refund policy absent; no invented documentation; offline PASS |
| T-999 | 404 without invented user context; offline PASS |
| MCP unavailable | 503 before the model, with no fabricated success; offline PASS |

An omitted ticket gives a general FAQ answer. User IDs in the question cannot
select CRM records. Unknown JSON fields/duplicate keys are rejected. Limits:
2000 UTF-8 question bytes, 8192 HTTP body bytes. Obvious secret patterns are
rejected; errors do not echo input or upstream bodies, and access logs are off.
The filter is limited; use only supplied synthetic data, never real credentials.

Output includes ticket ID, source IDs/links, separate model/application evidence,
context-use markers and evidence gaps. Sources establish provenance; the narrow
catalogue and explicit semantic review are also needed for acceptance.

Post-course backlog: unified curl adapter/live HTTP, RU/EN replies, broader FAQ,
semantic retrieval, general claim verification, real CRM/operator auth, persistent
MCP sessions. No Web UI, chat history or public deployment. Lexical search can
miss paraphrases. GitHub publication and video recording are separate steps;
PR/merge require owner authorization. OpenAI API was not used.
