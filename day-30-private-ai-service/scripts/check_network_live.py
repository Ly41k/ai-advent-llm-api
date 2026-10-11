"""Verified LAN/tailnet HTTPS API/auth and blocked-port check on the calling device."""
import argparse
import asyncio
from datetime import datetime, timezone
import getpass
import json
from pathlib import Path
import platform
import socket
import ssl
import sys
import time
import uuid

import httpx

from check_storage import ROOT, manifest
from check_browser_https import run_browser
from network_common import private_origin


def blocked_port(host, port):
    started = time.perf_counter()
    try:
        with socket.create_connection((host,port),timeout=3):
            state = "reachable"
    except ConnectionRefusedError:
        state = "refused"
    except (TimeoutError,socket.timeout):
        state = "timeout"
    except OSError:
        state = "network_error"
    return {"port":port,"state":state,"passed":state in {"refused","timeout"},
            "elapsed_seconds":time.perf_counter()-started}


async def run(args,report,password):
    tls = ssl.create_default_context(cafile=str(args.ca_file)) if args.ca_file else ssl.create_default_context()
    async with httpx.AsyncClient(base_url=args.url,verify=tls,trust_env=False,follow_redirects=False,timeout=15) as client:
        def check(name,passed):
            report["checks"].append({"name":name,"passed":bool(passed)})
            if not passed: raise ValueError("controlled_check_failed")
        started=time.perf_counter()
        r=await client.get("/api/v1/health/live")
        check("certificate_verified_live",r.status_code==200 and r.json()=={"status":"alive"})
        report["live_latency_seconds"]=time.perf_counter()-started
        for path in ("/","/assets/app.js","/assets/app.css"):
            r=await client.get(path)
            check("static_https_"+path,r.status_code==200 and r.headers.get("cache-control")=="no-store")
        await run_browser(client,report,args.username,password)
        for port in (args.api_port,11434):
            result=await asyncio.to_thread(blocked_port,urlsplit_host(args.url),port)
            report["blocked_ports"].append(result)
            check("port_unreachable_"+str(port),result["passed"])


def urlsplit_host(url):
    from urllib.parse import urlsplit
    return urlsplit(url).hostname


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url",required=True)
    parser.add_argument("--network",choices=("lan","tailnet"),required=True)
    parser.add_argument("--username",required=True)
    parser.add_argument("--ca-file",type=Path,help="Public LAN root.crt; tailnet uses system CA")
    parser.add_argument("--api-port",type=int,default=8000)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    try:
        private_origin(args.url,args.network)
        if not 1024<=args.api_port<=65535: raise ValueError()
        if args.network=="lan" and not args.ca_file: raise ValueError()
    except ValueError:
        parser.error("Canonical private HTTPS URL required; LAN requires --ca-file root.crt")
    stamp=datetime.now(timezone.utc); run_id=stamp.strftime("%Y%m%dT%H%M%S")+"-"+uuid.uuid4().hex[:8]
    output=args.output or ROOT/"reports/check"/("stage6-network-"+run_id+".json")
    output.parent.mkdir(parents=True,exist_ok=True)
    source=manifest()
    report={"format":"bublik-stage6-network-live-v1","run_id":run_id,"created_at":stamp.isoformat(),
            "status":"failed","source_sha256":source,"checks":[],"blocked_ports":[],
            "url":args.url,"network":args.network,
            "environment":{"python":platform.python_version(),"system":platform.system(),"machine":platform.machine()},
            "evidence":"Actual calling-device HTTPS sockets with certificate+hostname verification, auth/CSRF, history mutation and port probes. No browser or inference; client hardware/network type not independently established.",
            "not_run":["physical phone/browser","mobile internet conditions","Qwen inference","Ollama listener inspection","CPU/RAM"]}
    with output.open("x",encoding="utf-8") as f:
        started=time.perf_counter()
        try:
            password=getpass.getpass("Account password: ")
            asyncio.run(run(args,report,password))
            report["source_unchanged"]=source==manifest()
            if report["checks"] and all(c["passed"] for c in report["checks"]) and report["source_unchanged"]: report["status"]="passed"
        except (KeyboardInterrupt,EOFError): report["error_code"]="operator_interrupted"
        except Exception as error:
            report["error_code"]="network_check_failed"; report["failure_type"]=type(error).__name__
        report["elapsed_seconds"]=time.perf_counter()-started
        json.dump(report,f,ensure_ascii=False,indent=2); f.write("\n")
    print(json.dumps({"report":str(output),"status":report["status"]}))
    return 0 if report["status"]=="passed" else 1


if __name__=="__main__": sys.exit(main())
