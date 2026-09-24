"""One command runs all three MCP tools in sequence."""

import argparse
import asyncio

from agent import BublikPipelineAgent
from mcp_client import connect_mcp


async def run(owner: str, repo: str) -> None:
    async with connect_mcp() as session:
        result = await BublikPipelineAgent(session).run(owner, repo)
    for step in result.steps:
        print(f"[MCP] {step.tool}: {step.output}")
    print(f"Saved report: {result.report['path']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Bublik's three-tool MCP pipeline")
    parser.add_argument("owner", help="GitHub repository owner")
    parser.add_argument("repo", help="GitHub repository name")
    arguments = parser.parse_args()
    asyncio.run(run(arguments.owner, arguments.repo))
