"""Одинаковый live-сценарий для сравнения трёх стратегий через Groq."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import load_dotenv
from groq import Groq

from agent import BublikAgent
from memory import SQLiteContextRepository
from strategies import StrategyName


SCENARIO = [
    "Собираем ТЗ исследовательского корабля для экспедиции на 10 лет.",
    "Главная цель — исследовать неизвестные планеты, а не участвовать в боях.",
    "Экипаж состоит из 12 человек.",
    "Запас автономности без пополнения должен составлять минимум 18 месяцев.",
    "Выбираем два ионных маршевых двигателя.",
    "Ограничение массы корабля — 900 тонн.",
    "Приоритет — надёжность, затем скорость, затем стоимость.",
    "Добавляем лабораторию на четыре рабочих места.",
    "Отказываемся от тяжёлого вооружения, оставляем только защитные системы.",
    "Бюджет проекта ограничен 240 миллионами кредитов.",
    "Срок постройки — не более трёх лет.",
]
FINAL_REQUEST = (
    "Подготовь итоговое ТЗ. Перечисли цель, числовые ограничения, "
    "выбранные решения и приоритеты. Ничего не выдумывай."
)


def run_linear_strategy(
    client: Groq,
    memory: SQLiteContextRepository,
    strategy: StrategyName,
) -> tuple[str, int, float]:
    conversation = memory.create_conversation(f"experiment-{strategy.value}", strategy.value)
    agent = BublikAgent(client, memory, conversation.id)
    for prompt in SCENARIO:
        agent.process(prompt)
    result = agent.process(FINAL_REQUEST)
    usage = agent.get_usage()
    return (
        result.content,
        usage.total_tokens + usage.fact_update_tokens,
        usage.estimated_cost_usd + usage.fact_update_cost_usd,
    )


def run_branching_strategy(
    client: Groq,
    memory: SQLiteContextRepository,
) -> tuple[str, int, float]:
    conversation = memory.create_conversation("experiment-branching", "branching")
    agent = BublikAgent(client, memory, conversation.id)
    for prompt in SCENARIO[:7]:
        agent.process(prompt)
    agent.create_checkpoint("base-requirements")
    agent.create_branch("research", "base-requirements")
    agent.create_branch("economy", "base-requirements")

    agent.switch_branch("research")
    for prompt in SCENARIO[7:]:
        agent.process(prompt)
    research_result = agent.process(FINAL_REQUEST)

    agent.switch_branch("economy")
    agent.process("Для этой ветки минимизируем стоимость корабля.")
    economy_result = agent.process(
        "Назови цель и приоритеты только этой ветки без решений ветки research."
    )
    usage = agent.get_usage()
    content = (
        "ВЕТКА RESEARCH:\n"
        f"{research_result.content}\n\n"
        "ВЕТКА ECONOMY:\n"
        f"{economy_result.content}"
    )
    return content, usage.total_tokens, usage.estimated_cost_usd


def main() -> None:
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Добавьте GROQ_API_KEY в .env")
    client = Groq(api_key=api_key)
    with TemporaryDirectory() as temporary_directory:
        memory = SQLiteContextRepository(Path(temporary_directory) / "experiment.db")
        results = {
            StrategyName.SLIDING_WINDOW.value: run_linear_strategy(
                client, memory, StrategyName.SLIDING_WINDOW
            ),
            StrategyName.STICKY_FACTS.value: run_linear_strategy(
                client, memory, StrategyName.STICKY_FACTS
            ),
            StrategyName.BRANCHING.value: run_branching_strategy(client, memory),
        }

    for name, (answer, tokens, cost) in results.items():
        print("\n" + "=" * 70)
        print(name.upper())
        print("=" * 70)
        print(answer)
        print(f"\nВсе токены стратегии: {tokens:,}")
        print(f"Общая стоимость: ${cost:.8f}")

    print("\nКритерии ручной оценки:")
    print("1. Сохранены ли ранние цель, экипаж и автономность?")
    print("2. Сохранены ли все числа без подмены?")
    print("3. Не смешались ли решения двух веток?")
    print("4. Насколько естественно продолжать диалог пользователю?")


if __name__ == "__main__":
    main()
