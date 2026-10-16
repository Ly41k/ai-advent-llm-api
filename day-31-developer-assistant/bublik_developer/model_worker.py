"""Owned inference task, separate from retrieval/Git processes and contexts."""
import json
import re
import sys

from .contracts import Role, ContextEnvelope, canonical
from .errors import DeveloperError, ErrorCode
from .generation import Qwen, validate_context
from .model_session import ModelSession
from .workspace import ProjectWorkspace


def execute(payload, *, client_class=Qwen, context_validator=validate_context):
    required = {"root", "workspace_identity", "project_id", "role", "context", "context_digest", "final", "request_id", "task_id"}
    if not isinstance(payload, dict) or set(payload) != required or type(payload["final"]) is not bool:
        raise DeveloperError(ErrorCode.PERMISSION_DENIED)
    if any(not isinstance(payload[key], str) or not re.fullmatch(r"[a-f0-9]{32}", payload[key]) for key in ("request_id", "task_id")):
        raise DeveloperError(ErrorCode.INVALID_INPUT)
    try:
        role = Role(payload["role"])
    except (ValueError, TypeError):
        raise DeveloperError(ErrorCode.PERMISSION_DENIED, "role") from None
    context_validator(role, payload["context"])
    if ContextEnvelope.seal(payload["context"]).digest != payload["context_digest"]:
        raise DeveloperError(ErrorCode.INVALID_INPUT)
    workspace = ProjectWorkspace.open(payload["root"], payload["project_id"])
    if list(workspace.identity) != payload["workspace_identity"]:
        raise DeveloperError(ErrorCode.WORKSPACE_CHANGED)
    client = None
    try:
        with ModelSession(workspace).lease() as lease:
            client = client_class(lease)
            result = client.generate(role, payload["context"], final=payload["final"])
        return {"data": result, "error_code": None, "metrics": {**client.metrics, "request_id": payload["request_id"], "task_id": payload["task_id"]}}
    except DeveloperError as error:
        return {"data": {}, "error_code": error.code.value,
                "metrics": {**(client.metrics if client and client.metrics else {"llm_calls": 0}),
                            "request_id": payload["request_id"], "task_id": payload["task_id"]}}


def main(*, client_class=Qwen, context_validator=validate_context):
    payload = None
    try:
        raw = sys.stdin.buffer.read(32769)
        if len(raw) > 32768:
            raise DeveloperError(ErrorCode.CONTEXT_BUDGET)
        payload = json.loads(raw)
        reply = execute(payload, client_class=client_class, context_validator=context_validator)
    except DeveloperError as error:
        reply = {"data": {}, "error_code": error.code.value, "metrics": {"llm_calls": 0}}
    except Exception:
        # Unknown failure may follow dispatch; never label it as zero inference.
        reply = {"data": {}, "error_code": ErrorCode.AGENT_FAILED.value,
                 "metrics": {"llm_calls": None, "status": "unknown"}}
    if isinstance(payload, dict):
        for key in ("request_id", "task_id"):
            if isinstance(payload.get(key), str) and re.fullmatch(r"[a-f0-9]{32}", payload[key]):
                reply["metrics"][key] = payload[key]
    print(canonical(reply))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
