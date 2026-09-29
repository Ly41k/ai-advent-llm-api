"""Fixed-window and structure-aware chunking with stable provenance."""

import ast
from dataclasses import dataclass
from hashlib import sha256
import re

from corpus import Document


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source: str
    title: str
    section: str
    strategy: str
    text: str
    start_line: int
    end_line: int
    token_count: int


def _pieces(text: str, limit: int, overlap: int):
    if limit <= 0 or overlap < 0 or overlap >= limit:
        raise ValueError("Require limit > 0 and 0 <= overlap < limit")
    spans = list(re.finditer(r"\S+", text))
    start = 0
    while start < len(spans):
        end = min(start + limit, len(spans))
        left, right = spans[start].start(), spans[end - 1].end()
        yield text[left:right], left, len(spans[start:end])
        if end == len(spans):
            break
        start = end - overlap


def _make(document: Document, strategy: str, section: str, part: str,
          base_line: int, limit: int, overlap: int) -> list[Chunk]:
    result = []
    for text, offset, count in _pieces(part, limit, overlap):
        start_line = base_line + part.count("\n", 0, offset)
        end_line = start_line + text.count("\n")
        key = f"{strategy}:{document.source}:{start_line}:{section}:{text}"
        result.append(Chunk(sha256(key.encode()).hexdigest()[:20], document.source,
                            document.title, section, strategy, text,
                            start_line, end_line, count))
    return result


def fixed_chunks(document: Document, limit: int = 500, overlap: int = 75) -> list[Chunk]:
    return _make(document, "fixed", document.title, document.text, 1, limit, overlap)


def _markdown_sections(text: str):
    lines = text.splitlines(keepends=True)
    start, heading = 0, "Preamble"
    for index, line in enumerate(lines):
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if match:
            if index > start:
                yield heading, "".join(lines[start:index]), start + 1
            heading, start = match.group(1), index
    if start < len(lines):
        yield heading, "".join(lines[start:]), start + 1


def _python_sections(text: str):
    lines = text.splitlines(keepends=True)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        yield "file", text, 1
        return
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef,
              ast.AsyncFunctionDef, ast.ClassDef))]
    cursor = 0
    for node in nodes:
        # Include decorators in the section so source fragments remain complete.
        first = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
        if first > cursor:
            yield "module", "".join(lines[cursor:first]), cursor + 1
        yield f"{type(node).__name__} {node.name}", "".join(lines[first:node.end_lineno]), first + 1
        cursor = node.end_lineno
    if cursor < len(lines):
        yield "module", "".join(lines[cursor:]), cursor + 1


def structural_chunks(document: Document, limit: int = 500,
                      overlap: int = 75) -> list[Chunk]:
    sections = (_python_sections(document.text) if document.source.endswith(".py")
                else _markdown_sections(document.text))
    result = []
    for title, text, line in sections:
        if text.strip():
            result.extend(_make(document, "structural", title, text, line,
                                limit, overlap))
    return result


def chunk_documents(documents: list[Document], strategy: str,
                    limit: int = 500, overlap: int = 75) -> list[Chunk]:
    if strategy not in {"fixed", "structural"}:
        raise ValueError(f"Unknown strategy: {strategy}")
    fn = fixed_chunks if strategy == "fixed" else structural_chunks
    return [chunk for document in documents
            for chunk in fn(document, limit=limit, overlap=overlap)]
