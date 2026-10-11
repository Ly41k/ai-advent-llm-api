"""Real HTTPS auth/CSRF client check (no Web UI or actual browser proof)."""
import argparse
import asyncio
from datetime import datetime,timezone
import getpass
import json
from pathlib import Path
import ssl
import sys
from urllib.parse import urlsplit
import uuid

import httpx

from check_storage import ROOT,manifest
from bublik_service.http_api import runtime_manifest
from bublik_service.security import COOKIE

P = "/api/v1"


async def run_browser(client,report,username,password):
    checks = report.setdefault("checks",[])
    def check(name,passed):
        checks.append({"name":name,"passed":bool(passed)})
        if not passed:
            raise ValueError("check_failed:"+name)
    origin = str(client.base_url).rstrip("/")
    check("unauthorized",(await client.get(P+"/chats")).status_code==401)
    r = await client.get(P+"/auth/session")
    check("bootstrap",r.status_code==200 and r.json()["user"] is None)
    cookie = r.headers.get("set-cookie","").lower()
    check("secure_cookie",all(part in cookie for part in (COOKIE.lower(),"secure","httponly","samesite=strict","path=/")) and "domain=" not in cookie)
    csrf = r.json()["csrf_token"]
    old = client.cookies.get(COOKIE)
    body = {"username":username,"password":password}
    denied = await client.post(P+"/auth/login",json=body,headers={"Origin":origin})
    check("login_csrf_required",denied.status_code==403)
    r = await client.post(P+"/auth/login",json=body,headers={"Origin":origin,"X-CSRF-Token":csrf})
    check("login",r.status_code==200)
    csrf = r.json()["csrf_token"]
    check("session_rotated",client.cookies.get(COOKIE)!=old)
    check("authenticated_history",(await client.get(P+"/chats")).status_code==200)
    ready = await client.get(P+"/health/ready")
    check("matching_runtime",ready.status_code in {200,503} and ready.json()["runtime_source_unchanged"] and ready.json()["runtime_source_sha256"]==runtime_manifest())
    denied = await client.post(P+"/chats",json={},headers={"Idempotency-Key":"csrf-check-"+uuid.uuid4().hex,"Origin":origin})
    check("mutation_csrf_required",denied.status_code==403)
    bad_origin = await client.post(P+"/chats",json={},headers={"Idempotency-Key":"origin-check-"+uuid.uuid4().hex,"Origin":"https://forbidden.example","X-CSRF-Token":csrf})
    check("origin_required",bad_origin.status_code==403)
    r = await client.post(P+"/chats",json={"title":"Stage 4 synthetic browser-auth check"},headers={"Idempotency-Key":"https-check-"+uuid.uuid4().hex,"Origin":origin,"X-CSRF-Token":csrf})
    check("authorized_mutation",r.status_code==201)
    report["created_chat_id"] = r.json()["chat_id"]
    check("ambiguous_credentials_denied",(await client.get(P+"/chats",headers={"Authorization":"Bearer invalid"})).status_code==403)
    saved_cookie = client.cookies.get(COOKIE)
    r = await client.post(P+"/auth/logout",json={},headers={"Origin":origin,"X-CSRF-Token":csrf})
    check("logout",r.status_code==200)
    check("logout_revoked",(await client.get(P+"/chats",headers={"Cookie":COOKIE+"="+saved_cookie})).status_code==401)
    # No password, opaque cookie or CSRF value is stored in the report.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url",default="https://localhost:8443")
    parser.add_argument("--username",required=True)
    parser.add_argument("--ca-file",type=Path)
    parser.add_argument("--output",type=Path)
    args = parser.parse_args()
    parsed = urlsplit(args.url)
    if parsed.scheme!="https" or parsed.hostname not in {"localhost","127.0.0.1","::1"} or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        parser.error("Stage 4 requires a canonical loopback HTTPS origin")
    password = getpass.getpass("Account password: ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"-"+uuid.uuid4().hex[:8]
    output = args.output or ROOT/"reports/check"/("stage4-https-"+run_id+".json")
    output.parent.mkdir(parents=True,exist_ok=True)
    source = manifest()
    report = {"format":"bublik-stage4-https-v1","run_id":run_id,"status":"failed","checks":[],"source_sha256":source,
              "evidence":"Real certificate-verified HTTPS client; no Web UI/browser engine and no Qwen inference"}
    async def execute():
        tls = ssl.create_default_context(cafile=str(args.ca_file)) if args.ca_file else True
        async with httpx.AsyncClient(base_url=args.url,verify=tls,trust_env=False,follow_redirects=False,timeout=15) as client:
            await run_browser(client,report,args.username,password)
    with output.open("x",encoding="utf-8") as stream:
        try:
            asyncio.run(execute())
            report["source_unchanged"] = source==manifest()
            if report["checks"] and all(c["passed"] for c in report["checks"]) and report["source_unchanged"]:
                report["status"]="passed"
        except KeyboardInterrupt:
            report["error_code"]="operator_interrupted"
        except Exception:
            report["error_code"]="https_check_failed"
        json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write("\n")
    print(json.dumps({"report":str(output),"status":report["status"]}))
    return 0 if report["status"]=="passed" else 1


if __name__=="__main__":
    raise SystemExit(main())
