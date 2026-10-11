"""Generate reviewable per-user launchd files. Never load jobs or change a DB."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import sys

from check_storage import ROOT
from bublik_service.http_api import HTTPSettings

API_LABEL = "local.bublik.private-ai.api"
CADDY_LABEL = "local.bublik.private-ai.caddy"
PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


def existing(value, *, directory=False, executable=False):
    # Preserve the venv Python symlink: resolving it would lose the venv.
    path = Path(value).expanduser().absolute()
    if any(ord(c) < 32 for c in str(path)):
        raise ValueError("invalid_path")
    if not (path.is_dir() if directory else path.is_file()):
        raise ValueError("path_missing")
    if executable and not os.access(path, os.X_OK):
        raise ValueError("not_executable")
    return path


def job(label, arguments, working, environment=None):
    return {"Label": label, "ProgramArguments": arguments,
            "WorkingDirectory": str(working), "RunAtLoad": True,
            "KeepAlive": True, "ThrottleInterval": 30, "ExitTimeOut": 60,
            "Umask": 0o077, "ProcessType": "Background",
            "EnvironmentVariables": {"PATH": PATH, "PYTHONUNBUFFERED": "1",
                                     "PYTHONNOUSERSITE": "1", **(environment or {})},
            # Failures are inspected with launchctl exit status + health/doctor.
            # No unbounded logs, private HTTP contents or raw traceback persistence.
            "StandardOutPath": "/dev/null", "StandardErrorPath": "/dev/null"}


def generate(python, repo, database, origins, output, *, caddy=None,
             caddy_config=None, caddy_data=None, caddy_state=None):
    python = existing(python, executable=True)
    repo = existing(repo, directory=True)
    database = existing(database)
    if not (repo / "bublik_service/__main__.py").is_file():
        raise ValueError("invalid_service_repository")
    HTTPSettings(database, origins=tuple(origins), trusted_loopback_proxy=True)
    args = [str(python), "-m", "bublik_service", "--db", str(database),
            "serve", "--port", "8000", "--trusted-loopback-proxy"]
    for origin in origins:
        args += ["--origin", origin]
    files = {API_LABEL + ".plist": job(API_LABEL, args, repo)}
    optional = (caddy, caddy_config, caddy_data, caddy_state)
    if any(optional):
        if not all(optional):
            raise ValueError("all_caddy_paths_required")
        binary = existing(caddy, executable=True)
        config = existing(caddy_config)
        data = existing(caddy_data, directory=True)
        state = existing(caddy_state, directory=True)
        files[CADDY_LABEL + ".plist"] = job(CADDY_LABEL,
            [str(binary), "run", "--config", str(config)], repo,
            {"XDG_DATA_HOME": str(data), "XDG_CONFIG_HOME": str(state)})
    output = Path(output).expanduser().absolute()
    output.mkdir(mode=0o700)  # NEW only, including symlink rejection.
    for name, value in files.items():
        with (output / name).open("xb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            plistlib.dump(value, stream, sort_keys=True)
    return {"status": "generated_not_installed", "directory": str(output),
            "labels": [v["Label"] for v in files.values()],
            "origins": list(origins), "database_moved": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--origin", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    for key in ("caddy", "caddy-config", "caddy-data", "caddy-state"):
        parser.add_argument("--" + key, type=Path)
    args = parser.parse_args()
    try:
        result = generate(args.python, args.repo, args.db, args.origin, args.output,
            caddy=args.caddy, caddy_config=args.caddy_config,
            caddy_data=args.caddy_data, caddy_state=args.caddy_state)
    except (OSError, ValueError):
        parser.error("Existing repo/interpreter/database, canonical HTTPS origins and NEW output directory required; Caddy paths must all exist")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
