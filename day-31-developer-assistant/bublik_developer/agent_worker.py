"""Retrieval/Verification workers; explicit embeddings, no answer generation/tools."""
import json
import re
import sys

from .contracts import ContextEnvelope, Role, canonical
from .errors import DeveloperError, ErrorCode
from .rag.corpus import ProjectCorpus, SourceSpec
from .rag.index import ProjectIndex
from .rag.retrieval import query_terms, search
from .rag.state import ProjectState
from .workspace import ProjectWorkspace


def execute(payload):
    expected = {"role", "root", "workspace_identity", "project_id", "state_dir", "selection", "context"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise DeveloperError(ErrorCode.PERMISSION_DENIED)
    context = payload["context"]
    if payload["role"] == Role.DOCUMENTATION:
        if (not isinstance(context, dict) or "question" not in context
                or set(context) - {"question", "mode", "changed_paths"}
                or context.get("mode", "fts") not in {"fts", "dense", "hybrid"}):
            raise DeveloperError(ErrorCode.PERMISSION_DENIED, "role")
        query_terms(context["question"])
    elif payload["role"] != Role.VERIFICATION or not isinstance(context, dict) or set(context) != {"results"}:
        raise DeveloperError(ErrorCode.PERMISSION_DENIED, "role")
    workspace = ProjectWorkspace.open(payload["root"], payload["project_id"])
    if list(workspace.identity) != payload["workspace_identity"]:
        raise DeveloperError(ErrorCode.WORKSPACE_CHANGED)
    selection = payload["selection"]
    if selection is not None:
        selection = [SourceSpec(**spec) for spec in selection]
    corpus = None
    state = ProjectState(workspace, payload["state_dir"])
    if payload["role"] == Role.DOCUMENTATION:
        if context.get("changed_paths") == []:
            return {"kind": "documentation_evidence", "project_id": workspace.project_id,
                "index_version": None, "corpus_revision": None, "sources": [], "settings": {}, "content_filter": {},
                "semantic_support_verified": False, "retrieval_metrics": {}, "embedding_events": [],
                "chain": {"changed_paths_count": 0, "used_paths": [], "limited": False,
                          "association": "exact_relative_path_mentions_only", "linked_sources": []}}, "answered"
        corpus = ProjectCorpus(workspace, selection)
        mode = context.get("mode", "fts")
        question, sources, chain = context["question"], None, None
        if "changed_paths" in context:
            paths = context["changed_paths"]
            if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
                raise DeveloperError(ErrorCode.INVALID_INPUT)
            for path in paths:
                workspace.path(path, missing=True)
            used = paths[:4]
            snapshot = corpus.collect()
            sources = [doc.source for doc in snapshot.documents if any(path == doc.source or
                       re.search(r"(?<![\w/.-])" + re.escape(path) + r"(?![\w/.-])", doc.text) for path in used)]
            chain = {"changed_paths_count": len(paths), "used_paths": used, "limited": len(paths) > 4,
                     "association": "exact_relative_path_mentions_only", "linked_sources": sources}
            question = "Documentation for changed files: " + " ".join(used)
            query_terms(question)
        from contextlib import nullcontext
        from .model_session import ModelSession
        from .rag.embeddings import LocalEmbeddings
        manager = ModelSession(workspace).lease() if mode != "fts" and sources != [] else nullcontext(None)
        with manager as lease, ProjectIndex.current(state, corpus) as index:
            provider = LocalEmbeddings(lease) if lease else None
            if sources == []:
                result = {"sources": [], "index_version": index.metadata["index_version"],
                          "corpus_revision": index.metadata["corpus_revision"], "settings": {}, "content_filter": {}}
            else:
                result = search(index, question, mode=mode, provider=provider,
                                sources=sources, final_k=3, context_bytes=4096)
        data = {"kind": "documentation_evidence", "project_id": workspace.project_id,
                "index_version": result["index_version"], "corpus_revision": result["corpus_revision"],
                "sources": [{key: value for key, value in hit.items() if key != "ranking"} for hit in result["sources"]],
                "settings": result["settings"], "content_filter": result["content_filter"],
                "semantic_support_verified": False}
        data["retrieval_metrics"] = result.get("metrics", {})
        data["embedding_events"] = provider.events if provider else []
        if chain is not None:
            data["chain"] = chain
        return data, "answered" if data["sources"] else "insufficient_evidence"
    if payload["role"] != Role.VERIFICATION or not isinstance(context, dict) or set(context) != {"results"}:
        raise DeveloperError(ErrorCode.PERMISSION_DENIED, "role")
    results = context["results"]
    if not isinstance(results, list) or not 1 <= len(results) <= 3:
        raise DeveloperError(ErrorCode.INVALID_INPUT)
    verified, checks = [], []
    for result in results:
        if (not isinstance(result, dict) or set(result) != {"task_id", "role", "data"}
                or not isinstance(result["task_id"], str) or result["task_id"] in verified):
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        data = result["data"]
        if result["role"] == Role.DOCUMENTATION:
            expected = {"kind", "project_id", "index_version", "corpus_revision", "sources", "settings", "content_filter", "semantic_support_verified"}
            if (not isinstance(data, dict) or set(data) - expected - {"chain", "retrieval_metrics", "embedding_events"} or expected - set(data)
                    or data["kind"] != "documentation_evidence" or data["project_id"] != workspace.project_id
                    or not isinstance(data["sources"], list) or len(data["sources"]) > 3
                    or data["semantic_support_verified"] is not False):
                raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
            if (data.get("chain") == {"changed_paths_count": 0, "used_paths": [], "limited": False,
                    "association": "exact_relative_path_mentions_only", "linked_sources": []}
                    and data["index_version"] is None and data["corpus_revision"] is None and data["sources"] == []):
                checks.append({"task_id": result["task_id"], "check": "no_changed_paths_requires_no_documentation_index", "status": "passed"})
                verified.append(result["task_id"])
                continue
            corpus = ProjectCorpus(workspace, selection)
            with ProjectIndex.current(state, corpus) as index:
                if (data["index_version"] != index.metadata["index_version"]
                        or data["corpus_revision"] != index.metadata["corpus_revision"]):
                    raise DeveloperError(ErrorCode.INDEX_STALE)
                ids = set()
                for hit in data["sources"]:
                    if (not isinstance(hit, dict) or not isinstance(hit.get("chunk_id"), str)
                            or hit["chunk_id"] in ids or index.evidence(hit["chunk_id"]) != hit):
                        raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
                    ids.add(hit["chunk_id"])
                index.fresh()
            if "chain" in data:
                chain = data["chain"]
                if (not isinstance(chain, dict) or set(chain) != {"changed_paths_count", "used_paths", "limited", "association", "linked_sources"}
                        or chain["association"] != "exact_relative_path_mentions_only" or type(chain["limited"]) is not bool
                        or type(chain["changed_paths_count"]) is not int or not isinstance(chain["used_paths"], list)
                        or len(chain["used_paths"]) > 4 or not isinstance(chain["linked_sources"], list)
                        or any(hit["source"] not in chain["linked_sources"] for hit in data["sources"])):
                    raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
                if (any(not isinstance(path, str) for path in chain["used_paths"])
                        or chain["changed_paths_count"] < len(chain["used_paths"])
                        or chain["limited"] != (chain["changed_paths_count"] > 4)):
                    raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
                associated = [doc.source for doc in corpus.collect().documents if any(path == doc.source or
                    re.search(r"(?<![\w/.-])" + re.escape(path) + r"(?![\w/.-])", doc.text) for path in chain["used_paths"])]
                if chain["linked_sources"] != associated:
                    raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
            checks.append({"task_id": result["task_id"], "check": "fresh_exact_source_provenance", "status": "passed"})
        elif result["role"] == Role.GIT:
            from .mcp_schema import GitReply
            from pydantic import ValidationError
            try:
                reply = GitReply.model_validate(data)
            except ValidationError:
                raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT) from None
            if not reply.ok or reply.project_id != workspace.project_id:
                raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
            checks.append({"task_id": result["task_id"], "check": "validated_mcp_git_observation", "status": "passed",
                           "observed_at": reply.observed_at, "git_reobserved": False})
        else:
            raise DeveloperError(ErrorCode.PERMISSION_DENIED, "role")
        verified.append(result["task_id"])
    return {"kind": "verification_report", "verified_task_ids": verified, "checks": checks,
            "semantic_support_verified": False, "scope": "source_provenance_and_git_schema"}, "answered"


def main():
    try:
        raw = sys.stdin.buffer.read(32769)
        if len(raw) > 32768:
            raise DeveloperError(ErrorCode.CONTEXT_BUDGET)
        data, outcome = execute(json.loads(raw))
        ContextEnvelope.seal(data)
        reply = {"data": data, "outcome": outcome, "error_code": None}
    except DeveloperError as error:
        reply = {"data": {}, "outcome": "error", "error_code": error.code.value}
    except Exception:
        # No private source bodies, raw OS errors or stack traces on either pipe.
        reply = {"data": {}, "outcome": "error", "error_code": ErrorCode.AGENT_FAILED.value}
    print(canonical(reply))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
