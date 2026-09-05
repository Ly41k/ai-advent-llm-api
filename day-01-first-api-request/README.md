**English** | [Русский](README.ru.md)

# Day 1 — First LLM API Request

The first AI Advent assignment introduces large language models through a direct API call.

## Assignment

Write a minimal program that:

- sends a request to an LLM through an API;
- receives the model response;
- displays it in a console or a simple interface.

## Result

The result is a CLI chatbot that calls `openai/gpt-oss-20b` through the Groq API, prints responses, and preserves the current conversation history.

## Implemented Features

- loading an API key from an environment variable;
- connecting to the Groq API;
- sending messages to a language model;
- using the `system`, `user`, and `assistant` roles;
- configuring a character through the system prompt;
- preserving history while the program is running;
- ignoring empty user input;
- handling API errors;
- exiting with the `выход` command.

## Characters

The model acts as **Bublik**, the onboard assistant of a spaceship.

The user is **Cheburator**, a space traveler looking for adventures across the galaxy. Bublik responds in Russian.

## How It Works

### System prompt

The conversation starts with a `system` message:

```python
messages = [
    {
        "role": "system",
        "content": (
            "Ты бортовой помощник космического корабля по имени Бублик. "
            "Пользователя зовут Чебуратор. "
            "Он космический путешественник, который ищет "
            "приключения в галактике. "
            "Отвечай ему на русском языке."
        ),
    }
]
```

The system prompt defines the model's role, conversation context, and response language.

### Conversation history

Before every request, the user message is appended with the `user` role:

```python
messages.append(
    {
        "role": "user",
        "content": user_input,
    }
)
```

After a successful request, the model response is appended with the `assistant` role:

```python
messages.append(
    {
        "role": "assistant",
        "content": bot_response,
    }
)
```

The resulting sequence is:

```text
system → user → assistant → user → assistant
```

The model receives the complete accumulated conversation with every request. History exists only in memory and is discarded when the program stops.

### Model request

```python
response = client.chat.completions.create(
    model="openai/gpt-oss-20b",
    messages=messages,
    temperature=0.8,
    reasoning_effort="medium",
)
```

Parameters:

- `model` selects the language model;
- `messages` contains the system prompt and conversation history;
- `temperature` controls response variability;
- `reasoning_effort` controls the amount of computation used for reasoning.

### Error handling

The program stops with a clear message if `GROQ_API_KEY` is missing.

API calls are wrapped in `try/except`. If a request fails, the unmatched user message is removed from history:

```python
except Exception as error:
    messages.pop()
    print(f"Ошибка при обращении к LLM: {error}\n")
```

This prevents a failed request without an assistant response from remaining in the conversation.

## Setup

Complete the shared [project setup](../README.md#project-setup) and add `GROQ_API_KEY` to the root `.env` file.

## Run

From the repository root:

```bash
python day-01-first-api-request/main.py
```

The program displays:

```text
🤖 Чат-бот на Groq
Введите «выход» для завершения.

Вы:
```

Example:

```text
Вы: Как тебя зовут?
Бот: Меня зовут Бублик. Я твой бортовой помощник, Чебуратор!

Вы: Куда мы отправимся сегодня?
Бот: Предлагаю исследовать неизвестную планету!
```

Enter `выход` to stop the program.

## Day 1 Takeaway

The first complete LLM API integration is working. The program reads user input, sends the conversation history to the model, receives a response, and prints it to the console.

Next: [controlling response format and length](../day-02-response-control).
