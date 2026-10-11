"""Local OS witness of a loopback-only Ollama listener (macOS/Linux with lsof)."""
import hashlib
import os
import subprocess

from bublik_service.domain import ModelUnavailable


PROCESS_TABLE_COMMAND = ("ps", "-axo", "pid=,ppid=,comm=")
MAX_PROCESS_TABLE_CHARACTERS = 1024 * 1024


def _command(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=3, check=False,
                                env={**os.environ, "LC_ALL": "C", "TZ": "UTC"})
    except (OSError, subprocess.TimeoutExpired):
        raise ModelUnavailable("engine_process_unverified") from None
    # A normal macOS process table can exceed 64 KiB (688 processes produced
    # 66,366 characters on the target Mac). Keep a separate finite allowance
    # for this exact command, and inspect the entire table: truncating it could
    # hide an orphan runner. Other commands retain their original 64 KiB limit.
    limit = MAX_PROCESS_TABLE_CHARACTERS if tuple(args) == PROCESS_TABLE_COMMAND else 65536
    if result.returncode or len(result.stdout) > limit:
        raise ModelUnavailable("engine_process_unverified")
    return result.stdout.strip()


def engine_epoch(port):
    """PID + process start time + uid; /api/ps is deliberately not an idle witness.

    Also refuse wildcard/non-loopback listeners. Run under the same OS user as
    Ollama; no privilege escalation. This is not a remote network accessibility test.
    """
    raw = _command(["lsof", "-nP", "+c", "0", "-a", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fpcn"])
    pids, commands, names = set(), set(), []
    for line in raw.splitlines():
        if line.startswith("p"):
            pids.add(line[1:])
        elif line.startswith("c"):
            commands.add(line[1:])
        elif line.startswith("n"):
            names.append(line[1:])
    if (len(pids) != 1 or commands != {"ollama"} or not names
            or any(n not in {f"127.0.0.1:{port}", f"[::1]:{port}"} for n in names)):
        raise ModelUnavailable("ollama_listener_not_isolated")
    pid = next(iter(pids))
    if not pid.isdecimal():
        raise ModelUnavailable("engine_process_unverified")
    uid = _command(["ps", "-p", pid, "-o", "uid="])
    started = _command(["ps", "-p", pid, "-o", "lstart="])
    if uid != str(os.getuid()) or not started:
        raise ModelUnavailable("engine_process_unverified")
    # Restarting the parent alone is not sufficient: an orphan runner may survive.
    # Inspect executable names/parents only (never process argv with private prompts).
    topology = {}
    runners = set()
    for line in _command(list(PROCESS_TABLE_COMMAND)).splitlines():
        columns = line.split(maxsplit=2)
        if len(columns) != 3 or not columns[0].isdecimal() or not columns[1].isdecimal():
            raise ModelUnavailable("engine_process_unverified")
        child, parent, command = columns
        topology[child] = parent
        if os.path.basename(command) in {"ollama", "ollama_llama_server", "llama-server"}:
            runners.add(child)
    if pid not in topology:
        raise ModelUnavailable("engine_process_unverified")
    for runner in runners - {pid}:
        ancestor, visited = runner, set()
        while ancestor != pid and ancestor in topology and ancestor not in visited:
            visited.add(ancestor)
            ancestor = topology[ancestor]
        if ancestor != pid:
            raise ModelUnavailable("orphan_or_other_ollama_process")
    return hashlib.sha256(f"{pid}|{uid}|{started}".encode()).hexdigest()
