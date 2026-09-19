"""Preflight- и postflight-проверки по отдельной invariant policy."""

import re

from models import InvariantCheckResult, InvariantPolicy


class InvariantValidator:
    def validate_request(
        self,
        content: str,
        policy: InvariantPolicy,
    ) -> InvariantCheckResult:
        return self._validate_patterns(
            content,
            policy,
            pattern_attribute="request_conflict_patterns",
        )

    def validate_response(
        self,
        content: str,
        policy: InvariantPolicy,
    ) -> InvariantCheckResult:
        result = self._validate_patterns(
            content,
            policy,
            pattern_attribute="response_forbidden_patterns",
        )
        if content.strip():
            return result
        return InvariantCheckResult(
            passed=False,
            checked=["empty_response", *result.checked],
            violations=["empty_response", *result.violations],
            explanations=["Модель вернула пустой ответ", *result.explanations],
        )

    @staticmethod
    def build_refusal(
        result: InvariantCheckResult,
        policy: InvariantPolicy,
        source: str = "request",
    ) -> str:
        violated = {
            invariant.id: invariant
            for invariant in policy.invariants
            if invariant.id in result.violations
        }
        opening = (
            "Не могу выполнить запрос в предложенном виде: "
            "он конфликтует с обязательными инвариантами проекта."
            if source == "request"
            else
            "Не могу предоставить подготовленный ответ: проверка обнаружила "
            "конфликт с обязательными инвариантами проекта."
        )
        lines = [
            opening,
            "",
            "Нарушенные инварианты:",
        ]
        for invariant_id in result.violations:
            invariant = violated.get(invariant_id)
            if invariant is None:
                explanation = next(
                    iter(result.explanations),
                    "Проверка ответа не была пройдена",
                )
                lines.extend(
                    [
                        f"- [{invariant_id}] {explanation}",
                        "  Почему: ответ нельзя безопасно подтвердить.",
                        "  Совместимый вариант: повторить запрос или уточнить его.",
                    ]
                )
                continue
            lines.extend(
                [
                    f"- [{invariant.id}] {invariant.description}",
                    f"  Почему: {invariant.rationale}",
                    f"  Совместимый вариант: {invariant.compatible_alternative}",
                ]
            )
        lines.extend(
            [
                "",
                "Инварианты хранятся отдельно от диалога "
                "и не могут быть отменены сообщением пользователя.",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _validate_patterns(
        content: str,
        policy: InvariantPolicy,
        pattern_attribute: str,
    ) -> InvariantCheckResult:
        checked: list[str] = []
        violations: list[str] = []
        explanations: list[str] = []
        for invariant in policy.invariants:
            checked.append(invariant.id)
            patterns = getattr(invariant, pattern_attribute)
            if any(
                re.search(pattern, content, flags=re.IGNORECASE)
                for pattern in patterns
            ):
                violations.append(invariant.id)
                explanations.append(invariant.description)
        return InvariantCheckResult(
            passed=not violations,
            checked=checked,
            violations=violations,
            explanations=explanations,
        )
