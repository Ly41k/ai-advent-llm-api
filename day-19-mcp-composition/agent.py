"""Bublik's explicit, automatic composition of three MCP calls."""

import json
from dataclasses import dataclass
from typing import Any

from github_api import validate_name


@dataclass(frozen=True)
class Step:
    tool: str
    input: dict
    output: dict


@dataclass(frozen=True)
class PipelineResult:
    report: dict
    steps: tuple[Step, ...]


class BublikPipelineAgent:
    def __init__(self, session: Any) -> None:
        self._session = session

    async def run(self, owner: str, repo: str) -> PipelineResult:
        """Stop at the first failure; never save a partial or fabricated summary."""
        args = {"owner": validate_name(owner, "owner"), "repo": validate_name(repo, "repo")}
        available = {tool.name for tool in (await self._session.list_tools()).tools}
        required = {"search_repository", "summarize_repository", "save_report"}
        if not required <= available:
            raise RuntimeError(f"Missing MCP tools: {sorted(required - available)}")

        steps: list[Step] = []
        for tool, arguments in (
            ("search_repository", args),
            ("summarize_repository", None),
            ("save_report", None),
        ):
            if arguments is None:
                arguments = {"repository" if tool == "summarize_repository" else "summary": steps[-1].output}
            response = await self._session.call_tool(tool, arguments=arguments)
            if response.isError:
                details = " ".join(item.text for item in response.content if hasattr(item, "text"))
                raise RuntimeError(f"{tool} failed: {details}")
            # FastMCP's tool return value is JSON text; decode it at every boundary.
            parts = [item.text for item in response.content if hasattr(item, "text")]
            if len(parts) != 1:
                raise RuntimeError(f"{tool} returned an unexpected MCP result")
            output = json.loads(parts[0])
            if not isinstance(output, dict):
                raise RuntimeError(f"{tool} did not return a JSON object")
            steps.append(Step(tool, arguments, output))

        if steps[0].output["full_name"] != steps[1].output["full_name"] or steps[1].output["full_name"] != steps[2].output["full_name"]:
            raise RuntimeError("Repository identity changed between tools")
        return PipelineResult(steps[-1].output, tuple(steps))
