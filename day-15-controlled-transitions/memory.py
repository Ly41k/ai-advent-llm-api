"""SQLite-хранилище с физически разделёнными слоями памяти."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from models import (
    Conversation,
    LongTermKind,
    MemoryEntry,
    Message,
    TaskContext,
    TaskState,
    WorkingNote,
)


class SQLiteMemoryRepository:
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
                    profile_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                -- SHORT-TERM: журнал относится только к одному диалогу.
                CREATE TABLE IF NOT EXISTS short_term_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('pending', 'completed', 'failed')
                    ),
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS index_short_term_conversation
                ON short_term_messages(conversation_id, id);

                -- WORKING: структурированное состояние текущей задачи.
                CREATE TABLE IF NOT EXISTS working_memory (
                    conversation_id TEXT PRIMARY KEY,
                    task TEXT NOT NULL,
                    state TEXT NOT NULL,
                    step INTEGER NOT NULL,
                    plan_json TEXT NOT NULL,
                    done_json TEXT NOT NULL,
                    current TEXT,
                    validation_passed INTEGER NOT NULL DEFAULT 0,
                    validation_details TEXT,
                    paused INTEGER NOT NULL DEFAULT 0,
                    plan_approved INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS working_notes (
                    conversation_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (conversation_id, key),
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                        ON DELETE CASCADE
                );

                -- LONG-TERM: решения и знания профиля доступны его диалогам.
                CREATE TABLE IF NOT EXISTS long_term_memory (
                    profile_id TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK (kind IN ('decision', 'knowledge')),
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (profile_id, kind, key)
                );
                """
            )
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(working_memory)"
                ).fetchall()
            }
            if "plan_approved" not in columns:
                connection.execute(
                    "ALTER TABLE working_memory ADD COLUMN "
                    "plan_approved INTEGER NOT NULL DEFAULT 0"
                )

    def create_conversation(self, title: str, profile_id: str) -> Conversation:
        prepared = title.strip()
        prepared_profile_id = profile_id.strip()
        if not prepared or not prepared_profile_id:
            raise ValueError("Название диалога и ID профиля не могут быть пустыми")
        conversation_id = str(uuid4())
        now = self._now()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO conversations VALUES (?, ?, ?, ?, ?)",
                (conversation_id, prepared, prepared_profile_id, now, now),
            )
        return Conversation(conversation_id, prepared, prepared_profile_id, 0, now)

    def get_conversations(self) -> list[Conversation]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.id, c.title, c.profile_id, c.updated_at,
                       COUNT(CASE WHEN m.status = 'completed' THEN 1 END) message_count
                FROM conversations c
                LEFT JOIN short_term_messages m ON m.conversation_id = c.id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                """
            ).fetchall()
        return [
            Conversation(
                row["id"], row["title"], row["profile_id"],
                row["message_count"], row["updated_at"]
            )
            for row in rows
        ]

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT c.id, c.title, c.profile_id, c.updated_at,
                       COUNT(CASE WHEN m.status = 'completed' THEN 1 END) message_count
                FROM conversations c
                LEFT JOIN short_term_messages m ON m.conversation_id = c.id
                WHERE c.id = ?
                GROUP BY c.id
                """,
                (conversation_id,),
            ).fetchone()
        if row is None:
            return None
        return Conversation(
            row["id"], row["title"], row["profile_id"],
            row["message_count"], row["updated_at"]
        )

    def set_conversation_profile(self, conversation_id: str, profile_id: str) -> None:
        prepared = profile_id.strip()
        if not prepared:
            raise ValueError("ID профиля не может быть пустым")
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE conversations SET profile_id = ?, updated_at = ? WHERE id = ?",
                (prepared, self._now(), conversation_id),
            )
        if cursor.rowcount != 1:
            raise ValueError("Диалог не найден")

    # SHORT-TERM MEMORY
    def start_user_request(self, conversation_id: str, content: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO short_term_messages(
                    conversation_id, role, content, status, created_at
                ) VALUES (?, 'user', ?, 'pending', ?)""",
                (conversation_id, content, self._now()),
            )
        return int(cursor.lastrowid)

    def complete_exchange(
        self,
        user_message_id: int,
        conversation_id: str,
        assistant_content: str,
    ) -> None:
        now = self._now()
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE short_term_messages SET status = 'completed'
                   WHERE id = ? AND status = 'pending'""",
                (user_message_id,),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Не найден ожидающий пользовательский запрос")
            connection.execute(
                """INSERT INTO short_term_messages(
                    conversation_id, role, content, status, created_at
                ) VALUES (?, 'assistant', ?, 'completed', ?)""",
                (conversation_id, assistant_content, now),
            )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )

    def fail_request(self, user_message_id: int, error_message: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE short_term_messages
                   SET status = 'failed', error_message = ?
                   WHERE id = ? AND status = 'pending'""",
                (error_message, user_message_id),
            )

    def get_short_term(self, conversation_id: str, limit: int = 6) -> list[Message]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, role, content, status, created_at
                FROM short_term_messages
                WHERE conversation_id = ? AND status = 'completed'
                ORDER BY id DESC LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()
        return [self._to_message(row) for row in reversed(rows)]

    def get_full_history(self, conversation_id: str) -> list[Message]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, role, content, status, created_at
                FROM short_term_messages
                WHERE conversation_id = ? AND status = 'completed'
                ORDER BY id
                """,
                (conversation_id,),
            ).fetchall()
        return [self._to_message(row) for row in rows]

    # WORKING MEMORY
    def save_task_context(self, conversation_id: str, context: TaskContext) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO working_memory(
                    conversation_id, task, state, step, plan_json, done_json,
                    current, validation_passed, validation_details, paused,
                    plan_approved, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    task = excluded.task,
                    state = excluded.state,
                    step = excluded.step,
                    plan_json = excluded.plan_json,
                    done_json = excluded.done_json,
                    current = excluded.current,
                    validation_passed = excluded.validation_passed,
                    validation_details = excluded.validation_details,
                    paused = excluded.paused,
                    plan_approved = excluded.plan_approved,
                    updated_at = excluded.updated_at
                """,
                (
                    conversation_id,
                    context.task,
                    context.state.value,
                    context.step,
                    json.dumps(context.plan, ensure_ascii=False),
                    json.dumps(context.done, ensure_ascii=False),
                    context.current,
                    int(context.validation_passed),
                    context.validation_details,
                    int(context.paused),
                    int(context.plan_approved),
                    self._now(),
                ),
            )

    def get_task_context(self, conversation_id: str) -> TaskContext | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM working_memory WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        if row is None:
            return None
        return TaskContext(
            task=row["task"],
            state=TaskState(row["state"]),
            step=row["step"],
            plan=json.loads(row["plan_json"]),
            done=json.loads(row["done_json"]),
            current=row["current"],
            validation_passed=bool(row["validation_passed"]),
            validation_details=row["validation_details"],
            paused=bool(row["paused"]),
            plan_approved=bool(row["plan_approved"]),
        )

    def save_working_note(self, conversation_id: str, key: str, value: str) -> None:
        prepared_key, prepared_value = self._prepare_pair(key, value)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO working_notes VALUES (?, ?, ?, ?)
                   ON CONFLICT(conversation_id, key) DO UPDATE SET
                       value = excluded.value, updated_at = excluded.updated_at""",
                (conversation_id, prepared_key, prepared_value, self._now()),
            )

    def get_working_notes(self, conversation_id: str) -> list[WorkingNote]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT key, value, updated_at FROM working_notes
                   WHERE conversation_id = ? ORDER BY key""",
                (conversation_id,),
            ).fetchall()
        return [WorkingNote(row["key"], row["value"], row["updated_at"]) for row in rows]

    # LONG-TERM MEMORY
    def save_long_term(
        self, profile_id: str, kind: LongTermKind, key: str, value: str
    ) -> None:
        prepared_key, prepared_value = self._prepare_pair(key, value)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO long_term_memory VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(profile_id, kind, key) DO UPDATE SET
                       value = excluded.value, updated_at = excluded.updated_at""",
                (profile_id, kind.value, prepared_key, prepared_value, self._now()),
            )

    def get_long_term(self, profile_id: str) -> list[MemoryEntry]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT kind, key, value, updated_at FROM long_term_memory
                   WHERE profile_id = ? ORDER BY kind, key""",
                (profile_id,),
            ).fetchall()
        return [
            MemoryEntry(LongTermKind(row["kind"]), row["key"], row["value"], row["updated_at"])
            for row in rows
        ]

    @staticmethod
    def _prepare_pair(key: str, value: str) -> tuple[str, str]:
        prepared_key = key.strip()
        prepared_value = value.strip()
        if not prepared_key or not prepared_value:
            raise ValueError("Ключ и значение не могут быть пустыми")
        return prepared_key, prepared_value

    @staticmethod
    def _to_message(row: sqlite3.Row) -> Message:
        return Message(row["id"], row["role"], row["content"], row["status"], row["created_at"])

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
