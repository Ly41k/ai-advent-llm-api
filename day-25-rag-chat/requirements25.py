"""Derive coverage gates without confusing operation identifiers with intent."""
import re

from support25 import strict_requirements


def coverage_requirements25(question):
    """Only the lexical intent scan is masked; all audit DATA keeps the question.

    Quoted code and an uppercase identifier explicitly used as a command/tool/
    operation (or after a premature-choice qualifier) are names, not verbs
    requesting verification. Real check/test/confirm words outside those names
    retain Day 24's independent action and observation criteria.
    """
    scan = re.sub(r"(```|~~~)[\s\S]*?\1", " ", question)
    scan = re.sub(r"(`+)([^`\n]*)\1", " ", scan)
    context = (r"(?:\b(?:operation|command|step|tool|premature|early)\b|"
               r"\b(?:операци\w*|команд\w*|шаг\w*|инструмент\w*|преждевремен\w*|выбор\w*)\b)")
    # Do not ignore a bare/emphasized VERIFY verb in a genuine how-to-check
    # question. Only explicit identifier contexts below qualify.
    prefix = re.compile(r"((?i:" + context + r")\s+(?:[a-zа-яё]+\s+){0,2})([A-Z][A-Z0-9_]{1,})\b")
    scan = prefix.sub(lambda match: match.group(1) + " ", scan)
    suffix = re.compile(r"\b[A-Z][A-Z0-9_]{1,}(\s+(?i:operation|command|step|tool)\b)")
    scan = suffix.sub(lambda match: match.group(1), scan)
    return strict_requirements(scan)
