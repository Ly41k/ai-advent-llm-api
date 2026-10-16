"""Immutable, bounded JSON contexts and task/result contracts for later dispatch."""
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
import math
from uuid import uuid4

from .errors import DeveloperError, ErrorCode


class Role(StrEnum):
    MAIN = "main"
    DOCUMENTATION = "documentation"
    GIT = "git"
    VERIFICATION = "verification"


class TaskStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


def canonical(value):
    try:
        encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        raise DeveloperError(ErrorCode.INVALID_INPUT) from None
    return encoded


@dataclass(frozen=True)
class ContextEnvelope:
    """Serialized snapshot: later mutation of caller-owned dicts cannot alter it."""
    payload_json: str
    digest: str

    @classmethod
    def seal(cls, payload, max_bytes=24000):
        if not isinstance(payload, dict) or type(max_bytes) is not int or max_bytes <= 0:
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        encoded = canonical(payload)
        if len(encoded.encode()) > max_bytes:
            raise DeveloperError(ErrorCode.CONTEXT_BUDGET)
        return cls(encoded, sha256(encoded.encode()).hexdigest())

    def open(self):
        if sha256(self.payload_json.encode()).hexdigest() != self.digest:
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        try:
            value = json.loads(self.payload_json)
        except (ValueError, RecursionError):
            raise DeveloperError(ErrorCode.INVALID_INPUT) from None
        if not isinstance(value, dict) or canonical(value) != self.payload_json:
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        return value


@dataclass(frozen=True)
class TaskEnvelope:
    request_id: str
    task_id: str
    role: Role
    project_id: str
    objective: str
    context: ContextEnvelope
    max_tool_calls: int = 8
    timeout_seconds: float = 30
    delegation_depth: int = 1

    def __post_init__(self):
        if (not isinstance(self.role, Role) or not isinstance(self.context, ContextEnvelope)
                or any(not isinstance(v, str) or not v or len(v) > n for v, n in
                       ((self.request_id, 80), (self.task_id, 80), (self.project_id, 80), (self.objective, 2000)))
                or type(self.max_tool_calls) is not int or not 1 <= self.max_tool_calls <= 8
                or type(self.timeout_seconds) not in (int, float) or not math.isfinite(self.timeout_seconds)
                or not 0 < self.timeout_seconds <= 300
                or type(self.delegation_depth) is not int or self.delegation_depth != 1):
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        self.context.open()

    @classmethod
    def create(cls, role, project_id, objective, context, *, request_id=None):
        return cls(request_id or uuid4().hex, uuid4().hex, role, project_id, objective, ContextEnvelope.seal(context))


@dataclass(frozen=True)
class AgentResult:
    task_id: str
    status: TaskStatus
    outcome: str
    data: ContextEnvelope
    error_code: str | None = None

    def __post_init__(self):
        if (not isinstance(self.status, TaskStatus) or not isinstance(self.data, ContextEnvelope)
                or not isinstance(self.task_id, str) or not self.task_id or len(self.task_id) > 80
                or self.outcome not in {"answered", "insufficient_evidence", "partial", "error"}
                or (self.status == TaskStatus.SUCCESS) != (self.error_code is None)
                or (self.error_code is not None and self.error_code not in {e.value for e in ErrorCode})):
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        self.data.open()
