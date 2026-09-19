"""Бублик с памятью, Task State Machine и обязательными invariants."""

from dataclasses import replace

from configuration import ConfigurationLoader
from memory import SQLiteMemoryRepository
from models import (
    AgentResponse,
    LongTermKind,
    TaskContext,
    TaskState,
)
from prompt_builder import MemoryPromptBuilder
from semantic_guard import SemanticGuardError, SemanticInvariantGuard
from state_machine import TaskStateMachine
from validators import InvariantValidator


SHORT_TERM_LIMIT = 6
MODEL_NAME = "openai/gpt-oss-20b"
MAX_COMPLETION_TOKENS = 1_200


class AgentError(RuntimeError):
    pass


class BublikAgent:
    def __init__(
        self,
        client,
        memory: SQLiteMemoryRepository,
        configuration: ConfigurationLoader,
        conversation_id: str,
        prompt_builder: MemoryPromptBuilder | None = None,
        validator: InvariantValidator | None = None,
        semantic_guard: SemanticInvariantGuard | None = None,
        state_machine: TaskStateMachine | None = None,
    ) -> None:
        conversation = memory.get_conversation(conversation_id)
        if conversation is None:
            raise AgentError("Выбранный диалог не найден")
        configuration.load_profile(conversation.profile_id)
        self._client = client
        self._memory = memory
        self._configuration = configuration
        self._conversation_id = conversation_id
        self._prompt_builder = prompt_builder or MemoryPromptBuilder()
        self._validator = validator or InvariantValidator()
        self._semantic_guard = semantic_guard or SemanticInvariantGuard(
            client, MODEL_NAME
        )
        self._state_machine = state_machine or TaskStateMachine()

    def process(self, user_input: str) -> AgentResponse:
        prepared = user_input.strip()
        if not prepared:
            raise AgentError("Запрос не может быть пустым")
        invariants = self._configuration.load_invariants()
        request_validation = self._validator.validate_request(
            prepared, invariants
        )
        prompt = self.get_context_preview(invariants)
        user_message_id = self._memory.start_user_request(
            self._conversation_id, prepared
        )
        try:
            if not request_validation.passed:
                return self._complete_refusal(
                    user_message_id, request_validation, invariants, "request"
                )
            semantic_request_validation = self._semantic_guard.validate_request(
                prepared, invariants
            )
            if not semantic_request_validation.passed:
                return self._complete_refusal(
                    user_message_id,
                    semantic_request_validation,
                    invariants,
                    "request",
                )
            response = self._client.chat.completions.create(
                model=MODEL_NAME,
                messages=[*prompt, {"role": "user", "content": prepared}],
                temperature=0.2,
                reasoning_effort="low",
                max_completion_tokens=MAX_COMPLETION_TOKENS,
            )
            content = (response.choices[0].message.content or "").strip()
            validation = self._validator.validate_response(content, invariants)
            if not validation.passed:
                return self._complete_refusal(
                    user_message_id, validation, invariants, "response"
                )
            semantic_response_validation = self._semantic_guard.validate_response(
                content, invariants, task=self.get_task()
            )
            if not semantic_response_validation.passed:
                return self._complete_refusal(
                    user_message_id,
                    semantic_response_validation,
                    invariants,
                    "response",
                )
            self._memory.complete_exchange(
                user_message_id, self._conversation_id, content
            )
            return self._build_response(content, semantic_response_validation)
        except Exception as error:
            self._memory.fail_request(user_message_id, str(error))
            if isinstance(error, AgentError):
                raise
            if isinstance(error, SemanticGuardError):
                raise AgentError(
                    "Не удалось подтвердить соблюдение invariants; "
                    "ответ заблокирован безопасным образом"
                ) from error
            raise AgentError(f"Не удалось обработать запрос: {error}") from error

    def get_context_preview(self, invariants=None) -> list[dict[str, str]]:
        task = self.get_task()
        return self._prompt_builder.build(
            assistant=self._configuration.load_assistant(),
            profile=self.get_profile(),
            invariants=invariants or self._configuration.load_invariants(),
            short_term=self.get_short_term(),
            task=task,
            working_notes=self.get_working_notes(),
            long_term=self.get_long_term(),
            allowed_transitions=(
                self._state_machine.allowed_target_names(task)
                if task is not None
                else ()
            ),
        )

    def get_allowed_transitions(self) -> tuple[str, ...]:
        task = self.get_task()
        if task is None:
            return ()
        return self._state_machine.allowed_target_names(task)

    def get_invariants(self):
        return self._configuration.load_invariants()

    def get_short_term(self):
        return self._memory.get_short_term(
            self._conversation_id, SHORT_TERM_LIMIT
        )

    def get_full_history(self):
        return self._memory.get_full_history(self._conversation_id)

    def get_task(self) -> TaskContext | None:
        return self._memory.get_task_context(self._conversation_id)

    def get_working_notes(self):
        return self._memory.get_working_notes(self._conversation_id)

    def get_long_term(self):
        return self._memory.get_long_term(self.get_profile().id)

    def get_profile(self):
        conversation = self._memory.get_conversation(self._conversation_id)
        if conversation is None:
            raise AgentError("Выбранный диалог не найден")
        return self._configuration.load_profile(conversation.profile_id)

    def switch_profile(self, profile_id: str):
        conversation = self._memory.get_conversation(self._conversation_id)
        if conversation is None:
            raise AgentError("Выбранный диалог не найден")
        if conversation.message_count or self.get_task() or self.get_working_notes():
            raise ValueError(
                "Профиль можно сменить только в пустом диалоге без рабочей памяти"
            )
        profile = self._configuration.load_profile(profile_id)
        self._memory.set_conversation_profile(self._conversation_id, profile.id)
        return profile

    def create_task(self, task: str) -> TaskContext:
        prepared = task.strip()
        if not prepared:
            raise ValueError("Описание задачи не может быть пустым")
        context = TaskContext(
            task=prepared,
            state=TaskState.PLANNING,
            step=0,
            plan=[],
            done=[],
            current=None,
            validation_passed=False,
        )
        self._memory.save_task_context(self._conversation_id, context)
        return context

    def set_plan(self, plan: list[str]) -> TaskContext:
        context = self._require_task()
        self._state_machine.ensure_active(context)
        if context.state is not TaskState.PLANNING:
            raise ValueError("План можно менять только в состоянии planning")
        prepared = [item.strip() for item in plan if item.strip()]
        if not prepared:
            raise ValueError("План должен содержать хотя бы один шаг")
        updated = replace(
            context,
            plan=prepared,
            done=[],
            step=0,
            current=None,
            validation_passed=False,
            validation_details=None,
            plan_approved=False,
        )
        self._memory.save_task_context(self._conversation_id, updated)
        return updated

    def approve_plan(self) -> TaskContext:
        updated = self._state_machine.approve_plan(self._require_task())
        self._memory.save_task_context(self._conversation_id, updated)
        return updated

    def transition_task(self, target: TaskState | str) -> TaskContext:
        context = self._require_task()
        updated = self._state_machine.transition(context, TaskState(target))
        self._memory.save_task_context(self._conversation_id, updated)
        return updated

    def complete_current_step(self) -> TaskContext:
        updated = self._state_machine.complete_current_step(self._require_task())
        self._memory.save_task_context(self._conversation_id, updated)
        return updated

    def pause_task(self) -> TaskContext:
        updated = self._state_machine.pause(self._require_task())
        self._memory.save_task_context(self._conversation_id, updated)
        return updated

    def resume_task(self) -> TaskContext:
        updated = self._state_machine.resume(self._require_task())
        self._memory.save_task_context(self._conversation_id, updated)
        return updated

    def record_task_validation(self, passed: bool, details: str) -> TaskContext:
        context = self._require_task()
        self._state_machine.ensure_active(context)
        if context.state is not TaskState.VALIDATION:
            raise ValueError("Результат проверки сохраняется только в validation")
        prepared_details = details.strip()
        if not prepared_details:
            raise ValueError("Добавьте описание результата проверки")
        updated = replace(
            context,
            validation_passed=passed,
            validation_details=prepared_details,
        )
        self._memory.save_task_context(self._conversation_id, updated)
        return updated

    def remember_working(self, key: str, value: str) -> None:
        self._memory.save_working_note(self._conversation_id, key, value)

    def remember_long_term(
        self,
        kind: LongTermKind | str,
        key: str,
        value: str,
    ) -> None:
        self._memory.save_long_term(
            self.get_profile().id, LongTermKind(kind), key, value
        )

    def _require_task(self) -> TaskContext:
        context = self.get_task()
        if context is None:
            raise ValueError("Сначала создайте задачу")
        return context

    def _complete_refusal(
        self,
        user_message_id: int,
        validation,
        invariants,
        source: str,
    ) -> AgentResponse:
        refusal = self._validator.build_refusal(
            validation, invariants, source=source
        )
        self._memory.complete_exchange(
            user_message_id, self._conversation_id, refusal
        )
        return self._build_response(
            refusal,
            validation,
            refused_by_invariants=True,
        )

    def _build_response(
        self,
        content,
        validation,
        refused_by_invariants: bool = False,
    ) -> AgentResponse:
        return AgentResponse(
            content=content,
            profile_id=self.get_profile().id,
            validation=validation,
            task_context=self.get_task(),
            short_term_messages=len(self.get_short_term()),
            working_memory_items=(
                len(self.get_working_notes()) + (1 if self.get_task() else 0)
            ),
            long_term_items=len(self.get_long_term()) + 1,
            refused_by_invariants=refused_by_invariants,
        )
