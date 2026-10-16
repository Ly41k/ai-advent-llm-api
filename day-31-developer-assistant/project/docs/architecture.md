# Current repository architecture / Архитектура репозитория

## Local developer tools: Day 31

Day 31 is a separate package named bublik_developer inside day-31-developer-assistant.
The CLI entry point is main.py. The main.py launcher imports bublik_developer.cli.
ProjectWorkspace fixes the root of a local Git repository and a logical project ID.
Read-only Git data comes through a real FastMCP stdio server with discovery and call_tool.

The project documentation index is separate from the Week 6 knowledge.db and from
the private conversation database of Day 30. Project RAG uses SQLite FTS5, optional
local bge-m3 embeddings and hybrid rank fusion. It returns exact source excerpts
with relative paths, line ranges, raw file digests and corpus/index versions.

День 31 хранит отдельный индекс документации проекта вне рабочего репозитория.
История пользователя дня 30 не является источником Project RAG. Изменение документа
инвалидирует текущий corpus fingerprint; устаревшие доказательства не публикуются.

The agent runtime delegates Documentation, Git and Verification as separate
TaskEnvelope tasks with sealed contexts. Documentation and Verification use owned
worker processes; Git uses the real MCP connection. The dispatcher validates
dependencies, role capabilities and call budgets. Documentation and Git can
execute concurrently; Verification runs after their results. Main merges validated
blocks through SPAWN / EXECUTE / REPORT / MERGE lifecycle events.

The agents demo still makes zero LLM calls. The Day 31 /help question and ask
commands use a project pipeline with bounded RU/EN routing. An independent
documentation question and Git observation use fan-out; documentation about
changed files depends on a prior Git status result. Ambiguous multiple Git
intentions request clarification rather than choosing an operation silently.

Documentation generation and Main assembly are separate inference tasks in
owned workers. Documentation sees the scoped question and source excerpts;
Main sees the full question, checked claims and application-produced Git facts.
Git and Verification do not receive a generation capability. Qwen is serialized
through the shared model lease. Main can order existing claim/fact IDs, not add
new text or facts. Publication checks sources again and reobserves Git after
generation. Claim wording still needs semantic human review; source provenance
is not proof that every natural-language claim is correct.

Bare /help and Git-only requests need no model or project index. Project search
continues returning excerpts. The console remembers one prior documentation
question scoped to project identity and corpus revision, not personal history.
Real Qwen contexts for this new pipeline require a separate Mac smoke report.

## Earlier MCP components: Days 16–20

Day 16 establishes a stdio connection. Day 17 adds a GitHub repository tool.
Day 18 stores scheduled jobs and uses worker.py to execute background work.
Day 19 composes tool calls into a chain. Day 20 uses ToolRegistry in
day-20-mcp-orchestration/mcp_registry.py to discover a namespaced catalog from
GitHub, analysis and storage MCP servers.

MCP servers provide tools. A server is not automatically an independent subagent.

## RAG components: Days 21–29

Day 21 implements corpus collection, fixed/structural chunking, embeddings,
SQLite vector storage and cosine retrieval. Its shared corpus is deliberately
limited to README documentation of Days 1–20 and selected Python sources of Days 16–20.
Days 23–25 add filtering, grounded citations and conversational context.
Day 28 connects retrieval to local Ollama generation and opens the existing index read-only.
Day 29 adds measurements and selected task prompts. Its selected Qwen profile uses
temperature 0, num_ctx 8192 and a maximum of 1024 output tokens.

## Private service: Day 30

The bublik_service package provides a FastAPI HTTP API and Web UI. SQLite stores
owners, chats, original messages, generation jobs and context snapshots. The
Coordinator runs one active generation. Ollama provides Qwen2.5:14b Q4_K_M locally.
Browser clients use the same server conversations through authenticated HTTPS.

Sources: day-21-document-indexing/corpus.py; day-29-local-llm-optimization/SELECTED_PROFILE.json;
day-30-private-ai-service/bublik_service/inference/coordinator.py;
day-31-developer-assistant/bublik_developer/cli.py;
day-31-developer-assistant/bublik_developer/agent_runtime.py;
day-31-developer-assistant/bublik_developer/agent_worker.py.
Pipeline sources: day-31-developer-assistant/bublik_developer/pipeline.py;
day-31-developer-assistant/bublik_developer/routing.py;
day-31-developer-assistant/bublik_developer/generation.py;
day-31-developer-assistant/bublik_developer/inference_tasks.py;
day-31-developer-assistant/bublik_developer/model_worker.py.
