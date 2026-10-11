"""Private, verified history transport. No HTTP, inference or automatic replay.

Format v1 restores schema 2 idle snapshots into NEW database files only.
Archive hashes detect damage, not malicious replacement; archives are not encrypted.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bublik_service import __version__
from bublik_service.domain import ServiceError
from bublik_service.storage import ChatRepository
from bublik_service.storage.database import APPLICATION_ID, Database

FORMAT = "bublik-memory-archive-v1"
DATABASE = "snapshot.sqlite3"
MANIFEST = "manifest.json"
SIDECARS = ("-wal", "-shm", "-journal")
AUTH_TABLES = {"browser_sessions", "api_tokens"}
MAX_MANIFEST_BYTES = 128 * 1024


def fail(code):
    raise ServiceError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def safe_path(value):
    path = Path(value).expanduser().absolute()
    if path.is_symlink():
        fail("archive_symlink_forbidden")
    # Resolve parent aliases such as macOS /var -> /private/var.
    return path.parent.resolve() / path.name


def private(path, directory=False):
    info = path.lstat()
    valid = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not valid or info.st_uid != os.getuid() or info.st_mode & 0o077:
        fail("archive_must_be_private")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def schema_digest(db):
    rows = [tuple(r) for r in db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")]
    return hashlib.sha256(canonical(rows)).hexdigest()


@lru_cache(maxsize=1)
def expected_schema():
    # The packaged migrations are the only accepted schema, not a self-declared ledger.
    with tempfile.TemporaryDirectory(prefix="bublik-schema-") as folder:
        reference = Database(Path(folder) / "reference.sqlite3")
        with reference.connect() as db:
            return schema_digest(db), [tuple(r) for r in db.execute(
                "SELECT version,name,sha256 FROM schema_migrations ORDER BY version")]


def inspect_snapshot(path):
    """Stream canonical rows in deterministic order; never print personal fields."""
    private(path)
    if any(Path(str(path) + suffix).exists() for suffix in SIDECARS):
        fail("archive_snapshot_has_sidecars")
    expected, ledger = expected_schema()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
        db.execute("PRAGMA trusted_schema=OFF")
        if (db.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
                or db.execute("PRAGMA user_version").fetchone()[0] != len(ledger)
                or schema_digest(db) != expected):
            fail("archive_incompatible_schema")
        if list(db.execute("SELECT version,name,sha256 FROM schema_migrations ORDER BY version")) != ledger:
            fail("archive_incompatible_schema")
        if (db.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                or db.execute("PRAGMA foreign_key_check").fetchall()):
            fail("archive_integrity_failed")
        tables = {}
        for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            columns = [r[1] for r in db.execute("PRAGMA table_info(" + quote(name) + ")")]
            h = hashlib.sha256(canonical(columns) + b"\n")
            count = 0
            sql = "SELECT * FROM " + quote(name) + " ORDER BY " + ",".join(map(quote, columns))
            for row in db.execute(sql):
                h.update(canonical(row) + b"\n")
                count += 1
            tables[name] = {"rows": count, "sha256": h.hexdigest()}
        pending = {state: db.execute("SELECT count(*) FROM generations WHERE status=?", (state,)).fetchone()[0]
                   for state in ("queued", "running")}
        uncertain = db.execute("SELECT inference_uncertain FROM service_state WHERE id=1").fetchall()
        if len(uncertain) != 1 or uncertain[0][0] not in (0, 1):
            fail("archive_integrity_failed")
        return {"schema_version": len(ledger), "schema_sha256": expected,
                "tables": tables, "logical_sha256": hashlib.sha256(canonical(tables)).hexdigest(),
                **pending, "inference_recovery_required": bool(uncertain[0][0])}


def idle(state):
    return not (state["queued"] or state["running"] or state["inference_recovery_required"])


def create_archive(database, destination):
    source = safe_path(database)
    private(source)
    # Refuse old/future/foreign schemas BEFORE constructing a repository (which migrates).
    expected, ledger = expected_schema()
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("BEGIN")
        if (db.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
                or db.execute("PRAGMA user_version").fetchone()[0] != len(ledger)
                or schema_digest(db) != expected
                or list(db.execute("SELECT version,name,sha256 FROM schema_migrations ORDER BY version")) != ledger):
            fail("archive_incompatible_schema")
    output = safe_path(destination)
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Exclusive directory creation: a pre-existing archive is never replaced.
    try:
        output.mkdir(mode=0o700)
    except FileExistsError:
        fail("archive_destination_exists")
    try:
        snapshot = output / DATABASE
        ChatRepository(source).backup(snapshot)
        # Snapshot is a self-contained read-only transport file, not a live WAL DB.
        state = inspect_snapshot(snapshot)
        manifest = {"format": FORMAT, "created_at": datetime.now(timezone.utc).isoformat(),
                    "service_version": __version__, "database": {"name": DATABASE,
                    "bytes": snapshot.stat().st_size, "sha256": digest(snapshot)}, "state": state}
        # Manifest is the completion marker, published only after the snapshot is verified.
        fd = os.open(output / MANIFEST, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(manifest) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        sync_directory(output)
        sync_directory(output.parent)
    except BaseException:
        # This invocation owns the new directory; never remove a previous archive.
        shutil.rmtree(output)
        raise
    return {"status": "created", "archive": str(output), "restorable_now": idle(state),
            "state": state, "encrypted": False}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail("archive_manifest_invalid")
        result[key] = value
    return result


def verify_archive(archive):
    folder = safe_path(archive)
    private(folder, directory=True)
    if {p.name for p in folder.iterdir()} != {DATABASE, MANIFEST}:
        fail("archive_members_invalid")
    path = folder / MANIFEST
    private(path)
    with path.open("rb") as stream:
        data = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(data) > MAX_MANIFEST_BYTES:
        fail("archive_manifest_invalid")
    try:
        manifest = json.loads(data, object_pairs_hook=unique_object,
                              parse_constant=lambda _: fail("archive_manifest_invalid"))
        if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
            fail("archive_manifest_invalid")
        metadata = manifest["database"]
        snapshot = safe_path(folder / DATABASE)
        private(snapshot)
        if (metadata["name"] != DATABASE or type(metadata["bytes"]) is not int
                or metadata["bytes"] != snapshot.stat().st_size
                or metadata["sha256"] != digest(snapshot)):
            fail("archive_checksum_mismatch")
        state = inspect_snapshot(snapshot)
        if canonical(state) != canonical(manifest["state"]):
            fail("archive_logical_mismatch")
    except (KeyError, TypeError, ValueError, UnicodeError):
        fail("archive_manifest_invalid")
    return {"status": "verified", "manifest": manifest,
            "restorable_now": idle(state), "encrypted": False}


def destination_free(path):
    if any(p.exists() or p.is_symlink() for p in [path, *(Path(str(path) + s) for s in SIDECARS)]):
        fail("restore_destination_exists_or_protected")


def restore_archive(archive, destination):
    verified = verify_archive(archive)
    manifest = verified["manifest"]
    if not verified["restorable_now"]:
        # First-stage transport never replays queued jobs or guesses another host's engine epoch.
        fail("restore_requires_idle_snapshot")
    target = safe_path(destination)
    destination_free(target)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    private(target.parent, directory=True)
    source = safe_path(Path(archive).expanduser() / DATABASE)
    fd, name = tempfile.mkstemp(prefix=".bublik-restore-", dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream, source.open("rb") as snapshot:
            shutil.copyfileobj(snapshot, stream, length=1024 * 1024)
            stream.flush()
            os.fsync(stream.fileno())
        if digest(temporary) != manifest["database"]["sha256"]:
            fail("archive_checksum_mismatch")
        if canonical(inspect_snapshot(temporary)) != canonical(manifest["state"]):
            fail("archive_logical_mismatch")
        with closing(sqlite3.connect(temporary.as_uri() + "?mode=rw", uri=True)) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA synchronous=FULL")
            # Keep IDs/passwords/receipts; old devices must log in again and renew tokens.
            db.execute("DELETE FROM browser_sessions")
            db.execute("UPDATE api_tokens SET revoked=1")
            db.commit()
            db.execute("PRAGMA journal_mode=DELETE")
        after = inspect_snapshot(temporary)
        preserved = {k: v for k, v in manifest["state"]["tables"].items() if k not in AUTH_TABLES}
        if preserved != {k: v for k, v in after["tables"].items() if k not in AUTH_TABLES}:
            fail("restore_history_mismatch")
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        destination_free(target)
        os.link(temporary, target)  # Atomic, refuses a destination creation race.
        sync_directory(target.parent)
        return {"status": "restored", "database": str(target),
                "history_tables_unchanged": True, "sessions_cleared": True,
                "api_tokens_revoked": True, "source_archive_unchanged": True,
                "state": after, "inference_replayed": False}
    finally:
        for suffix in ("", *SIDECARS):
            Path(str(temporary) + suffix).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--db", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True, help="NEW private archive directory")
    verify = commands.add_parser("verify")
    verify.add_argument("--archive", type=Path, required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--db", type=Path, required=True, help="NEW database in a private directory")
    args = parser.parse_args()
    try:
        if args.command == "create":
            result = create_archive(args.db, args.output)
        elif args.command == "verify":
            result = verify_archive(args.archive)
        else:
            result = restore_archive(args.archive, args.db)
    except ServiceError as error:
        result = {"status": "failed", "error": error.code}
    except (OSError, sqlite3.Error):
        result = {"status": "failed", "error": "archive_io_or_database_error"}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
