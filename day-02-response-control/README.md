**English** | [Русский](README.ru.md)

# Day 2 — Controlling LLM Response Format

The second AI Advent assignment explores how to control the structure, length, and completion of a language model response.

## Assignment

Send the same request twice:

1. Without additional constraints.
2. With an explicit format, length limit, and completion condition.

Then compare the responses.

## Result

The program sends one user request to `openai/gpt-oss-20b` twice and prints two separate results:

- a response without format control;
- a response with explicit rules.

## Implemented Features

- the same user request for both API calls;
- additional system instructions for the controlled response;
- an explicit output structure;
- a visible limit of 70 words;
- a technical `max_completion_tokens` limit;
- an instruction to stop after the third bullet point;
- side-by-side console output.

## Levels of Control

| Requirement | Implementation |
|---|---|
| Format | The `Краткий ответ:` heading followed by exactly three bullet points |
| Length | No more than 70 words and `max_completion_tokens=500` |
| Completion | An explicit instruction to stop after the third item |

### Format

The controlled request defines the exact expected structure:

```text
1. Начни со строки «Краткий ответ:».
2. Затем напиши ровно три пункта маркированного списка.
```

Without these instructions, the model chooses its own response structure.

### Length limit

The system prompt contains a semantic constraint:

```text
Используй не более 70 слов.
```

The API request also receives a technical generation limit:

```python
request_parameters["max_completion_tokens"] = 500
```

`max_completion_tokens` limits the full generation budget. The value includes room for internal reasoning, while the visible response length is controlled by the prompt.

### Completion condition

The assignment allows either a stop sequence or an explicit instruction. This implementation uses an instruction:

```text
4. Заверши ответ сразу после третьего пункта.
5. Не добавляй заключение или дополнительный текст.
```

The model is therefore asked to finish immediately after the third bullet point.

## Control Instructions

All rules are stored in one constant:

```python
CONTROL_INSTRUCTIONS = (
    "\n\nПравила ответа:\n"
    "1. Начни со строки «Краткий ответ:».\n"
    "2. Затем напиши ровно три пункта маркированного списка.\n"
    "3. Используй не более 70 слов.\n"
    "4. Заверши ответ сразу после третьего пункта.\n"
    "5. Не добавляй заключение или дополнительный текст."
)
```

The rules are appended to the base system prompt only for the controlled request:

```python
if with_limits:
    system_prompt += CONTROL_INSTRUCTIONS
```

## Comparing the Requests

Both calls use:

- the same model;
- the same user request;
- the same temperature;
- the same reasoning effort.

Only the control instructions and technical token limit differ:

```python
response_without_limits = get_response(
    user_input=user_input,
    with_limits=False,
)

response_with_limits = get_response(
    user_input=user_input,
    with_limits=True,
)
```

Conversation history is intentionally not preserved. Each request starts with clean context, so the first response cannot influence the second.

## Setup

Complete the shared [project setup](../README.md#project-setup) and add `GROQ_API_KEY` to the root `.env` file.

## Run

From the repository root:

```bash
python day-02-response-control/main.py
```

Enter a request, for example:

```text
Расскажи, как подготовиться к путешествию на Марс.
```

The program prints:

```text
==================================================
БЕЗ ОГРАНИЧЕНИЙ
==================================================
Развёрнутый ответ модели...

==================================================
С ОГРАНИЧЕНИЯМИ
==================================================
Краткий ответ: Подготовка к Марсу требует тщательного планирования.

- Проверь оборудование и запасы.
- Изучи маршрут и возможные риски.
- Пройди физическую и психологическую подготовку.
```

Enter `выход` to stop the program.

## Day 2 Takeaway

The same request can produce noticeably different results depending on the instructions. Structure, visible length, and the completion point can be controlled through the system prompt and API parameters.

## Useful Links

- [Groq: Text Generation](https://console.groq.com/docs/text-chat)
- [Groq API Reference](https://console.groq.com/docs/api-reference)
