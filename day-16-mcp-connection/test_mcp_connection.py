"""Smoke test for the Day 16 MCP connection."""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXPECTED_TOOLS = {"ping", "add"}


async def check() -> None:
    server_path = Path(__file__).with_name("server.py")
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            initialization = await session.initialize()
            assert initialization.serverInfo is not None

            result = await session.list_tools()
            tool_names = {tool.name for tool in result.tools}

            assert EXPECTED_TOOLS.issubset(tool_names), (
                f"Expected {EXPECTED_TOOLS}, got {tool_names}"
            )


if __name__ == "__main__":
    asyncio.run(check())
    print("OK: MCP connection works and tools are returned correctly.")
