**English** | [Русский](README.ru.md)

# Day 4 — Temperature

The fourth AI Advent assignment explores the `temperature` parameter and its effect on language model responses.

The same prompt is sent to `openai/gpt-oss-20b` with three temperature values. The responses are then compared by accuracy, creativity, and diversity.

## Assignment

Run one request with:

- `temperature=0`;
- `temperature=0.7`;
- `temperature=1.2`.

Compare the responses and determine which types of tasks suit each setting.

## Selected Prompt

```text
Придумай концепцию автономного робота для исследования подлёдного
океана Европы — спутника Юпитера. Укажи название робота, цель миссии,
три технически правдоподобные функции и короткий слоган.
Не выдавай предположения за подтверждённые факты.
```

The prompt combines factual constraints with a creative task. This makes it possible to evaluate both originality and the model's ability to preserve technical plausibility as randomness increases.

## How the Experiment Works

The program performs three independent requests. Every call uses the same:

- model;
- system prompt;
- user prompt;
- reasoning effort;
- completion-token limit.

Only `temperature` changes:

```python
TEMPERATURES = (0.0, 0.7, 1.2)

for temperature in TEMPERATURES:
    response = get_response(
        user_prompt=TASK,
        temperature=temperature,
    )
```

A fourth request is then executed with `temperature=0`. It receives all three responses, compares them using the selected criteria, and produces a conclusion.

## What `temperature` Controls

Temperature affects how the next token is selected:

- a low value strongly favors the most probable options;
- a medium value allows more variation;
- a high value increases the probability of less expected choices.

Temperature does not add knowledge to a model and cannot guarantee correctness or originality. It controls generation randomness.

Groq accepts `temperature` values from `0` to `2`. Higher values generally produce more varied responses, while lower values make generation more focused and stable.

## Expected Characteristics

| Temperature | Expected behavior | Suitable tasks |
|---:|---|---|
| `0` | The most focused and predictable response | Data extraction, classification, technical instructions, structured output |
| `0.7` | A balance between accuracy and variation | Chatbots, explanations, product ideas, general writing |
| `1.2` | More unexpected ideas and wording, with a higher risk of inaccuracies | Brainstorming, names, slogans, story ideas, creative experiments |

These are guidelines rather than guarantees. Results also depend on the model, prompt, context, and other generation parameters.

## Evaluation Criteria

### Accuracy

The evaluator checks whether:

- every requested part is present;
- the proposed robot functions are logically plausible;
- assumptions are not presented as confirmed facts.

### Creativity

The evaluator considers the originality of the robot's name, functions, mission description, and slogan.

### Diversity

The responses are compared to determine how much their ideas and wording differ from the more obvious alternatives.

One response per temperature demonstrates a possible behavior, but it is not enough for a statistically reliable diversity measurement. A rigorous experiment would run every temperature multiple times.

## Model Parameters

```python
response = client.chat.completions.create(
    model=MODEL,
    messages=messages,
    temperature=temperature,
    reasoning_effort="low",
    max_completion_tokens=MAX_COMPLETION_TOKENS,
)
```

`top_p` is not set explicitly. It is generally easier to interpret an experiment when changing either `temperature` or `top_p`, rather than both at once.

## Number of API Calls

| Stage | API calls |
|---|---:|
| Response at `temperature=0` | 1 |
| Response at `temperature=0.7` | 1 |
| Response at `temperature=1.2` | 1 |
| Final comparison | 1 |
| **Total** | **4** |

## Setup and Run

Complete the shared [project setup](../README.md#project-setup), add `GROQ_API_KEY` to the root `.env` file, and run:

```bash
python day-04-temperature/main.py
```

The program prints the original prompt, three responses, and the final comparison.

## Day 4 Takeaway

- `temperature=0` is useful when stability, rule-following, and minimal randomness are important.
- `temperature=0.7` is a flexible default for many conversational and writing tasks.
- `temperature=1.2` helps explore unusual ideas when the result can be reviewed and filtered.

For high-stakes tasks, a low temperature is not enough by itself. Outputs still require rules, tests, reliable sources, or human review.

## Useful Links

- [Groq API Reference](https://console.groq.com/docs/api-reference)
- [Groq: Text Generation](https://console.groq.com/docs/text-chat)
