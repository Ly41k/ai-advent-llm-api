# Day 29 — task-specific local LLM optimization

[Russian documentation](README.ru.md) | [Installation](START_HERE.ru.md)

Selected: local Qwen2.5 14B Instruct Q4_K_M, temperature 0, output limit 1024,
context 8192, local bge-m3 embeddings and the existing Week 6 index.
Validated on the user's M1 MacBook Pro with 32 GB RAM.

Scope: factual repository lookups and unsupported-question abstention (12/12),
plus the Day 18 periodic VPS worker verification procedure (3/3 calibration
and 6/6 on two frozen, previously unrun RU/EN formulations). Seven questions,
21 reviewed selected-profile observations, within a small task-specific set.

Factual answers retain V3. For periodic procedures, the local model selects
four exact evidence IDs and the application validates and renders a source-
extractive plan. Raw model selections remain separate from rendered answers.
Invalid completed selections are retained failures, with no hidden retry.

Original Q4/Q5 measurements and failed drafts remain unchanged. Q4/Q5 parity
is established on one factual question only. No isolated temperature effect
or improvement in general free-text reasoning is claimed. V7 output tokens
describe selections, not the full rendered procedure. RSS and size_vram are
not full physical unified-memory measurements.

No further generation is needed to finish this scope. Extract the day folder
into the repository root and merge it, keeping your existing cache. Python
files are identical to the already tested V7. Use the V7 launcher for verifying
V7 reports; semantic reviews are separate from sealed automatic results.
