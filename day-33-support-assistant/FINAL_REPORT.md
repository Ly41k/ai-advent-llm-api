# Day 33 — final Course Minimum report

**Accepted: PASS, 2026-10-17 (Europe/Kiev).** The accepted attempt is **attempt-03**:
a fresh Mac execution of question → real MCP → ticket → user → RAG → Groq →
evidence validator → final user answer. Semantic review of the saved answer is PASS.
[Russian](FINAL_REPORT.ru.md) · [machine-readable acceptance](reports/accepted.json).

| Component | Result |
|---|---|
| Mac offline acceptance | PASS, 25/25, checked by final runner before POST |
| MCP stdio | PASS: `get_ticket(T-101)` then `get_user(U-001)` |
| User binding | PASS: only the ticket's U-001 synthetic context |
| RAG | PASS: SQLite FTS5/BM25, 14 indexed chunks, top-3 |
| Real Groq | PASS: one curl POST, HTTP 200, no retry/fallback |
| JSON, quotes and evidence validation | PASS |
| Semantic quality | PASS: manual assistant assessment of saved answer |
| Full live E2E, corrected implementation | PASS |

Groq model: `openai/gpt-oss-120b`, temperature 0, reasoning low, completion cap
1800. Actual usage: **1370 input + 233 completion = 1603 tokens**; completion
includes **129 reasoning tokens**. HTTP request ID:
`req_01m53etxjwewhbfqzfk12b4veg`. Completion ID:
`chatcmpl-05789f69-9e29-48ee-ab8f-7adb8977cfb5`. Finish reason: `stop`; curl exit 0.

The input contained `DOC-ERRORS`, `FAQ-AUTH`, `DOC-AUTH`. The model cited
`DOC-ERRORS`; the application separately assigned `FAQ-AUTH` to `sign_in` and
`DOC-ERRORS` to `check_auth`. The final answer uses two cited sources, from three
retrieved inputs. Application evidence is not represented as model citation.

The diagnosis `session_expired` follows the explicit ticket field, not HTTP 401
alone. Reopening the original HTTPS chat and signing in is reasonable. Asking
whether access uses a browser session or Bearer credential is safe, though the
ticket already identifies a browser session. No guaranteed fix, invented cause,
wrong-password diagnosis or another user's data appears in the answer. Review was
performed by the assistant; the original raw receipt's pending-review field was
not rewritten. The derived acceptance record contains the review decision.

## Preserved attempts and SHA bindings

| Attempt | HTTP | Actual input / completion | Original full E2E |
|---|---:|---:|---|
| 01, urllib | 403 | unknown / unknown | FAIL, no model answer |
| 02, curl | 200 | 1370 / 230 | FAIL, `missing_action_evidence` |
| 02, offline replay | no POST | 0 new / 0 new | PASS replay only; original verdict unchanged |
| 03, curl, corrected code | 200 | 1370 / 233 | PASS fresh live |

The first 403 cause remains unknown; key entry and transport differed between
attempts. Successful curl calls do not prove a particular WAF/User-Agent cause.
A blocked duplicate launch performed no POST. All original receipts and markers
remain unchanged; public acceptance is derived, not an edited original.

- Base main: `c654e24610bdabed15747088f9e1691ed36d0b17`.
- Attempt-03 original receipt SHA256: `dc03e5e22a9ca1d72885df97ae548a88ada8666c9ce60c2005ab9fb8ef694acb`.
- Request body SHA256: `8010cd4309636300702e335b3b738fd86227dcab51ed573e099fa0e22bd2d4c8`.
- Mac offline receipt SHA256: `106b3d7544210c5b7a9d2b77113cc0dace0b84e734aaaa0d43b298c9feac3acd`.
- Accepted `support_agent.py` SHA256: `1342a3b1a88c4942526370c5f08c4c158e0a690d4b9ba3698fbc5e333460f0e3`.

The JSON record retains 19 runtime/support-file hashes and the original README
hashes. Final documentation was updated after acceptance; old runner manifests
remain historical and will reject changed README bytes. Use `verify_delivery.py`
for retained delivery checks. It performs no model/network/MCP calls and is not a
new live acceptance. SHA hashes are integrity bindings, not signatures.

## Cost, limits and remaining publication

Attempt-03 list-price estimate: **$0.0003453**, using $0.15 input / $0.60 output
per million tokens. Both HTTP-200 calls together: $0.0006888 estimated. Actual
billing is **unknown**, and attempt-01 usage/cost is unknown; no zero-cost claim
is made for that attempt. No OpenAI API was used.

Only T-101 received accepted real-model E2E coverage; other required scenarios
were tested offline. The HTTP interface always uses mock, while the explicit
acceptance CLI is the real Groq path. This is a bounded, Russian-language local
support demo with synthetic CRM, no production operator auth or arbitrary
free-text diagnosis. No Day 30 database or lesson 1–32 runtime was changed.

No new generation is required for the video: use the retained accepted answer.
Video recording, GitHub publication and merge remain separate from technical
acceptance. PR/merge require owner authorization. Post-course backlog: unify the
curl transport with the normal adapter/live HTTP, bilingual replies, broader FAQ,
real CRM/operator auth and persistent MCP sessions.
