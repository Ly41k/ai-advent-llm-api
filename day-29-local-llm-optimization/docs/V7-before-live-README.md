# Day 29 — bounded local procedure evidence selection, V7

[Russian instructions](README.ru.md) | [Start here](START_HERE.ru.md)

Qwen2.5 14B Instruct Q4_K_M, local bge-m3 embeddings and the Week 6 index.
Settings remain temperature 0, max output 1024, context 8192. Factual V3 results
and all previous Q4/Q5/speed/resource comparisons remain unchanged.

V6 failed manual procedure review. V7 changes the periodic-procedure contract:
the local model selects four source-derived evidence IDs, and the application
validates and renders an extractive verification plan. It does not fill missing
selections, rewrite old model output or invoke a second model. An invalid or
incomplete completed selection is a retained, quality-blocked refusal.

V7 live quality and performance are pending. With the previous environment,
the next control reuses 27 observations and generates three new selections.
Keep the cache; token probes and warmups are separately accounted for.
All V1–V6 Python and original live reports are byte-identical.

generation.answer is raw model selection; response.answer is deterministic
application rendering. Selection output token counts are not the length of
the rendered answer or evidence of better free-text generation. V7 reports
must be read/verified/imported through the V7 decoder; its launcher supports
legacy V1–V6 reports too. Manual semantic review is still required.
