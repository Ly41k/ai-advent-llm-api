"""Сборка prompt из персонализации и трёх слоёв памяти."""

from models import (
    AssistantIdentity,
    MemoryEntry,
    Message,
    TaskContext,
    UserProfile,
    WorkingNote,
)


class MemoryPromptBuilder:
    def build(
        self,
        assistant: AssistantIdentity,
        profile: UserProfile,
        invariants: dict,
        short_term: list[Message],
        task: TaskContext | None,
        working_notes: list[WorkingNote],
        long_term: list[MemoryEntry],
    ) -> list[dict[str, str]]:
        messages = [
            {"role": "system", "content": self._base_prompt(assistant, invariants)},
            {"role": "system", "content": self._profile_prompt(profile)},
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
    def _base_prompt(assistant: AssistantIdentity, invariants: dict) -> str:
        stack = "\n".join(f"- {item}" for item in invariants["stack"])
        architecture = "\n".join(f"- {item}" for item in invariants["architecture"])
        rules = "\n".join(
            f"- {item['id']}: {item['description']}" for item in invariants["rules"]
        )
        return (
            "[ASSISTANT IDENTITY]\n"
            f"Ты {assistant.name}, {assistant.role}.\n\n"
            f"[INVARIANTS]\nSTACK:\n{stack}\n\n"
            f"ARCHITECTURE:\n{architecture}\n\nRULES:\n{rules}\n\n"
            "Следуй текущему состоянию задачи. Не выполняй действия будущих этапов."
        )

    @staticmethod
    def _profile_prompt(profile: UserProfile) -> str:
        style = "\n".join(f"- {item}" for item in profile.style)
        response_format = "\n".join(
            f"- {item}" for item in profile.response_format
        )
        constraints = "\n".join(f"- {item}" for item in profile.constraints)
        return (
            "[USER PROFILE — APPLY AUTOMATICALLY]\n"
            f"Profile ID: {profile.id}\n"
            f"Пользователь: {profile.name}, {profile.role}.\n"
            f"Язык: {profile.language}.\n"
            f"Уровень детализации: {profile.detail_level}.\n\n"
            f"STYLE:\n{style}\n\n"
            f"RESPONSE FORMAT:\n{response_format}\n\n"
            f"USER CONSTRAINTS:\n{constraints}\n\n"
            "Применяй профиль к каждому ответу автоматически. "
            "Пользователь не обязан повторять эти предпочтения в запросе."
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
