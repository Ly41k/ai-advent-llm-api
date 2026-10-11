"""Run storage and synthetic inference tests; never claim real Qwen/network proof."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def manifest():
    paths = {ROOT / "pyproject.toml"}
    if (ROOT / "requirements.lock").exists():
        paths.add(ROOT / "requirements.lock")
    if (ROOT / "requirements.browser.lock").exists():
        paths.add(ROOT / "requirements.browser.lock")
    for directory in ("bublik_service", "tests", "scripts"):
        paths.update(p for p in (ROOT / directory).rglob("*") if p.suffix in {".py", ".sql", ".html", ".css", ".js", ".png", ".webmanifest"})
    paths.update(p for p in (ROOT / "deploy").rglob("*") if p.is_file())
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def startTest(self, test):
        self.started = time.perf_counter()
        self.outcome = "passed"
        super().startTest(test)

    def addFailure(self, test, err):
        self.outcome = "failed"
        super().addFailure(test, err)

    def addError(self, test, err):
        self.outcome = "error"
        super().addError(test, err)

    def addSkip(self, test, reason):
        self.outcome = "skipped"
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        self.outcome = "expected_failure"
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self.outcome = "unexpected_success"
        super().addUnexpectedSuccess(test)

    def addSubTest(self, test, subtest, err):
        if err is not None:
            self.outcome = "failed" if issubclass(err[0], test.failureException) else "error"
        super().addSubTest(test, subtest, err)

    def stopTest(self, test):
        self.records.append({"id": test.id(), "status": self.outcome,
                             "elapsed_seconds": time.perf_counter() - self.started})
        super().stopTest(test)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New JSON report path (must not exist)")
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ is required")
    stamp = datetime.now(timezone.utc)
    run_id = stamp.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    output = args.output or ROOT / "reports/check" / (run_id + ".json")
    output = output.absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve before running, so an existing historical report is never replaced.
    with output.open("x", encoding="utf-8") as report_file:
        before = manifest()
        parent = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True, check=False)
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
        start = time.perf_counter()
        result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(suite)
        elapsed = time.perf_counter() - start
        unchanged = before == manifest()
        passed = (result.wasSuccessful() and result.testsRun > 0 and unchanged
                  and all(r["status"] == "passed" for r in result.records))
        report = {
            "format": "bublik-offline-check-v2", "run_id": run_id,
            "created_at": stamp.isoformat(), "stages": [1, 2, 3, 4, 5, 6, 7, 8],
            "status": "passed" if passed else "failed",
            "environment": {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
                            "system": platform.system(), "machine": platform.machine(),
                            "implementation": platform.python_implementation()},
            "source": {"git_head_at_run": parent.stdout.strip() if parent.returncode == 0 else None,
                       "interpretation": "HEAD plus the source_sha256 manifest; files may be uncommitted",
                       "unchanged_during_run": unchanged, "source_sha256": before},
            "summary": {"tests": result.testsRun, "failures": len(result.failures),
                        "errors": len(result.errors), "skipped": len(result.skipped),
                        "elapsed_seconds": elapsed},
            "tests": result.records,
            "evidence": "Real SQLite/threads/processes, ASGI security and verified loopback TLS sockets; synthetic inference only, NO real Ollama/Qwen",
            "not_run": ["Ollama/Qwen inference", "actual Qwen token counting",
                        "real HTTP + Qwen 10 sequential / 3 concurrent", "real browser acceptance",
                        "LAN device access", "mobile internet chat", "Ollama network isolation",
                        "server reboot/autostart", "operational production restore"]
                       + ([] if platform.system() == "Darwin" and platform.machine() == "arm64" else ["target MacBook/M1 storage and protocol tests"]),
        }
        json.dump(report, report_file, ensure_ascii=False, indent=2, allow_nan=False)
        report_file.write("\n")
    print(json.dumps({"report": str(output), "status": report["status"], **report["summary"]}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
