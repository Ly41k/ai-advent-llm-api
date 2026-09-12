"""SQLite-память диалогов, facts, checkpoints, веток и метрик."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from tokens import FactUpdateUsage, RequestTokenUsage


@dataclass(frozen=True)
class Conversation:
    id: str
    title: str
    strategy: str
    active_branch_id: str
    message_count: int
    updated_at: str


@dataclass(frozen=True)
class Branch:
    id: str
    conversation_id: str
    name: str
    parent_branch_id: str | None
    forked_from_message_id: int | None
    created_at: str


@dataclass(frozen=True)
class Checkpoint:
    id: str
    conversation_id: str
    branch_id: str
    name: str
    message_id: int | None
    created_at: str


@dataclass(frozen=True)
class Message:
    id: int
    branch_id: str
    role: str
    content: str
    status: str
    created_at: str


@dataclass(frozen=True)
class Fact:
    key: str
    value: str
    updated_at: str


@dataclass(frozen=True)
class ConversationUsage:
    request_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    fact_update_count: int
    fact_update_tokens: int
    fact_update_cost_usd: float


class SQLiteContextRepository:
    """Хранит полную историю; стратегии меняют только выбор контекста."""

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
                    strategy TEXT NOT NULL,
                    active_branch_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS branches (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    parent_branch_id TEXT,
                    forked_from_message_id INTEGER,
                    created_at TEXT NOT NULL,
                    UNIQUE(conversation_id, name),
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (parent_branch_id) REFERENCES branches(id)
                        ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    branch_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('pending', 'completed', 'failed')
                    ),
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (branch_id) REFERENCES branches(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS index_messages_branch
                ON messages(branch_id, id);

                CREATE TABLE IF NOT EXISTS checkpoints (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    branch_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    message_id INTEGER,
                    created_at TEXT NOT NULL,
                    UNIQUE(conversation_id, name),
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (branch_id) REFERENCES branches(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (message_id) REFERENCES messages(id)
                        ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS facts (
                    conversation_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (conversation_id, key),
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS request_usage (
                    user_message_id INTEGER PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    branch_id TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    current_request_tokens INTEGER NOT NULL,
                    full_history_tokens INTEGER NOT NULL,
                    strategy_context_tokens INTEGER NOT NULL,
                    saved_history_tokens INTEGER NOT NULL,
                    estimated_prompt_tokens INTEGER NOT NULL,
                    api_prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    visible_response_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    estimated_cost_usd REAL NOT NULL,
                    FOREIGN KEY (user_message_id) REFERENCES messages(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS fact_update_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    user_message_id INTEGER NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    estimated_cost_usd REAL NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (user_message_id) REFERENCES messages(id)
                        ON DELETE CASCADE
                );
                """
            )

    def create_conversation(self, title: str, strategy: str) -> Conversation:
        prepared_title = title.strip()
        if not prepared_title:
            raise ValueError("Название диалога не может быть пустым")

        conversation_id = str(uuid4())
        branch_id = str(uuid4())
        created_at = self._now()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO conversations(
                    id, title, strategy, active_branch_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    conversation_id,
                    prepared_title,
                    strategy,
                    branch_id,
                    created_at,
                    created_at,
                ),
            )
            connection.execute(
                """INSERT INTO branches(
                    id, conversation_id, name, parent_branch_id,
                    forked_from_message_id, created_at
                ) VALUES (?, ?, 'main', NULL, NULL, ?)""",
                (branch_id, conversation_id, created_at),
            )
        return Conversation(
            conversation_id,
            prepared_title,
            strategy,
            branch_id,
            0,
            created_at,
        )

    def get_conversations(self) -> list[Conversation]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.id, c.title, c.strategy, c.active_branch_id, c.updated_at,
                       COUNT(CASE WHEN m.status = 'completed' THEN 1 END) message_count
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                """
            ).fetchall()
        return [self._to_conversation(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT c.id, c.title, c.strategy, c.active_branch_id, c.updated_at,
                       COUNT(CASE WHEN m.status = 'completed' THEN 1 END) message_count
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.id = ?
                GROUP BY c.id
                """,
                (conversation_id,),
            ).fetchone()
        return self._to_conversation(row) if row else None

    def set_strategy(self, conversation_id: str, strategy: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE conversations SET strategy = ?, updated_at = ? WHERE id = ?",
                (strategy, self._now(), conversation_id),
            )

    def start_user_request(
        self,
        conversation_id: str,
        branch_id: str,
        content: str,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO messages(
                    conversation_id, branch_id, role, content, status, created_at
                ) VALUES (?, ?, 'user', ?, 'pending', ?)""",
                (conversation_id, branch_id, content, self._now()),
            )
        return int(cursor.lastrowid)

    def complete_exchange(
        self,
        user_message_id: int,
        conversation_id: str,
        branch_id: str,
        strategy: str,
        assistant_content: str,
        usage: RequestTokenUsage,
    ) -> None:
        now = self._now()
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE messages SET status = 'completed'
                   WHERE id = ? AND status = 'pending'""",
                (user_message_id,),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Не найден ожидающий пользовательский запрос")
            connection.execute(
                """INSERT INTO messages(
                    conversation_id, branch_id, role, content, status, created_at
                ) VALUES (?, ?, 'assistant', ?, 'completed', ?)""",
                (conversation_id, branch_id, assistant_content, now),
            )
            connection.execute(
                """INSERT INTO request_usage VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )""",
                (
                    user_message_id,
                    conversation_id,
                    branch_id,
                    strategy,
                    usage.current_request_tokens,
                    usage.full_history_tokens,
                    usage.strategy_context_tokens,
                    usage.saved_history_tokens,
                    usage.estimated_prompt_tokens,
                    usage.api_prompt_tokens,
                    usage.completion_tokens,
                    usage.visible_response_tokens,
                    usage.total_tokens,
                    usage.estimated_cost_usd,
                ),
            )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )

    def fail_request(self, user_message_id: int, error_message: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE messages SET status = 'failed', error_message = ?
                   WHERE id = ? AND status = 'pending'""",
                (error_message, user_message_id),
            )

    def get_branch_history(self, branch_id: str) -> list[Message]:
        """Собирает унаследованные сообщения до checkpoint и локальную ветку."""

        lineage = self._get_branch_lineage(branch_id)
        result: list[Message] = []
        with self._connect() as connection:
            for index, branch in enumerate(lineage):
                upper_bound = (
                    lineage[index + 1].forked_from_message_id
                    if index + 1 < len(lineage)
                    else None
                )
                query = """
                    SELECT id, branch_id, role, content, status, created_at
                    FROM messages
                    WHERE branch_id = ? AND status = 'completed'
                """
                parameters: list[object] = [branch.id]
                if upper_bound is not None:
                    query += " AND id <= ?"
                    parameters.append(upper_bound)
                query += " ORDER BY id ASC"
                rows = connection.execute(query, parameters).fetchall()
                result.extend(self._to_message(row) for row in rows)
        return result

    def get_history(self, branch_id: str, limit: int = 30) -> list[Message]:
        history = self.get_branch_history(branch_id)
        return history[-limit:]

    def get_facts(self, conversation_id: str) -> list[Fact]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT key, value, updated_at FROM facts
                   WHERE conversation_id = ? ORDER BY key""",
                (conversation_id,),
            ).fetchall()
        return [Fact(row["key"], row["value"], row["updated_at"]) for row in rows]

    def replace_facts(
        self,
        conversation_id: str,
        facts: dict[str, str],
        user_message_id: int,
        usage: FactUpdateUsage,
    ) -> None:
        now = self._now()
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM facts WHERE conversation_id = ?",
                (conversation_id,),
            )
            connection.executemany(
                """INSERT INTO facts(conversation_id, key, value, updated_at)
                   VALUES (?, ?, ?, ?)""",
                [
                    (conversation_id, key, value, now)
                    for key, value in sorted(facts.items())
                ],
            )
            connection.execute(
                """INSERT INTO fact_update_usage(
                    conversation_id, user_message_id, prompt_tokens,
                    completion_tokens, total_tokens, estimated_cost_usd
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    conversation_id,
                    user_message_id,
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    usage.total_tokens,
                    usage.estimated_cost_usd,
                ),
            )

    def create_checkpoint(self, conversation_id: str, name: str) -> Checkpoint:
        prepared_name = name.strip()
        if not prepared_name:
            raise ValueError("Имя checkpoint не может быть пустым")
        conversation = self._require_conversation(conversation_id)
        history = self.get_branch_history(conversation.active_branch_id)
        message_id = history[-1].id if history else None
        checkpoint = Checkpoint(
            str(uuid4()),
            conversation_id,
            conversation.active_branch_id,
            prepared_name,
            message_id,
            self._now(),
        )
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO checkpoints VALUES (?, ?, ?, ?, ?, ?)",
                (
                    checkpoint.id,
                    checkpoint.conversation_id,
                    checkpoint.branch_id,
                    checkpoint.name,
                    checkpoint.message_id,
                    checkpoint.created_at,
                ),
            )
        return checkpoint

    def get_checkpoints(self, conversation_id: str) -> list[Checkpoint]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM checkpoints WHERE conversation_id = ?
                   ORDER BY created_at""",
                (conversation_id,),
            ).fetchall()
        return [self._to_checkpoint(row) for row in rows]

    def create_branch(
        self,
        conversation_id: str,
        name: str,
        checkpoint_name: str,
    ) -> Branch:
        prepared_name = name.strip()
        if not prepared_name:
            raise ValueError("Имя ветки не может быть пустым")
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM checkpoints
                   WHERE conversation_id = ? AND name = ?""",
                (conversation_id, checkpoint_name),
            ).fetchone()
            if row is None:
                raise ValueError(f"Checkpoint '{checkpoint_name}' не найден")
            checkpoint = self._to_checkpoint(row)
            branch = Branch(
                str(uuid4()),
                conversation_id,
                prepared_name,
                checkpoint.branch_id,
                checkpoint.message_id,
                self._now(),
            )
            connection.execute(
                """INSERT INTO branches VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    branch.id,
                    branch.conversation_id,
                    branch.name,
                    branch.parent_branch_id,
                    branch.forked_from_message_id,
                    branch.created_at,
                ),
            )
        return branch

    def get_branches(self, conversation_id: str) -> list[Branch]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM branches WHERE conversation_id = ?
                   ORDER BY created_at""",
                (conversation_id,),
            ).fetchall()
        return [self._to_branch(row) for row in rows]

    def switch_branch(self, conversation_id: str, branch_name: str) -> Branch:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM branches
                   WHERE conversation_id = ? AND name = ?""",
                (conversation_id, branch_name),
            ).fetchone()
            if row is None:
                raise ValueError(f"Ветка '{branch_name}' не найдена")
            branch = self._to_branch(row)
            connection.execute(
                """UPDATE conversations SET active_branch_id = ?, updated_at = ?
                   WHERE id = ?""",
                (branch.id, self._now(), conversation_id),
            )
        return branch

    def get_active_branch(self, conversation_id: str) -> Branch:
        conversation = self._require_conversation(conversation_id)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM branches WHERE id = ?",
                (conversation.active_branch_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("Активная ветка не найдена")
        return self._to_branch(row)

    def get_conversation_usage(self, conversation_id: str) -> ConversationUsage:
        with self._connect() as connection:
            request = connection.execute(
                """SELECT COUNT(*) count, COALESCE(SUM(api_prompt_tokens), 0) prompt,
                          COALESCE(SUM(completion_tokens), 0) completion,
                          COALESCE(SUM(total_tokens), 0) total,
                          COALESCE(SUM(estimated_cost_usd), 0) cost
                   FROM request_usage WHERE conversation_id = ?""",
                (conversation_id,),
            ).fetchone()
            facts = connection.execute(
                """SELECT COUNT(*) count, COALESCE(SUM(total_tokens), 0) total,
                          COALESCE(SUM(estimated_cost_usd), 0) cost
                   FROM fact_update_usage WHERE conversation_id = ?""",
                (conversation_id,),
            ).fetchone()
        return ConversationUsage(
            int(request["count"]),
            int(request["prompt"]),
            int(request["completion"]),
            int(request["total"]),
            float(request["cost"]),
            int(facts["count"]),
            int(facts["total"]),
            float(facts["cost"]),
        )

    def _get_branch_lineage(self, branch_id: str) -> list[Branch]:
        lineage: list[Branch] = []
        current_id: str | None = branch_id
        with self._connect() as connection:
            while current_id is not None:
                row = connection.execute(
                    "SELECT * FROM branches WHERE id = ?",
                    (current_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("Ветка не найдена")
                branch = self._to_branch(row)
                lineage.append(branch)
                current_id = branch.parent_branch_id
        return list(reversed(lineage))

    def _require_conversation(self, conversation_id: str) -> Conversation:
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            raise ValueError("Диалог не найден")
        return conversation

    @staticmethod
    def _to_conversation(row: sqlite3.Row) -> Conversation:
        return Conversation(
            row["id"],
            row["title"],
            row["strategy"],
            row["active_branch_id"],
            int(row["message_count"]),
            row["updated_at"],
        )

    @staticmethod
    def _to_branch(row: sqlite3.Row) -> Branch:
        return Branch(
            row["id"],
            row["conversation_id"],
            row["name"],
            row["parent_branch_id"],
            row["forked_from_message_id"],
            row["created_at"],
        )

    @staticmethod
    def _to_checkpoint(row: sqlite3.Row) -> Checkpoint:
        return Checkpoint(
            row["id"],
            row["conversation_id"],
            row["branch_id"],
            row["name"],
            row["message_id"],
            row["created_at"],
        )

    @staticmethod
    def _to_message(row: sqlite3.Row) -> Message:
        return Message(
            int(row["id"]),
            row["branch_id"],
            row["role"],
            row["content"],
            row["status"],
            row["created_at"],
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
