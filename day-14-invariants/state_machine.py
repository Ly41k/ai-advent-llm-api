"""Конечный автомат задачи с паузой и контролируемыми переходами."""

from dataclasses import replace

from models import TaskContext, TaskState


ALLOWED_TRANSITIONS = {
    TaskState.PLANNING: {TaskState.EXECUTION},
    TaskState.EXECUTION: {TaskState.VALIDATION, TaskState.PLANNING},
    TaskState.VALIDATION: {TaskState.DONE, TaskState.EXECUTION},
    TaskState.DONE: set(),
}


class InvalidStateTransition(ValueError):
    pass


class TaskStateMachine:
    def transition(self, context: TaskContext, target: TaskState) -> TaskContext:
        self.ensure_active(context)
        if target not in ALLOWED_TRANSITIONS[context.state]:
            raise InvalidStateTransition(
                f"Переход {context.state.value} -> {target.value} запрещён"
            )
        self._validate_guard(context, target)
        current = context.current
        step = context.step
        done = context.done
        if target is TaskState.EXECUTION and context.state is TaskState.PLANNING:
            step = 1
            current = context.plan[0]
        if target is TaskState.EXECUTION and context.state is TaskState.VALIDATION:
            # Неуспешная проверка возвращает последний шаг на доработку.
            step = context.total
            current = context.plan[-1]
            done = context.done[:-1]
        if target is TaskState.PLANNING:
            step = 0
            current = None
            done = []
        return replace(
            context,
            state=target,
            step=step,
            current=current,
            done=done,
            validation_passed=(
                context.validation_passed if target is TaskState.DONE else False
            ),
            validation_details=(
                context.validation_details if target is TaskState.DONE else None
            ),
        )

    def complete_current_step(self, context: TaskContext) -> TaskContext:
        self.ensure_active(context)
        if context.state is not TaskState.EXECUTION:
            raise InvalidStateTransition("Шаги можно завершать только в execution")
        if context.current is None:
            raise InvalidStateTransition("В плане нет текущего шага")
        done = [*context.done, context.current]
        next_index = len(done)
        current = context.plan[next_index] if next_index < context.total else None
        return replace(
            context,
            done=done,
            step=min(next_index + 1, context.total),
            current=current,
        )

    @staticmethod
    def pause(context: TaskContext) -> TaskContext:
        if context.state is TaskState.DONE:
            raise InvalidStateTransition("Завершённую задачу нельзя поставить на паузу")
        if context.paused:
            raise InvalidStateTransition("Задача уже на паузе")
        return replace(context, paused=True)

    @staticmethod
    def resume(context: TaskContext) -> TaskContext:
        if not context.paused:
            raise InvalidStateTransition("Задача не находится на паузе")
        return replace(context, paused=False)

    @staticmethod
    def ensure_active(context: TaskContext) -> None:
        if context.paused:
            raise InvalidStateTransition(
                "Задача на паузе. Сначала выполните /task resume"
            )

    @staticmethod
    def _validate_guard(context: TaskContext, target: TaskState) -> None:
        if context.state is TaskState.PLANNING and target is TaskState.EXECUTION:
            if not context.plan:
                raise InvalidStateTransition("Нельзя начать выполнение без плана")
        if context.state is TaskState.EXECUTION and target is TaskState.VALIDATION:
            if len(context.done) != context.total:
                raise InvalidStateTransition("Сначала завершите все шаги плана")
        if context.state is TaskState.VALIDATION and target is TaskState.EXECUTION:
            if context.validation_details is None:
                raise InvalidStateTransition("Сначала сохраните результат проверки")
            if context.validation_passed:
                raise InvalidStateTransition(
                    "Успешная проверка ожидает завершения задачи"
                )
        if context.state is TaskState.VALIDATION and target is TaskState.DONE:
            if not context.validation_passed:
                raise InvalidStateTransition("Нельзя завершить задачу без успешной проверки")
