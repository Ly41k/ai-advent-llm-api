"""CLI агента с отображением токенов и стоимости диалога."""

import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from agent import AgentError, AgentResponse, BublikAgent
from memory import Conversation, SQLiteContextRepository


def select_conversation(
    memory: SQLiteContextRepository,
) -> Conversation | None:
    """Предлагает продолжить прошлый диалог или создать новую тему."""

    while True:
        conversations = memory.get_conversations()

        print("\n" + "=" * 70)
        print("ДИАЛОГИ БОРТОВОГО КОМПЬЮТЕРА")
        print("=" * 70)

        if conversations:
            print("Выберите тему, которую хотите продолжить:\n")
            for index, conversation in enumerate(conversations, start=1):
                print(
                    f"{index}. {conversation.title} "
                    f"({conversation.message_count} сообщений)"
                )
        else:
            print("Сохранённых диалогов пока нет.")

        new_dialog_number = len(conversations) + 1
        print(f"{new_dialog_number}. Начать новый диалог")
        print("0. Завершить программу")

        selected_value = input("\nВаш выбор: ").strip()
        if not selected_value.isdigit():
            print("Введите номер пункта меню.")
            continue

        selected_number = int(selected_value)
        if selected_number == 0:
            return None

        if selected_number == new_dialog_number:
            title = input("Название новой темы: ").strip()
            if not title:
                print("Название темы не может быть пустым.")
                continue
            return memory.create_conversation(title)

        if 1 <= selected_number <= len(conversations):
            return conversations[selected_number - 1]

        print("Такого пункта нет. Повторите выбор.")


def print_history(agent: BublikAgent) -> None:
    """Печатает последние сообщения из постоянной памяти."""

    history = agent.get_history()
    if not history:
        print("\nЖурнал экспедиции пока пуст.\n")
        return

    print("\n" + "=" * 70)
    print("СОХРАНЁННЫЙ ЖУРНАЛ ЭКСПЕДИЦИИ")
    print("=" * 70)

    for message in history:
        author = "Чебуратор" if message.role == "user" else "Бублик"
        status = "" if message.status == "completed" else f" [{message.status}]"
        print(f"{author}{status}: {message.content}")
    print()


def print_request_usage(response: AgentResponse) -> None:
    """Показывает локальные и фактические метрики последнего запроса."""

    usage = response.usage
    print("Токены текущего обмена:")
    print(f"  текущий запрос: {usage.current_request_tokens:,}")
    print(f"  сохранённая история: {usage.history_tokens:,}")
    print(f"  prompt, локальная оценка: {usage.estimated_prompt_tokens:,}")
    print(f"  prompt, данные Groq: {usage.api_prompt_tokens:,}")
    print(f"  ответ модели: {usage.completion_tokens:,}")
    print(f"  видимый текст ответа: {usage.visible_response_tokens:,}")
    print(f"  всего обработано API: {usage.total_tokens:,}")
    print(f"  стоимость обмена: ${usage.estimated_cost_usd:.8f}\n")


def print_conversation_usage(agent: BublikAgent) -> None:
    """Показывает накопленное потребление выбранного диалога."""

    usage = agent.get_conversation_usage()
    print("\n" + "=" * 70)
    print("СТАТИСТИКА ДИАЛОГА")
    print("=" * 70)
    print(f"Завершённых запросов: {usage.request_count:,}")
    print(f"Оплаченных входных токенов: {usage.prompt_tokens:,}")
    print(f"Оплаченных выходных токенов: {usage.completion_tokens:,}")
    print(f"Всего обработано токенов: {usage.total_tokens:,}")
    print(f"Расчётная стоимость: ${usage.estimated_cost_usd:.8f}\n")


def run_dialog(
    client: Groq,
    memory: SQLiteContextRepository,
    conversation: Conversation,
) -> bool:
    """Продолжает выбранный диалог до выхода или смены темы."""

    agent = BublikAgent(
        client=client,
        memory=memory,
        conversation_id=conversation.id,
    )

    print(f"\nТекущая тема: {conversation.title}")
    restored_count = agent.restored_message_count
    if restored_count:
        print(f"Восстановлено сообщений: {restored_count}")
    else:
        print("Это новый диалог.")
    print(
        "Команды: /history — журнал, /stats — токены и стоимость, "
        "/dialogs — сменить тему, /exit — выход.\n"
    )

    while True:
        user_input = input("Чебуратор: ").strip()

        if user_input.lower() in {"/exit", "выход"}:
            print("Бублик: Сеанс завершён. Все контексты сохранены.")
            return False

        if user_input.lower() == "/dialogs":
            return True

        if user_input.lower() == "/history":
            print_history(agent)
            continue

        if user_input.lower() == "/stats":
            print_conversation_usage(agent)
            continue

        try:
            response = agent.process(user_input)
            print(f"Бублик: {response.content}\n")
            print_request_usage(response)
        except AgentError as error:
            print(f"Ошибка агента: {error}\n")


def main() -> None:
    """Создаёт зависимости и запускает выбор сохраняемых диалогов."""

    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Переменная GROQ_API_KEY не найдена. "
            "Добавьте API-ключ в файл .env"
        )

    current_directory = Path(__file__).resolve().parent
    database_path = current_directory / "data" / "bublik-token-usage.db"
    memory = SQLiteContextRepository(database_path)
    client = Groq(api_key=api_key)

    print("🤖 День 8 — Бублик считает токены и стоимость")

    should_select_dialog = True
    while should_select_dialog:
        conversation = select_conversation(memory)
        if conversation is None:
            print("Бублик: Все контексты сохранены. До следующего сеанса.")
            return
        should_select_dialog = run_dialog(client, memory, conversation)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nОшибка запуска программы: {error}\n")
