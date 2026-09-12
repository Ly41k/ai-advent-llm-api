"""Локальные тесты стратегий и независимости веток без Groq API."""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from memory import Fact, SQLiteContextRepository  # noqa: E402
from agent import BublikAgent  # noqa: E402
from strategies import (  # noqa: E402
    BranchingStrategy,
    SlidingWindowStrategy,
    StickyFactsStrategy,
)
from tokens import RequestTokenUsage  # noqa: E402


EMPTY_USAGE = RequestTokenUsage(0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0)


class FakeCompletions:
    def create(self, **kwargs):
        is_facts_request = "key-value" in kwargs["messages"][0]["content"]
        content = '{"goal": "исследование"}' if is_facts_request else "Принято."
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
            ),
        )


class FakeClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions())


class ContextStrategiesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.memory = SQLiteContextRepository(
            Path(self.temporary_directory.name) / "test.db"
        )
        self.conversation = self.memory.create_conversation("test", "branching")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def add_exchange(self, branch_id: str, user: str, assistant: str) -> None:
        message_id = self.memory.start_user_request(
            self.conversation.id, branch_id, user
        )
        self.memory.complete_exchange(
            message_id,
            self.conversation.id,
            branch_id,
            "branching",
            assistant,
            EMPTY_USAGE,
        )

    def test_sliding_window_keeps_only_last_n_messages(self) -> None:
        branch = self.memory.get_active_branch(self.conversation.id)
        for number in range(4):
            self.add_exchange(branch.id, f"u{number}", f"a{number}")
        history = self.memory.get_branch_history(branch.id)
        context = SlidingWindowStrategy(limit=3).build(history, [])
        self.assertEqual([item["content"] for item in context], ["a2", "u3", "a3"])

    def test_facts_are_added_before_recent_messages(self) -> None:
        branch = self.memory.get_active_branch(self.conversation.id)
        self.add_exchange(branch.id, "цель", "принято")
        history = self.memory.get_branch_history(branch.id)
        facts = [Fact("goal", "исследование", "now")]
        context = StickyFactsStrategy(limit=1).build(history, facts)
        self.assertEqual(context[0]["role"], "system")
        self.assertIn("goal: исследование", context[0]["content"])
        self.assertEqual(context[1]["content"], "принято")

    def test_two_branches_inherit_checkpoint_but_not_each_other(self) -> None:
        main = self.memory.get_active_branch(self.conversation.id)
        self.add_exchange(main.id, "общая цель", "принято")
        self.memory.create_checkpoint(self.conversation.id, "base")
        first = self.memory.create_branch(self.conversation.id, "first", "base")
        second = self.memory.create_branch(self.conversation.id, "second", "base")
        self.add_exchange(first.id, "решение A", "ветка A")
        self.add_exchange(second.id, "решение B", "ветка B")

        first_context = BranchingStrategy().build(
            self.memory.get_branch_history(first.id), []
        )
        second_context = BranchingStrategy().build(
            self.memory.get_branch_history(second.id), []
        )
        first_text = " ".join(item["content"] for item in first_context)
        second_text = " ".join(item["content"] for item in second_context)
        self.assertIn("общая цель", first_text)
        self.assertIn("общая цель", second_text)
        self.assertIn("решение A", first_text)
        self.assertNotIn("решение B", first_text)
        self.assertIn("решение B", second_text)
        self.assertNotIn("решение A", second_text)

    def test_facts_agent_persists_facts_and_both_usage_types(self) -> None:
        facts_conversation = self.memory.create_conversation("facts", "facts")
        agent = BublikAgent(FakeClient(), self.memory, facts_conversation.id)

        response = agent.process("Наша цель — исследование")

        self.assertEqual(response.content, "Принято.")
        self.assertEqual(agent.get_facts()[0].value, "исследование")
        usage = agent.get_usage()
        self.assertEqual(usage.request_count, 1)
        self.assertEqual(usage.fact_update_count, 1)
        self.assertEqual(usage.total_tokens, 15)
        self.assertEqual(usage.fact_update_tokens, 15)


if __name__ == "__main__":
    unittest.main()
