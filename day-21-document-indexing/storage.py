"""SQLite storage for corpus versions, two chunking strategies and dense vectors."""

from dataclasses import dataclass
import json
import math
import sqlite3
from pathlib import Path

from chunking import Chunk
from corpus import Document


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    source: str
    section: str
    text: str
    score: float
    start_line: int
    end_line: int

    @property
    def score_01(self) -> float:
        """Display transform of cosine, not a relevance probability."""
        return (max(-1.0, min(1.0, self.score)) + 1.0) / 2.0


class KnowledgeBase:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS documents (
                source TEXT PRIMARY KEY, title TEXT NOT NULL, digest TEXT NOT NULL,
                text TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS indexes (
                strategy TEXT PRIMARY KEY, model TEXT NOT NULL, dimension INTEGER NOT NULL,
                limit_tokens INTEGER NOT NULL, overlap_tokens INTEGER NOT NULL,
                revision TEXT NOT NULL, built_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY, strategy TEXT NOT NULL REFERENCES indexes(strategy),
                source TEXT NOT NULL REFERENCES documents(source),
                title TEXT NOT NULL, section TEXT NOT NULL, text TEXT NOT NULL,
                start_line INTEGER NOT NULL, end_line INTEGER NOT NULL,
                token_count INTEGER NOT NULL, embedding TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS chunks_strategy ON chunks(strategy);
        """)

    def close(self):
        self.db.close()

    def save(self, documents: list[Document], strategy: str, chunks: list[Chunk],
             vectors: list[list[float]], model: str, limit: int, overlap: int,
             revision: str):
        if len(chunks) != len(vectors) or not chunks or not vectors[0]:
            raise ValueError("Chunks and non-empty vectors must match")
        dimension = len(vectors[0])
        if any(len(vector) != dimension for vector in vectors):
            raise ValueError("Inconsistent embedding dimensions")
        with self.db:
            self.db.executemany("INSERT INTO documents VALUES (?, ?, ?, ?) "
                                "ON CONFLICT(source) DO UPDATE SET title=excluded.title, "
                                "digest=excluded.digest, text=excluded.text",
                                [(d.source, d.title, d.digest, d.text) for d in documents])
            self.db.execute("DELETE FROM chunks WHERE strategy=?", (strategy,))
            self.db.execute("INSERT INTO indexes(strategy, model, dimension, limit_tokens, "
                            "overlap_tokens, revision) VALUES (?, ?, ?, ?, ?, ?) "
                            "ON CONFLICT(strategy) DO UPDATE SET model=excluded.model, "
                            "dimension=excluded.dimension, limit_tokens=excluded.limit_tokens, "
                            "overlap_tokens=excluded.overlap_tokens, revision=excluded.revision, "
                            "built_at=CURRENT_TIMESTAMP",
                            (strategy, model, dimension, limit, overlap, revision))
            self.db.executemany("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                [(c.chunk_id, strategy, c.source, c.title, c.section, c.text,
                                  c.start_line, c.end_line, c.token_count, json.dumps(v))
                                 for c, v in zip(chunks, vectors)])

    def info(self, strategy: str):
        row = self.db.execute("SELECT * FROM indexes WHERE strategy=?", (strategy,)).fetchone()
        if row is None:
            raise ValueError(f"Strategy {strategy} has not been indexed")
        return dict(row)

    def stats(self):
        return [dict(row) for row in self.db.execute("""
            SELECT i.strategy, i.model, i.dimension, i.limit_tokens, i.overlap_tokens,
                   i.revision, i.built_at, count(c.chunk_id) AS chunks,
                   round(avg(c.token_count), 1) AS average_tokens
            FROM indexes i LEFT JOIN chunks c ON c.strategy=i.strategy
            GROUP BY i.strategy ORDER BY i.strategy
        """)]

    def validate(self) -> list[dict]:
        """Check stored vectors and metadata, including corpus agreement."""
        reports = []
        for strategy in ("fixed", "structural"):
            info = self.info(strategy)
            rows = self.db.execute("SELECT c.*, d.digest FROM chunks c "
                                   "JOIN documents d ON c.source=d.source "
                                   "WHERE c.strategy=?", (strategy,)).fetchall()
            if not rows:
                raise RuntimeError(f"Empty index: {strategy}")
            for row in rows:
                vector = json.loads(row["embedding"])
                if (len(vector) != info["dimension"] or
                    any(not math.isfinite(x) for x in vector) or
                    abs(sum(x * x for x in vector) - 1.0) > 1e-3):
                    raise RuntimeError(f"Invalid embedding: {row['chunk_id']}")
                if not all(row[key] for key in ("chunk_id", "source", "title", "section", "text")):
                    raise RuntimeError(f"Missing chunk metadata: {row['chunk_id']}")
            reports.append({"strategy": strategy, "chunks": len(rows),
                            "dimension": info["dimension"], "model": info["model"],
                            "revision": info["revision"], "valid": True})
        if len({(r["model"], r["revision"]) for r in reports}) != 1:
            raise RuntimeError("Strategies use different models or corpus revisions")
        return reports

    def search(self, strategy: str, query_vector: list[float], top_k: int = 5) -> list[Hit]:
        info = self.info(strategy)
        if len(query_vector) != info["dimension"] or top_k <= 0:
            raise ValueError("Query vector dimension or top_k is invalid")
        ranked = []
        for row in self.db.execute("SELECT * FROM chunks WHERE strategy=?", (strategy,)):
            vector = json.loads(row["embedding"])
            score = sum(a * b for a, b in zip(query_vector, vector))
            ranked.append(Hit(row["chunk_id"], row["source"], row["section"],
                              row["text"], score, row["start_line"], row["end_line"]))
        return sorted(ranked, key=lambda hit: (-hit.score, hit.chunk_id))[:top_k]
