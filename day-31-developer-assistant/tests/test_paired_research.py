"""Real fixture FTS; explicitly synthetic Git/model responses, never Mac proof."""
from copy import deepcopy
from hashlib import sha256
import json
import subprocess
import sys
import unittest
from unittest.mock import patch, AsyncMock

import test_pipeline as fixtures
from bublik_developer.baseline import (BaselineQwen, BaselineTasks, baseline_schema,
    validate_baseline_context, validate_baseline_output, doc_context)
from bublik_developer.contracts import Role, canonical, ContextEnvelope
from bublik_developer.errors import DeveloperError, ErrorCode
from bublik_developer.generation import Qwen, validate_context, validate_output, OPTIONS, SYSTEM_DOC
from bublik_developer.inference_tasks import InferenceTasks
from bublik_developer.model_worker import execute
from bublik_developer.paired_research import (SPEC, capture_snapshot, SnapshotPipeline, paired_bound,
    pair_order, signature, remap_observation, single_inference, compare, paired_freeze, paired_review_template, catalog_design)
from bublik_developer.research import conditions, ROOT, GenerationSlots, load_cases, select_cases


def combined_context():
    original = fixtures.documentation_context()
    return {"question": "How does memory work and what is the current branch?", "documentation_question": original["question"],
        "language": "en", "evidence": original["evidence"], "git_facts": [{"id": "g1", "text": "Branch: main."}]}


def baseline_reply(context):
    return {"status": "answered", "language": context["language"],
        "claims": [{"text": "History uses SQLite." if context["language"] == "en" else "История хранится в SQLite.",
                    "evidence_ids": [context["evidence"][0]["id"]]}],
        "git_fact_ids": [x["id"] for x in context["git_facts"]]}


class BaselineTests(unittest.TestCase):
    def test_baseline_has_full_sources_git_and_question_but_production_denies_it(self):
        context = combined_context()
        validate_baseline_context(Role.MAIN, context)
        self.assertEqual(doc_context(context)["evidence"], context["evidence"])
        for role in (Role.MAIN, Role.DOCUMENTATION):
            with self.assertRaises(DeveloperError): validate_context(role, context)
        for role in (Role.GIT, Role.VERIFICATION):
            with self.assertRaises(DeveloperError): validate_baseline_context(role, context)
        value = deepcopy(context); value["history"] = "PRIVATE"
        with self.assertRaises(DeveloperError): validate_baseline_context(Role.MAIN, value)

    def test_baseline_validator_preserves_doc_rules_and_requires_exact_git_ids(self):
        context = combined_context(); reply = baseline_reply(context)
        self.assertEqual(validate_baseline_output(Role.MAIN, reply, context), reply)
        for field, value in (("git_fact_ids", []), ("git_fact_ids", ["g2"]), ("git_fact_ids", ["g1", "g1"]),
                             ("language", "ru"), ("claims", [])):
            changed = deepcopy(reply); changed[field] = value
            with self.assertRaises(DeveloperError): validate_baseline_output(Role.MAIN, changed, context)
        changed = deepcopy(reply); changed["claims"][0]["evidence_ids"] = ["e99"]
        with self.assertRaises(DeveloperError): validate_baseline_output(Role.MAIN, changed, context)

    def test_unknown_baseline_preserves_git_with_empty_documentation_claims(self):
        context = combined_context()
        value = {"status": "unknown", "language": "en", "claims": [], "git_fact_ids": ["g1"]}
        self.assertEqual(validate_baseline_output(Role.MAIN, value, context), value)
        value["claims"] = baseline_reply(context)["claims"]
        with self.assertRaises(DeveloperError): validate_baseline_output(Role.MAIN, value, context)

    def test_baseline_schema_is_disjoint_and_closed_with_same_evidence_ids(self):
        schema = baseline_schema(Role.MAIN, combined_context())
        self.assertEqual(set(schema), {"oneOf"})
        self.assertEqual(len(schema["oneOf"]), 2)
        for branch in schema["oneOf"]:
            self.assertFalse(branch["additionalProperties"])
            self.assertEqual(branch["properties"]["claims"]["items"]["properties"]["evidence_ids"]["items"]["enum"], ["e1"])
            self.assertEqual(branch["properties"]["git_fact_ids"]["items"]["enum"], ["g1"])

    def test_baseline_uses_one_standard_transport_call_same_options_and_terminal_unload(self):
        context = combined_context(); transport, calls = fixtures.GenerationTests().server(baseline_reply(context))
        lease = fixtures.FakeLease(); client = BaselineQwen(lease, transport=transport)
        client.generate(Role.MAIN, context)
        chats = [body for endpoint, body in calls if endpoint == "/api/chat"]
        self.assertEqual(len(chats), 1)
        self.assertEqual(chats[0]["options"], OPTIONS)
        self.assertEqual(chats[0]["keep_alive"], "0s")
        self.assertEqual(json.loads(chats[0]["messages"][1]["content"]), context)
        self.assertEqual(client.metrics["output_validation"], "passed")
        self.assertEqual(client.metrics["prompt_version"], "snapshot-single-v23")
        self.assertTrue(lease.finished)

    def test_production_transport_messages_and_schema_are_unchanged_by_hooks(self):
        context = fixtures.documentation_context(); transport, calls = fixtures.GenerationTests().server()
        client = Qwen(fixtures.FakeLease(), transport=transport); client.generate(Role.DOCUMENTATION, context)
        chat = next(body for endpoint, body in calls if endpoint == "/api/chat")
        self.assertEqual(chat["messages"], [{"role": "system", "content": SYSTEM_DOC},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False, sort_keys=True)}])
        raw = json.dumps(chat["messages"], ensure_ascii=False, separators=(",", ":")).encode()
        self.assertEqual(client.metrics["message_digest"], sha256(raw).hexdigest())
        self.assertEqual(client.metrics["output_schema_version"], "status-claims-text-first-v7")

    def test_baseline_budget_blocks_before_dispatch_without_truncating_evidence(self):
        context = combined_context(); context["evidence"][0]["quote"] = "x" * 9000
        transport, calls = fixtures.GenerationTests().server(); lease = fixtures.FakeLease()
        with self.assertRaises(DeveloperError) as caught:
            BaselineQwen(lease, transport=transport).generate(Role.MAIN, context)
        self.assertEqual(caught.exception.code, ErrorCode.CONTEXT_BUDGET)
        self.assertEqual(len(context["evidence"][0]["quote"]), 9000)
        self.assertFalse(lease.started)
        self.assertFalse(any(endpoint == "/api/chat" for endpoint, _ in calls))

    def test_baseline_lost_call_remains_uncertain_and_is_never_replayed(self):
        transport, calls = fixtures.GenerationTests().server(lose=True)
        lease = fixtures.FakeLease(); client = BaselineQwen(lease, transport=transport)
        with self.assertRaises(DeveloperError): client.generate(Role.MAIN, combined_context())
        self.assertTrue(lease.invalidated)
        self.assertIsNone(client.metrics["llm_calls"])
        self.assertEqual(sum(endpoint == "/api/chat" for endpoint, _ in calls), 1)

    def test_baseline_fits_full_4096_byte_evidence_in_ru_and_en_without_truncation(self):
        for language in ("ru", "en"):
            context = combined_context(); context["language"] = language
            context["evidence"][0]["quote"] = "Я" * 2048
            context["question"] = "Как работает память и какая текущая ветка?" if language == "ru" else context["question"]
            context["git_facts"][0]["text"] = "Ветка: main. Наблюдение: 2026-10-13T17:16:03.265807+00:00"
            content = {"status": "unknown", "language": language, "claims": [], "git_fact_ids": ["g1"]}
            transport, calls = fixtures.GenerationTests().server(content)
            client = BaselineQwen(fixtures.FakeLease(), transport=transport); client.generate(Role.MAIN, context)
            body = next(body for endpoint, body in calls if endpoint == "/api/chat")
            self.assertEqual(json.loads(body["messages"][1]["content"])["evidence"], context["evidence"])
            self.assertLessEqual(client.metrics["input_bytes"] + 256 + 1024 + 512, 8192)

    def test_baseline_schema_matches_application_on_status_claims_and_git_matrix(self):
        from jsonschema import Draft202012Validator
        context = combined_context(); schema = Draft202012Validator(baseline_schema(Role.MAIN, context))
        for status in ("unknown", "answered", "partial"):
            for claims in ([], baseline_reply(context)["claims"]):
                for ids in ([], ["g1"], ["g2"], ["g1", "g1"]):
                    value = {"status": status, "language": "en", "claims": claims, "git_fact_ids": ids}
                    try: validate_baseline_output(Role.MAIN, value, context); valid = True
                    except DeveloperError: valid = False
                    self.assertEqual(schema.is_valid(value), valid)

    def test_production_worker_rejects_combined_context_before_workspace_access(self):
        context = combined_context()
        payload = {"root": "/not-accessed", "workspace_identity": [], "project_id": "fixture", "role": "main",
            "context": context, "context_digest": ContextEnvelope.seal(context).digest, "final": True,
            "request_id": "a"*32, "task_id": "b"*32}
        with patch("bublik_developer.model_worker.ProjectWorkspace.open", side_effect=AssertionError):
            with self.assertRaises(DeveloperError): execute(payload)


class PairedTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixture = fixtures.PipelineTests(); self.fixture.setUp(); self.addCleanup(self.fixture.temp.cleanup)
        self.case = {"id": "fixture-mixed", "language": "en", "question": "How does memory work and what is the current branch?",
            "expected_route": "fan_out", "acceptable_answer_status": ["answered"], "rubric_sources": ["README.md"],
            "required_points": ["PRIVATE_RUBRIC_CANARY_49119"]}
        self.document = {"format": "bublik-research-cases-v1", "batch_core": [self.case["id"]], "cases": [self.case]}
        self.path = self.fixture.parent / "cases.json"; self.path.write_text(json.dumps(self.document))
        self.output = self.fixture.parent / "paired.json"
        self.model = {"name": "qwen2.5:14b", "digest": "a"*64, "quantization": "Q4_K_M"}
        self.frozen = {"format": "bublik-research-freeze-v1", "model": self.model, "comparison_spec": deepcopy(SPEC),
            "catalog_design": catalog_design(self.document, conditions(self.fixture.workspace, self.fixture.state, cases_path=self.path)["cases_sha256"]),
            "conditions": conditions(self.fixture.workspace, self.fixture.state, cases_path=self.path)}
        self.metadata = patch("bublik_developer.paired_research.inspect_model",
            return_value={"model": self.model, "metadata_http_events": [], "generation_calls": 0})
        self.metadata.start(); self.addCleanup(self.metadata.stop)

    async def snapshot(self):
        with self.fixture.controlled_git(), patch.object(InferenceTasks, "run", side_effect=AssertionError("generation during acquisition")):
            return await capture_snapshot(self.fixture.workspace, self.fixture.state, self.case)

    def synthetic_baseline(self, *, fail=False, capture=None, mutate=False):
        owner = self
        class SyntheticBaseline(BaselineTasks):
            async def run(self, role, context, *, final=True):
                validate_baseline_context(role, context); self.budget.consume()
                if capture is not None: capture.append(deepcopy(context))
                self.observations.append({"role": "main", "llm_calls": 1, "input_tokens": 5, "output_tokens": 3,
                    "transport": "synthetic_test_transport", "model": owner.model, "status": "completed"})
                if fail: raise DeveloperError(ErrorCode.INVALID_MODEL_OUTPUT)
                if mutate: (owner.fixture.root / "README.md").write_text("# Changed\nNew corpus.\n")
                return baseline_reply(context)
        return SyntheticBaseline

    def test_bound_and_alternating_order_are_fixed_before_model_access(self):
        self.assertEqual(paired_bound([self.case], 3), 9)
        self.assertEqual(pair_order(0), ["single", "multi"])
        self.assertEqual(pair_order(1), ["multi", "single"])
        self.assertEqual(pair_order(2), ["multi", "single"])
        changed = deepcopy(self.case); changed["question"] = "Which files changed and where is functionality documented?"
        with self.assertRaises(DeveloperError): paired_bound([changed])
        for count in (0, 4, True):
            with self.assertRaises(DeveloperError): paired_bound([self.case], count)

    async def test_capture_is_real_fts_without_model_and_snapshot_contains_no_rubric(self):
        snapshot = await self.snapshot()
        self.assertEqual(snapshot["observation"]["status"], "completed")
        self.assertEqual(snapshot["observation"]["metrics"]["capability_calls"], 3)
        self.assertIn("SQLite", json.dumps(snapshot))
        self.assertNotIn("PRIVATE_RUBRIC_CANARY_49119", json.dumps(snapshot))

    def test_catalog_order_flips_repeats_and_balances_alternating_language_groups(self):
        for index in range(20):
            self.assertEqual(pair_order(index,1),list(reversed(pair_order(index,0))))
            self.assertEqual(pair_order(index,2),pair_order(index,0))
        for group in (range(0,20,2),range(1,20,2)):
            starts=[pair_order(index,repeat)[0] for repeat in range(3) for index in group]
            self.assertEqual(starts.count('single'),15)
            self.assertEqual(starts.count('multi'),15)
        for index,repeat in ((-1,0),(True,0),(0,True),(0,3)):
            with self.assertRaises(DeveloperError):pair_order(index,repeat)

    async def test_selected_batch_uses_catalog_position_and_reverses_each_repeat(self):
        prior=[deepcopy(self.case),deepcopy(self.case)]
        prior[0]['id']='prior-a';prior[1]['id']='prior-b'
        self.document['cases']=prior+[self.case]
        self.path.write_text(json.dumps(self.document))
        self.frozen['conditions']=conditions(self.fixture.workspace,self.fixture.state,cases_path=self.path)
        self.frozen['catalog_design']=catalog_design(self.document,self.frozen['conditions']['cases_sha256'])
        fixture_factory=self.fixture.model_factory()
        async def synthetic_run(tasks,role,context,*,final=True):
            model=fixture_factory(tasks.workspace,tasks.request_id,tasks.record,tasks.budget)
            value=await model.run(role,context,final=final)
            tasks.observations.extend(model.observations)
            return value
        with self.fixture.controlled_git(),patch.object(InferenceTasks,'run',new=synthetic_run), \
             patch('bublik_developer.paired_research.result_models_match',return_value=True):
            report=await compare(self.fixture.workspace,self.fixture.state,self.frozen,[self.case],
                cases_path=self.path,output=self.output,baseline_tasks=self.synthetic_baseline(),
                max_generation_calls=9,repeats=3)
        self.assertEqual(report['status'],'completed',report['error'])
        self.assertEqual([p['catalog_position'] for p in report['pairs']],[2,2,2])
        self.assertEqual([p['order'] for p in report['pairs']],
            [['multi','single'],['single','multi'],['multi','single']])
        self.assertEqual(report['summary']['known_llm_calls'],9)

    async def test_replay_multi_keeps_production_two_contexts_and_git_reobservation(self):
        snapshot = await self.snapshot()
        with self.fixture.controlled_git():
            result = await SnapshotPipeline(self.fixture.workspace, state_dir=self.fixture.state.path,
                language="en", snapshot=snapshot, inference_factory=self.fixture.model_factory()).run(self.case["question"])
        self.assertEqual(result["answer_status"], "answered")
        self.assertEqual(result["metrics"]["llm_calls"], 2)
        self.assertEqual(result["metrics"]["capability_calls"], 8)
        self.assertEqual(len(result["stage_metrics"]), 2)
        self.assertEqual(result["snapshot_digest"], sha256(canonical(snapshot).encode()).hexdigest())
        self.assertEqual(result["metrics"]["equal_budget_total_seconds"],
                         result["metrics"]["total_seconds"] + snapshot["common_preparation_seconds"])

    async def test_single_receives_exact_common_evidence_and_git_in_one_call(self):
        snapshot = await self.snapshot(); slots = GenerationSlots(1); captured = []
        factory = single_inference(slots, snapshot, tasks_class=self.synthetic_baseline(capture=captured))
        with self.fixture.controlled_git():
            result = await SnapshotPipeline(self.fixture.workspace, state_dir=self.fixture.state.path,
                language="en", snapshot=snapshot, inference_factory=factory).run(self.case["question"])
        self.assertEqual(result["answer_status"], "answered")
        self.assertEqual(result["metrics"]["llm_calls"], 1)
        self.assertEqual(result["metrics"]["capability_calls"], 7)
        self.assertEqual(slots.used, 1)
        self.assertEqual(captured[0]["question"], self.case["question"])
        self.assertEqual(captured[0]["git_facts"][0]["text"].split(". Observed:")[0], "Branch: main")
        sources = next(x["data"]["sources"] for x in snapshot["observation"]["merged"] if x["role"] == "documentation")
        self.assertEqual(captured[0]["evidence"], [{"id": "e"+str(i), "quote": row["quote"]} for i, row in enumerate(sources, 1)])

    async def test_snapshot_wrong_question_and_mutation_are_rejected(self):
        snapshot = await self.snapshot()
        pipeline = SnapshotPipeline(self.fixture.workspace, state_dir=self.fixture.state.path, snapshot=snapshot, language="en")
        with self.assertRaises(DeveloperError): await pipeline.run("different question")
        pipeline.snapshot["question"] = "tampered"
        with self.assertRaises(DeveloperError): await pipeline.run(self.case["question"])

    async def test_final_source_change_rejects_baseline_claims_without_second_generation(self):
        snapshot = await self.snapshot(); slots = GenerationSlots(1)
        with self.fixture.controlled_git():
            result = await SnapshotPipeline(self.fixture.workspace, state_dir=self.fixture.state.path, language="en",
                snapshot=snapshot, inference_factory=single_inference(slots, snapshot,
                    tasks_class=self.synthetic_baseline(mutate=True))).run(self.case["question"])
        self.assertEqual(result["claims"], [])
        self.assertIn(ErrorCode.INDEX_STALE.value, result["diagnostics"])
        self.assertEqual(slots.used, 1)

    async def test_git_change_is_rejected_on_both_modes(self):
        snapshot = await self.snapshot()
        self.fixture.branch = "different"
        for factory in (self.fixture.model_factory(), single_inference(GenerationSlots(1), snapshot, tasks_class=self.synthetic_baseline())):
            with self.fixture.controlled_git():
                result = await SnapshotPipeline(self.fixture.workspace, state_dir=self.fixture.state.path,
                    language="en", snapshot=snapshot, inference_factory=factory).run(self.case["question"])
            self.assertIn(ErrorCode.GIT_STATE_CHANGED.value, result["diagnostics"])
            self.assertEqual(result["git_facts"], [])

    async def test_cap_refuses_before_output_preparation_or_model(self):
        capture = AsyncMock()
        with self.assertRaises(DeveloperError):
            await compare(self.fixture.workspace, self.fixture.state, self.frozen, [self.case], cases_path=self.path,
                          output=self.output, max_generation_calls=2, capture=capture)
        capture.assert_not_awaited(); self.assertFalse(self.output.exists())

    async def test_technical_failure_preserves_first_result_stops_second_mode_and_does_not_repair(self):
        with self.fixture.controlled_git():
            report = await compare(self.fixture.workspace, self.fixture.state, self.frozen, [self.case], cases_path=self.path,
                output=self.output, baseline_tasks=self.synthetic_baseline(fail=True), max_generation_calls=3)
        self.assertEqual(report["status"], "stopped")
        self.assertEqual(len(report["requests"]), 1)
        self.assertEqual(report["generation_slots_reserved"], 1)
        self.assertEqual(report["requests"][0]["result"]["claims"], [])
        self.assertEqual(json.loads(self.output.read_text()), report)
        self.assertEqual(report["summary"]["semantic_acceptance"], "not_evaluated")
        self.assertFalse(report["pairs"][0]["conditions_valid_after"])

    async def test_failed_common_acquisition_is_saved_before_any_model(self):
        snapshot = await self.snapshot(); snapshot["observation"]["status"] = "failed"
        snapshot["observation"]["results"][0]["error_code"] = ErrorCode.MCP_UNAVAILABLE.value
        report = await compare(self.fixture.workspace, self.fixture.state, self.frozen, [self.case], cases_path=self.path,
            output=self.output, capture=AsyncMock(return_value=snapshot), max_generation_calls=3)
        self.assertEqual(report["status"], "stopped")
        self.assertEqual(len(report["pairs"]), 1)
        self.assertEqual(report["requests"], [])
        self.assertEqual(report["generation_slots_reserved"], 0)
        self.assertEqual(report["pairs"][0]["snapshot"]["observation"]["status"], "failed")

    async def test_full_two_pair_runner_alternates_and_counts_six_synthetic_calls(self):
        second = deepcopy(self.case); second["id"] = "fixture-mixed-2"
        self.document["cases"].append(second); self.path.write_text(json.dumps(self.document))
        self.frozen["conditions"] = conditions(self.fixture.workspace, self.fixture.state, cases_path=self.path)
        self.frozen["catalog_design"] = catalog_design(self.document, self.frozen["conditions"]["cases_sha256"])
        fixture_factory = self.fixture.model_factory()
        async def synthetic_run(tasks, role, context, *, final=True):
            model = fixture_factory(tasks.workspace, tasks.request_id, tasks.record, tasks.budget)
            value = await model.run(role, context, final=final)
            tasks.observations.extend(model.observations)
            return value
        with self.fixture.controlled_git(), patch.object(InferenceTasks, "run", new=synthetic_run), \
             patch("bublik_developer.paired_research.result_models_match", return_value=True):
            report = await compare(self.fixture.workspace, self.fixture.state, self.frozen, [self.case, second],
                cases_path=self.path, output=self.output, baseline_tasks=self.synthetic_baseline(), max_generation_calls=6)
        self.assertEqual(report["status"], "completed", (report["error"], [(x["mode"],x.get("result",{}).get("diagnostics")) for x in report["requests"]]))
        self.assertEqual([row["mode"] for row in report["requests"]], ["single", "multi", "multi", "single"])
        self.assertEqual(report["summary"]["known_llm_calls"], 6)
        self.assertEqual(report["generation_slots_reserved"], 6)
        self.assertEqual(report["summary"]["pairs_completed"], 2)
        self.assertEqual(report["summary"]["actual_common_capability_calls"], 6)
        for pair in report["pairs"]:
            self.assertTrue(pair["conditions_valid_after"])
            rows = [row for row in report["requests"] if row["pair_id"] == pair["pair_id"]]
            self.assertEqual(len({row["result"]["snapshot_digest"] for row in rows}), 1)
        self.assertNotIn("PRIVATE_RUBRIC_CANARY_49119", json.dumps(report))

    async def test_changed_freeze_spec_and_substituted_rubric_are_rejected_before_output(self):
        for frozen, cases in (({**self.frozen, "comparison_spec": {}}, [self.case]),
                              (self.frozen, [{**self.case, "required_points": ["changed"]}])):
            with self.assertRaises(DeveloperError):
                await compare(self.fixture.workspace, self.fixture.state, frozen, cases, cases_path=self.path,
                              output=self.output, max_generation_calls=3)
            self.assertFalse(self.output.exists())

    async def test_oversized_shared_preparation_deadline_prevents_generation(self):
        snapshot = await self.snapshot(); snapshot["common_preparation_seconds"] = 301
        inference = AsyncMock()
        pipeline = SnapshotPipeline(self.fixture.workspace, state_dir=self.fixture.state.path,
            language="en", snapshot=snapshot, inference_factory=lambda *args: inference)
        with self.assertRaises(DeveloperError) as caught: await pipeline.run(self.case["question"])
        self.assertEqual(caught.exception.code, ErrorCode.TIMEOUT)
        inference.run.assert_not_awaited()

    async def test_synthetic_transport_cannot_pass_real_model_acceptance(self):
        with self.fixture.controlled_git():
            report = await compare(self.fixture.workspace, self.fixture.state, self.frozen, [self.case], cases_path=self.path,
                output=self.output, baseline_tasks=self.synthetic_baseline(), max_generation_calls=3)
        self.assertEqual(report["status"], "stopped")
        self.assertEqual(report["error"], ErrorCode.LLM_UNAVAILABLE.value)
        self.assertEqual(len(report["requests"]), 1)

    def test_paired_review_template_pins_catalog_keeps_modes_and_requires_human_scores(self):
        from bublik_developer.research import load_cases
        result = {"answer": "Synthetic answer", "execution_status": "completed", "answer_status": "answered"}
        report = {"format": "bublik-paired-snapshot-v1", "frozen_conditions": self.frozen,
            "requests": [{"pair_id": 1, "case_id": self.case["id"], "mode": mode, "repeat": 1, "result": result}
                         for mode in ("single", "multi")]}
        digest = load_cases(self.path)[1]
        review = paired_review_template(report, self.document, digest)
        self.assertEqual(review["status"], "pending")
        self.assertIsNone(review["reviewer"])
        self.assertEqual([row["mode"] for row in review["reviews"]], ["single", "multi"])
        self.assertTrue(all(value is None for row in review["reviews"] for value in row["scores"].values()))
        with self.assertRaises(DeveloperError): paired_review_template(report, self.document, "changed")

    def test_cli_default_plan_is_four_observations_six_generations_without_inference(self):
        run = subprocess.run([sys.executable, str(ROOT / "scripts/compare_single_multi.py"), "plan"],
                             check=True, capture_output=True, text=True, timeout=10)
        result = json.loads(run.stdout)
        self.assertEqual(result["generation_upper_bound"], 6)
        self.assertEqual(result["request_observations"], 4)
        self.assertFalse(result["inference_performed"])

    def test_prespecified_catalog_has_twenty_new_balanced_cases_and_five_bounded_batches(self):
        document, digest = load_cases(ROOT / "evaluation/research_prespecified_v071.json")
        self.assertEqual(len(document["cases"]), 20)
        self.assertEqual(sum(case["language"] == "ru" for case in document["cases"]), 10)
        old_questions = {case["question"] for file in ("research_cases.json", "research_clarifications.json")
                         for case in load_cases(ROOT / "evaluation" / file)[0]["cases"]}
        self.assertFalse(old_questions & {case["question"] for case in document["cases"]})
        ids = []
        from bublik_developer.routing import route
        for batch in document["batches"]:
            cases = select_cases(document, batch["case_ids"])
            self.assertEqual(paired_bound(cases), batch["generation_upper_bound"])
            self.assertEqual(len(cases) * 2, batch["request_observations"])
            ids.extend(batch["case_ids"])
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {case["id"] for case in document["cases"]})
        for case in document["cases"]:
            self.assertEqual(route(case["question"]).kind, case["expected_route"], case["id"])
        self.assertEqual(catalog_design(document, digest)["kind"], "prespecified_new_questions")

    def test_custom_catalog_cli_uses_batch_core_and_reports_pending_review_without_models(self):
        path = ROOT / "evaluation/research_prespecified_v071.json"
        run = subprocess.run([sys.executable, str(ROOT / "scripts/compare_single_multi.py"), "plan", "--cases", str(path)],
                             check=True, capture_output=True, text=True, timeout=10)
        value = json.loads(run.stdout)
        self.assertEqual(value["case_ids"], load_cases(path)[0]["batch_core"])
        self.assertEqual(value["generation_upper_bound"], 10)
        self.assertEqual(value["request_observations"], 8)
        self.assertFalse(value["inference_performed"])
        self.assertEqual(value["catalog_design"]["human_review"], "pending")
        self.assertFalse(value["catalog_design"]["independent_semantic_acceptance"])

    def test_catalog_metadata_rejects_invalid_kind_or_scope(self):
        for field, value in (("evaluation_kind", {}), ("evaluation_kind", "automatically_passed"),
                             ("scope", 5), ("scope", "")):
            document = {**self.document, field: value}
            with self.assertRaises(DeveloperError): catalog_design(document, "a" * 64)

    def test_new_catalog_freeze_is_metadata_only_and_pins_design(self):
        from bublik_developer.paired_research import comparison_spec
        document = {**self.document, "evaluation_kind": "prespecified_new_questions", "scope": "New fixture case; review pending"}
        self.path.write_text(json.dumps(document))
        with patch("bublik_developer.research.inspect_model", return_value={"model": self.model, "metadata_http_events": [], "generation_calls": 0}), \
             patch.object(Qwen, "generate") as generate:
            value = paired_freeze(self.fixture.workspace, self.fixture.state, cases_path=self.path)
        generate.assert_not_called()
        digest = load_cases(self.path)[1]
        self.assertEqual(value["catalog_design"], catalog_design(document, digest))
        self.assertEqual(value["comparison_spec"], comparison_spec(document, digest))
        self.assertEqual(value["generation_calls"], 0)

    async def test_tampered_catalog_design_is_refused_before_output_or_acquisition(self):
        frozen = deepcopy(self.frozen); frozen["catalog_design"]["kind"] = "prespecified_new_questions"
        capture = AsyncMock()
        with self.assertRaises(DeveloperError):
            await compare(self.fixture.workspace, self.fixture.state, frozen, [self.case], cases_path=self.path,
                          output=self.output, capture=capture, max_generation_calls=3)
        capture.assert_not_awaited(); self.assertFalse(self.output.exists())

    async def test_new_question_report_labels_change_without_claiming_semantic_pass(self):
        document = {**self.document, "evaluation_kind": "prespecified_new_questions", "scope": "New fixture; review pending"}
        self.path.write_text(json.dumps(document))
        with patch("bublik_developer.research.inspect_model", return_value={"model": self.model, "metadata_http_events": [], "generation_calls": 0}):
            frozen = paired_freeze(self.fixture.workspace, self.fixture.state, cases_path=self.path)
        fixture_factory = self.fixture.model_factory()
        async def synthetic_run(tasks, role, context, *, final=True):
            models = fixture_factory(tasks.workspace, tasks.request_id, tasks.record, tasks.budget)
            value = await models.run(role, context, final=final)
            tasks.observations.extend(models.observations)
            return value
        with self.fixture.controlled_git(), patch.object(InferenceTasks, "run", new=synthetic_run), \
             patch("bublik_developer.paired_research.result_models_match", return_value=True):
            report = await compare(self.fixture.workspace, self.fixture.state, frozen, [self.case], cases_path=self.path,
                                  output=self.output, baseline_tasks=self.synthetic_baseline(), max_generation_calls=3)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["catalog_design"]["kind"], "prespecified_new_questions")
        self.assertEqual(report["summary"]["single_multi_comparison"], "snapshot_new_questions")
        self.assertEqual(report["summary"]["semantic_acceptance"], "not_evaluated")
        self.assertNotIn("PRIVATE_RUBRIC_CANARY_49119", json.dumps(report))


if __name__ == "__main__": unittest.main()
