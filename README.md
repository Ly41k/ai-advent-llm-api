**English** | [Русский](README.ru.md)

# AI Advent — Working with LLM APIs

A learning repository containing practical assignments from the AI Advent challenge.

The project explores LLM APIs step by step: from the first request and conversation history to response control, reasoning strategies, temperature, model comparison, and a standalone agent with persistent memory.

The examples share one continuing story. **Cheburator** is the captain of a research spacecraft on a long expedition to distant galaxies, while **Bublik** evolves from a simple onboard assistant into an autonomous onboard computer.

## Completed Assignments

| Day | Topic | Result |
|---|---|---|
| [Day 1](day-01-first-api-request) | First LLM API request | A CLI chatbot with conversation history |
| [Day 2](day-02-response-control) | Response control | The same request with and without explicit constraints |
| [Day 3](day-03-reasoning-methods) | Reasoning strategies | Four approaches to one problem with automated comparison |
| [Day 4](day-04-temperature) | Temperature | Accuracy, creativity, and diversity at three temperatures |
| [Day 5](day-05-model-versions) | Model versions | Quality, latency, token usage, and cost across three models |
| [Day 6](day-06-first-agent) | First agent | A standalone onboard agent with policies and persistent SQLite memory |

## Technologies

- Python;
- [Groq API](https://console.groq.com/);
- GPT-OSS 20B and 120B;
- Qwen 3.6 27B;
- Groq Python SDK;
- `python-dotenv`;
- SQLite from the Python standard library.

## Repository Structure

```text
ai-advent-llm-api/
├── day-01-first-api-request/
│   ├── main.py
│   ├── README.md
│   └── README.ru.md
├── day-02-response-control/
│   ├── main.py
│   ├── README.md
│   └── README.ru.md
├── day-03-reasoning-methods/
│   ├── main.py
│   ├── README.md
│   └── README.ru.md
├── day-04-temperature/
│   ├── main.py
│   ├── README.md
│   └── README.ru.md
├── day-05-model-versions/
│   ├── main.py
│   ├── README.md
│   └── README.ru.md
├── day-06-first-agent/
│   ├── agent.py
│   ├── main.py
│   ├── memory.py
│   ├── README.md
│   └── README.ru.md
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── README.ru.md
```

Each directory contains an independent practical assignment, a runnable example, and documentation in English and Russian.

## Project Setup

### 1. Clone the repository

```bash
git clone https://github.com/Ly41k/ai-advent-llm-api.git
cd ai-advent-llm-api
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add the API key

Create a key in the [Groq Console](https://console.groq.com/keys).

Create a `.env` file in the project root using `.env.example` as a template:

```env
GROQ_API_KEY=your_api_key_here
```

The `.env` file is excluded by `.gitignore`. Never publish or share your API key.

## Running the Assignments

Run all commands from the repository root.

Day 1:

```bash
python day-01-first-api-request/main.py
```

Day 2:

```bash
python day-02-response-control/main.py
```

Day 3:

```bash
python day-03-reasoning-methods/main.py
```

Day 4:

```bash
python day-04-temperature/main.py
```

Day 5:

```bash
python day-05-model-versions/main.py
```

Day 6:

```bash
python day-06-first-agent/main.py
```

Days 1, 2, and 6 are interactive. Enter `выход` to stop them. Day 6 also supports `/exit` and `/history`.

Days 3, 4, and 5 use predefined prompts and exit automatically after producing their results.

## What I Learned

### Day 1 — First Request

- creating a Groq client;
- using the `system`, `user`, and `assistant` roles;
- sending a request and reading the response;
- preserving conversation history;
- handling API errors.

### Day 2 — Response Control

- controlling response structure through a prompt;
- semantic and technical length limits;
- using `max_completion_tokens`;
- defining an explicit completion condition;
- comparing the same request with different levels of control.

### Day 3 — Reasoning Strategies

- direct prompting;
- step-by-step instructions;
- asking the model to generate a prompt;
- simulating a group of experts;
- automated evaluation against a known answer;
- handling token-per-minute limits.

### Day 4 — Temperature

- how `temperature` affects generation;
- comparing `0`, `0.7`, and `1.2`;
- evaluating accuracy, creativity, and diversity;
- choosing a temperature for different tasks;
- automated comparison of the responses.

### Day 5 — Model Versions

- running the same prompt on models of different sizes;
- comparing GPT-OSS 20B, Qwen 3.6 27B, and GPT-OSS 120B;
- configuring model-specific reasoning modes;
- measuring end-to-end latency with `perf_counter()`;
- reading token usage from `response.usage`;
- estimating cost from public Groq pricing;
- anonymizing responses for quality evaluation;
- understanding the limits of cloud-based resource measurements.

See the [Day 5 README](day-05-model-versions/README.md) for the complete experiment.

### Day 6 — First Agent

- separating the user interface from agent logic;
- encapsulating the complete request-response workflow in `BublikAgent`;
- applying deterministic input and output policies;
- storing conversations and messages in SQLite;
- preserving history between program runs;
- tracking `pending`, `completed`, and `failed` requests;
- excluding failed requests from future LLM context;
- loading only the latest completed messages into the prompt;
- keeping the agent reusable for a future REST or web interface.

See the [Day 6 README](day-06-first-agent/README.md) for the architecture, persistence test, and implementation details.

The source code contains detailed Russian comments that explain the main steps of each program. User prompts and console output are also in Russian because they are part of the experiments.

## Groq API Limits

Available requests and tokens depend on the account tier and model.

Days 3 and 4 wait for 60 seconds and retry once after a supported rate-limit error.

Day 5 does not retry automatically because waiting would distort latency measurements. Its main requests use `max_completion_tokens=900`. If Qwen returns `429 rate_limit_exceeded`, wait for the rolling minute window to reset and run the complete experiment again.

Reasoning models spend part of the output budget on internal reasoning. Day 5 therefore uses the lowest supported modes: `low` for GPT-OSS and `none` for Qwen.

Day 6 uses `max_completion_tokens=1200` and sends only the latest 20 completed conversation messages. The full mission history remains in SQLite, while failed requests are retained for diagnostics and excluded from the LLM context.

## Interpreting the Results

Responses and latency can vary between runs. A single experiment demonstrates model behavior under specific conditions; it is not a universal ranking.

For a more reliable comparison:

- run every model multiple times;
- use tasks from different categories;
- compare median latency;
- define evaluation criteria in advance;
- verify actual pricing for the account tier in use.

## Project Goal

The goal is to understand, through small runnable examples, how prompts, API parameters, model selection, architecture, and memory affect an LLM-powered application.

The first five days examine individual mechanisms. Day 6 begins combining them into a reusable agent that can later be extended with layered memory, topic branches, vector search, self-reflection, a judge, multiple model providers, and a REST interface.

## Useful Links

- [Groq: Text Generation](https://console.groq.com/docs/text-chat)
- [Groq: Prompting](https://console.groq.com/docs/prompting)
- [Groq: Reasoning](https://console.groq.com/docs/reasoning)
- [Groq: Supported Models and Pricing](https://console.groq.com/docs/models)
- [Groq: Rate Limits](https://console.groq.com/docs/rate-limits)
- [Groq API Reference](https://console.groq.com/docs/api-reference)
