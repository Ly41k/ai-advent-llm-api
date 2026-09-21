**English** | [Русский](README.ru.md)

# AI Advent — From the First LLM Request to a Stateful Agent

A hands-on project for learning how to work with LLM APIs. Each day adds one new mechanism: response control, model comparison, persistent history, token accounting, context compression and strategies, explicit memory layers, personalization, formal task state, non-overridable invariants, a controlled task lifecycle, and MCP connectivity.

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
| [Day 15](day-15-controlled-transitions) | Controlled state transitions | Guard-aware transitions, explicit plan approval, lifecycle validation, and safe pause/resume |
| [Day 16](day-16-mcp-connection) | MCP connection | Local MCP server, stdio client connection, initialization, and tool discovery |

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
    ↓
guard-aware lifecycle + explicit plan approval
    ↓
MCP connection + tool discovery
```

Day 16 is intentionally a standalone MCP experiment. It does not yet integrate MCP into `BublikAgent`: the goal is to verify the protocol lifecycle first.

## Technologies

- Python 3.13;
- [Groq API](https://console.groq.com/);
- GPT-OSS 20B and 120B;
- Qwen 3.6 27B;
- SQLite;
- `groq`;
- `python-dotenv`;
- `tiktoken` with the `o200k_harmony` encoding;
- Python MCP SDK;
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
├── day-15-controlled-transitions/
├── day-16-mcp-connection/
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

Day 16 has its own MCP dependency:

```bash
python3 -m pip install -r day-16-mcp-connection/requirements.txt
```

### 4. Add the API key

Create a root-level `.env` based on `.env.example`:

```env
GROQ_API_KEY=your_api_key_here
```

Create a key in the [Groq Console](https://console.groq.com/keys). `.env` is ignored by Git; never publish the key in the repository, logs, or screenshots.

The Day 16 local MCP example does not require a Groq API key.

## Running the Assignments

Run all commands from the repository root.

| Day | Main program | Experiment / verification |
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
| 15 | `python3 day-15-controlled-transitions/main.py` | `python3 day-15-controlled-transitions/experiment.py` |
| 16 | `python3 day-16-mcp-connection/client.py` | `python3 day-16-mcp-connection/test_mcp_connection.py` |

Interactive programs support `выход` or `/exit`. See each day's README for the exact command set.

## Local Tests

The tests do not call the Groq API or consume tokens.

```bash
python3 -m unittest discover -s day-10-context-strategies -p "test_*.py" -v
python3 -m unittest discover -s day-11-memory-layers -p "test_*.py" -v
python3 -m unittest discover -s day-12-personalization -p "test_*.py" -v
python3 -m unittest discover -s day-13-task-state-machine -p "test_*.py" -v
python3 -m unittest discover -s day-14-invariants -p "test_*.py" -v
python3 -m unittest discover -s day-15-controlled-transitions -p "test_*.py" -v
python3 day-16-mcp-connection/test_mcp_connection.py
```

Days 10–15 verify the agent architecture, memory, profiles, state machine, invariants, and guarded lifecycle. Day 16 uses a standalone smoke test to verify that the MCP session initializes and that the expected tools are returned.

## Current Agent Capabilities

By Day 15, Bublik can manage independent dialogues, explicit memory layers, personalization, formal task state, invariants, semantic guards, and controlled task transitions.

Day 16 deliberately keeps MCP separate from Bublik. The new experiment proves that an MCP client can:

- start a local MCP server through `stdio`;
- establish a `ClientSession`;
- complete `session.initialize()`;
- request tools with `session.list_tools()`;
- receive and print the server's available tools.

This separation keeps the assignment focused on MCP connectivity before tool execution or agent integration is introduced.

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

## Day 13 Task State Machine

The task context formally contains its stage, current step, derived expected action, and pause flag. SQLite restores all source fields after restart, and invalid transitions or progress while paused are rejected by code.

## Day 14 Invariants and State Constraints

Day 14 adds a separate, versioned invariant policy. Local and semantic preflight/postflight checks prevent requests and generated responses from violating formalized architecture, stack, business, and security constraints.

## Day 15 Controlled State Transitions

Day 15 turns the task lifecycle into an explicit contract. A plan must be explicitly approved before execution, validation requires completed execution steps, and `done` requires successful validation. Pause/resume preserves the exact task position.

## Day 16 MCP Connection

Day 16 introduces the **Model Context Protocol (MCP)** with the smallest useful local example.

`server.py` exposes two tools:

- `ping` — returns a message;
- `add` — adds two integers.

`client.py` starts the server through the `stdio` transport and establishes an MCP session:

```text
MCP client
    ↓
stdio transport
    ↓
local MCP server
    ↓
initialize()
    ↓
list_tools()
    ↓
ping + add
```

The client performs the MCP initialization handshake with `session.initialize()` and then requests the server capabilities with `session.list_tools()`. Every returned tool is printed to the console.

Run:

```bash
python3 -m pip install -r day-16-mcp-connection/requirements.txt
python3 day-16-mcp-connection/client.py
```

Verify:

```bash
python3 day-16-mcp-connection/test_mcp_connection.py
```

The smoke test checks both requirements of the assignment: the MCP connection initializes successfully and the returned tool list contains the expected `ping` and `add` tools.

No VPS, Groq request, API key, or external MCP service is required for this local experiment.

## Experiment Limitations

- Model availability and TPM/TPD limits depend on the current Groq plan.
- Generated answers may vary between runs even with identical parameters.
- Local token estimates can differ slightly from actual API usage.
- Semantic invariant classification depends on the guard model and is handled fail-closed when it cannot be verified.
- Day 16 validates local MCP connectivity and tool discovery only; MCP tool execution and integration into `BublikAgent` are outside this assignment.

## Project Goal

This repository demonstrates a continuous evolution of an LLM application rather than a collection of isolated API snippets. Each new mechanism can be run, measured, compared with the previous approach, and tested independently.

## Useful Links

- [Groq Console](https://console.groq.com/)
- [Groq Documentation](https://console.groq.com/docs)
- [GPT-OSS Documentation](https://console.groq.com/docs/model/openai/gpt-oss-20b)
- [tiktoken](https://github.com/openai/tiktoken)
- [Model Context Protocol](https://modelcontextprotocol.io/)
