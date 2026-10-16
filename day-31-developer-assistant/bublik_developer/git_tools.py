"""Reviewed read-only Git operations; no hooks, write-tree or remote commands."""
from datetime import datetime, timezone
from hashlib import sha256
import os
import re

from .errors import DeveloperError, ErrorCode
from .policy import authorize
from .contracts import Role, canonical
from .workspace import permitted_content, permitted_metadata

MAX_ENTRIES = 2000
MAX_CONTENT_BYTES = 65536
SECRET = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|\bgh[pousr]_[A-Za-z0-9]{20,}\b|"
                    r"(?i:authorization\s*[:=]\s*[\"']?bearer\s+\S+)|"
                    r"(?i:(?:api[_-]?key|password|secret[_-]?key|access[_-]?token)\s*[\"']?\s*[:=]\s*[\"'][^\"'\n]{12,})")


def now():
    return datetime.now(timezone.utc).isoformat()


def decode(value):
    # Filenames may contain undecodable POSIX bytes. JSON escapes surrogate codes.
    return value.decode("utf-8", "surrogateescape")


def nul_records(output):
    if output and not output.endswith(b"\0"):
        raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
    return output[:-1].split(b"\0") if output else []


class GitTools:
    def __init__(self, workspace):
        self.workspace = workspace

    def invoke(self, name, arguments):
        try:
            authorize(Role.GIT, name, arguments)
            data = getattr(self, name)(**arguments)
            value = {"ok": True, "tool": name, "project_id": self.workspace.project_id,
                     "observed_at": now(), "data": data, "error": None}
            if len(canonical(value).encode()) > 262144:
                raise DeveloperError(ErrorCode.OUTPUT_LIMIT)
            return value
        except DeveloperError as error:
            return {"ok": False, "tool": name, "project_id": self.workspace.project_id,
                    "observed_at": now(), "data": None, "error": error.to_dict()}

    def git_current_branch(self):
        code, branch = self.workspace.command("symbolic-ref", "--quiet", "--short", "HEAD", allowed_codes=(0, 1))
        head_code, head = self.workspace.command("rev-parse", "--verify", "HEAD", allowed_codes=(0, 128))
        oid = head.strip().decode("ascii") if not head_code else None
        if oid is not None and not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", oid):
            raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
        return {"kind": "branch", "branch": decode(branch[:-1]) if code == 0 and branch.endswith(b"\n") else None,
                "head_oid": oid, "detached_head": code == 1, "unborn": head_code != 0}

    def _raw_status(self):
        return self.workspace.command("status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=all")[1]

    def _entries(self, raw):
        values, entries, withheld = nul_records(raw), [], 0
        offset = 0
        while offset < len(values):
            item = values[offset]
            offset += 1
            if len(item) < 4 or item[2:3] != b" ":
                raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
            code, path = item[:2].decode("ascii"), decode(item[3:])
            old = None
            if "R" in code or "C" in code:
                if offset >= len(values):
                    raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
                old = decode(values[offset])
                offset += 1
            try:
                if not permitted_metadata(path) or (old is not None and not permitted_metadata(old)):
                    withheld += 1
                    continue
                self.workspace.path(path, missing=True)
                if old is not None:
                    self.workspace.path(old, missing=True)
            except DeveloperError as error:
                if error.code != ErrorCode.PERMISSION_DENIED:
                    raise
                withheld += 1
                continue
            entries.append({"path": path, "original_path": old, "index_status": code[0], "worktree_status": code[1]})
        if len(entries) > MAX_ENTRIES:
            raise DeveloperError(ErrorCode.OUTPUT_LIMIT)
        return entries, withheld

    def _witness(self, paths=()):
        branch = self.git_current_branch()
        raw = self._raw_status()
        stage = self.workspace.command("ls-files", "--stage", "-z")[1]
        fingerprints = []
        for value in paths:
            path = self.workspace.path(value, content=True, missing=True)
            try:
                # Refuse final symlink, and validate parents again after reading.
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            except FileNotFoundError:
                fingerprints.append((value, None))
                continue
            except OSError:
                raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path") from None
            try:
                with os.fdopen(fd, "rb") as stream:
                    data = stream.read(MAX_CONTENT_BYTES + 1)
                if len(data) > MAX_CONTENT_BYTES:
                    raise DeveloperError(ErrorCode.OUTPUT_LIMIT)
                self.workspace.path(value, content=True)
                fingerprints.append((value, sha256(data).hexdigest()))
            except OSError:
                raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path") from None
        return sha256(canonical({"branch": branch, "status": sha256(raw).hexdigest(),
                                 "stage": sha256(stage).hexdigest(), "files": fingerprints}).encode()).hexdigest()

    def git_status(self):
        before = self._witness()
        entries, withheld = self._entries(self._raw_status())
        after = self._witness()
        if before != after:
            raise DeveloperError(ErrorCode.GIT_STATE_CHANGED)
        return {"kind": "status", "entries": entries, "withheld_count": withheld,
                "snapshot_digest": before, "consistency": "head_index_status"}

    def project_list_files(self):
        before = self._witness()
        raw = self.workspace.command("ls-files", "-z", "--cached", "--others", "--exclude-standard")[1]
        selected, withheld = set(), 0
        for record in nul_records(raw):
            value = decode(record)
            try:
                if not permitted_metadata(value):
                    raise DeveloperError(ErrorCode.PERMISSION_DENIED)
                self.workspace.path(value, missing=True)
            except DeveloperError as error:
                if error.code != ErrorCode.PERMISSION_DENIED:
                    raise
                withheld += 1
                continue
            selected.add(value)
        if len(selected) > MAX_ENTRIES:
            raise DeveloperError(ErrorCode.OUTPUT_LIMIT)
        if self._witness() != before:
            raise DeveloperError(ErrorCode.GIT_STATE_CHANGED)
        return {"kind": "files", "files": sorted(selected), "withheld_count": withheld,
                "snapshot_digest": before, "consistency": "head_index_status"}

    def git_diff(self, scope="unstaged", paths=None, include_content=False):
        paths = paths or []
        for value in paths:
            self.workspace.path(value, content=include_content, missing=True)
        entries, withheld = self._entries(self._raw_status())
        changed = [entry["path"] for entry in entries if
                   (entry["index_status"] not in {" ", "?"} if scope == "staged" else entry["worktree_status"] not in {" ", "?"})]
        selected = paths or changed
        if include_content:
            if any(not permitted_content(value) for value in selected):
                raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path")
            indexed = self.workspace.command("ls-files", "--stage", "-z", "--", *selected)[1]
            if any(row.startswith((b"120000 ", b"160000 ")) for row in nul_records(indexed)):
                raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path")
            witness_paths = selected
        else:
            witness_paths = ()
        before = self._witness(witness_paths)
        options = ["diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--ignore-submodules=all"]
        if scope == "staged":
            options.append("--cached")
        # Empty selection must not turn into an unrestricted Git diff.
        summary = self.workspace.command(*options, "--numstat", "-z", "--", *selected)[1] if selected else b""
        files = []
        for item in nul_records(summary):
            parts = item.split(b"\t", 2)
            if len(parts) != 3:
                raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
            added, deleted, filename = parts
            path = decode(filename)
            self.workspace.path(path, content=include_content, missing=True)
            binary = added == b"-" or deleted == b"-"
            files.append({"path": path, "added": None if binary else int(added),
                          "deleted": None if binary else int(deleted), "binary": binary})
        patch = None
        if include_content:
            if any(row["binary"] for row in files):
                raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path")
            raw = self.workspace.command(*options, "--unified=3", "--", *selected, limit=MAX_CONTENT_BYTES)[1]
            try:
                patch = raw.decode("utf-8")
            except UnicodeError:
                raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path") from None
            if SECRET.search(patch):
                raise DeveloperError(ErrorCode.PERMISSION_DENIED, "secret")
        after_summary = self.workspace.command(*options, "--numstat", "-z", "--", *selected)[1] if selected else b""
        if before != self._witness(witness_paths) or summary != after_summary:
            raise DeveloperError(ErrorCode.GIT_STATE_CHANGED)
        return {"kind": "diff", "scope": scope, "files": files, "patch": patch, "content_included": include_content,
                "withheld_count": withheld, "untracked_content_included": False, "snapshot_digest": before,
                "consistency": "head_index_status_selected_files" if include_content else "head_index_status_numstat"}
