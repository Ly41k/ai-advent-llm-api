"""Агент Бублик с контролем токенов и стоимости."""

from dataclasses import dataclass

from groq import Groq

from memory import ConversationUsage, Message, SQLiteContextRepository
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
    "Корабль находится в длительной экспедиции в дальних галактиках. "
    "Учитывай восстановленную историю миссии и ранее принятые решения. "
    "Чётко отделяй известные данные от предположений. "
    "Если информации недостаточно, сообщи, какие данные нужны. "
    "Отвечай капитану на русском языке."
)


class AgentError(RuntimeError):
    """Ошибка обработки запроса агентом."""


class ContextWindowExceededError(AgentError):
    """Полный запрос не помещается в контекстное окно модели."""


@dataclass(frozen=True)
class AgentResponse:
    """Ответ агента вместе с метриками использованных токенов."""

    content: str
    usage: RequestTokenUsage


class BublikAgent:
    """Собирает контекст из SQLite и выполняет запрос к LLM."""

    def __init__(
        self,
        client: Groq,
        memory: SQLiteContextRepository,
        conversation_id: str,
        model: str = MODEL_NAME,
        token_counter: GptOssTokenCounter | None = None,
        context_window: int = MODEL_CONTEXT_WINDOW,
        max_completion_tokens: int = MAX_COMPLETION_TOKENS,
    ) -> None:
        self._client = client
        self._memory = memory
        self._conversation_id = conversation_id
        self._model = model
        self._token_counter = token_counter or GptOssTokenCounter()
        self._context_window = context_window
        self._max_completion_tokens = max_completion_tokens

        if not self._memory.conversation_exists(self._conversation_id):
            raise AgentError("Выбранный диалог не найден")

    @property
    def restored_message_count(self) -> int:
        """Количество сообщений, найденных в памяти при текущем запуске."""

        return self._memory.get_completed_message_count(self._conversation_id)

    def process(self, user_input: str) -> AgentResponse:
        """Обрабатывает запрос и сохраняет завершённый обмен сообщениями."""

        prepared_input = self._prepare_input(user_input)
        history = self._get_history_context()
        estimate = self._token_counter.estimate_context(
            system_prompt=SYSTEM_PROMPT,
            history=history,
            current_input=prepared_input,
            reserved_completion_tokens=self._max_completion_tokens,
            context_window=self._context_window,
        )
        if not estimate.fits_context_window:
            raise ContextWindowExceededError(
                "Контекст переполнен: требуется "
                f"{estimate.total_reserved_tokens:,} токенов, "
                f"лимит модели — {estimate.context_window:,}. "
                f"Превышение — {-estimate.remaining_tokens:,} токенов."
            )

        user_message_id = self._memory.start_user_request(
            conversation_id=self._conversation_id,
            content=prepared_input,
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=self._build_context(history, prepared_input),
                temperature=0.7,
                reasoning_effort="low",
                max_completion_tokens=self._max_completion_tokens,
            )
            raw_response = response.choices[0].message.content or ""
            agent_response = self._prepare_output(raw_response)
            usage = self._token_counter.build_usage(
                estimate=estimate,
                response_text=agent_response,
                api_prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

            self._memory.complete_exchange(
                user_message_id=user_message_id,
                conversation_id=self._conversation_id,
                assistant_content=agent_response,
                usage=usage,
            )
            return AgentResponse(content=agent_response, usage=usage)
        except Exception as error:
            self._memory.fail_request(user_message_id, str(error))
            if isinstance(error, AgentError):
                raise
            raise AgentError(f"Не удалось получить ответ LLM: {error}") from error

    def get_history(self, limit: int = 20) -> list[Message]:
        """Возвращает последние сообщения сохранённого журнала."""

        return self._memory.get_history(self._conversation_id, limit)

    def get_conversation_usage(self) -> ConversationUsage:
        """Возвращает накопленные API-метрики выбранного диалога."""

        return self._memory.get_conversation_usage(self._conversation_id)

    def _get_history_context(self) -> list[dict[str, str]]:
        restored_messages = self._memory.get_context_messages(self._conversation_id)
        return [
            {"role": message.role, "content": message.content}
            for message in restored_messages
        ]

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
