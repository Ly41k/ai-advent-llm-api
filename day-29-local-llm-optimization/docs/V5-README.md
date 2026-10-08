**English** | [Русский](README.ru.md)

# Day 29 — local LLM optimization

The selected configuration targets **short factual RAG answers about repository
documentation**: local Qwen2.5 14B Instruct Q4_K_M, temperature=0,
max_tokens=1024, num_ctx=8192, and the factual V3 one-claim example prompt.
Embeddings and retrieval are local. No cloud models or weight fine-tuning were used.

Twelve responses across four questions passed manual review, with three repeats
per question. The VPS verification procedure remains a known limitation: its
V5 keyword/source PASS does not establish per-claim semantic grounding.
Procedural V4/V5 templates remain experiments.

Measurements and limitations are in FINAL_REPORT.ru.md. SELECTED_PROFILE.json
records the configuration; review/manual-review.json records scoped judgments
linked to actual report and observation identities. Original JSON outputs are
unchanged. The eight supplied reports are included in reports/check/.

Extract into the existing course repository. Other days, root READMEs and the
index are not replaced. All previously delivered Python runtime/template files
are unchanged. Model weights, credentials and the local SQLite cache are excluded.
Keep the existing cache. No new model download or index rebuild is needed for the
existing environment. Initial instructions are archived in docs/V1-README.md.

## Offline report verification

```bash
python day-29-local-llm-optimization/experiments/focused_v3/main.py verify \
  day-29-local-llm-optimization/reports/check/control-v5.json
```

This performs no Ollama calls and is not a semantic quality verdict. The original
optimization_verified=false is preserved; independent scoped review is separate.

## Replay the verified factual subset

```bash
python day-29-local-llm-optimization/experiments/focused_v3/main.py run \
  --profiles baseline focused-v3-q4 \
  --split all --case base-06 base-07 base-08 negative-03 --repeats 3 \
  --retry-from day-29-local-llm-optimization/reports/check/control-v5.json \
  --output day-29-local-llm-optimization/reports/check/factual-final.json
```

With matching experimental identities, all 24 observations are reused. No new
answers, token probes or warmups are needed. Run still checks local model/index
readiness; plan instead performs zero HTTP calls. Changed questions/settings need
new observations. Weak but valid answers are retained rather than regenerated
until they pass. Use this launcher for the V3 template; the original main.py uses
the original V1 templates. New questions require separate quality assessment.
