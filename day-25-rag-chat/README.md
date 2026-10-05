**English** | [Русский](README.ru.md)

# Day 25 — persistent RAG chat with sources and task memory

A standalone Bublik CLI lesson reusing the current Days 21–24 Python modules. Days 21–23 remain unchanged; Day 24 adds an optional requirements factory, preserving its default behavior (135 regression tests pass). Full conversation history and task state are stored in `day-25-rag-chat/chats.db`, separately from the shared Day 21 knowledge index. Every ordinary question triggers fresh retrieval.

Message → recent history + task state → standalone question → embedding → candidates → inclusive cosine filter → exact evidence selection → citation/coverage validation → answer + sources → persisted turn.

## Run

From the project root, using your existing Python 3.13 environment. The base workflow uses the standard library only.

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

Defaults: fixed, candidate K 20, final K 5, raw cosine ≥0.50, heuristic rewrite, bge-m3, qwen2.5:14b, strict coverage, 32768-token model context. Recent context is bounded to four completed turns/2400 characters; the complete current task state is bounded to 6000 characters. Full history remains on disk. Character budgets are not exact model token counts.

Global options precede subcommands. `--answer-model`, `--verifier-model`, `--url`, `--timeout`, `--num-ctx`, `--num-predict`, `--db`, `--chat-db`, `--history-turns`, retrieval settings and coverage policy are configurable.

```bash
python day-25-rag-chat/main.py --answer-model qwen2.5:7b chat
python day-25-rag-chat/main.py chat --session <ID>
python day-25-rag-chat/main.py ask "Where is it stored?" --session <ID> --output answer.json
```

Pull an alternative answer model separately and evaluate its quality. Changing the embedding model requires rebuilding the index. Startup checks the selected index revision against the current corpus; `--allow-stale-index` explicitly permits an old revision and retains its provenance. Updated root READMEs are indexed, so rebuild after applying this solution. The original corpus rule remains unchanged: root READMEs, Days 1–20 lesson READMEs and Days 16–20 non-test Python files.

## History and memory

The CLI prints a session ID. Without `--session`, `ask`/`chat` creates a new isolated session. Reuse the ID after restart.

| Command | Action |
|---|---|
| `/new [title]`, `/use ID`, `/sessions` | Create, switch, list sessions |
| `/state`, `/history` | Inspect task memory or full persisted history/sources/errors |
| `/goal TEXT` | Set or explicitly change the dialogue goal |
| `/constraint TEXT`, `/clarify TEXT` | Add constraints or user clarifications |
| `/term NAME=DEFINITION` | Set or correct a term |
| `/forget goal` | Clear the goal |
| `/forget constraints KEY`, `/forget clarifications KEY`, `/forget terms KEY` | Remove an entry using its visible state key |
| `/export PATH.json` | Export history, responses, provenance, task state and edit events |
| `/recover` | Mark pending turns from a stopped/crashed process as errors |
| `/help`, `/quit` | Help or exit |

The structured conversation planner also extracts memory from ordinary messages, including labelled Russian lines `Цель:`, `Ограничение:`, `Уточнение:` and `Термин: NAME = DEFINITION`. It resolves follow-up questions using recent conversation and saved task state. Every stored value must be a literal substring of evidence in the current user message. Assistant-generated repository facts cannot become task memory. Existing goals cannot be replaced by an incidental next question. Each entry retains evidence, turn and origin. A full state rejects new updates visibly rather than dropping earlier entries. `/forget` is the explicit deletion path.

```bash
python day-25-rag-chat/main.py sessions
python day-25-rag-chat/main.py history <ID>
python day-25-rag-chat/main.py state <ID>
python day-25-rag-chat/main.py export <ID> --output dialogue.json
```

Inspection/export needs neither Ollama nor a knowledge index. The user message is persisted before network work. Technical failures are stored as errors, not generated answers. Ctrl+C records the interrupted turn; hard-killed processes leave pending history which `/recover` can release after the original process stops. SQLite prevents overlapping turns in one session; other sessions remain isolated.

## Sources and grounding

Answers preserve Day 24's v14 extractive protocol: the model selects existing quote IDs and the application copies exact source passages. It assigns citation numbers, source path, section, chunk ID and line ranges. The previous Python implementations are unchanged. Day 21 supplies storage/embeddings, Day 23 retrieval/rewrite/filtering, and Day 24 strict evidence/coverage checking; Day 22 provides the original RAG-flow precedent.

Every answer includes an explicit Sources block. Weak retrieval, ambiguity or failed validation returns unknown + clarification + no confirmed sources. Old answers and task memory are context for intent and relevance, never current evidence. Memory affects question interpretation and evidence selection; it cannot rewrite repository facts. Extractive answers may contain source-language prose or code without free synthesis/translation.

Strict coverage is the default. Optional `--coverage-policy diagnostic` may publish exact passages after a negative coverage audit, with a visible manual-review flag and the original negative judgment. Such a turn fails the Day 25 coverage evaluation check.

## Long scenarios and verification

`scenarios.json` contains two dialogues of 12 user questions each: Day 18 scheduling and Day 20 MCP orchestration. Including answers, there are 48 messages. They exercise goals, constraints, clarifications, terms, short follow-ups, a topic detour, return to the goal and reopening both databases after turn six.

```bash
python day-25-rag-chat/main.py offline-demo
python day-25-rag-chat/main.py --answer-model qwen2.5:14b evaluate \
  --output day-25-rag-chat/reports/check/live.json
```

The offline run uses the actual corpus, chunker, SQLite cosine search, Ollama HTTP client and citation validators. Hash-256 lexical embeddings and scripted planner/selector/coverage responses replace real models, with explicit fixture settings 40/20/cosine0.0. All 24 turns and 24 distinct embedding/search calls pass the software contract checks. The supplied report, readable dialogues and test logs are under `reports/verified/`. This is not a BGE-M3/Qwen quality result.

The live command uses your actual Ollama models and production defaults. It saves source/quote bindings, retrieval traces, planning warnings, coverage outcomes, per-turn goal retention, complete history and final retention of every memory field. Exit 0 means all automatic checks passed, exit 1 saves a failed report, exit 2 indicates setup/configuration failure. Individual turn failures are recorded and evaluation continues. Complete each turn's `manual_review` for relevance, completeness and respect of the task goal.

Preparation environment: Python 3.12.14. **150 Day25 tests passed on v22; 135 Day24/console regression tests passed on v20 (Day24 has not changed since); 34 unchanged Day21–23 tests passed earlier.** There is no live Ollama here; live answer quality is unverified. Target Python 3.13 is compatible with the syntax and standard library used.

The implementation is a local single-user CLI, without a web service or authentication. Recent model history is bounded while persistent history is complete. Old details outside saved task state and the recent window may need clarification. The planner can misinterpret intent despite valid literal provenance; inspect `/state` and correct it explicitly. Exact quotations and positive model coverage judgments still require source-based answer review. See the [Russian guide](README.ru.md) for detailed commands and the full file map.

Version 10 adds literal whole-line task declarations, preservation of current lesson scope, one model reference review (a repeated ambiguity still refuses), and lesson namespace retrieval before candidate/final limits. Two fresh dense branches use the current query and the current query plus indexed document titles; candidates retain the maximum actual cosine, with both branch scores recorded. The threshold remains 0.50. Historical assistant answers are excluded from evidence selection. The first user-run 12+12 live evaluation failed and is included with its manual review in `reports/live/`; v10 live quality is pending. See [LONG_SCENARIO_FIX.ru.md](LONG_SCENARIO_FIX.ru.md).

Version 11 addresses the real `long-init-v10.json` refusal: scoped retrieval and literal memory passed, but the auditor misread the selected server table. A compact Russian table audit preserves the entire original question/requirement/provenance/proof DATA and makes one model call; negative verdicts are not retried into approvals. Selector table navigation uses only literal allowed quote cells. See [TABLE_AUDIT_FIX.ru.md](TABLE_AUDIT_FIX.ru.md). Live v11 quality remains unverified.

Version 12 restores bounded consecutive-proof navigation in the mixed table audit after the live full-flow question was falsely rejected. Original DATA/schema and one independent audit remain unchanged. Selector scope instructions request only the smallest complete answer to the current question. See [MIXED_PROOF_FIX.ru.md](MIXED_PROOF_FIX.ru.md). Live v12 full-flow/completion checks passed, but the info answer appended an unlabelled full-report chain; v13 requires a live recheck.

Version 13 adds one compact selection-refinement call per candidate with multiple valid quotes. It can select only a subset of the initial selection. Unchanged Day 24 validation/auditing checks the full question afterwards. Both raw calls and metadata are retained in `validation.selection_refinements`. This adds latency; real Qwen pruning quality is pending. See [SELECTION_FIX.ru.md](SELECTION_FIX.ru.md).

Version 14 excludes whole incomplete pipe-table quote IDs from selector DATA/schema and rejects any attempted selection of those IDs. Lead-in/code dependencies now cover the full 1600-character quote limit, with exhaustive validation despite bounded navigation hints. Source text, index and strict coverage remain unchanged. Live info/summary/VPS checks on v13 passed; detour/return presentation fixes require live v14 rechecks. See [FRAGMENT_QUALITY_FIX.ru.md](FRAGMENT_QUALITY_FIX.ru.md).

Version 15 addresses the failed live detour v14: table filtering worked, but the auditor rejected direct worker evidence. Scope guidance distinguishes process identity from explicitly requested algorithm/path/command details; refinement prefers direct documentation and a short naming command over an assignment-test table. Guards, original requirements/schema and negative verdicts remain unchanged. 97 tests passed; live quality is pending. See [PROCESS_SCOPE_FIX.ru.md](PROCESS_SCOPE_FIX.ru.md).

Version 16: [DRAFT_FRAGMENT_FIX.ru.md](DRAFT_FRAGMENT_FIX.ru.md). Live detour v15 passed; live goal return v15 restored day 20 and all memory but failed because both initial selections included an unrelated installation intro without its following code. Subset refinement can now remove such draft-only fragments before final validation. Dependencies come from the original catalog, never filtered adjacency; no new IDs may be added. Final fragment validation and the unchanged strict audit remain mandatory. 103 automated tests passed; live return v16 and clean 12+12 scenarios are pending.

Version 17: [PYTHON_FRAGMENT_FIX.ru.md](PYTHON_FRAGMENT_FIX.ru.md). Live return v16 confirmed goal recovery, exact sources and unchanged memory; the answer is verbose but has no orphaned intro. First-collection v16 correctly answered immediately but included an unnecessary Python excerpt with an unterminated docstring. Such whole quote IDs are now excluded before selection using lexical analysis, without repairing source text. Table filtering, original intro/code adjacency, schemas, strict negative verdicts and fresh search remain in place. 110 automated tests passed; live rerun and clean 12+12 scenarios remain pending.

Version 18: [SELECTION_DOMAIN_FIX.ru.md](SELECTION_DOMAIN_FIX.ru.md). The second full live v17 run failed manual review: 22 answers, 2 refusals, 39 literal quotes, 5 problematic turns. Memory/history passed. Refinement now uses an array enum of structurally complete initial-ID subsets; narrative arrow diagrams retain their original captions. Header/separator width mismatch excludes a whole table quote. Reference review uses compact current declarations and accepted topics. 117 tests pass; real Ollama schema/answer checks and new clean 12+12 dialogues remain pending.

Version 19: [CONDITIONAL_AUDIT_FIX.ru.md](CONDITIONAL_AUDIT_FIX.ru.md). Live v18 proved structural cleanup/array enum and exact memory/sources, but the explicit action-plus-marker follow-up failed manual coverage: the auditor transferred an action from the HTTP-400 branch to the premature-operation branch. A compact single conditional audit retains all original DATA and supplies only literal clause offsets; selector/refiner also require the requested branch action. Negative verdicts and unchanged Day24 validators remain mandatory. 124 tests pass; real Qwen rerun and clean full dialogues are still pending.

Version 20: [REQUIREMENTS_INTENT_FIX.ru.md](REQUIREMENTS_INTENT_FIX.ru.md). The live v19 answer now directly proves both the corrective step and marker, with complete source captions and unchanged memory. An incidental VERIFY identifier still triggered an unrelated verification-observation criterion. Day25 now masks explicitly formatted operation identifiers only for intent scanning; full questions and evidence stay unchanged. Genuine verification requests retain independent action/observation criteria. Day24 gets an optional requirements factory with its old default and a mandatory full-question gate. Install both the Day25 folder and the included Day24 strict_agent.py. 129 Day25 and 135 Day24 regression tests pass; live v20 and clean full dialogues remain pending.

Version 21: [SOURCE_UNIT_FIX.ru.md](SOURCE_UNIT_FIX.ru.md). Live v20 retained the correct criterion, source identity and memory but its answer omitted the requested corrective action. Day25 now declares inseparable caption/narrative-sequence units BEFORE selection, records the original and decoded IDs, and rejects the observed positive cross-branch action transfer. Independent negative audits remain negative. All 141 Day25 tests pass with scripted HTTP/SQLite fixtures; live v21 remains pending. Next: `python day-25-rag-chat/main.py evaluate --output day-25-rag-chat/reports/check/live-long-scenarios-v21.json` (two fresh 12-turn sessions).

Version 22 submission candidate: [RELEASE_V22.ru.md](RELEASE_V22.ru.md). The real v21 12+12 dialogue report has full history/state and 45 literal quotes, with 23 answers and one false refusal. Two important issues (summary route audit and a docstring-tail lexical filter gap) are fixed; 150 Day25 tests pass. Minor verbosity/language duplication is deferred by user request. One live summary check remains pending; no completely clean v22 long run is claimed. [Video plan](VIDEO_DAY25.ru.md), [backlog](BACKLOG.ru.md).
