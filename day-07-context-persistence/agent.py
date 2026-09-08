"""Агент Бублик с восстановлением контекста после перезапуска."""

from groq import Groq

from memory import Message, SQLiteContextRepository


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


class BublikAgent:
    """Собирает контекст из SQLite и выполняет запрос к LLM."""

    def __init__(
        self,
        client: Groq,
        memory: SQLiteContextRepository,
        conversation_id: str,
        model: str = "openai/gpt-oss-20b",
        context_message_limit: int = 20,
    ) -> None:
        self._client = client
        self._memory = memory
        self._conversation_id = conversation_id
        self._model = model
        self._context_message_limit = context_message_limit

        if not self._memory.conversation_exists(self._conversation_id):
            raise AgentError("Выбранный диалог не найден")

    @property
    def restored_message_count(self) -> int:
        """Количество сообщений, найденных в памяти при текущем запуске."""

        return self._memory.get_completed_message_count(self._conversation_id)

    def process(self, user_input: str) -> str:
        """Обрабатывает запрос и сохраняет завершённый обмен сообщениями."""

        prepared_input = self._prepare_input(user_input)
        user_message_id = self._memory.start_user_request(
            conversation_id=self._conversation_id,
            content=prepared_input,
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=self._build_context(prepared_input),
                temperature=1.4,
                reasoning_effort="low",
                max_completion_tokens=1200,
            )
            raw_response = response.choices[0].message.content or ""
            agent_response = self._prepare_output(raw_response)

            self._memory.complete_exchange(
                user_message_id=user_message_id,
                conversation_id=self._conversation_id,
                assistant_content=agent_response,
            )
            return agent_response
        except Exception as error:
            self._memory.fail_request(user_message_id, str(error))
            if isinstance(error, AgentError):
                raise
            raise AgentError(f"Не удалось получить ответ LLM: {error}") from error

    def get_history(self, limit: int = 20) -> list[Message]:
        """Возвращает последние сообщения сохранённого журнала."""

        return self._memory.get_history(self._conversation_id, limit)

    def _build_context(self, current_input: str) -> list[dict[str, str]]:
        restored_messages = self._memory.get_context_messages(
            conversation_id=self._conversation_id,
            limit=self._context_message_limit,
        )

        context = [{"role": "system", "content": SYSTEM_PROMPT}]
        context.extend(
            {"role": message.role, "content": message.content}
            for message in restored_messages
        )
        context.append({"role": "user", "content": current_input})
        return context

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
