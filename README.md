**English** | [Русский](README.ru.md)

# AI Advent — Working with LLM APIs

A learning repository containing practical assignments from the AI Advent challenge.

The project explores LLM APIs step by step: from the first request and conversation history to response control, reasoning strategies, temperature, and comparisons between models of different sizes.

## Completed Assignments

| Day | Topic | Result |
|---|---|---|
| [Day 1](day-01-first-api-request) | First LLM API request | A CLI chatbot with conversation history |
| [Day 2](day-02-response-control) | Response control | The same request with and without explicit constraints |
| [Day 3](day-03-reasoning-methods) | Reasoning strategies | Four approaches to one problem with automated comparison |
| [Day 4](day-04-temperature) | Temperature | Accuracy, creativity, and diversity at three temperatures |
| [Day 5](day-05-model-versions) | Model versions | Quality, latency, token usage, and cost across three models |

## Technologies

- Python;
- [Groq API](https://console.groq.com/);
- GPT-OSS 20B and 120B;
- Qwen 3.6 27B;
- Groq Python SDK;
- `python-dotenv`.

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

Days 1 and 2 are interactive. Enter `выход` to stop them.

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

The source code contains detailed Russian comments that explain the main steps of each program. User prompts and console output are also in Russian because they are part of the experiments.

## Groq API Limits

Available requests and tokens depend on the account tier and model.

Days 3 and 4 wait for 60 seconds and retry once after a supported rate-limit error.

Day 5 does not retry automatically because waiting would distort latency measurements. Its main requests use `max_completion_tokens=900`. If Qwen returns `429 rate_limit_exceeded`, wait for the rolling minute window to reset and run the complete experiment again.

Reasoning models spend part of the output budget on internal reasoning. Day 5 therefore uses the lowest supported modes: `low` for GPT-OSS and `none` for Qwen.

## Interpreting the Results

Responses and latency can vary between runs. A single experiment demonstrates model behavior under specific conditions; it is not a universal ranking.

For a more reliable comparison:

- run every model multiple times;
- use tasks from different categories;
- compare median latency;
- define evaluation criteria in advance;
- verify actual pricing for the account tier in use.

## Project Goal

The goal is to understand, through small runnable examples, how prompts, API parameters, and model selection affect generation quality, latency, and cost.

## Useful Links

- [Groq: Text Generation](https://console.groq.com/docs/text-chat)
- [Groq: Prompting](https://console.groq.com/docs/prompting)
- [Groq: Reasoning](https://console.groq.com/docs/reasoning)
- [Groq: Supported Models and Pricing](https://console.groq.com/docs/models)
- [Groq: Rate Limits](https://console.groq.com/docs/rate-limits)
- [Groq API Reference](https://console.groq.com/docs/api-reference)
