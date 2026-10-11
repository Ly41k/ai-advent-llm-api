# API v1 — Bublik runtime 0.8.0

Both LAN HTTPS and Tailscale HTTPS expose the same `/api/v1` contract and users.
Origins have separate browser sessions. Ollama endpoints are never exposed.
The endpoints below are implemented. FastAPI always binds loopback; stage 6 adds
explicit TLS-terminating proxy configuration. See STAGE6.ru.md for LAN/Tailscale
deployment and physical-device checks. Physical Android handoff and three-device
sync/mobile use are accepted; current evidence/limits are in FINAL_REPORT.ru.md.
Stage 5 serves the static Web UI at `/` and allowlisted `/assets/app.js` and
`/assets/app.css`, over HTTPS only. Static responses contain no private data;
chat/auth operations still require the same server-side sessions and CSRF rules.

Stage 6 uses `serve --trusted-loopback-proxy --origin <https-origin>` (repeatable).
Backend TLS flags cannot be combined with this mode. Uvicorn proxy headers remain
disabled; the application requires an actual loopback peer and a single
`X-Forwarded-Proto: https`, rejects Forwarded chains, and validates preserved Host.
An optional X-Forwarded-Host must match Host; XFF/Tailscale identity never authenticate
a user or change the client rate-limit key. Local OS processes are trusted.
Missing/invalid proxy marker is 400 `secure_transport_required`, conflicting Host
400 `invalid_host`; duplicate protected headers are rejected. Cross-origin CSRF is
403 even when both origins are permitted. HTTPS responses send HSTS max-age=86400
without preload/includeSubDomains. Default direct TLS mode retains stage-5 behavior.

## Authentication

Browser: opaque server-side session in `__Host-bublik_session`; Secure, HttpOnly,
SameSite, Path=/, no Domain. State-changing requests require a session-bound
`X-CSRF-Token` and an allowed Origin, including login/logout. Login rotates the
session. `GET auth/session` supplies bootstrap/session state and the CSRF token
to in-memory client state. GET does not log in or mutate chat data.

Other applications: `Authorization: Bearer <personal-token>`, tied to a user,
revocable and scoped. Browser JavaScript never receives such a server token.
Reject ambiguous requests carrying both browser credentials and Bearer auth.
Do not pass tokens in query parameters. Account/token administration is local CLI.

Minimal liveness may be unauthenticated inside the permitted network. All chat,
generation, export, OpenAPI and detailed readiness operations require auth.
Unknown and foreign chat/generation IDs both return 404. Owner IDs are resolved
from auth; clients cannot supply them in create/send/retry JSON.

## Routes

| Method | Path below `/api/v1` | Result |
|---|---|---|
| GET | `/health/live` | 200 minimal process status |
| GET | `/health/ready` | 200 ready / 503 unavailable; cached bounded checks |
| GET | `/auth/session` | Login state and CSRF bootstrap |
| POST | `/auth/login` | Secure session cookie; no token in response body |
| POST | `/auth/logout` | Revoke current browser session; JSON `{}` |
| GET | `/openapi.json` | Authenticated OpenAPI JSON; `service:read` |
| POST | `/chats` | 201, idempotent create; `{"title":"..."}` |
| GET | `/chats?limit=50&cursor=...` | Owner-scoped page, next cursor |
| GET | `/chats/{id}` | ID, title, revision, timestamps |
| GET | `/chats/{id}/messages?limit=100&after_sequence=...` | Ordered history page |
| POST | `/chats/{id}/messages` | 202 durable receipt |
| GET | `/generations/{id}` | Status, saved assistant snapshot, bounded metadata |
| GET | `/generations/{id}/events` | Authenticated read-only SSE |
| POST | `/messages/{id}/retry` | 202 new attempt, same user message |
| GET | `/chats/{id}/export` | Versioned JSON snapshot |

Pagination caps are 100. HTTP chat cursor is opaque and tied to an ordering;
repository stage-2 cursor is the last owned chat ID, ordered by created_at/id.
Stage 5 adds compatible optional history parameters: `latest=true&limit=50`
returns the most recent page in ascending display order. `before_sequence=N`
returns the preceding page (exclusive). These responses use `next_before_sequence`
(first sequence when page is full, otherwise null). A full final page may require
one empty fetch to establish exhaustion. Combining reverse mode with nonzero
`after_sequence` is rejected; the old forward contract/response stays unchanged.
No chat deletion, arbitrary message editing, cancellation endpoint or regeneration
of a completed/old question in v1. These require separate retention/branching rules.

## Send / retry

`POST /chats/{id}/messages`, `Idempotency-Key: <client-generated-uuid>`:

```json
{"content":"Continue our discussion.","expected_revision":12}
```

After atomic commit:

```json
{
  "chat_id":"...",
  "accepted_revision":13,
  "user_message_id":"...",
  "assistant_message_id":"...",
  "generation_id":"...",
  "replayed":false
}
```

Create-chat also requires an idempotency key. Retry body contains only
`expected_revision`; it requires a new key for the new attempt. The failed or
interrupted original user question is not inserted again. Only the latest user
question with a retryable terminal attempt may be retried.

Same key + same original client payload returns stable IDs (HTTP 200 on replay). Same key + altered payload returns 409 `idempotency_conflict`.
Successful replay never consumes another inference slot. Key scope is user and
operation/resource; records survive restart and are not automatically expired
in v1. Changes to model defaults do not alter a previously accepted job.

Clients never send model URLs, system prompts, trusted roles or unrestricted
Ollama options. Each job snapshots the server profile/context. Admission validates
the current revision and the exact suffix selected by ContextBuilder inside the
same transaction as persistence. An accepted receipt is not a completed answer.

## States and streams

Generation: queued, running, completed, truncated, failed, interrupted. User
message: accepted. Assistant placeholder: the generation state and a saved text
snapshot. Error turns remain in full history. Failed/truncated/interrupted
answers do not become ordinary inference context automatically.

SSE uses monotonically numbered updates and snapshot resynchronization. Reconnect
must not append a previously delivered prefix again; the authoritative GET/SSE
snapshot can replace the rendered text. If replay of a Last-Event-ID is unavailable,
send a fresh snapshot rather than invent missing deltas. Generation execution
continues when a subscriber disconnects. Polling fallback is required on mobile.
Do not advertise unsaved deltas as persisted history. API GET serializes
only bounded context metadata, not the whole internal prompt/worker capability.

## Errors

```json
{"error":{"code":"stale_revision","message":"Reload the chat and retry.","retryable":false},"request_id":"..."}
```

| HTTP | Codes / semantics |
|---:|---|
| 401 | authentication_required / expired credential |
| 403 | csrf_failed / insufficient_scope |
| 404 | not_found; includes foreign resources |
| 409 | stale_revision, chat_has_outstanding_generation, idempotency_conflict, retry_not_allowed |
| 413 | request_body_too_large |
| 422 | invalid request, invalid_message, context_budget_exceeded |
| 429 | owner rate limit / user_queue_full; Retry-After |
| 503 | model_unavailable, global_queue_full, inference_recovery_required, storage_unavailable |

After 202, inference errors are recorded on the generation, not a retrospective
HTTP status change. A failed generation emits a final `snapshot` with terminal status and error_code.
Credential/storage failures emit `event: error`; stream lifetime expiry emits
`event: reconnect`. Safe bounded error codes contain no upstream body,
personal content, cookies, credentials, filesystem exception or SQL text.

All private API, exports and SSE use `Cache-Control: no-store`. Service worker
must bypass these routes. Do not load external fonts/CDN/analytics on the chat.
Readiness failure gates new inference; authenticated stored history remains
available when Ollama is offline, assuming storage itself is healthy.


## Operational limits

Sessions: anonymous bootstrap 15 min; authenticated 12 h absolute expiry.
Cookie uses SameSite=Strict. Login rotates session/CSRF; password reset revokes
all sessions and tokens. Tokens default to 30 days, CLI selectable 1–365 days.
Scopes: chats:read, chats:write, chats:export, service:read. No query credentials,
CORS, public signup, token issuance over HTTP, or external Swagger CDN.

Browser mutations require exact same allowed HTTPS Origin and X-CSRF-Token;
Bearer mutations with no browser credential do not require CSRF. Plain HTTP
Bearer access is restricted to loopback operators; browser auth requires HTTPS.
Direct serve does not trust forwarded headers. Explicit trusted-loopback-proxy
mode requires the raw loopback peer, HTTPS marker and preserved allowed Host.
Bare HTTP is rejected in that proxy mode, including Bearer requests.

Persistent sliding-window quotas: 10 accepted generations/min/user (all tokens
and sessions share quota), 120 authenticated HTTP requests/min/user, anonymous
bootstrap 60/min/peer, unauthenticated protected requests 60/min/peer, login
5/min/peer. Login verification concurrency=2. Quota+admission commit atomically;
failed admission/replay does not consume inference quota. General HTTP quota
still applies to replay. Limits use UTC wall clock; backward clock jumps may
conservatively delay expiry. Rate keys never use supplied X-Forwarded-For.

Body max=32 KiB including chunked data, read deadline=10 s; errors 413/408.
JSON required on mutation routes (415); duplicate keys/headers and unknown body
fields rejected. UTF-8 message max=16 KiB, assistant max=64 KiB. Starting inference
profile remains 8192 context, 1024 output, temperature=0, margin=512. There are
8 queued slots, 3 outstanding/user, one global running generation, queue deadline
600 s. No caller-supplied model/URL/roles/options.

Runtime 0.8.0 defaults to the measured `private-chat-v2` system prompt. Historical
`private-chat-v1` snapshots retain their original text/profile and IDs; idempotent
replay returns the original generation. A new turn can continue the same chat
with v2. The local operator may select v1 with `--prompt-version private-chat-v1`;
clients cannot select prompts. Startup refuses `queued_profile_mismatch` before
claiming jobs when queued profiles differ from the selected profile. Drain them
with the matching profile before upgrading; do not rewrite or delete their snapshots.

SSE: two connections/user, eight global, 900 s lifetime, heartbeat 10 s.
Each snapshot ID is a durable per-message revision maintained by SQLite triggers.
Always replace the displayed snapshot, including the first event on reconnect;
Last-Event-ID does not request delta replay. Disconnect does not cancel inference.
Revoked/expired credentials are checked during the stream. GET generation excludes
internal prompts, selected history IDs and dispatch capabilities; owner export
intentionally includes original context/profile snapshots for data continuity.

Readiness probes are bounded to 5 s and cached 5 s; queue/gate checked each call.
Authenticated readiness includes model metadata, profile and runtime source hashes
for report comparison. Hash comparison is not an attestation/signature. Detailed
readiness failing does not prevent authorized history access if SQLite is healthy.

No private response caching; no access-log request lines by default. Error responses
never serialize submitted validation input/upstream bodies/tracebacks. Full chat
export currently materializes one snapshot in RAM: paged/streaming export is backlog.

## Post-course history RAG (introduced in 0.9.1, now schema 3)

Message creation and retry accept optional strict boolean `use_memory`, default
`false`. It is part of the idempotency fingerprint when true; changing the mode
for an already-used key yields 409. Omitted/false preserves old fingerprints.
The Web UI defaults to enabled and always sends the explicit mode. Reload/logout
restores enabled; browser storage is not used for this preference.

`POST /api/v1/memory/search` accepts `{"query":"What laptop did I mention?"}`
(up to 2048 UTF-8 bytes), requires `chats:read` and returns `policy_version`,
`indexed_messages`, `search_seconds`, `reason` and up to three `sources`.
Browser sessions require the existing exact Origin/CSRF headers even for this
read-only POST. Queries are in JSON, not URLs. Existing request quotas apply.
This endpoint requires no loaded model; generation still requires Ollama readiness.

`GET /api/v1/chats/{chat}/messages/{message}` requires `chats:read`, validates
both the chat owner and message/chat relationship, and returns the original
message. Unauthenticated requests are401; foreign/mismatched IDs return404.

`GET /api/v1/chats/{chat}/messages/{message}/context?before=4&after=4`
requires the same scope/owner checks. Both ranges are integers0..10. It returns
`anchor_message_id`, ordered original `items` (at most21), `has_earlier`,
`has_later`; no full inference prompt is exposed. It works without Ollama.
Use the existing history pagination to read beyond this bounded window.

A RAG generation's public `context.memory` contains `enabled`, `policy_version`,
`indexed_messages`, `search_seconds`, and `sources`. Each source contains
`chat_id`, `message_id`, `sequence`, character `start`/`end`, whole-message
`source_sha256`, exact `quote`, `created_at`, `role` and `status`. Historical
0.9.0 sources without role/status represent accepted user text. The history endpoint includes
the same `memory` on assistant messages; prompts/engine provenance remain private.
The source block and policy are frozen at admission and survive retries/restarts
without repeating retrieval for idempotent replay. A new retry can request a new
mode explicitly and runs a new search. The UI retry uses the current checkbox.

All accepted user messages and nonempty terminal assistant text belonging to
the authenticated owner are indexed (`history-fts-v2`). Failed/interrupted turns
are preserved and searchable with status. Running/queued assistant text is still
mutable and is excluded from RAG until terminal; it remains readable in history.
Assistant statements are not verified facts about the user.
FTS5 uses words/prefixes, not embeddings. Sources shown are retrieved context, not
automated grounding verification. Index failure returns503 (public
`storage_unavailable`) and does not insert messages or fall back to normal chat.
No matches remains explicit memory mode with an empty archive and uncertainty
instruction. Context remains at most8192, including1024 output and512 margin;
memory messages are bounded to2600 conservative input tokens and three800-byte
quotes; recent complete pairs fill the remaining input budget.

## RU/EN preferences and explicit reply language (0.10.3, schema 3)

Only exact `ru` and `en` codes are supported. No `auto`, locale variants or
caller-supplied language prompts. All existing authorization, body-size limits,
quotas, transport and CSRF rules apply.

| Route | Scope | Contract |
|---|---|---|
| GET `/api/v1/preferences` | chats:read | Current owner's `{ui_language, reply_language, revision}` |
| PATCH `/api/v1/preferences` | chats:write | All fields `{ui_language, reply_language, expected_revision}` required; returns current settings |

Preferences have an independent nonnegative revision. A changed value increments
it; identical values do not. Stale revision returns `409 preferences_changed`.
Read current settings after conflict or uncertain delivery; do not blindly replay
an old PATCH. Unsupported values/extra fields/types return 422. No owner ID in
the payload: credentials determine the owner. Cookies require same HTTPS Origin
and X-CSRF-Token for PATCH; read-only tokens cannot update preferences.

Message creation and explicit retry add optional `reply_language: "ru" | "en"`.
Omission/null preserves legacy behavior and request fingerprints; account settings
are not silently applied to those old API requests. New clients first read
preferences, then explicitly pass the chosen reply language. Web UI does this.
Different language with the same idempotency key is a payload conflict; the same
language replays the original receipt even after preference changes.

The selected language and `language_policy: "reply-language-v4"` are frozen in
the generation's public context metadata and private snapshot. History includes
reply_language on assistant messages that have this metadata; old records are
unchanged. The effective first system instruction replaces the conflicting user-language
rule and is included in the context budget. The historical profile, model, original
stored input and selected memory quotations remain unchanged. For new explicit-language
requests, the latest model user message ends with an explicit application reply-language
instruction. It states that language requests in user text/history do not change the
selected language and rejects an opposite-language version of the answer. The exact
suffix is frozen and budgeted before admission. Private context
stores `original_user_content`; public context exposes only `language_hint` with
`policy_version: "latest-user-language-hint-v2"`, `original_sha256` and `rendered_sha256`.
The adapter checks the frozen suffix and hashes before dispatch. History never gains
the suffix. Legacy v1/v2/v3 snapshots are validated and dispatched without rewriting;
new requests use v4. Explicit translations/code/quotes may use other languages;
this is a model instruction, not a universal output guarantee or automatic retry.

GET `/manifest.webmanifest?lang=ru|en` returns localized PWA metadata with
Content-Language and no-store. Omitted lang means ru; unsupported values return
422. `/assets/i18n.js` is an authenticated-data-free static catalog served under
the existing CSP. API error codes and JSON field names remain language-neutral;
the browser translates labels locally without storing personal data or secrets.

Additive migration 003 creates user_preferences, defaults existing/new owners to
ru/ru, and preserves historical messages/snapshots/receipts. Archive v1 accepts
exact schemas 2/3; old snapshots are restored before a separate upgrade. New
archives retain preferences. Runtime 0.9.1 refuses schema 3: back up before upgrade.
See [deployment and acceptance](LANGUAGES.ru.md).

0.10.0 users: [reply language conflict fix](LANGUAGE_FIX.ru.md). Schema remains 3.
