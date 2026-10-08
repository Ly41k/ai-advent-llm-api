# Day 29 — local LLM optimization and evidence checks, V6

[Russian instructions](README.ru.md) | [Start here](START_HERE.ru.md)

Local-only Qwen2.5 14B Instruct with Ollama, local bge-m3 embeddings and the
Week 6 index. The factual Q4/V3 profile (temperature 0, max output 1024,
context 8192) has twelve manually reviewed responses on four questions.
Original Q4/Q5, speed, resource and baseline comparisons are retained.

Procedure quality is still open pending a live Mac run. V6 focuses evidence,
adds a procedure template and independently checks technical fragment bindings,
status-versus-execution mistakes and selected recurring-procedure coverage gaps.
Passing these conservative checks requires human semantic review; it is not
automatic approval. Raw responses and quotations are never repaired silently.

Extract over the existing Day 29 directory and keep your cache. All previous
Python files are unchanged. The bundled original reports are byte-identical.
With the previous environment, the initial V6 control reuses 27 observations
and generates only three procedure answers. Fully cached quality failures
also remain cached. A repeated run performs zero new answers, probes or warmups.
The first run separately records its token probe and warmups.

The profile name is retained for unchanged factual cache identities; actual
messages and evidence identify the new procedure experiment. No new model,
dependency or index rebuild is required. V6 runs have a default cap of three
new observations, with at most three repeats per identity.

See QUALITY_V6.ru.md and QUALITY_REVIEW.ru.md for the acceptance process.
