"""Real Chromium UI + your local Qwen over certificate-verified loopback HTTPS."""
import argparse
import asyncio
from datetime import datetime,timezone
import getpass
import importlib.metadata
import json
from pathlib import Path
import platform
import ssl
import sys
import time
from urllib.parse import urlsplit
import uuid

import httpx

from check_storage import ROOT,manifest
from check_web_ui import certificate_pin
from bublik_service.http_api import runtime_manifest


async def run(args,report,password):
    from playwright.async_api import async_playwright,expect
    checks=report["checks"]
    def checked(name,value=True):
        checks.append({"name":name,"passed":bool(value)})
        if not value: raise ValueError("controlled_check_failed")
    tls=ssl.create_default_context(cafile=str(args.ca_file)) if args.ca_file else ssl.create_default_context()
    async with httpx.AsyncClient(base_url=args.url,verify=tls,trust_env=False,follow_redirects=False) as client:
        checked("certificate_verified_preflight",(await client.get("/api/v1/health/live")).status_code==200)
    async with async_playwright() as pw:
        launch_args=getattr(args,"browser_launch_args",None)
        if launch_args is None:
            launch_args=["--ignore-certificate-errors-spki-list="+certificate_pin(args.ca_file)]
        browser=await pw.chromium.launch(args=launch_args)
        report["environment"]["browser"]=browser.version
        desktop=await browser.new_context(viewport={"width":1280,"height":850})
        mobile=await browser.new_context(viewport={"width":390,"height":844},is_mobile=True,has_touch=True)
        page=await desktop.new_page(); phone=await mobile.new_page()
        stream_statuses=[]; external=[]; errors=[]
        for target in (page,phone):
            target.on("request",lambda req:external.append(True) if not req.url.startswith(args.url+"/") else None)
            target.on("pageerror",lambda _:errors.append(True))
            target.on("response",lambda response:stream_statuses.append(response.status) if response.url.endswith("/events") else None)
        async def login(target,chat=None):
            await target.goto(args.url+("/#chat="+chat if chat else "/"))
            await expect(target.locator("#login-button")).to_be_enabled()
            await target.locator("#username").fill(args.username)
            await target.locator("#password").fill(password)
            await target.locator("#login-button").click()
            await expect(target.locator("#workspace")).to_be_visible()
            await expect(target.locator("#model-status")).to_contain_text("готова",timeout=20000)
        async def turn(target,question,expected):
            started=time.perf_counter()
            await expect(target.locator("#message-input")).to_be_enabled()
            await target.locator("#message-input").fill(question)
            await expect(target.locator("#send-button")).to_be_enabled()
            await target.locator("#send-button").click()
            await expect(target.locator("#message-input")).to_have_value("",timeout=30000)
            await expect(target.locator(".message.user .message-text").last).to_have_text(question,timeout=30000)
            await expect(target.locator(".message.assistant").last).to_have_attribute("data-state","completed",timeout=180000)
            value=(await target.locator(".message.assistant .message-text").last.inner_text()).strip()
            import hashlib
            number=len(report["answers_sha256"])
            report["answers_sha256"].append(hashlib.sha256(value.encode()).hexdigest())
            latest=await target.evaluate("chat => fetch('/api/v1/chats/'+chat+'/messages?latest=true&limit=1',{cache:'no-store'}).then(r=>r.json())",report["created_chat_id"])
            generation=await target.evaluate("id => fetch('/api/v1/generations/'+id,{cache:'no-store'}).then(r=>r.json())",latest["items"][-1]["generation_id"])
            report["generations"].append({"id":generation["id"],"status":generation["status"],"error_code":generation["error_code"],
                "metrics":generation["metrics"],"context":generation["context"],"browser_turn_seconds":time.perf_counter()-started})
            checked("literal_turn_"+str(number),value.casefold()==expected.casefold())
            checked("context_bound_turn_"+str(number),generation["metrics"]["input_tokens"]<=generation["context"]["input_token_upper_bound"]
                and generation["context"]["input_token_upper_bound"]+report["profile"]["max_output"]+report["profile"]["margin"]<=report["profile"]["num_ctx"])
        try:
            await login(page)
            ready=await page.evaluate("fetch('/api/v1/health/ready',{cache:'no-store'}).then(r=>r.json())")
            checked("matching_runtime_and_model_ready",ready.get("status")=="ready" and ready.get("runtime_source_sha256")==runtime_manifest())
            report["profile"]=ready["profile"]; report["model_identity"]=ready["model"]["identity"]
            checked("secure_session_cookie",any(c["name"]=="__Host-bublik_session" and c["secure"] and c["httpOnly"] and c["sameSite"]=="Strict" for c in await desktop.cookies()))
            await page.locator("#new-chat").click(); await page.locator("#new-title").fill("UI check "+report["run_id"])
            await page.locator("#create-form button[type=submit]").click()
            await expect(page.locator("#chat-title")).to_have_text("UI check "+report["run_id"])
            chat=page.url.split("#chat=")[1]; report["created_chat_id"]=chat
            await turn(page,"Запомни секретное слово: мандарин. Ответь только: принято","принято")
            await page.reload(); await expect(page.locator(".message")).to_have_count(2)
            checked("desktop_reload_same_history")
            await login(phone,chat); await expect(phone.locator(".message")).to_have_count(2)
            checked("second_browser_session_same_chat")
            await turn(phone,"Какое секретное слово я попросил запомнить? Ответь только этим словом.","мандарин")
            await page.locator("#refresh-chat").click(); await expect(page.locator(".message")).to_have_count(4)
            checked("desktop_receives_phone_turn")
            await turn(page,"Ответь только: OK","OK")
            await phone.locator("#refresh-chat").click(); await expect(phone.locator(".message")).to_have_count(6)
            checked("phone_receives_desktop_turn")
            checked("successful_sse_connection",200 in stream_statuses)
            checked("no_browser_storage",await page.evaluate("localStorage.length===0 && sessionStorage.length===0") and await phone.evaluate("localStorage.length===0 && sessionStorage.length===0"))
            checked("mobile_viewport_no_horizontal_overflow",await phone.evaluate("document.documentElement.scrollWidth<=innerWidth"))
            await page.locator("#logout").click(); await expect(page.locator("#login-screen")).to_be_visible()
            checked("logout_clears_private_view",await page.locator("#messages .message").count()==0)
            checked("no_external_requests",not external); checked("no_javascript_errors",not errors)
        finally:
            await browser.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url",default="https://localhost:8443")
    parser.add_argument("--username",required=True)
    parser.add_argument("--ca-file",type=Path,required=True,help="Self-signed localhost certificate from STAGE4")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    parsed=urlsplit(args.url)
    if parsed.scheme!="https" or parsed.hostname not in {"localhost","127.0.0.1","::1"} or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        parser.error("Only canonical loopback HTTPS origins are supported at stage 5")
    try:
        import playwright.async_api
        certificate_pin(args.ca_file)
    except ImportError:
        parser.error("Install requirements.browser.lock; python -m playwright install chromium")
    except Exception:
        parser.error("Cannot read the public localhost certificate")
    stamp=datetime.now(timezone.utc); run_id=stamp.strftime("%Y%m%dT%H%M%S")+"-"+uuid.uuid4().hex[:8]
    output=args.output or ROOT/"reports/check"/("stage5-ui-live-"+run_id+".json")
    output.parent.mkdir(parents=True,exist_ok=True)
    source=manifest()
    report={"format":"bublik-stage5-ui-live-v1","run_id":run_id,"created_at":stamp.isoformat(),"status":"failed",
      "source_sha256":source,"checks":[],"answers_sha256":[],"generations":[],
      "environment":{"python":platform.python_version(),"system":platform.system(),"machine":platform.machine(),"playwright":importlib.metadata.version("playwright")},
      "evidence":"Real Chromium desktop/mobile viewport and live service+Qwen. HTTPS preflight verifies certificate+hostname; Chromium pins only the supplied self-signed certificate SPKI.",
      "not_run":["physical phone","Safari/iOS/Android browser hardware","LAN","mobile internet","API restart during browser generation","physical RAM/CPU"]}
    with output.open("x",encoding="utf-8") as stream:
        started=time.perf_counter()
        try:
            password=getpass.getpass("Account password: ")
            asyncio.run(run(args,report,password))
            report["source_unchanged"]=source==manifest()
            if report["checks"] and all(c["passed"] for c in report["checks"]) and report["source_unchanged"]: report["status"]="passed"
        except (KeyboardInterrupt,EOFError): report["error_code"]="operator_interrupted"
        except Exception as error:
            report["error_code"]="live_browser_check_failed"; report["failure_type"]=type(error).__name__
        report["elapsed_seconds"]=time.perf_counter()-started
        json.dump(report,stream,ensure_ascii=False,indent=2); stream.write("\n")
    print(json.dumps({"report":str(output),"status":report["status"]}))
    return 0 if report["status"]=="passed" else 1


if __name__=="__main__": sys.exit(main())
