"""GitHub data provider: MCP server one of three."""

from mcp.server.fastmcp import FastMCP
from github_api import get_repository

mcp = FastMCP("Bublik GitHub")


@mcp.tool()
def get_repository_info(owner: str, repo: str) -> dict:
    """Fetch public GitHub repository metadata before creating a report."""
    return get_repository(owner, repo)


if __name__ == "__main__":
    mcp.run(transport="stdio")
