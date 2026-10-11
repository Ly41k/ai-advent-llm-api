"""Stage 8: real HTTPS/Qwen baseline, quality, bounded concurrency and macOS resources.

Creates only synthetic test chats. No prompt changes, cloud, automatic unload or replay.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import ssl
import sys
import time
import uuid

import httpx

from acceptance_support import API, history_record, literal, russian_only, latency_summary, observed_overlap, new_report
from check_http_live import CheckFailed, fingerprint, read_token
from check_inference_live import CASES
from check_network_live import blocked_port
from check_storage import ROOT, manifest
from network_common import private_origin
from resource_observer import MacObserver


async def workload(api, report, observer):
    before = await api.ready()
    report["server_before"] = before
    api.check("initially_idle",before["queued"]==before["running"]==0 and not before["inference_recovery_required"])
    live = await api.request("GET","/health/live")
    api.check("https_live",live.status_code==200 and live.json()=={"status":"alive"})
    unauth = await api.request("GET","/chats",headers={"Authorization":""},quota_retry=False)
    api.check("unauthorized_401",unauth.status_code==401)
    report["quality"] = []
    report["chats"] = []
    chat = await api.create("multi-turn")
    observer.phase = "sequential"
    loaded = before["model"]["loaded_models"]
    report["first_request_loading"] = "already_loaded" if loaded else "not_loaded_before_first_request"
    for index,(case,prompt,expected) in enumerate(CASES):
        # Unlike the old technical-only report, quality failures are retained,
        # continue the run, and make quality_status/top-level status failed.
        receipt = await api.send(chat,prompt,case)
        group = "first_request" if index==0 else "sequential_subsequent"
        value = (await api.wait_many([receipt],[case],group))[0]
        api.check("completed_"+case,value["status"]=="completed")
        if expected:
            report["quality"].append({"case":case,"method":"exact_literal","expected":expected,
                                      "passed":literal(value["assistant"]["content"],expected)})
        if index==0:
            saved = await api.history(chat)
            record = report["requests"][-1]
            replay = await api.request("POST",f"/chats/{chat}/messages",
                json={"content":prompt,"expected_revision":record["revision"]},headers={"Idempotency-Key":record["idempotency_key"]})
            api.check("durable_replay_same_ids",replay.status_code==200 and all(replay.json()[k]==receipt[k]
                       for k in ("generation_id","user_message_id","assistant_message_id")))
            api.check("replay_without_history_change",saved==await api.history(chat))
            revision = (await api.get("/chats/"+chat))["revision"]
            for name,body,status,code in (("context_overflow",{"content":"x"*7000,"expected_revision":revision},422,"context_budget_exceeded"),
                    ("body_overflow",{"content":"x"*40000,"expected_revision":revision},413,"request_body_too_large")):
                rejected = await api.request("POST",f"/chats/{chat}/messages",json=body,headers={"Idempotency-Key":report["run_id"]+name})
                api.check(name,rejected.status_code==status and rejected.json()["error"]["code"]==code)
                api.check(name+"_without_history_change",saved==await api.history(chat))
    items = await api.history(chat)
    api.check("ten_sequential_twenty_unique_messages",len(items)==20 and len({m["id"] for m in items})==20)
    report["chats"].append(history_record(chat,items))
    api.check("visible_context_omission",any(g["context"]["omitted_turns"]>0 for g in report["generations"]))
    # Separate chats exercise greeting-language regressions without an explicit
    # user override that would hide the original Russian/Chinese failure.
    observer.phase = "russian_quality"
    for index in range(3):
        c = await api.create("russian-"+str(index))
        case = "russian-greeting-"+str(index)
        receipt = await api.send(c,"Привет! Как у тебя дела? Чем ты можешь мне помочь?",case)
        value = (await api.wait_many([receipt],[case],"russian_quality"))[0]
        api.check("completed_"+case,value["status"]=="completed")
        report["quality"].append({"case":case,"method":"cyrillic_present_no_CJK_screen",
                                  "passed":bool(russian_only(value["assistant"]["content"]))})
        report["chats"].append(history_record(c,await api.history(c)))
    observer.phase = "quota_window_wait"
    parallel = [await api.create("concurrent-"+str(i)) for i in range(3)]
    # A full window ensures three generation slots are available. Do not rely on
    # Retry-After of the oldest admission for a three-request batch.
    print('{"waiting_for_fresh_quota_seconds":61}',flush=True)
    for _ in range(61):
        await api.pause(1)
    observer.phase = "concurrent"
    receipts = await asyncio.gather(*(api.send(c,f"Reply only: queue-{i}","concurrent-"+str(i),revision=0)
                                    for i,c in enumerate(parallel)),return_exceptions=True)
    api.check("all_concurrent_admissions_observed",all(not isinstance(r,BaseException) for r in receipts))
    results = await api.wait_many(receipts,["concurrent-"+str(i) for i in range(3)],"concurrent")
    for i,(c,value) in enumerate(zip(parallel,results)):
        api.check("completed_concurrent_"+str(i),value["status"]=="completed")
        report["quality"].append({"case":"concurrent-"+str(i),"method":"exact_literal",
                                  "expected":f"queue-{i}","passed":literal(value["assistant"]["content"],f"queue-{i}")})
        report["chats"].append(history_record(c,await api.history(c)))
    overlap = observed_overlap(report["generations"])
    report["actual_generation_interval_overlap_max"] = overlap
    api.check("serialized_generation_intervals",overlap==1)
    api.check("queued_concurrent_wait",any(g["metrics"].get("queue_seconds",0)>0
                                          for g in report["generations"] if g["group"]=="concurrent"))
    for g in report["generations"]:
        metrics, context = g["metrics"],g["context"]
        api.check("bounded_input_output_"+g["case"],type(metrics.get("input_tokens")) is int
            and metrics["input_tokens"]<=context["input_token_upper_bound"]
            and type(metrics.get("output_tokens")) is int and metrics["output_tokens"]<=before["profile"]["max_output"]
            and context["input_token_upper_bound"]+before["profile"]["max_output"]+before["profile"]["margin"]<=before["profile"]["num_ctx"])
        api.check("generation_identity_"+g["case"],context["model_identity"]==before["model"]["identity"])
    # Deterministic HTTP rate-limit proof using read-only requests, independent
    # of how long ten Qwen generations took. Does not claim a generation-quota test.
    observer.phase = "http_quota"
    saved = await api.history(chat)
    rate = None
    for index in range(121):
        r = await api.request("GET","/chats/"+chat,quota_retry=False)
        if r.status_code==429:
            rate = r
            report["rate_limit"] = {"scope":"http_owner_120_per_minute","requests_until_429":index+1,
                                     "retry_after_seconds":int(r.headers.get("retry-after","0"))}
            break
        api.check("quota_probe_200",r.status_code==200)
    api.check("http_rate_429_retry_after",rate is not None and rate.json()["error"]["code"]=="rate_limit_exceeded"
              and int(rate.headers.get("retry-after","0"))>0)
    api.check("quota_without_history_change",saved==await api.history(chat))
    report["server_after"] = await api.ready("ready_after")
    after = report["server_after"]
    api.check("identity_profile_unchanged",before["model"]["identity"]==after["model"]["identity"] and before["profile"]==after["profile"])
    api.check("final_idle_no_gate",after["queued"]==after["running"]==0 and not after["inference_recovery_required"])


async def verify_saved(api, before, report):
    api.check("baseline_same_sources",before.get("source_sha256")==report["source_sha256"])
    api.check("baseline_complete_technical_run",before.get("technical_status")=="passed" and bool(before.get("chats")))
    ready = await api.ready()
    report["server_before"] = ready
    api.check("same_model_profile",ready["model"]["identity"]==before["server_after"]["model"]["identity"]
              and ready["profile"]==before["server_after"]["profile"])
    report["chats"] = []
    for row in before["chats"]:
        current = history_record(row["id"],await api.history(row["id"]))
        api.check("saved_history_"+row["id"],current==row)
        report["chats"].append(current)
    report["quality_status"] = "not_run"


async def run(client, report, *, history_from=None, observer_factory=MacObserver, pause=asyncio.sleep, poll_interval=2):
    api = API(client,report,quota_pause=pause,poll_interval=poll_interval)
    if history_from:
        await verify_saved(api,history_from,report)
        report["technical_status"] = "passed"
        report["resources"] = {"status":"not_run","reason":"read_only_history_mode"}
        return
    ready = await api.ready("resource_preflight_ready")
    observer = observer_factory(ready["model"]["identity"])
    try:
        async with observer:
            await workload(api,report,observer)
        api.check("resource_observations_complete",observer.report()["status"]=="passed")
        report["technical_status"] = "passed"
    finally:
        report["resources"] = observer.report()
        report["latency"] = latency_summary(report["generations"])
        expected_checks = sum(expected is not None for _,_,expected in CASES)+6
        report["quality_status"] = ("incomplete" if len(report.get("quality",[]))!=expected_checks else
                                    "passed" if all(q["passed"] for q in report["quality"]) else "failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url",required=True)
    parser.add_argument("--network",choices=("lan","tailnet"),required=True)
    parser.add_argument("--token-file",type=Path,required=True)
    parser.add_argument("--ca-file",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--history-from",type=Path)
    args = parser.parse_args()
    try:
        endpoint = private_origin(args.url,args.network)
        if args.network=="lan" and not args.ca_file: raise ValueError()
        if platform.system()!="Darwin" or sys.version_info<(3,13): raise ValueError()
        token = read_token(args.token_file.expanduser())
        baseline = json.loads(args.history_from.read_bytes()) if args.history_from else None
        if baseline and (baseline.get("format")!="bublik-stage8-acceptance-live-v1" or baseline.get("technical_status")!="passed"):
            raise ValueError()
        tls = ssl.create_default_context(cafile=str(args.ca_file)) if args.ca_file else ssl.create_default_context()
    except (ValueError,OSError,KeyError):
        parser.error("Mac/Python 3.13, private HTTPS/token and valid baseline required; LAN needs CA")
    stamp = datetime.now(timezone.utc)
    report = {"format":"bublik-stage8-acceptance-live-v1","run_id":uuid.uuid4().hex,"created_at":stamp.isoformat(),
        "status":"failed","technical_status":"failed","quality_status":"not_run","source_sha256":manifest(),
        "url":args.url,"network":args.network,"mode":"history" if baseline else "baseline",
        "environment":{"python":platform.python_version(),"system":platform.system(),"machine":platform.machine()},
        "checks":[],"generations":[],"blocked_ports":[],"semantic_review":"pending_human_review",
        "evidence":"Calling Mac verified HTTPS/Qwen + synthetic chats + sampled OS counters; not physical-phone/network-condition proof.",
        "not_run":["generation admission quota timing-independent test","active inference interruption/recovery (separate checker)",
                   "independent physical phone observation","deployed grants policy audit","backup/restore","forced cold-model eviction"]}
    with new_report(parser,args.output) as stream:
        started = time.perf_counter()
        try:
            async def execute():
                async with httpx.AsyncClient(base_url=args.url,headers={"Authorization":"Bearer "+token},trust_env=False,
                        follow_redirects=False,timeout=15,verify=tls) as client:
                    await run(client,report,history_from=baseline)
                for port in (8000,11434):
                    probe = await asyncio.to_thread(blocked_port,endpoint.hostname,port)
                    report["blocked_ports"].append(probe)
                    if not probe["passed"]: raise CheckFailed("blocked_port_"+str(port))
            asyncio.run(execute())
            report["source_unchanged"] = report["source_sha256"]==manifest()
            if baseline: report["baseline_sha256"] = hashlib.sha256(args.history_from.read_bytes()).hexdigest()
            if report["source_unchanged"] and report["technical_status"]=="passed" and report["quality_status"] in {"passed","not_run"}:
                report["status"] = "passed"
        except CheckFailed as error:
            report["technical_status"] = "failed"
            report["failed_check"] = error.name
        except KeyboardInterrupt:
            report["technical_status"] = "failed"
            report["error_code"] = "operator_interrupted"
        except httpx.HTTPStatusError as error:
            report["technical_status"] = "failed"
            report["error_code"] = "http_observation_failed"
            report["http_status"] = error.response.status_code
        except httpx.RequestError:
            report["technical_status"] = "failed"
            report["error_code"] = "http_transport_failed"
        except Exception:
            report["technical_status"] = "failed"
            report["error_code"] = "acceptance_observation_failed"
        finally:
            report["source_unchanged"] = report["source_sha256"]==manifest()
            if not report["source_unchanged"]:
                report["technical_status"] = "failed"
                report["status"] = "failed"
            report["elapsed_seconds"] = time.perf_counter()-started
            json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False)
            stream.write("\n")
    print(json.dumps({"report":str(args.output),"status":report["status"],"technical_status":report["technical_status"],"quality_status":report["quality_status"]}))
    return 0 if report["status"]=="passed" else 1


if __name__=="__main__": sys.exit(main())
