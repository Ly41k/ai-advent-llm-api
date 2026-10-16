"""Synthetic generation/Git fixtures; real FTS, owned workers and source checks."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

from bublik_developer.agent_runtime import Dispatcher
from bublik_developer.agent_worker import execute as worker_execute
from bublik_developer.contracts import AgentResult, ContextEnvelope, Role, TaskStatus
from bublik_developer.errors import DeveloperError, ErrorCode
from bublik_developer.generation import Qwen, MODEL, strict_json, validate_context, validate_output
from bublik_developer.model_worker import execute as model_execute
from bublik_developer.pipeline import Pipeline
from bublik_developer.rag.corpus import ProjectCorpus
from bublik_developer.rag.index import build_index
from bublik_developer.rag.state import ProjectState
from bublik_developer.routing import ProjectSession, route
from bublik_developer.workspace import ProjectWorkspace


class RoutingTests(unittest.TestCase):
    def test_ru_en_routes_and_independent_doc_question(self):
        cases = [("Какая текущая ветка?", "git"), ("current branch", "git"),
                 ("Как устроена память?", "documentation"), ("How does memory work?", "documentation"),
                 ("Как устроена память и какая текущая ветка?", "fan_out"),
                 ("What is the API prefix and what is the current branch?", "fan_out"),
                 ("Какие файлы изменены и где описана их функциональность?", "chain"),
                 ("Which files changed and where is functionality documented?", "chain"),
                 ("Может ли git_diff читать untracked файлы?", "documentation")]
        for question, expected in cases:
            with self.subTest(question=question):
                planned = route(question)
                self.assertEqual(planned.kind, expected)
                if expected == "fan_out":
                    self.assertNotIn("branch", planned.documentation_question)
                    self.assertNotIn("ветка", planned.documentation_question)

    def test_write_and_ambiguous_intents_do_not_get_executor(self):
        for question in ("git push", "delete README.md", "удали README.md", "сделай коммит"):
            with self.assertRaises(DeveloperError) as caught:
                route(question)
            self.assertEqual(caught.exception.code, ErrorCode.PERMISSION_DENIED)
        self.assertEqual(route("branch and status").kind, "ambiguous")
        self.assertEqual(route("show staged diff").git_scope, "staged")
        self.assertEqual(route("show unstaged diff").git_scope, "unstaged")

    def test_followup_scope_is_project_and_revision_bound(self):
        session = ProjectSession("project")
        session.remember("How does memory work?", "r1")
        self.assertIn("How does memory", session.resolve("What about owner isolation?", "project", "r1"))
        with self.assertRaises(DeveloperError):
            session.resolve("What about owner?", "other", "r1")
        self.assertEqual(session.resolve("What about owner?", "project", "r2"), "What about owner?")


    def test_fanout_preserves_ru_en_internal_conjunctions(self):
        for doc, git in (
            ("Согласно архитектуре, задачи Alpha и Beta используют одну очередь или разные?", "Покажи текущую ветку."),
            ("According to the architecture, do Alpha and Beta share a queue or use different queues?", "Show the current branch.")):
            with self.subTest(doc=doc):
                planned = route(doc + " " + git)
                self.assertEqual(planned.kind, "fan_out")
                self.assertEqual(planned.documentation_question, doc)
                self.assertEqual(planned.git_operation, "branch")

    def test_fanout_preserves_multiple_documentation_question_boundaries(self):
        doc = "How does memory work? What are the API inputs and permissions?"
        planned = route(doc + " Also show the current branch.")
        self.assertEqual(planned.kind, "fan_out")
        self.assertEqual(planned.documentation_question, doc)
        self.assertEqual(route(planned.documentation_question).documentation_question, doc)

    def test_fanout_does_not_join_across_removed_git_intent(self):
        planned = route("How does memory work? Show current branch? What is the API?")
        self.assertEqual(planned.kind, "fan_out")
        self.assertEqual(planned.documentation_question, "How does memory work?\nWhat is the API?")
        leading = route("Show current branch and explain memory and owner isolation?")
        self.assertEqual(leading.documentation_question, "explain memory and owner isolation?")


class FakeLease:
    def __init__(self):
        self.started = self.finished = self.invalidated = False
    def validate(self): pass
    def begin(self): self.started = True
    def finish(self): self.finished = True
    def uncertain(self): self.invalidated = True


def documentation_context(language="en"):
    return {"question": "How does memory work?", "language": language,
            "evidence": [{"id": "e1", "quote": "Memory history uses SQLite and FTS5."}]}


class GenerationTests(unittest.TestCase):
    def server(self, content=None, *, lose=False, details=None, remote=False, done=True):
        calls = []
        def transport(endpoint, body):
            calls.append((endpoint, body))
            if endpoint == "/api/tags":
                return {"models": [{"name": MODEL, "digest": "a" * 64}]}
            if endpoint == "/api/show":
                return {"details": details or {"family": "qwen2", "parameter_size": "14.8B", "quantization_level": "Q4_K_M"},
                        **({"remote_host": "cloud"} if remote else {})}
            if endpoint == "/api/ps":
                return {"models": []}
            if lose:
                raise DeveloperError(ErrorCode.EMBEDDING_UNAVAILABLE)
            result = content if content is not None else {"status": "answered", "language": "en", "claims": [{"text": "Memory history uses SQLite.", "evidence_ids": ["e1"]}]}
            return {"model": MODEL, "done": done, "message": {"role": "assistant", "content": json.dumps(result)},
                    "prompt_eval_count": 42, "eval_count": 17, "total_duration": 100, "load_duration": 20}
        return transport, calls

    def test_generation_records_real_response_fields_separately_from_estimate(self):
        transport, calls = self.server()
        lease = FakeLease();client = Qwen(lease, transport=transport)
        result = client.generate(Role.DOCUMENTATION, documentation_context())
        self.assertEqual(result["status"], "answered")
        self.assertTrue(lease.started and lease.finished)
        self.assertFalse(lease.invalidated)
        self.assertEqual(client.metrics["input_tokens"], 42)
        self.assertEqual(client.metrics["output_tokens"], 17)
        self.assertEqual(client.metrics["llm_calls"], 1)
        chats = [body for endpoint, body in calls if endpoint == "/api/chat"]
        self.assertEqual(len(chats), 1)
        self.assertFalse(chats[0]["stream"])
        self.assertEqual(chats[0]["options"]["num_ctx"], 8192)
        for branch in chats[0]["format"]["oneOf"]:
            self.assertEqual(branch["properties"]["language"]["enum"], ["en"])
        for branch in chats[0]["format"]["oneOf"]:
            self.assertEqual(branch["properties"]["claims"]["items"]["properties"]["evidence_ids"]["items"]["enum"], ["e1"])
        self.assertNotIn("tools", chats[0])
        self.assertEqual(client.metrics["transport"], "synthetic_test_transport")

    def test_documentation_prompt_localizes_without_rewriting_context_or_extra_dispatch(self):
        import re
        for language in ("ru","en"):
            context=documentation_context(language)
            transport,calls=self.server(content={"status":"unknown","language":language,"claims":[]})
            client=Qwen(FakeLease(),transport=transport)
            result=client.generate(Role.DOCUMENTATION,context)
            chats=[body for endpoint,body in calls if endpoint=="/api/chat"]
            self.assertEqual(len(chats),1)
            self.assertEqual(result["status"],"unknown")
            messages=chats[0]["messages"]
            self.assertEqual([x["role"] for x in messages],["system","user"])
            self.assertEqual(bool(re.search(r"[А-Яа-яЁё]",messages[0]["content"])),language=="ru")
            self.assertEqual(json.loads(messages[1]["content"]),context)
            for branch in chats[0]["format"]["oneOf"]:
                self.assertEqual(branch["properties"]["language"]["enum"],[language])
            self.assertNotIn("tools",chats[0])
            raw=json.dumps(messages,ensure_ascii=False,separators=(",",":")).encode()
            self.assertEqual(client.metrics["message_digest"],sha256(raw).hexdigest())
            self.assertEqual(client.metrics["context_digest"],ContextEnvelope.seal(context).digest)
            self.assertEqual(client.metrics["prompt_version"],"project-answers-v22")
            self.assertEqual(client.metrics["llm_calls"],1)

    def test_localized_prompt_fits_full_worker_evidence_budget_without_truncation(self):
        # Worker evidence is bounded by UTF-8 bytes, not characters/tokens.
        for language in ("ru","en"):
            context=documentation_context(language)
            context["evidence"][0]["quote"]="Я"*2048  # exactly 4096 UTF-8 bytes
            transport,calls=self.server(content={"status":"unknown","language":language,"claims":[]})
            client=Qwen(FakeLease(),transport=transport)
            client.generate(Role.DOCUMENTATION,context)
            body=next(body for endpoint,body in calls if endpoint=="/api/chat")
            self.assertEqual(json.loads(body["messages"][1]["content"])["evidence"],context["evidence"])
            self.assertLessEqual(client.metrics["input_bytes"]+256+1024+512,8192)
            self.assertEqual(body["options"]["num_ctx"],8192)
            self.assertEqual(body["options"]["num_predict"],1024)
            self.assertEqual(client.metrics["dispatch_attempts"],1)

    def test_doc_schema_and_validator_agree_on_status_claims_matrix(self):
        from jsonschema import Draft202012Validator
        from bublik_developer.generation import output_schema
        for language in ("ru","en"):
            context=documentation_context(language)
            schema=output_schema(Role.DOCUMENTATION,context)
            Draft202012Validator.check_schema(schema)
            server_validator=Draft202012Validator(schema)
            self.assertNotIn("properties",schema)
            for status in ("answered","partial","unknown"):
                for count in (0,1,5,6):
                    for reply_language in ("ru","en"):
                        for evidence_id in ("e1","e2"):
                            value={"status":status,"language":reply_language,"claims":[{
                                "text":"История использует SQLite." if language == "ru" else "History uses SQLite.",
                                "evidence_ids":[evidence_id]} for _ in range(count)]}
                            expected=(reply_language==language and ((status=="unknown" and count==0) or
                                (status!="unknown" and 1<=count<=5 and evidence_id=="e1")))
                            self.assertEqual(server_validator.is_valid(value),expected)
                            try:validate_output(Role.DOCUMENTATION,value,context);accepted=True
                            except DeveloperError:accepted=False
                            self.assertEqual(accepted,expected)

    def test_status_validation_reasons_do_not_repair_frames_leak_text_or_replay(self):
        from copy import deepcopy
        from bublik_developer.generation import ModelOutputError
        claim={"text":"PRIVATE_MODEL_CANARY_7319","evidence_ids":["e1"]}
        cases=[({"status":"unknown","language":"en","claims":[claim]},"unknown_with_claims"),
               ({"status":"answered","language":"en","claims":[]},"supported_without_claims"),
               ({"status":"partial","language":"en","claims":[]},"supported_without_claims"),
               ({"status":"unsupported","language":"en","claims":[]},"documentation_status"),
               ({"status":"unknown","language":"ru","claims":[]},"documentation_language"),
               ({"status":"unknown","language":"en","claims":None},"documentation_claims_shape"),
               ({"status":"unknown","language":"en"},"documentation_fields")]
        for frame,reason in cases:
            before=deepcopy(frame);transport,calls=self.server(content=frame);lease=FakeLease()
            client=Qwen(lease,transport=transport)
            with self.assertRaises(ModelOutputError):client.generate(Role.DOCUMENTATION,documentation_context())
            self.assertEqual(client.metrics["output_validation_reason"],reason)
            self.assertEqual(client.metrics["llm_calls"],1)
            self.assertEqual(frame,before)
            self.assertTrue(lease.finished)
            self.assertFalse(lease.invalidated)
            self.assertNotIn("PRIVATE_MODEL_CANARY_7319",json.dumps(client.metrics))
            with self.assertRaises(DeveloperError):client.generate(Role.DOCUMENTATION,documentation_context())
            self.assertEqual(sum(endpoint=="/api/chat" for endpoint,body in calls),1)

    def test_wrong_role_extra_history_and_git_are_rejected_before_metadata(self):
        for role, context in ((Role.GIT, documentation_context()), (Role.VERIFICATION, documentation_context()),
                              (Role.DOCUMENTATION, {**documentation_context(), "chat_history": []}),
                              (Role.DOCUMENTATION, {**documentation_context(), "git_facts": []})):
            transport, calls = self.server()
            with self.assertRaises(DeveloperError):
                Qwen(FakeLease(), transport=transport).generate(role, context)
            self.assertEqual(calls, [])

    def test_wrong_profile_or_remote_model_never_dispatches(self):
        for settings in ({"remote": True}, {"details": {"family": "qwen2", "parameter_size": "14.8B", "quantization_level": "Q8_0"}}):
            transport, calls = self.server(**settings)
            with self.assertRaises(DeveloperError) as caught:
                Qwen(FakeLease(), transport=transport).generate(Role.DOCUMENTATION, documentation_context())
            self.assertEqual(caught.exception.code, ErrorCode.LLM_UNAVAILABLE)
            self.assertFalse(any(endpoint == "/api/chat" for endpoint, _ in calls))

    def test_lost_or_nonterminal_response_holds_uncertain_and_never_retries(self):
        for settings in ({"lose": True}, {"done": False}):
            transport, calls = self.server(**settings);lease = FakeLease();client = Qwen(lease, transport=transport)
            with self.assertRaises(DeveloperError):
                client.generate(Role.DOCUMENTATION, documentation_context())
            self.assertTrue(lease.invalidated)
            self.assertIsNone(client.metrics["llm_calls"])
            self.assertEqual(sum(endpoint == "/api/chat" for endpoint, _ in calls), 1)

    def test_invalid_terminal_claim_is_rejected_without_uncertain_replay(self):
        invalid = {"status": "answered", "language": "en", "claims": [{"text": "Call `fake_worker`.", "evidence_ids": ["e1"]}]}
        transport, _ = self.server(invalid);lease = FakeLease();client = Qwen(lease, transport=transport)
        with self.assertRaises(DeveloperError) as caught:
            client.generate(Role.DOCUMENTATION, documentation_context())
        self.assertEqual(caught.exception.code, ErrorCode.INVALID_MODEL_OUTPUT)
        self.assertTrue(lease.finished)
        self.assertFalse(lease.invalidated)
        self.assertEqual(client.metrics["llm_calls"], 1)

    def test_context_budget_blocks_chat_before_begin(self):
        context = documentation_context();context["evidence"][0]["quote"] = "x" * 9000
        transport, calls = self.server();lease = FakeLease()
        with self.assertRaises(DeveloperError) as caught:
            Qwen(lease, transport=transport).generate(Role.DOCUMENTATION, context)
        self.assertEqual(caught.exception.code, ErrorCode.CONTEXT_BUDGET)
        self.assertFalse(lease.started)
        self.assertFalse(any(endpoint == "/api/chat" for endpoint, _ in calls))

    def test_api_path_sentence_punctuation_is_not_an_identifier(self):
        context = {"question": "What is the API prefix?", "language": "en",
                   "evidence": [{"id": "e1", "quote": "Day 30 defines PREFIX=/api/v1 in bublik_service/http_api.py."}]}
        for text in ("The API prefix is /api/v1.", "The API prefix is `/api/v1`.",
                     "The API prefix is /api/v1, as documented.", "Use /api/v1; this is the prefix."):
            with self.subTest(text=text):
                value = {"status": "answered", "language": "en", "claims": [{"text": text, "evidence_ids": ["e1"]}]}
                self.assertEqual(validate_output(Role.DOCUMENTATION, value, context), value)

    def test_punctuation_fix_keeps_unsupported_and_literal_code_rejected(self):
        context = {"question": "What is the API prefix?", "language": "en",
                   "evidence": [{"id": "e1", "quote": "PREFIX=/api/v1"}]}
        for text in ("Use /api/v2.", "Use /api/v1/evil.", "Use `/api/v1.`.", "Run `fake_worker`."):
            with self.subTest(text=text), self.assertRaises(DeveloperError) as caught:
                validate_output(Role.DOCUMENTATION, {"status": "answered", "language": "en",
                    "claims": [{"text": text, "evidence_ids": ["e1"]}]}, context)
            self.assertEqual(caught.exception.code, ErrorCode.INVALID_MODEL_OUTPUT)

    def test_rejected_output_records_reason_without_model_text_or_retry(self):
        variants = [("Call `fake_worker`.", "en", "unsupported_identifier"),
                    ("История в SQLite.", "en", "claim_language")]
        for text, language, reason in variants:
            transport, calls = self.server({"status": "answered", "language": language,
                "claims": [{"text": text, "evidence_ids": ["e1"]}]})
            client = Qwen(FakeLease(), transport=transport)
            with self.assertRaises(DeveloperError):client.generate(Role.DOCUMENTATION, documentation_context())
            self.assertEqual(client.metrics["output_validation"], "rejected")
            self.assertEqual(client.metrics["output_validation_reason"], reason)
            self.assertNotIn(text, json.dumps(client.metrics, ensure_ascii=False))
            self.assertEqual(client.metrics["llm_calls"], 1)
            self.assertEqual(sum(endpoint == "/api/chat" for endpoint, _ in calls), 1)

    def test_strict_json_and_unknown_evidence_ids(self):
        for text in ('{"status":"a","status":"b"}', '{"x":NaN}', '```json\n{}\n```', '[]'):
            with self.assertRaises(DeveloperError):strict_json(text)
        with self.assertRaises(DeveloperError):
            validate_output(Role.DOCUMENTATION, {"status": "answered", "language": "en", "claims": [{"text": "Memory history uses SQLite.", "evidence_ids": ["e99"]}]}, documentation_context())

    def test_main_cannot_add_text_ids_or_drop_an_obligatory_part(self):
        context = {"question": "Memory and branch?", "language": "en", "claims": [{"id": "c1", "text": "Memory uses SQLite."}], "git_facts": [{"id": "g1", "text": "Branch: main."}]}
        for value in ({"claim_ids": ["c2"], "git_fact_ids": ["g1"]}, {"claim_ids": ["c1"], "git_fact_ids": []},
                      {"claim_ids": ["c1"], "git_fact_ids": ["g1"], "text": "Invented fact"}):
            with self.assertRaises(DeveloperError):validate_output(Role.MAIN, value, context)
        self.assertEqual(validate_output(Role.MAIN, {"claim_ids": ["c1"], "git_fact_ids": ["g1"]}, context)["claim_ids"], ["c1"])

    def test_model_worker_wrong_role_is_rejected_before_workspace_or_session(self):
        context = documentation_context()
        payload = {"root": "/unavailable", "workspace_identity": [], "project_id": "project", "role": "git",
                   "context": context, "context_digest": ContextEnvelope.seal(context).digest, "final": True,
                   "request_id": "a"*32, "task_id": "b"*32}
        with patch("bublik_developer.model_worker.ProjectWorkspace.open", side_effect=AssertionError("workspace accessed")):
            with self.assertRaises(DeveloperError) as caught:model_execute(payload)
        self.assertEqual(caught.exception.code, ErrorCode.PERMISSION_DENIED)


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name).resolve();self.root = self.parent / "repo";self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "README.md").write_text("# Memory\nMemory history uses SQLite and FTS5.\n\n# Tooling\nThe src/worker.py file executes background work.\n")
        self.workspace = ProjectWorkspace.open(self.root, "fixture");self.corpus = ProjectCorpus(self.workspace)
        self.state = ProjectState(self.workspace, self.parent / "state");build_index(self.corpus, self.state)
        self.branch = "main"
        self.changed_paths = ["src/worker.py"]

    @contextmanager
    def controlled_git(self):
        original = Dispatcher.execute
        owner = self
        async def execute(dispatcher, task, context):
            if task.role == Role.GIT:
                operation = context.open()["operation"]
                reply = {"ok": True, "project_id": owner.workspace.project_id, "observed_at": datetime.now(timezone.utc).isoformat(),
                    "tool": "git_current_branch", "data": {"kind": "branch", "branch": owner.branch,
                    "head_oid": "a" * 40, "detached_head": False, "unborn": False}, "error": None}
                if operation == "status":
                    reply.update(tool="git_status", data={"kind":"status","entries":[{"path":path,"original_path":None,"index_status":" ","worktree_status":"M"} for path in owner.changed_paths],
                        "withheld_count":0,"snapshot_digest":"a"*64,"consistency":"head_index_status"})
                elif operation != "branch":raise DeveloperError(ErrorCode.PERMISSION_DENIED)
                return AgentResult(task.task_id, TaskStatus.SUCCESS, "answered", ContextEnvelope.seal(reply))
            return await original(dispatcher, task, context)
        with patch.object(Dispatcher, "execute", new=execute):yield

    def model_factory(self, *, fail_main=False, change_doc=False, change_git=False, unknown=False):
        owner = self
        class SyntheticInference:
            def __init__(self, workspace, request_id, record, budget):
                self.observations=[];self.budget=budget
            async def run(self, role, context, *, final=True):
                validate_context(role, context);self.budget.consume()
                self.observations.append({"role": role.value, "llm_calls": 1, "input_tokens": 5, "output_tokens": 3,
                    "context_keys": sorted(context), "message_digest": ContextEnvelope.seal(context).digest,
                    "status": "completed", "transport": "synthetic_test_transport"})
                if role == Role.MAIN:
                    if change_doc:(owner.root / "README.md").write_text("# Changed\nNew source.\n")
                    if change_git:owner.branch="other"
                    if fail_main:raise DeveloperError(ErrorCode.INVALID_MODEL_OUTPUT)
                    return {"claim_ids": [x["id"] for x in context["claims"]], "git_fact_ids": [x["id"] for x in context["git_facts"]]}
                if unknown:
                    return {"status":"unknown","language":context["language"],"claims":[]}
                hit = next((x for x in context["evidence"] if "SQLite" in x["quote"]), context["evidence"][0])
                if "SQLite" in hit["quote"]:
                    text = "History uses SQLite." if context["language"] == "en" else "История хранится в SQLite."
                else:
                    text = "The `src/worker.py` file executes background work."
                return {"status": "answered", "language": context["language"], "claims": [{"text": text, "evidence_ids": [hit["id"]]}]}
        return SyntheticInference

    def pipeline(self, **values):
        return Pipeline(self.workspace, state_dir=self.state.path, corpus=self.corpus, language="en",
                        inference_factory=values.pop("inference_factory", self.model_factory()), **values)

    async def test_documentation_uses_real_fts_provenance_and_one_synthetic_context(self):
        result = await self.pipeline().run("How does memory work?")
        self.assertEqual(result["answer_status"], "answered")
        self.assertEqual(result["metrics"]["llm_calls"], 1)
        self.assertIn("SQLite", result["citations"][0]["quote"])
        self.assertFalse(result["semantic_support_verified"])
        self.assertFalse(result["independent_llm_contexts_verified"])
        self.assertTrue(Path(result["trace_file"]).exists())

    async def test_fanout_has_two_different_contexts_and_post_main_verification(self):
        with self.controlled_git():result = await self.pipeline().run("How does memory work and what is the current branch?")
        self.assertEqual(result["route"], "fan_out")
        self.assertEqual(result["answer_status"], "answered")
        self.assertEqual(result["metrics"]["llm_calls"], 2)
        self.assertEqual(result["metrics"]["capability_calls"], 8)
        calls=result["inference_tasks"]
        self.assertEqual(calls[0]["context_keys"], ["evidence", "language", "question"])
        self.assertEqual(calls[1]["context_keys"], ["claims", "git_facts", "language", "question"])
        self.assertNotEqual(calls[0]["message_digest"], calls[1]["message_digest"])
        self.assertEqual(result["trace"][-2]["event"], "FINAL_VERIFY")

    async def test_git_only_does_not_require_index_or_a_model(self):
        (self.root / "README.md").unlink()
        with self.controlled_git():
            result = await Pipeline(self.workspace, state_dir=self.parent / "git-state", language="en", inference_factory=self.model_factory()).run("current branch")
        self.assertEqual(result["answer_status"], "answered")
        self.assertEqual(result["metrics"]["llm_calls"], 0)

    async def test_unknown_empty_retrieval_is_successful_refusal_without_model(self):
        result=await self.pipeline().run("zxqv_unicorn_transducer_9988")
        self.assertEqual(result["execution_status"], "completed")
        self.assertEqual(result["answer_status"], "unknown")
        self.assertEqual(result["metrics"]["llm_calls"], 0)
        self.assertEqual(result["claims"], [])

    async def test_model_abstention_with_retrieved_sources_completes_in_both_languages(self):
        for language,question in (("ru","Как устроена memory?"),("en","How does memory work?")):
            result=await Pipeline(self.workspace,state_dir=self.state.path,corpus=self.corpus,language=language,
                inference_factory=self.model_factory(unknown=True)).run(question)
            self.assertEqual(result["execution_status"],"completed")
            self.assertEqual(result["answer_status"],"unknown")
            self.assertEqual(result["metrics"]["llm_calls"],1)
            self.assertEqual(result["diagnostics"],["documentation_unknown"])
            self.assertEqual(result["claims"],[])
            self.assertEqual(result["citations"],[])
            self.assertEqual(result["excerpts"],[])
            self.assertIn("insufficient" if language == "en" else "Недостаточно",result["answer"])
            self.assertIn("passed",[x.get("status") for x in result["trace"] if x["event"] == "FINAL_VERIFY"])

    async def test_model_abstention_on_mixed_request_preserves_only_git_as_partial(self):
        with self.controlled_git():
            result=await self.pipeline(inference_factory=self.model_factory(unknown=True)).run("How does memory work and what is the current branch?")
        self.assertEqual(result["execution_status"],"partial")
        self.assertEqual(result["answer_status"],"partial")
        self.assertEqual(result["metrics"]["llm_calls"],1)
        self.assertEqual(result["claims"],[])
        self.assertTrue(result["git_facts"])
        self.assertIn("documentation_not_answered",result["diagnostics"])
        self.assertIn("documentation part",result["answer"])

    async def test_source_changed_after_main_blocks_claims_and_citations(self):
        with self.controlled_git():result=await self.pipeline(inference_factory=self.model_factory(change_doc=True)).run("How does memory work and what is the current branch?")
        self.assertIn(ErrorCode.INDEX_STALE.value, result["diagnostics"])
        self.assertEqual(result["claims"], [])
        self.assertEqual(result["citations"], [])
        self.assertEqual(result["excerpts"], [])

    async def test_git_changed_after_main_blocks_stale_git_fact(self):
        with self.controlled_git():result=await self.pipeline(inference_factory=self.model_factory(change_git=True)).run("How does memory work and what is the current branch?")
        self.assertIn(ErrorCode.GIT_STATE_CHANGED.value, result["diagnostics"])
        self.assertEqual(result["git_facts"], [])
        self.assertTrue(result["claims"])

    async def test_main_failure_preserves_only_validated_blocks_as_partial(self):
        with self.controlled_git():result=await self.pipeline(inference_factory=self.model_factory(fail_main=True)).run("How does memory work and what is the current branch?")
        self.assertEqual(result["answer_status"], "partial")
        self.assertEqual(result["metrics"]["model_retries"], 0)
        self.assertTrue(result["claims"] and result["git_facts"])

    async def test_chain_namespace_is_explicit_path_reference_not_basename(self):
        (self.root / "other.md").write_text("# Other\nThe wrong src/worker.py.bak file executes work.\n")
        from bublik_developer.rag.corpus import SourceSpec
        corpus=ProjectCorpus(self.workspace,[SourceSpec("README.md"),SourceSpec("other.md")]);build_index(corpus,self.state)
        payload={"role":"documentation","root":str(self.root),"workspace_identity":list(self.workspace.identity),
                 "project_id":"fixture","state_dir":str(self.state.path),"selection":[{"path":"README.md","kind":"markdown"},{"path":"other.md","kind":"markdown"}],
                 "context":{"question":"Where are changed files described?","mode":"fts","changed_paths":["src/worker.py"]}}
        data,_=worker_execute(payload)
        self.assertEqual(data["chain"]["linked_sources"],["README.md"])
        self.assertTrue(all(x["source"]=="README.md" for x in data["sources"]))

    async def test_chain_executes_documentation_only_after_git_report(self):
        with self.controlled_git():result=await self.pipeline().run("Which files changed and where is functionality documented?")
        self.assertEqual(result["route"],"chain")
        self.assertEqual(result["answer_status"],"answered")
        events=result["trace"]
        git_report=next(i for i,x in enumerate(events) if x["event"]=="REPORT" and x.get("role")=="git")
        doc_execute=next(i for i,x in enumerate(events) if x["event"]=="EXECUTE" and x.get("role")=="documentation")
        self.assertLess(git_report,doc_execute)
        self.assertIn("src/worker.py",result["claims"][0]["text"])

    async def test_chain_without_changed_files_needs_no_model_or_index(self):
        self.changed_paths=[]
        (self.state.path/'CURRENT.json').unlink()
        (self.root/'README.md').unlink()
        with self.controlled_git():result=await Pipeline(self.workspace,state_dir=self.state.path,language="en",
            inference_factory=self.model_factory()).run("Which files changed and where is functionality documented?")
        self.assertEqual(result["answer_status"],"answered")
        self.assertEqual(result["metrics"]["llm_calls"],0)

    async def test_chain_unlinked_paths_explain_absent_association_and_four_path_limit(self):
        self.changed_paths=[f"src/undocumented-{i}.py" for i in range(6)]
        with self.controlled_git():
            result=await self.pipeline().run("Which files changed and where is functionality documented?")
        self.assertEqual(result["execution_status"],"partial")
        self.assertEqual(result["metrics"]["llm_calls"],0)
        self.assertIn("no_documented_path_association",result["diagnostics"])
        self.assertIn("No exact documentation associations",result["answer"])
        self.assertIn("first four",result["answer"])
        self.assertEqual(result["claims"],[])

    async def test_budget_exhaustion_never_publishes_unverified_model_claim(self):
        result=await self.pipeline(max_calls=2).run("How does memory work?")
        self.assertEqual(result["claims"],[])
        self.assertEqual(result["metrics"]["llm_calls"],0)

    async def test_ambiguous_query_has_no_task_or_model_and_pipeline_is_single_use(self):
        pipeline=self.pipeline();result=await pipeline.run("branch and status")
        self.assertEqual(result["answer_status"],"unknown")
        self.assertEqual(result["metrics"]["capability_calls"],0)
        self.assertIn("Split it into separate questions",result["answer"])
        with self.assertRaises(DeveloperError):await pipeline.run("current branch")
