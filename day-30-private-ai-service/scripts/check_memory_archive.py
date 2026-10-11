"""Storage-only portability and regression evidence; never a live model proof."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import sqlite3
import sys
import time
import unittest

from check_storage import ROOT, RecordingResult, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="NEW report; never overwrite")
    args = parser.parse_args()
    output = args.output.expanduser().absolute()
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        before = manifest()
        sys.path.insert(0, str(ROOT / "tests"))
        loader = unittest.defaultTestLoader
        suite = unittest.TestSuite([loader.loadTestsFromName("test_memory_archive"),
                                    loader.loadTestsFromName("test_storage")])
        started = time.perf_counter()
        result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(suite)
        elapsed = time.perf_counter() - started
        unchanged = before == manifest()
        passed = (result.wasSuccessful() and result.testsRun > 0 and unchanged
                  and all(r["status"] == "passed" for r in result.records))
        report = {"format": "bublik-offline-check-v2", "scope": "memory-portability-and-storage-only",
                  "created_at": datetime.now(timezone.utc).isoformat(),
                  "base_commit": "115247d6a2fb73788f22271991bb3445000ca12e",
                  "status": "passed" if passed else "failed",
                  "source": {"unchanged_during_run": unchanged, "source_sha256": before},
                  "environment": {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
                                  "system": platform.system(), "machine": platform.machine()},
                  "summary": {"tests": result.testsRun, "failures": len(result.failures),
                              "errors": len(result.errors), "skipped": len(result.skipped),
                              "elapsed_seconds": elapsed}, "tests": result.records,
                  "evidence": "Real SQLite WAL backups, files, corruption/rejection checks and separate-process restore; synthetic chat contents",
                  "not_run": ["full HTTP/inference/browser suite", "real Ollama/Qwen", "production Mac database",
                              "physical transfer to another computer", "power-cut durability", "archive encryption",
                              "disaster recovery from pending/uncertain inference", "semantic long-term recall"]}
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"report": str(output), "status": report["status"], **report["summary"]}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
