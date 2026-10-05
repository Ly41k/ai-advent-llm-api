**English** | [Русский](README.ru.md)

# Day 25 — persistent RAG chat with sources and task memory

Day 25 turns the grounded RAG pipeline from Days 21–24 into a persistent local Bublik chat.

The final **v24** implementation stores full dialogue history and evidence-bound task memory in SQLite, resolves follow-up questions with bounded recent context, performs fresh retrieval for every ordinary question, publishes exact source passages, and supports durable long-dialogue evaluation with process ownership, checkpoints, and resume.

## Final v24 status

The tested v24 acceptance cases are complete.

- **181 Day 25 tests passed**.
- **169 regression tests from Days 21–24 passed**.
- Final live 12+12 run: **24/24 answers passed manual review**.
- **47 exact quotations** were checked against repository files and line ranges.
- The 24 live questions produced **48 embedding calls and 48 search calls**.
- `--process-per-turn` used **24 distinct question processes/request IDs**.
- Two additional negative controls passed with the expected `unknown` behavior.
- Across those 26 live cases: 24 grounded answers, 2 expected refusals, 51 embedding calls, and 51 search calls.

Evidence and detailed review:

- [v24 audit](AUDIT_V24.ru.md)
- [v24 installation/check](RELEASE_V24.ru.md)
- [final v24 acceptance](ACCEPTANCE_V24.ru.md)
- [12+12 manual review](reports/live/live-long-scenarios-v24-review.ru.md)
- [negative-control review](reports/live/negative-controls-v24-review.ru.md)

These results validate the described scenarios, not arbitrary future prompts or perfect model behavior.

## Architecture

Request flow:

```text
message
  → recent completed history + task state
  → standalone/resolved question
  → fresh embedding
  → scoped candidate retrieval
  → inclusive cosine filter
  → exact evidence selection
  → citation/source validation
  → coverage validation
  → answer + explicit sources
  → durable turn persistence
```

Day 25 reuses the current Python implementation from earlier lessons:

- **Day 21:** document corpus, chunking, embeddings, SQLite knowledge base;
- **Day 22:** first complete question → retrieval → context → answer RAG flow;
- **Day 23:** query rewrite, candidate retrieval, cosine filtering;
- **Day 24:** exact quote selection, app-owned citations, strict coverage validation.

Day 25 adds persistence, conversation planning, task memory, lesson-scoped retrieval, failure recovery, and durable evaluation.

The chat does **not** treat old assistant answers or task memory as current repository evidence. They can help resolve intent and relevance; factual output still has to come from new retrieval.

## Requirements

- Python **3.13** target.
- macOS/Linux local filesystem for v24 process ownership (`fcntl` / POSIX advisory locks).
- Local Ollama for live chat/evaluation.
- No Groq key is needed for Day 25.
- The base Day 25 implementation uses the Python standard library.

Default live profile:

```text
embedding model: bge-m3
answer model: qwen2.5:14b
strategy: fixed
candidate K: 20
final K: 5
raw cosine threshold: >= 0.50
rewrite: heuristic
coverage: strict
Ollama context: 32768
recent completed history: 4 turns / 2400 chars
task state budget: 6000 chars
```

Character budgets are application limits, not exact model-token counts.

## Quick start

From the repository root:

```bash
source .venv/bin/activate

python day-25-rag-chat/test_day25.py -v
python day-25-rag-chat/main.py offline-demo

ollama pull bge-m3
ollama pull qwen2.5:14b

python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify

python day-25-rag-chat/main.py chat
```

Changing the answer model does not require rebuilding embeddings. Changing the embedding model does.

The Day 21 index contains root README files, Days 1–20 lesson READMEs, and Days 16–20 non-test Python files. Day 21–25 lesson READMEs are not part of the indexed corpus by default.

A new Git commit or a root README change can make the index revision stale. Rebuild/verify before a strict live run. `--allow-stale-index` exists only as an explicit override and keeps index provenance in traces.

## CLI

Global options must appear **before** the subcommand.

Examples:

```bash
python day-25-rag-chat/main.py --answer-model qwen2.5:7b chat
python day-25-rag-chat/main.py chat --session <ID>
python day-25-rag-chat/main.py ask "Where is it stored?" --session <ID> --output answer.json

python day-25-rag-chat/main.py sessions
python day-25-rag-chat/main.py state <ID>
python day-25-rag-chat/main.py history <ID>
python day-25-rag-chat/main.py export <ID> --output dialogue.json
```

Important global options include:

```text
--db
--chat-db
--url
--model
--answer-model
--verifier-model
--num-ctx
--num-predict
--timeout
--strategy
--candidate-k
--final-k
--min-similarity
--rewrite-method
--history-turns
--coverage-policy
--allow-stale-index
```

## Chat commands

The interactive CLI prints `session=<ID>`. Reuse that ID to continue after restart.

| Command | Action |
|---|---|
| `/new [title]` | Create an isolated session |
| `/use ID` | Switch to a session |
| `/sessions` | List sessions |
| `/state` | Inspect task memory |
| `/history` | Inspect complete persisted history, sources, and errors |
| `/goal TEXT` | Set or explicitly change the dialogue goal |
| `/constraint TEXT` | Add a constraint |
| `/clarify TEXT` | Add a user clarification |
| `/term NAME=DEFINITION` | Set/correct a term |
| `/forget goal` | Clear the goal |
| `/forget constraints KEY` | Remove one constraint |
| `/forget clarifications KEY` | Remove one clarification |
| `/forget terms KEY` | Remove one term |
| `/export PATH.json` | Export history, responses, provenance, task state, traces, and edit events |
| `/recover` | Recover a pending turn after its owning process is no longer alive |
| `/help` | Show help |
| `/quit` | Exit while preserving the session |

Example:

```text
/goal Prepare a check of the Day 18 scheduler.
/constraint Use SQLite.
/clarify We are discussing Day 18 scheduling.
/term snapshot=saved GitHub repository state
Which process executes scheduled jobs?
Where is it stored?
/state
/history
/quit
```

## Task memory

Task state is stored separately from normal dialogue history:

```text
goal
constraints
clarifications
terms
```

Memory updates can come from explicit commands or ordinary messages. Labelled Russian forms such as `Цель:`, `Ограничение:`, `Уточнение:` and `Термин:` are supported.

Every accepted memory value must have literal evidence in the current user message. Stored entries retain value, evidence, turn, and origin.

Important guards:

- an incidental next question does not silently replace an existing goal;
- planner updates cannot overwrite concurrent memory changes: stale writes are rejected;
- new question fragments and immediately negated text are rejected as memory facts;
- `/forget` is the explicit deletion path;
- a full task-state budget rejects new data visibly rather than dropping old entries.

Literal provenance proves where text came from; it does not prove that the planner understood its meaning correctly. Use `/state` to inspect and correct memory.

## History, interruption, and recovery

The full history is persisted in `day-25-rag-chat/chats.db`.

Only bounded recent completed history is sent back to the planner. Failed retries and pending/error turns do not consume that completed-history window.

The user message is reserved in SQLite before model/network work. A normal technical failure is stored as an error instead of a fabricated model answer.

v24 adds live-turn ownership on macOS/Linux:

- concurrent turns in one session are blocked;
- `/recover` refuses to cancel a turn while its owning process still holds the OS lock;
- after a crashed process releases the lock, recovery marks the pending turn as an error and records the recovery event;
- different sessions remain independent.

## Sources and grounding

Day 25 preserves the extractive Day 24 protocol.

The model selects quote IDs from retrieved data; the application copies the exact source passage and owns:

- source number;
- repository path;
- section;
- chunk ID;
- line range;
- claim/quote binding.

Every answered turn prints an explicit `Источники / Sources` block.

If the reference is ambiguous, retrieval is insufficient, the model returns unknown, or strict validation fails, the user gets an explicit refusal/clarification and **no fabricated confirmed source**.

Old answers and task memory can help interpret the current request but cannot become proof for repository facts.

### Coverage policies

Default:

```text
--coverage-policy strict
```

A negative coverage result blocks publication.

Optional:

```text
--coverage-policy diagnostic
```

Diagnostic mode may expose exact passages with a visible manual-review warning while preserving the negative judgment. Such a turn does not pass the Day 25 `coverage_pass` evaluation check.

## Lesson-scoped retrieval

When the resolved question clearly names one lesson, Day 25 restricts retrieval to that lesson namespace **before** candidate/final limits.

It performs two fresh dense branches when document titles are available:

1. rewritten/current query;
2. the same query plus indexed document titles from the selected lesson.

Candidates keep the maximum **actual cosine** observed across those branches. Both branches and scores are recorded in trace metadata. The cosine threshold is not lowered.

Historical assistant answers, task-memory facts, canned answers, and synthetic similarity scores are not injected into evidence.

## Offline demo

Run:

```bash
python day-25-rag-chat/main.py offline-demo
```

The offline demo uses:

- the real repository corpus;
- the real chunker;
- SQLite cosine search;
- the real Ollama HTTP client contract;
- the real citation/source validators;
- persistent chat state and the real evaluation path.

Only model behavior is replaced:

- lexical hash-256 vectors instead of BGE-M3;
- scripted planner/selector/coverage JSON instead of Qwen.

Fixture retrieval settings are explicitly different from production (`40/20/cosine0.0`).

The 24 scripted turns perform **48 embedding and 48 search calls** because the lesson-scoped retrieval path uses two fresh query branches per scoped turn. This verifies software contracts, not live semantic quality.

## Long scenarios and live evaluation

`scenarios.json` contains two dialogues of 12 user turns each:

1. Day 18 scheduling;
2. Day 20 MCP orchestration.

Together they contain 24 user questions / 48 messages when all answers succeed. They exercise:

- goals;
- constraints;
- clarifications;
- terms;
- short follow-ups;
- topic detour;
- return to the saved goal;
- persistent history and task state.

### Durable v24 live run

Recommended final command:

```bash
python day-25-rag-chat/main.py evaluate \
  --process-per-turn \
  --output day-25-rag-chat/reports/check/live-long-scenarios-v24.json
```

`--process-per-turn` launches every question in a separate CLI process.

After every turn the evaluator checkpoints the JSON report. An unfinished report has:

```text
run_status=running
```

Resume the same run with identical settings:

```bash
python day-25-rag-chat/main.py evaluate \
  --process-per-turn \
  --resume \
  --output day-25-rag-chat/reports/check/live-long-scenarios-v24.json
```

Resume validates scenarios, configuration, index revision, persistent history, and saved answers. Completed questions are not repeated. One committed turn lost between SQLite commit and JSON checkpoint can be reconciled from authoritative history.

A recovered technical error remains a failure; resume is for durability and diagnostics, not for turning a broken run into a clean PASS.

Expected clean summary:

```text
run_status=completed
user_turns=24
messages_including_answers=48
restart_kind=process_per_turn
all_checks_pass=true
model_quality_verified=false
manual_source_review_required=true
```

The last two flags intentionally remain false/true after automatic success: software validation is not human semantic review.

## Final live v24 result

The preserved final run was manually reviewed against the acceptance checklist.

Confirmed for the two 12-turn dialogues:

- 24 answers;
- 0 refusals;
- 0 technical errors/planner warnings;
- 47 literal quotes matched repository files/line ranges;
- 48 embedding calls;
- 48 search calls;
- 24 distinct process IDs and request IDs;
- saved goal, two constraints, clarification, and term in each final task state;
- topic detour did not overwrite the saved Day 20 goal;
- return-to-goal retrieval correctly returned to Day 20.

Two extra negative controls also passed:

1. ambiguous `Where is it stored?` in a new session → `unknown / ambiguous_reference`;
2. request for the exact row count in the user's local Day 18 `schedule.db` → `unknown / insufficient_context`.

Across the 26 reviewed live cases: **24 grounded answers + 2 expected unknowns, 51 embedding calls and 51 search calls**.

See `ACCEPTANCE_V24.ru.md` and the preserved reviews for the exact expected meaning of each turn.

## v24 reliability work

v24 focuses on truthful, durable evaluation rather than adding new RAG features.

It adds or strengthens:

- live-owner POSIX locking;
- correct recovery after crashed processes;
- one SQLite snapshot for export;
- atomic JSON output;
- output-path protection for chat/index databases and SQLite sidecars;
- strict JSON parsing for planner/intermediate model replies;
- rejection of duplicate keys and non-finite constants;
- real `retrieval_trace` recording;
- per-turn process evaluation;
- checkpoint after every turn;
- safe `--resume`;
- reconciliation of one committed-but-uncheckpointed turn;
- recomputation of checks from authoritative persistent data;
- independent source-offset/claim/rendered-answer verification.

## File map

| File | Purpose |
|---|---|
| `main.py` | CLI, configuration, Ollama wiring, index revision checks, evaluation subprocesses |
| `chat_agent.py` | One chat turn, fresh retrieval, grounded answer, source rendering |
| `chat_store.py` | SQLite sessions/history/state, snapshots, turn persistence |
| `lease25.py` | POSIX process ownership and recovery protection |
| `conversation.py` | Structured planner, follow-up resolution, bounded context, evidence helpers |
| `memory.py` | Evidence-bound task memory |
| `retrieval25.py` | Lesson namespace retrieval and two-branch query expansion |
| `requirements25.py` | Day 25 intent-aware coverage requirements |
| `io25.py` | Protected/atomic JSON output |
| `evaluate25.py` | Long-scenario evaluator, checkpoint/resume, source checks |
| `scenarios.json` | Two 12-turn scenarios |
| `offline_demo.py` | Scripted HTTP/SQLite contract fixture |
| `test_day25.py` | Contract, failure, persistence, integration, and regression tests |
| `support25.py` | Reuse of Days 21/23/24 modules |

## Limits

- Local single-user CLI; no web authentication or multi-user service.
- The chat does not execute arbitrary user code.
- The chat does not call external MCP tools.
- Full history is durable, but model context is intentionally bounded.
- Old details outside task state and recent completed history can require clarification.
- Planner interpretation can still be wrong even when literal provenance is valid.
- Exact citations prove provenance, not complete semantic correctness.
- Live-model quality is specific to the tested prompts/models/settings.
- POSIX ownership behavior is designed/tested for macOS/Linux local filesystems.

## Historical implementation notes

The main README now describes the final v24 behavior. Detailed intermediate fixes remain in the repository for auditability, including:

`LONG_SCENARIO_FIX.ru.md`, `TABLE_AUDIT_FIX.ru.md`, `MIXED_PROOF_FIX.ru.md`,
`SELECTION_FIX.ru.md`, `FRAGMENT_QUALITY_FIX.ru.md`, `PROCESS_SCOPE_FIX.ru.md`,
`DRAFT_FRAGMENT_FIX.ru.md`, `PYTHON_FRAGMENT_FIX.ru.md`,
`SELECTION_DOMAIN_FIX.ru.md`, `CONDITIONAL_AUDIT_FIX.ru.md`,
`REQUIREMENTS_INTENT_FIX.ru.md`, `SOURCE_UNIT_FIX.ru.md`,
`RELEASE_V22.ru.md`, `RELEASE_V23.ru.md`, `RELEASE_V24.ru.md`, and
`AUDIT_V24.ru.md`.

For the final course submission state, start with `AUDIT_V24.ru.md` and `ACCEPTANCE_V24.ru.md`.
