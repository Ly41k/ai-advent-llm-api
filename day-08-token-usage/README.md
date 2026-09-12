**English** | [Русский](README.ru.md)

# Day 8 — Working with Tokens

The eighth assignment measures how the current request, saved history, and model response consume the context window and affect API cost.

## Assignment

- count tokens in the current request, complete history, and model response;
- compare a short, long, and oversized dialogue;
- show how token usage and cost grow;
- demonstrate what fails when the model limit is exceeded.

## Result

`BublikAgent` now performs two complementary measurements:

1. Before the API call, `GptOssTokenCounter` uses the GPT-OSS `o200k_harmony` encoding to estimate the current request, history, and complete prompt.
2. After the API call, `response.usage` provides the actual billable prompt, completion, and total token counts reported by Groq.

The local estimate enables a preflight context check. The API result enables actual per-request and cumulative cost calculations.

## Structure

```text
day-08-token-usage/
├── agent.py
├── experiment.py
├── main.py
├── memory.py
├── tokens.py
├── README.md
└── README.ru.md
```

- `tokens.py` owns token counting, model limits, prices, and metrics;
- `agent.py` checks the context and combines estimates with Groq usage;
- `memory.py` stores usage for every completed request;
- `main.py` runs the interactive persistent agent;
- `experiment.py` compares three histories without API requests.

## Reported Metrics

After every response, the CLI prints the current-request tokens, saved-history tokens, estimated and actual prompt tokens, completion tokens, visible-response tokens, total tokens, and estimated cost.

Completion and visible-response tokens may differ because GPT-OSS is a reasoning model. Provider usage can include generated reasoning tokens that are absent from the final visible answer.

## Context Protection

GPT-OSS 20B on Groq currently has a 131,072-token context window. The agent reserves 1,200 tokens for the answer and checks:

```text
estimated prompt tokens + reserved completion tokens <= context window
```

If it does not fit, `ContextWindowExceededError` is raised before the request is saved or sent. Without this check, the provider would reject the oversized request.

## Cost

The example uses the current GPT-OSS 20B prices: `$0.075` input and `$0.30` output per 1 million tokens.

```text
cost = input_tokens × input_price + output_tokens × output_price
```

These constants are an educational snapshot and should be checked before real billing calculations.

## Run

Install dependencies and start the interactive agent:

```bash
pip install -r requirements.txt
python day-08-token-usage/main.py
```

Commands:

- `/history` — current dialogue history;
- `/stats` — cumulative actual tokens and cost;
- `/dialogs` — switch dialogue;
- `/exit` or `выход` — stop.

Run the reproducible comparison:

```bash
python day-08-token-usage/experiment.py
```

It creates a short dialogue with 1 exchange, a long dialogue with 100 exchanges, and an oversized dialogue with 1,500 exchanges. For valid scenarios, it also accumulates the input tokens, output tokens, total tokens, and estimated cost of all completed exchanges. It does not call Groq or spend API credits.

## Main Observation

Every request resends the selected history. The prompt therefore grows, later turns cost more, and cumulative billable input grows faster than the unique stored text.

Eventually the history plus the requested output no longer fits. The application must then remove old messages, summarize them, retrieve only relevant fragments, or use a larger context window.

## Current Limitations

- local prompt counts are estimates; Groq usage is authoritative for billing;
- the full history is intentionally sent to demonstrate overflow;
- truncation and summarization are not implemented yet;
- prices and limits can change;
- cached-input pricing is not included.

## Day 8 Outcome

Bublik now exposes token consumption, records the cost of every completed exchange, and stops oversized requests before they reach the model.
