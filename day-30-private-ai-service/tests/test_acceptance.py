"""Stage-8 observers and failure accounting; synthetic engine, never Mac/Qwen proof."""
import asyncio
import contextlib
from datetime import datetime, timezone, timedelta
import io
import json
import ssl
from pathlib import Path
import sys
import tempfile
import unittest

import httpx

from bublik_service.domain import ModelIdentity, ModelProfile, ModelUnavailable
from bublik_service.http_api import HTTPSettings, create_app
from bublik_service.inference.context import TEMPLATE_SHA256
from bublik_service.inference.ollama import Answer, Doctor, InferenceError
from bublik_service.security import SecurityStore, SCOPES
from bublik_service.storage import ChatRepository

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from acceptance_support import API, literal, russian_only, distribution, observed_overlap
from check_acceptance_live import run
from check_recovery_live import run as recovery_run, FORMAT, INTERRUPTION_PROMPT
from check_storage import manifest
from check_prompt_upgrade import run as upgrade_run
from check_http_live import CheckFailed
from resource_observer import cpu_seconds, processes, memory, loaded_models, summary
from browser_fixture import BrowserFixture


class SyntheticQuality:
    profile = ModelProfile()
    def __init__(self, quality_failure=False):
        self.quality_failure, self.calls, self.active, self.peak = quality_failure,0,0,0
        self.available, self.epoch = True,"b"*64
        self.interrupt = asyncio.Event()
        self.complete_instead_of_interrupt = False
    async def doctor(self):
        if not self.available: raise ModelUnavailable()
        return Doctor(ModelIdentity(self.profile.model,"a"*64,TEMPLATE_SHA256,"0.40.2"),self.epoch,(),1)
    async def generate(self,job,checkpoint):
        self.calls += 1
        self.active += 1
        self.peak = max(self.peak,self.active)
        try:
            content = job["context"]["messages"][-1]["content"]
            if content == INTERRUPTION_PROMPT:
                # Production coordinator checkpoints at 256 characters or .25 s.
                await checkpoint("Синтетический сохранённый незавершённый текст. "*8)
                await self.interrupt.wait()
                if self.complete_instead_of_interrupt:
                    return Answer("Синтетический сохранённый незавершённый текст. "*8,
                                  "completed", {"input_tokens": 1, "output_tokens": 80})
                raise InferenceError("model_unavailable",uncertain=True)
            if "Наполнитель" in content:
                answer = "lantern" if self.quality_failure else "OK"
            elif content.startswith("Привет"):
                answer = "Привет! Я могу помочь. 谢谢" if self.quality_failure else "Привет! Я могу помочь с вопросами."
            elif "queue-" in content:
                answer = content.split("queue-")[-1]
                answer = "queue-"+answer
            elif "сапфир" in content or "текущее русское" in content:
                answer = "принято" if content.startswith("Исправление") else "сапфир"
            elif "мандарин" in content or "контрольное слово" in content:
                answer = "запомнил" if content.startswith("Запомни") else "мандарин"
            elif "lantern" in content:
                answer = "remembered"
            elif "English code name" in content or "английск" in content:
                answer = "lantern"
            elif "2 + 2" in content or "2+2" in content:
                answer = "4"
            else:
                answer = "OK"
            await checkpoint(answer)
            await asyncio.sleep(.003)
            return Answer(answer,"completed",{"input_tokens":1,"output_tokens":1,
                "first_token_seconds":.001,"inference_seconds":.003,"load_seconds":0,"tokens_per_second":333.3})
        finally:
            self.active -= 1
    async def aclose(self): pass


class SyntheticObserver:
    def __init__(self,_): self.phase="idle_before"
    async def __aenter__(self): return self
    async def __aexit__(self,*_): pass
    def report(self):
        return {"status":"passed","evidence":"synthetic observer; no macOS measurements"}


class AcceptanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_v1_history_upgrade_check_and_changed_answer_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            app, adapter, token, pause = await self.fixture(tmp)
            adapter.profile = ModelProfile(prompt_version="private-chat-v1")
            baseline = {"format": "bublik-stage8-acceptance-live-v1", "run_id": "old-prompt",
                        "source_sha256": {"historical_source": "explicit_version_upgrade"}, "checks": []}
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="https://localhost:8000",
                                            headers={"Authorization":"Bearer "+token}) as client:
                    with contextlib.redirect_stdout(io.StringIO()):
                        await run(client, baseline, observer_factory=SyntheticObserver, pause=pause, poll_interval=.001)
            adapter.profile = ModelProfile()
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="https://localhost:8000",
                                            headers={"Authorization":"Bearer "+token}) as client:
                    calls = adapter.calls
                    report = {"checks": []}
                    await upgrade_run(client, baseline, report, pause=pause)
                    self.assertFalse(report["baseline_sources_match_current"])
                    self.assertEqual(len(report["old_generations"]), 16)
                    self.assertTrue(all(c["passed"] for c in report["checks"]))
                    baseline["generations"][0]["answer"] = "wrong synthetic reference"
                    with self.assertRaises(CheckFailed) as caught:
                        await upgrade_run(client, baseline, {"checks": []}, pause=pause)
                    self.assertTrue(caught.exception.name.startswith("old_generation_unchanged_"))
                    self.assertEqual(adapter.calls, calls)

    async def fixture(self, directory, quality_failure=False):
        repo = ChatRepository(Path(directory)/"chats.sqlite3")
        owner = repo.create_user("stage8-test","disabled:synthetic")
        clock = [100000.0]
        security = SecurityStore(repo,clock=lambda:clock[0])
        token = security.issue_token(owner,"stage8 synthetic",SCOPES)["token"]
        adapter = SyntheticQuality(quality_failure)
        app = create_app(HTTPSettings(repo.database.path,origins=("https://localhost:8000",)),
                         repository=repo,security=security,adapter_factory=lambda:adapter)
        async def pause(seconds):
            clock[0] += seconds
            await asyncio.sleep(0)
        return app,adapter,token,pause

    async def test_actual_sqlite_http_suite_and_quality_failure_remains_visible(self):
        for failure in (False,True):
            with tempfile.TemporaryDirectory() as tmp:
                app,adapter,token,pause = await self.fixture(tmp,failure)
                report = {"run_id":"synthetic-stage8","source_sha256":manifest(),"checks":[]}
                async with app.router.lifespan_context(app):
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="https://localhost:8000",
                                                headers={"Authorization":"Bearer "+token}) as client:
                        with contextlib.redirect_stdout(io.StringIO()):
                            await run(client,report,observer_factory=SyntheticObserver,pause=pause,poll_interval=.001)
                            calls = adapter.calls
                            history = {"run_id":"history","source_sha256":manifest(),"checks":[]}
                            await run(client,history,history_from=report,pause=pause)
                        self.assertEqual(adapter.calls,calls)
                        self.assertEqual(history["technical_status"],"passed")
                self.assertEqual(report["technical_status"],"passed")
                self.assertEqual(report["quality_status"],"failed" if failure else "passed")
                self.assertEqual(len(report["generations"]),16)
                self.assertEqual(len(report["chats"]),7)
                self.assertEqual(adapter.peak,1)
                self.assertEqual(report["actual_generation_interval_overlap_max"],1)
                self.assertEqual(report["rate_limit"]["scope"],"http_owner_120_per_minute")
                self.assertTrue(all(c["passed"] for c in report["checks"]))
                self.assertEqual(report["latency"]["n"],16)
                self.assertNotIn(token,json.dumps(report))
                if failure:
                    self.assertFalse(next(q["passed"] for q in report["quality"] if q["case"]=="long_a"))

    async def test_post_ambiguity_not_retried_and_429_reuses_exact_request(self):
        calls = []
        def broken(request):
            calls.append(request)
            raise httpx.ReadError("secret must never be copied into reports")
        report = {}
        async with httpx.AsyncClient(transport=httpx.MockTransport(broken),base_url="https://localhost:8000") as client:
            api = API(client,report)
            with self.assertRaises(httpx.ReadError):
                await api.request("POST","/chats",json={"title":"test"},headers={"Idempotency-Key":"same"})
        self.assertEqual(len(calls),1)
        calls.clear()
        def quota(request):
            calls.append((request.content,request.headers["idempotency-key"]))
            return httpx.Response(429,headers={"Retry-After":"1"},json={"error":{"code":"rate_limit_exceeded"}}) if len(calls)==1 else httpx.Response(201,json={"chat_id":"a"*32})
        async def pause(_): pass
        async with httpx.AsyncClient(transport=httpx.MockTransport(quota),base_url="https://localhost:8000") as client:
            r = await API(client,{},quota_pause=pause).request("POST","/chats",json={"title":"test"},headers={"Idempotency-Key":"same"})
        self.assertEqual(r.status_code,201)
        self.assertEqual(calls[0],calls[1])

    async def test_resource_failure_never_becomes_technical_success(self):
        class FailedObserver(SyntheticObserver):
            def report(self): return {"status":"failed","errors":[{"code":"synthetic_observation_failure"}]}
        with tempfile.TemporaryDirectory() as tmp:
            app,adapter,token,pause = await self.fixture(tmp)
            report = {"run_id":"failed-observer","checks":[]}
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="https://localhost:8000",
                                            headers={"Authorization":"Bearer "+token}) as client:
                    with contextlib.redirect_stdout(io.StringIO()):
                        with self.assertRaises(CheckFailed):
                            await run(client,report,observer_factory=FailedObserver,pause=pause,poll_interval=.001)
            self.assertNotEqual(report.get("technical_status"),"passed")
            self.assertEqual(report["resources"]["status"],"failed")
            self.assertEqual(len(report["generations"]),16)

    async def test_acceptance_workload_over_actual_certificate_verified_tls(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Existing fixture owns its isolated DB/socket and suppresses access logs.
            fixture = await asyncio.to_thread(BrowserFixture,tmp)
            try:
                synthetic = SyntheticQuality()
                fixture.adapter.generate = synthetic.generate
                clock = [100000.0]
                fixture.auth.clock = lambda:clock[0]
                token = fixture.auth.issue_token(fixture.owner,"TLS synthetic stage8",SCOPES)["token"]
                async def pause(seconds):
                    clock[0] += seconds
                    await asyncio.sleep(0)
                report={"run_id":"tls-synthetic","checks":[]}
                async with httpx.AsyncClient(base_url=fixture.url,verify=ssl.create_default_context(cafile=str(fixture.cert)),
                                            trust_env=False,headers={"Authorization":"Bearer "+token}) as client:
                    with contextlib.redirect_stdout(io.StringIO()):
                        await run(client,report,observer_factory=SyntheticObserver,pause=pause,poll_interval=.005)
                self.assertEqual(report["technical_status"],"passed")
                self.assertEqual(report["quality_status"],"passed")
                self.assertEqual(synthetic.calls,16)
                self.assertNotIn(token,json.dumps(report))
                self.assertEqual(sum(c["message_count"] for c in report["chats"]),32)
            finally:
                await asyncio.to_thread(fixture.close)

    async def test_recovery_real_sqlite_partial_gate_epoch_and_no_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            app,adapter,token,pause = await self.fixture(tmp)
            def report(phase):
                return {"format":FORMAT,"phase":phase,"run_id":"recovery-"+phase,"url":"https://localhost:8000",
                        "source_sha256":manifest(),"checks":[]}
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="https://localhost:8000",
                                            headers={"Authorization":"Bearer "+token}) as client:
                    with contextlib.redirect_stdout(io.StringIO()):
                        before = report("prepare")
                        await recovery_run(client,before,"prepare",pause=pause,poll_interval=.001)
                        self.assertEqual(before["challenge"]["interruption_prompt"],INTERRUPTION_PROMPT)
                        self.assertEqual(before["observed_generation"]["status"],"running")
                        adapter.available = False
                        adapter.interrupt.set()
                        await asyncio.sleep(.03)
                        app.state.ready_cache = None
                        middle = report("interrupted")
                        await recovery_run(client,middle,"interrupted",before,pause=pause,poll_interval=.001)
                        self.assertTrue(app.state.repository.queue_status()["inference_recovery_required"])
                        adapter.available = True
                        adapter.epoch = "c"*64
                        app.state.ready_cache = None
                        await app.state.coordinator.recover_after_restart()
                        after = report("restored")
                        await recovery_run(client,after,"restored",middle,pause=pause,poll_interval=.001)
                        wrong = {**middle,"source_sha256":{}}
                        with self.assertRaises(CheckFailed):
                            await recovery_run(client,report("restored"),"restored",wrong,pause=pause)
                    self.assertEqual(adapter.calls,3)
                    self.assertEqual(after["saved_history"],middle["saved_history"])
                    self.assertFalse(app.state.repository.queue_status()["inference_recovery_required"])
                    self.assertTrue(all(c["passed"] for r in (before,middle,after) for c in r["checks"]))

    async def test_completed_control_is_not_interruption_and_failure_keeps_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            app,adapter,token,pause = await self.fixture(tmp)
            def report(phase):
                return {"format":FORMAT,"phase":phase,"run_id":"completed-"+phase,
                        "url":"https://localhost:8000","source_sha256":manifest(),"checks":[]}
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="https://localhost:8000",
                                            headers={"Authorization":"Bearer "+token}) as client:
                    with contextlib.redirect_stdout(io.StringIO()):
                        before = report("prepare")
                        await recovery_run(client,before,"prepare",pause=pause,poll_interval=.001)
                        adapter.complete_instead_of_interrupt = True
                        adapter.interrupt.set()
                        middle = report("interrupted")
                        with self.assertRaises(CheckFailed) as failure:
                            await recovery_run(client,middle,"interrupted",before,pause=pause,poll_interval=.001)
                    self.assertEqual(failure.exception.name,"interrupted_terminal_status")
                    observed = middle["observed_generation"]
                    self.assertEqual(observed["status"],"completed")
                    self.assertEqual(observed["generation_id"],before["challenge"]["generation_id"])
                    self.assertEqual(observed["metrics"]["output_tokens"],80)
                    self.assertEqual(observed["saved_characters"],len(observed["control_answer"]))
                    self.assertIsNotNone(observed["finished_at"])
                    self.assertNotIn(token,json.dumps(middle))
                    self.assertNotIn("saved_history",middle)
                    self.assertFalse(app.state.repository.queue_status()["inference_recovery_required"])

    def test_mac_parsers_cpu_units_topology_and_no_other_process_names(self):
        self.assertAlmostEqual(cpu_seconds("1:02.50"),62.5)
        self.assertEqual(cpu_seconds("1-02:03:04"),93784)
        vm='Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 100.\nPages inactive: 200.\nPages occupied by compressor: 30.\n'
        mem=memory(vm,"total = 1024.00M used = 10.00M free = 1014.00M (encrypted)","34359738368\n")
        self.assertEqual(mem["free_bytes"],1638400)
        self.assertEqual(mem["swap"]["used_bytes"],10*1024**2)
        rows=processes("10 1 100 0:01.00 /private/API\n20 1 200 0:02.00 ollama\n21 20 300 0:00.50 /Applications/ollama_llama_server\n99 1 7 0:00.00 PRIVATE_OTHER_PROCESS\n",10,20)
        self.assertEqual(len(rows),3)
        self.assertNotIn("PRIVATE_OTHER_PROCESS",json.dumps(rows))
        self.assertEqual(rows[0]["rss_bytes"],102400)
        samples=[{"elapsed_seconds":0,"memory":mem,"processes":rows,"loaded":[]},
                 {"elapsed_seconds":2,"memory":mem,"processes":[{**r,"cpu_seconds":r["cpu_seconds"]+1} for r in rows],"loaded":[]}]
        result=summary(samples)
        self.assertEqual(result["api_interval_cpu_sampled_max_percent"],50)
        self.assertEqual(result["ollama_family_interval_cpu_sampled_max_percent"],100)
        self.assertIsNone(result["reported_size_vram_sampled_max_bytes"])
        with self.assertRaises(ValueError): processes("10 1 100 0:01.00 api\n20 1 200 0:01.00 ollama\n21 1 20 0:00.00 llama-server",10,20)
        with self.assertRaises(ValueError): memory(vm,"invalid", "32")
        with self.assertRaises(ValueError): loaded_models({"models":[{"name":"private","digest":"a"*64}]},{"model":"qwen2.5:14b","digest":"a"*64})

    def test_small_sample_metrics_language_and_overlap_failure(self):
        self.assertEqual(distribution([3,1,2])["p95_nearest_rank"],3)
        self.assertEqual(distribution([])["n"],0)
        self.assertTrue(russian_only("Привет!"))
        self.assertFalse(russian_only("Привет! 谢谢"))
        self.assertTrue(literal("OK\n","ok"))
        self.assertFalse(literal("OK. extra","ok"))
        start=datetime.now(timezone.utc)
        g={"started_at":start.isoformat(),"finished_at":(start+timedelta(seconds=2)).isoformat()}
        self.assertEqual(observed_overlap([g,g]),2)
        with self.assertRaises(ValueError):observed_overlap([{"started_at":None}])
