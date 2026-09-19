"""Эксперимент: продолжение задачи после паузы и пересоздания агента."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import load_dotenv
from groq import Groq

from agent import BublikAgent
from configuration import ConfigurationLoader
from memory import SQLiteMemoryRepository
from models import TaskState


def describe(prefix: str, agent: BublikAgent) -> None:
    task = agent.get_task()
    print(f"\n{prefix}")
    print("=" * 70)
    print(f"stage={task.state.value}")
    print(f"current={task.current or '—'}")
    print(f"expected={task.expected_action.value}")
    print(f"paused={'yes' if task.paused else 'no'}")


def main() -> None:
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Добавьте GROQ_API_KEY в .env")
    directory = Path(__file__).resolve().parent
    configuration = ConfigurationLoader(directory / "config")
    client = Groq(api_key=api_key)

    with TemporaryDirectory() as temporary_directory:
        database_path = Path(temporary_directory) / "experiment.db"
        memory = SQLiteMemoryRepository(database_path)
        conversation = memory.create_conversation("Day 13", "cheburator")
        agent = BublikAgent(client, memory, configuration, conversation.id)
        agent.create_task("Подготовить прототип навигационного модуля")
        agent.set_plan(
            ["Определить API", "Реализовать прототип", "Запустить тесты"]
        )
        agent.transition_task(TaskState.EXECUTION)
        agent.complete_current_step()
        agent.pause_task()
        describe("ДО ПЕРЕЗАПУСКА", agent)

        # Новый repository и agent имитируют новый запуск программы.
        restored_memory = SQLiteMemoryRepository(database_path)
        restored = BublikAgent(
            client, restored_memory, configuration, conversation.id
        )
        describe("ПОСЛЕ ПЕРЕЗАПУСКА", restored)
        restored.resume_task()
        response = restored.process("Продолжай.")

    print("\nОТВЕТ ПОСЛЕ ВОССТАНОВЛЕНИЯ")
    print("=" * 70)
    print(response.content)
    print("\nПользователь не повторял описание задачи, план или текущий шаг.")


if __name__ == "__main__":
    main()
