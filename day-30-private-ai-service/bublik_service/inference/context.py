"""Conservative byte-BPE bound for a single reviewed Qwen2.5 ChatML template."""
from bublik_service.domain import ContextPlan, InvalidInput, MemorySource
from bublik_service.memory import memory_messages
from bublik_service.languages import system_prompt_for_reply, user_content_for_reply
from bublik_service.storage.repository import MAX_MESSAGE_BYTES, text

# Published Ollama qwen2.5:14b template, eb4402837c78 (full normalized SHA-256).
# Unknown templates are NOT accepted by similarity or substring checks.
TEMPLATE_SHA256 = "eb4402837c7829a690fa845de4d7f3fd842c2adee476d5341da8a46ea9255175"


def upper_bound(messages):
    """Qwen byte BPE cannot emit more tokens than UTF-8 bytes of the input.

    This is not bytes/4 estimation. 128 per message bounds the reviewed no-tools
    ChatML control/role/newline overhead; 128 more bounds assistant prefix/BOS.
    Embedded special-token spellings only make this count more conservative.
    Applicability is enforced by doctor (template + tokenizer metadata).
    """
    return 128 + sum(len(m["content"].encode("utf-8")) + 128 for m in messages)


class ContextBuilder:
    def __init__(self, profile, identity):
        profile.validate()
        identity.validate(profile)
        if identity.template_sha256 != TEMPLATE_SHA256:
            raise InvalidInput("unsupported_template")
        self.profile, self.identity = profile, identity

    def build(self, candidates, content, *, memory=None, reply_language=None):
        text(content, MAX_MESSAGE_BYTES, "invalid_message")
        history = candidates["messages"]
        if len(history) % 2:
            raise InvalidInput("invalid_context_candidates")
        base = [{"role": "system", "content": system_prompt_for_reply(self.profile, reply_language)},
                {"role": "user", "content": user_content_for_reply(content, reply_language)}]
        budget = self.profile.num_ctx - self.profile.max_output - self.profile.margin
        if upper_bound(base) > budget:
            raise InvalidInput("context_budget_exceeded")
        sources, extra = [], []
        if memory is not None:
            for value in memory["sources"]:
                source = MemorySource(**value)
                source.validate()
                trial = memory_messages([*sources, source])
                if (upper_bound(trial) <= 2600
                        and upper_bound([base[0], *trial, base[1]]) <= budget):
                    sources.append(source)
            extra = memory_messages(sources)
            if upper_bound([base[0], *extra, base[1]]) > budget:
                # Memory mode must not silently become a normal ungrounded request.
                raise InvalidInput("context_budget_exceeded")
        selected = []
        for offset in range(len(history) - 2, -1, -2):
            pair = history[offset:offset + 2]
            trial = [base[0], *extra, *pair, *selected, base[1]]
            if upper_bound(trial) > budget:
                break
            selected = pair + selected
        messages = [base[0], *extra, *selected, base[1]]
        return ContextPlan(tuple(m["id"] for m in selected), upper_bound(messages),
                           policy_version="recent-complete-pairs-memory-v1" if memory is not None else "recent-complete-pairs-v1",
                           model_identity=self.identity, memory_enabled=memory is not None,
                           memory_sources=tuple(sources),
                           memory_indexed_messages=memory["indexed_messages"] if memory is not None else 0,
                           memory_search_seconds=memory["search_seconds"] if memory is not None else 0,
                           memory_policy=memory["policy_version"] if memory is not None else "",
                           reply_language=reply_language)
