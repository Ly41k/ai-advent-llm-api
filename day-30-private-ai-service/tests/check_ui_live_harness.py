"""Optional real-browser review of the live checker with synthetic control answers."""
import argparse
import asyncio
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from check_storage import ROOT,manifest
from check_web_ui_live import run
from browser_fixture import BrowserFixture,PASSWORD
from bublik_service.inference.ollama import Answer


async def review():
    results=[]
    for wrong in (False,True):
        with tempfile.TemporaryDirectory(prefix="bublik-live-checker-review-") as directory:
            fixture=BrowserFixture(directory)
            async def control(job,checkpoint):
                question=job["context"]["messages"][-1]["content"]
                answer="wrong" if wrong else ("мандарин" if "Какое" in question else "OK" if "OK" in question else "принято")
                await asyncio.sleep(.4); await checkpoint(answer)
                return Answer(answer,"completed",{"input_tokens":1,"output_tokens":1})
            fixture.adapter.generate=control
            value={"run_id":"synthetic-review-"+str(wrong),"checks":[],"environment":{},"answers_sha256":[],"generations":[]}
            args=SimpleNamespace(url=fixture.url,username="ui-test",ca_file=fixture.cert)
            rejected=False
            try:
                try: await run(args,value,PASSWORD)
                except ValueError: rejected=True
                passed=(not rejected and all(c["passed"] for c in value["checks"])) if not wrong else (
                    rejected and any(c["name"]=="literal_turn_0" and not c["passed"] for c in value["checks"]))
                results.append({"name":"reject_wrong_control_answer" if wrong else "live_checker_browser_flow",
                    "passed":passed,"observed_checks":value["checks"],"browser":value["environment"].get("browser")})
            finally: fixture.close()
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    source=manifest()
    report={"format":"bublik-stage5-live-checker-review-v1","created_at":datetime.now(timezone.utc).isoformat(),
        "status":"failed","source_sha256":source,
        "evidence":"Real Chromium/TLS/SQLite, synthetic control answers. Reviews live checker only; NOT real Qwen proof."}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as stream:
        try:
            report["checks"]=asyncio.run(review())
            report["source_unchanged"]=source==manifest()
            if all(c["passed"] for c in report["checks"]) and report["source_unchanged"]: report["status"]="passed"
        except Exception as error:
            report["error_code"]="checker_review_failed"; report["failure_type"]=type(error).__name__
        json.dump(report,stream,ensure_ascii=False,indent=2);stream.write("\n")
    print(json.dumps({"report":str(args.output),"status":report["status"]}))
    return 0 if report["status"]=="passed" else 1


if __name__=="__main__": sys.exit(main())
