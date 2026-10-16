"""Day 21 structural/window chunking adapted to preserve absolute character spans.

No legacy sys.path imports; no trimming of source preambles. Code fences do not
introduce Markdown sections. Word counts are estimates, never actual BPE counts.
"""
from dataclasses import dataclass
from hashlib import sha256
import re

VERSION = "project-structural-spans-v1"


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source: str
    section: str
    text: str
    start: int
    end: int
    start_line: int
    end_line: int
    word_count: int


def sections(document):
    if document.kind != "markdown":
        yield document.source, 0, len(document.text)
        return
    cursor, start, title, fence = 0, 0, "Preamble", None
    for line in document.text.splitlines(keepends=True):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token[0]
            elif token[0] == fence:
                fence = None
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line) if fence is None and not marker else None
        if heading:
            if cursor > start:
                yield title, start, cursor
            title, start = heading.group(1), cursor
        cursor += len(line)
    if start < len(document.text):
        yield title, start, len(document.text)


def chunk_document(document, limit=250, overlap=40):
    if type(limit) is not int or type(overlap) is not int or not 1 <= limit <= 1000 or not 0 <= overlap < limit:
        raise ValueError("invalid_chunk_settings")
    chunks = []
    for title, base, stop in sections(document):
        words = list(re.finditer(r"\S+", document.text[base:stop]))
        offset = 0
        while offset < len(words):
            finish = min(offset + limit, len(words))
            left, right = base + words[offset].start(), base + words[finish - 1].end()
            text = document.text[left:right]
            key = f"{VERSION}:{document.source}:{document.raw_digest}:{left}:{right}"
            chunks.append(Chunk(sha256(key.encode()).hexdigest(), document.source, title, text, left, right,
                               document.text.count("\n", 0, left) + 1,
                               document.text.count("\n", 0, right) + 1, finish - offset))
            if finish == len(words):
                break
            offset = finish - overlap
    return chunks
