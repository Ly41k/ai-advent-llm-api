import unittest

from models import TaskContext, TaskState
from state_machine import InvalidStateTransition, TaskStateMachine
from task_view import format_task_status


def context(state=TaskState.PLANNING, plan=None, done=None, **kwargs):
    plan = ["one", "two"] if plan is None else plan
    done = [] if done is None else done
    current = kwargs.pop("current", plan[len(done)] if len(done) < len(plan) else None)
    return TaskContext(
        task="controlled lifecycle",
        state=state,
        step=len(done),
        plan=plan,
        done=done,
        current=current,
        validation_passed=kwargs.pop("validation_passed", False),
        validation_details=kwargs.pop("validation_details", None),
        paused=kwargs.pop("paused", False),
        plan_approved=kwargs.pop("plan_approved", True),
    )


class ControlledTransitionTests(unittest.TestCase):
    def setUp(self):
        self.machine = TaskStateMachine()

    def test_allowed_targets_are_explicit_for_each_stage(self):
        self.assertEqual(self.machine.allowed_target_names(context()), ("execution",))
        self.assertEqual(
            self.machine.allowed_target_names(
                context(TaskState.EXECUTION, done=["one"], current="two")
            ),
            ("planning",),
        )
        self.assertEqual(
            self.machine.allowed_target_names(
                context(TaskState.VALIDATION, done=["one", "two"],
                        current=None, validation_details="FAIL")
            ),
            ("execution",),
        )
        self.assertEqual(self.machine.allowed_target_names(context(TaskState.DONE)), ())

    def test_planning_cannot_jump_to_validation_or_done(self):
        for target in (TaskState.VALIDATION, TaskState.DONE):
            with self.assertRaisesRegex(InvalidStateTransition, "Доступные сейчас переходы: execution"):
                self.machine.transition(context(), target)

    def test_execution_cannot_jump_to_done(self):
        task = context(TaskState.EXECUTION, done=["one", "two"], current=None)
        with self.assertRaisesRegex(InvalidStateTransition, "execution -> done"):
            self.machine.transition(task, TaskState.DONE)

    def test_validation_requires_pass_for_done(self):
        task = context(
            TaskState.VALIDATION,
            done=["one", "two"],
            current=None,
            validation_details="FAIL",
        )
        with self.assertRaisesRegex(InvalidStateTransition, "без успешной проверки"):
            self.machine.transition(task, TaskState.DONE)

    def test_guards_control_the_transitions_reported_as_available(self):
        no_plan = context(plan=[], plan_approved=False, current=None)
        self.assertEqual(self.machine.allowed_target_names(no_plan), ())

        unapproved = context(plan_approved=False)
        self.assertEqual(self.machine.allowed_target_names(unapproved), ())

        incomplete = context(
            TaskState.EXECUTION, done=["one"], current="two"
        )
        self.assertEqual(
            self.machine.allowed_target_names(incomplete), ("planning",)
        )

        failed = context(
            TaskState.VALIDATION,
            done=["one", "two"],
            current=None,
            validation_details="FAIL",
        )
        self.assertEqual(
            self.machine.allowed_target_names(failed), ("execution",)
        )

    def test_task_status_prints_only_currently_available_transitions(self):
        task = context(plan_approved=False)
        output = format_task_status(
            task,
            self.machine.allowed_target_names(task),
        )
        self.assertIn("Разрешённые переходы: нет", output)
        self.assertNotIn("Разрешённые переходы: execution", output)

    def test_pause_removes_all_implicit_transitions_and_resume_preserves_stage(self):
        task = context(TaskState.EXECUTION, done=["one"], current="two")
        paused = self.machine.pause(task)
        self.assertEqual(self.machine.allowed_targets(paused), ())
        with self.assertRaisesRegex(InvalidStateTransition, "на паузе"):
            self.machine.transition(paused, TaskState.VALIDATION)
        resumed = self.machine.resume(paused)
        self.assertEqual(resumed.state, TaskState.EXECUTION)
        self.assertEqual(resumed.current, "two")
        self.assertEqual(self.machine.allowed_target_names(resumed), ("planning",))


if __name__ == "__main__":
    unittest.main()
