"""Локальные тесты Task State Machine без Groq API."""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import BublikAgent  # noqa: E402
from configuration import ConfigurationLoader  # noqa: E402
from memory import SQLiteMemoryRepository  # noqa: E402
from models import ExpectedAction, TaskState  # noqa: E402
from state_machine import InvalidStateTransition  # noqa: E402


class FakeCompletions:
    def create(self, **kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Принято."))]
        )


class FakeClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions())


class TaskStateMachineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.db"
        self.memory = SQLiteMemoryRepository(self.database_path)
        self.configuration = ConfigurationLoader(
            Path(__file__).resolve().parent / "config"
        )
        conversation = self.memory.create_conversation("Day 13", "cheburator")
        self.conversation_id = conversation.id
        self.agent = self._create_agent(self.memory)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _create_agent(self, memory) -> BublikAgent:
        return BublikAgent(
            FakeClient(), memory, self.configuration, self.conversation_id
        )

    def _prepare_stage(self, stage: TaskState) -> BublikAgent:
        conversation = self.memory.create_conversation(stage.value, "cheburator")
        agent = BublikAgent(
            FakeClient(), self.memory, self.configuration, conversation.id
        )
        agent.create_task("Проверить паузу")
        if stage is TaskState.PLANNING:
            return agent
        agent.set_plan(["Сделать шаг"])
        agent.transition_task(TaskState.EXECUTION)
        if stage is TaskState.EXECUTION:
            return agent
        agent.complete_current_step()
        agent.transition_task(TaskState.VALIDATION)
        return agent

    def test_expected_action_is_derived_from_the_full_state(self) -> None:
        task = self.agent.create_task("Собрать модуль")
        self.assertEqual(task.expected_action, ExpectedAction.DEFINE_PLAN)

        task = self.agent.set_plan(["Код", "Тесты"])
        self.assertEqual(task.expected_action, ExpectedAction.START_EXECUTION)

        task = self.agent.transition_task(TaskState.EXECUTION)
        self.assertEqual(task.current, "Код")
        self.assertEqual(task.expected_action, ExpectedAction.COMPLETE_CURRENT_STEP)

        self.agent.complete_current_step()
        task = self.agent.complete_current_step()
        self.assertIsNone(task.current)
        self.assertEqual(task.expected_action, ExpectedAction.START_VALIDATION)

        task = self.agent.transition_task(TaskState.VALIDATION)
        self.assertEqual(task.expected_action, ExpectedAction.RECORD_VALIDATION)

        task = self.agent.record_task_validation(True, "Все тесты пройдены")
        self.assertEqual(task.expected_action, ExpectedAction.FINISH_TASK)

        task = self.agent.transition_task(TaskState.DONE)
        self.assertEqual(task.expected_action, ExpectedAction.NONE)

    def test_pause_and_resume_preserve_every_non_terminal_stage(self) -> None:
        for stage in (
            TaskState.PLANNING,
            TaskState.EXECUTION,
            TaskState.VALIDATION,
        ):
            with self.subTest(stage=stage.value):
                agent = self._prepare_stage(stage)
                before = agent.get_task()

                paused = agent.pause_task()
                self.assertTrue(paused.paused)
                self.assertEqual(paused.state, before.state)
                self.assertEqual(paused.current, before.current)
                self.assertEqual(paused.expected_action, ExpectedAction.RESUME)

                resumed = agent.resume_task()
                self.assertFalse(resumed.paused)
                self.assertEqual(resumed.state, before.state)
                self.assertEqual(resumed.current, before.current)
                self.assertEqual(resumed.expected_action, before.expected_action)

    def test_paused_task_rejects_progress(self) -> None:
        self.agent.create_task("Собрать модуль")
        self.agent.set_plan(["Код"])
        self.agent.transition_task(TaskState.EXECUTION)
        self.agent.pause_task()

        with self.assertRaisesRegex(InvalidStateTransition, "на паузе"):
            self.agent.complete_current_step()
        with self.assertRaisesRegex(InvalidStateTransition, "на паузе"):
            self.agent.transition_task(TaskState.VALIDATION)

    def test_task_resumes_after_restart_without_repeating_description(self) -> None:
        self.agent.create_task("Подготовить навигационный модуль")
        self.agent.set_plan(["Спроектировать API", "Добавить тесты"])
        self.agent.transition_task(TaskState.EXECUTION)
        self.agent.complete_current_step()
        self.agent.pause_task()

        restored_memory = SQLiteMemoryRepository(self.database_path)
        restored = self._create_agent(restored_memory)
        task = restored.get_task()

        self.assertEqual(task.task, "Подготовить навигационный модуль")
        self.assertEqual(task.state, TaskState.EXECUTION)
        self.assertEqual(task.current, "Добавить тесты")
        self.assertTrue(task.paused)
        self.assertEqual(task.expected_action, ExpectedAction.RESUME)

        prompt = "\n".join(item["content"] for item in restored.get_context_preview())
        self.assertIn("Stage: execution", prompt)
        self.assertIn("Current step: Добавить тесты", prompt)
        self.assertIn("Expected action: resume", prompt)
        self.assertIn("Do not ask the user to repeat", prompt)

        resumed = restored.resume_task()
        self.assertEqual(
            resumed.expected_action, ExpectedAction.COMPLETE_CURRENT_STEP
        )

    def test_failed_validation_returns_last_step_to_execution(self) -> None:
        self.agent.create_task("Собрать модуль")
        self.agent.set_plan(["Код", "Тесты"])
        self.agent.transition_task(TaskState.EXECUTION)
        self.agent.complete_current_step()
        self.agent.complete_current_step()
        self.agent.transition_task(TaskState.VALIDATION)
        failed = self.agent.record_task_validation(False, "Найден дефект")
        self.assertEqual(
            failed.expected_action, ExpectedAction.RETURN_TO_EXECUTION
        )

        retry = self.agent.transition_task(TaskState.EXECUTION)
        self.assertEqual(retry.current, "Тесты")
        self.assertEqual(retry.done, ["Код"])
        self.assertEqual(
            retry.expected_action, ExpectedAction.COMPLETE_CURRENT_STEP
        )


if __name__ == "__main__":
    unittest.main()
