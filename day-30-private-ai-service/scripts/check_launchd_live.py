"""Read-only Mac launchd + verified HTTPS/history checks across restart/reboot.

Never stops processes, loads jobs, retries inference, or records dialogue text.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import ssl
import subprocess
import sys
import time
import uuid

import httpx

from check_storage import manifest
from check_http_live import read_token, fingerprint
from configure_launchd import API_LABEL
from network_common import private_origin
from bublik_service.http_api import runtime_manifest


def command(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=5)
    if result.returncode or len(result.stdout) > 1024 * 1024:
        raise ValueError("os_observation_failed")
    return result.stdout


def launch_pid(output):
    state = re.search(r"^\s*state = (\w+)\s*$", output, re.M)
    pid = re.search(r"^\s*pid = (\d+)\s*$", output, re.M)
    if not state or state[1] != "running" or not pid or int(pid[1]) <= 0:
        raise ValueError("launch_agent_not_running")
    return int(pid[1])


def boot_fingerprint(output):
    # Hash the epoch fields, not locale/timezone-dependent human-readable date.
    value = re.search(r"sec\s*=\s*(\d+),\s*usec\s*=\s*(\d+)", output)
    if not value: raise ValueError("invalid_boot_witness")
    return fingerprint([int(value[1]), int(value[2])])


def baseline_checks(before, after, kind):
    outcomes = [("passed_baseline_same_source", before.get("format") == "bublik-stage7-launchd-live-v1"
        and before.get("status") == "passed" and before.get("source_sha256") == after["source_sha256"]),
        ("same_endpoint_chat_and_configuration", all(before.get(k) == after.get(k)
         for k in ("url", "chat_id", "plist_sha256"))),
        ("same_complete_saved_history", before.get("history_sha256") == after.get("history_sha256")
         and before.get("message_count") == after.get("message_count")),
        ("same_model_and_profile", before.get("model_identity") == after.get("model_identity")
         and before.get("profile") == after.get("profile"))]
    if kind == "restart":
        outcomes += [("new_api_pid_same_os_boot", before.get("api_pid") != after.get("api_pid")
                      and before.get("os_boot_sha256") == after.get("os_boot_sha256"))]
    elif kind == "reboot":
        outcomes += [("new_os_boot", before.get("os_boot_sha256") != after.get("os_boot_sha256"))]
    return outcomes


async def execute(args, report, token):
    def check(name, value):
        report["checks"].append({"name": name, "passed": bool(value)})
        if not value:
            raise ValueError("controlled_check_failed")
    plist_path = Path.home()/"Library/LaunchAgents"/(API_LABEL+".plist")
    raw = plist_path.read_bytes()
    info = plist_path.stat()
    value = plistlib.loads(raw)
    check("private_owned_launch_agent", not plist_path.is_symlink() and info.st_uid == os.getuid()
          and info.st_mode & 0o077 == 0)
    program = value["ProgramArguments"]
    check("expected_supervisor_configuration", value["Label"] == API_LABEL
        and value["KeepAlive"] is True and value["RunAtLoad"] is True
        and value["ExitTimeOut"] >= 60 and value["ThrottleInterval"] >= 30
        and program[1:4] == ["-m", "bublik_service", "--db"]
        and "--trusted-loopback-proxy" in program
        and "--port" in program and program[program.index("--port")+1] == "8000"
        and args.url in [program[i+1] for i,p in enumerate(program[:-1]) if p == "--origin"])
    report["plist_sha256"] = hashlib.sha256(raw).hexdigest()
    pid = launch_pid(command(["/bin/launchctl", "print", f"gui/{os.getuid()}/{API_LABEL}"]))
    report["api_pid"] = pid
    listeners = command(["/usr/sbin/lsof", "-nP", "+c", "0", "-a", "-iTCP:8000", "-sTCP:LISTEN", "-Fpn"])
    check("launchd_pid_owns_only_loopback_listener", set(re.findall(r"^p(\d+)$",listeners,re.M)) == {str(pid)}
          and set(re.findall(r"^n(.+)$",listeners,re.M)) == {"127.0.0.1:8000"})
    report["os_boot_sha256"] = boot_fingerprint(command(["/usr/sbin/sysctl","-n","kern.boottime"]))
    tls = ssl.create_default_context(cafile=str(args.ca_file)) if args.ca_file else ssl.create_default_context()
    async with httpx.AsyncClient(base_url=args.url, verify=tls, trust_env=False,
            follow_redirects=False, timeout=15, headers={"Authorization": "Bearer "+token}) as client:
        async def get(path):
            response = await client.get("/api/v1"+path)
            response.raise_for_status()
            return response.json()
        ready = await get("/health/ready")
        check("verified_https_ready_current_runtime", ready["status"] == "ready"
            and ready["runtime_source_unchanged"] and ready["runtime_source_sha256"] == runtime_manifest())
        check("idle_without_recovery_gate", ready["queued"] == ready["running"] == 0
              and not ready["inference_recovery_required"])
        report["model_identity"], report["profile"] = ready["model"]["identity"], ready["profile"]
        items, cursor = [], 0
        for _ in range(100):
            page = await get(f"/chats/{args.chat_id}/messages?limit=100&after_sequence={cursor}")
            items += page["items"]
            next_cursor = page["next_after_sequence"]
            if next_cursor is None:
                break
            if next_cursor <= cursor:
                raise ValueError("invalid_history_cursor")
            cursor = next_cursor
        else:
            raise ValueError("history_check_limit")
        check("nonempty_terminal_history", len(items) >= 2 and all(
              m["status"] == "accepted" if m["role"] == "user" else m["status"] in
              {"completed", "truncated", "failed", "interrupted"} for m in items))
        report["history_sha256"], report["message_count"] = fingerprint(items), len(items)
    if args.baseline:
        before = json.loads(args.baseline.read_bytes())
        for name, passed in baseline_checks(before, report, args.kind):
            check(name, passed)
        report["baseline_sha256"] = hashlib.sha256(args.baseline.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--network", choices=("lan", "tailnet"), required=True)
    parser.add_argument("--ca-file", type=Path)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--chat-id", required=True)
    parser.add_argument("--kind", choices=("initial", "restart", "reboot"), default="initial")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if platform.system() != "Darwin":
            raise ValueError()
        private_origin(args.url, args.network)
        if not re.fullmatch(r"[a-f0-9]{32}",args.chat_id):
            raise ValueError()
        if (args.kind != "initial") != bool(args.baseline) or (args.network == "lan" and not args.ca_file):
            raise ValueError()
        token = read_token(args.token_file.expanduser())
    except (ValueError, OSError, KeyError):
        parser.error("Mac, private HTTPS/token, valid chat ID required; restart/reboot require baseline; LAN requires CA")
    report = {"format": "bublik-stage7-launchd-live-v1", "run_id": uuid.uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(), "status": "failed", "checks": [],
        "url": args.url, "chat_id": args.chat_id, "kind": args.kind,
        "source_sha256": manifest(), "evidence": "Read-only launchd PID/listener/OS boot + verified HTTPS and full saved history hashes. No inference replay.",
        "not_run": ["independent phone/PWA installation observation", "active inference crash recovery", "CPU/RAM", "backup/restore"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        stream = args.output.open("x", encoding="utf-8")
    except OSError:
        parser.error("NEW writable report path required; earlier reports are preserved")
    with stream:
        start = time.perf_counter()
        try:
            asyncio.run(execute(args, report, token))
            report["source_unchanged"] = report["source_sha256"] == manifest()
            if report["source_unchanged"] and all(c["passed"] for c in report["checks"]):
                report["status"] = "passed"
        except (Exception, KeyboardInterrupt) as error:
            report["error_code"] = "launchd_check_failed"
            report["failure_type"] = type(error).__name__
        report["elapsed_seconds"] = time.perf_counter()-start
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"report": str(args.output), "status": report["status"]}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
