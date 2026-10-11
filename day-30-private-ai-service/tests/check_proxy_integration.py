"""Optional real Caddy/TLS/Chromium integration; synthetic inference only."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

import httpx
import uvicorn

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from check_storage import ROOT,manifest
from check_browser_https import run_browser
from check_web_ui import certificate_pin
from check_web_ui_live import run as run_ui
from check_device_handoff import execute as run_handoff,PHONE_QUESTION
from browser_fixture import BrowserAdapter,PASSWORD
from bublik_service.http_api import HTTPSettings,create_app
from bublik_service.inference.ollama import Answer
from bublik_service.security import password_hash,SecurityStore,SCOPES
from bublik_service.storage import ChatRepository


def free_listener():
    listener=socket.socket()
    listener.bind(("127.0.0.1",0)); listener.listen(64)
    return listener


async def execute(caddy,root,report):
    root=Path(root)
    root.chmod(0o700)
    repo=ChatRepository(root/"chat.sqlite3")
    owner=repo.create_user("ui-test",password_hash(PASSWORD))
    adapter=BrowserAdapter()
    async def generate(job,checkpoint):
        question=job["context"]["messages"][-1]["content"]
        if "Какое проверочное" in question:
            seed=next(m["content"] for m in job["context"]["messages"] if m["role"]=="user" and "Запомни проверочное слово:" in m["content"])
            answer=seed.split(": ",1)[1].split(".",1)[0]
        else:
            answer="мандарин" if "Какое" in question else "OK" if "OK" in question else "принято"
        await asyncio.sleep(.2); await checkpoint(answer)
        await asyncio.sleep(.2)
        return Answer(answer,"completed",{"input_tokens":1,"output_tokens":1})
    adapter.generate=generate
    listener=free_listener(); api_port=listener.getsockname()[1]
    probe=free_listener(); port=probe.getsockname()[1]; probe.close()
    url=f"https://127.0.0.1:{port}"
    app=create_app(HTTPSettings(repo.database.path,origins=(url,),trusted_loopback_proxy=True,sse_poll=.05),
                   adapter_factory=lambda:adapter,repository=repo)
    server=uvicorn.Server(uvicorn.Config(app,proxy_headers=False,access_log=False,log_level="critical",timeout_graceful_shutdown=2))
    thread=threading.Thread(target=lambda:server.run(sockets=[listener]),daemon=True)
    thread.start()
    config=(ROOT/"deploy/Caddyfile.lan.template").read_text()
    # Test-only loopback substitution. Production configure_network rejects it.
    for key,value in {"LAN_IP":"127.0.0.1","LAN_PORT":port,"API_PORT":api_port}.items():
        config=config.replace("@@"+key+"@@",str(value))
    path=root/"Caddyfile"; path.write_text(config)
    env={**os.environ,"XDG_DATA_HOME":str(root/"data"),"XDG_CONFIG_HOME":str(root/"config")}
    proc=None
    checks=report["checks"]
    def checked(name,value):
        checks.append({"name":name,"passed":bool(value)})
        if not value: raise ValueError("controlled_check_failed")
    try:
        adapted=subprocess.run([str(caddy),"adapt","--config",str(path),"--validate"],env=env,capture_output=True,check=True)
        value=json.loads(adapted.stdout)
        checked("exact_binding_no_admin_no_redirects",value["admin"]["disabled"] and
                all(s["listen"]==[f"127.0.0.1:{port}"] and s["automatic_https"]["disable_redirects"] and s["protocols"]==["h1","h2"] for s in value["apps"]["http"]["servers"].values()))
        proc=subprocess.Popen([str(caddy),"run","--config",str(path)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        ca=root/"data/caddy/pki/authorities/local/root.crt"
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            if proc.poll() is not None: raise RuntimeError("proxy_start_failed")
            if ca.exists() and server.started:
                try:
                    async with httpx.AsyncClient(verify=ssl.create_default_context(cafile=str(ca)),trust_env=False) as client:
                        if (await client.get(url+"/api/v1/health/live")).status_code==200: break
                except httpx.HTTPError: pass
            await asyncio.sleep(.1)
        else: raise TimeoutError("proxy_start_timeout")
        tls=ssl.create_default_context(cafile=str(ca))
        async with httpx.AsyncClient(base_url=url,verify=tls,trust_env=False,follow_redirects=False) as client:
            checked("verified_internal_ca_https",(await client.get("/")).status_code==200)
            r=await client.get("/",headers={"X-Forwarded-Proto":"http","X-Forwarded-Host":"evil.example","Forwarded":"proto=http"})
            checked("proxy_overwrites_untrusted_forwarding",r.status_code==200)
            await run_browser(client,report,"ui-test",PASSWORD)
        try:
            async with httpx.AsyncClient(base_url=url,verify=True,trust_env=False) as client: await client.get("/")
        except httpx.ConnectError: checked("untrusted_ca_rejected",True)
        else: checked("untrusted_ca_rejected",False)
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{api_port}",trust_env=False) as client:
            checked("raw_backend_cannot_open_ui",(await client.get("/",headers={"Host":f"127.0.0.1:{port}"})).status_code==400)
        # Independently verified peer leaf, ephemeral SPKI pin for this Linux
        # fixture only. Do not install a test CA in the user's/system trust store.
        def certificate():
            with socket.create_connection(("127.0.0.1",port),timeout=5) as raw:
                with tls.wrap_socket(raw,server_hostname="127.0.0.1") as secure:
                    return ssl.DER_cert_to_PEM_cert(secure.getpeercert(binary_form=True))
        leaf=root/"leaf.pem"; leaf.write_text(await asyncio.to_thread(certificate))
        args=SimpleNamespace(url=url,username="ui-test",ca_file=ca,
            browser_launch_args=["--ignore-certificate-errors-spki-list="+certificate_pin(leaf)])
        report.update({"answers_sha256":[],"generations":[],"run_id":"synthetic-proxy-review","environment":{}})
        await run_ui(args,report,PASSWORD)
        # Review prepare/verify against the real proxy and persisted synthetic
        # history. The second API turn here is a fixture, not physical phone proof.
        token=SecurityStore(repo).issue_token(owner,"fixture",SCOPES)["token"]
        args=SimpleNamespace(url=url,ca_file=ca,command="prepare")
        value={"format":"bublik-stage6-device-prepare-v1","run_id":"synthetic-handoff", "checks":[]}
        await run_handoff(args,value,token)
        value.update({"status":"passed","source_sha256":manifest()})
        challenge=root/"challenge.json"; challenge.write_text(json.dumps(value))
        async with httpx.AsyncClient(base_url=url,verify=tls,trust_env=False,headers={"Authorization":"Bearer "+token}) as client:
            chat=value["chat_id"]
            current=(await client.get("/api/v1/chats/"+chat)).json()
            response=await client.post(f"/api/v1/chats/{chat}/messages",json={"content":PHONE_QUESTION,"expected_revision":current["revision"]},headers={"Idempotency-Key":"synthetic-phone"})
            checked("handoff_fixture_second_turn_admitted",response.status_code==202)
            job=response.json()["generation_id"]
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                result=(await client.get("/api/v1/generations/"+job)).json()
                if result["status"] not in {"queued","running"}: break
                await asyncio.sleep(.1)
        args.command="verify"; args.challenge=challenge; args.device="android"; args.connection="wifi"
        value={"checks":[]}
        await run_handoff(args,value,token)
        for check in value["checks"]: checked("handoff_fixture_"+check["name"],check["passed"])
    finally:
        server.should_exit=True
        await asyncio.to_thread(thread.join,10)
        listener.close()
        if proc:
            proc.terminate()
            try: stdout,stderr=await asyncio.to_thread(proc.communicate,timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill(); stdout,stderr=await asyncio.to_thread(proc.communicate)
            checked("proxy_logs_no_password",PASSWORD.encode() not in stdout+stderr)
        if thread.is_alive(): raise RuntimeError("backend_stop_failed")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--caddy",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    source=manifest()
    report={"format":"bublik-stage6-proxy-fixture-v1","created_at":datetime.now(timezone.utc).isoformat(),
        "status":"failed","source_sha256":source,"checks":[],
        "system":platform.system(),"python":platform.python_version(),
        "caddy":subprocess.run([str(args.caddy),"version"],capture_output=True,check=True,text=True).stdout.strip(),
        "evidence":"Actual Caddy TLS/internal CA -> plain loopback Uvicorn, SQLite, Chromium desktop/mobile viewport. Synthetic inference only. Verified preflight + ephemeral leaf SPKI pin; no trust-store installation.",
        "not_run":["Qwen","LAN device","physical phone","Tailscale Serve","mobile internet","target Mac","normal browser trust"]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as f:
        started=time.perf_counter()
        try:
            with tempfile.TemporaryDirectory(prefix="bublik-proxy-review-") as root:
                asyncio.run(execute(args.caddy,root,report))
            report["source_unchanged"]=source==manifest()
            if report["checks"] and all(c["passed"] for c in report["checks"]) and report["source_unchanged"]: report["status"]="passed"
        except Exception as error:
            report["error_code"]="proxy_review_failed"; report["failure_type"]=type(error).__name__
        report["elapsed_seconds"]=time.perf_counter()-started
        json.dump(report,f,ensure_ascii=False,indent=2); f.write("\n")
    print(json.dumps({"report":str(args.output),"status":report["status"]}))
    return 0 if report["status"]=="passed" else 1


if __name__=="__main__": sys.exit(main())
