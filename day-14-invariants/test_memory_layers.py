"""Локальные тесты персонализации и memory layers без Groq API."""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import BublikAgent, SHORT_TERM_LIMIT  # noqa: E402
from configuration import ConfigurationLoader  # noqa: E402
from memory import SQLiteMemoryRepository  # noqa: E402
from models import LongTermKind, TaskState  # noqa: E402
from state_machine import InvalidStateTransition  # noqa: E402


class FakeCompletions:
    def __init__(self, content: str = "Принято.") -> None:
        self.content = content
        self.last_messages = []

    def create(self, **kwargs):
        is_guard = "[SEMANTIC INVARIANT GUARD]" in kwargs["messages"][0]["content"]
        if is_guard:
            content = json.dumps({"violations": []})
        else:
            self.last_messages = kwargs["messages"]
            content = self.content
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class FakeClient:
    def __init__(self, content: str = "Принято.") -> None:
        self.completions = FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


class MemoryLayersTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.memory = SQLiteMemoryRepository(
            Path(self.temporary_directory.name) / "test.db"
        )
        self.configuration = ConfigurationLoader(
            Path(__file__).resolve().parent / "config"
        )
        self.conversation = self.memory.create_conversation(
            "Первый диалог", "cheburator"
        )
        self.client = FakeClient()
        self.agent = BublikAgent(
            self.client,
            self.memory,
            self.configuration,
            self.conversation.id,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def add_exchange(self, conversation_id: str, user: str, assistant: str) -> None:
        message_id = self.memory.start_user_request(conversation_id, user)
        self.memory.complete_exchange(message_id, conversation_id, assistant)

    def test_short_term_contains_only_recent_current_dialogue_messages(self) -> None:
        for number in range(5):
            self.add_exchange(self.conversation.id, f"u{number}", f"a{number}")
        second = self.memory.create_conversation("Второй диалог", "cheburator")
        self.add_exchange(second.id, "чужое сообщение", "чужой ответ")

        short_term = self.agent.get_short_term()

        self.assertEqual(len(short_term), SHORT_TERM_LIMIT)
        self.assertEqual(short_term[0].content, "u2")
        self.assertNotIn("чужое сообщение", [item.content for item in short_term])

    def test_working_and_long_term_are_saved_explicitly_and_separately(self) -> None:
        self.agent.create_task("Спроектировать зонд")
        self.agent.remember_working("limit", "масса до 100 кг")
        self.agent.remember_long_term(
            LongTermKind.DECISION, "energy", "использовать солнечные панели"
        )

        self.assertEqual(self.agent.get_task().task, "Спроектировать зонд")
        self.assertEqual(self.agent.get_working_notes()[0].key, "limit")
        self.assertEqual(self.agent.get_long_term()[0].key, "energy")

    def test_long_term_is_shared_but_working_memory_is_isolated(self) -> None:
        self.agent.remember_working("draft", "вариант A")
        self.agent.remember_long_term(
            LongTermKind.KNOWLEDGE, "star", "объект K-41 нестабилен"
        )
        second = self.memory.create_conversation("Новая тема", "cheburator")
        second_agent = BublikAgent(
            FakeClient(), self.memory, self.configuration, second.id
        )

        self.assertEqual(second_agent.get_working_notes(), [])
        self.assertEqual(second_agent.get_long_term()[0].value, "объект K-41 нестабилен")

    def test_prompt_contains_all_memory_layers(self) -> None:
        self.add_exchange(self.conversation.id, "Текущий вопрос", "Текущий ответ")
        self.agent.create_task("Собрать требования")
        self.agent.remember_working("deadline", "3 цикла")
        self.agent.remember_long_term(
            LongTermKind.DECISION, "engine", "ионный"
        )

        prompt = self.agent.get_context_preview()
        text = "\n".join(item["content"] for item in prompt)

        self.assertIn("USER PROFILE — APPLY AUTOMATICALLY", text)
        self.assertIn("Profile ID: cheburator", text)
        self.assertIn("decision.engine: ионный", text)
        self.assertIn("Task: Собрать требования", text)
        self.assertIn("deadline: 3 цикла", text)
        self.assertEqual(prompt[-2]["content"], "Текущий вопрос")
        self.assertEqual(prompt[-1]["content"], "Текущий ответ")

    def test_state_machine_rejects_jumps_and_requires_completed_plan(self) -> None:
        self.agent.create_task("Построить модуль")
        with self.assertRaises(InvalidStateTransition):
            self.agent.transition_task(TaskState.EXECUTION)
        self.agent.set_plan(["Код", "Тесты"])
        task = self.agent.transition_task(TaskState.EXECUTION)
        self.assertEqual(task.current, "Код")
        with self.assertRaises(InvalidStateTransition):
            self.agent.transition_task(TaskState.VALIDATION)
        self.agent.complete_current_step()
        self.agent.complete_current_step()
        self.agent.transition_task(TaskState.VALIDATION)
        with self.assertRaises(InvalidStateTransition):
            self.agent.transition_task(TaskState.DONE)
        self.agent.record_task_validation(True, "Тесты пройдены")
        task = self.agent.transition_task(TaskState.DONE)
        self.assertEqual(task.state, TaskState.DONE)

    def test_memory_changes_prompt_and_agent_response_status(self) -> None:
        self.agent.remember_long_term(
            LongTermKind.KNOWLEDGE, "planet", "на планете есть вода"
        )
        response = self.agent.process("Что известно о планете?")
        sent = "\n".join(
            item["content"] for item in self.client.completions.last_messages
        )

        self.assertIn("knowledge.planet: на планете есть вода", sent)
        self.assertTrue(response.validation.passed)
        self.assertIn("security.no_secrets", response.validation.checked)
        self.assertEqual(response.short_term_messages, 2)
        self.assertEqual(response.profile_id, "cheburator")

    def test_different_profiles_build_different_personalization_prompts(self) -> None:
        scientist_conversation = self.memory.create_conversation(
            "Научный анализ", "scientist"
        )
        scientist = BublikAgent(
            FakeClient(), self.memory, self.configuration, scientist_conversation.id
        )

        cheburator_prompt = "\n".join(
            item["content"] for item in self.agent.get_context_preview()
        )
        scientist_prompt = "\n".join(
            item["content"] for item in scientist.get_context_preview()
        )

        self.assertIn("кратко, только необходимая информация", cheburator_prompt)
        self.assertIn("сначала дать вывод", cheburator_prompt)
        self.assertIn("подробно, с объяснением причин и рисков", scientist_prompt)
        self.assertIn("структурировать ответ по разделам", scientist_prompt)
        self.assertNotEqual(cheburator_prompt, scientist_prompt)

    def test_profile_is_attached_to_every_request_automatically(self) -> None:
        self.agent.process("Первый вопрос без описания предпочтений")
        first_prompt = "\n".join(
            item["content"] for item in self.client.completions.last_messages
        )
        self.agent.process("Второй вопрос без описания предпочтений")
        second_prompt = "\n".join(
            item["content"] for item in self.client.completions.last_messages
        )

        for prompt in (first_prompt, second_prompt):
            self.assertIn("Profile ID: cheburator", prompt)
            self.assertIn("RESPONSE FORMAT", prompt)
            self.assertIn("USER CONSTRAINTS", prompt)

    def test_long_term_memory_is_isolated_by_profile(self) -> None:
        self.agent.remember_long_term(
            LongTermKind.DECISION, "priority", "безопасность экипажа"
        )
        scientist_conversation = self.memory.create_conversation(
            "Другой пользователь", "scientist"
        )
        scientist = BublikAgent(
            FakeClient(), self.memory, self.configuration, scientist_conversation.id
        )

        self.assertEqual(scientist.get_long_term(), [])
        self.assertEqual(self.agent.get_long_term()[0].value, "безопасность экипажа")

    def test_profile_switch_is_allowed_only_for_empty_dialogue(self) -> None:
        empty = self.memory.create_conversation("Пустой", "cheburator")
        agent = BublikAgent(FakeClient(), self.memory, self.configuration, empty.id)
        self.assertEqual(agent.switch_profile("scientist").id, "scientist")
        agent.process("Начинаем")
        with self.assertRaisesRegex(ValueError, "только в пустом диалоге"):
            agent.switch_profile("cheburator")

    def test_selected_profile_is_restored_with_conversation(self) -> None:
        conversation = self.memory.create_conversation(
            "Сохраняемый профиль", "scientist"
        )
        restored_memory = SQLiteMemoryRepository(
            Path(self.temporary_directory.name) / "test.db"
        )
        restored_agent = BublikAgent(
            FakeClient(), restored_memory, self.configuration, conversation.id
        )

        self.assertEqual(restored_agent.get_profile().id, "scientist")
        prompt = "\n".join(
            item["content"] for item in restored_agent.get_context_preview()
        )
        self.assertIn("Profile ID: scientist", prompt)

    def test_response_that_breaks_invariant_becomes_explained_refusal(self) -> None:
        unsafe_agent = BublikAgent(
            FakeClient("Используй ключ gsk_12345678901234567890"),
            self.memory,
            self.configuration,
            self.conversation.id,
        )
        response = unsafe_agent.process("Покажи конфигурацию")

        self.assertTrue(response.refused_by_invariants)
        self.assertIn("[security.no_secrets]", response.content)
        self.assertIn("подготовленный ответ", response.content)
        self.assertNotIn("gsk_", response.content)
        history = unsafe_agent.get_short_term()
        self.assertEqual([item.role for item in history], ["user", "assistant"])
        self.assertEqual(history[-1].content, response.content)
        self.assertNotIn("gsk_", history[-1].content)


if __name__ == "__main__":
    unittest.main()
