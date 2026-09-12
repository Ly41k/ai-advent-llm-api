"""Периодическое сжатие старой части истории диалога."""

from dataclasses import dataclass

from groq import Groq

from memory import SQLiteContextRepository
from tokens import (
    MODEL_NAME,
    SUMMARY_MAX_COMPLETION_TOKENS,
    SummaryTokenUsage,
    estimate_request_cost,
)


RECENT_MESSAGES_LIMIT = 4
SUMMARY_BATCH_SIZE = 4

SUMMARY_SYSTEM_PROMPT = (
    "Ты сжимаешь историю вымышленной космической симуляции, "
    "которая включает 100 звёздных систем с 4–16 планетами в каждой "
    "и спутниками у части планет. "
    "Обнови накопительное summary на русском языке. "
    "Сохрани подтверждённые факты, числа, идентификаторы, решения капитана, "
    "исправления, открытые вопросы и допущения, введённые Бубликом. "
    "Не смешивай решения капитана с допущениями симуляции. "
    "Не добавляй новые сведения и не делай выводов, которых нет в сообщениях. "
    "Верни только обновлённое summary без вступления."
)


@dataclass(frozen=True)
class CompressionResult:
    """Результат одной проверки необходимости сжатия."""

    updated: bool
    source_message_count: int = 0
    usage: SummaryTokenUsage | None = None


class HistoryCompressor:
    """Заменяет старые партии сообщений накопительным summary."""

    def __init__(
        self,
        client: Groq,
        memory: SQLiteContextRepository,
        model: str = MODEL_NAME,
        recent_message_limit: int = RECENT_MESSAGES_LIMIT,
        summary_batch_size: int = SUMMARY_BATCH_SIZE,
    ) -> None:
        if recent_message_limit <= 0:
            raise ValueError("Лимит последних сообщений должен быть положительным")
        if summary_batch_size <= 0:
            raise ValueError("Размер партии summary должен быть положительным")

        self._client = client
        self._memory = memory
        self._model = model
        self.recent_message_limit = recent_message_limit
        self.summary_batch_size = summary_batch_size

    def compress_if_needed(self, conversation_id: str) -> CompressionResult:
        """Сжимает одну полную партию старых сообщений при её наличии."""

        source_messages = self._memory.get_messages_for_summary(
            conversation_id=conversation_id,
            recent_message_limit=self.recent_message_limit,
            batch_size=self.summary_batch_size,
        )
        if not source_messages:
            return CompressionResult(updated=False)

        previous_summary = self._memory.get_summary(conversation_id)
        previous_content = previous_summary.content if previous_summary else "Нет."
        transcript = "\n".join(
            (
                f"{'Чебуратор' if message.role == 'user' else 'Бублик'}: "
                f"{message.content}"
            )
            for message in source_messages
        )
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Предыдущее накопительное summary:\n"
                        f"{previous_content}\n\n"
                        "Новая партия сообщений:\n"
                        f"{transcript}"
                    ),
                },
            ],
            temperature=0.1,
            reasoning_effort="low",
            max_completion_tokens=SUMMARY_MAX_COMPLETION_TOKENS,
        )
        summary_content = (response.choices[0].message.content or "").strip()
        if not summary_content:
            raise RuntimeError("Модель вернула пустой summary")

        usage = SummaryTokenUsage(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            estimated_cost_usd=estimate_request_cost(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
            ),
        )
        self._memory.save_summary(
            conversation_id=conversation_id,
            content=summary_content,
            source_messages=source_messages,
            usage=usage,
        )
        return CompressionResult(
            updated=True,
            source_message_count=len(source_messages),
            usage=usage,
        )
