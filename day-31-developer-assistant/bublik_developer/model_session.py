"""Cooperative single-host model lease, fresh Ollama epoch and uncertain gate.

Adapted from Day 30 engine_epoch: API /ps is not an idle witness. An operator
restarts Ollama between prepare and confirm; no automatic shutdown or restart.
"""
from contextlib import contextmanager, ExitStack
from hashlib import sha256
import json
import os
from pathlib import Path
import re

from .errors import DeveloperError, ErrorCode
from .preflight import check_day30_off
from .process import executable, run_bounded
from .rag.state import ProjectState, default_state, private


def engine_epoch():
    def command(args, limit=65536):
        code, raw, _ = run_bounded(args, timeout=3, limit=limit)
        if code:
            raise DeveloperError(ErrorCode.MODEL_SESSION_REQUIRED)
        return raw.decode("utf-8", "replace").strip()
    raw = command([executable("lsof"), "-nP", "+c", "0", "-a", "-iTCP:11434", "-sTCP:LISTEN", "-Fpcn"])
    pids, commands, names = set(), set(), []
    for line in raw.splitlines():
        if line.startswith("p"):
            pids.add(line[1:])
        elif line.startswith("c"):
            commands.add(line[1:])
        elif line.startswith("n"):
            names.append(line[1:])
    if len(pids) != 1 or commands != {"ollama"} or not names or any(name not in {"127.0.0.1:11434", "[::1]:11434"} for name in names):
        raise DeveloperError(ErrorCode.MODEL_SESSION_REQUIRED)
    pid = next(iter(pids))
    if not pid.isdecimal():
        raise DeveloperError(ErrorCode.MODEL_SESSION_REQUIRED)
    binary = executable("ps")
    owner = command([binary, "-p", pid, "-o", "uid="])
    started = command([binary, "-p", pid, "-o", "lstart="])
    if owner != str(os.getuid()) or not started:
        raise DeveloperError(ErrorCode.MODEL_SESSION_REQUIRED)
    topology, runners = {}, set()
    for line in command([binary, "-axo", "pid=,ppid=,comm="], limit=2 * 1024 * 1024).splitlines():
        values = line.split(maxsplit=2)
        if len(values) != 3 or not values[0].isdecimal() or not values[1].isdecimal():
            raise DeveloperError(ErrorCode.MODEL_SESSION_REQUIRED)
        child, parent, name = values
        topology[child] = parent
        if Path(name).name in {"ollama", "ollama_llama_server", "llama-server"}:
            runners.add(child)
    if pid not in topology:
        raise DeveloperError(ErrorCode.MODEL_SESSION_REQUIRED)
    for runner in runners - {pid}:
        ancestor, visited = runner, set()
        while ancestor != pid and ancestor in topology and ancestor not in visited:
            visited.add(ancestor)
            ancestor = topology[ancestor]
        if ancestor != pid:
            raise DeveloperError(ErrorCode.MODEL_SESSION_REQUIRED)
    return sha256(f"{pid}|{owner}|{started}".encode()).hexdigest()


class ModelSession:
    def __init__(self, workspace, *, state_path=None, witness=engine_epoch):
        self.state = ProjectState(workspace, state_path or default_state("model-session"))
        self.witness = witness
        self.file = self.state.path / "SESSION.json"

    @contextmanager
    def _lock(self):
        with ExitStack() as stack:
            try:
                stack.enter_context(self.state.build_lock())
            except DeveloperError as error:
                if error.code == ErrorCode.INDEX_LOCKED:
                    raise DeveloperError(ErrorCode.MODEL_SESSION_BUSY) from None
                raise
            yield

    def _read(self):
        if not self.file.exists() and not self.file.is_symlink():
            raise DeveloperError(ErrorCode.MODEL_SESSION_REQUIRED)
        private(self.file)
        try:
            fd = os.open(self.file, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                raw = stream.read(4097)
            value = json.loads(raw)
            if (len(raw) > 4096 or not isinstance(value, dict) or set(value) != {"state", "epoch"}
                    or value["state"] not in {"prepared", "confirmed", "uncertain"}
                    or not isinstance(value["epoch"], str) or not re.fullmatch(r"[a-f0-9]{64}", value["epoch"])):
                raise ValueError
            return value
        except (OSError, ValueError, TypeError, RecursionError):
            raise DeveloperError(ErrorCode.MODEL_SESSION_REQUIRED) from None

    def _write(self, state, epoch):
        # Reuse atomic, fsynced private JSON publication without a second lock.
        from .contracts import canonical
        import tempfile
        if self.file.exists() or self.file.is_symlink():
            private(self.file)
        fd, name = tempfile.mkstemp(prefix=".session-", dir=self.state.path)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(canonical({"state": state, "epoch": epoch}))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.file)
            directory = os.open(self.state.path, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)

    def prepare(self):
        with self._lock():
            check_day30_off()
            epoch = self.witness()
            self._write("prepared", epoch)
            return {"status": "prepared", "action": "Restart Ollama, then run models confirm", "inference_performed": False}

    def status(self):
        """Read-only gate inspection; /ps and model requests are not used."""
        with self._lock():
            check_day30_off()
            try:
                value = self._read()
            except DeveloperError as error:
                if error.code != ErrorCode.MODEL_SESSION_REQUIRED:
                    raise
                return {"status": "not_confirmed", "gate_open": False,
                        "next_action": "models prepare; operator restarts Ollama; models confirm",
                        "inference_performed": False, "session_modified": False}
            epoch = self.witness()
            same = epoch == value["epoch"]
            return {"status": value["state"] if same else "epoch_changed", "stored_state": value["state"],
                    "gate_open": same and value["state"] == "confirmed", "epoch_matches": same,
                    "next_action": ("none" if same and value["state"] == "confirmed" else "models confirm" if not same
                                    else "operator restarts Ollama; models confirm"),
                    "inference_performed": False, "session_modified": False}

    def confirm(self):
        with self._lock():
            check_day30_off()
            value = self._read()
            epoch = self.witness()
            if value["state"] == "confirmed" and epoch == value["epoch"]:
                return {"status": "confirmed", "fresh_epoch": True, "inference_performed": False}
            if epoch == value["epoch"]:
                raise DeveloperError(ErrorCode.MODEL_SESSION_REQUIRED)
            self._write("confirmed", epoch)
            return {"status": "confirmed", "fresh_epoch": True, "scope": "day31_cooperative_exclusive_session", "inference_performed": False}

    @contextmanager
    def lease(self):
        with self._lock():
            check_day30_off()
            value = self._read()
            if value["state"] != "confirmed":
                raise DeveloperError(ErrorCode.MODEL_SESSION_REQUIRED)
            if self.witness() != value["epoch"]:
                raise DeveloperError(ErrorCode.MODEL_EPOCH_CHANGED)
            lease = ModelLease(self, value["epoch"])
            try:
                yield lease
            finally:
                lease.active = False


class ModelLease:
    def __init__(self, session, epoch):
        self.session, self.epoch, self.active = session, epoch, True

    def validate(self):
        check_day30_off()
        if not self.active or self.session._read()["state"] != "confirmed":
            raise DeveloperError(ErrorCode.MODEL_SESSION_REQUIRED)
        if self.session.witness() != self.epoch:
            raise DeveloperError(ErrorCode.MODEL_EPOCH_CHANGED)

    def uncertain(self):
        self.active = False
        self.session._write("uncertain", self.epoch)

    def begin(self):
        self.validate()
        # Persist before dispatch: an OS crash cannot leave a reusable idle claim.
        self.session._write("uncertain", self.epoch)

    def finish(self):
        check_day30_off()
        value = self.session._read()
        if not self.active or value != {"state": "uncertain", "epoch": self.epoch}:
            raise DeveloperError(ErrorCode.MODEL_SESSION_REQUIRED)
        if self.session.witness() != self.epoch:
            raise DeveloperError(ErrorCode.MODEL_EPOCH_CHANGED)
        self.session._write("confirmed", self.epoch)
