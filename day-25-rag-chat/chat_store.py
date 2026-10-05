"""SQLite history, task state and optimistic per-session turn ownership."""
import json
from pathlib import Path
import sqlite3
import uuid

from memory import empty_state, encode


class ChatStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA foreign_keys=ON;
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, state TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS chat_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES chat_sessions(id),
                question TEXT NOT NULL, status TEXT NOT NULL, response TEXT,
                error TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE UNIQUE INDEX IF NOT EXISTS chat_one_pending
                ON chat_turns(session_id) WHERE status='pending';
            CREATE TABLE IF NOT EXISTS chat_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL
                REFERENCES chat_sessions(id), kind TEXT NOT NULL, payload TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """)

    def close(self):
        self.db.close()

    def create(self, title="Bublik RAG chat"):
        ident = uuid.uuid4().hex
        with self.db:
            self.db.execute("INSERT INTO chat_sessions(id,title,state) VALUES(?,?,?)",
                            (ident, title[:120], encode(empty_state())))
        return ident

    def get(self, session):
        row = self.db.execute("SELECT * FROM chat_sessions WHERE id=?", (session,)).fetchone()
        if row is None:
            raise ValueError("Unknown session; use sessions or /new")
        result = dict(row)
        result["state"] = json.loads(result["state"])
        return result

    def sessions(self):
        return [dict(row) for row in self.db.execute("""
            SELECT s.id,s.title,s.version,s.created_at,count(t.id) AS turns
            FROM chat_sessions s LEFT JOIN chat_turns t ON t.session_id=s.id
            GROUP BY s.id ORDER BY s.created_at DESC,s.id
        """)]

    def history(self, session, limit=None):
        self.get(session)
        if limit is None:
            rows = self.db.execute("SELECT * FROM chat_turns WHERE session_id=? ORDER BY id", (session,))
        else:
            rows = reversed(self.db.execute("SELECT * FROM chat_turns WHERE session_id=? "
                "ORDER BY id DESC LIMIT ?", (session, limit)).fetchall())
        return [{**dict(row), "response": json.loads(row["response"]) if row["response"] else None}
                for row in rows]

    def begin(self, session, question):
        # Reserve and persist the user's message before any network operation.
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            current = self.get(session)
            try:
                cursor = self.db.execute("INSERT INTO chat_turns(session_id,question,status) VALUES(?,?,'pending')",
                                         (session, question))
            except sqlite3.IntegrityError as error:
                raise ValueError("Session has a pending turn; after a crashed process use /recover") from error
        return cursor.lastrowid, current

    def finish(self, session, turn, version, state, response=None, error=None):
        with self.db:
            cursor = self.db.execute("UPDATE chat_turns SET status=?,response=?,error=? "
                "WHERE id=? AND session_id=? AND status='pending'",
                ("error" if error else "complete", encode(response) if response else None, error, turn, session))
            if cursor.rowcount != 1:
                raise ValueError("Turn ownership was lost")
            cursor = self.db.execute("UPDATE chat_sessions SET state=?,version=version+1 WHERE id=? AND version=?",
                                     (encode(state), session, version))
            if cursor.rowcount != 1:
                raise ValueError("Session changed during this turn; retry after inspecting history")

    def set_state(self, session, state, event):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if self.db.execute("SELECT 1 FROM chat_turns WHERE session_id=? AND status='pending'", (session,)).fetchone():
                raise ValueError("Cannot edit memory during a pending turn")
            self.get(session)
            self.db.execute("UPDATE chat_sessions SET state=?,version=version+1 WHERE id=?", (encode(state), session))
            self.db.execute("INSERT INTO chat_events(session_id,kind,payload) VALUES(?,'memory',?)", (session, encode(event)))

    def recover(self, session):
        self.get(session)
        with self.db:
            cursor = self.db.execute("UPDATE chat_turns SET status='error',error='interrupted process' "
                                     "WHERE session_id=? AND status='pending'", (session,))
        return cursor.rowcount

    def export(self, session):
        return {"session": self.get(session), "turns": self.history(session),
                "events": [{**dict(row), "payload": json.loads(row["payload"])} for row in
                    self.db.execute("SELECT * FROM chat_events WHERE session_id=? ORDER BY id", (session,))]}
