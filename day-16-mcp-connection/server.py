"""Minimal local MCP server for Day 16."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Bublik Day 16 MCP Server")


@mcp.tool()
def ping(message: str = "Hello from Bublik") -> str:
    """Return a message to prove that the MCP server exposes a tool."""
    return f"Pong: {message}"


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


if __name__ == "__main__":
    mcp.run(transport="stdio")
