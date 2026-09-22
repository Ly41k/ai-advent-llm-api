"""Reusable stdio connection for the local Day 17 MCP server."""

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@asynccontextmanager
async def connect_github_mcp(
    server_path: Path | None = None,
) -> AsyncIterator[ClientSession]:
    """Start the local MCP server and yield an initialized client session."""
    selected_path = server_path or Path(__file__).with_name("server.py")
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(selected_path)],
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session
