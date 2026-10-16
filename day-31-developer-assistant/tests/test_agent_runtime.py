"""Actual worker processes, FTS and MCP; controlled faults contain no inference."""
import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from bublik_developer.agent_process import run_owned
from bublik_developer.agent_runtime import Dispatcher, Job, demo
from bublik_developer.agent_worker import execute as worker_execute
from bublik_developer.contracts import AgentResult, ContextEnvelope, Role, TaskEnvelope, TaskStatus
from bublik_developer.errors import DeveloperError, ErrorCode
from bublik_developer.process import minimal_env
from bublik_developer.rag.corpus import ProjectCorpus
from bublik_developer.rag.index import build_index
from bublik_developer.rag.state import ProjectState
from bublik_developer.workspace import ProjectWorkspace


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name).resolve(strict=True)
        self.root = self.parent / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "README.md").write_text("# Memory\nMemory history is stored in SQLite.\n")
        self.workspace = ProjectWorkspace.open(self.root, "fixture")
        self.corpus = ProjectCorpus(self.workspace)
        self.state = ProjectState(self.workspace, self.parent / "state")
        self.request = uuid4().hex

    def task(self, role, context):
        return TaskEnvelope.create(role, "fixture", "Scoped fixture task", context, request_id=self.request)

    def jobs(self):
        docs = self.task(Role.DOCUMENTATION, {"question": "memory"})
        git = self.task(Role.GIT, {"operation": "branch", "arguments": {}})
        ids = (docs.task_id, git.task_id)
        verify = self.task(Role.VERIFICATION, {"task_ids": list(ids)})
        return [Job(docs), Job(git), Job(verify, ids)]

    def dispatcher(self, **kwargs):
        return Dispatcher(self.workspace, self.corpus, self.state, **kwargs)

    async def test_actual_fanout_lifecycle_and_verified_merge(self):
        build_index(self.corpus, self.state)
        report = await self.dispatcher().run(self.jobs())
        self.assertEqual(report["status"], "completed")
        self.assertEqual(len(report["merged"]), 2)
        self.assertEqual(report["metrics"]["llm_calls"], 0)
        self.assertEqual(report["metrics"]["capability_calls"], 3)
        self.assertEqual(report["tool_events"][0]["tool"], "git__git_current_branch")
        for result in report["results"]:
            events = [row["event"] for row in report["trace"] if row.get("task_id") == result["task_id"]]
            self.assertEqual([e for e in events if e != "WORKER_REAPED"], ["SPAWN", "EXECUTE", "REPORT"])
        trace = report["trace"]
        docs = next(x for x in trace if x["event"] == "REPORT" and x["role"] == "documentation")
        git_start = next(x for x in trace if x["event"] == "EXECUTE" and x["role"] == "git")
        verifier = next(x for x in trace if x["event"] == "EXECUTE" and x["role"] == "verification")
        self.assertLess(git_start["sequence"], docs["sequence"])
        self.assertGreater(verifier["sequence"], docs["sequence"])
        self.assertEqual(trace[-1]["event"], "MERGE")
        for event in trace:
            if event["event"] == "WORKER_REAPED":
                with self.assertRaises(ProcessLookupError):
                    os.kill(event["worker_pid"], 0)

    async def test_contexts_are_sealed_and_do_not_share_caller_history(self):
        build_index(self.corpus, self.state)
        payload = {"question": "memory DOC_CANARY_671"}
        docs = self.task(Role.DOCUMENTATION, payload)
        payload["question"] = "MUTATED_PARENT_HISTORY"
        git = self.task(Role.GIT, {"operation": "branch", "arguments": {}})
        ids = (docs.task_id, git.task_id)
        verification = self.task(Role.VERIFICATION, {"task_ids": list(ids)})
        dispatcher = self.dispatcher()
        execute = dispatcher.execute
        observed = {}
        async def capture(task, context):
            observed[task.role] = context.open()
            return await execute(task, context)
        with patch.object(dispatcher, "execute", side_effect=capture):
            report = await dispatcher.run([Job(docs), Job(git), Job(verification, ids)])
        self.assertEqual(report["status"], "completed")
        self.assertIn("DOC_CANARY_671", json.dumps(observed[Role.DOCUMENTATION]))
        for role in (Role.GIT, Role.VERIFICATION):
            self.assertNotIn("DOC_CANARY_671", json.dumps(observed[role]))
            self.assertNotIn("MUTATED_PARENT_HISTORY", json.dumps(observed[role]))
        self.assertNotIn("DOC_CANARY_671", json.dumps(report["trace"]))
        self.assertEqual(len({row["context_digest"] for row in report["context_audit"]}), 3)

    async def test_wrong_role_extra_input_and_project_are_rejected_before_execute(self):
        jobs = self.jobs()
        variants = [replace(jobs[0].task, role=Role.MAIN),
                    replace(jobs[0].task, project_id="other"),
                    replace(jobs[0].task, context=ContextEnvelope.seal({"question": "memory", "history": "private"})),
                    replace(jobs[1].task, context=ContextEnvelope.seal({"operation": "commit", "arguments": {}})),
                    replace(jobs[1].task, context=ContextEnvelope.seal({"operation": [], "arguments": {}}))]
        for task in variants:
            dispatcher = self.dispatcher()
            with patch.object(dispatcher, "execute") as execute:
                with self.assertRaises(DeveloperError):
                    await dispatcher.run([Job(task)])
                execute.assert_not_called()
                self.assertEqual(dispatcher.trace, [])

    async def test_duplicate_unknown_dependency_and_request_mix_are_rejected(self):
        jobs = self.jobs()
        invalid = [[jobs[0], jobs[0]],
                   [Job(jobs[0].task, ("missing",))],
                   [jobs[0], Job(replace(jobs[1].task, request_id="another"))],
                   [Job(jobs[0].task, ([],))],
                   [Job(jobs[0].task, (jobs[0].task.task_id,))]]
        for value in invalid:
            with self.assertRaises(DeveloperError):
                await self.dispatcher().run(value)

    async def test_shared_call_budget_blocks_verifier_and_unverified_merge(self):
        build_index(self.corpus, self.state)
        report = await self.dispatcher(max_calls=2).run(self.jobs())
        self.assertEqual(report["metrics"]["capability_calls"], 2)
        self.assertEqual(report["merged"], [])
        self.assertEqual(report["results"][-1]["error_code"], ErrorCode.PERMISSION_DENIED)

    async def test_missing_index_preserves_git_result_and_blocks_dependency(self):
        report = await self.dispatcher().run(self.jobs())
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["results"][0]["error_code"], ErrorCode.INDEX_UNAVAILABLE)
        self.assertEqual(report["results"][1]["status"], "success")
        self.assertEqual(report["results"][2]["error_code"], ErrorCode.DEPENDENCY_FAILED)
        self.assertEqual(report["merged"], [])

    async def test_tampered_source_quote_is_rejected_after_delegation(self):
        build_index(self.corpus, self.state)
        dispatcher = self.dispatcher()
        execute = dispatcher.execute
        async def tamper(task, context):
            result = await execute(task, context)
            if task.role == Role.DOCUMENTATION:
                data = result.data.open()
                data["sources"][0]["quote"] = "Invented source claim"
                return replace(result, data=ContextEnvelope.seal(data))
            return result
        with patch.object(dispatcher, "execute", side_effect=tamper):
            report = await dispatcher.run(self.jobs())
        self.assertEqual(report["results"][-1]["error_code"], ErrorCode.INVALID_TOOL_OUTPUT)
        self.assertEqual(report["merged"], [])

    async def test_doc_change_before_verification_blocks_stale_provenance(self):
        build_index(self.corpus, self.state)
        dispatcher = self.dispatcher()
        execute = dispatcher.execute
        async def modify(task, context):
            if task.role == Role.VERIFICATION:
                (self.root / "README.md").write_text("# Changed\nNew content.\n")
            return await execute(task, context)
        with patch.object(dispatcher, "execute", side_effect=modify):
            report = await dispatcher.run(self.jobs())
        self.assertEqual(report["results"][-1]["error_code"], ErrorCode.INDEX_STALE)
        self.assertEqual(report["merged"], [])

    async def sleeper(self, task, context):
        code = "import os,pathlib,time;pathlib.Path(" + repr(str(self.parent / 'worker.pid')) + ").write_text(str(os.getpid()));time.sleep(20)"
        await run_owned([sys.executable, "-c", code], b"{}", cwd=str(self.parent), env=minimal_env())

    def assert_worker_gone(self):
        pid = int((self.parent / "worker.pid").read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    async def test_task_timeout_kills_and_reaps_owned_worker(self):
        dispatcher = self.dispatcher()
        task = replace(self.jobs()[0].task, timeout_seconds=.3)
        with patch.object(dispatcher, "execute", side_effect=self.sleeper):
            report = await dispatcher.run([Job(task)])
        self.assertEqual(report["results"][0]["status"], "timeout")
        self.assert_worker_gone()

    async def test_request_cancellation_reports_once_and_reaps_worker(self):
        dispatcher = self.dispatcher()
        with patch.object(dispatcher, "execute", side_effect=self.sleeper):
            handle = asyncio.create_task(dispatcher.run([self.jobs()[0]]))
            async with asyncio.timeout(3):
                while not (self.parent / "worker.pid").exists():
                    await asyncio.sleep(.01)
            handle.cancel()
            report = await handle
        self.assertEqual(report["results"][0]["status"], "cancelled")
        self.assertEqual(sum(row["event"] == "REPORT" for row in report["trace"]), 1)
        self.assert_worker_gone()

    async def test_request_deadline_cancels_and_reaps_worker(self):
        dispatcher = self.dispatcher(timeout=.3)
        with patch.object(dispatcher, "execute", side_effect=self.sleeper):
            report = await dispatcher.run([self.jobs()[0]])
        self.assertEqual(report["trace"][-1]["interruption"], "timeout")
        self.assert_worker_gone()

    async def test_worker_output_limit_is_enforced_while_reading(self):
        code = "import sys,time;sys.stdout.write('x'*500000);sys.stdout.flush();time.sleep(20)"
        async with asyncio.timeout(3):
            with self.assertRaises(DeveloperError) as caught:
                await run_owned([sys.executable, "-c", code], b"{}", cwd=str(self.parent), env=minimal_env())
        self.assertEqual(caught.exception.code, ErrorCode.OUTPUT_LIMIT)

    async def test_worker_descendant_is_reaped_after_parent_exits(self):
        marker = self.parent / "descendant.pid"
        child = "import os,pathlib,time;pathlib.Path(" + repr(str(marker)) + ").write_text(str(os.getpid()));time.sleep(20)"
        parent = "import subprocess,sys;subprocess.Popen([sys.executable,'-c'," + repr(child) + "]);print('{}')"
        with self.assertRaises(TimeoutError):
            async with asyncio.timeout(.5):
                await run_owned([sys.executable, "-c", parent], b"{}", cwd=str(self.parent), env=minimal_env())
        # A killed descendant can briefly remain a zombie until its OS reaper runs.
        pid = int(marker.read_text())
        code = subprocess.run(["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True)
        self.assertTrue(code.returncode != 0 or code.stdout.strip().startswith("Z"))

    async def test_existing_calibration_report_is_rejected_before_workspace_access(self):
        path = self.parent / "saved.json"
        path.write_text("original report")
        app = Path(__file__).resolve().parents[1]
        code = subprocess.run([sys.executable, str(app / "scripts/compare_project_retrieval.py"),
                               "--root", str(self.parent / "missing"), "--modes", "all", "--output", str(path)],
                              capture_output=True, text=True)
        self.assertEqual(code.returncode, 2)
        self.assertIn("output already exists", code.stderr)
        self.assertNotIn("Traceback", code.stderr)
        self.assertEqual(path.read_text(), "original report")

    async def test_worker_wrong_role_has_no_workspace_access(self):
        payload = {"role": "main", "root": str(self.root), "workspace_identity": list(self.workspace.identity),
                   "project_id": "fixture", "state_dir": str(self.state.path), "selection": None, "context": {}}
        with patch("bublik_developer.agent_worker.ProjectWorkspace.open") as opened:
            with self.assertRaises(DeveloperError):
                worker_execute(payload)
            opened.assert_not_called()

    async def test_no_evidence_is_successful_outcome_and_dispatcher_is_single_use(self):
        build_index(self.corpus, self.state)
        dispatcher = self.dispatcher()
        docs = self.task(Role.DOCUMENTATION, {"question": "zxqv_unicorn_transducer_9988"})
        verification = self.task(Role.VERIFICATION, {"task_ids": [docs.task_id]})
        report = await dispatcher.run([Job(verification, (docs.task_id,)), Job(docs)])
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["results"][1]["outcome"], "insufficient_evidence")
        with self.assertRaises(DeveloperError):
            await dispatcher.run([Job(docs)])
