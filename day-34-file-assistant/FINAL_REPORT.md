# Day 34 — final Course Minimum report

Course Minimum is **PASS with documented independent editorial review**, accepted by the owner on 2026-10-17. This report does not promote the original model ADR to full semantic acceptance.

| Acceptance | Status |
|---|---|
| Technical acceptance / real model selection / file operations | PASS |
| Mac offline v7 | 65/65 PASS |
| Usage quality | PASS |
| Original model ADR quality | PARTIAL |
| Original ADR exact source quotations | 17/17 PASS |
| Independently reviewed ADR quality | PASS |
| Reviewed ADR source quotations | 27/27 PASS |
| Replay of both original outputs, without new POST | PASS |
| Course Minimum | PASS after independent editorial review |
| Fully automatic semantic E2E of original documents | NOT_ACCEPTED |

## Why the assignment is satisfied

Real `gpt-5.4-mini` decisions selected operations and their arguments from natural-language goals. Both scenarios listed files, searched at least three files, read the three core Day 33 modules and additional sources, and created Markdown through the constrained `write_file` tool. Their original diffs and source evidence are retained. Search covered 17 real source files; the Usage report correctly classifies all ten `fetch_context` occurrences across five files. Saved decisions reproduce operations and document bytes without another generation.

The remaining ADR narrative defects were independently corrected and explicitly accepted. The assignment's autonomous file-work requirements are demonstrated by the real model; the final architecture document additionally passed editorial review. This is the basis of Course Minimum PASS, not a claim that the model produced a fully correct ADR without review.

## Artifacts and provenance

- [Original Usage](evidence/original/component-usage.md), 2,879 bytes, SHA-256 `c3b10db5cc5d01f28569b8875cc4096ba1c0ff5365357a6617ef1e564e7d1731`.
- [Original ADR](evidence/original/ADR-001-ticket-context.md), 5,058 bytes, SHA-256 `69b8d740ef46256ef9a5c40b563ffe5c0538f0f3bcd0193235f23e14eea89010`.
- [Reviewed ADR](evidence/reviewed/ADR-001-ticket-context-reviewed.md), 7,558 bytes, SHA-256 `7e1c49169bce21255d3600c7e5a0ed7634d5458cfd5a6bfa54faee9ade180d1d`.
- [Editorial changes](evidence/editorial-changes.diff), [exact reviewer evidence](evidence/reviewed/source-evidence.json) and [public acceptance](evidence/acceptance.json).
- [Usage decisions/trace](evidence/usage-trace.json), [ADR decisions/trace](evidence/adr-trace.json), [original diffs and automatic reports](evidence/historical/), [API usage](evidence/api-usage.json).

The editorial diff retains its historical `editorial-proposal/ADR-001-ticket-context.md` header. Its target bytes equal the public `reviewed/ADR-001-ticket-context-reviewed.md`. Public traces are explicitly derived decision-only projections: exact canonical requests/hashes, normalized model decisions, events and source quotations are preserved; raw provider payloads, identifiers and receipts are private. Original trace SHA-256 values identify their reviewed source. Native provider evidence was checked before redaction. The public replay does not authenticate a fresh model response.

## Preserved failure history

Groq used four POST: initial HTTP 400 `tool_use_failed`; another HTTP 400 for the empty-object schema; then a successful autonomous `list_files` and HTTP 400 `json_validate_failed`. The final Groq failure's cause is unestablished.

OpenAI Usage first stopped after three POST on a read exceeding the original 200-line contract. A separately approved continuation reused the three decisions, exposed bounded pagination and completed with two new POST. Final Usage has nine successful operations: 1 list, 2 searches, 5 reads, 1 write.

OpenAI ADR stopped after two POST on an end line beyond EOF. A separately approved continuation replayed the two saved decisions with explicit EOF clipping, read more sources and proposed a write. Two exact evidence quotes contained an extra `{`, so no file was written. One final approved POST repaired those quote arguments. The known rejected write remains in the trace; the successful write follows it. Fourteen operations include 1 list, 4 searches, 7 reads and 2 writes, one rejected.

That final model repair did **not** change Markdown. The original ADR ambiguously conflated CLI `prepare` and the HTTP answer path, called HTTP offline “by default” rather than always, and omitted retrieval. The reviewer corrected these statements and added source evidence for `retrieve(question, ticket)`, SQLite FTS5/BM25, payload construction and generation/validation. Reviewer edits are not attributed to the model. No historical traces, receipts, arguments or `NOT_ACCEPTED` reports were rewritten.

## Usage and cost

OpenAI: **10/10 POST**, five per scenario, all HTTP 200. Saved totals: 83,631 input, 5,666 completion, 89,297 total tokens; 21,248 input tokens reported cached. At the recorded calculation rates ($0.75/M input, $0.075/M cached input, $4.50/M output), conservative estimate is **$0.08822025**, cache-adjusted estimate **$0.07387785**. These are historical estimates, not verified current pricing or billing. Total conservative reservations were $0.44085975 against $0.50.

Groq: **4 POST**, including failures. Full usage/cost is unknown because failed responses lack usage; the checked successful response reports 1,140 tokens. Total provider POST across Day 34: 14. Finalization adds **0**. No retry/fallback or eleventh OpenAI call is authorized by this delivery.

## Verification and publication boundary

Run `python3.13 day-34-file-assistant/verify_delivery.py` from the repository root. It verifies the public file hashes/scope, all 17 source inputs, original outputs, exact editorial diff, review quotations, usage sums, 65 offline tests and both original-output replays. Replay matches saved events, Markdown SHA and original creation diffs with zero POST. Acceptance labels preserve the independent human judgment; hashes and exact citations alone do not establish narrative correctness.

Base `main` was checked at `25ba00685d0748ebe533570711b75e0d187ab20b`, including merged Day 33 implementation PR #5 and documentation PR #6. Publication scope is only `day-34-file-assistant/` and the two root READMEs. Days 1–33, historical results and RAG indices are unchanged. Root README changes may require future reindexing when older RAG lessons are reused.

Publication removes trailing spaces from two test lines without changing their logic; the accepted runtime is unchanged. A scoped Git whitespace attribute preserves the required single-space blank context lines in the frozen editorial unified diff. Historical artifacts are kept byte-for-byte.

No remote branch, push, PR or merge is performed. The [publication checklist](PUBLICATION.ru.md) and [terminal video](CONSOLE_VIDEO.ru.md) are ready for owner review. Remaining limitations/backlog are listed in [README](README.md); no additional functions or research are required to complete this course minimum.
