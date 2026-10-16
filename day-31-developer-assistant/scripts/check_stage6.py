"""Full reliability/regression suite, real MCP smoke, optional bounded Qwen smoke."""
import argparse
import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
import tempfile
import unittest

from check_stage12 import ROOT, RecordedResult
from bublik_developer import __version__
from bublik_developer.pipeline import Pipeline
from bublik_developer.rag.corpus import ProjectCorpus
from bublik_developer.rag.index import build_index
from bublik_developer.rag.state import ProjectState
from bublik_developer.workspace import ProjectWorkspace


async def smoke(workspace, state):
    values = []
    for question in ("current branch", "zxqv_unicorn_transducer_9988"):
        result = await Pipeline(workspace, state_dir=state.path, language="en").run(question)
        values.append(result)
    passed = (values[0]["answer_status"] == "answered" and values[0]["metrics"]["llm_calls"] == 0
              and values[1]["answer_status"] == "unknown" and values[1]["execution_status"] == "completed"
              and values[1]["metrics"]["llm_calls"] == 0)
    return {"status": "passed" if passed else "failed", "requests": values,
            "scope": "actual project FTS, actual Git MCP and owned workers; no model generation"}


async def live_smoke(workspace, state):
    observations = []
    for language, question in (("ru", "Где хранится полная история переписки?"),
                               ("en", "What is the private service API prefix and what is the current branch?")):
        result = await Pipeline(workspace, state_dir=state.path, language=language).run(question)
        observations.append(result)
        if result["execution_status"] != "completed" or result["answer_status"] != "answered":
            break  # No repair, retry or another model request after an inference failure.
    complete = (len(observations) == 2 and all(x["execution_status"] == "completed" and x["answer_status"] == "answered" for x in observations)
                and observations[0]["metrics"]["llm_calls"] == 1
                and observations[1]["metrics"]["llm_calls"] == 2
                and observations[1]["independent_llm_contexts_verified"])
    return {"status": "passed" if complete else "failed", "requests": observations,
            "scope": "real local Qwen tasks, two different scoped contexts on a mixed request; semantic correctness still needs human review",
            "requested_max_generation_calls": 3, "retrieval_mode": "fts", "hidden_retries": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT.parent)
    parser.add_argument("--state-dir", type=Path, help="Existing index for optional live generation")
    parser.add_argument("--live", action="store_true", help="At most three real local Qwen generations; no automatic model restart")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("output already exists; choose a new filename (no overwrite)")
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    offline, live, error, session_status = {}, None, None, None
    try:
        workspace = ProjectWorkspace.open(args.root, "ai-advent-llm-api")
        with tempfile.TemporaryDirectory() as folder:
            state = ProjectState(workspace, Path(folder).resolve() / "pipeline-state")
            built = build_index(ProjectCorpus(workspace), state)
            offline = asyncio.run(smoke(workspace, state))
            offline["build"] = built
        if args.live and result.wasSuccessful() and not result.skipped and offline["status"] == "passed":
            from bublik_developer.model_session import ModelSession
            session_status = ModelSession(workspace).status()
            if not session_status["gate_open"]:
                from bublik_developer.errors import DeveloperError, ErrorCode
                raise DeveloperError(ErrorCode.MODEL_SESSION_REQUIRED)
            live = asyncio.run(live_smoke(workspace, ProjectState(workspace, args.state_dir)))
    except Exception as caught:
        error = getattr(getattr(caught, "code", None), "value", "stage6_smoke_failed")
    passed = (result.wasSuccessful() and not result.skipped and error is None and offline.get("status") == "passed"
              and (not args.live or live is not None and live["status"] == "passed"))
    report = {"format": "bublik-developer-stage6-v1", "version": __version__, "created_at": datetime.now(timezone.utc).isoformat(),
              "status": "passed" if passed else "failed", "python": platform.python_version(), "platform": platform.system(),
              "tests_run": result.testsRun, "tests": result.observations, "error": error, "offline_pipeline_smoke": offline,
              "live_requested": args.live, "live_pipeline_smoke": live, "model_session_status": session_status,
              "retry_policy": {"metadata_transport_retries_per_model_task":1,"generation_retries":0,"embedding_retries":0,"mcp_tool_replays":0,"cloud_fallbacks":0},
              "source_sha256": {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
                                for path in sorted(ROOT.rglob("*.py")) if not {".venv", "__pycache__"}.intersection(path.parts)},
              "synthetic_checks": ["Qwen response/model identity fixtures in unit tests", "Git result fixtures in pipeline unit tests", "legacy dense vectors/OS witnesses", "reliability transport faults and synthetic epoch witnesses; owned child cleanup and persisted checkpoints are real"],
              "not_run": (["real Qwen generation"] if not args.live else []) + ["held-out semantic evaluation", "single/multi benchmark", "wide real Ollama interruption and resource stress"]}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=True, sort_keys=True, indent=2);stream.write("\n")
    print(json.dumps({"status": report["status"], "tests_run": result.testsRun, "offline_pipeline": offline.get("status"),
                      "live_pipeline": live.get("status") if live else None, "error": error}, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
