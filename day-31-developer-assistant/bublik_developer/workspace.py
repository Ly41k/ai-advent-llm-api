"""Canonical Git root, path capabilities, symlink rejection and content policy."""
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import re
import stat

from .errors import DeveloperError, ErrorCode
from .process import executable, minimal_env, run_bounded

CONTENT_SUFFIXES = frozenset({".md", ".py", ".kt", ".kts", ".java", ".swift", ".sql", ".toml"})
DENIED_PARTS = frozenset({".git", ".venv", "venv", "node_modules", "__pycache__", "memory-index", "reports",
                          "secrets", "credentials", "private", "backups"})
DENIED_SUFFIXES = frozenset({".db", ".sqlite", ".sqlite3", ".pem", ".key", ".p12", ".pfx", ".jks"})


def relative_path(value):
    if (not isinstance(value, str) or not value or len(value.encode("utf-8", "surrogateescape")) > 4096
            or "\x00" in value or "\\" in value):
        raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or str(path) != value or value == ".":
        raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path")
    return path


def permitted_metadata(value):
    path = relative_path(value)
    for part in path.parts:
        name = part.casefold()
        if (name in DENIED_PARTS or name == ".env" or name.startswith(".env.")
                or name.startswith(("credentials.", "secret.", "secrets.", "token."))
                or Path(name).suffix in DENIED_SUFFIXES):
            return False
    return True


def permitted_content(value):
    return permitted_metadata(value) and PurePosixPath(value).suffix.casefold() in CONTENT_SUFFIXES


@dataclass(frozen=True)
class ProjectWorkspace:
    root: Path
    project_id: str
    identity: tuple[int, int]
    git_executable: str

    @classmethod
    def open(cls, root, project_id=None):
        path = Path(root).expanduser().resolve(strict=True)
        if not path.is_dir():
            raise DeveloperError(ErrorCode.INVALID_INPUT, "repository")
        binary = executable("git")
        code, output, _ = run_bounded([binary, "--no-pager", "-C", str(path), "rev-parse", "--show-toplevel"])
        if code:
            raise DeveloperError(ErrorCode.INVALID_INPUT, "repository")
        # Remove only Git's final newline, not characters in a legal directory name.
        observed = Path(os.fsdecode(output[:-1] if output.endswith(b"\n") else output)).resolve(strict=True)
        if observed != path:
            raise DeveloperError(ErrorCode.INVALID_INPUT, "repository")
        project_id = project_id or "local-" + sha256(os.fsencode(path)).hexdigest()[:20]
        if not isinstance(project_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", project_id):
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        info = path.stat()
        return cls(path, project_id, (info.st_dev, info.st_ino), binary)

    def check(self):
        try:
            info = self.root.stat()
        except OSError:
            raise DeveloperError(ErrorCode.WORKSPACE_CHANGED) from None
        if self.root.resolve() != self.root or (info.st_dev, info.st_ino) != self.identity:
            raise DeveloperError(ErrorCode.WORKSPACE_CHANGED)

    def path(self, value, *, content=False, missing=False):
        self.check()
        parts = relative_path(value).parts
        allowed = permitted_content(value) if content else permitted_metadata(value)
        if not allowed:
            raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path")
        current = self.root
        for index, part in enumerate(parts):
            current /= part
            try:
                info = current.lstat()
            except FileNotFoundError:
                if missing:
                    break
                raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path") from None
            if stat.S_ISLNK(info.st_mode) or (index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode)):
                raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path")
            if index == len(parts) - 1 and not stat.S_ISREG(info.st_mode):
                raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path")
        if not current.resolve().is_relative_to(self.root):
            raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path")
        return self.root.joinpath(*parts)

    def command(self, *args, limit=262144, allowed_codes=(0,)):
        self.check()
        prefix = [self.git_executable, "--no-pager", "--literal-pathspecs", "-C", str(self.root),
                  "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
                  "-c", "core.hooksPath=" + os.devnull, "-c", "diff.external=", "-c", "diff.submodule=short",
                  "-c", "core.attributesFile=" + os.devnull, "-c", "color.ui=false"]
        # status/diff may invoke clean/process filters even without textconv.
        # Read names only (never credential values), then override every driver.
        config_code, names, _ = run_bounded([*prefix, "config", "--null", "--name-only", "--get-regexp",
                                           r"^filter\..*\.(clean|smudge|process|required)$"], env=minimal_env())
        if config_code not in (0, 1):
            raise DeveloperError(ErrorCode.GIT_FAILED)
        drivers = set()
        for key in names.rstrip(b"\0").split(b"\0") if names else []:
            value = key.decode("utf-8", "surrogateescape")
            if not value.startswith("filter.") or value.rsplit(".", 1)[-1] not in {"clean", "smudge", "process", "required"}:
                raise DeveloperError(ErrorCode.GIT_FAILED)
            drivers.add(value.rsplit(".", 1)[0])
        for driver in sorted(drivers):
            for setting in ("clean=", "smudge=", "process=", "required=false"):
                prefix += ["-c", driver + "." + setting]
        code, output, _ = run_bounded([*prefix, *args], limit=limit, env=minimal_env())
        if code not in allowed_codes:
            raise DeveloperError(ErrorCode.GIT_FAILED)
        self.check()
        return code, output
