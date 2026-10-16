"""Task-scoped Qwen workers; only Documentation and Main have inference."""
import asyncio
from dataclasses import replace
import json
import math
from pathlib import Path
import sys
from time import perf_counter

from .agent_process import run_owned
from .contracts import ContextEnvelope, Role, TaskEnvelope, canonical
from .errors import DeveloperError, ErrorCode
from .generation import validate_context, validate_output, valid_language_details
from .process import minimal_env


def valid_metrics(value):
    if "output_validation_details" in value and (
            value.get("output_validation") != "rejected" or
            value.get("output_validation_reason") != "claim_language" or
            not valid_language_details(value["output_validation_details"])):
        return False
    calls = value.get("llm_calls")
    if calls is not None and (type(calls) is not int or calls not in {0, 1}):
        return False
    for field in ("input_tokens", "output_tokens", "dispatch_attempts", "metadata_retries"):
        number = value.get(field)
        if number is not None and (type(number) is not int or number < 0):
            return False
    if value.get("metadata_retries", 0) not in {0, 1}:
        return False
    for field in ("seconds", "task_seconds"):
        number = value.get(field)
        if number is not None and (type(number) not in (int, float) or not math.isfinite(number) or number < 0):
            return False
    try:
        canonical(value)
    except DeveloperError:
        return False
    return True


class InferenceTasks:
    context_validator = staticmethod(validate_context)
    output_validator = staticmethod(validate_output)
    worker_module = "bublik_developer.model_worker"

    def __init__(self, workspace, request_id, record, budget):
        self.workspace, self.request_id, self.record, self.budget = workspace, request_id, record, budget
        self.observations = []

    async def run(self, role, context, *, final=True):
        self.context_validator(role, context)
        task = replace(TaskEnvelope.create(role, self.workspace.project_id, "Scoped project inference", context, request_id=self.request_id),
                       timeout_seconds=180, max_tool_calls=1)
        package = Path(__file__).resolve().parent.parent
        payload = {"root": str(self.workspace.root), "workspace_identity": list(self.workspace.identity),
            "project_id": self.workspace.project_id, "role": role.value, "context": task.context.open(),
            "context_digest": task.context.digest, "final": final,
            "request_id": task.request_id, "task_id": task.task_id}
        encoded = canonical(payload).encode()
        if len(encoded) > 32768:
            raise DeveloperError(ErrorCode.CONTEXT_BUDGET)
        self.budget.consume()
        self.record("SPAWN", task_id=task.task_id, role=role.value, context_digest=task.context.digest,
                    context_keys=sorted(context), capability="local_inference_only",
                    timeout_seconds=task.timeout_seconds, max_generation_calls=task.max_tool_calls)
        started = perf_counter()
        observation = {"task_id": task.task_id, "role": role.value, "context_digest": task.context.digest,
                       "context_keys": sorted(context), "llm_calls": None, "status": "unknown"}
        self.observations.append(observation)
        self.record("EXECUTE", task_id=task.task_id, role=role.value)
        try:
            async with asyncio.timeout(min(task.timeout_seconds, self.budget.seconds_remaining)):
                raw, pid = await run_owned([sys.executable, "-m", self.worker_module],
                    encoded, cwd=str(package), env={**minimal_env(), "PYTHONPATH": str(package)})
            reply = json.loads(raw)
            if (not isinstance(reply, dict) or set(reply) != {"data", "metrics", "error_code"}
                    or not isinstance(reply["metrics"], dict)
                    or "llm_calls" not in reply["metrics"] or not valid_metrics(reply["metrics"])):
                raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
            if reply["metrics"].get("task_id") != task.task_id or reply["metrics"].get("request_id") != task.request_id:
                raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
            observation.update(reply["metrics"])
            observation.update(task_id=task.task_id, role=role.value, context_digest=task.context.digest, context_keys=sorted(context))
            self.record("WORKER_REAPED", task_id=task.task_id, role=role.value, worker_pid=pid)
            if reply["error_code"]:
                raise DeveloperError(ErrorCode(reply["error_code"]))
            result = self.output_validator(role, reply["data"], context)
            self.record("REPORT", task_id=task.task_id, role=role.value, status="success")
            return result
        except TimeoutError:
            observation["status"] = "timeout"
            self.record("REPORT", task_id=task.task_id, role=role.value, status="timeout")
            raise DeveloperError(ErrorCode.TIMEOUT) from None
        except asyncio.CancelledError:
            observation["status"] = "cancelled"
            self.record("REPORT", task_id=task.task_id, role=role.value, status="cancelled")
            raise
        except DeveloperError as error:
            observation["error_code"] = error.code.value
            self.record("REPORT", task_id=task.task_id, role=role.value, status="failed", error_code=error.code.value)
            raise
        except (ValueError, TypeError):
            observation.update(status="invalid_worker_reply", error_code=ErrorCode.INVALID_TOOL_OUTPUT.value)
            self.record("REPORT", task_id=task.task_id, role=role.value, status="failed", error_code=ErrorCode.INVALID_TOOL_OUTPUT.value)
            raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT) from None
        finally:
            observation["task_seconds"] = perf_counter() - started
