"""Real Chromium + isolated TLS/SQLite/synthetic inference. NOT Qwen or phone proof."""
import argparse
import asyncio
import base64
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import uuid

from check_storage import ROOT,manifest


def certificate_pin(cert):
    public=subprocess.run(["openssl","x509","-in",str(cert),"-pubkey","-noout"],capture_output=True,check=True).stdout
    der=subprocess.run(["openssl","pkey","-pubin","-outform","DER"],input=public,capture_output=True,check=True).stdout
    return base64.b64encode(hashlib.sha256(der).digest()).decode()


async def run(report,root,screenshot_dir=None):
    from playwright.async_api import async_playwright,expect
    import httpx
    import ssl
    sys.path.insert(0,str(ROOT/"tests"))
    from browser_fixture import BrowserFixture,PASSWORD
    fixture=BrowserFixture(root)
    report["checks"]=[]
    def checked(name,condition=True):
        report["checks"].append({"name":name,"passed":bool(condition)})
        if not condition:
            raise ValueError(name)
    # Verify the certificate normally over a real socket before the browser pin.
    try:
        async with httpx.AsyncClient(verify=ssl.create_default_context(cafile=str(fixture.cert)),trust_env=False) as client:
            checked("verified_tls_preflight",(await client.get(fixture.url+"/api/v1/health/live")).status_code==200)
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(args=["--ignore-certificate-errors-spki-list="+certificate_pin(fixture.cert)])
            report["environment"]["browser"]=browser.version
            desktop=await browser.new_context(viewport={"width":1280,"height":850})
            mobile=await browser.new_context(viewport={"width":390,"height":844},is_mobile=True,has_touch=True)
            page=await desktop.new_page(); phone=await mobile.new_page()
            external=[]; errors=[]
            for target in (page,phone):
                target.on("request",lambda req: external.append(True) if not req.url.startswith(fixture.url+"/") else None)
                target.on("pageerror",lambda _:errors.append(True))
            async def login(target,username="ui-test"):
                await target.goto(fixture.url)
                await expect(target.locator("#login-button")).to_be_enabled()
                await target.locator("#username").fill(username)
                await target.locator("#password").fill(PASSWORD)
                await target.locator("#login-button").click()
                await expect(target.locator("#workspace")).to_be_visible()
                await expect(target.locator("#model-status")).to_contain_text("готова")
            async def send(target,content):
                await expect(target.locator("#message-input")).to_be_enabled()
                await target.locator("#message-input").fill(content)
                await expect(target.locator("#send-button")).to_be_enabled()
                await target.locator("#send-button").click()
            async def completed(target,content):
                await expect(target.locator(".message.user .message-text").last).to_have_text(content,timeout=20000)
                await expect(target.locator(".message.assistant").last).to_have_attribute("data-state","completed",timeout=20000)
                await expect(target.locator(".message.assistant .message-text").last).to_have_text("Synthetic reply: "+content,timeout=20000)
            await login(page)
            checked("desktop_login")
            cookies=await desktop.cookies()
            checked("cookie_secure_httponly_strict",any(c["name"]=="__Host-bublik_session" and c["secure"] and c["httpOnly"] and c["sameSite"]=="Strict" for c in cookies))
            await page.locator("#chat-list .chat-item").first.click()
            await expect(page.locator(".message")).to_have_count(50)
            await page.locator("#older-messages").click(); await expect(page.locator(".message")).to_have_count(100)
            await page.locator("#older-messages").click(); await expect(page.locator(".message")).to_have_count(120)
            checked("recent_page_and_older_history",await page.locator(".message .message-text").first.inner_text()=="seed 0")
            await page.locator("#new-chat").click(); await page.locator("#new-title").fill("Браузерная проверка")
            await page.locator("#create-form button[type=submit]").click()
            await expect(page.locator("#chat-title")).to_have_text("Браузерная проверка")
            chat=page.url.split("#chat=")[1]
            await send(page,"first")
            await expect(page.locator(".message.assistant .message-text").last).to_contain_text("Synthetic",timeout=10000)
            checked("persisted_stream_snapshot_visible")
            await completed(page,"first")
            await page.reload(); await expect(page.locator(".message")).to_have_count(2)
            checked("reopen_saved_chat_without_new_inference",fixture.adapter.calls==1)
            # Commit the POST, deliberately lose its response, then replay same key.
            keys=[]
            async def lost_response(route):
                keys.append(route.request.headers.get("idempotency-key"))
                async with httpx.AsyncClient(verify=ssl.create_default_context(cafile=str(fixture.cert)),trust_env=False) as committed:
                    await committed.post(route.request.url,content=route.request.post_data_buffer,headers=route.request.headers)
                await route.abort()
            path=f"**/api/v1/chats/{chat}/messages"
            await page.route(path,lost_response)
            await send(page,"lost-response")
            await expect(page.locator("#delivery-notice")).to_be_visible()
            await page.unroute(path,lost_response)
            async def remember(route):
                keys.append(route.request.headers.get("idempotency-key")); await route.continue_()
            await page.route(path,remember)
            await page.locator("#replay-request").click()
            await expect(page.locator("#delivery-notice")).to_be_hidden()
            await completed(page,"lost-response")
            await page.unroute(path,remember)
            checked("lost_response_same_key_no_duplicate",len(keys)==2 and keys[0]==keys[1] and len(fixture.repo.history(fixture.owner,chat))==4 and fixture.adapter.calls==2)
            # Disable SSE, proving the polling fallback against the real API.
            await page.route("**/events",lambda route:route.abort())
            await send(page,"poll-fallback"); await completed(page,"poll-fallback")
            await page.unroute("**/events")
            checked("sse_failure_polling_fallback")
            await send(page,"FAIL_ONCE")
            await expect(page.locator(".message.assistant").last).to_have_attribute("data-state","failed")
            await expect(page.locator("#retry-generation")).to_be_enabled()
            await page.locator("#retry-generation").click(); await completed(page,"FAIL_ONCE")
            checked("failed_generation_retry_same_question",sum(m["role"]=="user" and m["content"]=="FAIL_ONCE" for m in fixture.repo.history(fixture.owner,chat))==1)
            before=len(fixture.repo.history(fixture.owner,chat))
            await send(page,"x"*8000)
            await expect(page.locator("#app-status")).to_contain_text("не помещается")
            checked("context_rejection_preserves_draft_and_history",await page.locator("#message-input").input_value()=="x"*8000 and len(fixture.repo.history(fixture.owner,chat))==before)
            await page.locator("#message-input").fill("я"*9000)
            await expect(page.locator("#send-button")).to_be_disabled()
            checked("utf8_size_limit_before_submission")
            await page.locator("#message-input").fill("")
            await login(phone); await phone.goto(fixture.url+"/#chat="+chat)
            await expect(phone.locator(".message")).to_have_count(before)
            checked("second_device_same_saved_chat")
            # A second client advances revision; first client must explicitly resend after 409.
            release=asyncio.Event()
            async def delayed_metadata(route):
                await release.wait(); await route.continue_()
            metadata_path=f"**/api/v1/chats/{chat}"
            await page.route(metadata_path,delayed_metadata)
            await send(phone,"phone-turn"); await completed(phone,"phone-turn")
            await send(page,"after-phone")
            await expect(page.locator("#app-status")).to_contain_text("другом устройстве")
            release.set()
            await expect(page.locator(".message.user .message-text").last).to_have_text("phone-turn")
            await page.unroute(metadata_path,delayed_metadata)
            checked("stale_revision_requires_review",await page.locator("#message-input").input_value()=="after-phone")
            await send(page,"after-phone"); await completed(page,"after-phone")
            payload='<img src=x onerror="window.privateXss=1"> **literal**'
            await send(page,payload); await completed(page,payload)
            checked("model_text_does_not_execute_html",await page.locator("#messages img").count()==0 and await page.evaluate("window.privateXss===undefined"))
            count=len(fixture.repo.history(fixture.owner,chat))
            fixture.auth.generation_limit=1
            await send(page,"quota-check")
            await expect(page.locator("#app-status")).to_contain_text("лимит запросов")
            checked("rate_limit_does_not_write_or_auto_retry",len(fixture.repo.history(fixture.owner,chat))==count and await page.locator("#message-input").input_value()=="quota-check")
            fixture.auth.generation_limit=10
            await page.locator("#message-input").fill("")
            await phone.locator("#refresh-chat").click()
            await expect(phone.locator(".message.assistant .message-text").last).to_have_text("Synthetic reply: "+payload)
            for width in (390,320):
                await phone.set_viewport_size({"width":width,"height":844})
                checked("mobile_no_horizontal_overflow_"+str(width),await phone.evaluate("document.documentElement.scrollWidth<=innerWidth"))
            await phone.locator("#menu-button").click(); await expect(phone.locator("#sidebar")).to_be_visible()
            await phone.locator("#drawer-backdrop").click(position={"x":width-10,"y":300})
            await expect(phone.locator("#sidebar")).to_be_hidden(); checked("mobile_navigation")
            await phone.set_viewport_size({"width":390,"height":844})
            if screenshot_dir:
                screenshot_dir.mkdir(parents=True,exist_ok=True)
                await page.screenshot(path=str(screenshot_dir/"desktop.png"))
                await phone.screenshot(path=str(screenshot_dir/"mobile.png"))
            checked("no_browser_storage_of_chat_or_credentials",await page.evaluate("localStorage.length===0 && sessionStorage.length===0") and await phone.evaluate("localStorage.length===0 && sessionStorage.length===0"))
            fixture.adapter.available=False; fixture.app.state.ready_cache=None
            await page.locator("#refresh-chat").click(); await expect(page.locator("#model-status")).to_contain_text("недоступна")
            checked("model_outage_history_readable",await page.locator(".message").count()>0)
            fixture.adapter.available=True; fixture.app.state.ready_cache=None
            await page.locator("#refresh-chat").click(); await expect(page.locator("#model-status")).to_contain_text("готова")
            checked("model_readiness_recovers")
            fixture.auth.set_password(fixture.owner,PASSWORD)
            await page.locator("#refresh-chat").click(); await expect(page.locator("#login-screen")).to_be_visible()
            checked("revocation_clears_private_dom",await page.locator("#messages .message").count()==0 and await page.locator("#message-input").input_value()=="")
            await login(page,"other")
            checked("different_owner_does_not_see_chats",await page.locator("#chat-list .chat-item").count()==0 and await page.locator("#messages .message").count()==0)
            await page.locator("#logout").click(); await expect(page.locator("#login-screen")).to_be_visible()
            checked("logout_clears_private_dom")
            checked("no_external_requests",not external); checked("no_javascript_errors",not errors)
            await browser.close()
    finally:
        fixture.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--screenshots",type=Path,help="Synthetic fixture screenshots only; new directory")
    args=parser.parse_args()
    try:
        import playwright.async_api
    except ImportError:
        parser.error("Install optional requirements.browser.lock and run python -m playwright install chromium")
    if args.screenshots and args.screenshots.exists():
        parser.error("Screenshot directory must not exist")
    stamp=datetime.now(timezone.utc)
    run_id=stamp.strftime("%Y%m%dT%H%M%S")+"-"+uuid.uuid4().hex[:8]
    output=args.output or ROOT/"reports/check"/("stage5-browser-"+run_id+".json")
    output.parent.mkdir(parents=True,exist_ok=True)
    source=manifest()
    report={"format":"bublik-stage5-browser-fixture-v1","run_id":run_id,"created_at":stamp.isoformat(),"status":"failed",
      "source_sha256":source,"environment":{"python":platform.python_version(),"system":platform.system(),
        "machine":platform.machine(),"playwright":importlib.metadata.version("playwright")},
      "evidence":"Real Chromium desktop/mobile viewport + loopback TLS/SQLite; synthetic inference only. Chromium trusts only the fixture SPKI pin; independent HTTPS preflight verifies certificate+hostname.",
      "not_run":["real Qwen in browser","Safari/iOS/Android hardware","LAN","mobile internet","physical RAM/CPU"]}
    with output.open("x",encoding="utf-8") as stream:
        started=time.perf_counter()
        try:
            with tempfile.TemporaryDirectory(prefix="bublik-ui-fixture-") as root:
                asyncio.run(run(report,root,args.screenshots))
            report["source_unchanged"]=source==manifest()
            if report["checks"] and all(c["passed"] for c in report["checks"]) and report["source_unchanged"]:
                report["status"]="passed"
        except KeyboardInterrupt:
            report["error_code"]="operator_interrupted"
        except Exception as error:
            report["error_code"]="browser_check_failed"
            report["failure_type"]=type(error).__name__
            # Never store browser traces, screenshots of credentials, request bodies or secrets.
        report["elapsed_seconds"]=time.perf_counter()-started
        json.dump(report,stream,ensure_ascii=False,indent=2); stream.write("\n")
    print(json.dumps({"report":str(output),"status":report["status"]}))
    return 0 if report["status"]=="passed" else 1


if __name__=="__main__":
    sys.exit(main())
