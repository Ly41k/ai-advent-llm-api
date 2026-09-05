**English** | [Русский](README.ru.md)

# Day 5 — Model Versions

The fifth AI Advent assignment compares language models of different sizes.

The same technical prompt is sent to three models through the Groq API. The program measures latency, token usage, and estimated cost for each response. A separate request then compares response quality and produces a short conclusion.

## Assignment

Run the same request on:

- a smaller model;
- a medium-sized model;
- a larger model.

Measure:

- response time;
- input and output tokens;
- request cost.

Then compare quality, speed, and resource usage.

## Selected Models

| Experiment level | Model | Groq model ID | Input per 1M tokens | Output per 1M tokens |
|---|---|---|---:|---:|
| Smaller | [GPT-OSS 20B](https://huggingface.co/openai/gpt-oss-20b) | `openai/gpt-oss-20b` | $0.075 | $0.30 |
| Medium | [Qwen 3.6 27B](https://huggingface.co/Qwen/Qwen3.6-27B) | `qwen/qwen3.6-27b` | $0.60 | $3.00 |
| Larger | [GPT-OSS 120B](https://huggingface.co/openai/gpt-oss-120b) | `openai/gpt-oss-120b` | $0.15 | $0.60 |

Prices were recorded in the source code on September 4, 2026. Check the [official Groq model list](https://console.groq.com/docs/models) before reusing them because model availability and pricing can change.

The experiment levels are intentionally approximate. Parameter count alone does not guarantee better output. Architecture, training, specialization, and reasoning mode also affect quality.

## Selected Prompt

The models analyze a real one-time-event problem in Kotlin Multiplatform:

```kotlin
private val _resultFlow = MutableSharedFlow<VeriffResult>()
val resultFlow: SharedFlow<VeriffResult> = _resultFlow.asSharedFlow()

private fun onActivityResult(result: VeriffResult) {
    _resultFlow.tryEmit(result)
}
```

The event is emitted before collection starts, so the screen does not receive it. Every model must:

1. Explain the exact cause.
2. Propose the smallest fix.
3. Provide corrected code.
4. Compare `replay=1`, `extraBufferCapacity=1`, and `Channel(BUFFERED)`.
5. Explain how to avoid processing the same result again.

The answer must also consider multiple collectors, screen recreation, one-time-event semantics, and the limits of exactly-once delivery after process death.

## Experiment Conditions

The three main requests use the same:

- system prompt;
- user prompt;
- `temperature=0.2`;
- `max_completion_tokens=900`;
- sequential execution order.

The model and its lowest supported reasoning mode change:

| Model | `reasoning_effort` |
|---|---|
| GPT-OSS 20B | `low` |
| Qwen 3.6 27B | `none` |
| GPT-OSS 120B | `low` |

GPT-OSS and Qwen use different mode names. Their lowest supported settings reduce internal reasoning-token usage and leave more of the completion budget for visible output.

## Measuring Latency

End-to-end request time is measured with `perf_counter()`:

```python
started_at = perf_counter()

response = client.chat.completions.create(...)

elapsed_seconds = perf_counter() - started_at
```

The value includes network transfer, provider-side waiting, processing, and complete response generation. One run is a sample, not a permanent speed rating. A stronger benchmark would repeat every request and compare median latency.

## Counting Tokens

Token usage comes directly from `response.usage`:

```python
input_tokens = response.usage.prompt_tokens
output_tokens = response.usage.completion_tokens
```

- `prompt_tokens` counts the system and user messages;
- `completion_tokens` counts tokens used during generation;
- total tokens are the sum of input and output tokens.

## Estimating Cost

Input and output costs are calculated separately:

```python
input_cost = input_tokens / 1_000_000 * input_price_per_million
output_cost = output_tokens / 1_000_000 * output_price_per_million
estimated_cost = input_cost + output_cost
```

This is an estimate based on public list prices, not the amount actually charged to the account. Actual charges may be zero on a free tier.

Price does not necessarily follow model size. In this model set, Qwen 3.6 27B has a higher list price than GPT-OSS 120B.

## Comparing Quality

After the three main requests, the program sends a separate evaluation request to `openai/gpt-oss-120b`:

```python
temperature=0.0
reasoning_effort="low"
max_completion_tokens=900
```

The responses are anonymized before evaluation:

- `A` — GPT-OSS 20B;
- `B` — Qwen 3.6 27B;
- `C` — GPT-OSS 120B.

The evaluator receives the answers and measured metrics. It produces a 3–5 sentence conclusion identifying:

- the best response by quality;
- the fastest model;
- the least expensive model;
- the limitations of a single-run comparison.

Evaluator token usage and cost are printed separately and are not mixed into the main comparison table.

The evaluation is still another model's opinion. A rigorous benchmark would require independent test cases, reference answers, and predefined scoring rules.

## Estimating Resource Usage

The Groq API does not expose actual GPU, memory, or energy consumption. The experiment therefore uses indirect indicators:

- model size;
- response time;
- token usage;
- estimated cost.

Direct hardware measurements would require running the models on controlled infrastructure and collecting system metrics.

## Groq API Limits

On the account tier used for this project, `qwen/qwen3.6-27b` may have a `1000 OTPM` output-token-per-minute limit. The main request uses a maximum of 900 tokens, but tokens already consumed in the rolling minute window also count.

If Groq returns `429 rate_limit_exceeded`, wait for the rolling window to reset and run the complete experiment again. The current implementation does not retry automatically because waiting would distort the latency measurement.

## Program Output

The program prints:

1. The original prompt.
2. Every model response and its metrics.
3. A summary table containing latency, tokens, and cost.
4. The separate evaluator cost.
5. A short conclusion comparing the models.
6. Links to all models and the Groq price list.

The links appear at the bottom of the console output:

```text
ССЫЛКИ НА ВСЕ МОДЕЛИ
- GPT-OSS 20B: https://huggingface.co/openai/gpt-oss-20b
- Qwen 3.6 27B: https://huggingface.co/Qwen/Qwen3.6-27B
- GPT-OSS 120B: https://huggingface.co/openai/gpt-oss-120b
- Groq Models and Pricing: https://console.groq.com/docs/models
```

## Setup and Run

Complete the shared [project setup](../README.md#project-setup), add `GROQ_API_KEY` to the root `.env` file, and run:

```bash
python day-05-model-versions/main.py
```

No user input is required. The program exits after all requests and comparisons are complete.

## Day 5 Takeaway

A larger model may handle complex requirements better, but it usually requires more computational resources. Latency and price also depend on the provider's infrastructure and pricing rather than model size alone.

A single experiment can reveal practical differences, but it cannot produce a universal ranking. Model selection should balance quality, latency, and cost on representative project tasks.

## Useful Links

- [Groq: Supported Models and Pricing](https://console.groq.com/docs/models)
- [Groq API Reference](https://console.groq.com/docs/api-reference)
- [Groq: Rate Limits](https://console.groq.com/docs/rate-limits)
- [GPT-OSS 20B on Hugging Face](https://huggingface.co/openai/gpt-oss-20b)
- [Qwen 3.6 27B on Hugging Face](https://huggingface.co/Qwen/Qwen3.6-27B)
- [GPT-OSS 120B on Hugging Face](https://huggingface.co/openai/gpt-oss-120b)
