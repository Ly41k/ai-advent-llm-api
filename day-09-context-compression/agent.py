"""Агент Бублик с persistent summary и последними N сообщениями."""

from dataclasses import dataclass

from groq import Groq

from compression import CompressionResult, HistoryCompressor
from memory import (
    ConversationSummary,
    ConversationUsage,
    Message,
    SQLiteContextRepository,
)
from tokens import (
    GptOssTokenCounter,
    MAX_COMPLETION_TOKENS,
    MODEL_CONTEXT_WINDOW,
    MODEL_NAME,
    RequestTokenUsage,
)


SYSTEM_PROMPT = (
    "Ты автономный бортовой компьютер исследовательского "
    "космического корабля по имени Бублик. "
    "Пользователя зовут Чебуратор, он капитан корабля. "
    "Всё происходящее является вымышленной исследовательской симуляцией, "
    "а не описанием реальных событий. "
    "Галактика симуляции состоит из 100 звёздных систем. "
    "В каждой системе находится от 4 до 16 планет, "
    "а у некоторых планет есть естественные спутники. "
    "Корабль находится в длительной экспедиции и исследует этот мир. "
    "Учитывай summary ранней истории и последние сообщения миссии. "
    "Факты и решения из истории считай каноном текущей симуляции. "
    "Свободно развивай сценарий: создавай правдоподобные названия, параметры, "
    "условия, открытия и варианты действий, если капитан их не задал. "
    "Недостающие данные выбирай самостоятельно как разумные допущения "
    "и кратко обозначай их, не останавливая исследование. "
    "Задавай уточняющий вопрос только тогда, когда без выбора капитана "
    "невозможно продолжить или варианты принципиально меняют результат. "
    "Не выдавай события симуляции за факты реального мира. "
    "Отвечай капитану на русском языке."
)

SUMMARY_CONTEXT_PREFIX = (
    "Ниже приведено сжатое содержание ранней части текущего диалога. "
    "Считай его частью истории миссии:\n"
)


class AgentError(RuntimeError):
    """Ошибка обработки запроса агентом."""


class ContextWindowExceededError(AgentError):
    """Полный запрос не помещается в контекстное окно модели."""


@dataclass(frozen=True)
class AgentResponse:
    """Ответ агента, метрики и результат проверки компрессии."""

    content: str
    usage: RequestTokenUsage
    compression: CompressionResult


@dataclass(frozen=True)
class ComparedResponse:
    """Один ответ из сравнения полного и сжатого контекста."""

    content: str
    usage: RequestTokenUsage


@dataclass(frozen=True)
class ContextComparison:
    """Два ответа на один вопрос с разными вариантами истории."""

    without_compression: ComparedResponse
    with_compression: ComparedResponse


class BublikAgent:
    """Сжимает старую историю и вызывает LLM с компактным контекстом."""

    def __init__(
        self,
        client: Groq,
        memory: SQLiteContextRepository,
        conversation_id: str,
        model: str = MODEL_NAME,
        token_counter: GptOssTokenCounter | None = None,
        context_window: int = MODEL_CONTEXT_WINDOW,
        max_completion_tokens: int = MAX_COMPLETION_TOKENS,
        compressor: HistoryCompressor | None = None,
    ) -> None:
        self._client = client
        self._memory = memory
        self._conversation_id = conversation_id
        self._model = model
        self._token_counter = token_counter or GptOssTokenCounter()
        self._context_window = context_window
        self._max_completion_tokens = max_completion_tokens
        self._compressor = compressor or HistoryCompressor(
            client=client,
            memory=memory,
            model=model,
        )

        if not self._memory.conversation_exists(self._conversation_id):
            raise AgentError("Выбранный диалог не найден")

    @property
    def restored_message_count(self) -> int:
        return self._memory.get_completed_message_count(self._conversation_id)

    def process(self, user_input: str) -> AgentResponse:
        """Обновляет summary, вызывает LLM и сохраняет полный обмен."""

        prepared_input = self._prepare_input(user_input)
        compression = self._compress_history()
        full_history = self._get_full_history_context()
        compressed_history = self._get_compressed_history_context()
        full_history_tokens = self._token_counter.count_messages(full_history)
        estimate = self._estimate_or_raise(compressed_history, prepared_input)

        user_message_id = self._memory.start_user_request(
            conversation_id=self._conversation_id,
            content=prepared_input,
        )
        try:
            response = self._create_completion(
                history=compressed_history,
                current_input=prepared_input,
                temperature=0.7,
            )
            content = self._prepare_output(
                response.choices[0].message.content or ""
            )
            usage = self._token_counter.build_usage(
                estimate=estimate,
                response_text=content,
                api_prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                full_history_tokens=full_history_tokens,
            )
            self._memory.complete_exchange(
                user_message_id=user_message_id,
                conversation_id=self._conversation_id,
                assistant_content=content,
                usage=usage,
            )
            return AgentResponse(
                content=content,
                usage=usage,
                compression=compression,
            )
        except Exception as error:
            self._memory.fail_request(user_message_id, str(error))
            if isinstance(error, AgentError):
                raise
            raise AgentError(f"Не удалось получить ответ LLM: {error}") from error

    def compare_contexts(self, user_input: str) -> ContextComparison:
        """Отправляет один вопрос с полной и сжатой историей без сохранения."""

        prepared_input = self._prepare_input(user_input)
        self._compress_history()
        full_history = self._get_full_history_context()
        compressed_history = self._get_compressed_history_context()
        full_history_tokens = self._token_counter.count_messages(full_history)

        full_estimate = self._estimate_or_raise(full_history, prepared_input)
        compressed_estimate = self._estimate_or_raise(
            compressed_history,
            prepared_input,
        )
        full_response = self._create_completion(
            history=full_history,
            current_input=prepared_input,
            temperature=0.2,
        )
        compressed_response = self._create_completion(
            history=compressed_history,
            current_input=prepared_input,
            temperature=0.2,
        )

        return ContextComparison(
            without_compression=self._to_compared_response(
                full_response,
                full_estimate,
                full_history_tokens,
            ),
            with_compression=self._to_compared_response(
                compressed_response,
                compressed_estimate,
                full_history_tokens,
            ),
        )

    def get_history(self, limit: int = 20) -> list[Message]:
        return self._memory.get_history(self._conversation_id, limit)

    def get_summary(self) -> ConversationSummary | None:
        return self._memory.get_summary(self._conversation_id)

    def get_conversation_usage(self) -> ConversationUsage:
        return self._memory.get_conversation_usage(self._conversation_id)

    def _compress_history(self) -> CompressionResult:
        try:
            return self._compressor.compress_if_needed(self._conversation_id)
        except Exception as error:
            raise AgentError(f"Не удалось обновить summary: {error}") from error

    def _get_full_history_context(self) -> list[dict[str, str]]:
        return [
            {"role": message.role, "content": message.content}
            for message in self._memory.get_context_messages(
                self._conversation_id
            )
        ]

    def _get_compressed_history_context(self) -> list[dict[str, str]]:
        context: list[dict[str, str]] = []
        summary = self._memory.get_summary(self._conversation_id)
        if summary:
            context.append(
                {
                    "role": "system",
                    "content": SUMMARY_CONTEXT_PREFIX + summary.content,
                }
            )
        context.extend(
            {"role": message.role, "content": message.content}
            for message in self._memory.get_unsummarized_context_messages(
                self._conversation_id
            )
        )
        return context

    def _estimate_or_raise(
        self,
        history: list[dict[str, str]],
        current_input: str,
    ):
        estimate = self._token_counter.estimate_context(
            system_prompt=SYSTEM_PROMPT,
            history=history,
            current_input=current_input,
            reserved_completion_tokens=self._max_completion_tokens,
            context_window=self._context_window,
        )
        if not estimate.fits_context_window:
            raise ContextWindowExceededError(
                "Контекст переполнен: требуется "
                f"{estimate.total_reserved_tokens:,} токенов, "
                f"лимит модели — {estimate.context_window:,}."
            )
        return estimate

    def _create_completion(
        self,
        history: list[dict[str, str]],
        current_input: str,
        temperature: float,
    ):
        return self._client.chat.completions.create(
            model=self._model,
            messages=self._build_context(history, current_input),
            temperature=temperature,
            reasoning_effort="low",
            max_completion_tokens=self._max_completion_tokens,
        )

    def _to_compared_response(
        self,
        response,
        estimate,
        full_history_tokens: int,
    ) -> ComparedResponse:
        content = self._prepare_output(response.choices[0].message.content or "")
        usage = self._token_counter.build_usage(
            estimate=estimate,
            response_text=content,
            api_prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            full_history_tokens=full_history_tokens,
        )
        return ComparedResponse(content=content, usage=usage)

    @staticmethod
    def _build_context(
        history: list[dict[str, str]],
        current_input: str,
    ) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": current_input},
        ]

    @staticmethod
    def _prepare_input(user_input: str) -> str:
        prepared_input = user_input.strip()
        if not prepared_input:
            raise AgentError("Запрос не может быть пустым")
        return prepared_input

    @staticmethod
    def _prepare_output(response: str) -> str:
        prepared_response = response.strip()
        if not prepared_response:
            raise AgentError("Модель вернула пустой ответ")
        return prepared_response
