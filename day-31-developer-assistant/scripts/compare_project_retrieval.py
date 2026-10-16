"""Source-level retrieval calibration; no answer LLM and no hidden reruns."""
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bublik_developer.model_session import ModelSession
from bublik_developer import __version__
from bublik_developer.rag.corpus import ProjectCorpus, load_selection
from bublik_developer.rag.embeddings import LocalEmbeddings
from bublik_developer.rag.index import ProjectIndex
from bublik_developer.rag.retrieval import search, resolve_dense_query, QUERY_DEFAULTS_VERSION
from bublik_developer.rag.state import ProjectState
from bublik_developer.workspace import ProjectWorkspace


def trials(modes, policy):
    if modes == "fts":
        return [("fts", "raw")]
    if policy == "auto":
        return [("fts", "raw"), ("dense", resolve_dense_query("dense", "auto")), ("hybrid", resolve_dense_query("hybrid", "auto"))]
    policies = ("vocabulary", "raw") if policy == "both" else (policy,)
    return [("fts", "raw")] + [(mode, query) for mode in ("dense", "hybrid") for query in policies]


def expected_dense_matches(index, case, result):
    """Evaluation labels annotate finished rankings; never enter model inputs."""
    diagnostic = result.get("dense_diagnostics")
    if diagnostic is None:
        return None
    matches = []
    selected = {hit["chunk_id"] for hit in result["sources"]}
    for row in diagnostic["rows"]:
        hit = index.db.execute("SELECT source,text,start_line,end_line FROM chunks WHERE chunk_id=?", (row["chunk_id"],)).fetchone()
        if hit["source"] in case["sources"] and all(term.casefold() in hit["text"].casefold() for term in case["terms"]):
            matches.append({**row, "source": hit["source"], "start_line": hit["start_line"],
                            "end_line": hit["end_line"], "selected": row["chunk_id"] in selected})
    return {"matches": matches, "rank_scope": "top_100_eligible_dense_chunks_before_threshold",
            "not_found_in_diagnostic_window": not matches, "truncated": diagnostic["truncated"]}


def acceptance(summary, complete):
    required = ("fts", "dense/raw", "dense/vocabulary", "hybrid/raw", "hybrid/vocabulary")
    if not complete or any(key not in summary for key in required):
        return {"status": "not_evaluated", "reason": "complete paired all-mode comparison required"}
    checks = {"all_raw_positive_hits": all(summary[key]["source_hit_at_5"] == 1 for key in ("fts", "dense/raw", "hybrid/raw")),
              "all_negative_controls_empty": all(summary[key]["negative_no_candidates"] == summary[key]["negative_cases"] for key in required),
              "no_mrr_regression": all(summary[mode + "/raw"]["source_mrr"] >= summary[mode + "/vocabulary"]["source_mrr"] for mode in ("dense", "hybrid"))}
    return {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
            "scope": "calibration source/keyword checks; not held-out semantic quality"}


def selected_acceptance(summary, complete):
    """Same quality checks, applied to the measured per-mode policy selection.

    Uniform raw remains a separately reported failed/accepted hypothesis.
    """
    required = ("fts", "dense/raw", "dense/vocabulary", "hybrid/raw", "hybrid/vocabulary")
    if not complete or any(key not in summary for key in required):
        return {"status": "not_evaluated", "reason": "complete paired all-mode comparison required"}
    selected = {mode: resolve_dense_query(mode, "auto") for mode in ("dense", "hybrid")}
    keys = ["fts"] + [mode + "/" + policy for mode, policy in selected.items()]
    checks = {"all_selected_positive_hits": all(summary[key]["source_hit_at_5"] == 1 for key in keys),
              "all_negative_controls_empty": all(summary[key]["negative_no_candidates"] == summary[key]["negative_cases"] for key in required),
              "no_mrr_regression": all(summary[mode + "/" + selected[mode]]["source_mrr"] >= max(summary[mode + "/" + policy]["source_mrr"] for policy in ("raw", "vocabulary")) for mode in selected)}
    return {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
            "selected_policies": selected, "selection_version": QUERY_DEFAULTS_VERSION,
            "scope": "calibration policy selection; not held-out semantic quality"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT.parent)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--project-id", default="ai-advent-llm-api")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--cases", type=Path, default=ROOT / "evaluation/retrieval_cases.json")
    parser.add_argument("--modes", choices=("fts", "all"), default="fts")
    parser.add_argument("--dense-query", choices=("auto", "raw", "vocabulary", "both"), default="auto")
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Reject a previous report before opening Git/index or dispatching embeddings.
    if args.output.exists() or args.output.is_symlink():
        parser.error("output already exists; choose a new filename (no overwrite)")
    raw_cases = args.cases.read_bytes()
    cases = json.loads(raw_cases)["cases"]
    workspace = ProjectWorkspace.open(args.root, args.project_id)
    corpus = ProjectCorpus(workspace, load_selection(args.manifest) if args.manifest else None)
    state = ProjectState(workspace, args.state_dir)
    rows, error, metadata, provider = [], None, None, None
    needs_model = args.modes == "all"
    manager = ModelSession(workspace).lease() if needs_model else nullcontext(None)
    try:
        with manager as lease, ProjectIndex.current(state, corpus) as index:
            provider = LocalEmbeddings(lease) if needs_model else None
            metadata = index.metadata
            for case in cases:
                for mode, policy in trials(args.modes, args.dense_query):
                    result = search(index, case["question"], mode=mode, provider=provider,
                                    dense_query=policy, diagnostics=args.diagnostics)
                    def relevant(hit):
                        return hit["source"] in case["sources"] and all(term.casefold() in hit["quote"].casefold() for term in case["terms"])
                    ranks = [position for position, hit in enumerate(result["sources"], 1) if relevant(hit)]
                    rows.append({"case_id": case["id"], "mode": mode, "dense_query_policy": policy if mode != "fts" else None,
                                 "status": result["status"],
                                 "source_hit_at_5": bool(ranks) if case["sources"] else None,
                                 "reciprocal_rank": 1 / min(ranks) if ranks else 0,
                                 "negative_no_candidates": not result["sources"] if not case["sources"] else None,
                                 "metrics": result["metrics"], "settings": result["settings"],
                                 "content_filter": result["content_filter"], "dense_diagnostics": result["dense_diagnostics"],
                                 "expected_dense_matches": expected_dense_matches(index, case, result),
                                 "sources": [{"source": hit["source"], "chunk_id": hit["chunk_id"],
                                    "start_line": hit["start_line"], "end_line": hit["end_line"], "raw_digest": hit["raw_digest"]} for hit in result["sources"]]})
    except Exception as caught:
        error = getattr(getattr(caught, "code", None), "value", "calibration_failed")
    embedding_events = provider.events if provider else []
    summary = {}
    for mode, policy in trials(args.modes, args.dense_query):
        group = [row for row in rows if row["mode"] == mode and (mode == "fts" or row["dense_query_policy"] == policy)]
        positive = [row for row in group if row["source_hit_at_5"] is not None]
        negative = [row for row in group if row["negative_no_candidates"] is not None]
        key = mode + "/" + policy if args.dense_query == "both" and mode != "fts" else mode
        if positive:
            summary[key] = {"positive_cases": len(positive), "source_hit_at_5": sum(row["source_hit_at_5"] for row in positive) / len(positive),
                             "source_mrr": sum(row["reciprocal_rank"] for row in positive) / len(positive),
                             "negative_no_candidates": sum(row["negative_no_candidates"] for row in negative), "negative_cases": len(negative)}
    complete = error is None and len(rows) == len(cases) * len(trials(args.modes, args.dense_query))
    quality = selected_acceptance(summary, complete)
    raw_quality = acceptance(summary, complete)
    report = {"format": "bublik-project-retrieval-calibration-v1", "version": __version__, "created_at": datetime.now(timezone.utc).isoformat(),
              "status": "completed" if error is None else "failed", "scope": "retrieval_only_calibration",
              "modes": args.modes, "dense_query_policy": args.dense_query,
              "source_sha256": {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
                                for path in sorted(ROOT.rglob("*.py")) if not {".venv", "__pycache__"}.intersection(path.parts)},
              "cases_sha256": sha256(raw_cases).hexdigest(), "index": metadata,
              "results": rows, "summary": summary, "error": error, "embedding_events": embedding_events,
              "answer_model_calls": 0, "embedding_calls": len(embedding_events),
              "embedding_calls_scope": "completed_calls_recorded_by_provider; failed dispatches are not counted here",
              "semantic_answers_evaluated": False,
              "quality_acceptance": quality,
              "raw_query_acceptance": raw_quality,
              "note": "Source/keyword hits are retrieval checks, not semantic answer verification. Failed cases remain failures. This is not the final held-out golden set."}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=True, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "summary": summary, "quality_acceptance": quality,
                      "raw_query_acceptance": raw_quality, "error": error}, ensure_ascii=True, indent=2))
    return 2 if error is not None else (3 if quality["status"] == "failed" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
