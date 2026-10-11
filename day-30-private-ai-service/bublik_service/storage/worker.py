"""Single-host POSIX worker lease and fenced generation transitions.

The lock is keyed by database inode, so hard-link/path aliases cannot create a
second worker. It is never unlinked while another process might retain its inode.
"""
from datetime import datetime, timedelta
import fcntl
import hashlib
import math
import os
from pathlib import Path
import stat
import tempfile
import threading
import uuid

from bublik_service.domain import Conflict, ERROR_CODES, InvalidInput, METRIC_KEYS, StorageUnavailable
from .repository import MAX_RESPONSE_BYTES, canonical
import json


def _lease(database):
    database.check_identity()
    root = Path(tempfile.gettempdir()) / f"bublik-private-ai-workers-{os.getuid()}"
    root.mkdir(mode=0o700, exist_ok=True)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise StorageUnavailable("worker_lock_directory_not_private")
    key = hashlib.sha256(repr(database.identity).encode()).hexdigest()
    fd = os.open(root / key, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise StorageUnavailable("worker_lock_file_not_private")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise Conflict("worker_already_running") from None
    except BaseException:
        os.close(fd)
        raise
    return fd


def metrics_value(metrics):
    if metrics is None:
        return {}
    if type(metrics) is not dict or set(metrics) - METRIC_KEYS:
        raise InvalidInput("invalid_generation_metrics")
    for key, value in metrics.items():
        if value is None:
            continue
        if (type(value) not in (int, float) or not math.isfinite(value) or value < 0
                or (key in {"input_tokens", "output_tokens"} and type(value) is not int)):
            raise InvalidInput("invalid_generation_metrics")
    return dict(metrics)


class WorkerSession:
    """Trusted internal capability; never expose it as an HTTP request dependency."""

    def __init__(self, repository):
        self.repository = repository
        self._mutex = threading.Lock()
        self._pid = os.getpid()
        self._fd = _lease(repository.database)
        self._token = uuid.uuid4().hex
        try:
            with repository.database.connect(write=True) as db:
                rows = db.execute("SELECT * FROM generations WHERE status='running'").fetchall()
                for row in rows:
                    repository._terminal(db, row, "interrupted", "process_interrupted", event="recovered")
                if rows:
                    db.execute("UPDATE service_state SET inference_uncertain=1 WHERE id=1")
                self.recovered_count = len(rows)
        except BaseException:
            self.close()
            raise

    def _check(self):
        if self._fd is None or self._pid != os.getpid():
            raise Conflict("worker_session_closed_or_forked")
        self.repository.database.check_identity()

    def close(self):
        with self._mutex:
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None

    def __enter__(self):
        self._check()
        return self

    def __exit__(self, *_):
        self.close()

    def require_queued_profile(self, profile):
        """Refuse a profile upgrade before claiming or rewriting old queued jobs."""
        expected = profile.to_dict()
        with self._mutex:
            self._check()
            with self.repository.database.connect() as db:
                rows = db.execute("SELECT DISTINCT profile_json FROM generations WHERE status='queued'").fetchall()
                if any(json.loads(row[0]) != expected for row in rows):
                    raise Conflict("queued_profile_mismatch")

    def confirm_inference_idle(self):
        """Stage 3 calls only after actual engine quiescence/restart is verified.

        Storage cannot independently prove that an upstream inference stopped.
        This operation is deliberately not an API endpoint or a user action.
        """
        with self._mutex:
            self._check()
            with self.repository.database.connect(write=True) as db:
                if db.execute("SELECT 1 FROM generations WHERE status='running'").fetchone():
                    raise Conflict("generation_still_running")
                db.execute("UPDATE service_state SET inference_uncertain=0 WHERE id=1")

    def claim_next(self):
        with self._mutex:
            self._check()
            with self.repository.database.connect(write=True) as db:
                if db.execute("SELECT inference_uncertain FROM service_state WHERE id=1").fetchone()[0]:
                    raise Conflict("inference_recovery_required")
                if db.execute("SELECT 1 FROM generations WHERE status='running'").fetchone():
                    return None
                row = db.execute("SELECT * FROM generations WHERE status='queued' ORDER BY queue_order LIMIT 1").fetchone()
                if row is None:
                    return None
                now = self.repository._now()
                db.execute("UPDATE generations SET status='running',worker_token=?,started_at=? WHERE id=?",
                           (self._token, now, row["id"]))
                db.execute("UPDATE messages SET status='running',updated_at=? WHERE id=?",
                           (now, row["assistant_message_id"]))
                db.execute("INSERT INTO chat_events(chat_id,generation_id,kind,created_at) VALUES (?,?,'claimed',?)",
                           (row["chat_id"], row["id"], now))
                row = db.execute("SELECT * FROM generations WHERE id=?", (row["id"],)).fetchone()
                return self.repository._public_generation(row)

    def _owned(self, db, generation):
        row = db.execute("SELECT * FROM generations WHERE id=? AND status='running' AND worker_token=?",
                         (generation, self._token)).fetchone()
        if row is None:
            raise Conflict("generation_ownership_lost")
        return row

    def checkpoint(self, generation, content):
        if not isinstance(content, str) or "\x00" in content:
            raise InvalidInput("invalid_answer")
        try:
            if len(content.encode("utf-8")) > MAX_RESPONSE_BYTES:
                raise InvalidInput("invalid_answer")
        except UnicodeError:
            raise InvalidInput("invalid_answer") from None
        with self._mutex:
            self._check()
            with self.repository.database.connect(write=True) as db:
                row = self._owned(db, generation)
                old = db.execute("SELECT content FROM messages WHERE id=?", (row["assistant_message_id"],)).fetchone()[0]
                if not content.startswith(old):
                    raise Conflict("answer_checkpoint_would_be_rewritten")
                db.execute("UPDATE messages SET content=?,updated_at=? WHERE id=?",
                           (content, self.repository._now(), row["assistant_message_id"]))

    def bind_engine_epoch(self, generation, epoch):
        """Commit dispatch provenance before any inference POST; prompt/profile stay immutable."""
        if not isinstance(epoch, str) or len(epoch) != 64 or any(c not in "0123456789abcdef" for c in epoch):
            raise InvalidInput("invalid_engine_epoch")
        with self._mutex:
            self._check()
            with self.repository.database.connect(write=True) as db:
                row = self._owned(db, generation)
                context = json.loads(row["context_json"])
                if context.get("dispatch_engine_epoch") not in (None, epoch):
                    raise Conflict("engine_epoch_already_bound")
                context["dispatch_engine_epoch"] = epoch
                db.execute("UPDATE generations SET context_json=? WHERE id=?", (canonical(context), generation))

    def finish(self, generation, *, status="completed", content=None, error_code=None, metrics=None, uncertain=None):
        if uncertain is not None and type(uncertain) is not bool:
            raise InvalidInput("invalid_inference_state")
        if status not in {"completed", "truncated", "failed", "interrupted"}:
            raise InvalidInput("invalid_terminal_status")
        if ((status in {"failed", "interrupted"} and error_code not in ERROR_CODES)
                or (status in {"completed", "truncated"} and error_code is not None)):
            raise InvalidInput("invalid_error_code")
        measured = metrics_value(metrics)
        with self._mutex:
            self._check()
            with self.repository.database.connect(write=True) as db:
                row = self._owned(db, generation)
                unknown = bool(uncertain) or (uncertain is None and (status == "interrupted" or error_code in {"model_timeout", "inference_state_unknown"}))
                if unknown:
                    context = json.loads(row["context_json"])
                    context["inference_uncertain"] = True
                    db.execute("UPDATE generations SET context_json=? WHERE id=?", (canonical(context), generation))
                self.repository._terminal(db, row, status, error_code, content=content, metrics=measured)
                if unknown:
                    db.execute("UPDATE service_state SET inference_uncertain=1 WHERE id=1")

    def expire_queued(self, max_age_seconds):
        if type(max_age_seconds) not in (int, float) or not math.isfinite(max_age_seconds) or max_age_seconds <= 0:
            raise InvalidInput("invalid_queue_deadline")
        with self._mutex:
            self._check()
            cutoff = (datetime.fromisoformat(self.repository._now()) - timedelta(seconds=max_age_seconds)).isoformat(timespec="microseconds")
            with self.repository.database.connect(write=True) as db:
                rows = db.execute("SELECT * FROM generations WHERE status='queued' AND created_at<=? ORDER BY queue_order",
                                  (cutoff,)).fetchall()
                for row in rows:
                    self.repository._terminal(db, row, "failed", "queue_expired", event="expired")
                return len(rows)
