**English** | [Русский](README.ru.md)

# Day 29 — local LLM optimization / V1

A local-only experiment for Bublik's Day 28 RAG: downloaded Qwen2.5 14B, bge-m3, the read-only Day 21 index, and Day 23 retrieval. It compares temperature, output limits, context windows, task prompts and Q4/Q5 quantization. No cloud provider is instantiated, no API key is loaded, and there is no cloud fallback.

**V1 provides the experiment, not a measured optimization claim.** `candidate-*` profiles require real quality/performance/resource measurements on the author's Mac. There is no weight training or fine-tuning.

## Install and start small

Extract this folder into the root of the existing `ai-advent-llm-api` repository. It adds Day 29 without replacing previous days, root READMEs, `.env` or the index. Dependencies were checked against commit `3d2e9616dc2fd857a918606f1cb371045ef48cd4`. Models are not bundled.

From the repository root:

```bash
source .venv/bin/activate
python -m pip install -r day-29-local-llm-optimization/requirements.txt
python -m unittest discover -s day-29-local-llm-optimization -p 'test_day29.py' -v
python day-29-local-llm-optimization/main.py doctor --profiles baseline
python day-29-local-llm-optimization/main.py plan --profiles baseline --case base-07
python day-29-local-llm-optimization/main.py run \
  --profiles baseline --case base-07 --repeats 3 \
  --output day-29-local-llm-optimization/reports/check/baseline-worker-v1.json
```

Ollama must be running with downloaded `qwen2.5:14b` and `bge-m3`. The existing `day-21-document-indexing/knowledge.db` must match its corpus. Use Day 21 build/verify only if the index is absent or stale. Day 29 itself is outside the indexed corpus. Python 3.13 is the author's environment; offline checks were run on Python 3.12.

Now add a candidate on the same question:

```bash
python day-29-local-llm-optimization/main.py run \
  --profiles baseline candidate-q4 --case base-07 --repeats 3 \
  --output day-29-local-llm-optimization/reports/check/worker-pair-v1.json
```

The completed three baseline answers are reused. Only three candidate answers are new, plus explicitly recorded maintenance probes/warmups. JSON retains raw output, exact evidence, settings, usage and process samples. The adjacent Markdown contains readable answers and a manual-review checklist.

## Resume: completed answers are never silently repeated

Default state: `day-29-local-llm-optimization/cache/experiments.sqlite3`. Every observation commits individually; reports are written atomically after observations. Ctrl+C retains completed trials. Resume uses the same command and cache; only missing/failed slots are requested. A technical error stops the run instead of silently issuing repeated HTTP calls.

Reuse requires matching question/rubric, profile, actual model digest and chat template, task prompt, evidence/index/embedding digest, runtime, Ollama/Python/hardware, sampling controls, seed schedule and series. Seeds default to 42/43/44 for trials 1/2/3 and match between compared profiles.

Valid but semantically poor answers are retained as quality failures, without endless regeneration until PASS. Invalid JSON, incomplete output or unverified local loading do not count as completed answers. Changing a prompt or settings requires new observations: old answers are never relabeled as new-profile measurements. Increasing repeats from 1 to 3 adds only slots 2 and 3.

For a short batch:

```bash
python day-29-local-llm-optimization/main.py run \
  --profiles baseline candidate-q4 --split calibration --max-new-observations 3
```

Repeat it to continue. The cap includes new observations, including refusals/errors; separately reported maintenance generations are extra. Retrieval is prepared for the selected case set first, so choose one `--case` for a minimal first run.

`plan` makes zero HTTP/embedding/generation calls and uses the last saved environment for a provisional reuse estimate. `run` verifies the current index and model identities before accepting that estimate. A fully cached live run makes no answer, token-probe or warmup calls, but still checks readiness.

Portable import from an original unedited Day 29 report:

```bash
python day-29-local-llm-optimization/main.py run \
  --profiles baseline candidate-q4 --case base-07 \
  --retry-from day-29-local-llm-optimization/reports/check/baseline-worker-v1.json \
  --output day-29-local-llm-optimization/reports/check/imported-pair-v1.json
```

Automatic SQLite resume normally makes this unnecessary. Imports validate checksums, raw model output, evidence bindings, schema, identity and summary. Day 28 reports are historical evidence, not compatible Day 29 observations. Checksums establish internal consistency, not authenticity. Keep the cache and source JSON when moving/updating the project. `--series fresh-02` deliberately starts fresh observations; do not change series merely to resume.

## Profiles and staged optimization

`profiles.json` contains editable five-field profiles: model, temperature, max_tokens, num_ctx, prompt. Runtime options are sent explicitly. The initial profiles are:

| Profile | Temperature | Output cap | Context | Task prompt |
|---|---:|---:|---:|---|
| baseline | 0 | 2048 | 16384 | Day 28 baseline |
| temperature-01 / temperature-02 | 0.1 / 0.2 | 2048 | 16384 | baseline |
| tokens-1024 / tokens-512 | 0 | 1024 / 512 | 16384 | baseline |
| context-8192 | 0 | 2048 | 8192 | baseline |
| prompt-compact | 0 | 2048 | 16384 | compact |
| candidate-q4 / candidate-q5 | 0 | 1024 | 8192 | compact |

Baseline is `qwen2.5:14b`; Q5 is `qwen2.5:14b-instruct-q5_K_M`. Confirm actual quantization in doctor metadata instead of inferring it from a mutable tag. A shorter output cap does not guarantee faster generation if the model already stops early.

Change one factor at a time using calibration:

```bash
python day-29-local-llm-optimization/main.py run --profiles baseline temperature-01 temperature-02 --split calibration
python day-29-local-llm-optimization/main.py run --profiles baseline tokens-1024 tokens-512 --split calibration
python day-29-local-llm-optimization/main.py run --profiles baseline context-8192 prompt-compact --split calibration
```

Completed baseline trials are reused across these runs. Calibration has eight cases: six factual and two negative controls. Evaluation has twelve. Add a `selected` profile with the winning values after calibration, then run `--profiles baseline selected --split evaluation --repeats 3` without tuning on evaluation. This is 72 observations. `--split all` for two profiles is 20 ×3 ×2 =120 observations, plus separately accounted maintenance calls. The course questions are already known: this is a held-out experiment split, not an independently unseen benchmark.

## Quantization

```bash
ollama pull qwen2.5:14b-instruct-q5_K_M
python day-29-local-llm-optimization/main.py doctor --profiles candidate-q4 candidate-q5
python day-29-local-llm-optimization/main.py run \
  --profiles candidate-q4 candidate-q5 --case base-07 --repeats 3
```

Verify both represent Qwen2.5 14B Instruct and their metadata reports Q4_K_M/Q5_K_M. Q5's approximate 11 GB download is not its entire memory footprint. Selected model variants run sequentially; the other selected quantization is unloaded before the block. bge-m3 is unloaded after shared retrieval to keep residency comparable. Unrelated user models are not automatically stopped. On the author's M1/32 GB Mac, start with the candidate 8192 context and watch memory pressure/swap. Q5 may cost more memory/time without improving this task.

## Context verification and maintenance overhead

A cached one-token `/api/chat` probe measures the full input for each exact model/prompt before testing a smaller context. It uses the same schema, a larger `--token-check-context` (32768 by default), and is never scored as an answer. The larger probe window temporarily consumes extra memory. V1 supports Qwen2 byte-level BPE; a conservative UTF-8-byte bound plus reserve protects the probe from input truncation, and `/api/show` checks the supported limit.

The candidate must satisfy `input_tokens + max_tokens + 128 <= num_ctx`. The real answer's input count must match the untruncated probe. No question or evidence is silently discarded. Overflow is reported without an answer call. Probes unload their model; a short target-context warmup precedes the measured block. Profile order alternates between trial blocks. Prompt-cache state is captured where Ollama exposes it; warming up does not imply an empty prompt cache.

## Metrics and acceptance

- Quality: exact JSON/evidence bindings plus transparent term/source/evidence heuristics. Manually inspect support, completeness, conditions, names and refusals.
- Speed: wall answer/validation time, raw Ollama input/output durations and decode tokens/s. Application refusals are excluded from generation timing.
- Resources: sampled RSS/CPU for processes with Ollama in their name, Python RSS, available system memory/swap, and `/api/ps` allocation details. GPU utilization is unavailable and remains null.
- Apple Silicon shares RAM/VRAM. Do not add RSS and size_vram; summed RSS may double-count shared mappings. Sampled peaks may miss short-lived processes.
- Pipeline time combines saved shared retrieval and a particular generation; it is reconstructed, not a fresh end-to-end measurement.
- Reused measurements keep their original timestamps. Missing slots and errors are visible; quality denominator includes present errors. Stable wrong answers remain wrong.

```bash
python day-29-local-llm-optimization/main.py verify day-29-local-llm-optimization/reports/check/worker-pair-v1.json
python day-29-local-llm-optimization/main.py summary day-29-local-llm-optimization/reports/check/worker-pair-v1.json
```

Verify is structural and returns 0 even for consistently recorded quality failures; it is not a semantic verdict. Run returns 0 for a complete heuristic pass or voluntary batch pause, 1 for a technical/quality issue, and 130 for Ctrl+C. Inspect `state` to distinguish paused/completed. `optimization_verified` stays false until results are manually assessed; candidates are not automatically certified.

Keep selected real reports in `reports/accepted/`; intermediate check/video reports and cache are ignored by Git. Offline scripted transport tests are implementation evidence, not live model measurements. See [VALIDATION.md](VALIDATION.md) and the more detailed Russian instructions.

Official references: [API](https://docs.ollama.com/api/chat), [usage](https://docs.ollama.com/api/usage), [context](https://docs.ollama.com/context-length), [Q5 model](https://ollama.com/library/qwen2.5:14b-instruct-q5_K_M).
