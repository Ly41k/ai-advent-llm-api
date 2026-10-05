"""Atomic JSON reports that cannot replace SQLite storage or its sidecars."""
import json
import os
from pathlib import Path
import tempfile


def validate_json_output(path, protected_paths=()):
    path = Path(path)
    target = path.resolve()
    for database in protected_paths:
        database = Path(database)
        for base in (database, database.resolve()):
            for suffix in ("", "-wal", "-shm", "-journal"):
                protected = Path(str(base) + suffix)
                if target == protected.resolve() or (
                        path.exists() and protected.exists() and path.samefile(protected)):
                    raise ValueError("JSON output cannot replace a database or its SQLite sidecars")
    if path.is_file():
        with path.open("rb") as existing:
            if existing.read(16) == b"SQLite format 3\x00":
                raise ValueError("JSON output cannot replace an existing SQLite database")
    return path


def write_json(path, payload, protected_paths=()):
    path = validate_json_output(path, protected_paths)
    # Serialize before touching the old report. A failed write must leave it intact.
    text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        validate_json_output(path, protected_paths)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
