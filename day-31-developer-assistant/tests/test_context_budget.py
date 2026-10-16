"""Input accounting regressions with explicitly synthetic transport, no live Qwen."""
from hashlib import sha256
import json
from pathlib import Path
import unittest

import test_pipeline as fixtures
from bublik_developer.contracts import Role
from bublik_developer.errors import DeveloperError, ErrorCode
from bublik_developer.generation import Qwen, context_budget, SYSTEM_DOC_RU, GENERATION_BUDGET_POLICY
from bublik_developer.baseline import BaselineQwen

ROOT = Path(__file__).resolve().parents[1]


def messages(client, role, context):
    return [{"role": "system", "content": client.system_prompt(role, context)},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False, sort_keys=True)}]


class ContextBudgetTests(unittest.TestCase):
    def test_historical_stopped_mac_input_is_admitted_without_changing_messages_or_evidence(self):
        fixture = json.loads((ROOT / "evaluation/context_budget_regression_v071.json").read_text())
        context = fixture["context"]
        transport, calls = fixtures.GenerationTests().server({"status": "unknown", "language": "ru", "claims": []})
        historical = json.loads((ROOT / "evaluation/context_budget_historical_prompt_v071.json").read_text())
        class HistoricalQwen(Qwen):
            prompt_version = historical["prompt_version"]
            def system_prompt(self, role, context):
                return historical["system_prompt_ru"]
        client = HistoricalQwen(fixtures.FakeLease(), transport=transport)
        original = messages(client, Role.DOCUMENTATION, context)
        wire = json.dumps(original, ensure_ascii=False, separators=(",", ":")).encode()
        self.assertEqual(len(wire), fixture["legacy_wire_message_bytes"])
        self.assertEqual(len(wire) + 256 + 1024 + 512, 8234)
        client.generate(Role.DOCUMENTATION, context)
        chat = next(body for endpoint, body in calls if endpoint == "/api/chat")
        self.assertEqual(chat["messages"], original)
        self.assertEqual(json.loads(chat["messages"][1]["content"])["evidence"], context["evidence"])
        self.assertEqual(client.metrics["message_digest"], sha256(wire).hexdigest())
        self.assertEqual(client.metrics["context_budget"]["estimated_total"], 8107)
        self.assertEqual(client.metrics["input_content_bytes"], 6315)
        self.assertEqual(client.metrics["input_bytes"], 6442)
        self.assertEqual(client.metrics["llm_calls"], 1)

    def test_wire_escaping_is_excluded_but_literal_user_json_is_fully_counted(self):
        context = fixtures.documentation_context("ru")
        context["evidence"][0]["quote"] = 'Русский "текст"\\path\nстрока\t' * 20
        client = Qwen(fixtures.FakeLease())
        prompt = messages(client, Role.DOCUMENTATION, context)
        budget = context_budget(prompt)
        expected = len(SYSTEM_DOC_RU.encode()) + len(json.dumps(context, ensure_ascii=False, sort_keys=True).encode())
        self.assertEqual(budget["content_bytes"], expected)
        self.assertEqual(budget["input_token_upper_bound_estimate"], expected + 256)
        wire = json.dumps(prompt, ensure_ascii=False, separators=(",", ":")).encode()
        self.assertGreater(len(wire), expected)
        self.assertEqual(budget["policy"], GENERATION_BUDGET_POLICY)

    def test_boundary_accepts_exact_limit_and_rejects_one_byte_over_before_dispatch(self):
        for over in (0, 1):
            context = fixtures.documentation_context()
            transport, calls = fixtures.GenerationTests().server({"status": "unknown", "language": "en", "claims": []})
            lease = fixtures.FakeLease(); client = Qwen(lease, transport=transport)
            count = context_budget(messages(client, Role.DOCUMENTATION, context))["content_bytes"]
            context["evidence"][0]["quote"] += "x" * (6400 - count + over)
            if over:
                with self.assertRaises(DeveloperError) as caught: client.generate(Role.DOCUMENTATION, context)
                self.assertEqual(caught.exception.code, ErrorCode.CONTEXT_BUDGET)
                self.assertFalse(lease.started)
                self.assertEqual(client.metrics["status"], "context_rejected_before_dispatch")
                self.assertEqual(client.metrics["llm_calls"], 0)
                self.assertEqual(client.metrics["dispatch_attempts"], 0)
                self.assertFalse(any(endpoint == "/api/chat" for endpoint, _ in calls))
            else:
                client.generate(Role.DOCUMENTATION, context)
                self.assertTrue(lease.finished)
            self.assertEqual(client.metrics["context_budget"]["estimated_total"], 8192 + over)

    def test_baseline_uses_same_counter_and_preserves_existing_model_options(self):
        from test_paired_research import combined_context, baseline_reply
        context = combined_context()
        transport, calls = fixtures.GenerationTests().server(baseline_reply(context))
        client = BaselineQwen(fixtures.FakeLease(), transport=transport); client.generate(Role.MAIN, context)
        chat = next(body for endpoint, body in calls if endpoint == "/api/chat")
        self.assertEqual(client.metrics["context_budget"], context_budget(chat["messages"]))
        self.assertEqual(chat["options"], {"temperature": 0, "num_ctx": 8192, "num_predict": 1024, "seed": 31})
        self.assertEqual(client.metrics["prompt_version"], "snapshot-single-v23")

    def test_counter_rejects_extra_messages_roles_media_and_history_shapes(self):
        good = [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}]
        invalid = [good + [{"role": "assistant", "content": "history"}], good[::-1],
                   [good[0], {**good[1], "images": []}], [good[0], {"role": "user", "content": None}]]
        for value in invalid:
            with self.assertRaises(DeveloperError): context_budget(value)

    def test_budget_metadata_contains_no_source_or_question_text(self):
        value = context_budget([{"role": "system", "content": "SYSTEM_CANARY_92881"},
                                {"role": "user", "content": "PRIVATE_CANARY_78222"}])
        self.assertNotIn("CANARY", json.dumps(value))
        self.assertEqual(value["template_allowance"], 256)
        self.assertEqual(value["safety_reserve"], 512)
        self.assertEqual(value["output_reserve"], 1024)
