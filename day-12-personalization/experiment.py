"""Сравнение одного запроса с двумя пользовательскими профилями."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import load_dotenv
from groq import Groq

from agent import BublikAgent
from configuration import ConfigurationLoader
from memory import SQLiteMemoryRepository


QUESTION = (
    "Сравни исследование планеты с океаном и планеты с активными вулканами. "
    "Какую цель выбрать следующей?"
)


def create_agent(client, memory, configuration, profile_id: str) -> BublikAgent:
    conversation = memory.create_conversation(
        f"Эксперимент: {profile_id}", profile_id
    )
    agent = BublikAgent(client, memory, configuration, conversation.id)
    agent.create_task("Выбрать следующую научную цель")
    agent.set_plan(["Сравнить цели", "Оценить риск", "Предложить выбор"])
    agent.remember_working("ocean_risk", "низкий")
    agent.remember_working("volcano_risk", "высокий")
    return agent


def main() -> None:
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Добавьте GROQ_API_KEY в .env")
    directory = Path(__file__).resolve().parent
    configuration = ConfigurationLoader(directory / "config")
    client = Groq(api_key=api_key)

    with TemporaryDirectory() as temporary_directory:
        memory = SQLiteMemoryRepository(Path(temporary_directory) / "experiment.db")
        cheburator = create_agent(
            client, memory, configuration, "cheburator"
        ).process(QUESTION)
        scientist = create_agent(
            client, memory, configuration, "scientist"
        ).process(QUESTION)

    print("\nПРОФИЛЬ: ЧЕБУРАТОР — КРАТКО И ПО СУЩЕСТВУ")
    print("=" * 70)
    print(cheburator.content)
    print("\nПРОФИЛЬ: ДОКТОР ЛИРА — ПОДРОБНО И С ОЦЕНКОЙ РИСКОВ")
    print("=" * 70)
    print(scientist.content)
    print("\nПРОВЕРКА")
    print("=" * 70)
    print("Запрос и working memory одинаковы.")
    print("Первый ответ должен быть кратким, второй — подробным и структурированным.")
    print("Пользователь не повторяет предпочтения в самом запросе.")


if __name__ == "__main__":
    main()
