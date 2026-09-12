"""Подсчёт токенов, стоимости и экономии после сжатия контекста."""

from dataclasses import dataclass

import tiktoken


MODEL_NAME = "openai/gpt-oss-20b"
MODEL_CONTEXT_WINDOW = 131_072

# Ограничение текущего Groq tier — 8K TPM.
# Не используем весь лимит, чтобы оставить безопасный запас.
GROQ_TPM_LIMIT = 8_000
SAFE_REQUEST_TOKEN_LIMIT = 6_000

MAX_COMPLETION_TOKENS = 1_200
SUMMARY_MAX_COMPLETION_TOKENS = 600

INPUT_PRICE_PER_MILLION = 0.075
OUTPUT_PRICE_PER_MILLION = 0.30


@dataclass(frozen=True)
class ContextTokenEstimate:
    """Локальная оценка размера контекста до обращения к API."""

    current_request_tokens: int
    history_tokens: int
    prompt_tokens: int
    reserved_completion_tokens: int
    context_window: int

    @property
    def total_reserved_tokens(self) -> int:
        return self.prompt_tokens + self.reserved_completion_tokens

    @property
    def remaining_tokens(self) -> int:
        return self.context_window - self.total_reserved_tokens

    @property
    def fits_context_window(self) -> bool:
        return self.remaining_tokens >= 0


@dataclass(frozen=True)
class RequestTokenUsage:
    """Метрики запроса с полным и сжатым вариантами истории."""

    current_request_tokens: int
    full_history_tokens: int
    compressed_history_tokens: int
    saved_history_tokens: int
    estimated_prompt_tokens: int
    api_prompt_tokens: int
    completion_tokens: int
    visible_response_tokens: int
    total_tokens: int
    estimated_cost_usd: float


@dataclass(frozen=True)
class SummaryTokenUsage:
    """API-метрики одного обновления summary."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float


class GptOssTokenCounter:
    """Считает токены GPT-OSS с помощью кодировки o200k_harmony."""

    def __init__(self) -> None:
        self._encoding = tiktoken.get_encoding("o200k_harmony")

    def count_text(self, text: str) -> int:
        """Возвращает число токенов в обычном тексте."""

        return len(self._encoding.encode(text, disallowed_special=()))

    def count_messages(
        self,
        messages: list[dict[str, str]],
        add_generation_prompt: bool = False,
    ) -> int:
        """Оценивает токены сообщений вместе со служебной разметкой ролей."""

        rendered_messages = "".join(
            (
                f"<|start|>{message['role']}<|message|>"
                f"{message['content']}<|end|>\n"
            )
            for message in messages
        )
        if add_generation_prompt:
            rendered_messages += "<|start|>assistant"
        return len(
            self._encoding.encode(
                rendered_messages,
                allowed_special="all",
            )
        )

    def estimate_context(
        self,
        system_prompt: str,
        history: list[dict[str, str]],
        current_input: str,
        reserved_completion_tokens: int = MAX_COMPLETION_TOKENS,
        context_window: int = MODEL_CONTEXT_WINDOW,
    ) -> ContextTokenEstimate:
        """Оценивает текущий запрос, историю и полный prompt."""

        current_message = {"role": "user", "content": current_input}
        prompt = [
            {"role": "system", "content": system_prompt},
            *history,
            current_message,
        ]
        return ContextTokenEstimate(
            current_request_tokens=self.count_text(current_input),
            history_tokens=self.count_messages(history) if history else 0,
            prompt_tokens=self.count_messages(prompt, add_generation_prompt=True),
            reserved_completion_tokens=reserved_completion_tokens,
            context_window=context_window,
        )

    def build_usage(
        self,
        estimate: ContextTokenEstimate,
        response_text: str,
        api_prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        full_history_tokens: int,
    ) -> RequestTokenUsage:
        """Объединяет оценку контекста с фактическими данными Groq."""

        return RequestTokenUsage(
            current_request_tokens=estimate.current_request_tokens,
            full_history_tokens=full_history_tokens,
            compressed_history_tokens=estimate.history_tokens,
            saved_history_tokens=max(
                full_history_tokens - estimate.history_tokens,
                0,
            ),
            estimated_prompt_tokens=estimate.prompt_tokens,
            api_prompt_tokens=api_prompt_tokens,
            completion_tokens=completion_tokens,
            visible_response_tokens=self.count_text(response_text),
            total_tokens=total_tokens,
            estimated_cost_usd=estimate_request_cost(
                prompt_tokens=api_prompt_tokens,
                completion_tokens=completion_tokens,
            ),
        )


def estimate_request_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Оценивает стоимость запроса по тарифам GPT-OSS 20B."""

    return (
        prompt_tokens * INPUT_PRICE_PER_MILLION
        + completion_tokens * OUTPUT_PRICE_PER_MILLION
    ) / 1_000_000
