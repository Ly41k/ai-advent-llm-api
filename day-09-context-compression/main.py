"""CLI агента со сжатием старой истории диалога."""

import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from agent import AgentError, AgentResponse, BublikAgent, ContextComparison
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
    """Печатает последние сообщения из полной постоянной памяти."""

    history = agent.get_history()
    if not history:
        print("\nЖурнал экспедиции пока пуст.\n")
        return

    print("\n" + "=" * 70)
    print("ПОЛНЫЙ ЖУРНАЛ ЭКСПЕДИЦИИ")
    print("=" * 70)
    for message in history:
        author = "Чебуратор" if message.role == "user" else "Бублик"
        status = "" if message.status == "completed" else f" [{message.status}]"
        print(f"{author}{status}: {message.content}")
    print()


def print_request_usage(response: AgentResponse) -> None:
    """Показывает экономию токенов после сжатия истории."""

    usage = response.usage
    if response.compression.updated:
        print(
        "Summary обновлён: сжато "
        f"{response.compression.source_message_count} сообщений."
        )

    print("Токены текущего обмена:")
    print(f"  текущий запрос: {usage.current_request_tokens:,}")
    print(f"  полная история: {usage.full_history_tokens:,}")
    print(f"  summary + последние сообщения: {usage.compressed_history_tokens:,}")
    print(f"  сэкономлено токенов истории: {usage.saved_history_tokens:,}")
    print(f"  prompt, локальная оценка: {usage.estimated_prompt_tokens:,}")
    print(f"  prompt, данные Groq: {usage.api_prompt_tokens:,}")
    print(f"  ответ модели: {usage.completion_tokens:,}")
    print(f"  всего обработано API: {usage.total_tokens:,}")
    print(f"  стоимость обмена: ${usage.estimated_cost_usd:.8f}\n")


def print_summary(agent: BublikAgent) -> None:
    """Показывает отдельно сохранённый summary и его стоимость."""

    summary = agent.get_summary()
    print("\n" + "=" * 70)
    print("SUMMARY РАННЕЙ ИСТОРИИ")
    print("=" * 70)
    if summary is None:
        print("Summary ещё не создан: недостаточно старых сообщений.\n")
        return

    print(summary.content)
    print("\nМетрики summary:")
    print(f"  сжато сообщений: {summary.source_message_count:,}")
    print(f"  обновлений: {summary.update_count:,}")
    print(f"  всего токенов на обновления: {summary.total_tokens:,}")
    print(f"  стоимость обновлений: ${summary.estimated_cost_usd:.8f}\n")


def print_conversation_usage(agent: BublikAgent) -> None:
    """Показывает стоимость ответов и отдельную стоимость summary."""

    usage = agent.get_conversation_usage()
    summary = agent.get_summary()
    summary_tokens = summary.total_tokens if summary else 0
    summary_cost = summary.estimated_cost_usd if summary else 0.0

    print("\n" + "=" * 70)
    print("СТАТИСТИКА ДИАЛОГА")
    print("=" * 70)
    print(f"Завершённых запросов: {usage.request_count:,}")
    print(f"Токенов основных запросов: {usage.total_tokens:,}")
    print(f"Стоимость основных запросов: ${usage.estimated_cost_usd:.8f}")
    print(f"Токенов создания summary: {summary_tokens:,}")
    print(f"Стоимость создания summary: ${summary_cost:.8f}")
    print(f"Общая стоимость: ${usage.estimated_cost_usd + summary_cost:.8f}\n")


def print_comparison(comparison: ContextComparison) -> None:
    """Печатает два ответа и фактическую разницу токенов."""

    full = comparison.without_compression
    compressed = comparison.with_compression
    saved_prompt_tokens = (
        full.usage.api_prompt_tokens - compressed.usage.api_prompt_tokens
    )
    saved_cost = (
        full.usage.estimated_cost_usd - compressed.usage.estimated_cost_usd
    )

    print("\n" + "=" * 70)
    print("БЕЗ СЖАТИЯ")
    print("=" * 70)
    print(full.content)
    print(f"\nPrompt tokens: {full.usage.api_prompt_tokens:,}")
    print(f"Стоимость: ${full.usage.estimated_cost_usd:.8f}")

    print("\n" + "=" * 70)
    print("СО СЖАТИЕМ")
    print("=" * 70)
    print(compressed.content)
    print(f"\nPrompt tokens: {compressed.usage.api_prompt_tokens:,}")
    print(f"Стоимость: ${compressed.usage.estimated_cost_usd:.8f}")

    print("\n" + "=" * 70)
    print("РЕЗУЛЬТАТ СРАВНЕНИЯ")
    print("=" * 70)
    print(f"Сэкономлено prompt tokens: {saved_prompt_tokens:,}")
    print(f"Разница стоимости двух ответов: ${saved_cost:.8f}")
    print(
        "Качество проверьте по четырём критериям: сохранены ли факты, "
        "решения капитана, числовые значения и открытые вопросы.\n"
    )


def run_dialog(
    client: Groq,
    memory: SQLiteContextRepository,
    conversation: Conversation,
) -> bool:
    """Продолжает выбранный диалог до выхода или смены темы."""

    agent = BublikAgent(client, memory, conversation.id)
    print(f"\nТекущая тема: {conversation.title}")
    print(f"Восстановлено сообщений: {agent.restored_message_count}")
    print(
        "Команды: /history — полный журнал, /summary — сжатая история, "
        "/compare — сравнение, /stats — стоимость, "
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
        if user_input.lower() == "/summary":
            print_summary(agent)
            continue
        if user_input.lower() == "/stats":
            print_conversation_usage(agent)
            continue
        if user_input.lower() == "/compare":
            question = input("Вопрос для сравнения: ").strip()
            try:
                print_comparison(agent.compare_contexts(question))
            except AgentError as error:
                print(f"Ошибка сравнения: {error}\n")
            continue

        try:
            response = agent.process(user_input)
            print(f"Бублик: {response.content}\n")
            print_request_usage(response)
        except AgentError as error:
            print(f"Ошибка агента: {error}\n")


def main() -> None:
    """Создаёт зависимости и запускает агент с компрессией истории."""

    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Переменная GROQ_API_KEY не найдена. Добавьте API-ключ в .env"
        )

    current_directory = Path(__file__).resolve().parent
    memory = SQLiteContextRepository(
        current_directory / "data" / "bublik-context-compression.db"
    )
    client = Groq(api_key=api_key)

    print("🤖 День 9 — Бублик сжимает старую историю")
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
