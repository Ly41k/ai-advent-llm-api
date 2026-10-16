"""Closed role dispatcher with independent tasks, dependencies and lifecycle.

Stage 4 uses real FTS and MCP, with Documentation/Verification in owned workers.
This dispatcher has no generation capability; Stage 5 uses separate inference tasks.
The capability boundary assumes trusted app code, not hostile Python plugins.
"""
import asyncio
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys
from time import perf_counter

from .agent_process import run_owned
from .contracts import AgentResult, ContextEnvelope, Role, TaskEnvelope, TaskStatus, canonical
from .errors import DeveloperError, ErrorCode
from .policy import authorize
from .process import minimal_env
from .rag.retrieval import query_terms

GIT_NAMES = {"branch": "git__git_current_branch", "status": "git__git_status",
             "files": "git__project_list_files", "diff": "git__git_diff"}


@dataclass(frozen=True)
class Job:
    task: TaskEnvelope
    dependencies: tuple[str, ...] = ()


class Dispatcher:
    def __init__(self, workspace, corpus, state, *, max_calls=8, timeout=300):
        if (type(max_calls) is not int or not 1 <= max_calls <= 8
                or type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 300
                or (corpus is not None and corpus.workspace != workspace)):
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        self.workspace, self.corpus, self.state = workspace, corpus, state
        self.max_calls, self.timeout, self.calls = max_calls, timeout, 0
        self.trace, self.results, self.audit, self.tool_events = [], {}, [], []
        self.started, self.used = perf_counter(), False
        self.active = asyncio.Semaphore(4)

    def record(self, event, task=None, **extra):
        self.trace.append({"sequence": len(self.trace) + 1, "event": event,
                           "seconds": round(perf_counter() - self.started, 6),
                           **({"task_id": task.task_id, "role": task.role.value} if task else {}), **extra})

    def validate(self, jobs):
        if (not isinstance(jobs, list) or not 1 <= len(jobs) <= 4
                or any(not isinstance(job, Job) or not isinstance(job.task, TaskEnvelope) for job in jobs)):
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        tasks = {job.task.task_id: job for job in jobs}
        if len(tasks) != len(jobs) or len({job.task.request_id for job in jobs}) != 1:
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        for job in jobs:
            task = job.task
            if task.project_id != self.workspace.project_id or task.role == Role.MAIN:
                raise DeveloperError(ErrorCode.PERMISSION_DENIED, "role")
            value = task.context.open()
            if (not isinstance(job.dependencies, tuple)
                    or any(not isinstance(dep, str) or not dep or len(dep) > 80 for dep in job.dependencies)
                    or len(set(job.dependencies)) != len(job.dependencies)
                    or any(dep not in tasks or dep == task.task_id for dep in job.dependencies)):
                raise DeveloperError(ErrorCode.INVALID_INPUT)
            if task.role == Role.GIT:
                if (set(value) != {"operation", "arguments"} or not isinstance(value["operation"], str)
                        or value["operation"] not in GIT_NAMES or job.dependencies):
                    raise DeveloperError(ErrorCode.PERMISSION_DENIED, "role")
                authorize(task.role, GIT_NAMES[value["operation"]].removeprefix("git__"), value["arguments"])
            elif task.role == Role.DOCUMENTATION:
                allowed = {"question", "mode", "from_changed_files"}
                if (self.corpus is None or not isinstance(value, dict) or "question" not in value or set(value) - allowed
                        or value.get("mode", "fts") not in {"fts", "dense", "hybrid"}
                        or type(value.get("from_changed_files", False)) is not bool):
                    raise DeveloperError(ErrorCode.PERMISSION_DENIED, "role")
                if job.dependencies:
                    if (value.get("from_changed_files") is not True or len(job.dependencies) != 1
                            or tasks[job.dependencies[0]].task.role != Role.GIT
                            or tasks[job.dependencies[0]].task.context.open()["operation"] != "status"):
                        raise DeveloperError(ErrorCode.PERMISSION_DENIED, "role")
                elif value.get("from_changed_files"):
                    raise DeveloperError(ErrorCode.PERMISSION_DENIED, "role")
                query_terms(value["question"])
            elif task.role == Role.VERIFICATION:
                if (set(value) != {"task_ids"} or not isinstance(value["task_ids"], list)
                        or value["task_ids"] != list(job.dependencies) or not job.dependencies
                        or any(tasks[dep].task.role not in {Role.GIT, Role.DOCUMENTATION} for dep in job.dependencies)):
                    raise DeveloperError(ErrorCode.PERMISSION_DENIED, "role")
            else:
                raise DeveloperError(ErrorCode.PERMISSION_DENIED, "role")
        visited, visiting = set(), set()
        def visit(key):
            if key in visiting:
                raise DeveloperError(ErrorCode.INVALID_INPUT)
            if key in visited:
                return
            visiting.add(key)
            for dep in tasks[key].dependencies:
                visit(dep)
            visiting.remove(key)
            visited.add(key)
        for key in tasks:
            visit(key)
        return tasks

    async def worker(self, task, context):
        package = Path(__file__).resolve().parent.parent
        selection = None if self.corpus is None or self.corpus.dynamic_default else self.corpus.specs
        payload = {"role": task.role.value, "root": str(self.workspace.root),
                   "workspace_identity": list(self.workspace.identity), "project_id": self.workspace.project_id,
                   "state_dir": str(self.state.path), "selection": None if selection is None else
                       [{"path": spec.path, "kind": spec.kind} for spec in selection], "context": context.open()}
        raw, pid = await run_owned([sys.executable, "-m", "bublik_developer.agent_worker"],
                                  canonical(payload).encode(), cwd=str(package),
                                  env={**minimal_env(), "PYTHONPATH": str(package)})
        try:
            reply = json.loads(raw)
            if not isinstance(reply, dict) or set(reply) != {"data", "outcome", "error_code"}:
                raise ValueError
            data = ContextEnvelope.seal(reply["data"])
            result = AgentResult(task.task_id, TaskStatus.SUCCESS if reply["error_code"] is None else TaskStatus.FAILED,
                                 reply["outcome"], data, reply["error_code"])
        except (ValueError, TypeError, KeyError):
            raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT) from None
        self.record("WORKER_REAPED", task, worker_pid=pid)
        return result

    async def execute(self, task, context):
        if task.role == Role.GIT:
            from .mcp_client import ScopedGitClient, connect_git
            value = context.open()
            async with connect_git(self.workspace) as registry:
                data = await ScopedGitClient(registry, task).call(GIT_NAMES[value["operation"]], value["arguments"])
                self.tool_events.extend({**event, "task_id": task.task_id} for event in registry.events)
                return AgentResult(task.task_id, TaskStatus.SUCCESS, "answered", ContextEnvelope.seal(data))
        return await self.worker(task, context)

    async def run(self, jobs):
        if self.used:
            raise DeveloperError(ErrorCode.PERMISSION_DENIED)
        tasks = self.validate(jobs)
        self.used = True
        self.started = perf_counter()
        running = {}
        async def one(job):
            task, context = job.task, job.task.context
            started = perf_counter()
            result = None
            try:
                async with asyncio.timeout(task.timeout_seconds):
                    dependencies = [await asyncio.shield(running[key]) for key in job.dependencies]
                    if any(value.status != TaskStatus.SUCCESS for value in dependencies):
                        raise DeveloperError(ErrorCode.DEPENDENCY_FAILED)
                    if task.role == Role.VERIFICATION:
                        context = ContextEnvelope.seal({"results": [
                            {"task_id": value.task_id, "role": tasks[value.task_id].task.role.value,
                             "data": value.data.open()} for value in dependencies]})
                    elif task.role == Role.DOCUMENTATION and job.dependencies:
                        value = context.open()
                        entries = dependencies[0].data.open()["data"]["entries"]
                        value.pop("from_changed_files", None)
                        value["changed_paths"] = list(dict.fromkeys(
                            path for entry in entries for path in (entry["path"], entry["original_path"]) if path))
                        context = ContextEnvelope.seal(value)
                    self.audit.append({"task_id": task.task_id, "role": task.role.value,
                                       "context_digest": context.digest, "context_keys": sorted(context.open()),
                                       "context_bytes": len(context.payload_json.encode())})
                    async with self.active:
                        if self.calls >= self.max_calls:
                            raise DeveloperError(ErrorCode.PERMISSION_DENIED)
                        self.workspace.check()
                        self.calls += 1
                        self.record("EXECUTE", task, effective_context_digest=context.digest)
                        result = await self.execute(task, context)
                        if not isinstance(result, AgentResult) or result.task_id != task.task_id:
                            raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
            except asyncio.CancelledError:
                result = AgentResult(task.task_id, TaskStatus.CANCELLED, "error", ContextEnvelope.seal({}), ErrorCode.CANCELLED.value)
            except TimeoutError:
                result = AgentResult(task.task_id, TaskStatus.TIMEOUT, "error", ContextEnvelope.seal({}), ErrorCode.TIMEOUT.value)
            except DeveloperError as error:
                result = AgentResult(task.task_id, TaskStatus.FAILED, "error", ContextEnvelope.seal({}), error.code.value)
            except Exception:
                result = AgentResult(task.task_id, TaskStatus.FAILED, "error", ContextEnvelope.seal({}), ErrorCode.AGENT_FAILED.value)
            self.results[task.task_id] = result
            self.record("REPORT", task, status=result.status.value, outcome=result.outcome,
                        error_code=result.error_code, task_seconds=perf_counter() - started)
            return result
        # No await before every handle is registered: dependency order is irrelevant.
        for job in jobs:
            self.record("SPAWN", job.task, context_digest=job.task.context.digest, dependencies=list(job.dependencies))
            running[job.task.task_id] = asyncio.create_task(one(job))
        interruption = None
        try:
            async with asyncio.timeout(self.timeout):
                await asyncio.gather(*running.values())
        except (TimeoutError, asyncio.CancelledError) as error:
            interruption = "timeout" if isinstance(error, TimeoutError) else "cancelled"
            for handle in running.values():
                handle.cancel()
            await asyncio.gather(*running.values(), return_exceptions=True)
        for job in jobs:
            if job.task.task_id not in self.results:
                self.results[job.task.task_id] = AgentResult(job.task.task_id, TaskStatus.CANCELLED, "error",
                    ContextEnvelope.seal({}), ErrorCode.CANCELLED.value)
                self.record("REPORT", job.task, status="cancelled", outcome="error", error_code=ErrorCode.CANCELLED.value)
        verified = set()
        for job in jobs:
            result = self.results.get(job.task.task_id)
            if job.task.role == Role.VERIFICATION and result and result.status == TaskStatus.SUCCESS:
                verified.update(result.data.open()["verified_task_ids"])
        self.record("MERGE", verified_task_ids=sorted(verified), interruption=interruption)
        serialized = [{"task_id": job.task.task_id, "role": job.task.role.value,
                       "status": self.results[job.task.task_id].status.value,
                       "outcome": self.results[job.task.task_id].outcome,
                       "error_code": self.results[job.task.task_id].error_code,
                       "data": self.results[job.task.task_id].data.open()} for job in jobs]
        successes = sum(row["status"] == TaskStatus.SUCCESS for row in serialized)
        return {"status": "completed" if successes == len(jobs) else "partial" if successes else "failed",
                "request_id": jobs[0].task.request_id, "results": serialized,
                "merged": [row for row in serialized if row["task_id"] in verified],
                "trace": self.trace, "context_audit": self.audit, "tool_events": self.tool_events,
                "metrics": {"capability_calls": self.calls, "llm_calls": 0,
                            "total_seconds": perf_counter() - self.started},
                "scope": "agent_runtime_fts_mcp_and_provenance", "independent_llm_contexts_verified": False}


async def demo(workspace, corpus, state, *, question, operation="branch", mode="demo"):
    from uuid import uuid4
    request_id, jobs = uuid4().hex, []
    if mode in {"demo", "docs"}:
        task = TaskEnvelope.create(Role.DOCUMENTATION, workspace.project_id, "Retrieve project evidence",
                                   {"question": question}, request_id=request_id)
        jobs.append(Job(task))
    if mode in {"demo", "git"}:
        task = TaskEnvelope.create(Role.GIT, workspace.project_id, "Observe Git metadata",
                                   {"operation": operation, "arguments": {}}, request_id=request_id)
        jobs.append(Job(task))
    dependencies = tuple(job.task.task_id for job in jobs)
    task = TaskEnvelope.create(Role.VERIFICATION, workspace.project_id, "Verify delegated results",
                               {"task_ids": list(dependencies)}, request_id=request_id)
    jobs.append(Job(task, dependencies))
    return await Dispatcher(workspace, corpus, state).run(jobs)
