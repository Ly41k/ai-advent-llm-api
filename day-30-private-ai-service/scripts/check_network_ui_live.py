"""Real browser + Qwen via LAN/tailnet proxy. Two sessions on the calling computer."""
import argparse
import asyncio
from datetime import datetime, timezone
import getpass
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import time
import uuid

from check_storage import ROOT,manifest
from check_web_ui_live import run
from network_common import private_origin


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url",required=True)
    parser.add_argument("--network",choices=("lan","tailnet"),required=True)
    parser.add_argument("--username",required=True)
    parser.add_argument("--ca-file",type=Path,help="LAN root.crt; also install it in the browser/OS trust store")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    try:
        private_origin(args.url,args.network)
        if args.network=="lan" and not args.ca_file: raise ValueError()
        import playwright.async_api
    except ValueError:
        parser.error("Private canonical HTTPS origin required; LAN requires public root.crt")
    except ImportError:
        parser.error("Install requirements.browser.lock and Chromium")
    # Normal browser trust, no pin or TLS bypass. The LAN CA must be installed
    # by the operator. Tailnet uses the public certificate managed by Serve.
    args.browser_launch_args=[]
    stamp=datetime.now(timezone.utc); run_id=stamp.strftime("%Y%m%dT%H%M%S")+"-"+uuid.uuid4().hex[:8]
    output=args.output or ROOT/"reports/check"/("stage6-ui-"+run_id+".json")
    output.parent.mkdir(parents=True,exist_ok=True)
    source=manifest()
    report={"format":"bublik-stage6-ui-live-v1","run_id":run_id,"created_at":stamp.isoformat(),
            "status":"failed","source_sha256":source,"checks":[],"answers_sha256":[],"generations":[],
            "url":args.url,"network":args.network,
            "environment":{"python":platform.python_version(),"system":platform.system(),"machine":platform.machine(),"playwright":importlib.metadata.version("playwright")},
            "evidence":"Actual browser+Qwen via configured network HTTPS origin. Browser uses normal TLS trust, no bypass/pin. Desktop/mobile viewport sessions run on one computer; this does not prove phone or mobile internet.",
            "not_run":["physical phone","Safari/iOS/Android hardware","mobile internet conditions","API restart during generation","CPU/RAM"]}
    with output.open("x",encoding="utf-8") as f:
        started=time.perf_counter()
        try:
            password=getpass.getpass("Account password: ")
            asyncio.run(run(args,report,password))
            report["source_unchanged"]=source==manifest()
            if report["checks"] and all(c["passed"] for c in report["checks"]) and report["source_unchanged"]: report["status"]="passed"
        except (KeyboardInterrupt,EOFError): report["error_code"]="operator_interrupted"
        except Exception as error:
            report["error_code"]="network_browser_check_failed"; report["failure_type"]=type(error).__name__
        report["elapsed_seconds"]=time.perf_counter()-started
        json.dump(report,f,ensure_ascii=False,indent=2); f.write("\n")
    print(json.dumps({"report":str(output),"status":report["status"]}))
    return 0 if report["status"]=="passed" else 1


if __name__=="__main__": sys.exit(main())
