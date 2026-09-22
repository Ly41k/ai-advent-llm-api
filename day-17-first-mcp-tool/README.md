# Day 17 — First MCP Tool

An MCP server around GitHub REST API, connected to Bublik's LLM tool-calling
loop. The lesson continues the local `stdio` approach introduced on Day 16.

## Flow

1. `server.py` registers `get_github_repo` with `@mcp.tool()`.
2. Type annotations and the docstring publish the input JSON Schema and tool
   description through MCP.
3. The agent requests the MCP tool list and gives those schemas to the model.
4. The model requests `get_github_repo(owner, repo)`.
5. The agent calls the tool through `ClientSession.call_tool()`.
6. The MCP server requests repository data from GitHub REST API.
7. The result is returned to the model and used in its final answer.

The tool returns repository name, owner, description, stars, forks, open issue
count, default branch, and URL.

## Install and verify

```bash
cd day-17-first-mcp-tool
python3 -m pip install -r requirements.txt
python3 test_day17.py
```

The test checks the GitHub response mapping through a deterministic mock HTTP
transport and verifies the real MCP tool schema. It does not consume API quota.

## Run the end-to-end demo

```bash
python3 demo.py
```

The demo needs internet access but no Groq key. It sends a real request to the
public GitHub API and displays the user question, MCP call, raw tool result, and
Bublik's final answer. `GITHUB_TOKEN` is optional for public repositories.

## Run with Groq

```bash
cp .env.example .env
# Add GROQ_API_KEY to .env
python3 main.py
```

Example prompt: `Tell me about Ly41k/ai-advent-llm-api.`

## Course requirements

- tool registration: `@mcp.tool()` in `server.py`;
- input parameters: typed `owner` and `repo`, exposed as JSON Schema;
- returned result: normalized repository data from GitHub REST API;
- connected to the agent: MCP schemas are passed to the model in `agent.py`;
- called from the application: both `demo.py` and `main.py` execute the tool;
- result is used: the tool response is added as a `tool` message before the
  final model answer.

Everything runs locally over `stdio`. No VPS, open port, domain, Nginx, or SSL
certificate is required.
