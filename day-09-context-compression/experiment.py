"""Локальное сравнение полного и сжатого контекста без API-вызовов."""

from dataclasses import dataclass

from agent import SUMMARY_CONTEXT_PREFIX, SYSTEM_PROMPT
from compression import RECENT_MESSAGES_LIMIT
from tokens import (
    MAX_COMPLETION_TOKENS,
    GptOssTokenCounter,
    estimate_request_cost,
)


MISSION_ENTRY = (
    "Экипаж проверил двигатель, кислород, навигацию и связь. "
    "Системы работают штатно, новых рисков не обнаружено."
)
CURRENT_REQUEST = "Подготовь краткий отчёт о состоянии экспедиции."


@dataclass(frozen=True)
class Scenario:
    name: str
    exchange_count: int


def build_history(exchange_count: int) -> list[dict[str, str]]:
    """Создаёт повторяемую полную историю заданного размера."""

    history: list[dict[str, str]] = []
    for number in range(1, exchange_count + 1):
        history.extend(
            (
                {
                    "role": "user",
                    "content": f"Проверка {number}. {MISSION_ENTRY}",
                },
                {
                    "role": "assistant",
                    "content": (
                        f"Проверка {number} внесена в журнал. "
                        "Все показатели подтверждены."
                    ),
                },
            )
        )
    return history


def compress_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    """Имитирует сохранённый summary плюс последние N сообщений."""

    if len(history) <= RECENT_MESSAGES_LIMIT:
        return history

    summarized_count = len(history) - RECENT_MESSAGES_LIMIT
    summary = (
        f"Сжато {summarized_count} ранних сообщений. Экипаж выполнял "
        "регулярные проверки двигателя, кислорода, навигации и связи. "
        "Все системы работали штатно, новых рисков и незакрытых вопросов нет."
    )
    return [
        {"role": "system", "content": SUMMARY_CONTEXT_PREFIX + summary},
        *history[-RECENT_MESSAGES_LIMIT:],
    ]


def print_scenario(scenario: Scenario, counter: GptOssTokenCounter) -> None:
    """Печатает разницу токенов и максимальной стоимости запроса."""

    full_history = build_history(scenario.exchange_count)
    compressed_history = compress_history(full_history)
    full = counter.estimate_context(
        SYSTEM_PROMPT,
        full_history,
        CURRENT_REQUEST,
    )
    compressed = counter.estimate_context(
        SYSTEM_PROMPT,
        compressed_history,
        CURRENT_REQUEST,
    )
    saved_tokens = full.prompt_tokens - compressed.prompt_tokens
    saved_percent = saved_tokens / full.prompt_tokens * 100
    full_cost = estimate_request_cost(
        full.prompt_tokens,
        MAX_COMPLETION_TOKENS,
    )
    compressed_cost = estimate_request_cost(
        compressed.prompt_tokens,
        MAX_COMPLETION_TOKENS,
    )

    print(f"\n{scenario.name}")
    print("-" * 70)
    print(f"Сообщений в полной истории: {len(full_history):,}")
    print(f"Без сжатия: {full.prompt_tokens:,} prompt tokens")
    print(f"Со сжатием: {compressed.prompt_tokens:,} prompt tokens")
    print(f"Экономия: {saved_tokens:,} токенов ({saved_percent:.1f}%)")
    print(f"Стоимость без сжатия: ${full_cost:.6f}")
    print(f"Стоимость со сжатием: ${compressed_cost:.6f}")


def main() -> None:
    """Сравнивает три размера истории без обращения к Groq."""

    counter = GptOssTokenCounter()
    scenarios = [
        Scenario("КОРОТКИЙ ДИАЛОГ", 5),
        Scenario("СРЕДНИЙ ДИАЛОГ", 15),
        Scenario("ДЛИННЫЙ ДИАЛОГ", 100),
    ]
    print("День 9 — экономия токенов после сжатия истории")
    for scenario in scenarios:
        print_scenario(scenario, counter)


if __name__ == "__main__":
    main()
