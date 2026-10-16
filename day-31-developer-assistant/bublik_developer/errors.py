"""Bounded public diagnostics; never expose subprocess stderr or private bodies."""
from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    PERMISSION_DENIED = "permission_denied"
    WORKSPACE_CHANGED = "workspace_changed"
    GIT_FAILED = "git_execution_failed"
    GIT_STATE_CHANGED = "git_state_changed"
    TIMEOUT = "timeout"
    OUTPUT_LIMIT = "output_limit_exceeded"
    MCP_UNAVAILABLE = "mcp_unavailable"
    INVALID_TOOL_OUTPUT = "invalid_tool_output"
    SERVICE_ACTIVE = "day30_service_active"
    ISOLATION_UNVERIFIED = "day30_isolation_unverified"
    CONTEXT_BUDGET = "context_budget_exceeded"
    INDEX_STALE = "rag_index_stale"
    INDEX_UNAVAILABLE = "rag_index_unavailable"
    INDEX_LOCKED = "rag_index_locked"
    EMBEDDING_UNAVAILABLE = "embedding_unavailable"
    MODEL_SESSION_REQUIRED = "model_session_required"
    MODEL_EPOCH_CHANGED = "model_epoch_changed"
    MODEL_SESSION_BUSY = "model_session_busy"
    AGENT_FAILED = "agent_execution_failed"
    DEPENDENCY_FAILED = "dependency_failed"
    CANCELLED = "cancelled"
    LLM_UNAVAILABLE = "llm_unavailable"
    INVALID_MODEL_OUTPUT = "invalid_model_output"
    STATE_UNAVAILABLE = "private_state_unavailable"


class DeveloperError(Exception):
    def __init__(self, code: ErrorCode, detail: str = ""):
        self.code = ErrorCode(code)
        self.detail = detail if detail in {"path", "role", "scope", "secret", "schema", "repository", "model_stage_not_implemented"} else ""
        super().__init__(self.code.value)

    def to_dict(self):
        return {"code": self.code.value, "detail": self.detail or None}
