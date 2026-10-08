"""Atomic, append-only observations with strict, portable reuse identities."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3
from datetime import datetime, timezone


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def owned_cache(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(path.suffix + '.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another Day 29 run owns this cache. Wait for it to finish.') from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class Cache:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, body TEXT NOT NULL, sha TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY, job_key TEXT NOT NULL, trial INTEGER NOT NULL,
                body TEXT NOT NULL, sha TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS observation_job ON observations(job_key, trial);
        ''')
        if self.db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Cache integrity check failed; restore a backup.')

    def close(self):
        self.db.close()

    def get(self, key):
        row = self.db.execute('SELECT body, sha FROM metadata WHERE key=?', (key,)).fetchone()
        if row is None:
            return None
        if hashlib.sha256(row['body'].encode()).hexdigest() != row['sha']:
            raise ValueError('Cached metadata checksum mismatch.')
        return json.loads(row['body'])

    def put(self, key, value):
        body = canonical(value)
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO metadata VALUES (?, ?, ?)',
                            (key, body, hashlib.sha256(body.encode()).hexdigest()))

    def record(self, envelope):
        if envelope['job_key'] != digest(envelope['identity']):
            raise ValueError('Observation identity mismatch.')
        body = canonical(envelope)
        with self.db:
            self.db.execute('INSERT INTO observations(job_key, trial, body, sha, created_at) VALUES (?, ?, ?, ?, ?)',
                            (envelope['job_key'], envelope['trial'], body,
                             hashlib.sha256(body.encode()).hexdigest(), now()))

    def history(self, key, trial):
        rows = self.db.execute('SELECT body, sha FROM observations WHERE job_key=? AND trial=? ORDER BY id DESC',
                               (key, trial)).fetchall()
        result = []
        for row in rows:
            if hashlib.sha256(row['body'].encode()).hexdigest() != row['sha']:
                raise ValueError('Observation checksum mismatch.')
            result.append(json.loads(row['body']))
        return result

