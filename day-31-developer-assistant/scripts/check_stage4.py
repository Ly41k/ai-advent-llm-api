"""Real Stage 1–4 tests and scoped runtime demo; zero model generation."""
import argparse
import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import platform
import tempfile
import unittest

from check_stage12 import ROOT, RecordedResult
from bublik_developer import __version__
from bublik_developer.agent_runtime import demo
from bublik_developer.rag.corpus import ProjectCorpus
from bublik_developer.rag.index import build_index
from bublik_developer.rag.state import ProjectState
from bublik_developer.workspace import ProjectWorkspace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT.parent)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output and (args.output.exists() or args.output.is_symlink()):
        parser.error("output already exists; choose a new filename (no overwrite)")
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    smoke, smoke_error = {}, None
    try:
        workspace = ProjectWorkspace.open(args.root, "ai-advent-llm-api")
        corpus = ProjectCorpus(workspace)
        with tempfile.TemporaryDirectory() as folder:
            state = ProjectState(workspace, Path(folder).resolve(strict=True) / "project-index")
            built = build_index(corpus, state)
            observed = asyncio.run(demo(workspace, corpus, state, question="How does memory retrieval work?"))
            smoke = {"build": built, "runtime": observed,
                     "status": "passed" if observed["status"] == "completed" and len(observed["merged"]) == 2 else "failed"}
    except Exception as caught:
        smoke_error = getattr(getattr(caught, "code", None), "value", "runtime_smoke_failed")
    report = {"format": "bublik-developer-stage4-v1", "version": __version__,
              "created_at": datetime.now(timezone.utc).isoformat(), "platform": platform.system(), "python": platform.python_version(),
              "status": "passed" if result.wasSuccessful() and not result.skipped and smoke.get("status") == "passed" else "failed",
              "tests_run": result.testsRun, "tests": result.observations,
              "source_sha256": {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
                                for path in sorted(ROOT.rglob("*.py")) if not {".venv", "__pycache__"}.intersection(path.parts)},
              "packages": {name: importlib.metadata.version(name) for name in ("mcp", "jsonschema", "pydantic")},
              "project_runtime_smoke": smoke, "smoke_error": smoke_error,
              "evidence": "Actual owned worker processes, FTS/SQLite/source provenance and MCP stdio; separate role contexts and lifecycle.",
              "controlled_faults": ["worker timeout/cancel/output overflow/descendant", "tampered quote", "source changed before verification", "budget exhausted"],
              "simulated_checks": ["launchctl", "Ollama epoch", "embedding HTTP payloads and synthetic vectors in unit tests"],
              "not_run": ["Qwen generation", "two independent LLM contexts", "model failure recovery on Mac", "single/multi benchmark", "held-out human semantic evaluation"]}
    encoded = json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
    else:
        print(encoded, end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
