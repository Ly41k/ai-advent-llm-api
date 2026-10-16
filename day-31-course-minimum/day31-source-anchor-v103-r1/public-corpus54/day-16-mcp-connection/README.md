# Day 16 — MCP Connection

Minimal standalone implementation for the course task.

## What it demonstrates

- installs/uses the official Python MCP SDK;
- starts a local MCP server over `stdio`;
- establishes an MCP client session;
- performs the MCP initialization handshake;
- requests the list of tools with `list_tools()`;
- prints the tools returned by the server.

No VPS, API key, Groq request, or external MCP service is required for this task.

## Files

- `server.py` — minimal local MCP server with `ping` and `add` tools.
- `client.py` — MCP client that connects and prints the available tools.
- `test_mcp_connection.py` — smoke test for connection + tool discovery.
- `requirements.txt` — isolated dependency for this lesson.

## Run

From the repository root:

```bash
cd day-16-mcp-connection
python3 -m pip install -r requirements.txt
python3 client.py
```

Expected shape of the output:

```text
Connecting to MCP server...
MCP connection established.
Server: Bublik Day 16 MCP Server ...
Available tools (2):
- ping: ...
- add: ...
```

## Verify

```bash
python3 test_mcp_connection.py
```

Successful result:

```text
OK: MCP connection works and tools are returned correctly.
```

## Course requirements mapping

1. **MCP SDK / client installed** — `mcp` is declared in `requirements.txt`.
2. **MCP connection established** — `stdio_client(...)`, `ClientSession(...)`,
   and `session.initialize()`.
3. **Available tools requested** — `await session.list_tools()`.
4. **Tool list printed** — `client.py` prints every returned tool.
5. **Connection and result verified** — `test_mcp_connection.py` asserts that
   the server initializes and returns both expected tools.
