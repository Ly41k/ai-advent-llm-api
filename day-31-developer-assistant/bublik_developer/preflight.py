"""Read-only checks for known Day 30 processes, launchd registration and ports.

This proves observed service inactivity only; it is not an Ollama idle witness.
No process is stopped, no private database is opened, no model request is sent.
"""
import errno
import os
from pathlib import Path
import platform
import re
import socket

from .errors import DeveloperError, ErrorCode
from .process import executable, run_bounded

API_LABEL = "local.bublik.private-ai.api"


class ProbeFailure(DeveloperError):
    """Fixed reason labels and numeric exit codes; no process args or stderr."""
    def __init__(self, reason, *, returncode=None):
        super().__init__(ErrorCode.ISOLATION_UNVERIFIED)
        self.diagnostic = {"reason": reason}
        if returncode is not None:
            self.diagnostic["returncode"] = returncode


class DoctorFailure(DeveloperError):
    def __init__(self, code, checks):
        super().__init__(code)
        self.checks = checks


def supported_launcher(program):
    return program.startswith("python") or program in {"uvicorn", "gunicorn", "bublik-service"}


def day30_process(command, program=None):
    if not isinstance(command, str):
        raise DeveloperError(ErrorCode.ISOLATION_UNVERIFIED)
    first = command.split(maxsplit=1)[0] if command.strip() else ""
    program = program or Path(first).name.casefold()
    if not supported_launcher(program):
        return False
    # ps output is a display string, not shell source: quotes need not balance.
    # Executable identity comes separately from comm in the actual OS probe.
    tokens = [value.strip("\"'") for value in command.split()]
    if not tokens:
        return False
    for index, value in enumerate(tokens[1:], 1):
        if value == "-m" and index + 1 < len(tokens) and tokens[index + 1].startswith("bublik_service"):
            return True
        if value.startswith("bublik_service.") or value == "bublik_service":
            return True
        if "day-30-private-ai-service/" in value or "/bublik_service/" in value:
            return True
    return program == "bublik-service"


def process_check():
    binary = executable("ps")
    code, output, _ = run_bounded([binary, "-axo", "pid=,comm="], timeout=3, limit=2 * 1024 * 1024)
    if code:
        raise ProbeFailure("process_table_unavailable", returncode=code)
    active = 0
    for line in output.decode("utf-8", "replace").splitlines():
        if not line.strip():
            continue
        values = line.strip().split(maxsplit=1)
        if not values or not values[0].isdecimal() or len(values) != 2:
            raise ProbeFailure("process_table_malformed")
        pid = int(values[0])
        program = Path(values[1]).name.casefold()
        if pid == os.getpid() or not supported_launcher(program):
            continue
        code, command, stderr = run_bounded([binary, "-p", str(pid), "-o", "command="], timeout=3, limit=262144)
        if code == 1 and not command.strip() and not stderr.strip():
            continue  # Process disappeared between the two observations.
        if code or not command.strip():
            raise ProbeFailure("process_arguments_unavailable", returncode=code)
        if day30_process(command.decode("utf-8", "replace"), program):
            active += 1
    return active


def launchd_check():
    if platform.system() != "Darwin":
        return {"applicable": False, "loaded": False, "disabled": None}
    binary = executable("launchctl")
    domain = "gui/" + str(os.getuid())
    code, _, stderr = run_bounded([binary, "print", domain + "/" + API_LABEL], timeout=3)
    if code == 0:
        return {"applicable": True, "loaded": True, "disabled": None}
    # Fail closed for permission, domain or unsupported-command failures.
    if code != 113 or not re.search(r"Could not find service", stderr.decode("utf-8", "replace"), re.I):
        raise ProbeFailure("launchd_print_unrecognized", returncode=code)
    plist_exists = (Path.home() / "Library/LaunchAgents" / (API_LABEL + ".plist")).exists()
    disabled = None
    if plist_exists:
        code, output, _ = run_bounded([binary, "print-disabled", domain], timeout=3)
        if code:
            raise ProbeFailure("launchd_disabled_query_unavailable", returncode=code)
        states = re.findall(r'^\s*"' + re.escape(API_LABEL) + r'"\s*=>\s*(true|false|disabled|enabled)\s*$',
                            output.decode("utf-8", "replace"), re.MULTILINE)
        if len(states) != 1:
            raise ProbeFailure("launchd_disabled_state_unknown")
        disabled = states[0] in {"true", "disabled"}
        if not disabled:
            raise ProbeFailure("launchd_autostart_not_disabled")
    return {"applicable": True, "loaded": False, "disabled": disabled}


def port_check(port):
    occupied = False
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        with socket.socket(family, socket.SOCK_STREAM) as stream:
            stream.settimeout(.4)
            try:
                stream.connect((host, port))
                occupied = True
            except ConnectionRefusedError:
                pass
            except OSError as error:
                if family == socket.AF_INET6 and error.errno in {errno.EAFNOSUPPORT, errno.EADDRNOTAVAIL, errno.ENETUNREACH}:
                    continue
                raise DeveloperError(ErrorCode.ISOLATION_UNVERIFIED) from None
    return occupied


def check_day30_off(additional_ports=()):
    ports = {8000}
    for value in additional_ports:
        if type(value) is not int or not 1024 <= value <= 65535:
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        ports.add(value)
    checks, unverified, active = {}, False, False
    processes, job, listening = None, None, []
    def probe(name, function, is_active):
        nonlocal unverified, active
        try:
            value = function()
            detected = is_active(value)
            checks[name] = {"status": "active" if detected else "passed", "observation": value}
            active = active or detected
            return value
        except DeveloperError as error:
            unverified = True
            checks[name] = {"status": "unverified", "error": error.to_dict(),
                            "diagnostic": getattr(error, "diagnostic", {"reason": "probe_unavailable"})}
            return None
    processes = probe("processes", process_check, lambda value: value > 0)
    job = probe("launchd", launchd_check, lambda value: value["loaded"])
    for port in sorted(ports):
        occupied = probe("loopback_port_" + str(port), lambda port=port: port_check(port), bool)
        if occupied:
            listening.append(port)
    if active or unverified:
        raise DoctorFailure(ErrorCode.SERVICE_ACTIVE if active else ErrorCode.ISOLATION_UNVERIFIED, checks)
    return {"day30_off": True, "matching_processes": processes, "launchd": job,
            "checked_loopback_ports": sorted(ports), "listening_ports": listening,
            "ollama_idle_verified": False, "inference_performed": False,
            "scope": "known_day30_launchers_launchd_and_configured_ports", "probes": checks}
