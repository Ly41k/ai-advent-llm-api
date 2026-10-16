"""Versioned SQLite FTS5 + float32 dense index; never rewrites Week 6 data."""
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
import sqlite3
import struct
from time import perf_counter
from uuid import uuid4

from ..contracts import canonical
from ..errors import DeveloperError, ErrorCode
from .chunking import VERSION, chunk_document
from .state import private

MAX_INDEX_BYTES = 64 * 1024 * 1024
SCHEMA = """
CREATE TABLE metadata(value TEXT NOT NULL);
CREATE TABLE documents(source TEXT PRIMARY KEY,kind TEXT NOT NULL,text TEXT NOT NULL,raw_digest TEXT NOT NULL,text_digest TEXT NOT NULL);
CREATE TABLE chunks(chunk_id TEXT PRIMARY KEY,source TEXT NOT NULL REFERENCES documents(source),section TEXT NOT NULL,text TEXT NOT NULL,
 start INTEGER NOT NULL,end INTEGER NOT NULL,start_line INTEGER NOT NULL,end_line INTEGER NOT NULL,word_count INTEGER NOT NULL,vector BLOB);
CREATE VIRTUAL TABLE search USING fts5(chunk_id UNINDEXED,source,section,text,tokenize="unicode61 remove_diacritics 2 tokenchars '_'");
"""


def vector_bytes(vector, dimension):
    if (not isinstance(vector, list) or len(vector) != dimension
            or any(type(value) not in (int, float) or not math.isfinite(value) for value in vector)
            or abs(sum(value * value for value in vector) - 1) > 1e-3):
        raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
    return struct.pack("<" + str(dimension) + "f", *vector)


def read_vector(value, dimension):
    if not isinstance(value, bytes) or len(value) != dimension * 4:
        raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE)
    vector = struct.unpack("<" + str(dimension) + "f", value)
    if any(not math.isfinite(v) for v in vector) or abs(sum(v * v for v in vector) - 1) > 1e-3:
        raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE)
    return vector


def build_index(corpus, state, *, provider=None, limit=250, overlap=40):
    started = perf_counter()
    with state.build_lock():
        snapshot = corpus.collect()
        chunks = [chunk for doc in snapshot.documents for chunk in chunk_document(doc, limit, overlap)]
        if not chunks or len(chunks) > 10000 or any(len(chunk.text.encode()) > 16000 for chunk in chunks):
            raise DeveloperError(ErrorCode.CONTEXT_BUDGET)
        profile = provider.identity() if provider is not None else None
        vectors, embedding_calls = [], 0
        if provider is not None:
            for offset in range(0, len(chunks), 8):
                values = provider.embed([chunk.text for chunk in chunks[offset:offset + 8]], final=offset + 8 >= len(chunks))
                if len(values) != len(chunks[offset:offset + 8]):
                    raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
                vectors.extend(vector_bytes(value, profile["dimension"]) for value in values)
                embedding_calls += 1
            if provider.identity() != profile:
                raise DeveloperError(ErrorCode.EMBEDDING_UNAVAILABLE)
        version = uuid4().hex
        target = state.path / ("index-" + version + ".sqlite3")
        metadata = {"schema_version": 1, "index_version": version, "project_id": snapshot.project_id,
                    "corpus_revision": snapshot.revision, "selection_digest": snapshot.selection_digest,
                    "chunk_version": VERSION, "limit_words": limit, "overlap_words": overlap,
                    "embedding": profile, "built_at": datetime.now(timezone.utc).isoformat(),
                    "documents": len(snapshot.documents), "chunks": len(chunks)}
        published = False
        try:
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            with closing(sqlite3.connect(target)) as db:
                db.execute("PRAGMA foreign_keys=ON")
                db.executescript(SCHEMA)
                with db:
                    db.execute("INSERT INTO metadata VALUES (?)", (canonical(metadata),))
                    db.executemany("INSERT INTO documents VALUES (?,?,?,?,?)", [(doc.source, doc.kind, doc.text, doc.raw_digest, doc.text_digest) for doc in snapshot.documents])
                    db.executemany("INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?)", [
                        (chunk.chunk_id, chunk.source, chunk.section, chunk.text, chunk.start, chunk.end,
                         chunk.start_line, chunk.end_line, chunk.word_count, vectors[i] if profile else None)
                        for i, chunk in enumerate(chunks)])
                    db.executemany("INSERT INTO search VALUES (?,?,?,?)", [(chunk.chunk_id, chunk.source, chunk.section, chunk.text) for chunk in chunks])
                if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE)
            if target.stat().st_size > MAX_INDEX_BYTES:
                raise DeveloperError(ErrorCode.OUTPUT_LIMIT)
            if corpus.collect().revision != snapshot.revision:
                raise DeveloperError(ErrorCode.INDEX_STALE)
            descriptor = os.open(target, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            checksum = sha256(target.read_bytes()).hexdigest()
            # Validate the newly built version before replacing the CURRENT pointer.
            with ProjectIndex(target, checksum, corpus) as index:
                index.verify()
            # If pointer publication fails after replace/fsync, retaining a valid
            # DB is safer than deleting the version the pointer might reference.
            published = True
            state.publish({"file": target.name, "sha256": checksum, "index_version": version})
            return {"status": "built", "index": metadata, "state_directory": str(state.path),
                    "seconds": perf_counter() - started, "embedding_calls": embedding_calls,
                    "answer_model_calls": 0, "embedding_metrics": getattr(provider, "events", []) if provider else []}
        except sqlite3.Error:
            raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE) from None
        finally:
            if not published:
                target.unlink(missing_ok=True)
                for suffix in ("-journal", "-wal", "-shm"):
                    target.with_name(target.name + suffix).unlink(missing_ok=True)


class ProjectIndex:
    def __init__(self, path, expected_digest, corpus):
        self.path, self.corpus = path, corpus
        private(path)
        if path.stat().st_size > MAX_INDEX_BYTES or sha256(path.read_bytes()).hexdigest() != expected_digest:
            raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE)
        try:
            self.db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA query_only=ON")
            rows = self.db.execute("SELECT value FROM metadata").fetchall()
            if len(rows) != 1:
                raise ValueError
            self.metadata = json.loads(rows[0][0])
            required = {"schema_version", "index_version", "project_id", "corpus_revision", "selection_digest",
                        "chunk_version", "limit_words", "overlap_words", "embedding", "built_at", "documents", "chunks"}
            if not isinstance(self.metadata, dict) or set(self.metadata) != required:
                raise ValueError
            for key, lower, upper in (("limit_words", 1, 1000), ("overlap_words", 0, 999), ("documents", 1, 64), ("chunks", 1, 10000)):
                if type(self.metadata[key]) is not int or not lower <= self.metadata[key] <= upper:
                    raise ValueError
            if self.metadata["overlap_words"] >= self.metadata["limit_words"]:
                raise ValueError
            profile = self.metadata["embedding"]
            if profile is not None and (not isinstance(profile, dict) or set(profile) != {"name", "digest", "dimension"}
                    or profile["name"] != "bge-m3" or profile["dimension"] != 1024
                    or not isinstance(profile["digest"], str) or len(profile["digest"]) != 64):
                raise ValueError
            self.fresh()
        except (sqlite3.Error, ValueError, TypeError, KeyError):
            if hasattr(self, "db"):
                self.db.close()
            raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE) from None
        except BaseException:
            if hasattr(self, "db"):
                self.db.close()
            raise

    @classmethod
    def current(cls, state, corpus):
        path, pointer = state.current()
        result = cls(path, pointer["sha256"], corpus)
        if result.metadata["index_version"] != pointer["index_version"]:
            result.db.close()
            raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE)
        return result

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.db.close()

    def fresh(self):
        snapshot = self.corpus.collect()
        if (self.metadata.get("schema_version") != 1 or self.metadata.get("chunk_version") != VERSION
                or self.metadata.get("project_id") != snapshot.project_id
                or self.metadata.get("selection_digest") != snapshot.selection_digest
                or self.metadata.get("corpus_revision") != snapshot.revision):
            raise DeveloperError(ErrorCode.INDEX_STALE)
        return snapshot

    def verify(self):
        snapshot = self.fresh()
        docs = {doc.source: doc for doc in snapshot.documents}
        rows = self.db.execute("SELECT * FROM documents").fetchall()
        if len(rows) != len(docs) or self.metadata["documents"] != len(docs):
            raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE)
        for row in rows:
            doc = docs.get(row["source"])
            if doc is None or any(row[key] != getattr(doc, key) for key in ("kind", "text", "raw_digest", "text_digest")):
                raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE)
        expected = {chunk.chunk_id: chunk for doc in snapshot.documents for chunk in
                    chunk_document(doc, self.metadata["limit_words"], self.metadata["overlap_words"])}
        rows = self.db.execute("SELECT * FROM chunks").fetchall()
        search = {row["chunk_id"]: row for row in self.db.execute("SELECT * FROM search")}
        if len(rows) != len(expected) or len(search) != len(rows) or self.metadata["chunks"] != len(rows):
            raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE)
        profile = self.metadata["embedding"]
        for row in rows:
            chunk = expected.get(row["chunk_id"])
            if chunk is None or any(row[key] != getattr(chunk, key) for key in ("source", "section", "text", "start", "end", "start_line", "end_line", "word_count")):
                raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE)
            entry = search.get(row["chunk_id"])
            if entry is None or any(entry[key] != row[key] for key in ("source", "section", "text")):
                raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE)
            if profile:
                read_vector(row["vector"], profile["dimension"])
            elif row["vector"] is not None:
                raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE)
        return {"status": "verified", "index": self.metadata, "checks": ["current_corpus", "source_digests", "exact_spans", "fts_rows", "vectors"], "read_only": True}

    def evidence(self, chunk_id):
        row = self.db.execute("SELECT c.*,d.raw_digest,d.text_digest FROM chunks c JOIN documents d ON d.source=c.source WHERE chunk_id=?", (chunk_id,)).fetchone()
        if row is None:
            raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE)
        return {"chunk_id": row["chunk_id"], "source": row["source"], "section": row["section"], "quote": row["text"],
                "start_line": row["start_line"], "end_line": row["end_line"], "start": row["start"], "end": row["end"],
                "raw_digest": row["raw_digest"], "text_digest": row["text_digest"], "project_id": self.metadata["project_id"],
                "corpus_revision": self.metadata["corpus_revision"], "index_version": self.metadata["index_version"]}
