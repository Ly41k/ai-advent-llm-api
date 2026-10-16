"""Bounded FTS5 over base-checkout Markdown; adapted from Day 31 corpus/chunking/retrieval."""
import re
import sqlite3
from pathlib import Path

from common import SECRET, ReviewError, digest, fail, local_file

WORDS = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_]{2,40}")
STOP = {"readme", "modified", "added", "removed", "return", "self", "none", "true", "false", "import", "from",
        "def", "class", "value", "values", "args", "kwargs", "val", "var", "fun", "public", "private"}


def source_paths(root, files):
    """Explicit root/day READMEs and the changed file's nearest README from base."""
    candidates = {"README.md", "README.ru.md", "day-32-pr-review/README.md", "day-32-pr-review/README.ru.md"}
    for file in files:
        if "/" in file["path"]:
            candidates.add(file["path"].rsplit("/", 1)[0] + "/README.md")
        folder = file["path"].split("/")[0]
        if re.fullmatch(r"day-\d\d-[a-z0-9-]+", folder):
            candidates.update(f"{folder}/{name}" for name in ("README.md", "README.ru.md"))
    if len(candidates) > 32:
        fail("corpus_file_limit")
    return sorted(candidates)


def chunks(text):
    """Keep complete source lines and original offsets; headings inside fences are ignored."""
    lines = text.splitlines(keepends=True)
    start, used, title, fence = 0, 0, "Preamble", None
    for index, line in enumerate(lines):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            fence = marker[1][0] if fence is None else (None if marker[1][0] == fence else fence)
        heading = re.match(r"^#{1,6}\s+(.+)", line) if not fence and not marker else None
        if index > start and (heading or used + len(line.encode()) > 600):
            yield title, start + 1, index, "".join(lines[start:index]).rstrip("\n")
            start, used = index, 0
        if heading:
            title = heading[1].strip()
        used += len(line.encode())
    if start < len(lines):
        yield title, start + 1, len(lines), "".join(lines[start:]).rstrip("\n")


def retrieve(root, files, base_sha):
    terms = []
    for file in files:
        query = file["path"].rsplit("/", 1)[-1] + " " + " ".join(line["text"] for h in file["hunks"] for line in h["lines"] if line["changed"])
        for word in WORDS.findall(query):
            word = word.casefold()
            if word not in STOP and word not in terms:
                terms.append(word)
    terms = terms[:24]
    omitted, documents, total, oversized_chunks = [], [], 0, 0
    with sqlite3.connect(":memory:") as db:
        try:
            db.execute("CREATE VIRTUAL TABLE search USING fts5(text, tokenize='unicode61')")
        except sqlite3.OperationalError:
            fail("fts5_unavailable")
        for name in source_paths(root, files):
            try:
                path = local_file(root, name)
                if not path.exists():
                    continue
                with path.open("rb") as stream:
                    raw = stream.read(131073)
                if len(raw) > 131072 or total + len(raw) > 1048576:
                    fail("corpus_size_limit")
                text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
                if SECRET.search(text) or "\x00" in text:
                    fail("unsafe_document")
                total += len(raw)
                for section, start, end, quote in chunks(text):
                    # Long single lines are withheld rather than cut into invented line spans.
                    if not quote.strip():
                        continue
                    if len(quote.encode()) > 600:
                        oversized_chunks += 1
                        continue
                    doc = {"path": name, "base_sha": base_sha, "section": section,
                           "start_line": start, "end_line": end, "text": quote, "digest": digest(quote)}
                    documents.append(doc)
                    db.execute("INSERT INTO search(rowid,text) VALUES (?,?)", (len(documents), quote))
            except (ReviewError, UnicodeError, OSError):
                omitted.append({"path": name, "reason": "document_unavailable_or_unsafe"})
        query = " OR ".join('"' + word.replace('"', '""') + '"' for word in terms)
        rows = db.execute("SELECT rowid FROM search WHERE search MATCH ? ORDER BY bm25(search),rowid LIMIT 3", (query,)).fetchall() if terms else []
        hits = [{"id": f"D{index}", **documents[row[0] - 1]} for index, row in enumerate(rows, 1)]
    return hits, {"method": "sqlite_fts5_bm25", "terms": terms, "indexed_chunks": len(documents),
                  "oversized_document_chunks_omitted": oversized_chunks,
                  "documents_omitted": omitted, "matched_chunks": len(hits), "selected_chunks": len(hits),
                  "status": "retrieved" if hits else "no_evidence"}
