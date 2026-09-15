"""CLI для проверки трёх слоёв памяти Бублика."""

import os
import shlex
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from agent import AgentError, BublikAgent
from configuration import ConfigurationLoader
from memory import SQLiteMemoryRepository
from models import LongTermKind, TaskState


def select_conversation(memory: SQLiteMemoryRepository):
    while True:
        conversations = memory.get_conversations()
        print("\n" + "=" * 70)
        print("ДИАЛОГИ БОРТОВОГО КОМПЬЮТЕРА")
        print("=" * 70)
        for index, conversation in enumerate(conversations, 1):
            print(f"{index}. {conversation.title} ({conversation.message_count} сообщений)")
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
            try:
                return memory.create_conversation(title)
            except ValueError as error:
                print(error)
                continue
        if 1 <= number <= len(conversations):
            return conversations[number - 1]
        print("Такого пункта нет.")


def print_task(agent: BublikAgent) -> None:
    task = agent.get_task()
    print("\nWORKING MEMORY — TASK")
    print("=" * 70)
    if task is None:
        print("Активная задача не создана.\n")
        return
    print(f"Задача: {task.task}")
    print(f"Состояние: {task.state.value}")
    print(f"Прогресс: {len(task.done)}/{task.total}")
    print(f"Текущий шаг: {task.current or '—'}")
    print(f"Проверка: {'PASS' if task.validation_passed else 'NOT PASSED'}")
    if task.validation_details:
        print(f"Результат проверки: {task.validation_details}")
    for index, step in enumerate(task.plan, 1):
        marker = "✓" if step in task.done else "·"
        print(f"{marker} {index}. {step}")
    print()


def print_memory(agent: BublikAgent, layer: str | None = None) -> None:
    if layer in (None, "short"):
        print("\nSHORT-TERM MEMORY")
        print("=" * 70)
        messages = agent.get_short_term()
        if not messages:
            print("Текущий диалог пока пуст.")
        for message in messages:
            print(f"{message.role}: {message.content}")
    if layer in (None, "working"):
        print_task(agent)
        notes = agent.get_working_notes()
        print("Рабочие заметки:")
        for note in notes:
            print(f"- {note.key}: {note.value}")
        if not notes:
            print("- нет")
    if layer in (None, "long"):
        print("\nLONG-TERM MEMORY")
        print("=" * 70)
        print("Профиль: config/profile.json")
        entries = agent.get_long_term()
        for entry in entries:
            print(f"- {entry.kind.value}.{entry.key}: {entry.value}")
        if not entries:
            print("Решений и знаний пока нет.")
    print()


def print_context(agent: BublikAgent) -> None:
    print("\nPROMPT, КОТОРЫЙ ПОЛУЧИТ МОДЕЛЬ")
    print("=" * 70)
    for message in agent.get_context_preview():
        print(f"[{message['role']}]\n{message['content']}\n")


def print_response_status(response) -> None:
    task = response.task_context
    print("STATUS")
    print("=" * 70)
    print(
        "Memory: "
        f"short={response.short_term_messages}, "
        f"working={response.working_memory_items}, "
        f"long={response.long_term_items}"
    )
    print(
        "Invariants: PASS; checked="
        + ", ".join(response.validation.checked)
    )
    if task:
        print(
            f"Task: state={task.state.value}, "
            f"progress={len(task.done)}/{task.total}, "
            f"current={task.current or '—'}"
        )
    else:
        print("Task: не создана")
    print()


def handle_task_command(agent: BublikAgent, parts: list[str]) -> None:
    if len(parts) == 2 and parts[1] == "status":
        print_task(agent)
    elif len(parts) >= 3 and parts[1] == "create":
        agent.create_task(" ".join(parts[2:]))
        print("Задача создана. Состояние: planning.\n")
    elif len(parts) >= 3 and parts[1] == "plan":
        task = agent.set_plan(parts[2:])
        print(f"План сохранён: {task.total} шагов.\n")
    elif len(parts) == 3 and parts[1] == "transition":
        task = agent.transition_task(TaskState(parts[2]))
        print(f"Новое состояние: {task.state.value}.\n")
    elif len(parts) == 2 and parts[1] == "complete":
        task = agent.complete_current_step()
        print(f"Шаг завершён. Прогресс: {len(task.done)}/{task.total}.\n")
    elif len(parts) >= 3 and parts[1] == "check":
        passed = parts[2].lower() == "pass"
        if parts[2].lower() not in {"pass", "fail"}:
            raise ValueError("Используйте /task check pass|fail [результат]")
        task = agent.record_task_validation(passed, " ".join(parts[3:]))
        print(f"Результат проверки: {'PASS' if task.validation_passed else 'FAIL'}.\n")
    else:
        raise ValueError("Неизвестная команда /task")


def handle_command(agent: BublikAgent, raw_command: str) -> None:
    parts = shlex.split(raw_command)
    command = parts[0].lower()
    if command == "/history":
        for message in agent.get_full_history():
            print(f"{message.role}: {message.content}")
        print()
    elif command == "/context":
        print_context(agent)
    elif command == "/memory":
        layer = parts[1].lower() if len(parts) == 2 else None
        if layer not in {None, "short", "working", "long"}:
            raise ValueError("Слой: short, working или long")
        print_memory(agent, layer)
    elif command == "/remember" and len(parts) == 4 and parts[1] == "working":
        agent.remember_working(parts[2], parts[3])
        print("Запись сохранена в working memory.\n")
    elif command == "/remember" and len(parts) == 5 and parts[1] == "long":
        agent.remember_long_term(LongTermKind(parts[2]), parts[3], parts[4])
        print(f"Запись сохранена в long-term memory как {parts[2]}.\n")
    elif command == "/task":
        handle_task_command(agent, parts)
    else:
        raise ValueError("Неизвестная команда или неверное число аргументов")


def run_dialog(client, memory, configuration, conversation) -> bool:
    agent = BublikAgent(client, memory, configuration, conversation.id)
    print(f"\nТема: {conversation.title}")
    print(
        "Команды: /memory [short|working|long], /context, /history,\n"
        "/remember working KEY VALUE,\n"
        "/remember long decision|knowledge KEY VALUE,\n"
        "/task create DESCRIPTION, /task plan STEP1 STEP2,\n"
        "/task transition STATE, /task complete,\n"
        "/task check pass|fail RESULT, /task status, /dialogs, /exit.\n"
        "Значения с пробелами заключайте в кавычки.\n"
    )
    while True:
        user_input = input("Чебуратор: ").strip()
        if user_input.lower() in {"/exit", "выход"}:
            print("Бублик: Сеанс завершён. Все слои памяти сохранены.")
            return False
        if user_input.lower() == "/dialogs":
            return True
        if user_input.startswith("/"):
            try:
                handle_command(agent, user_input)
            except (AgentError, ValueError) as error:
                print(f"Ошибка команды: {error}\n")
            continue
        try:
            response = agent.process(user_input)
            print(f"Бублик: {response.content}\n")
            print_response_status(response)
        except AgentError as error:
            print(f"Ошибка агента: {error}\n")


def main() -> None:
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Добавьте GROQ_API_KEY в .env")
    directory = Path(__file__).resolve().parent
    memory = SQLiteMemoryRepository(directory / "data" / "bublik-memory.db")
    configuration = ConfigurationLoader(directory / "config")
    client = Groq(api_key=api_key)
    print("🤖 День 11 — явная модель памяти агента")
    while True:
        conversation = select_conversation(memory)
        if conversation is None:
            return
        if not run_dialog(client, memory, configuration, conversation):
            return


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nОшибка запуска программы: {error}\n")
