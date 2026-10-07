# V16 — final focused stability review

Reviewed on 8 October 2026 (Europe/Kiev). Source: openai-quality-stability-v16.json; run ID 8ff7c3ae-6011-4e5a-9d54-75f4748659e0.

One base-03 question, three trials, gpt-4.1-mini-2025-04-14, phases mode. Embeddings/retrieval used the existing Week 6 index locally. No local generation or other passing questions were rerun. Code is unchanged since the successful V16 probe.

| Check | Result |
|---|---|
| Valid completed responses | 3/3 |
| Original heuristic rubric | 3/3 |
| Strict verifier | Passed |
| Manual completeness and citation support | 3/3 |
| API/format errors | 0 |
| Generation calls / HTTP attempts | 3 / 3 |
| Identical citations | All three trials |
| Exact answer stability | 0/1 repeated group |
| Semantic consistency | Manually observed across all three trials |

Every before slot uses e1-q5 (Preflight): explicit local conflicts, semantic request checks against all invariants, refusal before answer generation. Every after slot uses e1-q7 (Postflight): local and independent semantic checks before persistence, discarded violating answers, explained refusals and fail-closed behavior for malformed JSON or unknown IDs. Each phase's statements are supported by that phase's selected quotation. Minor wording and supported detail variations do not change the mechanisms. This is manual observation, not an automated semantic metric or future guarantee.

| Trial | Generation wall, s | Pipeline, s |
|---|---:|---:|
| 1 | 3.301 | 4.419 |
| 2 | 2.650 | 2.755 |
| 3 | 2.836 | 2.908 |
| Median | 2.836 | 2.908 |

Interpolated generation p95: 3.255 s over only three observations. Total input/output tokens: 6885 / 593. Prompt SHA256 is identical; answer wording varies while quotations stay identical. The report does not establish why the first pipeline was slower.

The fix is confirmed for this sample. No further code changes or full 20 ×3 run are needed now. Retain VPS V13 and isolation V12 successes; this is historical evidence across modes/versions, not a fresh combined benchmark. See QUALITY_RESULTS_V16.md, FINAL_REPORT.md and OPENAI_RESULTS.md for the historical evaluation.

Day 28 requirements are implemented and evaluated: existing Week 6 index, local embeddings/retrieval, Ollama generation, optional cloud comparison, quality/speed/stability measurements. Exact text identity is an evaluated limitation, not an assignment requirement. This cloud-only run adds focused stability evidence; it is neither a fresh paired comparison nor a physical internet-disconnection test.

All 19 original JSON reports are byte-preserved and internally consistent. Audit: reports/verified/openai-stability-v16-audit.json. Previously passed V16 offline tests: 71. This update changes documents/audits only; root files, other days and the index are unchanged. No new inference was executed during review.
