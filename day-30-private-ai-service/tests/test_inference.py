"""Synthetic protocol fixture over real loopback HTTP. NEVER evidence of real Qwen."""
import asyncio
from dataclasses import asdict
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import subprocess
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import sys

import httpx

from bublik_service.domain import Conflict, InvalidInput, ModelIdentity, ModelProfile, ModelUnavailable, NotFound
from bublik_service.inference.context import ContextBuilder, TEMPLATE_SHA256, upper_bound
from bublik_service.inference.coordinator import Coordinator
from bublik_service.inference.engine import engine_epoch, MAX_PROCESS_TABLE_CHARACTERS, PROCESS_TABLE_COMMAND
from bublik_service.inference.ollama import OllamaAdapter
from bublik_service.storage import ChatRepository

FAKE_TEMPLATE = "synthetic-test-template-not-a-real-model"
FAKE_SHA = hashlib.sha256(FAKE_TEMPLATE.encode()).hexdigest()
DIGEST = "a" * 64


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def json_response(self, value, status=200):
        encoded = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.server.offline:
            return self.json_response({"error": "PRIVATE SECRET"}, 503)
        if self.path == "/api/version":
            return self.json_response({"version": "0.12.3"})
        if self.path == "/api/tags":
            return self.json_response({"models": [{"name": "qwen2.5:14b", "digest": self.server.digest, "size": 9_000_000_000}]})
        if self.path == "/api/ps":
            models = [{"name": "qwen2.5:14b", "digest": self.server.digest, "context_length": 8192, "size_vram": 9_000_000_000}] if self.server.loaded else []
            if self.server.foreign:
                models.append({"name": "bge-m3", "digest": "c" * 64})
            return self.json_response({"models": models})
        return self.json_response({}, 404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/api/show":
            return self.json_response({"template": self.server.template, "parameters": "stop im_end",
                "remote_host": "https://forbidden.example" if self.server.remote else None,
                "details": {"family": "qwen2", "format": "gguf", "quantization_level": "Q4_K_M", "parameter_size": "14.8B"},
                "model_info": {"general.architecture": "qwen2", "tokenizer.ggml.model": "gpt2",
                               "tokenizer.ggml.pre": "qwen2", "qwen2.context_length": 32768}})
        if self.path != "/api/chat":
            return self.json_response({}, 404)
        self.server.requests.append(body)
        self.server.loaded = True
        with self.server.guard:
            self.server.active += 1
            self.server.maximum = max(self.server.maximum, self.server.active)
        mode = self.server.mode
        first = {"model": "qwen2.5:14b", "done": False, "message": {"role": "assistant", "content": "Часть "}}
        final = {"model": "qwen2.5:14b", "done": True, "done_reason": "length" if mode == "length" else "stop",
                 "message": {"role": "assistant", "content": body["messages"][-1]["content"][:32]},
                 "prompt_eval_count": 12, "eval_count": 10, "eval_duration": 100_000_000, "load_duration": 0}
        if mode == "counter":
            final["prompt_eval_count"] = 100_000
        if mode == "output":
            final["eval_count"] = 1025
        if mode == "nan":
            final["eval_duration"] = float("nan")
        if mode == "tools":
            first["message"]["tool_calls"] = [{"name": "not-allowed"}]
        raw1 = json.dumps(first, ensure_ascii=False).encode() + b"\n"
        raw2 = (b"not-json\n" if mode == "malformed" else b"" if mode == "eof" else json.dumps(final, ensure_ascii=False).encode() + b"\n")
        if mode == "no-newline":
            raw2 = raw2.rstrip(b"\n")
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Content-Length", str(len(raw1) + len(raw2)))
            self.end_headers()
            self.wfile.write(raw1)
            self.wfile.flush()
            time.sleep(.15 if mode == "timeout" else .01)
            if mode == "switch":
                self.server.digest = "b" * 64
            self.wfile.write(raw2)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with self.server.guard:
                self.server.active -= 1


class ContextBuilderTests(unittest.TestCase):
    def setUp(self):
        self.profile = ModelProfile()
        self.builder = ContextBuilder(self.profile, ModelIdentity("qwen2.5:14b", DIGEST, TEMPLATE_SHA256, "0.12.3"))

    def test_real_byte_bound_handles_unicode_and_control_overhead(self):
        en = self.builder.build({"messages": []}, "hi")
        ru = self.builder.build({"messages": []}, "ёж")
        self.assertEqual(ru.input_token_upper_bound - en.input_token_upper_bound, 2)
        self.assertGreater(en.input_token_upper_bound, len("hi"))

    def test_complete_suffix_is_bounded_without_mutating_candidates(self):
        messages = [{"id": str(i), "role": "user" if i % 2 == 0 else "assistant", "content": "x" * 900} for i in range(12)]
        original = json.dumps(messages)
        plan = self.builder.build({"messages": messages}, "current")
        self.assertEqual(len(plan.history_message_ids) % 2, 0)
        self.assertTrue(plan.history_message_ids)
        self.assertLess(len(plan.history_message_ids), 12)
        self.assertEqual(plan.history_message_ids, tuple(m["id"] for m in messages[-len(plan.history_message_ids):]))
        self.assertEqual(json.dumps(messages), original)

    def test_one_oversized_question_is_rejected_before_inference(self):
        with self.assertRaises(InvalidInput) as caught:
            self.builder.build({"messages": []}, "x" * 7000)
        self.assertEqual(caught.exception.code, "context_budget_exceeded")

    def test_unknown_template_cannot_be_selected(self):
        with self.assertRaises(InvalidInput):
            ContextBuilder(self.profile, ModelIdentity("qwen2.5:14b", DIGEST, "b" * 64, "0.12.3"))


class EngineWitnessTests(unittest.TestCase):
    def process_table(self):
        # Long executable paths are normal on macOS. Put runner information
        # after 64 KiB so these checks also prevent an unsafe truncation fix.
        noise = "\n".join(f"{pid} 1 /Applications/" + "x" * 100 + "/fixture"
                          for pid in range(1000, 1688))
        return noise + "\n42 1 /usr/local/bin/ollama\n43 42 /usr/local/bin/ollama"

    def command_result(self, args, **kwargs):
        output = self.process_table() if tuple(args) == PROCESS_TABLE_COMMAND else self.output(args)
        return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")

    def test_mac_sized_process_table_is_verified_without_truncation(self):
        self.assertGreater(len(self.process_table()), 65536)
        with patch("bublik_service.inference.engine.subprocess.run", side_effect=self.command_result):
            self.assertEqual(len(engine_epoch(11434)), 64)

    def test_orphan_after_original_output_limit_still_blocks_witness(self):
        def result(args, **kwargs):
            value = self.command_result(args, **kwargs)
            if tuple(args) == PROCESS_TABLE_COMMAND:
                value.stdout += "\n44 1 /usr/local/bin/ollama_llama_server"
            return value
        with patch("bublik_service.inference.engine.subprocess.run", side_effect=result), self.assertRaises(ModelUnavailable) as caught:
            engine_epoch(11434)
        self.assertEqual(caught.exception.code, "orphan_or_other_ollama_process")

    def test_process_table_allowance_does_not_remove_failure_limits(self):
        from bublik_service.inference.engine import _command
        for args, output in ((list(PROCESS_TABLE_COMMAND), "x" * (MAX_PROCESS_TABLE_CHARACTERS + 1)),
                             (["ps", "-p", "42", "-o", "uid="], "x" * 65537)):
            with self.subTest(args=args), patch("bublik_service.inference.engine.subprocess.run",
                    return_value=subprocess.CompletedProcess(args, 0, stdout=output, stderr="")), self.assertRaises(ModelUnavailable):
                _command(args)
        with patch("bublik_service.inference.engine.subprocess.run",
                return_value=subprocess.CompletedProcess(list(PROCESS_TABLE_COMMAND), 1, stdout="", stderr="error")), self.assertRaises(ModelUnavailable):
            _command(list(PROCESS_TABLE_COMMAND))
        with patch("bublik_service.inference.engine.subprocess.run",
                side_effect=subprocess.TimeoutExpired(list(PROCESS_TABLE_COMMAND), 3)), self.assertRaises(ModelUnavailable):
            _command(list(PROCESS_TABLE_COMMAND))

    def output(self, args):
        if args[0] == "lsof":
            return "p42\ncollama\nn127.0.0.1:11434"
        if args[-1] == "pid=,ppid=,comm=":
            return "42 1 /usr/local/bin/ollama\n43 42 /usr/local/bin/ollama"
        return str(__import__("os").getuid()) if args[-1] == "uid=" else "Fri Oct 9 20:00:00 2026"

    def test_process_start_time_changes_epoch_without_trusting_api_ps(self):
        with patch("bublik_service.inference.engine._command", side_effect=self.output):
            before = engine_epoch(11434)
        def after(args):
            return self.output(args) if args[-1] != "lstart=" else "Fri Oct 9 20:01:00 2026"
        with patch("bublik_service.inference.engine._command", side_effect=after):
            self.assertNotEqual(before, engine_epoch(11434))

    def test_wildcard_and_non_ollama_listener_are_rejected(self):
        for raw in ("p42\ncollama\nn*:11434", "p42\ncfixture\nn127.0.0.1:11434", "p42\ncollama\nn192.168.1.2:11434"):
            with patch("bublik_service.inference.engine._command", return_value=raw), self.assertRaises(ModelUnavailable):
                engine_epoch(11434)

    def test_orphan_runner_blocks_recovery_witness(self):
        def orphan(args):
            return "42 1 ollama\n43 1 ollama" if args[-1] == "pid=,ppid=,comm=" else self.output(args)
        with patch("bublik_service.inference.engine._command", side_effect=orphan), self.assertRaises(ModelUnavailable) as caught:
            engine_epoch(11434)
        self.assertEqual(caught.exception.code, "orphan_or_other_ollama_process")


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        for module in ("bublik_service.inference.ollama", "bublik_service.inference.context"):
            self.enterContext(patch(module + ".TEMPLATE_SHA256", FAKE_SHA))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = ChatRepository(Path(self.tmp.name) / "chat.sqlite3")
        self.owner = self.repo.create_user("fixture", "disabled:fixture")
        self.other = self.repo.create_user("other", "disabled:fixture")
        self.chat = self.repo.create_chat(self.owner, key="chat").chat_id
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.server.mode = "normal"
        self.server.digest, self.server.template = DIGEST, FAKE_TEMPLATE
        self.server.remote = self.server.foreign = self.server.loaded = self.server.offline = False
        self.server.active = self.server.maximum = 0
        self.server.guard, self.server.requests = threading.Lock(), []
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=.01), daemon=True)
        self.thread.start()
        self.epoch = "e" * 64
        self.adapter = OllamaAdapter(url=f"http://127.0.0.1:{self.server.server_port}", epoch_probe=lambda _: self.epoch)

    async def asyncTearDown(self):
        await self.adapter.aclose()
        await asyncio.to_thread(self.server.shutdown)
        self.server.server_close()
        self.thread.join(1)

    async def send(self, coordinator, content="Привет", *, chat=None, key="send", revision=None):
        chat = chat or self.chat
        revision = self.repo.get_chat(self.owner, chat)["revision"] if revision is None else revision
        return await coordinator.service.send(self.owner, chat, content, expected_revision=revision, key=key)

    async def test_doctor_records_local_digest_template_and_rejects_remote(self):
        info = await self.adapter.doctor()
        self.assertEqual(info.identity.digest, DIGEST)
        self.assertEqual(info.engine_epoch, self.epoch)
        self.server.remote = True
        with self.assertRaises(ModelUnavailable) as caught:
            await self.adapter.doctor()
        self.assertEqual(caught.exception.code, "remote_model_forbidden")

    async def test_prompt_upgrade_preserves_queued_job_and_old_snapshots(self):
        from bublik_service.service import ChatService
        new_profile = self.adapter.profile
        self.adapter.profile = ModelProfile(prompt_version="private-chat-v1")
        old = await ChatService(self.repo, self.adapter).send(
            self.owner, self.chat, "Old question", expected_revision=0, key="old-prompt")
        before = self.repo.get_generation(self.owner, old.generation_id)
        self.adapter.profile = new_profile
        with self.assertRaises(Conflict) as caught:
            async with Coordinator(self.repo, self.adapter):
                self.fail("must not claim an old-profile queued job")
        self.assertEqual(caught.exception.code, "queued_profile_mismatch")
        self.assertEqual(self.repo.get_generation(self.owner, old.generation_id), before)
        self.assertEqual(self.server.requests, [])
        self.adapter.profile = ModelProfile(prompt_version="private-chat-v1")
        async with Coordinator(self.repo, self.adapter) as coordinator:
            completed = await coordinator.wait(self.owner, old.generation_id)
            self.assertEqual(completed["status"], "completed")
        self.adapter.profile = new_profile
        async with Coordinator(self.repo, self.adapter) as coordinator:
            replay = await coordinator.service.send(self.owner, self.chat, "Old question",
                                                     expected_revision=0, key="old-prompt")
            self.assertTrue(replay.replayed)
            self.assertEqual(replay.generation_id, old.generation_id)
            new = await self.send(coordinator, "New question", key="new-prompt")
            upgraded = await coordinator.wait(self.owner, new.generation_id)
        self.assertEqual(self.repo.get_generation(self.owner, old.generation_id), completed)
        self.assertEqual(completed["profile"]["prompt_version"], "private-chat-v1")
        self.assertEqual(upgraded["profile"]["prompt_version"], "private-chat-v2")
        self.assertEqual(upgraded["context"]["history_message_ids"],
                         [old.user_message_id, old.assistant_message_id])
        for result, request in zip([completed, upgraded], self.server.requests):
            self.assertEqual(result["context"]["messages"], request["messages"])
            self.assertEqual(result["context"]["messages"][0]["content"],
                             ModelProfile(**result["profile"]).system_prompt)
            from bublik_service.inference.context import upper_bound
            self.assertEqual(upper_bound(request["messages"]), result["context"]["input_token_upper_bound"])
        self.assertEqual(len(self.repo.history(self.owner, self.chat)), 4)

    async def test_wrong_prompt_bytes_are_rejected_before_inference_dispatch(self):
        from dataclasses import asdict
        from bublik_service.inference.context import upper_bound
        from bublik_service.inference.ollama import InferenceError
        info = await self.adapter.doctor()
        messages = [{"role": "system", "content": ModelProfile(prompt_version="private-chat-v1").system_prompt},
                    {"role": "user", "content": "Question"}]
        job = {"profile": self.adapter.profile.to_dict(), "context": {
            "messages": messages, "model_identity": asdict(info.identity),
            "input_token_upper_bound": upper_bound(messages)}}
        async def chunk(_): self.fail("no partial response expected")
        with self.assertRaises(InferenceError) as caught:
            await self.adapter.generate(job, chunk)
        self.assertFalse(caught.exception.uncertain)
        self.assertEqual(self.server.requests, [])

    async def test_unknown_template_and_foreign_loaded_model_fail_closed(self):
        self.server.template = "changed"
        with self.assertRaises(ModelUnavailable) as caught:
            await self.adapter.doctor()
        self.assertEqual(caught.exception.code, "unsupported_template")
        self.server.template, self.server.foreign = FAKE_TEMPLATE, True
        with self.assertRaises(ModelUnavailable) as caught:
            await self.adapter.doctor()
        self.assertEqual(caught.exception.code, "unexpected_loaded_model")
        self.assertEqual(self.server.requests, [])

    async def test_two_turns_persist_options_context_and_metrics(self):
        async with Coordinator(self.repo, self.adapter) as coordinator:
            first = await self.send(coordinator)
            result = await coordinator.wait(self.owner, first.generation_id)
            self.assertEqual(result["status"], "completed")
            second = await self.send(coordinator, "Continue", key="second")
            await coordinator.wait(self.owner, second.generation_id)
        body = self.server.requests[1]
        self.assertEqual([m["role"] for m in body["messages"]], ["system", "user", "assistant", "user"])
        self.assertEqual(body["options"], {"temperature": 0, "num_predict": 1024, "num_ctx": 8192})
        self.assertEqual(result["context"]["model_identity"]["digest"], DIGEST)
        self.assertEqual(result["context"]["dispatch_engine_epoch"], self.epoch)
        self.assertEqual(result["metrics"]["input_tokens"], 12)
        self.assertGreaterEqual(result["metrics"]["queue_seconds"], 0)
        self.assertEqual(len(ChatRepository(self.repo.database.path).history(self.owner, self.chat)), 4)

    async def test_three_concurrent_admissions_have_one_inference(self):
        chats = [self.chat] + [self.repo.create_chat(self.owner, key=f"chat{i}").chat_id for i in range(2)]
        async with Coordinator(self.repo, self.adapter) as coordinator:
            receipts = await asyncio.gather(*(self.send(coordinator, chat=chat, key=f"send{i}") for i, chat in enumerate(chats)))
            results = await asyncio.gather(*(coordinator.wait(self.owner, r.generation_id) for r in receipts))
            self.assertEqual(coordinator.max_active, 1)
        self.assertEqual(self.server.maximum, 1)
        self.assertTrue(all(r["status"] == "completed" for r in results))

    async def test_replay_does_not_require_model_and_ownership_precedes_doctor(self):
        async with Coordinator(self.repo, self.adapter) as coordinator:
            first = await self.send(coordinator)
            await coordinator.wait(self.owner, first.generation_id)
            self.server.offline = True
            replay = await self.send(coordinator, revision=0)
            self.assertTrue(replay.replayed)
            self.assertEqual(replay.generation_id, first.generation_id)
            with self.assertRaises(NotFound):
                await coordinator.service.send(self.other, self.chat, "private", expected_revision=0, key="foreign")
        self.assertEqual(len(self.server.requests), 1)

    async def test_oversized_context_never_saves_or_posts(self):
        async with Coordinator(self.repo, self.adapter) as coordinator:
            with self.assertRaises(InvalidInput) as caught:
                await self.send(coordinator, "x" * 7000)
            self.assertEqual(caught.exception.code, "context_budget_exceeded")
        self.assertEqual(self.repo.history(self.owner, self.chat), [])
        self.assertEqual(self.server.requests, [])

    async def test_eof_preserves_partial_and_requires_verified_restart(self):
        self.server.mode = "eof"
        async with Coordinator(self.repo, self.adapter) as coordinator:
            receipt = await self.send(coordinator)
            result = await coordinator.wait(self.owner, receipt.generation_id)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["assistant"]["content"], "Часть ")
            self.assertTrue(self.repo.queue_status()["inference_recovery_required"])
            with self.assertRaises(Conflict) as caught:
                await coordinator.recover_after_restart()
            self.assertEqual(caught.exception.code, "ollama_restart_required")
            self.epoch, self.server.mode = "f" * 64, "normal"
            await coordinator.recover_after_restart()
            retry = await coordinator.service.retry(self.owner, receipt.user_message_id, expected_revision=2, key="retry")
            second = await coordinator.wait(self.owner, retry.generation_id)
            self.assertEqual(second["status"], "completed")
        self.assertEqual(sum(m["role"] == "user" for m in self.repo.history(self.owner, self.chat)), 1)

    async def test_malformed_stream_is_safe_and_not_automatically_retried(self):
        self.server.mode = "malformed"
        async with Coordinator(self.repo, self.adapter) as coordinator:
            receipt = await self.send(coordinator)
            result = await coordinator.wait(self.owner, receipt.generation_id)
            self.assertEqual(result["error_code"], "invalid_model_response")
        self.assertEqual(len(self.server.requests), 1)
        self.assertTrue(self.repo.queue_status()["inference_recovery_required"])

    async def test_total_deadline_records_timeout_and_preserves_partial(self):
        self.server.mode, self.adapter.deadline = "timeout", .05
        async with Coordinator(self.repo, self.adapter) as coordinator:
            receipt = await self.send(coordinator)
            result = await coordinator.wait(self.owner, receipt.generation_id)
            self.assertEqual(result["error_code"], "model_timeout")
            self.assertTrue(self.repo.queue_status()["inference_recovery_required"])

    async def test_length_is_truncated_and_not_part_of_next_context(self):
        self.server.mode = "length"
        async with Coordinator(self.repo, self.adapter) as coordinator:
            receipt = await self.send(coordinator)
            self.assertEqual((await coordinator.wait(self.owner, receipt.generation_id))["status"], "truncated")
        self.assertEqual(self.repo.context_candidates(self.owner, self.chat)["messages"], [])

    async def test_actual_token_or_output_counter_overflow_never_completes(self):
        for index, mode in enumerate(("counter", "output")):
            self.server.mode = mode
            chat = self.repo.create_chat(self.owner, key=f"budget{index}").chat_id
            async with Coordinator(self.repo, self.adapter) as coordinator:
                receipt = await self.send(coordinator, chat=chat, key=mode)
                result = await coordinator.wait(self.owner, receipt.generation_id)
                self.assertEqual((result["status"], result["error_code"]), ("failed", "invalid_model_response"))
            self.assertFalse(self.repo.queue_status()["inference_recovery_required"])

    async def test_model_digest_drift_does_not_publish_success(self):
        self.server.mode = "switch"
        async with Coordinator(self.repo, self.adapter) as coordinator:
            receipt = await self.send(coordinator)
            result = await coordinator.wait(self.owner, receipt.generation_id)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["context"]["model_identity"]["digest"], DIGEST)

    async def test_shutdown_cancels_stream_and_retains_history(self):
        self.server.mode = "timeout"
        coordinator = Coordinator(self.repo, self.adapter, shutdown_grace=.01)
        await coordinator.__aenter__()
        receipt = await self.send(coordinator)
        for _ in range(100):
            if self.server.requests:
                break
            await asyncio.sleep(.005)
        await coordinator.__aexit__(None, None, None)
        result = self.repo.get_generation(self.owner, receipt.generation_id)
        self.assertEqual(result["status"], "interrupted")
        self.assertTrue(self.repo.queue_status()["inference_recovery_required"])
        with self.repo.worker_session():
            pass  # No leaked lease after cancellation.

    async def test_proxy_environment_is_ignored_and_remote_url_is_rejected(self):
        with patch.dict("os.environ", {"HTTP_PROXY": "http://127.0.0.1:1", "ALL_PROXY": "http://127.0.0.1:1"}):
            client = OllamaAdapter(url=self.adapter.url, epoch_probe=lambda _: self.epoch)
            try:
                await client.doctor()
            finally:
                await client.aclose()
        for url in ("https://127.0.0.1:11434", "http://localhost:11434", "http://192.168.1.1:11434", "http://u:p@127.0.0.1:11434"):
            with self.assertRaises(InvalidInput):
                OllamaAdapter(url=url)

    async def test_unavailable_model_rejects_new_message_but_history_remains(self):
        self.server.offline = True
        async with Coordinator(self.repo, self.adapter) as coordinator:
            with self.assertRaises(ModelUnavailable) as caught:
                await self.send(coordinator)
            self.assertNotIn("PRIVATE SECRET", str(caught.exception))
            self.assertEqual(self.repo.history(self.owner, self.chat), [])
        self.assertEqual(self.server.requests, [])

    async def test_terminal_record_without_final_newline_is_accepted(self):
        self.server.mode = "no-newline"
        async with Coordinator(self.repo, self.adapter) as coordinator:
            receipt = await self.send(coordinator)
            self.assertEqual((await coordinator.wait(self.owner, receipt.generation_id))["status"], "completed")

    async def test_nan_metrics_and_unrequested_tools_cannot_complete(self):
        for i, mode in enumerate(("nan", "tools")):
            self.server.mode = mode
            chat = self.repo.create_chat(self.owner, key=f"invalid{i}").chat_id
            async with Coordinator(self.repo, self.adapter) as coordinator:
                receipt = await self.send(coordinator, chat=chat, key=f"invalid{i}")
                self.assertEqual((await coordinator.wait(self.owner, receipt.generation_id))["status"], "failed")

    async def test_legacy_stage2_queued_job_is_preserved_but_not_inferred(self):
        from bublik_service.domain import ContextPlan
        receipt = self.repo.accept_message(self.owner, self.chat, "Legacy question", expected_revision=0,
                                           key="legacy", context=ContextPlan(input_token_upper_bound=100))
        async with Coordinator(self.repo, self.adapter) as coordinator:
            result = await coordinator.wait(self.owner, receipt.generation_id)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(self.server.requests, [])
            self.assertEqual(self.repo.history(self.owner, self.chat)[0]["content"], "Legacy question")
            retry = await coordinator.service.retry(self.owner, receipt.user_message_id, expected_revision=2, key="new-profile")
            self.assertEqual((await coordinator.wait(self.owner, retry.generation_id))["status"], "completed")

    async def test_crash_before_dispatch_can_recover_without_restart(self):
        from bublik_service.service import ChatService
        service = ChatService(self.repo, self.adapter)
        receipt = await service.send(self.owner, self.chat, "No POST", expected_revision=0, key="undispatched")
        with self.repo.worker_session() as worker:
            worker.claim_next()
        async with Coordinator(self.repo, self.adapter) as coordinator:
            self.assertEqual((await coordinator.recover_after_restart())["recovery"], "verified_no_dispatch")
        self.assertEqual(self.server.requests, [])
        self.assertEqual(self.repo.get_generation(self.owner, receipt.generation_id)["status"], "interrupted")

    async def test_live_harness_preserves_observations_but_fixture_fails_quality(self):
        scripts = str(Path(__file__).resolve().parents[1] / "scripts")
        sys.path.insert(0, scripts)
        try:
            from check_inference_live import run_live
            repository = ChatRepository(Path(self.tmp.name) / "live-fixture.sqlite3")
            report = await run_live(self.adapter, repository)
            self.assertEqual(len(report["generations"]), 13)
            self.assertEqual(report["observed_service_max_active"], 1)
            self.assertFalse(all(q["matched"] for q in report["quality"]))
            self.assertTrue(next(c["passed"] for c in report["checks"] if c["name"] == "visible_context_omission"))
        finally:
            sys.path.remove(scripts)

    async def test_arbitrary_tcp_fragmentation_preserves_utf8(self):
        info = await self.adapter.doctor()
        context = ContextBuilder(self.adapter.profile, info.identity).build({"messages": []}, "Привет")
        job = {"profile": self.adapter.profile.to_dict(), "context": {
            "messages": [{"role": "system", "content": self.adapter.profile.system_prompt},
                         {"role": "user", "content": "Привет"}],
            "model_identity": asdict(info.identity), "input_token_upper_bound": context.input_token_upper_bound}}
        payload = json.dumps({"model": "qwen2.5:14b", "done": True, "done_reason": "stop",
            "message": {"role": "assistant", "content": "ёж🙂"}, "prompt_eval_count": 12,
            "eval_count": 3, "eval_duration": 1, "load_duration": 0}, ensure_ascii=False).encode()
        class Bytes(httpx.AsyncByteStream):
            async def __aiter__(self):
                for value in payload:
                    yield bytes([value])
        adapter = OllamaAdapter(transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=Bytes())))
        observed = []
        async def chunk(content):
            observed.append(content)
        try:
            answer = await adapter.generate(job, chunk)
            self.assertEqual(answer.content, "ёж🙂")
            self.assertEqual(observed, ["ёж🙂"])
        finally:
            await adapter.aclose()
