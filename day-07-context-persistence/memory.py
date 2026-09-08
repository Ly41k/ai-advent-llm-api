"""Постоянное SQLite-хранилище контекста диалога."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class Conversation:
    """Диалог, который можно выбрать и продолжить после перезапуска."""

    id: str
    title: str
    message_count: int
    updated_at: str


@dataclass(frozen=True)
class Message:
    """Сообщение, восстановленное из истории диалога."""

    role: str
    content: str
    status: str
    created_at: str


class SQLiteContextRepository:
    """Сохраняет сообщения и восстанавливает контекст между запусками."""

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
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
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

            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(conversations)"
                ).fetchall()
            }
            if "updated_at" not in columns:
                connection.execute(
                    "ALTER TABLE conversations ADD COLUMN updated_at TEXT"
                )
                connection.execute(
                    """
                    UPDATE conversations
                    SET updated_at = created_at
                    WHERE updated_at IS NULL
                    """
                )

    def create_conversation(self, title: str) -> Conversation:
        """Создаёт новую независимую тему для общения с агентом."""

        prepared_title = title.strip()
        if not prepared_title:
            raise ValueError("Название диалога не может быть пустым")

        conversation_id = str(uuid4())
        created_at = self._now()

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations(id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, prepared_title, created_at, created_at),
            )

        return Conversation(
            id=conversation_id,
            title=prepared_title,
            message_count=0,
            updated_at=created_at,
        )

    def get_conversations(self) -> list[Conversation]:
        """Возвращает прошлые диалоги, начиная с самого свежего."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    conversations.id,
                    conversations.title,
                    conversations.updated_at,
                    COUNT(
                        CASE WHEN messages.status = 'completed' THEN 1 END
                    ) AS message_count
                FROM conversations
                LEFT JOIN messages
                    ON messages.conversation_id = conversations.id
                GROUP BY conversations.id
                ORDER BY conversations.updated_at DESC
                """
            ).fetchall()

        return [
            Conversation(
                id=row["id"],
                title=row["title"],
                message_count=int(row["message_count"]),
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def conversation_exists(self, conversation_id: str) -> bool:
        """Проверяет, что выбранный диалог присутствует в базе."""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
        return row is not None

    def start_user_request(self, conversation_id: str, content: str) -> int:
        """Сохраняет запрос до обращения к LLM."""

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO messages(
                    conversation_id, role, content, status, created_at
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
            cursor = connection.execute(
                """
                UPDATE messages
                SET status = 'completed'
                WHERE id = ?
                  AND conversation_id = ?
                  AND status = 'pending'
                """,
                (user_message_id, conversation_id),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Не найден ожидающий пользовательский запрос")

            connection.execute(
                """
                INSERT INTO messages(
                    conversation_id, role, content, status, created_at
                )
                VALUES (?, 'assistant', ?, 'completed', ?)
                """,
                (conversation_id, assistant_content, self._now()),
            )
            connection.execute(
                """
                UPDATE conversations
                SET updated_at = ?
                WHERE id = ?
                """,
                (self._now(), conversation_id),
            )

    def fail_request(self, user_message_id: int, error_message: str) -> None:
        """Сохраняет неуспешный запрос для диагностики."""

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE messages
                SET status = 'failed', error_message = ?
                WHERE id = ? AND status = 'pending'
                """,
                (error_message, user_message_id),
            )

    def get_context_messages(
        self,
        conversation_id: str,
        limit: int,
    ) -> list[Message]:
        """Загружает последние успешные сообщения в исходном порядке."""

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
        """Возвращает журнал, включая неуспешные запросы."""

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

    def get_completed_message_count(self, conversation_id: str) -> int:
        """Возвращает число сообщений, доступных после перезапуска."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS message_count
                FROM messages
                WHERE conversation_id = ? AND status = 'completed'
                """,
                (conversation_id,),
            ).fetchone()

        return int(row["message_count"])

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
