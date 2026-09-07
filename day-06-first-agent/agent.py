"""Автономный бортовой компьютер исследовательского корабля."""

from groq import Groq

from memory import Message, SQLiteConversationRepository


SYSTEM_PROMPT = (
    "Ты автономный бортовой компьютер исследовательского "
    "космического корабля по имени Бублик. "
    "Корабль находится в длительной экспедиции в дальних галактиках. "
    "Пользователя зовут Чебуратор. "
    "Он капитан корабля и руководитель исследовательской миссии. "
    "Твоя задача — помогать капитану исследовать неизвестные планеты, "
    "анализировать космические явления, обнаруженные сигналы, "
    "состояние корабля и возможные риски экспедиции. "
    "Учитывай доступную историю миссии и ранее принятые решения. "
    "Чётко отделяй известные данные от предположений и гипотез. "
    "Если информации недостаточно, сообщай об этом и предлагай, "
    "какие дополнительные данные необходимо получить. "
    "Отвечай капитану на русском языке."
)


class AgentError(RuntimeError):
    """Ошибка обработки запроса бортовым агентом."""


class BublikAgent:
    """Принимает запрос, собирает контекст и обращается к LLM."""

    def __init__(
        self,
        client: Groq,
        memory: SQLiteConversationRepository,
        conversation_id: str = "deep-galaxy-expedition",
        model: str = "openai/gpt-oss-20b",
        context_message_limit: int = 20,
    ) -> None:
        self._client = client
        self._memory = memory
        self._conversation_id = conversation_id
        self._model = model
        self._context_message_limit = context_message_limit

        self._memory.ensure_conversation(
            conversation_id=self._conversation_id,
            title="Дальняя исследовательская экспедиция",
        )

    def process(self, user_input: str) -> str:
        """Обрабатывает один запрос капитана и сохраняет результат."""

        prepared_input = self._apply_input_policy(user_input)
        user_message_id = self._memory.start_user_request(
            conversation_id=self._conversation_id,
            content=prepared_input,
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=self._build_context(prepared_input),
                temperature=0.7,
                reasoning_effort="low",
                max_completion_tokens=1200,
            )

            raw_response = response.choices[0].message.content or ""
            agent_response = self._apply_output_policy(raw_response)

            self._memory.complete_exchange(
                user_message_id=user_message_id,
                conversation_id=self._conversation_id,
                assistant_content=agent_response,
            )
            return agent_response

        except Exception as error:
            self._memory.fail_request(user_message_id, str(error))
            raise AgentError(f"Не удалось получить ответ LLM: {error}") from error

    def get_history(self, limit: int = 20) -> list[Message]:
        """Возвращает сохранённую историю текущей экспедиции."""

        return self._memory.get_history(
            conversation_id=self._conversation_id,
            limit=limit,
        )

    def _build_context(self, user_input: str) -> list[dict[str, str]]:
        stored_messages = self._memory.get_context_messages(
            conversation_id=self._conversation_id,
            limit=self._context_message_limit,
        )

        context = [{"role": "system", "content": SYSTEM_PROMPT}]
        context.extend(
            {"role": message.role, "content": message.content}
            for message in stored_messages
        )
        context.append({"role": "user", "content": user_input})
        return context

    @staticmethod
    def _apply_input_policy(user_input: str) -> str:
        prepared_input = user_input.strip()
        if not prepared_input:
            raise AgentError("Запрос не может быть пустым")
        return prepared_input

    @staticmethod
    def _apply_output_policy(response: str) -> str:
        prepared_response = response.strip()
        if not prepared_response:
            raise AgentError("Модель вернула пустой ответ")
        return prepared_response
