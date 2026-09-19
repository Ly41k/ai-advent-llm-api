"""Pure text rendering for task status; safe to test without API dependencies."""

from models import TaskContext


def format_task_status(
    task: TaskContext | None,
    allowed_transitions: tuple[str, ...] = (),
) -> str:
    lines = ["WORKING MEMORY — TASK", "=" * 70]
    if task is None:
        lines.append("Активная задача не создана.")
        return "\n".join(lines)
    lines.extend(
        [
            f"Задача: {task.task}",
            f"Этап: {task.state.value}",
            f"Пауза: {'да' if task.paused else 'нет'}",
            f"План утверждён: {'да' if task.plan_approved else 'нет'}",
            f"Прогресс: {len(task.done)}/{task.total}",
            f"Текущий шаг: {task.current or '—'}",
            f"Ожидаемое действие: {task.expected_action.value}",
            "Разрешённые переходы: "
            + (", ".join(allowed_transitions) if allowed_transitions else "нет"),
            f"Проверка: {'PASS' if task.validation_passed else 'NOT PASSED'}",
        ]
    )
    if task.validation_details:
        lines.append(f"Результат проверки: {task.validation_details}")
    for index, step in enumerate(task.plan, 1):
        marker = "✓" if step in task.done else "·"
        lines.append(f"{marker} {index}. {step}")
    return "\n".join(lines)
