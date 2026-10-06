"""Three reproducible prompts and application-owned acceptance checks."""

import json
from pathlib import Path

SYSTEM_PROMPT = (
    "Ты Бублик, бортовой помощник исследовательского корабля Чебуратора. "
    "Отвечай кратко и точно на языке запроса. Следуй требуемому формату. "
    "Если передан контекст, используй только его для фактов о проекте. "
    "Не придумывай неизвестные сведения. Для JSON не добавляй Markdown или пояснения."
)


ENERGY_INPUTS = {"budget": 3600, "activation_cost": 1200, "cycle_cost": 400}


def calculate_energy(budget, activation_cost, cycle_cost):
    """Trusted application tool; the LLM never executes arbitrary Python code."""
    if any(type(x) is not int for x in (budget, activation_cost, cycle_cost)):
        raise ValueError("Energy inputs must be integers")
    if budget < 0 or activation_cost < 0 or cycle_cost <= 0:
        raise ValueError("Budget/activation must be nonnegative and cycle cost positive")
    if budget < activation_cost:
        raise ValueError("Insufficient energy for activation")
    cycles, remaining = divmod(budget - activation_cost, cycle_cost)
    return {"cycles": cycles, "total_cost": budget - remaining, "remaining": remaining}


def load_examples():
    fixture = json.loads((Path(__file__).parent / "fixtures/day18-context.json").read_text(encoding="utf-8"))
    energy_result = calculate_energy(**ENERGY_INPUTS)
    return [
        {"id": "simple", "difficulty": "simple", "title": "Простой ответ",
         "prompt": "Чему равно 2 + 2? Ответь только одним числом.", "source": None},
        {"id": "calculation", "difficulty": "medium", "title": "Расчёт с инструментом",
         "prompt": "У корабля 3600 единиц энергии. Активация сканера стоит 1200, "
                   "каждый полный цикл сканирования стоит 400. Энергия не восстанавливается. "
                   "Нужны максимальное число полных циклов после одной активации, "
                   "общий расход вместе с активацией и остаток энергии.\n"
                   "Приложение уже вызвало доверенный инструмент calculate_energy. "
                   "Это фактический результат вычисления на Python, а не предположение модели.\n"
                   "Входы инструмента: " + json.dumps(ENERGY_INPUTS, ensure_ascii=False) + "\n"
                   "Результат инструмента: " + json.dumps(energy_result, ensure_ascii=False) + "\n"
                   "Верни результат инструмента как единственный JSON-объект "
                   "с целочисленными полями cycles, total_cost, remaining. "
                   "Сохрани все три вычисленных значения. Пояснения и Markdown не добавляй.",
         "source": {"kind": "application tool result; not unaided model arithmetic",
                    "tool": "calculate_energy", "inputs": dict(ENERGY_INPUTS), "result": energy_result}},
        {"id": "grounded_json", "difficulty": "complex", "title": "JSON с точной цитатой",
         "prompt": "Контекст из README проекта:\n" + fixture["text"] + "\n\n"
                   "По этому контексту верни только JSON с полями: "
                   "worker (имя файла процесса), database (имя SQLite-файла), "
                   "metrics (массив названий трёх GitHub-метрик), "
                   "delivery (массив каналов вывода: stdout и systemd journal), "
                   "quote (полное предложение из контекста о каналах вывода без изменений). "
                   "Не утверждай, что worker отправляет сообщения в чат.",
         "source": fixture["source"]},
    ]


def messages_for(prompt):
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]


def strict_json(answer):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError("Non-finite JSON constant")
    return json.loads(answer, object_pairs_hook=pairs, parse_constant=reject_constant)


def validate(example_id, answer):
    errors = []
    if example_id == "simple":
        if answer.strip() != "4":
            errors.append("Expected exactly 4.")
    else:
        try:
            data = strict_json(answer)
        except (ValueError, TypeError):
            return {"passed": False, "errors": ["Expected one strict JSON object without Markdown."]}
        if not isinstance(data, dict):
            return {"passed": False, "errors": ["Expected a JSON object."]}
        if example_id == "calculation":
            expected = calculate_energy(**ENERGY_INPUTS)
            if set(data) != set(expected) or any(type(data.get(k)) is not int or data[k] != v
                                                for k, v in expected.items()):
                errors.append("Expected integer cycles=6, total_cost=3600, remaining=0.")
        elif example_id == "grounded_json":
            expected = {"worker": "worker.py", "database": "schedule.db",
                        "metrics": ["stars", "forks", "open_issues"],
                        "delivery": ["stdout", "systemd journal"],
                        "quote": "The worker outputs summaries to stdout or the systemd journal; it does not push messages to a chat."}
            if set(data) != set(expected):
                errors.append("Expected exactly worker, database, metrics, delivery, quote.")
            for key, value in expected.items():
                actual = data.get(key)
                if isinstance(value, list):
                    valid = isinstance(actual, list) and all(isinstance(x, str) for x in actual)
                    valid = valid and sorted(actual) == sorted(value)
                else:
                    valid = actual == value
                if not valid:
                    errors.append(f"Incorrect {key}.")
        else:
            raise ValueError("Unknown example ID")
    return {"passed": not errors, "errors": errors}
