"""All stage 1–3 tests and actual project FTS smoke; models stay synthetic here."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import tempfile
import unittest

from check_stage12 import ROOT, RecordedResult
from bublik_developer import __version__
from bublik_developer.rag.corpus import ProjectCorpus
from bublik_developer.rag.index import ProjectIndex, build_index
from bublik_developer.rag.retrieval import search
from bublik_developer.rag.state import ProjectState
from bublik_developer.workspace import ProjectWorkspace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT.parent)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    suite = unittest.TestSuite([unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=pattern)
                               for pattern in ("test_foundation.py", "test_mcp_git.py", "test_project_rag.py")])
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    smoke, smoke_error = {}, None
    try:
        workspace = ProjectWorkspace.open(args.root, "ai-advent-llm-api")
        corpus = ProjectCorpus(workspace)
        with tempfile.TemporaryDirectory() as folder:
            # Use the physical temporary directory on macOS (/var is a link).
            state = ProjectState(workspace, Path(folder).resolve(strict=True) / "project-index")
            built = build_index(corpus, state)
            with ProjectIndex.current(state, corpus) as index:
                verified = index.verify()
                rows = [search(index, question) for question in (
                    "Как устроена память Бублика?", "What is the API prefix?", "What is git_current_branch?")]
                smoke = {"build": built, "verify": verified, "searches": rows,
                         "status": "passed" if all(row["sources"] for row in rows) else "failed"}
    except Exception as error:
        smoke_error = getattr(getattr(error, "code", None), "value", "smoke_failed")
    source_hashes = {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
                     for path in sorted(ROOT.rglob("*.py")) if not {".venv", "__pycache__"}.intersection(path.parts)}
    report = {"format": "bublik-developer-stage3-v1", "version": __version__,
              "created_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(), "platform": platform.system(),
              "status": "passed" if result.wasSuccessful() and not result.skipped and smoke.get("status") == "passed" else "failed",
              "tests_run": result.testsRun, "tests": result.observations, "source_sha256": source_hashes,
              "packages": {name: importlib.metadata.version(name) for name in ("mcp", "jsonschema", "pydantic")},
              "project_fts_smoke": smoke, "smoke_error": smoke_error,
              "evidence": "Real Git/MCP/SQLite/FTS/corpus/files/sockets. Synthetic dense vectors and model-session witnesses in unit tests.",
              "simulated_checks": ["launchctl", "Ollama epoch witness", "embedding HTTP payloads/vectors"],
              "not_run": ["real bge-m3 embeddings", "real fresh Ollama session", "Qwen answers", "agent lifecycle", "single/multi benchmark", "human semantic evaluation"]}
    encoded = json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
    else:
        print(encoded, end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
