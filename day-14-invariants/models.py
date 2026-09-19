"""Модели памяти, состояния задачи, персонализации и invariants."""

from dataclasses import dataclass
from enum import Enum


class TaskState(str, Enum):
    PLANNING = "planning"
    EXECUTION = "execution"
    VALIDATION = "validation"
    DONE = "done"


class ExpectedAction(str, Enum):
    DEFINE_PLAN = "define_plan"
    START_EXECUTION = "start_execution"
    COMPLETE_CURRENT_STEP = "complete_current_step"
    START_VALIDATION = "start_validation"
    RECORD_VALIDATION = "record_validation"
    FINISH_TASK = "finish_task"
    RETURN_TO_EXECUTION = "return_to_execution"
    RESUME = "resume"
    NONE = "none"


class LongTermKind(str, Enum):
    DECISION = "decision"
    KNOWLEDGE = "knowledge"


class InvariantCategory(str, Enum):
    STACK = "stack"
    ARCHITECTURE = "architecture"
    TECHNICAL_DECISION = "technical_decision"
    BUSINESS_RULE = "business_rule"
    SECURITY = "security"


@dataclass(frozen=True)
class Invariant:
    id: str
    category: InvariantCategory
    description: str
    rationale: str
    request_conflict_patterns: list[str]
    response_forbidden_patterns: list[str]
    compatible_alternative: str


@dataclass(frozen=True)
class InvariantPolicy:
    version: int
    invariants: list[Invariant]


@dataclass(frozen=True)
class Conversation:
    id: str
    title: str
    profile_id: str
    message_count: int
    updated_at: str


@dataclass(frozen=True)
class Message:
    id: int
    role: str
    content: str
    status: str
    created_at: str


@dataclass(frozen=True)
class TaskContext:
    task: str
    state: TaskState
    step: int
    plan: list[str]
    done: list[str]
    current: str | None
    validation_passed: bool
    validation_details: str | None = None
    paused: bool = False

    @property
    def total(self) -> int:
        return len(self.plan)

    @property
    def expected_action(self) -> ExpectedAction:
        """Следующее допустимое действие, однозначно выведенное из состояния."""
        if self.paused:
            return ExpectedAction.RESUME
        if self.state is TaskState.PLANNING:
            return (
                ExpectedAction.START_EXECUTION
                if self.plan
                else ExpectedAction.DEFINE_PLAN
            )
        if self.state is TaskState.EXECUTION:
            return (
                ExpectedAction.COMPLETE_CURRENT_STEP
                if self.current is not None
                else ExpectedAction.START_VALIDATION
            )
        if self.state is TaskState.VALIDATION:
            if self.validation_details is None:
                return ExpectedAction.RECORD_VALIDATION
            return (
                ExpectedAction.FINISH_TASK
                if self.validation_passed
                else ExpectedAction.RETURN_TO_EXECUTION
            )
        return ExpectedAction.NONE


@dataclass(frozen=True)
class MemoryEntry:
    kind: LongTermKind
    key: str
    value: str
    updated_at: str


@dataclass(frozen=True)
class WorkingNote:
    key: str
    value: str
    updated_at: str


@dataclass(frozen=True)
class AssistantIdentity:
    name: str
    role: str


@dataclass(frozen=True)
class UserProfile:
    id: str
    name: str
    role: str
    language: str
    detail_level: str
    style: list[str]
    response_format: list[str]
    constraints: list[str]


@dataclass(frozen=True)
class InvariantCheckResult:
    passed: bool
    checked: list[str]
    violations: list[str]
    explanations: list[str]


@dataclass(frozen=True)
class AgentResponse:
    content: str
    profile_id: str
    validation: InvariantCheckResult
    task_context: TaskContext | None
    short_term_messages: int
    working_memory_items: int
    long_term_items: int
    refused_by_invariants: bool = False
