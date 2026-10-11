"""Real Chromium/HTTPS UI fixture; synthetic inference, not real Qwen/phones."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time

from check_storage import ROOT, manifest
from check_web_ui import certificate_pin


async def run(record, root):
    from playwright.async_api import async_playwright, expect
    sys.path.insert(0,str(ROOT/'tests'))
    from browser_fixture import BrowserFixture, PASSWORD
    fixture=BrowserFixture(root)
    source=fixture.repo.history(fixture.owner,fixture.seed)[0]
    statement='My laptop is a MacBook Pro M1. <script>window.memoryLeak=true</script>'
    # Synthetic fixture setup before any index/search; not production editing.
    with fixture.repo.database.connect(write=True) as db:
        db.execute('UPDATE messages SET content=? WHERE id=?',(statement,source['id']))
    try:
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(args=['--ignore-certificate-errors-spki-list='+certificate_pin(fixture.cert)])
            context=await browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
            page=await context.new_page()
            errors=[];external=[]
            page.on('pageerror',lambda _:errors.append(True))
            page.on('request',lambda r:external.append(True) if not r.url.startswith(fixture.url+'/') else None)
            await page.goto(fixture.url)
            await expect(page.locator('#login-button')).to_be_enabled()
            await page.locator('#username').fill('ui-test')
            await page.locator('#password').fill(PASSWORD)
            await page.locator('#login-button').click()
            await expect(page.locator('#workspace')).to_be_visible()
            await page.locator('#menu-button').click()
            await page.locator('#new-chat').click()
            await page.locator('#new-title').fill('RAG browser fixture')
            await page.locator('#create-form button[type=submit]').click()
            await expect(page.locator('#message-input')).to_be_enabled()
            record('memory_on_by_default',await page.locator('#use-memory').is_checked())
            await page.locator('#message-input').fill('What laptop did I mention?')
            await page.locator('#send-button').click()
            await expect(page.locator('.message.assistant .message-state')).to_have_text('Ответ сохранён',timeout=15000)
            await expect(page.locator('.memory-sources')).to_have_count(1)
            await page.locator('.memory-sources summary').click()
            await expect(page.locator('.memory-sources blockquote')).to_contain_text('MacBook')
            record('source_displayed_on_mobile',True)
            record('citation_is_literal_text',await page.evaluate('window.memoryLeak!==true'))
            rag_url=page.url
            await page.locator('#use-memory').uncheck()
            record('memory_can_be_explicitly_disabled',not await page.locator('#use-memory').is_checked())
            await page.reload()
            await expect(page.locator('.memory-sources')).to_have_count(1)
            record('saved_sources_survive_reload',True)
            record('memory_switch_resets_without_web_storage',await page.locator('#use-memory').is_checked()
                   and await page.evaluate('localStorage.length===0 && sessionStorage.length===0'))
            await page.locator('.memory-sources summary').click()
            await page.locator('.memory-sources a').first.click()
            await expect(page.locator('#source-preview')).to_be_visible()
            await expect(page.locator('#source-preview')).to_contain_text(statement)
            record('old_source_beyond_latest_page_opens',await page.locator('.message').count()==50)
            record('source_preview_is_literal_text',await page.evaluate('window.memoryLeak!==true'))
            record('no_horizontal_mobile_overflow',await page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
            await page.locator('#menu-button').click()
            await page.locator('#logout').click()
            await expect(page.locator('#login-screen')).to_be_visible()
            record('logout_clears_private_source_preview',await page.locator('#source-preview').text_content()=='')
            record('no_external_requests_or_js_errors',not errors and not external)
            await context.close();await browser.close()
    finally:
        fixture.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        import playwright.async_api
    except ImportError:
        parser.error('Optional requirements.browser.lock and Chromium are required')
    args.output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    try:
        fd=os.open(args.output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except OSError:
        parser.error('NEW writable report path required')
    before=manifest()
    report={'format':'bublik-offline-check-v2','scope':'rag-Chromium-mobile-viewport-HTTPS-synthetic-inference',
            'created_at':datetime.now(timezone.utc).isoformat(),'status':'failed','tests':[],
            'not_run':['real Qwen','physical Android/iPhone','mobile internet','semantic memory quality']}
    def record(name,passed):
        report['tests'].append({'id':name,'status':'passed' if passed else 'failed'})
        if not passed:raise RuntimeError('controlled_check_failed')
    started=time.monotonic()
    with os.fdopen(fd,'w',encoding='utf-8') as stream:
        try:
            with tempfile.TemporaryDirectory(prefix='bublik-rag-browser-') as root:
                asyncio.run(run(record,root))
            report['status']='passed'
        except Exception as error:
            report['error_type']=type(error).__name__
        unchanged=before==manifest()
        if not unchanged:report['status']='failed'
        report['source']={'unchanged_during_run':unchanged,'source_sha256':before}
        report['summary']={'tests':len(report['tests']),'failures':sum(t['status']!='passed' for t in report['tests']),
                           'errors':int('error_type' in report),'skipped':0,'elapsed_seconds':time.monotonic()-started}
        json.dump(report,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps({'report':str(args.output),'status':report['status']}))
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':
    sys.exit(main())
