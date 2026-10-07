# Day 28 — Final local RAG evaluation

Additional live OpenAI V12 results are now verified: [results](OPENAI_RESULTS.md), 9/9 technically successful answers, 5/9 quality passes. This is a separate cloud-only subset; the historical V11 evaluation below remains unchanged.
Reviewed 2026-10-07. The local RAG uses the existing Week 6 index, local bge-m3 embedding/retrieval and downloaded qwen2.5:14b generation. Quality, speed and stability have been evaluated. The optional cloud comparison includes recorded failures; it is not an all-pass run. The assignment asks for evaluation, not perfect cloud answers.

## Evidence and scope

- Existing Day 21 knowledge.db is read-only. Live index: fixed 120 / structural 594 chunks, bge-m3, 1024 dimensions. Source digests, corpus fingerprint and vectors checked.
- Local adapters allow loopback Ollama only and reject proxies/redirects/remote models. ask/evaluate do not create a cloud provider. Models must be downloaded beforehand; a separate live run with networking disabled was not recorded.
- 57 Day 28 offline tests passed. All 12 original V2–V11 reports passed internal consistency checks; strict success varies and failures remain recorded.
- Current rubric coverage retains successful three-trial groups for all 20 local cases across historical versions: 17 from compare-v2, base-01 from retry-v3, base-03 from local-retry-v4 and rewrite-ru-02 from local-stability-v11. This is not a fresh full V11 benchmark or proof of every historical claim.
- Exact citations and heuristic scores require semantic review. Stable output can still be incorrect.

## Original paired V2 benchmark

| Metric | Local | Cloud |
|---|---:|---:|
| Scheduled observations | 60 | 60 |
| Valid outcomes | 60 | 48 |
| Model-generated valid outcomes | 51 | 39 |
| Original heuristic passes | 48/60 | 38/48 |
| Generation wall median | 54.53 s | 0.82 s |
| Generation wall p95 | 77.69 s | 1.21 s |
| Exact stability among complete valid groups | 20/20 | 11/14 |

Each pair shared the exact retrieval/prompt. Application abstentions count as valid and stable but are excluded from generation timings. Cloud had eight contract failures and four HTTP 429 outcomes. These are original scores and timings, not blended results from later fixes.

## V11 local synthesis

rewrite-ru-02 passed 3/3 with no errors; final answers and citations were identical. Strict verifier passed. Manual review supports the Russian explanation of SQLite conversations/messages, restoration of completed history and isolation by conversation_id. Six explicit model calls served three observations: selection followed by synthesis from selected original evidence. First-stage statements and gold expectations are not passed as evidence to synthesis.

Generation wall median, including both stages: 43.03 s; p95: 43.16 s; pipeline median: 43.12 s. A separate initial probe took 106.48 s and is kept separate from these subsequent measurements. Optional --synthesis may produce provider-specific second prompts in paired comparisons because providers can select different evidence. Without the flag, the original one-call mode remains.

## Cloud retry V11

21 planned observations resulted in ten actual HTTP attempts: four successful requests and six HTTP 429 responses. After persistent 429, 16 observations were skipped without HTTP. Quality passed 3/4 generated answers; no complete three-trial cloud groups remain for stability measurement. Internal consistency passes, strict success fails. base-03 omitted preflight despite available evidence. Waiting cannot fix that quality defect. rewrite-ru-02 describes conversation_id isolation but inaccurately attributes prevention of topic mixing to completed statuses; statuses exclude unfinished/failed turns instead.

Generation wall median 31.11 s includes retry waits; median successful HTTP attempt duration 1.22 s is a separate diagnostic that excludes waits/failures. Provider latency_seconds also includes retries with this adapter. Headers and full error details were not saved; the exact TPM/TPD/other limit and reset time are unknown.

Official Groq documentation checked 2026-10-07: https://console.groq.com/docs/rate-limits . Published Free Plan gpt-oss-20b limits: 30 RPM, 1000 RPD, 8000 TPM, 200000 TPD. Actual organization limits can differ; check https://console.groq.com/settings/limits . These prompts used 2788–5791 input tokens, so consecutive requests can plausibly exceed 8000 TPM, but that does not establish which limit this account hit. Daily limits require their own reset. HTTP 400 was absent in this retry and structured outputs produced valid answers; this does not rule out every possible future 400.

## Conclusion and use

No further cloud run, provider migration or full local rerun is required to evaluate this assignment on existing evidence. Cloud failures are part of the comparison. A future small benchmark should be predefined, shared across providers, paced using actual token limits and rate-limit headers, and reported separately; failed cases must not be removed from existing results.

```bash
python day-28-local-rag/main.py ask "Which process executes scheduled jobs on Day 18?" --synthesis
python day-28-local-rag/verify_report.py day-28-local-rag/reports/check/local-stability-v11.json
```

doctor checks readiness without generation; its zero attempts and local_rag_verified=false are expected. Original report bytes are preserved under reports/check. Per-case provenance and verifier results: reports/verified/final-audit-v11.json. Only Day 28 changes; no root/other-day edits or reindex. Historical pending notes describe past checkpoints; this report provides the current evaluation.
