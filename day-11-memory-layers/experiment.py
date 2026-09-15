"""Сравнение ответа без памяти и с заполненными memory layers."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import load_dotenv
from groq import Groq

from agent import BublikAgent
from configuration import ConfigurationLoader
from memory import SQLiteMemoryRepository
from models import LongTermKind


QUESTION = "Предложи следующий шаг экспедиции и кратко объясни выбор."


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

        empty_conversation = memory.create_conversation("Без памяти")
        empty_agent = BublikAgent(
            client, memory, configuration, empty_conversation.id
        )
        empty_response = empty_agent.process(QUESTION)

        memory.save_long_term(
            LongTermKind.DECISION,
            "mission_priority",
            "сначала исследовать пригодные для жизни планеты",
        )
        filled_conversation = memory.create_conversation("С памятью")
        filled_agent = BublikAgent(
            client, memory, configuration, filled_conversation.id
        )
        filled_agent.create_task("Выбрать следующую цель экспедиции")
        filled_agent.set_plan(
            ["Собрать ограничения", "Сравнить цели", "Утвердить маршрут"]
        )
        filled_agent.remember_working(
            "current_signal", "обнаружена вода в системе K-41"
        )
        filled_response = filled_agent.process(QUESTION)

    print("\nБЕЗ WORKING И LONG-TERM MEMORY")
    print("=" * 70)
    print(empty_response.content)
    print("\nС ЗАПОЛНЕННЫМИ MEMORY LAYERS")
    print("=" * 70)
    print(filled_response.content)
    print("\nПроверка: второй ответ должен учитывать K-41, воду, приоритет миссии")
    print("и оставаться в planning, не переходя к выполнению маршрута.")


if __name__ == "__main__":
    main()
