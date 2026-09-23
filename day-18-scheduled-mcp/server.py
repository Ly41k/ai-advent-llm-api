"""MCP tools for scheduling GitHub observations and reading summaries."""

from mcp.server.fastmcp import FastMCP
from scheduler import Scheduler

mcp = FastMCP("Bublik Day 18 Scheduler")
scheduler = Scheduler()


@mcp.tool()
def schedule_github_summary(owner: str, repo: str, interval_minutes: int = 60) -> dict:
    """Schedule recurring GitHub repository snapshots; first snapshot is due immediately.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        interval_minutes: Period in minutes, from 1 to 10080.
    """
    return scheduler.schedule(owner, repo, interval_minutes)


@mcp.tool()
def get_github_summary(owner: str, repo: str, limit: int = 20) -> dict:
    """Return saved observations and change since the oldest selected observation.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        limit: Number of recent snapshots to aggregate, from 1 to 100.
    """
    return scheduler.summary(owner, repo, limit)


@mcp.tool()
def list_scheduled_jobs() -> list[dict]:
    """List persisted schedules, including next execution and latest error."""
    return scheduler.jobs()


if __name__ == "__main__":
    mcp.run(transport="stdio")
