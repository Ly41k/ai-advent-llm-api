"""Owner-scoped history, durable jobs and atomic idempotent admission.

All methods are synchronous and open their own SQLite connection. The future
async API must offload each entire operation, not individual SQL statements.
The owner argument comes from an authenticated server principal, never HTTP JSON.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import uuid

from bublik_service.domain import (
    CapacityExceeded, Conflict, ContextPlan,
    InvalidInput, ModelProfile, NotFound, QueueLimits, Receipt,
    RETRYABLE_STATUSES, StorageUnavailable, integer,
)
from .database import APPLICATION_ID, Database

MAX_MESSAGE_BYTES = 16 * 1024
MAX_RESPONSE_BYTES = 64 * 1024


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def text(value, maximum, code="invalid_input"):
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise InvalidInput(code)
    try:
        if len(value.encode("utf-8")) > maximum:
            raise InvalidInput(code)
    except UnicodeError:
        raise InvalidInput(code) from None
    return value


def request_key(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value):
        raise InvalidInput("invalid_idempotency_key")
    return value


class ChatRepository:
    def __init__(self, path, *, limits=None, clock=None, timeout=5, admission_policy=None):
        self.database = Database(path, timeout=timeout)
        self.admission_policy = admission_policy
        self.limits = limits or QueueLimits()
        self.limits.validate()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self):
        now = self.clock()
        if now.tzinfo is None:
            raise InvalidInput("clock_must_be_aware")
        return now.astimezone(timezone.utc).isoformat(timespec="microseconds")

    @staticmethod
    def _user(db, owner):
        if db.execute("SELECT id FROM users WHERE id=?", (owner,)).fetchone() is None:
            raise NotFound()

    @staticmethod
    def _chat(db, owner, chat):
        row = db.execute("SELECT * FROM chats WHERE id=? AND owner_id=?", (chat, owner)).fetchone()
        if row is None:
            raise NotFound()
        return row

    @staticmethod
    def _generation(db, owner, generation):
        row = db.execute("SELECT g.* FROM generations g JOIN chats c ON c.id=g.chat_id "
                         "WHERE g.id=? AND c.owner_id=?", (generation, owner)).fetchone()
        if row is None:
            raise NotFound()
        return row

    def create_user(self, username, password_hash):
        """Identity persistence only; password hashing/login belong to stage 4."""
        name = text(username, 80).strip().casefold()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,79}", name):
            raise InvalidInput("invalid_username")
        text(password_hash, 1024, "invalid_password_hash")
        with self.database.connect(write=True) as db:
            if db.execute("SELECT 1 FROM users WHERE username=?", (name,)).fetchone():
                raise Conflict("username_exists")
            ident = uuid.uuid4().hex
            db.execute("INSERT INTO users VALUES (?,?,?,?)", (ident, name, password_hash, self._now()))
            return ident

    def user_id(self, username):
        """Local operator lookup, not authentication; never expose to unauthenticated HTTP."""
        name = text(username, 80).strip().casefold()
        with self.database.connect() as db:
            row = db.execute("SELECT id FROM users WHERE username=?", (name,)).fetchone()
            if row is None:
                raise NotFound()
            return row[0]

    @staticmethod
    def _replay(db, owner, operation, key, payload):
        fingerprint = hashlib.sha256(canonical(payload).encode()).hexdigest()
        row = db.execute("SELECT * FROM idempotency WHERE owner_id=? AND operation=? AND request_key=?",
                         (owner, operation, key)).fetchone()
        if row is None:
            return None, fingerprint
        if row["fingerprint"] != fingerprint:
            raise Conflict("idempotency_conflict")
        return Receipt(**json.loads(row["result_json"]), replayed=True), fingerprint

    def _remember(self, db, owner, operation, key, fingerprint, receipt):
        value = asdict(receipt)
        value.pop("replayed")
        db.execute("INSERT INTO idempotency VALUES (?,?,?,?,?,?)",
                   (owner, operation, key, fingerprint, canonical(value), self._now()))

    def create_chat(self, owner, title="Bublik chat", *, key):
        text(title, 480, "invalid_title")
        if len(title) > 120:
            raise InvalidInput("invalid_title")
        request_key(key)
        with self.database.connect(write=True) as db:
            self._user(db, owner)
            replay, fingerprint = self._replay(db, owner, "chat.create", key, {"title": title})
            if replay:
                return replay
            ident, now = uuid.uuid4().hex, self._now()
            db.execute("INSERT INTO chats(id,owner_id,title,created_at,updated_at) VALUES (?,?,?,?,?)",
                       (ident, owner, title, now, now))
            receipt = Receipt(ident, 0)
            self._remember(db, owner, "chat.create", key, fingerprint, receipt)
            return receipt

    def get_chat(self, owner, chat):
        with self.database.connect() as db:
            return dict(self._chat(db, owner, chat))

    def list_chats(self, owner, *, limit=50, after=None):
        self._page(limit)
        with self.database.connect() as db:
            self._user(db, owner)
            params, clause = [owner], ""
            if after is not None:
                anchor = self._chat(db, owner, after)
                clause = " AND (created_at,id) > (?,?)"
                params += [anchor["created_at"], anchor["id"]]
            params.append(limit)
            return [dict(r) for r in db.execute(
                "SELECT * FROM chats WHERE owner_id=?" + clause + " ORDER BY created_at,id LIMIT ?", params)]

    @staticmethod
    def _page(limit):
        if not integer(limit, 1) or limit > 100:
            raise InvalidInput("invalid_page_size")

    def history(self, owner, chat, *, after_sequence=0, limit=100):
        self._page(limit)
        if not integer(after_sequence):
            raise InvalidInput("invalid_history_cursor")
        with self.database.connect() as db:
            self._chat(db, owner, chat)
            return [self._history_row(r) for r in db.execute(
                "SELECT m.*,g.id AS generation_id,g.attempt,g.error_code,g.context_json "
                "FROM messages m LEFT JOIN generations g ON g.assistant_message_id=m.id "
                "WHERE m.chat_id=? AND m.sequence>? ORDER BY m.sequence LIMIT ?",
                (chat, after_sequence, limit))]

    def history_tail(self, owner, chat, *, before_sequence=None, limit=50):
        """Recent history in display order; earlier pages never change old cursors."""
        self._page(limit)
        if before_sequence is not None and not integer(before_sequence, 1):
            raise InvalidInput("invalid_history_cursor")
        with self.database.connect() as db:
            self._chat(db, owner, chat)
            params, clause = [chat], ""
            if before_sequence is not None:
                params.append(before_sequence)
                clause = " AND m.sequence<?"
            params.append(limit)
            rows = db.execute(
                "SELECT m.*,g.id AS generation_id,g.attempt,g.error_code,g.context_json "
                "FROM messages m LEFT JOIN generations g ON g.assistant_message_id=m.id "
                "WHERE m.chat_id=?" + clause + " ORDER BY m.sequence DESC LIMIT ?", params).fetchall()
            return [self._history_row(r) for r in reversed(rows)]

    @staticmethod
    def _history_row(row):
        result = dict(row)
        context = json.loads(result.pop("context_json") or "{}")
        # Expose only the citations, never full inference prompts/engine provenance.
        if context.get("memory", {}).get("enabled"):
            result["memory"] = context["memory"]
        if context.get("reply_language"):
            result["reply_language"] = context["reply_language"]
        return result

    @staticmethod
    def _completed(db, chat, max_turns=100):
        rows = db.execute(
            "SELECT u.id AS uid,u.content AS question,a.id AS aid,a.content AS answer "
            "FROM generations g JOIN messages u ON u.id=g.user_message_id "
            "JOIN messages a ON a.id=g.assistant_message_id "
            "WHERE g.chat_id=? AND g.status='completed' ORDER BY u.sequence DESC LIMIT ?",
            (chat, max_turns)).fetchall()
        result = []
        for row in reversed(rows):
            result += [{"id": row["uid"], "role": "user", "content": row["question"]},
                       {"id": row["aid"], "role": "assistant", "content": row["answer"]}]
        return result

    def context_candidates(self, owner, chat, *, limit_turns=32):
        """A consistent revision and eligible complete pairs for ContextBuilder."""
        self._page(limit_turns)
        with self.database.connect() as db:
            current = self._chat(db, owner, chat)
            return {"revision": current["revision"], "messages": self._completed(db, chat, limit_turns),
                    "total_completed_turns": db.execute(
                        "SELECT count(*) FROM generations WHERE chat_id=? AND status='completed'", (chat,)).fetchone()[0]}

    def memory_source(self, owner, chat, message):
        with self.database.connect() as db:
            self._chat(db, owner, chat)
            row = db.execute("SELECT * FROM messages WHERE id=? AND chat_id=?",
                             (message, chat)).fetchone()
            if row is None:
                raise NotFound()
            return dict(row)

    def preferences(self, owner):
        with self.database.connect() as db:
            self._user(db, owner)
            row = db.execute("SELECT ui_language,reply_language,revision FROM user_preferences WHERE owner_id=?", (owner,)).fetchone()
            if row is None:
                raise StorageUnavailable("preferences_missing")
            return dict(row)

    def set_preferences(self, owner, *, ui_language, reply_language, expected_revision):
        from bublik_service.languages import validate_language
        validate_language(ui_language); validate_language(reply_language)
        if not integer(expected_revision):
            raise InvalidInput("invalid_revision")
        with self.database.connect(write=True) as db:
            self._user(db, owner)
            row = db.execute("SELECT * FROM user_preferences WHERE owner_id=?", (owner,)).fetchone()
            if row is None:
                raise StorageUnavailable("preferences_missing")
            if row["revision"] != expected_revision:
                raise Conflict("preferences_changed")
            if (row["ui_language"], row["reply_language"]) != (ui_language, reply_language):
                db.execute("UPDATE user_preferences SET ui_language=?,reply_language=?,revision=revision+1 WHERE owner_id=?",
                           (ui_language, reply_language, owner))
            return dict(db.execute("SELECT ui_language,reply_language,revision FROM user_preferences WHERE owner_id=?", (owner,)).fetchone())

    @staticmethod
    def _memory_row(db, owner, message):
        # Accepted user text is immutable even when its answer failed or is pending.
        # Only immutable terminal assistant text enters retrieval snapshots.
        return db.execute(
            "SELECT m.* FROM messages m JOIN chats c ON c.id=m.chat_id "
            "WHERE m.id=? AND c.owner_id=? AND m.content<>'' AND "
            "(m.role='user' OR (m.status IN ('completed','truncated','failed','interrupted') "
            "AND EXISTS (SELECT 1 FROM generations g WHERE g.assistant_message_id=m.id "
            "AND g.status=m.status)))", (message, owner)).fetchone()

    def memory_context(self, owner, chat, message, *, before=4, after=4):
        """Bounded original conversation window; independent of inference budget."""
        if not integer(before) or not integer(after) or before > 10 or after > 10:
            raise InvalidInput("invalid_history_cursor")
        with self.database.connect() as db:
            self._chat(db, owner, chat)
            anchor = db.execute("SELECT * FROM messages WHERE id=? AND chat_id=?",
                                (message, chat)).fetchone()
            if anchor is None:
                raise NotFound()
            lo, hi = max(1, anchor["sequence"] - before), anchor["sequence"] + after
            rows = db.execute(
                "SELECT m.*,g.id AS generation_id,g.attempt,g.error_code,g.context_json "
                "FROM messages m LEFT JOIN generations g ON g.assistant_message_id=m.id "
                "WHERE m.chat_id=? AND m.sequence BETWEEN ? AND ? ORDER BY m.sequence",
                (chat, lo, hi)).fetchall()
            return {"anchor_message_id": message, "items": [self._history_row(r) for r in rows],
                    "has_earlier": bool(db.execute("SELECT 1 FROM messages WHERE chat_id=? AND sequence<? LIMIT 1", (chat,lo)).fetchone()),
                    "has_later": bool(db.execute("SELECT 1 FROM messages WHERE chat_id=? AND sequence>? LIMIT 1", (chat,hi)).fetchone())}

    def _snapshot(self, db, chat, content, plan, profile):
        if not isinstance(plan, ContextPlan) or not isinstance(profile, ModelProfile):
            raise InvalidInput("invalid_context_plan")
        plan.validate(profile)
        count = len(plan.history_message_ids)
        if count > 200:
            raise InvalidInput("context_too_many_messages")
        completed = self._completed(db, chat, max_turns=count // 2) if count else []
        total = db.execute("SELECT count(*) FROM generations WHERE chat_id=? AND status='completed'", (chat,)).fetchone()[0]
        selected = completed[-count:] if count else []
        if (count % 2 or count > len(completed)
                or tuple(x["id"] for x in selected) != plan.history_message_ids):
            raise InvalidInput("context_not_complete_suffix")
        snapshot = {"policy_version": plan.policy_version,
                "history_message_ids": list(plan.history_message_ids),
                "omitted_turns": total - count // 2,
                "input_token_upper_bound": plan.input_token_upper_bound,
                "model_identity": asdict(plan.model_identity) if plan.model_identity is not None else None,
                "messages": [{"role": "system", "content": profile.system_prompt},
                             *[{"role": x["role"], "content": x["content"]} for x in selected],
                             {"role": "user", "content": content}]}
        from bublik_service.languages import system_prompt_for_reply, user_content_for_reply, language_hint_metadata, POLICY as LANGUAGE_POLICY
        language = plan.reply_language is not None
        if language:
            snapshot["messages"][0]["content"] = system_prompt_for_reply(profile, plan.reply_language)
            snapshot["reply_language"] = plan.reply_language
            snapshot["language_policy"] = LANGUAGE_POLICY
            snapshot["original_user_content"] = content
            snapshot["language_hint"] = language_hint_metadata(content, plan.reply_language)
            snapshot["messages"][-1]["content"] = user_content_for_reply(content, plan.reply_language)
        if plan.memory_enabled:
            from bublik_service.memory import memory_messages
            owner = db.execute("SELECT owner_id FROM chats WHERE id=?", (chat,)).fetchone()[0]
            for source in plan.memory_sources:
                row = self._memory_row(db, owner, source.message_id)
                if (row is None or row["chat_id"] != source.chat_id or row["sequence"] != source.sequence
                        or row["created_at"] != source.created_at
                        or row["role"] != source.role or row["status"] != source.status
                        or hashlib.sha256(row["content"].encode()).hexdigest() != source.source_sha256
                        or row["content"][source.start:source.end] != source.quote):
                    raise InvalidInput("memory_source_mismatch")
            snapshot["messages"][1:1] = memory_messages(plan.memory_sources)
            snapshot["memory"] = {"enabled": True, "policy_version": plan.memory_policy,
                                  "sources": [asdict(x) for x in plan.memory_sources],
                                  "indexed_messages": plan.memory_indexed_messages,
                                  "search_seconds": plan.memory_search_seconds}
            from bublik_service.inference.context import upper_bound
            if upper_bound(snapshot["messages"]) != plan.input_token_upper_bound:
                raise InvalidInput("invalid_context_plan")
        elif language:
            from bublik_service.inference.context import upper_bound
            if upper_bound(snapshot["messages"]) != plan.input_token_upper_bound:
                raise InvalidInput("invalid_context_plan")
        return snapshot

    @staticmethod
    def _message_payload(content, expected_revision, use_memory, reply_language=None):
        from bublik_service.languages import validate_language
        validate_language(reply_language, optional=True)
        if type(use_memory) is not bool:
            raise InvalidInput("invalid_memory_mode")
        result = {"content": content, "expected_revision": expected_revision}
        if use_memory:
            result["use_memory"] = True
        if reply_language is not None:
            result["reply_language"] = reply_language
        return result

    @staticmethod
    def _retry_payload(expected_revision, use_memory, reply_language=None):
        from bublik_service.languages import validate_language
        validate_language(reply_language, optional=True)
        if type(use_memory) is not bool:
            raise InvalidInput("invalid_memory_mode")
        result = {"expected_revision": expected_revision}
        if use_memory:
            result["use_memory"] = True
        if reply_language is not None:
            result["reply_language"] = reply_language
        return result

    def _admission(self, db, owner, chat, expected_revision):
        if db.execute("SELECT inference_uncertain FROM service_state WHERE id=1").fetchone()[0]:
            raise Conflict("inference_recovery_required")
        current = self._chat(db, owner, chat)
        if current["revision"] != expected_revision:
            raise Conflict("stale_revision")
        if db.execute("SELECT 1 FROM generations WHERE chat_id=? AND status IN ('queued','running')",
                      (chat,)).fetchone():
            raise Conflict("chat_has_outstanding_generation")
        outstanding = db.execute(
            "SELECT count(*) FROM generations g JOIN chats c ON c.id=g.chat_id "
            "WHERE c.owner_id=? AND g.status IN ('queued','running')", (owner,)).fetchone()[0]
        if outstanding >= self.limits.per_user_outstanding:
            raise CapacityExceeded("user_queue_full")
        if db.execute("SELECT count(*) FROM generations WHERE status='queued'").fetchone()[0] >= self.limits.queued:
            raise CapacityExceeded("global_queue_full")
        if self.admission_policy is not None:
            self.admission_policy(db, owner)
        return current

    def replay_message(self, owner, chat, content, *, expected_revision, key, use_memory=False, reply_language=None):
        text(content, MAX_MESSAGE_BYTES, "invalid_message")
        request_key(key)
        if not integer(expected_revision):
            raise InvalidInput("invalid_revision")
        with self.database.connect() as db:
            self._chat(db, owner, chat)
            return self._replay(db, owner, "message.create:" + chat, key,
                                self._message_payload(content, expected_revision, use_memory, reply_language))[0]

    def retry_candidate(self, owner, message):
        with self.database.connect() as db:
            row = db.execute("SELECT m.* FROM messages m JOIN chats c ON c.id=m.chat_id "
                             "WHERE m.id=? AND m.role='user' AND c.owner_id=?", (message, owner)).fetchone()
            if row is None:
                raise NotFound()
            return dict(row)

    def replay_retry(self, owner, message, *, expected_revision, key, use_memory=False, reply_language=None):
        request_key(key)
        if not integer(expected_revision):
            raise InvalidInput("invalid_revision")
        with self.database.connect() as db:
            row = db.execute("SELECT m.chat_id FROM messages m JOIN chats c ON c.id=m.chat_id "
                             "WHERE m.id=? AND m.role='user' AND c.owner_id=?", (message, owner)).fetchone()
            if row is None:
                raise NotFound()
            return self._replay(db, owner, "message.retry:" + message, key,
                                self._retry_payload(expected_revision, use_memory, reply_language))[0]

    def recovery_context(self):
        """Trusted coordinator only: last transition that could have set the inference gate."""
        with self.database.connect() as db:
            row = db.execute("SELECT context_json FROM generations WHERE status='interrupted' "
                             "OR error_code IN ('model_timeout','inference_state_unknown') "
                             "OR json_extract(context_json,'$.inference_uncertain')=1 "
                             "ORDER BY finished_at DESC,queue_order DESC LIMIT 1").fetchone()
            return json.loads(row[0]) if row else None

    def accept_message(self, owner, chat, content, *, expected_revision, key, context,
                       profile=None):
        text(content, MAX_MESSAGE_BYTES, "invalid_message")
        request_key(key)
        if not integer(expected_revision):
            raise InvalidInput("invalid_revision")
        profile = profile or ModelProfile()
        with self.database.connect(write=True) as db:
            self._chat(db, owner, chat)
            operation = "message.create:" + chat
            replay, fingerprint = self._replay(db, owner, operation, key,
                                              self._message_payload(content, expected_revision, context.memory_enabled, context.reply_language))
            if replay:
                return replay
            self._admission(db, owner, chat, expected_revision)
            snapshot = self._snapshot(db, chat, content, context, profile)
            user_id, assistant_id, generation_id = (uuid.uuid4().hex for _ in range(3))
            now = self._now()
            sequence = db.execute("SELECT coalesce(max(sequence),0)+1 FROM messages WHERE chat_id=?",
                                  (chat,)).fetchone()[0]
            db.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?,?)",
                       (user_id, chat, sequence, "user", content, "accepted", now, now))
            self._enqueue(db, chat, user_id, assistant_id, generation_id, sequence + 1,
                          expected_revision, snapshot, profile, attempt=1)
            receipt = Receipt(chat, expected_revision + 1, user_id, assistant_id, generation_id)
            self._remember(db, owner, operation, key, fingerprint, receipt)
            return receipt

    def _enqueue(self, db, chat, user, assistant, generation, sequence, revision, snapshot,
                 profile, *, attempt):
        now = self._now()
        db.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?,?)",
                   (assistant, chat, sequence, "assistant", "", "queued", now, now))
        db.execute("INSERT INTO generations(id,chat_id,user_message_id,assistant_message_id,attempt,status,"
                   "base_revision,profile_json,context_json,created_at) VALUES (?,?,?,?,?,'queued',?,?,?,?)",
                   (generation, chat, user, assistant, attempt, revision,
                    canonical(profile.to_dict()), canonical(snapshot), now))
        changed = db.execute("UPDATE chats SET revision=revision+1,updated_at=? WHERE id=? AND revision=?",
                             (now, chat, revision))
        if changed.rowcount != 1:
            raise Conflict("stale_revision")
        db.execute("INSERT INTO chat_events(chat_id,generation_id,kind,created_at) VALUES (?,?,'accepted',?)",
                   (chat, generation, now))

    def retry_message(self, owner, message, *, expected_revision, key, context, profile=None):
        request_key(key)
        if not integer(expected_revision):
            raise InvalidInput("invalid_revision")
        profile = profile or ModelProfile()
        with self.database.connect(write=True) as db:
            row = db.execute("SELECT m.* FROM messages m JOIN chats c ON c.id=m.chat_id "
                             "WHERE m.id=? AND m.role='user' AND c.owner_id=?", (message, owner)).fetchone()
            if row is None:
                raise NotFound()
            operation = "message.retry:" + message
            replay, fingerprint = self._replay(db, owner, operation, key, self._retry_payload(expected_revision, context.memory_enabled, context.reply_language))
            if replay:
                return replay
            chat = row["chat_id"]
            self._admission(db, owner, chat, expected_revision)
            latest_user = db.execute("SELECT id FROM messages WHERE chat_id=? AND role='user' "
                                     "ORDER BY sequence DESC LIMIT 1", (chat,)).fetchone()[0]
            previous = db.execute("SELECT * FROM generations WHERE user_message_id=? ORDER BY attempt DESC LIMIT 1",
                                  (message,)).fetchone()
            if latest_user != message or previous is None or previous["status"] not in RETRYABLE_STATUSES:
                raise Conflict("retry_not_allowed")
            snapshot = self._snapshot(db, chat, row["content"], context, profile)
            assistant, generation = uuid.uuid4().hex, uuid.uuid4().hex
            sequence = db.execute("SELECT max(sequence)+1 FROM messages WHERE chat_id=?", (chat,)).fetchone()[0]
            self._enqueue(db, chat, message, assistant, generation, sequence, expected_revision,
                          snapshot, profile, attempt=previous["attempt"] + 1)
            receipt = Receipt(chat, expected_revision + 1, message, assistant, generation)
            self._remember(db, owner, operation, key, fingerprint, receipt)
            return receipt

    @staticmethod
    def _public_generation(row):
        result = {k: row[k] for k in row.keys()
                  if k not in {"worker_token", "profile_json", "context_json", "metrics_json", "queue_order"}}
        result.update(profile=json.loads(row["profile_json"]), context=json.loads(row["context_json"]),
                      metrics=json.loads(row["metrics_json"]))
        return result

    def get_generation(self, owner, generation):
        with self.database.connect() as db:
            row = self._generation(db, owner, generation)
            result = self._public_generation(row)
            result["assistant"] = dict(db.execute("SELECT * FROM messages WHERE id=?",
                                                  (row["assistant_message_id"],)).fetchone())
            result["stream_revision"] = db.execute("SELECT version FROM message_stream_versions WHERE message_id=?",
                                                   (row["assistant_message_id"],)).fetchone()[0]
            return result

    def export_chat(self, owner, chat):
        """One WAL read snapshot; no password hashes or worker tokens are exported."""
        with self.database.connect() as db:
            current = dict(self._chat(db, owner, chat))
            return {"format": "bublik-chat-export-v1", "chat": current,
                    "messages": [dict(r) for r in db.execute("SELECT * FROM messages WHERE chat_id=? ORDER BY sequence", (chat,))],
                    "generations": [self._public_generation(r) for r in db.execute(
                        "SELECT * FROM generations WHERE chat_id=? ORDER BY queue_order", (chat,))],
                    "events": [dict(r) for r in db.execute("SELECT * FROM chat_events WHERE chat_id=? ORDER BY id", (chat,))]}

    def worker_session(self):
        from .worker import WorkerSession
        return WorkerSession(self)

    def _terminal(self, db, row, status, error_code, *, content=None, metrics=None, event="finished"):
        now = self._now()
        existing = db.execute("SELECT content FROM messages WHERE id=?", (row["assistant_message_id"],)).fetchone()[0]
        content = existing if content is None else content
        if not isinstance(content, str) or not content.startswith(existing):
            raise Conflict("answer_checkpoint_would_be_rewritten")
        if status in {"completed", "truncated"}:
            text(content, MAX_RESPONSE_BYTES, "invalid_answer")
        else:
            try:
                if len(content.encode("utf-8")) > MAX_RESPONSE_BYTES or "\x00" in content:
                    raise InvalidInput("invalid_answer")
            except UnicodeError:
                raise InvalidInput("invalid_answer") from None
        db.execute("UPDATE messages SET content=?,status=?,updated_at=? WHERE id=?",
                   (content, status, now, row["assistant_message_id"]))
        db.execute("UPDATE generations SET status=?,error_code=?,metrics_json=?,finished_at=? WHERE id=?",
                   (status, error_code, canonical(metrics or {}), now, row["id"]))
        changed = db.execute("UPDATE chats SET revision=revision+1,updated_at=? WHERE id=? AND revision=?",
                             (now, row["chat_id"], row["base_revision"] + 1))
        if changed.rowcount != 1:
            raise Conflict("generation_revision_changed")
        db.execute("INSERT INTO chat_events(chat_id,generation_id,kind,created_at) VALUES (?,?,?,?)",
                   (row["chat_id"], row["id"], event, now))

    def storage_status(self):
        result = self.database.status()
        result.update(self.queue_status())
        return result

    def queue_status(self):
        result = {}
        with self.database.connect() as db:
            result["inference_recovery_required"] = bool(db.execute(
                "SELECT inference_uncertain FROM service_state WHERE id=1").fetchone()[0])
            result["queued"] = db.execute("SELECT count(*) FROM generations WHERE status='queued'").fetchone()[0]
            result["running"] = db.execute("SELECT count(*) FROM generations WHERE status='running'").fetchone()[0]
        return result

    def backup(self, destination):
        """Create a new consistent backup; never overwrite an existing file."""
        import os
        import tempfile
        target = Path(destination).expanduser().absolute()
        protected = [Path(str(self.database.path) + suffix) for suffix in ("", "-wal", "-shm", "-journal")]
        if target.is_symlink() or target.exists() or target.resolve() in {p.resolve() for p in protected}:
            raise InvalidInput("backup_destination_exists_or_protected")
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.database.check_identity()
        try:
            fd, temporary_name = tempfile.mkstemp(prefix=".bublik-backup-", dir=target.parent)
            os.close(fd)
        except OSError:
            raise StorageUnavailable("backup_failed") from None
        source = destination_db = None
        try:
            source = sqlite3.connect(self.database.path.as_uri() + "?mode=ro", uri=True)
            destination_db = sqlite3.connect(temporary_name)
            source.backup(destination_db)
            if (destination_db.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                    or destination_db.execute("PRAGMA foreign_key_check").fetchall()
                    or destination_db.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID):
                raise StorageUnavailable("backup_verification_failed")
            destination_db.close()
            destination_db = None
            with open(temporary_name, "rb") as backup_file:
                os.fsync(backup_file.fileno())
            # Atomic publication with no replacement, even after a destination race.
            os.link(temporary_name, target)
        except (sqlite3.Error, OSError):
            raise StorageUnavailable("backup_failed") from None
        finally:
            if destination_db is not None:
                destination_db.close()
            if source is not None:
                source.close()
            Path(temporary_name).unlink(missing_ok=True)
        return {"path": str(target), "integrity": "ok", "schema_version": self.database.status()["schema_version"]}
