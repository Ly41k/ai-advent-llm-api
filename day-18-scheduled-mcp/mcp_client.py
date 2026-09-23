"""Connect to the Day 18 MCP server over stdio."""
import sys
import os
from contextlib import asynccontextmanager
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@asynccontextmanager
async def connect_mcp():
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(Path(__file__).with_name("server.py"))],
                                   env={key: os.environ[key] for key in
                                        ("BUBLIK_DB_PATH", "GITHUB_TOKEN", "GITHUB_API_BASE_URL")
                                        if key in os.environ})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
