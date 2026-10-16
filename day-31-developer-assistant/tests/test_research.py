"""Synthetic pipeline/model fixtures; real Git/FTS/state and exclusive reports."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import AsyncMock,patch

import test_pipeline as fixtures
from bublik_developer.contracts import Role
from bublik_developer.errors import DeveloperError,ErrorCode
from bublik_developer.inference_tasks import InferenceTasks
from bublik_developer.research import (load_cases,select_cases,generation_bound,conditions,freeze,
    validate_freeze,GenerationSlots,limited_inference,structural_outcome,result_models_match,
    new_output,write_new,evaluate,review_template,summarize,inspect_retrieval)
from bublik_developer.routing import route


class ResearchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixture=fixtures.PipelineTests();self.fixture.setUp();self.addCleanup(self.fixture.temp.cleanup)
        self.document,self.digest=load_cases()
        self.selected=select_cases(self.document)
        self.current=conditions(self.fixture.workspace,self.fixture.state)
        self.frozen={"format":"bublik-research-freeze-v1","conditions":self.current,
                     "model":{"name":"qwen2.5:14b","digest":"a"*64,"quantization":"Q4_K_M"}}
        self.model_patch=patch("bublik_developer.research.inspect_model",return_value={"model":self.frozen["model"],"metadata_http_events":[],"generation_calls":0})
        self.model_patch.start();self.addCleanup(self.model_patch.stop)
        self.output=self.fixture.parent/"evaluation.json"

    def test_new_cases_are_twenty_paired_questions_and_core_cap_is_six(self):
        self.assertEqual(len(self.document["cases"]),20)
        self.assertEqual(sum(x["language"]=="ru" for x in self.document["cases"]),10)
        self.assertEqual(sum(generation_bound(x["question"]) for x in self.selected),6)
        self.assertEqual(len(self.selected),4)
        for case in self.document["cases"]:
            try:kind=route(case["question"]).kind
            except DeveloperError:kind="denied"
            self.assertEqual(kind,case["expected_route"],case["id"])

    def test_conditions_pin_code_corpus_policy_profile_and_git_without_model(self):
        self.assertEqual(self.current["pipeline_mode"],"fts")
        self.assertEqual(self.current["dense_policy"],"vocabulary")
        self.assertEqual(self.current["hybrid_policy"],"raw")
        self.assertEqual(self.current["model_options"]["num_ctx"],8192)
        self.assertIn("git_branch",self.current)
        self.assertTrue(self.current["source_sha256"])

    def test_changed_conditions_are_refused(self):
        validate_freeze(self.frozen,self.current)
        for field in ("cases_sha256","source_sha256","index","git_branch","model_options"):
            changed=deepcopy(self.current);changed[field]="changed"
            with self.assertRaises(DeveloperError):validate_freeze(self.frozen,changed)

    def test_freeze_uses_only_metadata_and_no_generation(self):
        self.model_patch.stop()
        from contextlib import contextmanager
        @contextmanager
        def lease(*args):yield fixtures.FakeLease()
        with patch("bublik_developer.research.ModelSession.lease",side_effect=lease),patch("bublik_developer.research.Qwen.identity",return_value=self.frozen["model"]),patch("bublik_developer.research.Qwen.generate") as generate:
            value=freeze(self.fixture.workspace,self.fixture.state)
        generate.assert_not_called()
        self.assertEqual(value["generation_calls"],0)
        self.assertEqual(value["conditions"],self.current)

    def test_labels_and_reports_do_not_enter_project_index(self):
        before=self.fixture.corpus.collect().revision
        folder=self.fixture.root/"day-31-developer-assistant/evaluation";folder.mkdir(parents=True)
        (folder/"research_cases.json").write_text('LABEL_CANARY_882019')
        self.assertEqual(self.fixture.corpus.collect().revision,before)

    def test_slots_reserve_before_failure_and_do_not_refund(self):
        slots=GenerationSlots(1);events=[];slots.on_reserve=lambda:events.append(slots.used)
        slots.reserve()
        with self.assertRaises(DeveloperError):slots.reserve()
        self.assertEqual(slots.used,1)
        self.assertEqual(events,[1])

    async def test_limited_inference_blocks_second_attempt_after_lost_first(self):
        from bublik_developer.pipeline import Budget
        slots=GenerationSlots(1);models=limited_inference(slots)(self.fixture.workspace,"a"*32,lambda *a,**kw:None,Budget())
        with patch.object(InferenceTasks,"run",new=AsyncMock(side_effect=DeveloperError(ErrorCode.LLM_UNAVAILABLE))) as run:
            with self.assertRaises(DeveloperError):await models.run(Role.DOCUMENTATION,fixtures.documentation_context())
            with self.assertRaises(DeveloperError) as caught:await models.run(Role.DOCUMENTATION,fixtures.documentation_context())
        self.assertEqual(caught.exception.code,ErrorCode.CONTEXT_BUDGET)
        self.assertEqual(run.await_count,1)

    def test_output_is_exclusive_and_outside_project(self):
        new_output(self.output,self.fixture.workspace);write_new(self.output,{"value":1})
        with self.assertRaises(DeveloperError):new_output(self.output)
        with self.assertRaises(DeveloperError):new_output(self.fixture.root/"report.json",self.fixture.workspace)
        self.assertEqual(json.loads(self.output.read_text()),{"value":1})

    def test_case_selection_rejects_unknown_and_duplicate_ids(self):
        for ids in (["missing"],[self.selected[0]["id"]]*2,[]):
            with self.assertRaises(DeveloperError):select_cases(self.document,ids)

    def custom_cases(self):
        document=deepcopy(self.document)
        document["cases"]=document["cases"][:1]
        document["batch_core"]=[document["cases"][0]["id"]]
        document["cases"][0]["required_points"]=["PRIVATE_LABEL_CANARY_98117"]
        path=self.fixture.parent/"custom-cases.json"
        path.write_text(json.dumps(document))
        return path,document

    def test_custom_case_digest_is_frozen_and_clarification_cli_plan_is_model_free(self):
        import subprocess,sys
        from bublik_developer.research import ROOT
        path,document=self.custom_cases()
        observed=freeze(self.fixture.workspace,self.fixture.state,cases_path=path)
        self.assertEqual(observed["conditions"]["cases_sha256"],load_cases(path)[1])
        self.assertNotEqual(observed["conditions"]["cases_sha256"],self.current["cases_sha256"])
        with self.assertRaises(DeveloperError):validate_freeze(observed,self.current)
        catalog=ROOT/"evaluation/research_clarifications.json"
        planned=subprocess.run([sys.executable,str(ROOT/"scripts/research_project.py"),"plan","--cases",str(catalog)],
                               capture_output=True,text=True,check=True,timeout=10)
        value=json.loads(planned.stdout)
        self.assertEqual(value["request_count"],4)
        self.assertEqual(value["generation_upper_bound"],6)
        self.assertFalse(value["inference_performed"])
        self.assertEqual(value["cases_sha256"],load_cases(catalog)[1])

    async def test_custom_catalog_guard_and_labels_stay_outside_pipeline(self):
        path,document=self.custom_cases();frozen=freeze(self.fixture.workspace,self.fixture.state,cases_path=path)
        capture=[]
        result=await evaluate(self.fixture.workspace,self.fixture.state,frozen,select_cases(document),output=self.output,
                              cases_path=path,pipeline_factory=self.fake_pipeline(capture=capture))
        self.assertEqual(result["status"],"completed")
        self.assertEqual(result["frozen_conditions"]["conditions"]["cases_sha256"],load_cases(path)[1])
        self.assertNotIn("cases_path",capture[0])
        self.assertNotIn("PRIVATE_LABEL_CANARY_98117",json.dumps(result))
        other_output=self.fixture.parent/"wrong-catalog.json"
        with self.assertRaises(DeveloperError):
            await evaluate(self.fixture.workspace,self.fixture.state,frozen,select_cases(document),output=other_output,
                           pipeline_factory=self.fake_pipeline())
        self.assertFalse(other_output.exists())

    async def test_custom_catalog_change_after_answer_stops_without_repair(self):
        path,document=self.custom_cases();frozen=freeze(self.fixture.workspace,self.fixture.state,cases_path=path)
        parent=self.fake_pipeline()
        class MutatingPipeline(parent):
            async def run(self,question):
                result=await super().run(question)
                changed=deepcopy(document);changed["cases"][0]["required_points"].append("changed rubric")
                path.write_text(json.dumps(changed))
                return result
        result=await evaluate(self.fixture.workspace,self.fixture.state,frozen,select_cases(document),output=self.output,
                              cases_path=path,pipeline_factory=MutatingPipeline)
        self.assertEqual(result["status"],"stopped")
        self.assertEqual(result["error"],ErrorCode.WORKSPACE_CHANGED.value)
        self.assertFalse(result["requests"][0]["conditions_valid_after"])
        self.assertEqual(len(result["requests"]),1)

    async def test_substituted_case_labels_and_wrong_review_catalog_are_rejected(self):
        import subprocess,sys
        from bublik_developer.research import ROOT
        path,document=self.custom_cases();frozen=freeze(self.fixture.workspace,self.fixture.state,cases_path=path)
        substituted=select_cases(deepcopy(document));substituted[0]["required_points"]=["substituted rubric"]
        with self.assertRaises(DeveloperError):
            await evaluate(self.fixture.workspace,self.fixture.state,frozen,substituted,output=self.output,
                           cases_path=path,pipeline_factory=self.fake_pipeline())
        self.assertFalse(self.output.exists())
        result=await evaluate(self.fixture.workspace,self.fixture.state,frozen,select_cases(document),output=self.output,
                              cases_path=path,pipeline_factory=self.fake_pipeline())
        changed=deepcopy(document);changed["cases"][0]["required_points"]=["changed review rubric"]
        path.write_text(json.dumps(changed));review=self.fixture.parent/"wrong-review.json"
        run=subprocess.run([sys.executable,str(ROOT/"scripts/research_project.py"),"review-template","--root",str(self.fixture.root),
            "--cases",str(path),"--report",str(self.output),"--output",str(review)],capture_output=True,text=True,timeout=10)
        self.assertEqual(run.returncode,2)
        self.assertEqual(json.loads(run.stdout)["error"]["code"],ErrorCode.WORKSPACE_CHANGED.value)
        self.assertFalse(review.exists())

    def test_structural_checks_do_not_claim_semantic_acceptance(self):
        result={"route":"documentation","answer_status":"answered","citations":[{"source":self.selected[0]["rubric_sources"][0]}]}
        value=structural_outcome(self.selected[0],result)
        self.assertTrue(value["expected_source_present"])
        self.assertEqual(value["semantic_review"],"pending")
        self.assertFalse(value["semantic_support_verified"])

    def fake_pipeline(self,*,technical=False,capture=None,reply=None):
        class FixturePipeline:
            def __init__(self,workspace,**kwargs):
                if capture is not None:capture.append(kwargs)
            async def run(self,question):
                if reply is not None:return deepcopy(reply)
                return {"route":"documentation","answer_status":"answered","execution_status":"failed" if technical else "completed",
                        "answer":"Synthetic fixture answer.","diagnostics":[ErrorCode.LLM_UNAVAILABLE.value] if technical else [],
                        "citations":[],"git_facts":[],"inference_tasks":[],
                        "metrics":{"known_llm_calls":0,"llm_calls":0,"unknown_inference_attempts":0,"input_tokens":0,"output_tokens":0}}
        return FixturePipeline

    async def test_pipeline_inputs_exclude_labels_and_review_is_pending(self):
        capture=[]
        result=await evaluate(self.fixture.workspace,self.fixture.state,self.frozen,self.selected[:2],output=self.output,
                              pipeline_factory=self.fake_pipeline(capture=capture))
        self.assertEqual(result["status"],"completed")
        self.assertEqual(len(result["requests"]),2)
        self.assertEqual(set(capture[0]),{"state_dir","language","mode","max_calls","timeout","inference_factory"})
        review=review_template(result,self.document)
        self.assertEqual(review["status"],"pending")
        self.assertTrue(all(x is None for x in review["reviews"][0]["scores"].values()))
        self.assertEqual(result["summary"]["semantic_acceptance"],"not_evaluated")

    async def test_generation_cap_rejects_batch_before_pipeline_or_file_creation(self):
        with self.assertRaises(DeveloperError):
            await evaluate(self.fixture.workspace,self.fixture.state,self.frozen,self.selected,output=self.output,
                           max_generation_calls=5,pipeline_factory=AsyncMock())
        self.assertFalse(self.output.exists())

    async def test_technical_failure_stops_without_repair_or_next_request(self):
        result=await evaluate(self.fixture.workspace,self.fixture.state,self.frozen,self.selected[:2],output=self.output,
                              pipeline_factory=self.fake_pipeline(technical=True))
        self.assertEqual(result["status"],"stopped")
        self.assertEqual(len(result["requests"]),1)
        self.assertEqual(json.loads(self.output.read_text())["status"],"stopped")

    def test_failed_execution_is_not_an_expected_unknown_outcome(self):
        case=select_cases(self.document,["unknown-en"])[0]
        result={"route":"documentation","answer_status":"unknown","execution_status":"failed",
                "diagnostics":["documentation_unknown","documentation_not_answered"]}
        value=structural_outcome(case,result)
        self.assertTrue(value["answer_status_expected"])
        self.assertFalse(value["execution_status_expected"])

    async def test_failed_execution_without_typed_error_stops_next_case(self):
        reply={"route":"documentation","answer_status":"unknown","execution_status":"failed",
               "diagnostics":["documentation_unknown","documentation_not_answered"]}
        cases=select_cases(self.document,["unknown-ru","unknown-en"])
        result=await evaluate(self.fixture.workspace,self.fixture.state,self.frozen,cases,output=self.output,
                              pipeline_factory=self.fake_pipeline(reply=reply))
        self.assertEqual(result["status"],"stopped")
        self.assertEqual(result["error"],"technical_request_failure")
        self.assertEqual(len(result["requests"]),1)
        self.assertEqual(result["summary"]["failed_requests"],1)

    async def test_completed_abstention_continues_without_becoming_semantic_pass(self):
        reply={"route":"documentation","answer_status":"unknown","execution_status":"completed",
               "diagnostics":["documentation_unknown"],"metrics":{"input_tokens":0,"output_tokens":0}}
        cases=select_cases(self.document,["unknown-ru","unknown-en"])
        result=await evaluate(self.fixture.workspace,self.fixture.state,self.frozen,cases,output=self.output,
                              pipeline_factory=self.fake_pipeline(reply=reply))
        self.assertEqual(result["status"],"completed")
        self.assertEqual(len(result["requests"]),2)
        self.assertEqual(result["summary"]["failed_requests"],0)
        self.assertTrue(all(x["structural_checks"]["execution_status_expected"] for x in result["requests"]))
        self.assertEqual(result["summary"]["semantic_acceptance"],"not_evaluated")

    async def test_partial_typed_error_stops_and_counts_technical_failure_separately(self):
        reply={"route":"documentation","answer_status":"partial","execution_status":"partial",
               "diagnostics":[ErrorCode.INVALID_MODEL_OUTPUT.value],"claims":[],"citations":[],
               "excerpts":[{"source":"README.md","quote":"Synthetic verified excerpt."}]}
        result=await evaluate(self.fixture.workspace,self.fixture.state,self.frozen,self.selected[:2],output=self.output,
                              pipeline_factory=self.fake_pipeline(reply=reply))
        self.assertEqual(result["status"],"stopped")
        self.assertEqual(len(result["requests"]),1)
        self.assertEqual(result["summary"]["failed_requests"],0)
        self.assertEqual(result["summary"]["technical_failure_requests"],1)
        self.assertTrue(result["requests"][0]["result"]["excerpts"])

    def test_retrieval_inspection_uses_real_worker_limits_without_model_or_labels(self):
        cases=select_cases(self.document,["owner-en","liveness-branch-en"])
        self.model_patch.stop()
        with patch("bublik_developer.research.inspect_model") as metadata,patch("bublik_developer.research.Qwen.generate") as generate:
            value=inspect_retrieval(self.fixture.workspace,self.fixture.state,self.frozen,cases)
        metadata.assert_not_called();generate.assert_not_called()
        self.assertEqual(value["generation_calls"],0)
        self.assertEqual(value["model_http_calls"],0)
        first=value["requests"][0]
        self.assertTrue(first["data"]["sources"])
        self.assertEqual(first["data"]["settings"]["final_k"],3)
        self.assertEqual(first["data"]["settings"]["context_bytes"],4096)
        self.assertNotIn("branch",value["requests"][1]["documentation_question"])
        self.assertNotIn("required_points",json.dumps(value))
        self.assertNotIn("rubric_sources",json.dumps(value))

    def test_retrieval_inspection_refuses_changed_freeze_and_dependent_chain(self):
        changed=deepcopy(self.frozen);changed["conditions"]["git_branch"]="other"
        with patch("bublik_developer.agent_worker.execute") as worker:
            with self.assertRaises(DeveloperError):
                inspect_retrieval(self.fixture.workspace,self.fixture.state,changed,self.selected[:1])
            worker.assert_not_called()
        with self.assertRaises(DeveloperError):
            inspect_retrieval(self.fixture.workspace,self.fixture.state,self.frozen,select_cases(self.document,["chain-en"]))

    async def test_conditions_changed_after_answer_stop_comparison(self):
        changed=deepcopy(self.current);changed["git_branch"]="other"
        with patch("bublik_developer.research.conditions",side_effect=[self.current,self.current,changed]):
            result=await evaluate(self.fixture.workspace,self.fixture.state,self.frozen,self.selected[:1],output=self.output,
                                  pipeline_factory=self.fake_pipeline())
        self.assertEqual(result["error"],ErrorCode.WORKSPACE_CHANGED.value)
        self.assertFalse(result["requests"][0]["conditions_valid_after"])

    async def test_changed_model_is_detected_before_pipeline_request(self):
        capture=[]
        with patch("bublik_developer.research.inspect_model",return_value={"model":{"name":"changed"},"metadata_http_events":[],"generation_calls":0}):
            result=await evaluate(self.fixture.workspace,self.fixture.state,self.frozen,self.selected[:1],output=self.output,pipeline_factory=self.fake_pipeline(capture=capture))
        self.assertEqual(result["status"],"stopped")
        self.assertEqual(capture,[])
        self.assertEqual(result["generation_slots_reserved"],0)

    async def test_real_write_router_is_denied_without_model_and_uses_requested_language(self):
        case=select_cases(self.document,["write-ru"])
        before=(self.fixture.root/"README.md").read_bytes()
        result=await evaluate(self.fixture.workspace,self.fixture.state,self.frozen,case,output=self.output,max_generation_calls=0)
        self.assertEqual(result["requests"][0]["result"]["answer_status"],"denied")
        self.assertIn("записи запрещена",result["requests"][0]["result"]["answer"])
        self.assertEqual(result["summary"]["known_llm_calls"],0)
        self.assertEqual((self.fixture.root/"README.md").read_bytes(),before)

    def test_synthetic_or_changed_model_is_not_marked_real(self):
        for transport,model in (("synthetic_test_transport",self.frozen["model"]),("ollama_loopback_http",{"name":"changed"})):
            result={"inference_tasks":[{"llm_calls":1,"model":model,"transport":transport}]}
            self.assertFalse(result_models_match(result,self.frozen["model"]))

    def test_inflight_reserved_call_remains_unknown(self):
        report={"generation_slots_reserved":1,"requests":[{"status":"started","generation_slots_before":0}]}
        result=summarize(report)
        self.assertIsNone(result["llm_calls"])
        self.assertEqual(result["unknown_inference_attempts"],1)
        self.assertIsNone(result["input_tokens"])
        self.assertIsNone(result["output_tokens"])
