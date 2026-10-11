"""Prompt experiment accounting; synthetic responses, no real Qwen proof."""
import contextlib
import copy
import io
import json
import sys
from pathlib import Path
import unittest

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
from check_prompt_compare import (CANDIDATE_PROMPT, CANDIDATE_VERSION, VARIANTS,
                                  frozen_cases, generate, run, summarize)
from check_http_live import CheckFailed
from check_inference_live import CASES
from check_storage import manifest
from bublik_service.domain import DEFAULT_SYSTEM_PROMPT, ModelIdentity, ModelProfile
from bublik_service.http_api import runtime_manifest
from bublik_service.inference.context import ContextBuilder, TEMPLATE_SHA256
from bublik_service.inference.ollama import Doctor, InferenceError


IDENTITY = ModelIdentity("qwen2.5:14b", "a"*64, TEMPLATE_SHA256, "0.40.2")
ANSWERS = ["запомнил", "мандарин", "remembered", "lantern", "принято", "сапфир", "4", "lantern", "lantern", "OK"]


def baseline():
    builder = ContextBuilder(ModelProfile(prompt_version="private-chat-v1"), IDENTITY)
    history, rows = [], []
    for index, (name, prompt, _) in enumerate(CASES):
        plan = builder.build({"messages": history}, prompt)
        rows.append({"case": name, "status": "completed", "answer": ANSWERS[index],
                     "context": {"input_token_upper_bound": plan.input_token_upper_bound,
                                 "omitted_turns": (len(history)-len(plan.history_message_ids))//2}})
        history.extend([{"id": f"u{index}", "role": "user", "content": prompt},
                        {"id": f"a{index}", "role": "assistant", "content": ANSWERS[index]}])
    rows.extend({"case": f"{name}-{index}", "status": "completed"}
                for name in ["russian-greeting", "concurrent"] for index in range(3))
    return {"format": "bublik-stage8-acceptance-live-v1", "technical_status": "passed",
            "source_sha256": manifest(), "generations": rows,
            "server_before": {"runtime_source_sha256": runtime_manifest(),
                              "profile": ModelProfile(prompt_version="private-chat-v1").to_dict(), "model": {"identity": IDENTITY.__dict__}}}


class Adapter:
    async def doctor(self): return Doctor(IDENTITY, "b"*64, (), 1)


class PromptCompareTests(unittest.IsolatedAsyncioTestCase):
    async def test_frozen_pair_contexts_abba_and_visible_quality_failure(self):
        self.assertEqual(ModelProfile().system_prompt, CANDIDATE_PROMPT)
        for failure in [False, True]:
            bodies = []
            def transport(request):
                body = json.loads(request.content)
                bodies.append(body)
                prompt = body["messages"][-1]["content"]
                candidate = body["messages"][0]["content"] == CANDIDATE_PROMPT
                if prompt.startswith("Привет"):
                    answer = "Привет! 谢谢" if failure and candidate else "Привет! Я могу помочь."
                elif prompt.startswith("Reply only: queue-"):
                    answer = prompt.removeprefix("Reply only: ")
                else:
                    index = next(i for i, c in enumerate(CASES) if c[1] == prompt)
                    answer = "OK" if index == 8 and candidate else ANSWERS[index]
                    if index == 0 and candidate: answer = "Другой синтетический ответ."
                return httpx.Response(200, json={"model": "qwen2.5:14b", "done": True, "done_reason": "stop",
                    "message": {"role": "assistant", "content": answer}, "prompt_eval_count": 1,
                    "eval_count": 2, "eval_duration": 1000000, "load_duration": 0})
            report = {"checks": []}
            async with httpx.AsyncClient(base_url="http://127.0.0.1:11434",transport=httpx.MockTransport(transport)) as client:
                with contextlib.redirect_stdout(io.StringIO()):
                    await run(Adapter(), client, baseline(), report, stopped_probe=lambda: True)
            summarize(report)
            self.assertEqual(len(bodies), 64)
            self.assertEqual(report["technical_status"], "passed")
            self.assertFalse(report["service_prompt_changed"])
            self.assertFalse(report["inference_outcome_unknown"])
            self.assertEqual(report["candidate_quality_status"], "failed" if failure else "passed")
            self.assertEqual(report["comparison"][CANDIDATE_VERSION]["controls"], 26)
            self.assertEqual(report["comparison"]["private-chat-v1"]["failed_cases"], ["long_a"])
            self.assertEqual(report["improvement_observed_cases"], ["long_a"])
            self.assertEqual(report["variant_order"], ["private-chat-v1", CANDIDATE_VERSION, CANDIDATE_VERSION, "private-chat-v1"])
            for index in range(16):
                self.assertTrue(all(bodies[index]["messages"][1:] == bodies[block*16+index]["messages"][1:] for block in range(4)))
            for body in bodies:
                self.assertEqual(body["options"], {"temperature": 0, "num_predict": 1024, "num_ctx": 8192})
                self.assertFalse(body["stream"])
            # A different candidate acknowledgement never becomes a later input.
            self.assertEqual(bodies[16+1]["messages"][-2]["content"], "запомнил")
            self.assertEqual(len(bodies[16+9]["messages"]), 2)  # Original omissions=9.

    async def test_active_api_blocks_dispatch_and_malformed_baseline_is_rejected(self):
        report = {"checks": []}
        async with httpx.AsyncClient(base_url="http://127.0.0.1:11434",trust_env=False) as client:
            with self.assertRaises(CheckFailed) as failure:
                await run(Adapter(), client, baseline(), report, stopped_probe=lambda: False)
        self.assertEqual(failure.exception.name, "api_stopped_before_experiment")
        self.assertEqual(report["records"], [])
        for change in ["runtime", "context", "duplicate"]:
            value = copy.deepcopy(baseline())
            if change == "runtime": value["server_before"]["runtime_source_sha256"] = {}
            elif change == "context": value["generations"][8]["context"]["input_token_upper_bound"] += 1
            else: value["generations"][1]["case"] = value["generations"][0]["case"]
            with self.assertRaises(CheckFailed): frozen_cases(value)

    async def test_ambiguous_post_is_recorded_and_never_retried(self):
        calls = []
        def fail(request):
            calls.append(request)
            raise httpx.ReadError("private upstream detail")
        report = {"checks": []}
        async with httpx.AsyncClient(base_url="http://127.0.0.1:11434",transport=httpx.MockTransport(fail)) as client:
            with self.assertRaises(httpx.ReadError):
                await run(Adapter(), client, baseline(), report, stopped_probe=lambda: True)
        summarize(report)
        self.assertEqual(len(calls), 1)
        self.assertTrue(report["inference_outcome_unknown"])
        self.assertEqual(report["candidate_quality_status"], "incomplete")
        self.assertNotIn("private upstream detail", json.dumps(report))

    async def test_invalid_counters_and_missing_terminal_are_not_success(self):
        good = {"model": "qwen2.5:14b", "done": True, "done_reason": "stop",
                "message": {"role": "assistant", "content": "OK"}, "prompt_eval_count": 1,
                "eval_count": 2, "eval_duration": 1000000, "load_duration": 0}
        for key, value, error in [("done", False, CheckFailed), ("eval_count", 1025, CheckFailed),
                                  ("prompt_eval_count", 100000, CheckFailed), ("eval_count", True, InferenceError)]:
            body = {**good, key: value}
            record = {}
            async with httpx.AsyncClient(base_url="http://127.0.0.1:11434",transport=httpx.MockTransport(lambda _:httpx.Response(200,json=body))) as client:
                with self.assertRaises(error):
                    await generate(client, ModelProfile(), [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
                                                           {"role": "user", "content": "Reply only OK"}], record)
            self.assertNotIn("status", record)
            self.assertTrue(record["dispatched"])


if __name__ == "__main__": unittest.main()
