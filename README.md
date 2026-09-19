**English** | [Русский](README.ru.md)

# AI Advent — From the First LLM Request to a Stateful Agent

A hands-on project for learning how to work with LLM APIs. Each day adds one new mechanism: response control, model comparison, persistent history, token accounting, context compression and strategies, explicit memory layers, personalization, formal task state, and non-overridable invariants.

All assignments share one story. **Cheburator** is the captain of a research spacecraft, while **Bublik** gradually evolves from a simple console assistant into a personalized autonomous agent.

## Completed Assignments

| Day | Topic | Result |
|---|---|---|
| [Day 1](day-01-first-api-request) | First API request | A console chat with in-session history |
| [Day 2](day-02-response-control) | Response control | Explicit response structure, length, and rules |
| [Day 3](day-03-reasoning-methods) | Reasoning methods | Four approaches compared on the same task |
| [Day 4](day-04-temperature) | Temperature | Accuracy, creativity, and variability comparison |
| [Day 5](day-05-model-versions) | Model versions | Quality, latency, token, and cost comparison |
| [Day 6](day-06-first-agent) | First agent | `BublikAgent`, thin CLI, and persistent SQLite memory |
| [Day 7](day-07-context-persistence) | Context persistence | Independent dialogues restored after restart |
| [Day 8](day-08-token-usage) | Token usage | Local estimates, actual usage, and request cost |
| [Day 9](day-09-context-compression) | Context compression | Persistent summary plus recent verbatim messages |
| [Day 10](day-10-context-strategies) | Context strategies | Sliding Window, Sticky Facts, and Branching |
| [Day 11](day-11-memory-layers) | Memory model | Short-term, working, and long-term memory |
| [Day 12](day-12-personalization) | Personalization | Profiles with style, format, and constraints in every request |
| [Day 13](day-13-task-state-machine) | Task State Machine | Persistent stage, current step, expected action, pause, and resume |
| [Day 14](day-14-invariants) | Invariants and state constraints | Separate policy, semantic preflight/postflight checks, and explainable refusals |

## Architecture Evolution

```text
simple API call
    ↓
controlled prompt and model parameters
    ↓
BublikAgent + thin CLI
    ↓
SQLite + independent dialogues
    ↓
context measurement and compression
    ↓
context strategies
    ↓
explicit memory layers + state machine
    ↓
personalization for every request
    ↓
formal task state + pause/resume
    ↓
invariant policy + semantic guard
```

In the latest assignments, the main flow is:

```text
CLI
  → BublikAgent
    → user profile
    → long-term memory
    → working memory
    → recent short-term messages
    → local invariant preflight
    → semantic request guard
    → Groq API
    → local + semantic response validation
    → deterministic refusal or accepted response
    → SQLite
```

## Technologies

- Python 3.13;
- [Groq API](https://console.groq.com/);
- GPT-OSS 20B and 120B;
- Qwen 3.6 27B;
- SQLite;
- `groq`;
- `python-dotenv`;
- `tiktoken` with the `o200k_harmony` encoding;
- standard-library `unittest`.

## Repository Structure

```text
ai-advent-llm-api/
├── day-01-first-api-request/
├── day-02-response-control/
├── day-03-reasoning-methods/
├── day-04-temperature/
├── day-05-model-versions/
├── day-06-first-agent/
├── day-07-context-persistence/
├── day-08-token-usage/
├── day-09-context-compression/
├── day-10-context-strategies/
├── day-11-memory-layers/
├── day-12-personalization/
├── day-13-task-state-machine/
├── day-14-invariants/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── README.ru.md
```

Each directory is a standalone example with its own English and Russian documentation.

## Project Setup

### 1. Clone the repository

```bash
git clone https://github.com/Ly41k/ai-advent-llm-api.git
cd ai-advent-llm-api
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Windows:

```text
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

### 4. Add the API key

Create a root-level `.env` based on `.env.example`:

```env
GROQ_API_KEY=your_api_key_here
```

Create a key in the [Groq Console](https://console.groq.com/keys). `.env` is ignored by Git; never publish the key in the repository, logs, or screenshots.

## Running the Assignments

Run all commands from the repository root.

| Day | Main program | Experiment |
|---|---|---|
| 1 | `python3 day-01-first-api-request/main.py` | — |
| 2 | `python3 day-02-response-control/main.py` | — |
| 3 | `python3 day-03-reasoning-methods/main.py` | — |
| 4 | `python3 day-04-temperature/main.py` | — |
| 5 | `python3 day-05-model-versions/main.py` | — |
| 6 | `python3 day-06-first-agent/main.py` | — |
| 7 | `python3 day-07-context-persistence/main.py` | — |
| 8 | `python3 day-08-token-usage/main.py` | `python3 day-08-token-usage/experiment.py` |
| 9 | `python3 day-09-context-compression/main.py` | `python3 day-09-context-compression/experiment.py` |
| 10 | `python3 day-10-context-strategies/main.py` | `python3 day-10-context-strategies/experiment.py` |
| 11 | `python3 day-11-memory-layers/main.py` | `python3 day-11-memory-layers/experiment.py` |
| 12 | `python3 day-12-personalization/main.py` | `python3 day-12-personalization/experiment.py` |
| 13 | `python3 day-13-task-state-machine/main.py` | `python3 day-13-task-state-machine/experiment.py` |
| 14 | `python3 day-14-invariants/main.py` | `python3 day-14-invariants/experiment.py` |

Interactive programs support `выход` or `/exit`. See each day's README for the exact command set.

## Local Tests

The tests do not call the Groq API or consume tokens.

```bash
python3 -m unittest discover -s day-10-context-strategies -p "test_*.py" -v
python3 -m unittest discover -s day-11-memory-layers -p "test_*.py" -v
python3 -m unittest discover -s day-12-personalization -p "test_*.py" -v
python3 -m unittest discover -s day-13-task-state-machine -p "test_*.py" -v
python3 -m unittest discover -s day-14-invariants -p "test_*.py" -v
```

They verify:

- Sliding Window size, facts injection, and branch isolation;
- separation of short-term, working, and long-term memory;
- valid state-machine transitions;
- complete prompt construction;
- profile injection into every request;
- differences between profiles;
- profile restoration and user-specific long-term memory isolation.
- task pause/resume and exact restoration after restart.
- invariant policy categories and separate storage;
- semantic request/response checks, explainable refusals, and unsafe-response exclusion from history.

## Current Agent Capabilities

By Day 14, Bublik can:

- manage multiple independent dialogues;
- restore history after restart;
- keep recent messages separate from task state;
- explicitly store decisions and knowledge;
- control tasks through `planning → execution → validation → done`;
- derive the next expected action from formal task state;
- pause and resume any unfinished stage without losing progress;
- apply user language, detail level, style, format, and constraints;
- isolate long-term memory between profiles;
- display the exact context before sending it to the model;
- reject responses that violate formalized invariants.
- load a versioned invariant policy outside the dialogue database;
- block explicit conflicts locally before generation;
- detect paraphrased conflicts with a structured semantic guard;
- validate generated responses against all invariants;
- replace violating responses with deterministic, explainable refusals;
- keep unsafe model output out of SQLite history.

Main commands:

| Command | Purpose |
|---|---|
| `/dialogs` | Switch or create a dialogue |
| `/history` | Show the full completed history |
| `/context` | Show the prompt that will be sent to the model |
| `/invariants` | Show the active invariant policy and rationales |
| `/memory short\|working\|long` | Show a selected memory layer |
| `/remember working KEY VALUE` | Save current-task data |
| `/remember long decision\|knowledge KEY VALUE` | Save a decision or knowledge item |
| `/task ...` | Control the current task state |
| `/profile` | Show the active profile |
| `/profile PROFILE_ID` | Change the profile of an empty dialogue |
| `/exit` | Exit the program |

Values containing spaces must be quoted.

## Day 12 Personalization

A user profile contains:

```text
name + role
language
detail_level
style
response_format
constraints
```

Before every request, `MemoryPromptBuilder` assembles context in a fixed order:

```text
assistant identity + invariants
user profile
profile-scoped long-term memory
dialogue-scoped working memory
last 6 completed short-term messages
current user request
```

The repository includes two contrasting profiles: concise `cheburator` and detailed scientific `scientist`. `experiment.py` sends them the same question with identical working memory, so response differences come from personalization.

## Day 13 Task State Machine

The task context now formally contains its stage, current step, derived expected action, and pause flag. SQLite restores all source fields after restart, and the prompt tells the model to continue from the stored position without asking the user to repeat the task. Invalid transitions and all progress while paused are rejected by code.

## Day 14 Invariants and State Constraints

Day 14 adds a separate, versioned policy in `day-14-invariants/config/invariants.json`. It formalizes stack, architecture, technical-decision, business-rule, and security constraints. Dialogue messages cannot override this policy.

The enforcement flow has three layers:

```text
user request
    ↓
local regex preflight
    ├── explicit conflict → deterministic refusal
    └── pass → semantic request guard
                   ├── conflict → deterministic refusal
                   └── pass → answer generation
                                  ↓
                         local + semantic postflight
                                  ├── violation → explained refusal
                                  └── pass → SQLite
```

The semantic guard returns a strict JSON result containing only allowed invariant IDs. A paraphrased conflict such as “TypeScript would be better than the current language” is refused even when it does not match a local regex. If a generated answer violates an architecture, stack, business, or security rule, it is discarded and replaced with an explainable refusal before persistence.

Run the application with:

```bash
python3 day-14-invariants/main.py
```

Run the local tests with:

```bash
python3 -m unittest discover -s day-14-invariants -p "test_*.py" -v
```

Compatible requests use semantic preflight, answer generation, and semantic postflight. Explicit regex conflicts are blocked locally without an API call.

## Experiment Limitations

- Model availability and TPM/TPD limits depend on the current Groq plan.
- Generated answers may vary between runs even with identical parameters.
- Local token estimates can differ slightly from actual API usage.
- Summary and Sticky Facts depend on model quality and can omit an important detail.
- Semantic invariant classification depends on the guard model; malformed or unknown guard output is handled fail-closed.
- A compatible Day 14 request may use three API calls: semantic preflight, answer generation, and semantic postflight.
- Automated tests validate architecture and prompt composition; real response quality is evaluated through experiments.

## Project Goal

This repository demonstrates a continuous evolution of an LLM application rather than a collection of isolated API snippets. Each new mechanism can be run, measured, compared with the previous approach, and tested independently.

## Useful Links

- [Groq Console](https://console.groq.com/)
- [Groq Documentation](https://console.groq.com/docs)
- [GPT-OSS Documentation](https://console.groq.com/docs/model/openai/gpt-oss-20b)
- [tiktoken](https://github.com/openai/tiktoken)
