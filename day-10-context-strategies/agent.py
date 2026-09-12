"""Агент Бублик с переключаемыми стратегиями управления контекстом."""

from dataclasses import dataclass

from groq import Groq

from facts import FactsExtractor
from memory import (
    Branch,
    Checkpoint,
    ConversationUsage,
    Fact,
    Message,
    SQLiteContextRepository,
)
from strategies import StrategyName, create_strategy
from tokens import (
    GptOssTokenCounter,
    MAX_COMPLETION_TOKENS,
    MODEL_CONTEXT_WINDOW,
    MODEL_NAME,
    RequestTokenUsage,
)


SYSTEM_PROMPT = (
    "Ты автономный бортовой компьютер исследовательского космического "
    "корабля по имени Бублик. Пользователя зовут Чебуратор, он капитан. "
    "Всё происходящее является вымышленной исследовательской симуляцией. "
    "Помогай собирать требования к экспедиции и кораблю. Факты и решения "
    "из переданного контекста считай каноном. Не утверждай, что помнишь "
    "детали, которых нет в текущем контексте. Недостающие данные обозначай "
    "как допущения. Отвечай капитану на русском языке."
)


class AgentError(RuntimeError):
    pass


class ContextWindowExceededError(AgentError):
    pass


@dataclass(frozen=True)
class AgentResponse:
    content: str
    strategy: StrategyName
    branch_name: str
    usage: RequestTokenUsage


class BublikAgent:
    def __init__(
        self,
        client: Groq,
        memory: SQLiteContextRepository,
        conversation_id: str,
        model: str = MODEL_NAME,
        token_counter: GptOssTokenCounter | None = None,
        context_window: int = MODEL_CONTEXT_WINDOW,
        max_completion_tokens: int = MAX_COMPLETION_TOKENS,
        facts_extractor: FactsExtractor | None = None,
    ) -> None:
        self._client = client
        self._memory = memory
        self._conversation_id = conversation_id
        self._model = model
        self._token_counter = token_counter or GptOssTokenCounter()
        self._context_window = context_window
        self._max_completion_tokens = max_completion_tokens
        self._facts_extractor = facts_extractor or FactsExtractor(client, model)
        if self._memory.get_conversation(conversation_id) is None:
            raise AgentError("Выбранный диалог не найден")

    @property
    def strategy_name(self) -> StrategyName:
        return StrategyName(self._conversation().strategy)

    @property
    def active_branch(self) -> Branch:
        return self._memory.get_active_branch(self._conversation_id)

    @property
    def restored_message_count(self) -> int:
        return len(self._memory.get_branch_history(self.active_branch.id))

    def process(self, user_input: str) -> AgentResponse:
        prepared_input = self._prepare_input(user_input)
        branch = self.active_branch
        strategy_name = self.strategy_name
        full_history = self._memory.get_branch_history(branch.id)
        full_api_history = self._to_api_messages(full_history)
        full_history_tokens = self._token_counter.count_messages(full_api_history)

        user_message_id = self._memory.start_user_request(
            self._conversation_id,
            branch.id,
            prepared_input,
        )
        try:
            if strategy_name is StrategyName.STICKY_FACTS:
                update = self._facts_extractor.update(
                    self._memory.get_facts(self._conversation_id),
                    prepared_input,
                )
                self._memory.replace_facts(
                    self._conversation_id,
                    update.facts,
                    user_message_id,
                    update.usage,
                )

            context = create_strategy(strategy_name).build(
                full_history,
                self._memory.get_facts(self._conversation_id),
            )
            estimate = self._token_counter.estimate_context(
                SYSTEM_PROMPT,
                context,
                prepared_input,
                self._max_completion_tokens,
                self._context_window,
            )
            if not estimate.fits_context_window:
                raise ContextWindowExceededError(
                    "Контекст стратегии не помещается в окно модели: "
                    f"{estimate.total_reserved_tokens:,} > {estimate.context_window:,}"
                )

            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    *context,
                    {"role": "user", "content": prepared_input},
                ],
                temperature=0.2,
                reasoning_effort="low",
                max_completion_tokens=self._max_completion_tokens,
            )
            content = self._prepare_output(response.choices[0].message.content or "")
            usage = self._token_counter.build_usage(
                estimate,
                content,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                response.usage.total_tokens,
                full_history_tokens,
            )
            self._memory.complete_exchange(
                user_message_id,
                self._conversation_id,
                branch.id,
                strategy_name.value,
                content,
                usage,
            )
            return AgentResponse(content, strategy_name, branch.name, usage)
        except Exception as error:
            self._memory.fail_request(user_message_id, str(error))
            if isinstance(error, AgentError):
                raise
            raise AgentError(f"Не удалось обработать запрос: {error}") from error

    def set_strategy(self, strategy: StrategyName | str) -> StrategyName:
        strategy_name = StrategyName(strategy)
        self._memory.set_strategy(self._conversation_id, strategy_name.value)
        return strategy_name

    def get_context_preview(self) -> list[dict[str, str]]:
        history = self._memory.get_branch_history(self.active_branch.id)
        return create_strategy(self.strategy_name).build(
            history,
            self._memory.get_facts(self._conversation_id),
        )

    def get_history(self) -> list[Message]:
        return self._memory.get_history(self.active_branch.id)

    def get_facts(self) -> list[Fact]:
        return self._memory.get_facts(self._conversation_id)

    def create_checkpoint(self, name: str) -> Checkpoint:
        return self._memory.create_checkpoint(self._conversation_id, name)

    def get_checkpoints(self) -> list[Checkpoint]:
        return self._memory.get_checkpoints(self._conversation_id)

    def create_branch(self, name: str, checkpoint_name: str) -> Branch:
        if self.strategy_name is not StrategyName.BRANCHING:
            raise AgentError("Ветки доступны только в стратегии branching")
        return self._memory.create_branch(
            self._conversation_id,
            name,
            checkpoint_name,
        )

    def get_branches(self) -> list[Branch]:
        return self._memory.get_branches(self._conversation_id)

    def switch_branch(self, name: str) -> Branch:
        if self.strategy_name is not StrategyName.BRANCHING:
            raise AgentError("Ветки доступны только в стратегии branching")
        return self._memory.switch_branch(self._conversation_id, name)

    def get_usage(self) -> ConversationUsage:
        return self._memory.get_conversation_usage(self._conversation_id)

    def _conversation(self):
        conversation = self._memory.get_conversation(self._conversation_id)
        if conversation is None:
            raise AgentError("Диалог не найден")
        return conversation

    @staticmethod
    def _to_api_messages(messages: list[Message]) -> list[dict[str, str]]:
        return [
            {"role": message.role, "content": message.content}
            for message in messages
        ]

    @staticmethod
    def _prepare_input(value: str) -> str:
        prepared = value.strip()
        if not prepared:
            raise AgentError("Запрос не может быть пустым")
        return prepared

    @staticmethod
    def _prepare_output(value: str) -> str:
        prepared = value.strip()
        if not prepared:
            raise AgentError("Модель вернула пустой ответ")
        return prepared
