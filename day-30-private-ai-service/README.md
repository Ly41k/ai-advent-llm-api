# Day 30 — Bublik Private AI Service

A private chat backed by local Qwen. The MacBook performs inference and stores
full history; Mac, Android and iPhone continue the same conversations. Other
applications use a versioned HTTP API. No cloud LLM or automatic fallback.

**Stages 1–9 implemented.** Course baseline **0.8.0**, SQLite schema **2**, prompt
**private-chat-v2**. The MacBook Pro M1 / 32 GB baseline passed **259/259 technical
and 13/13 quality checks**, saved history after restart **11/11**, and current
LAN HTTPS/launchd **6/6**. Three-device sync, mobile-data chat and Tailscale
reconnection were manually confirmed. See [final evidence and limits](FINAL_REPORT.ru.md).

Working-history archive/restore was rehearsed on the operator's Mac after the course; physical transfer to another host and old console-owner transfer remain pending. Saved tailnet policy has not been independently audited;
phone LAN CA installation is deferred. These are not recorded as passed.

## History portability after Day 30

The first extension adds verified SQLite archives and restoration into a new
private database, preserving conversation IDs, original messages and snapshots.
Restored browser sessions are cleared and API tokens revoked. No API/runtime or
model behavior changes. See [the portability guide](MEMORY_PORTABILITY.ru.md) for
commands, limits and a transfer rehearsal. Archives are not encrypted; pending or
uncertain inference snapshots cannot be restored by this first-stage tool.
Versioned long-term facts are not implemented. Lexical retrieval over both sides of history is added below.

## Post-course history RAG — 0.9.1

The **«Искать в прошлых разговорах»** switch enables local FTS5 retrieval over
all saved user text and nonempty terminal assistant text owned by the signed-in user. Up to three
exact fragments, timestamps, IDs and SHA-256 hashes are frozen in each generation
snapshot and displayed below the reply, with author and completion status. Sources
and the surrounding original conversation can be reopened.

The private `memory-index/` cache is rebuilt from the primary history. At its introduction, core schema
stayed **2**; archives preserve history and RAG snapshots, without transporting the
cache. No embeddings or second model are loaded. Lexical search cannot guarantee
recall of paraphrases. The Web UI enables retrieval by default; users can disable
it for a request. API v1 omission still means false for compatibility. Index failures reject RAG
admission with 503; there is no silent fallback.

See [installation and Mac checks](RAG_MEMORY.ru.md). The Day 30 live results above
belong to 0.8.0; 0.9.1 Qwen/phone checks are separate. Displayed sources are context
supplied to the model, not automatic verification of every generated claim.

See [memory continuity and future layers](MEMORY_ARCHITECTURE.ru.md). Summaries and
structured facts remain future work; originals are not replaced or aged out.

## Russian and English — 0.10.3

Two independent settings select the interface language and new reply language.
Settings are stored per user and loaded across devices. Only `ru` and `en`
are accepted; originals and memory quotations retain their saved text.
The Web UI sends an explicit reply language, frozen in the generation snapshot.
Legacy API requests without this field retain previous behavior.

An additive migration upgrades SQLite **2 → 3**; verified archives support both
schemas and new archives include language settings. Back up before upgrading;
the old runtime cannot reopen schema 3. See [upgrade and device checks](LANGUAGES.ru.md).
Version 0.10.3 adds an explicit model-only language hint that overrides contrary language requests to the latest user input; its bytes
are frozen and budgeted while stored messages remain original. See [update checks](LANGUAGE_EXPLICIT_HINT_FIX.ru.md).
Language instructions guide Qwen; they do not guarantee every output.
FTS5 remains lexical, without automatic multilingual semantic retrieval.

## Architecture

FastAPI/Uvicorn authenticates requests and atomically admits jobs into SQLite WAL.
One coordinator builds bounded context and dispatches one generation at a time to
Ollama at `127.0.0.1:11434`. Saved partial/terminal snapshots reach the responsive
Web UI through SSE with polling fallback. Python does not load the model.

Tailscale Serve is the main private HTTPS entry point, including mobile data.
Caddy provides direct LAN HTTPS with a trusted local CA. The API binds only
`127.0.0.1:8000`. Per-user launchd agents start API/Caddy after Mac user login.
Network identity does not replace application login or ownership.
See [architecture](ARCHITECTURE.ru.md) and [API v1](API.md).

## MacBook setup

The repository contains the complete implementation. Use these commands for a
new installation; an existing installation should keep its database and owners.
Documentation-only updates do not require restarting the API.

Python **3.13+**, macOS/POSIX, SQLite, and Ollama with downloaded
`qwen2.5:14b` Q4_K_M are required. From the repository root, for a new setup:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
cd day-30-private-ai-service
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -c 'from bublik_service import __version__; print(__version__)'
```

Reuse an existing root virtualenv; from this lesson use `source ../.venv/bin/activate`.
Do not start another `ollama serve` if the desktop application already serves it.
Create a separate database for a new installation:

```bash
BUBLIK_DATA_DIR="$HOME/bublik-private-ai"
BUBLIK_DB="$BUBLIK_DATA_DIR/chats.sqlite3"
python -m bublik_service --db "$BUBLIK_DB" init-db
python -m bublik_service --db "$BUBLIK_DB" user-add operator
python -m bublik_service --db "$BUBLIK_DB" doctor
```

Passwords are prompted privately; minimum 12 characters. Put `--db` before the
subcommand. `.env` is not automatically loaded. Default macOS storage is
`~/Library/Application Support/BublikPrivateAI/chats.sqlite3`; `BUBLIK_DATA_DIR`
overrides its directory. Keep databases, tokens and TLS keys outside git.

Connect Tailscale on Mac and phones. With the tested macOS application:

```bash
BUBLIK_TS_CLI="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
"$BUBLIK_TS_CLI" status
BUBLIK_TAIL_HOST="$("$BUBLIK_TS_CLI" status --json | python -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
BUBLIK_TAIL_URL="https://$BUBLIK_TAIL_HOST"
```

Configure tailnet access to the Mac TCP:443 and HTTPS certificates as described
in [network setup](STAGE6.ru.md). Review existing Serve configuration before
adding the route; do not replace another service already using it:

```bash
"$BUBLIK_TS_CLI" serve status
"$BUBLIK_TS_CLI" serve --bg --https=443 http://127.0.0.1:8000
"$BUBLIK_TS_CLI" serve status
"$BUBLIK_TS_CLI" funnel status
python -m bublik_service --db "$BUBLIK_DB" serve --port 8000 \
  --trusted-loopback-proxy --origin "$BUBLIK_TAIL_URL"
```

Use tailnet-only Serve, without public Funnel or router port forwarding. Audit
both grants and legacy ACLs for broad allow rules. Configure origins explicitly;
raw HTTP to the trusted-proxy backend correctly fails `secure_transport_required`.
Run one API worker without reload. Do not start a second manual server while the
installed LaunchAgent runs. Detailed operations: [RUNBOOK.ru.md](RUNBOOK.ru.md).

## Phones and LAN

On Android/iPhone, connect Tailscale to the same tailnet, open the Mac HTTPS
hostname and sign in as the same Bublik user. No API token or custom CA is needed
for the `.ts.net` URL. Tailscale remains necessary for that URL on home Wi-Fi.
The Mac must stay awake and online with API/Ollama available.

Open the same conversation to continue stored history. Android browser menu:
install/add to home screen. iPhone Safari: Share → Add to Home Screen. Installation
was manually confirmed on both phones. This PWA has no service worker or offline
private-history cache; inference still runs on the Mac.

Direct home access uses Caddy at `https://LAN_IP:8443`, a matching allowed origin
and trust in your own root CA. Tailscale is optional on that direct route.
Current Caddy/LAN HTTPS was checked from the Mac; phone CA setup is deferred.

## Daily use and Mac sleep

With launchd installed, open the chat URL after connecting the Mac and phone to
Tailscale; do not start a second `serve` process. Wait for **«Ответ сохранён»**
(answer saved) and check the same conversation on another device. Readiness and
saved history have different roles: history remains readable during model outages.

Before turning off the Mac's internet or closing its lid, wait for all replies to
be saved and stop sending new requests. To stop the installed API cleanly:

```bash
launchctl bootout "gui/$(id -u)/local.bublik.private-ai.api"
/usr/sbin/lsof -nP -a -iTCP:8000 -sTCP:LISTEN
```

Wait until the listener check has no output. After waking the Mac, restore its
network and Tailscale connection, open Ollama if you quit it, then start the API:

```bash
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/local.bublik.private-ai.api.plist"
```

If you did not stop the API before sleep, check `launchctl print` and reopen the
chat first; do not bootstrap a service that is already running. Keep the same
database. The chat is unavailable while its Mac host sleeps or is offline.
Details and interruption recovery: [RUNBOOK.ru.md](RUNBOOK.ru.md).

## API, persistence and limits

`/api/v1` exposes live/ready, browser login/session/logout, chats/history,
durable send, generation status/SSE, retry, export and authenticated OpenAPI.
Other applications use locally issued scoped, expiring and revocable Bearer tokens.
Browser auth uses Secure/HttpOnly/SameSite=Strict cookies and matching Origin/CSRF.
Foreign resources return 404; callers never supply owner IDs.

| Limit | Value |
|---|---:|
| Context / max output / temperature | 8192 / 1024 / 0 |
| Context safety margin | 512; input upper bound ≤6656 |
| Active inference / queued jobs | 1 / 8 |
| Outstanding jobs per owner | 3 |
| Accepted generations / HTTP requests per owner | 10 / 120 per sliding 60 s |
| JSON body / user text | 32 KiB / 16 KiB UTF-8 |
| Queue deadline | 600 s |

Full history is independent of the inference suffix. Only recent completed pairs
enter ordinary context; omissions are visible. The system prompt and new question
are not silently truncated. Counting uses a verified conservative byte-BPE upper
bound, not an exact tokenizer. Failed/truncated/interrupted turns remain stored.

Idempotency returns stable IDs without duplicate messages or another inference
quota charge. A 202 receipt means durable admission, not completion. History stays
readable during model outages. Unknown inference requires explicit verified recovery;
no hidden replay. Old v1 snapshots survive new v2 turns in the same conversation.

No credentials, drafts or history in browser localStorage/sessionStorage; no
CDN/analytics or raw HTML model output. Access logs are disabled; errors do not expose
input/secrets/upstream tracebacks. Discarded launchd output limits diagnostics.
Backup uses the SQLite backup API and refuses overwrite. Working-history restore
into a separate database was rehearsed by the operator; retention, off-host copies
and physical transfer remain separate tasks.

After starting the API, from a second terminal where `BUBLIK_TAIL_URL` is set:

```bash
curl --max-time 10 "$BUBLIK_TAIL_URL/api/v1/health/live"
curl --max-time 10 -i "$BUBLIK_TAIL_URL/api/v1/chats"
```

Expected: `200` / `{"status":"alive"}` and `401` without credentials. Open the
same HTTPS URL in the browser, sign in, create a conversation and wait for a saved
reply. Liveness alone does not prove that Qwen is ready. See [API.md](API.md) for
authenticated readiness, routes, error codes and token scopes.

## Verification and docs

```bash
python scripts/verify_report.py reports/verified/languages-policy-v2-offline-20261011.json
python -W error::ResourceWarning scripts/check_storage.py
```

The first checks the new221/221 offline report against81 source files; the
second runs the complete current offline suite and writes a new report. Earlier
RAG198/198, storage-only69/69 and course143/143 reports remain historical; their full-source
manifests need not match the new runtime. Hashes are neither
signatures nor live network/model proof.
Chromium/PWA fixtures use synthetic inference; real Mac Qwen and device evidence
are recorded separately. Original successful and failed JSON are preserved.

The user has recorded a UI demonstration with messages shared across devices.
The console scenario is optional; it does not replace saved verification reports.

See [final report](FINAL_REPORT.ru.md), [acceptance](ACCEPTANCE.ru.md),
[console video](CONSOLE_VIDEO.ru.md), [detailed stage-8 evidence](VALIDATION.stage8.ru.md),
[prompt upgrade](PROMPT_V2.ru.md), [launchd/PWA](STAGE7.ru.md), [plan](PLAN.ru.md)
and [backlog](BACKLOG.ru.md). Rust is deferred until after the course.

Stage 9 updates root READMEs. This changes the Day 21 indexed corpus: rebuild that
index before a new strict RAG live run. Day 30 does not use the index. Previous
lesson implementations, databases and historical reports remain unchanged.

[Русский](README.ru.md)
