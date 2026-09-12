"""Локальное сравнение короткого, длинного и переполненного диалогов."""

from dataclasses import dataclass

from agent import SYSTEM_PROMPT
from tokens import (
    MAX_COMPLETION_TOKENS,
    GptOssTokenCounter,
    estimate_request_cost,
)


MISSION_ENTRY = (
    "Экипаж проверил двигатель, запас кислорода, навигацию и связь. "
    "Все результаты добавлены в журнал экспедиции для следующего решения."
)


@dataclass(frozen=True)
class Scenario:
    """Один искусственно подготовленный размер истории."""

    name: str
    exchange_count: int


def build_history(exchange_count: int) -> list[dict[str, str]]:
    """Создаёт историю без API-вызовов и денежных расходов."""

    history: list[dict[str, str]] = []
    for number in range(1, exchange_count + 1):
        history.extend(
            [
                {
                    "role": "user",
                    "content": f"Запись {number}. {MISSION_ENTRY}",
                },
                {
                    "role": "assistant",
                    "content": (
                        f"Запись {number} принята. Системы работают штатно. "
                        f"{MISSION_ENTRY}"
                    ),
                },
            ]
        )
    return history


def print_scenario(
    scenario: Scenario,
    counter: GptOssTokenCounter,
) -> None:
    """Печатает размер и ожидаемую стоимость следующего запроса."""

    history = build_history(scenario.exchange_count)
    estimate = counter.estimate_context(
        system_prompt=SYSTEM_PROMPT,
        history=history,
        current_input="Подготовь краткий отчёт о состоянии экспедиции.",
    )
    cost = estimate_request_cost(
        prompt_tokens=estimate.prompt_tokens,
        completion_tokens=MAX_COMPLETION_TOKENS,
    )
    status = "помещается" if estimate.fits_context_window else "ПЕРЕПОЛНЕН"

    print(f"\n{scenario.name}")
    print("-" * 70)
    print(f"Завершённых обменов в истории: {scenario.exchange_count:,}")
    print(f"Токенов истории: {estimate.history_tokens:,}")
    print(f"Токенов следующего prompt: {estimate.prompt_tokens:,}")
    print(f"Резерв ответа: {estimate.reserved_completion_tokens:,}")
    print(f"Prompt + резерв: {estimate.total_reserved_tokens:,}")
    print(f"Лимит модели: {estimate.context_window:,}")
    print(f"Состояние: {status}")
    print(f"Стоимость при ответе на весь резерв: ${cost:.6f}")

    if not estimate.fits_context_window:
        print(
            "Что ломается: модель не сможет обработать запрос. "
            "BublikAgent остановит его до вызова Groq, иначе API вернёт ошибку "
            "из-за превышения контекстного окна."
        )


def main() -> None:
    """Запускает три воспроизводимых сценария без обращения к Groq."""

    counter = GptOssTokenCounter()
    scenarios = [
        Scenario("КОРОТКИЙ ДИАЛОГ", exchange_count=1),
        Scenario("ДЛИННЫЙ ДИАЛОГ", exchange_count=100),
        Scenario("ДИАЛОГ ВЫШЕ ЛИМИТА", exchange_count=1_500),
    ]

    print("День 8 — влияние истории на токены и стоимость")
    for scenario in scenarios:
        print_scenario(scenario, counter)


if __name__ == "__main__":
    main()
