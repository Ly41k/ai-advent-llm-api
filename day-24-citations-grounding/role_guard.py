"""Narrow deterministic actor contradiction guard, supplementary to semantic audit.

It detects an explicitly identical action assigned to different named roles in
prose. It is not a general entailment checker: paraphrases, implicit actors and
code still require the semantic audit and manual evaluation.
"""

import re

from evidence import EvidenceError


def split_statements(value):
    # Mask inline code for boundary detection; keep the original statement text.
    masked = re.sub(r"`[^`]*`", lambda m: "_" * len(m.group()), value)
    boundaries = [m.end() for m in re.finditer(r"[.!?](?=\s+[A-ZА-ЯЁ]|\s*$)", masked)]
    result, start = [], 0
    for end in boundaries:
        if value[start:end].strip():
            result.append(value[start:end].strip())
        start = end
    if value[start:].strip():
        result.append(value[start:].strip())
    return result


ROLE = re.compile(
    r"^(?:(?:the|an?|independent|separate|отдельный|независимый)\s+)*"
    r"(?P<role>worker|agent|client|server|scheduler|воркер|агент|клиент|сервер|планировщик)\b"
    r"\s+(?P<predicate>.+)$", re.I)
ALIASES = {"воркер": "worker", "агент": "agent", "клиент": "client",
           "сервер": "server", "планировщик": "scheduler"}


def explicit_role_clauses(value):
    # Code cannot be interpreted as prose by this guard.
    value = re.sub(r"```.*?```|~~~.*?~~~", "", value, flags=re.S)
    clauses = []
    for sentence in split_statements(value):
        match = ROLE.match(sentence.strip().lstrip("- "))
        if not match:
            continue
        role = match["role"].casefold()
        predicate = match["predicate"].casefold().strip().rstrip(".!?")
        predicate = re.sub(r"^(?:can|may|must|could|should|will|может|должен|умеет)\s+", "", predicate)
        predicate = " ".join(predicate.split())
        if len(predicate.split()) >= 3:
            clauses.append((ALIASES.get(role, role), predicate))
    return clauses


def validate_explicit_roles(claims):
    for claim in claims:
        evidence = [pair for ref in claim["citations"]
                    for pair in explicit_role_clauses(ref["quote"])]
        for actor, predicate in explicit_role_clauses(claim["text"]):
            matching = {role for role, action in evidence if predicate == action}
            if matching and actor not in matching:
                raise EvidenceError(
                    f"Claim {claim['id']} assigns an explicitly quoted action to {actor}, "
                    f"but its quotations assign the same action to {sorted(matching)}. "
                    "Keep the actual actor or remove the unsupported assertion.")
