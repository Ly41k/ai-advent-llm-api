"""Three explicit stages of a real Ollama interruption. Never stops/restarts any process.

prepare starts a LONG synthetic generation; the operator interrupts Ollama.
interrupted proves terminal partial/history/gate; restored proves verified recovery.
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

from acceptance_support import API, history_record, literal, new_report
from check_http_live import CheckFailed, fingerprint, read_token
from check_storage import manifest
from network_common import private_origin

FORMAT = "bublik-stage8-recovery-live-v1"
INTERRUPTION_PROMPT_VERSION = "forest-story-v2"
INTERRUPTION_PROMPT = (
    "Напиши художественный рассказ о неспешной прогулке по осеннему лесу. "
    "Разверни рассказ в восемь подробных абзацев: утро, дорога к лесу, "
    "опушка, тропа, ручей, встреча с птицами, отдых и возвращение домой. "
    "В каждом абзаце опиши события, звуки, запахи и ощущения героя. "
    "Пиши сам рассказ на русском языке, без плана, вступительного комментария "
    "и предложения согласовать объём. Начни словами: Утро было прохладным."
)


def generation_observation(value):
    """Persist the synthetic control outcome before a fail-fast assertion."""
    content = value["assistant"]["content"]
    return {"generation_id": value["id"], "status": value["status"],
            "error_code": value["error_code"], "saved_characters": len(content),
            "control_answer": content, "metrics": value["metrics"],
            "started_at": value["started_at"], "finished_at": value["finished_at"]}


async def prepare(api, report):
    ready = await api.ready()
    api.check("exclusive_idle_preflight",ready["queued"]==ready["running"]==0 and not ready["inference_recovery_required"])
    chat = await api.create("interruption")
    receipt = await api.send(chat,"Запомни контрольное слово: мандарин. Ответь только: запомнил.","seed")
    value = (await api.wait_many([receipt],["seed"],"recovery_seed"))[0]
    api.check("seed_completed",value["status"]=="completed")
    seed = await api.history(chat)
    api.check("seed_two_messages",len(seed)==2)
    challenge = report["challenge"] = {"chat_id":chat,"seed_history_sha256":fingerprint(seed),
        "model_identity":ready["model"]["identity"],"profile":ready["profile"],"engine_epoch":ready["model"]["engine_epoch"]}
    challenge["interruption_prompt_version"] = INTERRUPTION_PROMPT_VERSION
    challenge["interruption_prompt"] = INTERRUPTION_PROMPT
    print('{"action":"prepare_Ollama_Quit_menu","next":"interrupt_immediately_on_signal"}',flush=True)
    receipt = await api.send(chat,INTERRUPTION_PROMPT,"interrupt-long")
    challenge["generation_id"] = receipt["generation_id"]
    started = time.monotonic()
    while time.monotonic()-started<90:
        value = await api.get("/generations/"+receipt["generation_id"])
        report["observed_generation"] = generation_observation(value)
        content = value["assistant"]["content"]
        if value["status"]=="running" and len(content)>=20:
            challenge["partial_characters"] = len(content)
            challenge["partial_sha256"] = fingerprint(content)
            report["observed_status"] = "running_with_saved_partial"
            print('{"action":"interrupt_Ollama_now","generation_status":"running_with_saved_partial"}',flush=True)
            return
        api.check("generation_not_already_terminal",value["status"] in {"queued","running"})
        await asyncio.sleep(.25)
    raise CheckFailed("partial_observation_timeout")


async def interrupted(api, report, baseline):
    challenge = baseline["challenge"]
    report["challenge"] = challenge
    started = time.monotonic()
    while time.monotonic()-started<90:
        value = await api.get("/generations/"+challenge["generation_id"])
        report["observed_generation"] = generation_observation(value)
        if value["status"] not in {"queued","running"}: break
        await asyncio.sleep(2)
    api.check("interrupted_terminal_status",value["status"] in {"failed","interrupted"})
    api.check("saved_partial_prefix_preserved",fingerprint(value["assistant"]["content"][:challenge["partial_characters"]])==challenge["partial_sha256"])
    live = await api.request("GET","/health/live")
    api.check("live_during_outage",live.status_code==200 and live.json()=={"status":"alive"})
    ready = await api.request("GET","/health/ready")
    state = ready.json()
    api.check("not_ready_and_recovery_gated",ready.status_code==503 and state["inference_recovery_required"]
              and state["queued"]==state["running"]==0)
    api.check("model_unavailable",not state["model_ready"])
    items = await api.history(challenge["chat_id"])
    api.check("seed_history_unchanged",len(items)==4 and fingerprint(items[:2])==challenge["seed_history_sha256"])
    report["saved_history"] = history_record(challenge["chat_id"],items)
    revision = (await api.get("/chats/"+challenge["chat_id"]))["revision"]
    rejected = await api.request("POST",f'/chats/{challenge["chat_id"]}/messages',
        json={"content":"Контрольный запрос при недоступной модели.","expected_revision":revision},
        headers={"Idempotency-Key":report["run_id"]+"-rejected"})
    api.check("new_admission_blocked",rejected.status_code==503 and rejected.json()["error"]["code"] in
              {"model_unavailable","inference_recovery_required"})
    api.check("rejection_without_history_change",items==await api.history(challenge["chat_id"]))
    report["terminal"] = {"generation_id":value["id"],"status":value["status"],"error_code":value["error_code"],
                           "partial_characters":len(value["assistant"]["content"])}


async def restored(api, report, baseline):
    challenge = baseline["challenge"]
    report["challenge"] = challenge
    ready = await api.ready()
    api.check("recovered_idle_no_gate",ready["queued"]==ready["running"]==0 and not ready["inference_recovery_required"])
    api.check("verified_new_engine_epoch",ready["model"]["engine_epoch"]!=challenge["engine_epoch"])
    api.check("same_model_profile",ready["model"]["identity"]==challenge["model_identity"] and ready["profile"]==challenge["profile"])
    row = history_record(challenge["chat_id"],await api.history(challenge["chat_id"]))
    api.check("full_terminal_history_unchanged",row==baseline["saved_history"])
    old = await api.get("/generations/"+challenge["generation_id"])
    api.check("old_generation_not_replayed",old["status"]==baseline["terminal"]["status"]
              and old["id"]==baseline["terminal"]["generation_id"])
    # New explicit generation in a NEW chat; never replay the interrupted job.
    chat = await api.create("after-recovery")
    receipt = await api.send(chat,"Сколько будет 2+2? Ответь только числом.","new-explicit")
    value = (await api.wait_many([receipt],["new-explicit"],"after_recovery"))[0]
    api.check("new_generation_completed",value["status"]=="completed" and literal(value["assistant"]["content"],"4"))
    api.check("old_history_still_unchanged",row==history_record(challenge["chat_id"],await api.history(challenge["chat_id"])))
    report["saved_history"] = row


async def run(client, report, phase, baseline=None, *, pause=asyncio.sleep,poll_interval=2):
    api = API(client,report,quota_pause=pause,poll_interval=poll_interval)
    if baseline:
        api.check("same_source_and_endpoint",baseline["source_sha256"]==report["source_sha256"] and baseline["url"]==report["url"])
    if phase=="prepare": await prepare(api,report)
    elif phase=="interrupted": await interrupted(api,report,baseline)
    elif phase=="restored": await restored(api,report,baseline)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("prepare","interrupted","restored"))
    parser.add_argument("--url",required=True)
    parser.add_argument("--network",choices=("lan","tailnet"),required=True)
    parser.add_argument("--token-file",type=Path,required=True)
    parser.add_argument("--ca-file",type=Path)
    parser.add_argument("--baseline",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    try:
        private_origin(args.url,args.network)
        if args.network=="lan" and not args.ca_file: raise ValueError()
        if sys.version_info<(3,13): raise ValueError()
        token = read_token(args.token_file.expanduser())
        baseline = json.loads(args.baseline.read_bytes()) if args.baseline else None
        if (args.phase!="prepare") != bool(baseline): raise ValueError()
        expected = "prepare" if args.phase=="interrupted" else "interrupted"
        if baseline and (baseline.get("format")!=FORMAT or baseline.get("status")!="passed" or baseline.get("phase")!=expected):
            raise ValueError()
        tls = ssl.create_default_context(cafile=str(args.ca_file)) if args.ca_file else ssl.create_default_context()
    except (ValueError,OSError,KeyError):
        parser.error("Private HTTPS/token and valid previous-phase baseline required; LAN needs CA")
    report = {"format":FORMAT,"run_id":uuid.uuid4().hex,"created_at":datetime.now(timezone.utc).isoformat(),
              "status":"failed","phase":args.phase,"url":args.url,"network":args.network,"source_sha256":manifest(),
              "checks":[],"environment":{"python":platform.python_version(),"system":platform.system(),"machine":platform.machine()},
              "evidence":"Actual HTTP observations of one explicitly created synthetic chat; operator stops/restarts Ollama separately.",
              "not_run":["forced API SIGKILL crash","physical device observation","backup/restore"]}
    with new_report(parser,args.output) as stream:
        started = time.perf_counter()
        try:
            async def execute():
                async with httpx.AsyncClient(base_url=args.url,headers={"Authorization":"Bearer "+token},trust_env=False,
                        follow_redirects=False,timeout=15,verify=tls) as client:
                    await run(client,report,args.phase,baseline)
            asyncio.run(execute())
            report["source_unchanged"] = report["source_sha256"]==manifest()
            if baseline: report["baseline_sha256"] = hashlib.sha256(args.baseline.read_bytes()).hexdigest()
            if report["source_unchanged"]: report["status"] = "passed"
        except CheckFailed as error: report["failed_check"] = error.name
        except KeyboardInterrupt: report["error_code"] = "operator_interrupted"
        except Exception: report["error_code"] = "recovery_observation_failed"
        finally:
            report["source_unchanged"] = report["source_sha256"]==manifest()
            if not report["source_unchanged"]: report["status"] = "failed"
            report["elapsed_seconds"] = time.perf_counter()-started
            json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write("\n")
    print(json.dumps({"report":str(args.output),"status":report["status"],"phase":args.phase}))
    return 0 if report["status"]=="passed" else 1


if __name__=="__main__": sys.exit(main())
