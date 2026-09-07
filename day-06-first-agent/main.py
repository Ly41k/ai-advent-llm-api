"""Консольный интерфейс бортового компьютера Бублик."""

import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from agent import AgentError, BublikAgent
from memory import SQLiteConversationRepository


def print_history(agent: BublikAgent) -> None:
    """Выводит последние сохранённые сообщения экспедиции."""

    history = agent.get_history()
    if not history:
        print("\nЖурнал экспедиции пока пуст.\n")
        return

    print("\n" + "=" * 70)
    print("ЖУРНАЛ ЭКСПЕДИЦИИ")
    print("=" * 70)

    for message in history:
        author = "Чебуратор" if message.role == "user" else "Бублик"
        status = "" if message.status == "completed" else f" [{message.status}]"
        print(f"{author}{status}: {message.content}")

    print()


def main() -> None:
    """Создаёт зависимости и запускает интерактивный цикл CLI."""

    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Переменная GROQ_API_KEY не найдена. "
            "Добавьте API-ключ в файл .env"
        )

    current_directory = Path(__file__).resolve().parent
    database_path = current_directory / "data" / "bublik.db"

    memory = SQLiteConversationRepository(database_path)
    agent = BublikAgent(
        client=Groq(api_key=api_key),
        memory=memory,
    )

    print("🤖 Бортовой компьютер исследовательского корабля «Бублик»")
    print("Экспедиция в дальние галактики продолжается.")
    print("Команды: /history — журнал, /exit — завершить сеанс.\n")

    while True:
        user_input = input("Чебуратор: ").strip()

        if user_input.lower() in {"/exit", "выход"}:
            print("Бублик: Сеанс завершён. Журнал экспедиции сохранён.")
            break

        if user_input.lower() == "/history":
            print_history(agent)
            continue

        try:
            response = agent.process(user_input)
            print(f"Бублик: {response}\n")
        except AgentError as error:
            print(f"Ошибка агента: {error}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nОшибка запуска программы: {error}\n")
