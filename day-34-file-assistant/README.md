**English** | [Русский](README.ru.md)

# Day 34 — AI File Assistant

**Course Minimum: PASS with documented independent editorial review.** Technical acceptance and Usage quality passed. The original model ADR remains **PARTIAL**; the separately labelled reviewed ADR passed. Historical automatic `full_e2e: NOT_ACCEPTED` reports are unchanged. See the [final report](FINAL_REPORT.md) and [public acceptance](evidence/acceptance.json).

## Assignment and scope

Build an assistant that reads project files, searches multiple files, analyses their content, creates or changes files, and initiates these operations from a natural-language goal. Demonstrate at least two scenarios across 2–3 files, retain changes or a diff, and support reproducibility.

This module implements the minimum with Python's standard library, local file tools and a bounded LLM loop. It creates Markdown files; it does not modify earlier lessons. It is a course demonstration on pinned sources, not a general production agent, another RAG system or a multi-agent platform. MCP is not required for Day 34 tooling; Day 33's MCP implementation is the subject of analysis.

## Architecture and tools

`main.py` provides the CLI. `agent.py` sends the goal and untrusted tool results to an adapter, validates each selected action and executes it through `file_tools.py`. `llm_adapter.py` contains Groq, explicitly scripted offline fixtures and saved-decision replay. `openai_adapter.py` implements strict native function calling with curl. `resume.py` and `quote_repair.py` preserve the approved continuation history after local failures.

| Tool | Behaviour |
|---|---|
| `list_files` | Lists allowlisted paths, line counts and SHA-256 |
| `search_files` | Literal search in selected files, or all allowlisted files; returns paths and line numbers |
| `read_file` | Reads a file or a numbered range, at most 200 lines per operation; explicit EOF/pagination metadata |
| `write_file` | Exclusively creates a Markdown basename inside a fresh Day 34 results directory; validates exact source evidence |

The real model selects tools, arguments, search terms, read ranges, the document name/content and completion. Python enforces the contract and boundaries; it does not prescribe the live operation sequence. OpenAI uses native strict schemas; Groq used a strict JSON decision contract. Offline fixtures are scripted and **cannot establish real LLM selection**.

## Sources and safety

`inputs.json` pins 17 Day 33 Python/JSON files at `25ba00685d0748ebe533570711b75e0d187ab20b`. Both scenarios read `main.py`, `mcp_client.py` and `support_agent.py`, with additional files selected by the model.

- Read allowlist and source SHA checks; no arbitrary repository reads.
- Writes only under `day-34-file-assistant/results/<fresh-run-id>/`; exclusive creation prevents accidental overwrite.
- Reject absolute paths, traversal and symlink escape using directory descriptors and `O_NOFOLLOW`.
- Source files ≤65,536 bytes, documents ≤20,000 bytes, ≤24 file operations and bounded model turns.
- File contents are untrusted data, not agent instructions. No LLM-supplied shell execution.
- Evidence must cite previously read lines and match them exactly. This checks provenance, not the truth of every narrative claim.
- Explicit provider approval, immutable POST reservations, token/cost limits and no automatic retries/fallback. No more cloud calls are part of this delivery.

## The two real scenarios

| Scenario | Saved model work | Result |
|---|---|---|
| Usage: find `fetch_context` | 1 list, 2 searches, 5 reads, 1 write; search covers 17 files | [Original report](evidence/original/component-usage.md): 10 occurrences in 5 files — 1 definition, 4 imports, 5 calls; quality PASS |
| ADR: study ticket context through MCP | 1 list, 4 searches, 7 reads, 2 write attempts (one rejected) | [Original ADR](evidence/original/ADR-001-ticket-context.md): technical PASS, 17/17 exact citations, quality PARTIAL |

The model repaired two `evidence.quote` values through one explicitly approved final POST. The Markdown body stayed unchanged: CLI/HTTP wording was imprecise and retrieval was omitted. The [reviewed ADR](evidence/reviewed/ADR-001-ticket-context-reviewed.md) is a **reviewer edit**, with 27 checked quotations, explicit provenance and an [editorial diff](evidence/editorial-changes.diff). It clarifies CLI `prepare`, HTTP's always-offline adapter, and SQLite FTS5/BM25 retrieval. It is not presented as an unchanged model answer.

Both real runs autonomously performed the required file operations and produced Markdown and diffs. Course Minimum acceptance combines that evidence, accepted Usage, replay and the independently reviewed ADR. It does **not** claim fully automatic semantic success for the original ADR.

## API results and history

Groq `openai/gpt-oss-120b`: 4 POST total. Failures included `tool_use_failed`, an invalid empty-object schema, and a later `json_validate_failed` whose cause remains unestablished. One successful response selected `list_files`. No blind retry was treated as acceptance.

OpenAI `gpt-5.4-mini`: 10 POST total, all HTTP 200, five per scenario including continuations. Earlier local stops were `invalid_line_range` (over-200-line request and later end beyond EOF) and `quote_mismatch`. Bounded reads and an explicit saved-state continuation preserved original arguments; the exact quote validator was not weakened. Each continuation had separate authorization. Failed attempts and receipts remain private and unchanged.

Saved usage: **83,631 input + 5,666 output = 89,297 tokens**, including 21,248 reported cached input tokens. Conservative estimate **$0.08822025**, cache-adjusted estimate **$0.07387785**; actual billing is unknown. Total reserved estimate was $0.44085975 under the $0.50 ceiling. Full Groq usage is unknown; the retained successful response reports 1,140 tokens. See [API totals](evidence/api-usage.json) and [OpenAI per-POST summary](evidence/openai-posts.json). Finalization makes **zero new POST**.

## Install and verify on Mac

From the repository root with Python 3.13; no pip dependencies, keys, network or Ollama are needed for this module's verification:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python3.13 day-34-file-assistant/verify_delivery.py
```

If the existing venv is active, run only the last command. Expected final JSON: `status: PASS`, `offline_tests: 65/65 PASS`, both replays `equal: true`, and `new_provider_posts: 0`. Mac v7's original 65/65 report is retained separately. This is a delivery/replay check of an accepted review, not a new live semantic evaluation.

The verifier checks the publication manifest, 17 input SHAs, frozen documents/evidence, exact editorial diff, citation evidence, usage totals, private-file patterns, Git index scope when available, the 65 existing tests and both saved-decision replays in a temporary directory. Local private results are left intact. Git's tracked/staged files must stay within the delivery scope; unexpected files fail verification.

Other actual CLI commands, all offline:

```bash
python3.13 day-34-file-assistant/main.py --help
python3.13 day-34-file-assistant/main.py offline-check --run-id manual-offline-01
```

Use a fresh run ID for each `offline-check`; results are never overwritten. Its automatic `NOT_ACCEPTED` concerns fresh live/semantic acceptance, not the separately accepted final review. The verifier replays the public projections directly through the existing `ReplayAdapter` and agent loop. On a Mac retaining the private full traces, the normal CLI also works:

```bash
python3.13 day-34-file-assistant/main.py replay --trace day-34-file-assistant/results/mac-openai-usage-01-resume-01/trace.json --run-id manual-usage-replay-01
python3.13 day-34-file-assistant/main.py replay --trace day-34-file-assistant/results/mac-openai-adr-01-repair-01/trace.json --run-id manual-adr-replay-01
```

Those last two commands require the historical local results and fresh output IDs. They are not required by the public verifier. Do not run live/resume/repair modes: the authorized generation budget is exhausted.

## Public delivery and limitations

`evidence/` contains originals, the separate reviewer version, original creation diffs/manifests, preserved automatic acceptance, Mac offline report, API summaries and two decision-only trace projections. Projections retain exact canonical requests, selected arguments, tool results and document hashes; raw provider wire messages, IDs and private receipts are omitted. Native wire/receipt checks were performed before publication. Public replay checks the retained decisions and filesystem results, not raw provider identity or a fresh generation.

`delivery-manifest.json` lists the public files and their SHA-256. Private `results/`, receipts, raw HTTP payloads, virtual environments and caches are excluded. See [publication instructions](PUBLICATION.ru.md), [terminal video script](CONSOLE_VIDEO.ru.md) and [final report](FINAL_REPORT.md).

Known limits: literal search, a fixed source snapshot, Markdown-only creation, bounded context and operations, POSIX/macOS filesystem assumptions, and human review for narrative correctness. Post-course backlog: better provider schema portability, range guidance, general claim checking and broader inputs. These are not required for Day 34. Root README changes may require rebuilding older RAG indices when reused; none are rebuilt here. GitHub publication completed with merged [PR #7](https://github.com/Ly41k/ai-advent-llm-api/pull/7) on 2026-10-17 (commit `2d20ebf`); the [publication checklist](PUBLICATION.ru.md) is a preserved pre-merge instruction, not a current pending step. The terminal video script is ready; video recording has not been independently confirmed.
