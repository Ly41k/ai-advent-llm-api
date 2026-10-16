"""Namespaced discovery/calls adapted from Day 20; capability bound per task."""
import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
import json
from pathlib import Path
import sys
from time import perf_counter

from jsonschema import Draft202012Validator, ValidationError
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import ValidationError as ModelValidationError

from .contracts import Role, TaskEnvelope, canonical
from .errors import DeveloperError, ErrorCode
from .mcp_schema import GitReply
from .policy import TOOLS, authorize
from .process import minimal_env


class ToolRegistry:
    def __init__(self, session, workspace, *, timeout=15):
        self.session, self.workspace, self.timeout = session, workspace, timeout
        self.catalog, self.events = {}, []

    async def discover(self):
        async with asyncio.timeout(self.timeout):
            result = await self.session.list_tools()
        if {tool.name for tool in result.tools} != TOOLS or len(result.tools) != len(TOOLS):
            raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT, "schema")
        for tool in result.tools:
            if not isinstance(tool.inputSchema, dict) or not isinstance(tool.outputSchema, dict):
                raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT, "schema")
            Draft202012Validator.check_schema(tool.inputSchema)
            Draft202012Validator.check_schema(tool.outputSchema)
            self.catalog["git__" + tool.name] = {"input": tool.inputSchema, "output": tool.outputSchema}
        return self.catalog

    async def call(self, role, name, arguments):
        actual = name.removeprefix("git__")
        authorize(role, actual, arguments)
        if name not in self.catalog:
            raise DeveloperError(ErrorCode.PERMISSION_DENIED)
        schema = self.catalog[name]
        try:
            Draft202012Validator(schema["input"]).validate(arguments)
        except ValidationError:
            raise DeveloperError(ErrorCode.INVALID_INPUT, "schema") from None
        started = perf_counter()
        event = {"tool": name, "argument_keys": sorted(arguments), "status": "failed"}
        try:
            async with asyncio.timeout(self.timeout):
                result = await self.session.call_tool(actual, arguments=arguments)
            if result.isError:
                raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
            if isinstance(result.structuredContent, dict):
                value = result.structuredContent
                if set(value) == {"result"}:
                    value = value["result"]
            else:
                parts = [part.text for part in result.content if getattr(part, "type", None) == "text"]
                if len(parts) != 1 or len(parts[0].encode()) > 262144:
                    raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
                value = json.loads(parts[0])
            if len(canonical(value).encode()) > 262144:
                raise DeveloperError(ErrorCode.OUTPUT_LIMIT)
            Draft202012Validator(schema["output"]).validate(value)
            reply = GitReply.model_validate(value)
            if reply.project_id != self.workspace.project_id or reply.tool != actual:
                raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
            self.workspace.check()
            if not reply.ok:
                raise DeveloperError(ErrorCode(reply.error.code), reply.error.detail or "")
            data = value["data"]
            returned_paths = []
            if actual == "git_status":
                for entry in data["entries"]:
                    returned_paths.extend([entry["path"], *([entry["original_path"]] if entry["original_path"] else [])])
            elif actual == "project_list_files":
                returned_paths = data["files"]
            elif actual == "git_diff":
                returned_paths = [entry["path"] for entry in data["files"]]
                if (data["scope"] != arguments.get("scope", "unstaged")
                        or data["content_included"] != arguments.get("include_content", False)
                        or arguments.get("paths") and not set(returned_paths).issubset(arguments["paths"])):
                    raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
            for path in returned_paths:
                self.workspace.path(path, content=actual == "git_diff" and data["content_included"], missing=True)
            event["status"] = "success"
            return value
        except (TimeoutError, asyncio.TimeoutError):
            raise DeveloperError(ErrorCode.TIMEOUT) from None
        except (ValidationError, ModelValidationError, ValueError, TypeError):
            raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT) from None
        finally:
            event["seconds"] = perf_counter() - started
            self.events.append(event)


class ScopedGitClient:
    def __init__(self, registry, task):
        if not isinstance(task, TaskEnvelope) or task.role != Role.GIT or task.project_id != registry.workspace.project_id:
            raise DeveloperError(ErrorCode.PERMISSION_DENIED)
        self.registry, self.task, self.calls = registry, task, 0
        self.started = perf_counter()

    async def call(self, name, arguments):
        if self.calls >= self.task.max_tool_calls:
            raise DeveloperError(ErrorCode.PERMISSION_DENIED)
        remaining = self.task.timeout_seconds - (perf_counter() - self.started)
        if remaining <= 0:
            raise DeveloperError(ErrorCode.TIMEOUT)
        self.calls += 1
        async with asyncio.timeout(remaining):
            return await self.registry.call(self.task.role, name, arguments)


@asynccontextmanager
async def connect_git(workspace, *, timeout=15):
    # Entry point and import directory belong to this application, not the target repo.
    trusted_package = Path(__file__).resolve().parent.parent
    parameters = StdioServerParameters(command=sys.executable,
        args=["-m", "bublik_developer.mcp_server", "--root", str(workspace.root), "--project-id", workspace.project_id],
        cwd=trusted_package, env={**minimal_env(), "PYTHONPATH": str(trusted_package), "PYTHONUNBUFFERED": "1"})
    async with AsyncExitStack() as stack:
        read, write = await stack.enter_async_context(stdio_client(parameters))
        session = await stack.enter_async_context(ClientSession(read, write, read_timeout_seconds=timedelta(seconds=timeout)))
        try:
            async with asyncio.timeout(timeout):
                await session.initialize()
            registry = ToolRegistry(session, workspace, timeout=timeout)
            await registry.discover()
        except Exception:
            raise DeveloperError(ErrorCode.MCP_UNAVAILABLE) from None
        yield registry
