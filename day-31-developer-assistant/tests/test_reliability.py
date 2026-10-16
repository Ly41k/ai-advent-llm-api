"""Fault injection: real owned workers/state/FTS; synthetic model and epoch witnesses."""
import asyncio
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import tempfile
from time import sleep
import unittest
from unittest.mock import AsyncMock, patch
from urllib.error import HTTPError, URLError

import test_pipeline as fixtures
from bublik_developer.agent_process import run_owned
from bublik_developer.contracts import Role
from bublik_developer.errors import DeveloperError, ErrorCode
from bublik_developer.generation import Qwen
from bublik_developer.inference_tasks import InferenceTasks
from bublik_developer.model_session import ModelSession
from bublik_developer.pipeline import Budget, Pipeline
from bublik_developer.process import minimal_env
from bublik_developer.rag.embeddings import LocalEmbeddings, TransportUnavailable
from bublik_developer.reliability import failure_advice
from bublik_developer.workspace import ProjectWorkspace


class MetadataFaultTests(unittest.TestCase):
    def transport(self, *, failures=1, phase="before", malformed=False):
        healthy, calls = fixtures.GenerationTests().server()
        seen, dispatched = 0, False
        def fault(endpoint, body):
            nonlocal seen, dispatched
            if endpoint == "/api/chat":dispatched = True
            if endpoint == "/api/tags" and (phase == "before" and not dispatched or phase == "after" and dispatched):
                seen += 1
                if seen <= failures:
                    calls.append((endpoint, body))
                    if malformed:raise DeveloperError(ErrorCode.EMBEDDING_UNAVAILABLE)
                    raise TransportUnavailable()
            return healthy(endpoint, body)
        return fault, calls

    def test_transient_metadata_retries_once_before_generation(self):
        transport, calls = self.transport();client = Qwen(fixtures.FakeLease(), transport=transport)
        client.generate(Role.DOCUMENTATION, fixtures.documentation_context())
        self.assertEqual(client.metrics["metadata_retries"], 1)
        self.assertEqual(client.metrics["llm_calls"], 1)
        self.assertEqual(sum(x[0] == "/api/chat" for x in calls), 1)
        self.assertEqual(len(client.metrics["http_events"]), len(calls))
        self.assertEqual(client.metrics["http_events"][0]["status"], "retry_scheduled")
        self.assertEqual(client.metrics["http_events"][0]["delay_seconds"], .05)

    def test_second_metadata_failure_stops_before_dispatch(self):
        transport, calls = self.transport(failures=10);lease = fixtures.FakeLease();client = Qwen(lease, transport=transport)
        with self.assertRaises(DeveloperError) as caught:client.generate(Role.DOCUMENTATION, fixtures.documentation_context())
        self.assertEqual(caught.exception.code, ErrorCode.LLM_UNAVAILABLE)
        self.assertEqual(client.metrics["llm_calls"], 0)
        self.assertEqual(client.metrics["metadata_retries"], 1)
        self.assertEqual(len(calls), 2)
        self.assertFalse(lease.started)

    def test_malformed_metadata_is_not_retried(self):
        transport, calls = self.transport(malformed=True);client = Qwen(fixtures.FakeLease(), transport=transport)
        with self.assertRaises(DeveloperError):client.generate(Role.DOCUMENTATION, fixtures.documentation_context())
        self.assertEqual(len(calls), 1)
        self.assertEqual(client.metrics["metadata_retries"], 0)

    def test_post_dispatch_metadata_is_not_retried_or_generated_again(self):
        transport, calls = self.transport(phase="after");client = Qwen(fixtures.FakeLease(), transport=transport)
        with self.assertRaises(DeveloperError):client.generate(Role.DOCUMENTATION, fixtures.documentation_context())
        self.assertEqual(client.metrics["llm_calls"], 1)
        self.assertEqual(client.metrics["metadata_retries"], 0)
        self.assertEqual(sum(x[0] == "/api/chat" for x in calls), 1)

    def test_real_http_adapter_distinguishes_connection_and_http_errors(self):
        client = LocalEmbeddings(fixtures.FakeLease())
        with patch.object(client.opener, "open", side_effect=URLError("PRIVATE_FAILURE_BODY")):
            with self.assertRaises(TransportUnavailable) as caught:client.request("/api/tags")
        self.assertNotIn("PRIVATE_FAILURE_BODY", str(caught.exception))
        with patch.object(client.opener, "open", side_effect=HTTPError("http://127.0.0.1:11434", 503, "secret", {}, None)):
            with self.assertRaises(DeveloperError) as caught:client.request("/api/tags")
        self.assertNotIsInstance(caught.exception, TransportUnavailable)

    def test_client_is_single_use_after_completed_or_failed_generation(self):
        for settings in ({}, {"failures": 10}):
            transport, calls = self.transport(**settings);client = Qwen(fixtures.FakeLease(), transport=transport)
            try:client.generate(Role.DOCUMENTATION, fixtures.documentation_context())
            except DeveloperError:pass
            total = len(calls)
            with self.assertRaises(DeveloperError) as caught:client.generate(Role.DOCUMENTATION, fixtures.documentation_context())
            self.assertEqual(caught.exception.code, ErrorCode.PERMISSION_DENIED)
            self.assertEqual(len(calls), total)


class SessionFaultTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PipelineTests();self.fixture.setUp();self.addCleanup(self.fixture.temp.cleanup)
        self.epoch = "a" * 64
        self.session = ModelSession(self.fixture.workspace, state_path=self.fixture.parent / "model-state", witness=lambda:self.epoch)

    def test_status_without_session_does_not_publish_one(self):
        with patch("bublik_developer.model_session.check_day30_off"):
            result = self.session.status()
        self.assertEqual(result["status"], "not_confirmed")
        self.assertFalse(result["gate_open"])
        self.assertFalse(self.session.file.exists())

    def test_status_preserves_confirmed_uncertain_and_changed_epoch(self):
        with patch("bublik_developer.model_session.check_day30_off"):
            for state in ("prepared", "confirmed", "uncertain"):
                self.session._write(state, self.epoch);before = self.session.file.read_bytes()
                value = self.session.status()
                self.assertEqual(value["gate_open"], state == "confirmed")
                self.assertEqual(self.session.file.read_bytes(), before)
            self.epoch = "b" * 64
            self.assertEqual(self.session.status()["status"], "epoch_changed")
            self.assertFalse(self.session.status()["gate_open"])

    def test_uncertain_gate_requires_a_changed_epoch_for_confirm(self):
        self.session._write("uncertain", self.epoch)
        with patch("bublik_developer.model_session.check_day30_off"):
            with self.assertRaises(DeveloperError):
                with self.session.lease():pass
            with self.assertRaises(DeveloperError):self.session.confirm()
            self.epoch = "b" * 64
            self.assertEqual(self.session.confirm()["status"], "confirmed")
            with self.session.lease() as lease:lease.validate()

    def test_busy_session_is_typed_without_changing_checkpoint_or_waiting(self):
        self.session._write("confirmed",self.epoch)
        with patch("bublik_developer.model_session.check_day30_off"),self.session.lease():
            before = self.session.file.read_bytes()
            for operation in (self.session.status,self.session.prepare,self.session.confirm):
                with self.assertRaises(DeveloperError) as caught:operation()
                self.assertEqual(caught.exception.code,ErrorCode.MODEL_SESSION_BUSY)
                self.assertEqual(self.session.file.read_bytes(),before)
        with patch("bublik_developer.model_session.check_day30_off"),self.assertRaises(DeveloperError) as caught:
            with self.session.lease():raise DeveloperError(ErrorCode.INDEX_LOCKED)
        self.assertEqual(caught.exception.code,ErrorCode.INDEX_LOCKED)


class OwnedInferenceFaultTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixture = fixtures.PipelineTests();self.fixture.setUp();self.addCleanup(self.fixture.temp.cleanup)
        self.events = []
        self.tasks = InferenceTasks(self.fixture.workspace, "a" * 32,
            lambda event, **kw:self.events.append({"event":event, **kw}), Budget())

    async def test_invalid_worker_json_reports_unknown_and_does_not_retry(self):
        with patch("bublik_developer.inference_tasks.run_owned", new=AsyncMock(return_value=(b"not JSON", 1))) as worker:
            with self.assertRaises(DeveloperError) as caught:await self.tasks.run(Role.DOCUMENTATION, fixtures.documentation_context())
        self.assertEqual(caught.exception.code, ErrorCode.INVALID_TOOL_OUTPUT)
        self.assertEqual(worker.await_count, 1)
        self.assertIsNone(self.tasks.observations[0]["llm_calls"])
        self.assertEqual(sum(x["event"] == "REPORT" for x in self.events), 1)

    async def test_wrong_worker_identity_is_not_accepted_as_zero_calls(self):
        reply = {"data": {}, "error_code": None, "metrics": {"llm_calls":0,"task_id":"wrong","request_id":"wrong"}}
        with patch("bublik_developer.inference_tasks.run_owned", new=AsyncMock(return_value=(json.dumps(reply).encode(), 1))):
            with self.assertRaises(DeveloperError):await self.tasks.run(Role.DOCUMENTATION, fixtures.documentation_context())
        self.assertIsNone(self.tasks.observations[0]["llm_calls"])

    async def test_budget_blocks_worker_before_spawn(self):
        self.tasks.budget = Budget(limit=1, used=1)
        with patch("bublik_developer.inference_tasks.run_owned", new=AsyncMock()) as worker:
            with self.assertRaises(DeveloperError):await self.tasks.run(Role.DOCUMENTATION, fixtures.documentation_context())
        worker.assert_not_awaited()
        self.assertEqual(self.tasks.observations, [])

    async def test_invalid_worker_telemetry_is_not_counted_as_known_inference(self):
        for calls, tokens in ((True, 5),(1,-1),(1,"secret")):
            async def reply(argv,payload,**kw):
                identifiers = json.loads(payload)
                return json.dumps({"data":{},"error_code":None,"metrics":{"llm_calls":calls,"input_tokens":tokens,
                    "request_id":identifiers["request_id"],"task_id":identifiers["task_id"]}}).encode(),1
            tasks = InferenceTasks(self.fixture.workspace,"a"*32,lambda *a,**kw:None,Budget())
            with patch("bublik_developer.inference_tasks.run_owned",side_effect=reply):
                with self.assertRaises(DeveloperError) as caught:await tasks.run(Role.DOCUMENTATION,fixtures.documentation_context())
            self.assertEqual(caught.exception.code,ErrorCode.INVALID_TOOL_OUTPUT)
            self.assertIsNone(tasks.observations[0]["llm_calls"])

    async def test_cancel_reaps_real_owned_worker_and_preserves_uncertain_checkpoint(self):
        folder = self.fixture.parent;marker = folder / "inference.pid"
        epoch, model_state = "a" * 64, folder / "model-state"
        session = ModelSession(self.fixture.workspace, state_path=model_state, witness=lambda:epoch)
        session._write("confirmed", epoch)
        code = ("from pathlib import Path;import os,time;from unittest.mock import patch;"
                "from bublik_developer.workspace import ProjectWorkspace;from bublik_developer.model_session import ModelSession;"
                "w=ProjectWorkspace.open("+repr(str(self.fixture.root))+",'fixture');"
                "s=ModelSession(w,state_path=Path("+repr(str(model_state))+"),witness=lambda:"+repr(epoch)+");"
                "p=patch('bublik_developer.model_session.check_day30_off');p.start();"
                "manager=s.lease();lease=manager.__enter__();lease.begin();"
                "Path("+repr(str(marker))+").write_text(str(os.getpid()));time.sleep(20)")
        package = str(Path(__file__).resolve().parents[1])
        async def worker(*args, **kw):
            return await run_owned([sys.executable,"-c",code], b"{}", cwd=package, env={**minimal_env(),"PYTHONPATH":package})
        with patch("bublik_developer.inference_tasks.run_owned", side_effect=worker):
            handle = asyncio.create_task(self.tasks.run(Role.DOCUMENTATION, fixtures.documentation_context()))
            async with asyncio.timeout(8):
                while not marker.exists():await asyncio.sleep(.01)
            handle.cancel()
            with self.assertRaises(asyncio.CancelledError):await handle
        pid = int(marker.read_text())
        with self.assertRaises(ProcessLookupError):os.kill(pid,0)
        self.assertEqual(session._read()["state"], "uncertain")
        self.assertIsNone(self.tasks.observations[0]["llm_calls"])
        self.assertEqual(self.tasks.observations[0]["status"], "cancelled")
        with patch("bublik_developer.model_session.check_day30_off"):
            with self.assertRaises(DeveloperError):
                with session.lease():pass
        self.assertEqual(sum(x["event"] == "REPORT" for x in self.events), 1)

    async def test_repeated_cancellation_still_waits_for_owned_cleanup(self):
        from bublik_developer.agent_process import stop
        marker = self.fixture.parent / "owned.pid"
        code = "import os,time;from pathlib import Path;Path("+repr(str(marker))+").write_text(str(os.getpid()));time.sleep(20)"
        entered, release = asyncio.Event(), asyncio.Event()
        async def slow_stop(process):
            entered.set()
            await release.wait()
            await stop(process)
        with patch("bublik_developer.agent_process.stop",side_effect=slow_stop):
            handle = asyncio.create_task(run_owned([sys.executable,"-c",code],b"{}",cwd=str(self.fixture.parent),env=minimal_env()))
            async with asyncio.timeout(8):
                while not marker.exists():await asyncio.sleep(.01)
            handle.cancel()
            await entered.wait()
            handle.cancel()
            await asyncio.sleep(0)
            self.assertFalse(handle.done())
            release.set()
            with self.assertRaises(asyncio.CancelledError):await handle
        with self.assertRaises(ProcessLookupError):os.kill(int(marker.read_text()),0)


class PipelineFaultTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixture = fixtures.PipelineTests();self.fixture.setUp();self.addCleanup(self.fixture.temp.cleanup)

    async def interrupted(self, *, timeout=False):
        ready = asyncio.Event()
        class AbsorbingDispatcher:
            def __init__(self,*args,**kw):pass
            async def run(self,jobs):
                ready.set()
                try:await asyncio.Event().wait()
                except asyncio.CancelledError:pass
                return {"results":[],"merged":[],"metrics":{"capability_calls":1},
                        "trace":[{"event":"MERGE","interruption":"cancelled"}]}
        pipeline = self.fixture.pipeline(runtime_factory=AbsorbingDispatcher,timeout=.05 if timeout else 5)
        handle = asyncio.create_task(pipeline.run("How does memory work?"))
        await ready.wait()
        if not timeout:handle.cancel()
        return await handle

    async def test_swallowed_runtime_cancellation_cannot_launch_model_or_publish(self):
        result = await self.interrupted()
        self.assertEqual(result["execution_status"], "failed")
        self.assertIn("cancelled", result["diagnostics"])
        self.assertEqual(result["metrics"]["llm_calls"],0)
        self.assertEqual(result["claims"],[])
        self.assertEqual(result["metrics"]["capability_calls"],1)

    async def test_overall_deadline_survives_runtime_swallowing_cancellation(self):
        result = await self.interrupted(timeout=True)
        self.assertEqual(result["execution_status"],"failed")
        self.assertIn("timeout",result["diagnostics"])
        self.assertEqual(result["metrics"]["timeout_count"],1)
        self.assertEqual(result["claims"],[])

    async def test_slow_final_source_check_cannot_publish_after_deadline(self):
        pipeline = self.fixture.pipeline(timeout=4)
        original, calls = pipeline.verify_sources, 0
        def slow(catalog):
            nonlocal calls
            calls += 1
            if calls == 2:sleep(4.1)
            return original(catalog)
        with patch.object(pipeline,"verify_sources",side_effect=slow):result = await pipeline.run("How does memory work?")
        self.assertEqual(result["execution_status"],"failed")
        self.assertIn("timeout",result["diagnostics"])
        self.assertEqual(result["claims"],[])
        self.assertEqual(result["citations"],[])
        self.assertEqual(calls,2)

    async def test_model_unknown_cannot_hide_stale_final_sources(self):
        owner = self.fixture
        class UnknownInference:
            def __init__(self,*args):self.observations=[]
            async def run(self,*args,**kw):
                (owner.root/"README.md").write_text("# Changed\nChanged source.\n")
                return {"status":"unknown","language":"en","claims":[]}
        result = await self.fixture.pipeline(inference_factory=UnknownInference).run("How does memory work?")
        self.assertEqual(result["execution_status"],"failed")
        self.assertIn(ErrorCode.INDEX_STALE.value,result["diagnostics"])

    async def test_trace_write_failure_is_typed_without_private_exception_text(self):
        pipeline = self.fixture.pipeline()
        async def result(plan,question):return pipeline.envelope(plan,[],[],[],[],execution="completed",answer="unknown")
        with patch.object(pipeline,"_run",side_effect=result), patch.object(Path,"mkdir",side_effect=OSError("PRIVATE_DISK_DETAIL")):
            report = await pipeline.run("How does memory work?")
        self.assertEqual(report["trace_persistence"],"failed")
        self.assertIn(ErrorCode.STATE_UNAVAILABLE.value,report["diagnostics"])
        self.assertNotIn("PRIVATE_DISK_DETAIL",json.dumps(report))

    async def test_unavailable_model_reports_verified_excerpts_without_claiming_no_evidence(self):
        class UnavailableInference:
            def __init__(self,*args):self.observations=[]
            async def run(self,*args,**kw):raise DeveloperError(ErrorCode.LLM_UNAVAILABLE)
        result = await self.fixture.pipeline(inference_factory=UnavailableInference).run("How does memory work?")
        self.assertEqual(result["execution_status"],"partial")
        self.assertTrue(result["excerpts"])
        self.assertEqual(result["claims"],[])
        self.assertIn("verified source excerpts",result["answer"])

    def test_public_recovery_is_bounded_and_uncertain_never_recommends_replay(self):
        for language in ("ru","en"):
            advice = failure_advice(ErrorCode.TIMEOUT,language,uncertain=True)
            self.assertEqual(advice["action"],"inspect_model_session")
            self.assertFalse(advice["automatic_replay"])
        self.assertIsNone(failure_advice("private arbitrary text"))
