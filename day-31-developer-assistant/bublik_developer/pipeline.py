"""Router / chain / fan-out, scoped Qwen tasks, and post-synthesis checks."""
import asyncio
from dataclasses import dataclass
import math
import os
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from .agent_runtime import Dispatcher, Job
from .contracts import Role, TaskEnvelope, canonical
from .errors import DeveloperError, ErrorCode
from .generation import validate_output
from .inference_tasks import InferenceTasks
from .rag.corpus import ProjectCorpus
from .rag.index import ProjectIndex
from .rag.state import ProjectState, private
from .routing import route
from .reliability import failure_advice


@dataclass
class Budget:
    limit: int = 8
    used: int = 0
    deadline: float | None = None

    def __post_init__(self):
        if type(self.limit) is not int or not 1 <= self.limit <= 8:
            raise DeveloperError(ErrorCode.INVALID_INPUT)

    def consume(self, count=1):
        self.checkpoint()
        if type(count) is not int or count < 0 or self.used + count > self.limit:
            raise DeveloperError(ErrorCode.PERMISSION_DENIED)
        self.used += count

    def checkpoint(self):
        if self.deadline is not None and perf_counter() >= self.deadline:
            raise DeveloperError(ErrorCode.TIMEOUT)

    @property
    def seconds_remaining(self):
        self.checkpoint()
        return max(0., self.deadline - perf_counter()) if self.deadline is not None else 300.

    @property
    def remaining(self):
        return self.limit - self.used


def git_text(reply, language):
    data, when = reply["data"], reply["observed_at"]
    ru = language == "ru"
    if data["kind"] == "branch":
        text = ("Ветка: " if ru else "Branch: ") + (data["branch"] or "detached HEAD")
        if data["unborn"]:
            text += " (без коммитов)" if ru else " (no commits)"
    elif data["kind"] == "status":
        text = ("Изменённых разрешённых файлов: " if ru else "Changed allowed files: ") + str(len(data["entries"]))
    elif data["kind"] == "files":
        text = ("Разрешённых файлов проекта: " if ru else "Allowed project files: ") + str(len(data["files"]))
    else:
        text = ("Файлов в " if ru else "Files in ") + data["scope"] + " diff: " + str(len(data["files"]))
    if data.get("withheld_count"):
        text += ("; скрытых записей: " if ru else "; withheld entries: ") + str(data["withheld_count"])
    return text + (". Наблюдение: " if ru else ". Observed: ") + when


class Pipeline:
    def __init__(self, workspace, *, state_dir=None, corpus=None, language="ru", mode="fts", max_calls=8, timeout=300,
                 runtime_factory=Dispatcher, inference_factory=InferenceTasks):
        if (language not in {"ru", "en"} or mode not in {"fts", "dense", "hybrid"}
                or type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 300):
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        self.workspace, self.corpus = workspace, corpus
        self.state = ProjectState(workspace, state_dir)
        self.language, self.mode, self.timeout = language, mode, timeout
        self.runtime_factory, self.inference_factory = runtime_factory, inference_factory
        self.budget = Budget(max_calls)
        self.request_id, self.trace, self.stages = uuid4().hex, [], []
        self.started, self.used = perf_counter(), False
        self.models = inference_factory(workspace, self.request_id, self.record, self.budget)

    def record(self, event, **values):
        self.trace.append({**values, "sequence": len(self.trace) + 1, "event": event,
                           "seconds": round(perf_counter() - self.started, 6)})

    def task(self, role, context):
        return TaskEnvelope.create(role, self.workspace.project_id, "Project request", context, request_id=self.request_id)

    async def runtime(self, jobs):
        if self.budget.remaining == 0:
            raise DeveloperError(ErrorCode.PERMISSION_DENIED)
        observed = await self.runtime_factory(self.workspace, self.corpus, self.state,
            max_calls=self.budget.remaining, timeout=min(self.timeout, self.budget.seconds_remaining)).run(jobs)
        # Preserve accounting even when a dispatcher has consumed cancellation.
        self.budget.used += observed["metrics"]["capability_calls"]
        if self.budget.used > self.budget.limit:
            raise DeveloperError(ErrorCode.PERMISSION_DENIED)
        self.stages.append(observed)
        for event in observed["trace"]:
            self.record(event["event"], stage_index=len(self.stages), stage_seconds=event.get("seconds"),
                        **{k: v for k, v in event.items() if k not in {"event", "sequence", "seconds"}})
        interruptions = [x.get("interruption") for x in observed["trace"] if x["event"] == "MERGE"]
        if "cancelled" in interruptions:
            raise asyncio.CancelledError
        if "timeout" in interruptions:
            raise DeveloperError(ErrorCode.TIMEOUT)
        self.budget.checkpoint()
        return observed

    def verify_sources(self, catalog):
        if not catalog:
            return
        with ProjectIndex.current(self.state, self.corpus) as index:
            for evidence in catalog.values():
                if (evidence["index_version"] != index.metadata["index_version"]
                        or evidence["corpus_revision"] != index.metadata["corpus_revision"]):
                    raise DeveloperError(ErrorCode.INDEX_STALE)
                if index.evidence(evidence["chunk_id"]) != evidence:
                    raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
            index.fresh()

    async def _run(self, plan, question):
        diagnostics, catalog, claims, facts, draft = [], {}, [], [], None
        if plan.kind == "ambiguous":
            return self.envelope(plan, [], [], [], ["ambiguous_git_intent"], execution="completed", answer="unknown")
        if plan.documentation_question:
            try:
                self.corpus = self.corpus or ProjectCorpus(self.workspace)
            except DeveloperError as error:
                if plan.kind != "chain" or error.code != ErrorCode.INVALID_INPUT:
                    raise
                # An empty corpus must not prevent the no-changed-files Git answer.
                self.corpus = None
        jobs, git_task, doc_task = [], None, None
        git_arguments = {"scope": plan.git_scope, "paths": [], "include_content": False} if plan.git_operation == "diff" else {}
        if plan.git_operation:
            git_task = self.task(Role.GIT, {"operation": plan.git_operation, "arguments": git_arguments})
            jobs.append(Job(git_task))
        if plan.documentation_question and self.corpus is not None:
            context = {"question": plan.documentation_question, "mode": self.mode}
            dependencies = ()
            if plan.kind == "chain":
                context["from_changed_files"] = True
                dependencies = (git_task.task_id,)
            doc_task = self.task(Role.DOCUMENTATION, context)
            jobs.append(Job(doc_task, dependencies))
        dependencies = tuple(job.task.task_id for job in jobs)
        verifier = self.task(Role.VERIFICATION, {"task_ids": list(dependencies)})
        jobs.append(Job(verifier, dependencies))
        observed = await self.runtime(jobs)
        diagnostics += [x["error_code"] for x in observed["results"] if x["error_code"]]
        by_id = {x["task_id"]: x for x in observed["merged"]}
        doc = by_id.get(doc_task.task_id) if doc_task else None
        initial_git = next((x["data"] for x in observed["results"] if git_task and x["task_id"] == git_task.task_id and x["status"] == "success"), None)
        if initial_git and initial_git["data"].get("withheld_count"):
            diagnostics.append("git_entries_withheld")
        if plan.kind == "chain" and self.corpus is None and initial_git and initial_git["data"]["entries"]:
            diagnostics.append("documentation_corpus_unavailable")
        if doc:
            catalog = {"e" + str(i): evidence for i, evidence in enumerate(doc["data"]["sources"], 1)}
            if doc["data"].get("chain", {}).get("limited"):
                diagnostics.append("changed_paths_limited_to_four")
            if not catalog and plan.kind == "chain" and initial_git and initial_git["data"]["entries"]:
                diagnostics.append("no_documented_path_association")
        doc_context = None
        if catalog:
            self.verify_sources(catalog)
            doc_context = {"question": plan.documentation_question, "language": self.language,
                           "evidence": [{"id": key, "quote": value["quote"]} for key, value in catalog.items()]}
            try:
                draft = await self.models.run(Role.DOCUMENTATION, doc_context, final=not bool(initial_git))
                validate_output(Role.DOCUMENTATION, draft, doc_context)
                claims = [{"id": "c" + str(i), **claim} for i, claim in enumerate(draft["claims"], 1)]
                if draft["status"] != "answered":
                    diagnostics.append("documentation_" + draft["status"])
            except DeveloperError as error:
                diagnostics.append(error.code.value)
        if initial_git:
            facts = [{"id": "g1", "text": git_text(initial_git, self.language), "observation": initial_git}]
        if claims and facts:
            main_context = {"question": question, "language": self.language,
                "claims": [{"id": x["id"], "text": x["text"]} for x in claims],
                "git_facts": [{"id": x["id"], "text": x["text"]} for x in facts]}
            try:
                merged = await self.models.run(Role.MAIN, main_context, final=True)
                validate_output(Role.MAIN, merged, main_context)
                first_model = self.models.observations[0].get("model")
                last_model = self.models.observations[-1].get("model")
                if first_model is not None and first_model != last_model:
                    raise DeveloperError(ErrorCode.LLM_UNAVAILABLE)
                claim_map, fact_map = {x["id"]: x for x in claims}, {x["id"]: x for x in facts}
                claims = [claim_map[key] for key in merged["claim_ids"]]
                facts = [fact_map[key] for key in merged["git_fact_ids"]]
                self.record("MAIN_MERGE", claim_ids=merged["claim_ids"], git_fact_ids=merged["git_fact_ids"])
            except DeveloperError as error:
                diagnostics.append(error.code.value)
                self.record("DETERMINISTIC_MERGE_FALLBACK", reason=error.code.value)
        # Git is independently reobserved after generation, through its own MCP role.
        if facts:
            try:
                again = self.task(Role.GIT, {"operation": plan.git_operation, "arguments": git_arguments})
                check = self.task(Role.VERIFICATION, {"task_ids": [again.task_id]})
                refreshed = await self.runtime([Job(again), Job(check, (again.task_id,))])
                if not refreshed["merged"] or refreshed["merged"][0]["data"]["data"] != initial_git["data"]:
                    raise DeveloperError(ErrorCode.GIT_STATE_CHANGED)
                newer = refreshed["merged"][0]["data"]
                facts = [{"id": "g1", "text": git_text(newer, self.language), "observation": newer}]
            except DeveloperError as error:
                diagnostics.append(error.code.value)
                facts = []
        try:
            self.budget.consume()
            self.workspace.check()
            self.verify_sources(catalog)
            if draft:
                validate_output(Role.DOCUMENTATION, draft, doc_context)
            self.budget.checkpoint()
            self.record("FINAL_VERIFY", status="passed", scope="fresh_provenance_closed_claim_ids_and_git_reobservation")
        except DeveloperError as error:
            diagnostics.append(error.code.value)
            claims, catalog = [], {}
            if error.code in {ErrorCode.TIMEOUT, ErrorCode.WORKSPACE_CHANGED, ErrorCode.PERMISSION_DENIED}:
                facts = []
            self.record("FINAL_VERIFY", status="failed", error_code=error.code.value)
        no_changes = plan.kind == "chain" and initial_git and not initial_git["data"]["entries"]
        # A validated abstention is a completed documentation task. A mixed
        # request still lacks its requested documentation answer; failures from
        # final verification must remain failures regardless of model status.
        completed_unknown = (draft is not None and draft["status"] == "unknown"
                             and not facts and not plan.git_operation
                             and diagnostics == ["documentation_unknown"])
        if plan.documentation_question and not claims and (catalog or facts) and not no_changes and not completed_unknown:
            diagnostics.append("documentation_not_answered")
        if plan.documentation_question and not claims and not catalog and not facts and not diagnostics:
            return self.envelope(plan, [], [], [], [], execution="completed", answer="unknown")
        citations = [{"evidence_id": key, **catalog[key]} for key in dict.fromkeys(key for claim in claims for key in claim["evidence_ids"])]
        excerpts = [{"evidence_id": key, **value} for key, value in catalog.items()] if not claims and any(x in {code.value for code in ErrorCode} for x in diagnostics) else []
        outputs = bool(claims or facts or excerpts)
        answer = "partial" if diagnostics and outputs else "answered" if outputs else "unknown"
        execution = "partial" if diagnostics and outputs else "failed" if diagnostics else "completed"
        if completed_unknown:
            execution, answer = "completed", "unknown"
        return self.envelope(plan, claims, facts, citations, diagnostics, execution=execution, answer=answer, excerpts=excerpts)

    def envelope(self, plan, claims, facts, citations, diagnostics, *, execution, answer, excerpts=None):
        observations = self.models.observations
        known = sum(x.get("llm_calls") or 0 for x in observations)
        unknown = sum(x.get("llm_calls") is None for x in observations)
        calls = [x for x in observations if x.get("llm_calls") == 1]
        independent = (len(calls) == 2 and {x["role"] for x in calls} == {"documentation", "main"}
                       and len({x.get("message_digest") for x in calls}) == 2
                       and len({canonical(x.get("model")) for x in calls}) == 1
                       and all(x.get("transport") == "ollama_loopback_http" and x.get("status") == "completed" for x in calls))
        self.record("OUTPUT", execution_status=execution, answer_status=answer)
        empty = "Недостаточно подтверждённых источников для ответа." if self.language == "ru" else "There is insufficient supported evidence to answer."
        if plan.kind == "ambiguous":
            empty = ("В запросе несколько Git-операций. Разделите его на отдельные вопросы."
                     if self.language == "ru" else "The request contains multiple Git operations. Split it into separate questions.")
        elif execution == "failed":
            empty = "Не удалось завершить запрос. Проверьте diagnostics и recovery." if self.language == "ru" else "The request could not be completed. Check diagnostics and recovery."
        elif execution == "partial" and excerpts and not claims and not facts:
            empty = "Ответ модели не получен; доступны проверенные выдержки источников." if self.language == "ru" else "No model answer was obtained; verified source excerpts are available."
        limitations = []
        if facts and "no_documented_path_association" in diagnostics:
            limitations.append("В документации не найдены точные связи с проверенными изменёнными путями; их функциональность не подтверждена."
                               if self.language == "ru" else "No exact documentation associations were found for the checked changed paths; their functionality is unsupported.")
        elif facts and "documentation_not_answered" in diagnostics:
            limitations.append("Документационная часть запроса осталась без подтверждённого ответа."
                               if self.language == "ru" else "The documentation part of the request has no supported answer.")
        if facts and "changed_paths_limited_to_four" in diagnostics:
            limitations.append("Связи с документацией проверены только для первых четырёх разрешённых изменённых путей."
                               if self.language == "ru" else "Documentation associations were checked only for the first four allowed changed paths.")
        return {"schema_version": 1, "request_id": self.request_id, "project_id": self.workspace.project_id,
            "execution_status": execution, "answer_status": answer, "language": self.language, "route": plan.kind,
            "answer": "\n".join([x["text"] for x in claims] + [x["text"] for x in facts] + limitations) or empty,
            "claims": claims, "citations": citations, "git_facts": facts, "excerpts": excerpts or [],
            "diagnostics": list(dict.fromkeys(diagnostics)), "semantic_support_verified": False,
            "recovery": [advice for code in dict.fromkeys(diagnostics)
                         if (advice := failure_advice(code, self.language, uncertain=bool(unknown)))],
            "independent_llm_contexts_verified": independent, "inference_tasks": observations,
            "stage_metrics": [{"stage_index": i, "status": stage.get("status"), "metrics": stage["metrics"],
                               "tool_events": stage.get("tool_events", []),
                               "tasks": [{k: event[k] for k in ("task_id", "role", "status", "error_code", "task_seconds") if k in event}
                                         for event in stage["trace"] if event["event"] == "REPORT"]}
                              for i, stage in enumerate(self.stages, 1)],
            "metrics": {"capability_calls": self.budget.used, "llm_calls": known if not unknown else None,
                "known_llm_calls": known, "unknown_inference_attempts": unknown,
                "input_tokens": sum(x.get("input_tokens") or 0 for x in observations) if all(x.get("input_tokens") is not None for x in calls) and not unknown else None,
                "output_tokens": sum(x.get("output_tokens") or 0 for x in observations) if all(x.get("output_tokens") is not None for x in calls) and not unknown else None,
                "embedding_calls_completed": sum(len(x["data"].get("embedding_events", [])) for stage in self.stages for x in stage["results"] if x["role"] == "documentation"),
                "metadata_retries": sum(x.get("metadata_retries", 0) for x in observations),
                "model_http_attempts": sum(len(x.get("http_events", [])) for x in observations),
                "cancel_count": int("cancelled" in diagnostics), "timeout_count": int("timeout" in diagnostics),
                "model_retries": 0, "cloud_fallbacks": 0, "total_seconds": perf_counter() - self.started},
            "trace": self.trace}

    async def run(self, question, *, session=None):
        if self.used:
            raise DeveloperError(ErrorCode.PERMISSION_DENIED)
        self.used = True
        self.started = perf_counter()
        self.budget.deadline = self.started + self.timeout
        plan = route(question)
        if session and session.project_id != self.workspace.project_id:
            raise DeveloperError(ErrorCode.PERMISSION_DENIED)
        if session and plan.documentation_question:
            try:
                self.corpus = self.corpus or ProjectCorpus(self.workspace)
            except DeveloperError as error:
                if plan.kind != "chain" or error.code != ErrorCode.INVALID_INPUT:
                    raise
            if self.corpus is not None:
                revision = self.corpus.collect().revision
                resolved = session.resolve(question, self.workspace.project_id, revision)
                plan = route(resolved)
                session.remember(plan.documentation_question, revision)
        self.record("ROUTE", kind=plan.kind, git_operation=plan.git_operation)
        try:
            async with asyncio.timeout(self.budget.seconds_remaining):
                result = await self._run(plan, question)
        except (TimeoutError, asyncio.CancelledError) as error:
            result = self.envelope(plan, [], [], [], ["timeout" if isinstance(error, TimeoutError) else "cancelled"], execution="failed", answer="unknown")
        except DeveloperError as error:
            result = self.envelope(plan, [], [], [], [error.code.value], execution="failed", answer="unknown")
        except OSError:
            result = self.envelope(plan, [], [], [], [ErrorCode.STATE_UNAVAILABLE.value], execution="failed", answer="unknown")
        try:
            directory = self.state.path / "traces"
            directory.mkdir(mode=0o700, exist_ok=True)
            private(directory, directory=True)
            file = directory / (self.request_id + ".json")
            fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(canonical(result))
                stream.flush()
                os.fsync(stream.fileno())
            result["trace_file"] = str(file)
            result["trace_persistence"] = "saved"
        except (OSError, DeveloperError):
            result["trace_persistence"] = "failed"
            result["diagnostics"].append(ErrorCode.STATE_UNAVAILABLE.value)
            result["recovery"].append(failure_advice(ErrorCode.STATE_UNAVAILABLE, self.language))
            result["execution_status"] = "partial" if result["claims"] or result["git_facts"] else "failed"
        return result
