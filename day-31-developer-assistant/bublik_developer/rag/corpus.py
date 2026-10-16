"""Explicit corpus, byte digests, unchanged line offsets and immutable snapshots."""
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import PurePosixPath
import stat

from ..contracts import canonical
from ..errors import DeveloperError, ErrorCode
from ..git_tools import SECRET
from ..workspace import permitted_metadata, relative_path

NORMALIZATION = "utf8-newlines-to-lf-no-strip-v1"
MAX_FILE_BYTES = 1024 * 1024
MAX_CORPUS_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class SourceSpec:
    path: str
    kind: str = "markdown"

    def __post_init__(self):
        path = relative_path(self.path)
        suffix = path.suffix.casefold()
        if (not isinstance(self.kind, str) or not permitted_metadata(self.path) or self.kind not in {"markdown", "schema"}
                or (self.kind == "markdown" and suffix != ".md")
                or (self.kind == "schema" and suffix not in {".json", ".yaml", ".yml"})):
            raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path")


@dataclass(frozen=True)
class Document:
    source: str
    kind: str
    text: str
    raw_digest: str
    text_digest: str


@dataclass(frozen=True)
class CorpusSnapshot:
    project_id: str
    revision: str
    selection_digest: str
    documents: tuple[Document, ...]

    def manifest(self):
        return [{"source": doc.source, "kind": doc.kind, "raw_digest": doc.raw_digest,
                 "text_digest": doc.text_digest} for doc in self.documents]


def default_sources(workspace):
    root = workspace.root
    paths = {name for name in ("README.md", "README.ru.md") if (root / name).exists()}
    for day in range(16, 31):
        for name in ("README.md", "README.ru.md"):
            paths.update(path.relative_to(root).as_posix() for path in root.glob(f"day-{day:02d}-*/{name}"))
    for name in ("ARCHITECTURE.ru.md", "MEMORY_ARCHITECTURE.ru.md", "RAG_MEMORY.ru.md", "LANGUAGES.ru.md"):
        path = root / "day-30-private-ai-service" / name
        if path.exists():
            paths.add(path.relative_to(root).as_posix())
    # The current architecture docs are distinct from evaluations and reports.
    for name in ("architecture.md", "memory.md", "tooling.md", "api.md",
                 "architecture.ru.md", "memory.ru.md", "tooling.ru.md", "api.ru.md"):
        path = root / "day-31-developer-assistant/project/docs" / name
        if path.exists():
            paths.add(path.relative_to(root).as_posix())
    return [SourceSpec(path) for path in sorted(paths)]


def load_selection(path):
    try:
        raw = path.read_bytes()
        if len(raw) > 32768:
            raise ValueError
        value = json.loads(raw)
        if (not isinstance(value, dict) or set(value) != {"schema_version", "sources"}
                or type(value["schema_version"]) is not int or value["schema_version"] != 1
                or not isinstance(value["sources"], list)):
            raise ValueError
        specs = []
        for row in value["sources"]:
            if not isinstance(row, dict) or set(row) != {"path", "kind"}:
                raise ValueError
            specs.append(SourceSpec(**row))
        return specs
    except (OSError, ValueError, TypeError, RecursionError):
        raise DeveloperError(ErrorCode.INVALID_INPUT) from None


class ProjectCorpus:
    def __init__(self, workspace, specs=None):
        self.workspace = workspace
        self.dynamic_default = specs is None
        self.specs = tuple(sorted(default_sources(workspace) if specs is None else specs, key=lambda spec: spec.path))
        if not 1 <= len(self.specs) <= 64 or len({spec.path for spec in self.specs}) != len(self.specs):
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        self.selection_digest = sha256(canonical({"normalization": NORMALIZATION,
             "sources": [{"path": spec.path, "kind": spec.kind} for spec in self.specs]}).encode()).hexdigest()

    def read(self, spec):
        path = self.workspace.path(spec.path)
        try:
            before = path.lstat()
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "rb") as stream:
                opened = os.fstat(stream.fileno())
                raw = stream.read(MAX_FILE_BYTES + 1)
                after_fd = os.fstat(stream.fileno())
            self.workspace.path(spec.path)
            after = path.lstat()
            identities = {(info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) for info in (before, opened, after_fd, after)}
            if len(identities) != 1 or not stat.S_ISREG(opened.st_mode):
                raise DeveloperError(ErrorCode.INDEX_STALE)
            if len(raw) > MAX_FILE_BYTES:
                raise DeveloperError(ErrorCode.OUTPUT_LIMIT)
            text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        except (OSError, UnicodeError):
            raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path") from None
        if "\x00" in text or not text.strip():
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        if SECRET.search(text):
            raise DeveloperError(ErrorCode.PERMISSION_DENIED, "secret")
        return Document(spec.path, spec.kind, text, sha256(raw).hexdigest(), sha256(text.encode()).hexdigest())

    def collect(self):
        specs = tuple(default_sources(self.workspace)) if self.dynamic_default else self.specs
        if not 1 <= len(specs) <= 64:
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        selection = sha256(canonical({"normalization": NORMALIZATION,
             "sources": [{"path": spec.path, "kind": spec.kind} for spec in specs]}).encode()).hexdigest()
        documents = tuple(self.read(spec) for spec in specs)
        if sum(len(doc.text.encode()) for doc in documents) > MAX_CORPUS_BYTES:
            raise DeveloperError(ErrorCode.OUTPUT_LIMIT)
        manifest = [{"source": doc.source, "kind": doc.kind, "raw_digest": doc.raw_digest,
                     "text_digest": doc.text_digest} for doc in documents]
        revision = sha256(canonical({"selection": selection, "documents": manifest}).encode()).hexdigest()
        return CorpusSnapshot(self.workspace.project_id, revision, selection, documents)
