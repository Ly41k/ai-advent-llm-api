"""Frozen, bounded production-pipeline evaluation; labels never enter model context."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from time import perf_counter

from . import __version__
from .contracts import Role, canonical
from .errors import DeveloperError, ErrorCode
from .generation import DOC_SCHEMA_VERSION, OPTIONS, PROMPT_VERSION, Qwen, GENERATION_BUDGET_POLICY
from .inference_tasks import InferenceTasks
from .model_session import ModelSession
from .pipeline import Pipeline
from .rag.corpus import ProjectCorpus
from .rag.index import ProjectIndex
from .rag.retrieval import ENDPOINT_POLICY_VERSION, QUERY_DEFAULTS_VERSION, query_terms, resolve_dense_query
from .rag.state import ProjectState
from .routing import route

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "evaluation/research_cases.json"


def code_digests():
    return {p.relative_to(ROOT).as_posix():sha256(p.read_bytes()).hexdigest()
            for p in sorted(ROOT.rglob("*.py")) if not {".venv","__pycache__"}.intersection(p.parts)}


def load_cases(path=CASES):
    raw = Path(path).read_bytes()
    try:
        value = json.loads(raw)
        cases = value["cases"]
    except (ValueError,TypeError,KeyError):
        raise DeveloperError(ErrorCode.INVALID_INPUT) from None
    if (value.get("format") != "bublik-research-cases-v1" or not isinstance(cases,list)
            or not 1 <= len(cases) <= 40 or any(not isinstance(x,dict) for x in cases)):
        raise DeveloperError(ErrorCode.INVALID_INPUT)
    for case in cases:
        if (set(case) != {"id","language","question","expected_route","acceptable_answer_status","rubric_sources","required_points"}
                or not isinstance(case["id"],str) or not 1 <= len(case["id"]) <= 64
                or not isinstance(case["language"],str) or case["language"] not in {"ru","en"}
                or not isinstance(case["question"],str) or not isinstance(case["required_points"],list)):
            raise DeveloperError(ErrorCode.INVALID_INPUT)
    if len({x["id"] for x in cases}) != len(cases):raise DeveloperError(ErrorCode.INVALID_INPUT)
    return value,sha256(raw).hexdigest()


def generation_bound(question):
    try:
        planned = route(question)
    except DeveloperError as error:
        if error.code == ErrorCode.PERMISSION_DENIED:return 0
        raise
    return 2 if planned.kind in {"fan_out","chain"} else 1 if planned.kind == "documentation" else 0


def select_cases(document, ids=None):
    ids = document["batch_core"] if ids is None else ids
    catalog = {case["id"]:case for case in document["cases"]}
    if not ids or len(ids) != len(set(ids)) or any(key not in catalog for key in ids):
        raise DeveloperError(ErrorCode.INVALID_INPUT)
    return [catalog[key] for key in ids]


def new_output(path, workspace=None):
    path = Path(path).absolute()
    if path.exists() or path.is_symlink():raise DeveloperError(ErrorCode.PERMISSION_DENIED)
    if workspace and path.resolve().is_relative_to(workspace.root):
        raise DeveloperError(ErrorCode.PERMISSION_DENIED)
    return path


def write_new(path, value):
    fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as stream:
        stream.write(canonical(value));stream.write("\n");stream.flush();os.fsync(stream.fileno())


def checkpoint(path, value):
    """Replace only the fresh report exclusively created by this invocation."""
    fd, temporary = tempfile.mkstemp(prefix=".research-",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            stream.write(canonical(value));stream.write("\n");stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def conditions(workspace, state, *, cases_path=CASES):
    corpus = ProjectCorpus(workspace)
    with ProjectIndex.current(state,corpus) as index:
        index.verify()
        metadata = dict(index.metadata)
    _,head = workspace.command("rev-parse","--verify","HEAD",allowed_codes=(0,128))
    branch_code,branch = workspace.command("symbolic-ref","--quiet","--short","HEAD",allowed_codes=(0,1))
    return {"version":__version__,"project_id":workspace.project_id,"source_sha256":code_digests(),
            "git_head":head.decode("utf-8").strip() or None,"git_branch":branch.decode("utf-8").strip() if branch_code == 0 else None,
            "index":metadata,"cases_sha256":load_cases(cases_path)[1],"pipeline_mode":"fts",
            "model_options":dict(OPTIONS),"prompt_version":PROMPT_VERSION,
            "documentation_schema_version":DOC_SCHEMA_VERSION,
            "generation_budget_policy":GENERATION_BUDGET_POLICY,
            "query_defaults_version":QUERY_DEFAULTS_VERSION,
            "fts_endpoint_policy":ENDPOINT_POLICY_VERSION,
            "dense_policy":resolve_dense_query("dense","auto"),"hybrid_policy":resolve_dense_query("hybrid","auto"),
            "capability_limit":8,"request_deadline":300,"warmups":0,"token_probes":0}


def inspect_model(workspace):
    with ModelSession(workspace).lease() as lease:
        client = Qwen(lease)
        identity = client.identity()  # Metadata only, never /api/chat or embedding.
    return {"model":identity,"metadata_http_events":client.http_events,"generation_calls":0}


def freeze(workspace, state, *, cases_path=CASES):
    value = conditions(workspace,state,cases_path=cases_path)
    observed = inspect_model(workspace)
    return {"format":"bublik-research-freeze-v1","created_at":datetime.now(timezone.utc).isoformat(),
            "conditions":value,"model":observed["model"],"metadata_http_events":observed["metadata_http_events"],
            "generation_calls":0,"embedding_calls":0,"scope":"production multi-context quality evaluation; comparisons remain pending"}


def validate_freeze(value, current):
    if (not isinstance(value,dict) or value.get("format") != "bublik-research-freeze-v1"
            or value.get("conditions") != current or not isinstance(value.get("model"),dict)):
        raise DeveloperError(ErrorCode.WORKSPACE_CHANGED)


class GenerationSlots:
    """A lost or preflight-failed attempt still consumes its reservation."""
    def __init__(self, limit):
        if type(limit) is not int or not 0 <= limit <= 32:raise DeveloperError(ErrorCode.INVALID_INPUT)
        self.limit,self.used = limit,0
        self.on_reserve = None
    def reserve(self):
        if self.used >= self.limit:raise DeveloperError(ErrorCode.CONTEXT_BUDGET)
        self.used += 1
        if self.on_reserve:self.on_reserve()


def limited_inference(slots):
    class LimitedInference(InferenceTasks):
        async def run(self,role,context,*,final=True):
            slots.reserve()
            return await super().run(role,context,final=final)
    return LimitedInference


def structural_outcome(case,result):
    """Route/outcome/provenance shape only; no semantic correctness score."""
    expected_sources = set(case["rubric_sources"])
    citations = result.get("citations",[])
    expected_execution = {"answered":"completed","unknown":"completed","partial":"partial","denied":"denied"}.get(result.get("answer_status"))
    return {"route_matches":result.get("route") == case["expected_route"],
            "answer_status_expected":result.get("answer_status") in case["acceptable_answer_status"],
            "execution_status_expected":expected_execution is not None and result.get("execution_status") == expected_execution,
            "expected_source_present":bool(expected_sources & {x["source"] for x in citations}) if expected_sources else None,
            "semantic_review":"pending","semantic_support_verified":False}


def result_models_match(result,model):
    for task in result.get("inference_tasks",[]):
        if task.get("llm_calls") == 1 and (task.get("model") != model or task.get("transport") != "ollama_loopback_http"):
            return False
    return True


def inspect_retrieval(workspace,state,frozen,cases,*,cases_path=CASES):
    """Reobserve the production FTS worker inputs; no answer, Git, or model call.

    This is a new observation, not reconstruction of a previous model context.
    Use its exact 3-source/4096-byte worker limits rather than CLI defaults.
    """
    from .agent_worker import execute
    validate_freeze(frozen,conditions(workspace,state,cases_path=cases_path))
    rows = []
    for case in cases:
        planned = route(case["question"])
        if planned.kind not in {"documentation","fan_out"}:
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        data,outcome = execute({"role":Role.DOCUMENTATION,"root":str(workspace.root),
            "workspace_identity":list(workspace.identity),"project_id":workspace.project_id,
            "state_dir":str(state.path),"selection":None,
            "context":{"question":planned.documentation_question,"mode":"fts"}})
        validate_freeze(frozen,conditions(workspace,state,cases_path=cases_path))
        rows.append({"case_id":case["id"],"question":case["question"],
            "documentation_question":planned.documentation_question,"terms":query_terms(planned.documentation_question),
            "worker_outcome":outcome,"data":data,"conditions_valid_after":True})
    return {"format":"bublik-research-retrieval-inspection-v1","version":__version__,"status":"completed",
        "freeze_sha256":sha256(canonical(frozen).encode()).hexdigest(),"requests":rows,
        "generation_calls":0,"embedding_calls":0,"model_http_calls":0,
        "scope":"new FTS observation using production worker limits; previous Qwen input is not reconstructed"}


def technical_failure(result):
    return (result.get("execution_status") != "denied" and
            (result.get("execution_status") == "failed" or
             any(code in {x.value for x in ErrorCode} for code in result.get("diagnostics",[]))))


def summarize(report):
    rows = [x for x in report["requests"] if "result" in x]
    metrics = [x["result"].get("metrics",{}) for x in rows]
    unknown = sum(x.get("unknown_inference_attempts",0) for x in metrics)
    inflight = [x for x in report["requests"] if "result" not in x]
    unknown += sum(max(0,report["generation_slots_reserved"]-x.get("generation_slots_before",report["generation_slots_reserved"])) for x in inflight)
    known = sum(x.get("known_llm_calls",0) for x in metrics)
    return {"requests_completed":len(rows),"generation_slots_reserved":report["generation_slots_reserved"],
            "failed_requests":sum(x["result"].get("execution_status") == "failed" for x in rows),
            "technical_failure_requests":sum(technical_failure(x["result"]) for x in rows),
            "known_llm_calls":known,"unknown_inference_attempts":unknown,
            "llm_calls":known if not unknown else None,
            "input_tokens":sum(x.get("input_tokens",0) or 0 for x in metrics) if not unknown and all(x.get("input_tokens") is not None for x in metrics) else None,
            "output_tokens":sum(x.get("output_tokens",0) or 0 for x in metrics) if not unknown and all(x.get("output_tokens") is not None for x in metrics) else None,
            "semantic_acceptance":"not_evaluated","single_multi_comparison":"not_run"}


async def evaluate(workspace,state,frozen,cases,*,output,max_generation_calls=6,pipeline_factory=Pipeline,cases_path=CASES):
    planned = sum(generation_bound(case["question"]) for case in cases)
    slots = GenerationSlots(max_generation_calls)
    if planned > max_generation_calls:raise DeveloperError(ErrorCode.CONTEXT_BUDGET)
    validate_freeze(frozen,conditions(workspace,state,cases_path=cases_path))
    document,_=load_cases(cases_path)
    if cases != select_cases(document,[case["id"] for case in cases]):
        raise DeveloperError(ErrorCode.WORKSPACE_CHANGED)
    output = new_output(output,workspace)
    report = {"format":"bublik-research-evaluation-v1","status":"running","version":__version__,
        "created_at":datetime.now(timezone.utc).isoformat(),"freeze_sha256":sha256(canonical(frozen).encode()).hexdigest(),
        "frozen_conditions":frozen,"planned_case_ids":[x["id"] for x in cases],"planned_generation_upper_bound":planned,
        "generation_cap":max_generation_calls,"generation_slots_reserved":0,"requests":[],"metadata_checks":[],"error":None,
        "scope":"production multi-context FTS pipeline; human review pending; no single/multi benchmark yet"}
    write_new(output,report)
    def reserved():
        report["generation_slots_reserved"]=slots.used
        checkpoint(output,report)
    slots.on_reserve=reserved
    try:
        for case in cases:
            started = perf_counter()
            validate_freeze(frozen,conditions(workspace,state,cases_path=cases_path))
            observed = inspect_model(workspace)
            report["metadata_checks"].append({"case_id":case["id"],**observed})
            checkpoint(output,report)
            if observed["model"] != frozen["model"]:raise DeveloperError(ErrorCode.LLM_UNAVAILABLE)
            row = {"case_id":case["id"],"language":case["language"],"question":case["question"],"status":"started",
                   "conditions_valid_after":False,"generation_slots_before":slots.used}
            report["requests"].append(row);checkpoint(output,report)
            try:
                result = await pipeline_factory(workspace,state_dir=state.path,language=case["language"],mode="fts",
                    max_calls=8,timeout=300,inference_factory=limited_inference(slots)).run(case["question"])
            except DeveloperError as error:
                # A router permission refusal is an expected, model-free result.
                if error.code != ErrorCode.PERMISSION_DENIED or generation_bound(case["question"]) != 0:raise
                result = {"route":"denied","answer_status":"denied","execution_status":"denied","diagnostics":[error.code.value],
                          "claims":[],"citations":[],"git_facts":[],
                          "answer":"Операция записи запрещена: ассистент работает только для чтения." if case["language"] == "ru" else "Read-only policy denied the requested write.",
                          "inference_tasks":[],"metrics":{"llm_calls":0,"known_llm_calls":0,"unknown_inference_attempts":0,
                                                        "input_tokens":0,"output_tokens":0}}
            row.update(status="finished",result=result,structural_checks=structural_outcome(case,result))
            report["generation_slots_reserved"] = slots.used;checkpoint(output,report)
            validate_freeze(frozen,conditions(workspace,state,cases_path=cases_path))
            row.update(conditions_valid_after=True,evaluation_case_seconds=perf_counter()-started)
            if not result_models_match(result,frozen["model"]):raise DeveloperError(ErrorCode.LLM_UNAVAILABLE)
            if technical_failure(result):
                report["status"]="stopped";report["error"]="technical_request_failure";break
        else:
            report["status"]="completed"
    except DeveloperError as error:
        report.update(status="stopped",error=error.code.value)
    except (OSError,ValueError):
        report.update(status="stopped",error="research_io_or_format_failure")
    finally:
        report["generation_slots_reserved"]=slots.used
        report["summary"]=summarize(report)
        checkpoint(output,report)
    return report


def review_template(report,document):
    catalog={x["id"]:x for x in document["cases"]}
    return {"format":"bublik-research-human-review-v1","evaluation_sha256":sha256(canonical(report).encode()).hexdigest(),
            "status":"pending","reviewer":None,
            "scale":"0 wrong, 1 partial, 2 correct; every score and explanation must be supplied by a reviewer",
            "reviews":[{"case_id":row["case_id"],"question":row["question"],"answer":row["result"]["answer"],
                        "required_points":catalog[row["case_id"]]["required_points"],
                        "citations":row["result"].get("citations",[]),"git_facts":row["result"].get("git_facts",[]),
                        "scores":{key:None for key in ("correctness","completeness","support","language","usefulness")},"comment":""}
                       for row in report["requests"] if "result" in row]}
