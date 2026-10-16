"""Paired synthesis on identical FTS/Git snapshots, separate from end-to-end tests."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from time import perf_counter

from . import __version__
from .baseline import BASELINE_VERSION, BaselineTasks
from .contracts import Role, canonical
from .errors import DeveloperError, ErrorCode
from .inference_tasks import InferenceTasks
from .pipeline import Pipeline, git_text
from .research import (conditions, freeze, validate_freeze, load_cases, select_cases, inspect_model,
    GenerationSlots, new_output, write_new, checkpoint, summarize, structural_outcome,
    technical_failure, result_models_match, limited_inference)
from .routing import route

SPEC = {"version": "paired-snapshot-v2", "baseline": BASELINE_VERSION,
    "modes": ["single", "multi"], "retrieval": "fts", "order": "catalog-gray-parity-repeat-flip-v1",
    "request_capability_limit": 8, "request_deadline_seconds": 300,
    "per_call_output_limit": 1024, "warmups": 0, "token_probes": 0,
    "cold_warm_control": "not_controlled_in_runner_smoke", "resource_measurement": "not_run",
    "scope": "same snapshot synthesis; known regression smoke, not held-out or end-to-end"}


def catalog_design(document, cases_digest):
    """Frozen research labels describe the experiment; never enter inference."""
    kind = document.get("evaluation_kind", "known_regression")
    scope = document.get("scope", "known regression catalog")
    if (not isinstance(kind, str) or kind not in {"known_regression", "prespecified_new_questions"} or
        not isinstance(scope, str) or not 1 <= len(scope) <= 2000):
        raise DeveloperError(ErrorCode.INVALID_INPUT)
    return {"kind": kind, "cases_sha256": cases_digest,
            "scope": scope,
            "case_count": len(document["cases"]), "human_review": "pending",
            "independent_semantic_acceptance": False}


def comparison_spec(document, cases_digest):
    value = deepcopy(SPEC)
    design = catalog_design(document, cases_digest)
    if design["kind"] == "prespecified_new_questions":
        value["version"] = "paired-snapshot-prespecified-v2"
        value["scope"] = "same snapshot synthesis; prespecified new questions, human review pending; not end-to-end"
    return value


def paired_freeze(workspace, state, *, cases_path):
    document, digest = load_cases(cases_path)
    design = catalog_design(document, digest)
    spec = comparison_spec(document, digest)
    value = freeze(workspace, state, cases_path=cases_path)
    if value["conditions"]["cases_sha256"] != digest:
        raise DeveloperError(ErrorCode.WORKSPACE_CHANGED)
    value.update(comparison_spec=spec, scope=spec["scope"], catalog_design=design)
    return value


def validate_paired_freeze(frozen, workspace, state, cases_path):
    validate_freeze(frozen, conditions(workspace, state, cases_path=cases_path))
    document, digest = load_cases(cases_path)
    if (frozen.get("comparison_spec") != comparison_spec(document, digest) or
        frozen.get("catalog_design") != catalog_design(document, digest)):
        raise DeveloperError(ErrorCode.WORKSPACE_CHANGED)


def pair_order(index, repeat=0):
    """Frozen catalog position, independent of batching; invert each repeat.

    Gray parity gives S/M/M/S blocks instead of correlating all alternating
    language pairs with one first mode. Odd repeats cannot balance each case
    exactly; planned catalog/group order still needs inspection before launch.
    """
    if type(index) is not int or index < 0 or type(repeat) is not int or not 0 <= repeat <= 2:
        raise DeveloperError(ErrorCode.INVALID_INPUT)
    return ["single", "multi"] if ((index ^ (index >> 1)) + repeat) % 2 == 0 else ["multi", "single"]


def paired_bound(cases, repeats=1):
    if type(repeats) is not int or not 1 <= repeats <= 3:
        raise DeveloperError(ErrorCode.INVALID_INPUT)
    total = 0
    for case in cases:
        kind = route(case["question"]).kind
        if kind not in {"documentation", "fan_out"}:
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        total += 3 if kind == "fan_out" else 2
    return total * repeats


def signature(jobs):
    roles = {job.task.task_id: job.task.role.value for job in jobs}
    values = []
    for job in jobs:
        context = job.task.context.open()
        if job.task.role == Role.VERIFICATION:
            context = {"task_roles": [roles[key] for key in context["task_ids"]]}
        values.append({"role": job.task.role.value, "context": context,
                       "dependencies": [roles[key] for key in job.dependencies]})
    return values


class SnapshotReady(Exception):
    pass


class CapturePipeline(Pipeline):
    async def runtime(self, jobs):
        observed = await super().runtime(jobs)
        self.snapshot_jobs, self.snapshot_observed = jobs, observed
        raise SnapshotReady  # All owned acquisition workers have already been reaped.


async def capture_snapshot(workspace, state, case):
    pipeline = CapturePipeline(workspace, state_dir=state.path, language=case["language"], mode="fts")
    pipeline.budget.deadline = pipeline.started + 300
    try:
        async with asyncio.timeout(300):
            await pipeline._run(route(case["question"]), case["question"])
    except SnapshotReady:
        pass
    except TimeoutError:
        raise DeveloperError(ErrorCode.TIMEOUT) from None
    observed = pipeline.snapshot_observed
    return {"signature": signature(pipeline.snapshot_jobs), "observation": observed,
        "question": case["question"], "language": case["language"],
        "common_preparation_seconds": perf_counter() - pipeline.started}


def remap_observation(snapshot, jobs):
    if signature(jobs) != snapshot["signature"]:
        raise DeveloperError(ErrorCode.INVALID_INPUT)
    old = snapshot["observation"]
    mapping = {row["task_id"]: job.task.task_id for row, job in zip(old["results"], jobs, strict=True)}
    mapping[old["request_id"]] = jobs[0].task.request_id
    def remap(value):
        if isinstance(value, str): return mapping.get(value, value)
        if isinstance(value, list): return [remap(x) for x in value]
        if isinstance(value, dict): return {key: remap(x) for key, x in value.items()}
        return value
    return remap(old)


class SnapshotPipeline(Pipeline):
    def __init__(self, *args, snapshot, **kwargs):
        super().__init__(*args, **kwargs)
        self.snapshot = deepcopy(snapshot)
        self.snapshot_digest = sha256(canonical(snapshot).encode()).hexdigest()
        self.replayed = False

    async def runtime(self, jobs):
        if self.replayed:
            return await super().runtime(jobs)  # Post-model Git reobservation is real MCP.
        self.replayed = True
        if sha256(canonical(self.snapshot).encode()).hexdigest() != self.snapshot_digest:
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        observed = remap_observation(self.snapshot, jobs)
        self.budget.consume(observed["metrics"]["capability_calls"])
        observed["scope"] = "shared_snapshot_replay_logically_charged_not_reexecuted"
        observed["tool_events"] = []  # Physical acquisition events are retained once in the pair snapshot.
        self.stages.append(observed)
        self.record("SNAPSHOT_REPLAY", snapshot_digest=self.snapshot_digest,
                    logical_capability_calls=observed["metrics"]["capability_calls"])
        return observed

    async def run(self, question, **kwargs):
        if question != self.snapshot["question"] or self.language != self.snapshot["language"]:
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        self.timeout = 300 - self.snapshot["common_preparation_seconds"]
        if self.timeout <= 0:
            raise DeveloperError(ErrorCode.TIMEOUT)
        result = await super().run(question, **kwargs)
        result["snapshot_digest"] = self.snapshot_digest
        result["metrics"]["common_preparation_seconds"] = self.snapshot["common_preparation_seconds"]
        result["metrics"]["equal_budget_total_seconds"] = self.snapshot["common_preparation_seconds"] + result["metrics"]["total_seconds"]
        result["metrics"]["capability_accounting"] = "common acquisition logically charged to each mode; actual acquisition counted once per pair"
        return result


def single_inference(slots, snapshot, *, tasks_class=BaselineTasks):
    initial_git = next((row["data"] for row in snapshot["observation"]["merged"] if row["role"] == "git"), None)
    facts = [{"id": "g1", "text": git_text(initial_git, snapshot["language"])}] if initial_git else []
    class SingleTasks(tasks_class):
        async def run(self, role, context, *, final=True):
            if role == Role.MAIN:
                # A single response already selected the Git IDs and ordered its claims.
                return {"claim_ids": [x["id"] for x in context["claims"]],
                        "git_fact_ids": [x["id"] for x in context["git_facts"]]}
            if role != Role.DOCUMENTATION:
                raise DeveloperError(ErrorCode.PERMISSION_DENIED)
            combined = {"question": snapshot["question"], "documentation_question": context["question"],
                        "language": context["language"], "evidence": context["evidence"], "git_facts": deepcopy(facts)}
            slots.reserve()
            value = await super().run(Role.MAIN, combined, final=True)
            return {key: value[key] for key in ("status", "language", "claims")}
    return SingleTasks


async def compare(workspace, state, frozen, cases, *, cases_path, output, max_generation_calls=6, repeats=1,
                  capture=capture_snapshot, pipeline_class=SnapshotPipeline, baseline_tasks=BaselineTasks):
    planned = paired_bound(cases, repeats)
    slots = GenerationSlots(max_generation_calls)
    if planned > max_generation_calls:
        raise DeveloperError(ErrorCode.CONTEXT_BUDGET)
    validate_paired_freeze(frozen, workspace, state, cases_path)
    document, _ = load_cases(cases_path)
    if cases != select_cases(document, [case["id"] for case in cases]):
        raise DeveloperError(ErrorCode.WORKSPACE_CHANGED)
    catalog_positions = {case["id"]: index for index, case in enumerate(document["cases"])}
    output = new_output(output, workspace)
    report = {"format": "bublik-paired-snapshot-v1", "version": __version__, "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(), "frozen_conditions": frozen,
        "freeze_sha256": sha256(canonical(frozen).encode()).hexdigest(), "comparison_spec": deepcopy(frozen["comparison_spec"]),
        "catalog_design": deepcopy(frozen["catalog_design"]),
        "planned_case_ids": [case["id"] for case in cases], "repeats": repeats,
        "planned_generation_upper_bound": planned, "generation_cap": max_generation_calls,
        "generation_slots_reserved": 0, "pairs": [], "requests": [], "metadata_checks": [], "error": None}
    write_new(output, report)
    def reserved():
        report["generation_slots_reserved"] = slots.used
        checkpoint(output, report)
    slots.on_reserve = reserved
    try:
        for repeat in range(repeats):
            for case in cases:
                validate_paired_freeze(frozen, workspace, state, cases_path)
                observed = inspect_model(workspace)
                report["metadata_checks"].append({"case_id": case["id"], "repeat": repeat + 1, **observed})
                checkpoint(output, report)
                if observed["model"] != frozen["model"]:
                    raise DeveloperError(ErrorCode.LLM_UNAVAILABLE)
                snapshot = await capture(workspace, state, case)
                digest = sha256(canonical(snapshot).encode()).hexdigest()
                pair = {"pair_id": len(report["pairs"]) + 1, "case_id": case["id"], "repeat": repeat + 1,
                        "catalog_position": catalog_positions[case["id"]],
                        "order": pair_order(catalog_positions[case["id"]], repeat), "snapshot_digest": digest, "snapshot": snapshot,
                        "status": "running", "conditions_valid_after": False}
                report["pairs"].append(pair); checkpoint(output, report)
                if snapshot["observation"]["status"] != "completed":
                    code = next((x["error_code"] for x in snapshot["observation"]["results"] if x["error_code"]), ErrorCode.INVALID_TOOL_OUTPUT.value)
                    raise DeveloperError(ErrorCode(code))
                for mode in pair["order"]:
                    validate_paired_freeze(frozen, workspace, state, cases_path)
                    row = {"pair_id": pair["pair_id"], "case_id": case["id"], "mode": mode, "repeat": repeat + 1,
                           "status": "started", "conditions_valid_after": False, "generation_slots_before": slots.used}
                    report["requests"].append(row); checkpoint(output, report)
                    factory = single_inference(slots, snapshot, tasks_class=baseline_tasks) if mode == "single" else limited_inference(slots)
                    result = await pipeline_class(workspace, state_dir=state.path, language=case["language"], mode="fts",
                        snapshot=snapshot, inference_factory=factory).run(case["question"])
                    row.update(result=result, status="completed", structural_checks=structural_outcome(case, result))
                    checkpoint(output, report)
                    if result.get("snapshot_digest") != digest:
                        raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
                    validate_paired_freeze(frozen, workspace, state, cases_path)
                    row["conditions_valid_after"] = True
                    if not result_models_match(result, frozen["model"]):
                        raise DeveloperError(ErrorCode.LLM_UNAVAILABLE)
                    checkpoint(output, report)
                    if technical_failure(result):
                        report.update(status="stopped", error="technical_request_failure")
                        break
                if report["error"]: break
                pair.update(status="completed", conditions_valid_after=True)
                checkpoint(output, report)
            if report["error"]: break
        if not report["error"]: report["status"] = "completed"
    except asyncio.CancelledError:
        report.update(status="stopped", error=ErrorCode.CANCELLED.value)
    except (DeveloperError, TimeoutError) as error:
        report.update(status="stopped", error=error.code.value if isinstance(error, DeveloperError) else ErrorCode.TIMEOUT.value)
    except Exception:
        report.update(status="stopped", error=ErrorCode.AGENT_FAILED.value)
    finally:
        report["generation_slots_reserved"] = slots.used
        for pair in report["pairs"]:
            if pair["status"] == "running": pair["status"] = "stopped"
        report["summary"] = summarize(report)
        report["summary"].update(pairs_completed=sum(x["status"] == "completed" for x in report["pairs"]),
            single_multi_comparison="snapshot_new_questions" if frozen["catalog_design"]["kind"] == "prespecified_new_questions" else "snapshot_smoke_only",
            semantic_acceptance="not_evaluated",
            embedding_calls=0, common_preparation_seconds=sum(x["snapshot"]["common_preparation_seconds"] for x in report["pairs"]),
            actual_common_capability_calls=sum(x["snapshot"]["observation"]["metrics"]["capability_calls"] for x in report["pairs"]))
        checkpoint(output, report)
    return report


def paired_review_template(report, document, cases_digest):
    if (report.get("format") != "bublik-paired-snapshot-v1" or
        report.get("frozen_conditions", {}).get("conditions", {}).get("cases_sha256") != cases_digest):
        raise DeveloperError(ErrorCode.WORKSPACE_CHANGED)
    catalog = {case["id"]: case for case in document["cases"]}
    return {"format": "bublik-paired-human-review-v1", "status": "pending", "reviewer": None,
        "report_sha256": sha256(canonical(report).encode()).hexdigest(),
        "scale": "0 wrong, 1 partial, 2 correct; reviewer supplies each score and explanation",
        "reviews": [{"pair_id": row["pair_id"], "case_id": row["case_id"], "mode": row["mode"], "repeat": row["repeat"],
            "question": catalog[row["case_id"]]["question"], "required_points": catalog[row["case_id"]]["required_points"],
            "answer": row["result"]["answer"], "citations": row["result"].get("citations", []),
            "git_facts": row["result"].get("git_facts", []), "execution_status": row["result"]["execution_status"],
            "answer_status": row["result"]["answer_status"],
            "scores": {key: None for key in ("correctness", "completeness", "support", "language", "usefulness")}, "comment": ""}
            for row in report["requests"] if "result" in row]}
