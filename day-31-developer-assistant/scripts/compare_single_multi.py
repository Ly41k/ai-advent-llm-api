"""Bounded paired snapshots with an explicit frozen case catalog and review scope."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bublik_developer.errors import DeveloperError
from bublik_developer.paired_research import paired_freeze, paired_bound, pair_order, compare, paired_review_template, catalog_design, comparison_spec
from bublik_developer.research import load_cases, select_cases, new_output, write_new
from bublik_developer.rag.state import ProjectState
from bublik_developer.workspace import ProjectWorkspace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "freeze", "run", "review-template"))
    parser.add_argument("--root", type=Path, default=ROOT.parent)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--cases", type=Path, default=ROOT / "evaluation/research_clarifications.json")
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-generation-calls", type=int, default=6)
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()
    try:
        document, digest = load_cases(args.cases)
        ids = args.case_id
        if ids is None and args.cases.resolve() == (ROOT / "evaluation/research_clarifications.json").resolve():
            ids = ["residency-explicit-ru", "residency-explicit-en"]
        selected = select_cases(document, ids)
        bound = paired_bound(selected, args.repeats)
        if args.operation == "plan":
            positions = {case['id']:i for i,case in enumerate(document['cases'])}
            print(json.dumps({"case_ids": [x["id"] for x in selected], "pairs": len(selected) * args.repeats,
                "request_observations": 2 * len(selected) * args.repeats, "generation_upper_bound": bound,
                "planned_orders": [{"case_id":case['id'],"repeat":repeat+1,
                    "catalog_position":positions[case['id']],"order":pair_order(positions[case['id']],repeat)}
                    for repeat in range(args.repeats) for case in selected],
                "cases_sha256": digest, "embedding_calls": 0, "inference_performed": False,
                "catalog_design": catalog_design(document, digest),
                "scope": comparison_spec(document, digest)["scope"]}, indent=2)); return 0
        if not args.output: parser.error("--output is required")
        output = new_output(args.output)
        if args.operation == "review-template":
            if not args.report: parser.error("--report is required")
            if output.resolve().is_relative_to(args.root.resolve()): parser.error("reports must be outside the project")
            report = json.loads(args.report.read_text())
            write_new(output, paired_review_template(report, document, digest))
            print('{"status":"pending_human_review"}'); return 0
        workspace = ProjectWorkspace.open(args.root, "ai-advent-llm-api")
        output = new_output(output, workspace)
        state = ProjectState(workspace, args.state_dir)
        if args.operation == "freeze":
            write_new(output, paired_freeze(workspace, state, cases_path=args.cases))
            print('{"status":"frozen","generation_calls":0,"embedding_calls":0}'); return 0
        if not args.freeze: parser.error("--freeze is required")
        frozen = json.loads(args.freeze.read_text())
        report = asyncio.run(compare(workspace, state, frozen, selected, cases_path=args.cases,
            output=output, max_generation_calls=args.max_generation_calls, repeats=args.repeats))
        print(json.dumps({"status": report["status"], "error": report["error"], "summary": report["summary"]}, indent=2))
        return 0 if report["status"] == "completed" else 2
    except DeveloperError as error:
        print(json.dumps({"status": "failed", "error": error.to_dict()})); return 2
    except (OSError, ValueError):
        print('{"status":"failed","error":{"code":"paired_io_or_format_failure"}}'); return 2


if __name__ == "__main__":
    raise SystemExit(main())
