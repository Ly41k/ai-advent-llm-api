"""Private app state outside the analyzed repository; append-only index versions."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import platform
import stat
import tempfile

from ..contracts import canonical
from ..errors import DeveloperError, ErrorCode


def private(path, *, directory=False):
    try:
        info = path.lstat()
    except OSError:
        raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE) from None
    valid = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not valid or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path")


def default_state(project_id):
    base = (Path.home() / "Library/Application Support" if platform.system() == "Darwin"
            else Path.home() / ".local/share")
    return base / "BublikDeveloper" / project_id


class ProjectState:
    def __init__(self, workspace, path=None):
        self.path = (Path(path).expanduser().absolute() if path is not None else default_state(workspace.project_id))
        if self.path.resolve().is_relative_to(workspace.root):
            raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path")
        for parent in (self.path, *self.path.parents):
            if parent.is_symlink():
                raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path")
        self.path.mkdir(mode=0o700, parents=True, exist_ok=True)
        private(self.path, directory=True)

    @contextmanager
    def build_lock(self):
        path = self.path / "build.lock"
        try:
            fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        except OSError:
            raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE) from None
        try:
            private(path)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise DeveloperError(ErrorCode.INDEX_LOCKED) from None
            yield
        finally:
            os.close(fd)

    def publish(self, value):
        path = self.path / "CURRENT.json"
        if path.exists() or path.is_symlink():
            private(path)
        temporary = None
        try:
            fd, name = tempfile.mkstemp(prefix=".current-", dir=self.path)
            temporary = Path(name)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(canonical(value))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            directory = os.open(self.path, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def current(self):
        path = self.path / "CURRENT.json"
        private(path)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                raw = stream.read(4097)
            if len(raw) > 4096:
                raise ValueError
            value = json.loads(raw)
            if (not isinstance(value, dict) or set(value) != {"file", "sha256", "index_version"}
                    or not isinstance(value["file"], str)
                    or value["file"] != "index-" + value["index_version"] + ".sqlite3"):
                raise ValueError
            import re
            if not re.fullmatch(r"[a-f0-9]{32}", value["index_version"]) or not re.fullmatch(r"[a-f0-9]{64}", value["sha256"]):
                raise ValueError
            file = self.path / value["file"]
            private(file)
            return file, value
        except (OSError, ValueError, TypeError, RecursionError):
            raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE) from None
