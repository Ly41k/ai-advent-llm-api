"""Детерминированная проверка ответа по формализованным invariants."""

import re

from models import InvariantCheckResult


class InvariantValidator:
    def validate(self, content: str, invariants: dict) -> InvariantCheckResult:
        violations: list[str] = []
        checked: list[str] = []
        if not content.strip():
            violations.append("empty_response: модель вернула пустой ответ")
        checked.append("empty_response")

        for rule in invariants.get("rules", []):
            rule_id = str(rule.get("id", "unknown_rule"))
            checked.append(rule_id)
            for pattern in rule.get("forbidden_patterns", []):
                if re.search(pattern, content, flags=re.IGNORECASE):
                    violations.append(f"{rule_id}: {rule.get('description', pattern)}")
                    break

        return InvariantCheckResult(
            passed=not violations,
            checked=checked,
            violations=violations,
        )
