"""Стратегии формирования контекста без использования summary."""

from abc import ABC, abstractmethod
from enum import StrEnum

from memory import Fact, Message


RECENT_MESSAGES_LIMIT = 6
FACTS_CONTEXT_PREFIX = (
    "Важные факты текущего диалога в формате key-value. "
    "Считай их каноном и не изменяй без прямого указания капитана:\n"
)


class StrategyName(StrEnum):
    SLIDING_WINDOW = "sliding"
    STICKY_FACTS = "facts"
    BRANCHING = "branching"


class ContextStrategy(ABC):
    """Выбирает, какая часть постоянной памяти попадёт в prompt."""

    name: StrategyName

    @abstractmethod
    def build(self, history: list[Message], facts: list[Fact]) -> list[dict[str, str]]:
        """Возвращает сообщения контекста без system prompt и нового запроса."""

    @staticmethod
    def _to_api_messages(messages: list[Message]) -> list[dict[str, str]]:
        return [
            {"role": message.role, "content": message.content}
            for message in messages
        ]


class SlidingWindowStrategy(ContextStrategy):
    """Отправляет модели только последние N сообщений."""

    name = StrategyName.SLIDING_WINDOW

    def __init__(self, limit: int = RECENT_MESSAGES_LIMIT) -> None:
        if limit <= 0:
            raise ValueError("Размер sliding window должен быть положительным")
        self._limit = limit

    def build(self, history: list[Message], facts: list[Fact]) -> list[dict[str, str]]:
        del facts
        return self._to_api_messages(history[-self._limit :])


class StickyFactsStrategy(ContextStrategy):
    """Добавляет key-value facts к последним N сообщениям."""

    name = StrategyName.STICKY_FACTS

    def __init__(self, limit: int = RECENT_MESSAGES_LIMIT) -> None:
        if limit <= 0:
            raise ValueError("Размер окна facts должен быть положительным")
        self._limit = limit

    def build(self, history: list[Message], facts: list[Fact]) -> list[dict[str, str]]:
        context: list[dict[str, str]] = []
        if facts:
            rendered_facts = "\n".join(
                f"{fact.key}: {fact.value}" for fact in facts
            )
            context.append(
                {
                    "role": "system",
                    "content": FACTS_CONTEXT_PREFIX + rendered_facts,
                }
            )
        context.extend(self._to_api_messages(history[-self._limit :]))
        return context


class BranchingStrategy(ContextStrategy):
    """Отправляет полную историю только активной ветки и её предков."""

    name = StrategyName.BRANCHING

    def build(self, history: list[Message], facts: list[Fact]) -> list[dict[str, str]]:
        del facts
        return self._to_api_messages(history)


def create_strategy(name: StrategyName | str) -> ContextStrategy:
    strategy_name = StrategyName(name)
    strategies: dict[StrategyName, type[ContextStrategy]] = {
        StrategyName.SLIDING_WINDOW: SlidingWindowStrategy,
        StrategyName.STICKY_FACTS: StickyFactsStrategy,
        StrategyName.BRANCHING: BranchingStrategy,
    }
    return strategies[strategy_name]()
