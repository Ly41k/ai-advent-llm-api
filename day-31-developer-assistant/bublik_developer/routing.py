"""Bounded RU/EN routing; no model chooses executable commands or flags."""
from dataclasses import dataclass
import re

from .errors import DeveloperError, ErrorCode
from .rag.retrieval import query_terms

PATTERNS = {
    "branch": r"\bbranch\b|\bветк[а-я]*\b|git_current_branch",
    "status": r"\bstatus\b|git_status|измен[её]н[а-я]*\s+файл|файл[а-я]*\s+измен[её]н|changed\s+files|files\s+(?:have\s+)?changed|что\s+измен",
    "diff": r"\bdiff\b|git_diff|разниц[а-я]*|покажи\s+изменения",
    "files": r"project_list_files|список\s+файлов|list\s+(?:project\s+)?files|^files[?]?$",
}
DOC = r"памят|memory|документ|document|архитект|architect|\bapi\b|как\s+устро|how.*work|объясн|explain|где.*опис|where.*describ"
RELATION = r"где.*опис|where.*(?:document|describ)|документ.*измен|document.*chang|функциональност|functionality"
WRITE = r"^(?:git\s+(?:push|commit|reset|clean)|(?:please\s+)?(?:push|commit|delete|remove)\b|(?:сделай\s+коммит|удали\b|запушь\b))"


@dataclass(frozen=True)
class Route:
    kind: str
    question: str
    documentation_question: str | None = None
    git_operation: str | None = None
    git_scope: str = "unstaged"


def route(question):
    query_terms(question)
    question = question.strip().removeprefix("/help ").strip()
    if re.search(WRITE, question, re.I):
        raise DeveloperError(ErrorCode.PERMISSION_DENIED)
    if re.search(r"why|почему|может\s+ли|does|can|how", question, re.I) and re.search(r"git_(?:diff|status|current_branch)|project_list_files", question, re.I):
        return Route("documentation", question, question)
    operations = [op for op, pattern in PATTERNS.items() if re.search(pattern, question, re.I)]
    if len(operations) > 1:
        # No silent choice between branch/status/diff. User can split the query.
        return Route("ambiguous", question)
    if not operations:
        return Route("documentation", question, question)
    op = operations[0]
    scope = "staged" if op == "diff" and re.search(r"\bstaged\b|подготовленн|в\s+индексе", question, re.I) else "unstaged"
    if op == "status" and re.search(RELATION, question, re.I):
        return Route("chain", question, question, op)
    if re.search(DOC, question, re.I):
        # Keep original connectors/punctuation between retained adjacent parts.
        # Splitting an internal "and" must not create a new question boundary.
        parts = re.split(r"(\s+(?:и|and|also)\s+|[?]\s*)", question, flags=re.I)
        retained = [i for i in range(0, len(parts), 2) if parts[i].strip()
                    and not any(re.search(p, parts[i], re.I) for p in PATTERNS.values())]
        groups = []
        previous = None
        for i in retained:
            if previous == i - 2:
                groups[-1] += parts[i - 1] + parts[i]
            else:
                groups.append(parts[i])
            if i + 2 not in retained and i + 1 < len(parts) and parts[i + 1].startswith("?"):
                groups[-1] += "?"
            previous = i
        objective = "\n".join(group.strip() for group in groups) if groups else question
        return Route("fan_out", question, objective, op, scope)
    return Route("git", question, None, op, scope)


@dataclass
class ProjectSession:
    """One prior project question; no private chat history or personal memory."""
    project_id: str
    revision: str | None = None
    previous_question: str | None = None

    def resolve(self, question, project_id, revision):
        if project_id != self.project_id:
            raise DeveloperError(ErrorCode.PERMISSION_DENIED)
        if revision != self.revision:
            self.previous_question = None
            self.revision = revision
        if re.match(r"^(?:а\s+(?:как|что|для|по)|а\s+владел|what\s+about|and\s+(?:how|what))\b", question, re.I) and self.previous_question:
            question = self.previous_question + "\nFollow-up: " + question
        query_terms(question)
        return question

    def remember(self, question, revision):
        query_terms(question)
        self.revision, self.previous_question = revision, question
