"""Task memory accepts user evidence, never generated repository facts."""
import copy
import hashlib
import json
import re

KINDS = ("goal", "constraints", "clarifications", "terms")
MAX_STATE_CHARS = 6000


def empty_state():
    return {"goal": None, "constraints": {}, "clarifications": {}, "terms": {}}


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def memory_key(state, kind, key, value, message, origin="planner"):
    """A model-selected key alone never authorizes replacing a saved fact."""
    if kind == "goal":
        return key
    if origin == "planner" and kind in ("constraints", "clarifications"):
        # Reuse identical facts without creating duplicates or changing provenance.
        for existing_key, entry in state[kind].items():
            if entry["value"] == value:
                return existing_key
        previous = state[kind].get(key)
        correction = re.search(r"\b(?:исправ\w*|замен\w*|вместо|теперь|correct\w*|replace\w*|instead|now)\b", message, re.I)
        if previous and correction and (key in message or previous["value"] in message):
            return key  # The user explicitly identified the entry to replace.
        return hashlib.sha256(value.encode()).hexdigest()[:12]
    return key or hashlib.sha256(value.encode()).hexdigest()[:12]


def update(state, kind, key, value, evidence, message, turn, origin="planner"):
    if kind not in KINDS:
        raise ValueError("Unknown task-memory field")
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 600:
        raise ValueError("Memory value must contain 1–600 characters")
    if not isinstance(evidence, str) or not evidence or evidence not in message or value not in evidence:
        raise ValueError("Memory must be an exact substring of current user evidence")
    if not isinstance(key, str) or len(key) > 80:
        raise ValueError("Memory key is too long")
    if origin == "planner" and kind == "goal" and state["goal"]:
        lines = [line for line in message.splitlines() if evidence in line]
        if lines and all("?" in line and not re.match(r"^\s*(?:цель|goal)\s*:", line, re.I) for line in lines):
            raise ValueError("A question about a goal cannot replace it; an explicit goal statement is required")
    if origin == "planner" and kind != "goal":
        lines = [line for line in message.splitlines() if evidence in line]
        if lines and all("?" in line for line in lines):
            raise ValueError("Questions are not confirmed task-memory clarifications, constraints or terms")
        # Exact-substring evidence alone must not turn 'not using SQLite'
        # into 'using SQLite'. Conservative refusal keeps the previous memory.
        offsets = [line.split(value, 1)[0].rstrip() for line in lines if value in line]
        if offsets and all(re.search(r"\b(?:не|not|never)\s*$", prefix, re.I) for prefix in offsets):
            raise ValueError("Memory value dropped the user's negation")
        interrogative = re.match(r"^\s*(?:какой|какая|какие|какое|как|где|когда|почему|зачем|что|кто|сколько|"
                                r"what|which|how|where|when|why|who)(?:\s|$)", value, re.I)
        statement = re.match(r"^\s*как\s+(?:минимум|максимум|правило)\b", value, re.I)
        if "?" in value or (interrogative and not statement):
            raise ValueError("Questions are not confirmed task-memory clarifications, constraints or terms")
    result = copy.deepcopy(state)
    entry = {"value": value, "evidence": evidence, "turn": turn, "origin": origin}
    if kind == "goal":
        if state["goal"] and origin == "planner" and not re.search(r"\b(goal|цель)\b", message, re.I):
            raise ValueError("Changing the goal requires an explicit goal statement")
        result[kind] = entry
    else:
        key = memory_key(state, kind, key, value, message, origin)
        if kind == "terms" and key not in evidence:
            raise ValueError("The term name must occur in current user evidence")
        if key in state[kind] and state[kind][key]["value"] == value:
            return result
        result[kind][key] = entry
    if len(encode(result)) > MAX_STATE_CHARS:
        raise ValueError("Task memory is full; use /forget to remove obsolete entries")
    return result


def forget(state, kind, key):
    if kind not in KINDS:
        raise ValueError("Unknown task-memory field")
    result = copy.deepcopy(state)
    if kind == "goal":
        result[kind] = None
    else:
        if key not in result[kind]:
            raise ValueError("Unknown memory key")
        del result[kind][key]
    return result


def public_state(state):
    """Bounded, complete task memory is sent on every turn independently of history."""
    return {"goal": state["goal"]["value"] if state["goal"] else None,
            **{kind: {key: row["value"] for key, row in state[kind].items()}
               for kind in KINDS if kind != "goal"}}
