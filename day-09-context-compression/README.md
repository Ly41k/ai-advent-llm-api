**English** | [Русский](README.ru.md)

# Day 9 — Context Management: History Compression

The ninth assignment keeps recent dialogue details verbatim while replacing older messages with a separately persisted cumulative summary.

## Simulation World

Bublik operates inside a fictional research simulation containing 100 star systems. Each system has 4–16 planets, and some planets have natural satellites. When the captain does not specify a parameter, Bublik introduces a plausible simulation assumption and continues the research. It asks a clarifying question only when the captain's choice is required or different options would fundamentally change the result.

## Assignment

- keep the latest N messages unchanged;
- summarize older messages in batches;
- persist the summary separately and use it instead of the full history;
- compare answer quality and token usage with and without compression.

## Result

The complete successful history still remains in SQLite. It is never deleted. The context sent to the model contains:

```text
system prompt + cumulative summary + unsummarized messages + current request
```

The latest 10 messages are always protected. Up to 9 additional old messages may temporarily remain verbatim while the next complete batch accumulates. When 10 messages exist before the protected window, `HistoryCompressor` sends that batch together with the previous summary to GPT-OSS 20B. The resulting cumulative summary replaces the previous summary in `conversation_summaries` and advances `summarized_through_message_id`.

## Structure

```text
day-09-context-compression/
├── agent.py
├── compression.py
├── experiment.py
├── main.py
├── memory.py
├── tokens.py
├── README.md
└── README.ru.md
```

- `compression.py` selects old batches and updates the summary;
- `memory.py` stores complete messages, the summary cursor, and separate costs;
- `agent.py` builds compressed and full contexts;
- `main.py` exposes the interactive agent and comparison commands;
- `experiment.py` measures reproducible offline token savings.

## Persistence

The `conversation_summaries` table stores one cumulative summary per `conversation_id`:

- summary text;
- the last summarized message ID;
- number of compressed source messages and updates;
- cumulative prompt, completion, total tokens, and summary cost.

The full `messages` table is retained for diagnostics, `/history`, and a fair comparison against the compressed context.

## Run

```bash
pip install -r requirements.txt
python day-09-context-compression/main.py
```

Commands:

- `/history` — latest entries from the complete history;
- `/summary` — persisted summary and its generation cost;
- `/compare` — ask the same question with full and compressed histories;
- `/stats` — main-request cost plus summary overhead;
- `/dialogs` — switch conversation;
- `/exit` or `выход` — stop.

Run the offline token comparison:

```bash
python day-09-context-compression/experiment.py
```

It compares short, medium, and long synthetic histories without calling Groq.

## Comparing Quality

Use a dialogue with at least 20 completed messages so a summary exists. Run `/compare` and ask a question that depends on earlier facts and recent decisions. The command sends the same question twice with identical model settings:

1. full successful history;
2. cumulative summary plus the latest 10 messages.

Compare whether both answers preserve facts, captain decisions, numeric values, and unresolved questions. The command also prints actual Groq prompt tokens and costs for both responses. Comparison requests are not added to the dialogue.

## Honest Cost Accounting

Summary generation is an additional API call. Its tokens and cost are stored separately and included by `/stats`. Compression becomes beneficial when the input tokens saved on later requests exceed the one-time cost of updating the summary.

## Current Limitations

- summary quality depends on the model;
- quality comparison is manual rather than judged by another model;
- compression uses fixed limits of 10 recent messages and 10 messages per batch;
- local token counts are estimates, while Groq usage is authoritative;
- the comparison mode performs two paid API calls.

## Day 9 Outcome

Bublik preserves recent details, compresses old context without deleting the original history, measures the real compression overhead, and exposes the quality-versus-cost trade-off.
