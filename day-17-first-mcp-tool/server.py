"""MCP server exposing GitHub REST API as a typed tool."""

from mcp.server.fastmcp import FastMCP

from github_api import GitHubApi


mcp = FastMCP("Bublik Day 17 GitHub MCP Server")
github_api = GitHubApi()


@mcp.tool()
def get_github_repo(owner: str, repo: str) -> dict:
    """Get public information about a GitHub repository.

    Args:
        owner: GitHub user or organization name, for example ``Ly41k``.
        repo: Repository name, for example ``ai-advent-llm-api``.

    Returns:
        Repository name, owner, description, stars, forks, open issue count,
        default branch and GitHub URL.
    """
    return github_api.get_repository(owner, repo)


if __name__ == "__main__":
    mcp.run(transport="stdio")
