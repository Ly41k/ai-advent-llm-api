"""CLI Бублика с Sliding Window, Sticky Facts и Branching."""

import os
import shlex
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from agent import AgentError, AgentResponse, BublikAgent
from memory import Conversation, SQLiteContextRepository
from strategies import StrategyName


STRATEGY_LABELS = {
    StrategyName.SLIDING_WINDOW: "Sliding Window",
    StrategyName.STICKY_FACTS: "Sticky Facts / Key-Value Memory",
    StrategyName.BRANCHING: "Branching",
}


def select_strategy() -> StrategyName:
    strategies = list(StrategyName)
    while True:
        print("\nВыберите стратегию контекста:")
        for index, strategy in enumerate(strategies, start=1):
            print(f"{index}. {STRATEGY_LABELS[strategy]}")
        selected = input("Ваш выбор: ").strip()
        if selected.isdigit() and 1 <= int(selected) <= len(strategies):
            return strategies[int(selected) - 1]
        print("Введите номер стратегии.")


def select_conversation(memory: SQLiteContextRepository) -> Conversation | None:
    while True:
        conversations = memory.get_conversations()
        print("\n" + "=" * 70)
        print("ДИАЛОГИ БОРТОВОГО КОМПЬЮТЕРА")
        print("=" * 70)
        for index, conversation in enumerate(conversations, start=1):
            print(
                f"{index}. {conversation.title} — {conversation.strategy} "
                f"({conversation.message_count} сообщений)"
            )
        new_number = len(conversations) + 1
        print(f"{new_number}. Начать новый диалог")
        print("0. Завершить программу")
        selected = input("\nВаш выбор: ").strip()
        if not selected.isdigit():
            print("Введите номер пункта меню.")
            continue
        number = int(selected)
        if number == 0:
            return None
        if number == new_number:
            title = input("Название новой темы: ").strip()
            if not title:
                print("Название не может быть пустым.")
                continue
            return memory.create_conversation(title, select_strategy().value)
        if 1 <= number <= len(conversations):
            return conversations[number - 1]
        print("Такого пункта нет.")


def print_usage(response: AgentResponse) -> None:
    usage = response.usage
    print(f"Стратегия: {response.strategy.value}; ветка: {response.branch_name}")
    print(f"  полная история: {usage.full_history_tokens:,}")
    print(f"  контекст стратегии: {usage.strategy_context_tokens:,}")
    print(f"  сэкономлено в истории: {usage.saved_history_tokens:,}")
    print(f"  prompt Groq: {usage.api_prompt_tokens:,}")
    print(f"  completion Groq: {usage.completion_tokens:,}")
    print(f"  всего: {usage.total_tokens:,}")
    print(f"  стоимость: ${usage.estimated_cost_usd:.8f}\n")


def print_history(agent: BublikAgent) -> None:
    print(f"\nИСТОРИЯ ВЕТКИ: {agent.active_branch.name}")
    print("=" * 70)
    for message in agent.get_history():
        author = "Чебуратор" if message.role == "user" else "Бублик"
        print(f"{author}: {message.content}")
    print()


def print_context(agent: BublikAgent) -> None:
    print(f"\nКОНТЕКСТ СТРАТЕГИИ: {agent.strategy_name.value}")
    print("=" * 70)
    context = agent.get_context_preview()
    if not context:
        print("Контекст пока пуст.")
    for item in context:
        print(f"[{item['role']}] {item['content']}")
    print()


def print_facts(agent: BublikAgent) -> None:
    print("\nSTICKY FACTS")
    print("=" * 70)
    facts = agent.get_facts()
    if not facts:
        print("Facts пока не извлечены.")
    for fact in facts:
        print(f"{fact.key}: {fact.value}")
    print()


def print_branches(agent: BublikAgent) -> None:
    active_id = agent.active_branch.id
    print("\nВЕТКИ")
    print("=" * 70)
    for branch in agent.get_branches():
        marker = " *" if branch.id == active_id else ""
        parent = branch.parent_branch_id or "—"
        print(f"{branch.name}{marker} | parent={parent}")
    print("\nCHECKPOINTS")
    for checkpoint in agent.get_checkpoints():
        print(f"{checkpoint.name} | message_id={checkpoint.message_id}")
    print()


def print_stats(agent: BublikAgent) -> None:
    usage = agent.get_usage()
    print("\nСТАТИСТИКА ДИАЛОГА")
    print("=" * 70)
    print(f"Основных запросов: {usage.request_count:,}")
    print(f"Токенов основных запросов: {usage.total_tokens:,}")
    print(f"Стоимость основных запросов: ${usage.estimated_cost_usd:.8f}")
    print(f"Обновлений facts: {usage.fact_update_count:,}")
    print(f"Токенов обновления facts: {usage.fact_update_tokens:,}")
    print(f"Стоимость обновления facts: ${usage.fact_update_cost_usd:.8f}")
    print(
        "Общая стоимость: "
        f"${usage.estimated_cost_usd + usage.fact_update_cost_usd:.8f}\n"
    )


def handle_command(agent: BublikAgent, raw_command: str) -> bool:
    try:
        parts = shlex.split(raw_command)
    except ValueError as error:
        print(f"Ошибка команды: {error}\n")
        return True
    command = parts[0].lower()
    try:
        if command == "/history":
            print_history(agent)
        elif command == "/context":
            print_context(agent)
        elif command == "/facts":
            print_facts(agent)
        elif command == "/stats":
            print_stats(agent)
        elif command == "/strategy":
            strategy = StrategyName(parts[1]) if len(parts) > 1 else select_strategy()
            agent.set_strategy(strategy)
            print(f"Стратегия изменена на {strategy.value}.\n")
        elif command == "/checkpoint" and len(parts) == 2:
            checkpoint = agent.create_checkpoint(parts[1])
            print(f"Checkpoint '{checkpoint.name}' сохранён.\n")
        elif command == "/branches":
            print_branches(agent)
        elif command == "/branch" and len(parts) == 4 and parts[1] == "create":
            branch = agent.create_branch(parts[2], parts[3])
            print(
                f"Ветка '{branch.name}' создана. "
                f"Переключение: /branch switch {branch.name}\n"
            )
        elif command == "/branch" and len(parts) == 3 and parts[1] == "switch":
            branch = agent.switch_branch(parts[2])
            print(f"Активная ветка: {branch.name}.\n")
        else:
            print("Неизвестная команда или неверное число аргументов.\n")
    except (AgentError, ValueError) as error:
        print(f"Ошибка команды: {error}\n")
    return True


def run_dialog(client: Groq, memory: SQLiteContextRepository, conversation: Conversation) -> bool:
    agent = BublikAgent(client, memory, conversation.id)
    print(f"\nТема: {conversation.title}")
    print(f"Стратегия: {agent.strategy_name.value}")
    print(f"Активная ветка: {agent.active_branch.name}")
    print(f"Восстановлено сообщений: {agent.restored_message_count}")
    print(
        "Команды: /strategy [sliding|facts|branching], /history, /context, "
        "/facts, /checkpoint NAME, /branches, "
        "/branch create NAME CHECKPOINT, /branch switch NAME, "
        "/stats, /dialogs, /exit.\n"
    )
    while True:
        user_input = input("Чебуратор: ").strip()
        if user_input.lower() in {"/exit", "выход"}:
            print("Бублик: Сеанс завершён. Все контексты сохранены.")
            return False
        if user_input.lower() == "/dialogs":
            return True
        if user_input.startswith("/"):
            handle_command(agent, user_input)
            continue
        try:
            response = agent.process(user_input)
            print(f"Бублик: {response.content}\n")
            print_usage(response)
        except AgentError as error:
            print(f"Ошибка агента: {error}\n")


def main() -> None:
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Добавьте GROQ_API_KEY в .env")
    directory = Path(__file__).resolve().parent
    memory = SQLiteContextRepository(directory / "data" / "bublik-strategies.db")
    client = Groq(api_key=api_key)
    print("🤖 День 10 — три стратегии управления контекстом без summary")
    while True:
        conversation = select_conversation(memory)
        if conversation is None or not run_dialog(client, memory, conversation):
            return


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nОшибка запуска программы: {error}\n")
