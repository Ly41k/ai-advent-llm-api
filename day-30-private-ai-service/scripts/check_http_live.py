"""Live API + local Qwen checks; never start Ollama or claim LAN/phone proof."""
import argparse
import asyncio
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import sys
import time
from urllib.parse import urlsplit
import uuid

import httpx

from check_storage import ROOT,manifest
from bublik_service.http_api import runtime_manifest

P = "/api/v1"
SAFE_ERROR_CODES = frozenset({"rate_limit_exceeded", "user_queue_full", "global_queue_full",
    "model_unavailable", "storage_unavailable", "service_unavailable", "authentication_required",
    "insufficient_scope", "stale_revision", "chat_has_outstanding_generation",
    "context_budget_exceeded", "inference_recovery_required", "invalid_request"})


class CheckFailed(ValueError):
    """A controlled check name, never an upstream response or exception message."""
    def __init__(self, name):
        self.name = name
        super().__init__("check_failed")


def admission_observation(response, case):
    value = {"case": case, "http_status": response.status_code}
    try:
        body = response.json()
    except ValueError:
        return value
    if isinstance(body, dict):
        if response.status_code == 202:
            ident = body.get("generation_id")
            if isinstance(ident, str) and len(ident) == 32 and all(c in "0123456789abcdef" for c in ident):
                value["generation_id"] = ident
        else:
            error = body.get("error")
            code = error.get("code") if isinstance(error, dict) else None
            value["error_code"] = code if isinstance(code, str) and code in SAFE_ERROR_CODES else "unknown_error"
    return value


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def read_token(path):
    info = path.stat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode&0o077:
        raise ValueError("Token file must be a private regular file (0600)")
    if info.st_size>8192:
        raise ValueError("Invalid token file")
    value = json.loads(path.read_text())["token"]
    if not isinstance(value,str) or len(value)!=43:
        raise ValueError("Invalid token file")
    return value


async def run_checks(client,report,*,resume=None,deadline=1800):
    checks = report.setdefault("checks",[])
    def check(name,passed):
        checks.append({"name":name,"passed":bool(passed)})
        if not passed:
            raise CheckFailed(name)
    async def get(path):
        r = await client.get(P+path)
        r.raise_for_status()
        return r.json()
    before = await get("/health/ready")
    report["server_before"] = before
    check("ready_and_matching_runtime",before["status"]=="ready" and before["runtime_source_unchanged"] and before["runtime_source_sha256"]==runtime_manifest())
    report.setdefault("chats",[])
    if resume:
        check("runtime_matches_original_report",resume["server_before"]["runtime_source_sha256"]==before["runtime_source_sha256"])
        for record in resume["chats"]:
            history = await get(f"/chats/{record['id']}/messages?limit=100")
            check("restart_history_"+record["id"],fingerprint(history)==record["history_sha256"])
            report["chats"].append(record)
        check("history_after_restart",bool(report["chats"]))
        return
    report["generations"] = []
    async def create(key):
        r = await client.post(P+"/chats",json={"title":"Stage 4 synthetic HTTP check"},headers={"Idempotency-Key":key})
        check("create_"+key,r.status_code==201)
        return r.json()["chat_id"]
    async def send(chat,content,revision,key):
        return await client.post(P+f"/chats/{chat}/messages",json={"content":content,"expected_revision":revision},headers={"Idempotency-Key":key})
    async def wait(receipt,name):
        start = time.monotonic()
        while time.monotonic()-start<deadline:
            value = await get("/generations/"+receipt["generation_id"])
            if value["status"] not in {"queued","running"}:
                report["generations"].append({"case":name,"id":value["id"],"status":value["status"],
                    "error_code":value["error_code"],"answer":value["assistant"]["content"],
                    "metrics":value["metrics"],"context":value["context"]})
                check("completed_"+name,value["status"]=="completed")
                check("context_bound_"+name,value["metrics"]["input_tokens"]<=value["context"]["input_token_upper_bound"])
                return value
            await asyncio.sleep(1)
        raise ValueError("generation_wait_timeout")
    unauth = await client.get(P+"/chats",headers={"Authorization":""})
    check("unauthorized_request",unauth.status_code==401)
    chat = await create("main-"+report["run_id"])
    prompts = [
        ("Запомни: контрольное слово — мандарин. Ответь только: запомнил.","запомнил"),
        ("Какое контрольное слово я назвал? Ответь одним словом.","мандарин"),
        ("Remember a separate English code name: lantern. Reply only: remembered.","remembered"),
        ("What English code name did I give you? Reply with that word only.","lantern"),
        ("Исправление: теперь русское контрольное слово — сапфир. Ответь только: принято.","принято"),
        ("Назови текущее русское контрольное слово одним словом.","сапфир"),
        ("Сколько будет 2 + 2? Ответь только числом.","4"),
        ("Назови английское кодовое слово одним словом.","lantern"),
        ("Назови текущее русское контрольное слово одним словом.","сапфир"),
        ("Ответь только OK.","ok"),
    ]
    for index,(prompt,expected) in enumerate(prompts):
        revision = (await get("/chats/"+chat))["revision"]
        key = "sequential-"+str(index)
        response = await send(chat,prompt,revision,key)
        check("admitted_"+key,response.status_code==202)
        answer = await wait(response.json(),key)
        check("literal_"+key,answer["assistant"]["content"].strip().casefold()==expected)
        if index==0:
            replay = await send(chat,prompt,revision,key)
            check("idempotent_delivery",replay.status_code==200 and replay.json()["generation_id"]==response.json()["generation_id"])
            saved = await get(f"/chats/{chat}/messages?limit=100")
            overflow = await send(chat,"x"*7000,(await get("/chats/"+chat))["revision"],"overflow")
            check("context_overflow",overflow.status_code==422 and overflow.json()["error"]["code"]=="context_budget_exceeded")
            check("overflow_did_not_change_history",saved==await get(f"/chats/{chat}/messages?limit=100"))
        print(json.dumps({"completed_case":key}),flush=True)
    check("ten_sequential",len(report["generations"])==10)
    revision = (await get("/chats/"+chat))["revision"]
    saved = await get(f"/chats/{chat}/messages?limit=100")
    rate = await send(chat,"Reply only OK.",revision,"rate-check")
    # Fixed quota is 10 successful admissions in a sliding minute. Slow machines
    # may span >60s; report inconclusive rather than silently claiming a pass.
    check("rate_limit",rate.status_code==429 and int(rate.headers.get("retry-after","0"))>0)
    check("rate_rejected_without_write",saved==await get(f"/chats/{chat}/messages?limit=100"))
    # Retry-After is time until the OLDEST admission expires: only one slot
    # is guaranteed to open. A batch of three needs a fresh sliding window.
    # Wait a full minute after the rejection so all this run's admissions
    # expire, without changing the server quota or retrying an accepted job.
    delay = max(61, int(rate.headers["retry-after"])+1)
    report["quota_wait"] = {"retry_after_seconds":int(rate.headers["retry-after"]),
                            "wait_seconds":delay,"policy":"fresh-60s-window-v1"}
    print(json.dumps({"waiting_for_quota_seconds":delay}),flush=True)
    while delay>0:
        step = min(delay,5)
        await asyncio.sleep(step)
        delay-=step
    parallel = [await create("parallel-"+str(i)+"-"+report["run_id"]) for i in range(3)]
    responses = await asyncio.gather(*(send(c,f"Reply only queue-{i}.",0,"parallel-"+str(i)) for i,c in enumerate(parallel)))
    report["concurrent_admissions"] = [admission_observation(r,"parallel-"+str(i)) for i,r in enumerate(responses)]
    check("three_concurrent_admissions",[r.status_code for r in responses]==[202]*3)
    for i,response in enumerate(responses):
        value = await wait(response.json(),"parallel-"+str(i))
        check("parallel_isolation_"+str(i),value["assistant"]["content"].strip().casefold()==f"queue-{i}")
    check("observed_queue_wait",any(r["metrics"]["queue_seconds"]>0 for r in report["generations"][-3:]))
    for ident in [chat,*parallel]:
        history = await get(f"/chats/{ident}/messages?limit=100")
        report["chats"].append({"id":ident,"history_sha256":fingerprint(history),"messages":len(history["items"])})
    after = await get("/health/ready")
    report["server_after"] = after
    check("runtime_unchanged",after["runtime_source_unchanged"] and after["runtime_source_sha256"]==before["runtime_source_sha256"])
    check("model_identity_unchanged",after["model"]["identity"]==before["model"]["identity"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url",default="http://127.0.0.1:8000")
    parser.add_argument("--token-file",type=Path,required=True)
    parser.add_argument("--ca-file",type=Path)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--history-from",type=Path,help="After server restart: verify saved history from previous report")
    args = parser.parse_args()
    parsed = urlsplit(args.url)
    if parsed.scheme not in {"http","https"} or parsed.hostname not in {"localhost","127.0.0.1","::1"} or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        parser.error("Stage 4 checker accepts only literal loopback/localhost HTTP(S) origins")
    if sys.version_info<(3,13):
        parser.error("Python 3.13+ required")
    try:
        token = read_token(args.token_file.expanduser())
        resume = json.loads(args.history_from.read_text()) if args.history_from else None
        if resume and (resume.get("status")!="passed" or not resume.get("chats")):
            raise ValueError("History source must be a passed complete report")
    except (OSError,ValueError,KeyError) as error:
        parser.error(str(error) if isinstance(error,ValueError) else "Cannot read private token/history file")
    stamp = datetime.now(timezone.utc)
    run_id = stamp.strftime("%Y%m%dT%H%M%S")+"-"+uuid.uuid4().hex[:8]
    output = args.output or ROOT/"reports/check"/("stage4-http-"+run_id+".json")
    output.parent.mkdir(parents=True,exist_ok=True)
    source = manifest()
    report = {"format":"bublik-stage4-http-live-v1","run_id":run_id,"created_at":stamp.isoformat(),"status":"failed",
              "mode":"history_after_restart" if resume else "inference", "source_sha256":source,
              "environment":{"python":platform.python_version(),"system":platform.system(),"machine":platform.machine()},
              "checks":[],"network_access":"loopback HTTP(S) only","not_run":["LAN devices","mobile internet","browser on Mac/iOS/Android",
              "operational Ollama off/on","physical peak RAM/CPU/swap", "external clients sharing Ollama"]}
    async def execute():
        import ssl
        verify = ssl.create_default_context(cafile=str(args.ca_file)) if args.ca_file else True
        async with httpx.AsyncClient(base_url=args.url,headers={"Authorization":"Bearer "+token},trust_env=False,
                                    follow_redirects=False,timeout=30,verify=verify) as client:
            await run_checks(client,report,resume=resume)
    with output.open("x",encoding="utf-8") as stream:
        try:
            asyncio.run(execute())
            report["source_unchanged"] = source==manifest()
            if report["checks"] and all(c["passed"] for c in report["checks"]) and report["source_unchanged"]:
                report["status"]="passed"
        except KeyboardInterrupt:
            report["error_code"]="operator_interrupted"
        except CheckFailed as error:
            report["error_code"]="check_failed"
            report["failed_check"]=error.name
        except httpx.HTTPStatusError as error:
            report["error_code"]="http_request_failed"
            report["http_status"]=error.response.status_code
        except httpx.RequestError:
            report["error_code"]="http_transport_failed"
        except Exception:
            report["error_code"]="live_check_failed"
        json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write("\n")
    print(json.dumps({"report":str(output),"status":report["status"]}))
    return 0 if report["status"]=="passed" else 1


if __name__=="__main__":
    raise SystemExit(main())
