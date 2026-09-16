"""Модели памяти, состояния задачи и персонализации."""

from dataclasses import dataclass
from enum import Enum


class TaskState(str, Enum):
    PLANNING = "planning"
    EXECUTION = "execution"
    VALIDATION = "validation"
    DONE = "done"


class LongTermKind(str, Enum):
    DECISION = "decision"
    KNOWLEDGE = "knowledge"


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

    @property
    def total(self) -> int:
        return len(self.plan)


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


@dataclass(frozen=True)
class AgentResponse:
    content: str
    profile_id: str
    validation: InvariantCheckResult
    task_context: TaskContext | None
    short_term_messages: int
    working_memory_items: int
    long_term_items: int
