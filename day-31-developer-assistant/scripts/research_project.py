"""Freeze conditions, plan a bounded batch, collect new RU/EN answers, prepare review."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bublik_developer.errors import DeveloperError,ErrorCode
from bublik_developer.rag.state import ProjectState
from bublik_developer.research import (freeze,load_cases,select_cases,new_output,write_new,
    generation_bound,evaluate,review_template,inspect_retrieval,CASES)
from bublik_developer.workspace import ProjectWorkspace


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation",choices=("freeze","plan","run","review-template","inspect-retrieval"))
    parser.add_argument("--root",type=Path,default=ROOT.parent)
    parser.add_argument("--state-dir",type=Path)
    parser.add_argument("--freeze",type=Path)
    parser.add_argument("--report",type=Path)
    parser.add_argument("--case-id",action="append")
    parser.add_argument("--cases",type=Path,default=CASES,help="Prespecified case catalog; its bytes are pinned in freeze")
    parser.add_argument("--max-generation-calls",type=int,default=6)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    try:
        document,cases_digest=load_cases(args.cases)
        if args.operation == "plan":
            selected=select_cases(document,args.case_id)
            print(json.dumps({"case_ids":[x["id"] for x in selected],"request_count":len(selected),
                "generation_upper_bound":sum(generation_bound(x["question"]) for x in selected),
                "cases_sha256":cases_digest,
                "pipeline_mode":"fts","embedding_calls":0,"inference_performed":False},indent=2));return 0
        if not args.output:parser.error("--output is required")
        output=new_output(args.output)  # Refuse prior reports before workspace/model access.
        if args.operation == "review-template":
            if not args.report:parser.error("--report is required")
            if output.resolve().is_relative_to(args.root.resolve()):parser.error("reports must be outside the project")
            report=json.loads(args.report.read_text())
            if report.get("frozen_conditions",{}).get("conditions",{}).get("cases_sha256") != cases_digest:
                raise DeveloperError(ErrorCode.WORKSPACE_CHANGED)
            write_new(output,review_template(report,document));print('{"status":"pending_human_review"}');return 0
        workspace=ProjectWorkspace.open(args.root,"ai-advent-llm-api")
        output=new_output(output,workspace)
        state=ProjectState(workspace,args.state_dir)
        if args.operation == "freeze":
            write_new(output,freeze(workspace,state,cases_path=args.cases));print('{"status":"frozen","generation_calls":0}');return 0
        if not args.freeze:parser.error("--freeze is required")
        selected=select_cases(document,args.case_id)
        frozen=json.loads(args.freeze.read_text())
        if frozen.get("conditions",{}).get("cases_sha256") != cases_digest:
            raise DeveloperError(ErrorCode.WORKSPACE_CHANGED)
        if args.operation == "inspect-retrieval":
            report=inspect_retrieval(workspace,state,frozen,selected,cases_path=args.cases)
            write_new(output,report)
            print('{"status":"completed","generation_calls":0,"embedding_calls":0,"model_http_calls":0}');return 0
        report=asyncio.run(evaluate(workspace,state,frozen,selected,output=output,max_generation_calls=args.max_generation_calls,cases_path=args.cases))
        print(json.dumps({"status":report["status"],"error":report["error"],"summary":report["summary"]},indent=2))
        return 0 if report["status"] == "completed" else 2
    except DeveloperError as error:
        print(json.dumps({"status":"failed","error":error.to_dict()}));return 2
    except (OSError,ValueError):
        print('{"status":"failed","error":{"code":"research_io_or_format_failure"}}');return 2


if __name__ == "__main__":raise SystemExit(main())
