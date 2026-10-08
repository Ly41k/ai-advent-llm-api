**English** | [Русский](README.ru.md)

# Day 29 — task-specific local LLM optimization

This lesson optimizes a local Qwen RAG application for short repository lookups, unsupported-question abstention, and a source-backed procedure for checking the Day 18 periodic worker on a VPS.

The selected configuration is **Qwen2.5 14B Instruct Q4_K_M**, served by local Ollama on a **MacBook Pro M1 with 32 GB RAM**. Embeddings, retrieval, and answer generation run locally. The final V7 evidence contains **21 semantically reviewed selected-profile observations across seven questions**. The assignment is complete within this tested scope; another live run is optional.

## Selected configuration

| Setting | Baseline | Selected |
|---|---:|---:|
| Model | Qwen2.5 14B Instruct | Qwen2.5 14B Instruct |
| Quantization | Q4_K_M | Q4_K_M; separately compared with Q5_K_M |
| Temperature | 0 | 0 |
| Maximum output tokens | 2048 | 1024 |
| Context window (`num_ctx`) | 16384 | 8192 |
| Prompt / output contract | General factual claims | V3 factual answers; V7 periodic-procedure evidence selections |

[SELECTED_PROFILE.json](SELECTED_PROFILE.json) records the approved scope, settings, templates, launcher, and evidence files. `max_tokens` is the application's output limit; the provider maps it to Ollama's `num_predict`.

Retrieval reuses the Week 6 / [Day 21 index](../day-21-document-indexing/README.md): local `bge-m3`, fixed chunks, candidate K=20, final K=5, cosine threshold 0.50, heuristic rewrite, and a 16000-character retrieval-context limit. The database is opened read-only.

Temperature variants are available in [profiles.json](profiles.json), but an isolated temperature improvement was not measured. Output/context limits and prompts changed together. The model weights were not fine-tuned.

## How V7 works

The current launcher is **`experiments/quality_v7/main.py`**. It retains the V3 factual template and routes supported periodic-worker verification questions to the V7 selector contract. The top-level `main.py` retains the original experiment CLI and does not automatically enable V7.

For a periodic procedure:

1. Local retrieval supplies source excerpts and exact quotation units.
2. The application groups evidence into four roles: service status, logs, execution results, and recurrence against the schedule.
3. Local Qwen selects one allowed evidence ID per role, or abstains, using a constrained JSON schema.
4. The application validates IDs, roles, source metadata, and exact substrings, then renders a source-extractive observation plan.
5. An offline audit checks explicit rules; a separate semantic review assesses the resulting answer against the sources.

`generation.answer` preserves the model's raw selections. `response.answer` is the application-rendered procedure. The application does not execute the suggested VPS commands or establish that a particular VPS actually works. Other procedures are outside the approved V7 scope.

Unknown IDs, wrong roles, missing steps, or substituted evidence block publication of a factual procedure. Completed poor answers remain stored failures; the application does not silently retry until a pass. No cloud fallback or additional auditor LLM is called by the runtime.

## Quality before and after

| Stage | Observed behavior / reviewed result |
|---|---|
| Baseline worker answer | Names `worker.py`, but adds unnecessary VPS setup instructions and an unsupported citation binding |
| V3 factual / negative controls | Four questions × three trials: **12/12 pass** |
| V6 periodic procedure | More precise source bindings, but wrong language, setup commands, and incomplete recurrence verification: **3/3 fail** |
| V7 original Russian procedure | **3/3 pass**; status, logs, execution, and repeated stored results are separated |
| Frozen V7 transfer, new English formulation | **3/3 pass** |
| Frozen V7 transfer, new Russian formulation | **3/3 pass** |

The final scope includes four factual/abstention questions and three formulations of one periodic-procedure case. All three observations per case are retained. Within each new transfer question, all three rendered responses are identical. Code and transfer questions were frozen before the transfer run.

Semantic reviews were performed by an assistant against the supplied JSON and source documentation, and are stored separately in `review/`. Automated checks and exact quotations alone do not establish semantic completeness. The original reports, failures, and automated verdicts remain unchanged.

## Speed, quantization, and resources

| Case / variant | Median generation time |
|---|---:|
| Worker fact, baseline | 26.281 s |
| Worker fact, Q4 / V3 | 6.091 s |
| Worker fact, Q5 / V3 | 7.665 s |
| Periodic VPS procedure, V6 | 16.572 s |
| Periodic VPS procedure, V7 | 6.077 s |
| New English V7 formulation | 6.067 s |
| New Russian V7 formulation | 6.105 s |

V6→V7 reduces this procedure's median by about **63.3%**, while changing both the input and the output contract. V7's 75 output tokens are evidence selections; the full displayed procedure is rendered by the application. This is not a measurement of generating the same free-text answer faster.

The first transfer trial takes 13.496 s in English and 12.637 s in Russian; subsequent trials are around 6 s. Prefill and prompt/KV-cache affect timing. No new baseline or Q5 transfer run was performed.

Q4/Q5 were compared on **one factual worker question**, with three observations per variant and matching settings, messages, and evidence:

| Metric | Q4_K_M | Q5_K_M |
|---|---:|---:|
| Median generation | 6.09 s | 7.66 s |
| Median decode | 11.47 tokens/s | 9.27 tokens/s |
| Maximum Ollama `size_vram` | 9.56 GiB | 10.89 GiB |

Quality was equivalent on that question; Q5 took about 25.8% longer and reported 1.33 GiB more allocation. Q4 was measured first; order was not randomized. This does not establish superiority on other tasks.

The full control report records maximum `size_vram` of 11.19 GiB for baseline and 9.67 GiB for the selected profile. Reports also retain sampled process RSS/CPU, available system memory, and swap. **RSS and `size_vram` are not full physical unified-memory usage and must not be added together.** Full physical peak and GPU utilization were not measured.

See [FINAL_REPORT.ru.md](FINAL_REPORT.ru.md) for detailed comparisons and limitations.

## Check the saved result without Ollama

Run from the **repository root**, with the earlier lesson folders present:

```bash
python day-29-local-llm-optimization/experiments/quality_v7/main.py verify \
  day-29-local-llm-optimization/reports/check/control-v7.json

python day-29-local-llm-optimization/experiments/quality_v7/main.py verify \
  day-29-local-llm-optimization/reports/check/quality-transfer-v7.json
```

These commands check report seals, observations, reconstructed answers, and summaries without contacting Ollama or requiring the original index database. They do not regenerate answers or rerun semantic review. Use the V7 launcher for V7 reports.

`consistent=true` confirms internal consistency. The saved reports may still show **`optimization_verified=false` and `human_review_required=true`**: these conservative automatic fields are preserved. The separate semantic review is not written back into the sealed automatic verdict.

## Optional new local experiment

Keep Days 21, 23, 26, and 28 alongside this lesson: Day 29 imports their index, retrieval, and provider components. Use the project's Python 3.13 environment:

```bash
python -m pip install -r day-29-local-llm-optimization/requirements.txt
ollama pull bge-m3
ollama pull qwen2.5:14b
```

An existing Ollama desktop server is sufficient. A cloud key is not required. Q5 is needed only for a separate quantization experiment.

The indexed corpus includes the root READMEs. **After replacing them, rebuild the index before the next live run**:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
```

A rebuild changes the index identity; earlier cache entries are historical results, not fresh measurements for the new corpus. Saved-report verification above remains available without rebuilding.

Preview a selected-profile experiment without model calls:

```bash
python day-29-local-llm-optimization/experiments/quality_v7/main.py plan \
  --profiles focused-v3-q4 --split all --case base-10
```

Check the installed model and current index, then optionally generate up to three new scored answers:

```bash
python day-29-local-llm-optimization/experiments/quality_v7/main.py doctor \
  --profiles focused-v3-q4

python day-29-local-llm-optimization/experiments/quality_v7/main.py run \
  --profiles focused-v3-q4 --split all --case base-10 \
  --max-new-observations 3 \
  --output day-29-local-llm-optimization/reports/check/readme-live.json
```

`doctor` contacts local Ollama but generates no answers. `run` may also perform separately reported warmups and token probes; the scored-answer limit does not limit those calls. Matching completed trials are reused, including quality failures. Read the generated audit and review all answers against their sources.

## Tests and project files

```bash
python day-29-local-llm-optimization/test_day29.py -v
python -m unittest discover \
  -s day-29-local-llm-optimization/experiments/quality_v6 \
  -p test_quality_v6.py -v
python -m unittest discover \
  -s day-29-local-llm-optimization/experiments/quality_v7 \
  -p test_quality_v7.py -v
```

[VALIDATION.md](VALIDATION.md) records 28 original V1, 17 V6, and 14 V7 tests. These are offline implementation checks, separate from the live quality measurements.

| Path | Purpose |
|---|---|
| `cli29.py`, `engine29.py`, `provider29.py` | Experiment CLI, identity/validation, and measured local generation |
| `store29.py`, `resources29.py` | SQLite cache and sampled resource metrics |
| `profiles.json`, `questions.json` | Original experiment profiles and question set |
| `experiments/focused_v3/` | Selected factual prompt and settings |
| `experiments/quality_v7/` | Current selector launcher, renderer, audit, and transfer questions |
| `reports/check/` | Committed original live evidence plus ignored new local outputs |
| `review/` | Separate automatic audits, semantic reviews, and reanalyses |
| `docs/` | Earlier documentation snapshots; historical, not current instructions |

The existing `.gitignore` excludes cache, bytecode, video outputs, and new check reports. Selected original reports are already tracked and remain available after cloning. Preserve them without editing. `MANIFEST.sha256.json` describes the original final V7 bundle; replacing these READMEs changes their archive hashes, but does not change the sealed report contents.

Further reading: [assignment checklist](ASSIGNMENT_CHECKLIST.ru.md), [V7 contract](QUALITY_V7.ru.md), [quality review](QUALITY_REVIEW.ru.md), [console demonstration](CONSOLE_VIDEO.ru.md), and [backlog](BACKLOG.ru.md).
