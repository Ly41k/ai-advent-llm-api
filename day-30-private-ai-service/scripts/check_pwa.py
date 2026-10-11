"""Real Chromium/TLS synthetic fixture; no claim of OS PWA installation."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import ssl
import sys
import tempfile
import time
import uuid

import httpx

from check_storage import ROOT, manifest
from check_web_ui import certificate_pin


async def run(report, root):
    from playwright.async_api import async_playwright, expect
    sys.path.insert(0, str(ROOT/"tests"))
    from browser_fixture import BrowserFixture, PASSWORD
    fixture = BrowserFixture(root)
    def check(name, value=True):
        report["checks"].append({"name": name, "passed": bool(value)})
        if not value: raise ValueError("controlled_check_failed")
    try:
        async with httpx.AsyncClient(verify=ssl.create_default_context(cafile=str(fixture.cert)),trust_env=False) as client:
            check("verified_tls_preflight", (await client.get(fixture.url+"/api/v1/health/live")).status_code == 200)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(args=["--ignore-certificate-errors-spki-list="+certificate_pin(fixture.cert)])
            report["browser"] = browser.version
            context = await browser.new_context(viewport={"width":390,"height":844},is_mobile=True,has_touch=True)
            page = await context.new_page()
            errors, external = [], []
            page.on("pageerror",lambda _: errors.append(True))
            page.on("request",lambda r: external.append(True) if not r.url.startswith(fixture.url+"/") else None)
            await page.goto(fixture.url)
            await expect(page.locator("#login-button")).to_be_enabled()
            check("manifest_link", await page.locator('link[rel="manifest"]').get_attribute("href") == "/manifest.webmanifest")
            value = await page.evaluate("async () => {const r=await fetch('/manifest.webmanifest');return {type:r.headers.get('content-type'),cache:r.headers.get('cache-control'),manifest:await r.json()};}")
            check("same_origin_standalone_manifest", "application/manifest+json" in value["type"]
                and value["cache"] == "no-store" and value["manifest"]["display"] == "standalone"
                and value["manifest"]["scope"] == value["manifest"]["start_url"] == "/")
            for size in (180,192,512):
                dimensions = await page.evaluate("size => new Promise((resolve,reject)=>{const i=new Image();i.onload=()=>resolve([i.naturalWidth,i.naturalHeight]);i.onerror=reject;i.src='/assets/icon-'+size+'.png';})", size)
                check("decoded_icon_"+str(size), dimensions == [size,size])
            await page.locator("#username").fill("ui-test")
            await page.locator("#password").fill(PASSWORD)
            await page.locator("#login-button").click()
            await expect(page.locator("#workspace")).to_be_visible()
            await page.goto(fixture.url+"/#chat="+fixture.seed)
            await expect(page.locator(".message")).to_have_count(50)
            privacy = await page.evaluate("async()=>({workers:(await navigator.serviceWorker.getRegistrations()).length,caches:await caches.keys(),local:localStorage.length,session:sessionStorage.length})")
            check("no_worker_cache_or_web_storage",privacy == {"workers":0,"caches":[],"local":0,"session":0})
            await context.set_offline(True)
            result = await page.evaluate("async()=>{try {await fetch('/api/v1/chats',{cache:'no-store'});return false;} catch {return true;}}")
            check("offline_private_api_not_available_from_cache",result)
            await context.set_offline(False)
            await page.reload()
            await expect(page.locator(".message")).to_have_count(50)
            first_page = fixture.repo.history(fixture.owner,fixture.seed,limit=100)
            second_page = fixture.repo.history(fixture.owner,fixture.seed,after_sequence=first_page[-1]["sequence"],limit=100)
            check("online_reopen_preserves_server_history",len(first_page)+len(second_page) == 120 and fixture.adapter.calls == 0)
            await page.locator("#menu-button").click()
            await page.locator("#logout").click()
            await expect(page.locator("#login-screen")).to_be_visible()
            check("logout_clears_displayed_history",await page.locator(".message").count() == 0)
            check("no_external_requests_or_js_errors",not external and not errors)
            await context.close()
            await browser.close()
    finally:
        fixture.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    report={"format":"bublik-stage7-pwa-fixture-v1","run_id":uuid.uuid4().hex,
            "created_at":datetime.now(timezone.utc).isoformat(),"status":"failed","checks":[],
            "source_sha256":manifest(),"system":platform.system(),"python":platform.python_version(),
            "evidence":"Real Chromium, verified loopback TLS preflight and browser leaf SPKI pin, real SQLite; synthetic inference fixture. No OS installation or physical phone proof.",
            "not_run":["Android/iOS home-screen installation","normal phone certificate trust","Mac launchd/reboot","real Qwen"]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as stream:
        start=time.perf_counter()
        try:
            with tempfile.TemporaryDirectory() as tmp: asyncio.run(run(report,Path(tmp)))
            report["source_unchanged"]=report["source_sha256"]==manifest()
            if report["source_unchanged"] and all(c["passed"] for c in report["checks"]):report["status"]="passed"
        except Exception as error:
            report["error_code"]="pwa_fixture_failed";report["failure_type"]=type(error).__name__
        report["elapsed_seconds"]=time.perf_counter()-start
        json.dump(report,stream,indent=2,ensure_ascii=False);stream.write("\n")
    print(json.dumps({"report":str(args.output),"status":report["status"]}))
    return 0 if report["status"]=="passed" else 1


if __name__=="__main__": sys.exit(main())
