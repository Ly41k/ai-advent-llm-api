"""Model-directed orchestration with verified boundaries between servers."""

import json
from dataclasses import dataclass
from typing import Any

from github_api import validate_name
from mcp_registry import ToolRegistry

MODEL = "openai/gpt-oss-20b"
FLOW = ("github__get_repository_info", "analysis__summarize_repository",
        "storage__save_report", "storage__read_report", "analysis__verify_report")
FLOWS = {"info": FLOW[:1], "summary": FLOW[:2], "report": FLOW}
OPERATIONS = dict(zip(("FETCH", "SUMMARIZE", "SAVE", "READ", "VERIFY"), FLOW))
CODE_BY_TOOL = {name: code for code, name in OPERATIONS.items()}
PROMPT = (
    "Choose exactly one next operation code for the request. These are labels, "
    "not functions to call. FETCH obtains repository data; SUMMARIZE creates a "
    "summary; SAVE writes it; READ reads the saved file; VERIFY compares it. "
    "An info request needs FETCH; a summary needs FETCH then SUMMARIZE; a "
    "verified report needs FETCH, SUMMARIZE, SAVE, READ, VERIFY. Return only "
    "a JSON object with the operation code. Never attempt a function call."
)


@dataclass(frozen=True)
class Step:
    tool: str
    server: str
    arguments: dict
    output: dict
    selection_source: str


@dataclass(frozen=True)
class AgentResult:
    answer: str
    steps: tuple[Step, ...]


class BublikOrchestrator:
    def __init__(self, model_client: Any, registry: ToolRegistry):
        self.model_client = model_client
        self.registry = registry

    async def run(self, owner: str, repo: str, task: str = "report") -> AgentResult:
        owner, repo = validate_name(owner, "owner"), validate_name(repo, "repo")
        if task not in FLOWS:
            raise ValueError(f"Unknown task: {task}")
        flow = FLOWS[task]
        missing = set(flow) - set(self.registry.routes)
        if missing:
            raise RuntimeError(f"Missing MCP tools: {sorted(missing)}")
        request = {
            "info": f"Get repository information for {owner}/{repo}.",
            "summary": f"Summarize repository {owner}/{repo} without saving a file.",
            "report": f"Create and verify a report for {owner}/{repo}.",
        }[task]
        steps: list[Step] = []
        for _ in range(len(flow)):
            completed = [CODE_BY_TOOL[step.tool] for step in steps]
            messages = [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": f"Request: {request}\n"
                 f"Completed operations: {json.dumps(completed)}\n"
                 "Choose the next operation code."},
            ]
            try:
                response = self.model_client.chat.completions.create(
                    model=MODEL, messages=messages, temperature=0.1,
                    reasoning_effort="low", max_completion_tokens=250,
                    response_format={"type": "json_schema", "json_schema": {
                        "name": "operation_selection", "strict": True,
                        "schema": {"type": "object", "properties": {
                            "operation": {"type": "string", "enum": list(OPERATIONS)}
                        }, "required": ["operation"], "additionalProperties": False},
                    }},
                )
            except Exception as error:
                body = getattr(error, "body", None)
                code = getattr(error, "code", None)
                if isinstance(body, dict):
                    nested = body.get("error")
                    code = code or body.get("code") or (
                        nested.get("code") if isinstance(nested, dict) else None)
                if getattr(error, "status_code", None) != 400 or code != "tool_use_failed":
                    raise
                # Some Groq responses attempt a native call despite no tools being
                # provided. Use the guarded workflow for this step and show provenance.
                operation = CODE_BY_TOOL[flow[len(steps)]]
                selection_source = "agent fallback (Groq tool parser error)"
            else:
                try:
                    selection = json.loads(response.choices[0].message.content or "")
                except (ValueError, TypeError) as error:
                    raise RuntimeError("Model returned invalid operation JSON") from error
                if not isinstance(selection, dict) or set(selection) != {"operation"}:
                    raise RuntimeError("Model returned an invalid operation selection")
                operation = selection["operation"]
                selection_source = "model"
            if operation not in OPERATIONS:
                raise RuntimeError(f"Model selected an unknown operation: {operation!r}")
            name = OPERATIONS[operation]
            if name != flow[len(steps)]:
                # A model suggestion cannot skip dependencies. Correct it visibly
                # rather than letting an unsafe or premature MCP call run.
                selection_source = f"agent correction (model chose {operation})"
                name = flow[len(steps)]
            actual_arguments = self._arguments(len(steps), owner, repo, steps)
            output = await self.registry.call(name, actual_arguments)
            self._validate_output(len(steps), owner, repo, output, steps)
            alias, _ = self.registry.routes[name]
            steps.append(Step(name, alias, actual_arguments, output,
                              selection_source))
        name = f"{owner}/{repo}"
        if task == "report":
            if steps[-1].output.get("verified") is not True:
                raise RuntimeError("Final report verification failed")
            answer = f"Verified {name}; report: {steps[2].output['path']}"
        elif task == "summary":
            answer = f"Summary for {name}: {steps[1].output['markdown']}"
        else:
            answer = f"Repository {name}: {steps[0].output}"
        return AgentResult(answer, tuple(steps))

    @staticmethod
    def _arguments(index: int, owner: str, repo: str, steps: list[Step]) -> dict:
        if index in (0, 3):
            return {"owner": owner, "repo": repo}
        if index == 1:
            return {"repository": steps[0].output}
        if index == 2:
            return {"summary": steps[1].output}
        return {"summary": steps[1].output, "saved_report": steps[3].output}

    @staticmethod
    def _validate_output(index: int, owner: str, repo: str,
                         value: dict, steps: list[Step]) -> None:
        name = f"{owner}/{repo}"
        if value.get("full_name") != name:
            raise RuntimeError("Repository identity changed between MCP servers")
        if index == 2 and value.get("bytes_written") != len(steps[1].output["markdown"].encode("utf-8")):
            raise RuntimeError("Saved byte count differs from summary")
        if index == 3 and (value.get("markdown") != steps[1].output["markdown"] or
                           value.get("path") != steps[2].output["path"]):
            raise RuntimeError("Readback differs from saved report")
        if index == 4 and value.get("verified") is not True:
            raise RuntimeError("Final report verification failed")
