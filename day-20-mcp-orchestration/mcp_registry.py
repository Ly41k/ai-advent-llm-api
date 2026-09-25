"""Connect three independent stdio servers and expose one namespaced catalog."""

import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVERS = {
    "github": "github_server.py",
    "analysis": "analysis_server.py",
    "storage": "storage_server.py",
}


class ToolRegistry:
    def __init__(self, sessions: dict[str, ClientSession]):
        self.sessions = sessions
        self.routes: dict[str, tuple[str, str]] = {}
        self.schemas: list[dict] = []

    async def discover(self) -> list[dict]:
        self.routes.clear()
        self.schemas.clear()
        for alias, session in self.sessions.items():
            for tool in (await session.list_tools()).tools:
                public_name = f"{alias}__{tool.name}"
                if public_name in self.routes:
                    raise RuntimeError(f"Duplicate MCP tool: {public_name}")
                self.routes[public_name] = (alias, tool.name)
                self.schemas.append({"type": "function", "function": {
                    "name": public_name,
                    "description": f"Server {alias}: {tool.description or ''}",
                    "parameters": tool.inputSchema,
                }})
        return self.schemas

    async def call(self, public_name: str, arguments: dict) -> dict:
        if public_name not in self.routes:
            raise ValueError(f"Unknown MCP tool: {public_name}")
        alias, actual_name = self.routes[public_name]
        result = await self.sessions[alias].call_tool(actual_name, arguments=arguments)
        parts = [item.text for item in result.content if getattr(item, "type", None) == "text"]
        if result.isError:
            raise RuntimeError(f"{public_name} failed: {' '.join(parts)}")
        if result.structuredContent and isinstance(result.structuredContent, dict):
            # MCP SDKs can wrap a FastMCP return under `result` in structured content.
            value = result.structuredContent
            if set(value) == {"result"}:
                value = value["result"]
        else:
            import json
            if len(parts) != 1:
                raise RuntimeError(f"Unexpected response from {public_name}")
            value = json.loads(parts[0])
        if not isinstance(value, dict):
            raise RuntimeError(f"Expected JSON object from {public_name}")
        return value


@asynccontextmanager
async def connect_servers():
    async with AsyncExitStack() as stack:
        sessions = {}
        for alias, filename in SERVERS.items():
            params = StdioServerParameters(command=sys.executable,
                                           args=[str(Path(__file__).with_name(filename))],
                                           env=os.environ.copy())
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            sessions[alias] = session
        registry = ToolRegistry(sessions)
        await registry.discover()
        yield registry
