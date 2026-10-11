"""Application admission, with an authenticated principal supplied by future HTTP."""
import asyncio

from .domain import Conflict
from .inference.context import ContextBuilder
from .memory import HistorySearch, MemoryRetriever


class ChatService:
    def __init__(self, repository, adapter, notify=lambda: None, *, memory: HistorySearch | None = None):
        self.repository, self.adapter, self.notify = repository, adapter, notify
        self.memory = memory if memory is not None else MemoryRetriever(repository)

    async def send(self, owner, chat, content, *, expected_revision, key, use_memory=False):
        replay = await asyncio.to_thread(self.repository.replay_message, owner, chat, content,
                                        expected_revision=expected_revision, key=key, use_memory=use_memory)
        if replay:
            return replay
        candidates = await asyncio.to_thread(self.repository.context_candidates, owner, chat, limit_turns=100)
        if candidates["revision"] != expected_revision:
            raise Conflict("stale_revision")
        if (await asyncio.to_thread(self.repository.queue_status))["inference_recovery_required"]:
            raise Conflict("inference_recovery_required")
        doctor = await self.adapter.doctor()
        memory = await asyncio.to_thread(self.memory.search, owner, content) if use_memory else None
        context = ContextBuilder(self.adapter.profile, doctor.identity).build(candidates, content, memory=memory)
        receipt = await asyncio.to_thread(self.repository.accept_message, owner, chat, content,
            expected_revision=expected_revision, key=key, context=context, profile=self.adapter.profile)
        self.notify()
        return receipt

    async def retry(self, owner, message, *, expected_revision, key, use_memory=False):
        replay = await asyncio.to_thread(self.repository.replay_retry, owner, message,
                                        expected_revision=expected_revision, key=key, use_memory=use_memory)
        if replay:
            return replay
        original = await asyncio.to_thread(self.repository.retry_candidate, owner, message)
        candidates = await asyncio.to_thread(self.repository.context_candidates, owner, original["chat_id"], limit_turns=100)
        if candidates["revision"] != expected_revision:
            raise Conflict("stale_revision")
        if (await asyncio.to_thread(self.repository.queue_status))["inference_recovery_required"]:
            raise Conflict("inference_recovery_required")
        doctor = await self.adapter.doctor()
        memory = await asyncio.to_thread(self.memory.search, owner, original["content"],
                                        exclude_message=message) if use_memory else None
        plan = ContextBuilder(self.adapter.profile, doctor.identity).build(candidates, original["content"], memory=memory)
        receipt = await asyncio.to_thread(self.repository.retry_message, owner, message,
            expected_revision=expected_revision, key=key, context=plan, profile=self.adapter.profile)
        self.notify()
        return receipt
