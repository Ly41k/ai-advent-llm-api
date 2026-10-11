"""Prepare a control chat; verify phone continuation against persisted server history.

Phone hardware/Wi-Fi/mobile conditions are explicitly manual declarations, never
inferred from an API request made on the Mac. No API token is sent to the phone.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import ssl
import sys
import time
import uuid

import httpx

from check_storage import ROOT,manifest
from check_http_live import read_token,fingerprint
from bublik_service.http_api import runtime_manifest
from network_common import private_origin

P="/api/v1"
PHONE_QUESTION="Какое проверочное слово я попросил запомнить? Ответь только этим словом."


def history_checks(challenge,items):
    return [
        {"name":"same_saved_seed_history","passed":len(items)>=2 and fingerprint(items[:2])==challenge["seed_history_sha256"]},
        {"name":"one_phone_turn_without_duplicates","passed":len(items)==4 and items[2]["role"]=="user" and items[3]["role"]=="assistant"},
        {"name":"phone_control_question","passed":len(items)==4 and items[2]["content"]==PHONE_QUESTION},
        {"name":"remembered_control_word","passed":len(items)==4 and items[3]["content"].strip().casefold()==challenge["control_word"]},
        {"name":"phone_answer_completed","passed":len(items)==4 and items[3]["status"]=="completed"},
    ]


async def execute(args,report,token):
    tls=ssl.create_default_context(cafile=str(args.ca_file)) if args.ca_file else ssl.create_default_context()
    async with httpx.AsyncClient(base_url=args.url,verify=tls,trust_env=False,follow_redirects=False,
            timeout=15,headers={"Authorization":"Bearer "+token}) as client:
        def check(name,value):
            report["checks"].append({"name":name,"passed":bool(value)})
            if not value: raise ValueError("controlled_check_failed")
        async def get(path):
            r=await client.get(P+path); r.raise_for_status(); return r.json()
        ready=await get("/health/ready")
        check("verified_https_ready_runtime",ready["status"]=="ready" and ready["runtime_source_unchanged"] and ready["runtime_source_sha256"]==runtime_manifest())
        report["model_identity"]=ready["model"]["identity"]; report["profile"]=ready["profile"]
        if args.command=="prepare":
            r=await client.post(P+"/chats",json={"title":"Phone check "+report["run_id"]},headers={"Idempotency-Key":"device-chat-"+report["run_id"]})
            check("created_control_chat",r.status_code==201)
            chat=r.json()["chat_id"]; report["chat_id"]=chat
            word=secrets.choice(("мандарин","ромашка","карамель","фонарик","абрикос","черника"))
            report["control_word"]=word
            r=await client.post(P+f"/chats/{chat}/messages",json={"content":f"Запомни проверочное слово: {word}. Ответь только: принято","expected_revision":0},headers={"Idempotency-Key":"device-seed-"+report["run_id"]})
            check("seed_admitted",r.status_code==202)
            job=r.json()["generation_id"]; report["seed_generation_id"]=job
            deadline=time.monotonic()+240
            while time.monotonic()<deadline:
                value=await get("/generations/"+job)
                if value["status"] not in {"queued","running"}: break
                await asyncio.sleep(.5)
            else: raise TimeoutError("control_generation_deadline")
            check("seed_completed",value["status"]=="completed")
            items=(await get(f"/chats/{chat}/messages?limit=100"))["items"]
            check("seed_answer_literal",len(items)==2 and items[1]["content"].strip().casefold()=="принято")
            report["seed_history_sha256"]=fingerprint(items)
            report["chat_url"]=args.url+"/#chat="+chat
            report["phone_question"]=PHONE_QUESTION
            report["seed_metrics"]=value["metrics"]
            report["seed_context"]=value["context"]
            check("seed_context_bound",value["metrics"]["input_tokens"]<=value["context"]["input_token_upper_bound"] and
                  value["context"]["input_token_upper_bound"]+ready["profile"]["max_output"]+ready["profile"]["margin"]<=ready["profile"]["num_ctx"])
        else:
            challenge=json.loads(args.challenge.read_text())
            check("passed_prepare_same_source",challenge["format"]=="bublik-stage6-device-prepare-v1" and challenge["status"]=="passed" and challenge["source_sha256"]==manifest())
            chat=challenge["chat_id"]
            report["chat_id"]=chat
            items=(await get(f"/chats/{chat}/messages?limit=100"))["items"]
            for outcome in history_checks(challenge,items): check(outcome["name"],outcome["passed"])
            value=await get("/generations/"+items[3]["generation_id"])
            report["phone_generation"]={"id":value["id"],"status":value["status"],"metrics":value["metrics"],"context":value["context"]}
            check("phone_context_bound",value["metrics"]["input_tokens"]<=value["context"]["input_token_upper_bound"] and
                  value["context"]["input_token_upper_bound"]+ready["profile"]["max_output"]+ready["profile"]["margin"]<=ready["profile"]["num_ctx"])
            report["history_sha256"]=fingerprint(items)
            report["challenge_sha256"]=hashlib.sha256(args.challenge.read_bytes()).hexdigest()
            report["manual_declarations"]={"physical_phone":True,"device":args.device,"connection":args.connection,
                "source":"operator CLI declaration; hardware and Wi-Fi state are not independently measured by server"}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("prepare","verify"))
    parser.add_argument("--url",required=True)
    parser.add_argument("--network",choices=("lan","tailnet"),required=True)
    parser.add_argument("--token-file",type=Path,required=True,help="Existing private token file stays on the Mac")
    parser.add_argument("--ca-file",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--challenge",type=Path)
    parser.add_argument("--device",choices=("android","ios"))
    parser.add_argument("--connection",choices=("wifi","mobile"))
    parser.add_argument("--confirm-physical-device",action="store_true")
    args=parser.parse_args()
    try:
        private_origin(args.url,args.network)
        if args.network=="lan" and not args.ca_file: raise ValueError()
        if args.command=="verify" and not (args.challenge and args.device and args.connection and args.confirm_physical_device): raise ValueError()
        if args.command=="verify" and args.network=="lan" and args.connection!="wifi": raise ValueError()
        token=read_token(args.token_file.expanduser())
    except (ValueError,OSError,KeyError):
        parser.error("Private HTTPS endpoint/token required; verify requires challenge/device/connection/manual confirmation; LAN requires CA and Wi-Fi")
    stamp=datetime.now(timezone.utc); run_id=stamp.strftime("%Y%m%dT%H%M%S")+"-"+uuid.uuid4().hex[:8]
    source=manifest()
    report={"format":"bublik-stage6-device-"+args.command+"-v1","run_id":run_id,"created_at":stamp.isoformat(),
            "status":"failed","source_sha256":source,"checks":[],"url":args.url,"network":args.network,
            "evidence":"Actual certificate-verified API observations of a synthetic control chat. Phone continuation requires separate operator action. Hardware/network conditions are manual declarations, not automatically measured proof.",
            "not_run":["independent hardware/Wi-Fi state measurement","Safari/Android full browser matrix","CPU/RAM"]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as f:
        started=time.perf_counter()
        try:
            asyncio.run(execute(args,report,token))
            report["source_unchanged"]=source==manifest()
            if report["checks"] and all(c["passed"] for c in report["checks"]) and report["source_unchanged"]: report["status"]="passed"
        except (KeyboardInterrupt,EOFError): report["error_code"]="operator_interrupted"
        except Exception as error:
            report["error_code"]="device_check_failed"; report["failure_type"]=type(error).__name__
        report["elapsed_seconds"]=time.perf_counter()-started
        json.dump(report,f,ensure_ascii=False,indent=2); f.write("\n")
    result={"report":str(args.output),"status":report["status"]}
    if args.command=="prepare" and report["status"]=="passed":
        result.update({"open_on_phone":report["chat_url"],"send_on_phone":PHONE_QUESTION})
    print(json.dumps(result,ensure_ascii=False))
    return 0 if report["status"]=="passed" else 1


if __name__=="__main__": sys.exit(main())
