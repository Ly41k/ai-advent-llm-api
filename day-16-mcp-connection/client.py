"""Day 16: connect to a local MCP server and print its available tools."""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    server_path = Path(__file__).with_name("server.py")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
    )

    print("Connecting to MCP server...")

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            initialization = await session.initialize()

            print("MCP connection established.")
            print(
                "Server:",
                initialization.serverInfo.name,
                initialization.serverInfo.version,
            )

            tools_result = await session.list_tools()

            print(f"Available tools ({len(tools_result.tools)}):")
            for tool in tools_result.tools:
                print(f"- {tool.name}: {tool.description or 'No description'}")


if __name__ == "__main__":
    asyncio.run(main())
