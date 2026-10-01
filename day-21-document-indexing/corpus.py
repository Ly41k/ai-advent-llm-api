"""Collect a reproducible, shared corpus from the repository."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
CODE_DAYS = tuple(range(16, 21))


@dataclass(frozen=True)
class Document:
    source: str
    title: str
    text: str
    digest: str


def source_paths(root: Path = ROOT) -> list[Path]:
    paths = set(root.glob("README*.md"))
    # Freeze the shared learning corpus at Days 1–20. Later RAG lesson
    # instructions must not silently become evidence for their own evaluation.
    for day in range(1, 21):
        paths.update(root.glob(f"day-{day:02d}-*/README*.md"))
    for day in CODE_DAYS:
        for directory in root.glob(f"day-{day:02d}-*"):
            paths.update(path for path in directory.glob("*.py")
                         if not path.name.startswith("test_"))
    return sorted(path for path in paths if path.is_file())


def load_documents(root: Path = ROOT) -> list[Document]:
    documents = []
    for path in source_paths(root):
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
        if text:
            documents.append(Document(path.relative_to(root).as_posix(), path.name,
                                      text, sha256(text.encode("utf-8")).hexdigest()))
    return documents


def corpus_stats(documents: list[Document]) -> dict:
    markdown_words = sum(len(re.findall(r"\S+", d.text)) for d in documents
                         if d.source.endswith(".md"))
    code_lines = sum(len(d.text.splitlines()) for d in documents
                     if d.source.endswith(".py"))
    return {"files": len(documents), "markdown_words": markdown_words,
            "code_lines": code_lines, "estimated_text_pages": round(markdown_words / 300, 1),
            "estimated_code_pages": round(code_lines / 50, 1)}


def revision(root: Path = ROOT) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                            capture_output=True, text=True, check=False)
    snapshot = root / "day-21-document-indexing" / "source-revision.txt"
    commit = (result.stdout.strip() if result.returncode == 0 else
              snapshot.read_text(encoding="utf-8").strip() if snapshot.exists()
              else "unavailable")
    # A dirty worktree can have the same Git SHA and different source content.
    manifest = "\n".join(f"{d.source}:{d.digest}" for d in load_documents(root))
    return f"{commit}@{sha256(manifest.encode()).hexdigest()[:16]}"
