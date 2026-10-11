"""Versioned migrations and per-operation SQLite connections.

    No executescript inside an outer transaction: it may implicitly commit.
"""
from contextlib import closing, contextmanager
import hashlib
from importlib.resources import files
import os
from pathlib import Path
import sqlite3
import stat

from bublik_service.domain import SchemaError, StorageUnavailable

APPLICATION_ID = 0x42554230


def statements(script):
    pending = ""
    for line in script.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            yield pending
            pending = ""
    if pending.strip():
        raise SchemaError("incomplete_migration")


class Database:
    def __init__(self, path, *, timeout=5, migrations=None):
        self.path = Path(path).expanduser().absolute()
        if self.path.is_symlink():
            raise StorageUnavailable("database_symlink_forbidden")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        info = self.path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise StorageUnavailable("database_must_be_private")
        self.identity = info.st_dev, info.st_ino
        self.timeout = timeout
        self.migrations = migrations or files(__package__).joinpath("migrations")
        self.migrate()

    def check_identity(self):
        try:
            info = self.path.stat()
        except OSError:
            raise StorageUnavailable("database_file_changed") from None
        if self.path.is_symlink() or (info.st_dev, info.st_ino) != self.identity:
            raise StorageUnavailable("database_file_changed")

    @contextmanager
    def connect(self, *, write=False):
        self.check_identity()
        db = None
        try:
            # URI mode=rw prevents a deleted database from being silently recreated.
            db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True,
                                 timeout=self.timeout, isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA synchronous=FULL")
            self.check_identity()
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except sqlite3.Error:
            if db is not None:
                db.rollback()
            raise StorageUnavailable() from None
        except BaseException:
            if db is not None:
                db.rollback()
            raise
        finally:
            if db is not None:
                db.close()

    def migrate(self):
        candidates = sorted(self.migrations.iterdir(), key=lambda p: p.name)
        migrations = [(p.name, p.read_bytes()) for p in candidates if p.name.endswith(".sql")]
        if not migrations or any(not name.startswith(f"{i:03d}_") for i, (name, _) in enumerate(migrations, 1)):
            raise SchemaError("invalid_migration_sequence")
        # Inspect ownership before changing a foreign database's journal mode.
        with self.connect(write=True) as db:
            app_id = db.execute("PRAGMA application_id").fetchone()[0]
            names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if app_id not in (0, APPLICATION_ID) or (app_id == 0 and names):
                raise SchemaError("foreign_database")
            if app_id == APPLICATION_ID and "schema_migrations" not in names:
                raise SchemaError("missing_migration_ledger")
            db.execute("CREATE TABLE IF NOT EXISTS schema_migrations ("
                       "version INTEGER PRIMARY KEY, name TEXT NOT NULL, sha256 TEXT NOT NULL)")
            ledger = list(db.execute("SELECT * FROM schema_migrations ORDER BY version"))
            if len(ledger) > len(migrations):
                raise SchemaError("newer_database_schema")
            if app_id == APPLICATION_ID and db.execute("PRAGMA user_version").fetchone()[0] != len(ledger):
                raise SchemaError("schema_version_mismatch")
            for i, row in enumerate(ledger, 1):
                name, raw = migrations[i - 1]
                if (row["version"] != i or row["name"] != name
                        or row["sha256"] != hashlib.sha256(raw).hexdigest()):
                    raise SchemaError("migration_checksum_mismatch")
            for version, (name, raw) in enumerate(migrations, 1):
                if version <= len(ledger):
                    continue
                for statement in statements(raw.decode("utf-8")):
                    db.execute(statement)
                db.execute("INSERT INTO schema_migrations VALUES (?,?,?)",
                           (version, name, hashlib.sha256(raw).hexdigest()))
            db.execute(f"PRAGMA application_id={APPLICATION_ID}")
            db.execute(f"PRAGMA user_version={len(migrations)}")
        try:
            with closing(sqlite3.connect(self.path, timeout=self.timeout, isolation_level=None)) as db:
                if db.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() != "wal":
                    raise StorageUnavailable("wal_unavailable")
        except sqlite3.Error:
            raise StorageUnavailable("wal_unavailable") from None

    def status(self):
        with self.connect() as db:
            return {"schema_version": db.execute("PRAGMA user_version").fetchone()[0],
                    "journal_mode": db.execute("PRAGMA journal_mode").fetchone()[0],
                    "foreign_keys": db.execute("PRAGMA foreign_keys").fetchone()[0] == 1,
                    "synchronous": db.execute("PRAGMA synchronous").fetchone()[0],
                    "integrity": db.execute("PRAGMA integrity_check").fetchone()[0],
                    "foreign_key_violations": len(db.execute("PRAGMA foreign_key_check").fetchall())}
