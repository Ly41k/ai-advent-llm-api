"""Извлечение устойчивых key-value facts из сообщений пользователя."""

import json
from dataclasses import dataclass

from groq import Groq

from memory import Fact
from tokens import FactUpdateUsage, MODEL_NAME, estimate_request_cost


FACTS_MAX_COMPLETION_TOKENS = 500
FACTS_SYSTEM_PROMPT = (
    "Ты обновляешь key-value память космической симуляции. "
    "Это не summary и не пересказ диалога. Храни только устойчивые данные: "
    "цель, ограничения, предпочтения, выбранные параметры, решения и "
    "договорённости. Верни полный актуальный JSON-объект со строковыми "
    "ключами и значениями. Сохрани прежний факт, если новое сообщение его "
    "не меняет. Замени значение при явном исправлении. Не сохраняй приветствия, "
    "вопросы и временные детали. Ничего не выдумывай. Верни только JSON."
)


@dataclass(frozen=True)
class FactsUpdate:
    facts: dict[str, str]
    usage: FactUpdateUsage


class FactsExtractor:
    def __init__(self, client: Groq, model: str = MODEL_NAME) -> None:
        self._client = client
        self._model = model

    def update(self, current_facts: list[Fact], user_input: str) -> FactsUpdate:
        existing = {fact.key: fact.value for fact in current_facts}
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": FACTS_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Текущие facts:\n"
                        f"{json.dumps(existing, ensure_ascii=False)}\n\n"
                        "Новое сообщение капитана:\n"
                        f"{user_input}"
                    ),
                },
            ],
            temperature=0.0,
            reasoning_effort="low",
            max_completion_tokens=FACTS_MAX_COMPLETION_TOKENS,
        )
        content = (response.choices[0].message.content or "").strip()
        facts = self._parse_json_object(content)
        usage = FactUpdateUsage(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            estimated_cost_usd=estimate_request_cost(
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            ),
        )
        return FactsUpdate(facts=facts, usage=usage)

    @staticmethod
    def _parse_json_object(content: str) -> dict[str, str]:
        prepared = content
        if prepared.startswith("```"):
            lines = prepared.splitlines()
            prepared = "\n".join(lines[1:-1])
        try:
            value = json.loads(prepared)
        except json.JSONDecodeError as error:
            raise ValueError("Модель вернула некорректный JSON для facts") from error
        if not isinstance(value, dict):
            raise ValueError("Facts должны быть JSON-объектом")
        return {
            str(key).strip(): str(item).strip()
            for key, item in value.items()
            if str(key).strip() and str(item).strip()
        }
