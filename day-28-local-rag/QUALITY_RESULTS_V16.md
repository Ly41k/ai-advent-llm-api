# V16 quality result — both phases explained and separately evidenced

**Update: the focused three-trial review is complete: 3/3 automated and manual quality passes, identical quotations, varying wording. No further runs needed now. [Stability result](STABILITY_RESULTS_V16.md).**

Run f7472e8f-094a-46bd-a0aa-8023cd4a8069, gpt-4.1-mini-2025-04-14, phases mode, one base-03 question, one trial and one generation call. Strict verification passed; original heuristic quality 1/1; manual review passed.

The before statement explains Preflight: local explicit-conflict validation, semantic request checks against all invariants before answer generation, and explained refusal without generation on conflict. Its selected Preflight quotation supports these claims. The after statement explains Postflight: local/semantic response checks before persistence, discarding a violating response, explained refusal and fail-closed handling. Its selected Postflight quotation supports the whole statement. Uncited background policy-placement claims are absent.

Generation wall: 2.785 s; pipeline: 3.914 s; input/output tokens: 2295/195. No API/format errors. One trial does not measure stability; its median/p95 are just that single observation. The verifier's full_run scope means completion of this one-case request, not a fresh 20-case benchmark.

All three small OpenAI cases now have passing historical answers: invariants V16 phases 1/1, VPS V13 coverage 1/1, dialogue isolation V12 baseline 3/3. Manual reviews passed these observations. Different prompts and versions remain separate; original V12 quality stays 5/9 and V13 stays 1/2. No combined new success percentage or stability claim is made. The new fixes have only single successful trials; V12 exact output stability was not achieved for isolation.

The local RAG implementation, V11 local results and original V2 paired comparison remain unchanged. See FINAL_REPORT.md. No further code change is needed for this successful quality probe. An optional final stability check can repeat only base-03 three times with phases mode and a fresh output path; it must not use retry-from the successful probe. [Exact command and limits (RU)](QUALITY_RESULTS_V16.ru.md).

Phases mode is specialized for before/after check questions and is not a general mode for the full mixed question set. A new full local/cloud benchmark would require its own explicit mode plan. No new generation was run during this documentation update.

The original live JSON is unchanged. The audit records its hash, strict/manual review and historical source mapping. All 18 original reports V2–V16 remain internally consistent; code remains V16 with 71 passing offline tests.
