"""Own a finite subprocess and bound both pipes while they are being read."""
import os
from pathlib import Path
import selectors
import shutil
import subprocess
from time import monotonic

from .errors import DeveloperError, ErrorCode


def minimal_env():
    return {"PATH": os.defpath + ":/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin", "LC_ALL": "C", "LANG": "C",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat"}


def executable(name):
    path = shutil.which(name, path=minimal_env()["PATH"])
    if not path or not Path(path).is_file():
        raise DeveloperError(ErrorCode.GIT_FAILED if name == "git" else ErrorCode.ISOLATION_UNVERIFIED)
    return str(Path(path).resolve())


def run_bounded(argv, *, cwd=None, timeout=10, limit=262144, env=None):
    """No shell, inherited stdin, redirects, infinite waits, or partial parsing."""
    try:
        process = subprocess.Popen(argv, cwd=cwd, env=env or minimal_env(), stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError:
        raise DeveloperError(ErrorCode.GIT_FAILED) from None
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = monotonic() + timeout
    try:
        with selectors.DefaultSelector() as selector:
            for stream, label in ((process.stdout, "stdout"), (process.stderr, "stderr")):
                selector.register(stream, selectors.EVENT_READ, label)
            while selector.get_map():
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise DeveloperError(ErrorCode.TIMEOUT)
                for key, _ in selector.select(min(remaining, .1)):
                    block = os.read(key.fd, 16384)
                    if not block:
                        selector.unregister(key.fileobj)
                        continue
                    buffers[key.data].extend(block)
                    if sum(map(len, buffers.values())) > limit:
                        raise DeveloperError(ErrorCode.OUTPUT_LIMIT)
            try:
                code = process.wait(timeout=max(.01, deadline - monotonic()))
            except subprocess.TimeoutExpired:
                raise DeveloperError(ErrorCode.TIMEOUT) from None
            return code, bytes(buffers["stdout"]), bytes(buffers["stderr"])
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
        process.stderr.close()
