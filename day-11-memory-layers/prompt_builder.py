"""Явная сборка prompt из трёх слоёв памяти."""

from models import MemoryEntry, Message, Profile, TaskContext, WorkingNote


class MemoryPromptBuilder:
    def build(
        self,
        profile: Profile,
        invariants: dict,
        short_term: list[Message],
        task: TaskContext | None,
        working_notes: list[WorkingNote],
        long_term: list[MemoryEntry],
    ) -> list[dict[str, str]]:
        messages = [
            {"role": "system", "content": self._base_prompt(profile, invariants)},
            {"role": "system", "content": self._long_term_prompt(long_term)},
            {
                "role": "system",
                "content": self._working_memory_prompt(task, working_notes),
            },
        ]
        messages.extend(
            {"role": message.role, "content": message.content}
            for message in short_term
        )
        return messages

    @staticmethod
    def _base_prompt(profile: Profile, invariants: dict) -> str:
        style = "\n".join(f"- {item}" for item in profile.style)
        constraints = "\n".join(f"- {item}" for item in profile.constraints)
        stack = "\n".join(f"- {item}" for item in invariants["stack"])
        architecture = "\n".join(f"- {item}" for item in invariants["architecture"])
        rules = "\n".join(
            f"- {item['id']}: {item['description']}" for item in invariants["rules"]
        )
        return (
            "[PROFILE — LONG-TERM MEMORY]\n"
            f"Ты {profile.name}, {profile.role}. Пользователь — {profile.user_name}.\n"
            f"Язык ответа: {profile.language}.\n\nSTYLE:\n{style}\n\n"
            f"CONSTRAINTS:\n{constraints}\n\n[INVARIANTS]\nSTACK:\n{stack}\n\n"
            f"ARCHITECTURE:\n{architecture}\n\nRULES:\n{rules}\n\n"
            "Следуй текущему состоянию задачи. Не выполняй действия будущих этапов."
        )

    @staticmethod
    def _long_term_prompt(entries: list[MemoryEntry]) -> str:
        lines = ["[LONG-TERM MEMORY — DECISIONS AND KNOWLEDGE]"]
        if not entries:
            lines.append("Нет сохранённых решений и знаний.")
        else:
            lines.extend(
                f"- {entry.kind.value}.{entry.key}: {entry.value}" for entry in entries
            )
        return "\n".join(lines)

    @staticmethod
    def _working_memory_prompt(
        task: TaskContext | None,
        notes: list[WorkingNote],
    ) -> str:
        lines = ["[WORKING MEMORY — CURRENT TASK]"]
        if task is None:
            lines.append("Активная задача не создана.")
        else:
            lines.extend(
                [
                    f"Task: {task.task}",
                    f"State: {task.state.value}",
                    f"Progress: {len(task.done)}/{task.total}",
                    f"Current: {task.current or '—'}",
                    "Plan:",
                ]
            )
            lines.extend(f"{index}. {item}" for index, item in enumerate(task.plan, 1))
            lines.append("Completed: " + (", ".join(task.done) or "—"))
            lines.append(
                "Task validation: "
                + ("PASS" if task.validation_passed else "NOT PASSED")
            )
        lines.append("Working notes:")
        lines.extend(f"- {note.key}: {note.value}" for note in notes)
        if not notes:
            lines.append("- нет")
        return "\n".join(lines)
