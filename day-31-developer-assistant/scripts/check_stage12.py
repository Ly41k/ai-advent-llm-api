"""Produce a repeatable foundation/real-MCP report without any model calls."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
from time import perf_counter
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.observations = []

    def startTest(self, test):
        self.started = perf_counter()
        super().startTest(test)

    def record(self, test, status):
        self.observations.append({"id": test.id(), "status": status, "seconds": perf_counter() - self.started})

    def addSuccess(self, test):
        super().addSuccess(test)
        self.record(test, "passed")

    def addError(self, test, error):
        super().addError(test, error)
        self.record(test, "failed")

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.record(test, "failed")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.record(test, "skipped")

    def addSubTest(self, test, subtest, error):
        super().addSubTest(test, subtest, error)
        if error is not None:
            self.record(subtest, "failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="NEW JSON file; never overwrites a previous report")
    args = parser.parse_args()
    suite = unittest.TestSuite([unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=pattern)
                               for pattern in ("test_foundation.py", "test_mcp_git.py")])
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    sources = {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
               for path in sorted(ROOT.rglob("*.py")) if ".venv" not in path.parts and "__pycache__" not in path.parts}
    report = {"format": "bublik-developer-stage12-v1", "created_at": datetime.now(timezone.utc).isoformat(),
              "status": "passed" if result.wasSuccessful() and not result.skipped else "failed",
              "python": platform.python_version(), "platform": platform.system(),
              "packages": {name: importlib.metadata.version(name) for name in ("mcp", "jsonschema", "pydantic")},
              "tests_run": result.testsRun, "tests": result.observations, "source_sha256": sources,
              "evidence": "Real Git temporary repositories, actual MCP stdio processes, subprocesses and sockets. No LLM inference.",
              "simulated_checks": ["macOS launchctl return values", "Day 30 process presence", "unstable snapshot witnesses"],
              "not_run": (["macOS/M1 runtime"] if platform.system() != "Darwin" else ["M1 model/resource measurements"])
                         + ["actual launchd shutdown", "Ollama/Qwen/bge-m3", "project RAG", "multi-agent lifecycle", "single/multi benchmark"]}
    encoded = json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
    else:
        print(encoded, end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
