"""Локальное хранилище истории экспедиции."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Message:
    """Одно сохранённое сообщение экспедиции."""

    role: str
    content: str
    status: str
    created_at: str


class SQLiteConversationRepository:
    """Сохраняет диалоги и сообщения в локальной базе SQLite."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _create_tables(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('pending', 'completed', 'failed')
                    ),
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id)
                        REFERENCES conversations(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS index_messages_conversation
                ON messages(conversation_id, id);
                """
            )

    def ensure_conversation(self, conversation_id: str, title: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO conversations(id, title, created_at)
                VALUES (?, ?, ?)
                """,
                (conversation_id, title, self._now()),
            )

    def start_user_request(self, conversation_id: str, content: str) -> int:
        """Сохраняет запрос до вызова LLM и возвращает его идентификатор."""

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO messages(
                    conversation_id,
                    role,
                    content,
                    status,
                    created_at
                )
                VALUES (?, 'user', ?, 'pending', ?)
                """,
                (conversation_id, content, self._now()),
            )
            return int(cursor.lastrowid)

    def complete_exchange(
        self,
        user_message_id: int,
        conversation_id: str,
        assistant_content: str,
    ) -> None:
        """Атомарно завершает запрос и сохраняет ответ агента."""

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE messages
                SET status = 'completed'
                WHERE id = ? AND status = 'pending'
                """,
                (user_message_id,),
            )
            connection.execute(
                """
                INSERT INTO messages(
                    conversation_id,
                    role,
                    content,
                    status,
                    created_at
                )
                VALUES (?, 'assistant', ?, 'completed', ?)
                """,
                (conversation_id, assistant_content, self._now()),
            )

    def fail_request(self, user_message_id: int, error_message: str) -> None:
        """Помечает запрос как неуспешный, сохраняя причину ошибки."""

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE messages
                SET status = 'failed', error_message = ?
                WHERE id = ?
                """,
                (error_message, user_message_id),
            )

    def get_context_messages(
        self,
        conversation_id: str,
        limit: int,
    ) -> list[Message]:
        """Возвращает последние успешные сообщения в хронологическом порядке."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content, status, created_at
                FROM (
                    SELECT id, role, content, status, created_at
                    FROM messages
                    WHERE conversation_id = ? AND status = 'completed'
                    ORDER BY id DESC
                    LIMIT ?
                )
                ORDER BY id ASC
                """,
                (conversation_id, limit),
            ).fetchall()

        return [self._to_message(row) for row in rows]

    def get_history(
        self,
        conversation_id: str,
        limit: int = 20,
    ) -> list[Message]:
        """Возвращает последние сообщения, включая неуспешные запросы."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content, status, created_at
                FROM (
                    SELECT id, role, content, status, created_at
                    FROM messages
                    WHERE conversation_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                )
                ORDER BY id ASC
                """,
                (conversation_id, limit),
            ).fetchall()

        return [self._to_message(row) for row in rows]

    @staticmethod
    def _to_message(row: sqlite3.Row) -> Message:
        return Message(
            role=row["role"],
            content=row["content"],
            status=row["status"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
