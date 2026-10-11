"""Storage contracts; none of these objects starts inference or trusts HTTP input."""
from dataclasses import asdict, dataclass
import math
from types import MappingProxyType


class ServiceError(Exception):
    """Stable diagnostic code without personal text or upstream exception bodies."""

    code = "service_error"

    def __init__(self, code=None):
        self.code = code or type(self).code
        super().__init__(self.code)


class InvalidInput(ServiceError):
    code = "invalid_input"


class NotFound(ServiceError):
    code = "not_found"


class Conflict(ServiceError):
    code = "conflict"


class CapacityExceeded(ServiceError):
    code = "capacity_exceeded"


class StorageUnavailable(ServiceError):
    code = "storage_unavailable"


class SchemaError(ServiceError):
    code = "schema_error"


class ModelUnavailable(ServiceError):
    code = "model_unavailable"


TERMINAL_STATUSES = frozenset({"completed", "truncated", "failed", "interrupted"})
RETRYABLE_STATUSES = TERMINAL_STATUSES - {"completed"}
ERROR_CODES = frozenset({
    "model_unavailable", "model_timeout", "invalid_model_response", "storage_failure",
    "process_interrupted", "queue_expired", "inference_state_unknown", "operator_shutdown",
})
METRIC_KEYS = frozenset({
    "input_tokens", "output_tokens", "queue_seconds", "first_token_seconds",
    "inference_seconds", "load_seconds", "tokens_per_second",
    "total_seconds",
})
DEFAULT_SYSTEM_PROMPT = (
    "You are Bublik, a private local AI assistant. Reply in the user's language. "
    "Be clear about uncertainty and do not claim to have used tools or sources "
    "that were not provided."
)
# Historical v1 text is immutable: existing context snapshots keep its bytes.
DEFAULT_PROMPT_VERSION = "private-chat-v2"
SYSTEM_PROMPTS = MappingProxyType({
    "private-chat-v1": DEFAULT_SYSTEM_PROMPT,
    "private-chat-v2": (
        "You are Bublik, a private local AI assistant. Follow the latest user request "
        "and its output format; use history as context. Reply in the user's language. "
        "State uncertainty; don't claim unprovided tools or sources."
    ),
})


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


@dataclass(frozen=True)
class ModelProfile:
    """Starting settings, not evidence of model quality or local loading."""

    model: str = "qwen2.5:14b"
    temperature: float = 0
    max_output: int = 1024
    num_ctx: int = 8192
    margin: int = 512
    prompt_version: str = DEFAULT_PROMPT_VERSION

    def validate(self):
        if (not isinstance(self.model, str) or not self.model.strip()
                or len(self.model) > 120 or "cloud" in self.model.lower()
                or any(c.isspace() for c in self.model)):
            raise InvalidInput("invalid_model_profile")
        if (type(self.temperature) not in (int, float)
                or not math.isfinite(self.temperature) or not 0 <= self.temperature <= 2):
            raise InvalidInput("invalid_model_profile")
        if (not integer(self.max_output, 1) or not integer(self.num_ctx, 1)
                or not integer(self.margin, 1)
                or self.max_output + self.margin >= self.num_ctx
                or not isinstance(self.prompt_version, str)
                or self.prompt_version not in SYSTEM_PROMPTS):
            raise InvalidInput("invalid_model_profile")

    @property
    def system_prompt(self):
        self.validate()
        return SYSTEM_PROMPTS[self.prompt_version]

    def to_dict(self):
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class ModelIdentity:
    model: str
    digest: str
    template_sha256: str
    server_version: str
    parameters_sha256: str = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    tokenizer: str = "qwen2-byte-bpe"
    quantization: str = "Q4_K_M"
    counter_version: str = "qwen2-utf8-upper-v1"

    def validate(self, profile):
        import re
        if (self.model != profile.model or self.quantization != "Q4_K_M"
                or self.tokenizer != "qwen2-byte-bpe"
                or self.counter_version != "qwen2-utf8-upper-v1"
                or not re.fullmatch(r"[a-f0-9]{64}", self.digest)
                or not re.fullmatch(r"[a-f0-9]{64}", self.template_sha256)
                or not re.fullmatch(r"[a-f0-9]{64}", self.parameters_sha256)
                or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?", self.server_version)):
            raise InvalidInput("invalid_model_identity")


@dataclass(frozen=True)
class MemorySource:
    chat_id: str
    message_id: str
    sequence: int
    start: int
    end: int
    source_sha256: str
    quote: str
    created_at: str

    role: str = "user"
    status: str = "accepted"

    def validate(self):
        import re
        if ((self.role, self.status) not in {("user", "accepted"),
                ("assistant", "completed"), ("assistant", "truncated"),
                ("assistant", "failed"), ("assistant", "interrupted")}
                or any(not isinstance(v, str) or not re.fullmatch(r"[a-f0-9]{32}", v)
                for v in (self.chat_id, self.message_id))
                or not integer(self.sequence, 1) or not integer(self.start)
                or not integer(self.end, self.start + 1)
                or not isinstance(self.source_sha256, str)
                or not re.fullmatch(r"[a-f0-9]{64}", self.source_sha256)
                or not isinstance(self.quote, str) or not self.quote
                or len(self.quote.encode("utf-8")) > 800
                or len(self.quote) != self.end - self.start):
            raise InvalidInput("invalid_memory_source")
        from datetime import datetime
        try:
            if datetime.fromisoformat(self.created_at).tzinfo is None:
                raise ValueError()
        except (ValueError, TypeError):
            raise InvalidInput("invalid_memory_source") from None


@dataclass(frozen=True)
class ContextPlan:
    """Prepared by the future server ContextBuilder against a chat revision.

    Storage verifies the message identities, ordering and supplied budget. The
    tokenizer/template calculation itself belongs to stage 3, not this class.
    """

    history_message_ids: tuple[str, ...] = ()
    input_token_upper_bound: int = 0
    policy_version: str = "recent-complete-pairs-v1"
    model_identity: ModelIdentity | None = None
    memory_enabled: bool = False
    memory_sources: tuple[MemorySource, ...] = ()
    memory_indexed_messages: int = 0
    memory_search_seconds: float = 0
    memory_policy: str = ""

    def validate(self, profile):
        profile.validate()
        if self.model_identity is not None:
            if not isinstance(self.model_identity, ModelIdentity):
                raise InvalidInput("invalid_model_identity")
            self.model_identity.validate(profile)
        if (type(self.history_message_ids) is not tuple
                or any(not isinstance(x, str) for x in self.history_message_ids)
                or len(set(self.history_message_ids)) != len(self.history_message_ids)
                or not integer(self.input_token_upper_bound, 1)
                or type(self.memory_enabled) is not bool
                or self.policy_version != ("recent-complete-pairs-memory-v1" if self.memory_enabled
                                           else "recent-complete-pairs-v1")):
            raise InvalidInput("invalid_context_plan")
        if (type(self.memory_sources) is not tuple or len(self.memory_sources) > 3
                or not integer(self.memory_indexed_messages)
                or type(self.memory_search_seconds) not in (int, float)
                or not math.isfinite(self.memory_search_seconds) or self.memory_search_seconds < 0
                or not isinstance(self.memory_policy, str)
                or (self.memory_enabled and (not self.memory_policy or len(self.memory_policy) > 64
                    or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in self.memory_policy)))
                or (not self.memory_enabled and (self.memory_sources or self.memory_indexed_messages
                                                or self.memory_search_seconds or self.memory_policy))):
            raise InvalidInput("invalid_context_plan")
        for source in self.memory_sources:
            if not isinstance(source, MemorySource):
                raise InvalidInput("invalid_memory_source")
            source.validate()
        if len({source.message_id for source in self.memory_sources}) != len(self.memory_sources):
            raise InvalidInput("invalid_memory_source")
        if self.input_token_upper_bound + profile.max_output + profile.margin > profile.num_ctx:
            raise InvalidInput("context_budget_exceeded")


@dataclass(frozen=True)
class QueueLimits:
    queued: int = 8
    per_user_outstanding: int = 3

    def validate(self):
        if not integer(self.queued, 1) or not integer(self.per_user_outstanding, 1):
            raise InvalidInput("invalid_queue_limits")


@dataclass(frozen=True)
class Receipt:
    chat_id: str
    accepted_revision: int
    user_message_id: str | None = None
    assistant_message_id: str | None = None
    generation_id: str | None = None
    replayed: bool = False
